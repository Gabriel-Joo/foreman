"""화면 말 · 문서 인용 · 호버 약속이 어긋나는 것을 기계로 찾는다(11-15, log/foreman-6_screen_text_sync_proposal_20261115.md).

세 가지를 본다. 목록은 tests/data/screen_words.toml 하나에 있다.
- 안 A 바꾼 이름: 화면 말을 바꿨으면 옛 이름이 코드 문자열(주석 · 로그 글 · docstring 뺌)에 남으면 안 된다.
  범위가 「화면과 문서 인용」이면 문서(docs/*.md · README.md · 원고 notion/**/*.md · portfolio/*.md)의 인용(「…」 · "…" · […]) 안에도 남으면 안 된다
- 안 B 문서 [버튼]: 문서가 [버튼 이름]으로 인용한 글은 지금 코드에 있어야 한다
- 안 D 호버 약속: 호버 설명이 끌기 · 더블클릭 · 키 · 휠 같은 조작을 약속하면 약속 목록에 있어야 한다

문서 줄에 이력 표시(전 이름 · 바뀜 · → · ~~ 등)가 있으면 옛 이름을 적어도 된다(「무엇이 바뀌었는지」를 적는 줄이다).
걸린 문서는 이름을 바꾼 코더가 같은 브랜치에서 고친다(11-17 사용자 지시 21. 전에는 docs/operations.md, docs/style_guide.md, 원고를
코더가 고치지 않고 서기 몫에 적었다). 고칠 수 없는 까닭이 있을 때만 [[scribe]] 「서기 몫」에 적으면 통과하고, 서기가 맞춘 뒤
그 줄을 지운다(남은 수는 pytest 요약에 찍힌다).

손으로 돌리기: .venv/bin/python tests/screen_words.py [저장소 뿌리]
"""
from __future__ import annotations

import ast
import re
import sys
import time
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 손으로 돌릴 때도 bridge를 가져온다
from bridge.evidence import MARK  # noqa: E402

DATA = "tests/data/screen_words.toml"
# 서기 몫에 적을 수 있는 문서. 11-17부터 코더도 고친다(사용자 지시 21). 고칠 수 없는 까닭이 있을 때만 서기 몫에 적는다
SCRIBE_DOCS = ("docs/operations.md", "docs/style_guide.md")   # 고치면 합치기 카드가 사람에게 간다(config/handoff.toml human_paths)
MANUSCRIPT_DIRS = ("notion/", "portfolio/")                    # 원고(11-15)


def scribe_owned(path: str) -> bool:
    return path in SCRIBE_DOCS or path.startswith(MANUSCRIPT_DIRS)
SCOPES = ("화면", "화면과 문서 인용")

# 이력 표시 — 421 제안 그대로에 「전에는」 · 「전 [」 · 「11-NN 전」을 더했다(log/foreman-4_screen_words_test_20261115.md)
HIST = re.compile(r"~~|전 이름|\(전 |전 「|전 \[|전에는|옛 |지웠다|지운 |뺐다|바뀜|바뀌었다|바꿨다|→|였다|이었다|되돌|"
                  r"11-\d\d 전|에서 바뀜")
# 호버 약속 낱말(안 D). 「누르면 …」은 넣지 않는다(기능 시험이 다룬다)
ACTS = re.compile(r"더블\s?클릭|두 번 누르|끌어|↑↓|Esc|Enter|Ctrl|휠")
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


# ── 코드에서 글 뽑기 ──────────────────────────────────────────

def py_strings(src: str) -> list[tuple[int, str]]:
    """파이썬 문자열 상수 중 화면에 갈 수 있는 것. docstring(문장으로 홀로 선 문자열)과 로그 호출 인자는 뺀다."""
    tree = ast.parse(src)
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            skip.add(id(node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS:
            owner = node.func.value
            name = owner.id if isinstance(owner, ast.Name) else owner.attr if isinstance(owner, ast.Attribute) else ""
            if "log" in name.lower():
                for sub in ast.walk(node):
                    skip.add(id(sub))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


_CODE_JUMP = re.compile(r"[\"'`/{}]")
_TMPL_JUMP = re.compile(r"\\.|`|\$\{", re.S)
_REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WORDS = ("return", "typeof", "case", "of", "in", "delete", "void", "yield", "await")


def _regex_ok(src: str, i: int) -> bool:
    """i의 '/'가 정규식 시작인가 — 앞의 공백 아닌 글자로 가른다."""
    j = i - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    if j < 0 or src[j] in _REGEX_BEFORE:
        return True
    k = j
    while k >= 0 and (src[k].isalnum() or src[k] == "_"):
        k -= 1
    return src[k + 1:j + 1] in _REGEX_WORDS


def js_scan(src: str) -> tuple[list[tuple[int, str]], str]:
    """JS를 훑어 (문자열 조각들, 주석을 뺀 코드)를 준다. 템플릿은 `${…}` 밖 글을 조각으로, 안은 다시 코드로 훑는다."""
    strs: list[tuple[int, str]] = []
    keep: list[str] = []
    n = len(src)
    i = 0
    depth: list[int] = []   # 템플릿 ${ 안에서 연 { 수
    in_tmpl = False
    tmpl_start = 0

    def line(at: int) -> int:
        return src.count("\n", 0, at) + 1

    while i < n:
        if in_tmpl:
            m = _TMPL_JUMP.search(src, i)
            if not m:
                break
            tok = m.group()
            if tok.startswith("\\"):
                i = m.end()
                continue
            strs.append((line(tmpl_start), src[tmpl_start:m.start()]))
            keep.append(src[tmpl_start:m.end()])
            i = m.end()
            if tok == "`":
                in_tmpl = False
            else:
                depth.append(0)
                in_tmpl = False
            continue
        m = _CODE_JUMP.search(src, i)
        if not m:
            keep.append(src[i:])
            break
        j = m.start()
        keep.append(src[i:j])
        c = src[j]
        if c in "\"'":
            k = j + 1
            while k < n and src[k] != c and src[k] != "\n":
                k += 2 if src[k] == "\\" else 1
            strs.append((line(j), src[j + 1:k]))
            keep.append(src[j:k + 1])
            i = k + 1
        elif c == "`":
            keep.append("`")
            in_tmpl, tmpl_start, i = True, j + 1, j + 1
        elif c == "{":
            if depth:
                depth[-1] += 1
            keep.append(c)
            i = j + 1
        elif c == "}":
            keep.append(c)
            i = j + 1
            if depth:
                if depth[-1] == 0:
                    depth.pop()
                    in_tmpl, tmpl_start = True, i
                else:
                    depth[-1] -= 1
        else:  # '/'
            nxt = src[j + 1] if j + 1 < n else ""
            if nxt == "/":
                k = src.find("\n", j)
                i = n if k < 0 else k
            elif nxt == "*":
                k = src.find("*/", j + 2)
                i = n if k < 0 else k + 2
            elif _regex_ok(src, j):
                k, cls = j + 1, False
                while k < n and src[k] != "\n":
                    ch = src[k]
                    if ch == "\\":
                        k += 2
                        continue
                    if ch == "[":
                        cls = True
                    elif ch == "]":
                        cls = False
                    elif ch == "/" and not cls:
                        break
                    k += 1
                keep.append(src[j:k + 1])
                i = k + 1
            else:
                keep.append("/")
                i = j + 1
    return strs, "".join(keep)


_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_STYLE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_SCRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)


def _blank(m: re.Match) -> str:
    """지운 자리에 줄 수만 남긴다(뒤 줄 번호가 밀리지 않게)."""
    return "\n" * m.group().count("\n")


def html_scan(src: str) -> tuple[list[tuple[int, str]], str]:
    """HTML — 주석(HTML · <style> 안 CSS)을 빼고, 안의 <script>는 JS로 훑고, 나머지(태그 · 속성 · 글)는 줄마다 한 조각으로 본다."""
    src = _HTML_COMMENT.sub(_blank, src)
    src = _STYLE.sub(lambda m: m.group(1) + _CSS_COMMENT.sub(_blank, m.group(2)) + m.group(3), src)
    strs: list[tuple[int, str]] = []
    keep: list[str] = []
    pos = 0
    for m in _SCRIPT.finditer(src):
        outside = src[pos:m.start(2)]
        base = src.count("\n", 0, pos)
        strs += [(base + k + 1, ln) for k, ln in enumerate(outside.split("\n"))]
        keep.append(outside)
        s2, k2 = js_scan(m.group(2))
        off = src.count("\n", 0, m.start(2))
        strs += [(ln + off, t) for ln, t in s2]
        keep.append(k2)
        pos = m.start(3)
    base = src.count("\n", 0, pos)
    strs += [(base + k + 1, ln) for k, ln in enumerate(src[pos:].split("\n"))]
    keep.append(src[pos:])
    return strs, "".join(keep)


@dataclass
class Code:
    strings: list[tuple[str, int, str]] = field(default_factory=list)   # (파일, 줄, 글)
    text: dict[str, str] = field(default_factory=dict)                  # 파일 → 주석 뺀 코드(`${` · `}` 지움)


def code_files(root: Path) -> list[Path]:
    fs = list((root / "bridge/static").glob("*.html")) + list((root / "bridge/static/js").glob("*.js"))
    fs += [p for p in (root / "bridge").rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(fs)


def load_code(root: Path) -> Code:
    out = Code()
    for p in code_files(root):
        rel = p.relative_to(root).as_posix()
        src = p.read_text(encoding="utf-8")
        if p.suffix == ".py":
            strs = py_strings(src)
            kept = "\n".join(s for _, s in strs)
        elif p.suffix == ".js":
            strs, kept = js_scan(src)
        else:
            strs, kept = html_scan(src)
        out.strings += [(rel, ln, s) for ln, s in strs if s]
        out.text[rel] = kept.replace("${", "").replace("}", "")
    return out


# ── 문서 줄 ─────────────────────────────────────────────────

def doc_files(root: Path) -> list[Path]:
    """docs/*.md · README.md · 원고(11-15 — notion/ 아래 모든 .md, portfolio/*.md). 원고에 옛 화면 이름이 남으면 사람이 읽는
    노션 · 포트폴리오에 그대로 나간다."""
    fs = sorted((root / "docs").glob("*.md"))
    if (root / "README.md").exists():
        fs.append(root / "README.md")
    fs += sorted((root / "notion").rglob("*.md")) + sorted((root / "portfolio").glob("*.md"))
    return fs


def doc_lines(root: Path) -> list[tuple[str, int, str]]:
    """문서의 (파일, 줄 번호, 줄). ``` 울타리 안은 뺀다(코드 · 명령 견본)."""
    out = []
    for p in doc_files(root):
        rel = p.relative_to(root).as_posix()
        fence = False
        for i, ln in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if ln.lstrip().startswith("```"):
                fence = not fence
                continue
            if not fence:
                out.append((rel, i, ln))
    return out


_QUOTE = re.compile(r"「[^」\n]*」|\"[^\"\n]*\"|“[^”\n]*”|\[[^\[\]\n]*\]")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_BUTTON = re.compile(r"\[([^\[\]\n]{1,40})\](?!\()")
_REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S")


def buttons_in(line: str) -> list[str]:
    """문서 줄의 [버튼] 인용. 링크 · 근거 표시([log:…] [c:…])) · 체크칸 · 코드 안 괄호는 뺀다."""
    if _REF_DEF.match(line):
        return []
    line = _INLINE_CODE.sub("", line)
    out = []
    for m in _BUTTON.finditer(line):
        q = m.group(1).strip()
        # 근거 표시 이름(c · t · log · docs · code)은 bridge/evidence.py의 MARK 한 곳에서 가져온다
        if not q or MARK.match(f"[{q}]") or q in ("x", "X", " "):
            continue
        out.append(q)
    return out


_PLACE = re.compile(r"<[^>]*>|…|(?<![A-Za-z])[A-Z](?![A-Za-z])|\d+(?::\d+)?")


def quote_pattern(q: str) -> re.Pattern:
    """[버튼] 인용을 코드에 댈 정규식 — 낱자 대문자(N · M) · … · <…> · 숫자 · HH:MM은 아무 글."""
    parts, pos = [], 0
    for m in _PLACE.finditer(q):
        parts.append(re.escape(q[pos:m.start()]))
        parts.append(r"[^\n]{0,40}?")
        pos = m.end()
    parts.append(re.escape(q[pos:]))
    return re.compile("".join(parts))


# ── 판정 ────────────────────────────────────────────────────

def _at(line: int, s: str, k: int) -> int:
    """여러 줄 조각 s의 k번째 글자가 있는 줄."""
    return line + s.count("\n", 0, max(k, 0))


_ATTR_TIP = re.compile(r"""\b(?:title|data-tip)=(["'])(.*?)\1""", re.S)


def hover_texts(s: str) -> list[tuple[int, str]]:
    """조각 안의 호버 글 — HTML 속성(title · data-tip)이 있으면 그 값들, 없으면 조각 전체(상수 · 함수 인자)."""
    attrs = [(m.start(2), m.group(2)) for m in _ATTR_TIP.finditer(s)]
    if not attrs:
        return [(0, s)]
    # `title="${제목} — 설명"`처럼 속성이 ${…}에서 끊기면 조각이 속성 가운데서 시작한다 — 첫 따옴표 앞도 본다
    head = re.split(r"[\"']", s, maxsplit=1)[0]
    return ([(0, head)] if " — " in head else []) + attrs


@dataclass
class Hit:
    kind: str      # rename-code · rename-doc · button · promise
    where: str     # 파일:줄
    text: str      # 걸린 글(옛 이름 · 인용 · 호버)
    detail: str    # 줄 · 고칠 말

    @property
    def file(self) -> str:
        return self.where.rsplit(":", 1)[0]


@dataclass
class Report:
    fails: list[Hit] = field(default_factory=list)
    scribe: list[Hit] = field(default_factory=list)          # 서기 몫 목록으로 통과한 것
    stale: list[str] = field(default_factory=list)           # 지금은 쓸모없는 목록 줄(지워야 함)
    promises: int = 0
    untested: int = 0
    partial: int = 0
    seconds: float = 0.0


def load_data(root: Path) -> dict:
    p = root / DATA
    return tomllib.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def check(root: Path) -> Report:
    t0 = time.perf_counter()
    root = Path(root)
    data = load_data(root)
    code = load_code(root)
    docs = doc_lines(root)
    rep = Report()
    found: list[Hit] = []

    # 안 A
    cexc = data.get("code_exception", [])
    used_cexc: set[int] = set()
    for r in data.get("rename", []):
        old, new = r["old"], r["new"]
        for f, ln, s in code.strings:
            k = s.find(old)
            if k < 0 or (r.get("whole") and s.strip() != old):    # whole: 문자열 전체가 그 낱말일 때만(11-15 역할 이름 「점검」)
                continue
            ex = [j for j, e in enumerate(cexc) if e["file"] == f and e["old"] == old and e["near"] in s]
            if ex:
                used_cexc.update(ex)
                continue
            near = s[max(0, k - 30):k + len(old) + 30].replace("\n", " ").strip()
            found.append(Hit("rename-code", f"{f}:{_at(ln, s, k)}", old, f"「…{near}…」 → 「{new}」"))
        if r.get("scope") == "화면과 문서 인용":
            for f, ln, line in docs:
                if old in line and not HIST.search(line) and any(old in q.group() for q in _QUOTE.finditer(line)):
                    found.append(Hit("rename-doc", f"{f}:{ln}", old, f"문서 인용 → 「{new}」: {line.strip()[:100]}"))
    for j, e in enumerate(cexc):
        if j not in used_cexc:
            rep.stale.append(f"[[code_exception]] {e['file']} 「{e['old']}」 「{e['near']}」 — 이제 걸리지 않습니다. 이 줄을 지웁니다.")

    # 안 B
    exc = {(e["doc"], e["quote"]) for e in data.get("button_exception", [])}
    used_exc: set[tuple[str, str]] = set()
    corpus = "\n".join(code.text.values()).replace("＋", "+")   # 버튼 「＋ 세션」을 문서는 [+ 세션]으로 쓴다
    cache: dict[str, bool] = {}
    for f, ln, line in docs:
        if HIST.search(line):
            continue
        for q in buttons_in(line):
            if q not in cache:
                qq = q.replace("＋", "+")
                cache[q] = qq in corpus or bool(quote_pattern(qq).search(corpus))
            if cache[q]:
                continue
            if (f, q) in exc:
                used_exc.add((f, q))
                continue
            found.append(Hit("button", f"{f}:{ln}", q, line.strip()[:100]))
    for e in data.get("button_exception", []):
        if (e["doc"], e["quote"]) not in used_exc:
            rep.stale.append(f"[[button_exception]] {e['doc']} [{e['quote']}] — 이제 걸리지 않습니다(문서에서 빠졌거나 코드에 생김). 이 줄을 지웁니다.")

    # 안 D
    prom = data.get("promise", []) + data.get("promise_skip", [])
    used_prom: set[int] = set()
    for f, ln, s in code.strings:
        for k, tip in hover_texts(s):
            for piece in re.split(r"\\n|\n", tip):
                if " — " not in piece:
                    continue
                title, desc = piece.split(" — ", 1)
                act = ACTS.search(desc)
                if len(title) > 40 or not act:
                    continue
                hit = [j for j, p in enumerate(prom) if p["file"] == f and p["tip"] in piece]
                if hit:
                    used_prom.update(hit)
                    continue
                found.append(Hit("promise", f"{f}:{_at(ln, s, k)}", piece.strip()[:120], act.group()))
    for k, p in enumerate(prom):
        if k not in used_prom:
            rep.stale.append(f"[[promise]] {p['file']} 「{p['tip']}」 — 그 호버가 없거나 조작을 더 말하지 않습니다. 이 줄을 지웁니다.")
    rep.promises = len(data.get("promise", []))
    rep.untested = sum(1 for p in data.get("promise", []) if not p.get("test"))
    rep.partial = sum(1 for p in data.get("promise", []) if p.get("test") and p.get("gap"))

    # 서기 몫
    scribe = data.get("scribe", [])
    used_sc: set[int] = set()
    for h in found:
        if h.kind in ("rename-doc", "button") and scribe_owned(h.file):
            k = next((k for k, s in enumerate(scribe) if s["doc"] == h.file and s["text"] == h.text), None)
            if k is not None:
                used_sc.add(k)
                rep.scribe.append(h)
                continue
        rep.fails.append(h)
    for k, s in enumerate(scribe):
        if k not in used_sc:
            rep.stale.append(f"[[scribe]] {s['doc']} 「{s['text']}」 — 서기가 맞췄습니다(이제 걸리지 않음). 이 줄을 지웁니다.")
    rep.seconds = time.perf_counter() - t0
    return rep


HOW = {
    "rename-code": ("화면 글을 새 이름으로 고칩니다. 화면에 안 나가는 글(세션 · claude -p에 넣는 프롬프트처럼 문서 말을 쓰는 곳)이면 "
                    f"{DATA} [[code_exception]]에 한 줄(file · old · near = 그 문자열 안 한 조각 · why)"),
    "rename-doc": "문서 인용을 새 이름으로 고칩니다. 바뀐 이력을 적는 줄이면 「(전 이름 「…」)」 · 「바뀜」 · 「→」처럼 이력 표시를 넣습니다",
    "button": ("코드에 그 버튼 글이 없습니다. 버튼 이름이 바뀌었으면 문서를 지금 이름으로 고치고 "
               f"{DATA} [[rename]]에 한 줄(old · new · scope · commit)을 적습니다. "
               f"버튼이 아닌 대괄호 · 만들지 않은 계획이면 [[button_exception]]에 한 줄(doc · quote · why)"),
    "promise": (f"호버가 조작(끌기 · 더블클릭 · 키 · 휠)을 약속합니다. {DATA} [[promise]]에 한 줄(file · tip · acts · test, "
                "시험이 없으면 test = \"\")을 적습니다. CC에 보내는 키를 설명할 뿐이면 [[promise_skip]](file · tip · why)"),
}


def explain(rep: Report) -> str:
    out = []
    for kind in ("rename-code", "rename-doc", "button", "promise"):
        hs = [h for h in rep.fails if h.kind == kind]
        if not hs:
            continue
        out.append(f"■ {kind} {len(hs)}곳 — 고치는 법: {HOW[kind]}")
        out += [f"  {h.where}  「{h.text}」  {h.detail}" for h in hs]
        if kind in ("rename-doc", "button") and any(scribe_owned(h.file) for h in hs):
            out.append(f"  ※ {', '.join(SCRIBE_DOCS)}, 원고({', '.join(MANUSCRIPT_DIRS)})도 이름을 바꾼 코더가 같은 브랜치에서 고칩니다"
                       f"(앞의 둘은 고치면 합치기 카드가 사람에게 갑니다). 고칠 수 없는 까닭이 있을 때만 {DATA} [[scribe]]에 "
                       "한 줄(doc, text = 걸린 글)을 적고 그 까닭을 보고합니다. 서기가 맞춘 뒤 지웁니다")
    if rep.stale:
        out.append("■ 지금은 쓸모없는 목록 줄 — 지웁니다")
        out += [f"  {s}" for s in rep.stale]
    return "\n".join(out)


def summary(rep: Report) -> str:
    return (f"화면 말 시험: 서기 몫 {len(rep.scribe)}줄 남음(docs/operations.md · style_guide.md · 원고 notion/ · portfolio/), "
            f"호버 약속 {rep.promises}곳 중 시험 없음 {rep.untested} · 일부만 {rep.partial}, {rep.seconds:.2f}초")


LAST: Report | None = None   # 이 저장소를 본 결과 — conftest가 pytest 요약에 남은 수를 찍는다


@lru_cache(maxsize=4)
def check_cached(root: str) -> Report:
    return check(Path(root))


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
    r = check(root)
    print(explain(r) or "걸린 것 없음")
    for h in r.scribe:
        print(f"  (서기 몫) {h.where} 「{h.text}」")
    print(summary(r))
    sys.exit(1 if r.fails or r.stale else 0)
