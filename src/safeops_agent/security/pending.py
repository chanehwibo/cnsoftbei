"""待执行动作存储：确认令牌机制的核心。

中风险操作在 dry-run 预演时生成一次性 pending action（精确保存
tool + args，并绑定会话、限制有效期）。确认阶段凭 action_id 执行
的正是当初预演并经策略裁决过的动作，而不是把原始文本重新跑一遍
意图理解——消除"预演的是 A、确认后执行的是 B"的不一致窗口
（LLM 意图理解存在非确定性，重跑不保证得到同一动作）。

安全属性：
- 一次性：consume 即删除，无论后续执行成败都不可重放；
- 会话绑定：跨会话出示令牌直接拒绝（且令牌同样作废）；
- 有效期：超时令牌拒绝执行，需重新发起请求走完整裁决流程。
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from safeops_agent.config import PROJECT_ROOT

DEFAULT_TTL_SECONDS = 600


class PendingActionStore:
    def __init__(self, path: Path | str | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.path = Path(path) if path is not None else PROJECT_ROOT / "data" / "pending_actions.json"
        self.ttl = ttl_seconds
        self._lock = threading.Lock()

    def create(self, tool: str, args: dict[str, Any], request: str, session: str = "local") -> str:
        action_id = uuid.uuid4().hex
        with self._lock:
            actions = self._load()
            actions[action_id] = {
                "tool": tool,
                "args": args,
                "request": request,
                "session": session,
                "created_at": time.time(),
            }
            self._save(actions)
        return action_id

    def consume(self, action_id: str, session: str = "local") -> tuple[dict[str, Any] | None, str | None]:
        """取出并删除 pending action（一次性）。返回 (record, 拒绝原因)。"""
        with self._lock:
            actions = self._load()
            record = actions.pop(action_id, None)
            self._save(actions)
        if record is None:
            return None, "确认令牌不存在、已被使用或已过期"
        if time.time() - float(record.get("created_at", 0)) > self.ttl:
            return None, f"确认令牌已过期（有效期 {self.ttl // 60} 分钟），请重新发起请求"
        if record.get("session") != session:
            return None, "确认令牌与当前会话不匹配，已拒绝执行"
        return record, None

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        now = time.time()
        return {
            key: value
            for key, value in data.items()
            if isinstance(value, dict) and now - float(value.get("created_at", 0)) <= self.ttl
        }

    def _save(self, actions: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
