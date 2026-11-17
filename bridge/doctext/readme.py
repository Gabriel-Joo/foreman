"""README 생성(11-17 문서 정리 B, 사용자 지시). README는 「여기 무엇이 있는지」만 보이는 문지기이고, 파일 전체가 생성물이다.

들어가는 것 넷, 이 차례로:
1. 제목: 저장소 이름(`.foreman/docs.toml` `[readme] title`, 없으면 그 저장소의 게시 프로젝트 이름)
2. 소개 문단: 포트폴리오 00편(`portfolio/00_*.md`)의 첫 문단. 첫 # 줄 뒤에서 처음 나오는 본문 문단이다. 인용(`>`),
   절 제목, 그림, 표, 목록 줄은 건너뛴다. 글은 그대로 두고 근거 표시만 뗀다(노션 판과 같은 `STRIP`)
3. 포트폴리오와 기술문서 원고 편 목록: 표 칸은 번호와 제목(편 파일 링크). 번호는 첫 # 줄 앞 번호(`03 `, `02-01 `),
   없으면 파일 이름 번호(`03_x.md`는 03, `01_a/02_b.md`는 01-02). 제목은 번호를 뗀 첫 # 줄. 하위 편도 한 줄씩 넣는다
   (노션에서도 따로 페이지이고, 제목이 바뀌면 점검이 걸어야 한다). 번호가 없는 파일은 표에 넣지 않고 알린다
4. 노션 링크: 묶음마다 맨 위 편(번호가 가장 앞인 편)의 게시 주소를 「노션에서 보기」로 건다. 주소는 부르는 쪽이 넘긴다
   (`tools/docs.py`가 게시 기록 `doc_publish`에서 읽는다). 주소가 없으면 링크를 걸지 않고 「아직 노션에 올라가지 않았습니다」를
   쓰고 알린다(빈 주소를 걸거나 조용히 넘어가지 않는다)

빼는 것: 구조 그림(포트폴리오 00편에 있다), 띄우는 법(기술문서 원고 01~03편). 둘 다 노션 링크로 보낸다.
파일 맨 위 주석이 「손으로 고치면 다음에 만들 때 날아간다」고 알린다. 문서 점검 9번(`bridge/doctext/check.py`)이
지금 원고로 만든 글과 README를 통째로 맞댄다. 이 모듈은 글을 만들고 맞대기만 한다(파일 쓰기와 DB 읽기는 `tools/docs.py`).
표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bridge.doctext.lines import TEXT, split, walk
from bridge.doctext.marks import STRIP
from bridge.doctext.titles import first_h1

PATH = "README.md"
ORDER = ("portfolio", "notion")                       # README에 놓는 차례
NAME_KO = {"portfolio": "포트폴리오", "notion": "기술문서"}
PART = re.compile(r"^(\d{2})_")
TITLE_NUM = re.compile(r"^(\d{2}(?:-\d{2})?)\s+(.*)$")
NOT_PARA = re.compile(r"^\s*(>|#|!\[|\||[-*+]\s|\d+\.\s|---|<)")
LINK = re.compile(r"^\[노션에서 보기\]\((?P<u>[^)\s]+)\)$")
TOP = ("<!-- 이 파일은 `tools/docs.py readme`가 만든다. 손으로 고치면 다음에 만들 때 날아간다. "
       "소개는 포트폴리오 00편 첫 문단, 편 목록은 원고 첫 # 줄, 노션 주소는 게시 기록에서 온다 -->")
NO_LINK = "아직 노션에 올라가지 않았습니다."


@dataclass
class Built:
    text: str = ""
    errors: list[str] = field(default_factory=list)       # 만들 수 없는 까닭(소개 편이 없음 등). 있으면 text를 쓰지 않는다
    notes: list[str] = field(default_factory=list)        # 만들었지만 알릴 것(번호 없는 파일, 노션에 아직 없는 묶음)
    tops: dict[str, str] = field(default_factory=dict)    # 묶음 → 맨 위 편 경로(노션 주소를 찾을 편)


def number(rel: str) -> str | None:
    """묶음 폴더 아래 경로 → 번호(`03_x.md` 03, `01_a/02_b.md` 01-02). 마디 하나라도 번호가 없으면 None."""
    nums = [PART.match(p) for p in rel.split("/")]
    if not all(nums):
        return None
    return "-".join(m.group(1) for m in nums if m)


def rows(folder: str, paths: list[str], bodies: dict[str, str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(표 줄 [(번호, 제목, 경로)], 번호가 없어 뺀 경로). 차례는 경로 차례(`01_a.md`가 `01_a/` 아래 글보다 앞)."""
    out: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    for p in sorted(paths):
        num = number(p[len(folder):])
        if num is None:
            skipped.append(p)
            continue
        title = first_h1(bodies.get(p, ""))[1]
        if title and (t := TITLE_NUM.match(title)) and t.group(2).strip():
            num, title = t.group(1), t.group(2).strip()
        out.append((num, title or "(제목 없음)", p))
    return out, skipped


def intro(md: str) -> str | None:
    """첫 # 줄 뒤 첫 본문 문단(줄들을 이은 것, 근거 표시를 뗀 것). 없으면 None."""
    lines = split(md)
    h, _ = first_h1(md)
    if h is None:
        return None
    para: list[str] = []
    for i, kind in walk(lines, h + 1):
        s = lines[i]
        if kind != TEXT or not s.strip() or NOT_PARA.match(s):
            if para:
                break
            continue
        para.append(STRIP.sub("", s).strip())
    return " ".join(para) or None


def top_piece(rs: list[tuple[str, str, str]]) -> str | None:
    """묶음 맨 위 편: 하위 편이 아닌 것 가운데 번호가 가장 앞인 편."""
    tops = [r for r in rs if "-" not in r[0]]
    return min(tops)[2] if tops else None


def build(title: str, sets: dict[str, str], pieces: dict[str, list[str]], bodies: dict[str, str],
          links: dict[str, str | None]) -> Built:
    """README 글 전체. sets는 {묶음: 폴더}(없는 묶음은 빠진다), pieces는 {묶음: 편 경로}, links는 {편 경로: 노션 주소}."""
    b = Built()
    tables: dict[str, list[tuple[str, str, str]]] = {}
    for k in ORDER:
        if not sets.get(k):
            b.errors.append(f"{NAME_KO[k]} 묶음 폴더가 없습니다(.foreman/docs.toml [sets] 또는 notion.toml src)")
            continue
        rs, skipped = rows(sets[k], pieces.get(k, []), bodies)
        tables[k] = rs
        if skipped:
            b.notes.append(f"{NAME_KO[k]}: 번호가 없어 표에 넣지 않은 파일 {len(skipped)}개({', '.join(skipped[:5])})")
        if not rs:
            b.errors.append(f"{NAME_KO[k]} 묶음({sets[k]})에 번호 붙은 편이 없습니다")
        elif (t := top_piece(rs)):
            b.tops[k] = t
    first = next((p for n, _, p in tables.get("portfolio", []) if n == "00"), None)
    para = intro(bodies.get(first, "")) if first else None
    if "portfolio" in tables and not first:
        b.errors.append("포트폴리오 00편이 없어 소개 문단을 가져올 수 없습니다")
    elif first and not para:
        b.errors.append(f"{first}에 첫 # 줄 뒤 본문 문단이 없어 소개 문단을 가져올 수 없습니다")
    if b.errors:
        return b
    out = [TOP, f"# {title}", "", para or ""]
    for k in ORDER:
        out += ["", f"## {NAME_KO[k]}", ""]
        url = links.get(b.tops.get(k, ""))
        if url:
            out.append(f"[노션에서 보기]({url})")
        else:
            out.append(NO_LINK)
            b.notes.append(f"{NAME_KO[k]}: 맨 위 편 {b.tops.get(k)}의 노션 주소가 게시 기록에 없어 링크를 걸지 않았습니다")
        out += ["", "| 번호 | 제목 |", "|---|---|"]
        out += [f"| {n} | [{t.replace('|', chr(92) + '|')}]({p}) |" for n, t, p in tables[k]]
    b.text = "\n".join(out) + "\n"
    return b


def links_in(md: str) -> dict[str, str]:
    """README에 지금 걸린 노션 주소 {묶음: 주소}. 게시 기록을 못 읽을 때 점검이 이 값으로 나머지를 맞댄다."""
    out: dict[str, str] = {}
    cur = None
    names = {v: k for k, v in NAME_KO.items()}
    for ln in split(md):
        if ln.startswith("## "):
            cur = names.get(ln[3:].strip())
        elif cur and (m := LINK.match(ln.strip())):
            out.setdefault(cur, m["u"])
    return out


def diff(have: str, want: str) -> str | None:
    """다른 첫 줄 한 줄 설명. 같으면 None."""
    if have == want:
        return None
    h, w = have.split("\n"), want.split("\n")
    for i in range(max(len(h), len(w))):
        a = h[i] if i < len(h) else "(없음)"
        c = w[i] if i < len(w) else "(없음)"
        if a != c:
            return f"줄 {i + 1}: README 「{a[:60]}」, 만들 글 「{c[:60]}」"
    return "끝 줄바꿈이 다릅니다"


__all__ = ["Built", "NAME_KO", "NO_LINK", "ORDER", "PATH", "TOP", "build", "diff", "intro", "links_in", "number", "rows",
           "top_piece"]
