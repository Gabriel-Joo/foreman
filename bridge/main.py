"""FastAPI 앱. 실행은 `.venv/bin/python -m bridge` (bridge/__main__.py)."""

import asyncio
import contextlib
import logging
import os
import shutil
import socket
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bridge.api import approvals as approvals_api, dashboard as dashboard_api, debug, health, hooks, sessions, ws
from bridge.api import foreman as foreman_api, handoff as handoff_api, terminal as terminal_api, webhooks
from bridge.api import publish as publish_api
from bridge.api import scribe as scribe_api
from bridge.api import usage as usage_api
from bridge.usage import UsageMonitor, load_config as load_usage
from bridge.notion import NotionClient, Publisher, load_token
from bridge.foreman import ForemanDispatcher
from bridge.wake import Waker, load_wake
from bridge.handoff import HandoffManager
from bridge.promote import Promoter
from bridge.losscheck import LossChecker
from bridge.model_choice import Models
from bridge.liveness import live_sessions
from bridge.previews import Previews
from bridge.schemalock import SchemaLock
from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.api.auth import require_api_token
from bridge.assembler import Assembler
from bridge.compactwatch import CompactWatch, load_rules as load_compact_rules
from bridge.overlap import OverlapWatch
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
        app.state.compact_rules = load_compact_rules(s.notify_config)   # 대시보드 압축 표시 기준(적재가 꺼져 있어도)
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
            # 압축 알림(11-05) — 정한 횟수의 압축 직후 텔레그램. 기준값(notify.toml [compact])은 대시보드 표시에도 쓴다
            cw = CompactWatch(engine, app.state.notifier, getattr(app.state.notifier, "rules", None), s.notify_config)
            app.state.compact = cw
            cw_tasks: set[asyncio.Task[None]] = set()

            def on_compact(sid: int) -> None:
                t = asyncio.get_running_loop().create_task(cw.on_compact(sid))
                cw_tasks.add(t)
                t.add_done_callback(cw_tasks.discard)
            asm.on_compact = on_compact
            # 겹침 알림(11-06) — 사람 입력이 같은 프로젝트의 살아 있는 다른 세션의 최근 요청과 겹치면 알린다(막지 않는다)
            ow = OverlapWatch(engine, app.state.notifier, getattr(app.state.notifier, "rules", None), s.notify_config,
                              s.sessions_dir, on_change=dashboard_api.invalidate)
            app.state.overlap = ow
            asm.on_human_prompt = ow.on_prompt
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
        asm_ = app.state.assembler
        app.state.handoff = HandoffManager(engine, s.sessions_dir, app.state.notifier,
                                           on_change=dashboard_api.invalidate,
                                           project_of=(lambda cwd: asm_._project_for(cwd, "")) if asm_ else None)
        # 11-05 — 인계 2판 ① 문서로 옮기기(목록 → 사람 승인 → 세션이 쓰고 커밋 → 브리지가 git으로 확인)
        app.state.handoff.promote = Promoter(app.state.handoff)
        # 11-06 — 인계 2판 d [잃은 것 보기](압축 손실 점검, claude -p). 모델은 config/models.toml [tasks] losscheck
        app.state.handoff.losscheck = LossChecker(app.state.handoff, model=Models().task("losscheck"))
        try:
            n_ = await app.state.handoff.losscheck.recover()
            if n_:
                log.warning("잃은 것 점검 %d개가 돌던 중이었다 — failed로 바꿨다(브리지 재시작)", n_)
        except Exception as e:  # noqa: BLE001 — 0021 전이면 표가 없다. 브리지는 뜬다
            log.warning("잃은 것 점검 정리 못 함: %s", type(e).__name__)
        # 11-06 — Notion 게시(12c). 토큰(.env.notion)이 없으면 꺼 두고 사유를 보인다. 토큰 값은 찍지 않는다
        app.state.publisher, app.state.publisher_off = None, None
        root_dir = Path(__file__).resolve().parent.parent
        try:
            import tomllib
            ncfg = tomllib.loads((root_dir / "config" / "notion.toml").read_text(encoding="utf-8")).get("foreman") or {}
            tok = load_token(root_dir / ".env.notion")
            if not ncfg.get("root"):
                app.state.publisher_off = "config/notion.toml에 루트 페이지가 없습니다"
            elif not tok:
                app.state.publisher_off = "Notion 토큰이 없습니다 — .env.notion에 NOTION_TOKEN을 넣고 브리지를 다시 띄워 주세요"
            else:
                app.state.publisher = Publisher(engine, NotionClient(tok), ncfg["root"], str(root_dir),
                                                gh=ncfg.get("github") or "https://github.com/Gabriel-Joo/foreman")
        except OSError as e:
            app.state.publisher_off = f"Notion 설정을 읽지 못했습니다({type(e).__name__})"
        # 11-05 — 스키마 잠금(세션 둘 이상이 한 프로젝트에 붙을 때 DB 스키마는 한 세션만). 합치기 · 버리기에서 푼다
        sd = s.sessions_dir
        app.state.schema_lock = SchemaLock(Path(__file__).resolve().parent.parent / "config" / "worktree.toml",
                                           alive=lambda cc: cc in live_sessions(sd))
        app.state.handoff.schema = app.state.schema_lock
        # 11-05 — 미리보기 브리지(worktree 화면 + 지금 브리지 데이터). 버튼을 누를 때만 띄우고 끝내기 · 합치기 · 버리기 때 끈다
        app.state.handoff.previews = Previews(Path(__file__).resolve().parent.parent / "config" / "worktree.toml",
                                              app.state.handoff.socket, f"http://{s.bind_host}:{s.bind_port}")
        try:
            n = await app.state.handoff.previews.sweep()
            if n:
                log.info("주인 없는 미리보기 %d개를 껐다", n)
        except Exception as e:  # noqa: BLE001 — 정리 실패가 기동을 막지 않는다
            log.warning("미리보기 정리 실패: %s", e)
        if app.state.approvals:
            app.state.approvals.schema = app.state.schema_lock
        # 11단계 — 포먼 디스패처(사람이 말하면 계획 → 승인하면 시작). 부를 때만 claude -p
        async def _pipe_snap() -> dict:
            pm = app.state.pipeline_mgr
            return await pm.snapshot() if pm else {"projects": []}
        app.state.foreman = ForemanDispatcher(engine, s.sessions_dir, app.state.handoff,
                                              (lambda: asm_.projects) if asm_ else (lambda: []), _pipe_snap)
        # 11-08 — systemd PATH에 claude가 없어 디스패처가 이틀 동안 "claude를 띄우지 못했습니다"였다(부를 때까지 아무도 몰랐다).
        # 기동 때 찾아 보고, 없으면 텔레그램으로 한 번 — 디스패처 · 인계 요약 · 자동 기상이 모두 이 실행 파일을 쓴다
        if shutil.which("claude") is None:
            why = f"브리지가 claude 실행 파일을 PATH에서 찾지 못합니다 — 디스패처 · 인계 요약 · 자동 기상이 안 됩니다(PATH={os.environ.get('PATH', '')})"
            log.error(why)
            if app.state.notifier:
                rule = app.state.notifier.rules.for_project("foreman")
                app.state.notifier.send_direct("foreman", "direct", None, f"{(rule and rule.prefix) or '[FOREMAN]'} ⚠ {why}")
        # 감독실 캐릭터(디스패처의 얼굴)가 계획을 세우는 중 · 제안 대기를 보이게 — 화면이 /api/foreman/state를 다시 읽는다
        app.state.foreman.on_change = lambda: pipeline.publish({"type": "foreman"})
        # 11-08 자동 기상 2단계 — 실패 이벤트 → 디스패처가 계획만 → 텔레그램 · 화면에서 사람이 [시작]
        app.state.waker = None
        try:
            wr = load_wake(Path(__file__).resolve().parent.parent / "config" / "wake.toml")
            if wr.enabled:
                app.state.waker = Waker(engine, app.state.foreman, app.state.notifier, wr)
                for src in (app.state.pipeline_mgr, app.state.ingest_monitor):
                    if src is not None:
                        src.on_failure = app.state.waker.failure
                log.info("자동 기상 2단계 켬: %s(하루 %d번)", ", ".join(wr.kinds), wr.daily_max)
        except Exception as e:  # noqa: BLE001 — 자동 기상이 안 떠도 브리지는 뜬다
            log.warning("자동 기상을 켜지 못함: %s", e)
        # 11-08 사용량(docs/15) — `claude -p "/usage"`를 poll_s마다(모델 호출 없음). 못 읽으면 연달아 fail_alert번에 텔레그램
        app.state.usage = None
        usage_task = None
        if s.usage_enabled:
            try:
                ucfg = load_usage(s.usage_config)
                app.state.usage = UsageMonitor(engine, ucfg, app.state.notifier, on_change=usage_api.invalidate)
                usage_task = asyncio.create_task(app.state.usage.run(), name="foreman-usage")
                log.info("사용량 읽기 켬: %d초마다, 한도 %s", ucfg.poll_s, ", ".join(x.key for x in ucfg.limits))
            except Exception as e:  # noqa: BLE001 — 설정이 깨져도 브리지는 뜬다. 다만 조용히 넘어가지 않는다
                why = f"사용량 읽기를 켜지 못했다(config/usage.toml): {type(e).__name__}: {str(e)[:200]}"
                log.error(why)
                if app.state.notifier:
                    rule = app.state.notifier.rules.for_project("foreman")
                    app.state.notifier.send_direct("foreman", "usage", None, f"{(rule and rule.prefix) or '[FOREMAN]'} ⚠ {why}")
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
            if getattr(app.state, "waker", None):
                await app.state.waker.stop()
            if app.state.notifier:
                await app.state.notifier.stop()
            if app.state.terminal:
                await app.state.terminal.stop()   # ttyd만 내린다 — tmux 셸은 남는다
            for t in (watch_task, state_task, health_task, usage_task):
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
    app.include_router(publish_api.router)
    app.include_router(scribe_api.router)
    app.include_router(foreman_api.router)
    app.include_router(approvals_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(usage_api.router)
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

    @app.get("/usage", include_in_schema=False)
    async def usage_page() -> FileResponse:
        return FileResponse(STATIC / "usage.html")       # 11-08 사용량 · 한도(docs/15). 데이터는 /api/usage(토큰)

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
