from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.config import load_app_config, resolve_project_path
from safeops_agent.mcp_server import McpToolService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"
APP_CONFIG = load_app_config()
AUDIT_PATH = resolve_project_path(APP_CONFIG["audit_log"])


class SafeOpsWebHandler(BaseHTTPRequestHandler):
    server_version = "SafeOpsWeb/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json({"ok": True, "service": "safeops-web"})
            return
        if path == "/api/tools":
            self._json({"ok": True, "tools": McpToolService().list_tools()})
            return
        if path == "/api/audit":
            self._json({"ok": True, "events": AuditLogger(AUDIT_PATH).recent(20)})
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/agent":
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return

        request = str(payload.get("request", "")).strip()
        confirmed = bool(payload.get("confirmed", False))
        if not request:
            self._json({"ok": False, "error": "request is required"}, HTTPStatus.BAD_REQUEST)
            return

        agent = SafeOpsAgent(audit_logger=AuditLogger(AUDIT_PATH, source="web"))
        response = agent.handle(request, confirmed=confirmed)
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
            },
            HTTPStatus.OK if response.ok else HTTPStatus.ACCEPTED,
        )

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        relative = path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.is_file():
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
    print(f"SafeOps Web running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
