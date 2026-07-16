import io
import json
import unittest

from safeops_agent.mcp_stdio import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    McpStdioServer,
)


def make_server() -> McpStdioServer:
    return McpStdioServer(stdin=io.StringIO(), stdout=io.StringIO())


def make_initialized_server() -> McpStdioServer:
    server = make_server()
    server.handle_message(req("initialize", {"protocolVersion": PROTOCOL_VERSION}))
    server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return server


def req(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "method": method}
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    return msg


class InitializeTest(unittest.TestCase):
    def test_initialize_handshake(self):
        server = make_server()
        resp = server.handle_message(req("initialize", {"protocolVersion": PROTOCOL_VERSION}))
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 1)
        result = resp["result"]
        self.assertIn("protocolVersion", result)
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "safeops-agent")

    def test_initialize_echoes_client_protocol(self):
        server = make_server()
        resp = server.handle_message(req("initialize", {"protocolVersion": "2025-06-18"}))
        self.assertEqual(resp["result"]["protocolVersion"], "2025-06-18")

    def test_initialized_notification_no_response(self):
        server = make_server()
        server.handle_message(req("initialize", {"protocolVersion": PROTOCOL_VERSION}))
        resp = server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertIsNone(resp)
        self.assertTrue(server._initialized)

    def test_current_protocol_version_is_supported(self):
        self.assertEqual(PROTOCOL_VERSION, "2025-11-25")

    def test_tools_are_rejected_before_initialized_notification(self):
        server = make_server()
        server.handle_message(req("initialize", {"protocolVersion": PROTOCOL_VERSION}))
        response = server.handle_message(req("tools/list", msg_id=2))

        self.assertIn("error", response)


class ToolsListTest(unittest.TestCase):
    def test_tools_list_shape(self):
        server = make_initialized_server()
        resp = server.handle_message(req("tools/list"))
        tools = resp["result"]["tools"]
        self.assertTrue(len(tools) > 0)
        first = tools[0]
        self.assertIn("name", first)
        self.assertIn("inputSchema", first)
        self.assertIn("annotations", first)
        self.assertEqual(first["inputSchema"]["type"], "object")

    def test_system_info_is_readonly_hint(self):
        server = make_initialized_server()
        resp = server.handle_message(req("tools/list"))
        tools = {t["name"]: t for t in resp["result"]["tools"]}
        self.assertTrue(tools["system.info"]["annotations"]["readOnlyHint"])


class ToolsCallTest(unittest.TestCase):
    def test_call_low_risk_tool_ok(self):
        server = make_initialized_server()
        resp = server.handle_message(req("tools/call", {"name": "system.info", "arguments": {}}))
        result = resp["result"]
        self.assertFalse(result["isError"])
        self.assertIn("content", result)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertTrue(result["structuredContent"]["ok"])

    def test_call_medium_tool_requires_confirmation(self):
        server = make_initialized_server()
        resp = server.handle_message(
            req("tools/call", {"name": "service.restart", "arguments": {"service": "nginx"}})
        )
        result = resp["result"]
        self.assertTrue(result["isError"])
        self.assertTrue(result["structuredContent"]["requires_confirmation"])

    def test_call_blocks_command_injection(self):
        server = make_initialized_server()
        resp = server.handle_message(
            req("tools/call", {"name": "service.status", "arguments": {"service": "nginx;rm -rf /"}})
        )
        result = resp["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error_code"], "ARG_COMMAND_INJECTION")

    def test_call_unknown_tool(self):
        server = make_initialized_server()
        resp = server.handle_message(req("tools/call", {"name": "does.not.exist", "arguments": {}}))
        self.assertTrue(resp["result"]["isError"])
        self.assertEqual(resp["result"]["structuredContent"]["error_code"], "TOOL_NOT_FOUND")

    def test_call_missing_name_is_invalid_params(self):
        server = make_initialized_server()
        resp = server.handle_message(req("tools/call", {"arguments": {}}))
        self.assertEqual(resp["error"]["code"], INVALID_PARAMS)


class ProtocolErrorTest(unittest.TestCase):
    def test_unknown_method(self):
        server = make_server()
        resp = server.handle_message(req("foo/bar"))
        self.assertEqual(resp["error"]["code"], METHOD_NOT_FOUND)

    def test_ping(self):
        server = make_server()
        resp = server.handle_message(req("ping"))
        self.assertEqual(resp["result"], {})

    def test_invalid_jsonrpc_version(self):
        server = make_server()
        resp = server.handle_message({"jsonrpc": "1.0", "method": "ping", "id": 1})
        self.assertIsNotNone(resp["error"])

    def test_notification_unknown_method_no_response(self):
        server = make_server()
        resp = server.handle_message({"jsonrpc": "2.0", "method": "foo/bar"})
        self.assertIsNone(resp)


class StdioLoopTest(unittest.TestCase):
    def test_full_stdio_roundtrip(self):
        lines = [
            json.dumps(req("initialize", {"protocolVersion": PROTOCOL_VERSION})),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps(req("tools/list", msg_id=2)),
            json.dumps(req("ping", msg_id=3)),
        ]
        stdin = io.StringIO("\n".join(lines) + "\n")
        stdout = io.StringIO()
        McpStdioServer(stdin=stdin, stdout=stdout).serve_forever()
        outputs = [json.loads(l) for l in stdout.getvalue().strip().splitlines()]
        # initialize + tools/list + ping = 3 responses（notification 无响应）
        self.assertEqual(len(outputs), 3)
        self.assertEqual(outputs[0]["id"], 1)
        self.assertEqual(outputs[1]["id"], 2)
        self.assertEqual(outputs[2]["id"], 3)

    def test_parse_error_on_bad_json(self):
        stdin = io.StringIO("not json at all\n")
        stdout = io.StringIO()
        McpStdioServer(stdin=stdin, stdout=stdout).serve_forever()
        out = json.loads(stdout.getvalue().strip())
        self.assertEqual(out["error"]["code"], PARSE_ERROR)


if __name__ == "__main__":
    unittest.main()
