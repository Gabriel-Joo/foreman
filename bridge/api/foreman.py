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
    plan: dict[str, Any]
    inbox_id: int | None = None       # 11-09 코더에게 받은 할 일에서 연 계획 — 시작하면 그 세션이 가져간다(taken_by)


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


@router.post("/start")
async def start(body: StartIn, request: Request) -> JSONResponse:
    return await _run(_d(request).start(body.dispatch_id, body.plan, inbox_id=body.inbox_id))


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
