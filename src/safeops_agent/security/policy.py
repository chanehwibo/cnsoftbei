from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from safeops_agent.config import load_policy_config, load_tools_config
from safeops_agent.tools.models import RiskLevel, ToolSpec


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    risk: RiskLevel
    reason: str
    requires_confirmation: bool = False
    error_code: str | None = None


class PolicyEngine:
    destructive_keywords = (
        "rm -rf",
        "rm -fr",
        "mkfs",
        "dd if=",
        ":(){",
        "shutdown",
        "poweroff",
        "reboot",
        "halt",
        "init 0",
        "init 6",
        "chmod 777",
        "chmod -r",
        "chown -r",
        "iptables -f",
        "格式化",
        "清空磁盘",
        "清空日志",
        "删除根目录",
        "删除 /",
        "删除/etc",
        "删除/boot",
        "删除/usr",
        "删除系统文件",
        "递归删除",
        "删库",
        "关闭防火墙",
        "禁用审计",
        "修改root",
        "修改 root",
        "删除用户",
        "新增管理员",
        "提权",
        "关机",
        "重启系统",
        "重装系统",
    )
    dangerous_actions = ("删除", "清空", "覆盖", "格式化", "修改权限", "递归", "写入", "移动")
    sensitive_paths = ("/", "/etc", "/boot", "/usr", "/bin", "/sbin", "/var/lib", "/root", "c:\\windows")
    argument_forbidden_chars = set(";&|`$<>") | {"\n", "\r", "\t", "\x00"}

    def __init__(self, config_path: Path | str | None = None) -> None:
        config = load_policy_config() if config_path is None else {}
        if config_path is not None:
            from safeops_agent.config import load_simple_yaml

            config = load_simple_yaml(config_path)
        configured_keywords = tuple(str(item) for item in config.get("destructive_keywords", []))
        configured_paths = tuple(str(item).lower() for item in config.get("sensitive_paths", []))
        self.active_destructive_keywords = configured_keywords or self.destructive_keywords
        self.active_sensitive_paths = configured_paths or self.sensitive_paths
        tools_config = load_tools_config()
        self.service_allowlist = {
            str(item).strip().lower()
            for item in tools_config.get("service_allowlist", [])
            if str(item).strip()
        }
        self.protected_services = {
            str(item).strip().lower()
            for item in tools_config.get("protected_services", [])
            if str(item).strip()
        }

    def evaluate_intent(self, text: str) -> PolicyDecision | None:
        normalized = text.replace(" ", "").lower()
        lower_text = text.lower()
        for keyword in self.active_destructive_keywords:
            kw_compact = keyword.replace(" ", "").lower()
            if kw_compact.isascii():
                if self._ascii_keyword_match(lower_text, keyword.lower()):
                    return PolicyDecision(
                        allowed=False,
                        risk=RiskLevel.HIGH,
                        reason=f"命中高风险意图关键词：{keyword}",
                        error_code="INTENT_HIGH_RISK_KEYWORD",
                    )
            else:
                if kw_compact in normalized:
                    return PolicyDecision(
                        allowed=False,
                        risk=RiskLevel.HIGH,
                        reason=f"命中高风险意图关键词：{keyword}",
                        error_code="INTENT_HIGH_RISK_KEYWORD",
                    )
        path = self._matched_sensitive_path(text)
        if path and any(action in text for action in self.dangerous_actions):
            return PolicyDecision(
                allowed=False,
                risk=RiskLevel.HIGH,
                reason=f"高风险操作涉及敏感路径：{path}",
                error_code="INTENT_SENSITIVE_PATH",
            )
        return None

    def _ascii_keyword_match(self, text: str, keyword: str) -> bool:
        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                return False
            before_ok = pos == 0 or not text[pos - 1].isalnum()
            end = pos + len(keyword)
            after_ok = end >= len(text) or not text[end].isalnum()
            if before_ok and after_ok:
                return True
            start = pos + 1

    def evaluate_tool(
        self,
        tool: ToolSpec,
        args: dict[str, Any] | None = None,
        confirmed: bool = False,
    ) -> PolicyDecision:
        arg_decision = self._validate_tool_args(tool, args or {})
        if arg_decision is not None:
            return arg_decision
        if tool.risk == RiskLevel.LOW:
            return PolicyDecision(allowed=True, risk=tool.risk, reason="只读低风险工具")
        if tool.risk == RiskLevel.MEDIUM:
            if confirmed:
                return PolicyDecision(allowed=True, risk=tool.risk, reason="中风险工具已确认")
            return PolicyDecision(
                allowed=False,
                risk=tool.risk,
                reason="中风险工具需要用户确认",
                requires_confirmation=True,
                error_code="TOOL_CONFIRMATION_REQUIRED",
            )
        return PolicyDecision(allowed=False, risk=tool.risk, reason="高风险工具默认拒绝", error_code="TOOL_HIGH_RISK")

    def _validate_tool_args(self, tool: ToolSpec, args: dict[str, Any]) -> PolicyDecision | None:
        for key, value in args.items():
            text = str(value)
            if any(char in text for char in self.argument_forbidden_chars):
                return PolicyDecision(
                    allowed=False,
                    risk=RiskLevel.HIGH,
                    reason=f"参数 {key} 包含命令注入风险字符",
                    error_code="ARG_COMMAND_INJECTION",
                )
            path = self._matched_sensitive_path(text)
            if path and tool.risk != RiskLevel.LOW:
                return PolicyDecision(
                    allowed=False,
                    risk=RiskLevel.HIGH,
                    reason=f"中高风险工具参数涉及敏感路径：{path}",
                    error_code="ARG_SENSITIVE_PATH",
                )

        if tool.name in {"service.status", "service.restart", "service.start", "service.stop"}:
            service = str(args.get("service", "")).strip()
            if not service:
                return PolicyDecision(
                    allowed=False,
                    risk=RiskLevel.MEDIUM,
                    reason="服务名不能为空",
                    error_code="ARG_SERVICE_REQUIRED",
                    requires_confirmation=tool.risk == RiskLevel.MEDIUM,
                )
            if not self._safe_identifier(service, extra="@_.-"):
                return PolicyDecision(
                    allowed=False,
                    risk=RiskLevel.HIGH,
                    reason="服务名包含非法字符",
                    error_code="ARG_SERVICE_INVALID",
                )
            if tool.name in {"service.restart", "service.start", "service.stop"}:
                normalized_service = service.lower()
                if normalized_service in self.protected_services:
                    return PolicyDecision(
                        allowed=False,
                        risk=RiskLevel.HIGH,
                        reason=f"受保护系统服务禁止变更：{service}",
                        error_code="ARG_PROTECTED_SERVICE",
                    )
                if self.service_allowlist and normalized_service not in self.service_allowlist:
                    return PolicyDecision(
                        allowed=False,
                        risk=RiskLevel.HIGH,
                        reason=f"服务不在允许变更白名单中：{service}",
                        error_code="ARG_SERVICE_NOT_ALLOWLISTED",
                    )

        if tool.name == "package.query":
            package = str(args.get("package", "")).strip()
            if package and not self._safe_identifier(package, extra="+_.:-"):
                return PolicyDecision(
                    allowed=False,
                    risk=RiskLevel.HIGH,
                    reason="软件包名包含非法字符",
                    error_code="ARG_PACKAGE_INVALID",
                )
        return None

    def _matched_sensitive_path(self, text: str) -> str | None:
        compact = text.replace(" ", "").replace("\\\\", "\\").lower()
        for path in self.active_sensitive_paths:
            normalized = path.replace(" ", "").lower()
            if normalized == "/":
                if compact == "/" or compact.endswith("/") or "删除/" in compact or "覆盖/" in compact or "清空/" in compact:
                    return path
                continue
            if normalized in compact:
                return path
        return None

    def _safe_identifier(self, value: str, extra: str = "") -> bool:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" + extra)
        return bool(value) and all(char in allowed for char in value)
