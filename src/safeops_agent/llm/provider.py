from __future__ import annotations

import json
import re
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


class OpenAICompatibleProvider(DeepSeekProvider):
    """兼容 OpenAI chat/completions 接口的通用 Provider。

    适用于任何 OpenAI 兼容 API（如 vLLM、Ollama、通义千问、智谱等），
    通过 base_url 指向不同服务端点。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 10,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)

    def describe(self) -> str:
        return f"openai-compatible/{self._model}@{self._base_url}（超时 {self._timeout}s）"


class RuleBasedProvider(LLMProvider):
    """基于关键词匹配的规则引擎，不调用外部 API。

    覆盖 30+ 常见运维意图的中文关键词匹配，支持诊断场景、
    服务生命周期、系统采集、文件操作等全部工具类别。
    作为 LLM 不可用时的完整离线回退方案。
    """

    _KNOWN_SERVICES = (
        "redis-server", "systemd-resolved", "networkmanager", "containerd",
        "apache2", "postgresql", "mariadb", "firewalld", "iptables",
        "dockerd", "kubelet", "apache", "mysqld", "nginx", "httpd",
        "mysql", "redis", "docker", "sshd", "crond", "cron",
        "tomcat", "named", "bind9",
    )

    _SERVICE_HINTS = (
        "nginx", "httpd", "apache", "mysql", "mariadb", "postgresql",
        "redis", "docker", "sshd", "firewalld", "iptables", "crond",
        "tomcat", "java", "node", "python", "kubelet",
    )

    def __init__(self, tool_defaults: dict[str, Any] | None = None) -> None:
        self._defaults = tool_defaults or {}

    def describe(self) -> str:
        return "规则关键词匹配（离线模式，不调用外部 API）"

    def _default(self, key: str, fallback: int) -> int:
        try:
            return int(self._defaults.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    def set_tool_defaults(self, tool_defaults: dict[str, Any]) -> None:
        """同步由 Agent 配置加载的工具默认参数。"""
        self._defaults = tool_defaults

    def select_tool(
        self,
        text: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, dict[str, Any], str, str | None]:
        tool_name, args = self._match(text)
        if tool_name is None:
            return None, {}, "", None
        valid_names = {t["name"] for t in tools}
        if tool_name not in valid_names:
            return None, {}, f"规则匹配工具 {tool_name} 未在注册表中", None
        return tool_name, args, "规则关键词匹配", None

    def _match(self, text: str) -> tuple[str | None, dict[str, Any]]:
        compact = text.lower().replace(" ", "")

        if any(kw in compact for kw in ("诊断", "排查", "故障", "异常", "排障", "检查一下", "怎么了", "什么问题")):
            return self._match_diagnostic(text, compact)
        if any(kw in compact for kw in ("系统信息", "系统版本", "操作系统", "内核", "主机信息", "主机名", "机器信息", "uname")):
            return "system.info", {}
        if any(kw in compact for kw in ("磁盘分区", "挂载点", "分区信息", "df", "磁盘挂载")):
            return "disk.partitions", {}
        if any(kw in compact for kw in ("cpu", "内存", "资源", "负载", "内存占用", "cpu占用", "使用率", "利用率", "load", "磁盘用量", "磁盘使用")):
            return "system.resources", {}
        if any(kw in compact for kw in ("进程", "process", "任务管理器", "跑了什么", "运行了什么")):
            return "process.list", {"limit": self._default("process_limit", 10)}
        if any(kw in compact for kw in ("错误日志", "系统日志", "journal", "日志", "报错", "error")):
            return "logs.recent_errors", {"lines": self._default("log_lines", 100)}
        if "受管文件" in compact and any(kw in compact for kw in ("列表", "查看", "有哪些")):
            return "file.list_managed", {}
        if any(kw in compact for kw in ("回滚", "恢复")) and any(kw in compact for kw in ("快照", "受管文件", "snapshot")):
            return "file.rollback", {"snapshot_id": self._extract_snapshot_id(text)}
        if "受管文件" in compact and any(kw in compact for kw in ("写入", "保存", "更新")):
            name, content = self._extract_managed_file(text)
            return "file.apply", {"name": name, "content": content}
        if "重启" in compact and ("服务" in compact or self._has_service_hint(compact)):
            return "service.restart", {"service": self._extract_service_name(text)}
        if "启动" in compact and ("服务" in compact or self._has_service_hint(compact)):
            return "service.start", {"service": self._extract_service_name(text)}
        if any(kw in compact for kw in ("停止", "停掉")) and ("服务" in compact or self._has_service_hint(compact)):
            return "service.stop", {"service": self._extract_service_name(text)}
        if ("服务" in compact or self._has_service_hint(compact)) and any(kw in compact for kw in ("状态", "查询", "查看", "跑着没", "运行", "是否正常", "在不在")):
            return "service.status", {"service": self._extract_service_name(text)}
        if any(kw in compact for kw in ("网络连接", "连接列表", "netstat", "tcp连接", "udp连接", "网络状态")):
            return "network.connections", {"limit": self._default("network_limit", 50)}
        if any(kw in compact for kw in ("监听端口", "端口监听", "开放端口", "端口列表", "端口", "port", "哪些端口")):
            return "network.listening_ports", {"limit": self._default("network_limit", 50)}
        if any(kw in compact for kw in ("用户列表", "本地用户", "系统用户", "有哪些用户", "用户")):
            return "user.list", {}
        if any(kw in compact for kw in ("定时任务", "计划任务", "cron", "crontab", "定时")):
            return "schedule.cron", {}
        if any(kw in compact for kw in ("环境变量", "env", "path变量")):
            return "environment.safe", {}
        if any(kw in compact for kw in ("软件包", "安装包", "rpm", "dpkg", "装了什么", "有没有安装", "是否安装", "包版本")):
            return "package.query", {"package": self._extract_package_name(text)}
        return None, {}

    def match(self, text: str) -> tuple[str | None, dict[str, Any]]:
        """返回确定性规则匹配结果，供 Agent 的兼容入口与专项测试复用。"""
        return self._match(text)

    def extract_service_name(self, text: str) -> str:
        """从自然语言中提取合法服务标识符。"""
        return self._extract_service_name(text)

    def _match_diagnostic(self, text: str, compact: str) -> tuple[str, dict[str, Any]]:
        if any(kw in compact for kw in ("端口", "监听")):
            return "diagnostics.network_ports", {"limit": self._default("network_limit", 50)}
        if "服务" in compact:
            return "diagnostics.service", {"service": self._extract_service_name(text)}
        if any(kw in compact for kw in ("日志", "journal", "错误")):
            return "diagnostics.logs", {"lines": self._default("log_lines", 100)}
        if any(kw in compact for kw in ("磁盘", "空间", "挂载")):
            return "diagnostics.disk", {}
        if any(kw in compact for kw in ("cpu", "内存", "资源", "负载")):
            return "diagnostics.resources", {}
        return "diagnostics.overview", {}

    def has_service_hint(self, compact: str) -> bool:
        return any(s in compact for s in self._SERVICE_HINTS)

    _has_service_hint = has_service_hint

    def _extract_service_name(self, text: str) -> str:
        lower = text.lower()
        for svc in self._KNOWN_SERVICES:
            if svc in lower:
                return svc
        tokens = text.replace("，", " ").replace(",", " ").split()
        stop_words = {"服务", "状态", "查询", "查看", "重启", "诊断", "排查", "故障", "异常", "的",
                      "启动", "停止", "停掉"}
        for token in tokens:
            if token.lower() in stop_words:
                continue
            if any(c.isascii() and (c.isalnum() or c in "_.-@") for c in token):
                cleaned = "".join(c for c in token if c.isascii() and (c.isalnum() or c in "_.-@"))
                if cleaned:
                    return cleaned
        return ""

    def _extract_package_name(self, text: str) -> str:
        tokens = text.replace("，", " ").replace(",", " ").split()
        stop_words = {"查询", "查看", "软件包", "安装包", "版本", "列表", "的"}
        for token in tokens:
            if token.lower() in stop_words:
                continue
            cleaned = "".join(c for c in token if c.isascii() and (c.isalnum() or c in "+_.:-"))
            if cleaned:
                return cleaned
        return ""

    def _extract_managed_file(self, text: str) -> tuple[str, str]:
        match = re.search(
            r"(?:受管文件|文件)\s+([A-Za-z0-9._-]+)\s+"
            r"(?:内容为|内容|写入)\s*[:：]?\s*(.+)$",
            text, flags=re.IGNORECASE,
        )
        if match:
            return match.group(1), match.group(2).strip()
        name_match = re.search(r"\b([A-Za-z0-9][A-Za-z0-9._-]*)\b", text)
        return (name_match.group(1) if name_match else ""), ""

    def _extract_snapshot_id(self, text: str) -> str:
        match = re.search(
            r"(?:快照|snapshot(?:_id)?)\s*[:：]?\s*([A-Za-z0-9._-]+)",
            text, flags=re.IGNORECASE,
        )
        return match.group(1) if match else ""
