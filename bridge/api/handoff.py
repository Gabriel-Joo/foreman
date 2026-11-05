"""/api — 세션 인계 · 세션 조작(11-05, docs/11_handoff.md). API 토큰이 필요하다. 로직은 bridge/handoff.py."""

import os
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


class TitleIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)   # 빈 글 · null이면 자동 제목(CC가 붙인 것)으로


class ActionIn(BaseModel):
    action: Literal["exit", "stop", "resume", "interrupt"]


def _mgr(request: Request) -> HandoffManager:
    m = getattr(request.app.state, "handoff", None)
    if m is None:
        raise HTTPException(503, "인계 기능이 꺼져 있습니다")
    return m


async def _row(m: HandoffManager, sid: int) -> Any:
    row = await m.session(sid)
    if row is None:
        raise HTTPException(404, "세션이 없습니다")
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


class NewIn(BaseModel):
    cwd: str = Field(min_length=1, max_length=1024)
    summary_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    worktree: bool | None = None      # None: 그 프로젝트에 살아 있는 세션이 있으면 따로 작업(worktree)
    model: str | None = Field(default=None, max_length=40)   # config/models.toml id. None이면 역할(coder) 기본값
    role: Literal["coder", "inspector", "cicd"] | None = None


class WorktreeIn(BaseModel):
    action: Literal["merge", "discard"]
    confirm: str = ""                 # 버리기는 worktree 이름을 그대로 적어야 한다(합치지 않은 커밋까지 지운다)


@router.get("/spawn/options")
async def spawn_options(request: Request) -> dict[str, Any]:
    """+ 새 세션 창 — 프로젝트(저장소 폴더) · 최근 쓴 폴더 · 넣을 수 있는 인계 요약(최근)."""
    from sqlalchemy import text
    asm = request.app.state.assembler
    projects = [{"name": name, "repo": repo} for repo, _pid, name, _ch in (asm.projects if asm else [])]
    async with request.app.state.store.engine.connect() as c:
        cwds = [r[0] for r in (await c.execute(text(
            "SELECT cwd FROM character_session WHERE cwd IS NOT NULL AND type = 'agent' AND hidden_at IS NULL "
            "GROUP BY cwd ORDER BY MAX(id) DESC LIMIT 12"))).all()]
        sums = (await c.execute(text(
            "SELECT s.id, s.kind, s.source, s.chars, s.created_at, s.session_id, cs.cwd, "
            "COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)), p.name, LEFT(s.body, 800) "
            "FROM summary s JOIN character_session cs ON cs.id = s.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id WHERE s.status = 'ok' ORDER BY s.id DESC LIMIT 30"))).all()
    home = os.path.expanduser("~")
    return {"home": home, "projects": projects, "recent_cwds": [x for x in cwds if os.path.isdir(x)],
            "models": _mgr(request).models.view(),     # 고를 수 있는 모델 · 역할 기본값(config/models.toml)
            "summaries": [{"id": r[0], "kind": r[1], "source": r[2], "chars": r[3],
                           "created_at": r[4].isoformat() + "Z" if r[4] else None, "session_id": r[5], "cwd": r[6],
                           "session": r[7], "project": r[8], "head": _head(r[9])} for r in sums]}


def _head(body: str | None) -> str:
    """요약 본문의 첫 내용 줄 — 고르는 칸에서 세션 제목만으로는 무슨 요약인지 헷갈렸다(11-05 '푸른 고래')."""
    for ln in (body or "").splitlines():
        t = ln.strip().lstrip("-*• ").strip()
        if t and not ln.lstrip().startswith("#"):
            return t[:160]
    return ""


@router.get("/fs/dirs")
async def list_dirs(path: str = "~", hidden: bool = False) -> dict[str, Any]:
    """폴더 고르기(떠돌이 세션) — 집 폴더 아래의 하위 폴더 이름만. 파일 · 내용은 보지 않는다."""
    home = os.path.realpath(os.path.expanduser("~"))
    p = os.path.realpath(os.path.expanduser(path or "~"))
    if not (p == home or p.startswith(home + os.sep)) and not p.startswith("/tmp/"):
        raise HTTPException(400, "집 폴더와 /tmp 아래만 고를 수 있습니다")
    if not os.path.isdir(p):
        raise HTTPException(404, "폴더가 없습니다")
    try:
        names = sorted(e.name for e in os.scandir(p) if e.is_dir(follow_symlinks=False) and (hidden or not e.name.startswith(".")))
    except PermissionError:
        names = []
    return {"path": p, "parent": os.path.dirname(p) if p != home else None, "dirs": names[:300],
            "is_repo": os.path.isdir(os.path.join(p, ".git"))}


@router.post("/spawn")
async def spawn_new(body: NewIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _mgr(request).spawn_new(body.cwd, body.summary_id, body.title, worktree=body.worktree,
                                                          role=body.role, model=body.model or None))
    except Refused as e:
        return _refused(e)


@router.post("/sessions/{sid}/worktree")
async def worktree_act(sid: int, body: WorktreeIn, request: Request) -> JSONResponse:
    """따로 작업 합치기(rebase → fast-forward, 충돌이면 되돌리고 멈춤) · 버리기. 사람이 화면에서 확인한 뒤에만 부른다."""
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        if body.action == "discard":
            name = m._wt_of(row)[1]
            if body.confirm != name:
                raise Refused(f"버리려면 worktree 이름({name})을 그대로 적어 주세요")
        r = await m.worktree_act(row, body.action)
    except Refused as e:
        return _refused(e)
    return JSONResponse(r)


@router.post("/sessions/{sid}/preview")
async def preview_on(sid: int, request: Request) -> JSONResponse:
    """[미리보기 열기] — 없으면 띄우고(빈 포트) 있으면 그대로. 화면이 #t=<토큰>을 붙여 새 탭으로 연다."""
    m = _mgr(request)
    try:
        return JSONResponse(await m.preview(await _row(m, sid), True))
    except Refused as e:
        return _refused(e)


@router.delete("/sessions/{sid}/preview")
async def preview_off(sid: int, request: Request) -> JSONResponse:
    m = _mgr(request)
    try:
        return JSONResponse(await m.preview(await _row(m, sid), False))
    except Refused as e:
        return _refused(e)


@router.get("/schema-lock")
async def schema_lock(request: Request) -> dict[str, Any]:
    sl = getattr(request.app.state, "schema_lock", None)
    return sl.view() if sl else {}


@router.delete("/schema-lock/{project}")
async def schema_unlock(project: str, request: Request) -> dict[str, Any]:
    """사람이 잠금을 푼다(잠금을 가진 세션이 스키마 일을 그만뒀을 때)."""
    sl = getattr(request.app.state, "schema_lock", None)
    return {"released": bool(sl and sl.release(project))}


@router.put("/sessions/{sid}/title")
async def set_title(sid: int, body: TitleIn, request: Request) -> dict[str, Any]:
    """사람이 붙인 세션 이름(11-05) — character_session.custom_title. 비우면 자동 제목으로 되돌린다."""
    from sqlalchemy import text
    from bridge.api import dashboard
    title = (body.title or "").strip() or None
    async with request.app.state.store.engine.begin() as c:
        res = await c.execute(text("UPDATE character_session SET custom_title = :t WHERE id = :i"), {"t": title, "i": sid})
    if not res.rowcount:
        raise HTTPException(404, "세션이 없습니다")
    dashboard.invalidate()
    return {"id": sid, "custom_title": title}


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
