"""거꾸로 찾기(11-17 사용자 지시 21). 코드 파일을 주면 그 코드를 가리키는 문서(docs, 노션 원고, 포트폴리오)와 줄을 돌려준다.

읽기만 한다. 저장소를 바꾸지 않는다(git은 ls-tree, cat-file, diff, merge-base, rev-parse만 부른다).
명령은 `tools/docrefs.py`, 브리지는 `scan()`을 부른다(합치기 카드 「걸리는 문서」, `bridge/mergeprep.py`).

가리키는 꼴 넷(`how`):
- `mark`   원고의 근거 표시 `[code:bridge/x.py]`, 폴더 `[code:bridge/transcript/]`(그 아래 파일 모두), 줄 번호 `[code:bridge/x.py:10-20]`
- `path`   백틱 안이나 맨글의 저장소 경로(`bridge/x.py`, 폴더 `bridge/static/js/`)
- `name`   백틱 안의 파일 이름이나 경로 끝(`mergeprep.py`, `api/handoff.py`). 저장소에서 그 끝을 가진 파일이 하나뿐일 때만
- `covers` 원고와 포트폴리오 머리 주석 「다루는 곳」(파일, 끝이 /인 폴더, *가 든 글롭. 꼴은 `bridge/doctext/head.py`)

근거 표시, 머리 주석, 코드 울타리와 HTML 주석 가르기는 문서 문법 묶음 `bridge/doctext` 한 곳을 쓴다(11-17 문서 도구 합치기 1단계).

문서 묶음: `docs/`(docs), 원고 폴더(notion, 그 저장소 `.foreman/notion.toml`의 `src`, 없으면 FOREMAN `config/notion.toml`의
그 저장소 칸 `src`. `docs/`면 docs와 같은 묶음이라 따로 두지 않는다), `portfolio/`(portfolio). 셋 다 `*.md`만.

커밋 범위(`A..B`, `A...B`)를 주면 그 범위에서 바뀐 코드 파일로 찾고, 문서는 B 판을 읽는다. 그 문서가 같은 범위에서 바뀌었으면
`fixed` True(고침), 아니면 False(안 고침). 파일 목록만 주면 작업 트리(또는 `rev`)를 읽고 `fixed`는 None(모름)이다.
근거 표시에 줄 번호가 있으면 바뀐 줄 범위(범위의 옛 쪽 줄)와 겹치는지 `overlap`으로 보인다(줄 번호가 없으면 None).
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from bridge.doctext.head import parse_head
from bridge.doctext.lines import TEXT, walk
from bridge.doctext.marks import CODE_MARK as MARK
from bridge.doctext.marks import split_range as _split_range

FOREMAN_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = "docs/"
PORTFOLIO_DIR = "portfolio/"
SKIP_CODE_DIRS = ("log/",)          # 범위에서 바뀐 파일 중 코드로 치지 않는 곳(결과 기록). 문서 묶음 아래 파일(사진 포함)과 *.md도 코드가 아니다

TICK = re.compile(r"`([^`\n]+)`")
TOKEN = re.compile(r"[A-Za-z0-9_./*-]+(?::\d+(?:-\d+)?)?")
# 맨글 경로: 슬래시가 있고 확장자로 끝나는 것만(URL의 // 뒤, 다른 경로 가운데는 빼려고 앞 글자를 본다)
PLAIN = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6})(?::(\d+)(?:-(\d+))?)?(?![\w/-])")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s|^\s*\|")
EXT = re.compile(r"\.[A-Za-z0-9]{1,6}$")


class DocrefsError(RuntimeError):
    """git을 읽지 못함, 범위를 모름 등. 화면과 카드는 이 글을 그대로 보인다."""


def _git(repo: str | Path, *a: str, input_: bytes | None = None) -> bytes:
    try:
        r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, timeout=60, input=input_)
    except (OSError, subprocess.SubprocessError) as e:
        raise DocrefsError(f"git을 부르지 못했습니다({type(e).__name__})") from e
    if r.returncode:
        raise DocrefsError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def _gits(repo: str | Path, *a: str) -> str:
    return _git(repo, *a).decode(errors="replace")


# ── 설정: 원고 폴더 ─────────────────────────────────────────
def project_name(repo: str | Path) -> str:
    """저장소 이름. worktree면 원본 저장소 폴더 이름(`.worktrees/foreman-8` → foreman). FOREMAN `config/notion.toml` 칸 이름과 같다."""
    try:
        common = _gits(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        return Path(common).parent.name
    except DocrefsError:
        return Path(repo).resolve().name


def manuscript_src(repo: str | Path, config: str | Path | None = None) -> str | None:
    """원고 폴더(끝이 /). 그 저장소 `.foreman/notion.toml` `src`가 먼저, 없으면 FOREMAN `config/notion.toml`의 그 저장소 칸 `src`.
    둘 다 없으면 None(원고가 따로 없다). 깨진 파일은 없는 것으로 본다(이 도구는 설정을 고치지 않는다)."""
    def src_of(d: dict[str, Any]) -> str | None:
        v = d.get("src")
        return v if isinstance(v, str) and v.endswith("/") and ".." not in v and not v.startswith("/") else None
    own = Path(repo) / ".foreman" / "notion.toml"
    if own.is_file():
        try:
            v = src_of(tomllib.loads(own.read_text(encoding="utf-8")))
            if v:
                return v
        except (OSError, tomllib.TOMLDecodeError):
            pass
    cfg = Path(config) if config else FOREMAN_ROOT / "config" / "notion.toml"
    try:
        raw = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    sec = raw.get(project_name(repo))
    return src_of(sec) if isinstance(sec, dict) else None


def doc_sets(src: str | None, docs_dir: str = DOCS_DIR) -> dict[str, str]:
    """{묶음 이름: 폴더}. 원고 폴더가 docs와 같으면 docs 하나로."""
    d = docs_dir if docs_dir.endswith("/") else docs_dir + "/"
    out = {"docs": d}
    if src and src != d:
        out["notion"] = src
    out["portfolio"] = PORTFOLIO_DIR
    return out


def kind_of(path: str, sets: dict[str, str]) -> str | None:
    if not path.endswith(".md"):
        return None
    for k, d in sorted(sets.items(), key=lambda x: -len(x[1])):
        if path.startswith(d):
            return k
    return None


# ── 문서 읽기 ───────────────────────────────────────────────
def _tree(repo: str, rev: str | None, dirs: list[str] | None = None) -> list[str]:
    if rev:
        out = _gits(repo, "ls-tree", "-r", "--name-only", rev, "--", *(dirs or []))
    else:
        out = _gits(repo, "ls-files", "--", *(dirs or []))
    return [x for x in out.splitlines() if x]


def _read_many(repo: str, rev: str | None, paths: list[str]) -> dict[str, str]:
    """여러 문서를 한 번에. rev면 `git cat-file --batch`, 아니면 작업 트리."""
    if not paths:
        return {}
    if not rev:
        out = {}
        for p in paths:
            try:
                out[p] = (Path(repo) / p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        return out
    raw = _git(repo, "cat-file", "--batch", input_="".join(f"{rev}:{p}\n" for p in paths).encode())
    out: dict[str, str] = {}
    i = 0
    for p in paths:
        nl = raw.index(b"\n", i)
        head = raw[i:nl].decode(errors="replace").split()
        i = nl + 1
        if len(head) >= 2 and head[1] == "missing":
            continue
        size = int(head[2])
        out[p] = raw[i:i + size].decode(errors="replace")
        i += size + 1
    return out


# ── 문서 안의 가리킴(근거 표시, 머리 주석, 울타리와 주석 가르기는 bridge/doctext) ──
def _clean(tok: str) -> str:
    tok = tok.strip().strip(".,;")
    return tok[2:] if tok.startswith("./") else tok


def _pathlike(tok: str) -> bool:
    if not tok or tok.startswith(("-", "/", "~")) or ".." in tok.split("/") or not re.search(r"[A-Za-z]", tok):
        return False
    if not ("/" in tok or EXT.search(tok)):
        return False
    # 백틱과 맨글의 폴더, 글롭은 두 단계 이상만(`bridge/transcript/`). `bridge/` `tests/*`는 「그 폴더 전체」라는 말이라
    # 모든 파일에 걸려 헛걸림만 늘린다(11-17 첫 판에서 docs/roles.md가 바뀐 파일 20개 모두에 걸렸다). 근거 표시와 다루는 곳은 그대로 둔다
    fixed = re.split(r"[*?\[]", tok, maxsplit=1)[0]
    if (tok.endswith("/") or fixed != tok or not EXT.search(tok)) and len([s for s in fixed.split("/") if s]) < 2:
        return False
    return True


def refs_in(md: str) -> list[dict[str, Any]]:
    """한 문서의 가리킴 [{line, target, range, how, ref}]. 코드 울타리와 HTML 주석 안은 보지 않는다(머리 주석은 따로 covers로)."""
    out: list[dict[str, Any]] = []
    head = parse_head(md)
    if head:
        for c in head["covers"]:
            out.append({"line": head["line"], "target": _clean(c), "range": None, "how": "covers", "ref": f"다루는 곳: {c}"})
    lines = md.splitlines()
    for i0, kind in walk(lines):
        if kind != TEXT:
            continue
        i, ln = i0 + 1, lines[i0]
        seen: set[tuple[str, Any]] = set()

        def add(target: str, rng: tuple[int, int] | None, how: str, ref: str) -> None:
            if (target, rng) in seen:
                return
            seen.add((target, rng))
            out.append({"line": i, "target": target, "range": rng, "how": how, "ref": ref})

        for mk in MARK.finditer(ln):
            p, rng = _split_range(_clean(mk["v"]))
            add(p, rng, "mark", mk.group(0))
        rest = MARK.sub(" ", ln)
        for tk in TICK.finditer(rest):
            for t in TOKEN.findall(tk.group(1)):
                p, rng = _split_range(_clean(t))
                if _pathlike(p):
                    add(p, rng, "path" if "/" in p else "name", f"`{tk.group(1)[:80]}`")
        for pm in PLAIN.finditer(TICK.sub(" ", rest)):
            rng = (int(pm[2]), int(pm[3] or pm[2])) if pm[2] else None
            add(_clean(pm[1]), rng, "path", pm.group(0))
    return out


def _headings(lines: list[str]) -> list[str]:
    """줄마다 그 줄이 든 제목(울타리와 HTML 주석 안 #은 제목이 아니다)."""
    cur = ""
    out = []
    for i, kind in walk(lines):
        ln = lines[i]
        if kind == TEXT and re.match(r"^#{1,6}\s", ln):
            cur = ln.lstrip("#").strip()
        out.append(cur)
    return out


def paragraph(lines: list[str], line: int, cap: int = 400) -> tuple[int, int, str]:
    """걸린 줄의 문단. 목록 항목과 표 줄은 그 줄(들여 쓴 이어지는 줄까지), 아니면 빈 줄로 나뉜 덩어리. (시작, 끝, 글)."""
    i = line - 1
    if i < 0 or i >= len(lines):
        return line, line, ""
    if LIST_ITEM.match(lines[i]) or re.match(r"^\s*#{1,6}\s", lines[i]):
        a = b = i
        ind = len(lines[i]) - len(lines[i].lstrip())
        while b + 1 < len(lines) and lines[b + 1].strip() and not LIST_ITEM.match(lines[b + 1]) \
                and len(lines[b + 1]) - len(lines[b + 1].lstrip()) > ind:
            b += 1
    else:
        a = b = i
        while a > 0 and lines[a - 1].strip() and not LIST_ITEM.match(lines[a - 1]) and not lines[a - 1].lstrip().startswith("#"):
            a -= 1
        while b + 1 < len(lines) and lines[b + 1].strip() and not LIST_ITEM.match(lines[b + 1]):
            b += 1
    txt = " ".join(x.strip() for x in lines[a:b + 1])
    return a + 1, b + 1, txt if len(txt) <= cap else txt[: cap - 1] + "…"


# ── 맞대기 ──────────────────────────────────────────────────
def _glob(p: str) -> bool:
    return any(ch in p for ch in "*?[")


def matches(target: str, how: str, code: str, names: dict[str, list[str]]) -> bool:
    """가리킴 하나가 코드 파일 하나를 덮나. 폴더(끝이 /)는 그 아래 모두, 글롭은 fnmatch(*가 /도 넘는다),
    `name`은 저장소에서 그 끝을 가진 파일이 하나뿐일 때 그 파일만."""
    if target.endswith("/"):
        return code.startswith(target)
    if _glob(target):
        return fnmatch.fnmatchcase(code, target)
    if target == code:
        return True
    if how == "name" or (how == "path" and not code.startswith(target)):
        cands = names.get(PurePosixPath(target).name, [])
        hits = [c for c in cands if c == target or c.endswith("/" + target)]
        return len(hits) == 1 and hits[0] == code
    return code.startswith(target + "/")     # 백틱 안 폴더를 / 없이 적은 것(`bridge/transcript`)


def _names(paths: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in paths:
        out.setdefault(PurePosixPath(p).name, []).append(p)
    return out


def changed_lines(repo: str, a: str, b: str, files: list[str]) -> dict[str, list[tuple[int, int]]]:
    """범위의 바뀐 줄(옛 쪽 a 판 줄 번호). 근거 표시의 줄 번호는 그 글을 쓸 때 코드 판을 가리키므로 옛 쪽과 맞댄다."""
    if not files:
        return {}
    out: dict[str, list[tuple[int, int]]] = {}
    cur = None
    for ln in _gits(repo, "diff", "-U0", "--no-renames", a, b, "--", *files).splitlines():
        if ln.startswith("--- "):
            cur = ln[6:] if ln.startswith("--- a/") else None
        elif ln.startswith("+++ ") and cur is None and ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("@@") and cur:
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? ", ln)
            if m:
                s, n = int(m[1]), int(m[2] if m[2] is not None else 1)
                out.setdefault(cur, []).append((s, s + max(n, 1) - 1))
    return out


def parse_range(repo: str, rng: str) -> tuple[str, str]:
    """`A..B`, `A...B`(갈라진 곳부터), `A`(A..HEAD)를 (옛 쪽 커밋, 새 쪽 커밋)으로."""
    if "..." in rng:
        a, b = rng.split("...", 1)
        b = b or "HEAD"
        a = _gits(repo, "merge-base", a or "HEAD", b).strip()
    elif ".." in rng:
        a, b = rng.split("..", 1)
        a, b = a or "HEAD", b or "HEAD"
    else:
        a, b = rng, "HEAD"
    try:
        a2 = _gits(repo, "rev-parse", "--verify", "--quiet", a + "^{commit}").strip()
        b2 = _gits(repo, "rev-parse", "--verify", "--quiet", b + "^{commit}").strip()
    except DocrefsError as e:
        raise DocrefsError(f"커밋 범위를 알아보지 못했습니다: {rng}") from e
    return a2, b2


def is_code(path: str, sets: dict[str, str]) -> bool:
    """범위에서 바뀐 파일 가운데 코드인가. 문서 묶음 폴더 아래 파일은 확장자와 상관없이 코드가 아니다
    (11-17 `portfolio/img/`의 png, gif, webm이 코드로 세어져 합치기 카드에 헛걸림이 생겼다)."""
    if path.endswith(".md") or path.startswith(SKIP_CODE_DIRS):
        return False
    return not any(d and path.startswith(d) for d in sets.values())


def scan(repo: str | Path, files: list[str] | None = None, rng: str | None = None, rev: str | None = None,
         src: str | None = None, docs_dir: str = DOCS_DIR, config: str | Path | None = None,
         para_cap: int = 400) -> dict[str, Any]:
    """거꾸로 찾기 한 번. files(`경로` 또는 `경로:시작-끝`) 또는 rng 중 하나는 있어야 한다. 둘 다 주면 범위의 코드 파일 중 files만.

    돌려주는 것: {repo, range, rev, sets, code, docs: [{doc, kind, fixed, files, hits: [{line, heading, para_from, para_to,
    para, how, ref, code, range, overlap}]}], total, unfixed, warnings}. docs는 안 고친 것, 걸린 수가 많은 것 먼저."""
    repo = str(Path(repo).resolve())
    if not files and not rng:
        raise DocrefsError("코드 파일이나 커밋 범위를 주어야 합니다")
    src = src if src is not None else manuscript_src(repo, config)
    sets = doc_sets(src, docs_dir)
    warnings: list[str] = []
    given: dict[str, list[tuple[int, int]]] = {}
    for f in files or []:
        p, r = _split_range(_clean(f))
        given.setdefault(p, [])
        if r:
            given[p].append(r)
    changed: set[str] = set()
    lines_of: dict[str, list[tuple[int, int]]] = {}
    a = b = None
    if rng:
        a, b = parse_range(repo, rng)
        changed = set(_gits(repo, "diff", "--name-only", "--no-renames", a, b).splitlines())
        code = sorted(p for p in changed if is_code(p, sets))
        if given:
            code = [p for p in code if p in given or any(matches(g, "path", p, {}) for g in given)]
        rev = b
    else:
        code = sorted(given)
        lines_of = {p: r for p, r in given.items() if r}
    if not code:
        return {"repo": repo, "range": rng, "rev": rev, "sets": sets, "code": [], "docs": [], "total": 0, "unfixed": 0,
                "warnings": warnings}
    tracked = _tree(repo, rev)
    names = _names(sorted(set(tracked) | set(code)))
    doc_paths = [p for p in _tree(repo, rev, list(sets.values())) if kind_of(p, sets)]
    bodies = _read_many(repo, rev, doc_paths)
    raw_hits: dict[str, list[dict[str, Any]]] = {}
    for path in doc_paths:
        body = bodies.get(path)
        if body is None:
            continue
        refs = refs_in(body)
        if not refs:
            continue
        lines = body.splitlines()
        heads = None
        for r in refs:
            hit = [c for c in code if matches(r["target"], r["how"], c, names)]
            if not hit:
                continue
            if heads is None:
                heads = _headings(lines)
            pa, pb, ptxt = paragraph(lines, r["line"], para_cap) if r["how"] != "covers" else (r["line"], r["line"], r["ref"])
            for c in hit:
                raw_hits.setdefault(path, []).append({
                    "line": r["line"], "heading": "(머리 주석)" if r["how"] == "covers" else heads[r["line"] - 1],
                    "para_from": pa, "para_to": pb, "para": ptxt, "how": r["how"], "ref": r["ref"], "code": c,
                    "range": list(r["range"]) if r["range"] else None, "overlap": None})
    # 줄 번호가 있는 근거 표시만 바뀐 줄과 맞댄다
    want = sorted({h["code"] for hs in raw_hits.values() for h in hs if h["range"]})
    if want and rng and a and b:
        try:
            lines_of = changed_lines(repo, a, b, want)
        except DocrefsError as e:
            warnings.append(f"바뀐 줄을 읽지 못했습니다: {e}")
    for hs in raw_hits.values():
        for h in hs:
            if h["range"] and (rng or h["code"] in lines_of):
                spans = lines_of.get(h["code"], [])
                h["overlap"] = any(s <= h["range"][1] and h["range"][0] <= e for s, e in spans)
    docs = []
    for path, hs in raw_hits.items():
        hs.sort(key=lambda h: (h["line"], h["code"]))
        docs.append({"doc": path, "kind": kind_of(path, sets), "fixed": (path in changed) if rng else None,
                     "files": sorted({h["code"] for h in hs}), "hits": hs})
    docs.sort(key=lambda d: (d["fixed"] is True, -len(d["hits"]), d["doc"]))
    return {"repo": repo, "range": rng, "rev": rev, "sets": sets, "code": code, "docs": docs, "total": len(docs),
            "unfixed": sum(1 for d in docs if d["fixed"] is False), "warnings": warnings}


# ── 합치기 카드 모양 ────────────────────────────────────────
def card_docs(res: dict[str, Any], limit: int = 12, hits: int = 5) -> dict[str, Any]:
    """scan 결과 → 합치기 카드 `docs` 칸(옛 정리 후보 모양을 잇는다: where, lines, count, files, stale). `stale` = 이 브랜치에서
    안 고침. 더한 칸: kind(docs, notion, portfolio), hits(줄, 제목, 문단 앞부분), 전체 수 total과 안 고친 수 unfixed(목록을 자르기 전)."""
    groups = []
    for d in res["docs"]:
        lines = sorted({h["line"] for h in d["hits"]})
        groups.append({"where": d["doc"], "kind": d["kind"], "lines": lines[:8], "count": len(lines), "files": d["files"],
                       "stale": d["fixed"] is False,
                       "hits": [{"line": h["line"], "heading": h["heading"][:80], "text": h["para"][:160], "code": h["code"]}
                                for h in d["hits"][:hits]]})
    return {"readme": [], "docs": groups[:limit], "total": res["total"], "unfixed": res["unfixed"],
            "code": len(res["code"]), "warnings": res.get("warnings") or []}


# ── 코더 첫 글에 붙이는 묶음(11-17 사용자 지시 21) ─────────────
# 글의 말투 규칙은 문서마다 다르다. 코더가 쓴 글도 다른 편과 같은 말투여야 한다(사용자). 상세는 그 규칙의 원천을 가리킨다
TONE_FOREMAN = ("말투는 그 문서 쪽 규칙을 따른다. docs는 `docs/style_guide.md`(평서체, 세션이 읽는 글이라 얕고 짧게), "
                "노션 원고(`notion/`)는 평서체에 깊고 쉽게, 문장 끝 근거 표시(`[code:경로]` 등), 포트폴리오(`portfolio/`)는 경어체(합니다, 해요)에 "
                "화면 축, 문단으로(근거 표시는 git 원고에만 남고 노션 판에서는 떼어진다). 원고와 포트폴리오 머리 주석 「다루는 곳」이 바뀌면 함께 고친다. "
                "네 문서의 역할은 `docs/12_scribe.md` 「0.」, 원고와 포트폴리오 쓰는 법은 `bridge/scribe_room.py` `task_prompt`")
TONE_OTHER = "말투와 문서 자리는 이 저장소의 CLAUDE.md와 docs가 정한 것을 따른다"


def _same_repo(a: str | Path, b: str | Path) -> bool:
    try:
        ca = _gits(a, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        cb = _gits(b, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        return Path(ca).resolve() == Path(cb).resolve()
    except DocrefsError:
        return False


def prompt_block(cwd: str | Path, role: str | None) -> str:
    """코더 세션 첫 글 끝에 붙일 절. 코더가 아니면 빈 글(디자이너, 조사에는 넣지 않는다, 사용자). FOREMAN 저장소면 상대 경로 명령과
    FOREMAN 말투 규칙을, 다른 저장소면 FOREMAN 도구를 그 저장소에 대고 읽기만 하는 명령과 그 저장소 규칙을 따르라는 줄을 넣는다."""
    from bridge.roles import CODER_DOCS_RULE, DOCS_RULE_ROLES
    if role not in DOCS_RULE_ROLES:
        return ""
    own = _same_repo(cwd, FOREMAN_ROOT)
    if own:
        cmd = ".venv/bin/python tools/docrefs.py"
    else:
        py = FOREMAN_ROOT / ".venv" / "bin" / "python"
        cmd = f"{py if py.exists() else 'python3'} {FOREMAN_ROOT / 'tools' / 'docrefs.py'} --repo ."
    return ("\n\n## 고친 코드의 문서도 함께 (코더 규칙, 브리지가 붙임)\n"
            f"- {CODER_DOCS_RULE}\n"
            f"- 거꾸로 찾는 도구(읽기만 한다): `{cmd} --range main...HEAD --unfixed`(이 브랜치가 바꾼 코드를 가리키는데 아직 안 고친 문서와 줄), "
            f"커밋 전이면 `{cmd} <고친 파일 경로>`. 합치기 카드에도 「걸리는 문서 N, 안 고침 M」으로 보인다. 걸린 문단이 지금 코드와 맞으면 그대로 둔다\n"
            f"- {TONE_FOREMAN if own else TONE_OTHER}\n"
            "- 그 저장소 CLAUDE.md가 사람 승인으로 정한 문서(README.md, CLAUDE.md 등)는 고쳐도 합치기 카드가 사람에게 간다. "
            "고치지 못한 문서는 마지막 보고에(결과 기록을 남기는 저장소면 거기에도) 「무엇이 걸리는지」로 적는다")


def count_line(d: dict[str, Any] | None) -> str:
    """「걸리는 문서 N, 안 고침 M」. 카드 글, 알림 글이 같이 쓴다. 걸리는 문서가 없으면 빈 글."""
    if not d:
        return ""
    total = d.get("total", len(d.get("docs") or []))
    if not total:
        return ""
    unfixed = d.get("unfixed", sum(1 for x in d.get("docs") or [] if x.get("stale")))
    return f"걸리는 문서 {total}, 안 고침 {unfixed}"
