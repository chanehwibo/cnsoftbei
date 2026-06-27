# 开发脚本

## 1. 运行测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

作用：

- 设置 `PYTHONPATH=src`。
- 运行全部单元测试。

## 2. 运行验收

```powershell
powershell -ExecutionPolicy Bypass -File scripts\acceptance.ps1
```

作用：

- 运行单元测试。
- 验证 MCP 风格工具清单输出。
- 验证系统信息、资源指标、监听端口等低风险查询。
- 验证中风险操作需要确认。
- 验证高风险敏感路径请求会被拒绝。
- 检查审计日志是否生成。

## 3. 运行演示命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

作用：

- 依次执行核心演示场景。
- 输出最近审计日志。
- 高风险拦截命令返回非零状态时继续执行。

## 4. 启动 Web 工作台

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

访问：

```text
http://127.0.0.1:8765
```

## 5. 查看 MCP 工具清单

```powershell
powershell -ExecutionPolicy Bypass -File scripts\show-tools.ps1
```

也可以使用跨平台 CLI 命令：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.cli --list-tools
```

## 6. 生成提交包

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
```

作用：

- 创建 `dist/cnsoftbei-submission.zip`。
- 打包源码、测试、配置、Web、脚本、演示数据和文档。
- 不打包 `.git`、运行期审计日志和 Python 缓存。

## 7. 清理缓存

```powershell
powershell -ExecutionPolicy Bypass -File scripts\clean.ps1
```

作用：

- 删除 `__pycache__`。
- 删除 `.pytest_cache`。

## 8. 停止 Web 工作台

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
```

作用：

- 查找命令行中包含 `safeops_agent.web_server` 的进程。
- 停止 SafeOps Web 工作台后台进程。
