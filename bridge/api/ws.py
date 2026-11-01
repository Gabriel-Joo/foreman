"""/ws — 브라우저로 이벤트를 밀어 준다.

프로토콜
  클라이언트 → {"type": "auth", "token": "<FOREMAN_API_TOKEN>"}   연결 뒤 ws_auth_timeout_s 안에. 틀리면 close 1008
  서버 → {"type": "hello", "heartbeat_s": N}
  서버 → {"type": "event", "event": {...}}                          적재가 끝난 이벤트(id 포함)
  서버 → {"type": "ping", "ts": "..."}                              N초 동안 보낼 것이 없을 때. 끊김 감지용(README 3.10)
  서버 → {"type": "resync"}                                         밀려서 버렸다 — 빠진 것은 DB에서 다시 읽는다
클라이언트가 보내는 그 밖의 메시지는 지금은 무시한다(3단계 입력 주입에서 쓴다).
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from bridge.api.auth import token_ok

router = APIRouter()
log = logging.getLogger("foreman.ws")


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    s = ws.app.state.settings
    pipeline = ws.app.state.pipeline
    await ws.accept()

    try:
        async with asyncio.timeout(s.ws_auth_timeout_s):
            first = json.loads(await ws.receive_text())
        ok = isinstance(first, dict) and first.get("type") == "auth" and token_ok(
            first.get("token"), s.foreman_api_token.get_secret_value()
        )
    except (TimeoutError, ValueError, WebSocketDisconnect):
        ok = False
    if not ok:
        await _close(ws, status.WS_1008_POLICY_VIOLATION)
        return

    q = pipeline.subscribe()
    try:
        await ws.send_json({"type": "hello", "heartbeat_s": s.ws_heartbeat_s})

        async def reader() -> None:
            while True:
                await ws.receive_text()  # 끊기면 WebSocketDisconnect

        async def writer() -> None:
            while True:
                try:
                    async with asyncio.timeout(s.ws_heartbeat_s):
                        msg = await q.get()
                except TimeoutError:
                    msg = {"type": "ping", "ts": datetime.now(UTC).isoformat(timespec="seconds")}
                await ws.send_json(msg)

        tasks = [asyncio.create_task(reader()), asyncio.create_task(writer())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                log.warning("WS 종료: %s", type(exc).__name__)
    finally:
        pipeline.unsubscribe(q)


async def _close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code)
    except RuntimeError:
        pass  # 이미 닫힘
