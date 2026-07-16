import json
import tempfile
import unittest
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider
from safeops_agent.security.pending import PendingActionStore


class ConfirmFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = PendingActionStore(Path(self.tmp.name) / "pending.json")

    def make_agent(self, session="cli"):
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(self.tmp.name) / "audit.log"),
            llm=RuleBasedProvider(),
            session_id=session,
            pending_store=self.store,
        )

    def test_pending_actions_are_encrypted_at_rest(self):
        action_id = self.store.create(
            "file.apply",
            {"name": "app.conf", "content": "password=hunter2"},
            "write secret config",
            session="cli",
        )
        raw = self.store.path.read_text(encoding="utf-8")
        payload = json.loads(raw)

        self.assertEqual(payload["version"], 1)
        self.assertIn("ciphertext", payload)
        self.assertNotIn("hunter2", raw)
        self.assertNotIn("write secret config", raw)
        record, error = self.store.consume(action_id, session="cli")
        self.assertIsNone(error)
        self.assertEqual(record["args"]["content"], "password=hunter2")

    def test_dry_run_issues_token(self):
        agent = self.make_agent()
        resp = agent.handle("重启 nginx 服务")
        self.assertTrue(resp.requires_confirmation)
        self.assertIsNotNone(resp.pending_action_id)
        self.assertIn("pending_action_id", resp.data)

    def test_confirm_executes_adjudicated_action(self):
        agent = self.make_agent()
        resp = agent.handle("重启 nginx 服务")
        confirmed = agent.confirm(resp.pending_action_id)
        self.assertEqual(confirmed.tool, "service.restart")
        # Windows 开发环境返回预告（ok=True）；Linux 真实执行
        self.assertTrue(confirmed.ok)
        stages = [s["stage"] for s in confirmed.reasoning_chain]
        self.assertIn("pending_lookup", stages)
        self.assertIn("execution", stages)

    def test_token_is_single_use(self):
        agent = self.make_agent()
        resp = agent.handle("重启 nginx 服务")
        agent.confirm(resp.pending_action_id)
        second = agent.confirm(resp.pending_action_id)
        self.assertFalse(second.ok)
        self.assertIn("确认失败", second.message)

    def test_token_bound_to_session(self):
        agent_a = self.make_agent(session="web:alice")
        agent_b = self.make_agent(session="web:bob")
        resp = agent_a.handle("重启 nginx 服务")
        hijacked = agent_b.confirm(resp.pending_action_id)
        self.assertFalse(hijacked.ok)
        self.assertIn("会话不匹配", hijacked.message)

    def test_unknown_token_rejected(self):
        agent = self.make_agent()
        resp = agent.confirm("deadbeef" * 4)
        self.assertFalse(resp.ok)

    def test_expired_token_rejected(self):
        store = PendingActionStore(Path(self.tmp.name) / "expired.json", ttl_seconds=0)
        agent = SafeOpsAgent(
            audit_logger=AuditLogger(Path(self.tmp.name) / "audit.log"),
            llm=RuleBasedProvider(),
            session_id="cli",
            pending_store=store,
        )
        resp = agent.handle("重启 nginx 服务")
        confirmed = agent.confirm(resp.pending_action_id)
        self.assertFalse(confirmed.ok)

    def test_confirm_audited_with_event_type(self):
        agent = self.make_agent()
        resp = agent.handle("重启 nginx 服务")
        agent.confirm(resp.pending_action_id)
        events = AuditLogger(Path(self.tmp.name) / "audit.log").recent(1)
        self.assertEqual(events[0]["event_type"], "agent.confirm")
        self.assertIn("pending_action_id", events[0])


class LlmOutputGuardrailTest(unittest.TestCase):
    def make_agent(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(tmp.name) / "audit.log"),
            llm=RuleBasedProvider(),
            session_id="test",
            pending_store=PendingActionStore(Path(tmp.name) / "pending.json"),
        )

    def test_blocks_destructive_llm_output(self):
        agent = self.make_agent()
        sanitized = agent._sanitize_llm_text("建议您手动执行 rm -rf /tmp 清理空间")
        self.assertIn("已屏蔽", sanitized)

    def test_truncates_oversized_llm_output(self):
        agent = self.make_agent()
        sanitized = agent._sanitize_llm_text("好" * 500)
        self.assertLessEqual(len(sanitized), 302)

    def test_passes_normal_llm_output(self):
        agent = self.make_agent()
        text = "用户想查询 nginx 服务状态，匹配 service.status 工具"
        self.assertEqual(agent._sanitize_llm_text(text), text)


if __name__ == "__main__":
    unittest.main()
