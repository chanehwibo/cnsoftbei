from __future__ import annotations

import hmac
import json
import os
import secrets
import ssl
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.config import WEB_ROOT, load_app_config, resolve_project_path
from safeops_agent.llm import get_provider
from safeops_agent.mcp_server import McpToolService


APP_CONFIG = load_app_config()
AUDIT_PATH = resolve_project_path(APP_CONFIG["audit_log"])

_audit_logger = AuditLogger(AUDIT_PATH, source="web")
_mcp = McpToolService()

# 会话隔离：每个浏览器会话独立的 Agent 实例（对话历史、指代上下文互不串扰），
# 且各会话独立加锁——一个会话的慢 LLM 调用不再阻塞其他会话。
MAX_SESSIONS = 64
_sessions: dict[str, dict] = {}
_sessions_guard = threading.Lock()


def _session_key(raw: str | None) -> str:
    if not raw:
        return "default"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    cleaned = "".join(char for char in raw if char in allowed)[:64]
    return cleaned or "default"


def _get_session(session_key: str) -> tuple[SafeOpsAgent, threading.Lock]:
    with _sessions_guard:
        entry = _sessions.get(session_key)
        if entry is None:
            if len(_sessions) >= MAX_SESSIONS:
                oldest = min(_sessions, key=lambda key: _sessions[key]["last_used"])
                _sessions.pop(oldest, None)
            entry = {
                "agent": SafeOpsAgent(audit_logger=_audit_logger, session_id=f"web:{session_key}"),
                "lock": threading.Lock(),
                "last_used": time.monotonic(),
            }
            _sessions[session_key] = entry
        entry["last_used"] = time.monotonic()
        return entry["agent"], entry["lock"]

API_TOKEN: str = os.environ.get("SAFEOPS_TOKEN", "")
RATE_LIMIT_MAX: int = 30
RATE_LIMIT_WINDOW: int = 60
MAX_BODY_SIZE: int = 65536
ACCESS_LOG: bool = os.environ.get("SAFEOPS_ACCESS_LOG", "0") == "1"
CORS_ORIGIN: str = os.environ.get("SAFEOPS_CORS_ORIGIN", "")
AUTH_SESSION_TTL: int = 8 * 60 * 60
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
SECURE_TRANSPORT: bool = bool(APP_CONFIG.get("tls_enabled")) or os.environ.get(
    "SAFEOPS_BEHIND_HTTPS_PROXY", ""
) == "1"


class _WebSessionAuth:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, float] = {}

    def login(self, token: str) -> str | None:
        if not API_TOKEN or not hmac.compare_digest(token, API_TOKEN):
            return None
        session = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[session] = time.time() + AUTH_SESSION_TTL
        return session

    def valid(self, session: str) -> bool:
        if not session:
            return False
        now = time.time()
        with self._lock:
            expires = self._sessions.get(session, 0)
            if expires <= now:
                self._sessions.pop(session, None)
                return False
            return True


_session_auth = _WebSessionAuth()


class _RateLimiter:
    def __init__(self, max_requests: int = RATE_LIMIT_MAX, window: int = RATE_LIMIT_WINDOW) -> None:
        self._max = max_requests
        self._window = window
        self._lock = threading.Lock()
        self._buckets: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = self._buckets.get(key, [])
            timestamps = [t for t in timestamps if now - t < self._window]
            if len(timestamps) >= self._max:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            if len(self._buckets) > 1000:
                self._buckets = {
                    k: v for k, v in self._buckets.items()
                    if v and now - v[-1] < self._window
                }
            return True


_limiter = _RateLimiter()


class _SSEBroadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[threading.Event] = []

    def subscribe(self) -> threading.Event:
        event = threading.Event()
        with self._lock:
            self._events.append(event)
        return event

    def unsubscribe(self, event: threading.Event) -> None:
        with self._lock:
            try:
                self._events.remove(event)
            except ValueError:
                pass

    def notify(self) -> None:
        with self._lock:
            for event in self._events:
                event.set()


_sse = _SSEBroadcaster()
_shutdown_event = threading.Event()


class SafeOpsWebHandler(BaseHTTPRequestHandler):
    server_version = "SafeOpsWeb/0.1"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if SECURE_TRANSPORT:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        if CORS_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _check_auth(self) -> bool:
        if not API_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {API_TOKEN}"
        if hmac.compare_digest(auth, expected):
            return True
        cookie_header = self.headers.get("Cookie", "")
        cookies = {}
        for item in cookie_header.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookies[key] = value
        if _session_auth.valid(cookies.get("SafeOps-Session", "")):
            return True
        self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def _check_rate_limit(self) -> bool:
        client_ip = self.client_address[0]
        if _limiter.allow(client_ip):
            return True
        self._json({"ok": False, "error": "rate limit exceeded"}, HTTPStatus.TOO_MANY_REQUESTS)
        return False

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json({"ok": True, "service": "safeops-web"})
            return
        if path == "/api/auth/status":
            self._json({"ok": True, "required": bool(API_TOKEN)})
            return
        if not path.startswith("/api/"):
            self._serve_static(path)
            return
        if path == "/api/events":
            if not self._check_auth() or not self._check_rate_limit():
                return
            self._serve_sse()
            return
        if not self._check_auth() or not self._check_rate_limit():
            return
        if path == "/api/tools":
            self._json({"ok": True, "tools": _mcp.list_tools()})
            return
        if path == "/api/audit":
            params = parse_qs(urlparse(self.path).query)

            def _filter(name: str) -> str | None:
                value = params.get(name, [""])[0].strip()
                return value or None

            try:
                limit = int(params.get("limit", ["20"])[0])
            except (ValueError, TypeError):
                limit = 20
            events = _audit_logger.query(
                limit=limit,
                source=_filter("source"),
                risk=_filter("risk"),
                tool=_filter("tool"),
            )
            self._json({"ok": True, "events": events})
            return
        if path == "/api/audit/verify":
            report = _audit_logger.verify()
            self._json({"ok": report["ok"], "report": report})
            return
        if path == "/api/audit/export":
            self._serve_audit_export()
            return
        self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/auth":
            if not self._check_rate_limit():
                return
            self._serve_login()
            return
        if not self._check_auth() or not self._check_rate_limit():
            return
        if path != "/api/agent":
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except (ValueError, TypeError):
            self._json({"ok": False, "error": "invalid content-length"}, HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0:
            self._json({"ok": False, "error": "invalid content-length"}, HTTPStatus.BAD_REQUEST)
            return
        if content_length > MAX_BODY_SIZE:
            self._json({"ok": False, "error": "request body too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._json({"ok": False, "error": "json body must be an object"}, HTTPStatus.BAD_REQUEST)
            return

        request = str(payload.get("request", "")).strip()
        action_id = str(payload.get("action_id", "")).strip()
        if not request and not action_id:
            self._json({"ok": False, "error": "request or action_id is required"}, HTTPStatus.BAD_REQUEST)
            return

        session_key = _session_key(self.headers.get("X-Session-Id"))
        agent, agent_lock = _get_session(session_key)
        with agent_lock:
            if action_id:
                response = agent.confirm(action_id)
            else:
                response = agent.handle(request)
        _sse.notify()
        self._json(
            {
                "ok": response.ok,
                "message": response.message,
                "tool": response.tool,
                "risk": None if response.risk is None else response.risk.value,
                "risk_score": response.risk_score,
                "decision_summary": response.decision_summary,
                "data": response.data,
                "requires_confirmation": response.requires_confirmation,
                "decision_trace": response.reasoning_chain,
                "reasoning_chain": response.reasoning_chain,
                "pending_action_id": response.pending_action_id,
            },
            HTTPStatus.OK if response.ok else HTTPStatus.ACCEPTED,
        )

    def _serve_login(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except (ValueError, TypeError):
            self._json({"ok": False, "error": "invalid content-length"}, HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0 or content_length > MAX_BODY_SIZE:
            self._json({"ok": False, "error": "invalid request body size"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._json({"ok": False, "error": "json body must be an object"}, HTTPStatus.BAD_REQUEST)
            return
        if not API_TOKEN:
            self._json({"ok": True, "required": False})
            return
        session = _session_auth.login(str(payload.get("token", "")))
        if session is None:
            self._json({"ok": False, "error": "invalid token"}, HTTPStatus.UNAUTHORIZED)
            return
        cookie = (
            f"SafeOps-Session={session}; HttpOnly; SameSite=Strict; "
            f"Path=/; Max-Age={AUTH_SESSION_TTL}"
        )
        if SECURE_TRANSPORT:
            cookie += "; Secure"
        data = json.dumps({"ok": True, "required": True}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        if ACCESS_LOG:
            client_ip = self.client_address[0]
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {client_ip} {format % args}")

    def _serve_sse(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        event = _sse.subscribe()
        try:
            while not _shutdown_event.is_set():
                event.wait(timeout=15)
                if _shutdown_event.is_set():
                    break
                if event.is_set():
                    event.clear()
                    recent = _audit_logger.recent(1)
                    data = json.dumps(recent[-1] if recent else {}, ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                else:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            _sse.unsubscribe(event)

    def _serve_audit_export(self) -> None:
        events = _audit_logger.recent(200)
        report = {
            "report": "SafeOps 审计报告",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "total_events": len(events),
            "events": events,
            "summary": {
                "allowed": sum(1 for e in events if e.get("allowed")),
                "denied": sum(1 for e in events if not e.get("allowed", True)),
                "high_risk": sum(1 for e in events if e.get("risk") == "HIGH"),
                "medium_risk": sum(1 for e in events if e.get("risk") == "MEDIUM"),
                "low_risk": sum(1 for e in events if e.get("risk") == "LOW"),
            },
        }
        data = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=safeops_audit_report.json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        relative = path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if not target.is_relative_to(WEB_ROOT.resolve()) or not target.is_file():
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if target.suffix in (".css", ".js"):
            self.send_header("Cache-Control", "public, max-age=3600")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _build_server(host: str, port: int, config: dict | None = None) -> tuple[ThreadingHTTPServer, str]:
    active = APP_CONFIG if config is None else config
    tls_enabled = bool(active.get("tls_enabled"))
    if host not in LOOPBACK_HOSTS and not tls_enabled:
        raise RuntimeError("TLS is required when Web host is not loopback")

    server = ThreadingHTTPServer((host, port), SafeOpsWebHandler)
    if not tls_enabled:
        return server, "http"

    cert_path = resolve_project_path(str(active.get("tls_cert_file", "")))
    key_path = resolve_project_path(str(active.get("tls_key_file", "")))
    if not cert_path.is_file() or not key_path.is_file():
        server.server_close()
        raise RuntimeError("TLS certificate or private key file does not exist")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server, "https"


def main() -> int:
    host = str(APP_CONFIG["web_host"])
    port = int(APP_CONFIG["web_port"])
    if (bool(APP_CONFIG.get("require_auth")) or host not in LOOPBACK_HOSTS) and not API_TOKEN:
        raise RuntimeError("SAFEOPS_TOKEN is required when Web authentication is enabled or host is not loopback")
    server, scheme = _build_server(host, port)
    print(f"SafeOps Web running at {scheme}://{host}:{port}", flush=True)
    print(f"LLM 意图理解：{get_provider().describe()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown_event.set()
        _sse.notify()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
