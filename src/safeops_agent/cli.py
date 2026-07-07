from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.config import load_app_config, resolve_project_path
from safeops_agent.mcp_server import McpToolService


def _force_utf8_output() -> None:
    """Windows 控制台默认 GBK 编码会把中文输出打成乱码，统一切到 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    app_config = load_app_config()
    parser = argparse.ArgumentParser(description="安全智能运维 Agent CLI")
    parser.add_argument("request", nargs="?", help="自然语言运维请求")
    parser.add_argument("--yes", action="store_true", help="确认执行中风险操作（重跑意图理解后放行）")
    parser.add_argument("--confirm", metavar="ACTION_ID", help="凭一次性确认令牌精确执行已预演的中风险操作（推荐）")
    parser.add_argument("--audit-log", default=app_config["audit_log"], help="审计日志路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    parser.add_argument("--list-tools", action="store_true", help="输出 MCP 风格工具清单")
    parser.add_argument("--verify-audit", action="store_true", help="校验审计日志哈希链完整性")
    return parser


def main() -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args()

    if args.list_tools:
        print(json.dumps(McpToolService().list_tools(), ensure_ascii=False, indent=2))
        return 0

    if args.verify_audit:
        report = AuditLogger(resolve_project_path(Path(args.audit_log))).verify()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if not args.request and not args.confirm:
        parser.error("request is required unless --list-tools/--verify-audit/--confirm is used")

    agent = SafeOpsAgent(
        audit_logger=AuditLogger(resolve_project_path(Path(args.audit_log)), source="cli"),
        session_id="cli",
    )
    if args.confirm:
        response = agent.confirm(args.confirm)
    else:
        response = agent.handle(args.request, confirmed=args.yes)
    if args.json:
        print(json.dumps(response.__dict__, ensure_ascii=False, default=str, indent=2))
    else:
        print(response.message)
        if response.requires_confirmation:
            if response.pending_action_id:
                print(f"如确认执行：--confirm {response.pending_action_id}（10 分钟内有效），或追加 --yes。")
            else:
                print("如确认执行，请追加 --yes。")
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
