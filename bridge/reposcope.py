"""다른 저장소는 읽기만(11-09 사용자 — 구조 1단계).

`config/approval.toml [repo_scope] read_only_elsewhere`에 적은 프로젝트(지금 foreman)의 세션이 자기 저장소(+ 그 worktree)
밖의 git 저장소를 고치려 하면 PreToolUse에서 거부한다. 스키마 잠금처럼 승인 모드(observe · enforce)와 상관없다.

- Edit · Write · MultiEdit · NotebookEdit: 대상 파일이 다른 git 저장소 안이면
- Bash의 git: `-C` · `cd` · `--git-dir` · `--work-tree` · `GIT_DIR=`로 다른 저장소를 가리키며 읽기 명령(`read`) 밖을 쓰면.
  branch · tag · remote · stash · worktree는 목록 보기만 읽기로 친다. fetch도 그 저장소 .git에 쓰므로 막는다
- /tmp 아래(스크래치 복제본)와 git 저장소가 아닌 곳(~/.claude 등)은 막지 않는다
- 예외(11-10 사용자 — 인프라 묶음 1에서 펫퍼민트 · 런슈즈 문서를 고친다): `[repo_scope.writable]`에 적은 "<프로젝트>/<경로>/" 아래는
  Edit · Write로 고칠 수 있다. 그 프로젝트의 원본 저장소(DB project.repo_path)만 — 그 저장소의 worktree는 아니다.
  git은 add · commit만 그 경로 안에서(사용자 11-10 — 다른 변경이 섞이지 않게):
    add    경로를 적은 것만(그 경로 아래). -A · -u · . · :/ · 그 밖 옵션은 막는다
    commit -a · --amend · -i 등은 막는다. 경로를 적으면 그 경로 아래만, 안 적으면 그 저장소 스테이지가 그 경로 아래만 담을 때
           (다른 세션이 올려 둔 변경이 섞이지 않게 — PreToolUse 때 git diff --cached로 본다)
    push · 그 밖의 쓰기는 그대로 막는다
- 예외 2(11-10 사용자 — 인프라 세션의 docs 커밋은 관리자가 확인하고 push): `[repo_scope.manager_push]`에 적은 저장소에서
  관리자 세션(role manager, 그 프로젝트 원본 폴더 — worktree 아님)만 `git push [origin] [main]`을 할 수 있다.
  origin/main(ls-remote로 읽음)보다 앞선 커밋이 전부 그 경로("docs/")만 건드렸을 때만. 하나라도 밖이면 · 머지 커밋 · 뒤처짐 · 갈라짐 ·
  원격 못 읽음이면 거부. 역할은 부른 쪽(api/hooks.py)이 git push가 보일 때만 DB에서 읽어 넘긴다(wants_role)
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


def _strip_redir(rest: list[str]) -> list[str]:
    """리디렉션(<<'EOF' · > out · 2>&1)은 인자가 아니다 — 기호와 그 대상, 기호 바로 앞의 fd 숫자를 뺀다."""
    args: list[str] = []
    skip = False
    for k, a in enumerate(rest):
        if skip:
            skip = False
            continue
        if a and set(a) <= set("<>&"):          # 다음 토큰(파일 · EOF 표지 · ">&" 뒤 fd)은 대상
            skip = True
            continue
        if a.isdigit() and k + 1 < len(rest) and rest[k + 1] and set(rest[k + 1]) <= set("<>&"):
            continue
        args.append(a)
    return args


def _git(repo: str, *args: str, timeout: float = 5) -> str | None:
    """그 저장소에서 git 읽기 명령 — 표준 출력(끝 줄바꿈 뺌). 실패 · 시간 넘김이면 None."""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=timeout, check=True,
                           stdin=subprocess.DEVNULL, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.decode("utf-8", "replace").rstrip("\n")


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
        self.manager_push: dict[str, list[tuple[str, str]]] = {}   # 같은 모양 — 관리자 세션의 docs 전용 push(11-10)
        p = Path(config)
        if p.exists():
            r = tomllib.loads(p.read_text()).get("repo_scope") or {}
            self.projects = set(r.get("read_only_elsewhere") or [])
            self.read = set(r.get("read") or [])
            self.writable = self._pairs(r.get("writable"))
            self.manager_push = self._pairs(r.get("manager_push"))
        self.repos = repos   # 프로젝트 이름 → 저장소 경로(DB project.repo_path)

    @staticmethod
    def _pairs(table: Any) -> dict[str, list[tuple[str, str]]]:
        """{세션 프로젝트: ["<다른 프로젝트>/<경로>/", …]} → {세션 프로젝트: [(다른 프로젝트, "경로/")]}. 경로 없음 · ..는 버린다."""
        out: dict[str, list[tuple[str, str]]] = {}
        for proj, items in (table or {}).items():
            for it in items or []:
                name, _, sub = str(it).partition("/")
                sub = sub.strip("/")
                if name and sub and ".." not in sub.split("/"):
                    out.setdefault(proj, []).append((name, sub + "/"))
        return out

    def wants_role(self, tool: str, inp: dict[str, Any]) -> bool:
        """판정에 세션 역할이 필요한가 — git push가 보이는 Bash만(관리자 docs push, 11-10). 부른 쪽이 DB에서 역할을 읽어 넘긴다."""
        return tool == "Bash" and bool(self.manager_push) and bool(re.search(r"\bpush\b", str(inp.get("command") or "")))

    # ── 판정 ──────────────────────────────────────────────
    def check(self, project: str | None, cwd: str | None, tool: str, inp: dict[str, Any],
              scratch: str | None = None, role: str | None = None) -> str | None:
        """거부 이유 또는 None. role은 그 세션의 역할(DB character_session.role, worktree 세션이면 부른 쪽이 None)."""
        if not project or project not in self.projects:
            return None
        own = self.repos().get(project)
        if not own:
            return None
        base = cwd or own
        # 관리자 세션 — 그 프로젝트 원본 폴더(worktree 아님)에서 도는 role manager(11-10 사용자)
        manager = (role == "manager" and bool(cwd)
                   and _top(os.path.realpath(cwd or "")) == os.path.realpath(own))
        if tool in EDIT_TOOLS:
            path = inp.get("file_path") or inp.get("notebook_path")
            if isinstance(path, str) and path:
                full = _resolve(path, base)
                other = self._other(full, own, scratch)
                if other and not self._writable(project, full, other):
                    return self._why(other, f"{tool} {path}")
            return None
        if tool == "Bash":
            for why in self._git_writes(project, str(inp.get("command") or ""), base, own, scratch, manager):
                return why
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

    def _subs(self, project: str, other: str, table: dict[str, list[tuple[str, str]]] | None = None) -> list[str]:
        """[repo_scope.writable](또는 table)에서 이 세션 프로젝트가 저장소 other(맨 위, 실제 경로)에 대해 받은 경로들("docs/")."""
        repos = self.repos()
        return [sub for name, sub in (self.writable if table is None else table).get(project, [])
                if repos.get(name) and os.path.realpath(repos[name]) == other]

    @staticmethod
    def _under(full: str, other: str, subs: list[str]) -> bool:
        """full이 other의 그 경로 아래(그 폴더 자체 포함)인가."""
        for sub in subs:
            d = other.rstrip("/") + "/" + sub.rstrip("/")
            if full == d or full.startswith(d + "/"):
                return True
        return False

    def _writable(self, project: str, full: str, other: str) -> bool:
        """full(실제 경로)이 [repo_scope.writable]에 적은 다른 프로젝트 원본 저장소의 그 경로 아래인가."""
        return self._under(full, other, self._subs(project, other))

    # ── 예외 저장소의 git(11-10 사용자) — add는 경로를 적은 것만 · commit은 그 경로만 담길 때 · 나머지(push 등)는 막는다 ──
    _ADD_OK = {"-v", "--verbose", "-n", "--dry-run", "--"}
    _COMMIT_OK = {"-q", "--quiet", "-v", "--verbose", "-s", "--signoff", "--no-edit", "--no-verify", "-n", "--"}
    _COMMIT_VAL = {"-m", "--message", "-F", "--file", "--author", "--date", "--cleanup"}

    def _docs_git(self, sub: str, rest: list[str], target: str, other: str, subs: list[str]) -> str | None:
        """예외 저장소에서 add · commit이 허용 범위인지 — 거부 이유 또는 None. 그 밖의 git 쓰기는 부른 쪽이 막는다."""
        where = " · ".join(subs)
        rest = _strip_redir(rest)
        paths: list[str] = []
        i, dashdash = 0, False
        while i < len(rest):
            a = rest[i]
            name = a.split("=", 1)[0]
            if not dashdash and a == "--":
                dashdash = True
            elif not dashdash and a.startswith("-"):
                ok, val = (self._ADD_OK, set()) if sub == "add" else (self._COMMIT_OK, self._COMMIT_VAL)
                if name in val:
                    i += 0 if "=" in a else 1          # 값은 경로가 아니다(-m '메시지')
                elif name not in ok:
                    return f"git {sub} {a} — 이 저장소에서는 {where} 아래 경로를 적은 git add · commit만 됩니다(다른 변경이 섞이지 않게)."
            else:
                paths.append(a)
            i += 1
        if sub == "add" and not paths:
            return f"git add — 경로를 적어야 합니다({where} 아래 파일)."
        for p in paths:
            if p in (".", "*", ":/") or p.startswith(":") or "$" in p:
                return f"git {sub} {p} — {where} 아래 경로를 적은 것만 됩니다(git add -A · . 는 막습니다)."
            if not self._under(_resolve(p, target), other, subs):
                return f"git {sub} {p} — {where} 밖입니다. 이 저장소에서는 {where} 아래만 add · commit합니다."
        if sub == "commit" and not paths:
            staged = self._staged(other)
            if staged is None:
                return "git commit — 스테이지에 무엇이 올라 있는지 확인하지 못해 막았습니다. 경로를 적어 git commit -- <경로>로 하세요."
            bad = [f for f in staged if not self._under(os.path.join(other, f), other, subs)]
            if bad:
                return (f"git commit — 이 저장소 스테이지에 {where} 밖의 변경이 올라 있습니다({', '.join(bad[:3])}"
                        f"{' …' if len(bad) > 3 else ''}). 다른 세션의 변경일 수 있어 섞지 않습니다 — git commit -- <경로>로 경로를 적으세요.")
        return None

    @staticmethod
    def _staged(repo: str) -> list[str] | None:
        """그 저장소 스테이지에 올라 있는 파일(저장소 기준 경로). 못 읽으면 None."""
        import subprocess
        try:
            r = subprocess.run(["git", "-C", repo, "diff", "--cached", "--name-only", "-z"],
                               capture_output=True, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        return [f for f in r.stdout.decode("utf-8", "replace").split("\0") if f]

    def _git_writes(self, project: str, cmd: str, base: str, own: str, scratch: str | None, manager: bool = False):
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
                        why = self._git_seg(project, seg, cur, own, scratch, manager)
                        if why:
                            yield why
                seg = []

    def _git_seg(self, project: str, seg: list[str], cur: str, own: str, scratch: str | None,
                 manager: bool = False) -> str | None:
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
            return self._why(target, "git " + sub)
        other = self._other(target, own, scratch)
        if not other:
            return None
        subs = self._subs(project, other)
        if subs and sub in ("add", "commit"):
            return self._docs_git(sub, rest, target, other, subs)
        if sub == "push" and manager:
            psubs = self._subs(project, other, self.manager_push)
            if psubs:
                return self._manager_docs_push(rest, other, psubs)
        return self._why(other, "git " + sub)

    # ── 관리자 세션의 docs 전용 push(11-10 사용자) ──────────────────
    # 관리자 세션에만, [repo_scope.manager_push]에 적은 저장소의 원본에서, origin보다 앞선 커밋이 전부 그 경로만 건드렸을 때.
    # 모양은 git push [origin] [main]만(-q · -v 정도). 강제 · 삭제 · 미러 · 태그 · 다른 원격 · 다른 브랜치 · refspec은 막는다.
    _PUSH_OK = {"-q", "--quiet", "-v", "--verbose"}
    REMOTE, BRANCH = "origin", "main"
    LS_REMOTE_TIMEOUT = 10.0

    def _manager_docs_push(self, rest: list[str], other: str, subs: list[str]) -> str | None:
        where = " · ".join(subs)
        name = os.path.basename(other)
        head = f"git push({name}) — "
        pos: list[str] = []
        for a in _strip_redir(rest):
            if a.startswith("-"):
                if a not in self._PUSH_OK:
                    return head + f"{a}는 쓸 수 없습니다. 관리자 push는 git push [origin] [main]만 됩니다(강제 · 삭제 · 태그 · 미러 막음)."
            else:
                pos.append(a)
        if len(pos) > 2 or (pos and pos[0] != self.REMOTE) or (len(pos) == 2 and pos[1] != self.BRANCH):
            return head + f"'{' '.join(pos)}' — 관리자 push는 git push [origin] [main]만 됩니다(다른 원격 · 브랜치 · refspec 막음)."
        # 원격 설정이 push를 바꾸지 않는지(미러 · push refspec)
        if _git(other, "config", "--get", f"remote.{self.REMOTE}.mirror") not in (None, "", "false"):
            return head + f"remote.{self.REMOTE}.mirror가 켜져 있어 막았습니다."
        if _git(other, "config", "--get-all", f"remote.{self.REMOTE}.push"):
            return head + f"remote.{self.REMOTE}.push 설정이 있어 막았습니다(무엇이 올라갈지 바뀝니다)."
        if len(pos) < 2:   # 브랜치를 안 적으면 지금 브랜치가 main이고 push 대상이 origin/main이어야 한다
            if _git(other, "symbolic-ref", "--short", "HEAD") != self.BRANCH:
                return head + f"지금 브랜치가 {self.BRANCH}가 아닙니다 — git push origin main으로 적으세요."
            if (_git(other, "config", "--get", "push.default") or "simple") == "matching":
                return head + "push.default=matching이라 다른 브랜치도 올라갈 수 있어 막았습니다 — git push origin main으로 적으세요."
            if not pos and _git(other, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}") != f"{self.REMOTE}/{self.BRANCH}":
                return head + f"push 대상이 {self.REMOTE}/{self.BRANCH}가 아닙니다 — git push origin main으로 적으세요."
        # 원격 머리(네트워크 — 시간 제한)
        out = _git(other, "ls-remote", self.REMOTE, f"refs/heads/{self.BRANCH}", timeout=self.LS_REMOTE_TIMEOUT)
        if out is None:
            return head + f"원격({self.REMOTE})의 {self.BRANCH}를 읽지 못해 막았습니다(네트워크 · 인증 · {self.LS_REMOTE_TIMEOUT:.0f}초 넘김). 앞선 커밋이 docs만인지 확인할 수 없습니다."
        remote = out.split()[0] if out.split() else ""
        if not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", remote):
            return head + f"원격({self.REMOTE})에 {self.BRANCH}가 없습니다 — 관리자 push는 이미 있는 {self.BRANCH}에 앞선 커밋만 올립니다."
        local = _git(other, "rev-parse", "--verify", "-q", f"refs/heads/{self.BRANCH}^{{commit}}")
        if not local:
            return head + f"이 저장소에 {self.BRANCH} 브랜치가 없습니다."
        if _git(other, "cat-file", "-e", f"{remote}^{{commit}}") is None:
            return head + f"원격 {self.BRANCH}({remote[:8]})를 이 저장소가 갖고 있지 않습니다 — 뒤처졌거나 갈라졌습니다. 그 저장소 세션이 먼저 맞춥니다."
        if _git(other, "merge-base", "--is-ancestor", remote, local) is None:
            return head + f"로컬 {self.BRANCH}가 원격({remote[:8]})보다 앞선 상태가 아닙니다(뒤처짐 · 갈라짐)."
        ahead = _git(other, "rev-list", f"{remote}..{local}")
        if ahead is None:
            return head + "앞선 커밋을 읽지 못해 막았습니다."
        commits = ahead.split()
        if not commits:
            return None   # 올릴 것이 없다
        merges = _git(other, "rev-list", "--min-parents=2", f"{remote}..{local}")
        if merges is None or merges.split():
            return head + f"앞선 커밋에 머지 커밋이 있습니다({', '.join(m[:8] for m in (merges or '').split()[:3])}) — 관리자 push는 머지 없는 docs 커밋만 올립니다."
        bad: list[str] = []
        for c in commits:
            files = _git(other, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", c)
            if files is None:
                return head + f"커밋 {c[:8]}의 파일을 읽지 못해 막았습니다."
            for f in (x for x in files.split("\0") if x):
                if not self._under(os.path.join(other, f), other, subs):
                    bad.append(f"{c[:8]} {f}")
        if bad:
            return (head + f"앞선 커밋 {len(commits)}개 중 {where} 밖을 건드린 것이 있어 막았습니다: "
                    + ", ".join(bad[:5]) + (f" 외 {len(bad) - 5}개" if len(bad) > 5 else "")
                    + ". docs 밖은 그 저장소 세션이 올립니다.")
        return None

    @staticmethod
    def _why(other: str, what: str) -> str:
        return (f"다른 저장소 쓰기 막힘 — 이 세션은 다른 저장소({os.path.basename(other)})를 읽기만 합니다({what}). "
                "고칠 것은 그 저장소의 세션에 맡기거나(세션 간 메시지) 사용자에게 요청하세요. "
                "상태만 볼 때는 git ls-remote, 손볼 시험은 /tmp · 스크래치 복제본에서 합니다.")
