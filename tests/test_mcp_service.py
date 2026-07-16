import tempfile
import unittest
from pathlib import Path

from safeops_agent.mcp_server import McpToolService
from safeops_agent.security.pending import PendingActionStore
from safeops_agent.tools.models import RiskLevel, ToolResult, ToolSpec


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
        self.assertIn("pending_action_id", result["data"])

    def test_medium_risk_executes_only_through_one_time_token(self):
        calls = []
        tool = ToolSpec(
            name="service.restart",
            description="test",
            risk=RiskLevel.MEDIUM,
            handler=lambda args: calls.append(dict(args)) or ToolResult(ok=True, summary="done"),
            parameters={"service": {"type": "string"}},
            required=["service"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PendingActionStore(Path(tmp) / "pending.json")
            service = McpToolService(
                tools={tool.name: tool},
                pending_store=store,
                session_id="test-mcp",
            )
            preview = service.call_tool(tool.name, {"service": "nginx"})
            action_id = preview["data"]["pending_action_id"]

            confirmed = service.call_tool("safeops.confirm", {"action_id": action_id})
            replayed = service.call_tool("safeops.confirm", {"action_id": action_id})

        self.assertTrue(confirmed["ok"])
        self.assertEqual(calls, [{"service": "nginx"}])
        self.assertFalse(replayed["ok"])
        self.assertEqual(replayed["error_code"], "CONFIRM_TOKEN_INVALID")

    def test_unknown_tool_has_stable_error_code(self):
        result = McpToolService().call_tool("missing.tool", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "TOOL_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
