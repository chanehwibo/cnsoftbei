import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider
from safeops_agent.llm.provider import DeepSeekProvider


def make_agent(llm=None):
    tmp = tempfile.TemporaryDirectory()
    agent = SafeOpsAgent(
        audit_logger=AuditLogger(Path(tmp.name) / "audit.log"),
        llm=llm or RuleBasedProvider(),
    )
    agent._tmp = tmp  # keep alive
    return agent


class ReasoningChainTest(unittest.TestCase):
    def _stages(self, chain):
        return [s["stage"] for s in chain]

    def test_chain_present_on_success(self):
        agent = make_agent()
        resp = agent.handle("查看系统信息")
        self.assertIsNotNone(resp.reasoning_chain)
        stages = self._stages(resp.reasoning_chain)
        self.assertEqual(
            stages,
            ["context_resolution", "intent_screening", "tool_selection", "risk_adjudication", "execution"],
        )

    def test_steps_are_numbered_in_order(self):
        agent = make_agent()
        resp = agent.handle("查看CPU和内存")
        numbers = [s["step"] for s in resp.reasoning_chain]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_chain_stops_at_intent_on_high_risk(self):
        agent = make_agent()
        resp = agent.handle("删除 / 根目录")
        stages = self._stages(resp.reasoning_chain)
        self.assertIn("intent_screening", stages)
        self.assertNotIn("execution", stages)
        last = resp.reasoning_chain[-1]
        self.assertFalse(last["outputs"]["allowed"])

    def test_chain_records_confirmation_and_dry_run(self):
        agent = make_agent()
        resp = agent.handle("重启 nginx 服务")
        self.assertTrue(resp.requires_confirmation)
        exec_step = [s for s in resp.reasoning_chain if s["stage"] == "execution"][0]
        self.assertFalse(exec_step["outputs"]["executed"])
        self.assertTrue(exec_step["outputs"]["dry_run"])

    def test_context_resolution_recorded(self):
        agent = make_agent()
        agent.handle("查询 nginx 服务状态")  # establish last_service
        resp = agent.handle("重启它")
        ctx = resp.reasoning_chain[0]
        self.assertEqual(ctx["stage"], "context_resolution")
        self.assertEqual(ctx["inputs"]["raw"], "重启它")
        self.assertIn("nginx", ctx["outputs"]["resolved"])

    def test_llm_reasoning_captured_in_chain(self):
        mock_llm = MagicMock()
        mock_llm.select_tool.return_value = ("system.resources", {}, "用户询问服务器负载", None)
        mock_llm.__class__ = DeepSeekProvider
        agent = make_agent(llm=mock_llm)
        resp = agent.handle("服务器还撑得住吗")
        sel = [s for s in resp.reasoning_chain if s["stage"] == "tool_selection"][0]
        self.assertEqual(sel["outputs"]["source"], "llm")
        self.assertEqual(sel["outputs"]["llm_reasoning"], "用户询问服务器负载")

    def test_chain_persisted_to_audit(self):
        agent = make_agent()
        agent.handle("查看系统信息")
        events = agent.audit.recent(1)
        self.assertIn("reasoning_chain", events[0])
        self.assertTrue(len(events[0]["reasoning_chain"]) >= 4)


if __name__ == "__main__":
    unittest.main()
