"""/healthz — 인증 없이 열린 유일한 경로. 상태 말고는 아무것도 내보내지 않는다(원인은 브리지 로그에)."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
log = logging.getLogger("foreman.health")


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    store = request.app.state.store
    pipeline = request.app.state.pipeline
    was = getattr(request.app.state, "health_db", None)
    try:
        await store.ping()  # db_query_timeout_s 안에 답이 없으면 TimeoutError
        db = "ok"
        if was == "down":
            log.info("DB 복구")
    except Exception as e:  # noqa: BLE001 — 응답은 down 하나, 원인은 상태가 바뀔 때 한 번 로그
        db = "down"
        if was != "down":
            log.warning("DB 응답 없음: %s: %s", type(e).__name__, str(e)[:200])
    request.app.state.health_db = db
    body = {"status": "ok" if db == "ok" else "degraded", "db": db, "queue": pipeline.depth}
    return JSONResponse(body, status_code=200 if db == "ok" else 503)
