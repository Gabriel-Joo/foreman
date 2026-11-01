"""트랜스크립트 와처 — ~/.claude/projects 아래 디렉토리를 inotify로 감시하고, 바뀐 파일을 offset부터 읽어 조립기에 넘긴다.

- 파일이 아니라 디렉토리에 건다: 루트(새 프로젝트 디렉토리) · 프로젝트(새 세션 파일 · 세션 디렉토리) ·
  세션 디렉토리(subagents/ 생김) · subagents/(새 서브에이전트 파일)
- 새 디렉토리를 감시에 넣은 직후 그 안을 한 번 훑는다(감시를 걸기 전에 생긴 파일을 놓치지 않게)
- 시작하면 inotify를 먼저 건 다음 전체를 백필한다 — 백필 중에 쓰인 줄도 놓치지 않는다
- rescan_s마다 크기 > offset인 파일을 다시 본다(inotify 대기열 넘침 등 놓친 것 대비)
- 읽기는 스레드(asyncio.to_thread), 적재는 조립기의 단일 writer
"""

import asyncio
import logging
import os
import time
from pathlib import Path

from inotify_simple import INotify, flags

from bridge.assembler import Assembler
from bridge.config import Settings
from bridge.transcript.reader import FileKey, classify, iter_transcripts, read_chunk

log = logging.getLogger("foreman.watcher")

DIR_MASK = flags.CREATE | flags.MODIFY | flags.CLOSE_WRITE | flags.MOVED_TO | flags.DELETE_SELF


class Watcher:
    def __init__(self, settings: Settings, assembler: Assembler) -> None:
        self.s = settings
        self.root = Path(settings.projects_root)
        self.asm = assembler
        self.ino: INotify | None = None
        self.wd_path: dict[int, Path] = {}
        self.dirty: dict[str, FileKey] = {}
        self.wake = asyncio.Event()
        self.backfill_done = asyncio.Event()
        self.backfill_seconds: float | None = None
        self.failures: dict[str, int] = {}

    # ── inotify ─────────────────────────────────────────────
    def _watch_dir(self, d: Path) -> None:
        try:
            wd = self.ino.add_watch(str(d), DIR_MASK)  # type: ignore[union-attr]
        except OSError as e:
            log.warning("감시 실패 %s: %s", d, e)
            return
        self.wd_path[wd] = d
        for p in d.iterdir():  # 감시를 걸기 전에 생긴 것
            self._seen(p)

    def _seen(self, p: Path) -> None:
        if p.is_dir():
            rel = p.relative_to(self.root).parts
            # 루트/프로젝트, 루트/프로젝트/세션, 루트/프로젝트/세션/subagents 만 감시한다
            if len(rel) <= 2 or (len(rel) == 3 and rel[2] == "subagents"):
                self._watch_dir(p)
        elif (k := classify(p, self.root)) is not None:
            self.dirty[k.path] = k

    def _on_inotify(self) -> None:
        assert self.ino is not None
        for ev in self.ino.read(timeout=0):
            if ev.mask & flags.Q_OVERFLOW:
                log.warning("inotify 대기열 넘침 — 전체를 다시 훑는다")
                self._rescan()
                continue
            base = self.wd_path.get(ev.wd)
            if base is None:
                continue
            if ev.mask & (flags.DELETE_SELF | flags.IGNORED):
                self.wd_path.pop(ev.wd, None)
                continue
            if ev.name:
                self._seen(base / ev.name)
        self.wake.set()

    def _rescan(self) -> None:
        for k in iter_transcripts(self.root):
            fs = self.asm.file_state(k.path)
            try:
                size = os.path.getsize(k.path)
            except OSError:
                continue
            if fs is None or size != fs.offset:
                self.dirty[k.path] = k

    # ── 읽기 · 적재 ──────────────────────────────────────────
    async def _drain(self) -> None:
        while self.dirty:
            path, key = next(iter(self.dirty.items()))
            del self.dirty[path]
            fs = self.asm.file_state(path)
            try:
                ch = await asyncio.to_thread(read_chunk, key, fs.offset if fs else 0, fs.inode if fs else None,
                                             self.s.ingest_chunk_bytes)
                if ch is None:
                    continue
                if ch.reset:
                    log.warning("같은 파일이 아니다(inode 변경 · 잘림) — 처음부터: %s", path)
                await self.asm.apply_chunk(ch)
                self.failures.pop(path, None)
                if not ch.at_eof:
                    self.dirty[path] = key  # 남은 부분
                    await asyncio.sleep(0)  # hook 등 다른 작업에 차례를 준다
            except Exception as e:  # noqa: BLE001 — 한 파일 실패가 와처를 멈추면 안 된다
                n = self.failures[path] = self.failures.get(path, 0) + 1
                log.warning("적재 실패(%d회) %s: %s: %s", n, path, type(e).__name__, str(e)[:300])
                await asyncio.sleep(min(2 ** n, 60))
                self.dirty[path] = key

    async def backfill(self) -> float:
        """전체를 한 번 읽는다(inotify 없이). 걸린 초를 돌려준다."""
        t0 = time.monotonic()
        for k in iter_transcripts(self.root):
            self.dirty[k.path] = k
        self.asm.stats.files = len(self.dirty)
        await self._drain()
        await self.asm.link()
        self.backfill_seconds = time.monotonic() - t0
        return self.backfill_seconds

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.ino = INotify()
        self._watch_dir(self.root)          # 재귀적으로 디렉토리 감시 + 기존 파일을 dirty로
        loop.add_reader(self.ino.fd, self._on_inotify)
        log.info("감시 시작: 디렉토리 %d개", len(self.wd_path))
        try:
            secs = await self.backfill()
            closed = await self.asm.sweep()
            self.asm.live = True
            self.backfill_done.set()
            log.info("백필 끝 %.1f초, 정리로 닫은 턴 %d — 실시간 모드", secs, closed)
            last_rescan = last_sweep = last_link = time.monotonic()
            while True:
                try:
                    async with asyncio.timeout(5):
                        await self.wake.wait()
                except TimeoutError:
                    pass
                self.wake.clear()
                await self._drain()
                now = time.monotonic()
                if now - last_rescan > self.s.rescan_s:
                    self._rescan()
                    last_rescan = now
                    await self._drain()
                if now - last_sweep > self.s.sweep_s:
                    await self._safe(self.asm.sweep(), "정리")
                    last_sweep = now
                if now - last_link > self.s.link_s:
                    await self._safe(self.asm.link(), "연결")
                    last_link = now
        finally:
            loop.remove_reader(self.ino.fd)
            self.ino.close()

    @staticmethod
    async def _safe(coro, what: str) -> None:  # noqa: ANN001
        try:
            await coro
        except Exception as e:  # noqa: BLE001
            log.warning("%s 실패: %s: %s", what, type(e).__name__, str(e)[:200])
