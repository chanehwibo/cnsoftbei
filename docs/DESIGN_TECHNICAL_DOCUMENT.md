# SafeOps Agent 设计技术文档

> 文档状态：与 2026-07-16 当前实现同步。软件级验收已覆盖 Windows、真实 DeepSeek 调用和安装交付；麒麟硬件实机验证仍属于下一阶段。

## 1. 作品目标

SafeOps Agent 面向麒麟操作系统的日常状态查询、故障诊断、受控服务操作和受管文件变更。系统把自然语言交互的易用性与本地确定性安全控制结合起来，保证“理解”和“授权”分离。

设计目标：

1. 用户使用中文自然语言表达运维意图；
2. 系统只能选择固定白名单工具，不能生成任意 Shell 执行；
3. 低、中、高风险具有清晰且不可绕过的处理路径；
4. 中风险预演内容与确认执行内容完全一致；
5. 所有入口共享策略、Schema 和签名审计；
6. 在线模型不可用时核心运维能力继续工作；
7. 源码运行与 wheel 安装后的资源解析行为一致。

## 2. 总体设计

系统分为六层：

| 层 | 组件 | 输出 |
| --- | --- | --- |
| 入口 | CLI、Web、MCP stdio | 请求、会话、结构化参数 |
| 意图 | 输入筛查、LLM Provider、规则路由 | 候选工具和参数 |
| 策略 | PolicyEngine、配置规则 | PolicyDecision |
| 执行 | Tool Registry、诊断、受管文件事务 | ToolResult |
| 确认 | PendingActionStore | 加密的一次性动作记录 |
| 审计 | AuditLogger | 脱敏、签名、锚定 JSONL |

入口不直接访问系统命令。所有操作先查 Tool Registry，再由 PolicyEngine 裁决。模型输出仍被视为不可信输入。

## 3. 意图理解

### 3.1 输入筛查

在调用模型之前，系统先检查长度、高危关键词、危险动作与敏感路径组合。命中后直接返回 HIGH，不向外部模型发送请求。

### 3.2 双通道路由

- DeepSeekProvider 调用 OpenAI 兼容接口，返回工具名、对象参数、一句话选择说明和可选追问；
- OpenAICompatibleProvider 复用同一 `chat/completions` 契约，可连接 OpenAI 兼容服务；
- RuleBasedProvider 独立完成离线确定性路由，Agent 只负责编排并保留兼容入口；
- API Key 缺失、网络异常、超时、非法 JSON、未知工具时自动使用本地路由；
- `SAFEOPS_LLM_DISABLED=1` 可强制离线。

模型只提出候选工具。工具存在性、必填参数、类型、取值范围、注入字符、敏感路径和风险等级全部由本地代码验证。

### 3.3 请求时序

~~~text
用户输入
  -> 长度与高危意图筛查（命中则直接 HIGH）
  -> DeepSeek/OpenAI 兼容 Provider 或 RuleBasedProvider
  -> 固定工具名 + JSON 参数
  -> 注册表存在性、Schema 与参数安全校验
  -> PolicyEngine 风险、服务与路径裁决
  -> LOW 执行 / MEDIUM 预演与令牌 / HIGH 拒绝
  -> ToolResult + 结构化决策轨迹 + 签名审计
~~~

在线模型返回的工具名、参数、追问和选择说明全部按不可信输入处理。Provider 失败只影响意图增强，不影响本地策略和固定工具能力。

## 4. 风险模型

| 等级 | 含义 | 行为 |
| --- | --- | --- |
| LOW | 只读采集与诊断 | 校验后执行 |
| MEDIUM | 服务生命周期或受管文件变更 | 返回 dry-run 与一次性令牌 |
| HIGH | 破坏性、越权、敏感路径或保护服务 | 默认拒绝 |

中风险流程：

~~~text
请求 -> 参数与策略裁决 -> 保存 tool + args -> 返回 dry-run/action_id
     -> 用户提交 action_id -> 会话/时限/一次性校验
     -> 重新应用当前策略 -> 精确执行保存的 tool + args -> 审计
~~~

不存在布尔确认捷径。CLI 使用 `--confirm ACTION_ID`；MCP 使用 `safeops.confirm`；Web 提交 `action_id`。

## 5. 工具系统

当前注册 25 个工具：

- 系统与资源：`system.info`、`system.resources`、`process.list`；
- 日志、网络、磁盘、用户、计划任务、环境与软件包查询；
- 六类诊断工具；
- 服务 `status/start/stop/restart`；
- 受管文件 `apply/rollback/list_managed`；
- MCP 确认工具 `safeops.confirm`。

每个工具声明名称、说明、分类、风险、参数 Schema、必填字段和 handler。MCP 输出 inputSchema、outputSchema 与标准 annotations。

服务变更还受允许列表、保护列表、标识符校验和 Linux root 保护约束。handler 记录变更前后的 `systemctl is-active` 状态。

受管文件只能写入 `data/managed/`。内容按 UTF-8 字节限制，写前产生唯一快照；目标、快照和索引采用原子替换，rollback 恢复原始字节或删除新建文件。

## 6. 并发与持久化

PendingActionStore 和受管文件事务均使用：

- 进程内锁；
- O_EXCL 锁文件实现的跨进程互斥；
- 超时与陈旧锁处理；
- 唯一临时文件；
- 同卷原子 replace。

待确认记录在写盘前加密并附 HMAC。错误会话尝试不会销毁合法会话的令牌；合法消费后立即删除，不能重放。

## 7. 审计设计

审计事件包含来源、会话、工具、脱敏参数、风险、裁决、结果、耗时和结构化决策轨迹。`reasoning_chain` 是历史兼容字段名，内容是可复核事实，不包含模型隐藏思维过程。

完整性机制：

1. 每条新事件包含 `prev_hash` 和 `entry_hash`；
2. `entry_hmac` 使用部署密钥签名；
3. 每个日志段有带 HMAC 的事件数量与末尾哈希锚点；
4. 写入 flush、fsync 后更新锚点；
5. 轮转时日志与锚点一起移动；
6. 校验覆盖所有轮转段；
7. 旧无哈希记录和旧 SHA 链只允许位于签名链头部，并按原格式严格校验；
8. 首条删除、中间删除、内容修改、HMAC 删除和尾部截断都能被检测。

敏感键、Bearer Token、API Key 模式、确认令牌与受管文件内容在落盘前递归脱敏。

## 8. Web 设计

Web 基于 ThreadingHTTPServer：

- 默认必须设置 `SAFEOPS_TOKEN`；仅显式开发模式可在本机回环地址免认证；
- 非回环监听必须同时启用原生 TLS、认证并设置 `SAFEOPS_TOKEN`；
- 原生 TLS 最低使用 TLS 1.2，并发送 HSTS 响应头；
- `POST /api/auth` 建立 HttpOnly、SameSite=Strict 会话 Cookie；
- API 支持 Bearer Token，SSE 只使用 Cookie/Bearer，不接收 URL 查询令牌；
- 单 IP 限流、64 KiB 请求体上限和对象型 JSON 校验；
- CSP、X-Frame-Options、nosniff 与 Referrer-Policy 响应头；
- 每个浏览器会话独立 Agent、上下文和锁。

Web 响应使用 `decision_trace` 作为界面字段，并保留 `reasoning_chain` 兼容字段。

诊断模块先采集 CPU 负载、内存/磁盘比例、监听端口、服务状态和错误日志，再按明确阈值或日志特征生成原因与动作；未命中证据时返回健康或信息不足状态，不输出固定故障模板。诊断证据同时记录所用阈值、命中端口或已计算挂载点，便于评审复核。

主要 Web 接口：

| 接口 | 方法 | 作用 |
| --- | --- | --- |
| `/api/health` | GET | 健康检查 |
| `/api/auth` | POST | 校验令牌并建立 HttpOnly 会话 |
| `/api/tools` | GET | 返回工具 Schema、风险和分类 |
| `/api/agent` | POST | 提交自然语言请求或确认 action_id |
| `/api/audit` | GET | 按条件查询脱敏审计 |
| `/api/events` | GET | 建立经过认证的 SSE 通道 |

## 9. MCP 设计

stdio 服务使用换行分隔 JSON-RPC 2.0，当前协议 `2025-11-25`，兼容三个较早版本。生命周期为：

1. `initialize`；
2. `notifications/initialized`；
3. `tools/list`、`tools/call` 和 `ping`。

生命周期未完成、参数不是对象、缺少必填字段、类型或范围错误、包含额外字段时返回明确协议或工具错误。所有 MCP 调用和确认都进入统一签名审计。

## 10. 配置与安装

配置采用 PyYAML `safe_load`，支持标准嵌套 YAML。启动时按单文件优先级读取工作目录 `config/`，否则使用 wheel 内 `safeops_agent/resources/config/`。Web 资源同理。运行数据根目录是源码仓库、`SAFEOPS_PROJECT_ROOT` 或启动工作目录，不写入 site-packages。

发布脚本排除 `data/`、`config/llm.local.yaml`、`.env`、缓存和版本库元数据。校验脚本同时检查关键交付文件和禁止项。

配置优先级：

1. API Key 等私密值优先读取环境变量；
2. 工作目录 `config/llm.local.yaml` 覆盖公共模型配置；
3. 工作目录公共 YAML 覆盖 wheel 内置默认配置；
4. 找不到外部 Web 资源时使用 wheel package-data。

## 11. 已知边界

- 当前没有任意 Shell、插件动态执行或模型直执行通道；扩展能力必须先注册固定工具；
- 服务生命周期真实执行依赖麒麟/Linux 上的 `systemctl` 及最小权限配置；
- 当前完成 Windows 软件级回归和真实 DeepSeek 冒烟，尚未形成麒麟硬件实机报告；
- Web 原生服务适合比赛演示和受控部署；大规模生产部署应由成熟 HTTPS 反向代理承担公网入口；
- 诊断依据当前采集点和明确规则生成，不宣称替代完整 APM、SIEM 或专家复盘。

## 12. 验证

自动化测试覆盖 Agent、策略、工具、确认、加密、并发、审计篡改、MCP 生命周期与 Schema、Web 认证、配置、安装资源和前端逻辑。当前 217 项 Python 测试与 7 项 Node 测试全部通过；Python 分支覆盖综合值为 72.3%，CI 门槛为 70.0%，且以 ResourceWarning 作为错误运行。

另有配置校验、Web 冒烟、CLI 验收、MCP 真实握手、审计验签、wheel 隔离安装和 95 条目发布包验证。真实 `deepseek-chat` 请求成功选择 `system.info` 并完成 LOW 工具执行。软件级验收不包含硬件或麒麟实机执行。
