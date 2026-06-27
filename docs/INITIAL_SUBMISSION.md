# 初赛提交说明

## 1. 项目名称

面向麒麟操作系统的安全智能运维 Agent。

## 2. 赛题对应

中国软件杯赛题 1 A 组：面向麒麟操作系统的安全智能运维 Agent 设计与实现。

本项目围绕赛题中的自然语言运维、操作系统工具调用、安全控制、审计追踪和 MCP 风格工具接口进行实现。当前版本定位为可演示、可测试、可继续扩展的初赛 MVP。

## 3. 仓库信息

- GitHub 仓库：`https://github.com/chanehwibo/cnsoftbei`
- 默认分支：`main`
- 当前形态：本地规则驱动 MVP + MCP 风格工具接口 + Web 运维工作台

## 4. 一句话介绍

本项目把系统运维能力封装成受控工具，让用户通过自然语言查询系统信息、排查资源和网络问题，并在意图过滤、工具白名单、参数校验、风险分级、人工确认和审计日志的约束下执行运维动作。

## 5. 已完成能力

- CLI 自然语言入口：支持通过 `python -m safeops_agent.cli` 发起运维请求。
- Web 运维工作台：支持浏览器输入请求、查看工具清单、查看审计日志。
- MCP 风格工具接口：提供工具列表、工具 schema、风险标注和统一调用结果。
- 系统状态感知：支持系统信息、CPU/内存、进程、磁盘分区、网络连接、监听端口等查询。
- 日志与服务查询：支持最近错误日志、服务状态查询和中风险服务重启审批闭环。
- 安全策略：支持高风险意图拦截、敏感路径保护、命令注入字符拦截、工具风险分级。
- 审计日志：以 JSONL 格式记录请求来源、工具、参数、风险等级、决策、耗时和错误码。
- 自动化测试：覆盖 Agent、Policy、MCP Service、Audit、Registry 等核心模块。
- 操作文档：提供新手手册、演示脚本、部署说明、测试报告、安全护栏说明和脚本说明。

## 6. 初赛演示方式

进入项目目录：

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
$env:PYTHONPATH='src'
```

CLI 演示：

```powershell
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli "查看CPU和内存" --json
python -m safeops_agent.cli "查看监听端口" --json
python -m safeops_agent.cli "重启 nginx 服务" --json
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

Web 演示：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

浏览器访问：

```text
http://127.0.0.1:8765
```

自动验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
```

## 7. 初赛提交材料清单

- 源码：`src/safeops_agent`
- 单元测试：`tests`
- 配置文件：`config`
- Web 页面：`web`
- 演示数据：`demo`
- 开发脚本：`scripts`
- 项目入口说明：`README.md`
- 系统设计文档：`docs/SYSTEM_DESIGN.md`
- 安全护栏文档：`docs/SAFETY_GUARDRAILS.md`
- 测试计划与报告：`docs/TEST_PLAN_AND_REPORT.md`
- 部署说明：`docs/DEPLOYMENT.md`
- 新手全流程操作手册：`docs/BEGINNER_OPERATION_MANUAL.md`
- 答辩演示脚本：`docs/DEMO_SCRIPT.md`
- 初赛提交说明：`docs/INITIAL_SUBMISSION.md`
- 赛题完成度矩阵：`docs/COMPLETION_MATRIX.md`
- 麒麟实机验证清单：`docs/KYLIN_VALIDATION_CHECKLIST.md`

## 8. 当前限制

- 当前没有调用外部大模型 API，意图识别采用本地规则驱动，便于初赛阶段稳定演示。
- MCP 层为风格化实现，提供工具清单、schema 和调用 facade，后续可替换为官方 MCP SDK。
- 当前主要在 Windows 开发环境验证，麒麟系统适配需要在真实麒麟环境中执行验证清单。
- `service.restart` 当前只完成中风险审批闭环，不直接重启真实服务，避免误操作。
- 生产级 Web 鉴权、权限隔离和最小权限执行器仍属于后续增强项。

## 9. 初赛答辩重点

- 说明项目不是简单调用 shell，而是用工具白名单和策略引擎限制操作边界。
- 演示低风险查询自动执行、中风险操作要求确认、高风险意图直接拒绝。
- 展示 MCP 风格工具清单和统一调用结果，说明后续接入标准 MCP SDK 的路径清晰。
- 展示审计日志，证明每次决策和调用都有可追溯记录。
- 明确说明麒麟实机验证项和当前尚未完成的生产级能力，避免夸大完成度。

## 10. 后续计划

- 在真实麒麟系统上执行完整验证清单并补充实测记录。
- 接入真实大模型 API 或本地大模型，提高自然语言理解能力。
- 替换或兼容官方 MCP SDK，增强标准协议一致性。
- 增加最小权限 executor、sudo 白名单和生产级 Web 鉴权。
- 丰富运维工具集，逐步覆盖更多日志、安全基线、服务治理和故障排查场景。
