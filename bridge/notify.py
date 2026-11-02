"""텔레그램 알림 — 턴이 닫히는 순간 브리지가 기계적으로 보낸다(로드맵 4단계, README 3.2).

모델이 CLAUDE.md 지시를 보고 스크립트를 부르던 방식은 모델이 턴 종료를 판정해서 누락이 생겼다.
여기서는 조립기가 턴을 닫을 때(먼저 온 신호) 부른다. 규칙은 config/notify.toml.

- 종료 이유마다 제목이 다르다: 끝남 / ⚠ API 오류 / ⏹ 중단 / 세션 종료 / ⚠ 프로세스 사라짐 / (merged · no_signal은 기본 안 보냄)
- 서브에이전트는 따로 보내지 않는다. 사람이 연 턴이 끝날 때 그 턴의 서브에이전트를 한 줄로 요약하고,
  task-notification이 연 턴은 보내지 않다가 그 세션의 백그라운드 서브에이전트가 모두 끝났을 때 한 번 묶어 보낸다
- 보낸 것 · 안 보낸 것 · 묶음 대기는 notification 테이블에 이유와 함께 남는다
- 토큰은 .env.telegram에서 읽고, 어떤 오류 메시지 · 로그에도 싣지 않는다
"""

import asyncio
import logging
import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.config import REPO

log = logging.getLogger("foreman.notify")

FAIL_REASONS = {"stop_failure", "interrupted", "process_lost"}
TITLES = {
    "stop": "끝남",
    "stop_failure": "⚠ API 오류로 멈춤",
    "interrupted": "⏹ 중단됨(사용자)",
    "session_end": "세션 종료 — 진행 중이던 턴",
    "process_lost": "⚠ 프로세스가 사라짐(종료 신호 없음)",
    "merged": "응답 없이 다음 입력과 합쳐짐",
    "no_signal": "종료 신호 없이 다음 턴이 시작됨",
    "abandoned": "끝 신호 없이 버려진 턴",
}
ORIGIN_LABEL = {"human": "요청", "meta": "입력", "agent_message": "다른 세션 메시지", "task_notification": "완료 알림",
                "subagent_message": "서브에이전트 결과"}
SUB_STATUS = {"done": "완료", "failed": "실패", "stopped": "중단", "running": "진행", "stale": "확인 안 됨"}
_WRAP = re.compile(r'^\s*<pasted_content id="[0-9a-f]+">\s*', re.S)


# ── 규칙 ────────────────────────────────────────────────────
@dataclass
class ProjectRule:
    prefix: str | None
    end_reasons: set[str]
    origins: set[str]
    batch_origins: set[str]
    only_failures: bool
    min_turn_s: float


@dataclass
class Rules:
    enabled: bool = True
    env_file: str = ".env.telegram"
    timeout_s: float = 10.0
    min_interval_s: float = 1.1
    settle_s: float = 2.0
    defaults: ProjectRule = field(default_factory=lambda: ProjectRule(
        None, {"stop", "stop_failure", "interrupted", "session_end", "process_lost"}, {"human", "meta"},
        {"task_notification", "subagent_message"}, False, 0.0))
    projects: dict[str, ProjectRule] = field(default_factory=dict)

    def for_project(self, name: str | None) -> ProjectRule | None:
        """접두어가 있는 프로젝트만 규칙을 돌려준다(없으면 보내지 않는다)."""
        return self.projects.get(name or "")


def load_rules(path: str | Path) -> Rules:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    tg, dflt = raw.get("telegram", {}), raw.get("defaults", {})
    r = Rules(enabled=tg.get("enabled", True), env_file=tg.get("env_file", ".env.telegram"),
              timeout_s=tg.get("timeout_s", 10.0), min_interval_s=tg.get("min_interval_s", 1.1),
              settle_s=tg.get("settle_s", 2.0))

    def rule(d: dict[str, Any], base: ProjectRule, prefix: str | None) -> ProjectRule:
        return ProjectRule(prefix, set(d.get("end_reasons", base.end_reasons)), set(d.get("origins", base.origins)),
                           set(d.get("batch_origins", base.batch_origins)), d.get("only_failures", base.only_failures),
                           float(d.get("min_turn_s", base.min_turn_s)))

    r.defaults = rule(dflt, r.defaults, None)
    for name, d in raw.get("projects", {}).items():
        if d.get("prefix"):
            r.projects[name] = rule(d, r.defaults, d["prefix"])
    return r


# ── 문장 ────────────────────────────────────────────────────
def fmt_duration(secs: float | None) -> str:
    if secs is None:
        return "?"
    s = int(round(secs))
    if s < 60:
        return f"{s}초"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}분 {s}초" if s else f"{m}분"
    h, m = divmod(m, 60)
    return f"{h}시간 {m}분"


def first_line(s: str | None, limit: int) -> str:
    if not s:
        return ""
    s = _WRAP.sub("", s)
    for line in s.splitlines():
        line = line.strip()
        if line and not line.startswith("</pasted_content"):
            return line if len(line) <= limit else line[: limit - 1] + "…"
    return ""


def sub_summary(subs: list[tuple[str, str | None]]) -> str | None:
    if not subs:
        return None
    counts: dict[str, int] = {}
    for status, _ in subs:
        counts[status] = counts.get(status, 0) + 1
    parts = " · ".join(f"{SUB_STATUS.get(k, k)} {v}" for k, v in sorted(counts.items(), key=lambda kv: kv[0] != "done"))
    return f"서브에이전트 {len(subs)} — {parts}"


def compose_turn(prefix: str, reason: str, origin: str, secs: float | None, prompt: str | None,
                 reply: str | None, error: str | None, subs: list[tuple[str, str | None]]) -> str:
    lines = [f"{prefix} {TITLES.get(reason, reason)} · {fmt_duration(secs)}"]
    if (p := first_line(prompt, 80)):
        lines.append(f"{ORIGIN_LABEL.get(origin, '입력')}: {p}")
    if reason == "stop_failure" and error:
        lines.append(f"오류: {first_line(error, 200)}")
    elif reason == "stop" and (r := first_line(reply, 200)):
        lines.append(f"응답: {r}")
    if (sm := sub_summary(subs)):
        lines.append(sm)
    return "\n".join(lines)[:900]


def compose_batch(prefix: str, subs: list[tuple[str, str | None]]) -> str:
    lines = [f"{prefix} 백그라운드 서브에이전트 {len(subs)}개 모두 끝남", sub_summary(subs) or ""]
    for status, desc in subs[:5]:
        lines.append(f"- {first_line(desc, 60) or '(설명 없음)'} ({SUB_STATUS.get(status, status)})")
    if len(subs) > 5:
        lines.append(f"- 외 {len(subs) - 5}개")
    return "\n".join(lines)[:900]


# ── 보내기 ──────────────────────────────────────────────────
class SendError(Exception):
    pass


class Telegram:
    def __init__(self, env_path: str | Path, timeout_s: float) -> None:
        self.env_path = Path(env_path)
        self.timeout_s = timeout_s
        self._token: str | None = None
        self._chat: str | None = None

    def _load(self) -> None:
        vals = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            k, _, v = line.strip().partition("=")
            if k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                vals[k] = v.strip().strip("'\"")
        if "TELEGRAM_BOT_TOKEN" not in vals or "TELEGRAM_CHAT_ID" not in vals:
            raise SendError(f"{self.env_path.name}에 TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID가 없다")
        self._token, self._chat = vals["TELEGRAM_BOT_TOKEN"], vals["TELEGRAM_CHAT_ID"]

    def _clean(self, s: str) -> str:
        return s.replace(self._token, "«token»") if self._token else s

    async def send(self, msg: str) -> None:
        if self._token is None:
            self._load()
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        last = ""
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as c:
                    r = await c.post(url, data={"chat_id": self._chat, "text": msg, "disable_web_page_preview": "true"})
                if r.status_code == 200:
                    return
                if r.status_code == 429:
                    wait = float((r.json().get("parameters") or {}).get("retry_after", 2))
                    last = f"HTTP 429(retry_after {wait:g}s)"
                    await asyncio.sleep(min(wait, 30))
                    continue
                last = f"HTTP {r.status_code}"
                if r.status_code < 500:
                    break  # 4xx는 다시 해도 같다
            except httpx.HTTPError as e:
                last = self._clean(f"{type(e).__name__}: {e}")[:200]
            await asyncio.sleep(1 + attempt * 2)
        raise SendError(last)


# ── 판정 · 기록 ──────────────────────────────────────────────
class Notifier:
    def __init__(self, engine: AsyncEngine, rules: Rules, telegram: Telegram | Any, masker: Any) -> None:
        self.engine = engine
        self.rules = rules
        self.tg = telegram
        self.mask = masker
        self._send_q: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._worker: asyncio.Task[None] | None = None
        self._batch_pending: dict[int, asyncio.Task[Any]] = {}  # 세션별 묶음 판정 예약(몇 초 모은다)
        self.batch_debounce_s = max(self.rules.settle_s, 0.0) + 1.0

    def start(self) -> None:
        self._worker = asyncio.create_task(self._sender(), name="foreman-notify")

    async def baseline(self) -> int:
        """알림을 켜기 전에 이미 끝난 서브에이전트를 알린 것으로 표시한다 — 첫 묶음에 과거 것이 쏟아지지 않게."""
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "UPDATE subagent_run SET notified_at = UTC_TIMESTAMP(3) WHERE notified_at IS NULL AND status <> 'running'"))
            return res.rowcount

    async def stop(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        if self._worker:
            self._worker.cancel()

    async def drain(self, timeout: float = 30.0) -> None:
        """테스트용 — 판정 작업과 전송 대기열이 빌 때까지."""
        async with asyncio.timeout(timeout):
            while self._tasks or not self._send_q.empty():
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.05)

    def on_subagents_changed(self, session_id: int) -> None:
        """서브에이전트가 끝났다(완료 알림 줄 · SubagentStop hook · meta finished). 세션별로 잠깐 모았다가 묶음을 판정한다.
        task-notification 턴이 닫힐 때만 판정하면, CC가 그 입력으로 모델 턴을 돌리지 않을 때(다음 입력에 합쳐짐) 영영 안 나간다
        — 4단계 실측."""
        if not self.rules.enabled or session_id in self._batch_pending:
            return
        t = asyncio.create_task(self._batch_later(session_id))
        self._batch_pending[session_id] = t
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def _batch_later(self, session_id: int) -> None:
        try:
            await asyncio.sleep(self.batch_debounce_s)
            self._batch_pending.pop(session_id, None)
            async with asyncio.timeout(15):
                async with self.engine.begin() as c:
                    project = (await c.execute(text(
                        "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                        "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :s"), {"s": session_id})).scalar()
                    rule = self.rules.for_project(project)
                    if rule is None:
                        return
                    msg_id = await self._batch(c, rule, session_id, None, None, quiet=True)
            if msg_id:
                await self._send_q.put(msg_id)  # (알림 id, 문장)
        except Exception as e:  # noqa: BLE001
            self._batch_pending.pop(session_id, None)
            log.warning("묶음 판정 실패 session=%s: %s: %s", session_id, type(e).__name__, str(e)[:200])

    def send_direct(self, project: str | None, kind: str, session_id: int | None, msg: str) -> None:
        """규칙 판정 없이 바로 보낸다(승인 대기 등 — 기다리는 사람이 있다). 기록은 kind로 남는다."""
        if not self.rules.enabled:
            return

        async def go() -> None:
            try:
                async with self.engine.begin() as c:
                    nid = await self._record(c, session_id, None, kind, None, "pending", None, msg)
                if nid:
                    await self._send_q.put((nid, msg))
            except Exception as e:  # noqa: BLE001
                log.warning("직접 알림 실패: %s", type(e).__name__)
        t = asyncio.create_task(go())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def on_turn_closed(self, session_id: int, turn_id: int, reason: str, by: str, note: str | None = None) -> None:
        """조립기가 턴을 닫은 직후 부른다(트랜잭션 안일 수 있다 — 여기서는 기다렸다 읽기만 예약한다)."""
        if not self.rules.enabled:
            return
        t = asyncio.create_task(self._decide(session_id, turn_id, reason, by, note))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def _decide(self, session_id: int, turn_id: int, reason: str, by: str, note: str | None) -> None:
        try:
            await asyncio.sleep(self.rules.settle_s)
            async with asyncio.timeout(15):
                await self._decide_inner(session_id, turn_id, reason, by, note)
        except Exception as e:  # noqa: BLE001 — 알림 실패가 조립을 멈추면 안 된다
            log.warning("알림 판정 실패 turn=%s: %s: %s", turn_id, type(e).__name__, str(e)[:200])

    async def _decide_inner(self, session_id: int, turn_id: int, reason: str, by: str, note: str | None) -> None:
        async with self.engine.begin() as c:
            row = (await c.execute(text(
                "SELECT t.origin, t.started_at, t.ended_at, t.duration_ms, t.prompt_text, t.end_reason, p.name "
                "FROM turn t JOIN character_session cs ON cs.id = t.session_id JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id WHERE t.id = :t"), {"t": turn_id})).first()
            if row is None or row[2] is None:
                return  # 롤백됐거나 아직 안 닫힘
            origin, started, ended, dur_ms, prompt, end_reason, project = row
            reason = end_reason or reason
            secs = dur_ms / 1000 if dur_ms else (ended - started).total_seconds()
            rule = self.rules.for_project(project)
            if rule is None:
                await self._record(c, session_id, turn_id, "turn", reason, "skipped", f"project:{project or '미분류'}")
                return
            if origin in rule.batch_origins:
                # 이 턴 자체는 알리지 않는다 — 묶음 판정만
                await self._record(c, session_id, turn_id, "turn", reason, "skipped", f"batch_origin:{origin}")
                queued = await self._batch(c, rule, session_id, turn_id, reason)
                if queued:
                    await self._send_q.put(queued)
                return
            why = None
            if origin not in rule.origins:
                why = f"origin:{origin}"
            elif reason not in rule.end_reasons:
                why = f"end_reason:{reason}"
            elif rule.only_failures and reason not in FAIL_REASONS:
                why = "only_failures"
            elif reason not in FAIL_REASONS and secs < rule.min_turn_s:
                why = f"min_turn_s:{rule.min_turn_s:g}"
            subs = (await c.execute(text(
                "SELECT status, description FROM subagent_run WHERE spawn_turn_id = :t ORDER BY id"), {"t": turn_id})).all()
            if why:
                await self._record(c, session_id, turn_id, "turn", reason, "skipped", why)
                return
            reply = self.mask.text(note) if note else (await c.execute(text(
                "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE turn_id = :t AND type = 'assistant_msg' "
                "AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' ORDER BY id DESC LIMIT 1"),
                {"t": turn_id})).scalar()
            error = (await c.execute(text(
                "SELECT COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')), CAST(JSON_EXTRACT(payload, '$.error') AS CHAR)) "
                "FROM event WHERE turn_id = :t AND type = 'error' ORDER BY id DESC LIMIT 1"), {"t": turn_id})).scalar() \
                if reason == "stop_failure" else None
            msg = compose_turn(rule.prefix or "", reason, origin, secs, prompt, reply, error, [(s, d) for s, d in subs])
            nid = await self._record(c, session_id, turn_id, "turn", reason, "pending", None, msg)
            if nid:
                # 이 알림에 실린 끝난 서브에이전트는 묶음에서 다시 세지 않는다
                await c.execute(text(
                    "UPDATE subagent_run SET notified_at = UTC_TIMESTAMP(3) WHERE spawn_turn_id = :t "
                    "AND status <> 'running' AND notified_at IS NULL"), {"t": turn_id})
        if nid:
            await self._send_q.put((nid, msg))

    async def _batch(self, c: Any, rule: ProjectRule, session_id: int, turn_id: int | None, reason: str | None,
                     quiet: bool = False) -> tuple[int, str] | None:
        """세션의 끝난 · 아직 안 알린 서브에이전트를 한 번에. 보낼 것이 있으면 (알림 id, 문장).
        quiet=True(서브에이전트 쪽에서 부름)면 보류 · 빈 경우를 기록하지 않는다 — 판정이 잦다."""
        busy_turn = (await c.execute(text(
            "SELECT 1 FROM turn WHERE session_id = :s AND ended_at IS NULL AND origin IN ('human', 'meta') LIMIT 1"),
            {"s": session_id})).first()
        if busy_turn:
            # 사람이 연 턴이 진행 중 — 그 턴의 종료 알림이 서브에이전트를 요약해 싣는다
            if not quiet:
                await self._record(c, session_id, turn_id, "batch", reason, "held", "parent_turn_open")
            return None
        running = (await c.execute(text(
            "SELECT COUNT(*) FROM subagent_run WHERE session_id = :s AND status = 'running'"), {"s": session_id})).scalar()
        if running:
            if not quiet:
                await self._record(c, session_id, turn_id, "batch", reason, "held", f"subagents_running:{running}")
            return None
        subs = (await c.execute(text(
            "SELECT id, status, description FROM subagent_run WHERE session_id = :s AND status <> 'running' "
            "AND notified_at IS NULL ORDER BY COALESCE(ended_at, started_at), id FOR UPDATE"), {"s": session_id})).all()
        if not subs:
            if not quiet:
                await self._record(c, session_id, turn_id, "batch", reason, "skipped", "batch_empty")
            return None
        msg = compose_batch(rule.prefix or "", [(s, d) for _, s, d in subs])
        nid = await self._record(c, session_id, turn_id, "batch", reason, "pending", None, msg)
        if not nid:
            return None
        await c.execute(text("UPDATE subagent_run SET notified_at = UTC_TIMESTAMP(3) WHERE id IN :ids").bindparams(
            _expanding("ids")), {"ids": [i for i, _, _ in subs]})
        return nid, msg

    async def _record(self, c: Any, session_id: int | None, turn_id: int | None, kind: str, reason: str | None,
                      decision: str, rule: str | None, msg: str | None = None) -> int | None:
        """한 턴 · 종류에 한 번. 이미 있으면 None(재시작 · 신호 중복)."""
        res = await c.execute(text(
            "INSERT IGNORE INTO notification (session_id, turn_id, kind, end_reason, decision, rule, text) "
            "VALUES (:s, :t, :k, :r, :d, :rule, :msg)"),
            {"s": session_id, "t": turn_id, "k": kind, "r": reason, "d": decision, "rule": rule, "msg": msg})
        if not res.rowcount:
            return None
        if decision != "pending":
            log.info("알림 %s turn=%s %s %s", decision, turn_id, kind, rule or "")
        return res.lastrowid

    async def _sender(self) -> None:
        while True:
            nid, msg = await self._send_q.get()  # type: ignore[misc]
            try:
                await self.tg.send(msg)
                decision, err = "sent", None
            except Exception as e:  # noqa: BLE001
                decision, err = "failed", str(e)[:255]
                log.warning("알림 전송 실패 id=%d: %s", nid, err)
            try:
                async with self.engine.begin() as c:
                    await c.execute(text(
                        "UPDATE notification SET decision = :d, error = :e, sent_at = IF(:d = 'sent', UTC_TIMESTAMP(3), NULL) "
                        "WHERE id = :id"), {"d": decision, "e": err, "id": nid})
            except Exception as e:  # noqa: BLE001
                log.warning("알림 기록 실패 id=%d: %s", nid, type(e).__name__)
            await asyncio.sleep(self.rules.min_interval_s)


def _expanding(name: str):  # noqa: ANN202
    from sqlalchemy import bindparam
    return bindparam(name, expanding=True)


def default_telegram(rules: Rules) -> Telegram:
    p = Path(rules.env_file)
    return Telegram(p if p.is_absolute() else REPO / p, rules.timeout_s)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
