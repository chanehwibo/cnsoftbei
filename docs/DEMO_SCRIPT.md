# 答辩演示脚本

## 1. 演示目标

用 6 到 8 分钟展示系统的核心价值：

- 自然语言运维。
- MCP 风格工具发现和调用。
- 低风险只读工具自动执行。
- 中风险操作需要确认。
- 高风险操作被拒绝。
- 审计日志可追踪。

## 2. 演示准备

进入项目目录：

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
$env:PYTHONPATH='src'
```

先跑测试：

```powershell
python -m unittest discover -s tests
```

预期：

```text
Ran 15 tests
OK
```

## 3. 演示场景一：系统状态感知

讲解词：

```text
首先展示 Agent 对操作系统的基础感知能力。用户不需要记命令，只需要用自然语言请求系统信息。
```

命令：

```powershell
python -m safeops_agent.cli "查看系统信息" --json
```

预期现象：

- 返回系统名称、版本、架构、主机名、Python 版本。
- 工具为 `system.info`。
- 风险等级为 `LOW`。

## 4. 演示场景二：资源指标采集

讲解词：

```text
Agent 将自然语言请求映射到固定只读工具，采集 CPU、内存和磁盘指标。
```

命令：

```powershell
python -m safeops_agent.cli "查看CPU和内存" --json
```

预期现象：

- 工具为 `system.resources`。
- 返回 CPU 数量、内存或环境说明、磁盘使用率。

## 5. 演示场景三：网络与端口排查

讲解词：

```text
运维排障中常见问题是确认端口监听和连接状态。系统提供固定网络工具，不允许模型自由拼接命令。
```

命令：

```powershell
python -m safeops_agent.cli "查看监听端口" --json
```

预期现象：

- 工具为 `network.listening_ports`。
- 返回监听端口列表。
- 风险等级为 `LOW`。

## 6. 演示场景四：服务状态查询

讲解词：

```text
服务查询是只读操作，可以自动执行。到麒麟环境后会使用 systemctl 获取服务状态。
```

命令：

```powershell
python -m safeops_agent.cli "查看 nginx 服务状态" --json
```

预期现象：

- 工具为 `service.status`。
- Windows 开发环境返回麒麟/Linux 适配说明。
- 麒麟环境返回 systemctl status 输出。

## 7. 演示场景五：中风险操作确认

讲解词：

```text
重启服务会改变系统状态，因此被定义为中风险操作。未确认时，Agent 只给出风险提示，不执行。
```

命令：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
```

预期现象：

- 工具为 `service.restart`。
- 风险等级为 `MEDIUM`。
- `requires_confirmation=true`。
- 返回“中风险工具需要用户确认”。

确认命令：

```powershell
python -m safeops_agent.cli "重启 nginx 服务" --yes --json
```

预期现象：

- MVP 阶段仍不执行真实重启。
- 返回“审批闭环已完成但真实变更禁用”的说明。

## 8. 演示场景六：高风险操作拦截

讲解词：

```text
高风险请求不会进入工具调用阶段。这里演示敏感路径写入被本地安全策略拦截。
```

命令：

```powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

预期现象：

- 请求被拒绝。
- 风险等级为 `HIGH`。
- 错误码为 `INTENT_SENSITIVE_PATH`。

另一个高风险示例：

```powershell
python -m safeops_agent.cli "删除根目录所有文件" --json
```

预期现象：

- 命中高风险关键词。
- 不调用任何工具。

## 9. 演示场景七：MCP 工具清单

讲解词：

```text
系统将运维能力注册成 MCP 风格工具，每个工具都有 Schema、风险等级和行为标注。
```

可用 Python 片段：

```powershell
python -c "import sys,json; sys.path.insert(0,'src'); from safeops_agent.mcp_server import McpToolService; print(json.dumps(McpToolService().list_tools(), ensure_ascii=False, indent=2))"
```

预期现象：

- 展示工具名、分类、风险等级、inputSchema、annotations。

## 10. 演示场景八：审计日志追踪

讲解词：

```text
所有请求都会写入结构化审计日志，便于复盘谁请求了什么、系统为什么允许或拒绝。
```

命令：

```powershell
Get-Content .\data\audit.log -Encoding utf8 -Tail 5
```

预期现象：

- 每条日志包含 `event_id`、`request`、`tool`、`risk`、`allowed`、`reason`、`error_code`、`duration_ms`。

## 11. 收尾讲解

```text
本系统的重点不是让大模型直接控制操作系统，而是把大模型限制在 MCP 工具和本地安全策略之间。模型负责理解和规划，本地系统负责授权、执行和审计。
```

## 12. 兜底方案

如果现场没有麒麟环境：

- 使用 Windows 开发环境演示 Agent、安全策略、MCP 工具清单和审计日志。
- 说明 systemctl、journalctl、rpm/dpkg 工具已做麒麟/Linux 适配入口，需在真实麒麟环境补测。

如果终端编码异常：

```powershell
chcp 65001
```

如果 `PYTHONPATH` 丢失：

```powershell
$env:PYTHONPATH='src'
```
