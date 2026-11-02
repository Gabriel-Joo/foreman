"""FastAPI 앱. 실행은 `.venv/bin/python -m bridge` (bridge/__main__.py)."""

import logging
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bridge.api import approvals as approvals_api, dashboard as dashboard_api, debug, health, hooks, sessions, ws
from bridge.api import terminal as terminal_api
from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.api.auth import require_api_token
from bridge.assembler import Assembler
from bridge.bus import Pipeline
from bridge.config import Settings, get_settings
from bridge.db.engine import make_engine
from bridge.mask import Masker
from bridge.notify import Notifier, default_telegram, load_rules
from bridge.session_state import SessionStateWatcher
from bridge.store import Store
from bridge.terminal import TerminalManager
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
        app.state.assembler = app.state.watcher = app.state.notifier = app.state.approvals = None
        app.state.terminal = None
        watch_task = state_task = None
        if s.terminal_enabled:
            # 7단계 터미널 패널 — ttyd(UNIX 소켓) + tmux foreman-shell. 실패해도 브리지는 뜬다
            term = TerminalManager(engine, s, pipeline, Masker(), publish=pipeline.publish,
                                   on_change=dashboard_api.invalidate)
            try:
                await term.start()
                app.state.terminal = term
                log.info("터미널 패널 켬: tmux %s, ttyd 소켓 %s", s.terminal_tmux_session, s.terminal_socket)
            except Exception as e:  # noqa: BLE001
                log.warning("터미널 패널 시작 실패: %s: %s", type(e).__name__, str(e)[:200])
        if s.watch_enabled:
            asm = Assembler(engine, s, Masker(), publish=pipeline.publish)
            await asm.load()
            if s.notify_enabled:
                rules = load_rules(s.notify_config)
                notifier = Notifier(engine, rules, default_telegram(rules), Masker())
                notifier.start()
                n = await notifier.baseline()
                log.info("알림 기준선: 이미 끝난 서브에이전트 %d개를 알린 것으로", n)
                asm.on_subagents_changed = notifier.on_subagents_changed
                app.state.notifier = notifier
                log.info("알림 켬: %s", ", ".join(f"{k}{v.prefix}" for k, v in rules.projects.items()))
            # 턴이 닫히면 — 알림(4단계)과 터미널 부탁 감지(7단계)
            closed_cbs = [x.on_turn_closed for x in (app.state.notifier, app.state.terminal) if x]
            if closed_cbs:
                def on_turn_closed(*a: object) -> None:
                    for cb in closed_cbs:
                        cb(*a)
                asm.on_turn_closed = on_turn_closed
            watcher = Watcher(s, asm)
            app.state.assembler, app.state.watcher = asm, watcher

            async def titles() -> None:   # 0011 이전에 적재한 세션의 제목 — 빈 칸만 채운다
                try:
                    n = await asm.fill_titles()
                    if n:
                        log.info("세션 제목 채움: %d개", n)
                        dashboard_api.invalidate()
                except Exception as e:  # noqa: BLE001
                    log.warning("세션 제목 채우기 실패: %s", type(e).__name__)
            app.state.title_task = asyncio.create_task(titles(), name="foreman-titles")
            if s.approval_enabled:
                mgr = ApprovalManager(engine, load_policy(s.approval_config), asm, pipeline, Masker(),
                                      app.state.notifier)
                n = await mgr.start()
                asm.on_tool_result = mgr.on_tool_result
                app.state.approvals = mgr
                log.info("승인 정책 켬: %s (끊긴 대기 %d건 정리)", ", ".join(
                    f"{k}={v.mode}" for k, v in mgr.policy.projects.items()), n)
            watch_task = asyncio.create_task(watcher.run(), name="foreman-watcher")
            # 6단계 — 프로세스 정지 · 사라짐, CC status(busy · idle)는 이벤트로 오지 않는다. 바뀐 것만 WS로
            sw = SessionStateWatcher(s.sessions_dir, pipeline.publish)
            sw.on_change = dashboard_api.invalidate
            state_task = asyncio.create_task(sw.run(), name="foreman-session-state")
        log.info("브리지 시작 %s:%d (DB %s:%d, 와처 %s)", s.bind_host, s.bind_port, s.mysql_host, s.mysql_port,
                 "켬" if s.watch_enabled else "끔")
        try:
            yield
        finally:
            if app.state.notifier:
                await app.state.notifier.stop()
            if app.state.terminal:
                await app.state.terminal.stop()   # ttyd만 내린다 — tmux 셸은 남는다
            for t in (watch_task, state_task):
                if t:
                    t.cancel()
                    try:
                        await t
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
    app.include_router(sessions.router)
    app.include_router(approvals_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(terminal_api.api)
    app.include_router(terminal_api.router)

    @app.get("/api/ingest", dependencies=[Depends(require_api_token)])
    async def ingest_status() -> dict:
        asm, w = app.state.assembler, app.state.watcher
        if asm is None:
            return {"watch": "off"}
        return {"watch": "live" if asm.live else "backfill", "backfill_seconds": w.backfill_seconds,
                "watched_dirs": len(w.wd_path), "dirty": len(w.dirty), "stats": await asm.stats_snapshot()}

    if s.debug_endpoints:
        app.include_router(debug.router)

    # 화면은 비밀값이 없으므로 인증 없이 준다(토큰은 사용자가 페이지에 넣는다). 데이터 API는 모두 토큰이 필요하다
    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC / "dashboard.html")   # 6단계 대시보드

    @app.get("/debug", include_in_schema=False)
    async def debug_page() -> FileResponse:
        return FileResponse(STATIC / "debug.html")       # 1~5단계 확인 페이지(로그 · 디버그 이벤트)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
