# SafeOps Agent 新手傻瓜式操作手册与演示步骤

本文档面向第一次接触本项目的同学和演示录屏操作者。照着本文档逐步执行，可以完成 SafeOps Agent 的全流程功能演示：自然语言运维、三级风险策略、一次性确认令牌、五步思维链、哈希链审计、大模型意图理解、标准 MCP 协议、Web 工作台和回归测试。

文档目标不是解释所有源码细节，而是让操作者知道：

- 每一步输入什么命令。
- 命令跑对时屏幕上应该出现什么现象。
- 关键成功标志是什么。
- 录屏时旁边可以配什么红色说明文字，证明项目功能成功。

> 项目：面向麒麟操作系统的安全智能运维 Agent（SafeOps Agent）
> 队伍：G老师饲养大队（天津师范大学）

## 0. 演示总览

建议使用 PowerShell 作为演示终端。所有命令默认在项目根目录执行：

```text
C:\Users\CanhuiBao\Desktop\中国软件杯
```

本项目有两种运行模式，录屏前先想清楚用哪种：

| 模式 | 开启方式 | 特点 | 适用 |
| --- | --- | --- | --- |
| 离线规则模式 | `$env:SAFEOPS_LLM_DISABLED='1'` | 不联网、零费用、结果确定 | 测试验收、保底演示 |
| 在线大模型模式 | 配置 `config\llm.local.yaml` 且不设离线开关 | DeepSeek 理解意图，语义更强，失败自动回退规则 | 展示大模型亮点 |

完整演示会覆盖 11 类能力：

| 顺序 | 功能 | 展示目的 |
| --- | --- | --- |
| 1 | 环境检查 | 确认 Python、项目路径和模式正常 |
| 2 | 自动化测试 | 证明 130+ 个 unittest 全部通过 |
| 3 | 低风险查询 | 自然语言 → 只读工具直接执行 |
| 4 | 故障诊断 | 指标组织成现象/原因/建议的诊断报告 |
| 5 | 中风险确认令牌 | 预演计划 + 一次性令牌 + 精确执行闭环 |
| 6 | 令牌一次性/防伪造 | 令牌用后失效、伪造/过期被拒 |
| 7 | 高风险拦截 | 敏感路径、破坏性关键词、命令注入被拒 |
| 8 | 五步思维链 | 每次请求可回放的决策链 |
| 9 | 哈希链审计校验 | 审计日志防篡改、可一键校验 |
| 10 | 大模型意图理解 | 在线模式下 LLM 选工具，失败回退规则 |
| 11 | MCP 协议 / Web 工作台 | 标准协议服务端与可视化双入口 |

## 1. 演示前准备

### 1.1 打开 PowerShell

操作：

1. 按 `Win` 键。
2. 输入 `PowerShell`。
3. 打开 Windows PowerShell。

如果录屏，请先把 PowerShell 窗口放大，字体调大到观众能看清。

建议旁边红字说明：

```text
所有功能都通过本地 CLI 命令演示，安全护栏在本地策略引擎中生效。
```

### 1.2 进入项目目录

命令：

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
```

检查当前位置：

```powershell
Get-Location
```

正确现象：

```text
Path
----
C:\Users\CanhuiBao\Desktop\中国软件杯
```

如果路径不对，后续 `python -m safeops_agent.cli` 命令可能找不到项目代码。

### 1.3 设置终端编码和 Python 模块路径

命令：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='src'
```

正确现象：

- 命令执行后通常没有输出。
- 没有红色报错就是成功。

说明：

- `$env:PYTHONPATH='src'` 是必须的，它让 Python 能找到 `src\safeops_agent` 包。
- 每次新开 PowerShell 窗口，都要重新执行这一组命令。
- 用 `scripts\*.ps1` 脚本运行时，脚本内部会自动设置，无需手动执行；只有直接敲 `python -m safeops_agent.cli` 时才需要。

如果忘记设置，可能出现：

```text
ModuleNotFoundError: No module named 'safeops_agent'
```

建议旁边红字说明：

```text
PYTHONPATH 指向 src 后，CLI 可以加载本项目的智能运维 Agent 模块。
```

### 1.4 检查 Python

命令：

```powershell
python --version
```

正确现象：

```text
Python 3.14.3
```

版本号不必完全一致，但建议 Python 为 3.10 或更高。

### 1.5 选择运行模式

**方式一：离线规则模式（推荐用于测试和稳定演示）**

命令：

```powershell
$env:SAFEOPS_LLM_DISABLED='1'
```

正确现象：无输出、无报错。此后所有请求都走本地规则匹配，不联网、不消耗 API、结果确定。

**方式二：在线大模型模式（展示大模型亮点）**

命令：

```powershell
copy config\llm.local.yaml.example config\llm.local.yaml
notepad config\llm.local.yaml
```

在打开的文件里把 `llm_api_key` 填成你的 DeepSeek API Key 并保存。确保当前 PowerShell **没有**设置 `SAFEOPS_LLM_DISABLED`（该开关优先级最高）。

重要安全要求：

- 不要在录屏里打开 `config\llm.local.yaml` 展示明文 Key。
- `config\llm.local.yaml` 已被 `.gitignore` 忽略，不会提交仓库。

建议旁边红字说明：

```text
离线模式保证演示稳定不翻车；在线模式展示大模型意图理解，失败会自动回退规则。
```

## 2. 功能一：完整自动化测试

测试是证明项目稳定性的第一步，建议录屏开头或结尾展示。

### 2.1 运行 unittest

命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

当前正确输出尾部：

```text
----------------------------------------------------------------------
Ran 130+ tests in 2.xxxs

OK
```

关键成功标志：

- `Ran 130+ tests`
- `OK`

说明：

- 测试脚本内部会自动设置 `PYTHONPATH`，并走离线模式，不消耗 API。
- 中间可能打印少量工具执行摘要或 fallback 字样，是测试用例在验证 CLI 与回退行为，不是失败。

建议红框框选：

- `Ran 130+ tests`
- `OK`

建议旁边红字说明：

```text
130+ 个 unittest 覆盖 Agent、安全策略、确认令牌、哈希链审计、MCP 契约和护栏拦截，全部离线确定性通过。
```

## 3. 功能二：低风险自然语言查询

### 3.1 查看系统信息

命令：

```powershell
python -m safeops_agent.cli "查看系统信息" --json
```

当前正确输出示例（节选）：

```json
{
  "ok": true,
  "message": "系统信息采集完成：Windows / AMD64",
  "tool": "system.info",
  "risk": "LOW",
  "risk_score": 10,
  "decision_summary": "匹配工具 `system.info`，风险等级 LOW，风险评分 10/100，决策：允许执行，原因：只读低风险工具。"
}
```

关键成功标志：

- `"ok": true`
- `"tool": "system.info"`
- `"risk": "LOW"`

建议红框框选：`"tool": "system.info"`、`"risk": "LOW"`。

建议旁边红字说明：

```text
用户用自然语言请求系统信息，Agent 匹配到只读工具 system.info，风险 LOW，直接执行。
```

### 3.2 查看 CPU 和内存

命令：

```powershell
python -m safeops_agent.cli "查看CPU和内存" --json
```

关键成功标志：

- `"tool": "system.resources"`
- `data` 中包含 `cpu`、`memory`、`disk` 三块指标。

建议旁边红字说明：

```text
Agent 把自然语言映射到资源指标工具，采集 CPU、内存和磁盘信息。
```

### 3.3 查看进程 / 端口 / 磁盘 / 网络

命令（逐条执行）：

```powershell
python -m safeops_agent.cli "查看进程" --json
python -m safeops_agent.cli "查看监听端口" --json
python -m safeops_agent.cli "查看磁盘分区" --json
python -m safeops_agent.cli "查看网络连接" --json
```

正确现象：`tool` 字段依次为 `process.list`、`network.listening_ports`、`disk.partitions`、`network.connections`，`risk` 均为 `LOW`，`data.lines` 中是真实系统数据。

建议旁边红字说明：

```text
网络排障、进程排查、磁盘检查都不是让模型自由拼命令，而是调用固定的最小权限工具。
```

### 3.4 查看日志 / 服务状态 / 软件包

命令：

```powershell
python -m safeops_agent.cli "分析最近系统错误日志" --json
python -m safeops_agent.cli "查看 nginx 服务状态"
python -m safeops_agent.cli "查询 nginx 软件包" --json
```

Windows 下服务状态正确现象：

```text
当前为 Windows 开发环境，服务状态工具将在麒麟/Linux 环境使用 systemctl
```

建议旁边红字说明：

```text
服务状态查询是只读操作。当前在 Windows 上演示接口链路，到麒麟系统会用 systemctl 查询真实状态。
```

## 4. 功能三：故障诊断

### 4.1 诊断 CPU 和内存

命令：

```powershell
python -m safeops_agent.cli "诊断CPU和内存" --json
```

当前正确输出示例（节选）：

```json
{
  "ok": true,
  "tool": "diagnostics.resources",
  "data": {
    "diagnosis": {
      "scenario": "CPU/内存/磁盘资源诊断",
      "symptom": "已采集 CPU、内存和磁盘基础指标。",
      "possible_causes": [
        "业务进程 CPU 占用过高。",
        "内存缓存、日志或临时文件增长导致可用资源下降。",
        "磁盘使用率持续升高导致服务写入失败。"
      ],
      "recommended_actions": [
        "查看进程列表并按 CPU/内存占用排序。",
        "检查最近错误日志中是否存在 OOM、磁盘写满或服务异常。",
        "如需清理或重启服务，先进入中风险确认流程。"
      ],
      "risk": "LOW"
    }
  }
}
```

关键成功标志：`tool` 为 `diagnostics.resources`，`data.diagnosis` 含 `symptom`、`possible_causes`、`recommended_actions`。

### 4.2 排查端口占用 / 系统概览

命令：

```powershell
python -m safeops_agent.cli "排查端口占用问题" --json
python -m safeops_agent.cli "系统概览诊断" --json
```

正确现象：`tool` 依次为 `diagnostics.network_ports`、`diagnostics.overview`，返回结构化诊断报告。

建议红框框选：`possible_causes`、`recommended_actions`。

建议旁边红字说明：

```text
Agent 不只是返回原始指标，而是把指标组织成诊断报告：现象、可能原因、建议动作和风险等级。
```

## 5. 功能四：中风险操作与一次性确认令牌（重点）

这是最能体现"安全护栏"的演示，务必连贯录制。

### 5.1 发起中风险请求，系统不执行、只返回令牌

命令：

```powershell
python -m safeops_agent.cli "重启 nginx 服务"
```

当前正确输出示例：

```text
未执行 service.restart：中风险工具需要用户确认
如确认执行：--confirm c911f073ef6940e181cb2a1d791dcbc8（10 分钟内有效），或追加 --yes。
```

关键成功标志：出现 `未执行 service.restart` 和一串 `--confirm` 令牌。

### 5.2 查看 dry-run 预演计划

命令：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
```

`data.dry_run_plan` 当前正确输出示例（节选）：

```json
{
  "action": "service.restart",
  "target": { "service": "nginx" },
  "pre_checks": [
    "查看 nginx 服务状态",
    "查看监听端口，确认服务端口是否正常占用",
    "分析最近系统错误日志，确认是否存在启动失败或依赖异常"
  ],
  "planned_steps": [
    "记录当前服务状态和关键错误日志",
    "在用户显式确认后对 nginx 执行重启流程",
    "重启后再次检查服务状态、端口监听和错误日志"
  ],
  "rollback_suggestion": "如果重启后服务不可用，可通过逆操作回退，并查看状态与日志定位原因。",
  "risk_controls": [
    "未确认前不执行真实变更",
    "仅允许合法服务名参数",
    "所有决策和结果写入审计日志"
  ]
}
```

顶层字段还应看到：`"risk": "MEDIUM"`、`"risk_score": 65`、`"requires_confirmation": true`、`"pending_action_id": "..."`。

建议旁边红字说明：

```text
系统未确认时不重启服务，而是先给出预检查、拟操作、回滚建议和风险控制。
```

### 5.3 凭令牌精确执行

复制 5.1 输出里那串真实令牌，替换下面命令中的令牌：

```powershell
python -m safeops_agent.cli --confirm c911f073ef6940e181cb2a1d791dcbc8
```

Windows 下当前正确输出示例：

```text
当前为 Windows 开发环境，将在麒麟/Linux 环境使用 systemctl restart nginx
```

关键成功标志：确认后进入执行路径（Windows 为兼容文本，麒麟/Linux 会真实执行 `systemctl restart nginx`）。

建议红框框选：`--confirm`、令牌串、`systemctl restart nginx`。

建议旁边红字说明：

```text
一次性令牌确认执行的正是当初预演过的动作，不会"预演 A、执行 B"；令牌限时、绑定会话。
```

## 6. 功能五：令牌一次性与防伪造

### 6.1 伪造令牌被拒绝

命令：

```powershell
python -m safeops_agent.cli --confirm 00000000000000000000000000000000
```

当前正确输出示例：

```text
确认失败：确认令牌不存在、已被使用或已过期
```

### 6.2 令牌用一次即失效

把 5.3 中刚用过一次的真实令牌再执行一次，会得到与 6.1 相同的拒绝信息。

建议旁边红字说明：

```text
令牌一次性、限时 10 分钟、绑定会话，防止重放和跨会话冒用。
```

## 7. 功能六：高风险拦截

### 7.1 敏感路径拦截

命令：

```powershell
python -m safeops_agent.cli "覆盖 /etc/passwd"
```

当前正确输出示例：

```text
已拒绝执行：高风险操作涉及敏感路径：/
```

### 7.2 破坏性关键词拦截

命令：

```powershell
python -m safeops_agent.cli "删除根目录所有文件"
```

当前正确输出示例：

```text
已拒绝执行：命中高风险意图关键词：删除根目录
```

### 7.3 命令注入拦截

命令：

```powershell
python -m safeops_agent.cli "查询 nginx; rm -rf / 软件包"
```

当前正确输出示例：

```text
已拒绝执行：命中高风险意图关键词：rm -rf
```

正确现象：以上三条命令退出码均非零，这是**预期行为**，说明安全护栏生效。

建议红框框选：`已拒绝执行`。

建议旁边红字说明：

```text
高风险破坏性意图在最外层护栏就被拒绝，根本不进入工具调用，杜绝误操作。
```

## 8. 功能七：五步思维链

任意一次 `--json` 请求的 `reasoning_chain` 字段就是可回放的五步决策链。

命令：

```powershell
python -m safeops_agent.cli "查看系统信息" --json
```

`reasoning_chain` 当前正确输出示例（节选）：

```json
[
  { "step": 1, "stage": "context_resolution", "title": "上下文指代解析" },
  { "step": 2, "stage": "intent_screening",   "title": "意图风险筛查" },
  { "step": 3, "stage": "tool_selection",      "title": "工具选择",
    "outputs": { "tool": "system.info", "source": "rule" } },
  { "step": 4, "stage": "risk_adjudication",   "title": "风险裁决",
    "outputs": { "allowed": true, "risk": "LOW", "risk_score": 10 } },
  { "step": 5, "stage": "execution",           "title": "执行阶段",
    "outputs": { "executed": true, "ok": true } }
]
```

关键成功标志：五个 `step` 依次为上下文解析 → 意图筛查 → 工具选择 → 风险裁决 → 执行。

建议旁边红字说明：

```text
每次请求都记录五步可回放思维链，决策过程完全可解释、可复盘。
```

## 9. 功能八：哈希链审计与防篡改校验

### 9.1 查看最近审计日志

命令：

```powershell
Get-Content .\data\audit.log -Encoding utf8 -Tail 5
```

正确现象：每行是一条 JSON 事件，包含 `request`、`tool`、`risk`、`risk_score`、`intent_source`、`reasoning_chain`、`prev_hash`、`entry_hash` 等字段。

### 9.2 校验哈希链完整性

命令：

```powershell
python -m safeops_agent.cli --verify-audit
```

当前正确输出示例：

```json
{
  "ok": true,
  "checked": 39,
  "legacy": 57,
  "first_bad_line": null,
  "reason": null
}
```

关键成功标志：`"ok": true`、`"first_bad_line": null`。

说明：

- `checked` 是已校验的哈希链事件数。
- `legacy` 是启用哈希链之前的历史无哈希事件数（仅允许出现在文件头部）。
- 任何对历史事件的篡改、删除或重排都会使 `ok` 变为 `false` 并给出首个异常行号。

建议红框框选：`"ok": true`。

建议旁边红字说明：

```text
审计日志是哈希链结构，改一条即可被检出，做到"可自证完整"。
```

## 10. 功能九：大模型意图理解（在线模式）

本节需要按 1.5 方式二配置好 API Key，且当前 PowerShell 未设置 `SAFEOPS_LLM_DISABLED`。会消耗少量 API 额度。

### 10.1 用更口语化的说法触发大模型

命令：

```powershell
python -m safeops_agent.cli "帮我看看这台机器的内存和CPU占用" --json
```

正确现象：`tool` 为 `system.resources`，且 `reasoning_chain` 的工具选择步骤中：

```json
{ "source": "llm", "llm_reasoning": "用户请求查看内存和CPU占用，匹配system.resources工具。" }
```

关键成功标志：`source` 为 `llm`（走了大模型），且有 `llm_reasoning` 推理文本。

### 10.2 验证失败自动回退

临时改一个错误的 base_url 或断网后再执行同一命令，`source` 会变回 `rule`，`fallback_note` 记录回退原因，功能不中断。

建议红框框选：`"source": "llm"`、`llm_reasoning`。

建议旁边红字说明：

```text
在线模式由 DeepSeek 理解口语化意图；API 失败或超时会自动回退规则匹配，演示不中断。
```

## 11. 功能十：MCP 工具清单与标准协议服务

### 11.1 查看工具清单

命令：

```powershell
python -m safeops_agent.cli --list-tools
```

或用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\show-tools.ps1
```

正确现象：输出 24 个工具，每个含 `name`、`description`、`category`、`risk`、`inputSchema`、`annotations`。第一个工具示例：

```json
{
  "name": "system.info",
  "description": "采集操作系统版本、内核、架构和主机信息",
  "category": "system",
  "risk": "LOW",
  "inputSchema": { "type": "object", "properties": {}, "required": [], "additionalProperties": false },
  "annotations": { "readOnlyHint": true, "destructiveHint": false, "requiresConfirmation": false }
}
```

关键成功标志：工具数为 24，每个工具带 `risk` 与 `annotations` 安全注解。

### 11.2 启动标准 MCP stdio 服务端

命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp-stdio.ps1
```

正确现象：进程启动并等待 stdin 输入。这是符合 Model Context Protocol 的标准 JSON-RPC 2.0 stdio 服务端，支持 `initialize`（版本协商）、`tools/list`、`tools/call`、`ping`。演示后按 `Ctrl + C` 退出。

建议旁边红字说明：

```text
大模型/客户端只能调用工具清单里的受控工具，不能执行任意 shell 命令。工具调用同样经过安全策略裁决。
```

## 12. 功能十一：Web 工作台

### 12.1 启动

命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

正确现象：

```text
SafeOps Web running at http://127.0.0.1:8765
```

保持该窗口不要关闭。

### 12.2 打开浏览器

地址栏输入：

```text
http://127.0.0.1:8765
```

### 12.3 页面布局与演示步骤

页面分三块：左侧常用任务按钮、中间自然语言输入与响应、右侧工具清单与审计日志。

按顺序操作：

1. 点击 `系统信息` → `执行`。
2. 点击 `资源指标` → `执行`。
3. 点击 `诊断资源`、`排查端口` → 查看诊断报告。
4. 点击 `重启服务` → 页面提示需要确认，并显示 Dry-run 预案。
5. 点击页面 `确认` 按钮完成中风险确认。
6. 点击 `高风险拦截` → 观察请求被拒绝及原因。
7. 点击 `刷新审计` → 查看最近请求、工具、风险、评分、决策摘要。

### 12.4 关闭

回到启动 Web 的 PowerShell 窗口按 `Ctrl + C`；或执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
```

### 12.5 Web API 一览（供评审追问）

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/health` | GET | 健康检查 |
| `/api/tools` | GET | 工具清单 |
| `/api/audit` | GET | 最近审计事件 |
| `/api/audit/verify` | GET | 校验审计哈希链 |
| `/api/audit/export` | GET | 导出审计日志 |
| `/api/agent` | POST | 提交请求（`request` 发起 / `action_id` 凭令牌确认） |

一键 Web 冒烟测试（自动启动→打接口→关闭）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
```

建议旁边红字说明：

```text
Web 工作台把 CLI 能力可视化，按会话隔离上下文；CLI、Web、MCP 三入口共享同一套安全策略与审计。
```

## 13. 一键全流程演示脚本

不想逐条输入，可直接跑：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

它会依次演示：系统信息 → CPU/内存 → 监听端口 → nginx 服务状态 → 重启 nginx（中风险）→ 覆盖 /etc/passwd（高风险）→ 查询 nginx 软件包，并输出最近审计日志。高风险命令返回非零状态属正常。

## 14. 录制 5 分钟功能演示视频建议脚本

这里的视频只演示作品功能，不包含 PPT 汇报和口头答辩。

### 14.1 时间分配

| 时间 | 画面 | 操作 | 旁边说明文字 |
| --- | --- | --- | --- |
| 0:00-0:20 | README 或赛题页面 | 展示项目名和定位 | `面向麒麟操作系统的安全智能运维 Agent` |
| 0:20-0:40 | PowerShell | 进入目录，设置编码与 `PYTHONPATH` | `本地 CLI 演示，安全护栏在策略引擎中生效` |
| 0:40-1:05 | PowerShell | 运行 `scripts\test.ps1` | `130+ 个 unittest 全部离线通过` |
| 1:05-1:35 | PowerShell | `查看系统信息` / `查看CPU和内存` | `自然语言映射到只读工具，风险 LOW 直接执行` |
| 1:35-2:05 | PowerShell | `诊断CPU和内存` | `指标组织成诊断报告：现象、原因、建议` |
| 2:05-3:00 | PowerShell | 中风险令牌闭环（拿令牌→confirm） | `一次性令牌：预演与执行一致，限时绑定会话` |
| 3:00-3:35 | PowerShell | 高风险三连（敏感路径/关键词/注入） | `破坏性意图在护栏第一层被拒绝` |
| 3:35-4:05 | PowerShell | 展开某次 `--json` 的思维链 + `--verify-audit` | `五步思维链可回放，审计哈希链防篡改` |
| 4:05-4:35 | PowerShell | 在线模式一次请求，展示 `source: llm` | `DeepSeek 理解口语意图，失败自动回退规则` |
| 4:35-5:00 | 浏览器 | Web 工作台重复低/中/高风险 + 看审计 | `CLI/Web/MCP 三入口共享同一套安全策略` |

### 14.2 推荐录屏命令顺序

录屏时建议按下面顺序复制执行。

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli "查看CPU和内存" --json
python -m safeops_agent.cli "诊断CPU和内存" --json
```

```powershell
python -m safeops_agent.cli "重启 nginx 服务"
# 复制上一条输出里的真实令牌，替换下面这串
python -m safeops_agent.cli --confirm 复制到的真实令牌
python -m safeops_agent.cli --confirm 00000000000000000000000000000000
```

```powershell
python -m safeops_agent.cli "覆盖 /etc/passwd"
python -m safeops_agent.cli "删除根目录所有文件"
python -m safeops_agent.cli "查询 nginx; rm -rf / 软件包"
```

```powershell
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli --verify-audit
```

如果要展示在线大模型（先按 1.5 配置好 Key，并临时取消离线开关）：

```powershell
Remove-Item Env:\SAFEOPS_LLM_DISABLED
python -m safeops_agent.cli "帮我看看这台机器的内存和CPU占用" --json
```

最后展示 Web：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
# 浏览器打开 http://127.0.0.1:8765
```

如果 5 分钟时间不够，在线大模型和 Web 部分可以只展示命令和结果，不展开解释。

## 15. 生成/查看文件展示清单

演示过程中可打开这些内容佐证功能完整：

| 展示内容 | 命令 | 应展示的内容 | 成功说明文字 |
| --- | --- | --- | --- |
| 审计日志 | `Get-Content .\data\audit.log -Encoding utf8 -Tail 5` | JSONL 事件、思维链、哈希字段 | `每次决策与调用都可追溯` |
| 审计校验 | `python -m safeops_agent.cli --verify-audit` | `"ok": true` | `审计日志未被篡改` |
| 工具清单 | `python -m safeops_agent.cli --list-tools` | 24 个工具与安全注解 | `工具白名单，无任意 shell` |
| 安全策略 | `notepad config\policy.yaml` | 破坏性关键词、敏感路径 | `安全规则可配置` |

## 16. 常见问题排查

### 16.1 报错：找不到 `safeops_agent`

现象：

```text
ModuleNotFoundError: No module named 'safeops_agent'
```

原因：没有设置 `PYTHONPATH`。修复：

```powershell
$env:PYTHONPATH='src'
```

然后重新执行刚才失败的命令（或改用 `scripts\*.ps1` 脚本，脚本会自动设置）。

### 16.2 中文输出乱码

修复命令：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
chcp 65001
```

CLI 也会自动把输出切到 UTF-8；如仍乱码，可用 VS Code 打开文件并选 UTF-8。

### 16.3 PowerShell 不允许运行脚本

用这种格式运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

### 16.4 确认令牌提示"不存在、已被使用或已过期"

三种原因：令牌已用过一次（一次性）、超过 10 分钟有效期、或跨会话使用。重新发起中风险请求获取新令牌即可。这也是安全设计的一部分，不是 Bug。

### 16.5 高风险命令返回失败是不是 Bug

不是。高风险被拒绝是预期行为，命令退出码非零属正常，说明安全护栏生效。

### 16.6 Web 页面打不开

先查健康检查：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health'
```

失败就重启：`powershell -ExecutionPolicy Bypass -File scripts\web.ps1`。端口 8765 被占用时先跑 `scripts\stop-web.ps1` 再启动。

### 16.7 大模型没生效 / 想强制离线

- 强制离线：`$env:SAFEOPS_LLM_DISABLED='1'`（优先级最高）。
- 想用在线：确认 `config\llm.local.yaml` 已填 Key，且**未**设置 `SAFEOPS_LLM_DISABLED`。
- 判断走没走大模型：看 `--json` 里 `reasoning_chain` 工具选择步骤的 `source`，`llm` 是大模型，`rule` 是规则回退。

### 16.8 Windows 上服务状态/重启为什么不是真实的

当前开发机是 Windows，服务类工具返回兼容说明文本；在麒麟/Linux 上会真实执行 `systemctl status/restart <服务>`。录屏到这里务必口头说明，避免评委误以为功能没做。

## 17. 安全和提交边界

以下内容是本地数据或密钥，不提交仓库：

| 路径 | 原因 |
| --- | --- |
| `config\llm.local.yaml` | 包含真实 DeepSeek API Key |
| `data\audit.log` | 运行时审计日志 |
| `data\managed\`、`data\snapshots\` | 受管文件工作区与快照 |
| `data\pending_actions.json` | 待执行确认令牌 |
| `__pycache__\` | Python 运行缓存 |

检查工作区：

```powershell
git status --short
```

正确现象：如果没有修改源码和文档，tracked 区域应为空；上述本地数据被 `.gitignore` 忽略，不会提交。

建议旁边红字说明：

```text
真实密钥、运行日志和令牌文件保持 ignored，不进入开源仓库。
```

## 18. 最终成功判定清单

正式录屏或验收前，按下面清单逐项确认。

| 检查项 | 成功标准 |
| --- | --- |
| 进入项目目录 | `Get-Location` 指向 `中国软件杯` |
| 模块路径 | 已执行 `$env:PYTHONPATH='src'` |
| 运行模式 | 已确定离线或在线，且开关设置正确 |
| 自动化测试 | `Ran 130+ tests` 且 `OK` |
| 低风险查询 | `system.info` / `system.resources` 返回 `"ok": true`、`"risk": "LOW"` |
| 故障诊断 | `diagnostics.resources` 返回含 possible_causes 的诊断报告 |
| 中风险令牌 | 发起返回 `pending_action_id`，`--confirm` 令牌可精确执行 |
| 令牌一次性 | 伪造/复用令牌返回"不存在、已被使用或已过期" |
| 高风险拦截 | 敏感路径、关键词、注入均返回 `已拒绝执行` |
| 五步思维链 | `reasoning_chain` 有 5 个 step |
| 审计校验 | `--verify-audit` 返回 `"ok": true` |
| 工具清单 | `--list-tools` 输出 24 个工具及安全注解 |
| 大模型（可选） | 在线模式 `source` 为 `llm`，失败回退 `rule` |
| Web 工作台 | `http://127.0.0.1:8765` 可打开并完成低/中/高风险演示 |
| 安全边界 | `config\llm.local.yaml` 不展示、不提交 |

全部满足后，可以说明：

```text
SafeOps Agent 已完成从自然语言查询、故障诊断、中风险确认令牌、高风险拦截、五步思维链、
哈希链审计、大模型意图理解到标准 MCP 协议和 Web 工作台的全流程功能演示。
```
