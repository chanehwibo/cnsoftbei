# SafeOps Agent 操作手册与演示步骤

本文档面向第一次接触本项目的同学、答辩演示人员和录屏操作者。照着本文档从上到下执行，可以完成 SafeOps Agent 的环境检查、离线运行、真实 DeepSeek、LOW 查询、数据诊断、MEDIUM 预演、HIGH 拦截、审计、Web、MCP、自动测试和发布包验证。

本文档不要求读者先理解源码。每个功能都明确说明：

- 在哪里操作。
- 复制哪条命令。
- 命令成功时屏幕上应该出现什么。
- 哪些数字会随电脑变化。
- 哪些异常是安全策略的正确现象。
- 如果失败，应先检查什么。
- 录屏或答辩时可以框选什么、旁边写什么说明。

除非章节特别说明，所有命令都在项目根目录执行：

~~~text
C:\Users\CanhuiBao\Desktop\中国软件杯
~~~

## 0. 演示总览

完整演示建议覆盖 11 类能力：

| 顺序 | 功能 | 展示目的 |
| --- | --- | --- |
| 1 | 环境与配置检查 | 证明 Python、依赖、路径和 YAML 配置正常 |
| 2 | 工具清单 | 证明系统只开放 25 个固定工具，没有任意 Shell |
| 3 | LOW 只读查询 | 展示自然语言到固定工具的安全执行链 |
| 4 | 数据驱动诊断 | 展示诊断依据真实指标、阈值、状态和日志 |
| 5 | MEDIUM 预演 | 展示 dry-run、一次性 action_id 和“未确认不执行” |
| 6 | HIGH 拒绝 | 展示危险意图在调用工具前就被阻断 |
| 7 | 签名审计 | 展示决策轨迹、SHA/HMAC、锚点和完整性校验 |
| 8 | Web 工作台 | 展示认证、对话、确认、决策轨迹和审计查询 |
| 9 | MCP 服务 | 展示标准生命周期、Schema 和 25 个工具 |
| 10 | 真实 DeepSeek | 展示大模型选择候选工具，本地策略最终裁决 |
| 11 | 测试与交付 | 展示 217+7 测试、72.3% 覆盖率、wheel 和提交包 |

最短演示路线：

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
python -m safeops_agent.config_check
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli "重启 nginx 服务" --json
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
python -m safeops_agent.cli --verify-audit
~~~

最短路线的正确结果依次是：

1. 配置检查 `0 个错误、0 个警告`。
2. 系统信息请求显示 `ok=true`、`tool=system.info`、`risk=LOW`。
3. 重启请求显示 `risk=MEDIUM`、`requires_confirmation=true`，并生成 action_id，但没有执行。
4. 覆盖敏感文件显示 `risk=HIGH`、`ok=false`，没有进入工具执行。
5. 审计校验显示 `ok=true`。

## 1. 演示前准备

### 1.1 打开 PowerShell

操作：

1. 按键盘上的 `Win` 键。
2. 输入 `PowerShell`。
3. 打开“Windows PowerShell”。
4. 如果要录屏，把窗口最大化，并将字体调到观众能看清。

正确现象：

- 出现蓝色或黑色 PowerShell 窗口。
- 最后一行以类似 `PS C:\Users\你的用户名>` 开头。

建议旁边红字说明：

~~~text
SafeOps 的 CLI、Web、MCP 和测试均可从项目脚本启动。
~~~

### 1.2 进入项目目录

命令：

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
Get-Location
~~~

当前正确输出示例：

~~~text
Path
----
C:\Users\CanhuiBao\Desktop\中国软件杯
~~~

关键成功标志：

- 路径最后是 `中国软件杯`。
- 没有出现“找不到路径”。

如果路径不正确，后续可能出现：

~~~text
No module named safeops_agent
找不到 scripts\web.ps1
~~~

### 1.3 设置中文编码和源码模块路径

命令：

~~~powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='src'
~~~

正确现象：

- 三条命令通常没有任何输出。
- 没有红色报错，重新出现命令提示符，就是成功。

说明：

- 中文变成乱码时，先重新执行前两条。
- 如果已经执行 `python -m pip install -e .`，`PYTHONPATH` 不是必须的；演示时设置它更明确。
- 每次新开 PowerShell，都要重新设置这些环境变量。

### 1.4 检查 Python、pip 和 Node

命令：

~~~powershell
python --version
python -m pip --version
node --version
~~~

正确现象示例：

~~~text
Python 3.14.3
pip 25.x ...
v24.x.x
~~~

版本号不必完全一致：

- Python 必须是 3.10 或更高版本。
- pip 能输出版本即可。
- Node 只用于 7 项前端测试；不演示前端自动测试时可以暂时没有 Node。

错误现象：

~~~text
python 不是内部或外部命令
node 不是内部或外部命令
~~~

处理：

- Python 不存在：安装 Python 3.10+，安装时勾选“Add Python to PATH”。
- Node 不存在：安装 Node.js LTS；SafeOps CLI 本身仍可运行。

### 1.5 安装项目和测试依赖

首次运行执行：

~~~powershell
python -m pip install -e ".[test]"
python -m pip check
~~~

正确现象：

- 安装结尾出现 `Successfully installed`，或者提示依赖已经满足。
- `pip check` 输出：

~~~text
No broken requirements found.
~~~

说明：

- `-e` 是开发态安装，修改源码后不需要重复安装。
- 项目运行依赖包含 PyYAML；测试可选依赖包含 coverage。

### 1.6 检查关键文件是否存在

命令：

~~~powershell
Test-Path pyproject.toml
Test-Path config\app.yaml
Test-Path config\llm.yaml
Test-Path src\safeops_agent\agent.py
Test-Path web\index.html
Test-Path scripts\acceptance.ps1
~~~

正确现象：

~~~text
True
True
True
True
True
True
~~~

只要出现 `False`，说明当前目录不对或项目文件不完整。先不要录屏，重新确认第 1.2 节。

### 1.7 运行配置自检

命令：

~~~powershell
python -m safeops_agent.config_check
~~~

当前正确输出：

~~~text
配置校验通过：检查 5 个文件，0 个错误，0 个警告
~~~

关键成功标志：

- `检查 5 个文件`。
- `0 个错误`。
- `0 个警告`。
- 命令执行后 `$LASTEXITCODE` 为 0。

可以继续检查退出码：

~~~powershell
$LASTEXITCODE
~~~

正确现象：

~~~text
0
~~~

建议红框框选：

- `配置校验通过`。
- `0 个错误，0 个警告`。

建议旁边红字说明：

~~~text
公共配置、工具白名单、风险策略和模型配置均通过启动前校验。
~~~

## 2. 选择运行模式

SafeOps 有离线和在线两种意图理解方式。安全策略和工具执行完全相同，区别只是“谁来选择候选工具”。

### 2.1 离线规则模式：正式答辩首先使用

命令：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
python -c "from safeops_agent.llm import get_provider; print(type(get_provider()).__name__)"
~~~

正确输出：

~~~text
RuleBasedProvider
~~~

正确现象：

- 不需要网络。
- 不消耗 API。
- 自然语言由确定性规则选择工具。
- 适合录屏和正式答辩，结果最稳定。

建议旁边红字说明：

~~~text
核心运维能力可完全离线运行，大模型只是可选的意图增强层。
~~~

### 2.2 真实 DeepSeek 模式：演示在线增强时使用

如果 `config\llm.local.yaml` 还不存在：

~~~powershell
Copy-Item config\llm.local.yaml.example config\llm.local.yaml
notepad config\llm.local.yaml
~~~

只填写：

~~~yaml
llm_api_key: "你的 DeepSeek API Key"
~~~

不要修改公共 `config\llm.yaml` 保存密钥，不要在录屏中打开本地密钥文件。

保存后执行：

~~~powershell
Remove-Item Env:SAFEOPS_LLM_DISABLED -ErrorAction SilentlyContinue
python -c "from safeops_agent.llm import get_provider; print(type(get_provider()).__name__)"
~~~

Key 和配置正确时，输出：

~~~text
DeepSeekProvider
~~~

如果输出：

~~~text
RuleBasedProvider
~~~

说明当前没有采用在线 Provider。依次检查：

1. 是否还设置着 `SAFEOPS_LLM_DISABLED=1`。
2. `config\llm.local.yaml` 是否存在。
3. 文件中是否只写了 `llm_api_key`。
4. 是否在正确项目目录运行。

### 2.3 两种模式怎么选

| 场景 | 推荐模式 |
| --- | --- |
| 第一次跑项目 | 离线 |
| 正式录屏主流程 | 离线 |
| 答辩现场主流程 | 离线 |
| 展示真实大模型接入 | 在线，只演示一条 LOW 请求 |
| 网络不稳定 | 离线 |
| 自动测试 | 离线 |

## 3. 功能一：查看 25 个固定工具

### 3.1 输出工具清单

命令：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
python -m safeops_agent.cli --list-tools
~~~

正确现象：

- 输出一个较长的 JSON 数组。
- 每个对象都包含 `name`、`description`、`category`、`risk`、`inputSchema`、`outputSchema` 和 `annotations`。
- 开头能看到 `system.info`。
- 中间能看到 `diagnostics.resources`、`service.restart`、`file.apply`。
- 结尾能看到 `safeops.confirm`。
- 当前总数是 25。

典型片段：

~~~json
{
  "name": "system.info",
  "category": "system",
  "risk": "LOW",
  "annotations": {
    "readOnlyHint": true,
    "requiresConfirmation": false
  }
}
~~~

中风险工具的典型片段：

~~~json
{
  "name": "service.restart",
  "risk": "MEDIUM",
  "annotations": {
    "readOnlyHint": false,
    "requiresConfirmation": true
  }
}
~~~

关键成功标志：

- 工具来自固定列表。
- LOW 工具 `readOnlyHint=true`。
- MEDIUM 工具 `requiresConfirmation=true`。
- 没有 `shell.exec`、`cmd.exec` 或任意命令执行工具。

建议旁边红字说明：

~~~text
系统只开放 25 个固定 Schema 工具，大模型不能生成新的执行通道。
~~~

## 4. 功能二：LOW 只读查询

### 4.1 查看系统信息

命令：

~~~powershell
python -m safeops_agent.cli "查看系统信息" --json
~~~

当前 Windows 正确输出关键片段：

~~~json
{
  "ok": true,
  "message": "系统信息采集完成：Windows / AMD64",
  "tool": "system.info",
  "risk": "LOW",
  "requires_confirmation": false,
  "risk_score": 10,
  "pending_action_id": null
}
~~~

正确现象：

- `ok` 是 `true`。
- `tool` 是 `system.info`。
- `risk` 是 `LOW`。
- `requires_confirmation` 是 `false`。
- `risk_score` 当前为 10。
- `reasoning_chain` 有 5 步：上下文、意图筛查、工具选择、风险裁决、执行。
- 最后一步 `executed=true`、`ok=true`。

以下字段会随电脑变化，不要要求完全相同：

- `hostname`。
- Windows/Linux 版本。
- CPU 架构。
- Python 版本。

建议红框框选：

- `"ok": true`。
- `"tool": "system.info"`。
- `"risk": "LOW"`。
- 第 5 步 `"executed": true`。

建议旁边红字说明：

~~~text
自然语言被映射为固定只读工具，经本地 LOW 裁决后执行成功。
~~~

### 4.2 查看 CPU、内存和磁盘

命令：

~~~powershell
python -m safeops_agent.cli "查看CPU和内存" --json
~~~

正确输出关键片段：

~~~json
{
  "ok": true,
  "message": "CPU、内存和磁盘指标采集完成",
  "tool": "system.resources",
  "risk": "LOW",
  "requires_confirmation": false
}
~~~

`data` 中应该包含：

- `cpu`。
- `memory`。
- `disk`。
- `disk.used_percent`。

Windows 上可能出现：

~~~json
"memory": {
  "available": null,
  "note": "memory detail requires Linux /proc"
}
~~~

这是正确的跨平台降级现象，不是程序失败。Linux/麒麟上会读取 `/proc`，返回更完整的内存和负载数据。

### 4.3 查看端口、进程和磁盘分区

命令：

~~~powershell
python -m safeops_agent.cli "查看监听端口" --json
python -m safeops_agent.cli "查看进程列表" --json
python -m safeops_agent.cli "查看磁盘分区" --json
~~~

正确现象：

- 三条命令均应选择对应 LOW 工具。
- 返回数据量可能不同，但 `risk=LOW`、`requires_confirmation=false`。
- 端口和进程数量随当前机器变化。

对应工具：

| 请求 | 正确工具 |
| --- | --- |
| 查看监听端口 | `network.listening_ports` |
| 查看进程列表 | `process.list` |
| 查看磁盘分区 | `disk.partitions` |

## 5. 功能三：数据驱动诊断

### 5.1 诊断 CPU、内存和磁盘

命令：

~~~powershell
python -m safeops_agent.cli "诊断CPU和内存" --json
~~~

当前健康机器的正确输出关键片段：

~~~json
{
  "ok": true,
  "message": "资源诊断完成",
  "tool": "diagnostics.resources",
  "risk": "LOW",
  "data": {
    "diagnosis": {
      "scenario": "CPU/内存/磁盘资源诊断",
      "severity": "healthy",
      "possible_causes": [
        "已采集资源指标均未达到预警阈值，当前未发现明确资源瓶颈。"
      ],
      "evidence": {
        "evaluated_thresholds": {
          "cpu_load_warning_ratio": 0.75,
          "cpu_load_critical_ratio": 1.0,
          "resource_warning_percent": 80.0,
          "resource_critical_percent": 90.0
        }
      }
    }
  }
}
~~~

正确现象不是必须显示 `healthy`。如果当前机器负载或磁盘占用较高，也可能显示 warning/critical。真正的成功标准是：

- `ok=true`。
- `tool=diagnostics.resources`。
- 有 `possible_causes` 和 `recommended_actions`。
- `evidence` 中有真实采集值。
- `evaluated_thresholds` 明确写出判断阈值。

这证明诊断不是固定模板。

建议旁边红字说明：

~~~text
诊断先采集真实指标，再按明确阈值生成原因和建议；健康时不会伪造故障。
~~~

### 5.2 诊断端口、服务和日志

命令：

~~~powershell
python -m safeops_agent.cli "排查端口占用" --json
python -m safeops_agent.cli "诊断 nginx 服务" --json
python -m safeops_agent.cli "诊断最近错误日志" --json
~~~

正确工具：

| 请求 | 正确工具 |
| --- | --- |
| 排查端口占用 | `diagnostics.network_ports` |
| 诊断 nginx 服务 | `diagnostics.service` |
| 诊断最近错误日志 | `diagnostics.logs` |

Windows 上 `systemctl`、`journalctl` 不存在时，服务或日志采集可能返回“不支持/命令不存在”。这是环境能力边界；Linux/麒麟环境才是完整服务诊断目标。

## 6. 功能四：MEDIUM 中风险预演

### 6.1 请求重启 nginx

命令：

~~~powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
~~~

当前正确输出关键片段：

~~~json
{
  "ok": false,
  "message": "未执行 service.restart：中风险工具需要用户确认",
  "tool": "service.restart",
  "risk": "MEDIUM",
  "requires_confirmation": true,
  "risk_score": 65,
  "data": {
    "dry_run_plan": {
      "action": "service.restart",
      "target": {
        "service": "nginx"
      }
    },
    "pending_action_id": "<每次随机生成的32位action_id>"
  }
}
~~~

决策轨迹第 5 步应显示：

~~~text
需人工确认，已生成 dry-run 预演计划与一次性确认令牌，未执行任何真实变更
~~~

关键成功标志：

- `risk=MEDIUM`。
- `requires_confirmation=true`。
- `dry_run_plan` 包含前置检查、执行步骤、回滚建议和风险控制。
- 生成 32 位 `pending_action_id`。
- `executed=false`、`dry_run=true`。

### 6.2 为什么命令退出码是 1

紧接着执行：

~~~powershell
$LASTEXITCODE
~~~

正确输出：

~~~text
1
~~~

这是正确的业务状态，表示“动作尚未完成，正在等待人工确认”，不是程序崩溃。

同样，HIGH 拒绝也会返回 1，方便 CI 和脚本识别“没有执行成功”。

### 6.3 正式答辩为什么停在预演

Windows 演示机没有 `systemctl`，也不应该为了答辩真的重启服务。因此现场展示到 action_id 为止。

只有在准备好的麒麟/Linux 测试机上，确认服务：

~~~powershell
python -m safeops_agent.cli --confirm <复制上一步action_id> --json
~~~

成功前提：

- nginx 位于 `config/tools.yaml` 的 allowlist。
- nginx 不在保护列表。
- 当前账号具备所需权限。
- action_id 未过期、未使用且属于当前入口会话。
- Linux root 保护没有阻断。

成功时应看到 `ok=true`，并返回服务变更前后状态。Windows 上不要把“systemctl 不存在”误写成 SafeOps 安全链失败。

### 6.4 action_id 的安全属性

- 十分钟有效。
- 只能使用一次。
- 绑定入口会话。
- 保存的是已经裁决的 `tool + args`。
- 确认时不重新理解原始文本。
- 确认前重新应用当前策略。
- 写盘前加密并带 HMAC。
- 有线程锁、跨进程锁和原子替换。

建议旁边红字说明：

~~~text
中风险首次只预演；确认执行使用已保存参数，防止“预演 A、执行 B”。
~~~

## 7. 功能五：HIGH 高风险拒绝

### 7.1 请求覆盖敏感文件

命令：

~~~powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
~~~

当前正确输出：

~~~json
{
  "ok": false,
  "message": "已拒绝执行：高风险操作涉及敏感路径：/",
  "tool": null,
  "risk": "HIGH",
  "requires_confirmation": false,
  "risk_score": 95,
  "pending_action_id": null
}
~~~

决策轨迹只应有两步：

1. 上下文指代解析。
2. 意图风险筛查直接拒绝。

正确现象：

- `tool=null`，说明没有选择真实工具。
- `risk=HIGH`。
- `ok=false`。
- `requires_confirmation=false`，高风险不能靠确认绕过。
- 不存在执行阶段。
- `$LASTEXITCODE` 为 1。

### 7.2 其他拒绝示例

~~~powershell
python -m safeops_agent.cli "删除根目录所有文件" --json
python -m safeops_agent.cli "停止 auditd 服务" --json
python -m safeops_agent.cli "重启 not-allowed-service 服务" --json
~~~

正确现象：

- 破坏性意图和敏感路径直接 HIGH。
- 保护服务被拒绝。
- 非白名单服务被拒绝。
- handler 不执行。

建议旁边红字说明：

~~~text
危险意图在模型和工具执行之前就被本地策略阻断，高风险不存在确认后门。
~~~

## 8. 功能六：审计查询与完整性验证

### 8.1 查看最近审计

命令：

~~~powershell
python -m safeops_agent.cli --show-audit --audit-limit 3
~~~

正确现象：

- 输出最近 3 条脱敏审计事件。
- 能看到来源、请求、工具、风险、决策、结果和结构化决策轨迹。
- API Key、Bearer、action_id 和文件内容不会以明文落盘。

按风险筛选：

~~~powershell
python -m safeops_agent.cli --show-audit --audit-risk HIGH --audit-limit 3
~~~

正确现象：

- 只显示 HIGH 事件。
- 能看到刚才的 `覆盖 /etc/passwd` 拒绝记录。

### 8.2 验证审计完整性

命令：

~~~powershell
python -m safeops_agent.cli --verify-audit
~~~

当前正确输出示例：

~~~json
{
  "ok": true,
  "checked": 467,
  "legacy": 105,
  "segments": 1,
  "first_bad_line": null,
  "reason": null
}
~~~

`checked` 会随着每次运行继续增加，不要求恰好等于 467。成功标准：

- `ok=true`。
- `checked` 大于 0。
- `first_bad_line=null`。
- `reason=null`。

建议红框框选：

- `"ok": true`。
- `"first_bad_line": null`。

建议旁边红字说明：

~~~text
审计同时使用 SHA-256 链、HMAC 和持久化锚点，可检测修改、删除和尾部截断。
~~~

### 8.3 审计失败时不要做什么

如果 `ok=false`：

- 不要直接删除 audit.log。
- 不要单独复制日志而遗漏 key 和 anchor。
- 不要为了演示修改历史审计。

应备份整个 `data/`，查看 `first_bad_line` 和 `reason` 后再定位问题。

## 9. 功能七：Web 工作台

本章故意把 PowerShell 和浏览器分成三个窗口。第一次操作时不要复用同一个窗口，否则很容易把命令输入到正在运行 Web 服务的终端中。

| 名称 | 实际窗口 | 只负责什么 | 本章中是否可以输入命令 |
| --- | --- | --- | --- |
| 窗口 A | 第一个 PowerShell | 设置登录令牌、启动手工 Web | Web 启动前可以；Web 运行时不可以 |
| 窗口 B | Edge、Chrome 等浏览器 | 登录并点击 Web 工作台 | 不输入 PowerShell 命令 |
| 窗口 C | 第二个 PowerShell | 健康检查、停止 Web、运行自动冒烟 | 可以 |

完整顺序如下：

~~~text
窗口 A：设置 Token并复制 → 启动手工 Web → 保持窗口运行
窗口 B：打开网页 → 登录 → 演示 LOW/MEDIUM/HIGH → 查看审计
窗口 A：按 Ctrl+C 停止手工 Web
窗口 C：运行 web-smoke.ps1 → 等待脚本自动结束
窗口 A：清除 Token
窗口 B：关闭网页标签
~~~

### 9.1 准备窗口 A，并设置 Web 登录令牌

#### 第 1 步：打开窗口 A

1. 按一下键盘上的 Windows 徽标键。
2. 输入 `PowerShell`。
3. 点击搜索结果中的“Windows PowerShell”，或直接按 Enter。
4. 在新窗口中输入：

~~~powershell
Set-Location 'C:\Users\CanhuiBao\Desktop\中国软件杯'
~~~

5. 按 Enter。

正确现象：

- PowerShell 提示符所在目录变为 `C:\Users\CanhuiBao\Desktop\中国软件杯`。
- 没有红色报错。

后面把这个窗口称为“窗口 A”。不要关闭它。

#### 第 2 步：在窗口 A 生成 Token

在窗口 A 中输入：

~~~powershell
$env:SAFEOPS_TOKEN = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
~~~

按 Enter。此命令生成一个 64 位随机字符串，只保存在窗口 A 当前进程中。

然后在同一个窗口 A 中输入：

~~~powershell
Write-Output $env:SAFEOPS_TOKEN
~~~

按 Enter。

正确现象：下一行显示一串由数字和小写字母组成的长字符串，例如：

~~~text
9db67114d7ae49b587b150c7774f63192d36022d8caa443d85779807d1e6b387
~~~

这里的示例只是格式说明，实际登录必须使用你自己窗口中显示的字符串。

如果 `Write-Output` 后面是空白行，说明 Token 没有设置成功。重新执行上面两条命令，不要继续启动 Web。

#### 第 3 步：在窗口 A 复制 Token

在窗口 A 中输入：

~~~powershell
$env:SAFEOPS_TOKEN | Set-Clipboard
~~~

按 Enter。

正确现象：

- 命令没有文字输出。
- 没有红色报错。
- Token 已进入 Windows 剪贴板，稍后可在浏览器按 `Ctrl+V` 粘贴。

注意：

- 不要把真实 Token 写进 `config/app.yaml`、README、截图或录屏字幕。
- 新开的窗口 C 通常看不到窗口 A 中的 Token，这是 Windows 环境变量的正常隔离现象。
- Web 启动后，窗口 A 会被服务占用，不能再在里面执行 `Write-Output`。因此必须在启动前完成查看和复制。
- 如果启动后才发现忘记复制 Token，应按 9.5 的方法先停止 Web，重新设置并复制 Token，再重新启动。

### 9.2 在窗口 A 启动手工 Web

确认窗口 A 的提示符位于项目根目录，然后在窗口 A 输入：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

按 Enter。

正确现象：

- 窗口 A 持续运行，不再出现新的 `PS C:\...>` 输入提示符。
- 没有“`SAFEOPS_TOKEN is required`”报错。
- 没有“地址已被使用”或“端口被占用”报错。
- Web 正在本机 `127.0.0.1:8765` 上等待浏览器访问。

此时窗口 A 的正确使用方式是：

- 保持窗口打开。
- 可以最小化，但不能关闭。
- 不要继续键入健康检查、冒烟测试或停止脚本。
- 只有要用 `Ctrl+C` 停止手工 Web 时，才切回这个窗口。

这是因为 `web.ps1` 以前台方式运行服务器。终端没有返回 `PS C:\...>` 提示符时，表示它正在被 Web 服务占用。

### 9.3 打开窗口 C并检查 Web

这一步不是在窗口 A 中执行。

#### 第 1 步：打开第二个 PowerShell

1. 让窗口 A 继续运行。
2. 再按一次 Windows 徽标键。
3. 输入 `PowerShell`。
4. 再打开一个“Windows PowerShell”窗口。
5. 输入：

~~~powershell
Set-Location 'C:\Users\CanhuiBao\Desktop\中国软件杯'
~~~

6. 按 Enter。

后面把这个新窗口称为“窗口 C”。

#### 第 2 步：在窗口 C 做健康检查

在窗口 C 输入：

~~~powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
~~~

按 Enter。

正确现象：

- PowerShell 返回一个对象。
- 对象中能看到 `ok` 为 `True`，或等价的健康状态。
- 没有“无法连接到远程服务器”。

窗口 C 检查完后不要关闭，9.5 自动冒烟还会用到它。

### 9.4 在窗口 B 登录并逐项点击 Web 功能

#### 9.4.1 打开网页

1. 保持窗口 A 和窗口 C 都打开。
2. 点击任务栏中的 Edge 或 Chrome 图标；如果任务栏没有浏览器图标，按 Windows 徽标键，输入 `Edge`，再点击“Microsoft Edge”。
3. 点击浏览器顶部地址栏。
4. 输入：

~~~text
http://127.0.0.1:8765
~~~

5. 按 Enter。

后面把这个浏览器窗口称为“窗口 B”。

正确现象：

- 页面标题是“SafeOps Agent”。
- 页面左侧显示“系统信息”“资源指标”“诊断资源”“监听端口”“排查端口”“服务状态”“重启服务”“高风险拦截”。
- 页面中间上方显示“运维工作台”。
- 页面中间出现“工作台已就绪”。
- 页面右上区域出现“输入访问令牌”的密码框、“登录”按钮和“需要认证”。
- 页面连接状态显示“已连接”。

如果浏览器显示“无法访问此网站”：

1. 切回窗口 A。
2. 查看窗口 A 是否已经退出、被关闭或出现红色报错。
3. 如果窗口 A 已返回 `PS C:\...>`，按 9.2 重新启动。
4. 如果提示 8765 端口被占用，按 9.6 的“方法二”停止残留进程，再重新启动。

#### 9.4.2 登录

1. 在窗口 B 点击“输入访问令牌”密码框。
2. 按 `Ctrl+V`，粘贴 9.1 在窗口 A 复制的 Token。
3. 密码框只显示圆点或星号是正常现象。
4. 点击密码框右侧的“登录”按钮一次。
5. 等待页面完成加载。

正确现象：

- “需要认证”变为“已认证”。
- 右侧“工具清单”开始显示工具。
- 上方“工具数量”不再是 `-`，而是一个大于 0 的数字。
- URL 仍然是 `http://127.0.0.1:8765`，URL 中不会出现 Token。
- 页面没有跳转到另一个网站。

如果显示“认证失败”：

1. 不要反复猜测 Token。
2. 检查粘贴内容前后是否带空格。
3. 如果已经忘记 Token，切回窗口 A，按 `Ctrl+C` 停止 Web。
4. 等窗口 A 重新出现 `PS C:\...>` 提示符后，重新执行 9.1 的生成、显示和复制命令。
5. 在窗口 A 按 9.2 重新启动 Web。
6. 回到窗口 B，按 `Ctrl+R` 刷新页面，再粘贴新 Token 登录。

注意：Web 正在运行时，窗口 A 没有 PowerShell 提示符，不能直接在其中输入 `Write-Output $env:SAFEOPS_TOKEN`。窗口 C 也不会自动继承窗口 A 的 Token。

#### 9.4.3 认识工作台各区域

登录后先不要急着点击，确认页面分区：

| 页面位置 | 能看到的内容 | 用途 |
| --- | --- | --- |
| 左侧 | 八个快捷按钮 | 点击后把示例请求填入输入框 |
| 中间上方 | 最近工具、风险等级、风险评分、确认状态、决策摘要、工具数量 | 查看最近一次请求的安全决策 |
| 中间主体 | 请求与响应消息 | 查看执行结果、Dry-run 预案和决策审计轨迹 |
| 中间底部 | “输入运维请求”输入框和“执行”按钮 | 发送自然语言请求 |
| 右侧上方 | 工具清单 | 查看工具名、风险和类别 |
| 右侧下方 | 审计日志和三个筛选框 | 查看每次请求留下的审计事件 |
| 页面顶部 | “刷新审计”“导出报告” | 手工刷新或导出审计结果 |

重要：点击左侧快捷按钮只会把文字填入“输入运维请求”输入框，不会立即执行。还必须再点击中间底部的“执行”按钮。

#### 9.4.4 演示 LOW：查看系统信息

1. 在窗口 B 点击左侧“系统信息”。
2. 查看中间底部输入框，确认出现“查看系统信息”。
3. 点击输入框右侧的“执行”。
4. 等待响应出现在中间消息区。

正确现象：

- 中间消息区先出现“请求：查看系统信息”，随后出现“响应”。
- 上方“最近工具”显示 `system.info`。
- “风险等级”显示 `LOW`。
- “确认状态”显示“无需确认”。
- 响应中直接显示结果，不出现人工确认按钮。
- 响应下方可以展开“原始数据”。
- 右侧审计日志新增“查看系统信息”事件。

如果只看到输入框中有文字、没有响应，说明只点了左侧快捷按钮，还没有点击“执行”。

#### 9.4.5 演示 MEDIUM：重启 nginx 服务

1. 在窗口 B 点击左侧“重启服务”。
2. 确认中间底部输入框出现“重启 nginx 服务”。
3. 点击“执行”。
4. 等待中间消息区出现新的响应。
5. 向下滚动中间消息区，查看完整预案。

正确现象：

- 上方“风险等级”显示 `MEDIUM`。
- “确认状态”显示“需要确认”。
- 页面显示“Dry-run 预案”，其中包含前置检查、计划步骤、风险控制和回滚建议。
- 页面显示“决策审计轨迹”。
- 响应下方出现“确认执行该操作（一次性令牌，10 分钟内有效）”按钮。
- 在点击确认按钮之前，重启操作不会实际执行。

答辩演示安全门控时，建议停在确认按钮出现这一步，不点击确认，这已经能证明 MEDIUM 操作需要人工确认。

如果确实要演示确认流程：

1. 先确认测试机允许操作目标服务。
2. 点击“确认执行该操作（一次性令牌，10 分钟内有效）”一次。
3. 按钮会先显示“已提交确认…”。
4. 查看其后新增的响应，判断操作成功或失败。
5. nginx 在 Windows 上通常不存在，因此测试机可能返回服务不存在或执行失败；这不等于确认机制失效。
6. 不要连续重复点击。

#### 9.4.6 演示 HIGH：覆盖敏感文件

1. 在窗口 B 点击左侧“高风险拦截”。
2. 确认中间底部输入框出现“覆盖 /etc/passwd”。
3. 点击“执行”。
4. 等待响应。

正确安全现象：

- 上方“风险等级”显示 `HIGH`。
- 响应明确表示拒绝或阻止该操作。
- 不执行文件覆盖。
- 不出现人工确认按钮，HIGH 操作不能通过确认绕过。
- 右侧审计日志保留这次拒绝记录。

这里“被拒绝”就是测试通过，不是功能失败。

#### 9.4.7 查看、筛选和导出审计

1. 仍在窗口 B，查看页面右侧“审计日志”。
2. 如果最新事件没有立即出现，点击页面顶部“刷新审计”。
3. 点击“全部来源”下拉框，选择 `web`。
4. 点击“全部风险”下拉框，依次选择 `LOW`、`MEDIUM` 或 `HIGH`，观察列表变化。
5. 点击“工具名筛选”输入框，输入 `system.info`，等待约 1 秒。

正确现象：

- 筛选条件改变后，审计列表只显示匹配事件。
- 没有匹配项时显示“没有匹配筛选条件的审计事件”，不是页面故障。
- 删除工具名筛选内容，并把两个下拉框恢复为“全部来源”和“全部风险”后，完整列表恢复。

导出审计：

1. 先清空不需要的筛选条件。
2. 点击页面顶部“导出报告”。
3. 浏览器会打开或下载审计导出内容；具体表现由浏览器下载设置决定。
4. 如果浏览器右上角出现下载图标，点击该图标即可查看文件。

### 9.5 运行自动 Web 冒烟

自动冒烟不是在窗口 A 中执行，也不需要在浏览器中点击任何按钮。脚本会自己启动一个隐藏的临时 Web，完成检查后再自动停止它。

手工 Web 和自动冒烟都使用 `127.0.0.1:8765`，因此运行冒烟前必须先停止窗口 A 中的手工 Web。

#### 9.5.1 先在窗口 A 停止手工 Web

推荐方法：

1. 从浏览器窗口 B 切回启动 Web 的窗口 A。
2. 用鼠标点击一下窗口 A，确保它是当前活动窗口。
3. 按住键盘 `Ctrl`，再按一次字母 `C`。
4. 松开按键。
5. 等待窗口 A 重新出现 `PS C:\Users\CanhuiBao\Desktop\中国软件杯>` 提示符。

正确现象：

- Web 服务结束。
- 窗口 A 重新允许输入 PowerShell 命令。
- 没有必要关闭窗口 A。

验证确实停止：

1. 切回浏览器窗口 B。
2. 按 `Ctrl+R` 刷新。
3. 浏览器应显示“无法访问此网站”“拒绝连接”或等价提示。

此时浏览器连接失败是正确现象，说明 8765 端口已经让给自动冒烟。

如果按 `Ctrl+C` 后窗口 A 仍然没有出现提示符，可以在窗口 C 执行：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
~~~

窗口 C 正确输出类似：

~~~text
Stopping SafeOps Web process: 12345
~~~

其中进程号每次可能不同。随后窗口 A 会结束 Web 并重新出现提示符。

#### 9.5.2 在窗口 C 运行冒烟

1. 切到之前打开的第二个 PowerShell，也就是窗口 C。
2. 确认窗口 C 位于项目根目录。如果不确定，重新输入：

~~~powershell
Set-Location 'C:\Users\CanhuiBao\Desktop\中国软件杯'
~~~

3. 在窗口 C 输入：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
~~~

4. 按 Enter。
5. 等待脚本自己执行完，不要按 `Ctrl+C`。
6. 冒烟运行期间不需要切到窗口 B，也不需要刷新或登录网页。

脚本会自动完成以下动作：

1. 临时关闭 LLM，使用确定性的离线规则模式。
2. 生成临时强 Token。
3. 在后台启动临时 Web。
4. 检查 health、tools、agent 和 audit 接口。
5. 自动停止临时 Web。
6. 恢复窗口 C 原有的 Token 环境状态。

正确现象：窗口 C 最后显示：

~~~text
Web smoke passed: health/tools/agent/audit APIs are available.
~~~

随后重新出现 `PS C:\Users\CanhuiBao\Desktop\中国软件杯>` 提示符。此时临时 Web 已自动停止，不需要再运行 `stop-web.ps1`。

再次切到窗口 B 并刷新时，浏览器仍然应显示无法连接。这也是正确现象，因为冒烟服务已经自动退出。

如果窗口 C 提示端口 8765 被占用：

1. 不要反复启动冒烟。
2. 在窗口 C 执行：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
~~~

3. 看到 `Stopping SafeOps Web process: ...` 后，再次运行 `scripts\web-smoke.ps1`。
4. 如果输出 `No SafeOps Web process found.`，说明没有找到本项目的 Web 进程；再检查是否有其他软件占用了 8765 端口。

### 9.6 停止 Web 与最后清理

先判断自己属于哪种情况：

| 当前情况 | 还要不要停止 Web | 应在哪个窗口操作 |
| --- | --- | --- |
| 刚完成 9.5 自动冒烟 | 不需要；脚本已自动停止临时 Web | 不用执行停止命令 |
| 手工 Web 仍在窗口 A 前台运行 | 需要 | 优先在窗口 A 按 `Ctrl+C` |
| 找不到窗口 A，或 `Ctrl+C` 无效 | 需要 | 在窗口 C 运行 `stop-web.ps1` |

#### 方法一：在窗口 A 按 Ctrl+C，推荐

1. 切到窗口 A。
2. 点击窗口 A。
3. 按 `Ctrl+C`。
4. 等待 `PS C:\...>` 提示符重新出现。

#### 方法二：在窗口 C 运行停止脚本

仅在方法一不方便或无效时使用。在窗口 C 输入：

~~~powershell
Set-Location 'C:\Users\CanhuiBao\Desktop\中国软件杯'
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
~~~

正确现象之一：

~~~text
Stopping SafeOps Web process: 12345
~~~

如果本来就没有 Web 进程，则正确输出是：

~~~text
No SafeOps Web process found.
~~~

这两种输出都不是报错。

#### 清除窗口 A 中的 Token

`SAFEOPS_TOKEN` 是在窗口 A 中设置的，所以应回到窗口 A 清除。在窗口 C 执行清除命令不能清除窗口 A 自己保存的环境变量。

确认窗口 A 已经重新出现 PowerShell 提示符，然后在窗口 A 输入：

~~~powershell
Remove-Item Env:SAFEOPS_TOKEN -ErrorAction SilentlyContinue
Write-Output $env:SAFEOPS_TOKEN
~~~

正确现象：

- `Write-Output` 后面是空白行。
- 没有红色报错。

最后：

1. 切到浏览器窗口 B，关闭 SafeOps 网页标签。
2. 窗口 A 和窗口 C 如果不再使用，可以点击右上角 `×` 关闭。
3. 不要把 Token 留在答辩截图、聊天记录或提交文件中。

### 9.7 第 9 章结束时的正确状态

全部操作完成后，应同时满足：

- 窗口 A 没有正在运行的 Web 服务。
- 窗口 A 中 `Write-Output $env:SAFEOPS_TOKEN` 输出空白。
- 窗口 C 已显示冒烟通过文本并返回 PowerShell 提示符。
- 浏览器访问 `http://127.0.0.1:8765` 时无法连接。
- 8765 端口没有残留的 SafeOps Web 进程。

## 10. 功能八：MCP 标准工具服务

MCP 用于把 SafeOps 的固定工具接入支持 Model Context Protocol 的客户端。它不是另一个绕过策略的入口，所有调用仍经过同一 Tool Registry、PolicyEngine 和签名审计。

本章只需要一个新的 PowerShell。为了避免和第 9 章的窗口混淆，把它称为“窗口 D（MCP 专用窗口）”。

MCP stdio 不是普通的中文命令行，也不是菜单。启动以后，窗口 D 中输入的每一行都会被当成一条 JSON-RPC 消息解析。

必须记住：

- 不能只输入 `initialize`。
- 不能只输入 `notifications/initialized`。
- 不能输入“1.”“2.”等步骤编号。
- 必须复制本章代码块中的整行 JSON，并按一次 Enter。
- JSON 必须使用英文半角双引号 `"`，不能使用中文引号 `“”`。
- 一条 JSON 内部不能手工换行。

### 10.1 打开窗口 D并查看工具

#### 第 1 步：打开 MCP 专用 PowerShell

1. 按 Windows 徽标键。
2. 输入 `PowerShell`。
3. 点击“Windows PowerShell”或按 Enter。
4. 输入：

~~~powershell
Set-Location 'C:\Users\CanhuiBao\Desktop\中国软件杯'
~~~

5. 按 Enter。

后面把这个终端称为“窗口 D”。

#### 第 2 步：先查看 MCP 工具

在窗口 D 输入：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\show-tools.ps1
~~~

按 Enter并等待命令结束。

也可以使用：

~~~powershell
python -m safeops_agent.cli --list-tools
~~~

正确现象：

- 输出 25 个工具。
- 每个工具都有严格的 `inputSchema` 和 `outputSchema`。
- LOW 工具有 `readOnlyHint=true`。
- MEDIUM 工具有 `requiresConfirmation=true`。
- 能看到 `system.info` 和 `safeops.confirm`。
- 输出结束后重新出现 `PS C:\Users\CanhuiBao\Desktop\中国软件杯>` 提示符。

工具清单很长、控制台自动换行是正常现象。

核心安全含义：

~~~text
MCP 暴露的是同一组固定 Schema 工具，不提供任意 Shell 或模型直执行能力。
~~~

### 10.2 在窗口 D 启动 MCP stdio 服务

确认窗口 D 已经重新出现 PowerShell 提示符，然后输入：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp-stdio.ps1
~~~

按 Enter。

安装项目后也可以使用：

~~~powershell
safeops-mcp
~~~

正确现象：

- 命令执行后没有重新出现 `PS C:\...>` 提示符。
- 窗口 D 看起来停在空白处，光标等待输入。
- 没有普通调试信息输出。
- 进程保持运行。

这不是卡死。此时窗口 D 已从“PowerShell 命令输入窗口”变成“MCP JSON 输入通道”。

启动后不要在窗口 D 输入下面这些内容：

~~~text
initialize
notifications/initialized
tools/list
Write-Output test
~~~

这些都不是完整 JSON，会触发解析错误或未知方法错误。

如果已经看到：

~~~json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "解析 JSON 失败"}}
~~~

说明：

- MCP 服务已经成功运行。
- 只是刚才输入的那一行不是合法 JSON。
- 服务不会因为这次错误退出。
- 不需要重启，也不需要重新运行 `mcp-stdio.ps1`。
- 直接继续执行 10.3，把第一条完整初始化 JSON 粘贴到同一个窗口 D 即可。

### 10.3 在同一个窗口 D 完成 MCP 生命周期

下面三条消息必须严格按顺序发送。每个代码块中的内容都是一整行。

#### 第 1 条：发送 initialize 请求

1. 用鼠标完整选中下面代码块中的一整行。
2. 按 `Ctrl+C` 复制。这里是在网页或 Markdown 阅读器中复制，不是在正在运行 MCP 的窗口中按 `Ctrl+C`。
3. 切回窗口 D。
4. 在窗口 D 中单击鼠标右键粘贴，或按 `Ctrl+V`。
5. 确认粘贴内容以 `{` 开头、以 `}` 结尾。
6. 按一次 Enter。

要复制的完整单行：

~~~json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"manual-demo","version":"1.0"}}}
~~~

正确现象：窗口 D 紧接着输出一行响应，其中至少能看到：

~~~text
"id": 1
"protocolVersion": "2025-11-25"
"name": "safeops-agent"
~~~

完整输出可能很长，控制台可能把它在屏幕上自动折成几行。屏幕自动折行不等于协议消息被拆分，这是正常现象。

如果仍返回 `-32700`：

- 检查是否只复制了 `initialize` 这个单词。
- 检查开头和结尾的花括号是否完整。
- 检查是否把英文双引号变成了中文引号。
- 检查是否在 JSON 中间按了 Enter。
- 重新复制上面的完整单行再发送。

#### 第 2 条：发送 initialized 通知

在收到 `id: 1` 的初始化响应后，把下面完整单行粘贴到同一个窗口 D，然后按 Enter：

~~~json
{"jsonrpc":"2.0","method":"notifications/initialized"}
~~~

正确现象：

- 按 Enter 后没有任何 JSON 响应。
- 光标移动到下一空白行，继续等待输入。
- MCP 进程仍在运行。

“没有输出”是正确现象，因为 `notifications/initialized` 是通知，不带 `id`，服务端按协议不回复通知。

不要因为没有输出而重复发送，也不要按 `Ctrl+C`。等待约 1 秒后继续下一条。

#### 第 3 条：请求 tools/list

把下面完整单行粘贴到同一个窗口 D，然后按 Enter：

~~~json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
~~~

正确现象：

- 返回的 JSON 中有 `"id": 2`。
- 返回内容中有 `"tools"` 数组。
- 一共返回 25 个工具。
- 能在长输出中看到 `system.info` 和 `safeops.confirm`。
- 每个工具带有 Schema、risk 和 annotations。
- 输出结束后 MCP 继续等待下一行 JSON，不会返回 PowerShell 提示符。

工具列表响应非常长，自动铺满多行是正常现象，不需要逐字检查。

#### 第 4 条：可选的 ping 检查

继续在窗口 D 粘贴：

~~~json
{"jsonrpc":"2.0","id":3,"method":"ping","params":{}}
~~~

正确响应：

~~~json
{"jsonrpc": "2.0", "id": 3, "result": {}}
~~~

空的 `result` 表示连通性正常。

### 10.4 在窗口 D 调用 LOW 工具

必须先完成 10.3 的初始化和初始化完成通知，然后才能调用工具。

把下面完整单行粘贴到仍在运行 MCP 的窗口 D，再按 Enter：

~~~json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"system.info","arguments":{}}}
~~~

正确现象：

- 返回的响应 `id` 是 `4`。
- `result.isError` 是 `false`。
- `result.structuredContent.ok` 是 `true`。
- 风险等级是 `LOW`。
- 返回本机系统信息。
- LOW 只读操作不要求人工确认。

注意：这里的 `id` 只是请求和响应的对应编号。只要同一批演示中不混淆，使用其他数字也可以。

### 10.5 在窗口 D 演示 MEDIUM 确认门控

#### 第 1 步：首次请求重启服务

继续在同一个窗口 D 粘贴：

~~~json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"service.restart","arguments":{"service":"nginx"}}}
~~~

正确安全现象：

- 返回 `TOOL_CONFIRMATION_REQUIRED`。
- 返回 Dry-run 信息。
- 返回 `pending_action_id`。
- 不立即执行真实服务变更。
- 窗口 D 继续等待下一条 JSON。

答辩只演示安全门控时，到这里就可以停止，不必真的确认。

#### 第 2 步：需要时发送确认

如果确实要演示确认：

1. 在上一条长响应中找到 `pending_action_id`。
2. 只复制它对应的字符串值，不要复制字段名和双引号。
3. 把下面示例中的 `复制首次返回的action_id` 替换成真实值。
4. 保持同一个 MCP 进程，不能关闭并重新启动窗口 D，因为确认与当前会话绑定。
5. 粘贴替换后的完整单行并按 Enter。

~~~json
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"safeops.confirm","arguments":{"action_id":"复制首次返回的action_id"}}}
~~~

确认仍受会话、10 分钟有效期、一次性状态、服务白名单和当前策略约束。nginx 在 Windows 测试机上通常不存在，因此实际确认后可能返回服务不存在或执行失败；这不代表确认门控失效。

### 10.6 停止 MCP stdio

停止操作就在正在运行 MCP 的窗口 D 中完成，不需要再开新 PowerShell。

1. 用鼠标点击窗口 D。
2. 按住键盘 `Ctrl`。
3. 按一次字母 `C`。
4. 松开按键。
5. 等待 PowerShell 提示符重新出现。

正确现象：

- MCP stdio 进程退出。
- 窗口 D 重新显示 `PS C:\Users\CanhuiBao\Desktop\中国软件杯>`。
- 某些 Python 环境可能在退出时显示 `KeyboardInterrupt` 或 `^C`，这是手工中断进程的正常现象。

注意复制 JSON 时的 `Ctrl+C` 与停止进程时的 `Ctrl+C` 不同：

- 在手册或网页中选中文字后按 `Ctrl+C`：复制文字。
- 焦点位于正在运行 MCP 的窗口 D 时按 `Ctrl+C`：停止 MCP 进程。

### 10.7 常见错误对照

| 看到的现象 | 原因 | 应在哪个窗口处理 | 处理方法 |
| --- | --- | --- | --- |
| `-32700 解析 JSON 失败` | 输入了方法名、中文引号、不完整 JSON 或多行 JSON | 当前窗口 D | 不用重启，重新粘贴完整单行 JSON |
| `-32600 MCP 会话尚未完成 initialize/initialized 生命周期` | 直接发送了 `tools/list` 或 `tools/call` | 当前窗口 D | 按 10.3 从 `initialize` 重新完成生命周期 |
| `-32601 未知方法` | `method` 拼写错误 | 当前窗口 D | 对照手册修正方法名 |
| `-32602` | `params`、`name` 或 `arguments` 格式错误 | 当前窗口 D | 复制手册的完整示例，不要删字段 |
| 发送 initialized 后没有输出 | 通知本来就没有响应 | 无需处理 | 直接继续发送 `tools/list` |
| 工具列表铺满很多屏 | 25 个工具及 Schema 被压在一条响应中 | 无需处理 | 检查 `id:2`、`system.info` 和 `safeops.confirm` 即可 |
| 出现 `PS C:\...>` 提示符 | MCP 已经退出，当前是普通 PowerShell | 窗口 D | 重新执行 `scripts\mcp-stdio.ps1` |
| 输入 JSON 后出现 PowerShell 自己的红色语法错误 | JSON 被输入到了普通 PowerShell，而不是 MCP stdin | 窗口 D | 先启动 MCP，确认提示符消失，再粘贴 JSON |

### 10.8 第 10 章结束时的正确状态

完整演示完成后，应满足：

- `initialize` 返回 `id:1` 和协议版本 `2025-11-25`。
- `notifications/initialized` 没有响应。
- `tools/list` 返回 `id:2` 和 25 个工具。
- `system.info` 调用成功且风险为 LOW。
- `service.restart` 首次调用只产生 Dry-run 和确认要求，不自动执行。
- 最后在窗口 D 按 `Ctrl+C`，MCP 退出并返回 PowerShell 提示符。

## 11. 功能九：真实 DeepSeek 调用

这一节只在网络稳定且允许消耗少量 API 额度时演示。正式主流程建议先完成前面的离线演示。

### 11.1 安全填写 API Key

如果本地文件不存在：

~~~powershell
Copy-Item config\llm.local.yaml.example config\llm.local.yaml
notepad config\llm.local.yaml
~~~

文件内容：

~~~yaml
llm_api_key: "你的 DeepSeek API Key"
~~~

安全要求：

- 不在录屏中打开这个文件。
- 不把 Key 发到聊天或截图。
- 不把 Key 写进 `config/llm.yaml`。
- `config/llm.local.yaml` 已被 Git 和提交包排除。

确认忽略状态：

~~~powershell
git check-ignore -v config\llm.local.yaml
~~~

正确现象示例：

~~~text
.gitignore:16:config/llm.local.yaml  config/llm.local.yaml
~~~

### 11.2 确认在线 Provider

命令：

~~~powershell
Remove-Item Env:SAFEOPS_LLM_DISABLED -ErrorAction SilentlyContinue
python -m safeops_agent.config_check
python -c "from safeops_agent.llm import get_provider; p=get_provider(); print(type(p).__name__); print(p.describe())"
~~~

正确输出关键内容：

~~~text
配置校验通过：检查 5 个文件，0 个错误，0 个警告
DeepSeekProvider
deepseek/deepseek-chat
~~~

`describe()` 后面还会显示超时和自动回退说明，文字可能略有差异。

### 11.3 发起一条真实 LOW 请求

命令：

~~~powershell
python -m safeops_agent.cli "请查看当前系统信息" --json
~~~

在线调用成功时，正确现象：

- `tool` 为 `system.info`。
- `risk` 为 `LOW`。
- 工具选择步骤的 `source` 为 `llm`。
- `llm_reasoning` 有一句简短选择说明。
- 最终 `ok=true`、`executed=true`。

本项目在 2026-07-16 的真实验证结果：

~~~text
Provider: DeepSeekProvider
Model: deepseek-chat
API latency: about 3.22 seconds
Selected tool: system.info
Selected risk: LOW
Tool result: success
~~~

延迟会随网络变化，不要求恰好 3.22 秒。

建议旁边红字说明：

~~~text
DeepSeek 只选择候选工具；本地注册表和 PolicyEngine 仍完成最终安全裁决。
~~~

### 11.4 网络失败时什么现象算正确

可能原因：

- 网络断开。
- API 超时。
- Key 无效。
- 模型返回不合法 JSON。
- 模型返回未知工具。

系统正确行为：

- 当前请求回退 RuleBasedProvider。
- 工具选择步骤 `source=rule`。
- `fallback_note` 记录回退原因。
- 如果本地规则能识别请求，核心功能继续执行。

这属于可靠性设计，不是绕过安全。若要确认纯离线状态，重新执行：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
~~~

## 12. 功能十：自动化测试与进程验收

### 12.1 一键运行 Python 测试和覆盖率

命令：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
~~~

正确输出尾部关键内容：

~~~text
Ran 217 tests

OK
TOTAL ... 72.3%
Wrote XML report to coverage.xml
~~~

实际耗时可能变化。关键成功标志：

- `Ran 217 tests`。
- `OK`。
- 综合覆盖率 `72.3%`。
- 高于 CI 门槛 `70.0%`。
- 生成 `coverage.xml`。
- ResourceWarning 严格模式下没有失败。

建议红框框选：

- `Ran 217 tests`。
- `OK`。
- `TOTAL ... 72.3%`。

建议旁边红字说明：

~~~text
217 项 Python 自动化覆盖 Agent、策略、工具、确认、并发、审计、Web、MCP 和安装资源。
~~~

### 12.2 运行前端测试

命令：

~~~powershell
npm run test:web
~~~

正确输出尾部：

~~~text
tests 7
pass 7
fail 0
~~~

正确现象：

- 7 项全部通过。
- 覆盖请求错误、202 确认流程、筛选、排序、会话 ID 和响应字段映射。

### 12.3 运行 CLI 全链路验收

命令：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
~~~

正确现象：

- 自动测试通过。
- 工具清单能加载。
- 三个 LOW 场景成功。
- MEDIUM 返回预演与确认要求。
- HIGH 被拒绝。
- 审计生成并通过验证。
- 脚本最终退出码为 0。

说明：

- acceptance 内部会主动断言 MEDIUM/HIGH 的 CLI 退出码为 1。
- 因此单个请求返回 1，不会被错误当成验收失败。

### 12.4 运行 Web 冒烟

命令：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
~~~

正确现象：

- 临时启动带强 Token 的 Web。
- health、tools、agent、audit 全部通过。
- 测试后自动关闭进程。
- 脚本退出码为 0。

### 12.5 检查依赖和配置

命令：

~~~powershell
python -m pip check
python -m safeops_agent.config_check
~~~

正确输出：

~~~text
No broken requirements found.
配置校验通过：检查 5 个文件，0 个错误，0 个警告
~~~

## 13. 功能十一：wheel 和比赛提交包

### 13.1 构建 wheel

命令：

~~~powershell
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
~~~

正确现象：

- 出现 `Successfully built safeops-agent`。
- `dist` 下生成类似：

~~~text
safeops_agent-0.1.0-py3-none-any.whl
~~~

说明：

- wheel 内置默认 YAML 和 Web 静态资源。
- 安装后可以脱离源码目录运行。
- 私密 `llm.local.yaml` 不进入 wheel。

### 13.2 生成比赛提交包

命令：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
~~~

当前正确输出：

~~~text
Submission package created: ...\dist\cnsoftbei-submission.zip
~~~

检查文件：

~~~powershell
Test-Path dist\cnsoftbei-submission.zip
~~~

正确输出：

~~~text
True
~~~

### 13.3 校验提交包

命令：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
~~~

当前正确输出：

~~~text
Package verified: ...\dist\cnsoftbei-submission.zip
Entries: 95
~~~

关键成功标志：

- `Package verified`。
- `Entries: 95`。
- 关键源码、配置、Web、测试、文档和脚本存在。
- `data/`、`llm.local.yaml`、`.env`、缓存、dist 和 Git 元数据不存在于 ZIP 内。

建议旁边红字说明：

~~~text
发布包通过自动禁止项检查，运行数据和本地 API Key 不会随作品提交。
~~~

## 14. 五分钟功能演示视频建议

### 14.1 时间分配

| 时间 | 画面 | 操作 | 旁边说明文字 |
| --- | --- | --- | --- |
| 0:00–0:25 | README/PPT | 展示项目定位 | `面向麒麟的安全智能运维 Agent` |
| 0:25–0:45 | PowerShell | 进入目录、配置检查 | `5 个配置文件，0 error 0 warning` |
| 0:45–1:15 | PowerShell | 查看工具清单或系统信息 | `25 个固定工具，无任意 Shell` |
| 1:15–1:50 | PowerShell | 资源查询和数据诊断 | `真实指标 + 明确阈值，不是固定模板` |
| 1:50–2:30 | PowerShell | 重启 nginx 预演 | `MEDIUM 只生成 dry-run 和一次性令牌` |
| 2:30–3:00 | PowerShell | 覆盖 /etc/passwd | `HIGH 在工具执行前直接拒绝` |
| 3:00–3:35 | PowerShell | 审计查询和 verify-audit | `SHA/HMAC/锚点审计完整性通过` |
| 3:35–4:15 | 浏览器 | Web 登录、LOW/MEDIUM/HIGH | `同一安全内核，按会话隔离` |
| 4:15–4:35 | PowerShell/PPT | MCP 25 工具 | `标准生命周期和严格 Schema` |
| 4:35–5:00 | PowerShell | 测试尾部和覆盖率 | `217+7 测试，72.3% 覆盖率` |

### 14.2 推荐录屏命令顺序

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
~~~

~~~powershell
python -m safeops_agent.config_check
~~~

~~~powershell
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli "诊断CPU和内存" --json
~~~

~~~powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
~~~

~~~powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
~~~

~~~powershell
python -m safeops_agent.cli --verify-audit
~~~

Web 演示：

~~~powershell
$env:SAFEOPS_TOKEN='答辩现场使用的32位以上随机字符串'
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

测试证据：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
npm run test:web
~~~

## 15. 运行后会生成哪些文件

| 路径 | 用途 | 是否提交 |
| --- | --- | --- |
| `data\audit.log` | 脱敏审计 JSONL | 否 |
| `data\audit.log.key` | 审计 HMAC 密钥 | 否 |
| `data\audit.log.anchor.json` | 审计数量和末尾哈希锚点 | 否 |
| `data\pending_actions.json` | 加密待确认动作 | 否 |
| `data\pending_actions.json.key` | 待确认动作密钥 | 否 |
| `data\managed\` | 受管文件工作区 | 否 |
| `data\snapshots\` | 受管文件快照 | 否 |
| `coverage.xml` | 覆盖率 XML | 通常作为 CI 产物 |
| `dist\safeops_agent-*.whl` | Python 安装包 | 发布产物 |
| `dist\cnsoftbei-submission.zip` | 比赛提交包 | 提交产物 |

检查主要产物：

~~~powershell
Test-Path data\audit.log
Test-Path data\audit.log.anchor.json
Test-Path coverage.xml
Test-Path dist\cnsoftbei-submission.zip
~~~

正确现象：

- 已经跑过对应功能的文件显示 `True`。
- 尚未跑测试或打包时，coverage/ZIP 显示 `False` 也正常。

## 16. 常见问题排查

### 16.1 找不到 safeops_agent

现象：

~~~text
ModuleNotFoundError: No module named 'safeops_agent'
~~~

修复：

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
$env:PYTHONPATH='src'
python -m pip install -e .
~~~

### 16.2 中文输出乱码

现象：

- 中文显示成 `é…ç½®` 一类字符。

修复：

~~~powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
~~~

然后重新执行原命令。

### 16.3 配置检查提示缺少 PyYAML

修复：

~~~powershell
python -m pip install -e .
python -m safeops_agent.config_check
~~~

不要自行恢复旧的简易 YAML 解析器。

### 16.4 Web 启动提示必须设置 SAFEOPS_TOKEN

现象：

~~~text
SAFEOPS_TOKEN is required
~~~

修复：

~~~powershell
$env:SAFEOPS_TOKEN='请替换为至少32位的随机字符串'
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

必须在同一个 PowerShell 窗口执行。

### 16.5 Web 端口 8765 被占用

检查：

~~~powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
~~~

处理：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
~~~

如果仍被其他程序占用，修改 `config/app.yaml` 的 `web_port`，然后重新运行配置检查。

### 16.6 Web 登录返回 401

原因：

- Token 输入错误。
- Token 属于另一个 PowerShell 会话。
- 服务重启后仍使用旧 Cookie。

处理：

1. 确认当前 Web 进程对应的 `SAFEOPS_TOKEN`。
2. 刷新页面重新登录。
3. 必要时清除该站点 Cookie。

### 16.7 MEDIUM 或 HIGH 命令退出码为 1

这是正确现象：

- MEDIUM：等待确认，没有执行完成。
- HIGH：安全拒绝，没有执行。

判断程序是否崩溃不能只看退出码，还要看 JSON 中的 `risk`、`requires_confirmation` 和 `decision_summary`。

### 16.8 action_id 无效

可能原因：

- 超过十分钟。
- 已经使用过。
- 从 Web/MCP 复制到另一个入口。
- action_id 复制不完整。
- 服务重启后运行态数据不一致。

处理：

~~~text
重新发起原 MEDIUM 请求，获取新的 action_id。
~~~

不要尝试手工修改 `pending_actions.json`。

### 16.9 DeepSeek 没有被使用

检查：

~~~powershell
Remove-Item Env:SAFEOPS_LLM_DISABLED -ErrorAction SilentlyContinue
python -c "from safeops_agent.llm import get_provider; print(type(get_provider()).__name__)"
~~~

正确在线输出应为：

~~~text
DeepSeekProvider
~~~

如果仍是 RuleBasedProvider，检查本地 Key 和文件路径。

### 16.10 DeepSeek 超时或返回错误

正确理解：

- 核心请求会自动回退规则。
- 本地策略和工具不受影响。
- 回退原因会进入决策轨迹。

处理：

1. 检查网络。
2. 检查 Key。
3. 检查 `config/llm.yaml` 的 model/base_url。
4. 正式演示切回 `SAFEOPS_LLM_DISABLED=1`。

### 16.11 审计校验失败

现象：

~~~json
{"ok": false, "first_bad_line": 123, "reason": "..."}
~~~

处理：

- 立即备份整个 `data/`。
- 不要删除日志、key 或 anchor。
- 根据 `first_bad_line` 和 `reason` 检查是否发生截断、修改或文件不匹配。

### 16.12 MCP 调用提示生命周期未完成

原因：

- 客户端没有发送 `notifications/initialized`。

正确顺序：

~~~text
initialize -> notifications/initialized -> tools/list/tools/call
~~~

### 16.13 Node 命令不存在

影响：

- 只影响 7 项前端测试。
- Python Agent、CLI、Web 服务端和 MCP 仍可运行。

处理：

- 安装 Node.js LTS。
- 重新打开 PowerShell。
- 执行 `node --version` 和 `npm run test:web`。

### 16.14 unittest 中看到预期拒绝

测试会故意构造：

- HIGH 危险意图。
- MEDIUM 等待确认。
- 审计篡改。
- Web 401/429。
- MCP Schema 错误。

这些中间输出不是失败。真正成功标志是最后：

~~~text
Ran 217 tests
OK
~~~

## 17. 安全和提交边界

以下内容不能提交：

| 路径 | 原因 |
| --- | --- |
| `config/llm.local.yaml` | 包含本地 API Key |
| `.env` | 可能包含密钥 |
| `data/` | 审计、密钥、锚点、待确认动作和受管文件 |
| `dist/` | 本地构建产物，提交包由脚本单独交付 |
| `__pycache__/`、`*.pyc` | Python 缓存 |
| `.coverage` | 本地覆盖率数据库 |

检查工作区：

~~~powershell
git status --short --ignored
~~~

正确现象：

- `config/llm.local.yaml` 前面可能显示 `!!`，表示已忽略。
- `data/`、`dist/`、缓存可能显示 `!!`。
- 不应该看到本地 Key 文件以 `M`、`A` 或 `??` 出现在普通待提交区。

确认密钥文件被忽略：

~~~powershell
git check-ignore -v config\llm.local.yaml
~~~

建议旁边红字说明：

~~~text
API Key、审计密钥和运行数据全部保持 ignored，发布包还会再次执行禁止项检查。
~~~

## 18. 最终成功判定清单

正式答辩或录屏前，逐项确认：

| 检查项 | 成功标准 |
| --- | --- |
| 项目目录 | `Get-Location` 指向 `C:\Users\CanhuiBao\Desktop\中国软件杯` |
| Python | 3.10 或更高 |
| 依赖 | `pip check` 显示无损坏依赖 |
| 配置 | 检查 5 个文件，0 错误、0 警告 |
| 离线模式 | Provider 为 RuleBasedProvider |
| 工具清单 | 25 个固定工具，包含 safeops.confirm |
| LOW | `ok=true`、`risk=LOW`、`executed=true` |
| 诊断 | 有 evidence、thresholds、causes 和 actions |
| MEDIUM | `requires_confirmation=true`、有 dry-run/action_id、未执行 |
| HIGH | `risk=HIGH`、`tool=null`、没有执行阶段 |
| 审计 | `ok=true`、`first_bad_line=null` |
| Web | 登录后 LOW/MEDIUM/HIGH 三种页面状态正确 |
| MCP | 完成 2025-11-25 生命周期并返回 25 个工具 |
| DeepSeek | Provider 为 DeepSeekProvider，LOW 请求 `source=llm` |
| Python 测试 | Ran 217 tests、OK |
| 前端测试 | tests 7、pass 7、fail 0 |
| 覆盖率 | 72.3%，高于 70% 门槛 |
| wheel | 构建成功且包含内置配置/Web 资源 |
| 提交包 | Package verified、Entries: 95 |
| 密钥边界 | llm.local.yaml 和 data/ 未进入 Git/ZIP |

全部满足后，可以说明：

~~~text
SafeOps Agent 已完成从自然语言输入、固定工具选择、本地三级风险裁决、一次性确认、LOW 执行/HIGH 拒绝、数据驱动诊断、签名审计、Web/MCP 接入、真实 DeepSeek 到自动化测试与发布包校验的完整软件级闭环。
~~~

最后提醒：

- 当前软件级验收在 Windows 完成，真实 DeepSeek 已验证。
- 麒麟/Linux 是服务管理和完整系统采集的目标环境。
- 尚未完成的麒麟硬件实机报告必须如实说明，不能写成已经通过。
