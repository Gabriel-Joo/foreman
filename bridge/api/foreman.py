"""/api/foreman — 포먼 디스패처(11-05, docs/11_foreman_dispatch.md). 사람이 말하면 계획 → 사람이 고쳐 승인하면 시작."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.inject import Refused

router = APIRouter(prefix="/api/foreman", dependencies=[Depends(require_api_token)])


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class StartIn(BaseModel):
    dispatch_id: int
    plan: dict[str, Any]


def _d(request: Request) -> Any:
    d = getattr(request.app.state, "foreman", None)
    if d is None:
        raise HTTPException(503, "포먼 디스패처가 꺼져 있습니다")
    return d


@router.post("/plan")
async def plan(body: AskIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _d(request).plan(body.text))
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)


@router.post("/start")
async def start(body: StartIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _d(request).start(body.dispatch_id, body.plan))
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)


@router.get("/context")
async def context(request: Request, text: str = "") -> dict[str, Any]:
    """포먼에게 넣는 상황 묶음 — 확인용(무엇을 보고 판단하는지)."""
    s = await _d(request).context(text or "(요청 없음)")
    return {"chars": len(s), "context": s}
