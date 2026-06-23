# 演示数据和截图材料

## 1. 演示数据

已准备：

- `demo/demo_requests.json`：答辩演示请求清单。
- `demo/sample_audit_events.jsonl`：可放入 PPT 的示例审计事件。

演示请求覆盖：

- 系统信息查询。
- 资源指标查询。
- 监听端口查询。
- 服务状态查询。
- 中风险服务重启确认。
- 高风险敏感路径拦截。

## 2. 建议截图

### 2.1 Web 工作台首页

内容要求：

- 左侧常用任务。
- 中间自然语言输入和响应区域。
- 右侧工具清单和审计日志。

用途：

- 展示系统不是普通脚本，而是可交互运维工作台。

### 2.2 低风险查询结果

操作：

```text
查看系统信息
```

截图重点：

- `tool=system.info`
- `risk=LOW`
- 返回系统信息。

### 2.3 中风险确认

操作：

```text
重启 nginx 服务
```

截图重点：

- `tool=service.restart`
- `risk=MEDIUM`
- 显示需要确认。

### 2.4 高风险拦截

操作：

```text
覆盖 /etc/passwd
```

截图重点：

- `risk=HIGH`
- 拒绝原因。
- 错误码 `INTENT_SENSITIVE_PATH`。

### 2.5 MCP 工具清单

截图重点：

- 工具名称。
- 分类。
- 风险等级。
- inputSchema。

### 2.6 审计日志

截图重点：

- `event_id`
- `request`
- `tool`
- `risk`
- `allowed`
- `reason`
- `error_code`
- `duration_ms`

## 3. PPT 素材建议

建议页面：

- 背景痛点：传统运维门槛高，误操作风险高。
- 总体架构：CLI/Web、Agent、MCP、Policy、Tools、Audit。
- 安全护栏：意图过滤、工具白名单、参数校验、审批、审计。
- 演示流程：低风险查询、中风险确认、高风险拒绝。
- 测试结果：15 个自动化测试通过。
- 后续计划：麒麟实机适配、标准 MCP SDK、大模型接入。

## 4. 素材生成命令

启动 Web：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.web_server
```

访问：

```text
http://127.0.0.1:8765
```

生成演示审计数据可使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```
