from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    MAX_BACKUPS: int = 5
    GENESIS_HASH: str = "0" * 64
    LOCK_TIMEOUT_SECONDS: float = 5.0
    REDACTED: str = "[REDACTED]"
    SENSITIVE_KEYS = {
        "password",
        "passwd",
        "secret",
        "api_key",
        "authorization",
        "credential",
        "private_key",
        "content",
        "pending_action_id",
    }

    def __init__(self, path: Path | str = "data/audit.log", source: str = "safeops-agent") -> None:
        self.path = Path(path)
        self.source = source
        self._lock = threading.Lock()

    def record(self, event: dict[str, Any]) -> None:
        """追加一条带哈希链、HMAC 签名与持久化锚点的审计事件。"""
        with self._lock:
            with self._process_lock():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed()
                previous_count = self._event_count(self.path)
                sanitized_event = self._redact(event)
                payload = {
                    "event_id": uuid.uuid4().hex,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "source": self.source,
                    "host": platform.node(),
                    "pid": os.getpid(),
                    **sanitized_event,
                }
                payload["prev_hash"] = self._last_entry_hash()
                canonical = self._canonical(payload)
                payload["entry_hash"] = hashlib.sha256(canonical).hexdigest()
                payload["entry_hmac"] = hmac.new(
                    self._load_key(),
                    self._canonical(payload),
                    hashlib.sha256,
                ).hexdigest()
                with self.path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
                    file.flush()
                    os.fsync(file.fileno())
                self._write_anchor(self.path, payload["entry_hash"], previous_count + 1)

    def verify(self) -> dict[str, Any]:
        """校验当前日志及全部轮转日志的链、签名和锚点。"""
        with self._lock:
            with self._process_lock():
                paths = [
                    self.path.with_suffix(f".log.{index}")
                    for index in range(self.MAX_BACKUPS, 0, -1)
                    if self.path.with_suffix(f".log.{index}").exists()
                ]
                if self.path.exists():
                    paths.append(self.path)
                if not paths:
                    return {
                        "ok": True,
                        "checked": 0,
                        "legacy": 0,
                        "segments": 0,
                        "first_bad_line": None,
                        "reason": "审计文件不存在（空日志视为完整）",
                    }
                total_checked = 0
                total_legacy = 0
                for path in paths:
                    report = self._verify_file(path)
                    if not report["ok"]:
                        report["segment"] = path.name
                        report["checked"] += total_checked
                        report["legacy"] += total_legacy
                        report["segments"] = len(paths)
                        return report
                    total_checked += report["checked"]
                    total_legacy += report["legacy"]
                return {
                    "ok": True,
                    "checked": total_checked,
                    "legacy": total_legacy,
                    "segments": len(paths),
                    "first_bad_line": None,
                    "reason": None,
                }

    def _verify_file(self, path: Path) -> dict[str, Any]:
        checked = 0
        legacy = 0
        prev_hash: str | None = None
        key = self._load_key()
        missing = object()
        with path.open(encoding="utf-8") as file:
            for line_no, raw in enumerate(file, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "存在无法解析的事件行"}
                entry_hmac = event.pop("entry_hmac", missing)
                entry_hash = event.pop("entry_hash", None)
                if entry_hash is None:
                    if checked or prev_hash is not None:
                        return {"ok": False, "checked": checked, "legacy": legacy,
                                "first_bad_line": line_no,
                                "reason": "哈希链启用后出现无哈希事件（疑似删改）"}
                    legacy += 1
                    continue
                if entry_hmac is missing:
                    if checked:
                        return {"ok": False, "checked": checked, "legacy": legacy,
                                "first_bad_line": line_no,
                                "reason": "HMAC 签名链启用后出现旧式 SHA 事件（疑似删改）"}
                    recomputed = hashlib.sha256(
                        self._legacy_canonical(event)
                    ).hexdigest()
                else:
                    recomputed = hashlib.sha256(
                        self._canonical(event)
                    ).hexdigest()
                if recomputed != entry_hash:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "事件内容与哈希不符（内容被篡改）"}
                expected_prev = self.GENESIS_HASH if prev_hash is None else prev_hash
                if event.get("prev_hash") != expected_prev:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "链条断裂（事件被删除或重排）"}
                prev_hash = entry_hash
                if entry_hmac is missing:
                    legacy += 1
                    continue
                if not isinstance(entry_hmac, str):
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "事件缺少 HMAC 签名"}
                signed_event = {**event, "entry_hash": entry_hash}
                expected_hmac = hmac.new(
                    key,
                    self._canonical(signed_event),
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(entry_hmac, expected_hmac):
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "first_bad_line": line_no, "reason": "事件 HMAC 签名无效"}
                checked += 1
        anchor = self._read_anchor(path)
        if checked:
            if anchor is None:
                return {"ok": False, "checked": checked, "legacy": legacy,
                        "first_bad_line": None, "reason": "审计锚点缺失"}
            if anchor.get("count") != checked + legacy:
                return {"ok": False, "checked": checked, "legacy": legacy,
                        "first_bad_line": None, "reason": "审计事件数量与锚点不符（疑似截断）"}
            if anchor.get("last_hash") != prev_hash:
                return {"ok": False, "checked": checked, "legacy": legacy,
                        "first_bad_line": None, "reason": "审计末尾哈希与锚点不符（疑似截断）"}
        elif anchor is not None:
            if anchor.get("count") != legacy or (
                prev_hash is not None and anchor.get("last_hash") != prev_hash
            ):
                return {"ok": False, "checked": checked, "legacy": legacy,
                        "first_bad_line": None, "reason": "旧式审计链与已有锚点不符"}
        return {"ok": True, "checked": checked, "legacy": legacy,
                "first_bad_line": None, "reason": None}

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
            src_anchor = self._anchor_path(src)
            dst_anchor = self._anchor_path(dst)
            if src_anchor.exists():
                src_anchor.replace(dst_anchor)
        backup = self.path.with_suffix(".log.1")
        self.path.replace(backup)
        anchor = self._anchor_path(self.path)
        if anchor.exists():
            anchor.replace(self._anchor_path(backup))

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _legacy_canonical(payload: dict[str, Any]) -> bytes:
        """旧版本 SHA 链使用带默认空格的 JSON；仅用于只读兼容校验。"""
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def _redact(cls, value: Any, key: str | None = None) -> Any:
        normalized_key = (key or "").lower()
        if normalized_key in cls.SENSITIVE_KEYS:
            return cls.REDACTED
        if isinstance(value, dict):
            return {str(item_key): cls._redact(item_value, str(item_key))
                    for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        if isinstance(value, tuple):
            return [cls._redact(item) for item in value]
        if not isinstance(value, str):
            return value
        text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", cls.REDACTED, value)
        text = re.sub(r"(?i)\bBearer\s+\S+", f"Bearer {cls.REDACTED}", text)
        text = re.sub(
            r"(?i)\b(password|passwd|api[_-]?key|token|secret)\s*([:=])\s*\S+",
            lambda match: f"{match.group(1)}{match.group(2)}{cls.REDACTED}",
            text,
        )
        return text

    def _key_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.key")

    def _anchor_path(self, path: Path) -> Path:
        return path.with_name(f"{path.name}.anchor.json")

    def _load_key(self) -> bytes:
        configured = os.environ.get("SAFEOPS_AUDIT_HMAC_KEY", "")
        if configured:
            return configured.encode("utf-8")
        path = self._key_path()
        if path.is_file():
            return path.read_bytes()
        path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_hex(32).encode("ascii")
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_bytes(key)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        try:
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)
        return path.read_bytes()

    def _write_anchor(self, path: Path, last_hash: str, count: int) -> None:
        anchor = {"last_hash": last_hash, "count": count}
        anchor["hmac"] = hmac.new(
            self._load_key(),
            self._canonical(anchor),
            hashlib.sha256,
        ).hexdigest()
        target = self._anchor_path(path)
        temporary = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(anchor, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _read_anchor(self, path: Path) -> dict[str, Any] | None:
        target = self._anchor_path(path)
        if not target.is_file():
            return None
        try:
            anchor = json.loads(target.read_text(encoding="utf-8"))
            signature = anchor.pop("hmac")
        except (OSError, json.JSONDecodeError, KeyError, AttributeError):
            return None
        expected = hmac.new(
            self._load_key(),
            self._canonical(anchor),
            hashlib.sha256,
        ).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            return None
        return anchor

    @staticmethod
    def _event_count(path: Path) -> int:
        if not path.is_file():
            return 0
        with path.open(encoding="utf-8") as file:
            return sum(1 for line in file if line.strip())

    def _lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def _process_lock(self):
        lock_path = self._lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.LOCK_TIMEOUT_SECONDS
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(descriptor, str(os.getpid()).encode("ascii"))
            except FileExistsError:
                try:
                    stale = time.time() - lock_path.stat().st_mtime > self.LOCK_TIMEOUT_SECONDS * 4
                except OSError:
                    stale = False
                if stale:
                    lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for audit log process lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            lock_path.unlink(missing_ok=True)

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

    def query(
        self,
        limit: int = 20,
        source: str | None = None,
        risk: str | None = None,
        tool: str | None = None,
    ) -> list[dict[str, Any]]:
        """按来源、风险等级、工具名筛选最近审计事件（无筛选条件时等价于 recent）。

        source/risk 精确匹配（忽略大小写），tool 子串匹配（忽略大小写），
        条件之间为 AND 关系；返回时间顺序的最近 limit 条匹配事件。
        """
        if not (source or risk or tool):
            return self.recent(limit)
        if not self.path.exists():
            return []
        limit = max(1, min(int(limit), 200))
        source_key = source.strip().lower() if source else None
        risk_key = risk.strip().upper() if risk else None
        tool_key = tool.strip().lower() if tool else None
        matches: deque[dict[str, Any]] = deque(maxlen=limit)
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if source_key and str(event.get("source", "")).lower() != source_key:
                    continue
                if risk_key and str(event.get("risk", "")).upper() != risk_key:
                    continue
                if tool_key and tool_key not in str(event.get("tool", "")).lower():
                    continue
                matches.append(event)
        return list(matches)

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
