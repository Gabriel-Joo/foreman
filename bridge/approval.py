"""승인 정책 — PreToolUse마다 allow / ask / pass를 판정한다(로드맵 5단계, 규칙은 config/approval.toml).

원칙: 위험한 것부터 막는다. allow는 확실한 것만. 위험한 명령 이름이 있는데 무엇을 할지 확정할 수 없으면(변수 ·
명령 치환 · eval) ask. 그 밖의 평범한 작업은 pass — CC(auto mode 분류기 · 사용자 설정)가 지금처럼 정한다.

판정은 메모리 안에서 끝난다(DB · 네트워크 없음) — 모든 도구 호출 앞에서 불리므로 빨라야 한다.
"""

import os
import re
import shlex
import subprocess
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

EDIT_TOOLS = ("Edit", "MultiEdit", "NotebookEdit", "Write")
SEP = {"&&", "||", ";", "|", "&", "\n", ";;", "|&"}
REDIRECT = re.compile(r"^(\d*>>?|&>>?|<<?<?|\d*<&|\d*>&)$")


@dataclass(frozen=True)
class Decision:
    verdict: str          # allow | ask | pass
    rule: str             # 걸린 규칙 이름(pass면 unmatched 등)
    reason: str           # 사람이 읽을 이유 — 로그 · 이벤트 · 텔레그램 · CC 승인 창


@dataclass
class ProjectPolicy:
    mode: str = "enforce"
    unmatched: str = "pass"
    remote_approval: bool = True
    wait_s: float = 600.0


@dataclass
class Policy:
    allow_tools: set[str] = field(default_factory=set)
    edit_in_worktree: set[str] = field(default_factory=set)
    git_readonly: set[str] = field(default_factory=set)
    filters: set[str] = field(default_factory=set)
    allow_cd: bool = True
    write_outside: set[str] = field(default_factory=set)
    ask_bash: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    ambiguous_verb: re.Pattern[str] | None = None
    sensitive: list[re.Pattern[str]] = field(default_factory=list)   # secret — 읽기 · 쓰기 모두
    protect: list[re.Pattern[str]] = field(default_factory=list)     # 쓰기 · 편집만
    secret_readers: set[str] = field(default_factory=set)            # Bash에서 비밀 파일을 찍거나 옮기는 명령
    cc_own: list[re.Pattern[str]] = field(default_factory=list)      # CC 자신의 계획 · 메모리 — 안쪽으로 친다
    defaults: ProjectPolicy = field(default_factory=ProjectPolicy)
    projects: dict[str, ProjectPolicy] = field(default_factory=dict)

    def for_project(self, name: str | None) -> ProjectPolicy:
        return self.projects.get(name or "", self.defaults)

    # ── 판정 ────────────────────────────────────────────────
    def decide(self, tool: str, tool_input: dict[str, Any], cwd: str | None, scratchpad: str | None,
               project: str | None) -> Decision:
        pp = self.for_project(project)
        d = self._decide(tool, tool_input or {}, cwd, scratchpad)
        if d is None:
            if pp.unmatched == "ask":
                return Decision("ask", "unmatched", f"규칙에 없는 {tool} — 이 프로젝트는 규칙에 없으면 묻는다")
            return Decision("pass", "unmatched", "규칙에 없음 — CC가 정한다")
        return d

    def _decide(self, tool: str, inp: dict[str, Any], cwd: str | None, scratchpad: str | None) -> Decision | None:
        if tool == "Bash":
            return self._bash(str(inp.get("command") or ""), cwd)
        path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        if isinstance(path, str) and path and (s := self._sensitive(path, cwd, self.sensitive)):
            return Decision("ask", "민감한-경로", f"{tool}: 비밀이 든 파일({s})")
        if tool in EDIT_TOOLS and isinstance(path, str) and path and (s := self._sensitive(path, cwd, self.protect)):
            return Decision("ask", "보호-설정파일", f"{tool}: 설정 파일 쓰기({s})")
        if tool in self.allow_tools:
            return Decision("allow", f"도구-{tool}", f"{tool}는 읽기 전용")
        if tool in EDIT_TOOLS and isinstance(path, str) and path:
            where = self._where(path, cwd, scratchpad)
            if where == "outside" and tool in self.write_outside:
                return Decision("ask", "작업트리-밖-쓰기", f"{tool}: 작업 트리 밖({_short(path)})")
            if where == "git-dir":
                return Decision("ask", "git-내부", f"{tool}: .git 안({_short(path)})")
            if where == "inside" and tool in self.edit_in_worktree:
                return Decision("allow", "작업트리-편집", f"{tool}: 작업 트리 안")
        return None

    def _bash(self, cmd: str, cwd: str | None) -> Decision | None:
        for name, pat in self.ask_bash:
            if (m := pat.search(cmd)):
                return Decision("ask", name, f"운영 명령: {_short(m.group(0).strip(), 60)}")
        if self.ambiguous_verb and (m := self.ambiguous_verb.search(cmd)):
            return Decision("ask", "애매한-운영명령", f"동사 자리가 변수 · 명령 치환({_short(m.group(0).strip(), 40)}) — 무엇을 할지 확정할 수 없다")
        for head, tok in _path_tokens(cmd):   # 경로 토큰마다(공백 뒤 .env도), heredoc 본문은 빼고
            if any(s.search(tok) for s in self.sensitive) and (head in self.secret_readers or "@" in tok):
                return Decision("ask", "민감한-경로", f"Bash: 비밀이 든 파일을 찍거나 옮긴다({head} {_short(tok, 50)})")
        if self._bash_all_readonly(cmd):
            return Decision("allow", "git-읽기", "git status · log · diff(읽기 전용)")
        return None

    def _bash_all_readonly(self, cmd: str) -> bool:
        if not cmd.strip() or "$(" in cmd or "`" in cmd or "<(" in cmd or ">(" in cmd or "<<" in cmd:
            return False
        try:
            lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError:
            return False  # 따옴표가 안 닫힘 등 — 확실하지 않다
        segs: list[list[str]] = [[]]
        seps: list[str] = []
        for t in toks:
            if t in SEP:
                seps.append(t)
                segs.append([])
            else:
                segs[-1].append(t)
        if any(not s for s in segs) or "&" in seps:
            return False
        saw_git = False
        for i, seg in enumerate(segs):
            after_pipe = i > 0 and seps[i - 1] in ("|", "|&")
            if any(REDIRECT.match(t) for t in seg):
                # > /dev/null · 2>&1 만 허용
                if not _only_null_redirects(seg):
                    return False
                seg = _strip_redirects(seg)
            if not seg:
                return False
            if "=" in seg[0] and not seg[0].startswith("-"):
                return False  # FOO=bar cmd — 환경변수 앞붙임
            if seg[0] == "cd" and self.allow_cd and len(seg) <= 2 and not after_pipe:
                continue
            if seg[0] == "git" and not after_pipe and self._git_ok(seg):
                saw_git = True
                continue
            if after_pipe and seg[0] in self.filters:
                continue
            return False
        return saw_git

    def _git_ok(self, seg: list[str]) -> bool:
        i = 1
        while i < len(seg) and seg[i].startswith("-"):
            if seg[i] in ("-C",) and i + 1 < len(seg):
                i += 2
                continue
            if seg[i] in ("--no-pager", "--no-optional-locks"):
                i += 1
                continue
            return False  # -c(설정 주입) · --git-dir 등 — 확실하지 않다
        if i >= len(seg) or seg[i] not in self.git_readonly:
            return False
        bad = ("--output", "--ext-diff", "--textconv", "--exec", "-o")
        return not any(t == b or t.startswith(b + "=") for t in seg[i + 1:] for b in bad)

    def _sensitive(self, path: str, cwd: str | None, pats: list[re.Pattern[str]]) -> str | None:
        p = _abs(path, cwd)
        for s in pats:
            if s.search(p):
                return _short(p)
        return None

    def _where(self, path: str, cwd: str | None, scratchpad: str | None) -> str:
        p = _abs(path, cwd)
        if scratchpad and _within(p, os.path.realpath(scratchpad)):
            return "inside"   # CC가 준 세션 임시 폴더
        home_rel = "~" + p[len(os.path.expanduser("~")):] if p.startswith(os.path.expanduser("~") + "/") else p
        if any(r.search(home_rel) for r in self.cc_own):
            return "inside"   # CC 자신의 계획 · 메모리 파일
        root = worktree_root(cwd) if cwd else None
        if root is None:
            return "outside"
        if _within(p, os.path.join(root, ".git")):
            return "git-dir"
        return "inside" if _within(p, root) else "outside"


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", re.S)


def _path_tokens(cmd: str) -> list[tuple[str, str]]:
    """heredoc 본문을 뺀 명령에서 (그 조각의 첫 명령 이름, 경로처럼 생긴 토큰)들.
    경로처럼 생긴 것 = / · . · ~ 로 시작하거나 / 가 든 것. @파일(curl -d @x)도 경로로 본다."""
    body = HEREDOC.sub(" ", cmd)
    out = []
    for seg in re.split(r"&&|\|\||[;|\n]", body):
        words = [w for w in re.split(r"[\s'\"=<>()]+", seg) if w]
        words = [w for w in words if not re.fullmatch(r"\w+=.*", w)] or words   # FOO=bar 앞붙임 건너뜀
        head = os.path.basename(words[0]) if words else ""
        if head in ("sudo", "env", "nohup", "time") and len(words) > 1:
            head = os.path.basename(words[1])
        for w in words[1:]:
            t = w[1:] if w.startswith("@") else w
            if t and (t[0] in "/.~" or "/" in t):
                out.append((head, os.path.expanduser(t)))
    return out


def _abs(path: str, cwd: str | None) -> str:
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd or "/", p)
    # 아직 없는 파일이면 부모를 풀어 심볼릭 링크를 따라간다
    head, tail = os.path.split(os.path.normpath(p))
    return os.path.join(os.path.realpath(head), tail)


def _within(p: str, root: str) -> bool:
    root = root.rstrip("/")
    return p == root or p.startswith(root + "/")


def _short(s: str, n: int = 80) -> str:
    s = s.replace(os.path.expanduser("~"), "~")
    return s if len(s) <= n else s[: n - 1] + "…"


def _only_null_redirects(seg: list[str]) -> bool:
    for i, t in enumerate(seg):
        if REDIRECT.match(t):
            nxt = seg[i + 1] if i + 1 < len(seg) else ""
            if t in ("2>&1", ">&2", "1>&2") or (t in (">", "2>", "&>", "1>") and nxt == "/dev/null"):
                continue
            if t.endswith(">&") and nxt.isdigit():
                continue
            return False
    return True


def _strip_redirects(seg: list[str]) -> list[str]:
    out, skip = [], False
    for t in seg:
        if skip:
            skip = False
            continue
        if REDIRECT.match(t):
            skip = not t.endswith("&1") and not t.endswith("&2")
            continue
        out.append(t)
    return out


@lru_cache(maxsize=256)
def worktree_root(cwd: str) -> str | None:
    """세션 cwd의 git 최상위(= 작업 트리). git 밖이면 None — 그러면 어떤 쓰기도 '밖'이다."""
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def load_policy(path: str | Path) -> Policy:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    a, k = raw.get("allow", {}), raw.get("ask", {})
    amb = k.get("ambiguous", {})

    def pp(d: dict[str, Any], base: ProjectPolicy) -> ProjectPolicy:
        return ProjectPolicy(d.get("mode", base.mode), d.get("unmatched", base.unmatched),
                             d.get("remote_approval", base.remote_approval), float(d.get("wait_s", base.wait_s)))

    pol = Policy(
        allow_tools=set(a.get("tools", [])), edit_in_worktree=set(a.get("edit_in_worktree", [])),
        git_readonly=set(a.get("bash_git_readonly", [])), filters=set(a.get("bash_filters", [])),
        allow_cd=a.get("bash_cd", True), write_outside=set(k.get("write_outside_worktree", [])),
        ask_bash=[(name, re.compile(rx)) for name, rx in k.get("bash", {}).items()],
        ambiguous_verb=re.compile(amb["verb_re"]) if amb.get("verb_re") else None,
        sensitive=[re.compile(rx) for rx in raw.get("sensitive", {}).get("secret", [])],
        protect=[re.compile(rx) for rx in raw.get("sensitive", {}).get("protect", [])],
        secret_readers=set(raw.get("sensitive", {}).get("bash_secret_readers", [])),
        cc_own=[re.compile(rx) for rx in a.get("cc_own_paths", [])],
    )
    pol.defaults = pp(raw.get("defaults", {}), ProjectPolicy())
    for name, d in raw.get("projects", {}).items():
        pol.projects[name] = pp(d, pol.defaults)
    for m in [pol.defaults, *pol.projects.values()]:
        if m.mode not in ("enforce", "observe") or m.unmatched not in ("pass", "ask"):
            raise ValueError(f"approval.toml: mode는 enforce/observe, unmatched는 pass/ask — {m}")
    return pol
