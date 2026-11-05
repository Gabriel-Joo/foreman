"""FastAPI 앱. 실행은 `.venv/bin/python -m bridge` (bridge/__main__.py)."""

import asyncio
import contextlib
import logging
import socket
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bridge.api import approvals as approvals_api, dashboard as dashboard_api, debug, health, hooks, sessions, ws
from bridge.api import handoff as handoff_api, terminal as terminal_api, webhooks
from bridge.handoff import HandoffManager
from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.api.auth import require_api_token
from bridge.assembler import Assembler
from bridge.bus import Pipeline
from bridge.config import Settings, get_settings
from bridge.db.engine import make_engine
from bridge.ingest_health import IngestMonitor
from bridge.mask import Masker
from bridge.notify import Notifier, default_telegram, load_rules
from bridge.session_state import SessionStateWatcher
from bridge.pipeline import PipelineManager, load_pipeline
from bridge.store import Store
from bridge.terminal import TerminalManager
from bridge.transcript.watcher import Watcher

log = logging.getLogger("foreman")
STATIC = Path(__file__).resolve().parent / "static"


class _QuietServer(uvicorn.Server):
    """웹훅 전용 포트 — 같은 앱 · 같은 프로세스의 두 번째 리스너. 신호(Ctrl-C)는 주 서버가 받는다(이 서버가 가로채지 않게)."""

    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        yield


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
        app.state.ingest_monitor = None
        watch_task = state_task = health_task = None
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
            # 11-03 — 적재가 막히면 스스로 알린다(텔레그램 [포먼] + 대시보드 머리 띠, bridge/ingest_health.py)
            mon = IngestMonitor(watcher, asm, app.state.notifier, s.ingest_alert_s, s.ingest_tick_alert_s,
                                on_change=dashboard_api.invalidate)
            app.state.ingest_monitor = mon
            health_task = asyncio.create_task(mon.run(), name="foreman-ingest-health")
            # 6단계 — 프로세스 정지 · 사라짐, CC status(busy · idle)는 이벤트로 오지 않는다. 바뀐 것만 WS로
            sw = SessionStateWatcher(s.sessions_dir, pipeline.publish)
            sw.on_change = dashboard_api.invalidate
            state_task = asyncio.create_task(sw.run(), name="foreman-session-state")
        # 8단계 — CI/CD 인과 체인: 로컬 git 폴링 · 웹훅 · 인프라 캐릭터 생존. 웹훅 전용 포트(VM 망 쪽)도 여기서 띄운다
        app.state.pipeline_mgr = None
        hook_server = hook_task = None
        if s.pipeline_enabled:
            try:
                pm = PipelineManager(engine, load_pipeline(s.pipeline_config), pipeline, Masker(), app.state.notifier,
                                     on_change=dashboard_api.invalidate)
                await pm.start()
                app.state.pipeline_mgr = pm
                log.info("파이프라인 켬: %s", ", ".join(pm.rules.projects))
            except Exception as e:  # noqa: BLE001
                log.warning("파이프라인 시작 실패: %s: %s", type(e).__name__, str(e)[:200])
            if app.state.pipeline_mgr and s.webhook_bind_host and s.foreman_webhook_token:
                # 소켓을 먼저 직접 묶는다 — uvicorn은 묶기에 실패하면 프로세스를 끝낸다(sys.exit). 실패해도 브리지는 산다
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((s.webhook_bind_host, s.webhook_bind_port))
                    sock.set_inheritable(True)
                except OSError as e:
                    sock = None
                    log.warning("웹훅 포트 %s:%d를 열지 못함: %s", s.webhook_bind_host, s.webhook_bind_port, e)
                if sock:
                    hook_server = _QuietServer(uvicorn.Config(app, lifespan="off", proxy_headers=False, log_level="info"))
                    hook_task = asyncio.create_task(hook_server.serve(sockets=[sock]), name="foreman-webhook-listener")
                    log.info("웹훅 포트 %s:%d (/webhooks/*만, 허용 망 %s)", s.webhook_bind_host, s.webhook_bind_port,
                             s.webhook_allow_cidrs)
            elif app.state.pipeline_mgr:
                log.warning("웹훅 포트를 열지 않음 — FOREMAN_WEBHOOK_TOKEN이 없다")
        # 11단계 앞당김(11-05) — 세션 인계 · 세션 조작. 알림이 꺼져 있어도 돈다(알림만 빠진다)
        app.state.handoff = HandoffManager(engine, s.sessions_dir, app.state.notifier,
                                           on_change=dashboard_api.invalidate)
        log.info("브리지 시작 %s:%d (DB %s:%d, 와처 %s)", s.bind_host, s.bind_port, s.mysql_host, s.mysql_port,
                 "켬" if s.watch_enabled else "끔")
        try:
            yield
        finally:
            if hook_server and hook_task:
                hook_server.should_exit = True
                try:
                    async with asyncio.timeout(5):
                        await hook_task
                except (TimeoutError, asyncio.CancelledError, Exception):  # noqa: BLE001
                    hook_task.cancel()
            if app.state.pipeline_mgr:
                await app.state.pipeline_mgr.stop()
            if app.state.notifier:
                await app.state.notifier.stop()
            if app.state.terminal:
                await app.state.terminal.stop()   # ttyd만 내린다 — tmux 셸은 남는다
            for t in (watch_task, state_task, health_task):
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
    app.include_router(handoff_api.router)
    app.include_router(approvals_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(terminal_api.api)
    app.include_router(terminal_api.router)
    app.include_router(webhooks.router)

    @app.middleware("http")
    async def webhook_port_only(request, call_next):  # type: ignore[no-untyped-def]
        # 웹훅 전용 포트(VM 망 쪽)에서는 /webhooks/*만 — 대시보드 · API · 터미널은 127.0.0.1에서만 열린다
        server = request.scope.get("server")
        if server and server[1] == s.webhook_bind_port and server[0] == s.webhook_bind_host \
                and not request.url.path.startswith("/webhooks/"):
            return JSONResponse({"error": "없음"}, status_code=404)
        return await call_next(request)

    @app.get("/api/pipeline", dependencies=[Depends(require_api_token)])
    async def pipeline_snapshot() -> dict:
        pm = app.state.pipeline_mgr
        return await pm.snapshot() if pm else {"projects": [], "enabled": False}

    @app.get("/api/ingest", dependencies=[Depends(require_api_token)])
    async def ingest_status() -> dict:
        asm, w = app.state.assembler, app.state.watcher
        if asm is None:
            return {"watch": "off"}
        return {"watch": "live" if asm.live else "backfill", "backfill_seconds": w.backfill_seconds,
                "watched_dirs": len(w.wd_path), "dirty": len(w.dirty), "stats": await asm.stats_snapshot(),
                "health": w.health(s.ingest_alert_s)}

    if s.debug_endpoints:
        app.include_router(debug.router)

    # 화면은 비밀값이 없으므로 인증 없이 준다(토큰은 사용자가 페이지에 넣는다). 데이터 API는 모두 토큰이 필요하다
    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC / "office.html")      # 10단계 픽셀 화면(10b에 / 로 — 승인 · 대화 · 입력 · 터미널이 이 화면에서 된다)

    @app.get("/office", include_in_schema=False)
    async def office_page() -> FileResponse:
        return FileResponse(STATIC / "office.html")      # 예전 주소(북마크) — / 와 같다

    @app.get("/classic", include_in_schema=False)
    async def classic_page() -> FileResponse:
        return FileResponse(STATIC / "dashboard.html")   # 6단계 카드 대시보드

    @app.get("/debug", include_in_schema=False)
    async def debug_page() -> FileResponse:
        return FileResponse(STATIC / "debug.html")       # 1~5단계 확인 페이지(로그 · 디버그 이벤트)

    @app.middleware("http")
    async def no_stale_ui(request, call_next):  # type: ignore[no-untyped-def]
        # 화면 파일은 매번 다시 확인한다(ETag라 바뀌지 않았으면 304) — 7단계 실측: 브라우저가 옛 store.js를 캐시에서 써서
        # 새 terminal.js와 어긋났고, 그 오류로 대시보드 연결이 시작되지 않았다
        resp = await call_next(request)
        p = request.url.path
        if p in ("/", "/debug", "/office", "/classic") or p.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
