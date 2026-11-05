"""/api — 세션 인계 · 세션 조작(11-05, docs/11_handoff.md). API 토큰이 필요하다. 로직은 bridge/handoff.py."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.handoff import HandoffManager
from bridge.inject import Refused

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


class SummaryIn(BaseModel):
    kind: Literal["snapshot", "handoff"] = "snapshot"
    mode: Literal["live", "headless", "compact"] = "live"


class EditIn(BaseModel):
    body: str = Field(min_length=1, max_length=60_000)


class SpawnIn(BaseModel):
    summary_id: int | None = None


class InjectIn(BaseModel):
    cc_session_id: str = Field(min_length=36, max_length=36)
    cwd: str


class ActionIn(BaseModel):
    action: Literal["exit", "stop", "resume", "interrupt"]


def _mgr(request: Request) -> HandoffManager:
    m = getattr(request.app.state, "handoff", None)
    if m is None:
        raise HTTPException(503, "인계 기능이 꺼져 있다")
    return m


async def _row(m: HandoffManager, sid: int) -> Any:
    row = await m.session(sid)
    if row is None:
        raise HTTPException(404, "세션 없음")
    return row


def _refused(e: Refused) -> JSONResponse:
    return JSONResponse({"refused": str(e)}, status_code=409)


@router.get("/sessions/{sid}/handoff")
async def handoff_view(sid: int, request: Request) -> dict[str, Any]:
    m = _mgr(request)
    row = await _row(m, sid)
    return {"controls": await m.controls(row), "summaries": await m.summaries(sid)}


@router.post("/sessions/{sid}/summary")
async def make_summary(sid: int, body: SummaryIn, request: Request) -> JSONResponse:
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        if body.mode == "live":
            r = await m.request_live(row, body.kind)
        elif body.mode == "headless":
            r = await m.request_headless(row, body.kind)
        else:
            r = await m.from_compact(row, body.kind)
    except Refused as e:
        return _refused(e)
    return JSONResponse(r, status_code=202)


@router.put("/summaries/{summary_id}")
async def edit_summary(summary_id: int, body: EditIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _mgr(request).edit(summary_id, body.body))
    except Refused as e:
        return _refused(e)


@router.get("/summaries/{summary_id}/injection")
async def injection_preview(summary_id: int, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _mgr(request).injection(summary_id))
    except Refused as e:
        return _refused(e)


@router.post("/summaries/{summary_id}/inject")
async def inject_summary(summary_id: int, body: InjectIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _mgr(request).inject(summary_id, body.cc_session_id, body.cwd))
    except Refused as e:
        return _refused(e)


@router.post("/sessions/{sid}/spawn")
async def spawn(sid: int, body: SpawnIn, request: Request) -> JSONResponse:
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        return JSONResponse(await m.spawn(row, body.summary_id))
    except Refused as e:
        return _refused(e)


@router.post("/sessions/{sid}/action")
async def action(sid: int, body: ActionIn, request: Request) -> JSONResponse:
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        r = await m.action(row, body.action)
    except Refused as e:
        await m._act(sid, body.action, None, False, f"거부: {e}")
        return _refused(e)
    from bridge.api import dashboard
    dashboard.invalidate()
    return JSONResponse(r)
