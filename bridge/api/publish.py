"""/api/publish — Notion 게시(12c, 11-06, bridge/notion.py). [게시] 버튼으로만 부른다. API 토큰이 필요하다."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge import docsync as dsm
from bridge.api.auth import require_api_token
from bridge.notion import HumanEdited, NotionError, OutOfScope

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


class PublishIn(BaseModel):
    path: str = Field(default="docs/", min_length=4, max_length=255)
    # docsync — 한 묶음을 한 번에 올린다(11-09 기술문서 지금 맞추기, 11-20 포트폴리오도). path가 portfolio/로 시작하면 포트폴리오,
    # 아니면 기술문서. force면 path 그 편만 덮는다. 11-20 reorder(번호순 다시 세우기)와 prune(원본 없는 페이지 내리기)은 없앴다.
    # 둘 다 포트폴리오 docsync 한 번에 들어 있다(bridge/docsync.py sync)
    action: Literal["publish", "archive", "move", "docsync"] = "publish"
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
    # 11-17 포트폴리오 패널 프로젝트별: 고른 프로젝트의 portfolio/ 있음(has_dir)과 Notion 자리(place)를 같이 내린다.
    # portfolio/가 없어도 목록은 읽는다(폴더째 지운 뒤 Notion에 남은 페이지가 「원본 없음」으로 보이게). 화면은 글도 기록도 없으면 「아직 없음」.
    # 원본 커밋을 못 읽으면 has_dir None, 목록은 비우고 화면은 「읽지 못했습니다」
    st = p.portfolio_state() if hasattr(p, "portfolio_state") else {"has_dir": True, "place": True}
    docs = await p.list() if st.get("has_dir") is not None else []
    out = {"enabled": True, "root": p.root, "docs": docs, "portfolio": st}
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
        if body.force or body.action == "docsync":
            raise HTTPException(403, f"프로젝트 토큰({scope})으로는 할 수 없습니다 — force · 한꺼번에 맞추기는 FOREMAN 관리자에게 부탁합니다")
    p = _pub(request, body.project)
    if (stop := _halted(p)) is not None:
        return stop
    when = (datetime.now(UTC) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    ds = getattr(request.app.state, "docsync", None)
    # 11-20 묶음(기술문서 원고 폴더, portfolio/)에 든 편은 한 편 게시도 묶음 게시와 같은 함수(docsync.sync)로 간다. 한 잠금 안에서
    # 돌아 잇달아 눌러도 같은 페이지에 두 요청이 함께 쓰지 않고, 멈춤 줄, 「마지막으로 올림」, 텔레그램이 같은 자리에 남는다
    group = dsm.PORT if body.action == "docsync" and body.path.startswith(dsm.PORT) else (
        dsm.src_of(p) if body.action == "docsync" else dsm.group_of(p, body.path) if body.action == "publish" else None)
    if group is not None:
        if ds is None:
            return JSONResponse({"refused": "Notion 맞추기가 떠 있지 않습니다. 브리지 로그를 봐 주세요"}, status_code=503)
        if group == dsm.PORT and not getattr(p, "portfolio_page", None):
            return JSONResponse({"refused": f"{body.project}의 포트폴리오 Notion 자리가 정해지지 않았습니다(config/notion.toml portfolio_page)"},
                                status_code=409)
        if group != dsm.PORT and p.docs_mode == "off":
            return JSONResponse({"refused": f"{body.project}는 기술문서 게시가 꺼져 있습니다(config/notion.toml docs)"}, status_code=409)
        force = {body.path} if body.force else frozenset()
        if body.action == "docsync":
            r = await ds.run_one(body.project, force, src=group)
            # warnings: 링크로 못 바꾼 「→ 「제목」」(없는 제목, 겹치는 제목, 끝내 안 올라간 편, 11-17)
            return JSONResponse({"action": "docsync", "src": group, **{k: r[k] for k in ("done", "held", "failed")},
                                 "warnings": r.get("warnings", [])})
        return _one_reply(body, await ds.run_one(body.project, force, src=group, only={body.path}))
    try:
        if body.action == "move" and not body.section:
            return JSONResponse({"refused": "옮길 묶음 페이지 이름이 없습니다"}, status_code=409)
        if body.action == "docsync":       # 묶음이 없는 게시기(위에서 group이 정해지지 않음)
            return JSONResponse({"refused": f"{body.project}는 기술문서 게시가 꺼져 있습니다(config/notion.toml docs)"}, status_code=409)
        if body.action == "archive" and body.path.startswith("@section/"):     # 묶음 페이지(비었을 때만, 11-06)
            r = await p.archive_section(body.path.split("/", 1)[1])
        else:
            # 묶음 밖 글(log/, 기술문서 게시가 꺼진 프로젝트의 docs/)의 한 편 게시, 내리기, 옮기기
            r = await (p.publish(body.path, when, force=body.force) if body.action == "publish"
                       else p.archive(body.path) if body.action == "archive" else p.move(body.path, body.section or ""))
    except HumanEdited as e:
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


def _one_reply(body: PublishIn, r: dict[str, Any]) -> JSONResponse:
    """한 편 게시(only) 결과를 예전 응답 꼴로. 멈춤 409(고친 곳, url), 막힘 409, Notion 거부 502, 올림은 그 편의 action.
    알림(텔레그램)과 덮기 줄은 docsync.run_one이 이미 남겼다(묶음 게시와 같은 자리)."""
    warns = [w["warning"] for w in r.get("warnings", []) if w.get("path") == body.path]
    held = next((h for h in r["held"] if h["path"] == body.path), None)
    if held:
        return JSONResponse({"refused": f"Notion에서 사람이 고친 곳이 있어 덮지 않았습니다: {body.path}. git에 옮기거나 "
                                        "[Notion 수정 버리고 덮기]를 눌러 주세요", "edits": held["edits"][:10], "url": held.get("url")},
                            status_code=409)
    fail = next((f for f in r["failed"] if f["path"] in (body.path, dsm.PORT)), None) or (r["failed"][0] if r["failed"] and not r["done"] else None)
    if fail:
        if fail.get("kind") == "notion":
            return JSONResponse({"refused": f"Notion이 거부했습니다: {fail['error']}"}, status_code=502)
        return JSONResponse({"refused": fail["error"]}, status_code=409)
    done = next((d for d in r["done"] if d["path"] == body.path), {"path": body.path, "action": "unchanged"})
    return JSONResponse({**done, "warnings": warns})
