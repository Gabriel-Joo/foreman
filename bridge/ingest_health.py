"""적재(수집기)가 스스로 막힌 것을 알린다 — "조용한 고장"을 FOREMAN 자신에게도 적용한다.

11-03: 한 세션의 트랜스크립트가 06:48부터 같은 덩어리에서 실패를 되풀이했다. 로그에만 남아 몇 시간 아무도 몰랐다.
milvus-port-forward가 567,740번 재시작하는 것을 한 달 넘게 몰랐던 것과 같은 모양이다.

30초마다 watcher.health()를 보고, 바뀔 때만 알린다(텔레그램 [포먼] + 대시보드 머리 띠):
  - 막힘: 한 파일이 ingest_alert_s(기본 5분) 넘게 같은 자리에서 실패 중 → "적재 막힘", 풀리면 "적재 회복"
  - 버린 줄: 너그러운 모드에서 버린 줄 · 마지막 수단으로 건너뛴 덩어리 → 그때마다 한 번
  - 멈춤: 실시간 루프가 ingest_tick_alert_s(기본 2분) 넘게 돌지 않음 → "와처 멈춤"
"""

import asyncio
import logging
import time
from typing import Any

log = logging.getLogger("foreman.ingest_health")


class IngestMonitor:
    def __init__(self, watcher: Any, assembler: Any, notifier: Any, alert_s: float = 300.0, tick_alert_s: float = 120.0,
                 every_s: float = 30.0, on_change: Any = None) -> None:
        self.w, self.asm, self.notifier = watcher, assembler, notifier
        self.alert_s, self.tick_alert_s, self.every_s = alert_s, tick_alert_s, every_s
        self.on_change = on_change or (lambda: None)
        self.on_failure: Any = None             # 자동 기상 2단계(bridge/wake.py) — (project, kind, key, 알림 글)
        self.alerted: dict[str, float] = {}     # 막힘을 알린 파일 → 실패가 시작된 시각
        self.tick_alerted = False
        self.seen_skip = 0
        self.state: dict[str, Any] = {"ok": True, "stuck": [], "stalled": False, "skips": []}

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.every_s)
            try:
                self.check()
            except Exception as e:  # noqa: BLE001
                log.warning("적재 상태 확인 실패: %s: %s", type(e).__name__, str(e)[:200])

    def check(self) -> None:
        h = self.w.health(self.alert_s)
        changed = False
        stuck = {x["path"]: x for x in h["stuck"]}
        for path, x in stuck.items():
            if self.alerted.get(path) != x["since"]:
                self.alerted[path] = x["since"]
                why = "DB 연결 · 시간 초과 — 기다리는 중" if x["transient"] else "같은 줄에서 되풀이 — 곧 너그러운 모드 · 건너뛰기"
                msg = (f"⚠ 적재 막힘 — 세션 {x['session'][:8]} {x['minutes']}분째 같은 자리에서 실패({x['failures']}번). "
                       f"이 세션의 기록이 쌓이지 않는다\n{x['error'][:200]}\n{why}\n파일 {path}")
                self._send(msg)
                if self.on_failure and not x["transient"]:   # DB 끊김 · 시간 초과는 기다리면 돌아온다 — 계획할 거리가 아니다
                    try:
                        self.on_failure("foreman", "ingest_stuck", f"ingest:{path}:{x['since']}", msg)
                    except Exception as e:  # noqa: BLE001
                        log.warning("자동 기상에 넘기지 못함: %s", type(e).__name__)
                changed = True
        for path in [p for p in self.alerted if p not in stuck and p not in self.w.failures]:
            del self.alerted[path]
            self._send(f"✅ 적재 회복 — 세션 {path.rsplit('/', 1)[-1][:8]}")
            changed = True
        stalled = bool(self.asm.live) and h["tick_age_s"] > self.tick_alert_s
        if stalled and not self.tick_alerted:
            self._send(f"⚠ 와처 멈춤 — 트랜스크립트 감시 루프가 {int(h['tick_age_s'])}초째 돌지 않는다. 브리지 확인")
        elif self.tick_alerted and not stalled:
            self._send("✅ 와처 다시 돈다")
        if stalled != self.tick_alerted:
            self.tick_alerted, changed = stalled, True
        for sk in h["skips"]:
            if sk["seq"] > self.seen_skip:
                self.seen_skip = sk["seq"]
                what = (f"줄 {sk['count']}개를 버리고 나머지를 적재했다" if sk["kind"] == "records"
                        else f"덩어리 하나(줄 {sk['count']}개, [{sk['start']}, {sk['end']}))를 건너뛰었다 — 그 줄들은 DB에 없다")
                self._send(f"⚠ 적재 중 {what} — 세션 {sk['session'][:8]}\n{sk['reason'][:200]}")
                changed = True
        now = time.time()
        self.state = {"ok": not stuck and not stalled, "stuck": list(stuck.values()), "stalled": stalled,
                      "tick_age_s": int(h["tick_age_s"]), "failing": h["failing"],
                      "skips": [s for s in h["skips"] if now - s["at"] < 86400][-5:]}
        if changed:
            self.on_change()

    def snapshot(self) -> dict[str, Any]:
        return self.state

    def _send(self, msg: str) -> None:
        log.warning("적재 알림: %s", msg.splitlines()[0])
        if self.notifier is None:
            return
        rule = self.notifier.rules.for_project("foreman")
        prefix = rule.prefix if rule is not None else "[FOREMAN]"
        self.notifier.send_direct("foreman", "ingest", None, f"{prefix} {msg}")
