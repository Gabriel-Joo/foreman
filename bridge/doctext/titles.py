"""편 제목과 편 사이 참조.

- 편 제목: 문서에서 처음 나오는 `# ` 줄(first_h1). 노션 제목(`title = "h1"`), 서기실 편 이름, 편 사이 참조 색인이 같은 것을 쓴다
- 번호 뗀 제목: 앞 두 자리 번호(`03 `, `02-01 `)를 뗀 것. 인프라 원고는 참조를 번호 없이 쓴다(인프라 scripts/docs-check.py 5번 규칙)
- 편 사이 참조: 원고 글의 `→ 「제목」`. 같은 묶음 편의 제목을 그대로, 없으면 번호 뗀 제목으로 찾는다
"""

from __future__ import annotations

import re

from bridge.doctext.lines import TEXT, split, walk
from bridge.doctext.marks import STRIP_TURN

H1 = re.compile(r"^#\s+(.*)$")
BARE = re.compile(r"^\d{2}(?:-\d{2})?\s+")


def xref_pattern(arrow: str = "a", title: str = "t") -> str:
    """`→ 「제목」` 정규식 글(묶음 이름을 정해 다른 정규식 안에 끼운다). 제목은 한 줄, 비어 있지 않고 백틱이 없다."""
    return rf"(?P<{arrow}>→[ \t]*)「(?P<{title}>[^」\n`]+)」"


XREF = re.compile(xref_pattern())


def first_h1(md: str) -> tuple[int | None, str | None]:
    """(줄 번호 0부터, 제목 글). 없으면 (None, None).
    - 첫 H1 앞에 무엇이 있든 문서에서 처음 나오는 `# ` 줄이다
    - H1로 세지 않는 곳: 코드 울타리 안(셸 주석 `# …`), 맨 위 YAML 머리말(`---` … `---`), HTML 주석 안
    - `##` 이상은 H1이 아니다. 글은 앞뒤 공백, 뒤쪽 `#`(닫는 표시), `[t:…]` 표지, 백틱, `*`를 뗀 것
    - 빈 제목(`# `만)은 H1로 세지 않고 다음 후보를 찾는다"""
    lines = split(md)
    start, n = 0, len(lines)
    if n and lines[0].strip() == "---":                      # YAML 머리말
        j = next((k for k in range(1, n) if lines[k].strip() in ("---", "...")), None)
        if j is not None:
            start = j + 1
    for i, kind in walk(lines, start):
        if kind != TEXT or not (h := H1.match(lines[i].strip())):
            continue
        text = STRIP_TURN.sub("", h.group(1))
        text = re.sub(r"\s+#+$", "", text)
        text = re.sub(r"[`*]", "", text).strip()
        if text:
            return i, text
    return None, None


def bare_title(title: str) -> str:
    return BARE.sub("", title)


def xref_key(title: str) -> str:
    """참조에 적힌 제목을 색인과 맞댈 꼴로(백틱, * 떼기)."""
    return re.sub(r"[`*]", "", title).strip()


def xref_index(titles: dict[str, str | None]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """같은 묶음 편들(경로 → 첫 # 줄 제목)의 제목 색인. (그대로 제목 → 경로들, 번호 뗀 제목 → 경로들).
    FOREMAN 원고는 「→ 「03 세션 지켜보기와 글 넣기」」처럼 번호째 쓰고, 인프라 원고는 번호 없이 쓴다. 둘 다 받는다."""
    exact: dict[str, list[str]] = {}
    bare: dict[str, list[str]] = {}
    for path in sorted(titles):
        t = titles[path]
        if not t:
            continue
        exact.setdefault(t, []).append(path)
        b = bare_title(t)
        if b != t:
            bare.setdefault(b, []).append(path)
    return exact, bare


def xref_lookup(index: tuple[dict[str, list[str]], dict[str, list[str]]], title: str) -> list[str]:
    """참조 제목 → 그 제목을 가진 편 경로들(그대로 먼저, 없으면 번호 뗀 제목). 하나면 찾은 것, 여럿이면 겹침, 없으면 빈 목록."""
    exact, bare = index
    key = xref_key(title)
    return exact.get(key) or bare.get(key) or []
