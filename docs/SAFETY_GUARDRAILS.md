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

- `service.restart`

CLI 确认方式：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --yes
```

MVP 阶段即使确认，`service.restart` 仍不执行真实重启，只完成审批闭环。后续接入最小权限执行时再打开真实操作。

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

- 用户请求
- 匹配工具
- 工具参数
- 风险等级
- 是否允许
- 拒绝或允许原因
- 稳定错误码
- 执行耗时
- 执行结果摘要

审计不记录模型隐藏思维链，只记录可复盘的决策摘要，避免泄露内部推理和敏感上下文。

## 10. 安全测试清单

必须覆盖：

- 删除根目录被拒绝。
- 覆盖 `/etc/passwd` 被拒绝。
- 服务名注入 `nginx;rm -rf /` 被拒绝。
- 未确认重启服务被拒绝并提示确认。
- 低风险查询可以正常执行。
- 审计日志记录风险、原因和错误码。

## 11. 残余风险

- 关键词过滤不能覆盖所有自然语言表达，后续需结合分类模型或更完整规则库。
- 当前 Web/CLI 均为本地演示形态，生产环境需要认证、授权和 CSRF 防护。
- 最小权限执行尚未在真实麒麟环境完成验证。
- MCP 标准 Server 尚未接入官方 SDK。
