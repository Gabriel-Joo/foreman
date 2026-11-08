"""압축 알림(11-05, docs/11_handoff_v2.md 3장) — 세션이 압축을 거듭하면 새 세션으로 넘어갈 때라고 알린다.

근거(압축 손실 점검 두 번 — log/runshoes_compaction_loss_20261105.md · log/foreman_compaction_loss_20261105.md):
사용자 지시 · 결정의 약 63%가 사라지거나 약해졌고, 가장 많이 빠지는 때는 말한 뒤 **두 번째 압축**이었다.
그래서 2번째 압축 직후 "넘어갈 때"(due), 4번째부터 "늦었음"(late). 트랜스크립트 크기는 쓰지 않는다(대부분 도구 출력이라
횟수와 같이 늘 뿐). 압축 사이 사람 턴이 짧게 두 번 이어지면 "맥락이 금방 찬다"를 덧붙인다(보조).
압축 직후에 알린다 — 맥락이 1~2만 토큰으로 가벼워 인계 요청을 넣기 좋은 때다."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text

log = logging.getLogger("foreman.compact")


@dataclass
class CompactRules:
    due_at: int = 2            # 이 횟수부터 "넘어갈 때"
    late_at: int = 4           # 이 횟수부터 "늦었음"
    notify_at: tuple[int, ...] = (2, 4)   # 이 횟수의 압축 직후 텔레그램
    short_turns: int = 3       # 압축 사이 사람 턴이 이 이하면 "짧은 간격"
    # 맥락 크기(11-08, docs/15 — 사용자 승인 300k · 500k). 마지막 응답 맥락이 이만큼이면 "넘어갈 때" · "늦었음".
    # 압축은 맥락이 꽉 찬 뒤에야 일어난다 — 11-08 살아 있는 세션들이 압축 0번으로 300~440k에서 돌며 응답마다 그만큼 다시 읽었다
    context_at: tuple[int, ...] = (300_000, 500_000)


def load_rules(path: str | Path) -> CompactRules:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("compact") or {}
    except OSError:
        raw = {}
    r = CompactRules()
    return CompactRules(int(raw.get("due_at", r.due_at)), int(raw.get("late_at", r.late_at)),
                        tuple(int(x) for x in raw.get("notify_at", r.notify_at)), int(raw.get("short_turns", r.short_turns)),
                        tuple(sorted(int(x) for x in raw.get("context_at", r.context_at))))


def context_level(tokens: int, r: CompactRules) -> str | None:
    """마지막 응답 맥락 → 첫 문턱 이상 due, 마지막 문턱 이상 late."""
    if not r.context_at or tokens < r.context_at[0]:
        return None
    return "late" if len(r.context_at) > 1 and tokens >= r.context_at[-1] else "due"


async def context_status(c: Any, ids: list[int], r: CompactRules) -> dict[int, dict[str, Any]]:
    """세션별 마지막 본 대화 응답(서브에이전트 아님)의 맥락 = 입력 + 캐시 읽기 + 캐시 쓰기. {tokens, model, at, level}"""
    if not ids:
        return {}
    in_ids = "(" + ",".join(str(int(i)) for i in ids) + ")"
    rows = (await c.execute(text(
        f"SELECT t.session_id, m.model, m.token_input + m.token_cache_read + m.token_cache_creation, m.created_at "
        f"FROM message m JOIN turn t ON t.id = m.turn_id JOIN ("
        f"  SELECT t2.session_id, MAX(m2.created_at) mx FROM message m2 JOIN turn t2 ON t2.id = m2.turn_id "
        f"  WHERE t2.session_id IN {in_ids} AND m2.subagent_id IS NULL AND m2.model <> '<synthetic>' GROUP BY t2.session_id"
        f") x ON x.session_id = t.session_id AND x.mx = m.created_at WHERE m.subagent_id IS NULL"))).all()
    return {sid: {"tokens": int(tok or 0), "model": model, "at": at.isoformat() + "Z", "level": context_level(int(tok or 0), r)}
            for sid, model, tok, at in rows}


def context_rule(tokens: int, sent: set[str], r: CompactRules) -> str | None:
    """보낼 맥락 알림 rule("ctx:<문턱>") — 넘은 가장 높은 문턱, 그것이나 더 높은 것을 보냈으면 None(세션마다 문턱 한 번)."""
    crossed = [x for x in r.context_at if x <= tokens]
    if not crossed:
        return None
    thr = max(crossed)
    done = {int(s[4:]) for s in sent if s and s.startswith("ctx:") and s[4:].isdigit()}
    return None if any(d >= thr for d in done) else f"ctx:{thr}"


def context_message(prefix: str, title: str, tokens: int, lvl: str | None, per_reply_usd: float | None) -> str:
    cost = f" 응답 하나에 맥락 읽기만 약 ${per_reply_usd:.2f}입니다." if per_reply_usd else ""
    body = ("— 넘어갈 때입니다." if lvl == "due" else "— 늦었습니다. 응답 하나하나가 비쌉니다.")
    return (f"{prefix} 세션 「{title}」 맥락 {tokens / 1000:.0f}k {body}{cost} 응답마다 이 맥락 전체를 다시 읽습니다"
            f"(한도 사용의 대부분). 인계해 새로 시작하면 수십k에서 다시 시작합니다.\n패널에서 [인계 요약 받기]로 넘어갈 수 있습니다.")


def level(count: int, r: CompactRules) -> str | None:
    return "late" if count >= r.late_at else "due" if count >= r.due_at else None


def short_streak(gaps: list[int], r: CompactRules) -> bool:
    """마지막 두 간격(압축 사이 사람 턴 수)이 모두 짧은가."""
    return len(gaps) >= 2 and all(g <= r.short_turns for g in gaps[-2:])


async def status(c: Any, ids: list[int], r: CompactRules) -> dict[int, dict[str, Any]]:
    """세션별 {count, last_ts, level, short}. 압축이 없는 세션은 빠진다."""
    if not ids:
        return {}
    in_ids = "(" + ",".join(str(int(i)) for i in ids) + ")"
    rows = (await c.execute(text(
        f"SELECT session_id, ts FROM event WHERE type = 'compact' AND session_id IN {in_ids} ORDER BY session_id, ts"))).all()
    by: dict[int, list[Any]] = {}
    for sid, ts in rows:
        by.setdefault(sid, []).append(ts)
    out: dict[int, dict[str, Any]] = {}
    for sid, tss in by.items():
        gaps: list[int] = []
        if len(tss) >= 3:          # 짧은 간격은 마지막 두 간격만 본다
            for a, b in zip(tss[-3:], tss[-2:]):
                gaps.append(int((await c.execute(text(
                    "SELECT COUNT(*) FROM turn WHERE session_id = :s AND origin = 'human' AND started_at >= :a AND started_at < :b"),
                    {"s": sid, "a": a, "b": b})).scalar() or 0))
        out[sid] = {"count": len(tss), "last_ts": tss[-1].isoformat() + "Z", "level": level(len(tss), r),
                    "short": short_streak(gaps, r), "gaps": gaps}
    return out


def message(prefix: str, title: str, count: int, lvl: str | None, short: bool) -> str:
    head = f"{prefix} 세션 「{title}」 압축 {count}번"
    body = ("— 넘어갈 때입니다. 처음에 정한 것이 빠지기 시작합니다." if lvl == "due"
            else "— 늦었습니다. 앞에서 정한 결정 · 금지가 이미 많이 빠졌을 수 있습니다.")
    tail = " 압축 간격도 짧습니다(맥락이 금방 찹니다)." if short else ""
    return f"{head} {body}{tail}\n패널에서 [인계 요약 받기]로 넘어갈 수 있습니다."


class CompactWatch:
    """조립기의 압축 이벤트(실시간 적재 때만)를 받아 정한 횟수면 텔레그램을 보낸다."""

    def __init__(self, engine: Any, notifier: Any, notify_rules: Any, path: str | Path, price: Any = None) -> None:
        self.engine, self.notifier, self.notify_rules = engine, notifier, notify_rules
        self.rules = load_rules(path)
        self.price = price            # (model, 맥락 토큰) → 응답 하나의 맥락 읽기 달러(사용량 설정). 없으면 금액을 빼고 알린다
        self._tasks: set[Any] = set()

    def on_turn_closed(self, session_id: int, *_: Any, **__: Any) -> None:
        """조립기가 턴을 닫은 직후(트랜잭션 안일 수 있다) — 잠시 뒤 맥락 크기를 본다."""
        import asyncio

        async def go() -> None:
            await asyncio.sleep(1.0)
            await self.check_context(session_id)
        t = asyncio.get_running_loop().create_task(go())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def check_context(self, session_id: int) -> str | None:
        """처음 넘은 맥락 문턱이면 텔레그램 한 번(세션 · 문턱마다, notification kind 'context' · rule 'ctx:<문턱>'). 보낸 rule."""
        try:
            async with self.engine.connect() as c:
                st = (await context_status(c, [session_id], self.rules)).get(session_id)
                if not st or not st["level"]:
                    return None
                sent = {r[0] for r in (await c.execute(text(
                    "SELECT rule FROM notification WHERE kind = 'context' AND session_id = :s"), {"s": session_id})).all()}
                row = (await c.execute(text(
                    "SELECT p.name, COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)), cs.hidden_at "
                    "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                    "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :i"), {"i": session_id})).first()
            rule_key = context_rule(st["tokens"], sent, self.rules)
            if rule_key is None:
                return None
            if not row or row[2] is not None:
                return None
            rule = self.notify_rules.for_project(row[0]) if self.notify_rules else None
            if rule is None or self.notifier is None:
                return None
            usd = None
            if self.price:
                try:
                    usd = self.price(st["model"], st["tokens"])
                except Exception:  # noqa: BLE001 — 금액 없이 보낸다
                    usd = None
            self.notifier.send_direct(row[0], "context", session_id,
                                      context_message(rule.prefix, row[1] or str(session_id), st["tokens"], st["level"], usd),
                                      rule=rule_key)
            log.info("맥락 알림 session=%d %dk", session_id, st["tokens"] // 1000)
            return rule_key
        except Exception as e:  # noqa: BLE001 — 알림 실패가 적재를 막으면 안 된다
            log.warning("맥락 알림 실패 session=%s: %s", session_id, type(e).__name__)
            return None

    async def on_compact(self, session_id: int) -> None:
        try:
            async with self.engine.connect() as c:
                st = (await status(c, [session_id], self.rules)).get(session_id)
                row = (await c.execute(text(
                    "SELECT p.name, COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)), cs.hidden_at "
                    "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                    "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :i"), {"i": session_id})).first()
            if not st or not row or row[2] is not None or st["count"] not in self.rules.notify_at:
                return
            rule = self.notify_rules.for_project(row[0]) if self.notify_rules else None
            if rule is None or self.notifier is None:   # 접두어 없는 프로젝트(미분류)는 보내지 않는다 — 알림 규칙과 같다
                return
            self.notifier.send_direct(row[0], "compact", session_id,
                                      message(rule.prefix, row[1] or str(session_id), st["count"], st["level"], st["short"]))
            log.info("압축 알림 session=%d count=%d", session_id, st["count"])
        except Exception as e:  # noqa: BLE001 — 알림 실패가 적재를 막으면 안 된다
            log.warning("압축 알림 실패 session=%s: %s", session_id, type(e).__name__)
