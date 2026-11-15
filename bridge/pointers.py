"""인계 2판의 「읽을 곳」(11-05, docs/11_handoff_v2.md 2장 ②③) — 풀기 · 기계 확인 · 새 세션이 실제로 읽었나.

한 줄 모양(인계를 쓰는 세션에게 이 모양으로 쓰라고 시킨다):
  - `docs/01a_catalog_sources.md:40-60` — 스펙 출처 우선순위(다음 할 일 2에 필요)
  - CLAUDE.md 「작업 규칙」 — 금지 항목 다시 확인
  - log/runshoes_compaction_loss_20261105.md — 사라진 지시 목록
경로는 저장소 맨 위 기준(절대 경로도 받는다). 줄 범위(:a-b)나 절 이름(「…」)은 있어도 없어도 된다."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SECTION = "읽을 곳"
_LINE = re.compile(
    r"^\s*[-*•]\s*`?(?P<path>[~\w./\-]+\.[A-Za-z0-9]+)"
    r"(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?`?"
    r"\s*(?:「(?P<sec>[^」]+)」)?"
    r"\s*(?:[—–-]+\s*(?P<why>.*))?$")
STALE_COMMITS = 20      # 문서가 마지막으로 바뀐 뒤 저장소 커밋이 이만큼 쌓였으면 "오래됐을 수 있음"


@dataclass
class Pointer:
    path: str
    start: int | None = None
    end: int | None = None
    section: str | None = None
    why: str = ""
    raw: str = ""
    # 확인 결과
    ok: bool = True
    problem: str | None = None
    commits_since: int | None = None
    stale: bool = False


def is_v2(body: str | None) -> bool:
    return bool(body) and re.search(rf"^##\s*{SECTION}\s*$", body or "", re.M) is not None


def parse(body: str) -> list[Pointer]:
    """「## 읽을 곳」 절의 목록 줄들. 모양이 안 맞는 줄은 problem을 달아 돌려준다(빠뜨리지 않게)."""
    out: list[Pointer] = []
    inside = False
    for line in (body or "").splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == SECTION
            continue
        if not inside or not line.strip():
            continue
        m = _LINE.match(line)
        if not m:
            if line.lstrip().startswith(("-", "*", "•")):
                out.append(Pointer(path="", raw=line.strip(), ok=False, problem="모양을 알아보지 못했습니다(경로 — 이유)"))
            continue
        a, b = m["a"], m["b"]
        out.append(Pointer(path=m["path"], start=int(a) if a else None, end=int(b) if b else (int(a) if a else None),
                           section=m["sec"], why=(m["why"] or "").strip(), raw=line.strip()))
    return out


def _resolve(repo: str, p: str) -> Path:
    q = Path(p).expanduser()
    return q if q.is_absolute() else Path(repo) / q


async def _git(repo: str, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), 5)
    except TimeoutError:
        proc.kill()
        return ""
    return out.decode(errors="replace").strip()


def _problem(p: Pointer, repo: str) -> str | None:
    """그 저장소(폴더)에서 이 읽을 곳이 맞나 — 틀리면 까닭, 맞으면 None."""
    f = _resolve(repo, p.path)
    if not f.is_file():
        return "파일이 없습니다"
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "읽을 수 없습니다"
    if p.start is not None and (p.start < 1 or (p.end or p.start) > len(lines) or (p.end or p.start) < p.start):
        return f"줄 범위가 맞지 않습니다(파일은 {len(lines)}줄)"
    if p.section and not any(p.section in ln for ln in lines):
        return f"「{p.section}」을(를) 찾지 못했습니다"
    return None


async def check(pointers: list[Pointer], repo: str, other: str | None = None,
                other_note: str | None = None) -> list[Pointer]:
    """있나 · 줄 범위 · 절 이름이 맞나(틀리면 ok=False), 문서 뒤로 커밋이 얼마나 쌓였나(많으면 stale — 막지는 않는다).
    repo — 읽는 세션이 보는 폴더(받은 세션의 폴더, 넣기 전이면 새 세션이 시작할 원본 폴더).
    other — 같은 저장소의 다른 쪽(원본 ↔ worktree). repo에서 틀렸는데 other에서 맞으면 까닭 뒤에 other_note를 붙인다
    (11-09 런슈즈: 쓴 세션의 worktree가 main보다 뒤처져, main에는 있는 절을 "찾지 못했다"고 막았다)."""
    for p in pointers:
        if not p.path:
            continue
        prob = _problem(p, repo)
        if prob:
            if other and other_note and os.path.realpath(other) != os.path.realpath(repo) and _problem(p, other) is None:
                prob = f"{prob}. {other_note}"
            p.ok, p.problem = False, prob
            continue
        f = _resolve(repo, p.path)
        try:
            rel = str(f.resolve().relative_to(Path(repo).resolve()))
        except ValueError:
            continue                      # 저장소 밖 문서(메모리 등) — 커밋 수는 보지 않는다
        last = await _git(repo, "log", "-1", "--format=%H", "--", rel)
        if last:
            n = await _git(repo, "rev-list", "--count", f"{last}..HEAD")
            p.commits_since = int(n) if n.isdigit() else None
            p.stale = (p.commits_since or 0) >= STALE_COMMITS
    return pointers


WT_DIR = ".worktrees"
AUTO_LOADED = ("CLAUDE.md",)    # 저장소 맨 위 — CC가 세션 시작 · 압축 뒤에 스스로 넣는다. Read 도구로는 안 읽힌다


def _key(repo: str, p: str) -> str:
    """같은 저장소의 같은 파일이면 같은 열쇠 — 원본 폴더와 `.worktrees/<이름>`을 하나로 본다.
    11-06: 합치기 전에 worktree 경로로 읽은 c 결과 문서를, 합친 뒤 원본 기준 인계가 "안 읽음"으로 셌다."""
    f = _resolve(repo, p).resolve()
    main = Path(str(Path(repo).resolve()).split(f"/{WT_DIR}/")[0])
    try:
        parts = f.relative_to(main).parts
    except ValueError:
        return str(f)                       # 저장소 밖(메모리 등)은 절대 경로 그대로
    if len(parts) > 2 and parts[0] == WT_DIR:
        parts = parts[2:]
    return "repo:" + "/".join(parts)


def reads(pointers: list[Pointer], repo: str, read_targets: list[str]) -> dict[str, Any]:
    """새 세션의 Read 대상(절대 경로)과 맞댄다 — {total, read, missing: [path], auto: [path], failed: [{path, problem}]}.
    auto는 Read 없이도 세션에 들어가 있는 문서(맨 위 CLAUDE.md) — 읽음으로 세고 따로 보인다(늘 "안 읽음"으로 뜨지 않게).
    failed — check()에서 틀린 곳(그 세션 폴더에 파일 · 절이 없다). 열었어도 찾던 것을 못 읽었으니 읽음으로 세지 않는다(11-09 사용자:
    "6/6 읽음"에 ✗가 섞였다)."""
    got = {_key(repo, t) for t in read_targets if t}
    want = [p for p in pointers if p.path]
    auto = [p.path for p in want if _key(repo, p.path) in {"repo:" + n for n in AUTO_LOADED}]
    failed = [{"path": p.path, "problem": p.problem} for p in want if not p.ok]
    bad = {f["path"] for f in failed}
    missing = [p.path for p in want if p.path not in bad and p.path not in auto and _key(repo, p.path) not in got]
    return {"total": len(want), "read": len(want) - len(missing) - len(bad), "missing": missing, "auto": auto,
            "failed": failed}


def as_dicts(pointers: list[Pointer]) -> list[dict[str, Any]]:
    return [asdict(p) for p in pointers]
