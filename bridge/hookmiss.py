"""판정 없이 통과한 PreToolUse를 파일에 한 줄씩 남긴다(11-15 조사 A 3, 「고치는 순서」 2).

막기(스키마 잠금 · 다른 저장소 · pgrep · 역할 권한)는 브리지가 없거나 늦거나 판정 중에 실패하면 통과한다(README 3.3 설계).
통과는 그대로 두고, 통과했다는 사실만 남긴다. 스크립트 쪽 7갈래는 scripts/foreman-decide.sh가 같은 파일에 쓴다.

    <시각> <출처> <갈래> <까닭> session=<id> tool=<도구>

- 명령 글 · 입력 값은 쓰지 않는다(비밀값이 섞일 수 있다). 까닭은 예외 클래스 이름 · 시간처럼 코드가 만든 것만
- 자리: 저장소 `.run/hook_miss.log`(gitignore, 브리지가 꺼져도 스크립트가 쓴다). FOREMAN_HOOK_MISS_LOG로 바꾼다(시험)
- 1MB를 넘으면 `.1`로 한 벌만 돌려 둔다. 한 줄은 O_APPEND 한 번의 write — 짧아서 스크립트와 섞이지 않는다
- 쓰기 실패는 판정을 막지 않는다(로그 warning만)
"""

import logging
import os
import re
import time
from pathlib import Path

from bridge.config import REPO

log = logging.getLogger("foreman.hookmiss")
MAX_BYTES = 1_048_576
_SID = re.compile(r"[A-Za-z0-9-]{1,64}")
_TOOL = re.compile(r"[A-Za-z0-9_.:-]{1,80}")


def path() -> Path:
    return Path(os.environ.get("FOREMAN_HOOK_MISS_LOG") or REPO / ".run" / "hook_miss.log")


def _only(rx: re.Pattern[str], v: object) -> str:
    return v if isinstance(v, str) and rx.fullmatch(v) else "-"


def record(branch: str, why: str = "-", session: object = None, tool: object = None) -> None:
    why = re.sub(r"\s+", "_", why)[:80] or "-"
    line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} bridge {branch} {why} "
            f"session={_only(_SID, session)} tool={_only(_TOOL, tool)}\n")
    p = path()
    try:
        p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            if p.stat().st_size > MAX_BYTES:
                os.replace(p, p.with_name(p.name + ".1"))
        except FileNotFoundError:
            pass
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as e:
        log.warning("판정 없이 통과한 기록을 쓰지 못함(%s): %s", branch, type(e).__name__)
