"""/api/sessions — 붙어 있는 세션 목록과 입력 주입(3단계). API 토큰이 필요하다.

주입은 거부를 포함해 모두 event(source=bridge, type=input)로 남긴다. 거부 이유는 응답 · 로그 · 이벤트 세 곳에.
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from bridge.api.auth import require_api_token
from bridge.approval import load_policy
from bridge.inject import Refused, _status, _tmux_env, bang_check, deliver, tmux
from bridge.liveness import live_sessions
from bridge.mask import Masker
from bridge.models import EventIn, EventSource, EventStatus, EventType

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_api_token)])
log = logging.getLogger("foreman.sessions")
MAX_INPUT = 100_000
_mask = Masker()


class InputIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT)
    command: bool = False  # True면 '/'로 시작하는 입력을 슬래시 명령으로 보낸다('!'는 이 값과 상관없이 bang_check — 11-09)


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
        raise HTTPException(404, "세션이 없습니다")
    sid, cc, char_id, transcript, project, char = row
    payload: dict[str, Any] = {"chars": len(body.text), "lines": body.text.count("\n") + 1, "command": body.command}
    try:
        if not cc:
            raise Refused("CC 세션 ID가 없습니다")
        sent, command = body.text, body.command
        if body.text.strip().startswith("!"):
            # 11-09 '!' 셸 명령 — 앞뒤 공백을 떼고, 승인을 묻는 규칙에 걸리지 않으면 bash 모드로 보낸다(bridge/inject.bang_check)
            pol = load_policy(s.approval_config)
            sent = bang_check(body.text.strip(), lambda tool, inp: pol.decide(tool, inp, None, None, project))
            command = True
            payload["bang"] = True
        res = await deliver(cc, sent, sessions_dir=s.sessions_dir, transcript=transcript, command=command)
    except Refused as e:
        log.warning("주입 거부 session=%d(%s): %s", sid, (cc or "")[:8], e)
        payload["refused"] = str(e)
        _record(pipeline, sid, char_id, body.text, payload, EventStatus.ERROR)
        return JSONResponse({"refused": str(e)}, status_code=409)
    payload |= {k: res[k] for k in ("queued", "guarded", "pane")} | {"delivered": res["delivered"], "esc": res.get("esc", 0), "dialog": res.get("dialog")}
    turn_id = await _turn_for(request, sid, res["delivered"])
    _record(pipeline, sid, char_id, body.text, payload,
            EventStatus.WAITING if res["queued"] else (EventStatus.WORKING if res["delivered"] else EventStatus.ERROR),
            turn_id=turn_id)
    status = 202 if res["delivered"] else 504
    return JSONResponse(res | {"verified": bool(res["delivered"])}, status_code=status)


class ModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=40)


@router.post("/{session_id}/model")
async def switch_model(session_id: int, body: ModelIn, request: Request) -> JSONResponse:
    """패널 머리줄의 모델 표시 → 목록에서 고르면 그 세션에 `/model <id>`를 보낸다(11-05 사용자 요청).
    id는 config/models.toml 목록에 있는 것만(셸 · 입력에 그대로 들어간다). 작업 중이면 대기열에 들어가 지금 일이 끝난 뒤 바뀐다.
    주의: CC의 /model은 그 세션만이 아니라 CC의 새 세션 기본값까지 저장한다 — 브리지가 띄우는 세션은 --model을 넘겨 영향이 없다."""
    hm = request.app.state.handoff
    model = hm.models.resolve(body.model)          # 별칭(opus 등)이 오면 목록의 id로(11-14)
    if not model:
        return JSONResponse({"refused": f"고를 수 없는 모델입니다: {body.model}"}, status_code=409)
    before = _model_setting()
    # 화면에 앞서 바꾼 기록("Set model to …")이 남아 있을 수 있다 — 보내기 전 수를 세 두고 늘어났을 때만 바뀐 것으로 본다
    # (11-05: 옛 줄을 새 결과로 잘못 읽어 기본값을 너무 일찍 "되돌렸고", 그 뒤 CC가 저장한 값이 남았다)
    pane0 = await _pane_of(request, session_id)
    seen0 = _counts(await _screen(hm.socket, pane0)) if pane0 else (0, 0)
    resp = await inject_input(session_id, InputIn(text=f"/model {model}", command=True), request)
    if resp.status_code not in (202, 504):
        return resp
    res = json.loads(resp.body)
    # 고른 모델을 세션 행에 남긴다 — [이어서](--resume) · 새 세션으로 옮기기가 이 값으로 띄운다. 브리지를 다시 띄워도 그대로다
    async with request.app.state.store.engine.begin() as c:
        await c.execute(text("UPDATE character_session SET model = :m WHERE id = :i"), {"m": model, "i": session_id})
    # 바로 실행됐으면 몇 초 안에 끝난다. 대기열이면 지금 일이 끝난 뒤 실행되므로 뒤에서(최대 30분) 따라간다
    if res.get("pane"):
        if res["pane"] != pane0:
            seen0 = (0, 0) if pane0 is None else seen0
        if not res.get("queued") and await _follow(hm.socket, res["pane"], seen0, before, 8):
            res |= {"verified": True, "switched": True}
        else:
            t = asyncio.get_running_loop().create_task(_follow(hm.socket, res["pane"], seen0, before, 30 * 60))
            _bg.add(t)
            t.add_done_callback(_bg.discard)
    return JSONResponse(res, status_code=202 if res.get("switched") or res.get("queued") else resp.status_code)


# 대화가 쌓인 세션에서 /model은 "Switch model? … 전체 대화를 다시 읽는다" 확인 창을 띄운다(11-05 실측, CC 2.1.318).
# 사람이 패널에서 이미 골랐으므로 커서가 "Yes"에 있을 때만 Enter로 고른다
_SWITCH_ASK = re.compile(r"❯\s*1\.\s*Yes, switch to")


async def _pane_of(request: Request, session_id: int) -> str | None:
    row = await _row(request, session_id)
    ls = live_sessions(request.app.state.settings.sessions_dir).get(row[1] or "") if row else None
    te = _tmux_env(ls.pid) if ls else None
    return te[1] if te else None


async def _screen(socket: str, pane: str) -> str | None:
    """보이는 화면 + 스크롤 기록(위로 밀려난 줄까지 세야 수가 줄지 않는다)."""
    try:
        return await tmux(socket, "capture-pane", "-p", "-S", "-3000", "-t", pane)
    except Refused:
        return None


def _counts(screen: str | None) -> tuple[int, int]:
    """(바꾼 결과 줄 수, Yes를 고를 수 있는 확인 창 수)."""
    s = screen or ""
    return s.count("Set model to"), len(_SWITCH_ASK.findall(s))


async def _follow(socket: str, pane: str, seen0: tuple[int, int], before: tuple[bool, Any] | None, secs: float) -> bool:
    """/model이 실제로 바뀔 때까지 화면을 본다 — 새 확인 창이면 Yes, 새 "Set model to"가 뜨면 CC 기본값을 되돌리고 True.
    명령은 트랜스크립트에 글과 다른 모양으로 남아 주입의 제출 확인이 못 맞춘다 — 그래서 화면으로 본다."""
    loop = asyncio.get_running_loop()
    end = loop.time() + secs
    asks_done = seen0[1]
    while loop.time() < end:
        screen = await _screen(socket, pane)
        if screen is None:
            return False                                   # pane이 사라졌다
        done, asks = _counts(screen)
        # 바뀐 신호 둘: CC가 설정 파일에 새 기본값을 썼다(가장 확실하다 — 11-05 실측, 대기열에서 실행된 뒤 CC가 화면을
        # 다시 그려 스크롤 기록이 비었다) 또는 화면에 결과 줄이 늘었다(설정 값이 원래 같은 모델이었을 때)
        if (before is not None and _model_setting() not in (before, None)) or done > seen0[0]:
            # CC의 /model은 새 세션 기본값(~/.claude/settings.json "model")까지 저장한다 — 버튼은 "이 세션만"이므로 되돌린다
            await asyncio.sleep(0.5)
            _restore_model_setting(before)
            return True
        if asks > asks_done and _SWITCH_ASK.search(screen.rsplit("Switch model?", 1)[-1]):
            await tmux(socket, "send-keys", "-t", pane, "Enter")
            asks_done = asks
            log.info("모델 바꾸기 확인 창 — Yes를 골랐다 pane=%s", pane)
            await asyncio.sleep(1.0)
            continue
        await asyncio.sleep(0.5 if secs <= 10 else 2.0)
    return False


CC_SETTINGS = Path.home() / ".claude" / "settings.json"
_bg: set[asyncio.Task[Any]] = set()


def _model_setting() -> tuple[bool, Any] | None:
    """(키가 있나, 값). 파일을 못 읽으면 None — 그때는 되돌리지 않는다."""
    try:
        d = json.loads(CC_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return ("model" in d, d.get("model"))


def _restore_model_setting(before: tuple[bool, Any] | None) -> bool:
    """보내기 전의 "model" 값으로 되돌린다(다른 키는 그대로). 바뀐 게 없으면 False."""
    if before is None:
        return False
    try:
        d = json.loads(CC_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if ("model" in d, d.get("model")) == before:
        return False
    if before[0]:
        d["model"] = before[1]
    else:
        d.pop("model", None)
    tmp = CC_SETTINGS.with_suffix(".json.foreman-tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, CC_SETTINGS.stat().st_mode & 0o777)
    os.replace(tmp, CC_SETTINGS)
    log.info("CC 기본 모델을 되돌림 → %s", before[1] if before[0] else "(키 없음)")
    return True


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
