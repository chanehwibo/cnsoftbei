# MCP 接入

## 1. 服务

启动 stdio 服务端：

~~~powershell
$env:PYTHONPATH='src'
python -m safeops_agent.mcp_stdio
~~~

安装后可直接运行：

~~~powershell
safeops-mcp
~~~

传输使用 stdin/stdout，一行一条 JSON-RPC 2.0 消息。

## 2. 版本与生命周期

服务当前版本为 `2025-11-25`，兼容：

- `2025-06-18`；
- `2025-03-26`；
- `2024-11-05`。

客户端顺序：

1. 请求 `initialize`，提供 `protocolVersion`；
2. 发送通知 `notifications/initialized`；
3. 调用 `tools/list`、`tools/call` 或 `ping`。

在第 2 步之前调用工具会返回 `-32600`。

初始化请求：

~~~json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"demo","version":"1.0"}}}
~~~

初始化通知：

~~~json
{"jsonrpc":"2.0","method":"notifications/initialized"}
~~~

工具列表：

~~~json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
~~~

## 3. 工具契约

当前返回 25 个工具。每项包含：

- `name`、`description`、`category`、`risk`；
- 严格 `inputSchema`，默认禁止额外字段；
- `outputSchema`；
- `readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`；
- 扩展注解 `requiresConfirmation`。

Schema 校验覆盖必填、对象/数组/字符串/数值/布尔类型、长度、范围、正则、枚举和额外字段。

LOW 调用示例：

~~~json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"system.info","arguments":{}}}
~~~

结果同时包含 MCP `content`、`isError` 和机器可读 `structuredContent`。

## 4. 中风险确认

首次调用：

~~~json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"service.restart","arguments":{"service":"nginx"}}}
~~~

返回 `TOOL_CONFIRMATION_REQUIRED`、dry-run 和 `data.pending_action_id`，不会执行服务操作。

确认调用：

~~~json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"safeops.confirm","arguments":{"action_id":"复制首次调用返回的令牌"}}}
~~~

`safeops.confirm` 只消费 MCP 会话签发的一次性令牌，执行保存的工具和参数，并再次应用当前策略。

## 5. 安全

- 不暴露任意 Shell；
- 所有调用进入 PolicyEngine；
- HIGH 默认拒绝；
- 服务白名单和保护列表生效；
- 中风险没有布尔确认参数；
- 每次 tool call 与 confirm 写入统一 HMAC 审计；
- 参数不符合 Schema 时 handler 不运行。

## 6. 客户端配置示例

~~~json
{
  "mcpServers": {
    "safeops": {
      "command": "python",
      "args": ["-m", "safeops_agent.mcp_stdio"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\cnsoftbei\\src",
        "SAFEOPS_LLM_DISABLED": "1"
      }
    }
  }
}
~~~

MCP 服务本身不使用 LLM 路由；示例中的离线变量用于客户端同时启动其他 Agent 入口时保持确定性。
