from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import LLMProvider, RuleBasedProvider, get_provider
from safeops_agent.security.policy import PolicyDecision, PolicyEngine
from safeops_agent.tools.models import RiskLevel, ToolResult
from safeops_agent.tools.registry import build_registry


class _ReasoningChain:
    """按顺序累积可回放的思维链步骤。"""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def add(
        self,
        stage: str,
        title: str,
        detail: str,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append({
            "step": len(self.steps) + 1,
            "stage": stage,
            "title": title,
            "detail": detail,
            "inputs": inputs or {},
            "outputs": outputs or {},
        })


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
    reasoning_chain: list[dict[str, Any]] | None = None


class SafeOpsAgent:
    def __init__(self, audit_logger: AuditLogger | None = None, policy: PolicyEngine | None = None, llm: LLMProvider | None = None) -> None:
        self.tools = build_registry()
        self.audit = audit_logger or AuditLogger()
        self.policy = policy or PolicyEngine()
        self.llm = llm if llm is not None else get_provider()
        self._last_tool: str | None = None
        self._last_args: dict[str, Any] = {}
        self._last_service: str = ""

    MAX_INPUT_LENGTH: int = 2000

    def handle(self, text: str, confirmed: bool = False) -> AgentResponse:
        started = time.perf_counter()
        chain = _ReasoningChain()
        original_text = text
        if len(text) > self.MAX_INPUT_LENGTH:
            return AgentResponse(
                ok=False,
                message=f"输入过长（{len(text)} 字符），请限制在 {self.MAX_INPUT_LENGTH} 字符以内。",
                risk=RiskLevel.LOW,
                risk_score=5,
                decision_summary="输入超长，已拒绝处理。",
            )

        # 步骤 1：上下文指代解析
        text = self._resolve_context(text)
        if text != original_text:
            chain.add("context_resolution", "上下文指代解析",
                      f"将指代词按最近会话对象还原：last_service=`{self._last_service}`",
                      inputs={"raw": original_text}, outputs={"resolved": text})
        else:
            chain.add("context_resolution", "上下文指代解析", "无指代词，输入原样进入意图筛查",
                      inputs={"raw": original_text}, outputs={"resolved": text})

        # 步骤 2：意图风险筛查（护栏第一层）
        intent_decision = self.policy.evaluate_intent(text)
        if intent_decision is not None:
            chain.add("intent_screening", "意图风险筛查",
                      f"命中高风险意图，直接拒绝：{intent_decision.reason}",
                      outputs={"allowed": False, "risk": intent_decision.risk.value,
                               "error_code": intent_decision.error_code})
            risk_score = self._risk_score(intent_decision)
            decision_summary = self._decision_summary(None, intent_decision, risk_score)
            self._audit(text, None, {}, intent_decision, None, started, risk_score,
                        decision_summary, reasoning_chain=chain.steps)
            return AgentResponse(
                ok=False,
                message=f"已拒绝执行：{intent_decision.reason}",
                risk=intent_decision.risk,
                risk_score=risk_score,
                decision_summary=decision_summary,
                reasoning_chain=chain.steps,
            )
        chain.add("intent_screening", "意图风险筛查", "未命中高风险关键词与敏感路径，进入工具选择",
                  outputs={"allowed": True})

        # 步骤 3：工具选择（LLM 意图理解，失败回退规则匹配）
        tool_name, args, intent_source, llm_reasoning = self._smart_select_tool(text)
        source_label = "大模型意图理解" if intent_source == "llm" else "规则关键词匹配"
        if tool_name is None:
            chain.add("tool_selection", "工具选择", f"{source_label}未匹配到可执行工具",
                      outputs={"tool": None, "source": intent_source})
            decision = PolicyDecision(allowed=True, risk=RiskLevel.LOW, reason="未匹配到工具")
            risk_score = 5
            decision_summary = self._decision_summary(None, decision, risk_score)
            self._audit(text, None, {}, decision, None, started, risk_score,
                        decision_summary, intent_source=intent_source, reasoning_chain=chain.steps)
            return AgentResponse(
                ok=False,
                message="暂未匹配到可执行运维工具。可以尝试：查看系统信息、查看CPU和内存、查看进程、查看错误日志、查询 nginx 服务状态、查看监听端口、诊断CPU和内存。",
                risk=RiskLevel.LOW,
                risk_score=risk_score,
                decision_summary=decision_summary,
                reasoning_chain=chain.steps,
            )
        detail = f"{source_label}选定工具 `{tool_name}`，参数 {args}"
        if intent_source == "llm" and llm_reasoning:
            detail += f"；模型推理：{llm_reasoning}"
        chain.add("tool_selection", "工具选择", detail,
                  outputs={"tool": tool_name, "args": args, "source": intent_source,
                           "llm_reasoning": llm_reasoning or None})

        # 步骤 4：风险裁决（护栏第二层：等级 + 参数 + 确认）
        tool = self.tools[tool_name]
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=confirmed)
        risk_score = self._risk_score(decision)
        decision_summary = self._decision_summary(tool_name, decision, risk_score)
        chain.add("risk_adjudication", "风险裁决",
                  f"工具风险等级 {decision.risk.value}，评分 {risk_score}/100，"
                  f"{'允许' if decision.allowed else '拒绝'}执行：{decision.reason}",
                  outputs={"allowed": decision.allowed, "risk": decision.risk.value,
                           "risk_score": risk_score,
                           "requires_confirmation": decision.requires_confirmation,
                           "error_code": decision.error_code, "confirmed": confirmed})
        if not decision.allowed:
            dry_run_plan = self._dry_run_plan(tool_name, args) if decision.requires_confirmation else None
            data = {"dry_run_plan": dry_run_plan} if dry_run_plan else None
            note = "需人工确认，已生成 dry-run 预演计划，未执行任何真实变更" if decision.requires_confirmation \
                else "决策为拒绝，流程终止，未执行"
            chain.add("execution", "执行阶段", note,
                      outputs={"executed": False, "dry_run": dry_run_plan is not None})
            self._audit(text, tool_name, args, decision, None, started, risk_score,
                        decision_summary, dry_run_plan, intent_source=intent_source,
                        reasoning_chain=chain.steps)
            return AgentResponse(
                ok=False,
                message=f"未执行 {tool_name}：{decision.reason}",
                tool=tool_name,
                risk=decision.risk,
                data=data,
                requires_confirmation=decision.requires_confirmation,
                risk_score=risk_score,
                decision_summary=decision_summary,
                reasoning_chain=chain.steps,
            )

        # 步骤 5：执行工具
        try:
            result = tool.handler(args)
        except Exception as exc:
            error_result = ToolResult(ok=False, summary="工具执行异常", error=str(exc))
            chain.add("execution", "执行阶段", f"工具执行抛出异常：{exc}",
                      outputs={"executed": True, "ok": False})
            self._audit(text, tool_name, args, decision, error_result, started, risk_score,
                        decision_summary, intent_source=intent_source, reasoning_chain=chain.steps)
            return AgentResponse(
                ok=False,
                message=f"工具 {tool_name} 执行异常：{exc}",
                tool=tool_name,
                risk=decision.risk,
                risk_score=risk_score,
                decision_summary=decision_summary,
                reasoning_chain=chain.steps,
            )
        chain.add("execution", "执行阶段",
                  f"工具执行{'成功' if result.ok else '失败'}：{result.summary}",
                  outputs={"executed": True, "ok": result.ok, "summary": result.summary})
        self._update_context(tool_name, args)
        self._audit(text, tool_name, args, decision, result, started, risk_score,
                    decision_summary, intent_source=intent_source, reasoning_chain=chain.steps)
        return AgentResponse(
            ok=result.ok,
            message=result.summary if result.ok else f"{result.summary}：{result.error}",
            tool=tool_name,
            risk=decision.risk,
            data=result.data,
            risk_score=risk_score,
            decision_summary=decision_summary,
            reasoning_chain=chain.steps,
        )

    def _smart_select_tool(self, text: str) -> tuple[str | None, dict[str, Any], str, str]:
        """先尝试 LLM 意图理解，失败则 fallback 到规则匹配。

        返回 (tool, args, source, reasoning)。reasoning 为 LLM 给出的思维链原文，
        规则匹配时为空字符串。
        """
        if not isinstance(self.llm, RuleBasedProvider):
            tool_descriptions = [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "required": t.required,
                    "risk": t.risk.value,
                }
                for t in self.tools.values()
            ]
            tool_name, args, reasoning = self.llm.select_tool(text, tool_descriptions)
            if tool_name and tool_name in self.tools:
                return tool_name, args, "llm", reasoning

        tool_name, args = self._select_tool(text)
        return tool_name, args, "rule", ""

    def _select_tool(self, text: str) -> tuple[str | None, dict[str, Any]]:
        normalized = text.lower()
        compact = normalized.replace(" ", "")

        if any(keyword in compact for keyword in ("诊断", "排查", "故障", "异常", "排障", "检查一下", "怎么了", "什么问题")):
            return self._select_diagnostic_tool(text, compact)
        if any(keyword in compact for keyword in ("系统信息", "系统版本", "操作系统", "内核", "主机信息", "主机名", "机器信息", "uname")):
            return "system.info", {}
        if any(keyword in compact for keyword in ("磁盘分区", "挂载点", "分区信息", "df", "磁盘挂载")):
            return "disk.partitions", {}
        if any(keyword in compact for keyword in ("cpu", "内存", "资源", "负载", "内存占用", "cpu占用", "使用率", "利用率", "load", "磁盘用量", "磁盘使用")):
            return "system.resources", {}
        if any(keyword in compact for keyword in ("进程", "process", "任务管理器", "跑了什么", "运行了什么")):
            return "process.list", {"limit": 10}
        if any(keyword in compact for keyword in ("错误日志", "系统日志", "journal", "日志", "报错", "error")):
            return "logs.recent_errors", {"lines": 100}
        if "重启" in compact and ("服务" in compact or self._has_service_hint(compact)):
            service = self._extract_service_name(text)
            return "service.restart", {"service": service}
        if ("服务" in compact or self._has_service_hint(compact)) and any(keyword in compact for keyword in ("状态", "查询", "查看", "跑着没", "运行", "是否正常", "在不在")):
            service = self._extract_service_name(text)
            return "service.status", {"service": service}
        if any(keyword in compact for keyword in ("网络连接", "连接列表", "netstat", "tcp连接", "udp连接", "网络状态")):
            return "network.connections", {"limit": 50}
        if any(keyword in compact for keyword in ("监听端口", "端口监听", "开放端口", "端口列表", "端口", "port", "哪些端口")):
            return "network.listening_ports", {"limit": 50}
        if any(keyword in compact for keyword in ("用户列表", "本地用户", "系统用户", "有哪些用户", "用户")):
            return "user.list", {}
        if any(keyword in compact for keyword in ("定时任务", "计划任务", "cron", "crontab", "定时")):
            return "schedule.cron", {}
        if any(keyword in compact for keyword in ("环境变量", "env", "path变量")):
            return "environment.safe", {}
        if any(keyword in compact for keyword in ("软件包", "安装包", "rpm", "dpkg", "装了什么", "有没有安装", "是否安装", "包版本")):
            return "package.query", {"package": self._extract_package_name(text)}
        return None, {}

    def _has_service_hint(self, compact: str) -> bool:
        known = ("nginx", "httpd", "apache", "mysql", "mariadb", "postgresql",
                 "redis", "docker", "sshd", "firewalld", "iptables", "crond",
                 "tomcat", "java", "node", "python", "kubelet")
        return any(s in compact for s in known)

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
        lower = text.lower()
        known_services = (
            "redis-server", "systemd-resolved", "networkmanager", "containerd",
            "apache2", "postgresql", "mariadb", "firewalld", "iptables",
            "dockerd", "kubelet", "apache", "mysqld", "nginx", "httpd",
            "mysql", "redis", "docker", "sshd", "crond", "cron",
            "tomcat", "named", "bind9",
        )
        for svc in known_services:
            if svc in lower:
                return svc
        tokens = text.replace("，", " ").replace(",", " ").split()
        stop_words = {"服务", "状态", "查询", "查看", "重启", "诊断", "排查", "故障", "异常", "的"}
        for token in tokens:
            if token.lower() in stop_words:
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

    def _resolve_context(self, text: str) -> str:
        compact = text.replace(" ", "").lower()
        context_refs = ("它", "该服务", "那个服务", "刚才的", "上一个", "同一个")
        if not any(ref in compact for ref in context_refs):
            return text
        if self._last_service:
            for ref in ("该服务", "那个服务", "刚才的服务", "上一个服务", "同一个服务"):
                if ref in text:
                    text = text.replace(ref, self._last_service, 1)
                    return text
            if "它" in text and ("服务" in compact or "重启" in compact or "状态" in compact or self._has_service_hint(compact)):
                text = text.replace("它", self._last_service, 1)
        return text

    def _update_context(self, tool_name: str, args: dict[str, Any]) -> None:
        self._last_tool = tool_name
        self._last_args = dict(args)
        service = str(args.get("service", "")).strip()
        if service:
            self._last_service = service

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
        if tool_name in {"service.restart", "service.start", "service.stop"}:
            return self._service_dry_run(tool_name, args)
        if tool_name == "file.apply":
            return self._file_apply_dry_run(args)
        if tool_name == "file.rollback":
            return self._file_rollback_dry_run(args)
        return None

    def _service_dry_run(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        service = str(args.get("service", "")).strip() or "未识别服务"
        verb = {"service.restart": "重启", "service.start": "启动", "service.stop": "停止"}[tool_name]
        inverse = {"service.restart": "重启前状态回退", "service.start": "service.stop 停止",
                   "service.stop": "service.start 启动"}[tool_name]
        return {
            "action": tool_name,
            "target": {"service": service},
            "pre_checks": [
                f"查看 {service} 服务状态",
                "查看监听端口，确认服务端口是否正常占用",
                "分析最近系统错误日志，确认是否存在启动失败或依赖异常",
            ],
            "planned_steps": [
                "记录当前服务状态和关键错误日志",
                f"在用户显式确认后对 {service} 执行{verb}流程",
                f"{verb}后再次检查服务状态、端口监听和错误日志",
            ],
            "rollback_suggestion": f"如果{verb}后服务不可用，可通过逆操作（{inverse}）回退，并查看状态与日志定位原因。",
            "risk_controls": [
                "未确认前不执行真实变更",
                "仅允许合法服务名参数",
                "所有决策和结果写入审计日志",
            ],
        }

    def _file_apply_dry_run(self, args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name", "")).strip() or "未指定文件"
        size = len(str(args.get("content", "")).encode("utf-8"))
        return {
            "action": "file.apply",
            "target": {"name": name, "bytes": size},
            "pre_checks": [
                "校验文件名合法性，限制在受管工作区内",
                "确认写入内容大小未超上限",
            ],
            "planned_steps": [
                f"写入前对 {name} 现有内容打快照",
                f"在用户显式确认后写入 {name}（{size} 字节）",
                "返回快照 ID，可随时一键回滚",
            ],
            "rollback_suggestion": "调用 file.rollback 并传入返回的 snapshot_id，即可将文件恢复到写入前状态（真实逆操作）。",
            "risk_controls": [
                "写入仅限受管工作区，禁止路径穿越",
                "写入前强制快照，保证可回滚",
                "所有决策和结果写入审计日志",
            ],
        }

    def _file_rollback_dry_run(self, args: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(args.get("snapshot_id", "")).strip() or "未指定快照"
        return {
            "action": "file.rollback",
            "target": {"snapshot_id": snapshot_id},
            "pre_checks": [
                "校验 snapshot_id 合法性",
                "确认快照记录与快照文件存在",
            ],
            "planned_steps": [
                f"定位快照 {snapshot_id} 对应的受管文件",
                "在用户显式确认后将文件恢复到快照时的内容（新建文件则删除）",
            ],
            "rollback_suggestion": "回滚本身即逆操作；如需再次前进，可重新执行 file.apply。",
            "risk_controls": [
                "恢复目标限定受管工作区",
                "快照缺失时安全失败",
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
        intent_source: str = "rule",
        reasoning_chain: list[dict[str, Any]] | None = None,
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
            "intent_source": intent_source,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "result_ok": None if result is None else result.ok,
            "result_summary": None if result is None else result.summary,
        }
        if dry_run_plan is not None:
            event["dry_run_plan"] = dry_run_plan
        if reasoning_chain is not None:
            event["reasoning_chain"] = reasoning_chain
        self.audit.record(event)
