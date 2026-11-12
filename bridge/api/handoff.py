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
    fmt: Literal["v1", "v2"] = "v2"   # v2 = 짧은 인계 + 읽을 곳(11-05, docs/11_handoff_v2.md), v1 = 요약 통째로


class EditIn(BaseModel):
    body: str = Field(min_length=1, max_length=60_000)


class SpawnIn(BaseModel):
    summary_id: int | None = None
    replace: bool = False             # 새 세션으로 옮기기 — 옛 세션을 빼고 worktree를 판단한다(곧 끝나니 원본 폴더에서 뜬다, 11-09)
    note: str | None = Field(None, max_length=2000)   # [덧붙여서 보내기] — 인계 글 끝에 붙는 사람 말(11-09)


class InjectIn(BaseModel):
    cc_session_id: str = Field(min_length=36, max_length=36)
    cwd: str


class TitleIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)   # 빈 글 · null이면 자동 제목(CC가 붙인 것)으로


SessionRole = Literal["coder", "inspector", "cicd", "scribe", "manager", "designer"]   # bridge.handoff.ROLE_KO와 같다(foreman은 감독실 캐릭터 몫)


class RoleIn(BaseModel):
    role: SessionRole


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
    out = {"controls": await m.controls(row), "summaries": await m.summaries(sid), "promotions": [],
           "promotions_error": None}
    out["promote_inputs"] = []
    if m.promote is not None:
        try:
            out["promotions"] = await m.promote.list(sid)
            out["promote_inputs"] = await m.promote.inputs(row)
        except Exception as e:  # noqa: BLE001 — 표가 없을 때(0020 전)도 인계 칸은 떠야 한다. 화면에 사유를 보인다
            out["promotions_error"] = f"대화 결정 문서에 적기 목록을 읽지 못했습니다({type(e).__name__}) — 마이그레이션 0020 · 0021을 적용했는지 확인해 주세요"
    out["losschecks"], out["losschecks_error"] = [], None
    lc = getattr(m, "losscheck", None)
    if lc is not None:
        try:
            out["losschecks"] = await lc.list(sid)
            out["controls"]["losscheck"] = not any(x["status"] == "running" for x in out["losschecks"])
        except Exception as e:  # noqa: BLE001 — 0021 전에도 인계 칸은 뜬다
            out["losschecks_error"] = f"잃은 것 점검을 읽지 못했습니다({type(e).__name__}) — 마이그레이션 0021을 적용했는지 확인해 주세요"
    # 합치기 승인 카드(11-11 1물결 A, bridge/mergeprep.py) — 켜져 있을 때만. 꺼져 있으면 None
    mp = getattr(m, "mergeprep", None)
    out["merge_prep"] = ({"card": mp.card_for(sid), "health": mp.health, "stage": mp.cfg.stage} if mp is not None else None)
    return out


# ── 합치기 준비(11-11 1물결 A 「하나」 · 「넷」, bridge/mergeprep.py) ─────────────
class MergePrepIn(BaseModel):
    action: Literal["merge", "skip", "refresh"]
    by: Literal["human", "manager"] = "human"   # 11-12 — 관리자 세션이 승인할 때 manager. 프로젝트 토큰이면 저절로 manager


def _mp(m: HandoffManager) -> Any:
    mp = getattr(m, "mergeprep", None)
    if mp is None:
        raise HTTPException(503, "합치기 준비가 꺼져 있습니다(config/handoff.toml [merge_prep] enabled)")
    return mp


@router.get("/merge-prep")
async def merge_prep_list(request: Request, project: str | None = None) -> dict[str, Any]:
    """합치기 승인 카드 전부 + 준비 상태(health). 꺼져 있으면 enabled false.
    ?project= 면 그 프로젝트 카드만(11-12 — 관리자가 자기 카드를 모아 본다). 프로젝트 토큰은 자기 프로젝트로만(scopetoken이 먼저 본다)."""
    scope = getattr(request.state, "token_scope", None)
    if scope is not None and project != scope:
        raise HTTPException(403, f"프로젝트 토큰({scope})으로는 ?project={scope} 로만 읽을 수 있습니다")
    mp = getattr(_mgr(request), "mergeprep", None)
    return mp.view(project) if mp is not None else {"enabled": False, "cards": [], "health": None}


@router.post("/sessions/{sid}/merge-prep")
async def merge_prep_act(sid: int, body: MergePrepIn, request: Request) -> JSONResponse:
    """merge — 사람 승인: 충돌 없고 깨끗하면 (살아 있으면 끝내고) 합침, 충돌이면 그 세션(끝났으면 관리자)에 풀라고 보냄.
    skip — [나중에]: 이 브랜치 끝 커밋이 바뀌기 전까지 카드를 치움. refresh — 지금 다시 훑기.
    by=manager(11-12) — 그 프로젝트 승인자가 관리자이고 늘-사람에 안 걸린 카드만. 프로젝트 토큰은 늘 manager로 본다."""
    mp = _mp(_mgr(request))
    by = "manager" if getattr(request.state, "token_scope", None) is not None else body.by
    try:
        if body.action == "skip":
            r = await mp.skip(sid, by=by)
        elif body.action == "refresh":
            await mp.check()
            r = {"ok": True, "card": mp.card_for(sid)}
        else:
            r = await mp.approve(sid, by=by)
    except Refused as e:
        return _refused(e)
    if body.action == "merge":
        from bridge.api import coder
        coder.invalidate()
        if (rc := getattr(request.app.state, "reconciler", None)) is not None:
            rc.poke("합치기 승인")
    return JSONResponse(r)


# ── 인계 2판 d [잃은 것 보기](11-06, bridge/losscheck.py) ─────────────
@router.post("/sessions/{sid}/losscheck")
async def losscheck_start(sid: int, request: Request) -> JSONResponse:
    """압축 손실 점검 — 트랜스크립트에서 압축 구간별 사람 프롬프트를 뽑아 `claude -p`로 판정한다. 버튼을 누를 때만 돈다."""
    m = _mgr(request)
    lc = getattr(m, "losscheck", None)
    if lc is None:
        raise HTTPException(503, "압축으로 잊은 것 찾기가 꺼져 있습니다")
    try:
        return JSONResponse(await lc.start(await _row(m, sid)), status_code=202)
    except Refused as e:
        return _refused(e)


# ── 인계 2판 ① 문서로 옮기기(11-05, bridge/promote.py) ──────────────
class PromoteEditIn(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=100)


class PromoteIn(BaseModel):
    summary_id: int | None = None     # 같이 넣을 인계. 없으면 후보가 하나일 때만 그것, 여럿이면 거부(골라야 한다)
    no_input: bool = False            # 아무것도 넣지 않는다
    loss_check_id: int | None = None  # 같이 넣을 [잃은 것 보기] 점검(사라짐 · 약해짐) — 11-06


def _prom(m: HandoffManager) -> Any:
    if m.promote is None:
        raise HTTPException(503, "대화 결정 문서에 적기가 꺼져 있습니다")
    return m.promote


@router.post("/sessions/{sid}/promote")
async def promote_request(sid: int, request: Request, body: PromoteIn | None = None) -> JSONResponse:
    """1/2 — 세션에 "문서에 없는 것" 목록을 시킨다(파일은 안 고친다). 고른 2판 인계의 「문서와 다른 지금」을 같이 넣는다."""
    m = _mgr(request)
    body = body or PromoteIn()
    try:
        return JSONResponse(await _prom(m).request(await _row(m, sid), body.summary_id, body.no_input, body.loss_check_id),
                            status_code=202)
    except Refused as e:
        return _refused(e)


@router.put("/promotions/{pid}")
async def promote_edit(pid: int, body: PromoteEditIn, request: Request) -> JSONResponse:
    """사람이 고친 칸(what · dest · section · state)만 받는다."""
    try:
        return JSONResponse(await _prom(_mgr(request)).edit(pid, body.items))
    except Refused as e:
        return _refused(e)


@router.post("/promotions/{pid}/write")
async def promote_write(pid: int, request: Request) -> JSONResponse:
    """2/2 — 승인한 것만 세션에 보내 쓰고 커밋하게 한다. 끝나면 브리지가 git으로 확인한다."""
    try:
        return JSONResponse(await _prom(_mgr(request)).write(pid), status_code=202)
    except Refused as e:
        return _refused(e)


@router.post("/sessions/{sid}/summary")
async def make_summary(sid: int, body: SummaryIn, request: Request) -> JSONResponse:
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        if body.mode == "live":
            r = await m.request_live(row, body.kind, body.fmt)
        elif body.mode == "headless":
            r = await m.request_headless(row, body.kind, body.fmt)
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
async def injection_preview(summary_id: int, request: Request, replace: bool = False) -> JSONResponse:
    """replace=1 — 새 세션으로 옮기기의 ② 확인: worktree_next를 옛 세션을 빼고 판단한다."""
    try:
        return JSONResponse(await _mgr(request).injection(summary_id, replace=replace))
    except Refused as e:
        return _refused(e)


@router.post("/sessions/{sid}/reads/resend")
async def resend_reads(sid: int, request: Request) -> JSONResponse:
    """2판 인계를 받은 세션이 「읽을 곳」 중 안 읽은 곳만 다시 보낸다(11-05)."""
    m = _mgr(request)
    try:
        return JSONResponse(await m.resend_reads(await _row(m, sid)), status_code=202)
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
        r = await m.spawn(row, body.summary_id, replace=body.replace, note=body.note)
    except Refused as e:
        return _refused(e)
    from bridge.api.foreman import record_direct     # 11-11 교장 ④ — 옮기기도 dispatch 기록(실패는 옮기기 기록 session_action에 이미 남는다)
    if note := await record_direct(request, "move", row.cwd, {"role": None, "title": row.title},
                                   r, None, f"(옮기기) 세션 {sid}에서", body.summary_id):
        r["note"] = f"{r.get('note') or ''} {note}".strip()
    return JSONResponse(r)


class NewIn(BaseModel):
    cwd: str = Field(min_length=1, max_length=1024)
    summary_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    worktree: bool | None = None      # None: 그 프로젝트에 살아 있는 세션이 있으면 따로 작업(worktree)
    model: str | None = Field(default=None, max_length=40)   # config/models.toml id. None이면 역할(coder) 기본값
    role: SessionRole | None = None
    first_prompt: str | None = Field(default=None, max_length=20000)   # 첫 입력(12a 서기 일감 등). 인계 요약과 같이 줄 수 없다
    files: list[str] | None = Field(default=None, max_length=40)       # 11-11 맡을 파일 — dispatch 기록 · 겹침 알림(교장 ④ · 일곱)
    request: str | None = Field(default=None, max_length=4000)         # 11-11 무엇을 하려는지(기록용). 없으면 이름으로


class WorktreeIn(BaseModel):
    action: Literal["merge", "discard"]
    confirm: str = ""                 # 버리기는 worktree 이름을 그대로 적어야 한다(합치지 않은 커밋까지 지운다)
    end: bool = False                 # 세션이 살아 있으면 먼저 끝낸다(11-06 — 끝내고 합치기 · 끝내고 버리기)


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
            # 숨긴 세션(시험 등)의 요약은 고르는 칸에 내지 않는다 — 11-05 '푸른 고래' 같은 혼동
            "LEFT JOIN project p ON p.id = ch.project_id WHERE s.status = 'ok' AND cs.hidden_at IS NULL "
            "ORDER BY s.id DESC LIMIT 30"))).all()
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
    from bridge.api.foreman import record_direct     # 11-11 교장 ④ — 계획 없이 띄워도 dispatch 기록
    sess = {"role": body.role, "model": body.model, "title": body.title, "first_prompt": body.first_prompt,
            "worktree": body.worktree, "files": body.files}
    try:
        if body.first_prompt and body.summary_id is not None:
            raise Refused("첫 입력과 옮기기용 요약은 같이 줄 수 없습니다 — 하나만 골라 주세요")
        r = await _mgr(request).spawn_new(body.cwd, body.summary_id, body.title, worktree=body.worktree,
                                          role=body.role, model=body.model or None, first_prompt=body.first_prompt or None)
    except Refused as e:
        await record_direct(request, "spawn", body.cwd, sess, None, str(e), body.request, body.summary_id)
        return _refused(e)
    if note := await record_direct(request, "spawn", body.cwd, sess, r, None, body.request, body.summary_id):
        r["note"] = f"{r.get('note') or ''} {note}".strip()
    return JSONResponse(r)


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
        mp = getattr(m, "mergeprep", None)
        card = mp.cards.get(sid) if mp is not None else None
        if (body.action == "merge" and card is not None and getattr(request.state, "token_scope", None) is not None
                and card.human_why):
            # 11-12 — 늘-사람 카드를 프로젝트 토큰(관리자)이 이 길로 돌아 합치지 못하게. 관리 토큰(사람 화면)은 그대로
            raise Refused("이 세션의 합치기 카드는 사람 승인입니다 — 까닭: " + "; ".join(card.human_why))
        r = await m.worktree_act(row, body.action, end=body.end)
    except Refused as e:
        return _refused(e)
    from bridge.api import coder
    coder.invalidate()            # 쉬게 한 일 · 코더가 가져간 할 일의 상태가 바뀐다
    if (rc := getattr(request.app.state, "reconciler", None)) is not None:
        rc.poke("합치기 · 버리기")    # 11-11 끝난 뒤 어긋난 것 훑기
    return JSONResponse(r)


@router.post("/sessions/{sid}/rest")
async def rest(sid: int, request: Request) -> JSONResponse:
    """[쉬게 하기](11-09) — 지금까지를 이 worktree 브랜치에 커밋하고 세션만 끝낸다. worktree는 남는다."""
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        r = await m.rest(row)
    except Refused as e:
        return _refused(e)
    from bridge.api import coder, dashboard
    dashboard.invalidate()
    coder.invalidate()
    return JSONResponse(r)


@router.post("/sessions/{sid}/rest-resume")
async def rest_resume(sid: int, request: Request) -> JSONResponse:
    """[이어서](11-09) — 쉬게 한 worktree에서 그 CC 세션을 --resume으로 다시 붙인다."""
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        r = await m.rest_resume(row)
    except Refused as e:
        await m._act(sid, "rest-resume", None, False, f"거부: {e}")
        return _refused(e)
    from bridge.api import coder, dashboard
    dashboard.invalidate()
    coder.invalidate()
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


@router.get("/schema-lock/board")
async def schema_lock_board(request: Request) -> dict[str, Any]:
    """화면 방 배너(11-09) — 잠금마다 쥔 세션 · 막힌 세션의 화면 번호를 붙이고, 일찍 푼 것(released)도 같이."""
    from sqlalchemy import text
    sl = getattr(request.app.state, "schema_lock", None)
    if not sl:
        return {"locks": {}, "released": {}}
    locks = sl.view()
    ccs = {h["cc"] for h in locks.values()} | {(h.get("blocked") or {}).get("cc") for h in locks.values()} - {None}
    ids: dict[str, int] = {}
    if ccs:
        from sqlalchemy import bindparam
        async with request.app.state.store.engine.connect() as c:
            ids = {r[0]: r[1] for r in (await c.execute(text(
                "SELECT cc_session_id, MAX(id) FROM character_session WHERE cc_session_id IN :c GROUP BY cc_session_id")
                .bindparams(bindparam("c", expanding=True)), {"c": list(ccs)})).all()}
    out = {}
    for p, h in locks.items():
        b = h.get("blocked")
        out[p] = {**{k: h.get(k) for k in ("wt", "since", "what", "held")}, "session_id": ids.get(h["cc"]), "cc": h["cc"][:8],
                  "blocked": {**{k: b.get(k) for k in ("at", "what")}, "session_id": ids.get(b.get("cc")), "cc": (b.get("cc") or "")[:8]} if b else None}
    return {"locks": out, "released": sl.released_view()}


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


@router.put("/sessions/{sid}/role")
async def set_role(sid: int, body: RoleIn, request: Request) -> JSONResponse:
    """세션 역할 바꾸기(11-09) — 허용 값(RoleIn)만. character_session.role · 역할 캐릭터를 바꾸고 session_action 'role'에 남긴다."""
    m = _mgr(request)
    row = await _row(m, sid)
    try:
        r = await m.set_role(row, body.role)
    except Refused as e:
        return _refused(e)
    from bridge.api import dashboard
    dashboard.invalidate()
    return JSONResponse(r)


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
