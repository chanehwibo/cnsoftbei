# 开发记录

## 2026-06-22

### Step 1: 项目初始化

- 创建 `src/safeops_agent` 源码目录。
- 创建 `docs` 文档目录和 `tests` 测试目录。
- 创建 `pyproject.toml`，定义 Python 包和 CLI 入口。
- 创建 `README.md`，记录 MVP 运行方式、测试方式和当前限制。

### Step 2: MVP 核心设计

- 采用 Python 标准库优先，避免早期依赖安装阻塞。
- 将系统能力封装为固定工具，避免暴露任意 shell 执行。
- 将安全策略独立为 `PolicyEngine`，对工具风险和用户意图分别判断。
- 将审计日志独立为 `AuditLogger`，记录请求、工具、风险、决策和结果。

### Step 3: 基础运维工具实现

- 新增 `system.info`：采集系统、内核、架构、主机名和 `/etc/os-release` 信息。
- 新增 `system.resources`：采集 CPU、内存和磁盘指标。
- 新增 `process.list`：查看进程列表。
- 新增 `logs.recent_errors`：在麒麟/Linux 环境读取 `journalctl` 错误日志。
- 新增 `service.status`：在麒麟/Linux 环境查询 `systemctl status`。
- 新增 `service.restart`：登记为中风险工具，MVP 阶段只完成审批闭环，不执行真实重启。

### Step 4: 安全策略与审计实现

- 新增高风险意图过滤，当前可拦截删除根目录、格式化、关闭防火墙、禁用审计、提权等危险请求。
- 新增工具风险分级：低风险自动执行，中风险需要确认，高风险默认拒绝。
- 新增 JSONL 审计日志，记录时间、请求、工具、参数、风险、是否允许、决策原因和执行摘要。

### Step 5: CLI 与 MCP 风格接口实现

- 新增 `safeops_agent.cli`，支持自然语言请求、`--yes` 确认、`--json` 输出和自定义审计日志路径。
- 新增 `McpToolService`，提供工具列表和工具调用 facade，后续可替换为官方 MCP SDK。
- 新增 `.gitignore`，忽略运行期审计日志、Python 缓存和构建产物。

### Step 6: 初次验证

- `python -m unittest discover -s tests`：通过 8 个测试。
- `python -m safeops_agent.cli "查看系统信息" --json`：成功返回系统信息。
- `python -m safeops_agent.cli "查看CPU和内存" --json`：成功返回资源指标。
- `python -m safeops_agent.cli "重启 nginx 服务" --json`：被判定为中风险，要求确认。
- `python -m safeops_agent.cli "删除根目录所有文件" --json`：被高风险策略拒绝。
- 使用 UTF-8 读取 `data/audit.log`，确认审计日志内容正常。

### Step 7: 阶段计划补充

- 新增 `docs/MILESTONES.md`。
- 将后续工作拆为 M1 到 M6：MVP 闭环、麒麟适配、MCP 标准化、Web 工作台、大模型接入、答辩材料。
- 为每个阶段补充目标、任务和验收标准。

### Step 8: 本轮最终验证

- 再次执行 `python -m unittest discover -s tests`：通过 8 个测试。
- 再次执行 `python -m safeops_agent.cli "查看系统信息" --json`：成功返回系统信息。
- 核对项目文件清单，确认源码、测试、文档和运行期审计日志均已生成。

## 2026-06-22

### Step 9: 扩展只读运维工具

- 新增 `network.connections`：查看网络连接。
- 新增 `network.listening_ports`：查看监听端口。
- 新增 `disk.partitions`：查看磁盘分区和挂载点。
- 新增 `user.list`：查看本地用户列表。
- 新增 `schedule.cron`：查看 cron 定时任务配置。
- 新增 `environment.safe`：只返回安全白名单环境变量，避免泄露密钥。
- 新增 `package.query`：查询软件包列表或指定软件包版本，麒麟/Linux 环境优先使用 `rpm`，其次使用 `dpkg-query`。
- 更新自然语言路由，使 Agent 能匹配网络、端口、分区、用户、定时任务、环境变量和软件包相关请求。

### Step 10: 增强安全策略

- 扩展高风险意图关键词，覆盖 `mkfs`、`dd if=`、关机重启、递归改权限、清空防火墙规则、清空日志、删除系统目录等场景。
- 新增敏感路径识别，覆盖 `/`、`/etc`、`/boot`、`/usr`、`/bin`、`/sbin`、`/var/lib`、`/root` 和 `C:\Windows`。
- 新增工具参数校验，拦截 `;`、`&`、`|`、反引号、重定向等命令注入风险字符。
- 新增服务名和软件包名校验，避免把不可信文本传入系统工具。
- `PolicyDecision` 增加 `error_code`，为后续审计、MCP 错误格式和测试断言提供稳定字段。

### Step 11: 完善审计日志

- 审计日志新增 `event_id`，每条事件使用 UUID 标识。
- 审计日志新增 `source`、`host`、`pid`，记录请求来源和运行环境。
- Agent 审计事件新增 `event_type`，区分意图拦截和工具调用。
- Agent 审计事件新增 `duration_ms`，记录从接收请求到决策/执行完成的耗时。
- Agent 审计事件写入稳定 `error_code`，便于后续统计和测试。
- `AuditLogger` 新增 `recent(limit)`，支持读取最近审计事件。

### Step 12: 完善 MCP 工具定义

- `ToolSpec` 新增 `required` 和 `category` 字段。
- MCP 工具清单新增 `category`、`inputSchema` 和 `annotations`。
- `inputSchema` 采用 JSON Schema 风格，包含 `type`、`properties`、`required` 和 `additionalProperties`。
- MCP 调用结果统一返回 `ok`、`data`、`error`、`error_code`、`risk` 和 `requires_confirmation`。
- 未知工具返回稳定错误码 `TOOL_NOT_FOUND`。
- 新增 `docs/MCP_TOOLS.md`，记录工具元数据、调用结果格式和安全约束。

### Step 13: 补齐测试用例

- 扩展 `tests/test_policy.py`，覆盖中风险确认、服务名命令注入拦截、敏感路径破坏性意图拦截。
- 扩展 `tests/test_agent.py`，覆盖新增 `environment.safe` 工具路由。
- 扩展 `tests/test_mcp_service.py`，覆盖 `inputSchema`、`annotations`、中风险错误码和未知工具错误码。
- 新增 `tests/test_audit.py`，覆盖结构化审计事件字段。
- 新增 `tests/test_registry.py`，覆盖新增只读工具注册和工具分类字段。

### Step 14: 前五项最终验证

- 执行 `python -m unittest discover -s tests`：通过 15 个测试。
- 执行 `python -m safeops_agent.cli "查看环境变量" --json`：成功调用 `environment.safe`，只返回安全白名单环境变量。
- 执行 `python -m safeops_agent.cli "查看监听端口" --json`：成功调用 `network.listening_ports`。
- 执行 `python -m safeops_agent.cli "覆盖 /etc/passwd" --json`：被敏感路径安全策略拒绝，错误码为 `INTENT_SENSITIVE_PATH`。
- 执行 `python -m safeops_agent.cli "查询 nginx 软件包" --json`：成功进入 `package.query`，Windows 开发环境返回麒麟/Linux 适配说明。
- 使用 UTF-8 读取 `data/audit.log`，确认新增 `event_id`、`source`、`host`、`pid`、`event_type`、`duration_ms`、`error_code` 字段写入正常。

## 2026-06-23

### Step 15: 完成系统设计说明书

- 新增 `docs/SYSTEM_DESIGN.md`。
- 补充背景目标、总体架构、核心模块、数据流、安全设计、部署设计和后续演进。
- 明确 CLI/Web、Agent Core、MCP Tool Facade、Tool Registry、Policy Engine、Audit Logger 的职责边界。
- 记录低风险查询、中风险确认、高风险拒绝三类核心数据流。

### Step 16: 完成安全护栏设计文档

- 新增 `docs/SAFETY_GUARDRAILS.md`。
- 说明意图风险过滤、敏感路径保护、工具白名单、参数校验、风险分级和审批机制。
- 补充最小权限执行设计，包括普通用户运行、独立 executor 和 sudo 白名单方向。
- 补充审计追踪字段和安全测试清单。
- 明确当前残余风险：自然语言规则覆盖、Web 生产防护、麒麟最小权限验证、标准 MCP SDK 接入。

### Step 17: 完成测试方案与测试报告

- 新增 `docs/TEST_PLAN_AND_REPORT.md`。
- 覆盖功能测试、安全测试、MCP 测试和审计测试。
- 记录自动化测试命令和当前结果：15 个测试通过。
- 记录手工验证命令和已验证结果。
- 单独列出麒麟环境补测计划，避免将 Windows 开发环境结果误写为麒麟实测。

### Step 18: 完成答辩演示脚本

- 新增 `docs/DEMO_SCRIPT.md`。
- 按演示顺序整理系统状态感知、资源指标采集、网络端口排查、服务状态查询、中风险确认、高风险拦截、MCP 工具清单和审计日志追踪。
- 每个场景包含讲解词、命令和预期现象。
- 补充现场兜底方案，包括无麒麟环境、终端编码和 `PYTHONPATH` 配置问题。

### Step 19: 完成部署文档

- 新增 `docs/DEPLOYMENT.md`。
- 覆盖 Windows 开发环境、麒麟/Linux 环境、CLI、测试、审计日志、Web 工作台和 MCP facade 的运行方式。
- 补充常见问题，包括模块路径、中文乱码、Linux 命令不存在和权限不足。
- 明确 Web 工作台使用 Python 标准库启动，不依赖额外安装。

### Step 20: 完成 Web 运维工作台

- 新增 `src/safeops_agent/web_server.py`，使用 Python 标准库 `http.server` 提供本地 Web 服务。
- 新增 API：`GET /api/health`、`GET /api/tools`、`GET /api/audit`、`POST /api/agent`。
- 新增 `web/index.html`、`web/styles.css`、`web/app.js`。
- Web 页面包含常用任务、自然语言输入、确认中风险操作、结果展示、系统状态概览、MCP 工具清单和审计日志。
- Web 请求使用 `AuditLogger(..., source="web")` 写入审计日志，便于区分 CLI 和 Web 来源。

### Step 21: 完成演示数据和截图材料

- 新增 `demo/demo_requests.json`，整理答辩演示请求、预期工具和预期风险等级。
- 新增 `demo/sample_audit_events.jsonl`，提供可放入 PPT 的审计事件样例。
- 新增 `docs/DEMO_ASSETS.md`，列出 Web 首页、低风险查询、中风险确认、高风险拦截、MCP 工具清单和审计日志的截图建议。
- 补充 PPT 素材建议和演示数据生成命令。

### Step 22: 完成配置文件机制

- 新增 `config/app.yaml`，配置审计日志路径、Web 监听地址和端口。
- 新增 `config/policy.yaml`，外置高风险关键词和敏感路径。
- 新增 `config/tools.yaml`，预留工具开关和默认参数配置。
- 新增 `src/safeops_agent/config.py`，实现无需第三方依赖的简单 YAML 读取、项目路径解析和配置加载。
- CLI 和 Web 服务改为读取 `config/app.yaml` 中的审计日志路径。
- `PolicyEngine` 改为优先读取 `config/policy.yaml` 中的风险关键词和敏感路径。
- `ToolRegistry` 支持通过 `config/tools.yaml` 的 `disabled_tools` 禁用指定工具。

### Step 23: 完成开发脚本

- 新增 `scripts/test.ps1`，一键设置 `PYTHONPATH` 并运行单元测试。
- 新增 `scripts/demo.ps1`，一键执行答辩核心演示命令并输出最近审计日志。
- 新增 `scripts/web.ps1`，一键启动 Web 运维工作台。
- 新增 `scripts/show-tools.ps1`，一键输出 MCP 工具清单。
- 新增 `scripts/clean.ps1`，清理 Python 缓存目录。
- 新增 `docs/SCRIPTS.md`，记录脚本用途和运行方式。
