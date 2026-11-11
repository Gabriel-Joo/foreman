"""/hooks — CC hook(scripts/foreman-hook.sh)이 stdin JSON을 그대로 보낸다. hook 토큰(API 토큰과 별개)이 필요하다.

바로 202를 돌려주고 적재는 뒤에서 한다 — hook이 CC를 붙잡지 않게. 턴은 조립기에서 트랜스크립트 신호와 합쳐진다
(먼저 온 신호가 닫는다, README 3.2). 거절은 항상 이유를 로그에 남긴다(1단계 WS 1008 교훈 — 값은 남기지 않는다).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from bridge.api.auth import token_ok

router = APIRouter()
log = logging.getLogger("foreman.hooks")
_tasks: set[asyncio.Task[None]] = set()


async def _authed_body(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """hook 토큰 확인 + JSON 본문. 거절은 언제나 이유를 로그에(값은 남기지 않는다)."""
    s = request.app.state.settings
    client = request.client.host if request.client else "?"
    auth = request.headers.get("authorization", "")
    given = auth[7:] if auth.startswith("Bearer ") else None
    if not token_ok(given, s.foreman_hook_token.get_secret_value()):
        why = "Authorization 없음" if not auth else ("Bearer 아님" if given is None else f"토큰 불일치(받은 길이 {len(given)})")
        log.warning("hook 거절 %s %s: %s", client, request.url.path, why)
        return None, JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        body = json.loads(await request.body())
    except ValueError:
        log.warning("hook 거절 %s %s: JSON이 아님", client, request.url.path)
        return None, JSONResponse({"error": "JSON이 아님"}, status_code=400)
    if not isinstance(body, dict):
        return None, JSONResponse({"error": "객체가 아님"}, status_code=400)
    return body, None


@router.post("/hooks/pre")
async def pre_tool_use(request: Request) -> Response:
    """PreToolUse — 판정을 바로 돌려준다(메모리 안에서). 판정하지 않으면 204(본문 없음 → CC가 정한다)."""
    body, err = await _authed_body(request)
    if err:
        return err
    mgr = getattr(request.app.state, "approvals", None)
    if mgr is None:
        return Response(status_code=204)
    srole = None                           # 역할 권한(11-11 bridge/roleguard.py) — 켜져 있을 때만 읽는다(60초 기억). 못 읽으면 역할 없음으로
    if getattr(mgr, "roles", None) is not None and mgr.roles.active:
        try:
            srole = await mgr.roles.role_of(mgr.engine, body.get("session_id"))
        except Exception as e:  # noqa: BLE001
            log.warning("역할 권한: 세션 역할을 읽지 못함: %s", type(e).__name__)
    out = mgr.pre_tool_use(body, role=await mgr.session_role(body), session_role=srole)   # 역할은 git push가 보일 때만 읽는다(11-10)
    return JSONResponse(out) if out else Response(status_code=204)


@router.post("/hooks/permission")
async def permission_request(request: Request) -> Response:
    """PermissionRequest — 승인 창이 떴다. 브라우저 결정을 기다린다(터미널에서 먼저 답하면 풀린다)."""
    body, err = await _authed_body(request)
    if err:
        return err
    mgr = getattr(request.app.state, "approvals", None)
    if mgr is None:
        return Response(status_code=204)
    out = await mgr.permission_request(body)
    return JSONResponse(out) if out else Response(status_code=204)


@router.post("/hooks")
async def receive_hook(request: Request) -> JSONResponse:
    client = request.client.host if request.client else "?"
    body, err = await _authed_body(request)
    if err:
        return err
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
