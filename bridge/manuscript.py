"""원고 셈(11-15): 노션 기술문서(notion/)와 포트폴리오(portfolio/) 편마다 「코드가 바뀐 편」을 센다.

머리 주석의 꼴(「다루는 곳」, 「읽은 커밋」)과 읽기는 bridge/doctext/head.py 한 곳이다(11-17 문서 도구 합치기 1단계).
여기는 그 값으로 git을 읽어 세는 일과 원고 나무 차례만 한다.

- 읽은 커밋: 서기가 그 글을 쓸 때 읽은 main 커밋(worktree가 갈라진 커밋). 글이 맞는지는 서기가 읽은 코드 판에 달렸다
- 「코드가 바뀐 편」: 읽은 커밋 뒤로 다루는 곳을 바꾼 feat · fix 커밋이 있는 편(docs · test · chore 커밋은 세지 않는다 —
  문서 맞추기 커밋이 코드 파일을 건드릴 때를 거른다, log/foreman-7_scribe_design_20261115.md 5-3).
  머리 주석이 없거나 읽은 커밋을 찾지 못하면 셀 수 없다(None) — 0으로 두지 않는다(조용히 「그대로」로 보이지 않게)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import PurePosixPath
from typing import Any

# 머리 주석 문법은 묶음에서 가져온다. 옛 이름(manuscript.parse_head 등)으로 부르는 곳도 그대로 된다
from bridge.doctext.head import COVERS, READ, SHA as _SHA, bad_covers, head_text, parse_head, strip_comments  # noqa: F401
from bridge.doctext.titles import first_h1

CODE_TYPES = ("feat", "fix")
_TYPE = re.compile(r"^(?P<t>[a-z]+)(?:\([^)]*\))?!?:")


def _git(repo: str, *a: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=20)


def _spec(p: str) -> str:
    return f":(glob){p}" if any(ch in p for ch in "*?[") else p


_cache: dict[tuple[str, str, str, tuple[str, ...]], int | None] = {}


def code_commits(repo: str, read: str | None, covers: list[str], ref: str = "HEAD", ref_sha: str | None = None) -> int | None:
    """읽은 커밋 뒤로 다루는 곳을 바꾼 feat · fix 커밋 수(병합 커밋 뺌). 읽은 커밋이 없거나 저장소에 없으면 None."""
    if not read or not _SHA.fullmatch(read) or not covers or bad_covers(covers):
        return None
    sha = ref_sha or _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").stdout.strip()
    key = (repo, read, sha, tuple(covers))
    if sha and key in _cache:
        return _cache[key]
    if _git(repo, "cat-file", "-e", f"{read}^{{commit}}").returncode != 0:
        n = None
    else:
        r = _git(repo, "log", "--no-merges", "--format=%s", f"{read}..{sha or ref}", "--", *(_spec(c) for c in covers))
        n = None if r.returncode != 0 else sum(bool((m := _TYPE.match(s)) and m["t"] in CODE_TYPES) for s in r.stdout.splitlines())
    if sha:
        _cache[key] = n
    return n


def files(repo: str, folder: str, ref: str = "HEAD") -> list[str]:
    """ref에 있는 folder 아래 .md(하위 폴더까지), 나무 차례로 — 파일 번호가 차례, 폴더 `NN_이름/`은 `NN_이름.md` 바로 뒤."""
    raw = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", "--name-only", ref, folder],
                         capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
    return tree_order([f for f in raw.split("\0") if f.endswith(".md")])


def _num(name: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d+)([a-z])?_", name)
    return (int(m.group(1)), ord(m.group(2)) - 96 if m.group(2) else 0) if m else None


def tree_order(paths: list[str]) -> list[str]:
    """나무 차례 — 칸마다 (번호, 이름). 번호 없는 이름은 번호 있는 것 뒤. 부모 글(`02_x.md`)은 그 폴더(`02_x/`)의 글보다 앞."""
    def key(p: str) -> list[tuple[int, int, int, str]]:
        parts = p.split("/")
        parts[-1] = parts[-1][:-3] if parts[-1].endswith(".md") else parts[-1]
        out = []
        for part in parts:
            n = _num(part + "_") if re.fullmatch(r"\d+[a-z]?", part) else _num(part)
            out.append((0, *n, part) if n else (1, 0, 0, part))
        return out
    return sorted(paths, key=key)


def tree_parent(path: str, root: str) -> str | None:
    """나무 규칙의 부모 글 — `notion/02_x/01_y.md` → `notion/02_x.md`. root 바로 아래 글이면 None."""
    folder = path.rsplit("/", 1)[0] + "/"
    if folder == root:
        return None
    return folder[:-1] + ".md"


def pieces(repo: str, folder: str, ref: str = "HEAD") -> list[dict[str, Any]]:
    """folder 아래 편마다 {path, title, covers, read, commits, why}. commits = 코드가 바뀐 커밋 수(None이면 셀 수 없음, why에 까닭)."""
    sha =_git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").stdout.strip() or None
    out = []
    for f in files(repo, folder, ref):
        r = _git(repo, "show", f"{ref}:{f}")
        body = r.stdout if r.returncode == 0 else ""
        h = parse_head(body)
        title = first_h1(body)[1] or PurePosixPath(f).stem
        why = None
        n = None
        if h is None:
            why = "머리 주석이 없습니다"
        elif not h["read"]:
            why = f"「{READ}」이 없습니다"
        elif not h["covers"]:
            why = f"「{COVERS}」가 없습니다"
        elif bad_covers(h["covers"]):
            why = f"「{COVERS}」가 저장소 밖을 가리킵니다"
        else:
            n = code_commits(repo, h["read"], h["covers"], ref, sha)
            if n is None:
                why = f"{READ} {h['read']}을 저장소에서 찾지 못했습니다"
        out.append({"path": f, "title": title, "covers": (h or {}).get("covers", []), "read": (h or {}).get("read"),
                    "commits": n, "why": why})
    return out


def tally(ps: list[dict[str, Any]]) -> dict[str, int]:
    """글 N편 가운데 코드가 바뀐 편 M · 셀 수 없는 편 K."""
    return {"total": len(ps), "changed": sum(bool(p["commits"]) for p in ps), "unknown": sum(p["commits"] is None for p in ps)}
