import tempfile
import unittest
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger


class AgentTest(unittest.TestCase):
    def make_agent(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"))

    def test_handles_system_info(self):
        response = self.make_agent().handle("查看系统信息")

        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "system.info")
        self.assertEqual(response.risk_score, 10)
        self.assertIsNotNone(response.decision_summary)
        self.assertIn("风险评分 10/100", response.decision_summary)

    def test_rejects_destructive_request(self):
        response = self.make_agent().handle("删除根目录所有文件")

        self.assertFalse(response.ok)
        self.assertIn("拒绝", response.message)
        self.assertGreaterEqual(response.risk_score, 90)
        self.assertIn("拒绝执行", response.decision_summary)

    def test_medium_risk_requires_confirmation(self):
        response = self.make_agent().handle("重启 nginx 服务")

        self.assertFalse(response.ok)
        self.assertTrue(response.requires_confirmation)
        self.assertEqual(response.tool, "service.restart")
        self.assertGreaterEqual(response.risk_score, 65)
        self.assertIn("需要人工确认", response.decision_summary)
        self.assertIn("dry_run_plan", response.data)
        self.assertEqual(response.data["dry_run_plan"]["action"], "service.restart")

    def test_routes_resource_diagnostics(self):
        response = self.make_agent().handle("诊断 CPU 和内存异常")

        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "diagnostics.resources")
        self.assertIn("diagnosis", response.data)
        self.assertIn("recommended_actions", response.data["diagnosis"])

    def test_routes_network_port_diagnostics(self):
        response = self.make_agent().handle("排查端口占用问题")

        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "diagnostics.network_ports")
        self.assertIn("diagnosis", response.data)

    def test_handles_safe_environment(self):
        response = self.make_agent().handle("查看环境变量")

        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "environment.safe")
        self.assertIn("environment", response.data)


if __name__ == "__main__":
    unittest.main()