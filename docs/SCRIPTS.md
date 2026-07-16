# 脚本参考

所有脚本从自身位置解析仓库根目录。

| 脚本 | 作用 |
| --- | --- |
| `test.ps1` | 设置源码路径，运行严格模式 unittest，检查 70% 覆盖率门槛并生成 `coverage.xml` |
| `acceptance.ps1` | 运行自动测试、工具清单、LOW/MEDIUM/HIGH CLI 场景和审计生成 |
| `validate-config.ps1` | 运行标准 YAML 配置校验，参数原样转发 |
| `web.ps1` | 前台启动 Web 工作台 |
| `web-smoke.ps1` | 隐藏启动临时 Web 进程，验证 health/tools/agent/audit 后停止 |
| `stop-web.ps1` | 停止 Web 服务进程 |
| `mcp-stdio.ps1` | 启动 MCP stdio 服务 |
| `show-tools.ps1` | 输出 MCP 工具清单 |
| `demo.ps1` | 顺序演示查询、预演、拒绝和审计 |
| `report.ps1` | 运行 acceptance 并生成 `dist/acceptance-report.md` |
| `package.ps1` | 生成 `dist/cnsoftbei-submission.zip` |
| `verify-package.ps1` | 校验提交包必需项和禁止项 |
| `clean.ps1` | 清理开发缓存 |

常用命令：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\validate-config.ps1
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
~~~

## 发布包边界

`package.ps1` 只收集 README、pyproject、公共 config、demo、当前 docs、scripts、src、tests 和 web。以下内容被排除：

- `data/` 全部运行态数据；
- `config/llm.local.yaml`；
- `.env`；
- `.git/`、`dist/`、`__pycache__/` 和 pyc。

`verify-package.ps1` 会重新打开 ZIP，检查当前文档、核心源码、测试、脚本、包内资源和禁止路径。

## 脚本退出状态

- 测试、配置、冒烟、验收、打包校验成功返回 0；
- Agent 拒绝 HIGH 或等待 MEDIUM 确认时 CLI 返回 1，这是可由 acceptance 断言的业务状态；
- PowerShell 脚本启用 `$ErrorActionPreference = "Stop"`，外部步骤失败会中止。
