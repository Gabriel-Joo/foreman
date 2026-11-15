"""/api/foreman — 디스패처(11-05, docs/11_foreman_dispatch.md · 11-08 docs/14_dispatcher_note_wake.md).
사람이 말하면 계획 → 사람이 고쳐 승인하면 시작(노트 고치기도 같이). 자동 기상 2단계의 제안도 여기서 열고 시작 · 버린다."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.inject import Refused

router = APIRouter(prefix="/api/foreman", dependencies=[Depends(require_api_token)])


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    project: str | None = Field(default=None, max_length=64)   # 그 방의 팀장실에서 말하면


class StartIn(BaseModel):
    dispatch_id: int
    plan: dict[str, Any] | None = None   # 비우고 use_saved면 저장된 계획(관리자에게 넘긴 것 — bridge/handover.py)
    use_saved: bool = False
    inbox_id: int | None = None       # 11-09 코더에게 받은 할 일에서 연 계획 — 시작하면 그 세션이 가져간다(taken_by)
    inbox_ids: list[int] | None = Field(default=None, max_length=20)   # 11-11 할 일 여럿을 묶은 계획


class HandoverIn(BaseModel):
    dispatch_id: int
    plan: dict[str, Any]
    inbox_ids: list[int] | None = Field(default=None, max_length=20)


def _d(request: Request) -> Any:
    d = getattr(request.app.state, "foreman", None)
    if d is None:
        raise HTTPException(503, "계획 세우기가 꺼져 있습니다")
    return d


async def _run(coro: Any) -> JSONResponse:
    try:
        return JSONResponse(await coro)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)


@router.post("/plan")
async def plan(body: AskIn, request: Request) -> JSONResponse:
    return await _run(_d(request).plan(body.text, body.project))


def alert(request: Request, project: str | None, msg: str) -> None:
    """텔레그램 한 번(11-11 — 여러 세션 중 일부만 뜸 · 띄우기 기록 실패가 조용히 지나가지 않게). 알림이 꺼져 있으면 로그만."""
    import logging
    n = getattr(request.app.state, "notifier", None)
    logging.getLogger("foreman.dispatch").warning("%s", msg)
    if n is None:
        return
    rule = n.rules.for_project(project or "foreman") if getattr(n, "rules", None) else None
    try:
        n.send_direct(project or "foreman", "direct", None, f"{(rule and rule.prefix) or '[FOREMAN]'} ⚠ {msg}")
    except Exception:  # noqa: BLE001
        pass


@router.post("/start")
async def start(body: StartIn, request: Request) -> JSONResponse:
    async def go() -> dict[str, Any]:
        d = _d(request)
        plan = body.plan
        if plan is None:
            if not body.use_saved:
                raise Refused("계획(plan)이 없습니다. 저장된 계획으로 시작하려면 use_saved: true")
            plan = await d.saved_plan(body.dispatch_id)
        inbox = list(body.inbox_ids or plan.get("inbox_ids") or []) + ([body.inbox_id] if body.inbox_id else [])
        out = await d.start(body.dispatch_id, plan, inbox_id=inbox or None)
        if out.get("failed"):        # 여러 세션 중 일부만 떴다 — 화면(note)과 함께 텔레그램 한 번
            alert(request, plan.get("project"), f"계획 #{body.dispatch_id}에서 세션 {len(out['failed'])}개를 띄우지 못했습니다 — "
                  + "; ".join(f"「{f['title'] or f['idx'] + 1}」 {f['error'][:100]}" for f in out["failed"]))
        return out
    return await _run(go())


def _handover(request: Request) -> Any:
    h = getattr(request.app.state, "handover", None)
    if h is None or not h.cfg.enabled:
        raise HTTPException(503, "관리자에게 넘기기가 꺼져 있습니다(config/managers.toml [handover] enabled)")
    return h


@router.post("/handover")
async def handover(body: HandoverIn, request: Request) -> JSONResponse:
    """계획 카드 [관리자에게 보내기](11-11) — 고친 계획을 저장하고 그 프로젝트 관리자 입력 칸에 넣는다. 띄우기는 관리자가 /start로."""
    h = _handover(request)
    return await _run(h.send(body.dispatch_id, body.plan, body.inbox_ids))


@router.get("/handover")
async def handover_state(request: Request) -> dict[str, Any]:
    """카드가 [관리자에게 보내기]를 보일지 · 프로젝트마다 관리자가 있는지."""
    h = getattr(request.app.state, "handover", None)
    if h is None or not h.cfg.enabled:
        return {"enabled": False}
    return {"enabled": True, "wait_min": h.cfg.wait_min, "health": h.health,
            "managers": {b["project"]: (b["manager"] or {}).get("session_id") for b in await h.m.board()}}


async def record_direct(request: Request, origin: str, cwd: str | None, session: dict[str, Any], result: dict[str, Any] | None,
                        error: str | None = None, req_text: str | None = None, summary_id: int | None = None) -> str | None:
    """교장 계획 없이 띄운 것(/api/spawn · 옮기기)도 dispatch 기록을 남긴다(교장 ④). 화면에 붙일 글(겹침 · 기록 실패)을 돌려준다.
    기록이 실패해도 띄우기는 되돌리지 않는다 — 대신 글 + 텔레그램 한 번."""
    from bridge.foreman import record_spawn, sessions_of
    store = getattr(request.app.state, "store", None)
    if store is None:
        return None
    project = (result or {}).get("project")
    if project is None and cwd:
        hm = getattr(request.app.state, "handoff", None)
        try:
            project = hm.project_of(cwd)[0] if hm and hm.project_of else None
        except Exception:  # noqa: BLE001
            project = None
    try:
        did = await record_spawn(store.engine, origin, project, session, result, error, req_text, summary_id)
    except Exception as e:  # noqa: BLE001 — 0030 전 DB 등
        alert(request, project, f"띄우기 기록(dispatch)을 남기지 못했습니다({type(e).__name__}) — 세션 {(result or {}).get('session_id')}")
        return f"띄우기 기록을 남기지 못했습니다({type(e).__name__})."
    note = None
    d = getattr(request.app.state, "foreman", None)
    if d is not None and project and result and session.get("files"):
        ss = sessions_of({"sessions": [session], "sessions_edit": True})
        try:
            ov, fw = await d.file_conflicts(project, ss, did, exclude_session=result.get("session_id"))
        except Exception as e:  # noqa: BLE001
            ov, fw = [], [f"맡을 파일 겹침을 보지 못했습니다({type(e).__name__})"]
        if ov or fw:
            note = " ".join([o["text"] + "." for o in ov] + [w + "." for w in fw])
    return note


@router.get("/merge-order")
async def merge_order(project: str, request: Request, branches: str = "") -> JSONResponse:
    """합칠 브랜치가 둘 이상일 때 — 같은 파일을 건드리는 쌍 · 실제 충돌(merge-tree) · 권하는 순서 · 까닭(11-11 일곱).
    합치기 카드(생명주기 쪽)가 부른다. branches=cc/a,cc/b로 좁힐 수 있다. 저장소는 바꾸지 않는다."""
    only = [b.strip() for b in branches.split(",") if b.strip()] or None
    return await _run(_d(request).merge_order(project, only))


@router.get("/dispatch/{dispatch_id}")
async def get_dispatch(dispatch_id: int, request: Request) -> JSONResponse:
    return await _run(_d(request).get(dispatch_id))


@router.post("/dispatch/{dispatch_id}/discard")
async def discard(dispatch_id: int, request: Request) -> JSONResponse:
    async def go() -> dict[str, Any]:
        await _d(request).discard(dispatch_id)
        return {"ok": True}
    return await _run(go())


@router.get("/state")
async def state(request: Request) -> dict[str, Any]:
    """감독실 캐릭터 — 계획을 세우는 중 · [시작]을 기다리는 자동 제안."""
    return await _d(request).state()


@router.get("/notes")
async def notes(project: str, request: Request) -> JSONResponse:
    return await _run(_d(request).notes_of(project))


@router.post("/notes/{note_id}/retire")
async def retire(note_id: int, request: Request) -> JSONResponse:
    async def go() -> dict[str, Any]:
        await _d(request).retire_note(note_id)
        return {"ok": True}
    return await _run(go())


@router.post("/notes/{note_id}/restore")
async def restore(note_id: int, request: Request) -> JSONResponse:
    """기계가 내린 줄을 사람이 되살린다(11-13) — 다시 자동으로 내리지 않는다."""
    async def go() -> dict[str, Any]:
        await _d(request).restore_note(note_id)
        return {"ok": True}
    return await _run(go())


@router.post("/notes/{note_id}/touch")
async def touch(note_id: int, request: Request) -> JSONResponse:
    """「아직 진행 중」 — 낡음 줄의 확인 시각을 지금으로(11-13)."""
    async def go() -> dict[str, Any]:
        await _d(request).touch_note(note_id)
        return {"ok": True}
    return await _run(go())


class WakeTestIn(BaseModel):
    project: str | None = Field(default=None, max_length=64)
    kind: str = Field(default="infra_down", max_length=20)
    text: str = Field(min_length=1, max_length=1500)


@router.post("/wake-test")
async def wake_test(body: WakeTestIn, request: Request) -> JSONResponse:
    """자동 기상 2단계 시험 — 알림 글 하나로 실제 경로(디스패처 계획 → 텔레그램 · 화면 제안)를 끝까지 돌린다. 글 앞에 〔시험〕이 붙는다."""
    import time

    from bridge.wake import KINDS
    w = getattr(request.app.state, "waker", None)
    if w is None:
        return JSONResponse({"refused": "자동 기상이 꺼져 있습니다(config/wake.toml)"}, status_code=409)
    if body.kind not in KINDS:
        return JSONResponse({"refused": f"모르는 종류입니다 — {', '.join(KINDS)}"}, status_code=409)
    key = f"test:{body.kind}:{int(time.time())}"
    w.failure(body.project, body.kind, key, f"〔시험〕 {body.text}")
    return JSONResponse({"ok": True, "wake_key": key})


@router.get("/context")
async def context(request: Request, text: str = "", project: str | None = None) -> dict[str, Any]:
    """디스패처에게 넣는 상황 묶음 — 확인용(무엇을 보고 판단하는지)."""
    s = await _d(request).context(text or "(요청 없음)", project)
    return {"chars": len(s), "context": s}
