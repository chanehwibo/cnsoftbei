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

    def test_rejects_rm_rf(self):
        decision = PolicyEngine().evaluate_intent("rm -rf /tmp")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_rejects_shutdown(self):
        decision = PolicyEngine().evaluate_intent("关机")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_rejects_reboot(self):
        decision = PolicyEngine().evaluate_intent("重启系统")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_rejects_privilege_escalation(self):
        decision = PolicyEngine().evaluate_intent("提权到 root")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_rejects_disable_firewall(self):
        decision = PolicyEngine().evaluate_intent("关闭防火墙")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_allows_safe_query(self):
        decision = PolicyEngine().evaluate_intent("查看系统信息")
        self.assertIsNone(decision)

    def test_rejects_pipe_injection(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "nginx|cat /etc/passwd"})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "ARG_COMMAND_INJECTION")

    def test_rejects_backtick_injection(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "`whoami`"})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "ARG_COMMAND_INJECTION")

    def test_rejects_dollar_injection(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "$(rm -rf /)"})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "ARG_COMMAND_INJECTION")

    def test_rejects_newline_in_argument(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": "nginx\nrm -rf /"})
        self.assertFalse(decision.allowed)

    def test_rejects_empty_service_name(self):
        tool = build_registry()["service.status"]
        decision = PolicyEngine().evaluate_tool(tool, {"service": ""})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_code, "ARG_SERVICE_REQUIRED")

    def test_sensitive_path_root_slash(self):
        decision = PolicyEngine().evaluate_intent("覆盖 /")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_sensitive_path_etc(self):
        decision = PolicyEngine().evaluate_intent("删除 /etc 目录")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_sensitive_path_boot(self):
        decision = PolicyEngine().evaluate_intent("清空 /boot")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
