"""/api/publish — Notion 게시(12c, 11-06, bridge/notion.py). [게시] 버튼으로만 부른다. API 토큰이 필요하다."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.notion import NotionError, OutOfScope

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


class PublishIn(BaseModel):
    path: str = Field(min_length=4, max_length=255)
    action: Literal["publish", "archive"] = "publish"


def _pub(request: Request) -> Any:
    p = getattr(request.app.state, "publisher", None)
    if p is None:
        why = getattr(request.app.state, "publisher_off", None) or "Notion 게시가 꺼져 있습니다"
        raise HTTPException(503, why)
    return p


@router.get("/publish")
async def publish_list(request: Request) -> dict[str, Any]:
    p = getattr(request.app.state, "publisher", None)
    if p is None:
        return {"enabled": False, "why": getattr(request.app.state, "publisher_off", None), "docs": []}
    return {"enabled": True, "root": p.root, "docs": await p.list()}


@router.post("/publish")
async def publish_do(body: PublishIn, request: Request) -> JSONResponse:
    p = _pub(request)
    when = (datetime.now(UTC) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    try:
        r = await (p.publish(body.path, when) if body.action == "publish" else p.archive(body.path))
    except OutOfScope as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except FileNotFoundError as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    except NotionError as e:
        n = getattr(request.app.state, "notifier", None)
        if n:
            try:
                n.send_direct("foreman", "publish", None, f"[포먼] Notion 게시 실패 — {body.path}: {e}")
            except Exception:  # noqa: BLE001 — 알림 실패가 응답을 막지 않는다
                pass
        return JSONResponse({"refused": f"Notion이 거부했습니다 — {e}"}, status_code=502)
    return JSONResponse(r)
