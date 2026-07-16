# 测试方案与测试报告

## 1. 验收范围

本报告覆盖软件级自动化与进程级验证：

- Agent 路由、会话上下文和响应；
- 工具注册、系统采集、诊断和受管文件；
- 意图、参数、服务和三级风险策略；
- 一次性确认、加密持久化、并发和原子写；
- 审计脱敏、SHA/HMAC、锚点、轮转和历史格式；
- MCP 生命周期、协议版本、Schema、确认与审计；
- Web 登录、Cookie、CSP、限流边界和 API；
- 前端请求、筛选、排序、会话标识和响应映射逻辑；
- 标准 YAML、配置校验和安装态资源；
- wheel 隔离安装与发布包内容。

硬件和麒麟实机执行不属于本次软件验收范围。

## 2. 执行环境

| 项目 | 值 |
| --- | --- |
| 日期 | 2026-07-16 |
| 系统 | Windows |
| Python | 3.14 |
| 测试框架 | unittest、coverage.py、Node `node:test` |
| LLM | `SAFEOPS_LLM_DISABLED=1`，网络逻辑使用 mock |
| 警告策略 | ResourceWarning 作为错误 |

## 3. 自动化结果

执行命令：

~~~powershell
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
python -m pip install -e ".[test]"
python -W error::ResourceWarning -m coverage run -m unittest discover -s tests
python -m coverage report
python -m coverage xml
npm run test:web
~~~

结果：

~~~text
Ran 216 tests
OK
~~~

Node 前端测试：7 项通过。

覆盖率结果（coverage.py 7.15.2，`branch = true`）：

| 指标 | 数值 |
| --- | ---: |
| 语句覆盖率 | 75.1% |
| 分支覆盖率 | 64.0% |
| 综合覆盖率 | 72.1% |
| CI 最低门槛 | 70.0% |

CI 先以 `python -m pip install -e ".[test]"` 安装项目、PyYAML 和 coverage，再执行 `pip check`；随后生成 `coverage.xml` 并按操作系统和 Python 版本上传独立报告。依赖不完整或覆盖率低于门槛时任务失败。

测试文件：

| 文件 | 主要覆盖 |
| --- | --- |
| `test_agent.py`、`test_new_features.py` | Agent、上下文、离线路由、默认参数 |
| `test_policy.py` | 意图、注入、敏感路径、服务边界与风险 |
| `test_tools.py`、`test_operations.py` | 系统工具、诊断、原子快照与回滚 |
| `test_pending_confirm.py` | 一次性、会话、过期、加密与并发 |
| `test_audit.py`、`test_audit_chain.py` | 查询、脱敏、签名、锚点、轮转与旧链 |
| `test_mcp_service.py`、`test_mcp_stdio.py` | MCP 工具、生命周期、Schema 和协议 |
| `test_web_server.py` | HTTP Cookie/Bearer 认证、限流、会话过期/LRU、SSE、TLS 与输入边界 |
| `web/tests/app_logic.test.js` | 请求错误、202 流程、筛选、排序、会话 ID 与响应字段映射 |
| `test_config_check.py`、`test_packaging.py` | YAML、配置、资源同步和安装后备 |
| `test_llm.py`、`test_reasoning_chain.py` | Provider、输出护栏和结构化决策轨迹 |

## 4. 进程与发布验证

### 4.1 配置

~~~powershell
python -m safeops_agent.config_check
~~~

预期：退出码 0。

### 4.2 审计

~~~powershell
python -m safeops_agent.cli --verify-audit
~~~

2026-07-16 对现有日志的结果为 `ok=true`；历史无哈希/SHA 记录和新 HMAC 签名记录均按各自格式完成校验。事件数量会随验收运行继续增长。

### 4.3 Web

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
~~~

覆盖 health、tools、agent 和 audit API；认证专项由进程级 unittest 覆盖。

### 4.4 CLI 验收

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
~~~

覆盖测试套件、工具清单、三个 LOW 场景、MEDIUM 预演、HIGH 拒绝和审计生成。

### 4.5 wheel

使用 `pip wheel --no-deps --no-build-isolation` 构建，安装到隔离临时目录，并在没有外部 `config/` 和 `web/` 的工作目录中验证：

- `PROJECT_ROOT` 指向可写工作目录；
- `CONFIG_DIR` 使用包内默认配置；
- `WEB_ROOT` 使用包内静态资源；
- Web 模块可导入且 index.html 存在。

结果：通过。

### 4.6 发布包

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
~~~

校验关键源码、测试、配置、Web、脚本和当前文档存在；校验 `data/`、本地 LLM 配置、`.env`、缓存、dist 和 Git 元数据不存在。

## 5. 通过标准

软件验收通过需同时满足：

1. 216 项 unittest 与 7 项前端 Node 测试全部通过；
2. Python 综合覆盖率不低于 70.0%，并生成 XML 报告；
3. ResourceWarning 严格模式无警告；
4. 配置校验退出码为 0；
5. 审计完整性 `ok=true`；
6. Web 冒烟通过；
7. CLI acceptance 通过；
8. wheel 隔离安装通过；
9. 发布包校验通过；
10. Git 跟踪内容不包含运行态数据或私密配置。
