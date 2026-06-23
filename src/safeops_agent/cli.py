from __future__ import annotations

import argparse
import json
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.config import load_app_config, resolve_project_path


def build_parser() -> argparse.ArgumentParser:
    app_config = load_app_config()
    parser = argparse.ArgumentParser(description="安全智能运维 Agent CLI")
    parser.add_argument("request", help="自然语言运维请求")
    parser.add_argument("--yes", action="store_true", help="确认执行中风险操作")
    parser.add_argument("--audit-log", default=app_config["audit_log"], help="审计日志路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    agent = SafeOpsAgent(audit_logger=AuditLogger(resolve_project_path(Path(args.audit_log)), source="cli"))
    response = agent.handle(args.request, confirmed=args.yes)
    if args.json:
        print(json.dumps(response.__dict__, ensure_ascii=False, default=str, indent=2))
    else:
        print(response.message)
        if response.requires_confirmation:
            print("如确认执行，请追加 --yes。")
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
