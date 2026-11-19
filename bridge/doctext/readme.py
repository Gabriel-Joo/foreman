"""README 생성(11-17 문서 정리 B, 사용자 지시). README는 「여기 무엇이 있는지」만 보이는 문지기이고, 파일 전체가 생성물이다.

들어가는 것 다섯, 이 차례로:
1. 제목: 저장소 이름(`.foreman/docs.toml` `[readme] title`, 없으면 그 저장소의 게시 프로젝트 이름)
1-1. 머리글(`[readme] header_file`을 적은 저장소만): 제목 줄 바로 뒤에 그 파일 글을 그대로 넣는다(배지, 링크, 줄바꿈을 고치지 않는다.
   앞뒤 빈 줄만 뗀다). 그 파일은 사람이 쓰는 원본이라 생성물이 아니다(`GENERATED`에 넣지 않는다). 파일이 없거나 읽지 못하거나
   공백뿐이면 만들지 않고 틀림으로 알린다(조용히 빈칸으로 두지 않는다, 11-19 사용자). 맨 위 주석이 어느 파일에서 왔는지 적는다
2. 소개 문단: 포트폴리오 00편(`portfolio/00_*.md`)의 첫 문단. 첫 # 줄 뒤에서 처음 나오는 본문 문단이다. 인용(`>`),
   절 제목, 그림, 표, 목록 줄은 건너뛴다. 글은 그대로 두고 근거 표시만 뗀다(노션 판과 같은 `STRIP`). 문단 전체를 굵은 글 하나로 감쌌으면 그 표시만 벗긴다
3. 포트폴리오와 기술문서 원고 편 목록: 표 칸은 번호, 제목(편 파일 링크), 하위. 번호는 첫 # 줄 앞 번호(`03 `, `02-01 `),
   없으면 파일 이름 번호(`03_x.md`는 03, `01_a/02_b.md`는 01-02). 제목은 번호를 뗀 첫 # 줄. 표에는 맨 위 편만 넣고,
   하위 편이 있는 편은 「하위 N」을 하위 칸에 적는다(11-17 사용자: README는 길 안내라 50줄이면 목차가 된다. 하위 편은
   노션에서 본다). 맨 위 편이 없는 하위 편과 번호가 없는 파일은 표에 넣지 않고 알린다
4. 노션 링크: 묶음마다 맨 위 편(번호가 가장 앞인 편)의 게시 주소를 「노션에서 보기」로 건다. 주소는 부르는 쪽이 넘긴다
   (`tools/docs.py`가 게시 기록 `doc_publish`에서 읽는다). 주소가 없으면 링크를 걸지 않고 「아직 노션에 올라가지 않았습니다」를
   쓰고 알린다(빈 주소를 걸거나 조용히 넘어가지 않는다)
5. docs 차례(`[readme] docs = true`인 저장소만, 11-17 사용자): docs 묶음 폴더(`[sets] docs`) 바로 아래 `*.md`(그 폴더의
   `README.md`와 하위 폴더는 빼고) 한 줄씩, 칸은 문서(파일 링크), 제목, 요약. **상태 칸은 두지 않는다**(손으로 쓴 차례의 상태 칸이
   늘 낡았다). 제목은 첫 # 줄, 없으면 파일 이름. 요약은 저장소마다 꼴이 달라 `[readme] docs_summary`로 고른다:
   `"para"`(기본, 첫 # 줄 뒤 다음 절 제목 전의 첫 문단), `"heading:<글>"`(그 글이 든 절 제목 아래 첫 문단, 런슈즈 「한 줄 요약」),
   `"none"`. `docs_skip`에 적은 머리(예: `"상태:"`)로 시작하는 인용 문단은 건너뛴다. 문단의 첫 문장만, 120자까지.
   `docs_numbered_only = true`면 `NN_`로 시작하는 파일만 넣는다(기본 false)

README 칸에 옮기는 제목과 요약에서는 em dash와 가운뎃점을 쉼표로 바꾼다(백틱 안은 그대로). README 새 줄도 줄표 검사를 받는데
원본 문서의 옛 기호를 그대로 옮기면 생성물이 그 검사에 걸린다. 원본 문서는 바꾸지 않는다.

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
DOCS_HEAD = "문서"                                      # docs 차례 절 제목
SUMMARY_MAX = 120
WHOLE_BOLD = re.compile(r"^\*\*((?:(?!\*\*).)+)\*\*$")   # 굵은 글 하나가 문단 전체인 꼴
HEADING = re.compile(r"^#{1,6}\s")
SKIP_LINE = re.compile(r"^\s*(!\[|\||[-*+]\s|\d+\.\s|---|<)")
SENTENCE = re.compile(r"^(.+?[.!?](?:\*\*|[)」\"'])*)(?=\s|$)")
TICKS = re.compile(r"(`[^`]*`)")
DASHDOT = re.compile(r"\s*[—·]\s*")


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
    text = " ".join(para)
    # 문단 전체를 한 번에 감싼 굵은 표시만 벗긴다(굵은 글은 문단 안에서 한두 곳을 짚는 것이다). 일부만 굵은 글은 그대로 둔다
    m = WHOLE_BOLD.match(text)
    return (m.group(1).strip() if m else text) or None


def cell(s: str) -> str:
    """README 표 칸 글: em dash와 가운뎃점을 쉼표로(백틱 안은 그대로), `|`는 `\\|`로."""
    parts = TICKS.split(s)
    parts = [p if p.startswith("`") else DASHDOT.sub(", ", p) for p in parts]
    return "".join(parts).strip(" ,").replace("|", "\\|")


def doc_summary(md: str, mode: str = "para", skip: tuple[str, ...] = ()) -> str:
    """docs 문서 한 편의 한 줄 요약(첫 문장, SUMMARY_MAX자). 찾지 못하면 빈 글.
    para: 첫 # 줄 뒤(없으면 맨 앞부터) 다음 절 제목 전의 첫 문단. heading:<글>: 그 글이 든 절 제목 아래 첫 문단.
    인용 문단은 `>`를 떼고 본문으로 읽되, skip 머리로 시작하는 인용 문단과 인용 안 절 제목 줄은 건너뛴다."""
    if mode == "none":
        return ""
    lines = split(md)
    if mode.startswith("heading:"):
        want = mode[len("heading:"):]
        start = next((i for i, k in walk(lines) if k == TEXT and HEADING.match(lines[i].strip()) and want in lines[i]), None)
        if start is None:
            return ""
    else:
        h, _ = first_h1(md)
        start = -1 if h is None else h
    para: list[str] = []
    skipping = False
    for i, kind in walk(lines, start + 1):
        s = lines[i].strip()
        if kind != TEXT or not s:
            if para:
                break
            skipping = False
            continue
        if HEADING.match(s):
            break
        quoted = s.startswith(">")
        body = s.lstrip(">").strip() if quoted else s
        if not para and (skipping or (quoted and any(body.startswith(p) for p in skip))):
            skipping = True
            continue
        if not body or body.startswith("#") or SKIP_LINE.match(body):
            if para:
                break
            continue
        para.append(STRIP.sub("", body).strip())
    text = re.sub(r"\s+", " ", " ".join(para)).strip()
    if (m := SENTENCE.match(text)):
        text = m.group(1)
    if len(text) > SUMMARY_MAX:
        text = text[:SUMMARY_MAX - 1].rstrip() + "…"
    return text


def doc_rows(folder: str, paths: list[str], bodies: dict[str, str], mode: str = "para",
             skip: tuple[str, ...] = (), numbered_only: bool = False) -> list[tuple[str, str, str]]:
    """docs 차례 줄 [(경로, 제목, 요약)]: 폴더 바로 아래 `*.md`(그 폴더의 README.md는 뺀다), 파일 이름 차례.
    numbered_only면 `NN_`로 시작하는 파일만 넣는다(`[readme] docs_numbered_only`)."""
    out: list[tuple[str, str, str]] = []
    for p in sorted(paths):
        rel = p[len(folder):]
        if "/" in rel or not rel.endswith(".md") or rel == "README.md":
            continue
        if numbered_only and not PART.match(rel):
            continue
        md = bodies.get(p, "")
        title = STRIP.sub("", first_h1(md)[1] or "").strip() or rel[:-3]
        out.append((p, title, doc_summary(md, mode, skip)))
    return out


def top_piece(rs: list[tuple[str, str, str]]) -> str | None:
    """묶음 맨 위 편: 하위 편이 아닌 것 가운데 번호가 가장 앞인 편."""
    tops = [r for r in rs if "-" not in r[0]]
    return min(tops)[2] if tops else None


def top_rows(rs: list[tuple[str, str, str]]) -> tuple[list[tuple[str, str, str, int]], list[str]]:
    """(맨 위 편 [(번호, 제목, 경로, 하위 편 수)], 맨 위 편이 없어 셀 곳이 없는 하위 편 경로)."""
    tops = [(n, t, p, 0) for n, t, p in rs if "-" not in n]
    idx = {n: i for i, (n, _, _, _) in enumerate(tops)}
    orphans: list[str] = []
    for n, _, p in rs:
        if "-" not in n:
            continue
        i = idx.get(n.split("-")[0])
        if i is None:
            orphans.append(p)
            continue
        a, b, c, k = tops[i]
        tops[i] = (a, b, c, k + 1)
    return tops, orphans


def top_comment(header_path: str | None = None) -> str:
    """생성물 맨 위 주석. 머리글 파일이 있으면 어느 파일에서 왔는지 한 마디 더한다."""
    if not header_path:
        return TOP
    return TOP[:-len(" -->")] + f". 제목 바로 아래 머리글은 `{header_path}` 파일 글을 그대로 넣은 것이다 -->"


def build(title: str, sets: dict[str, str], pieces: dict[str, list[str]], bodies: dict[str, str],
          links: dict[str, str | None], docs: list[tuple[str, str, str]] | None = None,
          header: tuple[str, str | None] | None = None) -> Built:
    """README 글 전체. sets는 {묶음: 폴더}(없는 묶음은 빠진다), pieces는 {묶음: 편 경로}, links는 {편 경로: 노션 주소}.
    docs는 docs 차례 줄(doc_rows). None이면 그 절을 넣지 않는다(`[readme] docs`가 꺼진 저장소).
    header는 (머리글 파일 경로, 그 글). 글이 None(파일이 없거나 못 읽음)이거나 공백뿐이면 만들지 않고 틀림으로 알린다.
    None이면 머리글 칸이 꺼진 것이다."""
    b = Built()
    head = ""
    if header is not None:
        hp, ht = header
        if ht is None:
            b.errors.append(f"머리글 파일 {hp}를 읽지 못했습니다(없거나 읽을 수 없음, .foreman/docs.toml [readme] header_file)")
        elif not ht.strip():
            b.errors.append(f"머리글 파일 {hp}가 비어 있습니다(칸을 쓰려면 글을 채우고, 안 쓰려면 header_file 줄을 지웁니다)")
        else:
            head = ht.strip("\n")
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
    out = [top_comment(header[0] if header else None), f"# {title}", ""]
    if head:
        out += [head, ""]
    out.append(para or "")
    for k in ORDER:
        out += ["", f"## {NAME_KO[k]}", ""]
        url = links.get(b.tops.get(k, ""))
        if url:
            out.append(f"[노션에서 보기]({url})")
        else:
            out.append(NO_LINK)
            b.notes.append(f"{NAME_KO[k]}: 맨 위 편 {b.tops.get(k)}의 노션 주소가 게시 기록에 없어 링크를 걸지 않았습니다")
        tops, orphans = top_rows(tables[k])
        if orphans:
            b.notes.append(f"{NAME_KO[k]}: 맨 위 편이 없어 하위로 세지 못한 편 {len(orphans)}개({', '.join(orphans[:5])})")
        out += ["", "| 번호 | 제목 | 하위 |", "|---|---|---|"]
        out += [f"| {n} | [{cell(t)}]({p}) | {f'하위 {c}' if c else ''} |" for n, t, p, c in tops]
    if docs is not None:
        if not docs:
            b.notes.append("docs 차례에 넣을 문서가 없습니다")
        out += ["", f"## {DOCS_HEAD}", "", "| 문서 | 제목 | 요약 |", "|---|---|---|"]
        out += [f"| [{p.rsplit('/', 1)[-1]}]({p}) | {cell(t)} | {cell(s)} |" for p, t, s in docs]
        empty = [p for p, _, s in docs if not s]
        if empty:
            b.notes.append(f"docs 차례: 요약을 찾지 못한 문서 {len(empty)}개({', '.join(empty[:5])})")
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


GENERATED = (PATH,)       # 생성기가 쓰는 파일 전부(저장소 맨 위 기준 경로). 덮기 검사가 대상에서 뺀다. 새 생성물은 여기에 더한다


__all__ = ["Built", "DOCS_HEAD", "GENERATED", "NAME_KO", "NO_LINK", "ORDER", "PATH", "TOP", "build", "cell", "diff", "doc_rows",
           "doc_summary", "intro", "links_in", "number", "rows", "top_comment", "top_piece", "top_rows"]
