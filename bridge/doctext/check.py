"""문서 점검(11-17 문서 도구 합치기 3단계). 인프라 `scripts/docs-check.py` 1~7번 규칙을 묶음 위로 옮겼다. 읽기만 한다.

    1. 머리 주석: 편마다 「다루는 곳」과 「읽은 커밋」. 읽은 커밋은 편마다 저장소에 있어야 한다(read_commit "piece").
       "set"(인프라 전환 동안만)은 원고와 docs가 하나, 포트폴리오끼리 하나
    2. 다루는 곳: 적힌 파일, 폴더, 글롭이 있다(files_at 판)
    3. 근거 표시: 쓸 수 있는 종류(check.kinds), 커밋이 있다, 파일이 있고 줄 범위가 맞다(files_at 판), 턴 번호는 숫자
    4. 덮기: 문서 묶음과 기록 밖 추적 파일 하나하나가 check.cover_by 묶음 어느 편의 다루는 곳에 든다
    5. 편 사이 참조: → 「제목」이 같은 묶음(check.xref면 그 묶음) 편 하나의 첫 # 줄과 같다
    6. 금지어(check.banned 묶음만): IP 주소, 도메인(check.domains_in 묶음은 allowed_domains를 뺀다), 홈 경로, 토큰 꼴, 포트 번호
    7. 그림 `![…](경로)`: 파일이 있다
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

from bridge.doctext.config import DocsConfig
from bridge.doctext.head import COVERS, READ, SHA, bad_covers, parse_head
from bridge.doctext.lines import COMMENT, TEXT, walk
from bridge.doctext.marks import MARK, STRIP, target
from bridge.doctext.repo import RepoError, gits, read_many, tree
from bridge.doctext.titles import XREF, first_h1, xref_index, xref_lookup

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
    """파일 종류 근거 표시(`log`, `docs`, `code`)의 틀린 까닭. 맞으면 None."""
    t = target(v)
    if not t:
        return "모양을 알아보지 못했습니다"
    name, ta, tb = t
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts:
        return "저장소 밖을 가리킵니다"
    path = name if kind == "code" else (docs_dir if kind == "docs" else log_dir) + name
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
        names = [x for x in gits(repo, "ls-files", "--cached", "--others", "--exclude-standard", "--", folder).splitlines()
                 if x and (Path(repo) / x).is_file()]
    out = [p for p in sorted(set(names)) if p.endswith(".md") and not p.startswith(tuple(records))]
    if numbered:
        out = [p for p in out if NUMBERED.match(p[len(folder):])]
    return sorted(out)


def run(repo: str, rev: str | None, cfg: DocsConfig, sets: dict[str, str]) -> dict[str, Any]:
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
                    why = _mark_why(m["k"], m["v"], ck.kinds, v, sets.get("docs") or "docs/",
                                    (cfg.records[0] if cfg.records else "log/"), has)
                    if why:
                        err(p, i, f"{m.group(0)} {why}")
                for x in XREF.finditer(ln):
                    got = xref_lookup(idx, x["t"]) if idx else []
                    if len(got) != 1:
                        err(p, i, f"→ 「{x['t']}」 " + ("제목을 가진 편이 없습니다" if not got else f"제목이 여러 편에 있습니다({', '.join(got)})"))
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
    cover = {"target": 0, "covered": 0}
    if ck.cover_by:
        r0 = (reads.get("main") or [None])[0] if cfg.read_commit == "set" and ck.files_at == "read" else None
        files = sorted(GitView(repo, r0).files) if r0 and len(reads.get("main", [])) == 1 else (
            sorted(base.files) if isinstance(base, GitView) else tree(repo, None))
        folders = tuple(d for d in sets.values() if d) + tuple(cfg.records)
        target_files = [f for f in files if not f.startswith(folders)]
        covered: set[str] = set()
        for k in ck.cover_by:
            ps = checked.get(k) or (pieces_of(repo, rev, sets[k], k in ck.numbered_only, cfg.records) if sets.get(k) else [])
            for p in ps:
                h = heads.get(p) or parse_head(bodies.get(p) or read_many(repo, rev, [p]).get(p, ""), ck.head_at) or {}
                for c in h.get("covers", []):
                    covered.update(cover_matches(c, target_files))
        cover = {"target": len(target_files), "covered": len(covered)}
        for f in target_files:
            if f not in covered:
                err(None, None, f"덮기 밖: {f}가 {', '.join(ck.cover_by)} 어느 편의 {COVERS}에도 들지 않습니다")
    return {"errors": errors, "suspects": suspects, "sets": {k: len(ps) for k, ps in checked.items()},
            "marks": n_marks, "reads": reads, "cover": cover}


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
               f"덮기 대상 파일 {res['cover']['target']} 가운데 {res['cover']['covered']} 덮음")
    for e in res["errors"]:
        where = f"{e['doc']}:{e['line']}: " if e["doc"] and e["line"] else f"{e['doc']}: " if e["doc"] else ""
        out.append(f"틀림  {where}{e['what']}")
    if verbose:
        for s in res["suspects"]:
            out.append(f"의심  {s['doc']}:{s['line']}: {s['what']}")
    out.append(f"틀린 것 {len(res['errors'])}, 의심 {len(res['suspects'])}")
    return "\n".join(out)


__all__ = ["BANNED", "FsView", "GitView", "IMG", "RepoError", "SKIP_LINE", "commit_exists", "cover_matches",
           "covers_problem", "is_claim", "mark_problem", "render", "run"]
