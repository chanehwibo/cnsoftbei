# 面向麒麟操作系统的安全智能运维 Agent

本项目用于中国软件杯赛题 1 A 组：面向麒麟操作系统的安全智能运维 Agent 设计与实现。

当前阶段目标是先完成 MVP 闭环：

- 自然语言输入
- 意图识别
- 安全策略判断
- 最小权限工具调用
- 审计日志记录
- MCP 风格工具接口

## 运行方式

如果你是第一次运行，优先阅读：

- [新手全流程操作手册](docs/BEGINNER_OPERATION_MANUAL.md)
- [初赛提交说明](docs/INITIAL_SUBMISSION.md)
- [赛题要求完成度矩阵](docs/COMPLETION_MATRIX.md)
- [麒麟系统实机验证清单](docs/KYLIN_VALIDATION_CHECKLIST.md)
- [答辩演示脚本](docs/DEMO_SCRIPT.md)
- [开发脚本说明](docs/SCRIPTS.md)

在项目目录执行：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.cli "查看系统信息"
python -m safeops_agent.cli "查看CPU和内存"
python -m safeops_agent.cli "分析最近系统错误日志"
python -m safeops_agent.cli "删除根目录所有文件"
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
审计日志默认写入：

```text
data/audit.log
```

## 当前限制

- 目前是本地规则驱动的 MVP，还未接入真实大模型。
- MCP 层先提供工具清单和工具调用抽象，后续可替换为官方 MCP SDK。
- 高风险操作默认拒绝，中风险操作需要显式确认后才允许执行。
