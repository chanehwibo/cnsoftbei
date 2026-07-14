# 错误码字典

本文档汇总 SafeOps Agent 各层的错误码及处理建议。错误码出现在 Agent 响应的
`error_code` 字段、审计日志事件、MCP 工具调用结果和 Web API 响应中，便于
排障时快速定位是哪一层、哪条规则拒绝了请求。

## 1. 错误码分层

| 层 | 前缀 / 形式 | 定义位置 |
| --- | --- | --- |
| 意图安全护栏 | `INTENT_*` | `security/policy.py` `evaluate_intent` |
| 工具风险裁决 | `TOOL_*` | `security/policy.py` `evaluate_tool`、`agent.py`、`mcp_server.py` |
| 参数校验 | `ARG_*` | `security/policy.py` `_validate_tool_args` |
| 确认令牌 | `CONFIRM_*` | `agent.py` `confirm` |
| MCP stdio 协议 | JSON-RPC 负数错误码 | `mcp_stdio.py` |
| Web API | HTTP 状态码 + `error` 文本 | `web_server.py` |

## 2. 意图安全护栏（INTENT_*）

在进入工具调用之前，对自然语言请求本身做安全筛查，命中即拒绝。

| 错误码 | 含义 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| `INTENT_HIGH_RISK_KEYWORD` | 命中高风险意图关键词 | 请求包含 `config/policy.yaml` `destructive_keywords` 中的关键词（如 `rm -rf`、格式化、删库） | 属预期拦截。若为误报，检查关键词表是否过宽后调整 `policy.yaml` |
| `INTENT_SENSITIVE_PATH` | 高风险操作涉及敏感路径 | 请求同时包含敏感路径（`sensitive_paths`）与危险动作词（删除/清空/覆盖等） | 属预期拦截。只读查询不受影响；确需变更请改用受管工作区（`file.apply`） |

## 3. 工具风险裁决（TOOL_*）

| 错误码 | 含义 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| `TOOL_CONFIRMATION_REQUIRED` | 中风险工具需要用户确认 | 未带确认调用 MEDIUM 风险工具（service.restart/start/stop、file.apply/rollback） | 不是错误：响应会附 dry-run 预案和 `pending_action_id`，用 CLI `--confirm <ID>`、Web 一键确认按钮或 `--yes` 放行 |
| `TOOL_HIGH_RISK` | 高风险工具默认拒绝 | 调用 HIGH 风险工具（当前注册表未包含此类工具，属防御性兜底） | 属预期行为，无需处理 |
| `TOOL_NOT_FOUND` | 工具不存在或已被禁用 | 工具名未注册，或在 `config/tools.yaml` `disabled_tools` 中；确认执行时工具被下线也会出现 | 用 `--list-tools` 查看可用工具；检查 `disabled_tools` 是否误禁（`scripts/validate-config.ps1` 会对未知工具名告警） |
| `TOOL_EXECUTION_ERROR` | 工具执行抛出异常 | 工具 handler 运行期异常（如系统命令缺失） | 查看 `error` 文本与审计日志定位；Windows 开发机上部分 Linux 命令属预期缺失 |
| `TOOL_EXECUTION_FAILED` | 工具执行完成但结果失败 | 工具正常返回但 `ok=false`（如 systemctl 返回非零） | 按 `error` 文本处理目标系统问题，与 Agent 本身无关 |

## 4. 参数校验（ARG_*）

工具参数在策略层统一校验，全部先于真实执行发生。

| 错误码 | 含义 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| `ARG_COMMAND_INJECTION` | 参数包含命令注入风险字符 | 参数含 `; & \| ` $ < >`、换行等字符 | 去掉特殊字符重试；正常运维参数不需要这些字符 |
| `ARG_SENSITIVE_PATH` | 中高风险工具参数涉及敏感路径 | MEDIUM/HIGH 工具的参数命中 `sensitive_paths` | 属预期拦截，受管文件操作请使用工作区相对名 |
| `ARG_SERVICE_REQUIRED` | 服务名缺失 | service.* 工具未提供 `service` 参数 | 在请求中明确服务名（如"重启 nginx 服务"），Agent 会追问缺失参数 |
| `ARG_SERVICE_INVALID` | 服务名包含非法字符 | 服务名含 `@_.-` 与字母数字之外的字符 | 使用合法 systemd 单元名 |
| `ARG_PACKAGE_INVALID` | 软件包名包含非法字符 | `package.query` 的包名含 `+_.:-` 与字母数字之外的字符 | 使用合法包名 |

## 5. 确认令牌（CONFIRM_*）

| 错误码 | 含义 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| `CONFIRM_TOKEN_INVALID` | 确认令牌无效 | 令牌不存在、已被使用（一次性）、超过 10 分钟有效期，或与当前会话不匹配 | 重新发起原始请求获取新的 `pending_action_id`；`reason` 文本会说明具体原因 |

## 6. MCP stdio 协议错误码（JSON-RPC 2.0 标准）

`python -m safeops_agent.mcp_stdio` 通道返回标准 JSON-RPC 错误对象
`{"code": <负数>, "message": <说明>}`。

| code | 名称 | 触发条件 |
| --- | --- | --- |
| `-32700` | Parse error | 请求行不是合法 JSON |
| `-32600` | Invalid request | 不是合法的 JSON-RPC 2.0 请求对象 / 缺少 method |
| `-32601` | Method not found | method 不在 initialize/tools/list/tools/call 等已实现方法内 |
| `-32602` | Invalid params | `tools/call` 缺少工具名 name，或 arguments 不是对象 |
| `-32603` | Internal error | 处理请求时的未捕获异常 |

注意：工具层的拒绝（如需要确认、参数非法）不会映射为 JSON-RPC 错误，而是
在 `tools/call` 的正常结果中以 `ok=false + error_code` 返回，错误码见上文各节。

## 7. Web API 错误（HTTP 状态码）

| 状态码 | `error` 文本 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| 400 | `invalid content-length` / `invalid json` | 请求头或请求体格式非法 | 检查客户端请求构造 |
| 400 | `request or action_id is required` | POST /api/agent 既无 request 也无 action_id | 至少提供一项 |
| 401 | `unauthorized` | 设置了 `SAFEOPS_TOKEN` 但请求未带正确的 Bearer Token | 携带 `Authorization: Bearer <token>`（SSE 可用 `?token=`） |
| 404 | `not found` | 路径不存在或静态文件越界 | 检查 API 路径 |
| 413 | `request body too large` | 请求体超过 64 KB | 缩短请求 |
| 429 | `rate limit exceeded` | 单 IP 每 60 秒超过 30 次请求 | 稍后重试 |
| 202 | —（正常 JSON 响应） | Agent 拒绝执行或要求确认（`ok=false`） | 不是传输错误：按响应内的 `error_code`/`requires_confirmation` 处理 |

## 8. 排障入口

- 按错误码筛选审计日志：`python -m safeops_agent.cli --show-audit --audit-risk HIGH`
  （或 Web 审计区筛选、`GET /api/audit?risk=HIGH`），事件中的 `error_code`、
  `reason`、`reasoning_chain` 记录了完整裁决过程。
- 配置类问题先跑 `scripts/validate-config.ps1`。
