from __future__ import annotations

from safeops_agent.config import load_tools_config

from .diagnostics import (
    diagnose_disk,
    diagnose_logs,
    diagnose_network_ports,
    diagnose_overview,
    diagnose_resources,
    diagnose_service,
)
from .models import RiskLevel, ToolSpec
from .operations import (
    apply_managed_file,
    list_managed_files,
    rollback_managed_file,
)
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
    start_service,
    stop_service,
)


def _build_specs() -> list[ToolSpec]:
    return [
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
            name="diagnostics.overview",
            description="生成系统概览诊断报告",
            risk=RiskLevel.LOW,
            handler=diagnose_overview,
            category="diagnostics",
        ),
        ToolSpec(
            name="diagnostics.resources",
            description="诊断 CPU、内存和磁盘资源风险",
            risk=RiskLevel.LOW,
            handler=diagnose_resources,
            category="diagnostics",
        ),
        ToolSpec(
            name="diagnostics.disk",
            description="诊断磁盘空间和挂载点风险",
            risk=RiskLevel.LOW,
            handler=diagnose_disk,
            category="diagnostics",
        ),
        ToolSpec(
            name="diagnostics.network_ports",
            description="诊断端口占用和监听状态",
            risk=RiskLevel.LOW,
            handler=diagnose_network_ports,
            parameters={"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
            category="diagnostics",
        ),
        ToolSpec(
            name="diagnostics.service",
            description="诊断服务可用性问题",
            risk=RiskLevel.LOW,
            handler=diagnose_service,
            parameters={"service": {"type": "string"}},
            required=["service"],
            category="diagnostics",
        ),
        ToolSpec(
            name="diagnostics.logs",
            description="诊断最近系统错误日志",
            risk=RiskLevel.LOW,
            handler=diagnose_logs,
            parameters={"lines": {"type": "integer", "minimum": 10, "maximum": 500}},
            category="diagnostics",
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
        ToolSpec(
            name="service.start",
            description="启动指定 systemd 服务（逆操作：service.stop）",
            risk=RiskLevel.MEDIUM,
            handler=start_service,
            parameters={"service": {"type": "string"}},
            required=["service"],
            category="service",
        ),
        ToolSpec(
            name="service.stop",
            description="停止指定 systemd 服务（逆操作：service.start）",
            risk=RiskLevel.MEDIUM,
            handler=stop_service,
            parameters={"service": {"type": "string"}},
            required=["service"],
            category="service",
        ),
        ToolSpec(
            name="file.apply",
            description="写入受管工作区文件，写入前自动快照，返回可回滚的快照 ID",
            risk=RiskLevel.MEDIUM,
            handler=apply_managed_file,
            parameters={"name": {"type": "string"}, "content": {"type": "string"}},
            required=["name", "content"],
            category="operations",
        ),
        ToolSpec(
            name="file.rollback",
            description="按快照 ID 将受管文件恢复到写入前状态（真实逆操作）",
            risk=RiskLevel.MEDIUM,
            handler=rollback_managed_file,
            parameters={"snapshot_id": {"type": "string"}},
            required=["snapshot_id"],
            category="operations",
        ),
        ToolSpec(
            name="file.list_managed",
            description="列出受管工作区文件与历史快照数量",
            risk=RiskLevel.LOW,
            handler=list_managed_files,
            category="operations",
        ),
    ]


def all_tool_names() -> list[str]:
    """全量工具名（不受 disabled_tools 影响），供配置校验等场景使用。"""
    return [tool.name for tool in _build_specs()]


def build_registry() -> dict[str, ToolSpec]:
    disabled = set(load_tools_config().get("disabled_tools") or [])
    return {tool.name: tool for tool in _build_specs() if tool.name not in disabled}
