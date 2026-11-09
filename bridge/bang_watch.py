"""'!' 명령이 실행되지 않고 글로 들어간 것을 알린다(11-09 사용자).

CC는 맨 앞 '!'를 bash 모드로 실행하고 트랜스크립트에 `<bash-input>명령</bash-input>`으로 남긴다(11-09 실측). 사람 글이
공백 · 줄바꿈 뒤 '!'로 시작하면 실행되지 않고 모델에게 글로 갔다 — 11-07 ~ 11-09에 7번 그랬고 아무도 몰랐다
(패널이 앞에 공백을 붙였다 — 지금은 `inject.bang_check`로 고침. 그래도 터미널에서 앞에 공백을 친 것 · 다른 길은 남는다).
막지 않는다(이미 들어갔다) — 알리기만: 텔레그램 한 번(세션 · 시각마다).
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import text

log = logging.getLogger("foreman.bang_watch")

_BANG = re.compile(r"^\s*!(?=\S)")


def bang_text(prompt: str | None) -> str | None:
    """글로 들어간 '!' 명령의 첫 줄(앞 200자) — 아니면 None."""
    if not prompt or not _BANG.match(prompt):
        return None
    return prompt.strip().splitlines()[0][:200]


class BangWatch:
    def __init__(self, engine: Any, notifier: Any) -> None:
        self.engine, self.notifier = engine, notifier
        self._tasks: set[asyncio.Task[None]] = set()

    def on_prompt(self, session_id: int, cc_session_id: str, prompt: str, ts: datetime) -> None:
        cmd = bang_text(prompt)
        if cmd is None or self.notifier is None:
            return
        t = asyncio.get_running_loop().create_task(self.alert(session_id, cmd, ts))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def alert(self, session_id: int, cmd: str, ts: datetime) -> str | None:
        key = f"bang:{session_id}:{ts:%Y%m%d%H%M%S}"
        try:
            async with self.engine.connect() as c:
                if (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                    return None
                r = (await c.execute(text(
                    "SELECT COALESCE(cs.custom_title, cs.title), p.name FROM character_session cs "
                    "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                    "WHERE cs.id = :s"), {"s": session_id})).first()
        except Exception as e:  # noqa: BLE001 — 알림이 적재를 막지 않는다
            log.warning("'!' 알림 준비 실패: %s", type(e).__name__)
            return None
        title, project = (r[0], r[1]) if r else (None, None)
        rule = self.notifier.rules.for_project(project) if project else None
        msg = "\n".join([
            f"{(rule and rule.prefix) or '[' + (project or 'FOREMAN') + ']'} ⚠ '!' 명령이 실행되지 않고 글로 들어갔습니다 — 「{title or session_id}」 세션",
            f"▶ {cmd}",
            "셸에서 돌지 않았고 모델이 글로 받았습니다. 돌리려면 터미널에서 맨 앞에 '!'를 치거나(앞에 공백 없이), 그 세션에 '… 실행해 줘'로 맡깁니다"])
        log.warning("'!' 글로 들어감: 세션 %s %s", session_id, cmd[:80])
        self.notifier.send_direct(project, "bang", session_id, msg, rule=key)
        return key
