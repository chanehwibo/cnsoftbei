# 答辩材料清单与流程

> 答辩当天的"一张纸检查清单"——确保环境就绪、材料齐全、演示顺序清晰。
> 详细演示命令和讲解词见 `DEMO_SCRIPT.md`。

---

## 1. 答辩前一天（环境与材料）

### 1.1 检查清单

| # | 事项 | 命令 / 操作 | 通过标志 |
| --- | --- | --- | --- |
| 1 | Python 版本 ≥ 3.12 | `python --version` | 显示 3.12+ |
| 2 | 依赖已安装 | `pip install httpx pyyaml` | 无报错（离线环境提前装好 wheel） |
| 3 | 测试全通过 | `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` | `Ran 158 tests ... OK` |
| 4 | 配置校验通过 | `powershell -ExecutionPolicy Bypass -File scripts\validate-config.ps1` | `0 个错误` |
| 5 | Web 冒烟通过 | `powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1` | `Web smoke passed` |
| 6 | LLM 连通（可选） | `python -m safeops_agent.cli "查看系统信息"` 不加 `SAFEOPS_LLM_DISABLED=1` | 思维链审计出现 `intent_source: llm`（如断网则自动回退规则） |
| 7 | PPT 可打开 | 双击 `SafeOps_答辩演示PPT.pptx` | 正常渲染 |
| 8 | 提交包已最新 | `powershell -ExecutionPolicy Bypass -File scripts\package.ps1` | `dist/cnsoftbei-submission.zip` 生成 |
| 9 | 提交包校验 | `powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1` | 无缺失项 |

### 1.2 带到现场的材料

- 笔记本电脑（装好环境、确认屏幕分辨率和投影连接）
- U 盘备份（源码 zip + PPT + 设计技术文档 PDF）
- 本清单（纸质或手机截图）

---

## 2. 答辩当天（开场前 10 分钟）

```powershell
# 1. 进入项目目录
cd C:\Users\CanhuiBao\Desktop\中国软件杯
$env:PYTHONPATH = 'src'
chcp 65001    # 确保控制台 UTF-8

# 2. 快速冒烟（≤10 秒）
python -m safeops_agent.cli "查看系统信息"

# 3. 启动 Web 工作台（后台运行，答辩全程保持）
Start-Process -FilePath python -ArgumentList @('-m', 'safeops_agent.web_server') -WindowStyle Minimized

# 4. 浏览器打开 http://127.0.0.1:8765，确认"已连接"
```

### 打开的窗口（推荐排列）

| 窗口 | 位置 | 用途 |
| --- | --- | --- |
| PPT 全屏 | 投影/主屏 | 架构图、痛点、安全护栏 |
| 浏览器 `http://127.0.0.1:8765` | 副屏或 Alt-Tab | Web 工作台实时演示 |
| PowerShell 终端 | 副屏或 Alt-Tab | CLI 演示 |

---

## 3. 答辩流程（建议 8 分钟）

### 3.1 PPT 讲解段（3 分钟）

| 步骤 | 内容 | 时间 |
| --- | --- | --- |
| 1 | 背景痛点：传统运维门槛高、误操作代价大 | 30s |
| 2 | 总体架构：CLI/Web → Agent → LLM 意图理解 → 安全护栏（策略+确认令牌） → MCP 工具 → 审计 | 60s |
| 3 | 安全设计亮点：五步思维链、哈希链防篡改审计、一次性确认令牌、输出侧护栏 | 60s |
| 4 | 工程指标：158 个离线测试、GitHub Actions CI、MCP JSON-RPC 2.0 标准协议 | 30s |

### 3.2 现场演示段（4 分钟）

按风险递增顺序演示，评委看到"从放行到拦截"的完整光谱：

| # | 场景 | 入口 | 关键展示 | 预期风险 |
| --- | --- | --- | --- | --- |
| 1 | 系统信息查询 | Web 按钮「系统信息」 | 工具自动选择、风险评分 10、决策摘要 | LOW |
| 2 | 资源诊断 | Web 按钮「诊断资源」 | 诊断报告面板（现象→原因→建议→证据） | LOW |
| 3 | 审计筛选 | Web 审计区切换「risk=LOW」→「risk=MEDIUM」 | 筛选控件实时过滤 | — |
| 4 | 服务重启（未确认） | CLI `python -m safeops_agent.cli "重启 nginx 服务" --json` | MEDIUM、dry-run 预案、`pending_action_id`、思维链审计 | MEDIUM |
| 5 | 服务重启（确认） | CLI `--confirm <上一步的 action_id>` 或 Web 一键确认按钮 | 一次性令牌消费、执行结果（Linux/麒麟真实 systemctl） | MEDIUM |
| 6 | 高风险拦截 | Web 按钮「高风险拦截」 | `INTENT_SENSITIVE_PATH`、risk=HIGH、不进入工具调用 | HIGH |

> **节奏提示**：每个场景 30–40s，边操作边讲要点，不读代码。

### 3.3 收尾段（1 分钟）

| 步骤 | 内容 |
| --- | --- |
| 1 | 强调定位：模型负责理解和规划，本地系统负责授权、执行和审计 |
| 2 | 后续计划：麒麟实机验证、标准 MCP SDK 集成、多模型适配 |

---

## 4. 评委常见问题与应答要点

| 可能提问 | 应答方向 |
| --- | --- |
| 大模型幻觉怎么办？ | Agent 不执行模型生成的 shell 命令；工具白名单 + 参数校验 + 输出侧护栏三层防护；LLM 失败自动回退规则匹配 |
| 怎么保证审计日志不被篡改？ | SHA-256 哈希链（每条 entry_hash = H(含 prev_hash 的事件)），`--verify-audit` 一键校验；篡改/删除/重排都能检出 |
| 为什么不直接让 LLM 生成命令？ | MCP 工具模式：每个工具固定命令模板+固定参数 schema，模型只选工具+填参数，不拼 shell；参数还要过注入检测和敏感路径校验 |
| 中风险确认会不会被绕过？ | 一次性确认令牌：绑定会话、10 分钟过期、消费即删除、确认前复核策略；`--yes` 是开发便利，生产环境可关闭 |
| 没有麒麟实机怎么验证？ | GitHub Actions ubuntu CI 覆盖 Linux 分支；systemctl/journalctl/rpm 已做适配入口；Windows 开发机走兼容输出分支；差异点在 `KYLIN_VALIDATION_CHECKLIST.md` 有清单 |
| 测试覆盖率？ | 158 个用例，全离线 3 秒，覆盖 Agent 主流程、安全策略、审计哈希链、MCP 协议、LLM 层、配置校验等 8 个模块 |

---

## 5. 兜底方案

| 异常情况 | 处理 |
| --- | --- |
| 终端中文乱码 | `chcp 65001`；或切换到 Web 工作台演示 |
| Web 端口占用 | `powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1` 后重启 |
| LLM API 超时/断网 | 设 `$env:SAFEOPS_LLM_DISABLED='1'`，走规则模式（不影响核心功能，只是思维链的 intent_source 变成 rule） |
| Python 环境缺失 | 用 U 盘备份的 zip 包在备用机现场解压 + `pip install -e .` |
| 投影分辨率异常 | Web 工作台和 CLI 不依赖分辨率；PPT 有 PDF 备份（`设计技术文档1.pdf`） |
| 审计日志为空 | 先跑 `scripts\demo.ps1` 生成演示审计数据 |

---

## 6. 文件清单（确认每个都能打开）

| 文件 | 用途 |
| --- | --- |
| `SafeOps_答辩演示PPT.pptx` | 答辩主讲 PPT |
| `设计技术文档1.pdf` / `docs/DESIGN_TECHNICAL_DOCUMENT.md` | 评委阅读的设计技术文档 |
| `docs/DEMO_SCRIPT.md` | 演示详细命令与讲解词 |
| `docs/DEMO_ASSETS.md` | 截图清单与素材生成命令 |
| `docs/ARCHITECTURE.md` | 架构设计说明 |
| `docs/SAFETY_GUARDRAILS.md` | 安全护栏设计 |
| `docs/ERROR_CODES.md` | 错误码字典 |
| `docs/COVERAGE_NOTES.md` | 测试覆盖说明 |
| `dist/cnsoftbei-submission.zip` | 项目提交包 |
| `dist/acceptance-report.md` | 自动验收报告 |
