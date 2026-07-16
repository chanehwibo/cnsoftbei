from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_simple_yaml(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {"__yaml_error__": str(exc)}
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return {"__yaml_error__": "YAML 根节点必须为对象"}
    return loaded


def load_app_config() -> dict[str, Any]:
    config = {
        "audit_log": "data/audit.log",
        "web_host": "127.0.0.1",
        "web_port": 8765,
        "require_auth": False,
    }
    config.update(load_simple_yaml(CONFIG_DIR / "app.yaml"))
    config["web_port"] = int(config.get("web_port", 8765))
    return config


def load_policy_config() -> dict[str, Any]:
    return load_simple_yaml(CONFIG_DIR / "policy.yaml")


def load_tools_config() -> dict[str, Any]:
    return load_simple_yaml(CONFIG_DIR / "tools.yaml")


def load_llm_config() -> dict[str, Any]:
    """加载 LLM 配置，config/llm.local.yaml 覆盖 config/llm.yaml（本地私密文件不入库）。"""
    config = load_simple_yaml(CONFIG_DIR / "llm.yaml")
    local = load_simple_yaml(CONFIG_DIR / "llm.local.yaml")
    config.update(local)
    return config


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
