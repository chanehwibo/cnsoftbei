import tempfile
import unittest
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider


class AuditLoggerTest(unittest.TestCase):
    def test_agent_writes_structured_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            agent = SafeOpsAgent(audit_logger=AuditLogger(audit_path, source="test"), llm=RuleBasedProvider())

            response = agent.handle("查看系统信息")
            events = AuditLogger(audit_path).recent(1)

            self.assertTrue(response.ok)
            self.assertEqual(len(events), 1)
            self.assertIn("event_id", events[0])
            self.assertEqual(events[0]["source"], "test")
            self.assertEqual(events[0]["event_type"], "agent.tool_call")
            self.assertIn("duration_ms", events[0])
            self.assertEqual(events[0]["risk_score"], 10)
            self.assertIn("风险评分 10/100", events[0]["decision_summary"])

    def test_confirmation_request_writes_dry_run_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            agent = SafeOpsAgent(audit_logger=AuditLogger(audit_path, source="test"), llm=RuleBasedProvider())

            response = agent.handle("重启 nginx 服务")
            events = AuditLogger(audit_path).recent(1)

            self.assertFalse(response.ok)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tool"], "service.restart")
            self.assertTrue(events[0]["requires_confirmation"])
            self.assertGreaterEqual(events[0]["risk_score"], 65)
            self.assertIn("dry_run_plan", events[0])
            self.assertEqual(events[0]["dry_run_plan"]["target"]["service"], "nginx")


if __name__ == "__main__":
    unittest.main()