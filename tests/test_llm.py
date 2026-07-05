import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Any

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider, get_provider
from safeops_agent.llm.provider import DeepSeekProvider
from safeops_agent.llm.prompts import build_tool_selection_messages, build_tools_description


class RuleBasedProviderTest(unittest.TestCase):
    def test_always_returns_none(self):
        provider = RuleBasedProvider()
        tool_name, args, reasoning = provider.select_tool("查看系统信息", [])
        self.assertIsNone(tool_name)
        self.assertEqual(args, {})


class GetProviderTest(unittest.TestCase):
    @patch.dict("os.environ", {"LLM_API_KEY": ""}, clear=False)
    @patch("safeops_agent.config.load_simple_yaml", return_value={"llm_enabled": True, "llm_api_key": ""})
    def test_returns_rule_based_when_no_api_key(self, _mock_yaml):
        provider = get_provider()
        self.assertIsInstance(provider, RuleBasedProvider)

    @patch.dict("os.environ", {"LLM_API_KEY": "sk-test123"}, clear=False)
    @patch("safeops_agent.config.load_simple_yaml", return_value={"llm_enabled": True, "llm_provider": "deepseek"})
    def test_returns_deepseek_when_api_key_set(self, _mock_yaml):
        provider = get_provider()
        self.assertIsInstance(provider, DeepSeekProvider)


class PromptsTest(unittest.TestCase):
    def test_build_tools_description(self):
        tools = [
            {"name": "system.info", "description": "采集系统信息", "parameters": {}, "required": [], "risk": "LOW"},
            {"name": "service.status", "description": "查询服务状态", "parameters": {"service": {"type": "string"}}, "required": ["service"], "risk": "LOW"},
        ]
        desc = build_tools_description(tools)
        self.assertIn("system.info", desc)
        self.assertIn("service.status", desc)
        self.assertIn("(必填)", desc)

    def test_build_messages_structure(self):
        tools = [{"name": "system.info", "description": "test", "parameters": {}, "required": [], "risk": "LOW"}]
        messages = build_tool_selection_messages("查看系统信息", tools)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "查看系统信息")
        self.assertIn("system.info", messages[0]["content"])


class DeepSeekProviderParseTest(unittest.TestCase):
    def make_provider(self):
        return DeepSeekProvider(api_key="sk-test", model="deepseek-chat", base_url="https://api.deepseek.com", timeout=10)

    def test_parses_valid_response(self):
        provider = self.make_provider()
        tools = [{"name": "system.info", "description": "test", "parameters": {}, "required": [], "risk": "LOW"}]
        body = {
            "choices": [{
                "message": {
                    "content": json.dumps({"tool": "system.info", "args": {}, "reasoning": "用户想看系统信息"})
                }
            }]
        }
        tool_name, args, reasoning = provider._parse_response(body, tools)
        self.assertEqual(tool_name, "system.info")
        self.assertEqual(args, {})
        self.assertIn("系统信息", reasoning)

    def test_returns_none_for_null_tool(self):
        provider = self.make_provider()
        tools = [{"name": "system.info", "description": "test", "parameters": {}, "required": [], "risk": "LOW"}]
        body = {
            "choices": [{
                "message": {
                    "content": json.dumps({"tool": None, "args": {}, "reasoning": "不匹配"})
                }
            }]
        }
        tool_name, args, reasoning = provider._parse_response(body, tools)
        self.assertIsNone(tool_name)

    def test_rejects_unknown_tool(self):
        provider = self.make_provider()
        tools = [{"name": "system.info", "description": "test", "parameters": {}, "required": [], "risk": "LOW"}]
        body = {
            "choices": [{
                "message": {
                    "content": json.dumps({"tool": "unknown.tool", "args": {}, "reasoning": "test"})
                }
            }]
        }
        tool_name, args, reasoning = provider._parse_response(body, tools)
        self.assertIsNone(tool_name)
        self.assertIn("未知工具", reasoning)

    def test_handles_malformed_json(self):
        provider = self.make_provider()
        tools = []
        body = {"choices": [{"message": {"content": "not json at all"}}]}
        tool_name, args, reasoning = provider._parse_response(body, tools)
        self.assertIsNone(tool_name)
        self.assertIn("解析失败", reasoning)


class AgentLLMIntegrationTest(unittest.TestCase):
    def make_agent(self, llm=None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"),
            llm=llm,
        )

    def test_fallback_to_rule_when_llm_not_configured(self):
        agent = self.make_agent(llm=RuleBasedProvider())
        response = agent.handle("查看系统信息")
        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "system.info")

    def test_uses_llm_result_when_available(self):
        mock_llm = MagicMock()
        mock_llm.select_tool.return_value = ("system.resources", {}, "用户想看资源")
        # Ensure it's not a RuleBasedProvider
        mock_llm.__class__ = DeepSeekProvider

        agent = self.make_agent(llm=mock_llm)
        response = agent.handle("看看服务器还撑得住不")
        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "system.resources")

    def test_fallback_to_rule_when_llm_returns_none(self):
        mock_llm = MagicMock()
        mock_llm.select_tool.return_value = (None, {}, "未匹配")
        mock_llm.__class__ = DeepSeekProvider

        agent = self.make_agent(llm=mock_llm)
        response = agent.handle("查看系统信息")
        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "system.info")


if __name__ == "__main__":
    unittest.main()
