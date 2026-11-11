"""세션이 살아 있는지 · 멈췄는지(11-11, README 「나중에 할 일」 「세션이 살아 있는지 · 멈췄는지 알기」).

CC는 스스로 심장박동을 보내지 않는다 — sessions/<pid>.json의 updatedAt은 상태(busy · idle)가 바뀔 때만 바뀐다(11-11 확인:
작업 중 11분째에도 그대로). 그래서 브리지가 1분마다 직접 잰다(심장박동 = 프로세스 · CC 상태 · 대화 기록의 마지막 줄 · tmux 화면).

멈춤의 종류(kind) — 화면(/api/dashboard `stall`)과 텔레그램이 같은 판정을 쓴다:
- died        작업 중(열린 턴)에 세션 프로세스가 사라졌다 — 일이 끝났다는 신호 없이 끊김
- silent      작업 중(busy)인데 SILENT 동안 대화 기록에 한 줄도 없다 — 한 도구가 끝나지 않는다
              (11-09 `until ! pgrep -f …` 셸이 영원히 돌았던 꼴. 화면의 스피너는 계속 돌아 화면으로는 못 가린다)
- loop        같은 작업(열린 턴)에서 LOOP_WINDOW 안에 같은 도구 · 같은 대상을 LOOP_SAME번 넘게, 또는 실패가 LOOP_ERRORS번 넘게(삽질)
- exit_confirm CC 끝내기 확인 창("Background work is running … Exit and stop tasks")이 떠 있다 — 사람 답을 기다리며 멈춤
              (README 「세션이 끝나지 않고 CC 끝내기 확인 창에 걸린 것」)
- long        한 작업이 LONG 넘게 — 화면에만(알리지 않는다, 긴 일은 정상일 수 있다)

알림: kind마다 ALERT_AFTER를 넘으면 텔레그램 한 번(notification.rule 키 `stall:<kind>:<세션>:<시작 시각>` — 브리지를 다시 띄워도 한 번).
exit_confirm의 시작 시각은 브리지 메모리(처음 본 때)라, 다시 띄우면 한 번 더 갈 수 있다.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text

from bridge.inject import Refused, _status, _tmux_env, tmux
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.stallwatch")

SILENT = timedelta(minutes=30)
LOOP_WINDOW = timedelta(minutes=30)
LOOP_SAME = 6
LOOP_ERRORS = 8
# 같은 파일을 여러 번 고치고 읽는 것은 보통 코딩이다(11-11 실제로 재 보니 코더 272가 dashboard.py Edit 6번으로 걸렸다)
LOOP_QUIET = {"Edit", "MultiEdit", "Write", "NotebookEdit", "Read", "TodoWrite", "Grep", "Glob"}
LONG = timedelta(hours=2)
EXIT_RE = re.compile(r"Background work is running|will stop when you exit|Exit and stop tasks")
ALERT_AFTER = {"died": timedelta(0), "silent": timedelta(0), "loop": timedelta(0), "exit_confirm": timedelta(minutes=2)}

LABEL = {
    "died": "작업 중에 끊김",
    "silent": "응답 없음",
    "loop": "같은 자리에서 맴돎",
    "exit_confirm": "끝내기 확인 창에서 멈춤",
    "long": "긴 작업",
}


@dataclass
class Sample:
    """한 세션의 한 번 잰 값 — judge()의 입력(순수 판정을 시험하려고 DB · tmux와 떼어 둠)."""
    sid: int
    live: bool
    busy: bool = False
    turn_started: datetime | None = None          # 열린 턴(없으면 None)
    last_event: datetime | None = None
    last_tool: tuple[str | None, str | None] | None = None
    same: tuple[str | None, str | None, int] | None = None   # (도구, 대상, 횟수) — LOOP_WINDOW 안 같은 것 가장 많이
    errors: int = 0
    screen: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def judge(s: Sample, now: datetime, exit_since: datetime | None = None) -> list[dict[str, Any]]:
    """멈춤 목록 — [{kind, label, since, detail}]. since는 그 상태가 시작된 때(알림 키에 쓴다)."""
    out: list[dict[str, Any]] = []

    def add(kind: str, since: datetime | None, detail: str) -> None:
        out.append({"kind": kind, "label": LABEL[kind], "since": since, "detail": detail})

    if not s.live:
        if s.turn_started:
            add("died", s.last_event or s.turn_started, "작업이 끝났다는 신호 없이 세션 프로세스가 사라졌습니다")
        return out
    if s.screen and EXIT_RE.search(s.screen):
        add("exit_confirm", exit_since or now, "CC가 뒤에서 도는 일을 멈출지 묻고 기다립니다(1 멈추고 끝내기 · 2 뒤로 보내고 끝내기 · 3 남기)")
    if s.busy and s.last_event and now - s.last_event >= SILENT:
        tool, target = s.last_tool or (None, None)
        mins = int((now - s.last_event).total_seconds() // 60)
        add("silent", s.last_event, f"{mins}분째 대화 기록에 줄이 없습니다 — 마지막 도구 {tool or '?'}"
            + (f" {target[:80]}" if target else "") + "가 끝나지 않았을 수 있습니다")
    if s.turn_started:
        if s.same and s.same[2] >= LOOP_SAME:
            add("loop", s.turn_started, f"30분 안에 {s.same[0]} {(s.same[1] or '')[:80]}를 {s.same[2]}번 했습니다")
        elif s.errors >= LOOP_ERRORS:
            add("loop", s.turn_started, f"30분 안에 도구가 {s.errors}번 실패했습니다")
        if now - s.turn_started >= LONG:
            add("long", s.turn_started, f"한 작업이 {int((now - s.turn_started).total_seconds() // 60)}분째입니다")
    return out


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


class StallWatch:
    def __init__(self, engine: Any, notifier: Any, sessions_dir: Any, every_s: float = 60.0) -> None:
        self.engine, self.notifier, self.dir, self.every = engine, notifier, sessions_dir, every_s
        self.live: Any = live_sessions          # 시험이 바꿔 끼운다
        self.status: Any = _status
        self.screen: Any = self._screen
        self.exit_seen: dict[int, datetime] = {}   # 끝내기 확인 창을 처음 본 때(세션별, 메모리)
        self.snapshot: dict[int, list[dict[str, Any]]] = {}   # 대시보드가 읽는다

    async def _screen(self, pid: int) -> str | None:
        te = _tmux_env(pid)
        if not te:
            return None
        try:
            return await tmux(te[0], "capture-pane", "-p", "-t", te[1])
        except Refused:
            return None

    async def samples(self, now: datetime) -> tuple[list[Sample], dict[int, tuple[Any, ...]]]:
        live = await asyncio.to_thread(self.live, self.dir)
        live_ok = {cc: ls for cc, ls in live.items() if ls.state != "T"}     # 멈춰 둔(Ctrl+Z) 것은 보지 않는다
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), p.name, "
                "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id) "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.type = 'agent' AND cs.hidden_at IS NULL AND (cs.cc_session_id IN :ids OR cs.id IN "
                "(SELECT session_id FROM turn WHERE ended_at IS NULL AND started_at > :cut))"
            ).bindparams(bindparam("ids", expanding=True)),
                {"ids": sorted(live_ok) or ["-"], "cut": now - timedelta(hours=24)})).all()
            if not rows:
                return [], {}
            in_ids = "(" + ",".join(str(int(r[0])) for r in rows) + ")"
            turns = {r[0]: r[1:] for r in (await c.execute(text(
                f"SELECT session_id, id, started_at FROM turn WHERE session_id IN {in_ids} AND ended_at IS NULL"))).all()}
            last_tool = {r[0]: (r[1], r[2]) for r in (await c.execute(text(
                f"SELECT e.session_id, e.tool, e.target FROM event e JOIN (SELECT session_id, MAX(id) mid FROM event "
                f"WHERE session_id IN {in_ids} AND type = 'tool_use' GROUP BY session_id) x ON x.mid = e.id"))).all()}
            same: dict[int, tuple[Any, Any, int]] = {}
            errs: dict[int, int] = {}
            for sid, (tid, _) in turns.items():
                r = (await c.execute(text(
                    "SELECT tool, LEFT(target, 160), COUNT(*) n FROM event WHERE session_id = :s AND turn_id = :t "
                    "AND type = 'tool_use' AND ts > :w AND tool NOT IN :quiet GROUP BY tool, LEFT(target, 160) "
                    "ORDER BY n DESC LIMIT 1").bindparams(bindparam("quiet", expanding=True)),
                    {"s": sid, "t": tid, "w": now - LOOP_WINDOW, "quiet": sorted(LOOP_QUIET)})).first()
                if r:
                    same[sid] = (r[0], r[1], int(r[2]))
                errs[sid] = int((await c.execute(text(
                    "SELECT COUNT(*) FROM event WHERE session_id = :s AND turn_id = :t AND type = 'tool_result' "
                    "AND status = 'error' AND ts > :w"), {"s": sid, "t": tid, "w": now - LOOP_WINDOW})).scalar() or 0)
        out: list[Sample] = []
        meta: dict[int, tuple[Any, ...]] = {}
        for sid, cc, title, project, last_ts in rows:
            if cc in live and cc not in live_ok:      # 멈춰 둔(T) 세션 — 끊긴 것도 멈춘 것도 아니다(사용자가 남겨 둠)
                continue
            ls = live_ok.get(cc)
            busy = bool(ls and self.status(self.dir, ls.pid) == "busy")
            screen = await self.screen(ls.pid) if ls and not busy else None    # 끝내기 확인 창은 일하지 않을 때 뜬다
            t = turns.get(sid)
            out.append(Sample(sid=sid, live=bool(ls), busy=busy, turn_started=t[1] if t else None, last_event=last_ts,
                              last_tool=last_tool.get(sid), same=same.get(sid), errors=errs.get(sid, 0), screen=screen))
            meta[sid] = (title, project)
        return out, meta

    async def check(self, now: datetime | None = None) -> list[str]:
        """한 번 잰다 — snapshot을 고치고, 알릴 것은 보낸다. 돌려주는 값: 이번에 보낸 rule 키들."""
        now = now or datetime.now(UTC).replace(tzinfo=None)
        samples, meta = await self.samples(now)
        snap: dict[int, list[dict[str, Any]]] = {}
        sent: list[str] = []
        seen_exit: set[int] = set()
        for s in samples:
            if s.screen and EXIT_RE.search(s.screen):
                seen_exit.add(s.sid)
                self.exit_seen.setdefault(s.sid, now)
            found = judge(s, now, self.exit_seen.get(s.sid))
            if found:
                snap[s.sid] = [{**f, "since": _iso(f["since"])} for f in found]
            for f in found:
                if f["kind"] not in ALERT_AFTER or now - (f["since"] or now) < ALERT_AFTER[f["kind"]]:
                    continue
                key = f"stall:{f['kind']}:{s.sid}:{(f['since'] or now):%Y%m%d%H%M}"
                if await self._send(key, s.sid, meta.get(s.sid, (None, None)), f):
                    sent.append(key)
        for sid in list(self.exit_seen):
            if sid not in seen_exit:
                del self.exit_seen[sid]
        self.snapshot = snap
        return sent

    async def _send(self, key: str, sid: int, meta: tuple[Any, ...], f: dict[str, Any]) -> bool:
        if self.notifier is None:
            return False
        async with self.engine.connect() as c:
            if (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                return False
        title, project = meta
        rule = self.notifier.rules.for_project(project) if project else None
        prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
        what = {"died": "다시 띄우거나 [새로 띄우기]로 이어 갑니다",
                "silent": "터미널에서 무엇이 도는지 보고, 필요하면 [작업 중단]을 누릅니다",
                "loop": "그 세션에 다른 방법을 지시하거나 [작업 중단]을 누릅니다",
                "exit_confirm": "터미널에서 고릅니다 — 뒤에서 도는 일이 끝나도 되면 1, 남기려면 3"}.get(f["kind"], "")
        msg = "\n".join([f"{prefix} ⏸ {f['label']} — 「{title or sid}」(세션 {sid})", f"▶ {f['detail']}", what])
        log.warning("멈춤 알림: 세션 %s %s — %s", sid, f["kind"], f["detail"][:120])
        self.notifier.send_direct(project, "stall", sid, msg, rule=key)
        return True

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.every)
            try:
                await self.check()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 감시를 멈추지 않는다
                log.warning("멈춤 확인 실패: %s: %s", type(e).__name__, str(e)[:200])
