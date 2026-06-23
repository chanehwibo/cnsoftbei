# 系统设计说明书

## 1. 背景与目标

本项目面向中国软件杯赛题 1 A 组，目标是在麒麟操作系统上构建安全智能运维 Agent。系统将自然语言请求转换为受控的运维工具调用，使大模型具备系统状态感知、指标采集、日志分析和管理任务编排能力，同时通过安全护栏降低误操作风险。

系统设计遵循三条原则：

- 工具白名单：Agent 只能调用已注册工具，不执行模型自由生成的 shell 命令。
- 本地强制安全：风险判断、参数校验、审批和审计由本地策略执行，不依赖模型自觉。
- 可审计可复盘：所有请求、风险判断、工具参数和执行摘要均写入结构化审计日志。

## 2. 总体架构

系统由六个核心模块组成：

- CLI/Web 交互层：接收用户自然语言请求，展示结果、风险和审计信息。
- Agent Core：负责意图匹配、工具选择、策略调用、结果汇总。
- MCP Tool Facade：提供 MCP 风格工具发现和调用接口。
- Tool Registry：注册系统信息、资源指标、网络、服务、日志、用户等运维工具。
- Policy Engine：执行高风险意图拦截、工具风险判断、参数校验和确认控制。
- Audit Logger：写入 JSONL 审计日志，支撑追责、演示和测试。

```text
User
  |
CLI / Web
  |
SafeOpsAgent
  |---- PolicyEngine
  |---- ToolRegistry ---- Fixed Tools ---- OS
  |---- AuditLogger ---- data/audit.log
  |
MCP Tool Facade
```

## 3. 模块设计

### 3.1 Agent Core

文件：`src/safeops_agent/agent.py`

职责：

- 接收自然语言请求。
- 调用 `PolicyEngine.evaluate_intent` 做意图层风险过滤。
- 通过 `_select_tool` 将请求映射到固定工具。
- 调用 `PolicyEngine.evaluate_tool` 做工具层风险和参数校验。
- 调用工具 handler。
- 汇总响应并写入审计日志。

### 3.2 Tool Registry

文件：`src/safeops_agent/tools/registry.py`

当前工具：

- `system.info`
- `system.resources`
- `process.list`
- `logs.recent_errors`
- `service.status`
- `network.connections`
- `network.listening_ports`
- `disk.partitions`
- `user.list`
- `schedule.cron`
- `environment.safe`
- `package.query`
- `service.restart`

每个工具包含名称、描述、风险等级、参数 Schema、必填字段和分类。

### 3.3 Policy Engine

文件：`src/safeops_agent/security/policy.py`

职责：

- 高风险关键词识别。
- 敏感路径识别。
- 命令注入字符拦截。
- 服务名和软件包名校验。
- 低风险自动执行。
- 中风险要求确认。
- 高风险默认拒绝。

### 3.4 Audit Logger

文件：`src/safeops_agent/audit/logger.py`

审计日志采用 JSONL 格式，每行一条事件。关键字段包括：

- `event_id`
- `ts`
- `source`
- `host`
- `pid`
- `event_type`
- `request`
- `tool`
- `args`
- `risk`
- `allowed`
- `reason`
- `error_code`
- `duration_ms`
- `result_ok`
- `result_summary`

### 3.5 MCP Tool Facade

文件：`src/safeops_agent/mcp_server.py`

当前实现是轻量 MCP 风格 facade，提供：

- `list_tools()`
- `call_tool(name, args, confirmed)`

后续可替换为官方 MCP SDK，工具注册、安全策略和审计结构不需要大改。

## 4. 数据流

### 4.1 低风险查询

```text
用户请求 -> 意图检查 -> 工具匹配 -> 参数校验 -> 工具执行 -> 返回结果 -> 写审计
```

示例：

```text
查看监听端口 -> network.listening_ports -> LOW -> 执行 netstat/ss -> 返回端口列表
```

### 4.2 中风险操作

```text
用户请求 -> 意图检查 -> 工具匹配 -> 风险判断 -> 未确认则拒绝执行并提示确认 -> 写审计
```

示例：

```text
重启 nginx 服务 -> service.restart -> MEDIUM -> 需要 --yes
```

### 4.3 高风险请求

```text
用户请求 -> 命中高风险意图或敏感路径 -> 拒绝 -> 写审计
```

示例：

```text
覆盖 /etc/passwd -> INTENT_SENSITIVE_PATH -> 拒绝
```

## 5. 安全设计

系统不暴露任意 shell 执行工具。所有 OS 调用均由固定 handler 完成，命令参数来自受控解析和策略校验。

安全控制点：

- 意图层：先拦截明显破坏性请求。
- 工具层：按工具风险等级决定是否执行。
- 参数层：拒绝命令注入字符和非法标识符。
- 执行层：只调用固定命令模板。
- 审计层：记录完整决策链路。

## 6. 部署设计

开发环境：

- Windows + Python 3.10+
- 使用 `PYTHONPATH=src` 运行 CLI 和测试

目标环境：

- 麒麟操作系统
- Python 3.10+
- systemd、journalctl、rpm 或 dpkg-query

部署方式：

- MVP 阶段：CLI 本地运行。
- 演示阶段：启动本地 Web 运维工作台。
- 集成阶段：替换为标准 MCP Server，对接模型客户端。

## 7. 后续演进

- 接入真实 MCP SDK。
- 接入本地或云端大模型。
- 完善麒麟环境适配测试。
- 增加 sudo 白名单和最小权限执行用户。
- 增加 Web 审批流。
