"""/hooks — CC hook(scripts/foreman-hook.sh)이 stdin JSON을 그대로 보낸다. hook 토큰(API 토큰과 별개)이 필요하다.

바로 202를 돌려주고 적재는 뒤에서 한다 — hook이 CC를 붙잡지 않게. 턴은 조립기에서 트랜스크립트 신호와 합쳐진다
(먼저 온 신호가 닫는다, README 3.2). 거절은 항상 이유를 로그에 남긴다(1단계 WS 1008 교훈 — 값은 남기지 않는다).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.auth import token_ok

router = APIRouter()
log = logging.getLogger("foreman.hooks")
_tasks: set[asyncio.Task[None]] = set()


@router.post("/hooks")
async def receive_hook(request: Request) -> JSONResponse:
    s = request.app.state.settings
    client = request.client.host if request.client else "?"
    auth = request.headers.get("authorization", "")
    given = auth[7:] if auth.startswith("Bearer ") else None
    if not token_ok(given, s.foreman_hook_token.get_secret_value()):
        why = "Authorization 없음" if not auth else ("Bearer 아님" if given is None else f"토큰 불일치(받은 길이 {len(given)})")
        log.warning("hook 거절 %s: %s", client, why)
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        body = json.loads(await request.body())
    except ValueError:
        log.warning("hook 거절 %s: JSON이 아님", client)
        return JSONResponse({"error": "JSON이 아님"}, status_code=400)
    name = body.get("hook_event_name") if isinstance(body, dict) else None
    if not name or not body.get("session_id"):
        log.warning("hook 거절 %s: hook_event_name · session_id 없음", client)
        return JSONResponse({"error": "hook_event_name · session_id 필요"}, status_code=400)
    asm = getattr(request.app.state, "assembler", None)
    if asm is None:
        log.warning("hook 거절 %s: 와처가 꺼져 있음(%s)", client, name)
        return JSONResponse({"error": "와처 꺼짐"}, status_code=503)

    async def apply() -> None:
        try:
            await asm.apply_hook(name, body)
        except Exception as e:  # noqa: BLE001
            log.warning("hook 적재 실패 %s: %s: %s", name, type(e).__name__, str(e)[:200])

    t = asyncio.create_task(apply())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return JSONResponse({"accepted": name}, status_code=202)
