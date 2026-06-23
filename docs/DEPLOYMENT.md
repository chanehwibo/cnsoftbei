# 部署文档

## 1. 环境要求

最低要求：

- Python 3.10+
- 可访问项目源码目录

开发环境已验证：

- Windows 10
- Python 3.14.3

目标环境：

- 麒麟操作系统
- systemd
- journalctl
- rpm 或 dpkg-query

## 2. 获取项目

项目目录：

```text
C:\Users\CanhuiBao\Desktop\中国软件杯
```

进入目录：

```powershell
cd C:\Users\CanhuiBao\Desktop\中国软件杯
```

## 3. Windows 开发环境运行

设置模块路径：

```powershell
$env:PYTHONPATH='src'
```

运行 CLI：

```powershell
python -m safeops_agent.cli "查看系统信息"
python -m safeops_agent.cli "查看监听端口" --json
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

运行测试：

```powershell
python -m unittest discover -s tests
```

## 4. 麒麟/Linux 环境部署

进入项目目录：

```bash
cd /path/to/china-software-cup
```

设置模块路径：

```bash
export PYTHONPATH=src
```

验证 Python：

```bash
python3 --version
```

运行 CLI：

```bash
python3 -m safeops_agent.cli "查看系统信息" --json
python3 -m safeops_agent.cli "查看错误日志" --json
python3 -m safeops_agent.cli "查看 nginx 服务状态" --json
python3 -m safeops_agent.cli "查询 nginx 软件包" --json
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

## 5. 审计日志

默认路径：

```text
data/audit.log
```

自定义路径：

```powershell
python -m safeops_agent.cli "查看系统信息" --audit-log data/demo-audit.log
```

查看最近日志：

```powershell
Get-Content .\data\audit.log -Encoding utf8 -Tail 10
```

Linux：

```bash
tail -n 10 data/audit.log
```

## 6. Web 工作台

Web 工作台使用 Python 标准库启动，不需要安装额外依赖。

Windows：

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.web_server
```

Linux：

```bash
export PYTHONPATH=src
python3 -m safeops_agent.web_server
```

默认访问：

```text
http://127.0.0.1:8765
```

## 7. MCP 工具调用

当前提供 MCP 风格 facade：

```powershell
python -c "import sys,json; sys.path.insert(0,'src'); from safeops_agent.mcp_server import McpToolService; print(json.dumps(McpToolService().list_tools(), ensure_ascii=False, indent=2))"
```

后续替换为官方 MCP SDK 时，应保持：

- 工具注册表不变。
- `PolicyEngine` 继续作为本地强制策略。
- `AuditLogger` 继续记录工具调用。

## 8. 常见问题

### 8.1 找不到模块

确认已设置：

```powershell
$env:PYTHONPATH='src'
```

或 Linux：

```bash
export PYTHONPATH=src
```

### 8.2 中文乱码

PowerShell：

```powershell
chcp 65001
```

### 8.3 Linux 命令不存在

检查：

```bash
which systemctl
which journalctl
which ss
which rpm
```

### 8.4 权限不足

当前 MVP 以只读工具为主。后续中风险操作需要配置独立 executor 和 sudo 白名单。
