# MCP 工具定义

项目提供两层 MCP 能力：

1. **标准 MCP Server（`safeops_agent.mcp_stdio`）** —— 符合 Model Context Protocol
   的 JSON-RPC 2.0 stdio 服务端，可被 Claude Desktop 等真实 MCP 客户端直接连接。
2. **`McpToolService`** —— 工具注册、安全裁决与调用的内核，被 stdio server、
   Web 端、Agent 共享复用。

## 标准 MCP Server 使用

启动（stdio 传输，供 MCP 客户端拉起）：

```bash
PYTHONPATH=src python -m safeops_agent.mcp_stdio
# 或安装后： safeops-mcp
# 或 Windows： powershell scripts/mcp-stdio.ps1
```

实现的 JSON-RPC 方法：`initialize`、`notifications/initialized`、
`tools/list`、`tools/call`、`ping`，协议版本 `2024-11-05`。

在 Claude Desktop 的 `claude_desktop_config.json` 中注册：

```json
{
  "mcpServers": {
    "safeops": {
      "command": "python",
      "args": ["-m", "safeops_agent.mcp_stdio"],
      "env": { "PYTHONPATH": "src" }
    }
  }
}
```

`tools/call` 的每次调用都会先经 `PolicyEngine` 安全护栏裁决：LOW 直接放行、
MEDIUM 需 `confirmed=true`、HIGH 拒绝，参数注入与敏感路径一律拦截；被拦截时
响应 `isError=true` 并在 `structuredContent.error_code` 给出原因码。

## 手动握手示例

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | PYTHONPATH=src python -m safeops_agent.mcp_stdio
```

## 工具元数据

每个工具包含：

- `name`: 工具名，例如 `system.info`。
- `description`: 工具用途说明。
- `category`: 工具分类。
- `risk`: 风险等级，取值为 `LOW`、`MEDIUM`、`HIGH`。
- `inputSchema`: JSON Schema 风格输入定义。
- `annotations`: 工具行为提示，包括只读、破坏性和是否需要确认。

## 调用结果格式

成功：

```json
{
  "ok": true,
  "summary": "系统信息采集完成",
  "data": {},
  "error": null,
  "error_code": null,
  "risk": "LOW",
  "requires_confirmation": false
}
```

失败：

```json
{
  "ok": false,
  "error_code": "TOOL_CONFIRMATION_REQUIRED",
  "error": "中风险工具需要用户确认",
  "risk": "MEDIUM",
  "requires_confirmation": true,
  "data": {}
}
```

## 安全约束

- MCP 工具不暴露任意 shell 执行能力。
- 工具调用前必须经过 `PolicyEngine`。
- 中风险工具需要显式确认。
- 高风险工具默认拒绝。
- 参数校验失败时不会进入工具 handler。
