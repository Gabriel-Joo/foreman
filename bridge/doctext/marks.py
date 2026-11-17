"""근거 표시(11-06, `docs/12_scribe.md` 「4.」): 원고 문장 끝의 `[종류:값]`.

    [c:1a2b3c4]                 커밋
    [t:123]                     FOREMAN 턴(DB)
    [log:파일.md]               log/ 아래 파일
    [docs:파일.md:10-20]        docs/ 아래 파일, 줄 범위는 줄 하나(:10)나 범위(:10-20). 인프라는 [docs:history/x.md:193-197]
    [code:bridge/x.py]          저장소 맨 위 기준 파일, 끝이 /면 폴더, 뒤에 :줄 :줄-줄

값에는 공백과 `]`가 없다. 줄 범위 뒤 `#…`(절 이름)는 떼고 읽는다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

KINDS = ("c", "t", "log", "docs", "code")
FILE_KINDS = ("log", "docs", "code")      # 값이 파일 경로인 종류


def mark_re(kinds: Iterable[str] = KINDS) -> re.Pattern[str]:
    """`[종류:값]`. 이름 붙은 묶음 k(종류), v(값)."""
    return re.compile(rf"\[(?P<k>{'|'.join(kinds)}):(?P<v>[^\]\s]+)\]")


MARK = mark_re()
CODE_MARK = mark_re(("code",))
KINDS_RE = "|".join(KINDS)                                  # 다른 정규식 안에 끼울 때(bridge/notion.py 줄 안 꾸밈)
STRIP = re.compile(rf"\s*\[(?:{KINDS_RE}):[^\]\s]+\]")      # 노션 판에서 떼는 근거 표시(앞 공백까지)
STRIP_TURN = re.compile(r"\s*\[t:[^\]\s]+\]")               # 턴 표지만(원고가 아닌 글, 제목 줄)

# 값 = 파일(:줄(-줄))(#절). 파일에는 : # 이 없다
TARGET = re.compile(r"^(?P<f>[^:#]+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?(?:#.*)?$")
# 경로:줄(-줄). 백틱 안 경로, 명령 인자, [code:] 값에 쓴다(파일에 :가 있어도 마지막 :줄만 뗀다)
RANGE = re.compile(r"^(?P<p>.+?):(?P<a>\d+)(?:-(?P<b>\d+))?$")


def target(v: str) -> tuple[str, int | None, int | None] | None:
    """근거 표시 값 → (파일, 시작 줄, 끝 줄). 줄이 하나면 끝 줄은 None, 줄이 없으면 둘 다 None. 모양이 틀리면 None."""
    m = TARGET.match(v)
    if not m:
        return None
    return m["f"], int(m["a"]) if m["a"] else None, int(m["b"]) if m["b"] else None


def split_range(tok: str) -> tuple[str, tuple[int, int] | None]:
    """`경로:10-20` → (경로, (10, 20)), `경로:10` → (경로, (10, 10)), 줄이 없으면 (tok, None)."""
    m = RANGE.match(tok)
    if not m:
        return tok, None
    a = int(m["a"])
    return m["p"], (a, int(m["b"] or a))


def mark_file(v: str) -> str:
    """값의 파일 부분(줄 범위, 절을 뗀 것). 노션 판이 글자로 보일 때."""
    return re.split(r"[:#]", v)[0]


def marks(line: str, kinds: Iterable[str] | None = None) -> Iterator[tuple[str, str, re.Match[str]]]:
    """한 줄의 근거 표시 (종류, 값, 맞은 것)."""
    rx = MARK if kinds is None else mark_re(kinds)
    for m in rx.finditer(line):
        yield m["k"], m["v"], m
