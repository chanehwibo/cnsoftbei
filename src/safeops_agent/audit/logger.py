from __future__ import annotations

import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    MAX_BACKUPS: int = 5

    def __init__(self, path: Path | str = "data/audit.log", source: str = "safeops-agent") -> None:
        self.path = Path(path)
        self.source = source

    def record(self, event: dict[str, Any]) -> None:
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
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

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
