"""승인 정책 — PreToolUse마다 allow / ask / pass를 판정한다(로드맵 5단계, 규칙은 config/approval.toml).

원칙(2026-11-02 사용자 결정): **되돌릴 수 없는 것만 ask, 되돌릴 수 있는 것은 allow.** 애매하면 ask
(위험한 명령의 동사가 변수 · 명령 치환이거나, 지울 경로에 변수가 있으면). 그 밖의 평범한 작업은 pass —
CC(auto mode 분류기 · 사용자 설정)가 지금처럼 정한다.

"위험한 명령을 실행하는 것"과 "위험한 명령을 글자로 쓰는 것"을 가른다:
- 파일에 쓰기만 하는 heredoc(cat > f <<EOF, tee f <<EOF)의 본문은 검사하지 않는다 — 실행되지 않는다.
  해석기로 들어가는 heredoc(bash <<EOF, python - <<EOF)은 검사한다 — 실행된다
- 대신 **스크립트를 실행할 때**(bash x.sh, sh x.sh, source x, ./x.sh) 그 파일 내용을 읽어 검사한다 — heredoc이든
  Write 도구든 파일에 숨긴 위험 명령은 실행되는 순간 잡힌다. bash -c '…' · vagrant ssh … -c '…'는 안쪽으로
- 규칙 파일(config/approval.toml 등)은 [sensitive] protect — 쓰기 자체가 "안전 규칙 변경"이라 ask

판정은 메모리 안에서 끝난다(스크립트 파일 읽기 제외, 256KB까지) — 모든 도구 호출 앞에서 불리므로 빨라야 한다.
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
SHELLS = ("bash", "sh", "zsh", "dash")
SCRIPT_MAX = 256 * 1024
# heredoc: <<EOF · <<'EOF' · <<-"EOF" … 본문 … EOF. 여는 줄(앞부분 포함)을 함께 잡아 무엇이 받는지 본다
HEREDOC = re.compile(r"(?P<line>[^\n]*?)<<-?\s*(['\"]?)(?P<tag>\w+)\2(?P<rest>[^\n]*)\n(?P<body>.*?)\n[ \t]*(?P=tag)\b", re.S)


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
    edit: set[str] = field(default_factory=set)
    git_readonly: set[str] = field(default_factory=set)
    filters: set[str] = field(default_factory=set)
    allow_cd: bool = True
    bash_ops: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    delete_outside: bool = True
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
            return self._bash(str(inp.get("command") or ""), cwd, scratchpad)
        path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        if isinstance(path, str) and path and (s := self._match(path, cwd, self.sensitive)):
            return Decision("ask", "민감한-경로", f"{tool}: 비밀이 든 파일({s})")
        if tool in EDIT_TOOLS and isinstance(path, str) and path and (s := self._match(path, cwd, self.protect)):
            return Decision("ask", "보호-설정파일", f"{tool}: 안전 규칙 · 설정 파일 쓰기({s})")
        if tool in self.allow_tools:
            return Decision("allow", f"도구-{tool}", f"{tool}는 읽기 전용")
        if tool in EDIT_TOOLS and isinstance(path, str) and path:
            if self._where(path, cwd, scratchpad) == "git-dir":
                return Decision("ask", "git-내부", f"{tool}: .git 안({_short(path)})")
            if tool in self.edit:
                return Decision("allow", "편집", f"{tool}: 덮어쓴 파일은 되돌릴 수 있다")
        return None

    def _bash(self, cmd: str, cwd: str | None, scratchpad: str | None, depth: int = 0) -> Decision | None:
        scan, written = _strip_file_heredocs(cmd)
        for target in written:                     # heredoc으로 파일을 쓴다 — 쓰는 곳이 보호 · 비밀 파일이면 ask
            if (s := self._match(target, cwd, self.protect + self.sensitive)):
                return Decision("ask", "보호-설정파일", f"Bash: 안전 규칙 · 설정 · 비밀 파일 쓰기({s})")
        if (d := self._ask_patterns(scan)):
            return d
        if self.ambiguous_verb and (m := self.ambiguous_verb.search(scan)):
            return Decision("ask", "애매한-운영명령", f"동사 자리가 변수 · 명령 치환({_short(m.group(0).strip(), 40)}) — 무엇을 할지 확정할 수 없다")
        for head, tok in _path_tokens(scan):   # 경로 토큰마다(공백 뒤 .env도)
            if any(s.search(tok) for s in self.sensitive) and (head in self.secret_readers or "@" in tok):
                return Decision("ask", "민감한-경로", f"Bash: 비밀이 든 파일을 찍거나 옮긴다 — 한번 찍히면 되돌릴 수 없다({head} {_short(tok, 50)})")
        segs = _segments(scan)
        if segs is None:
            if self.delete_outside and re.search(r"(^|[\s;&|(])rm\s", scan):
                return Decision("ask", "애매한-삭제", "rm이 있는데 명령을 나눌 수 없다(따옴표 등) — 무엇을 지울지 확정할 수 없다")
            return None
        if (d := self._segments_ask(segs, cwd, scratchpad, depth)):
            return d
        if any(x in scan for x in ("$(", "`", "<(", ">(")):
            return None                            # 명령 치환 — 무엇이 실행될지 확실하지 않다. allow하지 않는다
        if self._all_allowed(segs, depth):
            return Decision("allow", self._allow_rule(segs), "읽기 · 되돌릴 수 있는 명령")
        return None

    def _ask_patterns(self, text: str) -> Decision | None:
        for name, pat in self.ask_bash:
            if (m := pat.search(text)):
                return Decision("ask", name, f"되돌릴 수 없는 명령: {_short(m.group(0).strip(), 60)}")
        return None

    def _segments_ask(self, segs: list[tuple[str, list[str]]], cwd: str | None, scratchpad: str | None,
                      depth: int) -> Decision | None:
        here = cwd
        for _sep, seg in segs:
            words = _strip_redirects(seg) if any(REDIRECT.match(t) for t in seg) else seg
            for i, t in enumerate(seg):            # 리다이렉트로 보호 · 비밀 파일에 쓰기
                if t in (">", ">>", "&>", "1>", "2>") and i + 1 < len(seg) and \
                        (s := self._match(seg[i + 1], here, self.protect + self.sensitive)):
                    return Decision("ask", "보호-설정파일", f"Bash: 안전 규칙 · 설정 · 비밀 파일 쓰기({s})")
            words = [w for w in words if not re.fullmatch(r"[A-Za-z_]\w*=.*", w)] or words
            if not words:
                continue
            head = words[0]
            if head in ("sudo", "nohup", "time", "env") and len(words) > 1:
                words = words[1:]
                head = words[0]
            if head == "cd" and len(words) == 2:
                here = _abs(words[1], here) if not words[1].startswith("$") else here
                continue
            inner = _inner_command(words)
            if inner is not None and depth < 3:     # bash -c '…' · vagrant ssh … -c '…' — 안쪽 명령으로
                d = self._bash(inner, None if words[0] == "vagrant" else here, scratchpad, depth + 1)
                if d and d.verdict == "ask":
                    return d
                continue
            script = _script_path(words)
            if script and depth < 3:                # 스크립트 실행 — 파일 내용을 검사한다
                body = _read_script(script, here)
                if body is not None and (d := self._ask_patterns(body)):
                    return Decision("ask", d.rule, f"스크립트 {_short(script, 40)} 안: {d.reason}")
            if head == "rm" and self.delete_outside:
                for a in words[1:]:
                    if a.startswith("-"):
                        continue
                    if "$" in a or "`" in a:
                        return Decision("ask", "애매한-삭제", f"지울 경로에 변수가 있다({_short(a, 40)}) — 무엇을 지울지 확정할 수 없다")
                    if self._where(a, here, scratchpad) != "inside":
                        return Decision("ask", "작업트리-밖-삭제", f"작업 트리 밖 삭제({_short(_abs(a, here), 60)})")
        return None

    def _all_allowed(self, segs: list[tuple[str, list[str]]], depth: int) -> bool:
        if not segs:
            return False
        meaningful = False
        for sep, seg in segs:
            after_pipe = sep in ("|", "|&")
            if any(REDIRECT.match(t) for t in seg):
                if not _only_null_redirects(seg):
                    return False
                seg = _strip_redirects(seg)
            if not seg or (re.fullmatch(r"[A-Za-z_]\w*=.*", seg[0])):
                return False                          # 비었거나 환경변수 앞붙임
            if any(("$(" in t or "`" in t) for t in seg):
                return False
            if seg[0] == "cd" and self.allow_cd and len(seg) <= 2 and not after_pipe:
                continue
            if after_pipe and seg[0] in self.filters:
                continue
            if after_pipe:
                return False
            if seg[0] == "git" and self._git_ok(seg):
                meaningful = True
                continue
            inner = _inner_command(seg)
            if inner is not None and depth < 3:
                isegs = _segments(_strip_file_heredocs(inner)[0])
                if isegs is not None and self._all_allowed(isegs, depth + 1):
                    meaningful = True
                    continue
                return False
            joined = " ".join(seg)
            if any(p.search(joined) for _, p in self.bash_ops):
                meaningful = True
                continue
            return False
        return meaningful

    def _allow_rule(self, segs: list[tuple[str, list[str]]]) -> str:
        for _sep, seg in segs:
            j = " ".join(seg)
            for name, p in self.bash_ops:
                if p.search(j):
                    return name
            inner = _inner_command(seg)
            if inner:
                for name, p in self.bash_ops:
                    if p.search(inner.strip()):
                        return name
        return "git-읽기"

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

    def _match(self, path: str, cwd: str | None, pats: list[re.Pattern[str]]) -> str | None:
        p = _abs(path, cwd)
        for s in pats:
            if s.search(p):
                return _short(p)
        return None

    def _where(self, path: str, cwd: str | None, scratchpad: str | None) -> str:
        p = _abs(path, cwd)
        if scratchpad and _within(p, os.path.realpath(scratchpad)):
            return "inside"   # CC가 준 세션 임시 폴더
        home = os.path.expanduser("~")
        home_rel = "~" + p[len(home):] if p.startswith(home + "/") else p
        if any(r.search(home_rel) for r in self.cc_own):
            return "inside"   # CC 자신의 계획 · 메모리 파일
        root = worktree_root(cwd) if cwd else None
        if root is None:
            return "outside"
        if _within(p, os.path.join(root, ".git")):
            return "git-dir"
        return "inside" if _within(p, root) else "outside"


# ── 명령 나누기 ─────────────────────────────────────────────
def _strip_file_heredocs(cmd: str) -> tuple[str, list[str]]:
    """파일에 쓰기만 하는 heredoc(cat > f · cat >> f · tee [-a] f)의 본문을 빼고, 쓰는 파일 목록을 돌려준다.
    해석기로 들어가는 heredoc(bash · python …)이나 받는 쪽을 모르는 것은 그대로 둔다 — 실행되기 때문이다.
    .sh · .bash · .zsh로 쓰는 것도 본문을 남긴다(바로 실행될 가능성이 크다)."""
    written: list[str] = []

    def sub(m: re.Match[str]) -> str:
        line = m.group("line") + " " + m.group("rest")
        seg = re.split(r"&&|\|\||;", line)[-1] if "|" not in m.group("line").split("<<")[0][-3:] else line
        w = re.search(r"(?:^|[\s(])(cat|tee)\b(?P<args>[^|]*)$", seg.strip())
        if not w:
            return m.group(0)
        tgt = None
        if w.group(1) == "cat":
            r = re.search(r">>?\s*(['\"]?)([^\s'\"]+)\1", w.group("args"))
            tgt = r.group(2) if r else None
        else:
            r = re.search(r"(?:^|\s)(?:-a\s+)?(['\"]?)([^\s'\"-][^\s'\"]*)\1", w.group("args"))
            tgt = r.group(2) if r else None
        if not tgt or tgt in ("/dev/null",) or re.search(r"\.(sh|bash|zsh)$", tgt):
            return m.group(0)
        written.append(tgt)
        return m.group("line") + "<<" + m.group("tag") + m.group("rest") + "\n" + m.group("tag")

    return HEREDOC.sub(sub, cmd), written


def _segments(cmd: str) -> list[tuple[str, list[str]]] | None:
    """(앞 구분자, 낱말들) 목록. heredoc 본문은 뺀다(남은 본문은 _strip_file_heredocs가 걸러 낸 뒤의 것).
    따옴표가 안 닫히는 등 나눌 수 없으면 None."""
    body = HEREDOC.sub(lambda m: m.group("line") + "<<" + m.group("tag"), cmd)
    try:
        lex = shlex.shlex(body, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    out: list[tuple[str, list[str]]] = []
    sep, cur = "", []
    for t in toks:
        if t in SEP:
            if cur:
                out.append((sep, cur))
            sep, cur = t, []
        else:
            cur.append(t)
    if cur:
        out.append((sep, cur))
    if any(s == "&" for s, _ in out):
        return out  # 백그라운드 실행 — 나누기는 하되 allow는 _all_allowed가 거른다
    return out


def _inner_command(words: list[str]) -> str | None:
    """bash -c '…' · sh -c '…' · vagrant ssh <vm> -c '…' · ssh … 'cmd'는 안쪽 명령을 돌려준다."""
    if not words:
        return None
    if words[0] in SHELLS and "-c" in words:
        i = words.index("-c")
        return words[i + 1] if i + 1 < len(words) else None
    if words[0] == "vagrant" and len(words) > 1 and words[1] == "ssh" and "-c" in words:
        i = words.index("-c")
        return words[i + 1] if i + 1 < len(words) else None
    return None


def _script_path(words: list[str]) -> str | None:
    """스크립트 파일 실행이면 그 경로 — bash x.sh · sh x · source x · . x · ./x.sh · /path/x.sh"""
    if not words:
        return None
    if words[0] in SHELLS:
        args = [w for w in words[1:] if not w.startswith("-")]
        if "-c" in words or "-s" in words or not args:
            return None
        return args[0]
    if words[0] in ("source", ".") and len(words) > 1:
        return words[1]
    if words[0].startswith(("./", "/", "~/")) and not words[0].endswith(("/python", "/python3")) \
            and re.search(r"\.(sh|bash|zsh)$", words[0]):
        return words[0]
    return None


def _read_script(path: str, cwd: str | None) -> str | None:
    p = _abs(path, cwd)
    try:
        if os.path.getsize(p) > SCRIPT_MAX:
            return None
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


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
    """세션 cwd의 git 최상위(= 작업 트리). git 밖이면 None — 그러면 삭제는 모두 '밖'이다."""
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
    sens = raw.get("sensitive", {})

    def pp(d: dict[str, Any], base: ProjectPolicy) -> ProjectPolicy:
        return ProjectPolicy(d.get("mode", base.mode), d.get("unmatched", base.unmatched),
                             d.get("remote_approval", base.remote_approval), float(d.get("wait_s", base.wait_s)))

    pol = Policy(
        allow_tools=set(a.get("tools", [])), edit=set(a.get("edit", [])),
        git_readonly=set(a.get("bash_git_readonly", [])), filters=set(a.get("bash_filters", [])),
        allow_cd=a.get("bash_cd", True),
        bash_ops=[(name, re.compile(rx)) for name, rx in a.get("bash_ops", {}).items()],
        delete_outside=k.get("delete_outside_worktree", True),
        ask_bash=[(name, re.compile(rx)) for name, rx in k.get("bash", {}).items()],
        ambiguous_verb=re.compile(amb["verb_re"]) if amb.get("verb_re") else None,
        sensitive=[re.compile(rx) for rx in sens.get("secret", [])],
        protect=[re.compile(rx) for rx in sens.get("protect", [])],
        secret_readers=set(sens.get("bash_secret_readers", [])),
        cc_own=[re.compile(rx) for rx in a.get("cc_own_paths", [])],
    )
    pol.defaults = pp(raw.get("defaults", {}), ProjectPolicy())
    for name, d in raw.get("projects", {}).items():
        pol.projects[name] = pp(d, pol.defaults)
    for m in [pol.defaults, *pol.projects.values()]:
        if m.mode not in ("enforce", "observe") or m.unmatched not in ("pass", "ask"):
            raise ValueError(f"approval.toml: mode는 enforce/observe, unmatched는 pass/ask — {m}")
    return pol
