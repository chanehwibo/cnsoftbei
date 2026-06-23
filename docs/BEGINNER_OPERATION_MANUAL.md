# 新手全流程操作手册

本手册面向第一次接触项目的同学，目标是做到照着复制命令就能完成完整演示和测试。

## 0. 你要演示什么

本项目演示的是一个“面向麒麟操作系统的安全智能运维 Agent”。

你需要展示 5 件事：

- 用户可以用自然语言提出运维请求。
- Agent 会把请求匹配到固定运维工具。
- 低风险查询可以直接执行。
- 中风险操作需要确认。
- 高风险操作会被拒绝，并写入审计日志。

当前版本不需要外部 API，不需要大模型密钥，不需要联网。

## 1. 准备工作

### 1.1 打开 PowerShell

在 Windows 桌面按下面步骤操作：

1. 按 `Win` 键。
2. 输入 `PowerShell`。
3. 点击打开 `Windows PowerShell`。

### 1.2 进入项目目录

复制下面命令，粘贴到 PowerShell，按回车：

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
```

确认当前目录正确：

```powershell
pwd
```

你应该看到类似：

```text
Path
----
C:\Users\CanhuiBao\Desktop\中国软件杯
```

### 1.3 检查 Python

复制执行：

```powershell
python --version
```

如果看到类似下面内容，说明 Python 可用：

```text
Python 3.14.3
```

如果提示找不到 `python`，需要先安装 Python 3.10 或更高版本。

### 1.4 设置项目路径

每次新打开 PowerShell，都先执行：

```powershell
$env:PYTHONPATH='src'
```

这一步的作用是告诉 Python 去 `src` 目录里找项目代码。

## 2. 一键健康检查

执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

成功时会看到：

```text
Ran 15 tests
OK
```

如果这一步通过，说明项目基础功能正常。

## 3. CLI 命令行演示

下面每条命令都可以直接复制执行。

### 3.1 演示一：查看系统信息

执行：

```powershell
python -m safeops_agent.cli "查看系统信息" --json
```

你需要关注输出里的字段：

```json
{
  "ok": true,
  "tool": "system.info",
  "risk": "LOW"
}
```

讲解词：

```text
用户用自然语言请求系统信息，Agent 自动匹配 system.info 工具。该工具是只读查询，所以风险等级是 LOW，可以自动执行。
```

### 3.2 演示二：查看 CPU 和内存

执行：

```powershell
python -m safeops_agent.cli "查看CPU和内存" --json
```

关注：

```json
{
  "tool": "system.resources",
  "risk": "LOW"
}
```

讲解词：

```text
Agent 可以把自然语言映射到资源指标工具，采集 CPU、内存和磁盘信息。
```

### 3.3 演示三：查看监听端口

执行：

```powershell
python -m safeops_agent.cli "查看监听端口" --json
```

关注：

```json
{
  "tool": "network.listening_ports",
  "risk": "LOW"
}
```

讲解词：

```text
网络排障常见任务是查看端口监听。这里不是让模型自由拼命令，而是调用固定的 network.listening_ports 工具。
```

### 3.4 演示四：查看服务状态

执行：

```powershell
python -m safeops_agent.cli "查看 nginx 服务状态" --json
```

Windows 开发环境下你会看到类似说明：

```text
当前为 Windows 开发环境，服务状态工具将在麒麟/Linux 环境使用 systemctl
```

讲解词：

```text
服务状态查询是只读操作。当前在 Windows 上演示接口链路，到麒麟系统后会通过 systemctl 查询真实服务状态。
```

### 3.5 演示五：中风险操作需要确认

执行：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
```

预期输出：

```json
{
  "ok": false,
  "tool": "service.restart",
  "risk": "MEDIUM",
  "requires_confirmation": true
}
```

讲解词：

```text
重启服务会改变系统状态，所以被定义为中风险。未确认时，Agent 不执行操作，只返回确认要求。
```

再执行确认版本：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --yes --json
```

当前 MVP 仍不会真实重启服务，会返回执行禁用说明。

讲解词：

```text
MVP 阶段完成了审批闭环，但真实变更暂时禁用。后续接入最小权限 executor 后，再开启真实重启。
```

### 3.6 演示六：高风险操作被拒绝

执行：

```powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

预期输出：

```json
{
  "ok": false,
  "risk": "HIGH"
}
```

你还会看到类似：

```text
已拒绝执行：高风险操作涉及敏感路径：/etc
```

讲解词：

```text
这一步展示安全护栏。请求涉及 /etc/passwd 这种敏感路径，所以在意图层直接拒绝，不会进入工具调用。
```

再演示一个高风险关键词：

```powershell
python -m safeops_agent.cli "删除根目录所有文件" --json
```

讲解词：

```text
删除根目录属于高风险破坏性意图，也会被本地策略拒绝。
```

## 4. 一键 CLI 全流程演示

如果你不想一条条输入，可以执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

这个脚本会自动执行：

- 查看系统信息。
- 查看 CPU 和内存。
- 查看监听端口。
- 查看 nginx 服务状态。
- 尝试重启 nginx 服务。
- 尝试覆盖 `/etc/passwd`。
- 查询 nginx 软件包。
- 输出最近审计日志。

看到高风险命令返回非零状态是正常的，因为系统拒绝了危险请求。

## 5. Web 工作台演示

### 5.1 启动 Web 工作台

执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

看到类似下面内容说明启动成功：

```text
SafeOps Web running at http://127.0.0.1:8765
```

这个 PowerShell 窗口不要关闭。

### 5.2 打开浏览器

打开 Chrome、Edge 或其他浏览器，地址栏输入：

```text
http://127.0.0.1:8765
```

### 5.3 Web 页面要展示什么

页面分为三块：

- 左侧：常用任务按钮。
- 中间：自然语言输入和 Agent 响应。
- 右侧：工具清单和审计日志。

### 5.4 Web 演示步骤

按顺序点击或输入：

1. 点击左侧 `系统信息`，再点击 `执行`。
2. 点击左侧 `资源指标`，再点击 `执行`。
3. 点击左侧 `监听端口`，再点击 `执行`。
4. 点击左侧 `重启服务`，再点击 `执行`。
5. 观察页面显示需要确认。
6. 勾选 `确认中风险操作`。
7. 再执行一次 `重启 nginx 服务`。
8. 点击左侧 `高风险拦截`，再点击 `执行`。
9. 观察高风险请求被拒绝。
10. 点击右上角 `刷新审计`，查看审计记录。

讲解词：

```text
Web 工作台把 CLI 能力可视化。评委可以看到请求、风险等级、工具调用结果和审计日志。
```

### 5.5 关闭 Web 工作台

如果 Web 是用 `scripts\web.ps1` 启动的，回到启动 Web 的 PowerShell 窗口，按：

```text
Ctrl + C
```

如果你不确定是否还有后台 Web 进程，可以执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
```

## 6. 查看审计日志

执行：

```powershell
Get-Content .\data\audit.log -Encoding utf8 -Tail 10
```

你会看到每条日志是一行 JSON。

重点字段：

- `event_id`：审计事件 ID
- `source`：来源，可能是 `cli` 或 `web`
- `request`：用户请求
- `tool`：调用工具
- `risk`：风险等级
- `allowed`：是否允许
- `reason`：允许或拒绝原因
- `error_code`：稳定错误码
- `duration_ms`：耗时

讲解词：

```text
审计日志让每次操作都可追踪，可以复盘用户请求、工具调用、风险判断和执行结果。
```

## 7. 查看 MCP 工具清单

执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\show-tools.ps1
```

关注每个工具的：

- `name`
- `description`
- `category`
- `risk`
- `inputSchema`
- `annotations`

讲解词：

```text
这些就是暴露给大模型的工具能力。大模型只能调用工具清单里的受控工具，不能直接执行任意 shell 命令。
```

## 8. 完整答辩推荐顺序

正式演示建议按这个顺序：

1. 打开项目目录。
2. 运行 `scripts\test.ps1`，证明测试通过。
3. 运行 `查看系统信息`，展示低风险系统感知。
4. 运行 `查看CPU和内存`，展示资源指标。
5. 运行 `查看监听端口`，展示网络排障能力。
6. 运行 `重启 nginx 服务`，展示中风险确认。
7. 运行 `覆盖 /etc/passwd`，展示高风险拦截。
8. 打开 Web 工作台，重复一次低风险、中风险、高风险演示。
9. 查看审计日志。
10. 查看 MCP 工具清单。

## 9. 常见问题

### 9.1 提示找不到模块 `safeops_agent`

原因：没有设置 `PYTHONPATH`。

解决：

```powershell
$env:PYTHONPATH='src'
```

### 9.2 PowerShell 不允许运行脚本

使用下面格式运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

### 9.3 中文乱码

执行：

```powershell
chcp 65001
```

然后重新运行命令。

### 9.4 Web 页面打不开

先确认 Web 是否启动：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health'
```

如果失败，重新启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

### 9.5 端口 8765 被占用

先停止已有 Web 服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
```

再启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

### 9.6 高风险命令返回失败是不是 Bug

不是。高风险命令被拒绝是预期行为。

例如：

```powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

返回失败说明安全护栏生效。

### 9.7 Windows 上服务状态为什么不是真实 nginx

当前开发机是 Windows。服务状态工具在 Windows 上会返回说明，在麒麟/Linux 环境中会使用：

```bash
systemctl status nginx --no-pager
```

## 10. 演示结束后检查

执行测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

查看 Git 状态：

```powershell
git status --short
```

如果没有输出，说明工作区干净。

## 11. 一句话讲清楚项目

```text
本项目把操作系统运维能力封装成 MCP 风格安全工具，让用户通过自然语言完成系统查询和受控操作；系统通过意图过滤、工具白名单、参数校验、风险分级、确认机制和审计日志，防止大模型误操作。
```
