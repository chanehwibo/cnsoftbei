"""可回滚的变更操作：在受管工作区内做真实的快照/写入/回滚。

安全设计：
- 所有写入被限制在项目内的受管工作区 `data/managed/`，杜绝越权写系统文件；
  文件名仅允许安全标识符，禁止路径穿越（`/`、`\\`、`..`）。
- 每次写入前自动对现有内容打快照（`data/snapshots/`），回滚即恢复快照，
  是可真正执行的逆操作，而非仅给建议。
- 服务生命周期（start/stop/restart）为不可逆或需系统权限的操作，
  统一附带 dry-run 预案与逆操作建议，交由确认后执行。
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from safeops_agent.config import PROJECT_ROOT
from .models import ToolResult

MANAGED_ROOT = PROJECT_ROOT / "data" / "managed"
SNAPSHOT_ROOT = PROJECT_ROOT / "data" / "snapshots"
MAX_CONTENT_LENGTH = 64 * 1024
MAX_SNAPSHOTS = 200
LOCK_TIMEOUT_SECONDS = 5.0
_STORAGE_LOCK = threading.Lock()


def _safe_name(name: str) -> str | None:
    """校验受管文件名：非空、无路径分隔符、无穿越。返回规范名或 None。"""
    name = name.strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not all(char in allowed for char in name):
        return None
    return name


def _managed_path(name: str) -> Path | None:
    safe = _safe_name(name)
    if safe is None:
        return None
    target = (MANAGED_ROOT / safe).resolve()
    if not target.is_relative_to(MANAGED_ROOT.resolve()):
        return None
    return target


def _snapshot_index() -> Path:
    return SNAPSHOT_ROOT / "index.jsonl"


def apply_managed_file(args: dict[str, Any]) -> ToolResult:
    """写入受管文件，写入前对旧内容打快照，返回快照 ID 供回滚。"""
    name = str(args.get("name", ""))
    content = str(args.get("content", ""))
    encoded_content = content.encode("utf-8")
    if len(encoded_content) > MAX_CONTENT_LENGTH:
        return ToolResult(ok=False, summary="内容过大，已拒绝写入",
                          error=f"content 超过 {MAX_CONTENT_LENGTH} 字节上限")
    target = _managed_path(name)
    if target is None:
        return ToolResult(ok=False, summary="受管文件名非法", error="name 含非法字符或路径穿越")

    with _operations_lock():
        MANAGED_ROOT.mkdir(parents=True, exist_ok=True)
        existed = target.is_file()
        previous = target.read_bytes() if existed else b""
        snapshot_id = f"{target.name}.{int(time.time() * 1000)}.{uuid.uuid4().hex}"
        snapshot_file = SNAPSHOT_ROOT / snapshot_id
        # 记录旧内容快照（不存在旧文件也记录一条空快照，回滚即删除新建文件）
        _atomic_write_bytes(snapshot_file, previous)
        _append_index({
            "snapshot_id": snapshot_id,
            "name": target.name,
            "existed_before": existed,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        _atomic_write_bytes(target, encoded_content)
    return ToolResult(
        ok=True,
        summary=f"已写入受管文件 {target.name}，可用快照 {snapshot_id} 回滚",
        data={
            "path": str(target),
            "snapshot_id": snapshot_id,
            "existed_before": existed,
            "bytes_written": len(content.encode("utf-8")),
            "rollback": {"tool": "file.rollback", "args": {"snapshot_id": snapshot_id}},
        },
    )


def rollback_managed_file(args: dict[str, Any]) -> ToolResult:
    """按快照 ID 恢复受管文件到写入前状态（真实逆操作）。"""
    snapshot_id = str(args.get("snapshot_id", "")).strip()
    if not snapshot_id or "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        return ToolResult(ok=False, summary="快照 ID 非法", error="snapshot_id 含非法字符")
    with _operations_lock():
        record = _find_index(snapshot_id)
        if record is None:
            return ToolResult(ok=False, summary="未找到对应快照", error=f"snapshot_id={snapshot_id}")
        snapshot_file = (SNAPSHOT_ROOT / snapshot_id).resolve()
        if not snapshot_file.is_relative_to(SNAPSHOT_ROOT.resolve()) or not snapshot_file.is_file():
            return ToolResult(ok=False, summary="快照文件缺失", error=f"snapshot_id={snapshot_id}")

        target = (MANAGED_ROOT / record["name"]).resolve()
        if not target.is_relative_to(MANAGED_ROOT.resolve()):
            return ToolResult(ok=False, summary="受管目标非法", error="回滚目标越界")

        if not record.get("existed_before", False):
            # 写入前文件不存在，回滚即删除新建文件
            if target.is_file():
                target.unlink()
            return ToolResult(ok=True, summary=f"已回滚：删除新建文件 {target.name}",
                              data={"restored": True, "action": "deleted", "name": target.name})
        _atomic_write_bytes(target, snapshot_file.read_bytes())
        return ToolResult(ok=True, summary=f"已回滚受管文件 {target.name} 到写入前状态",
                          data={"restored": True, "action": "restored", "name": target.name})


def list_managed_files(_: dict[str, Any]) -> ToolResult:
    """列出受管工作区文件与可用快照数量。"""
    with _operations_lock():
        files = []
        if MANAGED_ROOT.is_dir():
            files = sorted(p.name for p in MANAGED_ROOT.iterdir() if p.is_file())
        snapshots = 0
        if _snapshot_index().is_file():
            with _snapshot_index().open(encoding="utf-8") as fh:
                snapshots = sum(1 for line in fh if line.strip())
    return ToolResult(ok=True, summary=f"受管文件 {len(files)} 个，历史快照 {snapshots} 条",
                      data={"managed_root": str(MANAGED_ROOT), "files": files, "snapshots": snapshots})


def _append_index(record: dict[str, Any]) -> None:
    index = _snapshot_index()
    existing = index.read_text(encoding="utf-8") if index.is_file() else ""
    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    content += json.dumps(record, ensure_ascii=False) + "\n"
    _atomic_write_bytes(index, content.encode("utf-8"))
    _prune_snapshots()


def _prune_snapshots(limit: int = MAX_SNAPSHOTS) -> None:
    """快照只增不减会无限膨胀：超过上限时删除最旧快照并重写索引。"""
    index = _snapshot_index()
    if not index.is_file():
        return
    lines = [line for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) <= limit:
        return
    dropped, kept = lines[:-limit], lines[-limit:]
    for line in dropped:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        snapshot_id = str(record.get("snapshot_id", ""))
        if not snapshot_id:
            continue
        snapshot_file = (SNAPSHOT_ROOT / snapshot_id).resolve()
        if snapshot_file.is_relative_to(SNAPSHOT_ROOT.resolve()) and snapshot_file.is_file():
            snapshot_file.unlink(missing_ok=True)
    _atomic_write_bytes(index, ("\n".join(kept) + "\n").encode("utf-8"))


def _find_index(snapshot_id: str) -> dict[str, Any] | None:
    index = _snapshot_index()
    if not index.is_file():
        return None
    with index.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("snapshot_id") == snapshot_id:
                return record
    return None


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _operations_lock():
    """串行化线程与进程间的快照/索引/目标文件事务。"""
    with _STORAGE_LOCK:
        SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        lock_path = SNAPSHOT_ROOT / ".operations.lock"
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(descriptor, str(os.getpid()).encode("ascii"))
            except FileExistsError:
                try:
                    stale = time.time() - lock_path.stat().st_mtime > LOCK_TIMEOUT_SECONDS * 4
                except OSError:
                    stale = False
                if stale:
                    lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for managed file process lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            lock_path.unlink(missing_ok=True)
