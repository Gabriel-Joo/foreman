"""터미널 패널(7단계) — ttyd 소켓으로 가는 길과 셸 기록 hook.

  POST /api/terminal/session     API 토큰 → 쿠키(HttpOnly · SameSite=Strict · Path=/terminal). 패널을 열 때 받는다
  GET  /api/terminal             상태 + 기다리는 부탁(CC가 "이 명령을 실행해 주세요"라고 한 것)
  POST /api/terminal/open        {project, tab} — 그 탭이 그 프로젝트의 셸 창을 보게 한다(없으면 그 저장소 폴더에서 만든다, 11-10)
  GET  /api/terminal/window?tab= 그 탭이 지금 보는 창(바꾸지 않는다)
  POST /api/terminal/respawn     {project, force} — 그 창의 셸을 새로 띄운다(바뀐 셸 설정을 읽게, 11-10). 화면 단추는 11-14에 뺐다
  POST /api/terminal/clear       {project, force} — [셸 비우기](11-14) 그 창의 셸 화면 · 스크롤백을 비운다
  DELETE /api/terminal/requests/{id}   부탁을 닫는다(결과를 전달하지 않는다)
  POST /api/terminal/requests/{id}/prefill   셸 입력 줄에 다시 채운다
  GET  /terminal/…  · WS /terminal/ws       쿠키를 확인하고 ttyd(UNIX 소켓)로 그대로 넘긴다
  GET  /api/terminal/cc/{sid}    「CC 화면」 탭(11-14) — 그 세션 CC 창에 붙을 수 있나(안 되면 까닭)
  GET  /ccscreen/…  · WS /ccscreen/ws?arg=<세션 번호>&arg=<탭>   CC 화면 ttyd. 브라우저가 준 세션 번호를 브리지가 확인된
                                 tmux 창으로 바꿔 넘긴다(브라우저가 붙을 곳을 정하지 않는다). 열고 닫은 것만 session_action에
  POST /hooks/shell              셸 PROMPT_COMMAND(hook 토큰) — 친 명령 · 종료 코드 · 위치

ttyd는 TCP 포트를 열지 않는다. 브라우저는 이 브리지(127.0.0.1)를 거쳐서만 닿고, 쿠키는 API 토큰을 가진 사람만 받는다.
WS는 Origin이 Host와 같아야 한다(다른 사이트가 브라우저 쿠키로 셸을 여는 것 — cross-site WebSocket hijacking — 을 막는다).
"""

import asyncio
import logging
import re
import time
from pathlib import Path
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
from bridge.terminal import CC_CLOSE, CC_OPEN, CC_VIEW_PREFIX, COOKIE, PANE_RE, TAB_RE, TERM_PROJECTS

log = logging.getLogger("foreman.terminal")
api = APIRouter(prefix="/api/terminal", dependencies=[Depends(require_api_token)])
router = APIRouter()

_FWD_REQ = ("accept", "accept-encoding", "accept-language", "if-none-match", "if-modified-since", "user-agent")
_FWD_RES = ("content-type", "content-encoding", "etag", "last-modified", "cache-control", "vary")


def _mgr(request: Request) -> Any:
    m = getattr(request.app.state, "terminal", None)
    if m is None:
        raise HTTPException(503, "셸 · CC 화면이 꺼져 있습니다")
    return m


@api.post("/session")
async def open_session(request: Request) -> JSONResponse:
    m = _mgr(request)
    resp = JSONResponse({"ok": True, "running": m.running, "cc_running": m.cc_running})
    # 같은 쿠키를 「CC 화면」(/ccscreen, 11-14)에도 — 경로마다 하나씩 붙인다(Path가 다르면 브라우저가 따로 보낸다)
    tok = m.new_cookie()
    for path in ("/terminal", "/ccscreen"):
        resp.set_cookie(COOKIE, tok, max_age=int(m.s.terminal_cookie_ttl_s), path=path,
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
        raise HTTPException(503, f"셸 창을 읽지 못했습니다 — {e}") from e


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
        raise HTTPException(503, f"셸 창을 고르지 못했습니다 — {e}") from e


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


class ClearIn(BaseModel):
    project: str
    force: bool = False            # 돌고 있는 명령 · 친 글이 있어도(사람이 확인 창에서 [확인]을 눌렀다)


@api.post("/clear")
async def clear(body: ClearIn, request: Request) -> dict[str, Any]:
    """[셸 비우기](11-14) — 그 프로젝트 창의 셸 화면 · 스크롤백을 비운다(셸은 그대로). 명령이 돌고 있거나 친 글이 있으면
    force 없이는 비우지 않고 {cleared:false, busy}를 돌려준다(화면이 확인 창을 띄운다)."""
    m = _mgr(request)
    if body.project not in TERM_PROJECTS:
        raise HTTPException(422, "모르는 프로젝트입니다")
    try:
        return await m.clear(body.project, body.force)
    except Refused as e:
        raise HTTPException(503, f"셸을 비우지 못했습니다 — {e}") from e


@api.get("/cc/{sid}")
async def cc_state(sid: int, request: Request) -> dict[str, Any]:
    """「CC 화면」 탭(11-14) — 그 세션 CC 창에 붙을 수 있나. {ok, tmux_session, size, running} 또는 {ok:false, reason, running}.
    탭이 열려 있는 동안 화면이 다시 물어 끝남 · ttyd 꺼짐을 까닭으로 띄운다(조용히 빈 화면이 되지 않게)."""
    m = _mgr(request)
    try:
        r = await m.cc_target(sid)
    except Refused as e:
        r = {"ok": False, "reason": f"CC 창을 확인하지 못했습니다 — {e}", "running": m.cc_running}
    if r.get("ok") and not r.get("running"):
        r = {**r, "ok": False, "reason": "CC 화면 서버(ttyd)가 떠 있지 않습니다 — 브리지 로그(.run/ttyd-cc.log)를 확인해 주세요"}
    r.pop("pane", None)            # 화면은 tmux 창 대상을 몰라도 된다(붙을 곳은 브리지가 정한다)
    return r


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
        return Response("셸은 대시보드에서 엽니다(인증 쿠키가 없습니다)", status_code=401, media_type="text/plain; charset=utf-8")
    if not m.running:
        return Response("셸 서버(ttyd)가 떠 있지 않습니다", status_code=503, media_type="text/plain; charset=utf-8")
    return await _proxy_http(m.s.terminal_socket, "/terminal/", path, request)


@router.get("/ccscreen", include_in_schema=False)
async def ccscreen_root() -> RedirectResponse:
    return RedirectResponse("/ccscreen/", status_code=307)


@router.get("/ccscreen/{path:path}", include_in_schema=False)
async def ccscreen_http(path: str, request: Request) -> Response:
    """「CC 화면」 ttyd의 화면 파일(11-14). 주소의 ?arg=<세션 번호>는 ttyd 화면이 WS 주소에 그대로 붙인다 — WS에서 확인한다."""
    m = getattr(request.app.state, "terminal", None)
    if not _cookie_ok(m, request.cookies):
        return Response("CC 화면은 대시보드 세션 패널에서 엽니다(인증 쿠키가 없습니다)", status_code=401,
                        media_type="text/plain; charset=utf-8")
    if not m.cc_running:
        return Response("CC 화면 서버(ttyd)가 떠 있지 않습니다", status_code=503, media_type="text/plain; charset=utf-8")
    return await _proxy_http(m.s.ccscreen_socket, "/ccscreen/", path, request)


async def _proxy_http(sock: Path, base: str, path: str, request: Request) -> Response:
    hdrs = {k: v for k, v in request.headers.items() if k.lower() in _FWD_REQ}
    url = "http://localhost" + base + path + (f"?{request.url.query}" if request.url.query else "")
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(sock)),
                                     timeout=10.0) as c:
            # 받은 그대로(압축된 채) 넘긴다 — httpx가 풀면 Content-Encoding과 본문이 어긋난다
            async with c.stream("GET", url, headers=hdrs) as r:
                content = b"".join([chunk async for chunk in r.aiter_raw()])
    except httpx.HTTPError as e:
        log.warning("ttyd HTTP 실패 %s%s: %s", base, path, type(e).__name__)
        return Response("ttyd에 닿지 못했습니다", status_code=502, media_type="text/plain; charset=utf-8")
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
    try:
        await _pump(ws, up)
    finally:
        m.clients -= 1


def _cc_args(ws: WebSocket) -> tuple[int, str] | None:
    """「CC 화면」 WS 주소의 ?arg=<세션 번호>&arg=<탭> — 모양이 맞을 때만. 브라우저가 tmux 대상을 줄 길은 없다(세션 번호뿐)."""
    a = ws.query_params.getlist("arg")
    if len(a) != 2 or not re.fullmatch(r"[0-9]{1,12}", a[0]) or not TAB_RE.match(a[1]):
        return None
    return int(a[0]), a[1]


@router.websocket("/ccscreen/ws")
async def ccscreen_ws(ws: WebSocket) -> None:
    """「CC 화면」(11-14) — 쿠키 · 같은 출처 → 세션 번호를 DB · 살아 있는 프로세스로 확인한 tmux 창으로 바꿔 ttyd에 넘긴다.
    열고 닫은 것만 session_action(ccview-open · ccview-close)에 남긴다. 키 하나하나는 남기지 않는다(사람이 CC 창에 직접 치는 길이다)."""
    m = getattr(ws.app.state, "terminal", None)
    client = ws.client.host if ws.client else "?"
    if not _cookie_ok(m, ws.cookies):
        log.warning("CC 화면 WS 거절 %s: 쿠키 없음 · 만료", client)
        await ws.close(1008)
        return
    if not _same_origin(ws.headers):
        log.warning("CC 화면 WS 거절 %s: Origin이 Host와 다르다", client)
        await ws.close(1008)
        return
    args = _cc_args(ws)
    if args is None:
        log.warning("CC 화면 WS 거절 %s: 세션 번호 · 탭 모양이 틀렸다", client)
        await ws.close(1008)
        return
    sid, tab = args
    try:
        t = await m.cc_target(sid)
    except Refused as e:
        t = {"ok": False, "reason": str(e)}
    if not t.get("ok") or not PANE_RE.match(t.get("pane") or ""):
        log.warning("CC 화면 WS 거절 session=%d: %s", sid, t.get("reason"))
        await ws.close(1008)
        return
    q = urlencode([("arg", t["pane"]), ("arg", tab)])
    try:
        await m.sweep_views(prefix=CC_VIEW_PREFIX)      # 붙기 전에 끊겨 남은 탭 세션(창은 CC 세션 쪽에 그대로)
    except Exception as e:  # noqa: BLE001 — 치우기 실패가 화면을 막지 않는다
        log.warning("CC 화면 남은 탭 세션 치우기 실패: %s", type(e).__name__)
    try:
        up = await unix_connect(str(m.s.ccscreen_socket), "ws://localhost/ccscreen/ws?" + q, subprotocols=["tty"],
                                max_size=None, open_timeout=5, ping_interval=None)
    except Exception as e:  # noqa: BLE001
        log.warning("CC 화면 WS: ttyd에 닿지 못했다: %s", type(e).__name__)
        await ws.close(1011)
        return
    await ws.accept(subprotocol="tty")
    started = time.monotonic()
    where = f"tmux {t['tmux_session']} {t['pane']} 크기 {t['size']} 탭 {tab}"
    await m.record_action(sid, CC_OPEN, True, where)
    log.info("CC 화면 열림 session=%d %s", sid, where)
    try:
        await _pump(ws, up)
    finally:
        secs = round(time.monotonic() - started)
        await m.record_action(sid, CC_CLOSE, True, f"{where} · {secs}초")
        log.info("CC 화면 닫힘 session=%d (%d초)", sid, secs)


async def _pump(ws: WebSocket, up: Any) -> None:
    """브라우저 WS ↔ ttyd WS를 그대로 잇는다(한쪽이 끝나면 둘 다 닫는다)."""
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
        for t in tasks:
            t.cancel()
        await up.close()
        try:
            await ws.close()
        except RuntimeError:
            pass
