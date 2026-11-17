"""줄 나누기: 코드 울타리와 HTML 주석을 가른다. 문법을 읽는 곳은 모두 이 걷기를 쓴다(11-17 문서 도구 합치기 1단계).

- 코드 울타리: 앞 공백 뒤 ``` 이나 ~~~ 세 개 이상으로 연다. 같은 글자로 같은 길이 이상 시작하는 줄이 닫는다(뒤에 언어 이름이 붙어도)
- HTML 주석: 앞 공백 뒤 `<!--`로 시작하는 줄부터 `-->`가 든 줄까지. 같은 줄에 `-->`가 있으면 그 한 줄
- 주석 안의 ``` 줄은 울타리를 열지 않고, 울타리 안의 `<!--` 줄은 주석을 열지 않는다
"""

from __future__ import annotations

import re
from collections.abc import Iterator

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")

TEXT = "text"
FENCED = "fence"        # 울타리를 여는 줄, 닫는 줄, 그 사이
COMMENT = "comment"     # 주석을 여는 줄부터 닫는 줄까지


def split(md: str) -> list[str]:
    """머리 주석, 첫 # 줄을 읽는 곳의 줄 나누기(\\r\\n만 줄바꿈으로 본다). 근거 표시를 읽는 곳은 str.splitlines를 그대로 쓴다."""
    return md.replace("\r\n", "\n").split("\n")


def walk(lines: list[str], start: int = 0) -> Iterator[tuple[int, str]]:
    """(줄 번호 0부터, 종류 TEXT/FENCED/COMMENT). start 앞 줄은 건너뛴다(YAML 머리말 뒤부터 읽을 때)."""
    fence: str | None = None
    in_comment = False
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if fence:
            if s.startswith(fence):
                fence = None
            yield i, FENCED
        elif in_comment:
            in_comment = "-->" not in s
            yield i, COMMENT
        elif (m := FENCE.match(s)):
            fence = m.group(1)
            yield i, FENCED
        elif s.startswith("<!--"):
            in_comment = "-->" not in s
            yield i, COMMENT
        else:
            yield i, TEXT


def text_lines(lines: list[str]) -> Iterator[tuple[int, str]]:
    """울타리와 주석 밖 줄만 (줄 번호 1부터, 줄)."""
    for i, kind in walk(lines):
        if kind == TEXT:
            yield i + 1, lines[i]


def comments(lines: list[str]) -> list[tuple[int, int, str]]:
    """울타리 밖 HTML 주석마다 (시작 줄, 끝 줄, `<!--`와 `-->` 사이 글). 줄 번호는 0부터. 닫히지 않은 주석은 마지막 줄까지."""
    out: list[tuple[int, int, str]] = []
    a: int | None = None
    for i, kind in walk(lines):
        if kind != COMMENT:
            continue
        if a is None:
            a = i
        if "-->" in lines[i]:
            out.append(_comment(lines, a, i))
            a = None
    if a is not None:
        out.append(_comment(lines, a, len(lines) - 1))
    return out


def _comment(lines: list[str], a: int, b: int) -> tuple[int, int, str]:
    body = "\n".join(lines[a:b + 1])
    return a, b, body.split("<!--", 1)[1].rsplit("-->", 1)[0]
