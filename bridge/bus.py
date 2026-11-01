"""적재 파이프라인 — 생산자 → (대기열) → 적재 → 구독자(WS).

- 쓰는 쪽은 작업 하나(single writer)다. event.id 순서 = 들어온 순서가 보장된다
- 적재가 끝난 뒤에 내보낸다. 구독자는 항상 id가 붙은 이벤트를 받고, 화면에 보인 것은 DB에도 있다
- DB가 죽으면 그 이벤트를 붙든 채 재시도한다(지수 대기, 상한 db_retry_max_s). 그동안 대기열이 찬다
  대기열이 꽉 차면 submit이 asyncio.QueueFull을 낸다 — 생산자가 처리한다(2단계 와처는 offset을 멈춘다)
- 다시 해도 안 될 오류(중복 uuid, 잘못된 값)는 버리고 기록만 남긴다. 대기열을 막지 않는다
- 느린 구독자는 쌓인 것을 비우고 {"type": "resync"}를 받는다(빠진 것은 DB에서 다시 읽는다 — 6단계 UI)
"""

import asyncio
import logging
from typing import Any

from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError

from bridge.models import EventIn
from bridge.store import Store

log = logging.getLogger("foreman.bus")

DUP_KEY = 1062  # MySQL ER_DUP_ENTRY


def _is_permanent(e: Exception) -> bool:
    """재시도해도 같은 결과일 오류인가. 연결 · 타임아웃은 일시적이다."""
    if isinstance(e, IntegrityError):
        return True
    if isinstance(e, DBAPIError) and e.connection_invalidated:
        return False
    if isinstance(e, StatementError) and not isinstance(e, DBAPIError):
        return True  # 파라미터 변환 실패 등
    orig = getattr(e, "orig", None)
    code = orig.args[0] if orig is not None and orig.args else None
    # 1xxx 중 데이터 · 문법 오류(1054 칼럼 없음, 1064 문법, 1264 범위, 1366 값, 1406 너무 김, 3140 JSON)
    return code in (1054, 1064, 1264, 1366, 1406, 3140)


class Pipeline:
    def __init__(self, store: Store, *, queue_max: int, retry_max_s: float, subscriber_max: int = 256) -> None:
        self.store = store
        self.retry_max_s = retry_max_s
        self.subscriber_max = subscriber_max
        self._in: asyncio.Queue[tuple[EventIn, asyncio.Future[int | None]]] = asyncio.Queue(queue_max)
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._task: asyncio.Task[None] | None = None
        self.db_ok: bool | None = None  # 마지막 적재 시도의 결과(healthz 참고용)

    # 생산자 쪽
    def submit(self, ev: EventIn) -> asyncio.Future[int | None]:
        """대기열에 넣는다. 돌려준 Future는 적재되면 event.id, 버려지면 None. 꽉 차면 QueueFull."""
        fut: asyncio.Future[int | None] = asyncio.get_running_loop().create_future()
        self._in.put_nowait((ev, fut))
        return fut

    @property
    def depth(self) -> int:
        return self._in.qsize()

    # 구독자 쪽
    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(self.subscriber_max)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(q)

    @property
    def subscribers(self) -> int:
        return len(self._subs)

    def publish(self, msg: dict[str, Any]) -> None:
        """이미 적재된 것을 구독자에게만 낸다(조립기 — 턴 · 트랜스크립트 이벤트는 조립기가 직접 적재한다)."""
        self._fanout(msg)

    def _fanout(self, msg: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                while not q.empty():
                    q.get_nowait()
                q.put_nowait({"type": "resync"})

    # 쓰는 작업
    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="foreman-pipeline")

    async def stop(self, drain_timeout_s: float = 5.0) -> None:
        """남은 것을 잠깐 적재해 보고 멈춘다. 못 쓴 것은 기록하고 버린다(hook 이벤트는 잃는다 — 01 결과의 백업 근거)."""
        if self._task is None:
            return
        try:
            async with asyncio.timeout(drain_timeout_s):
                while not self._in.empty():
                    await asyncio.sleep(0.05)
        except TimeoutError:
            pass
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        if self.depth:
            log.warning("종료 시 적재하지 못한 이벤트 %d개를 버림", self.depth)

    async def _run(self) -> None:
        while True:
            ev, fut = await self._in.get()
            row = await self._write(ev)
            if not fut.done():
                fut.set_result(row["id"] if row else None)
            if row:
                self._fanout({"type": "event", "event": row})

    async def _write(self, ev: EventIn) -> dict[str, Any] | None:
        delay = 0.5
        while True:
            try:
                row = await self.store.insert_event(ev)
                if self.db_ok is False:
                    log.info("DB 적재 복구")
                self.db_ok = True
                return row
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 어떤 오류든 쓰는 작업이 죽으면 안 된다
                if _is_permanent(e):
                    orig = getattr(e, "orig", None)
                    code = orig.args[0] if orig is not None and orig.args else None
                    if code == DUP_KEY:
                        log.debug("중복 uuid 건너뜀: %s", ev.uuid)
                    else:
                        log.error("적재 불가로 버림: %s(%s) type=%s", type(e).__name__, code, ev.type)
                    return None
                if self.db_ok is not False:
                    log.warning("DB 적재 실패, 재시도: %s", type(e).__name__)
                self.db_ok = False
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.retry_max_s)
