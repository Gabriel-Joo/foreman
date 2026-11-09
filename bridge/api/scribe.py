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


class InboxIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=sr.INBOX_MAX)


def _iso(v: Any) -> Any:
    return v.isoformat() + "Z" if hasattr(v, "isoformat") else v


@router.post("/inbox")
async def inbox_add(body: InboxIn, request: Request) -> JSONResponse:
    """할 일 받는 함(11-09) — 머리줄 [＋ 할 일]. 세션을 거치지 않고 그대로 적는다. 정리는 서기의 「나중에 할 일 정리」."""
    try:
        iid = await sr.inbox_add(request.app.state.store.engine, body.project, body.body)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _cache["data"] = None
    return JSONResponse({"id": iid}, status_code=201)


@router.get("/inbox")
async def inbox_list(request: Request, project: str | None = None, limit: int = 50) -> dict[str, Any]:
    rows = await sr.inbox_list(request.app.state.store.engine, project, max(1, min(limit, 200)))
    return {"items": [{**{k: _iso(v) for k, v in r.items()}, "label": sr.INBOX_LABEL.get(r["state"], r["state"])} for r in rows]}


@router.post("/inbox/{iid}/drop")
async def inbox_drop(iid: int, request: Request) -> dict[str, Any]:
    ok = await sr.inbox_drop(request.app.state.store.engine, iid)
    _cache["data"] = None
    return {"ok": ok}


@router.get("/todo")
async def scribe_todo(request: Request) -> dict[str, Any]:
    """프로젝트마다 할 일 — 화면이 1분마다 부른다. git · 파일을 보므로 30초 동안은 같은 답을 준다."""
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < 30:
        return _cache["data"]
    data = {"tasks": sr.TASKS, "projects": await sr.todo(request.app.state.store.engine,
                                                          getattr(request.app.state, "publishers", None),
                                                          getattr(request.app.state, "docsync", None))}
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
