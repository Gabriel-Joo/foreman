"""세션 상태 감시(6단계) — 프로세스 정지(T) · 사라짐, CC가 적는 status(busy · idle · shell)는 이벤트로 오지 않는다.
2초마다 ~/.claude/sessions/*.json(.key는 열지 않는다)과 /proc을 보고, 바뀐 것만 WS로 낸다.
"""

import asyncio
import logging
from typing import Any

from bridge.inject import _status
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.session_state")


class SessionStateWatcher:
    def __init__(self, sessions_dir: Any, publish: Any, interval_s: float = 2.0) -> None:
        self.dir = sessions_dir
        self.publish = publish
        self.interval = interval_s
        self.prev: dict[str, tuple[int, str, str | None]] = {}
        self.on_change: Any = None     # 바뀌면 부른다(대시보드 스냅샷 캐시 비우기)

    def tick(self) -> list[dict[str, Any]]:
        now: dict[str, tuple[int, str, str | None]] = {}
        for sid, ls in live_sessions(self.dir).items():
            now[sid] = (ls.pid, ls.state, _status(self.dir, ls.pid))
        msgs = []
        for sid, v in now.items():
            if self.prev.get(sid) != v:
                msgs.append({"type": "session_state", "cc_session_id": sid, "pid": v[0], "proc": v[1], "cc_status": v[2]})
        for sid in self.prev.keys() - now.keys():
            msgs.append({"type": "session_state", "cc_session_id": sid, "pid": None, "proc": None, "cc_status": None})
        self.prev = now
        return msgs

    async def run(self) -> None:
        self.tick()                    # 처음 상태는 기준으로만(스냅샷이 이미 갖고 있다)
        while True:
            await asyncio.sleep(self.interval)
            try:
                msgs = await asyncio.to_thread(self.tick)
            except Exception as e:  # noqa: BLE001
                log.warning("세션 상태 확인 실패: %s", type(e).__name__)
                continue
            for m in msgs:
                self.publish(m)
            if msgs and self.on_change:
                self.on_change()
