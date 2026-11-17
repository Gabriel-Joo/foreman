"""새 줄의 em dash와 가운뎃점(11-17 문서 도구 합치기 4단계, `docs/manuscript_rules.md` 「1.」 「6.」). 읽기만 한다.

기준 커밋(BASE) 뒤로 더해지거나 고쳐진 줄만 본다(`git diff BASE`, 작업 트리와 추적하지 않는 파일까지). 이미 있던 줄은 세지 않는다.
고친 덩어리는 지운 줄과 더한 줄의 기호 수를 맞대어 늘어난 기호만 건다(옛 줄을 고치기만 해도 옛 기호를 다 걷어야 하면
11-17 하루치(커밋 41개) 82건 가운데 57건이 그런 줄이라 사람이 시험을 무시하게 된다. `log/foreman-4_manuscript_rules_20261117.md`).

- 문서: docs, notion, portfolio 아래 `*.md`. 코드 울타리와 HTML 주석 안은 보지 않는다
- 코드 주석: `.py`(`#` 주석과 문자열만으로 된 문장, 곧 독스트링), `.js`와 `.css`(`//`, `/* */`), `.toml`과 `.sh`(`#`)
- 세지 않는 것: 백틱 안, 「」와 『』와 큰따옴표 안(화면 글과 절 제목 인용), 기호 하나만 괄호로 감싼 것
- 보지 않는 곳: `log/`, 문서 묶음 밖 `*.md`(README.md, CLAUDE.md), 그 밖의 확장자. 코드의 문자열(화면 글, 지시문)

표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import io
import re
import subprocess
import tokenize
from pathlib import Path

from bridge.doctext.lines import TEXT, walk

CHARS = {"—": "em dash", "·": "가운뎃점"}
DOC_DIRS = ("docs/", "notion/", "portfolio/")
SKIP_DIRS = ("log/", ".venv/", "node_modules/", ".tools/", ".worktrees/")
CODE_EXT = (".py", ".js", ".css", ".toml", ".sh")

# 세지 않는 자리(인용과 코드). 줄에서 지운 뒤 기호를 찾는다
QUOTED = re.compile(r"`[^`]*`|「[^」]*」|『[^』]*』|\"[^\"]*\"|“[^”]*”|\([—·]\)")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class DashDotError(RuntimeError):
    pass


def _git(repo: str | Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *a], capture_output=True, timeout=120)
    if r.returncode:
        raise DashDotError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout.decode(errors="replace")


def wanted(path: str) -> str | None:
    """"doc", "code", 또는 None(보지 않는다)."""
    if path.startswith(SKIP_DIRS):
        return None
    if path.endswith(".md"):
        return "doc" if path.startswith(DOC_DIRS) else None
    if path.startswith(DOC_DIRS):
        return None
    return "code" if path.endswith(CODE_EXT) else None


Hunk = tuple[str, str | None, range, range]     # (새 경로, 옛 경로 또는 None, 옛 줄, 새 줄). 줄 번호는 1부터


def hunks(repo: str | Path, base: str) -> list[Hunk]:
    """기준 커밋과 작업 트리 사이에 바뀐 덩어리. 추적하지 않는 파일은 통째로 새 덩어리 하나.
    base가 HEAD의 조상이 아니면 DashDotError(조용히 0줄로 지나가지 않게)."""
    try:
        _git(repo, "merge-base", "--is-ancestor", base, "HEAD")
    except DashDotError as e:
        raise DashDotError(f"기준 커밋 {base[:10]}이 HEAD의 조상이 아닙니다: {e}") from e
    out: list[Hunk] = []
    old: str | None = None
    cur: str | None = None
    for line in _git(repo, "diff", "--no-color", "--no-ext-diff", "-U0", "-M", "--diff-filter=AMR", base).splitlines():
        if line.startswith("--- "):
            p = line[4:]
            old = p[2:] if p.startswith("a/") else None
        elif line.startswith("+++ "):
            p = line[4:]
            cur = p[2:] if p.startswith("b/") and wanted(p[2:]) else None
        elif cur and (m := HUNK.match(line)):
            a, b, c, d = (int(x) if x is not None else 1 for x in m.groups())
            out.append((cur, old, range(a, a + b), range(c, c + d)))
    for p in _git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
        if wanted(p):
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


def _count(parts: dict[int, str], rows: range) -> dict[str, int]:
    n = {name: 0 for name in CHARS.values()}
    for r in rows:
        bare = QUOTED.sub("", parts.get(r, ""))
        for ch, name in CHARS.items():
            n[name] += bare.count(ch)
    return n


def scan(repo: str | Path, base: str, strict: bool = False) -> list[tuple[str, int, str, str]]:
    """(파일, 줄, 기호 이름, 그 줄 글 앞 80자). 기준 커밋 뒤 새 줄만.

    덩어리마다 지운 줄과 더한 줄의 기호 수를 맞대어, 그 기호가 늘어난 덩어리의 더한 줄만 낸다. 옛 줄을 고치기만 하고
    기호를 더하지 않았으면 걸지 않는다(이미 있던 기호는 세지 않는다). strict면 늘었는지 보지 않고 더한 줄을 모두 본다."""
    out: list[tuple[str, int, str, str]] = []
    new_parts: dict[str, dict[int, str]] = {}
    old_parts: dict[str, dict[int, str]] = {}
    for path, old, old_rows, new_rows in sorted(hunks(repo, base), key=lambda h: (h[0], h[3].start)):
        if path not in new_parts:
            try:
                new_parts[path] = parts_of(path, (Path(repo) / path).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                new_parts[path] = {}
        parts = new_parts[path]
        grew = set(CHARS.values())
        if not strict and old and old_rows:
            if old not in old_parts:
                try:
                    old_parts[old] = parts_of(old, _git(repo, "show", f"{base}:{old}"))
                except DashDotError:
                    old_parts[old] = {}
            was, now = _count(old_parts[old], old_rows), _count(parts, new_rows)
            grew = {k for k in grew if now[k] > was[k]}
        for row in new_rows:
            s = parts.get(row)
            if s:
                for name in hits_in(s):
                    if name in grew:
                        out.append((path, row, name, s.strip()[:80]))
    return out
