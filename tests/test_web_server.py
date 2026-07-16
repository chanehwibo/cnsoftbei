import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import safeops_agent.web_server as web


class WebAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.old_token = web.API_TOKEN
        self.old_auth = web._session_auth
        self.old_limiter = web._limiter
        self.old_secure_transport = web.SECURE_TRANSPORT
        self.old_development_mode = web.DEVELOPMENT_MODE
        web.API_TOKEN = "test-token"
        web._session_auth = web._WebSessionAuth()
        web._limiter = web._RateLimiter(max_requests=1000, window=60)
        web.SECURE_TRANSPORT = False
        web.DEVELOPMENT_MODE = False
        self.server = web.ThreadingHTTPServer(("127.0.0.1", 0), web.SafeOpsWebHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        web.API_TOKEN = self.old_token
        web._session_auth = self.old_auth
        web._limiter = self.old_limiter
        web.SECURE_TRANSPORT = self.old_secure_transport
        web.DEVELOPMENT_MODE = self.old_development_mode

    def request(self, method, path, payload=None, headers=None):
        body = None
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
            request_headers["Content-Length"] = str(len(body))
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, dict(response.getheaders()), parsed
        finally:
            connection.close()

    def login(self):
        status, headers, payload = self.request("POST", "/api/auth", {"token": "test-token"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        return cookie.split(";", 1)[0]

    def test_protected_api_requires_authenticated_cookie(self):
        status, _, _ = self.request("GET", "/api/tools")
        self.assertEqual(status, 401)

        cookie = self.login()
        status, headers, payload = self.request("GET", "/api/tools", headers={"Cookie": cookie})

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_bearer_token_authenticates_programmatic_client(self):
        status, _, payload = self.request(
            "GET",
            "/api/tools",
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_rate_limit_returns_429_after_budget_is_exhausted(self):
        web._limiter = web._RateLimiter(max_requests=1, window=60)
        headers = {"Authorization": "Bearer test-token"}

        first_status, _, _ = self.request("GET", "/api/tools", headers=headers)
        second_status, _, payload = self.request("GET", "/api/tools", headers=headers)

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 429)
        self.assertEqual(payload["error"], "rate limit exceeded")

    def test_authentication_session_expires_and_is_removed(self):
        auth = web._WebSessionAuth()
        with mock.patch.object(
            web.time,
            "time",
            side_effect=[1000, 1001, 1000 + web.AUTH_SESSION_TTL + 1],
        ):
            session = auth.login("test-token")
            self.assertIsNotNone(session)
            self.assertTrue(auth.valid(session))
            self.assertFalse(auth.valid(session))

        self.assertNotIn(session, auth._sessions)

    def test_query_token_is_not_an_authentication_channel(self):
        status, _, _ = self.request("GET", "/api/tools?token=test-token")
        self.assertEqual(status, 401)

    def test_agent_rejects_non_object_json(self):
        cookie = self.login()
        status, _, payload = self.request(
            "POST",
            "/api/agent",
            [],
            headers={"Cookie": cookie},
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "json body must be an object")

    def test_invalid_login_is_rejected(self):
        status, _, payload = self.request("POST", "/api/auth", {"token": "wrong"})
        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])

    def test_secure_transport_sets_hsts_and_secure_cookie(self):
        web.SECURE_TRANSPORT = True
        status, headers, _ = self.request("POST", "/api/auth", {"token": "test-token"})

        self.assertEqual(status, 200)
        self.assertIn("Secure", headers["Set-Cookie"])
        self.assertIn("max-age=31536000", headers["Strict-Transport-Security"])

    def test_sse_endpoint_pushes_latest_audit_event(self):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        web._shutdown_event.clear()
        try:
            connection.request(
                "GET",
                "/api/events",
                headers={"Authorization": "Bearer test-token"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(response.getheader("Content-Type").startswith("text/event-stream"))

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with web._sse._lock:
                    if web._sse._events:
                        break
                time.sleep(0.01)
            else:
                self.fail("SSE subscriber was not registered")

            event = {"event_type": "agent.tool_call", "tool": "system.info"}
            with mock.patch.object(web._audit_logger, "recent", return_value=[event]):
                web._sse.notify()
                line = response.fp.readline().decode("utf-8")

            self.assertTrue(line.startswith("data: "))
            self.assertEqual(json.loads(line.removeprefix("data: ")), event)
        finally:
            web._shutdown_event.set()
            web._sse.notify()
            connection.close()
            web._shutdown_event.clear()


class WebTlsConfigurationTest(unittest.TestCase):
    def test_non_loopback_plain_http_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "TLS"):
            web._build_server("0.0.0.0", 0, {"tls_enabled": False})

    def test_tls_wraps_server_socket_and_requires_tls_1_2(self):
        with tempfile.TemporaryDirectory() as directory:
            cert = Path(directory) / "server.crt"
            key = Path(directory) / "server.key"
            cert.write_text("test", encoding="utf-8")
            key.write_text("test", encoding="utf-8")
            context = mock.Mock()
            context.wrap_socket.side_effect = lambda sock, server_side: sock
            with mock.patch.object(web.ssl, "SSLContext", return_value=context):
                server, scheme = web._build_server(
                    "127.0.0.1",
                    0,
                    {
                        "tls_enabled": True,
                        "tls_cert_file": str(cert),
                        "tls_key_file": str(key),
                    },
                )
            try:
                self.assertEqual(scheme, "https")
                self.assertEqual(context.minimum_version, web.ssl.TLSVersion.TLSv1_2)
                context.load_cert_chain.assert_called_once_with(
                    certfile=str(cert),
                    keyfile=str(key),
                )
                context.wrap_socket.assert_called_once()
            finally:
                server.server_close()


class WebStartupAuthenticationTest(unittest.TestCase):
    def test_default_mode_rejects_empty_token(self):
        with self.assertRaisesRegex(RuntimeError, "SAFEOPS_TOKEN"):
            web._validate_startup_auth(
                "127.0.0.1",
                {"require_auth": True, "development_mode": False},
                token="",
            )

    def test_authentication_cannot_be_silently_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "explicit development_mode"):
            web._validate_startup_auth(
                "127.0.0.1",
                {"require_auth": False, "development_mode": False},
                token="unused",
            )

    def test_explicit_development_mode_is_loopback_only(self):
        config = {"require_auth": False, "development_mode": True}
        web._validate_startup_auth("127.0.0.1", config, token="")
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            web._validate_startup_auth("0.0.0.0", config, token="")


class WebAgentSessionLruTest(unittest.TestCase):
    def test_oldest_agent_session_is_evicted_at_capacity(self):
        old_max_sessions = web.MAX_SESSIONS
        with web._sessions_guard:
            old_sessions = dict(web._sessions)
            web._sessions.clear()
        web.MAX_SESSIONS = 2
        agents = [object(), object(), object()]
        try:
            with (
                mock.patch.object(web, "SafeOpsAgent", side_effect=agents) as factory,
                mock.patch.object(web.time, "monotonic", side_effect=[1, 1, 2, 2, 3, 4, 4]),
            ):
                first, _ = web._get_session("first")
                second, _ = web._get_session("second")
                web._get_session("first")
                third, _ = web._get_session("third")

            self.assertIs(first, agents[0])
            self.assertIs(second, agents[1])
            self.assertIs(third, agents[2])
            self.assertEqual(factory.call_count, 3)
            self.assertEqual(set(web._sessions), {"first", "third"})
        finally:
            web.MAX_SESSIONS = old_max_sessions
            with web._sessions_guard:
                web._sessions.clear()
                web._sessions.update(old_sessions)


if __name__ == "__main__":
    unittest.main()
