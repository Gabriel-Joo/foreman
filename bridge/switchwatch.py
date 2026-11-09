"""작업 전환 권유(11-09) — 쌓인 대화가 어느 정도 찬 세션에서 사람이 "다음 일"로 넘어가는 말을 하고,
직전에 일이 끝난 흔적(커밋 · 긴 쉼)이 겹치면 [새 세션으로 옮기기]를 권한다.

왜 이 셋을 겹치나 — 하나씩은 약하다.
- 전환 말투 한 줄만으로는 같은 일의 다음 단계("이제 테스트 돌려줘")도 잡는다.
- 커밋 · 쉼만으로는 같은 주제로 이어 가는 경우가 많다.
- 둘이 같이 있고 쌓인 대화가 40% 이상이면 "새 일 + 이미 무겁다"라 옮길 이유가 분명하다.
오탐 비용은 띠(또는 텔레그램) 한 번이다. 막지 않고 알리기만 한다(겹침 알림과 같은 태도, bridge/overlap.py).
clear가 아니라 새 세션으로 옮기기를 권한다 — 대화에서만 정한 결정은 문서로 옮긴 뒤 넘겨야 한다
(압축 손실 점검: log/*_compaction_loss_20261105.md, docs/11_handoff_v2.md 1장)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

log = logging.getLogger("foreman.switch")

# 사람이 다른 일로 넘어간다는 말 — 요청 글 앞머리(첫 160자)에서만 본다. 긴 지시서 안의 우연한 낱말을 피하려는 것
_SWITCH = re.compile(
    r"(다음\s*(일|작업|건|것)|다른\s*(일|건|작업|얘기|이야기)|새로운\s*(일|작업)|새\s*작업|"
    r"그건\s*(됐|끝)|그건\s*이만|이번엔|이번에는|별개로|이제\s*(다른|그만|다음)|"
    r"넘어가|넘어가자|바꿔서|이어서\s*다른|next\s+(task|thing)|switch(ing)?\s+to|moving\s+on)", re.I)
HEAD_CHARS = 160
COMMIT_WINDOW = timedelta(minutes=30)    # 이 프롬프트 직전 이만큼 안의 커밋
IDLE_GAP = timedelta(minutes=20)         # 직전 턴이 끝난 뒤 이만큼 쉬었다가 온 프롬프트


@dataclass
class SwitchSignal:
    turn_id: int
    prompt_head: str
    committed: bool        # 직전 30분 안에 이 세션 커밋
    idle: bool             # 직전 턴 끝 → 이 프롬프트 사이 20분 이상
    phrase: str            # 걸린 전환 말


def switch_phrase(prompt: str | None) -> str | None:
    """요청 글 앞머리에서 전환 말을 찾는다. 없으면 None."""
    m = _SWITCH.search((prompt or "")[:HEAD_CHARS])
    return m.group(0) if m else None


def should_suggest(pct: int | None, min_pct: int, phrase: str | None, committed: bool, idle: bool) -> bool:
    """전환 말 + (커밋 또는 쉼) + 쌓인 대화가 min_pct% 이상. 창을 모르는 모델(pct None)은 권하지 않는다."""
    return bool(phrase) and (committed or idle) and pct is not None and pct >= min_pct


async def latest_signal(c: Any, session_id: int) -> SwitchSignal | None:
    """이 세션의 가장 최근 사람 턴에서 전환 신호를 모은다. 사람 턴이 없거나 전환 말이 없으면 None."""
    cur = (await c.execute(text(
        "SELECT id, prompt_text, started_at FROM turn WHERE session_id = :s AND origin = 'human' "
        "ORDER BY started_at DESC LIMIT 1"), {"s": session_id})).first()
    if not cur or not cur[1]:
        return None
    phrase = switch_phrase(cur[1])
    if not phrase:
        return None
    started: datetime = cur[2]
    prev_end = (await c.execute(text(
        "SELECT MAX(ended_at) FROM turn WHERE session_id = :s AND started_at < :t"), {"s": session_id, "t": started})).scalar()
    committed = bool((await c.execute(text(
        "SELECT 1 FROM git_commit WHERE session_id = :s AND committed_at >= :a AND committed_at <= :b LIMIT 1"),
        {"s": session_id, "a": started - COMMIT_WINDOW, "b": started})).first())
    idle = bool(prev_end and started - prev_end >= IDLE_GAP)
    return SwitchSignal(int(cur[0]), (cur[1] or "")[:60].replace("\n", " "), committed, idle, phrase)


def switch_message(prefix: str, title: str, pct: int, sig: SwitchSignal) -> str:
    why = "방금 커밋했고" if sig.committed else "한참 쉬었다 왔고"
    if sig.committed and sig.idle:
        why = "방금 커밋했고 한참 쉬었다 왔고"
    return (f"{prefix} 세션 「{title}」 다른 일로 넘어가시는 것 같습니다 — {why} 지금까지 쌓인 대화가 {pct}%입니다. "
            f"새 일은 새 세션에서 시작하면 응답이 빠르고 쌉니다.\n패널에서 [새 세션으로 옮기기]를 누르세요. "
            f"(옮기기 전에 대화에서만 정한 결정은 문서로 옮겨 둡니다)")
