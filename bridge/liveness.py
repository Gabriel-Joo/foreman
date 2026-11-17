"""살아 있는 CC 프로세스 — ~/.claude/sessions/<pid>.json 만 읽는다(.key 파일은 열지 않는다).

json에 sessionId · pid · procStart · cwd가 있다. procStart를 /proc/<pid>/stat의 starttime과 맞춰
PID 재사용을 걸러 낸다. 프로세스가 끝나면 json이 사라지거나 /proc이 없어진다.
상태 문자(R S T …)도 돌려준다 — T(정지)는 SUSPENDED 판정 근거(docs/00_design.md 2.1, 폴링은 뒤 단계)
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LiveSession:
    pid: int
    session_id: str
    cwd: str
    state: str  # /proc/<pid>/stat의 상태 문자


def _proc_stat(pid: int) -> tuple[str, str] | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    rest = raw.rsplit(") ", 1)[1].split()
    return rest[0], rest[19]  # 상태, starttime(필드 22)


def live_sessions(sessions_dir: str | Path) -> dict[str, LiveSession]:
    out: dict[str, LiveSession] = {}
    d = Path(sessions_dir)
    if not d.is_dir():
        return out
    for p in d.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            pid = int(j.get("pid") or p.stem)
        except (OSError, ValueError):
            continue
        st = _proc_stat(pid)
        if st is None:
            continue
        state, start = st
        ps = j.get("procStart")
        if ps is not None and str(ps) != start:
            continue  # 같은 PID를 다른 프로세스가 쓰고 있다
        sid = j.get("sessionId")
        if sid:
            out[sid] = LiveSession(pid, sid, j.get("cwd", ""), state)
    return out


def is_alive(pid: int) -> bool:
    return os.path.exists(f"/proc/{pid}")
