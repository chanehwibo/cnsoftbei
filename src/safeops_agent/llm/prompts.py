from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """你是麒麟操作系统安全智能运维 Agent 的意图理解模块。

你的职责是：
1. 理解用户的自然语言运维请求
2. 从可用工具列表中选择最匹配的工具
3. 从请求中提取该工具所需的参数

## 输出格式

严格输出 JSON 对象，不包含任何额外文本：
```json
{
  "tool": "tool_name",
  "args": {"param1": "value1"},
  "reasoning": "选择该工具的原因（一句话）"
}
```

## 规则

- 如果请求明确属于某个工具的能力范围，输出对应的 tool 和 args
- 如果请求不属于任何工具能力范围，输出 `{"tool": null, "args": {}, "reasoning": "原因"}`
- args 中的值必须从用户请求中提取，不要编造
- 服务名、包名等参数只提取用户明确提到的值
- 如果用户请求涉及危险操作（删除系统文件、格式化磁盘等），仍然匹配工具，安全策略会在后续阶段拦截
- 参数中不要包含注入字符（;、|、`、$、<、>）

## 可用工具列表

{tools_description}
"""


def build_tool_selection_messages(user_text: str, tools: list[dict[str, Any]]) -> list[dict[str, str]]:
    tools_desc = _format_tools(tools)
    system_content = SYSTEM_PROMPT.replace("{tools_description}", tools_desc)
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_text},
    ]


def build_tools_description(tools: list[dict[str, Any]]) -> str:
    return _format_tools(tools)


def _format_tools(tools: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for tool in tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")
        risk = tool.get("risk", "LOW")
        params = tool.get("parameters", {})
        required = tool.get("required", [])

        param_parts: list[str] = []
        for pname, pschema in params.items():
            ptype = pschema.get("type", "string") if isinstance(pschema, dict) else "string"
            req_mark = " (必填)" if pname in required else ""
            param_parts.append(f"    - {pname}: {ptype}{req_mark}")

        lines.append(f"### {name}")
        lines.append(f"描述: {desc}")
        lines.append(f"风险等级: {risk}")
        if param_parts:
            lines.append("参数:")
            lines.extend(param_parts)
        else:
            lines.append("参数: 无")
        lines.append("")

    return "\n".join(lines)
