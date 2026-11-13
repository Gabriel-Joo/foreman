"""미리보기 관리(11-05, docs/11_worktree.md 2절) — 버튼을 누를 때만 띄우고, 세션을 끝내거나 합치기 · 버리기 때 끈다.

- 명령은 `config/worktree.toml`의 `[preview.<프로젝트>] cmd`. `{py}`(원본 저장소 .venv 파이썬) · `{repo}` · `{wt}` · `{port}` ·
  `{upstream}` · `{label}`을 채운다. 미리보기 서버 코드는 원본 저장소 것을 쓴다(worktree가 이 기능보다 먼저 갈라졌을 수 있다)
- 포트는 8200~8299에서 빈 것. tmux 세션 `fm-pv-<worktree 이름>`에서 돌아 브리지를 다시 띄워도 남는다
- 상태는 `~/.foreman/previews.json`(worktree 경로 → 포트 · tmux 이름 · 시작 시각). 브리지가 뜰 때 맞춰 본다(sweep)
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import socket
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from bridge import worktree as wt
from bridge.inject import Refused, tmux
from bridge.preview import IDENT_HEADER, IDENT_PATH

PORTS = range(8200, 8300)


def free_port(host: str = "127.0.0.1") -> int:
    for p in PORTS:
        with socket.socket() as s:
            try:
                s.bind((host, p))
            except OSError:
                continue
            return p
    raise Refused("미리보기에 쓸 빈 포트(8200~8299)가 없습니다")


class Previews:
    def __init__(self, config: str | Path, socket_path: str, upstream: str, state: str | Path | None = None) -> None:
        cfg = tomllib.loads(Path(config).read_text()) if Path(config).exists() else {}
        self.cmds: dict[str, str] = {k: v["cmd"] for k, v in (cfg.get("preview") or {}).items() if v.get("cmd")}
        self.socket, self.upstream = socket_path, upstream
        self.state_path = Path(state or Path.home() / ".foreman" / "previews.json")
        try:
            self.state: dict[str, dict[str, Any]] = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            self.state = {}
        self.dead: dict[str, str] = {}      # worktree 경로 → 죽어서 기록을 치운 까닭(다시 띄우기에 실패하면 그대로 알린다)

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
        os.replace(tmp, self.state_path)

    async def _alive(self, tname: str) -> bool:
        try:
            await tmux(self.socket, "has-session", "-t", tname)
            return True
        except Refused:
            return False

    @staticmethod
    async def _probe(port: int) -> bool:
        """127.0.0.1의 그 포트가 **미리보기 브리지**로 답하는지 — 포트만 열려 있는 것으로는 믿지 않는다(남의 서비스일 수 있다)."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"http://127.0.0.1:{port}{IDENT_PATH}")
            return r.status_code == 200 and r.headers.get(IDENT_HEADER) == "1" and r.json().get("foreman_preview") is True
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    async def get(self, wt_path: str) -> dict[str, Any] | None:
        """기록이 있어도 tmux가 살아 있고 그 포트가 미리보기로 답할 때만 「있음」. 아니면 기록을 치우고 까닭을 `dead`에 남긴다."""
        e = self.state.get(wt_path)
        if not e:
            return None
        if not await self._alive(e["tmux"]):
            why = f"tmux 세션({e['tmux']})이 없습니다"
        elif not await self._probe(e["port"]):
            why = f"포트 {e['port']}가 미리보기로 답하지 않습니다"
        else:
            self.dead.pop(wt_path, None)
            return e
        self.state.pop(wt_path, None)
        self.dead[wt_path] = why
        self._save()
        if await self._alive(e["tmux"]):          # 서버만 죽고 tmux가 남은 경우 — 치워야 다시 띄울 수 있다
            try:
                await tmux(self.socket, "kill-session", "-t", e["tmux"])
            except Refused:
                pass
        return None

    async def start(self, project: str | None, wt_path: str) -> dict[str, Any]:
        if (e := await self.get(wt_path)):
            return e | {"reused": True}
        was_dead = self.dead.get(wt_path)
        try:
            e = await self._start(project, wt_path)
        except Refused as ex:
            if was_dead:
                raise Refused(f"미리보기가 죽어 있습니다 — {was_dead}. 다시 띄우지 못했습니다: {ex}") from ex
            raise
        self.dead.pop(wt_path, None)
        return e | ({"restarted": True, "was_dead": was_dead} if was_dead else {})

    async def _start(self, project: str | None, wt_path: str) -> dict[str, Any]:
        cmd = self.cmds.get(project or "")
        if not cmd:
            raise Refused(f"이 프로젝트({project})는 미리보기 명령이 없습니다(config/worktree.toml [preview.{project}])")
        repo, name = wt.split(wt_path)
        if not name or not Path(wt_path).is_dir():
            raise Refused("따로 작업(worktree) 폴더가 없습니다")
        port = free_port()
        tname = f"fm-pv-{name}"
        line = cmd.format(py=shlex.quote(f"{repo}/.venv/bin/python"), repo=shlex.quote(repo), wt=shlex.quote(wt_path),
                          port=port, upstream=shlex.quote(self.upstream), label=shlex.quote(wt.BRANCH_PREFIX + name))
        if await self._alive(tname):
            await tmux(self.socket, "kill-session", "-t", tname)
        await tmux(self.socket, "new-session", "-d", "-s", tname, "-c", repo, line)
        if not await self._ready(port):               # 포트가 열리고 **미리보기 확인 주소**가 답해야 한다
            out = ""
            try:
                out = (await tmux(self.socket, "capture-pane", "-p", "-t", tname))[-400:]
                await tmux(self.socket, "kill-session", "-t", tname)
            except Refused:
                pass
            raise Refused(f"미리보기가 10초 안에 뜨지 않았습니다. {out.strip()}")
        e = {"port": port, "tmux": tname, "project": project, "since": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.state[wt_path] = e
        self._save()
        return e

    @staticmethod
    async def _ready(port: int) -> bool:
        for _ in range(40):
            if await Previews._probe(port):
                return True
            await asyncio.sleep(0.25)
        return False

    async def stop(self, wt_path: str) -> bool:
        e = self.state.pop(wt_path, None)
        if not e:
            return False
        self._save()
        if await self._alive(e["tmux"]):
            await tmux(self.socket, "kill-session", "-t", e["tmux"])
        return True

    async def sweep(self) -> int:
        """브리지가 뜰 때 — tmux가 없어진 기록은 지우고, worktree가 없어진 미리보기는 끈다."""
        n = 0
        for path in list(self.state):
            if not Path(path).is_dir():
                n += await self.stop(path)
            else:
                await self.get(path)
        return n
