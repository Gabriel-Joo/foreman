"""저장소 읽기(11-17 문서 도구 합치기 2단계, 전에는 `bridge/docrefs.py`의 `_git`, `_tree`, `_read_many`).

읽기만 한다. git은 ls-files, ls-tree, cat-file, diff, merge-base, rev-parse만 부른다(부르는 쪽이 고른다).
작업 트리를 읽거나(rev 없음) 커밋 하나를 읽는다(rev). 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


class RepoError(RuntimeError):
    """git을 부르지 못함, git 명령 실패. 화면과 카드는 이 글을 그대로 보인다(`bridge.docrefs.DocrefsError`와 같은 것)."""


QUOTED_PATH = re.compile(r'^"(?:[^"\\]|\\.)*"$')


def quoted_problem(path: str) -> str:
    """git이 경로를 따옴표와 8진수로 싸서 내보낸 것을 알리는 글. 문서 도구가 git 출력에서 파일 이름을 읽는 모든 길이 같은 글을 쓴다."""
    return f"git이 경로를 따옴표로 내보내 파일 이름을 읽지 못했습니다({path})"


def is_quoted(path: str) -> bool:
    """`"data/\\352\\261..md"`처럼 git이 싼 경로인가. `-z`나 `core.quotepath=false`로 읽으면 한글 이름은 싸이지 않는다(따옴표, 역슬래시, 제어 글자만 싸인다)."""
    return bool(QUOTED_PATH.match(path)) and "\\" in path


def git(repo: str | Path, *a: str, input_: bytes | None = None) -> bytes:
    # core.quotepath=false: 한글 같은 비아스키 이름을 8진수로 싸지 않게(11-19 펫퍼민트 52줄이 덮기 밖으로 세어진 조용한 고장)
    try:
        r = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=false", *a], capture_output=True, timeout=60,
                           input=input_)
    except (OSError, subprocess.SubprocessError) as e:
        raise RepoError(f"git을 부르지 못했습니다({type(e).__name__})") from e
    if r.returncode:
        raise RepoError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def gits(repo: str | Path, *a: str) -> str:
    return git(repo, *a).decode(errors="replace")


def git_z(repo: str | Path, *a: str) -> list[str]:
    """파일 목록을 내는 git 명령을 `-z`로 읽는다. 첫 낱말 뒤에 `-z`를 넣고 `\\0`로 나눠, 따옴표 싸기도 줄바꿈 깨짐도 없다."""
    return [x for x in git(repo, a[0], "-z", *a[1:]).decode(errors="replace").split("\0") if x]


def tree(repo: str | Path, rev: str | None, dirs: list[str] | None = None) -> list[str]:
    """추적 파일 경로. rev면 그 커밋(ls-tree), 아니면 작업 트리의 색인(ls-files). dirs로 좁힌다."""
    if rev:
        return git_z(repo, "ls-tree", "-r", "--name-only", rev, "--", *(dirs or []))
    return git_z(repo, "ls-files", "--", *(dirs or []))


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
