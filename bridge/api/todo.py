"""/api/todo — 받은 할 일 목록에서 바로 고치기(11-11 받은 할 일 #8). 버리기는 /api/scribe/inbox/{id}/drop 그대로.
여럿을 골라 「이거 해라」는 화면이 글을 묶어 교장 계획 창으로 넘기고(foremanchat.js openWith), [시작]이 그 할 일들을 가져간다."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge import scribe_room as sr
from bridge.api.auth import require_api_token
from bridge.inject import Refused

router = APIRouter(prefix="/api/todo", dependencies=[Depends(require_api_token)])


class EditIn(BaseModel):
    body: str = Field(min_length=1, max_length=sr.INBOX_MAX)


@router.put("/{iid}")
async def edit(iid: int, body: EditIn, request: Request) -> JSONResponse:
    try:
        ok = await sr.inbox_edit(request.app.state.store.engine, iid, body.body)
    except Refused as e:
        return JSONResponse({"refused": str(e)}, status_code=409)
    if not ok:
        return JSONResponse({"refused": "새로인 할 일만 고칠 수 있습니다. 이미 가져갔거나 버린 것입니다"}, status_code=409)
    try:
        from bridge.api import coder
        coder.invalidate()
    except Exception:  # noqa: BLE001
        pass
    out: dict[str, Any] = {"ok": True, "id": iid}
    return JSONResponse(out)
