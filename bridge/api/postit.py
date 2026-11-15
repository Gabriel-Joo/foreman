"""/api/postit — 포스트잇(11-15, bridge/postit.py). 머리 탭 포스트잇 · 서기실이 같은 목록을 본다. API 토큰이 필요하다.

- GET  /api/postit?project=          열린 것 · 판정 · 최근 닫힌 것 · 요약(한 프로젝트)
- GET  /api/postit/summary           프로젝트마다 요약(머리 탭 개수 · 가장 오래된 날)
- POST /api/postit {project, body, session?}   하나 올리기. session(관리자 자기 세션 id)을 주면 출처 said, 근거는 그 세션의 마지막 사람 턴
- POST /api/postit/save {project, body?, confirm?}   [저장] — 적은 글을 올리고 확인 전 줄을 받아들인다
- POST /api/postit/{id}/close {reason: drop|limit|done, note?}   [x] · [→] · 끝남
- POST /api/postit/refresh {project}   [갱신] — 조사 세션을 띄운다
- POST /api/postit/check/{cid} {action: close|keep}   판정 한 줄을 사람이 닫거나 남긴다
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge import postit as pi
from bridge.api.auth import require_api_token
from bridge.inject import Refused

router = APIRouter(prefix="/api/postit", dependencies=[Depends(require_api_token)])


class AddIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=pi.MAX)
    session: int | None = None          # 관리자 자기 세션 id — 주면 출처 said(대화에서 사람이 말함)
    source: Literal["note", "todo", "said"] | None = None


class SaveIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    body: str | None = Field(default=None, max_length=pi.MAX)
    confirm: list[int] = Field(default_factory=list, max_length=200)


class CloseIn(BaseModel):
    reason: Literal["drop", "limit", "done"]
    note: str | None = Field(default=None, max_length=2000)


class RefreshIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)


class CheckIn(BaseModel):
    action: Literal["close", "keep"]


def _iso(v: Any) -> Any:
    return v.isoformat() + "Z" if hasattr(v, "isoformat") else v


def _changed() -> None:
    """서기 할 일(30초 캐시) · 코더 맡길 일을 다시 세게."""
    from bridge.api import coder, scribe
    scribe._cache["data"] = None
    coder.invalidate()


def _row(x: dict[str, Any], ck: dict[str, Any] | None) -> dict[str, Any]:
    out = {k: _iso(v) for k, v in x.items()}
    out["confirmed"] = bool(x.get("confirmed"))
    out["label"] = pi.STATE_KO.get(x["state"], x["state"])
    out["source_label"] = pi.SOURCE_KO.get(x.get("source") or "", x.get("source") or "")
    out["check"] = _check(ck) if ck else None
    # 코더 추천 — [갱신]이 「남음, 코더에게 맡길 만함」으로 본 것 · 옛 「코더에게」 줄. 이미 코더가 가져간 것은 빼고
    out["recommend"] = x["state"] == "new" and bool((ck and ck["coder"]) or x.get("assignee") == "coder")
    return out


def _check(k: dict[str, Any]) -> dict[str, Any]:
    out = {kk: _iso(v) for kk, v in k.items()}
    out["coder"] = bool(k.get("coder"))
    out["label"] = pi.VERDICT_KO.get(k["verdict"], k["verdict"])
    return out


async def view(engine: Any, project: str) -> dict[str, Any]:
    from bridge import scribe_room as sr
    posts = await pi.items(engine, project)
    cks = await pi.checks(engine, project)
    by = {k["item"]: k for k in cks}
    closed = await pi.items(engine, project, open_only=False, limit=20)
    summ = await pi.summary(engine, project, await sr.later_since(engine, project))
    return {"project": project, "items": [_row(x, by.get(f"p:{x['id']}")) for x in posts],
            "readme_checks": [_check(k) for k in cks if k["item"].startswith("L:")],
            "closed": [_row(x, None) for x in closed], "summary": sr._json_postit(summ)}


@router.get("")
async def postit_get(request: Request, project: str) -> dict[str, Any]:
    return await view(request.app.state.store.engine, project)


@router.get("/summary")
async def postit_summary(request: Request) -> dict[str, Any]:
    from sqlalchemy import text

    from bridge import scribe_room as sr
    engine = request.app.state.store.engine
    async with engine.connect() as c:
        names = [r[0] for r in (await c.execute(text("SELECT name FROM project ORDER BY id"))).all()]
    return {"projects": {n: sr._json_postit(await pi.summary(engine, n, await sr.later_since(engine, n))) for n in names}}


@router.post("")
async def postit_add(body: AddIn, request: Request) -> JSONResponse:
    src = body.source or ("said" if body.session is not None else "note")
    try:
        r = await pi.add(request.app.state.store.engine, body.project, body.body, src, session=body.session)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _changed()
    return JSONResponse(r, status_code=201 if r["created"] else 200)


@router.post("/save")
async def postit_save(body: SaveIn, request: Request) -> JSONResponse:
    engine = request.app.state.store.engine
    out: dict[str, Any] = {"id": None, "confirmed": 0}
    try:
        if (body.body or "").strip():
            out["id"] = (await pi.add(engine, body.project, body.body or "", "note"))["id"]
        out["confirmed"] = await pi.confirm(engine, body.confirm)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _changed()
    return JSONResponse(out)


@router.post("/refresh")
async def postit_refresh(body: RefreshIn, request: Request) -> JSONResponse:
    m = getattr(request.app.state, "handoff", None)
    if m is None:
        raise HTTPException(503, "세션 띄우기가 꺼져 있습니다")
    try:
        r = await pi.start_check(m, request.app.state.store.engine, body.project)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _changed()
    return JSONResponse(r, status_code=202)


@router.post("/check/{cid}")
async def postit_check(cid: int, body: CheckIn, request: Request) -> JSONResponse:
    try:
        r = await pi.resolve_check(request.app.state.store.engine, cid, body.action)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _changed()
    return JSONResponse(r)


@router.post("/{iid}/close")
async def postit_close(iid: int, body: CloseIn, request: Request) -> JSONResponse:
    from bridge import scribe_room as sr
    engine = request.app.state.store.engine
    try:
        ok = await (sr.inbox_drop(engine, iid) if body.reason == "drop" else pi.close(engine, iid, body.reason, body.note))
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    _changed()
    return JSONResponse({"ok": ok})
