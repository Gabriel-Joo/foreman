"""권한 거부가 오래 풀리지 않으면 알린다(11-09 사용자 — "권한 거부 30분 알림").

CC auto mode 자체 검사가 막은 것(이벤트 error_preview "Permission for this action was denied")은 FOREMAN 승인 카드로
오지 않는다. 화면(칩 "권한 거부" · 방 배너 "✋ 권한 거부 N")에는 뜨지만, 화면을 안 보면 그 세션은 사람이 다시 입력할 때까지
멈춰 있다 — 조용한 멈춤. 판단은 화면과 같은 `human_needs`(마지막 사람 입력 뒤의 거부)를 쓴다.

- 거부 뒤 AFTER(30분) 지났고, 그 세션이 살아 있고 지금 일하지 않으면(CC status ≠ busy) 텔레그램 한 번
  — 거부 뒤 CC가 다른 방법으로 이어서 일하는 중이면 막힌 것이 아니다
- 같은 거부(세션 · 거부 시각)는 notification.rule 키로 한 번만(브리지를 다시 띄워도)
- "답 기다림"(글로 묻고 끝남)은 알리지 않는다 — 턴 끝 알림이 이미 간다(그 글이 곧 물음)

11-13 API 오류로 멈춘 세션도 같은 틀로(README 「API 오류로 멈춘 세션이 화면에서 일하는 것처럼 보인다」): 턴이 끝날 때 「⚠ API 오류로
멈춤」이 한 번 가고, 그 뒤 API_AFTER(30분) 지나도 새 턴이 없으면(대시보드 `api_stop`과 같은 `api_stops`) 한 번 더.
키 `apistop:<세션>:<턴>` — 브리지를 다시 띄워도 한 번. 끝난 세션(살아 있지 않음) · 멈춰 둔 세션(T) · 일하는 세션은 뺀다(위와 같은 거름).
30분: 사람이 첫 알림을 보고 손댈 틈(11-12 코더 311은 첫 턴 17초 만에 멈췄는데 화면에서는 쉬는 코더와 같았다 — 첫 알림을 놓치면
남는 길이 없었다). 권한 거부와 같은 값이라 알림 쪽 리듬이 하나다
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text

from bridge.api.dashboard import api_stops, human_needs
from bridge.inject import _status
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.human_wait")

AFTER = timedelta(minutes=30)
API_AFTER = timedelta(minutes=30)     # API 오류로 멈춘 뒤 다시 알리기까지(첫 알림은 턴 끝 알림 「⚠ API 오류로 멈춤」)


def _utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


class DeniedWatch:
    def __init__(self, engine: Any, notifier: Any, sessions_dir: Any, every_s: float = 60.0) -> None:
        self.engine, self.notifier, self.dir, self.every = engine, notifier, sessions_dir, every_s
        self.live: Any = live_sessions          # 시험이 바꿔 끼운다
        self.status: Any = _status

    async def check(self, now: datetime | None = None) -> list[str]:
        """돌려주는 값: 이번에 보낸 rule 키들."""
        now = now or datetime.now(UTC).replace(tzinfo=None)
        if self.notifier is None:
            return []
        live = await asyncio.to_thread(self.live, self.dir)
        if not live:
            return []
        idle = {cc for cc, ls in live.items() if ls.state != "T" and self.status(self.dir, ls.pid) != "busy"}
        if not idle:
            return []
        sent: list[str] = []
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), p.name FROM character_session cs "
                "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.type = 'agent' AND cs.hidden_at IS NULL AND cs.cc_session_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)), {"ids": sorted(idle)})).all()
            if not rows:
                return []
            meta = {r[0]: r for r in rows}
            needs = await human_needs(c, "(" + ",".join(str(int(i)) for i in meta) + ")")
            for sid, n in needs.items():
                d = n.get("denied")
                if not d or not d.get("at"):
                    continue
                at = _utc(d["at"])
                if now - at < AFTER:
                    continue
                key = f"denied:{sid}:{at:%Y%m%d%H%M%S}"
                if (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                    continue
                _, _, title, project = meta[sid]
                rule = self.notifier.rules.for_project(project) if project else None
                mins = int((now - at).total_seconds() // 60)
                msg = "\n".join([
                    f"{(rule and rule.prefix) or '[' + (project or 'FOREMAN') + ']'} ✋ 권한 거부 {mins}분째 — "
                    f"「{title or sid}」 세션이 CC 자체 검사에 막힌 뒤 멈춰 있습니다",
                    f"▶ 막힌 도구 {d.get('tool') or '?'}" + (f" · 이유 [{d['reason']}]" if d.get("reason") else "")
                    + (" (서브에이전트)" if d.get("subagent") else ""),
                    "FOREMAN 승인 카드로 오지 않습니다. 그 세션에 허용하거나 다른 방법을 지시해 주세요(패널 입력 칸이나 터미널)"])
                log.warning("권한 거부 알림: 세션 %s %d분", sid, mins)
                self.notifier.send_direct(project, "denied", sid, msg, rule=key)
                sent.append(key)
            for sid, a in (await api_stops(c, "(" + ",".join(str(int(i)) for i in meta) + ")")).items():
                if not a.get("at"):
                    continue
                at = _utc(a["at"])
                if now - at < API_AFTER:
                    continue
                key = f"apistop:{sid}:{a['turn_id']}"
                if (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                    continue
                _, _, title, project = meta[sid]
                rule = self.notifier.rules.for_project(project) if project else None
                mins = int((now - at).total_seconds() // 60)
                msg = "\n".join([
                    f"{(rule and rule.prefix) or '[' + (project or 'FOREMAN') + ']'} ⚠ API 오류로 멈춤 {mins}분째 — "
                    f"「{title or sid}」 세션이 API 오류로 턴을 끝낸 뒤 새 입력이 없습니다",
                    f"▶ {a.get('line') or a.get('label') or 'API 오류'}",
                    "화면에서는 쉬는 세션과 비슷해 보입니다. 그 세션에 다시 보내거나 다른 지시를 해 주세요(패널 입력 칸이나 터미널)"])
                log.warning("API 오류 멈춤 알림: 세션 %s %d분", sid, mins)
                self.notifier.send_direct(project, "apistop", sid, msg, rule=key)
                sent.append(key)
        return sent

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.every)
            try:
                await self.check()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 감시를 멈추지 않는다
                log.warning("권한 거부 확인 실패: %s: %s", type(e).__name__, str(e)[:200])
