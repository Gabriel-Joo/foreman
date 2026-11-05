"""인계 2판의 「읽을 곳」(11-05, docs/11_handoff_v2.md 2장 ②③) — 풀기 · 기계 확인 · 새 세션이 실제로 읽었나.

한 줄 모양(인계를 쓰는 세션에게 이 모양으로 쓰라고 시킨다):
  - `docs/01a_catalog_sources.md:40-60` — 스펙 출처 우선순위(다음 할 일 2에 필요)
  - CLAUDE.md 「작업 규칙」 — 금지 항목 다시 확인
  - log/runshoes_compaction_loss_20261105.md — 사라진 지시 목록
경로는 저장소 맨 위 기준(절대 경로도 받는다). 줄 범위(:a-b)나 절 이름(「…」)은 있어도 없어도 된다."""

from __future__ import annotations

import asyncio
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


async def check(pointers: list[Pointer], repo: str) -> list[Pointer]:
    """있나 · 줄 범위 · 절 이름이 맞나(틀리면 ok=False), 문서 뒤로 커밋이 얼마나 쌓였나(많으면 stale — 막지는 않는다)."""
    for p in pointers:
        if not p.path:
            continue
        f = _resolve(repo, p.path)
        if not f.is_file():
            p.ok, p.problem = False, "파일이 없습니다"
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            p.ok, p.problem = False, "읽을 수 없습니다"
            continue
        if p.start is not None and (p.start < 1 or (p.end or p.start) > len(lines) or (p.end or p.start) < p.start):
            p.ok, p.problem = False, f"줄 범위가 맞지 않습니다(파일은 {len(lines)}줄)"
            continue
        if p.section and not any(p.section in ln for ln in lines):
            p.ok, p.problem = False, f"「{p.section}」을(를) 찾지 못했습니다"
            continue
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


def reads(pointers: list[Pointer], repo: str, read_targets: list[str]) -> dict[str, Any]:
    """새 세션의 Read 대상(절대 경로)과 맞댄다 — {total, read, missing: [path]}."""
    got = {str(Path(t).resolve()) for t in read_targets if t}
    want = [p for p in pointers if p.path]
    missing = [p.path for p in want if str(_resolve(repo, p.path).resolve()) not in got]
    return {"total": len(want), "read": len(want) - len(missing), "missing": missing}


def as_dicts(pointers: list[Pointer]) -> list[dict[str, Any]]:
    return [asdict(p) for p in pointers]
