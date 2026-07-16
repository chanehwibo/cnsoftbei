from __future__ import annotations

import re
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
                "outputSchema": self._output_schema(),
                "annotations": {
                    "readOnlyHint": tool.risk.value == "LOW",
                    "destructiveHint": tool.risk.value == "HIGH",
                    "idempotentHint": tool.risk.value == "LOW",
                    "openWorldHint": False,
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
            "outputSchema": self._output_schema(),
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
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
            error = self._validate_schema(
                args,
                {
                    "type": "object",
                    "properties": {"action_id": {"type": "string", "minLength": 32, "maxLength": 64}},
                    "required": ["action_id"],
                    "additionalProperties": False,
                },
            )
            if error:
                return self._schema_error("MEDIUM", error)
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
        schema_error = self._validate_schema(args, self._input_schema(tool))
        if schema_error:
            return self._schema_error(tool.risk.value, schema_error)
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

    @staticmethod
    def _output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "summary": {"type": ["string", "null"]},
                "data": {"type": "object"},
                "error": {"type": ["string", "null"]},
                "error_code": {"type": ["string", "null"]},
                "risk": {"type": ["string", "null"]},
                "requires_confirmation": {"type": "boolean"},
            },
            "required": ["ok", "data", "error_code", "risk", "requires_confirmation"],
        }

    @staticmethod
    def _schema_error(risk: str, message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "summary": None,
            "data": {},
            "error": message,
            "error_code": "ARG_SCHEMA_VALIDATION",
            "risk": risk,
            "requires_confirmation": False,
        }

    @classmethod
    def _validate_schema(cls, value: Any, schema: dict[str, Any], path: str = "arguments") -> str | None:
        expected = schema.get("type")
        expected_types = expected if isinstance(expected, list) else [expected] if expected else []
        if expected_types and not cls._matches_type(value, expected_types):
            return f"{path} 类型不匹配，期望 {expected_types}"
        if isinstance(value, dict):
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            for key in required:
                if key not in value:
                    return f"{path} 缺少必填参数：{key}"
            if schema.get("additionalProperties") is False:
                extras = sorted(set(value) - set(properties))
                if extras:
                    return f"{path} 包含未声明参数：{', '.join(extras)}"
            for key, item in value.items():
                item_schema = properties.get(key)
                if isinstance(item_schema, dict):
                    error = cls._validate_schema(item, item_schema, f"{path}.{key}")
                    if error:
                        return error
        if isinstance(value, str):
            if "minLength" in schema and len(value) < int(schema["minLength"]):
                return f"{path} 长度小于 {schema['minLength']}"
            if "maxLength" in schema and len(value) > int(schema["maxLength"]):
                return f"{path} 长度超过 {schema['maxLength']}"
            if "pattern" in schema and re.fullmatch(str(schema["pattern"]), value) is None:
                return f"{path} 格式不匹配"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                return f"{path} 小于最小值 {schema['minimum']}"
            if "maximum" in schema and value > schema["maximum"]:
                return f"{path} 超过最大值 {schema['maximum']}"
        if "enum" in schema and value not in schema["enum"]:
            return f"{path} 不在允许值范围"
        return None

    @staticmethod
    def _matches_type(value: Any, expected_types: list[Any]) -> bool:
        mapping = {
            "null": lambda item: item is None,
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
        }
        return any(kind in mapping and mapping[kind](value) for kind in expected_types)
