from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from kama_claude.core.bus.envelope import JsonRpcRequest

type EventHandler = Callable[[dict[str, Any]], Awaitable[None]]

_MAX_LINE_BYTES = 64 * 1024 * 1024  # 64 MB per frame，兼容 MCP 大文件工具结果


class IpcError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class SocketClient:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._event_handlers: list[EventHandler] = []

    # 建立到 core 守护进程的 TCP 连接
    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port, limit=_MAX_LINE_BYTES
        )

    # 关闭 TCP 连接并等待底层 socket 释放
    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=1.0)
            except TimeoutError:
                pass

    # Register an event handler to receive event pushes from the core daemon.
    # 1. on_event( cli/commands/run.py )
    def on_event(self, handler: EventHandler) -> None:
        self._event_handlers.append(handler)

    # 发送 JSON-RPC 命令并等待响应，成功返回 result dict，失败抛出 IpcError
    async def send_command(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._writer is None:
            raise RuntimeError("not connected — call connect() first")
        req_id = str(uuid.uuid4())
        request = JsonRpcRequest(id=req_id, method=method, params=params)
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        self._writer.write(request.model_dump_json().encode() + b"\n")
        await self._writer.drain()
        return await fut

    # 持续读取服务器消息，分发 RPC 响应到 pending future 或事件到 event handler
    async def run_event_loop(self) -> None:
        if self._reader is None:
            raise RuntimeError("not connected — call connect() first")
        try:
            while True:
                try:
                    line = await self._reader.readline()
                except (ConnectionResetError, OSError):
                    break
                except (ValueError, asyncio.LimitOverrunError):
                    # 单行超出 limit；丢弃本行，继续读取后续消息
                    continue
                if not line:
                    break
                await self._dispatch(line)
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    # Parse a single line of JSON-RPC response or event push, dispatch to the corresponding future or event handler
    async def _dispatch(self, line: bytes) -> None:
        try:
            msg: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            return

        # Two kinds of messages from the server: JSON-RPC responses and event pushes.
        if "jsonrpc" in msg:
            req_id: str | None = msg.get("id")
            if req_id and req_id in self._pending:
                fut = self._pending.pop(req_id)
                if not fut.done():
                    if "error" in msg:
                        err = msg["error"]
                        fut.set_exception(
                            IpcError(err.get("code", -1), err.get("message", "unknown"))
                        )
                    else:
                        fut.set_result(msg.get("result") or {})
        elif msg.get("kind") == "event":
            event_data: dict[str, Any] = msg.get("event", {})
            for handler in self._event_handlers:
                await handler(event_data)
