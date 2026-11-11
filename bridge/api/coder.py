"""/api/coder — 코더 상주(11-09, bridge/coder_room.py). 방마다 코더의 맡길 일 중 DB에서 세는 것. API 토큰이 필요하다."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request

from bridge import coder_room as cr
from bridge.api.auth import require_api_token

router = APIRouter(prefix="/api/coder", dependencies=[Depends(require_api_token)])
_cache: dict[str, Any] = {"at": 0.0, "data": None}


def invalidate() -> None:
    """받은 할 일 · 쉬게 하기 · 합치기가 바뀌었다 — 다음 요청은 새로 센다."""
    _cache["data"] = None


@router.get("/todo")
async def coder_todo(request: Request) -> dict[str, Any]:
    """프로젝트마다 {inbox, rested} — 화면이 1분마다 부른다. 15초 동안은 같은 답."""
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < 15:
        return _cache["data"]
    data = {"projects": await cr.todo(request.app.state.store.engine, request.app.state.settings.sessions_dir)}
    # 끝난 뒤 어긋난 것(11-11, bridge/reconcile.py) — 마지막으로 훑은 결과. 방마다 drift
    rc = getattr(request.app.state, "reconciler", None)
    for name, v in data["projects"].items():
        v["drift"] = rc.for_project(name) if rc else []
    data["drift_at"] = rc.at.isoformat() + "Z" if rc and rc.at else None
    _cache.update(at=time.monotonic(), data=data)
    return data
