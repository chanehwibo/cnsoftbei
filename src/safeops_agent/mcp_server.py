from __future__ import annotations

from typing import Any

from safeops_agent.security.policy import PolicyEngine
from safeops_agent.tools.registry import build_registry


class McpToolService:
    """Small MCP-style facade for listing and invoking registered tools."""

    def __init__(self, tools: dict | None = None, policy: PolicyEngine | None = None) -> None:
        self.tools = tools if tools is not None else build_registry()
        self.policy = policy if policy is not None else PolicyEngine()

    def list_tools(self) -> list[dict[str, Any]]:
        return [
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

    def call_tool(self, name: str, args: dict[str, Any], confirmed: bool = False) -> dict[str, Any]:
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
        decision = self.policy.evaluate_tool(tool, args=args, confirmed=confirmed)
        if not decision.allowed:
            return {
                "ok": False,
                "risk": decision.risk.value,
                "requires_confirmation": decision.requires_confirmation,
                "error_code": decision.error_code,
                "error": decision.reason,
                "data": {},
            }
        try:
            result = tool.handler(args)
        except Exception as exc:
            return {
                "ok": False,
                "summary": None,
                "data": {},
                "error": f"tool execution error: {exc}",
                "error_code": "TOOL_EXECUTION_ERROR",
                "risk": decision.risk.value,
                "requires_confirmation": False,
            }
        return {
            "ok": result.ok,
            "summary": result.summary,
            "data": result.data,
            "error": result.error,
            "error_code": None if result.ok else "TOOL_EXECUTION_FAILED",
            "risk": decision.risk.value,
            "requires_confirmation": False,
        }

    def _input_schema(self, tool) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": tool.parameters,
            "required": tool.required,
            "additionalProperties": False,
        }
