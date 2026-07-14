# 测试覆盖说明

当前测试基线：**158 个用例，全量离线，约 3 秒跑完**（`scripts/test.ps1` 或
`PYTHONPATH=src python -m unittest discover -s tests`）。所有测试注入
`RuleBasedProvider` 或设置 `SAFEOPS_LLM_DISABLED=1`，不发起真实 LLM 请求，
不消耗 API 费用，结果确定可复现。

## 1. 覆盖矩阵（按模块）

| 模块 | 测试文件（用例数） | 覆盖内容 |
| --- | --- | --- |
| Agent 主流程 `agent.py` | test_agent.py (6)、test_new_features.py (19) | 意图理解→裁决→执行→审计全链路；多轮上下文、参数追问、风险评分、决策摘要、诊断报告 |
| 思维链审计 | test_reasoning_chain.py (7) | 五步推理链的阶段、顺序与内容 |
| 安全策略 `security/policy.py` | test_policy.py (19) | 高危关键词（中英文、词边界）、敏感路径、参数注入、服务/包名校验、风险分级裁决 |
| 确认令牌 `security/pending.py` | test_pending_confirm.py (10) | 一次性消费、过期、会话绑定、确认后策略复核 |
| 审计日志 `audit/logger.py` | test_audit.py (9)、test_audit_chain.py (6) | 结构化事件字段、哈希链防篡改（篡改/删除/重排检出）、按来源/风险/工具筛选查询 |
| 工具集 `tools/` | test_tools.py (22)、test_operations.py (11)、test_registry.py (3) | 各查询/诊断工具输出契约、受管文件写入与快照回滚、注册表与禁用过滤 |
| MCP 协议 | test_mcp_service.py (4)、test_mcp_stdio.py (16) | 工具 schema、错误码、风险标注契约；JSON-RPC 2.0 解析、版本协商、五类协议错误 |
| LLM 层 `llm/` | test_llm.py (15) | 规则回退、输出侧护栏（工具名/参数白名单）、超时降级、离线开关 |
| 配置校验 `config_check.py` | test_config_check.py (11) | 四个 yaml 的字段/类型/范围校验、error 与 warning 分级、llm.local.yaml 覆盖 |

## 2. 平台差异与 CI

- 本仓库在 **Windows 开发机**上开发，Linux/麒麟专属分支（systemctl、journalctl、
  rpm 等真实命令路径）由 **GitHub Actions ubuntu CI** 近似覆盖，Windows 本地
  跑的是各工具的兼容输出分支。
- 哪些结果在 Windows 为兼容输出、哪些必须在麒麟上验证，见
  `docs/KYLIN_VALIDATION_CHECKLIST.md` 与部署文档。

## 3. 已知覆盖缺口

| 缺口 | 说明 | 计划 |
| --- | --- | --- |
| 麒麟实机验证 | 无麒麟实机，systemd 真实生命周期操作只在 ubuntu CI 上验证过 | 按 `KYLIN_VALIDATION_CHECKLIST.md` 在实机补验并出报告（P0-01） |
| Web 服务端单测 | `web_server.py` 的鉴权、限流、会话隔离目前靠 `scripts/web-smoke.ps1` 端到端冒烟覆盖，无进程内单测 | 后续可用 ThreadingHTTPServer 随机端口起服务补 API 级测试 |
| 真实 LLM 通路 | DeepSeek 真实调用（网络、鉴权、超时）不进测试，仅人工冒烟 | 保持现状：测试离线是硬约束，真实通路由演示前人工检查 |
| 前端逻辑 | web/app.js 无自动化测试 | 逻辑单薄且随演示频繁手工验证，暂不投入 |
| 覆盖率数值 | 未接入 coverage.py 统计行覆盖率 | 如需数字指标可加 `coverage run -m unittest discover`，当前以模块矩阵代替 |

## 4. 新增测试的约定

- **必须离线**：注入 `llm=RuleBasedProvider()` 或设 `SAFEOPS_LLM_DISABLED=1`，
  否则会真实调用 DeepSeek API（慢、烧钱、断言被非确定性打破）。
- 审计相关测试写临时目录（`tempfile.TemporaryDirectory`），不污染 `data/audit.log`。
- 断言精确工具名的测试走规则模式（验收脚本同理，见 `scripts/acceptance.ps1`）。
