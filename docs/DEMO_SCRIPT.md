# 答辩演示脚本

## 1. 准备

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
python -m pip install -e .
$env:SAFEOPS_LLM_DISABLED='1'
python -m safeops_agent.config_check
~~~

说明：演示先用离线模式保证确定性。软件功能不依赖模型网络。

## 2. 八分钟流程

### 0:00–1:00 架构

讲解：

- 自然语言只产生候选工具；
- 固定工具注册表没有任意 Shell；
- PolicyEngine 本地裁决；
- LOW、MEDIUM、HIGH 三条路径；
- 所有入口进入同一签名审计。

### 1:00–2:00 只读查询

~~~powershell
safeops-agent "查看系统信息" --json
safeops-agent "查看CPU和内存" --json
~~~

展示 `tool`、`risk=LOW`、结果和 `decision_summary`。

### 2:00–3:00 诊断

~~~powershell
safeops-agent "诊断CPU和内存" --json
safeops-agent "排查端口占用" --json
~~~

展示诊断不是硬编码成功：底层采集失败会传播 `ok=false`。

### 3:00–4:15 中风险预演

~~~powershell
safeops-agent "重启 nginx 服务" --json
~~~

展示：

- `risk=MEDIUM`；
- `requires_confirmation=true`；
- dry-run 前置检查、步骤与回滚建议；
- `pending_action_id`；
- 此时没有执行服务变更。

演示环境不执行确认第二步；讲解正式 Linux 部署中需要复制令牌并运行 `safeops-agent --confirm ACTION_ID`。

### 4:15–5:00 高风险拒绝

~~~powershell
safeops-agent "覆盖 /etc/passwd" --json
~~~

展示 `risk=HIGH`、明确错误码和执行阶段缺失。

### 5:00–6:00 决策轨迹与审计

在 JSON 或 Web 中展开决策轨迹。说明：

- 它记录上下文解析、筛查、工具选择、裁决和结果；
- `reasoning_chain` 是兼容字段名；
- 内容是结构化事实，不是模型隐藏思维过程。

~~~powershell
safeops-agent --verify-audit
safeops-agent --show-audit --audit-limit 3
~~~

讲解 SHA 链、HMAC、锚点、轮转和脱敏。

### 6:00–7:00 Web

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

打开 `http://127.0.0.1:8765`，演示查询、决策轨迹和审计筛选。说明远程监听必须设置 token，浏览器使用 HttpOnly 会话 Cookie。

### 7:00–7:40 MCP

~~~powershell
safeops-agent --list-tools
~~~

展示 25 个工具的 inputSchema、outputSchema 与 annotations。说明客户端必须完成 `initialize/initialized`，中风险调用使用 `safeops.confirm`。

### 7:40–8:00 验收

~~~powershell
python -W error::ResourceWarning -m unittest discover -s tests
~~~

展示 196 项测试通过。说明另有 Web 冒烟、wheel 隔离安装和提交包禁止项校验。

## 3. 一键演示

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
~~~

## 4. 关键答复

| 问题 | 答复 |
| --- | --- |
| 模型能直接执行命令吗 | 不能。它只返回候选工具和参数，本地注册表与策略决定后续。 |
| 中风险怎么确认 | 首次保存已裁决 tool/args 并签发一次性令牌；确认阶段不重新理解文本。 |
| 如何防止停防火墙或审计 | 保护服务始终拒绝，非白名单服务也拒绝。 |
| 审计删除最后一行能发现吗 | 能。持久化锚点同时记录事件数和末尾哈希。 |
| 安装后 Web 为什么还能打开 | 默认配置和静态资源作为 wheel package-data 内置。 |
| 没有网络能运行吗 | 能。设置离线变量后规则路由覆盖核心查询、诊断和受控操作。 |

本演示执行软件级功能，不进行硬件或麒麟实机操作。
