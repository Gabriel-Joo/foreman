"""세션마다 따로 작업하는 자리(git worktree, 11-05 · README 3.4).

한 프로젝트에 세션이 이미 살아 있는데 하나를 더 띄우면, 기본으로 `<repo>/.worktrees/<이름>`(브랜치 `cc/<이름>`)에서 띄운다.
같은 파일을 둘이 덮어쓰거나 커밋이 섞이는 것을 막는다. 끝낼 때는 사람이 승인하면 main 위로 rebase한 뒤 fast-forward로 합친다.
충돌이 나면 rebase를 되돌리고 충돌 파일을 보여 준다(멈춤). 합친 뒤에는 worktree와 브랜치를 지운다.

- 폴더를 저장소 안에 두는 까닭: 조립기가 cwd 접두어로 프로젝트를 정하므로(`_project_for`) 그대로 같은 프로젝트의 캐릭터가 된다.
  CC 폴더 신뢰도 상위 폴더를 따른다
- 커밋 안 하는 것(.venv · .env* · node_modules)은 원본을 가리키는 링크로 둔다. `.git/info/exclude`(로컬 전용, 저장소 파일 아님)에
  `.worktrees/`와 링크 이름을 넣어 git이 보지 않게 한다
- CC 메모리 폴더는 작업 폴더 경로마다 따로 생긴다 — worktree 쪽 `memory`를 원본 메모리 폴더 링크로 만든다
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from bridge.inject import Refused

WT_DIR = ".worktrees"
BRANCH_PREFIX = "cc/"
EXCLUDE = [f"/{WT_DIR}/", "/.venv", "/.env*", "node_modules"]   # 링크는 파일이라 `.venv/` 패턴에 안 걸린다
LINK_TOP = re.compile(r"^(\.venv|\.env.*)$")                     # 저장소 맨 위에서 링크할 것(추적 안 되는 것만)
LINK_SUB = ("node_modules",)                                     # 한 단계 아래(frontend/node_modules 등)


async def git(cwd: str | Path, *args: str, check: bool = True) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec("git", "-C", str(cwd), *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.STDOUT, env={**os.environ, "GIT_EDITOR": "true",
                                                                                   "GIT_TERMINAL_PROMPT": "0"})
    out, _ = await p.communicate()
    s = out.decode(errors="replace").strip()
    if check and p.returncode:
        raise Refused(f"git {' '.join(args[:2])} 실패: {s[-300:]}")
    return p.returncode or 0, s


def cc_project_dir(cwd: str | Path) -> Path:
    """CC가 그 폴더의 트랜스크립트 · 메모리를 두는 곳(handoff.transcript_path와 같은 규칙)."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(cwd))


def split(path: str | Path) -> tuple[str, str | None]:
    """폴더 → (저장소, worktree 이름 또는 None). `<repo>/.worktrees/<name>/…`이면 그 이름."""
    p = os.path.realpath(str(path))
    m = re.match(rf"^(.*?)/{re.escape(WT_DIR)}/([^/]+)(?:/|$)", p)
    return (m.group(1), m.group(2)) if m else (p, None)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:24] or "wt"


async def is_repo(path: str) -> bool:
    rc, out = await git(path, "rev-parse", "--show-toplevel", check=False)
    return rc == 0 and os.path.realpath(out) == os.path.realpath(path)


async def base_branch(repo: str) -> str:
    _, b = await git(repo, "branch", "--show-current")
    if not b:
        raise Refused("원본 저장소가 브랜치 위에 있지 않습니다(detached HEAD)")
    return b


async def create(repo: str, hint: str) -> dict[str, Any]:
    """새 worktree — 이름은 `<hint>`, 겹치면 -2, -3 …. 원본 브랜치의 지금 커밋에서 갈라진다."""
    repo = os.path.realpath(repo)
    if not await is_repo(repo):
        raise Refused(f"git 저장소의 맨 위 폴더가 아닙니다: {repo}")
    base = await base_branch(repo)
    _, branches = await git(repo, "branch", "--list", f"{BRANCH_PREFIX}*", "--format=%(refname:short)")
    taken = set(branches.split()) | {p.name for p in (Path(repo) / WT_DIR).glob("*")}
    name, n = slug(hint), 2
    while name in taken or BRANCH_PREFIX + name in taken:
        name, n = f"{slug(hint)}-{n}", n + 1
    path = Path(repo) / WT_DIR / name
    _exclude(repo)
    await git(repo, "worktree", "add", "-b", BRANCH_PREFIX + name, str(path), base)
    links = link_local(repo, str(path))
    mem = link_memory(repo, str(path))
    return {"name": name, "path": str(path), "branch": BRANCH_PREFIX + name, "base": base, "links": links, "memory": mem}


def _exclude(repo: str) -> None:
    f = Path(repo) / ".git" / "info" / "exclude"
    f.parent.mkdir(parents=True, exist_ok=True)
    have = f.read_text().splitlines() if f.exists() else []
    add = [x for x in EXCLUDE if x not in have]
    if add:
        with f.open("a") as fh:
            fh.write(("\n" if have and have[-1] else "") + "# FOREMAN worktree(11-05)\n" + "\n".join(add) + "\n")


def link_local(repo: str, wt: str) -> list[str]:
    """커밋 안 하는 것 — 원본을 가리키는 링크. 이미 있으면(추적되는 파일 등) 건드리지 않는다."""
    done = []
    cands = [p for p in Path(repo).iterdir() if LINK_TOP.match(p.name)]
    for sub in Path(repo).iterdir():
        if sub.is_dir() and not sub.name.startswith("."):
            cands += [sub / n for n in LINK_SUB if (sub / n).exists()]
    for src in cands:
        dst = Path(wt) / src.relative_to(repo)
        if dst.exists() or dst.is_symlink() or not dst.parent.is_dir():
            continue
        dst.symlink_to(src)
        done.append(str(src.relative_to(repo)))
    return done


def link_memory(repo: str, wt: str) -> str | None:
    """worktree 쪽 CC 프로젝트 폴더의 memory → 원본 저장소의 memory. 원본에 메모리가 없으면 만들지 않는다."""
    src = cc_project_dir(repo) / "memory"
    if not src.is_dir():
        return None
    d = cc_project_dir(wt)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / "memory"
    if dst.is_symlink() or dst.exists():
        return str(dst)
    dst.symlink_to(src)
    return str(dst)


async def status(repo: str, name: str) -> dict[str, Any]:
    """합치기 전에 보는 것 — 갈라진 뒤 쌓인 커밋, 원본이 앞서간 커밋 수, 커밋 안 된 변경, 바뀐 파일."""
    path = Path(repo) / WT_DIR / name
    branch = BRANCH_PREFIX + name
    out: dict[str, Any] = {"name": name, "path": str(path), "branch": branch, "exists": path.is_dir()}
    if not path.is_dir():
        return out
    base = await base_branch(repo)
    _, ahead = await git(repo, "rev-list", "--count", f"{base}..{branch}")
    _, behind = await git(repo, "rev-list", "--count", f"{branch}..{base}")
    _, log = await git(repo, "log", "--format=%h %s", f"{base}..{branch}")
    _, dirty = await git(path, "status", "--porcelain")
    _, stat = await git(repo, "diff", "--stat", f"{base}...{branch}")
    out.update(base=base, ahead=int(ahead or 0), behind=int(behind or 0), commits=log.splitlines()[:30],
               dirty=[ln for ln in dirty.splitlines() if ln][:30], diffstat=stat.splitlines()[-12:])
    return out


def _forbidden(wt_path: str, rel: str) -> bool:
    """쉬게 하기 커밋에 넣으면 안 되는 것 — 원본을 가리키는 링크(.venv · .env* · node_modules)와 worktree 밖을 가리키는 링크.
    .gitignore가 없는 저장소에서도 막는다(`.venv/` 패턴은 링크(파일)에 안 걸린다 — EXCLUDE 주석). 견본(.env*.example)은 넣는다."""
    top = rel.split("/", 1)[0]
    if "node_modules" in rel.split("/"):
        return True
    if top == ".venv" or (top.startswith(".env") and not top.endswith(".example")):
        return True
    p = Path(wt_path) / rel
    if p.is_symlink():
        target = os.path.realpath(p)
        return not (target == os.path.realpath(wt_path) or target.startswith(os.path.realpath(wt_path) + os.sep))
    return False


async def save_progress(wt_path: str, message: str) -> dict[str, Any]:
    """[쉬게 하기](11-09) — 커밋 안 한 변경을 이 브랜치에 커밋한다. `git add -A`(.gitignore를 지킨다) 뒤 넣으면 안 되는 것(_forbidden)은
    빼고, 빠진 것은 결과에 적는다(조용히 넘어가지 않는다). 변경이 없으면 커밋하지 않는다. 실패는 Refused로 — 세션을 끝내기 전에 멈춘다."""
    _, dirty = await git(wt_path, "status", "--porcelain")
    if not dirty.strip():
        return {"commit": None, "files": 0, "skipped": []}
    await git(wt_path, "add", "-A")
    _, staged = await git(wt_path, "diff", "--cached", "--name-only", "-z")
    names = [n for n in staged.split("\0") if n]
    skipped = [n for n in names if _forbidden(wt_path, n)]
    if skipped:
        await git(wt_path, "reset", "-q", "--", *skipped)
    keep = [n for n in names if n not in skipped]
    if not keep:
        return {"commit": None, "files": 0, "skipped": skipped}
    rc, out = await git(wt_path, "commit", "-q", "-m", message, check=False)
    if rc:
        await git(wt_path, "reset", "-q", check=False)       # 올려 둔 것을 내린다 — 작업 트리는 그대로
        raise Refused(f"커밋하지 못했습니다 — {out[-300:] or 'git commit 실패'}. 세션은 끝내지 않았습니다")
    _, h = await git(wt_path, "rev-parse", "--short", "HEAD")
    return {"commit": h, "files": len(keep), "skipped": skipped}


async def merge(repo: str, name: str) -> dict[str, Any]:
    """rebase(worktree에서) → fast-forward(원본에서) → worktree · 브랜치 지우기. 충돌이면 rebase를 되돌리고 멈춘다.
    push는 하지 않는다(런슈즈는 push가 곧 배포 — 사람이 따로)."""
    st = await status(repo, name)
    if not st["exists"]:
        raise Refused("worktree가 없습니다")
    if st["dirty"]:
        raise Refused(f"커밋 안 된 변경이 {len(st['dirty'])}개 있습니다. 그 세션에서 커밋하거나 버린 뒤 합쳐 주세요")
    path, base, branch = st["path"], st["base"], st["branch"]
    if st["ahead"] == 0:
        await remove(repo, name, force=False)
        return {"ok": True, "merged": 0, "note": "합칠 커밋이 없어 worktree만 지웠습니다."}
    if st["behind"]:
        rc, out = await git(path, "rebase", base, check=False)
        if rc:
            _, files = await git(path, "diff", "--name-only", "--diff-filter=U", check=False)
            await git(path, "rebase", "--abort", check=False)
            return {"ok": False, "conflict": files.splitlines(), "detail": out[-800:],
                    "note": "rebase 중 충돌이 나서 되돌렸습니다. 충돌 파일을 그 세션에서 풀어 커밋한 뒤 다시 합쳐 주세요."}
    _, dirty_main = await git(repo, "status", "--porcelain", "--untracked-files=no")
    rc, out = await git(repo, "merge", "--ff-only", branch, check=False)
    if rc:
        return {"ok": False, "conflict": [], "detail": out[-800:],
                "note": "원본 저장소에서 fast-forward가 되지 않았습니다(원본의 커밋 안 된 변경과 겹칠 수 있습니다)."
                        + (f" 원본에 커밋 안 된 파일 {len(dirty_main.splitlines())}개." if dirty_main else "")}
    await remove(repo, name, force=False)
    return {"ok": True, "merged": st["ahead"], "commits": st["commits"],
            "note": f"{base}에 커밋 {st['ahead']}개를 합쳤습니다. push는 하지 않았습니다."}


async def remove(repo: str, name: str, force: bool) -> None:
    path = Path(repo) / WT_DIR / name
    if path.is_dir():
        await git(repo, "worktree", "remove", *(["--force"] if force else []), str(path))
    await git(repo, "worktree", "prune", check=False)
    await git(repo, "branch", "-D" if force else "-d", BRANCH_PREFIX + name, check=False)
