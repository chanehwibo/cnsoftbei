from __future__ import annotations

from typing import Any

from safeops_agent.audit.logger import AuditLogger
from safeops_agent.security.pending import PendingActionStore
from safeops_agent.security.policy import PolicyEngine
from safeops_agent.tools.registry import build_registry


class McpToolService:
    """Small MCP-style facade for listing and invoking registered tools."""

    CONFIRM_TOOL = "safeops.confirm"

    def __init__(
        self,
        tools: dict | None = None,
        policy: PolicyEngine | None = None,
        pending_store: PendingActionStore | None = None,
        audit_logger: AuditLogger | None = None,
        session_id: str = "mcp",
    ) -> None:
        self.tools = tools if tools is not None else build_registry()
        self.policy = policy if policy is not None else PolicyEngine()
        self.pending = pending_store if pending_store is not None else PendingActionStore()
        self.audit = audit_logger if audit_logger is not None else AuditLogger(source="mcp")
        self.session_id = session_id

    def list_tools(self) -> list[dict[str, Any]]:
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "risk": tool.risk.value,
                "inputSchema": self._input_schema(tool),
                "annotations": {
                    "readOnlyHint": tool.risk.value == "LOW",
                    "destructiveHint": tool.risk.value == "HIGH",
                    "requiresConfirmation": tool.risk.value == "MEDIUM",
                },
            }
            for tool in self.tools.values()
        ]
        tools.append({
            "name": self.CONFIRM_TOOL,
            "description": "凭一次性确认令牌执行已预演并绑定参数的中风险操作",
            "category": "security",
            "risk": "MEDIUM",
            "inputSchema": {
                "type": "object",
                "properties": {"action_id": {"type": "string", "minLength": 32, "maxLength": 64}},
                "required": ["action_id"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "requiresConfirmation": False,
            },
        })
        return tools

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        outcome = self._dispatch(name, args)
        self.audit.record({
            "event_type": "mcp.confirm" if name == self.CONFIRM_TOOL else "mcp.tool_call",
            "session": self.session_id,
            "tool": name,
            "args": args,
            "allowed": bool(outcome.get("ok")),
            "risk": outcome.get("risk"),
            "requires_confirmation": bool(outcome.get("requires_confirmation")),
            "error_code": outcome.get("error_code"),
            "reason": outcome.get("error"),
            "result_ok": bool(outcome.get("ok")),
            "result_summary": outcome.get("summary"),
        })
        return outcome

    def _dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == self.CONFIRM_TOOL:
            return self._confirm(str(args.get("action_id", "")).strip())
        if name not in self.tools:
            return {
                "ok": False,
                "error_code": "TOOL_NOT_FOUND",
                "error": f"unknown tool: {name}",
                "risk": None,
                "requires_confirmation": False,
                "data": {},
            }
        tool = self.tools[name]
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=False)
        if not decision.allowed:
            data: dict[str, Any] = {}
            if decision.requires_confirmation and decision.error_code == "TOOL_CONFIRMATION_REQUIRED":
                action_id = self.pending.create(
                    name,
                    args,
                    f"MCP tool call: {name}",
                    session=self.session_id,
                )
                data = {
                    "pending_action_id": action_id,
                    "dry_run_plan": {
                        "action": name,
                        "target": args,
                        "planned_steps": [
                            "校验工具参数与安全策略",
                            "等待用户凭一次性令牌显式确认",
                            "确认后复核策略并精确执行已保存参数",
                        ],
                    },
                }
            return {
                "ok": False,
                "risk": decision.risk.value,
                "requires_confirmation": decision.requires_confirmation,
                "error_code": decision.error_code,
                "error": decision.reason,
                "data": data,
            }
        return self._execute(tool, args, decision.risk.value)

    def _confirm(self, action_id: str) -> dict[str, Any]:
        if not action_id:
            return {
                "ok": False,
                "error_code": "CONFIRM_TOKEN_INVALID",
                "error": "action_id is required",
                "risk": "MEDIUM",
                "requires_confirmation": False,
                "data": {},
            }
        record, error = self.pending.consume(action_id, session=self.session_id)
        if record is None:
            return {
                "ok": False,
                "error_code": "CONFIRM_TOKEN_INVALID",
                "error": error or "invalid confirmation token",
                "risk": "MEDIUM",
                "requires_confirmation": False,
                "data": {},
            }
        name = str(record.get("tool", ""))
        args = dict(record.get("args", {}))
        tool = self.tools.get(name)
        if tool is None:
            return {
                "ok": False,
                "error_code": "TOOL_NOT_FOUND",
                "error": f"unknown tool: {name}",
                "risk": "MEDIUM",
                "requires_confirmation": False,
                "data": {},
            }
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=True)
        if not decision.allowed:
            return {
                "ok": False,
                "risk": decision.risk.value,
                "requires_confirmation": decision.requires_confirmation,
                "error_code": decision.error_code,
                "error": decision.reason,
                "data": {},
            }
        return self._execute(tool, args, decision.risk.value)

    @staticmethod
    def _execute(tool, args: dict[str, Any], risk: str) -> dict[str, Any]:
        try:
            result = tool.handler(args)
        except Exception as exc:
            return {
                "ok": False,
                "summary": None,
                "data": {},
                "error": f"tool execution error: {exc}",
                "error_code": "TOOL_EXECUTION_ERROR",
                "risk": risk,
                "requires_confirmation": False,
            }
        return {
            "ok": result.ok,
            "summary": result.summary,
            "data": result.data,
            "error": result.error,
            "error_code": None if result.ok else "TOOL_EXECUTION_FAILED",
            "risk": risk,
            "requires_confirmation": False,
        }

    def _input_schema(self, tool) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": tool.parameters,
            "required": tool.required,
            "additionalProperties": False,
        }
