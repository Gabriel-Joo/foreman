"""저장소 읽기(11-17 문서 도구 합치기 2단계, 전에는 `bridge/docrefs.py`의 `_git`, `_tree`, `_read_many`).

읽기만 한다. git은 ls-files, ls-tree, cat-file, diff, merge-base, rev-parse만 부른다(부르는 쪽이 고른다).
작업 트리를 읽거나(rev 없음) 커밋 하나를 읽는다(rev). 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class RepoError(RuntimeError):
    """git을 부르지 못함, git 명령 실패. 화면과 카드는 이 글을 그대로 보인다(`bridge.docrefs.DocrefsError`와 같은 것)."""


def git(repo: str | Path, *a: str, input_: bytes | None = None) -> bytes:
    try:
        r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, timeout=60, input=input_)
    except (OSError, subprocess.SubprocessError) as e:
        raise RepoError(f"git을 부르지 못했습니다({type(e).__name__})") from e
    if r.returncode:
        raise RepoError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def gits(repo: str | Path, *a: str) -> str:
    return git(repo, *a).decode(errors="replace")


def tree(repo: str | Path, rev: str | None, dirs: list[str] | None = None) -> list[str]:
    """추적 파일 경로. rev면 그 커밋(ls-tree), 아니면 작업 트리의 색인(ls-files). dirs로 좁힌다."""
    if rev:
        out = gits(repo, "ls-tree", "-r", "--name-only", rev, "--", *(dirs or []))
    else:
        out = gits(repo, "ls-files", "--", *(dirs or []))
    return [x for x in out.splitlines() if x]


def read_many(repo: str | Path, rev: str | None, paths: list[str]) -> dict[str, str]:
    """여러 파일을 한 번에. rev면 `git cat-file --batch`, 아니면 작업 트리. 없는 파일은 빠진다."""
    if not paths:
        return {}
    out: dict[str, str] = {}
    if not rev:
        for p in paths:
            try:
                out[p] = (Path(repo) / p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        return out
    raw = git(repo, "cat-file", "--batch", input_="".join(f"{rev}:{p}\n" for p in paths).encode())
    i = 0
    for p in paths:
        nl = raw.index(b"\n", i)
        head = raw[i:nl].decode(errors="replace").split()
        i = nl + 1
        if len(head) < 3 or head[1] == "missing":
            continue
        size = int(head[2])
        out[p] = raw[i:i + size].decode(errors="replace")
        i += size + 1
    return out
