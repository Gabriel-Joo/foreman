"""역할 규칙을 글이 아니라 권한으로(11-11 C 2물결 「다섯」, log/coder_c_wave2_20261111.md · 기록만으로 두기 log/inspect_roleguard_20261114.md).

「worktree는 커밋만 · push는 관리자」 「파일은 Edit · Write로만」이 CLAUDE.md 글로만 있어 계속 샜다(11-10 worktree 코더에게
push 지시서, 11-11 세션이 sed · heredoc으로 파일을 두 번 고침). PreToolUse에서 역할마다 막을 것을 본다 —
pgrep_guard · reposcope와 같은 자리(bridge/approvals.py).

규칙(config/roles.toml [roles.rules]에서 하나씩 끌 수 있다):
  worktree-push   worktree 세션(역할 무관)의 `git push` — push는 관리자가 합친 뒤 원본 폴더에서
  bash-file-edit  Bash로 저장소 파일 고치기 — `sed -i` · `perl -i` · `>`/`>>` 리디렉션(heredoc `cat >> f <<EOF` 포함) · `tee`
                  /tmp · 세션 스크래치 · git 저장소 밖(~/.claude 등)은 막지 않는다. 명령 안의 `cd`를 따라간다.
                  해석기(python -c 등) 안의 쓰기는 보지 않는다 — 데이터 만들기와 소스 고치기를 가를 수 없다
  manager-code    관리자(원본 폴더)가 코드 고치기 — config/*.toml · log/ · README.md 밖을 Edit · Write
                  (CLAUDE.md 「관리자는 코드를 고치지 않는다」. 합친 뒤 깨진 것 몇 줄 · 주석은 관찰에 걸릴 수 있다 — 그래서 처음엔 관찰)
  scribe-code     서기가 코드(bridge/ · tests/ · migrations/ · tools/) 고치기
  inspector-write 조사(inspector)가 저장소 파일 고치기(11-15 사용자 — 「조사가 log를 쓸 수 있게」). 조사는 전에 CC plan 모드(읽기 전용)로
                  떠서 결과 log 하나에도 계획 승인이 한 번 필요했다 — 그래서 관리자가 조사를 피하고 코더로 띄웠다. 이제 보통 모드로 뜨고 여기서 막는다:
                  Edit · Write는 inspector_allow(log/*) 안의 새 파일 · 이 세션이 만든 파일 · git이 아직 모르는 파일만.
                  Bash는 저장소 파일 쓰기(리디렉션 · sed -i · tee · rm · mv · cp · touch …), git push, 저장소를 바꾸는 git(checkout · reset …),
                  log 밖 `git add`, 스테이지에 log 밖 파일이 섞인 `git commit`을 막는다. 저장소 밖(스크래치 · /tmp)은 자유
모드(`[roles] mode`):
  observe  막지 않고 기록만 — 그 호출의 approval_req 이벤트 payload에 role_rule · role_reason(지난 호출로 헛거부를 센다)
  enforce  거부 + 무엇이 왜 막혔는지 · 어떻게 하면 되는지(세션이 읽는다 — 조용히 실패하지 않게)
  off      보지 않음
  `[roles] enforce`에 적은 규칙은 mode가 observe여도 막는다(11-15 — 조사 규칙 하나만. 다른 규칙은 사용자 결정으로 관찰 그대로)
판정 중 예외는 막지 않고(세션을 묶지 않게) 로그 error + 텔레그램 한 번(시간마다) — `on_error`.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bridge import hookmiss
from bridge.reposcope import _strip_redir

CONFIG = Path(__file__).resolve().parent.parent / "config" / "roles.toml"
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
FREE = ("/tmp/", "/dev/", "/proc/")
RULES = ("worktree-push", "bash-file-edit", "manager-code", "scribe-code", "inspector-write")
SEPS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&", "\n"}
# 조사(inspector)가 Bash로 못 하는 것(11-15). 파일을 바꾸는 명령 — 인자가 저장소 안이면 막는다(cp · ln · install은 마지막 인자 = 쓰는 곳)
FILE_CMDS = {"rm", "rmdir", "unlink", "mv", "cp", "ln", "install", "touch", "mkdir", "truncate", "chmod", "chown", "patch"}
DEST_LAST = {"cp", "ln", "install", "mv"}
# 저장소(작업 트리 · 브랜치 · 원격)를 바꾸는 git. add · commit · branch · tag · stash · worktree는 따로 본다
GIT_DENY = {"push", "checkout", "switch", "restore", "reset", "rebase", "merge", "cherry-pick", "revert", "rm", "mv", "apply",
            "am", "clean", "pull", "init", "clone", "submodule", "update-index", "filter-branch", "notes", "gc", "prune", "replace"}
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
COMMIT_VALUE_OPTS = {"-m", "-F", "-c", "-C", "-t", "--message", "--file", "--author", "--date", "--fixup", "--squash",
                     "--template", "--cleanup", "--reuse-message", "--reedit-message", "--trailer"}


@dataclass
class RolesConfig:
    mode: str = "observe"
    projects: list[str] = field(default_factory=lambda: ["foreman"])
    rules: dict[str, bool] = field(default_factory=lambda: {r: True for r in RULES})
    manager_allow: list[str] = field(default_factory=lambda: ["config/*.toml", "log/*", "README.md"])
    scribe_deny: list[str] = field(default_factory=lambda: ["bridge/*", "tests/*", "migrations/*", "tools/*"])
    inspector_allow: list[str] = field(default_factory=lambda: ["log/*"])
    enforce: list[str] = field(default_factory=list)     # mode가 observe여도 막는 규칙(11-15 조사 규칙)
    error: str | None = None

    @classmethod
    def load(cls, path: Path = CONFIG) -> "RolesConfig":
        if not path.exists():
            return cls(mode="off")
        try:
            raw = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as e:
            return cls(mode="off", error=f"{path.name}을 읽지 못했습니다: {e}")
        r = raw.get("roles") or {}
        mode = str(r.get("mode", "observe"))
        if mode not in ("off", "observe", "enforce"):
            return cls(mode="off", error=f"[roles] mode는 off · observe · enforce 중 하나입니다(받은 값 {mode})")
        c = cls(mode=mode, projects=[str(p) for p in r.get("projects", ["foreman"])])
        c.rules.update({k: bool(v) for k, v in (r.get("rules") or {}).items() if k in RULES})
        if "manager_allow" in r:
            c.manager_allow = [str(x) for x in r["manager_allow"]]
        if "scribe_deny" in r:
            c.scribe_deny = [str(x) for x in r["scribe_deny"]]
        if "inspector_allow" in r:
            c.inspector_allow = [str(x) for x in r["inspector_allow"]]
        bad = [str(x) for x in r.get("enforce", []) if x not in RULES]
        if bad:
            return cls(mode="off", error=f"[roles] enforce에 모르는 규칙이 있습니다: {', '.join(bad)}")
        c.enforce = [str(x) for x in r.get("enforce", [])]
        return c


@dataclass
class Hit:
    rule: str
    reason: str
    key: str = ""             # [roles.rules]의 규칙 키(inspector-write 등)
    enforce: bool = False     # 막는가(mode enforce거나 [roles] enforce에 든 규칙) — check가 채운다


def _top(path: str) -> str | None:
    p = Path(path)
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return str(d)
    return None


def in_worktree(cwd: str | None) -> bool:
    return bool(cwd) and "/.worktrees/" in os.path.realpath(cwd or "") + "/"


def _match(rel: str, pats: list[str]) -> bool:
    # fnmatch의 *는 /도 넘는다 — "log/*"는 log 아래 모두
    return any(fnmatch.fnmatch(rel, p) for p in pats)


def _strip_quotes(s: str) -> str:
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'', " _q_ ", s, flags=re.S)


_HD_TAG = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")


def _heredoc_free(cmd: str) -> list[str]:
    """줄마다 나누되 heredoc 본문은 뺀다. 한 줄에 heredoc이 여럿이어도(`<<'EOF' || … <<'EOF2'`) 차례로 따라간다."""
    out: list[str] = []
    ends: list[str] = []
    for line in cmd.splitlines():
        if ends:
            if line.strip() == ends[0]:
                ends.pop(0)
            continue
        out.append(line)
        ends = [m.group(2) for m in _HD_TAG.finditer(line)]
    return out


def _shell_tokens(s: str) -> list[str] | None:
    """셸 토큰 — 줄바꿈도 조각 나눔(따옴표 안의 줄바꿈은 글자 그대로). 따옴표가 안 닫히면 None."""
    import shlex
    try:
        lx = shlex.shlex(s, posix=True, punctuation_chars="();<>|&\n")
        lx.whitespace = " \t\r"
        lx.whitespace_split = True
        out = []
        for t in lx:
            if "\n" in t and set(t) <= set("();<>|&\n"):       # 「;\n」 「&&\n」처럼 붙은 기호는 나눈다
                out.extend(p for p in re.split(r"(\n)", t) if p)
            else:
                out.append(t)
        return out
    except ValueError:
        return None


class RoleGuard:
    def __init__(self, cfg: RolesConfig, on_error: Callable[[str], None] | None = None, free: tuple[str, ...] = FREE) -> None:
        self.cfg = cfg
        self.free = free
        self.on_error = on_error
        self._err_hour: int | None = None
        self._roles: dict[str, tuple[float, str | None]] = {}     # cc 세션 → (읽은 때, 역할)
        self.seen: list[dict[str, Any]] = []                      # 최근 걸린 것(관찰 · 막기) — 200개
        self._made: set[tuple[str, str]] = set()                  # (cc 세션, 경로) — 조사가 Write로 새로 만든 log(그 뒤 고치기 허용)

    @property
    def active(self) -> bool:
        return self.cfg.mode in ("observe", "enforce")

    def enforces(self, rule: str, project: str | None) -> bool:
        """이 프로젝트에서 이 규칙이 실제로 막는가 — 교장 계획이 조사를 읽기 전용(plan 모드)으로 띄울지 정할 때 본다(11-15)."""
        return (self.active and self._on(rule) and (not self.cfg.projects or project in self.cfg.projects)
                and (self.cfg.mode == "enforce" or rule in self.cfg.enforce))

    # ── 역할 읽기(PreToolUse마다 DB를 치지 않게 60초 기억) ──
    async def role_of(self, engine: Any, cc: str | None) -> str | None:
        if not cc:
            return None
        hit = self._roles.get(cc)
        now = time.monotonic()
        if hit and now - hit[0] < 60:
            return hit[1]
        from sqlalchemy import text
        async with engine.connect() as c:
            r = (await c.execute(text("SELECT role FROM character_session WHERE cc_session_id = :s ORDER BY id DESC LIMIT 1"),
                                 {"s": cc})).first()
        role = r[0] if r else None
        self._roles[cc] = (now, role)
        if len(self._roles) > 2000:
            self._roles.clear()
        return role

    # ── 판정 ──
    def check(self, project: str | None, role: str | None, cwd: str | None, tool: str, inp: dict[str, Any],
              scratch: str | None = None, session: str | None = None) -> Hit | None:
        if not self.active or (self.cfg.projects and project not in self.cfg.projects):
            return None
        try:
            h = self._check(role, cwd, tool, inp, scratch, session)
        except Exception as e:  # noqa: BLE001 — 판정 실패가 세션을 묶지 않게: 통과시키고 알린다
            self._fail(f"역할 권한 판정 실패({tool}): {type(e).__name__}: {str(e)[:200]}")
            hookmiss.record("역할판정예외", type(e).__name__, session, tool)   # 알림은 시간마다 한 번, 기록은 매번(11-15)
            return None
        if h:
            h.enforce = self.cfg.mode == "enforce" or h.key in self.cfg.enforce
            self.seen.append({"at": time.time(), "project": project, "role": role, "tool": tool, "rule": h.rule,
                              "mode": "enforce" if h.enforce else self.cfg.mode})
            del self.seen[:-200]
        return h

    def _fail(self, why: str) -> None:
        h = int(time.time() // 3600)
        if self.on_error and h != self._err_hour:
            self._err_hour = h
            try:
                self.on_error(why)
            except Exception:  # noqa: BLE001
                pass

    def _on(self, rule: str) -> bool:
        return self.cfg.rules.get(rule, False)

    def _check(self, role: str | None, cwd: str | None, tool: str, inp: dict[str, Any], scratch: str | None,
               session: str | None = None) -> Hit | None:
        wt = in_worktree(cwd)
        if role == "inspector" and self._on("inspector-write"):
            h = self._inspector(cwd, tool, inp, scratch, session)
            if h:
                return h
        if tool in EDIT_TOOLS:
            path = inp.get("file_path") or inp.get("notebook_path")
            if not isinstance(path, str) or not path:
                return None
            full = os.path.realpath(os.path.join(cwd or "/", os.path.expanduser(path)))
            top = _top(full)
            if not top or (cwd and _top(os.path.realpath(cwd)) != top):
                return None          # 저장소 밖 · 다른 저장소(그것은 reposcope 몫)
            rel = os.path.relpath(full, top)
            if role == "manager" and not wt and self._on("manager-code") and not _match(rel, self.cfg.manager_allow):
                return Hit("역할-관리자코드", f"관리자는 코드를 고치지 않습니다 — {rel}. 관리자가 직접 고쳐도 되는 것은 "
                           f"{', '.join(self.cfg.manager_allow)}입니다. 코드는 worktree 코더에게 맡깁니다(교장 경로로 세션 띄우기). "
                           "합친 뒤 깨진 것을 바로 막는 몇 줄이면 사람에게 허락을 받습니다", "manager-code")
            if role == "scribe" and self._on("scribe-code") and _match(rel, self.cfg.scribe_deny):
                return Hit("역할-서기코드", f"서기는 코드를 고치지 않습니다 — {rel}. 문서(README · docs · log · portfolio)만 고칩니다. "
                           "코드 고칠 것은 포스트잇이나 관리자에게 보냅니다", "scribe-code")
            return None
        if tool != "Bash":
            return None
        cmd = str(inp.get("command") or "")
        if self._on("worktree-push") and wt and re.search(r"\bgit\b[^;&|\n]*\spush\b", _strip_quotes("\n".join(_heredoc_free(cmd)))):
            return Hit("역할-worktree push", "worktree 세션은 커밋만 하고 push하지 않습니다 — 합치기는 관리자가 하고, push는 합친 뒤 "
                       "원본 폴더에서 관리자가 합니다. 커밋을 마치고 보고하면 합치기 카드가 생깁니다", "worktree-push")
        if self._on("bash-file-edit"):
            target = self._bash_write(cmd, cwd, scratch)
            if target:
                return Hit("역할-Bash파일고침", f"파일은 Edit · Write로 고칩니다 — Bash로 저장소 파일({target})을 고치려 했습니다"
                           "(sed -i · 리디렉션 · heredoc · tee). Edit · Write로 고치면 무엇을 바꿨는지 기록 · 승인 · 되돌리기가 "
                           "그대로 돕니다. 임시 파일은 /tmp나 세션 스크래치에 씁니다", "bash-file-edit")
        return None

    # ── 조사(inspector)는 자기 log만 쓴다(11-15 사용자) ──
    INSPECTOR_HOW = ("조사는 읽고 알아보는 일이라 저장소의 다른 파일은 고치지 않습니다. 결과는 log/ 아래 새 파일에 Write로 쓰고 "
                     "`git add log/<파일>` 뒤 `git commit -m`으로 커밋합니다. 고칠 것은 그 log와 보고에 적어 관리자에게 올립니다")

    def _deny_inspector(self, what: str) -> Hit:
        return Hit("역할-조사쓰기", f"조사 세션은 log 파일만 쓸 수 있습니다. {what}. {self.INSPECTOR_HOW}", "inspector-write")

    @staticmethod
    def _git(top: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", top, *args], capture_output=True, text=True, timeout=3)

    def _inspector(self, cwd: str | None, tool: str, inp: dict[str, Any], scratch: str | None, session: str | None) -> Hit | None:
        if tool in EDIT_TOOLS:
            path = inp.get("file_path") or inp.get("notebook_path")
            if not isinstance(path, str) or not path:
                return None
            full = os.path.realpath(os.path.join(cwd or "/", os.path.expanduser(path)))
            top = _top(full)
            if not top or (cwd and _top(os.path.realpath(cwd)) != top):
                return None          # 저장소 밖(스크래치 · /tmp · 메모리)은 자유, 다른 저장소는 reposcope 몫
            rel = os.path.relpath(full, top)
            if not _match(rel, self.cfg.inspector_allow):
                return self._deny_inspector(f"{rel}은(는) 고칠 수 없습니다")
            key = (session or "", full)
            if not os.path.exists(full):
                self._made.add(key)                       # 새 log — 이 세션이 만든 것으로 기억(이어서 Edit 허용)
                if len(self._made) > 5000:
                    self._made.clear()
                return None
            if key in self._made:
                return None
            # 브리지가 다시 떠 기억을 잃었어도: git이 아직 모르는 파일(커밋 전)이면 이 세션이 쓰던 것으로 본다
            if self._git(top, "ls-files", "--error-unmatch", "--", rel).returncode != 0:
                return None
            return self._deny_inspector(f"{rel}은(는) 이 세션이 만든 파일이 아닙니다. 다른 세션의 기록은 고치지 않고 새 파일에 씁니다")
        if tool != "Bash":
            return None
        for seg, base in self._segments(str(inp.get("command") or ""), cwd):
            if base is None:                 # `cd $X` 뒤 — 어디인지 모른다
                continue
            h = self._inspector_seg(seg, base, scratch)
            if h:
                return h
        return None

    def _inspector_seg(self, seg: list[str], base: str, scratch: str | None) -> Hit | None:
        rel = self._seg_write(seg, base, scratch)
        if rel:
            return self._deny_inspector(f"Bash로 저장소 파일({rel})을 쓸 수 없습니다. log도 Write로 씁니다")
        while seg and re.match(r"^\w+=", seg[0]):
            seg = seg[1:]
        if not seg:
            return None
        name = os.path.basename(seg[0])
        args = [a for a in _strip_redir(seg[1:])]
        if name in FILE_CMDS:
            pos = [a for a in args if not a.startswith("-")]
            for a in (pos[-1:] if name in DEST_LAST and name != "mv" else pos):
                r = self._in_repo(a, base, scratch)
                if r:
                    return self._deny_inspector(f"{name}로 저장소 파일({r})을 바꿀 수 없습니다")
            return None
        if name != "git":
            return None
        # git 앞 옵션(-C 경로 · -c 키=값 …)
        i = 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] == "-C" and i + 1 < len(args):
                base = os.path.realpath(os.path.join(base, os.path.expanduser(args[i + 1])))
            i += 2 if args[i] in GIT_VALUE_OPTS else 1
        if i >= len(args):
            return None
        sub, rest = args[i], args[i + 1:]
        top = _top(base)
        if not top:
            return None                      # 저장소 밖 git(스크래치에 만든 시험 저장소 등)
        flags = [a for a in rest if a.startswith("-")]
        pos = [a for a in rest if not a.startswith("-")]
        if sub == "restore" and any(f in ("--staged", "-S") for f in flags) and not any(f in ("--worktree", "-W") for f in flags):
            return None                      # 스테이지에서 내리기만 — 작업 트리는 그대로
        if sub in GIT_DENY:
            return self._deny_inspector(f"`git {sub}`은(는) 저장소를 바꿉니다" + (". push는 관리자가 합니다" if sub == "push" else ""))
        if sub == "stash" and pos[:1] not in (["list"], ["show"]):
            return self._deny_inspector("`git stash`는 작업 트리를 바꿉니다")
        if sub == "worktree" and pos[:1] != ["list"]:
            return self._deny_inspector("`git worktree`로 작업 자리를 만들거나 지울 수 없습니다")
        if sub == "tag" and (pos or any(f in ("-d", "--delete", "-a", "-s", "-f") for f in flags)):
            return self._deny_inspector("`git tag`로 태그를 만들거나 지울 수 없습니다")
        if sub == "branch" and (pos or any(f in ("-d", "-D", "-m", "-M", "-c", "-C", "-f", "--delete", "--move", "--copy", "--force",
                                                 "-u", "--set-upstream-to", "--unset-upstream") for f in flags)):
            return self._deny_inspector("`git branch`로 브랜치를 만들거나 바꿀 수 없습니다(보기만 됩니다)")
        if sub == "add":
            if any(f in ("-A", "--all", "-u", "--update") for f in flags) or not pos:
                return self._deny_inspector("`git add`는 log 파일 이름을 하나씩 적어야 합니다(-A, -u, . 은 안 됩니다)")
            for a in pos:
                r = self._repo_rel(a, base, top)
                if r is None or not _match(r, self.cfg.inspector_allow):
                    return self._deny_inspector(f"`git add`는 log 파일만 됩니다({r or a})")
            return None
        if sub == "commit":
            if any(f in ("-a", "--all", "-i", "--include", "-o", "--only", "-p", "--patch", "--interactive") or
                   (re.fullmatch(r"-[a-zA-Z]+", f) and "a" in f[1:] and f not in COMMIT_VALUE_OPTS) for f in flags):
                return self._deny_inspector("`git commit -a`처럼 log 밖 파일까지 담는 커밋은 안 됩니다")
            paths, skip = [], False
            for a in rest:
                if skip:
                    skip = False
                    continue
                if a in COMMIT_VALUE_OPTS or (re.fullmatch(r"-[a-zA-Z]*[mFcCt]", a) and a not in ("-a",)):
                    skip = True              # 다음 토큰은 값(-m 글 · -F 파일)
                    continue
                if a.startswith("-"):
                    continue
                paths.append(a)
            for a in paths:
                r = self._repo_rel(a, base, top)
                if r is None or not _match(r, self.cfg.inspector_allow):
                    return self._deny_inspector(f"`git commit`에 log 밖 경로({r or a})를 줄 수 없습니다")
            p = self._git(top, "diff", "--cached", "--name-only")
            if p.returncode != 0:
                return self._deny_inspector("스테이지를 읽지 못해 커밋할 수 없습니다. `git status`로 확인한 뒤 다시 합니다")
            staged = [x for x in p.stdout.splitlines() if x]
            outside = [x for x in staged if not _match(x, self.cfg.inspector_allow)]
            if outside:
                return self._deny_inspector(f"스테이지에 log 밖 파일({', '.join(outside[:3])})이 있습니다. "
                                            "`git restore --staged <파일>`로 내린 뒤 log 파일만 올려 커밋합니다")
        return None

    def _repo_rel(self, path: str, base: str, top: str) -> str | None:
        full = os.path.realpath(os.path.join(base, os.path.expanduser(path)))
        if full != top and not full.startswith(top.rstrip("/") + "/"):
            return None
        return os.path.relpath(full, top)

    # ── Bash로 저장소 파일 쓰기 ──
    def _in_repo(self, path: str, cwd: str | None, scratch: str | None) -> str | None:
        if not path or "$" in path or path.startswith("&") or "`" in path:
            return None
        full = os.path.realpath(os.path.join(cwd or "/", os.path.expanduser(path)))
        if (self.free and full.startswith(self.free)) or full.startswith("/dev/") or (scratch and full.startswith(os.path.realpath(scratch).rstrip("/") + "/")):
            return None
        if os.path.realpath(os.path.expanduser("~/.claude")) in full:
            return None
        top = _top(full if os.path.isdir(full) else os.path.dirname(full) or "/")
        if not top:
            return None
        return os.path.relpath(full, top)

    def _bash_write(self, cmd: str, cwd: str | None, scratch: str | None) -> str | None:
        """줄마다 토큰으로 나눠 조각(&& · ; · |)마다 본다. 앞 조각의 `cd X`를 따라간다(11-11 지난 7일 다시 돌림 —
        `cd /tmp/…/scratchpad && cat > x.sh`를 저장소 파일로 잘못 봤다). heredoc 본문(커밋 글 등)은 뺀다."""
        for seg, base in self._segments(cmd, cwd):
            rel = self._seg_write(seg, base, scratch)
            if rel:
                return rel
        # 해석기(python -c · python - <<EOF) 안의 쓰기는 보지 않는다 — 데이터를 만드는 스크립트와 소스 고치기를 글로 가를 수 없다
        # (11-11 지난 7일 다시 돌림: 걸린 것이 대부분 화면 시험용 JSON 만들기였다)
        return None

    @staticmethod
    def _segments(cmd: str, cwd: str | None) -> list[tuple[list[str], str | None]]:
        """명령을 조각(&& · ; · |)으로 — (토큰, 그 조각의 폴더). `cd` 조각은 폴더만 바꾸고 내지 않는다. `cd $X` 뒤 폴더는 None.
        따옴표가 안 닫힘 등으로 나눌 수 없으면 빈 목록(판정할 수 없다 — 막지 않는다)."""
        base = cwd
        body = re.sub(r"\\\n", " ", "\n".join(_heredoc_free(cmd)))    # 줄 이음(\)은 한 줄로
        toks = _shell_tokens(body)
        if toks is None:
            return []
        out: list[tuple[list[str], str | None]] = []
        seg: list[str] = []
        for t in [*toks, ";"]:
            if t not in SEPS:
                seg.append(t)
                continue
            if seg and seg[0] == "cd":
                nxt = seg[1] if len(seg) > 1 else "~"
                base = None if "$" in nxt else os.path.realpath(os.path.join(base or "/", os.path.expanduser(nxt)))
            elif seg:
                out.append((seg, base))
            seg = []
        return out

    def _seg_write(self, seg: list[str], base: str | None, scratch: str | None) -> str | None:
        if base is None:                     # `cd $X` 뒤 — 어디인지 모른다. 막지 않는다
            return None
        for i, t in enumerate(seg):
            if t in (">", ">>", ">|", "&>", "&>>") and i + 1 < len(seg):
                tgt = seg[i + 1]
                if tgt in ("/dev/null", "/dev/stderr", "/dev/stdout", "-") or tgt.isdigit() or tgt in SEPS:
                    continue
                rel = self._in_repo(tgt, base, scratch)
                if rel:
                    return rel
        if seg and os.path.basename(seg[0]) == "tee":
            for a in seg[1:]:
                if a.startswith("-") or a in (">", ">>"):
                    continue
                rel = self._in_repo(a, base, scratch)
                if rel:
                    return rel
        return self._inplace(seg, base, scratch)

    def _inplace(self, seg: list[str], cwd: str | None, scratch: str | None) -> str | None:
        while seg and re.match(r"^\w+=", seg[0]):        # 환경 변수 앞붙임
            seg = seg[1:]
        if not seg or os.path.basename(seg[0]) not in ("sed", "perl", "gsed"):
            return None
        args = _strip_redir(seg[1:])                  # `2>/dev/null`의 2 · 대상은 인자가 아니다
        if not any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") or (a.startswith("-") and not a.startswith("--")
                   and "i" in a[1:] and os.path.basename(seg[0]) == "perl") for a in args):
            return None
        pos, skip, script_seen = [], False, False
        explicit = any(a in ("-e", "-f", "--expression", "--file") for a in args)
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-e", "-f", "--expression", "--file"):
                skip = True
                continue
            if a.startswith("-"):
                continue
            if not explicit and not script_seen:
                script_seen = True           # 첫 위치 인자는 sed 스크립트
                continue
            pos.append(a)
        for p in pos:
            rel = self._in_repo(p, cwd, scratch)
            if rel:
                return rel
        return None
