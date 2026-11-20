"""거꾸로 찾기(11-17 사용자 지시 21). 바뀐 코드나 문서를 주면 그것을 가리키는 문서(docs, 노션 원고, 포트폴리오)와 줄을 돌려준다.

읽기만 한다. 저장소를 바꾸지 않는다(git은 ls-tree, ls-files, cat-file, diff, merge-base, rev-parse만 부른다).
명령은 `tools/docs.py refs`, 브리지는 `scan()`을 부른다(합치기 카드 「걸리는 문서」, `bridge/mergeprep.py`).

이 도구는 밀림 검사다(11-17 사용자 결정, 문서 도구 합치기 3단계). 원고 머리 주석 「다루는 곳」(파일 단위, 덮기 검사만 읽는다,
`tools/docs.py check`)은 읽지 않고, 근거 표시와 글 안 경로만 따라간다. 전에는 두 검사가 같은 자리를 읽어 다루는 곳에 넣은
파일이 바뀔 때마다 편 전체가 헛걸렸다. 편 단위 밀림은 서기실 셈(`bridge/manuscript.py`, 다루는 곳의 feat, fix 커밋)이 본다.

저장소마다 다른 것은 그 저장소 `.foreman/docs.toml`(`bridge/doctext/config.py`)에서 읽는다(11-17 문서 도구 합치기 2단계).
파일이 없으면 FOREMAN 기본값이다. 설정은 작업 트리 판을 읽는다(범위 없이 `rev`를 주면 그 커밋 판).
- `[sets]` 문서 묶음 폴더(docs, notion, portfolio). notion이 없으면 그 저장소 `.foreman/notion.toml` `src`, 그것도 없으면
  FOREMAN `config/notion.toml`의 그 저장소 칸 `src`. docs와 같으면 따로 두지 않는다. 셋 다 `*.md`만
- `records` 기록 폴더(FOREMAN `log/`, 인프라 `docs/history/`). 문서도 아니고 걸게 하지도 않는다
- `not_code` 바뀌어도 코드로 세지 않는 확장자(`.md`), 파일 경로, 글롭(`bridge/__init__.py`)
- `pair_numbers` docs의 `NN_*.md`가 바뀌면 같은 번호 원고 `NN_*.md`와 `NN_*/` 아래 글도 건다(인프라만 켬)

걸게 하는 것(`triggers`, 종류 `code` 또는 `doc`)
- code  문서 묶음 폴더 밖의 파일 가운데 기록 폴더가 아니고 `not_code` 확장자가 아닌 것
- doc   docs 묶음 문서와 묶음 밖의 `*.md`(README.md, CLAUDE.md 등). 근거 표시로 가리킬 때만 걸린다
        (경로를 글에 적은 것만으로는 걸지 않는다). 원고와 포트폴리오, 기록은 걸게 하지 않는다
걸린 문서마다 `by`: 코드 파일로 걸린 줄이 하나라도 있으면 "code", 문서로만 걸렸으면 "doc"(합치기 카드가 둘을 나눠 센다)

가리키는 꼴(`how`, 결과에 그대로 남아 어느 자리에서 걸렸는지 보인다)
- `mark`   근거 표시 `[code:경로]`, `[docs:경로]`(docs 묶음 폴더 기준), 폴더(끝이 /는 아래 모두), 줄 번호 `[code:경로:10-20]`
- `path`   백틱 안이나 맨글의 저장소 경로(`bridge/x.py`, 폴더 `bridge/static/js/`). code만
- `name`   백틱 안의 파일 이름이나 경로 끝(`mergeprep.py`). 저장소에서 그 끝을 가진 파일이 하나뿐일 때만. code만
- `pair`   번호 짝(`pair_numbers`)

근거 표시, 코드 울타리와 HTML 주석 가르기, 저장소 읽기는 문서 문법 묶음 `bridge/doctext` 한 곳을 쓴다.

커밋 범위(`A..B`, `A...B`)를 주면 그 범위에서 바뀐 파일로 찾고, 문서는 B 판을 읽는다. 그 문서가 같은 범위에서 바뀌었으면
`fixed` True(고침), 아니면 False(안 고침). 파일 목록만 주면 작업 트리(또는 `rev`)를 읽고 `fixed`는 None(모름)이다.
근거 표시에 줄 번호가 있고 바뀐 줄을 알면(범위, 또는 `경로:줄-줄` 인자) 겹칠 때만 건다(`overlap` True). 바뀐 줄은 범위의
옛 쪽 줄 번호다. 줄 번호 없는 표시와 경로는 늘 건다(`overlap` None).
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from bridge.doctext import config as dcfg
from bridge.doctext import readme as _readme
from bridge.doctext.lines import TEXT, walk
from bridge.doctext.marks import MARK as ANY_MARK
from bridge.doctext.marks import REF_MARK as MARK
from bridge.doctext.marks import mark_target
from bridge.doctext.marks import split_range as _split_range
from bridge.doctext.repo import RepoError as DocrefsError
from bridge.doctext.repo import git_z, is_quoted, quoted_problem
from bridge.doctext.repo import gits as _gits
from bridge.doctext.repo import read_many as _read_many
from bridge.doctext.repo import tree as _tree

FOREMAN_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = dcfg.DocsConfig().sets["docs"]
PORTFOLIO_DIR = dcfg.DocsConfig().sets["portfolio"]

TICK = re.compile(r"`([^`\n]+)`")
TOKEN = re.compile(r"[\w./*-]+(?::\d+(?:-\d+)?)?")      # \w: 한글 이름 파일(`bridge/한글.py`)이 아스키 조각으로 쪼개져 안 걸리지 않게(11-19)
# 맨글 경로: 슬래시가 있고 확장자로 끝나는 것만(URL의 // 뒤, 다른 경로 가운데는 빼려고 앞 글자를 본다)
PLAIN = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6})(?::(\d+)(?:-(\d+))?)?(?![\w/-])")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s|^\s*\|")
EXT = re.compile(r"\.[A-Za-z0-9]{1,6}$")


# ── 설정: 원고 폴더와 문서 묶음 ─────────────────────────────
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


def doc_sets(src: str | None, docs_dir: str = DOCS_DIR, portfolio: str | None = PORTFOLIO_DIR) -> dict[str, str]:
    """{묶음 이름: 폴더}. 원고 폴더가 docs와 같으면 docs 하나로."""
    d = docs_dir if docs_dir.endswith("/") else docs_dir + "/"
    out = {"docs": d}
    if src and src != d:
        out["notion"] = src
    if portfolio:
        out["portfolio"] = portfolio
    return out


def resolve_sets(repo: str | Path, cfg: dcfg.DocsConfig, src: str | None = None, docs_dir: str | None = None,
                 config: str | Path | None = None) -> dict[str, str]:
    """docs.toml `[sets]`으로 문서 묶음을 정한다. 원고 폴더는 src 인자, docs.toml, notion.toml 차례. docs 폴더는 그 저장소에
    docs.toml이 있으면 그 값, 없으면 docs_dir 인자(합치기 카드가 FOREMAN `config/handoff.toml` `docs_dir`를 넘긴다), 그것도 없으면 기본값."""
    docs = cfg.sets.get("docs") or DOCS_DIR
    if cfg.source == "default" and docs_dir:
        docs = docs_dir
    notion = src if src is not None else (cfg.sets.get("notion") or manuscript_src(repo, config))
    return doc_sets(notion, docs, cfg.sets.get("portfolio"))


def kind_of(path: str, sets: dict[str, str], records: list[str] | tuple[str, ...] = ()) -> str | None:
    """문서 묶음 이름. 문서가 아니면(또는 기록 폴더면) None."""
    if not path.endswith(".md") or (records and path.startswith(tuple(records))):
        return None
    for k, d in sorted(sets.items(), key=lambda x: -len(x[1])):
        if path.startswith(d):
            return k
    return None


def trigger_kind(path: str, sets: dict[str, str], cfg: dcfg.DocsConfig | None = None) -> str | None:
    """걸게 하는 파일의 종류: "code", "doc", 또는 None(원고, 포트폴리오, 기록, 문서 묶음 아래 사진 같은 것)."""
    cfg = cfg or dcfg.DocsConfig()
    if path.startswith(tuple(cfg.records)):
        return None
    # [readme] 표가 켜진 저장소의 맨 위 README.md는 생성물이다(tools/docs.py readme). 사람이 고치는 글이 아니라 걸지 않는다.
    # 새 칸을 두지 않는다: 두 설정을 늘 맞춰야 하고 한쪽만 켜진 상태가 생긴다(11-17 사용자)
    if cfg.readme is not None and path in _readme.GENERATED:
        return None
    inside = any(d and path.startswith(d) for d in sets.values())
    if dcfg.not_code_match(path, cfg.not_code):
        if path.endswith(".md") and (not inside or kind_of(path, sets, cfg.records) == "docs"):
            return "doc"
        return None
    # 문서 묶음 폴더 아래 파일은 확장자와 상관없이 코드가 아니다(11-17 `portfolio/img/`의 png, gif, webm이 코드로 세어져
    # 합치기 카드에 헛걸림이 생겼다)
    return None if inside else "code"


def is_code(path: str, sets: dict[str, str], cfg: dcfg.DocsConfig | None = None) -> bool:
    return trigger_kind(path, sets, cfg) == "code"


# ── 문서 안의 가리킴(근거 표시, 머리 주석, 울타리와 주석 가르기는 bridge/doctext) ──
def _clean(tok: str) -> str:
    tok = tok.strip().strip(".,;")
    return tok[2:] if tok.startswith("./") else tok


def _pathlike(tok: str) -> bool:
    if not tok or tok.startswith(("-", "/", "~")) or ".." in tok.split("/") or not re.search(r"[^\W\d_]", tok):
        return False
    if not ("/" in tok or EXT.search(tok)):
        return False
    # 백틱과 맨글의 폴더, 글롭은 두 단계 이상만(`bridge/transcript/`). `bridge/` `tests/*`는 「그 폴더 전체」라는 말이라
    # 모든 파일에 걸려 헛걸림만 늘린다(11-17 첫 판에서 docs/roles.md가 바뀐 파일 20개 모두에 걸렸다). 근거 표시와 다루는 곳은 그대로 둔다
    fixed = re.split(r"[*?\[]", tok, maxsplit=1)[0]
    if (tok.endswith("/") or fixed != tok or not EXT.search(tok)) and len([s for s in fixed.split("/") if s]) < 2:
        return False
    return True


def refs_in(md: str, docs_dir: str = DOCS_DIR) -> list[dict[str, Any]]:
    """한 문서의 가리킴 [{line, target, range, how, ref}]. 코드 울타리와 HTML 주석 안은 보지 않는다. 머리 주석 「다루는 곳」도
    읽지 않는다(덮기 검사 몫, 11-17 3단계). `[docs:x]`의 target은 docs 묶음 폴더 기준 경로(`docs/x`)다."""
    out: list[dict[str, Any]] = []
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
            t = mark_target(mk["k"], _clean(mk["v"]), docs_dir)      # 점검, 노션 판과 같은 풀기(code, repo는 맨 위 기준)
            if t:
                add(t[0], (t[1], t[2] or t[1]) if t[1] else None, "mark", mk.group(0))
        rest = ANY_MARK.sub(" ", ln)
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


def matches(target: str, how: str, code: str, names: dict[str, list[str]], kind: str = "code") -> bool:
    """가리킴 하나가 걸게 하는 파일 하나를 덮나. 폴더(끝이 /)는 그 아래 모두, 글롭은 fnmatch(*가 /도 넘는다),
    `name`은 저장소에서 그 끝을 가진 파일이 하나뿐일 때 그 파일만. 문서(kind doc)는 근거 표시만 본다.
    how "covers"는 가리킴이 아니라 파일 인자 폴더, 글롭을 펼칠 때 쓴다(폴더 아래 모두, 글롭)."""
    if kind == "doc" and how != "mark":
        return False
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
        if ln.startswith(("--- ", "+++ ")) and is_quoted(ln[4:]):
            raise DocrefsError(quoted_problem(ln[4:]))
        if ln.startswith("--- "):
            cur = ln[6:] if ln.startswith("--- a/") else None
        elif ln.startswith("+++ ") and cur is None and ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("@@") and cur:
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? ", ln)
            if m:
                s, n = int(m[1]), int(m[2] if m[2] is not None else 1)
                # 줄을 넣기만 한 덩어리(-s,0)는 옛 줄을 바꾸지 않는다. s와 s+1 사이로 적어(s+1, s) 근거 범위 안쪽에 끼어들 때만
                # 겹치게 한다(인프라 11-17 고장: CLAUDE.md 34줄 뒤에 넣은 줄이 34줄을 건 근거를 헛걸었다)
                out.setdefault(cur, []).append((s + 1, s) if n == 0 else (s, s + n - 1))
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


def _pair_hits(trigger: str, doc_paths: list[str], sets: dict[str, str], records: list[str]) -> list[str]:
    """docs 묶음의 `NN_*.md` → 같은 번호 원고 `NN_*.md`, `NN_*/` 아래 글(바로 docs 묶음 폴더 아래 것만)."""
    src = sets.get("notion")
    m = re.match(rf"^{re.escape(sets['docs'])}(\d{{2}})_[^/]*\.md$", trigger)
    if not m or not src:
        return []
    return [p for p in doc_paths if kind_of(p, sets, records) == "notion" and re.match(rf"^{m.group(1)}_", p[len(src):])]


def scan(repo: str | Path, files: list[str] | None = None, rng: str | None = None, rev: str | None = None,
         src: str | None = None, docs_dir: str | None = None, config: str | Path | None = None,
         para_cap: int = 400, cfg: dcfg.DocsConfig | None = None) -> dict[str, Any]:
    """거꾸로 찾기 한 번. files(`경로`, `폴더/`, 글롭, `경로:시작-끝`) 또는 rng 중 하나는 있어야 한다. 둘 다 주면 범위의 파일 중 files만.
    cfg를 주지 않으면 그 저장소 `.foreman/docs.toml`(작업 트리, 범위 없이 rev를 주면 그 판)을 읽는다.

    돌려주는 것: {repo, range, rev, sets, config, code, triggers, docs: [{doc, kind, fixed, by, files, hits: [{line, heading,
    para_from, para_to, para, how, ref, code, range, overlap}]}], total, unfixed, by, warnings}. `code`는 걸게 한 코드 파일,
    `triggers`는 코드와 문서 모두, 걸린 줄의 `code`는 그 줄이 가리킨 걸게 한 파일(문서일 수도 있다).
    맨 위 `by`는 {"code": {total, unfixed}, "doc": {total, unfixed}}(코드로 걸린 문서와 문서로만 걸린 문서, 둘을 더하면 total).
    docs는 안 고친 것, 걸린 수가 많은 것 먼저."""
    repo = str(Path(repo).resolve())
    if not files and not rng:
        raise DocrefsError("코드 파일이나 커밋 범위를 주어야 합니다")
    if cfg is None:
        try:
            cfg = dcfg.load(repo, None if rng else rev)
        except dcfg.DocsConfigError as e:
            raise DocrefsError(f"문서 설정을 읽지 못했습니다: {e}") from e
    sets = resolve_sets(repo, cfg, src, docs_dir, config)
    warnings: list[str] = list(cfg.warnings)
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
        changed = set(git_z(repo, "diff", "--name-only", "--no-renames", a, b))
        trig = sorted(p for p in changed if trigger_kind(p, sets, cfg))
        if given:
            trig = [p for p in trig if p in given or any(matches(g, "path", p, {}) for g in given)]
        rev = b
        tracked = _tree(repo, rev)
    else:
        tracked = _tree(repo, rev)
        trig = []
        for g, r in given.items():
            if g.endswith("/") or _glob(g):
                under = [p for p in tracked if matches(g, "covers", p, {}) and trigger_kind(p, sets, cfg)]
                if not under:
                    warnings.append(f"{g}: 아래에 걸게 하는 파일이 없습니다")
                trig += under
            elif trigger_kind(g, sets, cfg):
                trig.append(g)
                if r:
                    lines_of[g] = r
            else:
                warnings.append(f"{g}: 코드도 docs 문서도 아니라 찾지 않습니다(원고, 포트폴리오, 기록 폴더는 걸게 하지 않습니다)")
        trig = sorted(set(trig))
    kinds = {p: trigger_kind(p, sets, cfg) or "code" for p in trig}
    code = [p for p in trig if kinds[p] == "code"]
    empty = {"repo": repo, "range": rng, "rev": rev, "sets": sets, "config": cfg.source, "code": code, "triggers": trig,
             "docs": [], "total": 0, "unfixed": 0, "by": split_by([]), "warnings": warnings}
    if not trig:
        return empty
    names = _names(sorted(set(tracked) | set(trig)))
    doc_paths = [p for p in _tree(repo, rev, list(sets.values())) if kind_of(p, sets, cfg.records)]
    bodies = _read_many(repo, rev, doc_paths)
    raw_hits: dict[str, list[dict[str, Any]]] = {}
    for path in doc_paths:
        body = bodies.get(path)
        if body is None:
            continue
        refs = refs_in(body, sets["docs"])
        if not refs:
            continue
        lines = body.splitlines()
        heads = None
        for r in refs:
            hit = [t for t in trig if t != path and matches(r["target"], r["how"], t, names, kinds[t])]
            if not hit:
                continue
            if heads is None:
                heads = _headings(lines)
            pa, pb, ptxt = paragraph(lines, r["line"], para_cap)
            for t in hit:
                raw_hits.setdefault(path, []).append({
                    "line": r["line"], "heading": heads[r["line"] - 1],
                    "para_from": pa, "para_to": pb, "para": ptxt, "how": r["how"], "ref": r["ref"], "code": t,
                    "range": list(r["range"]) if r["range"] else None, "overlap": None})
    if cfg.pair_numbers:
        for t in trig:
            for p in _pair_hits(t, doc_paths, sets, cfg.records):
                raw_hits.setdefault(p, []).append({
                    "line": 1, "heading": "(번호 짝)", "para_from": 1, "para_to": 1, "para": "", "how": "pair",
                    "ref": f"번호 짝 {t}", "code": t, "range": None, "overlap": None})
    # 줄 번호가 있는 근거 표시만 바뀐 줄과 맞댄다. 바뀐 줄을 알고 겹치지 않으면 걸린 것으로 치지 않는다
    want = sorted({h["code"] for hs in raw_hits.values() for h in hs if h["range"] and h["how"] == "mark"})
    if want and rng and a and b:
        try:
            lines_of = changed_lines(repo, a, b, want)
        except DocrefsError as e:
            warnings.append(f"바뀐 줄을 읽지 못해 줄 번호를 보지 않았습니다: {e}")
    docs = []
    for path, hs in raw_hits.items():
        keep = []
        for h in hs:
            if h["range"] and h["how"] == "mark" and h["code"] in lines_of:
                h["overlap"] = any(s <= h["range"][1] and h["range"][0] <= e for s, e in lines_of[h["code"]])
                if not h["overlap"]:
                    continue
            keep.append(h)
        if not keep:
            continue
        keep.sort(key=lambda h: (h["line"], h["code"]))
        by = "code" if any(kinds[h["code"]] == "code" for h in keep) else "doc"
        docs.append({"doc": path, "kind": kind_of(path, sets), "fixed": (path in changed) if rng else None, "by": by,
                     "files": sorted({h["code"] for h in keep}), "hits": keep})
    docs.sort(key=lambda d: (d["fixed"] is True, -len(d["hits"]), d["doc"]))
    return {**empty, "docs": docs, "total": len(docs), "unfixed": sum(1 for d in docs if d["fixed"] is False), "by": split_by(docs)}


def config_changed(repo: str | Path, rng: str) -> bool:
    """범위가 문서 설정(`.foreman/docs.toml`)을 바꿨나. 거꾸로 찾기는 설정을 작업 트리 판으로 읽으므로, 바꿨으면 그 셈은 옛 값 기준이다."""
    a, b = parse_range(str(repo), rng)
    return bool(_gits(repo, "diff", "--name-only", "--no-renames", a, b, "--", dcfg.PATH).strip())


def split_by(docs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """코드로 걸린 문서와 문서로만 걸린 문서의 수(11-17 사용자 결정 8). 2단계 문서 트리거로 FOREMAN 합치기 카드 수가 407에서 600으로
    늘었는데 코드로 새로 걸린 것은 0이었다. 섞어 보이면 둘 다 안 보게 된다."""
    out = {"code": {"total": 0, "unfixed": 0}, "doc": {"total": 0, "unfixed": 0}}
    for d in docs:
        k = out["code" if d.get("by", "code") == "code" else "doc"]
        k["total"] += 1
        k["unfixed"] += d.get("fixed") is False or d.get("stale") is True
    return out


# ── 글 모양(tools/docs.py refs) ─────────────────────────────
KIND_KO = {"docs": "docs", "notion": "노션 원고", "portfolio": "포트폴리오"}
HOW_KO = {"mark": "근거 표시", "path": "경로", "name": "파일 이름", "pair": "번호 짝"}
BY_KO = {"code": "코드로", "doc": "문서로만"}


def fixed_ko(v: bool | None) -> str:
    return "고침" if v is True else "안 고침" if v is False else "모름"


def render(res: dict[str, Any], brief: bool = False, unfixed: bool = False) -> str:
    out = []
    n_doc = len(res.get("triggers", res["code"])) - len(res["code"])
    what = f"코드 파일 {len(res['code'])}개" + (f", 문서 {n_doc}개" if n_doc else "")
    head = f"걸리는 문서 {res['total']}"
    if res["range"]:
        head += f", 안 고침 {res['unfixed']} (범위 {res['range']}, 바뀐 {what})"
    else:
        head += f" ({what}, 고쳤는지는 범위를 주어야 압니다)"
    out.append(head)
    if res["total"]:
        out.append(split_line(res))
    for w in res.get("warnings") or []:
        out.append(f"⚠ {w}")
    for d in res["docs"]:
        if unfixed and d["fixed"] is not False:
            continue
        lines = sorted({h["line"] for h in d["hits"]})
        out.append(f"\n[{fixed_ko(d['fixed'])}] {d['doc']} ({KIND_KO.get(d['kind'], d['kind'])}, {BY_KO[d.get('by', 'code')]} 걸림) "
                   f"줄 {', '.join(map(str, lines[:12]))}"
                   + (" …" if len(lines) > 12 else "") + f" ← {', '.join(d['files'])}")
        if brief:
            continue
        last = None
        for h in d["hits"]:
            key = (h["para_from"], h["code"], h["how"] == "pair")
            if key == last:
                continue
            last = key
            rng = f" 줄 {h['range'][0]}-{h['range'][1]}" + (" (바뀐 줄과 겹침)" if h["overlap"] else "") if h["range"] else ""
            out.append(f"  {h['line']}: 「{h['heading'] or '(제목 없음)'}」 {HOW_KO.get(h['how'], h['how'])} {h['ref']} → {h['code']}{rng}")
            if h["how"] != "pair":
                span = f"{h['para_from']}-{h['para_to']}" if h["para_to"] != h["para_from"] else str(h["para_from"])
                out.append(f"     ({span}) {h['para']}")
    return "\n".join(out)


# ── 합치기 카드 모양 ────────────────────────────────────────
def card_docs(res: dict[str, Any], limit: int = 12, hits: int = 5) -> dict[str, Any]:
    """scan 결과 → 합치기 카드 `docs` 칸(옛 정리 후보 모양을 잇는다: where, lines, count, files, stale). `stale` = 이 브랜치에서
    안 고침. 더한 칸: kind(docs, notion, portfolio), by(code 코드로 걸림, doc 문서로만 걸림), hits(줄, 제목, 문단 앞부분),
    전체 수 total과 안 고친 수 unfixed, 나눈 수 by(목록을 자르기 전). 목록은 코드로 걸린 것 먼저."""
    groups = []
    for d in sorted(res["docs"], key=lambda d: d.get("by", "code") != "code"):
        lines = sorted({h["line"] for h in d["hits"]})
        groups.append({"where": d["doc"], "kind": d["kind"], "by": d.get("by", "code"), "lines": lines[:8], "count": len(lines),
                       "files": d["files"], "stale": d["fixed"] is False,
                       "hits": [{"line": h["line"], "heading": h["heading"][:80], "text": h["para"][:160], "code": h["code"]}
                                for h in d["hits"][:hits]]})
    return {"readme": [], "docs": groups[:limit], "total": res["total"], "unfixed": res["unfixed"],
            "by": res.get("by") or split_by(res["docs"]), "code": len(res["code"]), "warnings": res.get("warnings") or []}


# ── 코더 첫 글에 붙이는 묶음(11-17 사용자 지시 21) ─────────────
# 말투와 깊이 같은 원고 기준은 모든 저장소가 한 벌(`docs/manuscript_rules.md`, bridge/manuscript_rules.py)이고 아래 「원고 쓰는 기준」
# 절로 붙는다(11-17 문서 도구 합치기 4단계). 여기 두 줄은 저장소마다 다른 것(근거 표시, 머리 주석, 문서 자리)만 가리킨다
TONE_FOREMAN = ("FOREMAN만 다른 것은 `docs/style_guide.md`를 따른다. 노션 원고(`notion/`)와 포트폴리오(`portfolio/`)는 문장 끝 근거 표시"
                "(`[code:경로]` 등, git 원고에만 남고 노션 판에서는 떼어진다)를 달고, 머리 주석 「다루는 곳」이 바뀌면 함께 고친다. "
                "원고와 포트폴리오 쓰는 차례는 `bridge/scribe_room.py` `task_prompt`")
TONE_OTHER = "이 저장소만 다른 것(문서 자리, 근거 표시, 차례, 금지값)은 이 저장소의 CLAUDE.md와 `docs/style_guide.md`가 정한 것을 따른다"


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
    from bridge import manuscript_rules
    from bridge.roles import CODER_DOCS_RULE, DOCS_RULE_ROLES
    if role not in DOCS_RULE_ROLES:
        return ""
    own = _same_repo(cwd, FOREMAN_ROOT)
    if own:
        cmd = ".venv/bin/python tools/docs.py refs"
    else:
        py = FOREMAN_ROOT / ".venv" / "bin" / "python"
        cmd = f"{py if py.exists() else 'python3'} {FOREMAN_ROOT / 'tools' / 'docs.py'} --repo . refs"
    return ("\n\n## 고친 코드의 문서도 함께 (코더 규칙, 브리지가 붙임)\n"
            f"- {CODER_DOCS_RULE}\n"
            f"- 거꾸로 찾는 도구(읽기만 한다): `{cmd} --range main...HEAD --unfixed`(이 브랜치가 바꾼 코드를 가리키는데 아직 안 고친 문서와 줄), "
            f"커밋 전이면 `{cmd} <고친 파일 경로>`. 합치기 카드에도 「코드로 걸린 문서 N, 안 고침 M」으로 보인다(문서만 바꿔 걸린 것은 따로 센다). "
            "걸린 문단이 지금 코드와 맞으면 그대로 둔다\n"
            f"- {TONE_FOREMAN if own else TONE_OTHER}\n"
            "- 그 저장소 CLAUDE.md가 사람 승인으로 정한 문서(README.md, CLAUDE.md 등)는 고쳐도 합치기 카드가 사람에게 간다. "
            "고치지 못한 문서는 마지막 보고에(결과 기록을 남기는 저장소면 거기에도) 「무엇이 걸리는지」로 적는다"
            "\n\n" + manuscript_rules.block("coder", own, "## 원고 쓰는 기준, 문서와 코드 주석을 쓸 때"))


def split_line(d: dict[str, Any]) -> str:
    """「코드로 걸린 문서 N, 안 고침 M / 문서로만 걸린 문서 K, 안 고침 L」. 0인 쪽은 뺀다."""
    by = d.get("by") or split_by(d.get("docs") or [])
    parts = [f"{'코드로 걸린' if k == 'code' else '문서로만 걸린'} 문서 {by[k]['total']}, 안 고침 {by[k]['unfixed']}"
             for k in ("code", "doc") if by.get(k, {}).get("total")]
    return " / ".join(parts)


def count_line(d: dict[str, Any] | None) -> str:
    """카드 글, 알림 글이 같이 쓰는 한 줄. 코드로 걸린 것과 문서로만 걸린 것을 나눈다(11-17 사용자 결정 8, `split_line`).
    `by`가 없는 옛 카드는 「걸리는 문서 N, 안 고침 M」. 걸리는 문서가 없으면 빈 글."""
    if not d:
        return ""
    total = d.get("total", len(d.get("docs") or []))
    if not total:
        return ""
    if d.get("by"):
        return split_line(d)
    unfixed = d.get("unfixed", sum(1 for x in d.get("docs") or [] if x.get("stale")))
    return f"걸리는 문서 {total}, 안 고침 {unfixed}"
