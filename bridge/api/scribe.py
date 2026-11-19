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
    # 편이 있는 일의 편(portfolio/<slug>.md, notion/<하위 폴더>/<slug>.md에서 원고 폴더와 .md를 뗀 것. 없으면 폴더 통째로),
    # 문서 고치기의 점검 결과 이름. 11-19 기술문서 편이 하위 폴더 경로라 40자에서 sr.TOPIC_MAX로 늘렸다. 꼴은 start가 본다
    topic: str | None = Field(default=None, max_length=sr.TOPIC_MAX)
    note: str | None = Field(default=None, max_length=sr.NOTE_MAX)   # 문서 고치기 — 물어보기 답(고칠 목록) · 기술문서 쓰기 — 덧붙인 요청


class InboxIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=sr.INBOX_MAX)
    assignee: str = Field(default="scribe", max_length=8)      # 11-09 받는 사람 — scribe(서기 정리) · coder(코더에게)


class AskIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


@router.post("/ask")
async def scribe_ask(body: AskIn, request: Request) -> JSONResponse:
    """서기에게 물어보기(11-10) — 세션 없이 읽기 전용 `claude -p` 한 번. 답만 하고 파일은 고치지 않는다."""
    from bridge import scribe_ask as sa
    from bridge.model_choice import Models
    try:
        r = await sa.ask(request.app.state.store.engine, body.project, body.text, model=Models().task("scribe_ask"))
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    return JSONResponse(r)


def _iso(v: Any) -> Any:
    return v.isoformat() + "Z" if hasattr(v, "isoformat") else v


@router.post("/inbox")
async def inbox_add(body: InboxIn, request: Request) -> JSONResponse:
    """할 일 받는 함(11-09) — 머리줄 [＋ 할 일]. 세션을 거치지 않고 그대로 적는다. 정리는 서기의 「나중에 할 일 정리」."""
    try:
        iid = await sr.inbox_add(request.app.state.store.engine, body.project, body.body, body.assignee)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _cache["data"] = None
    from bridge.api import coder
    coder.invalidate()
    return JSONResponse({"id": iid}, status_code=201)


@router.get("/inbox")
async def inbox_list(request: Request, project: str | None = None, limit: int = 50) -> dict[str, Any]:
    rows = await sr.inbox_list(request.app.state.store.engine, project, max(1, min(limit, 200)))
    return {"items": [{**{k: _iso(v) for k, v in r.items()}, "label": sr.inbox_label(r["state"], r.get("assignee")),
                       "to": sr.ASSIGNEE_KO.get(r.get("assignee") or "scribe", "")} for r in rows]}


@router.post("/inbox/{iid}/drop")
async def inbox_drop(iid: int, request: Request) -> dict[str, Any]:
    ok = await sr.inbox_drop(request.app.state.store.engine, iid)
    _cache["data"] = None
    from bridge.api import coder
    coder.invalidate()
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
        r = await sr.start(m, request.app.state.store.engine, body.project, body.task, body.topic, body.note,
                           publishers=getattr(request.app.state, "publishers", None))
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _cache["data"] = None
    return JSONResponse(r, status_code=202)
