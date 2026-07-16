# 错误码字典

错误码出现在 Agent 审计、MCP `structuredContent` 和部分 JSON 响应中。被策略拒绝不表示协议传输失败。

## 1. 意图

| 错误码 | 含义 |
| --- | --- |
| `INTENT_HIGH_RISK_KEYWORD` | 命中破坏性或越权关键词 |
| `INTENT_SENSITIVE_PATH` | 危险动作涉及系统敏感路径 |

处理：确认请求用途；只读查询改用相应 LOW 工具，文件写入改用受管工作区。不要通过改写字符绕过策略。

## 2. 工具裁决

| 错误码 | 含义 |
| --- | --- |
| `TOOL_CONFIRMATION_REQUIRED` | MEDIUM 工具已预演，等待一次性令牌确认 |
| `TOOL_HIGH_RISK` | HIGH 工具默认拒绝 |
| `TOOL_NOT_FOUND` | 工具未注册、被禁用或确认时已不可用 |
| `TOOL_EXECUTION_ERROR` | handler 抛出异常 |
| `TOOL_EXECUTION_FAILED` | handler 正常返回 `ok=false` |

`TOOL_CONFIRMATION_REQUIRED` 的 `data.pending_action_id` 用于 CLI `--confirm`、Web `action_id` 或 MCP `safeops.confirm`。

## 3. 参数

| 错误码 | 含义 |
| --- | --- |
| `ARG_SCHEMA_VALIDATION` | MCP 参数缺失、类型/范围/长度错误或有额外字段 |
| `ARG_COMMAND_INJECTION` | 参数含命令注入字符或控制字符 |
| `ARG_SENSITIVE_PATH` | 中高风险参数命中敏感路径 |
| `ARG_SERVICE_REQUIRED` | 服务名缺失 |
| `ARG_SERVICE_INVALID` | 服务名格式非法 |
| `ARG_PROTECTED_SERVICE` | 请求变更保护服务 |
| `ARG_SERVICE_NOT_ALLOWLISTED` | 服务不在允许变更列表 |
| `ARG_PACKAGE_INVALID` | 软件包名格式非法 |

`file.apply` 的 `content` 是数据字段，不按 Shell 参数解析；文件名仍执行路径与标识符校验。

## 4. 确认

| 错误码 | 含义 |
| --- | --- |
| `CONFIRM_TOKEN_INVALID` | 令牌不存在、已使用、已过期或会话不匹配 |

重新发起原始 MEDIUM 请求可获得新令牌。CLI、Web 和 MCP 令牌绑定各自会话，不能跨入口混用。

## 5. JSON-RPC

| code | 含义 |
| --- | --- |
| `-32700` | JSON 解析失败 |
| `-32600` | JSON-RPC 请求无效或 MCP 生命周期未完成 |
| `-32601` | 未知方法 |
| `-32602` | 方法参数无效 |
| `-32603` | 服务内部异常 |

工具策略拒绝仍是 `tools/call` 的正常 result，通过 `isError=true` 和 `structuredContent.error_code` 表达。

## 6. Web HTTP

| 状态 | 含义 |
| --- | --- |
| 200 | 请求成功、登录成功或公开健康检查 |
| 202 | Agent 已处理，但动作被拒绝或等待确认 |
| 400 | Content-Length、JSON、对象根节点或必要字段无效 |
| 401 | Bearer 或会话 Cookie 无效 |
| 404 | API/静态资源不存在 |
| 413 | 请求体超过 64 KiB |
| 429 | 单 IP 超过限流 |

SSE 不接受 URL 查询参数令牌。浏览器先调用 `POST /api/auth` 获取 HttpOnly Cookie；程序接口使用 `Authorization: Bearer <token>`。

## 7. 排查

~~~powershell
python -m safeops_agent.config_check
python -m safeops_agent.cli --show-audit --audit-risk HIGH
python -m safeops_agent.cli --show-audit --audit-tool service
python -m safeops_agent.cli --verify-audit
~~~

审计事件中的 `error_code`、`reason`、`decision_summary` 和结构化决策轨迹给出裁决事实。
