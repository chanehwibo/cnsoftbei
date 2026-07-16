from __future__ import annotations

from typing import Any

from .models import ToolResult
from .system import (
    get_resource_usage,
    get_service_status,
    inspect_recent_errors,
    list_disk_partitions,
    list_listening_ports,
)


def diagnose_overview(_: dict[str, Any]) -> ToolResult:
    resources = get_resource_usage({})
    ports = list_listening_ports({"limit": 20})
    diagnosis = _base_diagnosis(
        scenario="系统概览诊断",
        symptom="已完成资源指标和监听端口的基础采集。",
        possible_causes=[
            "如果资源使用率过高，可能存在异常进程、业务流量突增或容量不足。",
            "如果监听端口异常，可能存在服务配置错误、端口冲突或未授权服务。",
        ],
        recommended_actions=[
            "继续执行 CPU/内存、磁盘、端口、服务或日志专项诊断。",
            "先执行只读排查，再根据风险等级决定是否进入变更流程。",
        ],
        evidence={"resources": resources.data, "listening_ports": ports.data},
    )
    failures = [result for result in (resources, ports) if not result.ok]
    return ToolResult(
        ok=not failures,
        summary="系统概览诊断完成" if not failures else "系统概览诊断采集失败",
        data={"diagnosis": diagnosis},
        error="；".join(result.error or result.summary for result in failures) or None,
    )


def diagnose_resources(_: dict[str, Any]) -> ToolResult:
    result = get_resource_usage({})
    disk = result.data.get("disk", {}) if result.data else {}
    disk_used = disk.get("used_percent")
    possible_causes = [
        "业务进程 CPU 占用过高。",
        "内存缓存、日志或临时文件增长导致可用资源下降。",
        "磁盘使用率持续升高导致服务写入失败。",
    ]
    recommended_actions = [
        "查看进程列表并按 CPU/内存占用排序。",
        "检查最近错误日志中是否存在 OOM、磁盘写满或服务异常。",
        "如需清理或重启服务，先进入中风险确认流程。",
    ]
    if isinstance(disk_used, (int, float)) and disk_used >= 85:
        possible_causes.insert(0, f"根分区使用率已达到 {disk_used}%，存在容量风险。")
        recommended_actions.insert(0, "优先定位大文件、日志目录和临时目录占用。")
    diagnosis = _base_diagnosis(
        scenario="CPU/内存/磁盘资源诊断",
        symptom="已采集 CPU、内存和磁盘基础指标。",
        possible_causes=possible_causes,
        recommended_actions=recommended_actions,
        evidence=result.data,
    )
    return ToolResult(
        ok=result.ok,
        summary="资源诊断完成" if result.ok else "资源诊断采集失败",
        data={"diagnosis": diagnosis},
        error=result.error if not result.ok else None,
    )


def diagnose_disk(_: dict[str, Any]) -> ToolResult:
    partitions = list_disk_partitions({})
    diagnosis = _base_diagnosis(
        scenario="磁盘空间诊断",
        symptom="已采集磁盘分区和挂载点信息。",
        possible_causes=[
            "日志文件、缓存文件或备份文件持续增长。",
            "应用写入目录未做容量限制。",
            "磁盘分区规划不足或挂载点使用不均衡。",
        ],
        recommended_actions=[
            "检查 `/var/log`、应用日志目录、临时目录和备份目录。",
            "优先执行只读定位命令，确认后再进行清理。",
            "对生产环境清理操作保留审计记录和回滚方案。",
        ],
        evidence=partitions.data,
    )
    return ToolResult(
        ok=partitions.ok,
        summary="磁盘诊断完成" if partitions.ok else "磁盘诊断采集失败",
        data={"diagnosis": diagnosis},
        error=partitions.error if not partitions.ok else None,
    )


def diagnose_network_ports(args: dict[str, Any]) -> ToolResult:
    ports = list_listening_ports({"limit": args.get("limit", 50)})
    diagnosis = _base_diagnosis(
        scenario="端口占用诊断",
        symptom="已采集监听端口列表。",
        possible_causes=[
            "目标端口已被其他进程占用。",
            "服务启动后监听地址或端口与预期不一致。",
            "防火墙、服务配置或权限导致端口未正常监听。",
        ],
        recommended_actions=[
            "确认端口、PID 和服务名是否匹配。",
            "查看对应服务状态和最近错误日志。",
            "涉及停止或重启服务时进入中风险确认流程。",
        ],
        evidence=ports.data,
    )
    return ToolResult(
        ok=ports.ok,
        summary="端口诊断完成" if ports.ok else "端口诊断采集失败",
        data={"diagnosis": diagnosis},
        error=ports.error if not ports.ok else None,
    )


def diagnose_service(args: dict[str, Any]) -> ToolResult:
    service = str(args.get("service", "")).strip()
    status = get_service_status({"service": service}) if service else ToolResult(ok=False, summary="缺少服务名", error="service is required")
    diagnosis = _base_diagnosis(
        scenario="服务可用性诊断",
        symptom=f"已查询服务 `{service or '未指定'}` 的状态。",
        possible_causes=[
            "服务未安装、未启动或启动失败。",
            "配置文件错误、端口冲突或依赖服务不可用。",
            "权限不足导致服务状态无法完整读取。",
        ],
        recommended_actions=[
            "先查看服务状态和最近错误日志。",
            "确认配置文件和监听端口是否符合预期。",
            "如需重启服务，先查看 Dry-run 预案并显式确认。",
        ],
        evidence=status.data if status.data else {"error": status.error, "summary": status.summary},
        suggested_followups=[
            f"查看 {service} 服务状态" if service else "查看目标服务状态",
            "分析最近系统错误日志",
            f"重启 {service} 服务" if service else "重启目标服务",
        ],
    )
    return ToolResult(
        ok=status.ok,
        summary="服务诊断完成" if status.ok else "服务诊断采集失败",
        data={"diagnosis": diagnosis},
        error=status.error if not status.ok else None,
    )


def diagnose_logs(args: dict[str, Any]) -> ToolResult:
    logs = inspect_recent_errors({"lines": args.get("lines", 100)})
    diagnosis = _base_diagnosis(
        scenario="错误日志诊断",
        symptom="已读取最近系统错误日志或环境兼容说明。",
        possible_causes=[
            "服务启动失败、依赖不可用或配置错误。",
            "资源不足导致进程被系统终止。",
            "权限、文件路径或网络访问异常导致错误。",
        ],
        recommended_actions=[
            "按时间顺序关联服务状态、端口监听和资源指标。",
            "优先定位重复出现的错误码、服务名和路径。",
            "涉及变更操作前生成 Dry-run 预案并记录审计。",
        ],
        evidence=logs.data if logs.data else {"error": logs.error, "summary": logs.summary},
    )
    return ToolResult(
        ok=logs.ok,
        summary="日志诊断完成" if logs.ok else "日志诊断采集失败",
        data={"diagnosis": diagnosis},
        error=logs.error if not logs.ok else None,
    )


def _base_diagnosis(
    scenario: str,
    symptom: str,
    possible_causes: list[str],
    recommended_actions: list[str],
    evidence: dict[str, Any] | None,
    suggested_followups: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "symptom": symptom,
        "possible_causes": possible_causes,
        "recommended_actions": recommended_actions,
        "risk": "LOW",
        "requires_confirmation": False,
        "suggested_followups": suggested_followups or [],
        "evidence": evidence or {},
    }
