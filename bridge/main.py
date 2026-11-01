"""FastAPI 앱. 실행은 `.venv/bin/python -m bridge` (bridge/__main__.py)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bridge.api import health, ws
from bridge.bus import Pipeline
from bridge.config import Settings, get_settings
from bridge.db.engine import make_engine
from bridge.store import Store

log = logging.getLogger("foreman")


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(s)
        store = Store(engine, s)
        pipeline = Pipeline(store, queue_max=s.ingest_queue_max, retry_max_s=s.db_retry_max_s)
        app.state.settings = s
        app.state.store = store
        app.state.pipeline = pipeline
        pipeline.start()
        log.info("브리지 시작 %s:%d (DB %s:%d)", s.bind_host, s.bind_port, s.mysql_host, s.mysql_port)
        try:
            yield
        finally:
            await pipeline.stop()
            await engine.dispose()
            log.info("브리지 종료")

    # 문서 화면(/docs · /openapi.json)은 열지 않는다 — 토큰 없이 API 지도를 내보이지 않게
    app = FastAPI(title="FOREMAN bridge", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health.router)
    app.include_router(ws.router)
    return app
