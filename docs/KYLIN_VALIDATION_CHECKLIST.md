# 麒麟系统实机验证清单

## 1. 使用目的

本清单用于在真实麒麟操作系统上验证项目是否满足初赛演示和赛题适配要求。当前开发环境主要是 Windows，因此凡是涉及 `systemctl`、`journalctl`、`ss`、`rpm` 等 Linux/麒麟命令的能力，都需要按本清单在麒麟实机或麒麟虚拟机中补测。

## 2. 验证原则

- 只执行只读命令和安全演示命令。
- 不直接重启生产服务，不删除系统文件，不修改系统权限。
- `service.restart` 只验证中风险确认闭环，不验证真实重启效果。
- 每条验证都记录实际输出摘要、是否通过、失败原因和截图编号。
- 如果使用虚拟机验证，需要记录虚拟机版本、CPU、内存和 Python 版本。

## 3. 环境准备

进入项目目录：

```bash
cd /path/to/cnsoftbei
export PYTHONPATH=src
```

检查 Python：

```bash
python3 --version
python --version
```

如果系统默认命令是 `python3`，后续命令可把 `python` 替换为 `python3`。

## 4. 操作系统基础信息验证

| 编号 | 验证项 | 命令 | 预期结果 | 结果 |
| --- | --- | --- | --- | --- |
| K01 | 系统版本 | `cat /etc/os-release` | 能看到 Kylin/麒麟发行版信息 | 待验证 |
| K02 | 内核信息 | `uname -a` | 能看到 Linux 内核和架构 | 待验证 |
| K03 | systemd 版本 | `systemctl --version` | systemd 命令可用 | 待验证 |
| K04 | 日志系统 | `journalctl -p err -n 20 --no-pager` | 可读取最近错误日志，或明确权限不足 | 待验证 |
| K05 | 监听端口 | `ss -lntup` | 可列出监听端口，普通用户可能看不到进程名 | 待验证 |
| K06 | 软件包系统 | `rpm -qa | head` | 可列出 rpm 软件包 | 待验证 |
| K07 | 当前用户 | `id` | 记录普通用户权限 | 待验证 |
| K08 | 磁盘挂载 | `df -h` | 可查看磁盘分区和挂载点 | 待验证 |
| K09 | 进程列表 | `ps -eo pid,comm,user,%cpu,%mem --sort=-%cpu | head` | 可查看进程摘要 | 待验证 |

## 5. 项目基础功能验证

| 编号 | 验证项 | 命令 | 预期结果 | 结果 |
| --- | --- | --- | --- | --- |
| K10 | 单元测试 | `python -m unittest discover -s tests` | 测试通过 | 待验证 |
| K11 | 系统信息 | `python -m safeops_agent.cli "查看系统信息" --json` | 返回 `system.info` 结果 | 待验证 |
| K12 | 资源指标 | `python -m safeops_agent.cli "查看CPU和内存" --json` | 返回 `system.resources` 结果 | 待验证 |
| K13 | 进程列表 | `python -m safeops_agent.cli "查看进程" --json` | 返回 `process.list` 结果 | 待验证 |
| K14 | 监听端口 | `python -m safeops_agent.cli "查看监听端口" --json` | 返回 `network.listening_ports` 结果 | 待验证 |
| K15 | 磁盘分区 | `python -m safeops_agent.cli "查看磁盘分区" --json` | 返回 `disk.partitions` 结果 | 待验证 |
| K16 | 最近错误日志 | `python -m safeops_agent.cli "分析最近系统错误日志" --json` | 返回日志摘要或权限说明 | 待验证 |
| K17 | 服务状态 | `python -m safeops_agent.cli "查看 sshd 服务状态" --json` | 返回 `service.status` 结果或服务不存在说明 | 待验证 |
| K18 | 软件包查询 | `python -m safeops_agent.cli "查询 bash 软件包" --json` | 优先通过 rpm 查询软件包 | 待验证 |
| K19 | MCP 工具清单 | `python -m safeops_agent.cli --list-tools` | 输出工具清单和 schema 摘要 | 待验证 |
| K20 | 审计日志 | `tail -n 5 data/audit.log` | 能看到 JSONL 审计事件 | 待验证 |

## 6. 安全策略验证

| 编号 | 验证项 | 命令 | 预期结果 | 结果 |
| --- | --- | --- | --- | --- |
| K21 | 高风险删除拦截 | `python -m safeops_agent.cli "删除根目录所有文件" --json` | 请求被拒绝，风险等级为 HIGH | 待验证 |
| K22 | 敏感路径保护 | `python -m safeops_agent.cli "覆盖 /etc/passwd" --json` | 请求被拒绝，错误码为敏感路径相关 | 待验证 |
| K23 | 命令注入拦截 | `python -m safeops_agent.cli "查询 nginx; rm -rf / 服务" --json` | 请求被拒绝，错误码为参数非法或注入风险 | 待验证 |
| K24 | 中风险确认 | `python -m safeops_agent.cli "重启 nginx 服务" --json` | 不带确认时要求人工确认 | 待验证 |
| K25 | 中风险确认闭环 | `python -m safeops_agent.cli "重启 nginx 服务" --yes --json` | 进入已确认路径，但不真实重启服务 | 待验证 |

## 7. Web 工作台验证

启动 Web：

```bash
python -m safeops_agent.web_server
```

浏览器访问：

```text
http://127.0.0.1:8765
```

| 编号 | 验证项 | 操作 | 预期结果 | 结果 |
| --- | --- | --- | --- | --- |
| K26 | 健康检查 | 访问 `/api/health` | 返回 `ok=true` | 待验证 |
| K27 | 页面加载 | 打开首页 | 能看到自然语言输入框、常用任务、工具清单和审计日志区域 | 待验证 |
| K28 | 低风险查询 | 输入“查看系统信息” | 自动执行并展示结果 | 待验证 |
| K29 | 中风险确认 | 输入“重启 nginx 服务” | 页面提示需要确认 | 待验证 |
| K30 | 高风险拒绝 | 输入“覆盖 /etc/passwd” | 页面展示拒绝原因 | 待验证 |
| K31 | 审计展示 | 查看审计区域 | 能看到最近请求记录 | 待验证 |

## 8. 验证记录模板

| 字段 | 内容 |
| --- | --- |
| 验证日期 | 待填写 |
| 验证人员 | 待填写 |
| 机器类型 | 物理机/虚拟机/云主机 |
| 麒麟版本 | 待填写 |
| 内核版本 | 待填写 |
| CPU/内存 | 待填写 |
| Python 版本 | 待填写 |
| Git 提交哈希 | 待填写 |
| 单元测试结果 | 待填写 |
| CLI 演示结果 | 待填写 |
| Web 演示结果 | 待填写 |
| 安全策略结果 | 待填写 |
| 未通过项 | 待填写 |
| 截图编号 | 待填写 |

## 9. 通过标准

- K10 单元测试通过。
- K11 到 K18 至少能完成系统信息、资源、进程、端口、磁盘、日志、服务状态、软件包查询中的主要路径验证。
- K21 到 K25 安全策略行为符合预期。
- Web 工作台能启动并完成低风险查询、中风险确认和高风险拒绝演示。
- 审计日志能记录 CLI 和 Web 请求。

## 10. 当前状态

截至当前开发记录，本清单尚未在真实麒麟系统执行。初赛提交时应表述为“已完成麒麟验证清单和 Linux/麒麟适配实现，待在真实麒麟环境完成实机验证并补充记录”。
