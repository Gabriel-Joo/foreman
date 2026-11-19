"""편 제목과 편 사이 참조.

- 편 제목: 문서에서 처음 나오는 `# ` 줄(first_h1). 노션 제목(`title = "h1"`), 서기실 편 이름, 편 사이 참조 색인이 같은 것을 쓴다
- 번호 뗀 제목: 앞 두 자리 번호(`03 `, `02-01 `)를 뗀 것. 인프라 원고는 참조를 번호 없이 쓴다(인프라 scripts/docs-check.py 5번 규칙)
- 편 사이 참조: 원고 글의 `→ 「제목」`. 같은 묶음 편의 제목을 그대로, 없으면 번호 뗀 제목으로 찾는다
- 「」 없는 편 사이 참조(bare_xrefs): `→ 07 합치기`, `→ 포스트잇에서`, 화살표를 「」 안에 넣은 `「→ 포스트잇」`. 원고 기준
  (`docs/manuscript_rules.md`)은 `→ 「제목」`만 참조로 읽어 노션 링크로 바꾸고(bridge/notion.py) 점검이 제목을 맞댄다.
  이 꼴은 링크도 점검도 빠지는 참조라 문서 점검이 따로 센다(11-19 관리자 410 일감)
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


# 「」 없는 참조에서 번호 없는 제목 뒤에 올 수 있는 것: 줄 끝, 표 칸 끝(`|`), 근거 표시(` [code:…]`), 문장부호, 「 편」, 조사.
# 그 밖(「알림기」, 「화면 이름」, 「승인 → 와처」처럼 제목 낱말로 시작하는 다른 말이나 흐름 화살표)은 참조로 보지 않는다.
# 번호 붙은 제목(`07 합치기`)은 그 자체로 편 이름이라 뒤를 보지 않는다
_AFTER_OK = re.compile(r"\s*$|\s*\||\s+\[|[.,;:)」\[!?]| 편|(?:에서|에|이|가|의|와|과|은|는|을|를|으로|로|도|만)(?:$|[\s.,;:)」|\[])")
_CODE_SPAN = re.compile(r"`[^`]*`")


def bare_xrefs(line: str, index: tuple[dict[str, list[str]], dict[str, list[str]]]) -> list[tuple[int, str, bool]]:
    """한 줄의 「」 없는 편 사이 참조: (화살표 자리 0부터, 적힌 제목, 화살표가 「」 안인가).

    가르는 기준(화살표 뒤가 편 사이 참조인지 화면 글인지): 화살표 바로 뒤(공백 뒤)가 같은 묶음 편의 제목(index의 그대로 제목이나
    번호 뗀 제목, 긴 것 먼저)으로 시작하면 참조다. 번호 없는 제목은 뒤에 `_AFTER_OK`가 올 때만이다.
    - `→ 「제목」`(XREF)은 바른 꼴이라 내지 않는다. 판정은 같은 XREF 하나라 노션 링크 바꾸기(bridge/notion.py)와 두 벌이 아니다
    - 화면 글이나 사람 말을 옮긴 `→ "…"`는 제목으로 시작하지 않아 내지 않는다(원고 기준: 화살표 뒤 화면 글은 " ")
    - 백틱 안 화살표(코드, 명령)는 보지 않는다
    - 제목을 모르는 말(`→ 브리지`, `A → B` 흐름)은 참조인지 알 수 없어 내지 않는다"""
    exact, bare = index
    keys = sorted({*exact, *bare}, key=len, reverse=True)
    if not keys or "→" not in line:
        return []
    hidden = _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
    proper = {m.start() for m in XREF.finditer(hidden)}
    out: list[tuple[int, str, bool]] = []
    for j, ch in enumerate(hidden):
        if ch != "→" or j in proper:
            continue
        rest = hidden[j + 1:].lstrip(" \t")
        for k in keys:
            if not rest.startswith(k):
                continue
            if BARE.match(k) or _AFTER_OK.match(rest[len(k):]):
                out.append((j, k, hidden[:j].rstrip(" \t").endswith("「")))
                break
    return out
