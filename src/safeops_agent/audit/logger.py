from __future__ import annotations

import hashlib
import json
import os
import platform
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    MAX_BACKUPS: int = 5
    GENESIS_HASH: str = "0" * 64

    def __init__(self, path: Path | str = "data/audit.log", source: str = "safeops-agent") -> None:
        self.path = Path(path)
        self.source = source
        self._lock = threading.Lock()

    def record(self, event: dict[str, Any]) -> None:
        """追加一条审计事件，并接入防篡改哈希链。

        entry_hash = SHA-256(含 prev_hash 的事件规范化 JSON)，
        prev_hash 指向上一条的 entry_hash（文件轮转后从创世哈希重新起链）。
        改动任意历史事件的内容或删除中间事件都会破坏链条，可由 verify() 检出。
        """
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            payload = {
                "event_id": uuid.uuid4().hex,
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": self.source,
                "host": platform.node(),
                "pid": os.getpid(),
                **event,
            }
            payload["prev_hash"] = self._last_entry_hash()
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            payload["entry_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def verify(self) -> dict[str, Any]:
        """校验当前审计文件的哈希链完整性。

        返回 {ok, checked, legacy, first_bad_line, reason}。
        legacy 为启用哈希链之前写入的无哈希事件数（仅允许出现在文件头部）。
        """
        if not self.path.exists():
            return {"ok": True, "checked": 0, "legacy": 0, "first_bad_line": None,
                    "reason": "审计文件不存在（空日志视为完整）"}
        checked = 0
        legacy = 0
        prev_hash: str | None = None
        with self.path.open(encoding="utf-8") as file:
            for line_no, raw in enumerate(file, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "存在无法解析的事件行"}
                entry_hash = event.pop("entry_hash", None)
                if entry_hash is None:
                    if checked:
                        return {"ok": False, "checked": checked, "legacy": legacy,
                                "first_bad_line": line_no,
                                "reason": "哈希链启用后出现无哈希事件（疑似删改）"}
                    legacy += 1
                    continue
                recomputed = hashlib.sha256(
                    json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()
                if recomputed != entry_hash:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "事件内容与哈希不符（内容被篡改）"}
                if prev_hash is not None and event.get("prev_hash") != prev_hash:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "链条断裂（事件被删除或重排）"}
                prev_hash = entry_hash
                checked += 1
        return {"ok": True, "checked": checked, "legacy": legacy, "first_bad_line": None, "reason": None}

    def _last_entry_hash(self) -> str:
        if not self.path.exists():
            return self.GENESIS_HASH
        lines = self._tail(1)
        if lines:
            try:
                last = json.loads(lines[-1])
                entry_hash = last.get("entry_hash")
                if isinstance(entry_hash, str) and entry_hash:
                    return entry_hash
            except json.JSONDecodeError:
                pass
        return self.GENESIS_HASH

    def _rotate_if_needed(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size < self.MAX_FILE_SIZE:
                return
        except OSError:
            return
        for i in range(self.MAX_BACKUPS - 1, 0, -1):
            src = self.path.with_suffix(f".log.{i}")
            dst = self.path.with_suffix(f".log.{i + 1}")
            if src.exists():
                src.replace(dst)
        backup = self.path.with_suffix(".log.1")
        self.path.replace(backup)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        limit = max(1, min(int(limit), 200))
        lines = self._tail(limit)
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"malformed": True, "raw": line})
        return events

    def _tail(self, n: int, block_size: int = 4096) -> list[str]:
        with self.path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return []
            data = b""
            pos = size
            while pos > 0 and data.count(b"\n") <= n:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                data = f.read(read_size) + data
            lines = data.decode("utf-8", errors="ignore").splitlines()
            return lines[-n:]
