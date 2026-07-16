import http.client
import json
import threading
import unittest

import safeops_agent.web_server as web


class WebAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.old_token = web.API_TOKEN
        self.old_auth = web._session_auth
        self.old_limiter = web._limiter
        web.API_TOKEN = "test-token"
        web._session_auth = web._WebSessionAuth()
        web._limiter = web._RateLimiter(max_requests=1000, window=60)
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


if __name__ == "__main__":
    unittest.main()
