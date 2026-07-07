from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from safeops_agent.llm.prompts import build_tool_selection_messages


class LLMProvider(ABC):
    """LLM 意图理解抽象基类。"""

    def describe(self) -> str:
        """人类可读的 Provider 自述，用于启动自检与运行日志。"""
        return self.__class__.__name__

    @abstractmethod
    def select_tool(
        self,
        text: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, dict[str, Any], str, str | None]:
        """理解用户意图，选择工具并提取参数。

        Returns:
            (tool_name, args, reasoning, clarification) — tool_name 为 None 表示未匹配，
            clarification 非 None 时表示需要追问用户。
        """


class DeepSeekProvider(LLMProvider):
    """基于 DeepSeek API 的意图理解实现（兼容 OpenAI 接口格式）。"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 8,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def describe(self) -> str:
        return f"deepseek/{self._model}（超时 {self._timeout}s，失败自动回退规则匹配）"

    def select_tool(
        self,
        text: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, dict[str, Any], str, str | None]:
        messages = build_tool_selection_messages(text, tools, conversation_history)
        try:
            result = self._chat_completion(messages)
        except Exception:
            return None, {}, "LLM 调用失败", None

        return self._parse_response(result, tools)

    def _chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        payload = json.dumps(
            {
                "model": self._model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 512,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=False,
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            body = json.loads(response.read().decode("utf-8"))

        return body

    def _parse_response(
        self, body: dict[str, Any], tools: list[dict[str, Any]]
    ) -> tuple[str | None, dict[str, Any], str, str | None]:
        try:
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError):
            return None, {}, "LLM 响应解析失败", None

        tool_name = parsed.get("tool")
        args = parsed.get("args", {})
        reasoning = str(parsed.get("reasoning", ""))
        clarification = parsed.get("clarification")

        if not tool_name:
            return None, {}, reasoning or "LLM 未匹配到工具", clarification

        valid_names = {t["name"] for t in tools}
        if tool_name not in valid_names:
            return None, {}, f"LLM 返回未知工具: {tool_name}", None

        if not isinstance(args, dict):
            args = {}

        return str(tool_name), args, reasoning, clarification if clarification else None


class RuleBasedProvider(LLMProvider):
    """规则引擎 fallback，不调用外部 API。"""

    def describe(self) -> str:
        return "规则关键词匹配（离线模式，不调用外部 API）"

    def select_tool(
        self,
        text: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, dict[str, Any], str, str | None]:
        return None, {}, "", None
