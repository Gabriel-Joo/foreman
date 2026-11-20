"""문서 점검(11-17 문서 도구 합치기 3단계). 인프라 `scripts/docs-check.py` 1~7번 규칙을 묶음 위로 옮겼다. 읽기만 한다.

    1. 머리 주석: 편마다 「다루는 곳」과 「읽은 커밋」. 읽은 커밋은 편마다 저장소에 있어야 한다(read_commit "piece").
       "set"(인프라 전환 동안만)은 원고와 docs가 하나, 포트폴리오끼리 하나
    2. 다루는 곳: 적힌 파일, 폴더, 글롭이 있다(files_at 판)
    3. 근거 표시: 쓸 수 있는 종류(check.kinds), 커밋이 있다, 파일이 있고 줄 범위가 맞다(files_at 판), 턴 번호는 숫자
    4. 덮기: 문서 묶음과 기록 밖 추적 파일 하나하나가 check.cover_by 묶음 어느 편의 다루는 곳에 든다.
       시험 파일(check.tests 무늬)은 다루는 곳에 들지 않아도 덮은 것으로 친다(11-20)
    5. 편 사이 참조: → 「제목」이 같은 묶음(check.xref면 그 묶음) 편 하나의 첫 # 줄과 같다
       「」 없이 쓴 참조(→ 07 합치기, 「→ 포스트잇」. 판정은 `titles.bare_xrefs`)는 check.xref_base 뒤에 더하거나 고친 줄만 틀림이고
       옛 줄은 의심이다(줄표 검사와 같은 새 줄, `dashdot.new_doc_rows`). 칸이 없으면 모두 의심으로 세고 notes에 알린다
    6. 금지어(check.banned 묶음만): IP 주소, 도메인(check.domains_in 묶음은 allowed_domains를 뺀다), 홈 경로, 토큰 꼴, 포트 번호
    7. 그림 `![…](경로)`: 파일이 있다
    8. 새 줄의 em dash와 가운뎃점(4단계, `bridge/doctext/dashdot.py`): check.dashdot_base 뒤에 더한 문서 줄과 코드 주석.
       칸이 없으면 검사하지 않고 결과 notes에 알린다(틀림으로 세지 않는다)
    9. README(문서 정리 B, `bridge/doctext/readme.py`): `[readme]` 표가 있는 저장소만. 맨 위 README.md가 지금 원고로 만든 글
       (제목, 포트폴리오 00편 첫 문단, 두 묶음 편 목록, 노션 링크, `[readme] docs`면 docs 차례)과 한 글자라도 다르면 틀림. 노션 주소는 부르는 쪽이 게시 기록에서
       읽어 넘긴다(links). 넘기지 못하면 README에 걸린 주소를 그대로 두고 나머지만 맞대며 결과 notes에 알린다.
       표가 없으면 검사하지 않고 notes에 알린다
    + 의심(틀림이 아니다): 숫자나 인용이 있는데 근거 표시가 없는 본문 줄(check.claim, check.claim_min)

「다루는 곳」은 파일 단위 자리라 덮기 검사(4)만 읽는다. 밀림(바뀐 코드를 가리키는 줄)은 거꾸로 찾기(`bridge/docrefs.py`)가
근거 표시로만 본다(11-17 사용자 결정 1). 근거 확인기(bridge/evidence.py)와 같은 판정(근거 파일과 줄, 다루는 곳 경로, 의심 줄 꼴)은
여기 한 곳(`mark_problem`, `covers_problem`, `is_claim`)이고 근거 확인기가 가져다 쓴다. 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import fnmatch
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from bridge.doctext import dashdot, readme
from bridge.doctext.config import DocsConfig, not_code_match, not_code_skip
from bridge.doctext.head import COVERS, READ, SHA, bad_covers, parse_head
from bridge.doctext.lines import COMMENT, TEXT, walk
from bridge.doctext.marks import MARK, STRIP, code_doc, mark_path, mark_target, repo_problem
from bridge.doctext.repo import RepoError, git_z, gits, is_quoted, quoted_problem, read_many, tree
from bridge.doctext.titles import XREF, bare_xrefs, first_h1, xref_index, xref_lookup

# 근거 확인기가 11-06부터 쓰던 꼴. 사진 줄(![설명](경로))도 뺀다(설명의 근거는 사진 자체다)
SKIP_LINE = re.compile(r"^\s*(#|>|\||```|---|!\[|\s*$)")
IMG = re.compile(r"!\[[^\]]*\]\((?P<src>[^)\s]+)\)")
NUMBERED = re.compile(r"^\d{2}_[^/]*\.md$")
BANNED = [   # 인프라 docs-check.py 6번과 같다
    ("IP 주소", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("도메인", re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:dev|com|kr|io|net|org|local|ai|app|cloud)\b", re.I)),
    ("홈 경로", re.compile(r"(?:/home/|~/)")),
    ("토큰 꼴", re.compile(r"\b(?:[0-9a-f]{32,}|[A-Za-z0-9_-]{40,})\b")),
    ("포트 번호", re.compile(r"(?::\d{2,5}\b|포트\s*\d{2,5}|\d{2,5}\s*번?\s*포트)")),
]


# ── 파일 판: 작업 트리(FsView) 또는 커밋 하나의 추적 파일(GitView) ──
class FsView:
    """작업 트리. 근거 확인기(서기 worktree)와 점검 기본(files_at "worktree")."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def is_file(self, p: str) -> bool:
        return (self.root / p).is_file()

    def is_dir(self, p: str) -> bool:
        return (self.root / p).is_dir()

    def n_lines(self, p: str) -> int:
        return len((self.root / p).read_text(encoding="utf-8", errors="replace").splitlines())

    def glob(self, pat: str) -> bool:
        return bool(list(self.root.glob(pat)))


class GitView:
    """커밋 하나의 추적 파일(인프라 files_at "read", 또는 --rev)."""

    def __init__(self, repo: str | Path, rev: str):
        self.repo, self.rev = str(repo), rev
        self.files = set(tree(repo, rev))
        self._n: dict[str, int] = {}

    def is_file(self, p: str) -> bool:
        return p in self.files

    def is_dir(self, p: str) -> bool:
        pre = p.rstrip("/") + "/"
        return any(f.startswith(pre) for f in self.files)

    def n_lines(self, p: str) -> int:
        if p not in self._n:
            self._n[p] = len(read_many(self.repo, self.rev, [p]).get(p, "").splitlines())
        return self._n[p]

    def glob(self, pat: str) -> bool:
        return any(fnmatch.fnmatchcase(f, pat) for f in self.files)


def _glob(p: str) -> bool:
    return any(ch in p for ch in "*?[")


# ── 근거 확인기와 같이 쓰는 판정 ─────────────────────────────
def mark_problem(kind: str, v: str, view: FsView | GitView, docs_dir: str = "docs/", log_dir: str = "log/") -> str | None:
    """파일 종류 근거 표시(`log`, `docs`, `code`, `repo`)의 틀린 까닭. 맞으면 None. 경로 풀기는 `marks.mark_target` 한 곳이다.
    `[code:]`가 문서(.md)를 가리키는 것은 여기서 세지 않는다(옛 줄이 많은 저장소가 있어 점검이 기준 커밋으로 가른다, `code_doc`)."""
    t = mark_target(kind, v, docs_dir, log_dir)
    if not t:
        return "모양을 알아보지 못했습니다"
    path, ta, tb = t
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        return "저장소 밖을 가리킵니다"
    if kind == "repo":
        why = repo_problem(v, docs_dir, log_dir)
        if why:
            return why
    if kind == "code" and ta is None and view.is_dir(path):
        return None                                   # 폴더 [code:bridge/static/js/]
    if not view.is_file(path):
        return f"{path} 파일이 없습니다"
    if ta is not None:
        n = view.n_lines(path)
        a, b = ta, tb or ta
        if a < 1 or b > n or b < a:
            return f"줄 범위가 맞지 않습니다(파일은 {n}줄)"
    return None


def covers_problem(c: str, view: FsView | GitView) -> str | None:
    """머리 주석 다루는 곳 값 하나의 틀린 까닭. 맞으면 None."""
    if bad_covers([c]):
        return "저장소 밖을 가리킵니다"
    if _glob(c):
        return None if view.glob(c) else "그 글롭에 맞는 파일이 없습니다"
    p = c.rstrip("/")
    return None if view.is_file(p) or view.is_dir(p) else "그 경로가 없습니다"


def is_claim(line: str, claim: re.Pattern[str], min_len: int) -> bool:
    """근거 표시가 있어야 할 줄(의심). 근거 표시가 든 줄, 제목, 표, 인용, 사진 줄은 아니다. → 「다른 편」 안내는 주장이 아니다."""
    if MARK.search(line) or SKIP_LINE.match(line) or len(line.strip()) < min_len:
        return False
    return bool(claim.search(XREF.sub("", line)))


def commit_exists(repo: str | Path, sha: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{6,40}", sha):
        return False
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True,
                          timeout=15).returncode == 0


def cover_matches(pat: str, files: list[str]) -> list[str]:
    """다루는 곳 값 하나가 덮는 파일. 폴더(끝이 /), 글롭(fnmatch, *가 /도 넘는다), 같은 경로, / 없이 쓴 폴더."""
    if pat.endswith("/"):
        return [f for f in files if f.startswith(pat)]
    if _glob(pat):
        return [f for f in files if fnmatch.fnmatchcase(f, pat)]
    return [f for f in files if f == pat or f.startswith(pat + "/")]


# ── 점검 한 번 ───────────────────────────────────────────────
def pieces_of(repo: str, rev: str | None, folder: str, numbered: bool, records: list[str]) -> list[str]:
    """그 묶음의 편. 작업 트리면 아직 git add 하지 않은 새 편도 본다(인프라 docs-check.py처럼 파일로 본다. 커밋 전에 돌리는 점검이다)."""
    if rev:
        names = tree(repo, rev, [folder])
    else:
        names = [x for x in git_z(repo, "ls-files", "--cached", "--others", "--exclude-standard", "--", folder)
                 if (Path(repo) / x).is_file()]
    out = [p for p in sorted(set(names)) if p.endswith(".md") and not p.startswith(tuple(records))]
    if numbered:
        out = [p for p in out if NUMBERED.match(p[len(folder):])]
    return sorted(out)


README_OFF = "[readme] 표가 없어 README 생성 검사를 하지 않았습니다(.foreman/docs.toml)"


def readme_project(repo: str, cfg: DocsConfig) -> str:
    """게시 기록의 프로젝트 이름: [readme] project, 없으면 origin 주소의 저장소 이름, 그것도 없으면 저장소 폴더 이름."""
    if cfg.readme and cfg.readme.get("project"):
        return cfg.readme["project"]
    try:
        url = gits(repo, "remote", "get-url", "origin").strip()
    except RepoError:
        url = ""
    name = re.split(r"[/:]", url.rstrip("/"))[-1] if url else ""
    name = name[:-4] if name.endswith(".git") else name
    return name or Path(gits(repo, "rev-parse", "--show-toplevel").strip()).name


def _header_text(repo: str, rev: str | None, rel: str) -> str | None:
    """`[readme] header_file`의 글. 없거나 못 읽거나 저장소 밖으로 풀리는 링크면 None(그러면 점검이 틀림으로 센다)."""
    if not rev:
        f = Path(repo) / rel
        try:
            if not f.resolve().is_relative_to(Path(repo).resolve()) or not f.is_file():
                return None
        except OSError:
            return None
    return read_many(repo, rev, [rel]).get(rel)


def readme_build(repo: str, rev: str | None, cfg: DocsConfig, sets: dict[str, str],
                 links: dict[str, str | None]) -> readme.Built:
    """지금 원고로 만든 README 글. links는 {편 경로: 노션 주소}."""
    s = {k: sets[k] for k in readme.ORDER if sets.get(k)}
    pieces = {k: pieces_of(repo, rev, d, False, cfg.records) for k, d in s.items()}
    bodies = read_many(repo, rev, sorted({p for ps in pieces.values() for p in ps}))
    rd = cfg.readme or {}
    title = rd.get("title") or readme_project(repo, cfg)
    docs = None
    if rd.get("docs"):
        folder = sets.get("docs")
        if not folder:
            b = readme.Built(errors=["docs 묶음 폴더가 없습니다(.foreman/docs.toml [sets] docs). [readme] docs를 켤 수 없습니다"])
            return b
        paths = pieces_of(repo, rev, folder, False, cfg.records)
        docs = readme.doc_rows(folder, paths, read_many(repo, rev, paths), rd.get("docs_summary", "para"),
                               tuple(rd.get("docs_skip", [])), bool(rd.get("docs_numbered_only", False)))
    header = None
    if rd.get("header_file"):
        hp = rd["header_file"]
        header = (hp, _header_text(repo, rev, hp))
    return readme.build(title, s, pieces, bodies, links, docs, header)


def readme_check(repo: str, rev: str | None, cfg: DocsConfig, sets: dict[str, str],
                 links: dict[str, str | None] | None) -> tuple[list[str], list[str]]:
    """(틀림, 알림). 점검 9번."""
    if cfg.readme is None:
        return [], [README_OFF]
    md = read_many(repo, rev, [readme.PATH]).get(readme.PATH)
    if md is None:
        return ["README.md가 없습니다(tools/docs.py readme로 만듭니다)"], []
    notes = []
    if links is None:
        b0 = readme_build(repo, rev, cfg, sets, {})
        have = readme.links_in(md)
        links = {b0.tops[k]: u for k, u in have.items() if k in b0.tops}
        notes.append("게시 기록을 읽지 못해 README에 걸린 노션 주소는 맞대지 않았습니다(나머지는 맞댐)")
    b = readme_build(repo, rev, cfg, sets, links)
    if b.errors:
        return [f"README를 만들 수 없습니다: {w}" for w in b.errors], notes
    why = readme.diff(md, b.text)
    errs = [f"README.md가 지금 원고로 만든 글과 다릅니다({why}). tools/docs.py readme로 다시 만듭니다"] if why else []
    return errs, notes + b.notes


def run(repo: str, rev: str | None, cfg: DocsConfig, sets: dict[str, str],
        links: dict[str, str | None] | None = None) -> dict[str, Any]:
    """돌려주는 것: {errors: [{doc, line, what}], suspects: [...], sets: {묶음: 편 수}, marks, reads, cover: {target, covered}}.
    doc이 None인 틀림은 저장소 전체(읽은 커밋 묶음, 덮기)."""
    ck = cfg.check
    claim = re.compile(ck.claim)
    errors: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []

    def err(doc: str | None, line: int | None, what: str) -> None:
        errors.append({"doc": doc, "line": line, "what": what})

    base: FsView | GitView = GitView(repo, rev) if rev else FsView(repo)
    checked = {k: pieces_of(repo, rev, sets[k], k in ck.numbered_only, cfg.records) for k in ck.sets if sets.get(k)}
    for k in ck.sets:
        if not sets.get(k):
            err(None, None, f"점검할 묶음 {k}의 폴더가 없습니다(.foreman/docs.toml [sets] 또는 notion.toml src)")
    want_titles = {ck.xref.get(k, k) for k in checked}
    every = {k: (checked[k] if k in checked else pieces_of(repo, rev, sets[k], k in ck.numbered_only, cfg.records))
             for k in want_titles if sets.get(k)}
    bodies = read_many(repo, rev, sorted({p for ps in [*checked.values(), *every.values()] for p in ps}))
    index = {k: xref_index({p: first_h1(bodies.get(p, ""))[1] for p in ps}) for k, ps in every.items()}

    # 1. 머리 주석과 읽은 커밋
    heads: dict[str, dict[str, Any]] = {}
    for k, ps in checked.items():
        for p in ps:
            h = parse_head(bodies.get(p, ""), ck.head_at)
            if h is None or not h["covers"] or not h["read"]:
                err(p, None, f"머리 주석에 {COVERS} 또는 {READ}이 없습니다")
                continue
            heads[p] = h
    commits: dict[str, bool] = {}

    def has(sha: str) -> bool:
        if sha not in commits:
            commits[sha] = commit_exists(repo, sha)
        return commits[sha]

    read_of: dict[str, str | None] = {}          # 편 → 파일 판으로 쓸 읽은 커밋(없으면 None, base 판)
    reads: dict[str, list[str]] = {}
    if cfg.read_commit == "set":
        groups = {"main": [p for k, ps in checked.items() if k != "portfolio" for p in ps],
                  "portfolio": checked.get("portfolio", [])}
        for g, ps in groups.items():
            rs = sorted({heads[p]["read"] for p in ps if p in heads})
            reads[g] = rs
            if not ps:
                continue
            ko = "포트폴리오 " if g == "portfolio" else ""
            if len(rs) != 1:
                err(None, None, f"{ko}읽은 커밋이 하나가 아닙니다: {rs}")
                continue
            if not has(rs[0]):
                err(None, None, f"{ko}읽은 커밋 {rs[0]}이 저장소에 없습니다")
                continue
            for p in ps:
                read_of[p] = rs[0]
    else:
        for p, h in heads.items():
            reads.setdefault("piece", [])
            if not SHA.fullmatch(h["read"]) or not has(h["read"]):
                err(p, h["line"], f"{READ} {h['read']}이 저장소에 없습니다")
            else:
                read_of[p] = h["read"]
        reads["piece"] = sorted(set(read_of.values()))
    views: dict[str, GitView] = {}

    def view_of(p: str) -> FsView | GitView:
        r = read_of.get(p) if ck.files_at == "read" else None
        if not r:
            return base
        if r not in views:
            views[r] = GitView(repo, r)
        return views[r]

    # 5의 「」 없는 참조: 기준 커밋 뒤 새 줄(없거나 못 읽으면 None, 모두 의심)
    xb_base = ck.xref_base
    xb_new: dict[str, set[int]] | None = None
    xb_note: str | None = None
    if xb_base:
        try:
            xb_new = dashdot.new_doc_rows(repo, xb_base, rev, tuple(d for d in sets.values() if d) or dashdot.DOC_DIRS,
                                          (*tuple(cfg.records), *dashdot.TOOL_DIRS))
        except dashdot.DashDotError as e:
            err(None, None, f"「」 없는 편 사이 참조 검사를 돌리지 못했습니다: {e}")
    xb = {"base": xb_base, "new": 0, "old": 0, "ran": xb_new is not None}
    # 3의 문서를 가리키는 [code:]: 같은 길, 기준 커밋은 check.code_doc_base(11-20). 다른 저장소의 옛 줄이 점검을 깨지 않게
    cd_base = ck.code_doc_base
    cd_new: dict[str, set[int]] | None = None
    if cd_base and cd_base == xb_base:
        cd_new = xb_new
    elif cd_base:
        try:
            cd_new = dashdot.new_doc_rows(repo, cd_base, rev, tuple(d for d in sets.values() if d) or dashdot.DOC_DIRS,
                                          (*tuple(cfg.records), *dashdot.TOOL_DIRS))
        except dashdot.DashDotError as e:
            err(None, None, f"문서를 가리키는 [code:] 검사를 돌리지 못했습니다: {e}")
    cd = {"base": cd_base, "new": 0, "old": 0, "ran": cd_new is not None}
    docs_dir = sets.get("docs") or "docs/"
    log_dir = cfg.records[0] if cfg.records else "log/"

    # 2, 3, 5, 6, 7 편마다
    n_marks = 0
    for k, ps in checked.items():
        idx = index.get(ck.xref.get(k, k))
        allowed = cfg.allowed_domains if k in ck.domains_in else []
        for p in ps:
            v = view_of(p)
            h = heads.get(p)
            for c in (h or {}).get("covers", []):
                why = covers_problem(c, v)
                if why:
                    err(p, h["line"], f"{COVERS} 「{c}」: {why}")
            lines = bodies.get(p, "").splitlines()
            for i0, kind in walk(lines):
                if kind == COMMENT or (kind != TEXT and not ck.fenced):
                    continue
                i, ln = i0 + 1, lines[i0]
                for m in MARK.finditer(ln):
                    n_marks += 1
                    why = _mark_why(m["k"], m["v"], ck.kinds, v, docs_dir, log_dir, has)
                    if why:
                        err(p, i, f"{m.group(0)} {why}")
                    if code_doc(m["k"], m["v"]):
                        what = f"{m.group(0)} {code_doc_what(m['v'], docs_dir, log_dir)}"
                        if cd_new is not None and i in cd_new.get(p, ()):
                            cd["new"] += 1
                            err(p, i, what)
                        else:
                            cd["old"] += 1
                            suspects.append({"doc": p, "line": i, "what": f"{what}. 기준 커밋 앞 옛 줄", "code_doc": True})
                for x in XREF.finditer(ln):
                    got = xref_lookup(idx, x["t"]) if idx else []
                    if len(got) != 1:
                        err(p, i, f"→ 「{x['t']}」 " + ("제목을 가진 편이 없습니다" if not got else f"제목이 여러 편에 있습니다({', '.join(got)})"))
                for _col, t, inner in (bare_xrefs(ln, idx) if idx and kind == TEXT else []):
                    what = bare_xref_what(t, inner)
                    if xb_new is not None and i in xb_new.get(p, ()):
                        xb["new"] += 1
                        err(p, i, what)
                    else:
                        xb["old"] += 1
                        suspects.append({"doc": p, "line": i, "what": f"{what}. 기준 커밋 앞 옛 줄", "xref": True,
                                         "touched": bool(xb_new and xb_new.get(p))})
                for g in IMG.finditer(ln):
                    src = g["src"]
                    if re.match(r"https?://", src):
                        continue
                    f = posixpath.normpath(posixpath.join(posixpath.dirname(p), src))
                    if not base.is_file(f):
                        err(p, i, f"그림 파일이 없습니다 {src}")
                if k in ck.banned:
                    plain = IMG.sub("", STRIP.sub("", ln))
                    for name, rx in BANNED:
                        for hit in rx.finditer(plain):
                            w = hit.group(0).lower()
                            if name == "도메인" and any(w == d or w.endswith("." + d) for d in allowed):
                                continue
                            err(p, i, f"원고 금지어({name}) 「{hit.group(0)}」")
                            break
                if kind == TEXT and is_claim(ln, claim, ck.claim_min):
                    suspects.append({"doc": p, "line": i, "what": "숫자나 인용이 있는데 근거 표시가 없습니다"})

    # 4. 덮기
    cover = {"target": 0, "covered": 0, "tests": 0}
    if ck.cover_by:
        r0 = (reads.get("main") or [None])[0] if cfg.read_commit == "set" and ck.files_at == "read" else None
        files = sorted(GitView(repo, r0).files) if r0 and len(reads.get("main", [])) == 1 else (
            sorted(base.files) if isinstance(base, GitView) else tree(repo, None))
        # git이 경로를 따옴표로 내보냈으면(설정이 바뀌었거나 새 길이 생겼을 때) 무늬와 폴더에 걸리지 않아 덮기 밖으로 조용히 세어진다.
        # 그렇게 세지 않고 틀림 하나로 알린다(11-19 펫퍼민트 52줄)
        quoted = [f for f in files if is_quoted(f)]
        if quoted:
            files = [f for f in files if f not in quoted]
            err(None, None, f"{quoted_problem(quoted[0])}. 같은 경로 {len(quoted)}개를 덮기 대상에서 뺐습니다")
        folders = tuple(d for d in sets.values() if d) + tuple(cfg.records)
        # `not_code`에 드는 파일(사진, 잠금 파일 같은 것)은 덮을 대상이 아니다. 확장자 `.md`만은 뺀다. 문서 묶음 밖 글(CLAUDE.md,
        # README.md, 운영 절차서)은 코드는 아니어도 어느 편이 다루는지 보는 대상으로 남겨 둔다(판단은 log/foreman-6_cover_not_code_*.md)
        # 생성물(`[readme]`이 켜진 저장소의 README.md)은 원고에서 만들어지는 글이라 어느 편도 다루지 않는다. 저장소가 not_code에 적지 않아도 뺀다
        # `[readme] header_file`이 가리키는 파일은 README 머리글로 그대로 들어가는 원본이라 같은 까닭으로 뺀다(11-19, 사람이 쓰는 글이라 GENERATED에는 없다)
        skip = not_code_skip(cfg.not_code)
        if cfg.readme is not None:
            skip += list(readme.GENERATED) + ([cfg.readme["header_file"]] if cfg.readme.get("header_file") else [])
        target_files = [f for f in files if not f.startswith(folders) and not not_code_match(f, skip)]
        covered: set[str] = set()
        for k in ck.cover_by:
            ps = checked.get(k) or (pieces_of(repo, rev, sets[k], k in ck.numbered_only, cfg.records) if sets.get(k) else [])
            for p in ps:
                h = heads.get(p) or parse_head(bodies.get(p) or read_many(repo, rev, [p]).get(p, ""), ck.head_at) or {}
                for c in h.get("covers", []):
                    covered.update(cover_matches(c, target_files))
        # 시험 파일은 어느 편의 다루는 곳에 들지 않아도 덮은 것으로 친다(11-20 사용자 결정). 본문이 설명하지 않는 시험 파일이 이 검사
        # 때문에 다루는 곳에 남아 있었다. 다루는 곳에 든 시험 파일은 그대로 세고, 따로 센 수(tests)는 결과 줄에 보인다
        tests = {f for f in target_files if f not in covered and not_code_match(f, ck.tests)}
        covered |= tests
        cover = {"target": len(target_files), "covered": len(covered), "tests": len(tests)}
        for f in target_files:
            if f not in covered:
                err(None, None, f"덮기 밖: {f}가 {', '.join(ck.cover_by)} 어느 편의 {COVERS}에도 들지 않습니다")
    # 8. 새 줄의 em dash와 가운뎃점
    dd = dashdot.for_repo(repo, ck.dashdot_base, sets, cfg.records, rev, not_code_skip(cfg.not_code))
    notes = [dd["note"]] if dd["note"] else []
    if not xb_base and xb["old"]:
        xb_note = f"{XREF_NO_BASE}. 「」 없는 편 사이 참조 {xb['old']}곳을 모두 의심으로 셌습니다"
        notes.append(xb_note)
    if not cd_base and cd["old"]:
        notes.append(f"{CODE_DOC_NO_BASE}. 문서를 가리키는 [code:] {cd['old']}곳을 모두 의심으로 셌습니다")
    if dd["error"]:
        err(None, None, f"줄표, 가운뎃점 검사를 돌리지 못했습니다: {dd['error']}")
    for p, i, name, s in dd["hits"]:
        err(p, i, f"새 줄의 {name}: {s}")
    # 9. README
    r_errs, r_notes = readme_check(repo, rev, cfg, sets, links)
    for w in r_errs:
        err(readme.PATH, None, w)
    # 꺼진 것은 notes가 아니라 readme 칸으로(점검 8번의 dashdot 칸과 같은 꼴). render가 한 줄로 알린다
    rd_on = r_notes != [README_OFF]
    if rd_on:
        notes += r_notes
    return {"errors": errors, "suspects": suspects, "sets": {k: len(ps) for k, ps in checked.items()},
            "marks": n_marks, "reads": reads, "cover": cover, "notes": notes,
            "dashdot": {"base": dd["base"], "hits": len(dd["hits"]), "ran": bool(dd["base"]) and not dd["error"]},
            "xref_bare": xb, "code_doc": cd, "readme": {"ran": rd_on}}


XREF_NO_BASE = "기준 커밋이 없어 「」 없는 편 사이 참조를 틀림으로 세지 않았습니다(.foreman/docs.toml [check] xref_base)"
CODE_DOC_NO_BASE = "기준 커밋이 없어 문서를 가리키는 [code:]를 틀림으로 세지 않았습니다(.foreman/docs.toml [check] code_doc_base)"


def code_doc_what(v: str, docs_dir: str = "docs/", log_dir: str = "log/") -> str:
    """문서(.md)를 가리키는 `[code:]` 한 곳의 글. 바꿀 꼴을 함께 알린다(docs, 기록 폴더 안이면 그 종류, 밖이면 [repo:])."""
    p = mark_path("code", v) or v
    rest = v[len(p):]                                  # 줄 범위와 절(:10-20#…). code 경로는 값의 앞머리 그대로다
    for k, d in (("docs", docs_dir), ("log", log_dir)):
        if d and p.startswith(d):
            return f"코드가 아닌 문서를 가리킵니다([{k}:{p[len(d):]}{rest}]로 씁니다)"
    return f"코드가 아닌 문서를 가리킵니다([repo:{v}]로 씁니다)"


def bare_xref_what(title: str, inner: bool) -> str:
    """「」 없는 편 사이 참조 한 곳의 글(점검 틀림과 의심, 서기 지시문이 같이 쓴다)."""
    if inner:
        return f"「→ {title}」: 화살표가 「」 안에 있습니다(→ 「{title}」 꼴로 씁니다)"
    return f"→ {title}: 편 사이 참조에 「」가 없습니다(→ 「{title}」 꼴로 씁니다)"


def piece_bare_xrefs(repo: str, rev: str | None, cfg: DocsConfig, sets: dict[str, str], path: str) -> list[tuple[int, str, bool]]:
    """편 하나의 「」 없는 편 사이 참조 (줄 번호 1부터, 제목, 화살표가 「」 안인가). 서기실이 그 편을 띄울 때 지시문에 넣는다.
    점검(run)과 같은 묶음, 같은 색인(check.xref면 그 묶음 제목), 같은 판정(`titles.bare_xrefs`), 울타리 밖 줄만. 묶음 밖 편이면 빈 목록."""
    ck = cfg.check
    k = next((k for k, d in sorted(sets.items(), key=lambda x: -len(x[1] or "")) if d and path.startswith(d)), None)
    if k is None or path.startswith(tuple(cfg.records)):
        return []
    g = ck.xref.get(k, k)
    if not sets.get(g):
        return []
    ps = pieces_of(repo, rev, sets[g], g in ck.numbered_only, cfg.records)
    bodies = read_many(repo, rev, sorted({*ps, path}))
    idx = xref_index({p: first_h1(bodies.get(p, ""))[1] for p in ps})
    lines = bodies.get(path, "").splitlines()
    return [(i0 + 1, t, inner) for i0, kind in walk(lines) if kind == TEXT for _c, t, inner in bare_xrefs(lines[i0], idx)]


def _mark_why(kind: str, v: str, kinds: list[str], view: FsView | GitView, docs_dir: str, log_dir: str, has) -> str | None:
    if kind not in kinds:
        return "이 저장소에서 쓰지 않는 종류입니다"
    if kind == "c":
        return None if has(v) else "그 커밋이 저장소에 없습니다"
    if kind == "t":
        return None if v.isdigit() else "턴 번호가 숫자가 아닙니다"
    return mark_problem(kind, v, view, docs_dir, log_dir)


def render(res: dict[str, Any], verbose: bool = False) -> str:
    out = []
    sets = ", ".join(f"{k} {n}" for k, n in res["sets"].items())
    reads = "; ".join(f"{k} {len(v)}가지" for k, v in res["reads"].items())
    out.append(f"편 {sum(res['sets'].values())}({sets}), 근거 표시 {res['marks']}, 읽은 커밋 {reads or '없음'}, "
               f"덮기 대상 파일 {res['cover']['target']} 가운데 {res['cover']['covered']} 덮음"
               + (f"(다루는 곳 없이 덮은 것으로 친 시험 파일 {res['cover']['tests']})" if res['cover'].get('tests') else ""))
    dd = res.get("dashdot") or {}
    if dd.get("ran"):
        out.append(f"줄표, 가운뎃점 검사: 기준 커밋 {dd['base'][:10]} 뒤 새 줄에서 {dd['hits']}건")
    xb = res.get("xref_bare") or {}
    if xb.get("ran"):
        out.append(f"「」 없는 편 사이 참조: 기준 커밋 {xb['base'][:10]} 뒤 새 줄 {xb['new']}곳(틀림), 옛 줄 {xb['old']}곳(의심)")
    cd = res.get("code_doc") or {}
    if cd.get("ran"):
        out.append(f"문서를 가리키는 [code:]: 기준 커밋 {cd['base'][:10]} 뒤 새 줄 {cd['new']}곳(틀림), 옛 줄 {cd['old']}곳(의심)")
    for n in res.get("notes", []):
        out.append(f"알림  {n}")
    if res.get("readme", {}).get("ran") is False:
        out.append(f"알림  {README_OFF}")
    for e in res["errors"]:
        where = f"{e['doc']}:{e['line']}: " if e["doc"] and e["line"] else f"{e['doc']}: " if e["doc"] else ""
        out.append(f"틀림  {where}{e['what']}")
    for s in res["suspects"]:
        # 기준 커밋 뒤 고친 편의 옛 「」 없는 참조는 -v 없이도 보인다(그 편을 고쳐 쓰는 서기가 함께 맞추게)
        if verbose or (s.get("xref") and s.get("touched")):
            out.append(f"의심  {s['doc']}:{s['line']}: {s['what']}")
    out.append(f"틀린 것 {len(res['errors'])}, 의심 {len(res['suspects'])}")
    return "\n".join(out)


__all__ = ["BANNED", "FsView", "GitView", "IMG", "RepoError", "SKIP_LINE", "commit_exists", "cover_matches",
           "covers_problem", "is_claim", "mark_problem", "readme_build", "readme_check", "readme_project", "render", "run"]
