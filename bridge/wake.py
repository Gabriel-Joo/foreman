"""자동 기상 2단계(11-08, docs/14_dispatcher_note_wake.md) — 실패 이벤트가 오면 디스패처가 계획만 만들고 사람에게 [시작]?을 묻는다.

README 3.5 "자동 기상"을 한 번에 자동으로 가지 않는다(docs/11_foreman_dispatch.md 7절):
  1단계 사람이 말하고 → 계획 → 승인(11-05) · **2단계 실패가 부르고 → 계획 → 텔레그램 · 화면에서 사람이 [시작]** · 3단계 묻지 않고 띄우기(보류)
조용한 고장이 되지 않게: 계획을 못 세우면 그것도 알리고, 하루 상한에 닿으면 그날 한 번 알린다. 알림을 보내는 쪽(파이프라인 · 적재 감시)은
이 모듈이 실패해도 아무 영향이 없다(콜백은 바로 돌아오고 일은 뒤에서).
"""

import asyncio
import logging
import socket
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import text

from bridge.inject import Refused
from bridge.roles import ROLE_KO

log = logging.getLogger("foreman.wake")
KST = ZoneInfo("Asia/Seoul")

KINDS = {
    "build_failed": "파이프라인 실패",
    "no_build": "빌드 알림 없음",
    "webhook_broken": "웹훅 끊김 의심",
    "infra_down": "인프라 응답 없음",
    "ingest_stuck": "적재 막힘",
}
MODE_KO = {"new": "새 세션", "handoff": "인계해서 새 세션", "attach": "살아 있는 세션에 보내기", "ask": "되묻기"}
# 역할 화면 이름 ROLE_KO는 bridge/roles.py 한 곳(11-15, 위 import)


@dataclass
class WakeRules:
    enabled: bool = True
    daily_max: int = 5
    dedupe_hours: float = 12.0
    public_url: str = ""
    kinds: list[str] = field(default_factory=lambda: list(KINDS))


def load_wake(path: str | Path) -> WakeRules:
    p = Path(path)
    if not p.exists():
        return WakeRules(enabled=False)
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    return WakeRules(enabled=bool(raw.get("enabled", True)), daily_max=int(raw.get("daily_max", 5)),
                     dedupe_hours=float(raw.get("dedupe_hours", 12)), public_url=str(raw.get("public_url", "")).rstrip("/"),
                     kinds=[k for k in raw.get("kinds", list(KINDS)) if k in KINDS])


LOCAL_URL = "http://localhost:8000"   # 화면은 서버 PC나 ssh -L로만 열린다(README 접속 · 3.13). public_url이 비면 이 주소
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def link_base(rules: WakeRules) -> str:
    return rules.public_url or LOCAL_URL


def is_local_url(url: str) -> bool:
    return (urlsplit(url).hostname or "") in LOCAL_HOSTS


async def check_public_url(rules: WakeRules, resolve: Callable[[str], Any] | None = None) -> str | None:
    """뜰 때 한 번: 알림 링크의 이름이 풀리는지 본다. 안 풀리면 사람에게 알릴 글을, 괜찮으면 None.
    11-15 — foreman.ronanlab.dev는 터널을 열지 않기로 한 날부터 풀리지 않는데 링크는 계속 그 이름이었고 아무도 몰랐다."""
    host = urlsplit(link_base(rules)).hostname or ""
    if not host or host in LOCAL_HOSTS:
        return None
    resolve = resolve or (lambda h: socket.getaddrinfo(h, None))
    try:
        await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, resolve, host), timeout=10)
    except Exception as e:  # noqa: BLE001 — 풀리지 않음 · 시간 초과 모두 같은 뜻
        return (f"config/wake.toml public_url의 이름 {host}을 찾지 못합니다({type(e).__name__}). 자동 기상 알림의 [시작] 링크가 열리지 않습니다. "
                f"public_url을 {LOCAL_URL}로 고치거나 비워 주십시오")
    return None


class Waker:
    def __init__(self, engine: Any, dispatcher: Any, notifier: Any, rules: WakeRules) -> None:
        self.engine, self.dispatcher, self.notifier, self.rules = engine, dispatcher, notifier, rules
        self._lock = asyncio.Lock()             # 한 번에 계획 하나(실패가 몰려도 claude -p를 여럿 띄우지 않는다)
        self._capped_day: str | None = None
        self._tasks: set[asyncio.Task] = set()

    # 파이프라인 · 적재 감시가 부른다 — 바로 돌아온다
    def failure(self, project: str | None, kind: str, key: str, what: str) -> None:
        if not self.rules.enabled or kind not in self.rules.kinds:
            return
        t = asyncio.create_task(self._wake(project, kind, key, what), name=f"foreman-wake-{kind}")
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        for t in list(self._tasks):
            t.cancel()

    async def _wake(self, project: str | None, kind: str, key: str, what: str) -> None:
        try:
            async with self._lock:
                await self._wake_inner(project, kind, key, what)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — 실패 알림 쪽으로 번지지 않게
            log.warning("자동 기상 실패 %s: %s", key, e)
            self._send(project, f"⚠ {KINDS[kind]} — 살펴볼 계획을 세우지 못했습니다({type(e).__name__}). 실패 알림을 직접 봐 주세요")

    async def _wake_inner(self, project: str | None, kind: str, key: str, what: str) -> None:
        now = datetime.now(KST)
        day0 = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        since = (now - timedelta(hours=self.rules.dedupe_hours)).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        async with self.engine.connect() as c:
            dup = (await c.execute(text("SELECT id FROM dispatch WHERE wake_key = :k AND created_at > :t LIMIT 1"),
                                   {"k": key, "t": since})).scalar()
            n_today = (await c.execute(text("SELECT COUNT(*) FROM dispatch WHERE origin = 'wake' AND created_at >= :t"),
                                       {"t": day0})).scalar() or 0
        if dup:
            log.info("자동 기상 — 같은 실패를 이미 계획함(dispatch #%s): %s", dup, key)
            return
        if n_today >= self.rules.daily_max:
            day = now.strftime("%Y-%m-%d")
            log.info("자동 기상 — 오늘 상한 %d번에 닿아 건너뜀: %s", self.rules.daily_max, key)
            if self._capped_day != day:
                self._capped_day = day
                self._send(project, f"오늘 자동 계획 {self.rules.daily_max}번을 다 썼습니다. 오늘 남은 실패는 알림만 갑니다(config/wake.toml daily_max)")
            return
        request = (f"[자동 · {KINDS[kind]}] 아래 실패 알림을 받았다. 원인을 살펴볼 세션 계획을 내라.\n\n{what[:1500]}")
        try:
            r = await self.dispatcher.plan(request, project, origin="wake", wake_key=key, wake_text=f"{KINDS[kind]} — {what.splitlines()[0][:300]}")
        except Refused as e:
            self._send(project, f"⚠ {KINDS[kind]} — 살펴볼 계획을 세우지 못했습니다. {e}. 실패 알림을 직접 봐 주세요")
            return
        p = r["plan"]
        base = link_base(self.rules)
        link = f"{base}/?dispatch={r['dispatch_id']}"
        test = "〔시험〕 " if what.startswith("〔시험〕") else ""
        lines = [f"🧭 {test}{KINDS[kind]} — 이렇게 살펴보자는 계획을 세웠습니다",
                 f"▶ {p.get('title') or '(이름 없음)'} — {ROLE_KO.get(p.get('role'), p.get('role'))}"
                 f"{' · 읽기 전용' if p.get('read_only') else ''} · {MODE_KO.get(p.get('mode'), p.get('mode'))}"
                 + (f"(세션 {p['attach_session']})" if p.get("attach_session") else "")]
        if p.get("reasons"):
            lines.append(f"이유: {str(p['reasons'][0])[:200]}")
        if p.get("questions"):
            lines.append(f"묻는 것: {str(p['questions'][0])[:200]}")
        how = "서버 PC 화면이나 ssh -L 8000:localhost:8000으로 엽니다" if is_local_url(base) else "화면에서 계획을 보고 눌러 주세요"
        lines.append(f"[시작]? 계획을 보고 화면에서 눌러 주세요. {how}: {link}")
        self._send(p.get("project") if p.get("repo") else project, "\n".join(lines))

    def _send(self, project: str | None, msg: str) -> None:
        if self.notifier is None:
            return
        rule = self.notifier.rules.for_project(project or "foreman")
        prefix = (rule and rule.prefix) or "[FOREMAN]"
        self.notifier.send_direct(project or "foreman", "wake", None, f"{prefix} {msg}")
