from __future__ import annotations

from safeops_agent.config import load_tools_config

from .models import RiskLevel, ToolSpec
from .system import (
    get_resource_usage,
    get_service_status,
    get_system_info,
    inspect_recent_errors,
    list_cron_jobs,
    list_disk_partitions,
    list_listening_ports,
    list_network_connections,
    list_processes,
    list_safe_environment,
    list_users,
    query_package,
    restart_service,
)


def build_registry() -> dict[str, ToolSpec]:
    tools = [
        ToolSpec(
            name="system.info",
            description="采集操作系统版本、内核、架构和主机信息",
            risk=RiskLevel.LOW,
            handler=get_system_info,
            category="system",
        ),
        ToolSpec(
            name="system.resources",
            description="采集 CPU、内存和磁盘基础指标",
            risk=RiskLevel.LOW,
            handler=get_resource_usage,
            category="system",
        ),
        ToolSpec(
            name="process.list",
            description="查看进程列表",
            risk=RiskLevel.LOW,
            handler=list_processes,
            parameters={"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            category="process",
        ),
        ToolSpec(
            name="logs.recent_errors",
            description="读取最近的系统错误日志",
            risk=RiskLevel.LOW,
            handler=inspect_recent_errors,
            parameters={"lines": {"type": "integer", "minimum": 10, "maximum": 500}},
            category="logs",
        ),
        ToolSpec(
            name="service.status",
            description="查询 systemd 服务状态",
            risk=RiskLevel.LOW,
            handler=get_service_status,
            parameters={"service": {"type": "string"}},
            required=["service"],
            category="service",
        ),
        ToolSpec(
            name="network.connections",
            description="查看网络连接",
            risk=RiskLevel.LOW,
            handler=list_network_connections,
            parameters={"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
            category="network",
        ),
        ToolSpec(
            name="network.listening_ports",
            description="查看监听端口",
            risk=RiskLevel.LOW,
            handler=list_listening_ports,
            parameters={"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
            category="network",
        ),
        ToolSpec(
            name="disk.partitions",
            description="查看磁盘分区和挂载点",
            risk=RiskLevel.LOW,
            handler=list_disk_partitions,
            category="disk",
        ),
        ToolSpec(
            name="user.list",
            description="查看本地用户列表",
            risk=RiskLevel.LOW,
            handler=list_users,
            category="user",
        ),
        ToolSpec(
            name="schedule.cron",
            description="查看 cron 定时任务配置",
            risk=RiskLevel.LOW,
            handler=list_cron_jobs,
            category="schedule",
        ),
        ToolSpec(
            name="environment.safe",
            description="查看安全环境变量白名单",
            risk=RiskLevel.LOW,
            handler=list_safe_environment,
            category="environment",
        ),
        ToolSpec(
            name="package.query",
            description="查询软件包列表或指定软件包版本",
            risk=RiskLevel.LOW,
            handler=query_package,
            parameters={"package": {"type": "string"}},
            category="package",
        ),
        ToolSpec(
            name="service.restart",
            description="重启指定 systemd 服务",
            risk=RiskLevel.MEDIUM,
            handler=restart_service,
            parameters={"service": {"type": "string"}},
            required=["service"],
            category="service",
        ),
    ]
    disabled = set(load_tools_config().get("disabled_tools", []))
    return {tool.name: tool for tool in tools if tool.name not in disabled}
