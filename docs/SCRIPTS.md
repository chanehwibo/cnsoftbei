# 开发脚本

## 1. 运行测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

作用：

- 设置 `PYTHONPATH=src`。
- 运行全部单元测试。

## 2. 运行演示命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

作用：

- 依次执行核心演示场景。
- 输出最近审计日志。
- 高风险拦截命令返回非零状态时继续执行。

## 3. 启动 Web 工作台

```powershell
powershell -ExecutionPolicy Bypass -File scripts\web.ps1
```

访问：

```text
http://127.0.0.1:8765
```

## 4. 查看 MCP 工具清单

```powershell
powershell -ExecutionPolicy Bypass -File scripts\show-tools.ps1
```

## 5. 清理缓存

```powershell
powershell -ExecutionPolicy Bypass -File scripts\clean.ps1
```

作用：

- 删除 `__pycache__`。
- 删除 `.pytest_cache`。

## 6. 停止 Web 工作台

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-web.ps1
```

作用：

- 查找命令行中包含 `safeops_agent.web_server` 的进程。
- 停止 SafeOps Web 工作台后台进程。
