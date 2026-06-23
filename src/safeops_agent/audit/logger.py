from __future__ import annotations

import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, path: Path | str = "data/audit.log", source: str = "safeops-agent") -> None:
        self.path = Path(path)
        self.source = source

    def record(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        limit = max(1, min(int(limit), 200))
        lines = self.path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"malformed": True, "raw": line})
        return events
