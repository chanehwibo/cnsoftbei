# SafeOps Agent 新手操作手册

## 1. 准备环境

~~~powershell
cd "C:\Users\CanhuiBao\Desktop\中国软件杯"
python --version
python -m pip install -e .
~~~

Python 需要 3.10 或更高版本。首次演示建议使用离线模式，结果确定且不会发起模型网络请求：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
~~~

如不安装项目，每个新 PowerShell 窗口先执行：

~~~powershell
$env:PYTHONPATH='src'
~~~

## 2. 配置自检

~~~powershell
python -m safeops_agent.config_check
~~~

看到“配置校验通过”即可继续。公共配置分别控制 Web、策略、工具与模型；`config/llm.local.yaml` 只保存本机 API Key。

## 3. 低风险查询

~~~powershell
python -m safeops_agent.cli "查看系统信息"
python -m safeops_agent.cli "查看CPU和内存"
python -m safeops_agent.cli "查看监听端口"
python -m safeops_agent.cli "查看 nginx 服务状态"
python -m safeops_agent.cli "诊断CPU和内存" --json
~~~

LOW 工具是只读采集。`--json` 会显示工具名、风险评分、决策摘要、结果和结构化决策轨迹。

## 4. 中风险确认

第一步只预演，不会变更服务：

~~~powershell
python -m safeops_agent.cli "重启 nginx 服务" --json
~~~

从输出复制 `pending_action_id`，再执行：

~~~powershell
python -m safeops_agent.cli --confirm <ACTION_ID> --json
~~~

令牌只能使用一次、十分钟有效并绑定 CLI 会话。确认时系统再次读取当前策略，然后精确执行签发时保存的 `service.restart + nginx`。服务变更只适用于 `config/tools.yaml` 的允许列表；保护服务始终拒绝。

如果只是演示安全流程，可以停在 dry-run 输出，不执行第二步。

## 5. 高风险拦截

~~~powershell
python -m safeops_agent.cli "删除根目录所有文件" --json
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
~~~

正确结果是 `risk=HIGH`、`ok=false`，且没有真实工具执行。参数中的命令注入字符、敏感路径、保护服务或非白名单服务也会在 handler 前被拒绝。

## 6. 审计

~~~powershell
python -m safeops_agent.cli --show-audit --audit-limit 5
python -m safeops_agent.cli --show-audit --audit-risk HIGH
python -m safeops_agent.cli --verify-audit
~~~

`reasoning_chain` 是兼容字段名，内容是上下文解析、意图筛查、工具选择、风险裁决和执行结果等可审计事实，不是模型私有推理过程。完整性校验会检查历史 SHA 链、新 HMAC 签名、轮转段和持久化锚点。

## 7. Web 工作台

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

浏览器访问 `http://127.0.0.1:8765`。页面可完成自然语言请求、令牌确认、决策轨迹查看和审计查询。

本机回环默认可不设置令牌。启用认证时：

~~~powershell
$env:SAFEOPS_TOKEN='使用足够长的随机值'
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
~~~

浏览器提交令牌后获得 HttpOnly 会话 Cookie。SSE 不接受 URL 查询参数令牌。

关闭 Web：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
~~~

## 8. MCP

查看工具：

~~~powershell
python -m safeops_agent.cli --list-tools
~~~

启动 stdio 服务：

~~~powershell
python -m safeops_agent.mcp_stdio
~~~

客户端先完成 `initialize` 和 `notifications/initialized`。LOW 工具可直接调用；MEDIUM 工具第一次返回 `pending_action_id`，之后调用 `safeops.confirm` 并传入 `action_id`。

## 9. 大模型模式

~~~powershell
Copy-Item config\llm.local.yaml.example config\llm.local.yaml
~~~

编辑新文件并填入 `llm_api_key`，然后清除离线变量：

~~~powershell
Remove-Item Env:SAFEOPS_LLM_DISABLED -ErrorAction SilentlyContinue
python -m safeops_agent.cli "帮我看看这台机器现在忙不忙" --json
~~~

工具选择步骤的 `source` 为 `llm` 表示使用了模型。`llm_reasoning` 只是模型返回的一句话工具选择说明。网络失败、响应格式错误或工具不合法时会自动回退本地规则。

## 10. 验收

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
python -W error::ResourceWarning -m unittest discover -s tests
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
~~~

自动化测试当前为 196 项。该组命令完成软件级回归、Web API 冒烟、核心 CLI 场景和发布包内容校验；不执行硬件或麒麟实机操作。

## 11. 常见处理

| 现象 | 处理 |
| --- | --- |
| 找不到 `safeops_agent` | 安装 `python -m pip install -e .`，或设置 `PYTHONPATH=src` |
| 中文乱码 | 设置 `$env:PYTHONIOENCODING='utf-8'` |
| 令牌无效 | 重新发起原请求获取新令牌；不要跨 CLI/Web/MCP 会话混用 |
| Web 401 | 先在页面登录，或 API 使用 `Authorization: Bearer ...` |
| 配置报错 | 运行 `python -m safeops_agent.config_check` |
| 被拒绝的危险请求返回非零码 | 这是安全裁决的正确执行状态 |
