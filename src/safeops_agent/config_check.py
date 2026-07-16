"""配置文件校验：检查 config/*.yaml 的必要字段、类型和取值范围。

用法：
    python -m safeops_agent.config_check            # 校验仓库默认 config 目录
    python -m safeops_agent.config_check --json     # 以 JSON 输出完整报告

退出码：0 = 校验通过（允许有 warning），1 = 存在 error。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from safeops_agent.config import CONFIG_DIR, load_simple_yaml
from safeops_agent.tools.registry import all_tool_names


REQUIRED_FILES = ("app.yaml", "policy.yaml", "tools.yaml", "llm.yaml")


def validate_configs(config_dir: Path | str = CONFIG_DIR) -> dict[str, Any]:
    """校验配置目录，返回 {ok, errors, warnings, checked_files}。

    error 表示会破坏运行的配置问题；warning 表示可运行但值得注意的问题
    （例如 API Key 缺失会自动回退规则模式）。
    """
    config_dir = Path(config_dir)
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[str] = []

    for name in REQUIRED_FILES:
        path = config_dir / name
        if not path.exists():
            errors.append(f"{name}: 文件缺失")
        else:
            checked.append(name)

    app = load_simple_yaml(config_dir / "app.yaml")
    _check_yaml_parse("app.yaml", app, errors)
    if (config_dir / "app.yaml").exists():
        _check_app(app, errors)

    policy = load_simple_yaml(config_dir / "policy.yaml")
    _check_yaml_parse("policy.yaml", policy, errors)
    if (config_dir / "policy.yaml").exists():
        _check_policy(policy, errors, warnings)

    tools = load_simple_yaml(config_dir / "tools.yaml")
    _check_yaml_parse("tools.yaml", tools, errors)
    if (config_dir / "tools.yaml").exists():
        _check_tools(tools, errors, warnings)

    llm = load_simple_yaml(config_dir / "llm.yaml")
    _check_yaml_parse("llm.yaml", llm, errors)
    local_path = config_dir / "llm.local.yaml"
    if local_path.exists():
        llm.update(load_simple_yaml(local_path))
        checked.append("llm.local.yaml")
    if (config_dir / "llm.yaml").exists():
        _check_llm(llm, errors, warnings)

    return {"ok": not errors, "errors": errors, "warnings": warnings, "checked_files": checked}


def _check_app(app: dict[str, Any], errors: list[str]) -> None:
    audit_log = app.get("audit_log")
    if not isinstance(audit_log, str) or not audit_log.strip():
        errors.append("app.yaml: audit_log 必须是非空字符串路径")
    web_host = app.get("web_host")
    if not isinstance(web_host, str) or not web_host.strip():
        errors.append("app.yaml: web_host 必须是非空字符串")
    web_port = app.get("web_port")
    if not isinstance(web_port, int) or isinstance(web_port, bool) or not (1 <= web_port <= 65535):
        errors.append("app.yaml: web_port 必须是 1-65535 的整数")
    require_auth = app.get("require_auth", True)
    if not isinstance(require_auth, bool):
        errors.append("app.yaml: require_auth 必须是 true/false")
    development_mode = app.get("development_mode", False)
    if not isinstance(development_mode, bool):
        errors.append("app.yaml: development_mode 必须是 true/false")
    tls_enabled = app.get("tls_enabled", False)
    if not isinstance(tls_enabled, bool):
        errors.append("app.yaml: tls_enabled 必须是 true/false")
    cert_file = app.get("tls_cert_file", "")
    key_file = app.get("tls_key_file", "")
    if tls_enabled is True:
        if not isinstance(cert_file, str) or not cert_file.strip():
            errors.append("app.yaml: tls_enabled=true 时 tls_cert_file 不能为空")
        if not isinstance(key_file, str) or not key_file.strip():
            errors.append("app.yaml: tls_enabled=true 时 tls_key_file 不能为空")
    if development_mode is True and require_auth is not False:
        errors.append("app.yaml: development_mode=true 时必须显式设置 require_auth: false")
    if development_mode is not True and require_auth is not True:
        errors.append("app.yaml: 非开发模式必须设置 require_auth: true")
    if development_mode is True and isinstance(web_host, str) and web_host not in {"127.0.0.1", "::1", "localhost"}:
        errors.append("app.yaml: development_mode 仅允许本机回环地址")
    if isinstance(web_host, str) and web_host not in {"127.0.0.1", "::1", "localhost"} and require_auth is not True:
        errors.append("app.yaml: 非本机回环地址必须设置 require_auth: true")
    if isinstance(web_host, str) and web_host not in {"127.0.0.1", "::1", "localhost"} and tls_enabled is not True:
        errors.append("app.yaml: 非本机回环地址必须启用 TLS")


def _check_policy(policy: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    keywords = policy.get("destructive_keywords")
    if not isinstance(keywords, list) or not keywords:
        errors.append("policy.yaml: destructive_keywords 必须是非空列表（高危关键词拦截依赖它）")
    elif not all(isinstance(item, str) and item.strip() for item in keywords):
        errors.append("policy.yaml: destructive_keywords 含空项或非字符串项")

    paths = policy.get("sensitive_paths")
    if not isinstance(paths, list) or not paths:
        errors.append("policy.yaml: sensitive_paths 必须是非空列表（敏感路径保护依赖它）")
    elif not all(isinstance(item, str) and item.strip() for item in paths):
        errors.append("policy.yaml: sensitive_paths 含空项或非字符串项")

    if isinstance(keywords, list):
        duplicated = {item for item in keywords if isinstance(item, str) and keywords.count(item) > 1}
        if duplicated:
            warnings.append(f"policy.yaml: destructive_keywords 存在重复项：{sorted(duplicated)}")


def _check_tools(tools: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    disabled = tools.get("disabled_tools", [])
    if disabled is None:
        disabled = []
    if not isinstance(disabled, list):
        errors.append("tools.yaml: disabled_tools 必须是列表（留空表示不禁用任何工具）")
    else:
        known = set(all_tool_names())
        for item in disabled:
            if not isinstance(item, str):
                errors.append(f"tools.yaml: disabled_tools 含非字符串项 {item!r}")
            elif item not in known:
                warnings.append(f"tools.yaml: disabled_tools 中的 {item} 不是已注册工具名（可能是拼写错误）")
        if isinstance(disabled, list) and known and known.issubset(set(disabled)):
            errors.append("tools.yaml: disabled_tools 禁用了全部工具，Agent 将无事可做")

    defaults = tools.get("tool_defaults", {})
    if not isinstance(defaults, dict):
        errors.append("tools.yaml: tool_defaults 必须是对象")
        defaults = {}
    for key in ("process_limit", "network_limit", "log_lines"):
        value = defaults.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"tools.yaml: {key} 必须是正整数")

    allowlist = tools.get("service_allowlist")
    protected = tools.get("protected_services")
    for key, value in (("service_allowlist", allowlist), ("protected_services", protected)):
        if not isinstance(value, list) or not value:
            errors.append(f"tools.yaml: {key} 必须是非空字符串列表")
        elif not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"tools.yaml: {key} 含空项或非字符串项")
    if isinstance(allowlist, list) and isinstance(protected, list):
        overlap = {str(item).lower() for item in allowlist} & {str(item).lower() for item in protected}
        if overlap:
            errors.append(f"tools.yaml: 服务不能同时出现在允许和保护列表：{sorted(overlap)}")


def _check_yaml_parse(name: str, config: dict[str, Any], errors: list[str]) -> None:
    if "__yaml_error__" in config:
        errors.append(f"{name}: YAML 解析失败：{config['__yaml_error__']}")


def _check_llm(llm: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    enabled = llm.get("llm_enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append("llm.yaml: llm_enabled 必须是 true/false")

    timeout = llm.get("llm_timeout")
    if timeout is not None:
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
            errors.append("llm.yaml: llm_timeout 必须是正整数（秒）")
        elif timeout > 30:
            warnings.append("llm.yaml: llm_timeout 超过 30 秒，API 抖动时会长时间卡住演示界面")

    base_url = llm.get("llm_base_url")
    if base_url is not None and not (isinstance(base_url, str) and base_url.startswith(("http://", "https://"))):
        errors.append("llm.yaml: llm_base_url 必须以 http:// 或 https:// 开头")

    if enabled is True:
        provider = llm.get("llm_provider")
        if not isinstance(provider, str) or not provider.strip():
            errors.append("llm.yaml: llm_enabled=true 时 llm_provider 不能为空")
        model = llm.get("llm_model")
        if not isinstance(model, str) or not model.strip():
            errors.append("llm.yaml: llm_enabled=true 时 llm_model 不能为空")
        api_key = llm.get("llm_api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            warnings.append(
                "llm.yaml: llm_api_key 为空，运行时将自动回退规则匹配模式"
                "（如需 LLM 意图理解，请在 config/llm.local.yaml 配置 Key）"
            )


def main() -> int:
    # Windows 控制台默认 GBK，中文报告会乱码，与 cli.py 一致强制 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = argparse.ArgumentParser(description="校验 config/*.yaml 配置文件")
    parser.add_argument("--config-dir", default=str(CONFIG_DIR), help="配置目录（默认仓库 config/）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整报告")
    args = parser.parse_args()

    report = validate_configs(args.config_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for message in report["errors"]:
            print(f"[ERROR] {message}")
        for message in report["warnings"]:
            print(f"[WARN ] {message}")
        status = "通过" if report["ok"] else "未通过"
        print(f"配置校验{status}：检查 {len(report['checked_files'])} 个文件，"
              f"{len(report['errors'])} 个错误，{len(report['warnings'])} 个警告")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
