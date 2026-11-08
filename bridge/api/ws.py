"""/ws — 브라우저로 이벤트를 밀어 준다.

프로토콜
  클라이언트 → {"type": "auth", "token": "<FOREMAN_API_TOKEN>"}   연결 뒤 ws_auth_timeout_s 안에. 틀리면 close 1008
  서버 → {"type": "hello", "heartbeat_s": N, "ui": "<화면 코드 지문>"}
  서버 → {"type": "event", "event": {...}}                          적재가 끝난 이벤트(id 포함)
  서버 → {"type": "ping", "ts": "..."}                              N초 동안 보낼 것이 없을 때. 끊김 감지용(README 3.10)
  서버 → {"type": "resync"}                                         밀려서 버렸다 — 빠진 것은 DB에서 다시 읽는다
  서버 → {"type": "batch", "items": [...]}                          50ms 안에 쌓인 메시지 묶음(6단계)
  서버 → {"type": "session_state", ...}                             프로세스 · CC status가 바뀜(6단계)
클라이언트가 보내는 그 밖의 메시지는 지금은 무시한다(3단계 입력 주입에서 쓴다).
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from bridge.api.auth import token_ok
from bridge.uiver import ui_version

router = APIRouter()
log = logging.getLogger("foreman.ws")


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    s = ws.app.state.settings
    pipeline = ws.app.state.pipeline
    await ws.accept()

    reason = await _auth_failure(ws, s.ws_auth_timeout_s, s.foreman_api_token.get_secret_value())
    if reason is not None:
        # 값은 남기지 않는다. 이유와 받은 길이만 — 길이로 붙여넣기 실수(키 이름 · 따옴표 · 잘림)를 가늠한다
        client = f"{ws.client.host}:{ws.client.port}" if ws.client else "?"
        log.warning("WS 인증 실패 %s: %s (기대 길이 %d)", client, reason, len(s.foreman_api_token.get_secret_value()))
        await _close(ws, status.WS_1008_POLICY_VIOLATION, reason)
        return

    q = pipeline.subscribe()
    try:
        # ui — 화면 코드 지문(bridge/uiver.py). 페이지가 처음 받은 것과 다르면 [새로 고침] 띠(11-09)
        await ws.send_json({"type": "hello", "heartbeat_s": s.ws_heartbeat_s, "ui": ui_version()})

        async def reader() -> None:
            while True:
                await ws.receive_text()  # 끊기면 WebSocketDisconnect

        async def writer() -> None:
            # 이벤트가 몰리면(초당 수십 개) 쌓인 것을 한 프레임으로 묶는다 — {"type": "batch", "items": [...]}.
            # 화면은 프레임마다가 아니라 자기 주기로 그린다(static/js/store.js)
            while True:
                try:
                    async with asyncio.timeout(s.ws_heartbeat_s):
                        msg = await q.get()
                except TimeoutError:
                    await ws.send_json({"type": "ping", "ts": datetime.now(UTC).isoformat(timespec="seconds")})
                    continue
                await asyncio.sleep(0.05)         # 50ms 모아서
                items = [msg]
                while not q.empty() and len(items) < 500:
                    items.append(q.get_nowait())
                await ws.send_json(items[0] if len(items) == 1 else {"type": "batch", "items": items})

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


async def _auth_failure(ws: WebSocket, timeout_s: float, expected: str) -> str | None:
    """첫 메시지를 검사한다. 통과하면 None, 아니면 클라이언트에도 그대로 보낼 짧은 이유(close reason, 123바이트 이하)."""
    try:
        async with asyncio.timeout(timeout_s):
            text = await ws.receive_text()
    except TimeoutError:
        return f"{timeout_s:g}초 안에 인증 메시지가 없음"
    except WebSocketDisconnect:
        return "인증 전에 끊김"
    try:
        first = json.loads(text)
    except ValueError:
        return "첫 메시지가 JSON이 아님"
    if not isinstance(first, dict) or first.get("type") != "auth":
        return 'type이 "auth"가 아님'
    token = first.get("token")
    if not isinstance(token, str) or not token:
        return "token이 없음"
    if not token_ok(token, expected):
        return f"토큰 불일치(받은 길이 {len(token)})"  # 기대 길이는 서버 로그에만
    return None


async def _close(ws: WebSocket, code: int, reason: str = "") -> None:
    try:
        await ws.close(code, reason)
    except RuntimeError:
        pass  # 이미 닫힘
