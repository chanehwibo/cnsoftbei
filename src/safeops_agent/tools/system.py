from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import ToolResult


def _run_command(command: list[str], timeout: int = 5) -> tuple[bool, str]:
    """统一子进程执行入口：绝对路径定位、不经 shell、强制超时。

    只读采集与经确认放行的变更命令（systemctl start/stop/restart）都从这里走。
    """
    executable = shutil.which(command[0])
    if executable is None:
        return False, f"command not found: {command[0]}"
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"command timeout: {' '.join(command)}"
    output = (completed.stdout or completed.stderr).strip()
    return completed.returncode == 0, output


def get_system_info(_: dict[str, Any]) -> ToolResult:
    os_release = _read_os_release()
    data = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "os_release": os_release,
    }
    distro = os_release.get("PRETTY_NAME") or data["system"]
    return ToolResult(ok=True, summary=f"系统信息采集完成：{distro} / {data['machine']}", data=data)


def get_resource_usage(_: dict[str, Any]) -> ToolResult:
    cpu = _read_cpu_load()
    memory = _read_memory()
    disk = _read_disk("/")
    data = {"cpu": cpu, "memory": memory, "disk": disk}
    return ToolResult(ok=True, summary="CPU、内存和磁盘指标采集完成", data=data)


def list_processes(args: dict[str, Any]) -> ToolResult:
    limit = int(args.get("limit", 10))
    limit = max(1, min(limit, 50))
    if platform.system().lower() == "windows":
        ok, output = _run_command(["tasklist"])
        if not ok:
            return ToolResult(ok=False, summary="进程列表采集失败", error=output)
        lines = output.splitlines()[: limit + 3]
    else:
        ok, output = _run_command(["ps", "-eo", "pid,ppid,comm,%cpu,%mem", "--sort=-%cpu"])
        if not ok:
            return ToolResult(ok=False, summary="进程列表采集失败", error=output)
        lines = output.splitlines()[: limit + 1]
    return ToolResult(ok=True, summary=f"已获取前 {limit} 条进程信息", data={"lines": lines})


def inspect_recent_errors(args: dict[str, Any]) -> ToolResult:
    lines = int(args.get("lines", 100))
    lines = max(10, min(lines, 500))
    if platform.system().lower() == "windows":
        return ToolResult(
            ok=True,
            summary="当前为 Windows 开发环境，日志分析工具将在麒麟/Linux 环境使用 journalctl",
            data={"lines": []},
        )
    ok, output = _run_command(["journalctl", "-p", "err", "-n", str(lines), "--no-pager"], timeout=8)
    if not ok:
        return ToolResult(ok=False, summary="系统错误日志读取失败", error=output)
    return ToolResult(ok=True, summary=f"已读取最近 {lines} 条系统错误日志", data={"output": output})


def get_service_status(args: dict[str, Any]) -> ToolResult:
    service = str(args.get("service", "")).strip()
    if not service:
        return ToolResult(ok=False, summary="缺少服务名", error="service is required")
    if not _safe_service_name(service):
        return ToolResult(ok=False, summary="服务名不合法", error="service name contains unsupported characters")
    if platform.system().lower() == "windows":
        return ToolResult(
            ok=True,
            summary="当前为 Windows 开发环境，服务状态工具将在麒麟/Linux 环境使用 systemctl",
            data={"service": service},
        )
    ok, output = _run_command(["systemctl", "status", service, "--no-pager"], timeout=8)
    return ToolResult(
        ok=ok,
        summary=f"服务 {service} 状态查询完成" if ok else f"服务 {service} 状态查询失败",
        data={"service": service, "output": output} if ok else {"service": service},
        error=None if ok else output,
    )


_SERVICE_VERBS = {"start": "启动", "stop": "停止", "restart": "重启"}
_SERVICE_INVERSE = {"start": "stop", "stop": "start", "restart": "restart"}


def restart_service(args: dict[str, Any]) -> ToolResult:
    return _service_lifecycle(args, action="restart")


def _service_lifecycle(args: dict[str, Any], action: str) -> ToolResult:
    """服务生命周期动作（start/stop/restart）：跨平台守护 + 逆操作建议。

    restart 无严格逆操作，回滚建议为结合 service.status 与日志核查后再次重启。
    该 handler 仅在策略引擎确认放行（中风险已确认）后才会被调用。
    """
    verb = _SERVICE_VERBS[action]
    inverse = _SERVICE_INVERSE[action]
    service = str(args.get("service", "")).strip()
    if not service:
        return ToolResult(ok=False, summary="缺少服务名", error="service is required")
    if not _safe_service_name(service):
        return ToolResult(ok=False, summary="服务名不合法", error="service name contains unsupported characters")
    rollback = {"tool": f"service.{inverse}", "args": {"service": service}}
    if platform.system().lower() == "windows":
        return ToolResult(
            ok=True,
            summary=f"当前为 Windows 开发环境，将在麒麟/Linux 环境使用 systemctl {action} {service}",
            data={"service": service, "action": action, "rollback": rollback},
        )
    ok, output = _run_command(["systemctl", action, service], timeout=15)
    return ToolResult(
        ok=ok,
        summary=f"服务 {service} 已{verb}" if ok else f"服务 {service} {verb}失败",
        data={"service": service, "action": action, "output": output, "rollback": rollback} if ok
        else {"service": service, "action": action},
        error=None if ok else output,
    )


def start_service(args: dict[str, Any]) -> ToolResult:
    return _service_lifecycle(args, action="start")


def stop_service(args: dict[str, Any]) -> ToolResult:
    return _service_lifecycle(args, action="stop")


def list_network_connections(args: dict[str, Any]) -> ToolResult:
    limit = _bounded_int(args.get("limit", 50), 1, 200)
    if platform.system().lower() == "windows":
        ok, output = _run_command(["netstat", "-ano"], timeout=8)
    else:
        ok, output = _run_command(["ss", "-tunap"], timeout=8)
        if not ok:
            ok, output = _run_command(["netstat", "-tunap"], timeout=8)
    if not ok:
        return ToolResult(ok=False, summary="网络连接采集失败", error=output)
    lines = output.splitlines()[: limit + 2]
    return ToolResult(ok=True, summary=f"已获取前 {limit} 条网络连接信息", data={"lines": lines})


def list_listening_ports(args: dict[str, Any]) -> ToolResult:
    limit = _bounded_int(args.get("limit", 50), 1, 200)
    if platform.system().lower() == "windows":
        ok, output = _run_command(["netstat", "-ano"], timeout=8)
        if ok:
            lines = [line for line in output.splitlines() if "LISTENING" in line.upper()]
        else:
            lines = []
    else:
        ok, output = _run_command(["ss", "-lntup"], timeout=8)
        if not ok:
            ok, output = _run_command(["netstat", "-lntup"], timeout=8)
        lines = output.splitlines() if ok else []
    if not ok:
        return ToolResult(ok=False, summary="监听端口采集失败", error=output)
    return ToolResult(ok=True, summary=f"已获取前 {limit} 条监听端口信息", data={"lines": lines[: limit + 1]})


def list_disk_partitions(_: dict[str, Any]) -> ToolResult:
    if platform.system().lower() == "windows":
        partitions = []
        skipped = []
        if hasattr(os, "listdrives"):
            roots = list(os.listdrives())
        else:
            roots = [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").exists()]
        get_drive_type = None
        try:
            import ctypes

            get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        except (ImportError, AttributeError, OSError):
            pass
        drive_remote = 4
        for root in roots:
            # 断开的网络映射盘会让 exists()/disk_usage() 阻塞数十秒，网络盘只列出不探测
            if get_drive_type is not None and get_drive_type(root) == drive_remote:
                skipped.append({"mount": root, "note": "network drive, usage not probed"})
                continue
            try:
                usage = shutil.disk_usage(root)
            except OSError:
                continue
            partitions.append(
                {
                    "mount": root,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                }
            )
        data: dict[str, Any] = {"partitions": partitions}
        if skipped:
            data["skipped"] = skipped
        summary = f"已获取 {len(partitions)} 个磁盘挂载点"
        if skipped:
            summary += f"（跳过 {len(skipped)} 个网络盘）"
        return ToolResult(ok=True, summary=summary, data=data)

    ok, output = _run_command(["df", "-hT"], timeout=8)
    if not ok:
        return ToolResult(ok=False, summary="磁盘分区采集失败", error=output)
    return ToolResult(ok=True, summary="已获取磁盘分区信息", data={"output": output})


def list_users(_: dict[str, Any]) -> ToolResult:
    if platform.system().lower() == "windows":
        return ToolResult(ok=True, summary="已获取当前 Windows 用户", data={"users": [os.getlogin()]})

    passwd = Path("/etc/passwd")
    if not passwd.exists():
        return ToolResult(ok=False, summary="用户列表采集失败", error="/etc/passwd not found")
    users = []
    for line in passwd.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) >= 7:
            users.append({"name": parts[0], "uid": parts[2], "gid": parts[3], "home": parts[5], "shell": parts[6]})
    return ToolResult(ok=True, summary=f"已获取 {len(users)} 个本地用户", data={"users": users})


def list_cron_jobs(_: dict[str, Any]) -> ToolResult:
    if platform.system().lower() == "windows":
        return ToolResult(ok=True, summary="当前为 Windows 开发环境，定时任务工具将在麒麟/Linux 环境读取 cron 配置", data={"jobs": []})

    jobs: list[dict[str, Any]] = []
    crontab = Path("/etc/crontab")
    if crontab.exists():
        jobs.append({"source": str(crontab), "content": crontab.read_text(encoding="utf-8", errors="ignore")})
    cron_d = Path("/etc/cron.d")
    if cron_d.exists():
        for item in sorted(cron_d.iterdir()):
            if item.is_file():
                jobs.append({"source": str(item), "content": item.read_text(encoding="utf-8", errors="ignore")})
    ok, output = _run_command(["crontab", "-l"], timeout=5)
    if ok:
        jobs.append({"source": "user-crontab", "content": output})
    return ToolResult(ok=True, summary=f"已获取 {len(jobs)} 组定时任务配置", data={"jobs": jobs})


def list_safe_environment(_: dict[str, Any]) -> ToolResult:
    allowlist = {
        "HOME",
        "HOSTNAME",
        "LANG",
        "LOGNAME",
        "OS",
        "PATH",
        "PROCESSOR_ARCHITECTURE",
        "SHELL",
        "TEMP",
        "TMP",
        "USER",
        "USERNAME",
    }
    values = {key: value for key, value in os.environ.items() if key in allowlist}
    return ToolResult(ok=True, summary=f"已获取 {len(values)} 个安全环境变量", data={"environment": values})


def query_package(args: dict[str, Any]) -> ToolResult:
    package = str(args.get("package", "")).strip()
    if package and not _safe_package_name(package):
        return ToolResult(ok=False, summary="软件包名不合法", error="package name contains unsupported characters")
    if platform.system().lower() == "windows":
        return ToolResult(ok=True, summary="当前为 Windows 开发环境，软件包查询将在麒麟/Linux 环境使用 rpm/dpkg", data={"package": package})

    if shutil.which("rpm"):
        command = ["rpm", "-qa"] if not package else ["rpm", "-q", package]
    elif shutil.which("dpkg-query"):
        command = ["dpkg-query", "-W"] if not package else ["dpkg-query", "-W", package]
    else:
        return ToolResult(ok=False, summary="软件包查询失败", error="rpm and dpkg-query are unavailable")
    ok, output = _run_command(command, timeout=10)
    return ToolResult(
        ok=ok,
        summary="软件包查询完成" if ok else "软件包查询失败",
        data={"package": package, "output": output} if ok else {"package": package},
        error=None if ok else output,
    )


def _read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def _read_cpu_load() -> dict[str, Any]:
    data: dict[str, Any] = {"cpu_count": os.cpu_count()}
    try:
        load1, load5, load15 = os.getloadavg()
        data["load_average"] = {"1m": load1, "5m": load5, "15m": load15}
    except (AttributeError, OSError):
        data["load_average"] = None
    return data


def _read_memory() -> dict[str, Any]:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {"available": None, "note": "memory detail requires Linux /proc"}
    values: dict[str, int] = {}
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            values[parts[0].rstrip(":")] = int(parts[1])
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used_percent = None
    if total and available is not None:
        used_percent = round((total - available) / total * 100, 2)
    return {"total_kb": total, "available_kb": available, "used_percent": used_percent}


def _read_disk(path: str) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(usage.used / usage.total * 100, 2) if usage.total else None,
    }


def _safe_service_name(value: str) -> bool:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@_.-")
    return bool(value) and all(char in allowed for char in value)


def _safe_package_name(value: str) -> bool:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+_.:-")
    return bool(value) and all(char in allowed for char in value)


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))
