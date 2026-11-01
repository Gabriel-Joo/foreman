"""FastAPI 앱. 실행은 `.venv/bin/python -m bridge` (bridge/__main__.py)."""

import logging
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse

from bridge.api import debug, health, hooks, ws
from bridge.api.auth import require_api_token
from bridge.assembler import Assembler
from bridge.bus import Pipeline
from bridge.config import Settings, get_settings
from bridge.db.engine import make_engine
from bridge.mask import Masker
from bridge.store import Store
from bridge.transcript.watcher import Watcher

log = logging.getLogger("foreman")
STATIC = Path(__file__).resolve().parent / "static"


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
        app.state.assembler = app.state.watcher = None
        watch_task = None
        if s.watch_enabled:
            asm = Assembler(engine, s, Masker(), publish=pipeline.publish)
            await asm.load()
            watcher = Watcher(s, asm)
            app.state.assembler, app.state.watcher = asm, watcher
            watch_task = asyncio.create_task(watcher.run(), name="foreman-watcher")
        log.info("브리지 시작 %s:%d (DB %s:%d, 와처 %s)", s.bind_host, s.bind_port, s.mysql_host, s.mysql_port,
                 "켬" if s.watch_enabled else "끔")
        try:
            yield
        finally:
            if watch_task:
                watch_task.cancel()
                try:
                    await watch_task
                except asyncio.CancelledError:
                    pass
            await pipeline.stop()
            await engine.dispose()
            log.info("브리지 종료")

    # 문서 화면(/docs · /openapi.json)은 열지 않는다 — 토큰 없이 API 지도를 내보이지 않게
    app = FastAPI(title="FOREMAN bridge", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health.router)
    app.include_router(ws.router)
    app.include_router(hooks.router)

    @app.get("/api/ingest", dependencies=[Depends(require_api_token)])
    async def ingest_status() -> dict:
        asm, w = app.state.assembler, app.state.watcher
        if asm is None:
            return {"watch": "off"}
        return {"watch": "live" if asm.live else "backfill", "backfill_seconds": w.backfill_seconds,
                "watched_dirs": len(w.wd_path), "dirty": len(w.dirty), "stats": await asm.stats_snapshot()}

    if s.debug_endpoints:
        app.include_router(debug.router)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        # 1단계 확인용 페이지. 비밀값이 없으므로 인증 없이 준다(토큰은 사용자가 페이지에 넣는다)
        return FileResponse(STATIC / "index.html")

    return app
