"""/api/scribe — 서기실(12a, 11-06, bridge/scribe_room.py). 할 일 세기 · 시킬 일 · 일 시키기. API 토큰이 필요하다."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge import scribe_room as sr
from bridge.api.auth import require_api_token
from bridge.inject import Refused

router = APIRouter(prefix="/api/scribe", dependencies=[Depends(require_api_token)])
_cache: dict[str, Any] = {"at": 0.0, "data": None}


class StartIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=16)
    topic: str | None = Field(default=None, max_length=40)     # 포트폴리오 쓰기의 주제(config/portfolio.toml slug)


@router.get("/todo")
async def scribe_todo(request: Request) -> dict[str, Any]:
    """프로젝트마다 할 일 — 화면이 1분마다 부른다. git · 파일을 보므로 30초 동안은 같은 답을 준다."""
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < 30:
        return _cache["data"]
    data = {"tasks": sr.TASKS, "projects": await sr.todo(request.app.state.store.engine,
                                                          getattr(request.app.state, "publisher", None))}
    _cache.update(at=time.monotonic(), data=data)
    return data


@router.post("/start")
async def scribe_start(body: StartIn, request: Request) -> JSONResponse:
    """서기 일을 worktree 세션으로 띄운다 — 사람이 서기실 창에서 고른 것만."""
    m = getattr(request.app.state, "handoff", None)
    if m is None:
        raise HTTPException(503, "세션 띄우기가 꺼져 있습니다")
    try:
        r = await sr.start(m, request.app.state.store.engine, body.project, body.task, body.topic)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _cache["data"] = None
    return JSONResponse(r, status_code=202)
