"""1단계 확인용 — 이벤트 하나가 대기열 → 적재 → WS까지 가는지 본다. DEBUG_ENDPOINTS=true일 때만 붙는다.

터널(브리프 02)로 내보내기 전에 끈다. 토큰이 필요하다.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.api.auth import require_api_token
from bridge.models import EventIn, EventSource, EventStatus, EventType

router = APIRouter(prefix="/api/debug", dependencies=[Depends(require_api_token)])

WAIT_S = 2.0


class EmitIn(BaseModel):
    type: EventType = EventType.DEBUG
    uuid: str | None = Field(default=None, max_length=36)
    character_id: int | None = None
    tool: str | None = Field(default=None, max_length=64)
    target: str | None = None
    status: EventStatus | None = None
    payload: dict[str, Any] | None = None


@router.post("/emit")
async def emit(body: EmitIn, request: Request) -> JSONResponse:
    store = request.app.state.store
    pipeline = request.app.state.pipeline

    # event에는 FK가 없으므로 참조는 애플리케이션이 확인한다
    if body.character_id is not None:
        try:
            exists = await store.character_exists(body.character_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(503, "DB 응답 없음") from e
        if not exists:
            raise HTTPException(422, f"character {body.character_id} 없음")

    ev = EventIn(source=EventSource.DEBUG, **body.model_dump())
    try:
        fut = pipeline.submit(ev)
    except asyncio.QueueFull:
        raise HTTPException(503, "적재 대기열이 꽉 찼다") from None

    try:
        async with asyncio.timeout(WAIT_S):
            event_id = await asyncio.shield(fut)
    except TimeoutError:
        # 버리지 않았다 — DB가 돌아오면 적재되고 WS로도 나간다
        return JSONResponse({"queued": True, "queue": pipeline.depth}, status_code=202)
    if event_id is None:
        return JSONResponse({"dropped": True, "reason": "중복 uuid 또는 적재 불가"}, status_code=409)
    return JSONResponse({"id": event_id}, status_code=201)


@router.delete("/events")
async def clear_debug_events(request: Request) -> dict[str, int]:
    """source='debug' 이벤트만 지운다."""
    deleted = await request.app.state.store.delete_debug_events()
    return {"deleted": deleted}
