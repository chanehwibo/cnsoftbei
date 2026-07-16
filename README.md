# 面向麒麟操作系统的安全智能运维 Agent

SafeOps Agent 是中国软件杯赛题 1 A 组作品。它把自然语言请求映射到固定白名单工具，并在本地策略、一次性确认令牌和签名审计的约束下执行运维动作。

核心能力：

- DeepSeek 意图理解，可无网络回退到确定性规则路由；
- 25 个固定工具，无任意 Shell、无模型直执行通道；
- LOW 只读直行、MEDIUM 预演后凭一次性令牌确认、HIGH 默认拒绝；
- 服务变更白名单、关键系统服务保护和 Linux root 运行保护；
- 受管文件写前快照、原子写入和真实回滚；
- 结构化决策轨迹；历史字段 `reasoning_chain` 仅承载可审计决策事实，不是模型隐藏思维过程；
- SHA-256 链、HMAC 签名、持久化锚点、轮转校验和敏感字段脱敏；
- MCP `2025-11-25` stdio 服务端与带会话认证的 Web 工作台；
- wheel 内置默认配置和 Web 静态资源，可脱离源码目录运行。

## 快速开始

需要 Python 3.10 或更高版本。

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
python -m pip install -e .
$env:SAFEOPS_LLM_DISABLED='1'

safeops-agent "查看系统信息"
safeops-agent "查看CPU和内存"
safeops-agent "查看监听端口"
~~~

也可以不安装，直接从源码运行：

~~~powershell
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
python -m safeops_agent.cli "查看系统信息"
~~~

## 风险与确认

中风险请求首次只生成 dry-run 计划和十分钟有效的一次性令牌：

~~~powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
python -m safeops_agent.cli --confirm <ACTION_ID> --json
~~~

令牌绑定会话和当时保存的工具参数；确认阶段不重新运行意图识别。服务 start/stop/restart 只允许 `config/tools.yaml` 中的白名单服务，保护列表中的安全基础服务始终拒绝变更。

高风险请求直接拒绝：

~~~powershell
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
~~~

被拒绝或等待确认时 CLI 返回非零退出码，便于脚本正确识别执行状态。

## 大模型配置

复制 `config/llm.local.yaml.example` 为 `config/llm.local.yaml`，填入 `llm_api_key`。私密本地配置和全部 `data/` 运行态文件都不会进入 Git 或发布包。也可以使用环境变量 `LLM_API_KEY`。

设置 `SAFEOPS_LLM_DISABLED=1` 会强制使用离线规则模式。模型只选择候选工具和提取参数，本地策略拥有最终裁决权。

## Web 与 MCP

启动本机 Web 工作台：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

默认地址是 `http://127.0.0.1:8765`，启动前必须设置 `SAFEOPS_TOKEN`；浏览器登录后使用 HttpOnly 会话 Cookie。只有显式配置 `development_mode: true`、`require_auth: false` 且绑定回环地址时才能免鉴权。非回环地址必须同时启用原生 TLS 和认证。HTTPS 反向代理必须让应用继续绑定回环地址，并设置 `SAFEOPS_BEHIND_HTTPS_PROXY=1`。

启动 MCP stdio 服务：

~~~powershell
safeops-mcp
~~~

客户端必须依次完成 `initialize`、`notifications/initialized`，之后才能调用 `tools/list` 和 `tools/call`。中风险 MCP 调用通过 `safeops.confirm` 消费一次性令牌。

## 验证

~~~powershell
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
python -W error::ResourceWarning -m coverage run -m unittest discover -s tests
python -m coverage report
npm run test:web
python -m safeops_agent.config_check
python -m safeops_agent.cli --verify-audit
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
~~~

当前自动化套件包含 216 项 Python 测试和 7 项前端 Node 测试；Python 分支覆盖综合值为 72.1%，CI 门槛为 70.0%。软件级验收在 Windows/Python 3.14 与 Node 24 环境执行；本次验收范围不包含硬件或麒麟实机执行。

## 文档

- [架构设计](docs/ARCHITECTURE.md)
- [设计技术文档](docs/DESIGN_TECHNICAL_DOCUMENT.md)
- [新手操作手册](docs/BEGINNER_OPERATION_MANUAL.md)
- [部署文档](docs/DEPLOYMENT.md)
- [安全护栏](docs/SAFETY_GUARDRAILS.md)
- [MCP 接入](docs/MCP_TOOLS.md)
- [大模型接入](docs/LLM_INTEGRATION.md)
- [测试方案与报告](docs/TEST_PLAN_AND_REPORT.md)
- [答辩演示脚本](docs/DEMO_SCRIPT.md)
- [脚本参考](docs/SCRIPTS.md)
- [错误码字典](docs/ERROR_CODES.md)
- [开发任务时间线](docs/DEVELOPMENT_LOG.md)

运行数据默认写入 `data/`。审计日志、签名密钥、锚点、确认令牌密钥和受管文件均属于运行态数据，不进入版本库与提交包。
