import unittest

from safeops_agent.mcp_server import McpToolService


class McpToolServiceTest(unittest.TestCase):
    def test_lists_registered_tools(self):
        tools = McpToolService().list_tools()
        names = {tool["name"] for tool in tools}

        self.assertIn("system.info", names)
        self.assertIn("service.restart", names)
        self.assertIn("diagnostics.resources", names)
        self.assertIn("diagnostics.network_ports", names)
        for tool in tools:
            self.assertIn("inputSchema", tool)
            self.assertIn("annotations", tool)

    def test_calls_diagnostic_tool(self):
        result = McpToolService().call_tool("diagnostics.resources", {})

        self.assertTrue(result["ok"])
        self.assertEqual(result["risk"], "LOW")
        self.assertFalse(result["requires_confirmation"])
        self.assertIn("diagnosis", result["data"])

    def test_blocks_medium_risk_without_confirmation(self):
        result = McpToolService().call_tool("service.restart", {"service": "nginx"})

        self.assertFalse(result["ok"])
        self.assertTrue(result["requires_confirmation"])
        self.assertEqual(result["error_code"], "TOOL_CONFIRMATION_REQUIRED")

    def test_unknown_tool_has_stable_error_code(self):
        result = McpToolService().call_tool("missing.tool", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "TOOL_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()