from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_simple_yaml(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {}
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key:
            result.setdefault(current_key, []).append(_parse_scalar(stripped[2:].strip()))
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if not value:
                result[key] = []
            elif value == "[]":
                result[key] = []
            else:
                result[key] = _parse_scalar(value)
    return result


def load_app_config() -> dict[str, Any]:
    config = {"audit_log": "data/audit.log", "web_host": "127.0.0.1", "web_port": 8765}
    config.update(load_simple_yaml(CONFIG_DIR / "app.yaml"))
    config["web_port"] = int(config.get("web_port", 8765))
    return config


def load_policy_config() -> dict[str, Any]:
    return load_simple_yaml(CONFIG_DIR / "policy.yaml")


def load_tools_config() -> dict[str, Any]:
    return load_simple_yaml(CONFIG_DIR / "tools.yaml")


def load_llm_config() -> dict[str, Any]:
    return load_simple_yaml(CONFIG_DIR / "llm.yaml")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _parse_scalar(value: str) -> Any:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value
