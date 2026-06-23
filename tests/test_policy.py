import unittest

from safeops_agent.security.policy import PolicyEngine
from safeops_agent.tools.models import RiskLevel
from safeops_agent.tools.registry import build_registry


class PolicyEngineTest(unittest.TestCase):
    def test_rejects_destructive_intent(self):
        decision = PolicyEngine().evaluate_intent("帮我删除根目录所有文件")

        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.HIGH)

    def test_low_risk_tool_is_allowed(self):
        tool = build_registry()["system.info"]
        decision = PolicyEngine().evaluate_tool(tool)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk, RiskLevel.LOW)

    def test_medium_risk_tool_requires_confirmation(self):
        tool = build_registry()["service.restart"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "nginx"})

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_confirmation)

    def test_rejects_command_injection_in_service_name(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "nginx;rm -rf /"})

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "ARG_COMMAND_INJECTION")

    def test_rejects_sensitive_path_destructive_intent(self):
        decision = PolicyEngine().evaluate_intent("覆盖 /etc/passwd")

        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "INTENT_SENSITIVE_PATH")


if __name__ == "__main__":
    unittest.main()
