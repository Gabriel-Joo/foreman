"""압축 알림(11-05, docs/11_handoff_v2.md 3장) — 세션이 압축을 거듭하면 새 세션으로 넘어갈 때라고 알린다.

근거(압축 손실 점검 두 번 — log/runshoes_compaction_loss_20261105.md · log/foreman_compaction_loss_20261105.md):
사용자 지시 · 결정의 약 63%가 사라지거나 약해졌고, 가장 많이 빠지는 때는 말한 뒤 **두 번째 압축**이었다.
그래서 2번째 압축 직후 "넘어갈 때"(due), 4번째부터 "늦었음"(late). 트랜스크립트 크기는 쓰지 않는다(대부분 도구 출력이라
횟수와 같이 늘 뿐). 압축 사이 사람 턴이 짧게 두 번 이어지면 "맥락이 금방 찬다"를 덧붙인다(보조).
압축 직후에 알린다 — 맥락이 1~2만 토큰으로 가벼워 인계 요청을 넣기 좋은 때다."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge.model_choice import load_windows, window_of

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
    # 맥락 비율(11-09) — 마지막 응답 맥락 ÷ 모델 창(models.toml [windows]). context_at과 먼저 닿는 쪽이 이긴다.
    # 창이 작은 모델은 300k가 도달 불가라 이게 없으면 띠가 영영 안 뜬다(notify.toml에 근거)
    context_pct: tuple[int, ...] = (50, 75)
    switch_min_pct: int = 40   # 작업 전환 권유는 이 비율 이상 찬 세션에만
    windows: dict[str, int] = field(default_factory=dict)   # family → 창(토큰). models.toml [windows]에서 읽는다


def load_rules(path: str | Path) -> CompactRules:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("compact") or {}
    except OSError:
        raw = {}
    r = CompactRules()
    # 창 크기는 notify.toml과 같은 config 폴더의 models.toml에서(없으면 비어서 %를 안 쓴다)
    windows = load_windows(Path(path).parent / "models.toml")
    return CompactRules(int(raw.get("due_at", r.due_at)), int(raw.get("late_at", r.late_at)),
                        tuple(int(x) for x in raw.get("notify_at", r.notify_at)), int(raw.get("short_turns", r.short_turns)),
                        tuple(sorted(int(x) for x in raw.get("context_at", r.context_at))),
                        tuple(sorted(int(x) for x in raw.get("context_pct", r.context_pct))),
                        int(raw.get("switch_min_pct", r.switch_min_pct)), windows)


def _token_level(tokens: int, r: CompactRules) -> str | None:
    if not r.context_at or tokens < r.context_at[0]:
        return None
    return "late" if len(r.context_at) > 1 and tokens >= r.context_at[-1] else "due"


def _pct_level(tokens: int, window: int | None, r: CompactRules) -> str | None:
    if not window or not r.context_pct:
        return None
    p = tokens * 100 / window
    if p < r.context_pct[0]:
        return None
    return "late" if len(r.context_pct) > 1 and p >= r.context_pct[-1] else "due"


def context_pct(tokens: int, window: int | None) -> int | None:
    """맥락 ÷ 창 → 0~100 정수(창을 모르면 None). 추정 창을 넘어도 100에서 멈춘다."""
    return None if not window else min(100, int(tokens * 100 / window + 0.5))


def context_level(tokens: int, r: CompactRules, window: int | None = None) -> str | None:
    """마지막 응답 맥락 → 토큰 문턱(context_at)과 비율 문턱(context_pct, 창을 알 때) 중 더 높은 단계.
    첫 문턱 이상 due, 마지막 문턱 이상 late."""
    a, b = _token_level(tokens, r), _pct_level(tokens, window, r)
    return "late" if "late" in (a, b) else "due" if "due" in (a, b) else None


def _rank(key: str, r: CompactRules) -> int:
    """보낸 알림 rule("ctx:<토큰>" · "pct:<비율>") → 단계 1(due) · 2(late), 모르면 0."""
    kind, _, num = (key or "").partition(":")
    if not num.isdigit():
        return 0
    n, last = int(num), None
    if kind == "ctx":
        last = r.context_at
    elif kind == "pct":
        last = r.context_pct
    if not last:
        return 0
    return 2 if len(last) > 1 and n >= last[-1] else 1


async def context_status(c: Any, ids: list[int], r: CompactRules) -> dict[int, dict[str, Any]]:
    """세션별 마지막 본 대화 응답(서브에이전트 아님)의 맥락 = 입력 + 캐시 읽기 + 캐시 쓰기.
    {tokens, model, at, level, window, pct, window_over} — window · pct는 창을 아는 모델만(모르면 None),
    window_over는 맥락이 설정한 창을 넘은 것(설정이 틀렸다는 신호)."""
    if not ids:
        return {}
    in_ids = "(" + ",".join(str(int(i)) for i in ids) + ")"
    rows = (await c.execute(text(
        f"SELECT t.session_id, m.model, m.token_input + m.token_cache_read + m.token_cache_creation, m.created_at "
        f"FROM message m JOIN turn t ON t.id = m.turn_id JOIN ("
        f"  SELECT t2.session_id, MAX(m2.created_at) mx FROM message m2 JOIN turn t2 ON t2.id = m2.turn_id "
        f"  WHERE t2.session_id IN {in_ids} AND m2.subagent_id IS NULL AND m2.model <> '<synthetic>' GROUP BY t2.session_id"
        f") x ON x.session_id = t.session_id AND x.mx = m.created_at WHERE m.subagent_id IS NULL"))).all()
    out: dict[int, dict[str, Any]] = {}
    for sid, model, tok, at in rows:
        n = int(tok or 0)
        w = window_of(r.windows, model)
        out[sid] = {"tokens": n, "model": model, "at": at.isoformat() + "Z", "level": context_level(n, r, w),
                    "window": w, "pct": context_pct(n, w), "window_over": bool(w and n > w)}
    return out


def context_rule(tokens: int, sent: set[str], r: CompactRules, window: int | None = None) -> str | None:
    """보낼 맥락 알림 rule — 단계(due · late)가 올랐을 때만, 세션마다 단계 한 번.
    토큰 문턱이 그 단계를 만들었으면 "ctx:<넘은 가장 높은 문턱>", 비율이 만들었으면 "pct:<그 단계 문턱>".
    같은 단계나 더 높은 단계를 이미 보냈으면 None(압축으로 줄었다 다시 커져도 다시 보내지 않는다)."""
    lvl = context_level(tokens, r, window)
    if lvl is None:
        return None
    rank = 2 if lvl == "late" else 1
    if any(_rank(s, r) >= rank for s in sent if s):
        return None
    if _token_level(tokens, r) == lvl:
        return f"ctx:{max(x for x in r.context_at if x <= tokens)}"
    return f"pct:{r.context_pct[-1] if rank == 2 and len(r.context_pct) > 1 else r.context_pct[0]}"


def window_over_message(prefix: str, title: str, model: str, tokens: int, window: int) -> str:
    """설정한 창 크기를 넘는 맥락이 보였다 — config/models.toml [windows]의 추정이 틀렸다는 신호(조용한 고장 방지)."""
    return (f"{prefix} 세션 「{title}」의 쌓인 대화가 {tokens / 1000:.0f}k로, 설정한 {model} 창 {window / 1000:.0f}k보다 큽니다. "
            f"창 크기 값이 틀렸습니다 — config/models.toml [windows]를 고쳐야 쌓인 대화 %가 맞습니다.")


def context_message(prefix: str, title: str, tokens: int, lvl: str | None, per_reply_usd: float | None,
                    pct: int | None = None) -> str:
    # 11-09 화면 말 통일 — "인계" → "새 세션으로 옮기기", 맥락 → "지금까지 쌓인 대화"
    cost = f" · 응답당 약 ${per_reply_usd:.2f}" if per_reply_usd else ""
    body = ("새 세션으로 옮길 때입니다." if lvl == "due" else "많이 늦었습니다 — 응답 하나하나가 비쌉니다.")
    share = f"({pct}%)" if pct is not None else ""
    return (f"{prefix} 세션 「{title}」 지금까지 쌓인 대화 {tokens / 1000:.0f}k{share}{cost}. {body} 답할 때마다 이걸 전부 다시 읽습니다"
            f"(한도 사용의 대부분). 새 세션으로 옮기면 수십k에서 다시 시작합니다.\n패널에서 [새 세션으로 옮기기]를 누르세요.")


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
    return f"{head} {body}{tail}\n패널에서 [새 세션으로 옮기기]를 누르세요."


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
