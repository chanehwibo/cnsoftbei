# 后续完善 TODO List

## 1. 状态说明

- `已完成`：代码、文档或脚本已经落地，并已有自动化测试或手工验证支撑。
- `已实现待验证`：实现已经落地，等待本轮完整验收脚本确认。
- `部分完成`：核心能力已有，但仍可继续扩展展示或工程细节。
- `待做`：尚未开始或仅有规划。

## 2. P0：初赛可信度补强

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P0-01 | 麒麟实机验证报告 | `docs/KYLIN_VALIDATION_REPORT.md` | 记录麒麟版本、Python 版本、测试结果、CLI/Web 演示结果、截图清单 | 待做 |
| P0-02 | 自动验收报告生成 | `scripts/report.ps1`、`dist/acceptance-report.md` | 一键运行验收、工具清单和审计摘要，并生成 Markdown 报告 | 已完成 |
| P0-03 | 初赛答辩材料清单 | `docs/DEFENSE_CHECKLIST.md` | 明确答辩前要打开的页面、命令、截图、讲解顺序和兜底方案 | 待做 |
| P0-04 | Web 演示冒烟测试 | `scripts/web-smoke.ps1` | 自动启动 Web，请求 `/api/health`、`/api/tools`、`/api/agent`、`/api/audit` 后停止服务 | 已完成 |
| P0-05 | 项目提交包校验 | `scripts/verify-package.ps1` | 校验 zip 包包含源码、测试、配置、Web、脚本和关键文档，不包含 `.git` 与运行日志 | 已完成 |

## 3. P1：智能运维亮点

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P1-01 | 故障诊断模块 | `src/safeops_agent/tools/diagnostics.py` | 支持系统概览、CPU/内存/磁盘资源、磁盘、端口、服务、日志诊断场景 | 已完成 |
| P1-02 | 诊断报告输出 | CLI/Web 诊断结果 | 输出现象、可能原因、建议动作、风险等级、是否需要确认和证据数据 | 已完成 |
| P1-03 | 中风险 Dry-run 执行预案 | `service.restart` 预案结果 | 未确认时返回目标服务、预检查、拟操作、回滚建议和风险控制，不执行真实变更 | 已完成 |
| P1-04 | 风险评分机制 | `risk_score` 字段 | 每次请求输出 0-100 风险分数，并写入审计日志 | 已完成 |
| P1-05 | Agent 决策摘要 | `decision_summary` 字段 | 说明为什么选择工具、为什么允许、拒绝或要求确认 | 已完成 |

## 4. P1：Web 工作台增强

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P1-06 | 风险等级与风险评分展示 | Web 状态卡片和消息结果 | LOW/MEDIUM/HIGH、0-100 分和确认状态可视化展示 | 已完成 |
| P1-07 | 审计记录增强展示 | Web 审计区 | 展示最近请求、工具、风险、风险评分、原因和决策摘要 | 已完成 |
| P1-08 | 工具分类展示 | Web 工具区 | 按分类排序展示 system/network/service/diagnostics 等工具 | 部分完成 |
| P1-09 | 一键演示请求 | Web 常用任务区 | 常用任务按钮覆盖低风险查询、诊断、中风险确认和高风险拦截 | 已完成 |
| P1-10 | 诊断报告面板 | Web 消息区 | 最近一次诊断展示结构化报告和建议动作 | 已完成 |

## 5. P2：协议与模型扩展

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P2-01 | LLM Provider 抽象 | `safeops_agent.llm` | 支持 `RuleBasedProvider` 默认实现，并预留 OpenAI/本地模型实现 | 已完成（DeepSeekProvider + 规则回退 + `SAFEOPS_LLM_DISABLED` 离线开关） |
| P2-02 | 大模型接入说明 | `docs/LLM_INTEGRATION.md` | 说明 API Key 配置、离线模式、安全边界和失败降级 | 已完成 |
| P2-03 | 标准 MCP SDK 迁移计划 | `docs/MCP_SDK_MIGRATION.md` | 明确现有工具注册、schema、调用结果如何迁移到官方 MCP SDK | 已完成（以更强形态落地：`mcp_stdio.py` 直接实现标准 JSON-RPC 2.0 stdio 协议，含版本协商） |
| P2-04 | MCP 兼容测试 | `tests/test_mcp_contract.py` | 测试工具 schema、错误码、风险标注和参数校验契约 | 已完成（`tests/test_mcp_stdio.py` + `tests/test_mcp_service.py`） |
| P2-05 | 配置校验 | `scripts/validate-config.ps1` | 校验 `config/*.yaml` 必要字段、工具禁用项和策略项格式 | 已完成（`safeops_agent.config_check` 模块 + 一键脚本，error/warning 分级，11 例测试） |

## 6. P2：安全与工程完善

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P2-06 | 最小权限执行器设计落地 | `docs/EXECUTOR_DESIGN.md`、原型代码 | 明确普通用户进程、受限 executor、sudo 白名单和审计边界 | 部分完成（受管工作区 + 确认令牌 + 真实 systemctl 已落地；sudo 白名单需麒麟实机） |
| P2-07 | 审计日志查询增强 | CLI/Web 审计筛选 | 支持按来源、风险等级、工具名筛选最近审计事件 | 已完成（`AuditLogger.query` + CLI `--show-audit` + `/api/audit` 查询参数 + Web 筛选控件） |
| P2-08 | 错误码字典 | `docs/ERROR_CODES.md` | 汇总策略、工具、MCP、Web 相关错误码和处理建议 | 已完成 |
| P2-09 | 测试覆盖报告 | `docs/COVERAGE_NOTES.md` | 记录当前测试覆盖模块、缺口和后续测试计划 | 已完成（158 例覆盖矩阵 + 缺口清单） |
| P2-10 | Windows/麒麟差异说明增强 | 更新部署和测试文档 | 明确哪些结果在 Windows 为兼容输出，哪些必须在麒麟验证 | 部分完成 |

## 7. P3：展示与材料优化

| 编号 | 任务 | 目标产物 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| P3-01 | 答辩 PPT 大纲 | `docs/PPT_OUTLINE.md` | 包含背景、痛点、架构、演示、安全、测试、计划 | 待做 |
| P3-02 | 截图清单补齐 | 更新 `docs/DEMO_ASSETS.md` | 每张截图对应演示步骤、文件名和讲解点 | 待做 |
| P3-03 | 演示数据刷新脚本 | `scripts/refresh-demo-data.ps1` | 自动生成最新审计样例和演示请求结果 | 待做 |
| P3-04 | README 项目结构图 | 更新 `README.md` | 用简洁目录说明源码、配置、脚本、文档、Web 的作用 | 待做 |
| P3-05 | 常见问题增强 | 更新新手手册 | 补充 Python 版本、PowerShell 编码、端口占用、权限不足、麒麟命令缺失等问题 | 部分完成 |

## 8. 下一轮推荐顺序

1. 完成真实麒麟系统验证报告（唯一无法在开发机完成的硬缺口）。
2. 生成初赛答辩材料清单（PPT 已有实体文件 `SafeOps_答辩演示PPT.pptx`）。
3. 继续增强 Web 诊断历史和截图导出，补齐截图清单与 README 结构图。

## 9. 本轮已落地的增强（2026-07）

- LLM 意图理解（DeepSeek）+ 输出侧护栏 + 失败回退可见性 + 8s 超时。
- 标准 MCP stdio 协议服务端（JSON-RPC 2.0，含版本协商）。
- 一次性确认令牌：预演与执行严格一致，限时 + 会话绑定 + 确认后策略复核。
- 审计日志哈希链防篡改 + `--verify-audit` / `GET /api/audit/verify` 校验。
- Web 会话隔离（对话上下文按会话独立，慢请求互不阻塞）。
- 服务 start/stop/restart 真实执行（Linux/麒麟），附逆操作建议。
- 测试全量离线化（不再消耗 API 费用），GitHub Actions ubuntu CI 近似覆盖 Linux 分支。
- Windows 开发环境体验：CLI UTF-8 输出、跳过断开网络盘（磁盘采集 21s → 0.1s）。
- 配置校验：`validate-config.ps1` / `python -m safeops_agent.config_check`，四个 yaml 的字段与取值校验。
- 审计筛选：CLI `--show-audit` 与 Web 审计区支持按来源、风险等级、工具名过滤。
- 工程文档补齐：错误码字典（`ERROR_CODES.md`）与测试覆盖说明（`COVERAGE_NOTES.md`）。