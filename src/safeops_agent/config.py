from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parent
BUNDLED_RESOURCE_ROOT = PACKAGE_ROOT / "resources"
BUNDLED_CONFIG_DIR = BUNDLED_RESOURCE_ROOT / "config"
BUNDLED_WEB_ROOT = BUNDLED_RESOURCE_ROOT / "web"


def _select_project_root() -> Path:
    configured = os.environ.get("SAFEOPS_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "pyproject.toml").is_file() and (source_root / "config").is_dir():
        return source_root
    return Path.cwd().resolve()


PROJECT_ROOT = _select_project_root()
LOCAL_CONFIG_DIR = PROJECT_ROOT / "config"
LOCAL_WEB_ROOT = PROJECT_ROOT / "web"
CONFIG_DIR = LOCAL_CONFIG_DIR if (LOCAL_CONFIG_DIR / "app.yaml").is_file() else BUNDLED_CONFIG_DIR
WEB_ROOT = LOCAL_WEB_ROOT if (LOCAL_WEB_ROOT / "index.html").is_file() else BUNDLED_WEB_ROOT


def _config_path(name: str) -> Path:
    local = LOCAL_CONFIG_DIR / name
    return local if local.is_file() else BUNDLED_CONFIG_DIR / name


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
        "tls_enabled": False,
        "tls_cert_file": "",
        "tls_key_file": "",
    }
    config.update(load_simple_yaml(_config_path("app.yaml")))
    config["web_port"] = int(config.get("web_port", 8765))
    return config


def load_policy_config() -> dict[str, Any]:
    return load_simple_yaml(_config_path("policy.yaml"))


def load_tools_config() -> dict[str, Any]:
    return load_simple_yaml(_config_path("tools.yaml"))


def load_llm_config() -> dict[str, Any]:
    """加载 LLM 配置，config/llm.local.yaml 覆盖 config/llm.yaml（本地私密文件不入库）。"""
    config = load_simple_yaml(_config_path("llm.yaml"))
    local = load_simple_yaml(LOCAL_CONFIG_DIR / "llm.local.yaml")
    config.update(local)
    return config


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
