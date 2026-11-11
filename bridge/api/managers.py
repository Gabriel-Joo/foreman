"""/api/managers — 프로젝트별 관리자 주소 · 관리자끼리 부탁(11-11, bridge/managers.py)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token

router = APIRouter(prefix="/api/managers", dependencies=[Depends(require_api_token)])


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    from_project: str | None = Field(default=None, max_length=64)
    from_session: int | None = None


def _m(request: Request) -> Any:
    m = getattr(request.app.state, "managers", None)
    if m is None:
        h = getattr(request.app.state, "handoff", None)
        if h is None:
            raise HTTPException(503, "세션 관리가 꺼져 있습니다")
        from bridge.managers import Managers, ManagersConfig
        m = Managers(h, ManagersConfig.load(), getattr(request.app.state, "notifier", None))
        request.app.state.managers = m
    return m


@router.get("")
async def board(request: Request) -> dict[str, Any]:
    m = _m(request)
    return {"enabled": m.cfg.enabled, "error": m.cfg.error, "projects": await m.board()}


@router.post("/{project}/ask")
async def ask(project: str, body: AskIn, request: Request) -> dict[str, Any]:
    m = _m(request)
    if not m.cfg.enabled:
        raise HTTPException(503, "관리자끼리 부탁이 꺼져 있습니다 — config/managers.toml [managers] enabled")
    scope = getattr(request.state, "token_scope", None)
    if scope and body.from_project and body.from_project != scope:
        raise HTTPException(403, f"프로젝트 토큰({scope})으로는 {body.from_project} 이름으로 부탁할 수 없습니다")
    out = await m.ask(project, body.text, scope or body.from_project, body.from_session)
    if not out["delivered"] and out.get("to_session") is None and "없거나" in (out.get("reason") or ""):
        raise HTTPException(404, out["reason"])
    return out
