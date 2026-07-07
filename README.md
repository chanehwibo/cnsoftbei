# 面向麒麟操作系统的安全智能运维 Agent

本项目用于中国软件杯赛题 1 A 组：面向麒麟操作系统的安全智能运维 Agent 设计与实现。

核心能力：

- 自然语言输入（DeepSeek 大模型意图理解，离线自动回退规则匹配）
- 意图风险过滤（输入与模型输出双向护栏）
- 安全策略判断（低风险直执行 / 中风险确认令牌 / 高风险拒绝）
- 最小权限工具调用（19+ 白名单工具，禁任意 shell）
- 五步思维链审计 + 哈希链防篡改审计日志
- 标准 MCP 协议 stdio 服务端（JSON-RPC 2.0）
- 一次性确认令牌：预演与执行严格一致，限时、绑定会话
- 受管工作区文件变更：写前快照、真实回滚

## 运行方式

如果你是第一次运行，优先阅读：

- [新手全流程操作手册](docs/BEGINNER_OPERATION_MANUAL.md)
- [初赛提交说明](docs/INITIAL_SUBMISSION.md)
- [赛题要求完成度矩阵](docs/COMPLETION_MATRIX.md)
- [麒麟系统实机验证清单](docs/KYLIN_VALIDATION_CHECKLIST.md)
- [后续完善 TODO List](docs/TODO_LIST.md)
- [功能完善与亮点优化总表](docs/FEATURE_HIGHLIGHTS_PLAN.md)
- [答辩演示脚本](docs/DEMO_SCRIPT.md)
- [开发脚本说明](docs/SCRIPTS.md)

在项目目录执行：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.cli "查看系统信息"
python -m safeops_agent.cli "查看CPU和内存"
python -m safeops_agent.cli "分析最近系统错误日志"
python -m safeops_agent.cli "删除根目录所有文件"      # 高风险，直接拒绝
python -m safeops_agent.cli "重启 nginx 服务"         # 中风险，返回 dry-run 计划 + 确认令牌
python -m safeops_agent.cli --confirm <令牌>          # 凭令牌精确执行已预演的动作
python -m safeops_agent.cli --verify-audit            # 校验审计日志哈希链完整性
```

启用大模型意图理解：复制 `config/llm.local.yaml.example` 为 `config/llm.local.yaml` 并填入 API Key（详见 [docs/LLM_INTEGRATION.md](docs/LLM_INTEGRATION.md)）。设置环境变量 `SAFEOPS_LLM_DISABLED=1` 可强制离线规则模式。

启动标准 MCP stdio 服务端（供 MCP 客户端接入）：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.mcp_stdio
```

运行测试：

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
```


一键验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
```

生成提交包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
```

生成自动验收报告：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\report.ps1
```

运行 Web 冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
```

校验提交包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
```
审计日志默认写入：

```text
data/audit.log
```

## 当前限制

- 大模型意图理解已接入（DeepSeek，OpenAI 兼容接口），无 Key/无网络时自动回退本地规则，功能不中断。
- MCP 已实现标准 JSON-RPC 2.0 stdio 协议服务端（initialize/tools/list/tools/call/ping），如需官方 SDK 形态可平滑替换传输层。
- 服务生命周期操作（start/stop/restart）在麒麟/Linux 环境真实执行 systemctl；Windows 开发环境返回预告文本。真实麒麟实机验证仍待执行（见 docs/KYLIN_VALIDATION_CHECKLIST.md）。
- 最小权限执行器（专用低权用户 + sudo 白名单）已有设计，需在麒麟实机落地。
- 高风险操作默认拒绝；中风险操作需凭一次性确认令牌（或 --yes）确认后才执行。
