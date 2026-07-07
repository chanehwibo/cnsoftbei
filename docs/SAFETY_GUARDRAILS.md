# 安全护栏设计文档

## 1. 设计目标

智能运维 Agent 的核心风险来自模型输出不可控、系统命令破坏性强、操作结果难以回滚。本项目采用多层安全护栏，确保 Agent 只能在受控范围内感知系统和执行任务。

目标：

- 阻止高风险自然语言意图进入执行链路。
- 阻止模型或用户构造任意 shell 命令。
- 对中风险操作要求显式确认。
- 对所有请求和决策过程进行审计。
- 为后续最小权限执行和人工审批扩展保留接口。

## 2. 护栏分层

```text
自然语言请求
  |
意图风险过滤
  |
工具白名单匹配
  |
参数校验
  |
工具风险分级
  |
确认/拒绝/执行
  |
审计日志
```

## 3. 意图风险过滤

实现位置：`src/safeops_agent/security/policy.py`

高风险关键词包括：

- 磁盘破坏：`mkfs`、`dd if=`、`格式化`、`清空磁盘`
- 系统破坏：`关机`、`重启系统`、`重装系统`
- 文件破坏：`rm -rf`、`递归删除`、`删除系统文件`
- 权限破坏：`chmod -R`、`chmod 777`、`chown -R`
- 安全绕过：`关闭防火墙`、`禁用审计`、`提权`
- 账户风险：`修改 root`、`删除用户`、`新增管理员`

命中后返回：

- `allowed=false`
- `risk=HIGH`
- `error_code=INTENT_HIGH_RISK_KEYWORD`

## 4. 敏感路径保护

敏感路径包括：

- `/`
- `/etc`
- `/boot`
- `/usr`
- `/bin`
- `/sbin`
- `/var/lib`
- `/root`
- `C:\Windows`

当请求同时包含破坏性动作和敏感路径时，系统直接拒绝。

示例：

```text
覆盖 /etc/passwd -> INTENT_SENSITIVE_PATH
删除 /boot 目录 -> INTENT_HIGH_RISK_KEYWORD 或 INTENT_SENSITIVE_PATH
```

## 5. 工具白名单

Agent 不提供任意命令执行工具，只能调用 `ToolRegistry` 中注册的固定工具。

工具注册内容包括：

- 工具名
- 描述
- 风险等级
- 参数 Schema
- 必填参数
- 分类
- 固定 handler

优势：

- 模型不能自由拼接 shell 命令。
- 工具行为可测试、可审计、可复盘。
- 权限控制可以按工具粒度落地。

## 6. 参数校验

参数层拦截以下风险字符：

```text
; & | ` $ < >
```

服务名允许字符：

```text
a-z A-Z 0-9 @ _ . -
```

软件包名允许字符：

```text
a-z A-Z 0-9 + _ . : -
```

参数不合法时，不进入工具 handler。

稳定错误码：

- `ARG_COMMAND_INJECTION`
- `ARG_SERVICE_REQUIRED`
- `ARG_SERVICE_INVALID`
- `ARG_PACKAGE_INVALID`
- `ARG_SENSITIVE_PATH`

## 7. 风险分级与审批

风险等级：

- `LOW`：只读查询，自动执行。
- `MEDIUM`：可能改变服务状态，需要确认。
- `HIGH`：可能造成数据破坏、越权或系统不可用，默认拒绝。

当前中风险工具：

- `service.restart` / `service.start` / `service.stop`
- `file.apply` / `file.rollback`（限受管工作区，写前快照、可真实回滚）

确认方式（推荐：一次性确认令牌）：

```powershell
# 第一步：预演。返回 dry-run 计划和确认令牌 pending_action_id
python -m safeops_agent.cli "重启 nginx 服务"
# 第二步：凭令牌精确执行当初裁决过的动作（不重跑意图理解）
python -m safeops_agent.cli --confirm <pending_action_id>
```

兼容方式：`--yes` 重跑意图理解后放行（存在 LLM 非确定性导致预演与执行不一致的理论窗口，故推荐令牌方式）。

确认令牌的安全属性：

- 一次性：使用即作废，不可重放；
- 限时：默认 10 分钟过期；
- 会话绑定：跨会话（CLI/不同浏览器会话）出示令牌直接拒绝；
- 确认后策略复核：执行前重新过一遍参数校验与风险裁决，策略保留最终否决权。

确认放行后，服务生命周期操作在麒麟/Linux 环境真实执行 `systemctl <action> <service>`（Windows 开发环境返回预告文本），执行结果附带逆操作建议（rollback 字段）。

## 7.1 LLM 输出侧护栏

LLM 的 `clarification`（追问文本）与 `reasoning`（推理说明）会展示给运维人员并写入审计。为防提示注入借模型之口输出诱导性指令（如"请手动执行 rm -rf …"），模型输出与用户输入过同一套高风险意图筛查，命中即整体屏蔽，并统一截断超长文本。LLM 调用失败会在思维链中留下回退原因，而不是静默降级。

## 7.2 会话隔离

Web 端按 `X-Session-Id` 为每个浏览器会话维护独立 Agent 实例：对话历史、指代上下文（"重启它"）互不串扰，确认令牌与会话绑定；各会话独立加锁，一个会话的慢 LLM 调用不阻塞其他会话。

## 8. 最小权限执行设计

当前实现：

- 只读工具默认使用当前进程权限。
- 不开放任意 shell。
- 中风险工具暂不执行真实变更。

后续落地：

- Agent 主进程使用普通用户运行。
- 特权操作交给独立 executor。
- executor 使用 sudo 白名单，仅允许固定命令模板。
- 每个中风险/高风险操作绑定审批记录。

示例 sudo 白名单目标：

```text
safeops ALL=(root) NOPASSWD: /bin/systemctl restart nginx.service
```

## 9. 审计追踪

审计日志位置：`data/audit.log`

每条审计事件记录：

- 用户请求、会话标识
- 匹配工具与参数
- 风险等级、风险评分、是否允许、原因、稳定错误码
- 意图来源（llm/rule）与可回放的五步思维链（指代解析 → 意图筛查 → 工具选择 → 风险裁决 → 执行）
- 确认令牌 ID（涉及确认流程时）
- 执行耗时与结果摘要

审计记录的是结构化、可复盘的决策链，而非模型的隐藏原始推理，避免泄露内部提示词和敏感上下文。

### 9.1 哈希链防篡改

每条事件包含 `prev_hash`（上一条事件的哈希）与 `entry_hash`（本条事件含 prev_hash 的 SHA-256）。修改任何历史事件的内容、删除或重排中间事件都会破坏链条。

校验方式：

```powershell
python -m safeops_agent.cli --verify-audit
```

Web 端：`GET /api/audit/verify`。日志轮转后新文件从创世哈希重新起链；哈希链启用前的存量事件计为 legacy，仅允许出现在文件头部。

## 10. 安全测试清单

必须覆盖：

- 删除根目录被拒绝。
- 覆盖 `/etc/passwd` 被拒绝。
- 服务名注入 `nginx;rm -rf /` 被拒绝。
- 未确认重启服务被拒绝并返回 dry-run 计划与确认令牌。
- 确认令牌一次性、过期、跨会话使用均被拒绝。
- 模型输出中的高风险指令被输出护栏屏蔽。
- 审计日志哈希链能检出内容篡改与事件删除。
- 低风险查询可以正常执行。
- 审计日志记录风险、原因和错误码。

对应测试：`tests/test_policy.py`、`tests/test_pending_confirm.py`、`tests/test_audit_chain.py` 等。

## 11. 残余风险

- 关键词过滤不能覆盖所有自然语言表达；LLM 意图理解已上线，但输出仍需经过策略裁决，双层过滤的规则库仍需持续扩充。
- 当前 Web/CLI 为本地演示形态（默认仅监听 127.0.0.1，可选 Bearer Token），生产环境需要完整认证、授权和 CSRF 防护。
- 服务生命周期操作已支持真实执行，但最小权限执行器（专用低权用户 + sudo 白名单）尚未在真实麒麟环境完成部署验证。
- 审计哈希链为单文件链，跨轮转文件的连续性校验和异地存证属于后续增强。
