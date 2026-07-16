import tempfile
import unittest
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider


class AuditLoggerTest(unittest.TestCase):
    def test_sensitive_values_are_redacted_before_persisting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            logger = AuditLogger(audit_path, source="test")
            logger.record({
                "request": "api_key=sk-1234567890abcdef",
                "args": {"content": "password=hunter2", "password": "hunter2"},
                "pending_action_id": "deadbeef",
            })

            event = logger.recent(1)[0]
            raw = audit_path.read_text(encoding="utf-8")

            self.assertNotIn("sk-1234567890abcdef", raw)
            self.assertNotIn("hunter2", raw)
            self.assertEqual(event["args"]["content"], AuditLogger.REDACTED)
            self.assertEqual(event["args"]["password"], AuditLogger.REDACTED)
            self.assertEqual(event["pending_action_id"], AuditLogger.REDACTED)

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


class AuditQueryTest(unittest.TestCase):
    def _seed_events(self, audit_path: Path) -> None:
        cli = AuditLogger(audit_path, source="cli")
        web = AuditLogger(audit_path, source="web")
        cli.record({"event_type": "agent.tool_call", "tool": "system.info", "risk": "LOW"})
        cli.record({"event_type": "agent.tool_call", "tool": "service.restart", "risk": "MEDIUM"})
        web.record({"event_type": "agent.tool_call", "tool": "service.status", "risk": "LOW"})
        web.record({"event_type": "agent.denied", "tool": "file.apply", "risk": "HIGH"})

    def test_query_without_filters_equals_recent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            logger = AuditLogger(audit_path)
            self.assertEqual(logger.query(limit=3), logger.recent(3))

    def test_query_filters_by_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            events = AuditLogger(audit_path).query(source="web")
            self.assertEqual(len(events), 2)
            self.assertTrue(all(event["source"] == "web" for event in events))

    def test_query_filters_by_risk_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            events = AuditLogger(audit_path).query(risk="high")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tool"], "file.apply")

    def test_query_filters_by_tool_substring(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            events = AuditLogger(audit_path).query(tool="service")
            self.assertEqual(len(events), 2)
            self.assertEqual({event["tool"] for event in events},
                             {"service.restart", "service.status"})

    def test_query_combines_filters_with_and(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            events = AuditLogger(audit_path).query(source="web", risk="LOW", tool="service")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tool"], "service.status")

    def test_query_returns_most_recent_matches_within_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            logger = AuditLogger(audit_path, source="cli")
            for index in range(5):
                logger.record({"event_type": "agent.tool_call", "tool": f"system.info", "risk": "LOW", "seq": index})
            events = AuditLogger(audit_path).query(limit=2, source="cli")
            self.assertEqual([event["seq"] for event in events], [3, 4])

    def test_query_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.log"
            self._seed_events(audit_path)
            self.assertEqual(AuditLogger(audit_path).query(source="nobody"), [])



if __name__ == "__main__":
    unittest.main()
