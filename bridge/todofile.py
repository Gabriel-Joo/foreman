"""저장소마다 `docs/TODO.md`(남은 일 한 곳, `docs/manuscript_rules.md` 1절)를 읽고, 번호를 붙여 더하고, 지운다(11-17 문서 정리 E).

포스트잇 창의 「할 일」 묶음과 「30일 넘은 것」 묶음이 이 파일을 가리킨다. 내용은 복사하지 않는다(두 벌이 생기지 않게).
가리킴은 포스트잇에서 TODO로 한 방향이다: 포스트잇 [TODO로]가 항목을 더하고, 포스트잇 줄은 그 번호를 적고 닫힌다.

읽는 판은 HEAD(`git show HEAD:docs/TODO.md`)다. 작업 트리에서 누가 고치는 중인 글을 보지 않는다.

항목 꼴(저장소마다 다르다. 둘 다 읽는다):
  FOREMAN  `- **foreman-12** 제목 (2026-11-15)` 다음 줄부터 두 칸 들여 쓴 내용과 「나온 곳」
  인프라   `- infra-12 (2026-11-12) 할 일 → 나온 곳` 한 줄
번호 꼴이 없는 저장소(런슈즈의 체크 목록, 펫퍼민트의 표)는 항목을 세지 않고 「번호 꼴이 아닙니다」로 알린다. 더하기도 거부한다.

쓰기(더하기, 지우기)는 브리지가 사람 단추로 그 저장소 원본 폴더에서 커밋한다. 다른 변경이 섞이지 않게:
  - 브랜치 위(HEAD가 떼어지지 않음)이고 합치기나 rebase가 도는 중이 아닐 때만
  - `docs/TODO.md`에 커밋 안 된 변경(스테이지 포함)이 있으면 건드리지 않고 거부한다(다른 세션이 고치는 중일 수 있다)
  - `git commit --only -- docs/TODO.md`로 그 파일만 담는다. 다른 세션이 올려 둔 스테이지는 그대로 남는다
  - push하지 않는다(push는 그 저장소 규칙대로 관리자가 한다)
커밋 메시지에 `(todo:infra-12)`가 있으면 그 항목을 끝낸 커밋으로 본다. 항목을 저절로 지우지 않고 화면에 알리기만 한다.
지우기는 사람이 [지우기]를 눌러 브리지가 커밋한다(가장 덜 위험한 쪽, 11-17 일감).
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

PATH = "docs/TODO.md"
OLD_DAYS = 30
SECTION = "## 포스트잇에서 보낸 것"          # [TODO로]가 더하는 절(없으면 파일 끝에 만든다)
TITLE_MAX = 120
ID = r"[a-z][a-z0-9]*-\d+"
_ITEM = re.compile(rf"^- (?P<b>\*\*)?(?P<id>{ID})(?P=b)?\s+(?P<rest>.*)$")
_DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)")
_HEAD_PREFIX = re.compile(r"\b([a-z][a-z0-9]*)-(?:N|번호)\b")
REF = re.compile(rf"\(todo:\s*({ID}(?:\s*,\s*{ID})*)\s*\)")


class TodoError(Exception):
    """거부 — 화면에 그대로 보이는 까닭(「~습니다」)."""


@dataclass
class Item:
    id: str
    title: str
    date: date | None
    start: int          # 줄 번호(0부터)
    end: int            # 다음 항목이 시작하는 줄(들여 쓴 내용 줄까지 이 항목)
    bold: bool

    @property
    def prefix(self) -> str:
        return self.id.rsplit("-", 1)[0]


def parse(text: str) -> list[Item]:
    """번호 붙은 항목만. 들여 쓴 다음 줄들은 그 항목의 내용이다."""
    lines = text.split("\n")
    out: list[Item] = []
    i = 0
    while i < len(lines):
        m = _ITEM.match(lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith((" ", "\t")) and lines[j].strip():
            j += 1
        rest = m.group("rest")
        d = _DATE.search(rest)
        day = None
        if d:
            try:
                day = date.fromisoformat(d.group(1))
            except ValueError:
                day = None
            rest = (rest[:d.start()] + rest[d.end():])
        if not m.group("b"):
            rest = rest.split(" → ", 1)[0]          # 인프라 꼴: 「→ 나온 곳」은 제목이 아니다
        title = re.sub(r"\s+", " ", rest).strip()
        out.append(Item(m.group("id"), title, day, i, j, bool(m.group("b"))))
        i = j
    return out


def prefix_of(text: str, items: list[Item]) -> str | None:
    """이 저장소의 번호 앞말. 항목에서 가장 많이 쓴 것, 항목이 없으면 머리 글의 「foreman-N」 「infra-번호」 꼴."""
    if items:
        return Counter(x.prefix for x in items).most_common(1)[0][0]
    m = _HEAD_PREFIX.search(text)
    return m.group(1) if m else None


def bold_style(text: str, items: list[Item], prefix: str) -> bool:
    if items:
        return Counter(x.bold for x in items).most_common(1)[0][0]
    return f"**{prefix}-" in text


def max_number(prefix: str, *texts: str) -> int:
    pat = re.compile(rf"\b{re.escape(prefix)}-(\d+)\b")
    return max((int(n) for t in texts for n in pat.findall(t or "")), default=0)


def entry_lines(prefix: str, n: int, body: str, day: date, ref: str, bold: bool) -> list[str]:
    """새 항목 줄. 제목은 글의 첫 줄, 나머지는 내용. 인프라 꼴은 한 줄에 모은다."""
    parts = [ln.strip() for ln in (body or "").strip().split("\n") if ln.strip()]
    if not parts:
        raise TodoError("보낼 글이 비어 있습니다")
    title = parts[0] if len(parts[0]) <= TITLE_MAX else parts[0][:TITLE_MAX - 1] + "…"
    rest = ([parts[0]] if title != parts[0] else []) + parts[1:]
    if bold:
        return [f"- **{prefix}-{n}** {title} ({day.isoformat()})"] + [f"  {x}" for x in rest] + [f"  나온 곳: {ref}"]
    return [f"- {prefix}-{n} ({day.isoformat()}) {' '.join(parts)} → {ref}"]


def add_entry(text: str, lines_new: list[str]) -> str:
    """「포스트잇에서 보낸 것」 절 끝에 더한다. 절이 없으면 파일 끝에 만든다."""
    lines = text.rstrip("\n").split("\n")
    at = next((i for i, ln in enumerate(lines) if ln.strip() == SECTION), None)
    if at is None:
        return "\n".join(lines + ["", SECTION, ""] + lines_new) + "\n"
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    while end > at + 1 and not lines[end - 1].strip():
        end -= 1
    pad = [""] if end == at + 1 else []
    return "\n".join(lines[:end] + pad + lines_new + lines[end:]).rstrip("\n") + "\n"


def remove_entry(text: str, tid: str) -> str:
    items = {x.id: x for x in parse(text)}
    x = items.get(tid)
    if x is None:
        raise TodoError(f"{PATH}에 {tid}가 없습니다")
    lines = text.split("\n")
    return "\n".join(lines[:x.start] + lines[x.end:])


def entry_text(text: str, tid: str) -> str | None:
    """그 항목의 원문(머리 줄과 들여 쓴 내용)."""
    x = next((i for i in parse(text) if i.id == tid), None)
    if x is None:
        return None
    return "\n".join(ln.strip() for ln in text.split("\n")[x.start:x.end])


def refs_in(message: str) -> list[str]:
    """커밋 메시지의 `(todo:infra-12)`, `(todo:infra-12, infra-13)`."""
    out: list[str] = []
    for m in REF.finditer(message or ""):
        out += [s.strip() for s in m.group(1).split(",")]
    return out


# ── git ────────────────────────────────────────────────────
def _git(repo: str, *a: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=timeout)


def head_text(repo: str) -> str | None:
    """HEAD의 docs/TODO.md. 없으면 None."""
    r = _git(repo, "show", f"HEAD:{PATH}")
    return r.stdout if r.returncode == 0 else None


def history_text(repo: str) -> str:
    """지난 판 전부(지운 번호를 다시 쓰지 않게). 못 읽으면 빈 글."""
    try:
        return _git(repo, "log", "-p", "--format=", "--", PATH, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


_DONE_CACHE: dict[tuple[str, str], dict[str, dict[str, str]]] = {}


def done_by_commits(repo: str, n: int = 500) -> dict[str, dict[str, str]]:
    """`(todo:번호)`를 적은 최근 커밋 — 번호 → {commit, subject}. 같은 HEAD면 다시 훑지 않는다."""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if not head:
        return {}
    key = (repo, head)
    if key in _DONE_CACHE:
        return _DONE_CACHE[key]
    raw = _git(repo, "log", f"-{n}", "--format=%h%x1f%s%x1f%b%x1e").stdout
    out: dict[str, dict[str, str]] = {}
    for rec in raw.split("\x1e"):
        f = rec.strip("\n").split("\x1f")
        if len(f) < 3:
            continue
        for tid in refs_in(f[1] + "\n" + f[2]):
            out.setdefault(tid, {"commit": f[0], "subject": f[1]})      # 가장 최근 커밋
    _DONE_CACHE.clear()
    _DONE_CACHE[key] = out
    return out


def view(repo: str | None, now: datetime | None = None) -> dict[str, Any]:
    """화면용 {path, exists, error, prefix, items[{id, title, date, days, old, done_by}], n, old, done}.
    번호와 한 줄 제목만 내린다(내용은 복사하지 않는다)."""
    out: dict[str, Any] = {"path": PATH, "exists": False, "error": None, "prefix": None, "items": [], "n": 0, "old": 0, "done": 0}
    if not repo or not Path(repo, ".git").exists():
        out["error"] = "이 프로젝트의 저장소를 찾지 못했습니다"
        return out
    try:
        text = head_text(repo)
    except (OSError, subprocess.TimeoutExpired) as e:
        out["error"] = f"{PATH}를 읽지 못했습니다: {type(e).__name__}"
        return out
    if text is None:
        out["error"] = f"이 저장소에는 {PATH}가 없습니다"
        return out
    out["exists"] = True
    items = parse(text)
    out["prefix"] = prefix_of(text, items)
    if not items:
        out["error"] = f"{PATH}에 번호 붙은 항목이 없습니다(이 저장소 꼴은 번호가 없습니다)" if text.strip() else None
    today = (now or datetime.now()).date()
    try:
        done = done_by_commits(repo)
    except (OSError, subprocess.TimeoutExpired):
        done = {}
    for x in items:
        days = (today - x.date).days if x.date else None
        out["items"].append({"id": x.id, "title": x.title, "date": x.date.isoformat() if x.date else None, "days": days,
                             "old": days is not None and days > OLD_DAYS, "done_by": done.get(x.id)})
    out["n"] = len(items)
    out["old"] = sum(i["old"] for i in out["items"])
    out["done"] = sum(bool(i["done_by"]) for i in out["items"])
    return out


_LOCKS: dict[str, asyncio.Lock] = {}


def _commit_sync(repo: str, change: Callable[[str], tuple[str, str]], subject: Callable[[str], str], body: str) -> dict[str, str]:
    """change(지금 글) → (새 글, 결과 값). 그 파일만 커밋한다. 실패하면 작업 트리의 그 파일을 HEAD로 되돌린다(고치기 전 깨끗했다)."""
    if _git(repo, "symbolic-ref", "-q", "HEAD").returncode != 0:
        raise TodoError("저장소가 브랜치 위에 있지 않아(HEAD가 떼어짐) 커밋하지 않았습니다")
    for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        p = _git(repo, "rev-parse", "--git-path", name).stdout.strip()
        if p and Path(repo, p).exists():
            raise TodoError("저장소에서 합치기나 rebase가 도는 중이라 커밋하지 않았습니다")
    st = _git(repo, "status", "--porcelain", "--", PATH)
    if st.returncode != 0:
        raise TodoError(f"저장소 상태를 읽지 못했습니다: {st.stderr.strip()[:200]}")
    if st.stdout.strip():
        raise TodoError(f"{PATH}에 커밋 안 된 변경이 있어 건드리지 않았습니다. 다른 세션이 고치는 중일 수 있습니다")
    old = head_text(repo)
    if old is None:
        raise TodoError(f"이 저장소에는 {PATH}가 없습니다")
    new, value = change(old)
    f = Path(repo, PATH)
    f.write_text(new, encoding="utf-8")
    r = _git(repo, "commit", "-q", "--only", "-m", subject(value), "-m", body, "--", PATH, timeout=60)
    if r.returncode != 0:
        _git(repo, "checkout", "HEAD", "--", PATH)
        raise TodoError(f"커밋하지 못했습니다: {(r.stderr or r.stdout).strip()[:300]}")
    return {"commit": _git(repo, "rev-parse", "--short", "HEAD").stdout.strip(), "value": value}


async def commit_change(repo: str, change: Callable[[str], tuple[str, str]], subject: Callable[[str], str], body: str) -> dict[str, str]:
    lock = _LOCKS.setdefault(str(Path(repo).resolve()), asyncio.Lock())
    async with lock:
        return await asyncio.to_thread(_commit_sync, repo, change, subject, body)


async def add(repo: str, body: str, ref: str, why: str, today: date | None = None) -> dict[str, str]:
    """다음 번호로 더하고 커밋한다 — {commit, value: 번호}. ref = 「나온 곳」(포스트잇 p:N)."""
    hist = await asyncio.to_thread(history_text, repo)
    day = today or datetime.now().date()

    def change(old: str) -> tuple[str, str]:
        items = parse(old)
        prefix = prefix_of(old, items)
        if not prefix:
            raise TodoError(f"{PATH}의 번호 꼴(예: infra-12)을 정하지 못했습니다. 번호 붙은 항목이나 머리 글의 「이름-N」 꼴이 있어야 합니다")
        n = max_number(prefix, old, hist) + 1
        tid = f"{prefix}-{n}"
        return add_entry(old, entry_lines(prefix, n, body, day, ref, bold_style(old, items, prefix))), tid

    # 번호는 change 안에서(잠금 안에서 HEAD를 읽은 뒤) 정해지므로 제목도 번호를 받아 만든다
    return await commit_change(repo, change, lambda tid: f"docs: TODO에 {tid} 항목을 더함", why)


async def remove(repo: str, tid: str, why: str) -> dict[str, str]:
    return await commit_change(repo, lambda old: (remove_entry(old, tid), tid), lambda t: f"docs: TODO에서 {t} 항목을 지움", why)
