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


def load_rules(path: str | Path) -> CompactRules:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("compact") or {}
    except OSError:
        raw = {}
    r = CompactRules()
    return CompactRules(int(raw.get("due_at", r.due_at)), int(raw.get("late_at", r.late_at)),
                        tuple(int(x) for x in raw.get("notify_at", r.notify_at)), int(raw.get("short_turns", r.short_turns)))


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

    def __init__(self, engine: Any, notifier: Any, notify_rules: Any, path: str | Path) -> None:
        self.engine, self.notifier, self.notify_rules = engine, notifier, notify_rules
        self.rules = load_rules(path)

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
