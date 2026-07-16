from __future__ import annotations

import re
from typing import Any

from .models import ToolResult
from .system import (
    get_resource_usage,
    get_service_status,
    inspect_recent_errors,
    list_disk_partitions,
    list_listening_ports,
)


RESOURCE_WARNING_PERCENT = 80.0
RESOURCE_CRITICAL_PERCENT = 90.0
CPU_LOAD_WARNING_RATIO = 0.75
CPU_LOAD_CRITICAL_RATIO = 1.0
DISK_WARNING_PERCENT = 85.0
DISK_CRITICAL_PERCENT = 95.0
_SEVERITY_ORDER = {"healthy": 0, "unknown": 1, "warning": 2, "critical": 3}


def diagnose_overview(_: dict[str, Any]) -> ToolResult:
    resources = get_resource_usage({})
    ports = list_listening_ports({"limit": 20})
    resource_analysis = _analyze_resources(resources.data if resources.ok else {})
    port_lines = _port_lines(ports.data)
    causes = list(resource_analysis["causes"] if resource_analysis["severity"] in {"warning", "critical"} else [])
    actions = list(resource_analysis["actions"] if causes else [])
    severity = resource_analysis["severity"]

    if ports.ok and not port_lines:
        causes.append("本次采集未发现监听端口；若主机应提供服务，相关服务可能未启动或未成功绑定端口。")
        actions.append("核对预期服务状态及其目标监听端口。")
        severity = _higher_severity(severity, "warning")
    elif not ports.ok:
        causes.append("监听端口采集失败，当前无法排除端口冲突或服务未监听。")
        actions.append("检查端口采集命令是否可用以及当前账户的读取权限。")
        severity = _higher_severity(severity, "unknown")

    if not causes:
        if severity == "unknown":
            causes = [f"资源指标不完整；已发现 {len(port_lines)} 条监听记录，但当前证据不足以判断整体健康状态。"]
            actions = ["补充当前平台缺失的资源指标后再判断。"]
        else:
            causes = [f"资源指标未超过预警阈值，且已发现 {len(port_lines)} 条监听记录，当前未见明确异常。"]
            actions = ["保持只读监控；出现具体症状时再执行对应专项诊断。"]

    diagnosis = _base_diagnosis(
        scenario="系统概览诊断",
        symptom=f"资源采集：{resource_analysis['symptom']}；监听记录 {len(port_lines)} 条。",
        possible_causes=causes,
        recommended_actions=_unique(actions),
        evidence={
            "resources": resources.data,
            "listening_ports": ports.data,
            "evaluated_thresholds": _threshold_evidence(),
        },
        severity=severity,
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
    analysis = _analyze_resources(result.data if result.ok else {})
    diagnosis = _base_diagnosis(
        scenario="CPU/内存/磁盘资源诊断",
        symptom=analysis["symptom"],
        possible_causes=analysis["causes"],
        recommended_actions=analysis["actions"],
        evidence={**(result.data or {}), "evaluated_thresholds": _threshold_evidence()},
        severity=analysis["severity"],
    )
    return ToolResult(
        ok=result.ok,
        summary="资源诊断完成" if result.ok else "资源诊断采集失败",
        data={"diagnosis": diagnosis},
        error=result.error if not result.ok else None,
    )


def diagnose_disk(_: dict[str, Any]) -> ToolResult:
    partitions = list_disk_partitions({})
    entries, skipped = _disk_usage_entries(partitions.data if partitions.ok else {})
    causes: list[str] = []
    actions: list[str] = []
    severity = "healthy" if entries else "unknown"
    for entry in entries:
        used = entry["used_percent"]
        mount = entry["mount"]
        if used >= DISK_CRITICAL_PERCENT:
            severity = _higher_severity(severity, "critical")
            causes.append(f"挂载点 {mount} 使用率为 {used:.1f}%，已达到严重容量阈值。")
            actions.append(f"立即只读定位 {mount} 下增长最快的大文件、日志、缓存和备份。")
        elif used >= DISK_WARNING_PERCENT:
            severity = _higher_severity(severity, "warning")
            causes.append(f"挂载点 {mount} 使用率为 {used:.1f}%，已达到容量预警阈值。")
            actions.append(f"检查 {mount} 的容量趋势和主要占用目录。")
    if skipped:
        severity = _higher_severity(severity, "unknown")
        actions.append(f"另有 {len(skipped)} 个未探测挂载点，需要在可访问环境中补充核查。")
    if not causes:
        if entries:
            maximum = max(entries, key=lambda item: item["used_percent"])
            causes = [
                f"已采集挂载点均低于 {DISK_WARNING_PERCENT:.0f}% 预警线；最高为 "
                f"{maximum['mount']} {maximum['used_percent']:.1f}%，当前未见容量瓶颈。"
            ]
            actions.insert(0, "继续监控磁盘增长趋势，无需立即清理。")
        else:
            causes = ["未获得可计算使用率的挂载点数据，当前无法判断磁盘容量风险。"]
            actions.insert(0, "确认 df 或平台磁盘采集接口可用后重新诊断。")

    diagnosis = _base_diagnosis(
        scenario="磁盘空间诊断",
        symptom=f"已分析 {len(entries)} 个可计算使用率的挂载点。",
        possible_causes=causes,
        recommended_actions=_unique(actions),
        evidence={
            **(partitions.data or {}),
            "evaluated_partitions": entries,
            "warning_percent": DISK_WARNING_PERCENT,
            "critical_percent": DISK_CRITICAL_PERCENT,
        },
        severity=severity,
    )
    return ToolResult(
        ok=partitions.ok,
        summary="磁盘诊断完成" if partitions.ok else "磁盘诊断采集失败",
        data={"diagnosis": diagnosis},
        error=partitions.error if not partitions.ok else None,
    )


def diagnose_network_ports(args: dict[str, Any]) -> ToolResult:
    ports = list_listening_ports({"limit": args.get("limit", 50)})
    lines = _port_lines(ports.data)
    target = _optional_port(args.get("port"))
    matches = [line for line in lines if target is not None and _line_has_port(line, target)]

    if not ports.ok:
        severity = "unknown"
        causes = ["监听端口采集失败，无法基于实际监听状态判断。"]
        actions = ["检查 ss/netstat 是否可用以及当前账户的读取权限。"]
    elif target is None:
        severity = "unknown"
        causes = [f"已采集 {len(lines)} 条监听记录，但未指定目标端口，无法判定具体端口冲突。"]
        actions = ["提供目标端口后重新诊断，并核对对应 PID 或进程名。"]
    elif matches:
        severity = "warning"
        causes = [f"目标端口 {target} 命中 {len(matches)} 条实际监听记录，若新服务需要该端口则会发生占用冲突。"]
        actions = ["核对命中记录中的 PID/进程是否为预期服务，再决定是否变更服务配置。"]
    else:
        severity = "healthy"
        causes = [f"目标端口 {target} 未出现在本次 {len(lines)} 条监听记录中，当前未发现占用冲突。"]
        actions = ["若服务本应已启动，请继续检查服务状态、绑定地址和最近错误日志。"]

    diagnosis = _base_diagnosis(
        scenario="端口占用诊断",
        symptom=f"已采集 {len(lines)} 条监听记录" + (f"，目标端口为 {target}" if target is not None else "，未指定目标端口") + "。",
        possible_causes=causes,
        recommended_actions=actions,
        evidence={**(ports.data or {}), "target_port": target, "matched_lines": matches},
        severity=severity,
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
    text = " ".join(
        str(value) for value in (
            status.summary,
            status.error or "",
            (status.data or {}).get("output", ""),
        )
    ).lower()

    if not service:
        severity = "unknown"
        causes = ["未指定服务名，无法采集并判断具体服务状态。"]
        actions = ["提供合法服务名后重新诊断。"]
    elif not status.ok:
        severity = "critical"
        if any(marker in text for marker in ("could not be found", "not-found", "not found")):
            causes = [f"实际状态输出表明服务 {service} 未安装或单元不存在。"]
            actions = ["核对服务单元名称和软件包安装状态。"]
        elif any(marker in text for marker in ("inactive", "dead", "failed")):
            causes = [f"实际状态输出表明服务 {service} 未运行或启动失败。"]
            actions = ["检查该服务最近错误日志、配置校验结果和依赖单元状态。"]
        elif any(marker in text for marker in ("permission denied", "access denied")):
            causes = [f"当前账户没有读取服务 {service} 完整状态的权限。"]
            actions = ["使用具备最小只读权限的账户重新采集服务状态。"]
        else:
            causes = [f"服务 {service} 状态采集失败：{status.error or status.summary}。"]
            actions = ["检查 systemctl 可用性并读取该服务的最近错误日志。"]
    elif "output" not in (status.data or {}):
        severity = "unknown"
        causes = [f"当前开发平台未提供服务 {service} 的实际 systemd 状态，无法判断是否运行。"]
        actions = ["在目标麒麟/Linux 环境重新执行服务诊断。"]
    else:
        severity = "healthy"
        causes = [f"服务 {service} 的实际状态查询成功，当前未发现不可用证据。"]
        actions = ["如仍有业务异常，继续核对监听端口和最近错误日志。"]

    diagnosis = _base_diagnosis(
        scenario="服务可用性诊断",
        symptom=f"已查询服务 `{service or '未指定'}` 的状态：{status.summary}。",
        possible_causes=causes,
        recommended_actions=actions,
        evidence=status.data if status.data else {"error": status.error, "summary": status.summary},
        suggested_followups=[
            f"查看 {service} 服务状态" if service else "查看目标服务状态",
            "分析最近系统错误日志",
            f"重启 {service} 服务" if service else "重启目标服务",
        ],
        severity=severity,
    )
    return ToolResult(
        ok=status.ok,
        summary="服务诊断完成" if status.ok else "服务诊断采集失败",
        data={"diagnosis": diagnosis},
        error=status.error if not status.ok else None,
    )


def diagnose_logs(args: dict[str, Any]) -> ToolResult:
    logs = inspect_recent_errors({"lines": args.get("lines", 100)})
    output = str((logs.data or {}).get("output", ""))
    normalized = output.lower()
    causes: list[str] = []
    actions: list[str] = []

    if not logs.ok:
        severity = "unknown"
        causes = ["错误日志采集失败，无法根据实际日志定位原因。"]
        actions = ["检查 journalctl 可用性和当前账户的日志读取权限。"]
    elif not output.strip() or "-- no entries --" in normalized:
        if "lines" in (logs.data or {}):
            severity = "unknown"
            causes = ["当前开发平台没有可供分析的 systemd 错误日志。"]
            actions = ["在目标麒麟/Linux 环境重新采集，或提供应用日志进行分析。"]
        else:
            severity = "healthy"
            causes = ["本次采集范围内没有错误级别日志，未发现明确日志异常。"]
            actions = ["若症状仍存在，扩大时间范围并检查应用自身日志。"]
    else:
        severity = "warning"
        if any(marker in normalized for marker in ("out of memory", "oom", "killed process")):
            causes.append("实际日志包含 OOM/进程被终止证据，内存压力可能导致服务异常。")
            actions.append("关联检查内存使用率、被终止进程和服务重启时间。")
            severity = "critical"
        if any(marker in normalized for marker in ("no space left", "disk full")):
            causes.append("实际日志包含磁盘空间耗尽证据，写入操作可能失败。")
            actions.append("立即检查相关挂载点使用率并只读定位主要占用目录。")
            severity = "critical"
        if any(marker in normalized for marker in ("permission denied", "access denied")):
            causes.append("实际日志包含权限拒绝证据，服务账户可能缺少目标资源访问权限。")
            actions.append("核对报错路径的属主、权限和服务账户，不要直接扩大权限。")
        if any(marker in normalized for marker in ("connection refused", "timed out", "timeout")):
            causes.append("实际日志包含连接拒绝或超时证据，依赖服务或网络路径可能不可用。")
            actions.append("核对依赖服务状态、目标端口监听和网络可达性。")
        if not causes:
            causes = ["采集结果包含错误级别日志，但未命中 OOM、磁盘、权限或网络特征。"]
            actions = ["按时间、服务名和重复错误码聚类后再定位具体故障。"]

    diagnosis = _base_diagnosis(
        scenario="错误日志诊断",
        symptom=f"日志采集结果：{logs.summary}。",
        possible_causes=causes,
        recommended_actions=_unique(actions),
        evidence=logs.data if logs.data else {"error": logs.error, "summary": logs.summary},
        severity=severity,
    )
    return ToolResult(
        ok=logs.ok,
        summary="日志诊断完成" if logs.ok else "日志诊断采集失败",
        data={"diagnosis": diagnosis},
        error=logs.error if not logs.ok else None,
    )


def _analyze_resources(data: dict[str, Any]) -> dict[str, Any]:
    causes: list[str] = []
    actions: list[str] = []
    measurements: list[str] = []
    severity = "healthy"
    measured = False

    cpu = data.get("cpu", {}) if isinstance(data.get("cpu"), dict) else {}
    loads = cpu.get("load_average") if isinstance(cpu.get("load_average"), dict) else {}
    load1 = loads.get("1m") if isinstance(loads, dict) else None
    cpu_count = cpu.get("cpu_count")
    if _is_number(load1) and _is_number(cpu_count) and cpu_count > 0:
        measured = True
        ratio = float(load1) / float(cpu_count)
        measurements.append(f"1 分钟 CPU 负载 {float(load1):.2f}/{int(cpu_count)} 核（{ratio * 100:.1f}%）")
        if ratio >= CPU_LOAD_CRITICAL_RATIO:
            causes.append("1 分钟 CPU 负载已达到或超过逻辑 CPU 数，存在持续排队或计算饱和风险。")
            actions.append("查看进程列表并按 CPU 占用排序，定位持续高负载进程。")
            severity = "critical"
        elif ratio >= CPU_LOAD_WARNING_RATIO:
            causes.append("1 分钟 CPU 负载超过逻辑 CPU 数的 75%，存在负载升高趋势。")
            actions.append("观察 5/15 分钟负载并核对近期任务或流量变化。")
            severity = "warning"

    for key, label in (("memory", "内存"), ("disk", "根分区")):
        metric = data.get(key, {}) if isinstance(data.get(key), dict) else {}
        used = metric.get("used_percent")
        if not _is_number(used):
            continue
        measured = True
        used_value = float(used)
        measurements.append(f"{label}使用率 {used_value:.1f}%")
        if used_value >= RESOURCE_CRITICAL_PERCENT:
            causes.append(f"{label}使用率已达到 {used_value:.1f}%，超过 {RESOURCE_CRITICAL_PERCENT:.0f}% 严重阈值。")
            action = "定位高内存进程并检查 OOM 日志。" if key == "memory" else "只读定位大文件、日志和临时目录占用。"
            actions.append(action)
            severity = _higher_severity(severity, "critical")
        elif used_value >= RESOURCE_WARNING_PERCENT:
            causes.append(f"{label}使用率已达到 {used_value:.1f}%，超过 {RESOURCE_WARNING_PERCENT:.0f}% 预警阈值。")
            action = "检查进程内存排名和缓存增长趋势。" if key == "memory" else "检查磁盘增长趋势和主要占用目录。"
            actions.append(action)
            severity = _higher_severity(severity, "warning")

    if not causes:
        if measured:
            causes = ["已采集资源指标均未达到预警阈值，当前未发现明确资源瓶颈。"]
            actions = ["保持趋势监控；业务仍异常时继续检查进程、端口和错误日志。"]
        else:
            severity = "unknown"
            causes = ["当前平台未提供可计算的 CPU、内存或磁盘使用率，无法完成阈值判断。"]
            actions = ["在目标麒麟/Linux 环境补充采集后重新诊断。"]

    return {
        "severity": severity,
        "symptom": "；".join(measurements) + "。" if measurements else "未获得可计算的资源指标。",
        "causes": causes,
        "actions": _unique(actions),
    }


def _disk_usage_entries(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Any]]:
    entries: list[dict[str, Any]] = []
    partitions = data.get("partitions", [])
    if isinstance(partitions, list):
        for partition in partitions:
            if not isinstance(partition, dict):
                continue
            total = partition.get("total_bytes")
            used = partition.get("used_bytes")
            if _is_number(total) and total > 0 and _is_number(used):
                entries.append({
                    "mount": str(partition.get("mount", "?")),
                    "used_percent": round(float(used) / float(total) * 100, 2),
                })
    output = data.get("output")
    if isinstance(output, str):
        for line in output.splitlines()[1:]:
            columns = line.split()
            percent = next((item for item in columns if re.fullmatch(r"\d+(?:\.\d+)?%", item)), None)
            if percent and columns:
                entries.append({"mount": columns[-1], "used_percent": float(percent[:-1])})
    skipped = data.get("skipped", [])
    return entries, skipped if isinstance(skipped, list) else []


def _port_lines(data: dict[str, Any] | None) -> list[str]:
    lines = (data or {}).get("lines", [])
    return [str(line) for line in lines] if isinstance(lines, list) else []


def _optional_port(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _line_has_port(line: str, port: int) -> bool:
    return re.search(rf"(?:[:.]){port}(?!\d)", line) is not None


def _threshold_evidence() -> dict[str, float]:
    return {
        "cpu_load_warning_ratio": CPU_LOAD_WARNING_RATIO,
        "cpu_load_critical_ratio": CPU_LOAD_CRITICAL_RATIO,
        "resource_warning_percent": RESOURCE_WARNING_PERCENT,
        "resource_critical_percent": RESOURCE_CRITICAL_PERCENT,
    }


def _higher_severity(current: str, candidate: str) -> str:
    return candidate if _SEVERITY_ORDER[candidate] > _SEVERITY_ORDER[current] else current


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _base_diagnosis(
    scenario: str,
    symptom: str,
    possible_causes: list[str],
    recommended_actions: list[str],
    evidence: dict[str, Any] | None,
    suggested_followups: list[str] | None = None,
    severity: str = "unknown",
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "symptom": symptom,
        "severity": severity,
        "possible_causes": possible_causes,
        "recommended_actions": recommended_actions,
        "risk": "LOW",
        "requires_confirmation": False,
        "suggested_followups": suggested_followups or [],
        "evidence": evidence or {},
    }
