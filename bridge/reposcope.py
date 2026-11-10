"""다른 저장소는 읽기만(11-09 사용자 — 구조 1단계).

`config/approval.toml [repo_scope] read_only_elsewhere`에 적은 프로젝트(지금 foreman)의 세션이 자기 저장소(+ 그 worktree)
밖의 git 저장소를 고치려 하면 PreToolUse에서 거부한다. 스키마 잠금처럼 승인 모드(observe · enforce)와 상관없다.

- Edit · Write · MultiEdit · NotebookEdit: 대상 파일이 다른 git 저장소 안이면
- Bash의 git: `-C` · `cd` · `--git-dir` · `--work-tree` · `GIT_DIR=`로 다른 저장소를 가리키며 읽기 명령(`read`) 밖을 쓰면.
  branch · tag · remote · stash · worktree는 목록 보기만 읽기로 친다. fetch도 그 저장소 .git에 쓰므로 막는다
- /tmp 아래(스크래치 복제본)와 git 저장소가 아닌 곳(~/.claude 등)은 막지 않는다
- 예외(11-10 사용자 — 인프라 묶음 1에서 펫퍼민트 · 런슈즈 문서를 고친다): `[repo_scope.writable]`에 적은 "<프로젝트>/<경로>/" 아래는
  Edit · Write로 고칠 수 있다. 그 프로젝트의 원본 저장소(DB project.repo_path)만 — 그 저장소의 worktree는 아니다. git 쓰기는 그대로 막는다
- Bash의 그 밖 쓰기(sed -i · 리디렉션)는 보지 않는다 — CC 샌드박스는 일상 명령을 시험한 뒤(사용자)
"""

from __future__ import annotations

import os
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any, Callable

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
FREE_ROOTS = ("/tmp/",)
SEPS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&"}
GIT_OPT_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}


def _top(path: str) -> str | None:
    p = Path(path)
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return str(d)
    return None


def _resolve(path: str, base: str) -> str:
    return os.path.realpath(os.path.join(base, os.path.expanduser(path)))


_BRANCH_W = {"-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy", "--force",
             "--set-upstream-to", "--unset-upstream", "--edit-description"}
_TAG_W = {"-d", "-a", "-s", "-f", "-m", "-F", "-u", "--delete", "--annotate", "--sign", "--force"}
_LIST_FLAGS = {"-l", "--list", "-a", "-r", "--all", "--remotes", "--contains", "--no-contains", "--merged",
               "--no-merged", "--points-at", "--show-current"}


def _is_read(sub: str, rest: list[str]) -> bool:
    """읽기 목록(read) 밖이지만 인자에 따라 읽기인 것 — 목록 보기 · 시험만 하기(11-09 지난 7일 다시 돌려 본 헛거부)."""
    flags = {a.split("=", 1)[0] for a in rest if a.startswith("-")}
    pos = [a for a in rest if a and not a.startswith("-")]
    first = pos[0] if pos else ""
    if sub == "branch":
        return not (flags & _BRANCH_W) and (not pos or bool(flags & _LIST_FLAGS))
    if sub == "tag":
        return not (flags & _TAG_W) and (not pos or bool(flags & _LIST_FLAGS))
    if sub == "remote":
        return first in ("", "show", "get-url")
    if sub == "stash":
        return first in ("list", "show")
    if sub == "worktree":
        return first == "list"
    if sub == "reflog":
        return first not in ("expire", "delete")
    if sub == "config":
        return bool(flags & {"--get", "--get-all", "--get-regexp", "--list", "-l", "--get-urlmatch"})
    if sub == "apply":
        return bool(flags & {"--check", "--stat", "--numstat", "--summary"})
    if sub == "fetch":
        return "--dry-run" in flags   # -n은 --no-tags다(dry-run 아님)
    return False


def _heredoc_free(cmd: str) -> list[str]:
    """줄마다 나누되 heredoc 본문(커밋 메시지 등)은 뺀다."""
    out, end = [], None
    for line in cmd.splitlines():
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        if m := re.search(r"<<-?\s*['\"]?([A-Za-z_][\w]*)['\"]?", line):
            end = m.group(1)
    return out


def _tokens(line: str) -> list[str]:
    try:
        lx = shlex.shlex(line, posix=True, punctuation_chars=True)
        lx.whitespace_split = True
        return list(lx)
    except ValueError:
        return line.split()


class RepoScope:
    def __init__(self, config: str | Path, repos: Callable[[], dict[str, str]],
                 free: tuple[str, ...] = FREE_ROOTS) -> None:
        self.free = free
        self.projects: set[str] = set()
        self.read: set[str] = set()
        self.writable: dict[str, list[tuple[str, str]]] = {}   # 세션 프로젝트 → [(다른 프로젝트, 경로 "docs/")]
        p = Path(config)
        if p.exists():
            r = tomllib.loads(p.read_text()).get("repo_scope") or {}
            self.projects = set(r.get("read_only_elsewhere") or [])
            self.read = set(r.get("read") or [])
            for proj, items in (r.get("writable") or {}).items():
                for it in items or []:
                    name, _, sub = str(it).partition("/")
                    sub = sub.strip("/")
                    if name and sub and ".." not in sub.split("/"):
                        self.writable.setdefault(proj, []).append((name, sub + "/"))
        self.repos = repos   # 프로젝트 이름 → 저장소 경로(DB project.repo_path)

    # ── 판정 ──────────────────────────────────────────────
    def check(self, project: str | None, cwd: str | None, tool: str, inp: dict[str, Any],
              scratch: str | None = None) -> str | None:
        """거부 이유 또는 None."""
        if not project or project not in self.projects:
            return None
        own = self.repos().get(project)
        if not own:
            return None
        base = cwd or own
        if tool in EDIT_TOOLS:
            path = inp.get("file_path") or inp.get("notebook_path")
            if isinstance(path, str) and path:
                full = _resolve(path, base)
                other = self._other(full, own, scratch)
                if other and not self._writable(project, full, other):
                    return self._why(other, f"{tool} {path}")
            return None
        if tool == "Bash":
            for other, what in self._git_writes(str(inp.get("command") or ""), base, own, scratch):
                return self._why(other, what)
        return None

    def _other(self, full: str, own: str, scratch: str | None) -> str | None:
        """full이 자기 저장소 밖의 git 저장소 안이면 그 저장소 맨 위."""
        if (self.free and full.startswith(self.free)) or (scratch and full.startswith(scratch.rstrip("/") + "/")):
            return None
        top = _top(full)
        if not top:
            return None
        own = os.path.realpath(own)
        if top == own or top.startswith(own.rstrip("/") + "/"):
            return None
        return top

    def _writable(self, project: str, full: str, other: str) -> bool:
        """full(실제 경로)이 [repo_scope.writable]에 적은 다른 프로젝트 원본 저장소의 그 경로 아래인가."""
        repos = self.repos()
        for name, sub in self.writable.get(project, []):
            repo = repos.get(name)
            if not repo or os.path.realpath(repo) != other:
                continue
            if full.startswith(other.rstrip("/") + "/" + sub):
                return True
        return False

    def _git_writes(self, cmd: str, base: str, own: str, scratch: str | None):
        cur = base
        for line in _heredoc_free(cmd):
            seg: list[str] = []
            for t in [*_tokens(line), ";"]:
                if t not in SEPS:
                    seg.append(t)
                    continue
                if seg:
                    if seg[0] in ("cd", "pushd") and len(seg) > 1 and "$" not in seg[1]:
                        cur = _resolve(seg[1], cur)
                    else:
                        hit = self._git_seg(seg, cur, own, scratch)
                        if hit:
                            yield hit
                seg = []

    def _git_seg(self, seg: list[str], cur: str, own: str, scratch: str | None) -> tuple[str, str] | None:
        i, target = 0, cur
        while i < len(seg) and re.match(r"^[A-Za-z_]\w*=", seg[i]):   # GIT_DIR=… git …
            k, v = seg[i].split("=", 1)
            if k in ("GIT_DIR", "GIT_WORK_TREE") and v:
                target = _resolve(v, cur)
            i += 1
        if i >= len(seg) or os.path.basename(seg[i]) != "git":
            return None
        i += 1
        while i < len(seg) and seg[i].startswith("-"):
            opt = seg[i]
            name, _, val = opt.partition("=")
            if name in GIT_OPT_ARG and not val:
                val = seg[i + 1] if i + 1 < len(seg) else ""
                i += 1
            if name == "-C" and val:
                target = _resolve(val, target)
            elif name in ("--git-dir", "--work-tree") and val:
                target = _resolve(val, cur)
            i += 1
        sub = seg[i] if i < len(seg) else ""
        rest = seg[i + 1:]
        if not sub or sub in self.read:
            return None
        if _is_read(sub, rest):
            return None
        if "$" in target:
            return target, "git " + sub
        other = self._other(target, own, scratch)
        return (other, "git " + sub) if other else None

    @staticmethod
    def _why(other: str, what: str) -> str:
        return (f"다른 저장소 쓰기 막힘 — 이 세션은 다른 저장소({os.path.basename(other)})를 읽기만 합니다({what}). "
                "고칠 것은 그 저장소의 세션에 맡기거나(세션 간 메시지) 사용자에게 요청하세요. "
                "상태만 볼 때는 git ls-remote, 손볼 시험은 /tmp · 스크래치 복제본에서 합니다.")
