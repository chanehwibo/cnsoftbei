# 部署文档

## 1. 环境

- Python 3.10 或更高版本；
- Windows PowerShell 用于仓库脚本；
- 麒麟/Linux 上的系统采集命令由固定工具调用；
- PyYAML 由项目依赖自动安装。

## 2. 开发态安装

~~~powershell
git clone https://github.com/chanehwibo/cnsoftbei.git
cd cnsoftbei
python -m pip install -e .
python -m safeops_agent.config_check
~~~

离线运行：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
safeops-agent "查看系统信息"
~~~

## 3. wheel 安装

~~~powershell
python -m pip wheel . --no-deps --wheel-dir dist
python -m pip install dist\safeops_agent-0.1.0-py3-none-any.whl
~~~

wheel 包含默认 `config/*.yaml` 与 `web/*`。安装后从任意可写工作目录启动即可；相对运行路径写入当前工作目录的 `data/`。可用 `SAFEOPS_PROJECT_ROOT` 显式指定配置覆盖和数据根目录。

## 4. 配置

| 文件 | 内容 |
| --- | --- |
| `config/app.yaml` | 审计路径、Web 地址、端口、认证和 TLS 证书路径 |
| `config/policy.yaml` | 高危关键词与敏感路径 |
| `config/tools.yaml` | 工具默认值、服务允许列表和保护列表 |
| `config/llm.yaml` | 公共模型配置 |
| `config/llm.local.yaml` | 本机 API Key，不入库、不打包 |

运行 `python -m safeops_agent.config_check` 校验配置。安装态缺少外部配置时使用 wheel 内默认值；工作目录中同名文件优先。

## 5. Linux 服务权限

服务 start/stop/restart 同时受以下边界约束：

1. 服务名必须符合安全标识符格式；
2. 服务必须位于 `service_allowlist`；
3. 服务不得位于 `protected_services`；
4. 策略要求一次性令牌；
5. Linux 以 root 运行时默认拒绝服务变更。

如果部署环境经过独立权限评审并必须以 root 运行，可显式设置 `SAFEOPS_ALLOW_ROOT_SERVICE_ACTIONS=1`。推荐使用专用低权限账号，并只授予所需 systemctl 单元权限。

## 6. Web 部署

本机：

~~~powershell
safeops-agent "查看系统信息"
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

直接对外监听时必须同时启用认证和原生 TLS，例如：

~~~yaml
web_host: 0.0.0.0
web_port: 8765
require_auth: true
tls_enabled: true
tls_cert_file: config/tls/server.crt
tls_key_file: config/tls/server.key
~~~

所有非开发部署都必须设置强随机 `SAFEOPS_TOKEN`；变量缺失时服务拒绝启动。服务端最低接受 TLS 1.2，发送 HSTS；证书或私钥缺失时拒绝启动。

使用 HTTPS 反向代理时，应用必须继续绑定 `127.0.0.1`，由代理终止 TLS，并设置 `SAFEOPS_BEHIND_HTTPS_PROXY=1`，使会话 Cookie 带 `Secure`。应用拒绝非回环地址上的明文 HTTP。

可选变量：

- `SAFEOPS_CORS_ORIGIN`：明确允许的跨域来源；
- `SAFEOPS_ACCESS_LOG=1`：启用访问日志；
- `SAFEOPS_BEHIND_HTTPS_PROXY=1`：应用绑定回环地址且由可信 HTTPS 反向代理转发时标记安全 Cookie。

## 7. MCP 部署

~~~powershell
safeops-mcp
~~~

MCP 使用 stdin/stdout，一行一条 JSON-RPC 2.0 消息。不要把调试文字写到 stdout。协议版本和生命周期见 [MCP_TOOLS.md](MCP_TOOLS.md)。

## 8. 数据保护与备份

`data/` 包含运行日志、HMAC 密钥、锚点、加密待确认记录、受管文件与快照。部署时：

- 目录仅授予服务账号读写；
- 审计日志与对应 `.key`、`.anchor.json` 一起备份；
- 不把 `data/` 复制进镜像、Git 或提交包；
- 可通过 `SAFEOPS_AUDIT_HMAC_KEY` 和 `SAFEOPS_PENDING_KEY` 由外部密钥系统注入稳定密钥；
- 恢复后运行 `safeops-agent --verify-audit`。

## 9. 健康检查

~~~text
GET /api/health
~~~

自动验证：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
~~~

本次软件验收不包含硬件或麒麟实机执行。
