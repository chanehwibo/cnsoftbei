# 测试方案与测试报告

## 1. 测试目标

验证安全智能运维 Agent 的核心能力：

- 自然语言请求可以匹配固定运维工具。
- 低风险只读工具可以正常执行。
- 中风险工具需要确认。
- 高风险请求会被拒绝。
- MCP 工具定义和调用结果格式稳定。
- 审计日志记录完整、可复盘。

## 2. 测试环境

当前已验证环境：

- OS：Windows 10
- Python：3.14.3
- 运行方式：`PYTHONPATH=src`

待验证目标环境：

- 麒麟操作系统
- Python 3.10+
- systemd
- journalctl
- rpm 或 dpkg-query

## 3. 测试范围

### 3.1 功能测试

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| F-01 | 查看系统信息 | 返回系统、内核、架构、主机名 |
| F-02 | 查看 CPU 和内存 | 返回资源指标 |
| F-03 | 查看进程 | 返回进程列表 |
| F-04 | 查看错误日志 | Linux 环境读取 journalctl |
| F-05 | 查看服务状态 | Linux 环境读取 systemctl |
| F-06 | 查看监听端口 | 返回监听端口列表 |
| F-07 | 查看环境变量 | 只返回安全白名单变量 |
| F-08 | 查询软件包 | Linux 环境查询 rpm/dpkg |

### 3.2 安全测试

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| S-01 | 删除根目录所有文件 | 拒绝，HIGH |
| S-02 | 覆盖 /etc/passwd | 拒绝，`INTENT_SENSITIVE_PATH` |
| S-03 | 服务名包含 `;rm -rf /` | 拒绝，`ARG_COMMAND_INJECTION` |
| S-04 | 重启 nginx 服务但未确认 | 拒绝，要求确认 |
| S-05 | 未注册工具调用 | 拒绝，`TOOL_NOT_FOUND` |

### 3.3 MCP 测试

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| M-01 | `list_tools()` | 返回所有工具 |
| M-02 | 工具包含 `inputSchema` | Schema 字段完整 |
| M-03 | 工具包含 `annotations` | 标注只读/破坏性/确认 |
| M-04 | 调用中风险工具 | 返回确认要求 |

### 3.4 审计测试

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| A-01 | 执行低风险工具 | 记录 `agent.tool_call` |
| A-02 | 拒绝高风险意图 | 记录 `agent.intent` |
| A-03 | 审计字段完整 | 包含 event_id、risk、error_code、duration_ms |

## 4. 自动化测试

运行命令：

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
```

当前自动化测试文件：

- `tests/test_agent.py`
- `tests/test_audit.py`
- `tests/test_mcp_service.py`
- `tests/test_policy.py`
- `tests/test_registry.py`

当前测试结果：

```text
Ran 15 tests
OK
```

## 5. 手工验证命令

```powershell
$env:PYTHONPATH='src'
python -m safeops_agent.cli "查看系统信息" --json
python -m safeops_agent.cli "查看CPU和内存" --json
python -m safeops_agent.cli "查看监听端口" --json
python -m safeops_agent.cli "查看环境变量" --json
python -m safeops_agent.cli "重启 nginx 服务" --json
python -m safeops_agent.cli "覆盖 /etc/passwd" --json
```

已验证结果：

- 低风险查询正常返回。
- 中风险重启服务要求确认。
- 高风险敏感路径操作被拒绝。
- 审计日志字段写入正常。

## 6. 麒麟环境补测计划

需要在麒麟环境补测：

- `/etc/os-release` 是否能正确识别麒麟版本。
- `journalctl -p err -n 100 --no-pager` 输出是否稳定。
- `systemctl status nginx --no-pager` 是否正常返回。
- `ss -lntup` 或 `netstat -lntup` 是否可用。
- `rpm -qa` 或 `dpkg-query -W` 是否可用。
- 普通用户权限下各只读命令是否可执行。
- sudo 白名单最小权限执行方案是否可落地。

## 7. 风险与改进

- 当前自动化测试主要覆盖策略和接口，不覆盖真实麒麟系统命令输出。
- Web 工作台完成后需要增加接口层测试。
- 接入真实 MCP SDK 后需要补充协议兼容测试。
- 接入大模型后需要补充提示注入和模型误调用测试。
