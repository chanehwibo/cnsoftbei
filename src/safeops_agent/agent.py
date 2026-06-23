from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from safeops_agent.audit.logger import AuditLogger
from safeops_agent.security.policy import PolicyDecision, PolicyEngine
from safeops_agent.tools.models import RiskLevel, ToolResult
from safeops_agent.tools.registry import build_registry


@dataclass(frozen=True)
class AgentResponse:
    ok: bool
    message: str
    tool: str | None = None
    risk: RiskLevel | None = None
    data: dict[str, Any] | None = None
    requires_confirmation: bool = False


class SafeOpsAgent:
    def __init__(self, audit_logger: AuditLogger | None = None, policy: PolicyEngine | None = None) -> None:
        self.tools = build_registry()
        self.audit = audit_logger or AuditLogger()
        self.policy = policy or PolicyEngine()

    def handle(self, text: str, confirmed: bool = False) -> AgentResponse:
        started = time.perf_counter()
        intent_decision = self.policy.evaluate_intent(text)
        if intent_decision is not None:
            self._audit(text, None, {}, intent_decision, None, started)
            return AgentResponse(
                ok=False,
                message=f"已拒绝执行：{intent_decision.reason}",
                risk=intent_decision.risk,
            )

        tool_name, args = self._select_tool(text)
        if tool_name is None:
            decision = PolicyDecision(allowed=True, risk=RiskLevel.LOW, reason="未匹配到工具")
            self._audit(text, None, {}, decision, None, started)
            return AgentResponse(
                ok=False,
                message="暂未匹配到可执行运维工具。可以尝试：查看系统信息、查看CPU和内存、查看进程、查看错误日志、查询 nginx 服务状态、查看监听端口。",
                risk=RiskLevel.LOW,
            )

        tool = self.tools[tool_name]
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=confirmed)
        if not decision.allowed:
            self._audit(text, tool_name, args, decision, None, started)
            return AgentResponse(
                ok=False,
                message=f"未执行 {tool_name}：{decision.reason}",
                tool=tool_name,
                risk=decision.risk,
                requires_confirmation=decision.requires_confirmation,
            )

        result = tool.handler(args)
        self._audit(text, tool_name, args, decision, result, started)
        return AgentResponse(
            ok=result.ok,
            message=result.summary if result.ok else f"{result.summary}：{result.error}",
            tool=tool_name,
            risk=decision.risk,
            data=result.data,
        )

    def _select_tool(self, text: str) -> tuple[str | None, dict[str, Any]]:
        normalized = text.lower()
        compact = normalized.replace(" ", "")

        if any(keyword in compact for keyword in ("系统信息", "系统版本", "操作系统", "内核", "主机信息")):
            return "system.info", {}
        if any(keyword in compact for keyword in ("cpu", "内存", "磁盘", "资源", "负载")):
            return "system.resources", {}
        if any(keyword in compact for keyword in ("进程", "process")):
            return "process.list", {"limit": 10}
        if any(keyword in compact for keyword in ("错误日志", "系统日志", "journal", "日志")):
            return "logs.recent_errors", {"lines": 100}
        if "重启" in compact and "服务" in compact:
            service = self._extract_service_name(text)
            return "service.restart", {"service": service}
        if "服务" in compact and any(keyword in compact for keyword in ("状态", "查询", "查看")):
            service = self._extract_service_name(text)
            return "service.status", {"service": service}
        if any(keyword in compact for keyword in ("网络连接", "连接列表", "netstat")):
            return "network.connections", {"limit": 50}
        if any(keyword in compact for keyword in ("监听端口", "端口监听", "开放端口", "端口列表")):
            return "network.listening_ports", {"limit": 50}
        if any(keyword in compact for keyword in ("磁盘分区", "挂载点", "分区")):
            return "disk.partitions", {}
        if any(keyword in compact for keyword in ("用户列表", "本地用户", "系统用户")):
            return "user.list", {}
        if any(keyword in compact for keyword in ("定时任务", "计划任务", "cron")):
            return "schedule.cron", {}
        if any(keyword in compact for keyword in ("环境变量", "env")):
            return "environment.safe", {}
        if any(keyword in compact for keyword in ("软件包", "安装包", "rpm", "dpkg")):
            return "package.query", {"package": self._extract_package_name(text)}
        return None, {}

    def _extract_service_name(self, text: str) -> str:
        tokens = text.replace("，", " ").replace(",", " ").split()
        for token in tokens:
            if token.lower() in {"服务", "状态", "查询", "查看", "重启", "的"}:
                continue
            if any(char.isascii() and (char.isalnum() or char in "_.-@") for char in token):
                cleaned = "".join(char for char in token if char.isascii() and (char.isalnum() or char in "_.-@"))
                if cleaned:
                    return cleaned
        return ""

    def _extract_package_name(self, text: str) -> str:
        tokens = text.replace("，", " ").replace(",", " ").split()
        stop_words = {"查询", "查看", "软件包", "安装包", "版本", "列表", "的"}
        for token in tokens:
            if token.lower() in stop_words:
                continue
            cleaned = "".join(char for char in token if char.isascii() and (char.isalnum() or char in "+_.:-"))
            if cleaned:
                return cleaned
        return ""

    def _audit(
        self,
        text: str,
        tool_name: str | None,
        args: dict[str, Any],
        decision: PolicyDecision,
        result: ToolResult | None,
        started: float,
    ) -> None:
        self.audit.record(
            {
                "event_type": "agent.tool_call" if tool_name else "agent.intent",
                "request": text,
                "tool": tool_name,
                "args": args,
                "allowed": decision.allowed,
                "risk": decision.risk.value,
                "reason": decision.reason,
                "error_code": decision.error_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "result_ok": None if result is None else result.ok,
                "result_summary": None if result is None else result.summary,
            }
        )
