# MCP 工具定义

当前项目提供 `McpToolService` 作为 MCP 风格 facade，后续可替换为标准 MCP Server。

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
