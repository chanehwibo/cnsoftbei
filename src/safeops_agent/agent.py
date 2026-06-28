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
    risk_score: int | None = None
    decision_summary: str | None = None


class SafeOpsAgent:
    def __init__(self, audit_logger: AuditLogger | None = None, policy: PolicyEngine | None = None) -> None:
        self.tools = build_registry()
        self.audit = audit_logger or AuditLogger()
        self.policy = policy or PolicyEngine()

    def handle(self, text: str, confirmed: bool = False) -> AgentResponse:
        started = time.perf_counter()
        intent_decision = self.policy.evaluate_intent(text)
        if intent_decision is not None:
            risk_score = self._risk_score(intent_decision)
            decision_summary = self._decision_summary(None, intent_decision, risk_score)
            self._audit(text, None, {}, intent_decision, None, started, risk_score, decision_summary)
            return AgentResponse(
                ok=False,
                message=f"已拒绝执行：{intent_decision.reason}",
                risk=intent_decision.risk,
                risk_score=risk_score,
                decision_summary=decision_summary,
            )

        tool_name, args = self._select_tool(text)
        if tool_name is None:
            decision = PolicyDecision(allowed=True, risk=RiskLevel.LOW, reason="未匹配到工具")
            risk_score = 5
            decision_summary = self._decision_summary(None, decision, risk_score)
            self._audit(text, None, {}, decision, None, started, risk_score, decision_summary)
            return AgentResponse(
                ok=False,
                message="暂未匹配到可执行运维工具。可以尝试：查看系统信息、查看CPU和内存、查看进程、查看错误日志、查询 nginx 服务状态、查看监听端口、诊断CPU和内存。",
                risk=RiskLevel.LOW,
                risk_score=risk_score,
                decision_summary=decision_summary,
            )

        tool = self.tools[tool_name]
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=confirmed)
        risk_score = self._risk_score(decision)
        decision_summary = self._decision_summary(tool_name, decision, risk_score)
        if not decision.allowed:
            dry_run_plan = self._dry_run_plan(tool_name, args) if decision.requires_confirmation else None
            data = {"dry_run_plan": dry_run_plan} if dry_run_plan else None
            self._audit(text, tool_name, args, decision, None, started, risk_score, decision_summary, dry_run_plan)
            return AgentResponse(
                ok=False,
                message=f"未执行 {tool_name}：{decision.reason}",
                tool=tool_name,
                risk=decision.risk,
                data=data,
                requires_confirmation=decision.requires_confirmation,
                risk_score=risk_score,
                decision_summary=decision_summary,
            )

        result = tool.handler(args)
        self._audit(text, tool_name, args, decision, result, started, risk_score, decision_summary)
        return AgentResponse(
            ok=result.ok,
            message=result.summary if result.ok else f"{result.summary}：{result.error}",
            tool=tool_name,
            risk=decision.risk,
            data=result.data,
            risk_score=risk_score,
            decision_summary=decision_summary,
        )

    def _select_tool(self, text: str) -> tuple[str | None, dict[str, Any]]:
        normalized = text.lower()
        compact = normalized.replace(" ", "")

        if any(keyword in compact for keyword in ("诊断", "排查", "故障", "异常")):
            return self._select_diagnostic_tool(text, compact)
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

    def _select_diagnostic_tool(self, text: str, compact: str) -> tuple[str, dict[str, Any]]:
        if any(keyword in compact for keyword in ("端口", "监听")):
            return "diagnostics.network_ports", {"limit": 50}
        if "服务" in compact:
            return "diagnostics.service", {"service": self._extract_service_name(text)}
        if any(keyword in compact for keyword in ("日志", "journal", "错误")):
            return "diagnostics.logs", {"lines": 100}
        if any(keyword in compact for keyword in ("磁盘", "空间", "挂载")):
            return "diagnostics.disk", {}
        if any(keyword in compact for keyword in ("cpu", "内存", "资源", "负载")):
            return "diagnostics.resources", {}
        return "diagnostics.overview", {}

    def _extract_service_name(self, text: str) -> str:
        tokens = text.replace("，", " ").replace(",", " ").split()
        for token in tokens:
            if token.lower() in {"服务", "状态", "查询", "查看", "重启", "诊断", "排查", "故障", "异常", "的"}:
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

    def _risk_score(self, decision: PolicyDecision) -> int:
        base = {
            RiskLevel.LOW: 10,
            RiskLevel.MEDIUM: 60,
            RiskLevel.HIGH: 90,
        }[decision.risk]
        if decision.requires_confirmation:
            base = max(base, 65)
        if decision.error_code == "INTENT_SENSITIVE_PATH":
            base = 95
        elif decision.error_code == "ARG_COMMAND_INJECTION":
            base = 90
        elif not decision.allowed and decision.risk == RiskLevel.HIGH:
            base = max(base, 90)
        elif not decision.allowed and decision.risk == RiskLevel.LOW:
            base = max(base, 20)
        return min(100, max(0, base))

    def _decision_summary(self, tool_name: str | None, decision: PolicyDecision, risk_score: int) -> str:
        if decision.requires_confirmation:
            action = "需要人工确认"
        elif decision.allowed:
            action = "允许执行"
        else:
            action = "拒绝执行"
        target = f"匹配工具 `{tool_name}`" if tool_name else "未进入具体工具调用"
        return f"{target}，风险等级 {decision.risk.value}，风险评分 {risk_score}/100，决策：{action}，原因：{decision.reason}。"

    def _dry_run_plan(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any] | None:
        if tool_name != "service.restart":
            return None
        service = str(args.get("service", "")).strip() or "未识别服务"
        return {
            "action": "service.restart",
            "target": {"service": service},
            "pre_checks": [
                f"查看 {service} 服务状态",
                "查看监听端口，确认服务端口是否正常占用",
                "分析最近系统错误日志，确认是否存在启动失败或依赖异常",
            ],
            "planned_steps": [
                "记录当前服务状态和关键错误日志",
                f"在用户显式确认后执行 {service} 服务重启流程",
                "重启后再次检查服务状态、端口监听和错误日志",
            ],
            "rollback_suggestion": "如果服务重启后不可用，立即查看服务状态和日志，必要时恢复配置或回退到变更前版本。",
            "risk_controls": [
                "未确认前不执行真实变更",
                "仅允许合法服务名参数",
                "所有决策和结果写入审计日志",
            ],
        }

    def _audit(
        self,
        text: str,
        tool_name: str | None,
        args: dict[str, Any],
        decision: PolicyDecision,
        result: ToolResult | None,
        started: float,
        risk_score: int,
        decision_summary: str,
        dry_run_plan: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "event_type": "agent.tool_call" if tool_name else "agent.intent",
            "request": text,
            "tool": tool_name,
            "args": args,
            "allowed": decision.allowed,
            "risk": decision.risk.value,
            "risk_score": risk_score,
            "requires_confirmation": decision.requires_confirmation,
            "reason": decision.reason,
            "decision_summary": decision_summary,
            "error_code": decision.error_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "result_ok": None if result is None else result.ok,
            "result_summary": None if result is None else result.summary,
        }
        if dry_run_plan is not None:
            event["dry_run_plan"] = dry_run_plan
        self.audit.record(event)
