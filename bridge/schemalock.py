"""스키마 잠금(11-05) — 한 프로젝트의 DB 스키마는 한 세션만 바꾼다.

worktree로 세션마다 파일은 갈라도 DB는 같이 쓴다. 두 세션이 마이그레이션을 따로 만들면 번호가 겹치거나, 한쪽이 먼저 DB에 적용해
다른 쪽 코드가 깨진다. 그래서 마이그레이션 파일을 처음 쓰거나 마이그레이션 명령을 처음 돌린 세션이 그 프로젝트의 잠금을 갖고,
다른 세션의 같은 시도는 PreToolUse에서 거부한다(프로젝트 승인 모드가 observe여도 — 사용자 지시).

잠금이 풀리는 때
- 잠금을 가진 세션이 worktree에 있었으면: 그 worktree를 합치거나 버렸을 때(세션이 끝나도 합치기 전엔 그 스키마가 main에 없다)
- 원본 폴더 세션이었으면: 그 세션이 끝났을 때
- 화면 · API에서 사람이 풀 때
상태는 `~/.foreman/schema_lock.json`(브리지를 다시 띄워도 남는다).
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from bridge import worktree as wt

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _top(path: str) -> str | None:
    """저장소 · worktree의 맨 위 — 위로 올라가며 `.git`(원본은 폴더, worktree는 파일)이 있는 첫 폴더."""
    p = Path(path)
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return str(d)
    return None


class SchemaLock:
    def __init__(self, config: str | Path, alive: Callable[[str], bool], state: str | Path | None = None) -> None:
        self.rules: dict[str, dict[str, Any]] = {}
        p = Path(config)
        if p.exists():
            for proj, r in (tomllib.loads(p.read_text()).get("schema_lock") or {}).items():
                self.rules[proj] = {"paths": [x.strip("/") + "/" for x in r.get("paths", [])],
                                    "commands": [re.compile(x) for x in r.get("commands", [])]}
        self.alive = alive
        self.state_path = Path(state or Path.home() / ".foreman" / "schema_lock.json")
        self.state: dict[str, dict[str, Any]] = {}
        try:
            self.state = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
        os.replace(tmp, self.state_path)

    def touches(self, project: str | None, tool: str, inp: dict[str, Any], cwd: str | None) -> str | None:
        """스키마를 바꾸는 시도면 그 대상(사람이 읽을 것), 아니면 None."""
        r = self.rules.get(project or "")
        if not r:
            return None
        if tool in EDIT_TOOLS:
            path = inp.get("file_path") or inp.get("notebook_path")
            if not isinstance(path, str) or not path:
                return None
            full = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd or "/", path))
            rel = os.path.relpath(full, _top(full) or cwd or "/")
            return rel if any(rel.startswith(x) for x in r["paths"]) else None
        if tool == "Bash":
            cmd = str(inp.get("command") or "")
            for rx in r["commands"]:
                if m := rx.search(cmd):
                    return m.group(0)
        return None

    def check(self, project: str | None, cc: str | None, cwd: str | None, tool: str, inp: dict[str, Any]) -> str | None:
        """거부 이유 또는 None. 처음 시도한 세션이 잠금을 갖는다."""
        what = self.touches(project, tool, inp, cwd)
        if not what or not cc or not project:
            return None
        h = self.state.get(project)
        if h and h["cc"] != cc and self._held(h):
            where = f"worktree {h['wt']}" if h.get("wt") else "원본 폴더"
            return (f"스키마 잠금 — 이 프로젝트의 DB 스키마는 다른 세션({h['cc'][:8]}, {where})이 바꾸는 중입니다({what}). "
                    "그 세션이 끝나 합쳐진 뒤에 하거나, 그 세션에 맡기거나, 화면에서 잠금을 풀어 달라고 사용자에게 요청하세요.")
        if not h or h["cc"] != cc:
            repo, name = wt.split(cwd or "")
            self.state[project] = {"cc": cc, "wt": name, "wt_path": os.path.join(repo, wt.WT_DIR, name) if name else None,
                                   "since": datetime.now(timezone.utc).isoformat(timespec="seconds"), "what": what}
            self._save()
        return None

    def _held(self, h: dict[str, Any]) -> bool:
        if self.alive(h["cc"]):
            return True
        return bool(h.get("wt_path")) and Path(h["wt_path"]).is_dir()   # 끝났어도 합치기 전 worktree면 계속

    def release(self, project: str, worktree_name: str | None = None) -> bool:
        h = self.state.get(project)
        if not h or (worktree_name is not None and h.get("wt") != worktree_name):
            return False
        del self.state[project]
        self._save()
        return True

    def view(self) -> dict[str, Any]:
        return {p: {**h, "held": self._held(h)} for p, h in self.state.items()}
