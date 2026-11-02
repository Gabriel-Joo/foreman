"""/api/sessions — 붙어 있는 세션 목록과 입력 주입(3단계). API 토큰이 필요하다.

주입은 거부를 포함해 모두 event(source=bridge, type=input)로 남긴다. 거부 이유는 응답 · 로그 · 이벤트 세 곳에.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from bridge.api.auth import require_api_token
from bridge.inject import Refused, _status, _tmux_env, deliver
from bridge.liveness import live_sessions
from bridge.mask import Masker
from bridge.models import EventIn, EventSource, EventStatus, EventType

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_api_token)])
log = logging.getLogger("foreman.sessions")
MAX_INPUT = 100_000
_mask = Masker()


class InputIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT)
    command: bool = False  # True면 '/'로 시작하는 입력을 슬래시 명령으로 보낸다('!'는 언제나 막는다)


async def _row(request: Request, session_id: int) -> Any:
    async with request.app.state.store.engine.connect() as c:
        return (await c.execute(text(
            "SELECT cs.id, cs.cc_session_id, cs.character_id, tf.path, p.name, ch.name "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id LEFT JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
            "WHERE cs.id = :id"), {"id": session_id})).first()


@router.get("")
async def list_sessions(request: Request) -> list[dict[str, Any]]:
    s = request.app.state.settings
    live = live_sessions(s.sessions_dir)
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT cs.id, cs.cc_session_id, cs.cwd, p.name, ch.name, "
            "(SELECT t.id FROM turn t WHERE t.session_id = cs.id AND t.ended_at IS NULL ORDER BY t.seq DESC LIMIT 1) "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.detached_at IS NULL AND cs.type = 'agent' "
            "ORDER BY cs.id"))).all()
    out = []
    for sid, cc, cwd, project, char, open_turn in rows:
        ls = live.get(cc or "")
        te = _tmux_env(ls.pid) if ls else None
        out.append({
            "id": sid, "cc_session_id": cc, "project": project, "character": char, "cwd": cwd,
            "pid": ls.pid if ls else None, "state": ls.state if ls else None,
            "status": _status(s.sessions_dir, ls.pid) if ls else None, "open_turn": open_turn,
            "tmux_pane": te[1] if te else None,
            # 미리 보는 값 — 실제 주입 때 pane 포그라운드까지 다시 확인한다
            "injectable": bool(ls and te and ls.state != "T"),
        })
    return out


@router.post("/{session_id}/input")
async def inject_input(session_id: int, body: InputIn, request: Request) -> JSONResponse:
    s = request.app.state.settings
    pipeline = request.app.state.pipeline
    row = await _row(request, session_id)
    if row is None:
        raise HTTPException(404, "세션 없음")
    sid, cc, char_id, transcript, project, char = row
    payload: dict[str, Any] = {"chars": len(body.text), "lines": body.text.count("\n") + 1, "command": body.command}
    try:
        if not cc:
            raise Refused("CC 세션 ID가 없다")
        res = await deliver(cc, body.text, sessions_dir=s.sessions_dir, transcript=transcript, command=body.command)
    except Refused as e:
        log.warning("주입 거부 session=%d(%s): %s", sid, (cc or "")[:8], e)
        payload["refused"] = str(e)
        _record(pipeline, sid, char_id, body.text, payload, EventStatus.ERROR)
        return JSONResponse({"refused": str(e)}, status_code=409)
    payload |= {k: res[k] for k in ("queued", "guarded", "pane")} | {"delivered": res["delivered"]}
    turn_id = await _turn_for(request, sid, res["delivered"])
    _record(pipeline, sid, char_id, body.text, payload,
            EventStatus.WAITING if res["queued"] else (EventStatus.WORKING if res["delivered"] else EventStatus.ERROR),
            turn_id=turn_id)
    status = 202 if res["delivered"] else 504
    return JSONResponse(res | {"verified": bool(res["delivered"])}, status_code=status)


async def _turn_for(request: Request, sid: int, delivered: dict[str, Any] | None) -> int | None:
    """주입이 들어간 턴 — 새 턴이면 그 promptId의 턴(조립기가 이미 적재했을 수 있다), 대기열이면 열린 턴."""
    try:
        async with request.app.state.store.engine.connect() as c:
            if delivered and delivered.get("prompt_id"):
                r = (await c.execute(text("SELECT id FROM turn WHERE prompt_id = :p"), {"p": delivered["prompt_id"]})).first()
                if r:
                    return r[0]
            r = (await c.execute(text(
                "SELECT id FROM turn WHERE session_id = :s AND ended_at IS NULL ORDER BY seq DESC LIMIT 1"), {"s": sid})).first()
            return r[0] if r else None
    except Exception:  # noqa: BLE001 — 연결은 화면 편의. 못 찾으면 비워 둔다
        return None


def _record(pipeline: Any, sid: int, char_id: int, text_: str, payload: dict[str, Any], status: EventStatus,
            turn_id: int | None = None) -> None:
    try:
        pipeline.submit(EventIn(source=EventSource.BRIDGE, type=EventType.INPUT, session_id=sid, character_id=char_id,
                                turn_id=turn_id, target=_mask.text(text_), status=status, payload=payload))
    except Exception as e:  # noqa: BLE001 — 기록 실패가 주입 결과를 바꾸지 않는다
        log.warning("주입 기록 실패: %s", type(e).__name__)
