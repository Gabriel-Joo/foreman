"""새 줄의 em dash와 가운뎃점(11-17 문서 도구 합치기 4단계, `docs/manuscript_rules.md` 「1.」 「6.」). 읽기만 한다.

기준 커밋(저장소마다 `.foreman/docs.toml` `[check] dashdot_base`) 뒤로 더해지거나 고쳐진 줄만 본다(`git diff 기준`, 작업 트리와
추적하지 않는 파일까지. rev를 주면 그 커밋까지). 이미 있던 줄은 세지 않는다.
옮긴 줄(근거 표시만 떼면 지운 줄과 글이 똑같은 더한 줄)은 새 줄이 아니다(`removed_pool`, `same_text`).
고친 덩어리는 지운 줄과 더한 줄의 기호 수를 맞대어 늘어난 기호만 건다(옛 줄을 고치기만 해도 옛 기호를 다 걷어야 하면
11-17 하루치(커밋 41개) 82건 가운데 57건이 그런 줄이라 사람이 시험을 무시하게 된다. `log/foreman-4_manuscript_rules_20261117.md`).
기준 커밋 뒤 새 문서 줄을 고르는 길(`new_doc_rows`)은 문서 점검의 「」 없는 편 사이 참조 검사도 함께 쓴다(그쪽 기준 커밋은 `xref_base`).

- 문서: 문서 묶음 폴더(docs, notion, portfolio. 저장소 설정의 [sets]) 아래 `*.md`와 맨 위 `README.md`, `CLAUDE.md`.
  코드 울타리와 HTML 주석 안은 보지 않는다
- 코드 주석: `.py`(`#` 주석과 문자열만으로 된 문장, 곧 독스트링), `.js`와 `.css`(`//`, `/* */`), `.toml`과 `.sh`(`#`)
- 세지 않는 것: 백틱 안, 「」와 『』와 큰따옴표 안(화면 글과 절 제목 인용), 기호 하나만 괄호로 감싼 것
- 보지 않는 곳: 기록 폴더(FOREMAN `log/`, 저장소 설정의 records), 저장소 설정의 `not_code`에 드는 파일(추적하는 파일과 추적하지 않는
  파일 모두. 덮기 검사와 같은 `config.not_code_match`, `.md`만 뺀다), 그 밖의 `*.md`와 확장자. 코드의 문자열(화면 글, 지시문)

표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import io
import re
import subprocess
import tokenize
from collections.abc import Callable
from pathlib import Path

from bridge.doctext.config import not_code_match
from bridge.doctext.lines import TEXT, walk
from bridge.doctext.repo import is_quoted, quoted_problem
from bridge.doctext.marks import STRIP

CHARS = {"—": "em dash", "·": "가운뎃점"}
DOC_DIRS = ("docs/", "notion/", "portfolio/")
ROOT_DOCS = ("README.md", "CLAUDE.md")          # 묶음 밖에서 보는 문서(11-17 사용자 결정, 맨 위 것만)
TOOL_DIRS = (".venv/", "node_modules/", ".tools/", ".worktrees/")
SKIP_DIRS = ("log/", *TOOL_DIRS)
CODE_EXT = (".py", ".js", ".css", ".toml", ".sh")
NO_BASE = "기준 커밋이 없어 줄표, 가운뎃점 검사를 하지 않았습니다(.foreman/docs.toml [check] dashdot_base)"

# 세지 않는 자리(인용과 코드). 줄에서 지운 뒤 기호를 찾는다
QUOTED = re.compile(r"`[^`]*`|「[^」]*」|『[^』]*』|\"[^\"]*\"|“[^”]*”|\([—·]\)")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class DashDotError(RuntimeError):
    pass


def _git(repo: str | Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=false", *a], capture_output=True, timeout=120)
    if r.returncode:
        raise DashDotError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout.decode(errors="replace")


def _git_z(repo: str | Path, *a: str) -> list[str]:
    """파일 목록 명령을 `-z`로 읽어 `\\0`로 나눈다(`bridge.doctext.repo.git_z`와 같다)."""
    return [x for x in _git(repo, a[0], "-z", *a[1:]).split("\0") if x]


def _header_path(line: str, prefix: str) -> str | None:
    """diff 머리(`--- a/…`, `+++ b/…`)의 파일 경로. 없는 파일(/dev/null)이면 None. 따옴표로 싼 경로는 이름을 읽을 수 없어 DashDotError."""
    p = line[4:]
    if is_quoted(p):
        raise DashDotError(quoted_problem(p))
    return p[2:] if p.startswith(prefix) else None


def wanted(path: str, doc_dirs: tuple[str, ...] = DOC_DIRS, skip: tuple[str, ...] = SKIP_DIRS,
           not_code: tuple[str, ...] = ()) -> str | None:
    """"doc", "code", 또는 None(보지 않는다). doc_dirs는 문서 묶음 폴더, skip은 기록 폴더와 도구 폴더.
    not_code는 저장소 설정의 `not_code`에서 `.md`를 뺀 무늬(`config.not_code_skip`). 덮기 검사와 같은 판정(`config.not_code_match`)으로
    거른다. 추적하는 파일과 추적하지 않는 파일이 모두 이 함수를 지나므로 둘 다 같은 거름을 받는다."""
    if path.startswith(skip) or (not_code and not_code_match(path, list(not_code))):
        return None
    if path.endswith(".md"):
        return "doc" if path.startswith(doc_dirs) or path in ROOT_DOCS else None
    if path.startswith(doc_dirs):
        return None
    return "code" if path.endswith(CODE_EXT) else None


Hunk = tuple[str, str | None, range, range]     # (새 경로, 옛 경로 또는 None, 옛 줄, 새 줄). 줄 번호는 1부터
Source = tuple[str, int]                        # (옛 경로, 옛 줄 번호). 지운 줄이 있던 자리


def same_text(line: str) -> str:
    """옮긴 줄을 맞댈 때의 글: 앞뒤 공백을 떼고 근거 표시(`[code:…]` 등 `marks.STRIP`, 앞 공백까지)만 뗀다.
    옮기면서 근거 표시를 덧붙이는 일이 흔해서(11-17 런슈즈 4e7dbca에서 걸린 줄 대부분) 표시만 다른 줄은 글이 같다고 본다.
    HTML 주석과 날짜 꼬리는 글이라 떼지 않는다. 표시를 뗀 본문이 한 글자라도 다르면 옮긴 줄이 아니다(11-17 사용자)."""
    return STRIP.sub("", line).strip()


def _has_char(text: str) -> bool:
    return any(ch in text for ch in CHARS)


def removed_pool(repo: str | Path, base: str, rev: str | None = None,
                 keep: Callable[[str], bool] = _has_char) -> dict[str, list[Source]]:
    """기준 커밋 뒤 브랜치 전체에서 지운 줄 가운데 기호(em dash, 가운뎃점)가 든 것: {`same_text`(앞뒤 공백과 근거 표시를 뗀 글): [지운 자리, ...]}.

    점검 밖 파일(기록 폴더, 코드, 설정)과 지워진 파일에서 지운 줄도 넣는다. 더한 줄이 이 글과 똑같으면 새 글이 아니라 옮긴 줄이다
    (11-17 런슈즈가 docs/09_chatbot_rag.md 안에서 절을 옮기기만 했는데 110건이 걸렸고, 곧 다른 파일 docs/archive/로 650줄을 더 옮긴다).
    덩어리 안에서만 맞대면 지운 쪽과 더한 쪽이 다른 덩어리나 다른 파일에 있는 옮김이 새 줄로 센다.
    git이 이름 바꿈과 복사로 알아본 파일은 안 바뀐 줄이 덩어리에 나오지 않아 여기에도 없다(hunks와 같은 diff 인자).
    keep은 모을 줄 거름이다. 기본은 기호가 든 줄, 「」 없는 편 사이 참조 검사(new_doc_rows)는 화살표가 든 줄."""
    pool: dict[str, list[Source]] = {}
    old: str | None = None
    left_old = left_new = row = 0
    for line in _git(repo, *_diff_args(base, rev)).splitlines():
        if left_old or left_new:                   # 덩어리 안: 줄 수를 세어 내용이 "--- "로 시작해도 머리로 읽지 않는다
            if line.startswith("-"):
                left_old -= 1
                text = same_text(line[1:])
                if old and keep(text):
                    pool.setdefault(text, []).append((old, row))
                row += 1
            elif line.startswith("+"):
                left_new -= 1
            continue
        if line.startswith("--- "):
            old = _header_path(line, "a/")
        elif m := HUNK.match(line):
            a, b, _, d = (int(x) if x is not None else 1 for x in m.groups())
            left_old, left_new, row = b, d, a
    return pool


def _diff_args(base: str, rev: str | None, only_wanted_kinds: bool = False) -> list[str]:
    # -C(기본 문턱 50%): 옮긴 뒤 옛 자리에 새 파일이 생겨도(11-17 README.md를 docs/00_design.md로 옮기고 README를 생성물로 만듦)
    # 옮긴 파일을 옛 파일의 복사로 알아본다. -M만 쓰면 옛 경로가 남아 있어 이름 바꿈이 아니게 되고, 옮긴 파일의 고친 줄이
    # 옛 줄과 맞대어지지 않아 기호 수가 같아도 새 줄로 걸린다(시험 test_moved_file_edited_line_is_compared_with_old_line).
    # 안 바뀐 옛 줄은 -C와 상관없이 옮긴 줄 풀이(removed_pool, 글이 같은 지운 줄)가 푼다. 그래서 한때 쓴 문턱 40%(`60d42c6`,
    # 설계 문서를 절반 넘게 줄여 유사도 42%일 때 안 바뀐 옛 줄 80건이 걸린 것을 막으려던 덧대기)는 걷었다. 지금 -C가 막는 것은
    # 복사로 알아본 파일에서 고친 줄의 새 기호뿐이고, 절반 넘게 줄인 파일의 고친 줄은 복사로 못 알아봐 건다(시험에서 고친다)
    args = ["diff", "--no-color", "--no-ext-diff", "-U0", "-M", "-C"]
    if only_wanted_kinds:
        args.append("--diff-filter=AMRC")      # 지운 파일은 새 줄을 내지 않는다. 지운 줄을 모으는 쪽은 이 거름을 쓰지 않는다
    return [*args, base, *([rev] if rev else [])]


def hunks(repo: str | Path, base: str, rev: str | None = None, doc_dirs: tuple[str, ...] = DOC_DIRS,
          skip: tuple[str, ...] = SKIP_DIRS, not_code: tuple[str, ...] = ()) -> list[Hunk]:
    """기준 커밋과 작업 트리(rev가 있으면 그 커밋) 사이에 바뀐 덩어리. 작업 트리면 추적하지 않는 파일은 통째로 새 덩어리 하나.
    base가 HEAD(또는 rev)의 조상이 아니면 DashDotError(조용히 0줄로 지나가지 않게)."""
    tip = rev or "HEAD"
    try:
        _git(repo, "merge-base", "--is-ancestor", base, tip)
    except DashDotError as e:
        raise DashDotError(f"기준 커밋 {base[:10]}이 {tip[:10]}의 조상이 아닙니다: {e}") from e
    out: list[Hunk] = []
    old: str | None = None
    cur: str | None = None
    for line in _git(repo, *_diff_args(base, rev, only_wanted_kinds=True)).splitlines():
        if line.startswith("--- "):
            old = _header_path(line, "a/")
        elif line.startswith("+++ "):
            p = _header_path(line, "b/")
            cur = p if p and wanted(p, doc_dirs, skip, not_code) else None
        elif cur and (m := HUNK.match(line)):
            a, b, c, d = (int(x) if x is not None else 1 for x in m.groups())
            out.append((cur, old, range(a, a + b), range(c, c + d)))
    if rev:
        return out
    for p in _git_z(repo, "ls-files", "--others", "--exclude-standard"):
        if wanted(p, doc_dirs, skip, not_code):
            try:
                n = len((Path(repo) / p).read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                continue
            out.append((p, None, range(0), range(1, n + 1)))
    return out


# ── 줄마다 볼 글: 문서는 울타리와 주석 밖 줄, 코드는 주석 부분 ──
def doc_parts(text: str) -> dict[int, str]:
    lines = text.splitlines()
    return {i + 1: lines[i] for i, kind in walk(lines) if kind == TEXT}


def _add(parts: dict[int, str], row: int, s: str) -> None:
    parts[row] = (parts.get(row, "") + " " + s).strip()


def py_parts(text: str) -> dict[int, str]:
    """`#` 주석과 문자열만으로 된 문장(독스트링). 토큰으로 못 읽는 파일은 `#` 뒤를 줄마다 본다."""
    parts: dict[int, str] = {}
    try:
        prev = tokenize.NEWLINE
        for t in tokenize.generate_tokens(io.StringIO(text).readline):
            if t.type == tokenize.COMMENT:
                _add(parts, t.start[0], t.string)
            elif t.type == tokenize.STRING and prev in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.NL):
                for k, s in enumerate(t.string.split("\n")):
                    _add(parts, t.start[0] + k, s)
            if t.type not in (tokenize.COMMENT, tokenize.NL):
                prev = t.type
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return hash_parts(text)
    return parts


def hash_parts(text: str) -> dict[int, str]:
    """`#` 주석(줄 처음이나 공백 뒤, 따옴표 밖). toml, 셸."""
    parts: dict[int, str] = {}
    for i, line in enumerate(text.splitlines(), 1):
        q: str | None = None
        for j, c in enumerate(line):
            if q:
                if c == q:
                    q = None
            elif c in "'\"":
                q = c
            elif c == "#" and (j == 0 or line[j - 1].isspace()):
                parts[i] = line[j:]
                break
    return parts


REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")


def js_parts(text: str, css: bool = False) -> dict[int, str]:
    """`//`와 `/* */` 주석(css는 `/* */`만). 문자열, 템플릿 문자열, 정규식 글자 안은 건너뛴다."""
    parts: dict[int, str] = {}
    i, n, row = 0, len(text), 1
    last = ""            # 마지막으로 본 공백 아닌 글자(정규식과 나눗셈 가르기)
    while i < n:
        c = text[i]
        if c == "\n":
            row += 1
            i += 1
            continue
        two = text[i:i + 2]
        if two == "/*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k, s in enumerate(text[i:j].split("\n")):
                _add(parts, row + k, s)
            row += text.count("\n", i, j)
            i = j
            continue
        if two == "//" and not css:
            j = text.find("\n", i)
            j = n if j < 0 else j
            _add(parts, row, text[i:j])
            i = j
            continue
        if c in "'\"`" or (c == "/" and not css and (last == "" or last in REGEX_BEFORE)):
            end = c
            j = i + 1
            in_class = False
            while j < n:
                d = text[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "\n" and end != "`":
                    break               # 닫히지 않은 줄(틀린 짐작)은 줄 끝에서 멈춘다
                if end == "/" and d == "[":
                    in_class = True
                elif end == "/" and d == "]":
                    in_class = False
                elif d == end and not in_class:
                    j += 1
                    break
                j += 1
            row += text.count("\n", i, j)
            i = j
            last = "a"
            continue
        if not c.isspace():
            last = c
        i += 1
    return parts


def parts_of(path: str, text: str) -> dict[int, str]:
    if path.endswith(".md"):
        return doc_parts(text)
    if path.endswith(".py"):
        return py_parts(text)
    if path.endswith(".js"):
        return js_parts(text)
    if path.endswith(".css"):
        return js_parts(text, css=True)
    return hash_parts(text)


def hits_in(s: str) -> list[str]:
    bare = QUOTED.sub("", s)
    return [name for ch, name in CHARS.items() if ch in bare]


def _count(parts: dict[int, str], rows: range, skip: frozenset[int] | set[int] = frozenset()) -> dict[str, int]:
    n = {name: 0 for name in CHARS.values()}
    for r in rows:
        if r in skip:
            continue
        bare = QUOTED.sub("", parts.get(r, ""))
        for ch, name in CHARS.items():
            n[name] += bare.count(ch)
    return n


def scan(repo: str | Path, base: str, strict: bool = False, rev: str | None = None,
         doc_dirs: tuple[str, ...] = DOC_DIRS, skip: tuple[str, ...] = SKIP_DIRS,
         not_code: tuple[str, ...] = ()) -> list[tuple[str, int, str, str]]:
    """(파일, 줄, 기호 이름, 그 줄 글 앞 80자). 기준 커밋 뒤 새 줄만. rev가 있으면 그 커밋 판을 읽는다.

    덩어리마다 지운 줄과 더한 줄의 기호 수를 맞대어, 그 기호가 늘어난 덩어리의 더한 줄만 낸다. 옛 줄을 고치기만 하고
    기호를 더하지 않았으면 걸지 않는다(이미 있던 기호는 세지 않는다). strict면 늘었는지 보지 않고 더한 줄을 모두 본다.

    옮긴 줄은 새 줄이 아니다(11-17 사용자). 브랜치 전체(점검 밖 파일 포함)에서 지운 줄과 앞뒤 공백과 근거 표시를 뗀 글(`same_text`)이 똑같은
    더한 줄은 옮긴 줄이라 세지 않는다. 같은 글을 여러 번 옮기면 지운 줄 하나가 더한 줄 하나만 풀어 준다(`removed_pool`).
    표시를 뗀 글이 조금이라도 다르면(HTML 주석과 날짜 꼬리는 글이다) 옮긴 줄이 아니다. 풀린 줄의 지운 쪽 자리도 기호 수 맞대기에서 뺀다(그 줄의 기호는 옮겨 간 것이지
    그 덩어리에서 지운 것이 아니라서, 안 빼면 같은 덩어리에 새 기호를 더하고도 지운 것으로 상쇄되어 놓친다)."""
    out: list[tuple[str, int, str, str]] = []
    new_parts: dict[str, dict[int, str]] = {}
    new_lines: dict[str, list[str]] = {}
    old_parts: dict[str, dict[int, str]] = {}
    todo = sorted(hunks(repo, base, rev, doc_dirs, skip, not_code), key=lambda h: (h[0], h[3].start))
    pool = removed_pool(repo, base, rev)
    moved: dict[str, set[int]] = {}         # 새 경로 -> 옮긴 줄로 풀린 더한 줄
    gone: dict[str, set[int]] = {}          # 옛 경로 -> 더한 줄을 풀어 준 지운 줄
    for path, _old, _old_rows, new_rows in todo:        # 1걸음: 옮긴 줄을 모두 짝짓는다(덩어리 차례대로, 한 번 쓴 지운 줄은 다시 못 쓴다)
        if path not in new_parts:
            try:
                text = _git(repo, "show", f"{rev}:{path}") if rev else (Path(repo) / path).read_text(encoding="utf-8")
                new_parts[path], new_lines[path] = parts_of(path, text), text.splitlines()
            except (OSError, UnicodeDecodeError, DashDotError):
                new_parts[path], new_lines[path] = {}, []
        lines = new_lines[path]
        for row in new_rows:
            t = same_text(lines[row - 1]) if 0 < row <= len(lines) else ""
            if t and pool.get(t):
                src_path, src_row = pool[t].pop(0)
                moved.setdefault(path, set()).add(row)
                gone.setdefault(src_path, set()).add(src_row)
    for path, old, old_rows, new_rows in todo:          # 2걸음: 덩어리마다 기호 수를 맞대고 더한 줄을 건다
        parts = new_parts[path]
        skip_new = moved.get(path, set())
        grew = set(CHARS.values())
        if not strict and old and old_rows:
            if old not in old_parts:
                try:
                    old_parts[old] = parts_of(old, _git(repo, "show", f"{base}:{old}"))
                except DashDotError:
                    old_parts[old] = {}
            was, now = _count(old_parts[old], old_rows, gone.get(old, set())), _count(parts, new_rows, skip_new)
            grew = {k for k in grew if now[k] > was[k]}
        for row in new_rows:
            s = parts.get(row)
            if s and row not in skip_new:
                for name in hits_in(s):
                    if name in grew:
                        out.append((path, row, name, s.strip()[:80]))
    return out


def new_doc_rows(repo: str | Path, base: str, rev: str | None = None, doc_dirs: tuple[str, ...] = DOC_DIRS,
                 skip: tuple[str, ...] = SKIP_DIRS, keep: Callable[[str], bool] = lambda t: "→" in t) -> dict[str, set[int]]:
    """기준 커밋 뒤 더하거나 고친 문서(`*.md`) 줄: {경로: 줄 번호들}. 줄표 검사와 같은 덩어리(`hunks`)와 옮긴 줄 풀이(`removed_pool`)를 쓴다.
    옮긴 줄(근거 표시만 떼면 지운 줄과 글이 같은 줄, keep에 드는 것만 맞댄다)은 새 줄이 아니다. 「」 없는 편 사이 참조 검사
    (`bridge/doctext/check.py`)가 쓴다. 기준 커밋이 조상이 아니거나 git이 실패하면 DashDotError."""
    pool = removed_pool(repo, base, rev, keep)
    out: dict[str, set[int]] = {}
    lines: dict[str, list[str]] = {}
    for path, _old, _old_rows, new_rows in sorted(hunks(repo, base, rev, doc_dirs, skip), key=lambda h: (h[0], h[3].start)):
        if not path.endswith(".md"):
            continue
        if path not in lines:
            try:
                text = _git(repo, "show", f"{rev}:{path}") if rev else (Path(repo) / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError, DashDotError):
                text = ""
            lines[path] = text.splitlines()
        ls = lines[path]
        for row in new_rows:
            t = same_text(ls[row - 1]) if 0 < row <= len(ls) else ""
            if t and pool.get(t):
                pool[t].pop(0)
                continue
            out.setdefault(path, set()).add(row)
    return out


def for_repo(repo: str | Path, base: str | None, sets: dict[str, str], records: list[str],
             rev: str | None = None, not_code: list[str] | None = None) -> dict:
    """저장소 하나를 그 설정대로(문서 점검 `bridge/doctext/check.py`가 부른다). 돌려주는 것: {base, hits, note, error}.

    기준 커밋 칸이 없으면 검사하지 않고 note(NO_BASE)를 남긴다. 조용히 모든 줄을 걸거나(옛 줄 수백 건) 조용히 넘어가지 않게.
    기준 커밋이 조상이 아니거나 git이 실패하면 error(0건으로 보이지 않게)."""
    if not base:
        return {"base": None, "hits": [], "note": NO_BASE, "error": None}
    doc_dirs = tuple(d for d in sets.values() if d) or DOC_DIRS
    skip = (*tuple(records), *TOOL_DIRS)
    try:
        hits = scan(repo, base, rev=rev, doc_dirs=doc_dirs, skip=skip, not_code=tuple(not_code or ()))
    except DashDotError as e:
        return {"base": base, "hits": [], "note": None, "error": str(e)}
    return {"base": base, "hits": hits, "note": None, "error": None}
