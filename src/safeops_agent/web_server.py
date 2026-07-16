from __future__ import annotations

import hmac
import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.config import load_app_config, resolve_project_path
from safeops_agent.llm import get_provider
from safeops_agent.mcp_server import McpToolService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"
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
        if CORS_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _check_auth(self, allow_query_token: bool = False) -> bool:
        if not API_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {API_TOKEN}"
        if hmac.compare_digest(auth, expected):
            return True
        if allow_query_token:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            token = params.get("token", [""])[0]
            if token and hmac.compare_digest(token, API_TOKEN):
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
        if not path.startswith("/api/"):
            self._serve_static(path)
            return
        if path == "/api/events":
            if not self._check_auth(allow_query_token=True) or not self._check_rate_limit():
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
        if not self._check_auth() or not self._check_rate_limit():
            return
        path = urlparse(self.path).path
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
                "reasoning_chain": response.reasoning_chain,
                "pending_action_id": response.pending_action_id,
            },
            HTTPStatus.OK if response.ok else HTTPStatus.ACCEPTED,
        )

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


def main() -> int:
    host = str(APP_CONFIG["web_host"])
    port = int(APP_CONFIG["web_port"])
    server = ThreadingHTTPServer((host, port), SafeOpsWebHandler)
    print(f"SafeOps Web running at http://{host}:{port}", flush=True)
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
