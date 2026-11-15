"""/api/publish — Notion 게시(12c, 11-06, bridge/notion.py). [게시] 버튼으로만 부른다. API 토큰이 필요하다."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.notion import HumanEdited, NotionError, OutOfScope

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


class PublishIn(BaseModel):
    path: str = Field(default="docs/", min_length=4, max_length=255)
    # reorder — 포트폴리오를 번호순으로 다시 세움(path는 "portfolio/"). docsync — 기술문서 지금 맞추기(11-09, path 무시)
    # prune — 원본이 git에서 사라진 포트폴리오 페이지를 휴지통으로(11-15, path 무시 — 새 판을 올린 뒤 옛 편 치우기)
    action: Literal["publish", "archive", "move", "reorder", "docsync", "prune"] = "publish"
    section: str | None = Field(default=None, max_length=100)   # move — 루트 아래 묶음 페이지 이름(없으면 만든다)
    project: str = Field(default="foreman", max_length=64)       # 11-09 — 프로젝트마다 게시기(config/notion.toml)
    force: bool = False   # Notion에서 사람이 고친 블록이 있어도 git 원본으로 덮는다([Notion 수정 버리고 덮기])


def _pub(request: Request, project: str = "foreman") -> Any:
    p = (getattr(request.app.state, "publishers", None) or {}).get(project)
    if p is None:
        why = getattr(request.app.state, "publisher_off", None) or f"{project}의 Notion 게시가 설정돼 있지 않습니다(config/notion.toml)"
        raise HTTPException(503, why)
    return p


def _halted(p: Any) -> JSONResponse | None:
    """저장소 게시 설정(.foreman/notion.toml)을 잃어 멈춘 게시기(11-12, bridge/notioncfg.py) — 아무것도 쓰지 않고 거절."""
    why = getattr(p, "config_halt", None)
    return JSONResponse({"refused": why, "halted": True}, status_code=409) if why else None


@router.get("/publish")
async def publish_list(request: Request, project: str = "foreman") -> dict[str, Any]:
    """게시 상태 읽기. ?project= 없으면 FOREMAN(서기 화면 [게시] — 지금까지와 같음). 프로젝트 토큰은 자기 프로젝트만(scopetoken)."""
    if project == "foreman":
        p = getattr(request.app.state, "publisher", None)
    else:
        p = (getattr(request.app.state, "publishers", None) or {}).get(project)
    if p is None:
        why = getattr(request.app.state, "publisher_off", None) or f"{project}의 Notion 게시가 설정돼 있지 않습니다(config/notion.toml)"
        return {"enabled": False, "why": why, "docs": []}
    out = {"enabled": True, "root": p.root, "docs": await p.list()}
    cfg = getattr(request.app.state, "notion_cfg", None)
    if cfg is not None and project in cfg.state:
        # 11-12 — 지금 쓰는 설정의 출처(repo · foreman) · 경고 · 오류(깨진 저장소 파일이면 옛 설정 그대로 + stale)
        out["config"] = {**cfg.state[project], "docs_mode": p.docs_mode}
    return out


@router.delete("/publish/repo-config")
async def forget_repo_config(request: Request, project: str) -> JSONResponse:
    """저장소 설정 기억 지우기(11-12) — 저장소 파일을 일부러 없애고 FOREMAN config/notion.toml 칸으로 되돌릴 때. 관리 토큰만
    (프로젝트 토큰은 scopetoken이 이 길을 막고, 여기서 한 번 더). 저장소 파일이 아직 있으면 다음 읽기에서 다시 기억한다."""
    if getattr(request.state, "token_scope", None) is not None:
        raise HTTPException(403, "저장소 설정 기억 지우기는 FOREMAN 관리 토큰으로만 할 수 있습니다")
    cfg = getattr(request.app.state, "notion_cfg", None)
    if cfg is None:
        raise HTTPException(503, getattr(request.app.state, "publisher_off", None) or "Notion 게시가 꺼져 있습니다")
    pub = (getattr(request.app.state, "publishers", None) or {}).get(project)
    lock = getattr(getattr(request.app.state, "docsync", None), "_lock", None)
    if lock is not None:
        async with lock:                              # 맞추기 도중에 칸이 바뀌지 않게
            had = cfg.forget(project, pub)
    else:
        had = cfg.forget(project, pub)
    return JSONResponse({"project": project, "forgot": had, "config": cfg.state.get(project)})


class PairIn(BaseModel):
    project: str = Field(max_length=64)
    path: str = Field(min_length=4, max_length=255)
    page_id: str = Field(min_length=32, max_length=64)


@router.post("/publish/pair")
async def publish_pair(body: PairIn, request: Request) -> JSONResponse:
    """짝 등록(11-12) — 사람이 옮겨 둔 Notion 페이지를 git 문서와 짝짓는다(관리자가 11-12에 SQL로 넣은 방식과 같게).
    그 프로젝트 root 아래 페이지만(Scope.under_root), 제목 · 부모 · url은 Notion에서 읽은 그대로, content_hash · commit_sha는 비운다
    (처음 짝이라 사람 수정 판정이 보수적으로 — 다음 게시가 다른 곳을 보여 준다). 같은 경로 · 같은 페이지 짝이 있으면 거부."""
    scope = getattr(request.state, "token_scope", None)
    if scope is not None and body.project != scope:
        raise HTTPException(403, f"프로젝트 토큰({scope})으로는 이 프로젝트 짝만 등록할 수 있습니다 — 받은 project: {body.project}")
    p = _pub(request, body.project)
    if (stop := _halted(p)) is not None:
        return stop
    try:
        r = await p.pair(body.path, body.page_id)
    except OutOfScope as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except FileNotFoundError as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except NotionError as e:
        return JSONResponse({"refused": f"Notion이 거부했습니다 — {e}"}, status_code=502)
    return JSONResponse(r)


@router.post("/publish")
async def publish_do(body: PublishIn, request: Request) -> JSONResponse:
    scope = getattr(request.state, "token_scope", None)
    if scope is not None:
        # 범위 판정(bridge/scopetoken.py)이 날 본문으로 이미 보았다 — 검증된 본문으로 한 번 더(칸막이가 새지 않게, 11-12)
        if body.project != scope:
            raise HTTPException(403, f"프로젝트 토큰({scope})으로는 이 프로젝트 문서만 게시할 수 있습니다 — 받은 project: {body.project}")
        if body.force or body.action in ("docsync", "prune"):
            raise HTTPException(403, f"프로젝트 토큰({scope})으로는 할 수 없습니다 — force · 한꺼번에 맞추기는 FOREMAN 관리자에게 부탁합니다")
    p = _pub(request, body.project)
    if (stop := _halted(p)) is not None:
        return stop
    when = (datetime.now(UTC) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    try:
        if body.action == "move" and not body.section:
            return JSONResponse({"refused": "옮길 묶음 페이지 이름이 없습니다"}, status_code=409)
        if body.action == "docsync":
            ds = getattr(request.app.state, "docsync", None)
            if ds is None or p.docs_mode == "off":
                return JSONResponse({"refused": f"{body.project}는 기술문서 게시가 꺼져 있습니다(config/notion.toml docs)"}, status_code=409)
            r = await ds.run_one(body.project, {body.path} if body.force else frozenset())
            r = {"action": "docsync", **{k: r[k] for k in ("done", "held", "failed")}}
        elif body.action == "reorder":
            r = await p.reorder_portfolio()
        elif body.action == "prune":
            r = await p.prune_portfolio()
        elif body.action == "archive" and body.path.startswith("@section/"):     # 묶음 페이지(비었을 때만, 11-06)
            r = await p.archive_section(body.path.split("/", 1)[1])
        else:
            r = await (p.publish(body.path, when, force=body.force) if body.action == "publish"
                       else p.archive(body.path) if body.action == "archive" else p.move(body.path, body.section or ""))
            ds = getattr(request.app.state, "docsync", None)
            if ds is not None and body.action == "publish":
                ds.release(body.project, body.path)
    except HumanEdited as e:
        ds = getattr(request.app.state, "docsync", None)
        if ds is not None and body.action == "publish" and not body.force:
            try:    # 11-12 — 서기 할 일 덮기 줄 + 텔레그램 ✋([지금 맞추기]로 멈춘 것과 같은 꼴). 실패해도 409 응답은 나간다
                ds.hold(body.project, body.path, e.edits, e.url)
            except Exception:  # noqa: BLE001
                pass
        return JSONResponse({"refused": f"{e}. git에 옮기거나 [Notion 수정 버리고 덮기]를 눌러 주세요", "edits": e.edits[:10],
                             "url": e.url}, status_code=409)
    except OutOfScope as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except FileNotFoundError as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except NotionError as e:
        n = getattr(request.app.state, "notifier", None)
        if n:
            try:
                rule = n.rules.for_project(body.project)
                n.send_direct(body.project, "publish", None,
                              f"{rule.prefix if rule else '[' + body.project + ']'} Notion 게시 실패 — {body.path}: {e}")
            except Exception:  # noqa: BLE001 — 알림 실패가 응답을 막지 않는다
                pass
        return JSONResponse({"refused": f"Notion이 거부했습니다: {e}"}, status_code=502)
    return JSONResponse(r)
