"""符合 Model Context Protocol 的 JSON-RPC 2.0 stdio 服务端。

传输层遵循 MCP stdio 规范：客户端与服务端通过 stdin/stdout 交换
以换行符分隔的 JSON-RPC 2.0 消息（单条消息内不含裸换行）。

实现的方法：
- initialize            —— 能力协商与握手
- notifications/initialized —— 客户端握手完成通知（无响应）
- tools/list            —— 返回工具清单（含 inputSchema 与安全注解）
- tools/call            —— 经安全策略裁决后调用工具
- ping                  —— 连通性探测

安全护栏在 tools/call 内生效：由 McpToolService 复用 PolicyEngine 对
参数注入、敏感路径、风险等级、确认要求进行裁决，Agent 与 Web 端共享同一套规则。
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from safeops_agent.mcp_server import McpToolService

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "safeops-agent"
SERVER_VERSION = "0.1.0"

# JSON-RPC 2.0 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class McpStdioServer:
    """在一对 text 流上运行的 MCP JSON-RPC 服务端。"""

    def __init__(
        self,
        service: McpToolService | None = None,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self.service = service if service is not None else McpToolService()
        self._in = stdin if stdin is not None else sys.stdin
        self._out = stdout if stdout is not None else sys.stdout
        self._initialized = False

    # ---- 主循环 ----------------------------------------------------------
    def serve_forever(self) -> None:
        for line in self._in:
            line = line.strip()
            if not line:
                continue
            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            self._send_error(None, PARSE_ERROR, "解析 JSON 失败")
            return
        response = self.handle_message(message)
        if response is not None:
            self._write(response)

    # ---- 分发 ------------------------------------------------------------
    def handle_message(self, message: Any) -> dict[str, Any] | None:
        """处理单条消息，返回响应字典；通知类消息返回 None。"""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return self._error_obj(None, INVALID_REQUEST, "无效的 JSON-RPC 请求")

        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        is_notification = "id" not in message

        if not isinstance(method, str):
            return None if is_notification else self._error_obj(msg_id, INVALID_REQUEST, "缺少 method")

        handler = {
            "initialize": self._on_initialize,
            "tools/list": self._on_tools_list,
            "tools/call": self._on_tools_call,
            "ping": self._on_ping,
        }.get(method)

        if method == "notifications/initialized":
            self._initialized = True
            return None

        if handler is None:
            if is_notification:
                return None
            return self._error_obj(msg_id, METHOD_NOT_FOUND, f"未知方法：{method}")

        try:
            result = handler(params)
        except _RpcError as exc:
            return self._error_obj(msg_id, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 —— 兜底，避免协议中断
            return self._error_obj(msg_id, INTERNAL_ERROR, f"内部错误：{exc}")

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    # ---- 方法实现 --------------------------------------------------------
    def _on_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        client_version = params.get("protocolVersion", PROTOCOL_VERSION)
        return {
            "protocolVersion": client_version if isinstance(client_version, str) else PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": "麒麟安全智能运维 Agent 的 MCP 工具服务，所有调用均经安全护栏裁决。",
        }

    def _on_tools_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": self.service.list_tools()}

    def _on_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise _RpcError(INVALID_PARAMS, "缺少工具名 name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise _RpcError(INVALID_PARAMS, "arguments 必须为对象")
        confirmed = bool(params.get("confirmed", False))

        outcome = self.service.call_tool(name, arguments, confirmed=confirmed)
        text = json.dumps(outcome, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": not outcome.get("ok", False),
            "structuredContent": outcome,
        }

    def _on_ping(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {}

    # ---- 输出辅助 --------------------------------------------------------
    def _write(self, obj: dict[str, Any]) -> None:
        self._out.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._out.flush()

    def _send_error(self, msg_id: Any, code: int, message: str) -> None:
        self._write(self._error_obj(msg_id, code, message))

    @staticmethod
    def _error_obj(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def main() -> int:
    McpStdioServer().serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
