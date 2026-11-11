"""터미널 패널(7단계) — ttyd 소켓으로 가는 길과 셸 기록 hook.

  POST /api/terminal/session     API 토큰 → 쿠키(HttpOnly · SameSite=Strict · Path=/terminal). 패널을 열 때 받는다
  GET  /api/terminal             상태 + 기다리는 부탁(CC가 "이 명령을 실행해 주세요"라고 한 것)
  POST /api/terminal/open        {project, tab} — 그 탭이 그 프로젝트의 셸 창을 보게 한다(없으면 그 저장소 폴더에서 만든다, 11-10)
  GET  /api/terminal/window?tab= 그 탭이 지금 보는 창(바꾸지 않는다)
  POST /api/terminal/respawn     {project, force} — 그 창의 셸을 새로 띄운다(바뀐 셸 설정을 읽게, 11-10)
  DELETE /api/terminal/requests/{id}   부탁을 닫는다(결과를 전달하지 않는다)
  POST /api/terminal/requests/{id}/prefill   셸 입력 줄에 다시 채운다
  GET  /terminal/…  · WS /terminal/ws       쿠키를 확인하고 ttyd(UNIX 소켓)로 그대로 넘긴다
  POST /hooks/shell              셸 PROMPT_COMMAND(hook 토큰) — 친 명령 · 종료 코드 · 위치

ttyd는 TCP 포트를 열지 않는다. 브라우저는 이 브리지(127.0.0.1)를 거쳐서만 닿고, 쿠키는 API 토큰을 가진 사람만 받는다.
WS는 Origin이 Host와 같아야 한다(다른 사이트가 브라우저 쿠키로 셸을 여는 것 — cross-site WebSocket hijacking — 을 막는다).
"""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from websockets.asyncio.client import unix_connect

from bridge.api.auth import require_api_token
from bridge.api.hooks import _authed_body
from bridge.inject import Refused
from bridge.terminal import COOKIE, TAB_RE, TERM_PROJECTS

log = logging.getLogger("foreman.terminal")
api = APIRouter(prefix="/api/terminal", dependencies=[Depends(require_api_token)])
router = APIRouter()

_FWD_REQ = ("accept", "accept-encoding", "accept-language", "if-none-match", "if-modified-since", "user-agent")
_FWD_RES = ("content-type", "content-encoding", "etag", "last-modified", "cache-control", "vary")


def _mgr(request: Request) -> Any:
    m = getattr(request.app.state, "terminal", None)
    if m is None:
        raise HTTPException(503, "터미널 패널이 꺼져 있다")
    return m


@api.post("/session")
async def open_session(request: Request) -> JSONResponse:
    m = _mgr(request)
    resp = JSONResponse({"ok": True, "running": m.running})
    resp.set_cookie(COOKIE, m.new_cookie(), max_age=int(m.s.terminal_cookie_ttl_s), path="/terminal",
                    httponly=True, samesite="strict", secure=request.url.scheme == "https")
    return resp


@api.get("")
async def state(request: Request) -> dict[str, Any]:
    return _mgr(request).snapshot()


@api.get("/window")
async def window(request: Request, tab: str | None = None) -> dict[str, Any]:
    """지금 tmux가 보이는 창(이름 · 폴더) — 창을 바꾸지 않는다. 화면 이름표가 거짓이 되지 않게 열려 있는 동안 묻는다(11-10).
    tmux의 "보이는 창"은 세션 하나에 하나라 다른 탭 · CC 부탁 · tmux 키가 바꿀 수 있다."""
    try:
        return await _mgr(request).current_view(tab)
    except Refused as e:
        raise HTTPException(503, f"터미널 창을 읽지 못했습니다 — {e}") from e


class OpenIn(BaseModel):
    project: str | None = None     # None이면 지금 보이는 창 그대로
    tab: str | None = None         # 브라우저 탭 id(11-10) — 그 탭의 그룹 세션에서 고른다. 없으면 기준 세션(옛 화면)


@api.post("/open")
async def open_project(body: OpenIn, request: Request) -> dict[str, Any]:
    """[터미널]을 열 때 — 고른 프로젝트의 창(없으면 그 저장소 폴더에서 만든다)을 보이고 실제 보이는 창을 돌려준다(11-10)."""
    m = _mgr(request)
    if body.project is not None and body.project not in TERM_PROJECTS:
        raise HTTPException(422, "모르는 프로젝트입니다")
    try:
        return await m.open_project(body.project, body.tab)
    except Refused as e:
        raise HTTPException(503, f"터미널 창을 고르지 못했습니다 — {e}") from e


class ScrollIn(BaseModel):
    tab: str
    action: str                    # up(한 쪽 위로 — 복사 모드로 들어감) · down · exit(복사 모드 끝내고 입력으로)


@api.post("/scroll")
async def scroll(body: ScrollIn, request: Request) -> dict[str, Any]:
    """[위로] · [아래로] · [입력으로](11-11) — 그 탭의 터미널을 tmux 복사 모드로 올려 본다. 바뀐 보이는 창 상태를 돌려준다."""
    m = _mgr(request)
    if not TAB_RE.match(body.tab) or body.action not in m.SCROLL_ACTIONS:
        raise HTTPException(422, "탭이나 동작이 올바르지 않습니다")
    try:
        return await m.scroll(body.tab, body.action)
    except Refused as e:
        raise HTTPException(503, f"스크롤하지 못했습니다 — {e}") from e


class RespawnIn(BaseModel):
    project: str
    force: bool = False            # 돌고 있는 명령 · 친 글이 있어도(사람이 확인 창에서 [확인]을 눌렀다)


@api.post("/respawn")
async def respawn(body: RespawnIn, request: Request) -> dict[str, Any]:
    """[새 셸](11-10) — 그 프로젝트 창의 셸을 새로 띄워 바뀐 셸 설정을 읽힌다. 명령이 돌고 있거나 친 글이 있으면
    force 없이는 띄우지 않고 {respawned:false, busy}를 돌려준다(화면이 확인 창을 띄운다 — 사람의 sudo · ssh가 돌 수 있는 셸이다)."""
    m = _mgr(request)
    if body.project not in TERM_PROJECTS:
        raise HTTPException(422, "모르는 프로젝트입니다")
    try:
        return await m.respawn(body.project, body.force)
    except Refused as e:
        raise HTTPException(503, f"셸을 새로 띄우지 못했습니다 — {e}") from e


@api.delete("/requests/{rid}")
async def dismiss(rid: int, request: Request) -> dict[str, Any]:
    if not _mgr(request).dismiss(rid):
        raise HTTPException(404, "그런 부탁이 없다(이미 끝났거나 시간이 지났다)")
    return {"ok": True}


@api.post("/requests/{rid}/prefill")
async def prefill(rid: int, request: Request) -> dict[str, Any]:
    m = _mgr(request)
    r = m.pending.get(rid)
    if r is None:
        raise HTTPException(404, "그런 부탁이 없다")
    r.prefilled, r.note = await m.prefill(r)
    return {"ok": r.prefilled, "note": r.note}


@router.post("/hooks/shell")
async def shell_hook(request: Request) -> Response:
    body, err = await _authed_body(request)
    if err:
        return err
    m = getattr(request.app.state, "terminal", None)
    if m is None:
        return Response(status_code=204)
    return JSONResponse(m.on_shell(body), status_code=202)


def _cookie_ok(m: Any, cookies: dict[str, str]) -> bool:
    return m is not None and m.cookie_ok(cookies.get(COOKIE))


@router.get("/terminal", include_in_schema=False)
async def terminal_root() -> RedirectResponse:
    return RedirectResponse("/terminal/", status_code=307)


@router.get("/terminal/{path:path}", include_in_schema=False)
async def terminal_http(path: str, request: Request) -> Response:
    m = getattr(request.app.state, "terminal", None)
    if not _cookie_ok(m, request.cookies):
        return Response("터미널 패널은 대시보드에서 연다(인증 쿠키 없음)", status_code=401, media_type="text/plain; charset=utf-8")
    if not m.running:
        return Response("ttyd가 떠 있지 않다", status_code=503, media_type="text/plain; charset=utf-8")
    hdrs = {k: v for k, v in request.headers.items() if k.lower() in _FWD_REQ}
    url = "http://localhost/terminal/" + path + (f"?{request.url.query}" if request.url.query else "")
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(m.s.terminal_socket)),
                                     timeout=10.0) as c:
            # 받은 그대로(압축된 채) 넘긴다 — httpx가 풀면 Content-Encoding과 본문이 어긋난다
            async with c.stream("GET", url, headers=hdrs) as r:
                content = b"".join([chunk async for chunk in r.aiter_raw()])
    except httpx.HTTPError as e:
        log.warning("ttyd HTTP 실패 %s: %s", path, type(e).__name__)
        return Response("ttyd에 닿지 못했다", status_code=502, media_type="text/plain; charset=utf-8")
    out = {k: v for k, v in r.headers.items() if k.lower() in _FWD_RES}
    # 이 화면은 대시보드 안(같은 출처)에서만 — 다른 사이트가 틀(iframe)에 넣어 클릭을 훔치지 못하게
    out["X-Frame-Options"] = "SAMEORIGIN"
    out["Content-Security-Policy"] = "frame-ancestors 'self'"
    out["Referrer-Policy"] = "no-referrer"
    return Response(content, status_code=r.status_code, headers=out)


def _same_origin(headers: Any) -> bool:
    origin, host = headers.get("origin"), headers.get("host")
    if not origin or not host:
        return False
    return urlsplit(origin).netloc == host


_PROJ_ARG = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")


def _ttyd_args(ws: WebSocket) -> str:
    """iframe 주소의 ?arg=<탭>&arg=<프로젝트>(ttyd 화면이 그대로 WS 주소에 붙인다) — 모양이 맞을 때만 ttyd로 넘긴다(11-10).
    ttyd -a는 이것을 명령 인자로 붙인다(셸을 거치지 않는다). 틀리면 아무것도 넘기지 않아 기준 세션에 붙는다."""
    a = ws.query_params.getlist("arg")
    if not a or not TAB_RE.match(a[0]):
        return ""
    q = [("arg", a[0])]
    if len(a) > 1 and _PROJ_ARG.match(a[1]):
        q.append(("arg", a[1]))
    return "?" + urlencode(q)


@router.websocket("/terminal/ws")
async def terminal_ws(ws: WebSocket) -> None:
    m = getattr(ws.app.state, "terminal", None)
    client = ws.client.host if ws.client else "?"
    if not _cookie_ok(m, ws.cookies):
        log.warning("터미널 WS 거절 %s: 쿠키 없음 · 만료", client)
        await ws.close(1008)
        return
    if not _same_origin(ws.headers):
        log.warning("터미널 WS 거절 %s: Origin이 Host와 다르다", client)
        await ws.close(1008)
        return
    try:
        up = await unix_connect(str(m.s.terminal_socket), "ws://localhost/terminal/ws" + _ttyd_args(ws), subprotocols=["tty"],
                                max_size=None, open_timeout=5, ping_interval=None)
    except Exception as e:  # noqa: BLE001
        log.warning("터미널 WS: ttyd에 닿지 못했다: %s", type(e).__name__)
        await ws.close(1011)
        return
    await ws.accept(subprotocol="tty")
    m.clients += 1

    async def c2u() -> None:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                await up.send(msg["bytes"])
            elif msg.get("text") is not None:
                await up.send(msg["text"])

    async def u2c() -> None:
        async for msg in up:
            if isinstance(msg, bytes):
                await ws.send_bytes(msg)
            else:
                await ws.send_text(msg)

    tasks = [asyncio.create_task(c2u()), asyncio.create_task(u2c())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        m.clients -= 1
        for t in tasks:
            t.cancel()
        await up.close()
        try:
            await ws.close()
        except RuntimeError:
            pass
