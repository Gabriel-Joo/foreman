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
# heredoc을 텍스트로 저장만 하는 곳(파일 쓰기 cat > f · tee f 는 따로 — 쓰는 파일이 보호 파일인지 본다)
TEXT_SINKS = [
    re.compile(r"(^|\s)git\b.*\s(commit|tag|notes|merge)\b.*(\s-F\s*-|\s--file(=|\s+)-)(\s|$)"),
    re.compile(r"(^|\s)gh\b.*\s(--body-file|-F)\s+-(\s|$)"),
]
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
    protect_tool_ok: list[re.Pattern[str]] = field(default_factory=list)  # 그중 Edit · Write 도구 편집은 통과(Bash 쓰기는 여전히 ask)
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
            # 11-03 "늘 Yes"(10번 모두 Edit 도구로 approval.toml) — 바뀐 내용이 터미널 · 기록에 그대로 보이는 도구 편집은
            # 통과시키고 텔레그램으로 알린다(approvals.py). 게이트를 통째로 끌 수 있는 파일(settings.json · hook 스크립트)은 계속 묻는다
            if self._match(path, cwd, self.protect_tool_ok):
                return Decision("allow", "규칙파일-편집", f"{tool}: 안전 규칙 파일을 도구로 고친다 — 내용이 보인다, 텔레그램으로 알림({s})")
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
        orig, written = _strip_file_heredocs(cmd)
        # "실행과 글자" 넓히기(11-02) — 실행되지 않는 글자 · 값이 새지 않는 것이 명백한 모양을 검사 전에 지운다(_neutralize)
        scan = _neutralize(orig, scratchpad)
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
        # 해석기로 들어가는 heredoc(python - <<EOF …)이 비밀 파일 경로를 쥐고 그 파일을 쓰거나 내용을 바로 찍는다.
        # (11-02 다시 돌려 보기에서 찾은 빈틈: python heredoc으로 .env.db를 쓰는 명령이 어느 규칙에도 걸리지 않았다.
        #  읽기만 하는 것 — 앱이 설정을 읽는 x = open('.env').read() — 은 5단계 결정대로 묻지 않는다)
        for m in HEREDOC.finditer(scan):
            body = m.group("body")
            if not _SCRIPT_WRITE.search(body):
                continue
            for lit in re.findall(r"['\"]([^'\"\n]{1,200})['\"]", body):
                if any(s.search(os.path.expanduser(lit)) for s in self.sensitive):
                    return Decision("ask", "민감한-경로", f"Bash: 스크립트가 비밀이 든 파일을 쓰거나 찍는다({_short(lit, 50)})")
        segs = _segments(scan)
        if segs is None:
            if self.delete_outside and re.search(r"(^|[\s;&|(])rm\s", scan):
                return Decision("ask", "애매한-삭제", "rm이 있는데 명령을 나눌 수 없다(따옴표 등) — 무엇을 지울지 확정할 수 없다")
            return None
        if (d := self._segments_ask(segs, cwd, scratchpad, depth)):
            return d
        if any(x in orig for x in ("$(", "`", "<(", ">(")):
            return None                            # 명령 치환 — 무엇이 실행될지 확실하지 않다. allow하지 않는다(지우기 전 원문으로 본다)
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
            # 리다이렉트 말고 파일에 쓰는 명령으로 보호 파일을 고치기(11-03 — 전엔 > · heredoc만 봤다. 다른 구현의 config-guard 참고):
            # sed -i · perl -i · cp · mv · install · tee · ln · dd of= · truncate · rsync
            base = os.path.basename(head)
            writes = base in ("cp", "mv", "install", "tee", "ln", "rsync", "truncate") or \
                (base in ("sed", "perl") and any(w.startswith("-i") or w == "--in-place" or w.startswith("-pi")
                                                 for w in words[1:]))
            if writes or base == "dd":
                args = [w for w in words[1:] if not w.startswith("-")]
                if base == "dd":
                    targets = [w[3:] for w in words[1:] if w.startswith("of=")]
                elif base in ("cp", "install", "rsync", "ln"):
                    # 쓰는 곳은 목적지뿐 — 보호 파일을 읽어 백업하는 cp ~/.claude/settings.json 백업/은 쓰기가 아니다
                    tdir = next((words[j + 1] for j, w in enumerate(words[:-1]) if w in ("-t", "--target-directory")), None)
                    targets = [tdir] if tdir else args[-1:]
                else:                                  # mv(원본을 옮겨 없앤다) · tee · truncate · sed -i · perl -i
                    targets = args
                for t in targets:
                    if t and (s := self._match(t, here, self.protect)):
                        return Decision("ask", "보호-설정파일", f"Bash: 안전 규칙 · 설정 파일 쓰기({base} → {s})")
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


# ── 실행과 글자 — 넓히기(11-02) ─────────────────────────────────
# 검사 전에 "실행되지 않는 글자"와 "값이 새지 않는 것이 명백한 모양"을 무해한 자리표시로 바꾼다. 조건이 하나라도 어긋나면
# 그대로 둔다(= 예전처럼 검사한다). allow 판정은 바꾸기 전 원문으로 하므로, 이 함수가 allow를 새로 만들지는 않는다.
#   1. 검색어: grep · rg · sed · awk의 패턴 인자(명령 치환이 없는 것). 그 파이프가 셸 · 해석기 · xargs로 이어지면 안 지운다.
#      sed의 e 명령 · s///e, awk의 system() · getline · print | 는 실행이므로 안 지운다
#   2. 키 이름만: 비밀 파일을 읽어도 마지막 단계가 sed 's/=.*//' · cut -d= -f1 · awk -F= '{print $1}'이면 값이 나오지 않는다
#   3. mktemp -d로 만든 디렉토리를 "${V:?}"로 지우기 — 같은 명령 안에서 V가 mktemp -d로 딱 한 번 정해지고 바뀌지 않을 때만
#   4. 비밀 파일 값을 curl 헤더로만: -H @<(printf '이름: … %s' "$(sed -n 's/^KEY=//p' 파일)") — curl이 요청 헤더를
#      찍는 옵션(-v · --trace · --libcurl)이 없고, 보내는 곳이 이 서버 · VM 망일 때만(밖으로 보내면 그 자체가 유출)
_SCRIPT_WRITE = re.compile(r"open\([^)\n]*['\"][wax]\+?b?['\"]|\.write_(text|bytes)\(|os\.(rename|replace)\(|"
                           r"shutil\.(copy\w*|move)\(|print\(\s*open\(|sys\.stdout\.write\(\s*open\(")
_SEARCH = ("grep","egrep", "fgrep", "rg", "ugrep", "sed", "awk", "gawk", "mawk")
_EXEC_SINKS = set(SHELLS) | {"python", "python3", "perl", "ruby", "node", "xargs", "eval", "source", ".", "env", "sudo",
                             "parallel", "watch", "nohup", "time"}
_OPT_ARG = {"grep": {"-f", "-m", "-A", "-B", "-C", "-d", "-D", "--file", "--max-count", "--include", "--exclude"},
            "rg": {"-f", "-m", "-A", "-B", "-C", "-g", "-t", "-T", "-j", "-M", "--glob", "--type", "--type-not",
                   "--max-count", "--max-columns", "--file"},
            "sed": {"-f", "-l", "--file", "--line-length"},
            "awk": {"-f", "-v", "-F", "--file", "--assign", "--field-separator"}}
_SED_EXEC = re.compile(r"(^|[;\n{}])\s*[0-9,$/!]*\s*e(\s|;|$)|s(.)(?:\\.|(?!\3).)*\3(?:\\.|(?!\3).)*\3[gpIiMm0-9w]*e")
_AWK_EXEC = re.compile(r"system\s*\(|getline|\|\s*[\"$]|print[^;}]*\|")
_LOCAL_HOST = re.compile(r"^(127\.\d+\.\d+\.\d+|localhost|\[::1\]|192\.168\.12[12]\.\d+)$")
_HDR = re.compile(
    r"(?P<opt>-H|--header)\s+@<\(\s*printf\s+(?P<q>['\"])(?P<fmt>[^'\"\n]*)(?P=q)\s+"
    r"\"\$\(\s*sed\s+-n\s+(?P<q2>['\"])s/\^?[A-Za-z_][A-Za-z0-9_]*=//p(?P=q2)\s+(?P<file>[^\s)'\"]+)\s*\)\"\s*\)")


def _seg_spans(cmd: str) -> list[tuple[int, int, str]]:
    """맨 바깥 수준의 (시작, 끝, 앞 구분자) — 따옴표 · $( ) · <( ) · 백틱 안의 구분자는 무시한다."""
    out, start, i, depth, q, sep = [], 0, 0, 0, None, ""
    n = len(cmd)
    while i < n:
        ch = cmd[i]
        if q:
            if ch == "\\" and q == '"':
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "'\"`":
            q = ch
        elif ch == "\\":
            i += 2
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in ";&|\n":
            two = cmd[i:i + 2]
            s = two if two in ("&&", "||", "|&", ";;") else ch
            out.append((start, i, sep))
            sep, i = s, i + len(s)
            start = i
            continue
        i += 1
    out.append((start, n, sep))
    return [(a, b, s) for a, b, s in out if cmd[a:b].strip()]


def _words(seg: str) -> list[str] | None:
    try:
        lex = shlex.shlex(seg, posix=True, punctuation_chars=False)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return None


def _head(words: list[str]) -> tuple[str, int]:
    i = 0
    while i < len(words) and re.fullmatch(r"[A-Za-z_]\w*=.*", words[i]):
        i += 1
    return (os.path.basename(words[i]) if i < len(words) else ""), i


def _pattern_idx(kind: str, words: list[str], h: int) -> list[int]:
    """검색 명령에서 패턴(스크립트 · 프로그램) 인자의 자리."""
    fam = "grep" if kind in ("grep", "egrep", "fgrep", "ugrep") else ("awk" if kind in ("awk", "gawk", "mawk") else kind)
    takes = _OPT_ARG.get(fam, set())
    explicit, positional, i = [], [], h + 1
    while i < len(words):
        w = words[i]
        if w == "--":
            positional += list(range(i + 1, len(words)))
            break
        if fam in ("grep", "rg", "sed") and w in ("-e", "--regexp", "--expression"):
            explicit.append(i + 1)
            i += 2
            continue
        if fam in ("grep", "rg") and w.startswith("--regexp="):
            return []                           # 붙여 쓴 패턴 — 따로 다루지 않는다(그대로 검사)
        if fam in ("sed", "awk") and w in ("-f", "--file"):
            return []                           # 스크립트 파일 — 실행 내용을 모른다
        if w in takes:
            i += 2
            continue
        if w.startswith("-") and len(w) > 1:
            i += 1
            continue
        positional.append(i)
        i += 1
    if explicit:
        return [j for j in explicit if j < len(words)]
    return positional[:1]


def _blank_patterns(cmd: str) -> str:
    spans = _seg_spans(cmd)
    # 파이프 묶음마다 — 뒤에 셸 · 해석기가 있으면 그 묶음은 손대지 않는다
    groups: list[list[tuple[int, int, str]]] = []
    for sp in spans:
        if sp[2] in ("|", "|&") and groups:
            groups[-1].append(sp)
        else:
            groups.append([sp])
    edits: list[tuple[int, int, str]] = []
    for g in groups:
        heads = []
        for a, b, _ in g:
            w = _words(cmd[a:b])
            heads.append(_head(w)[0] if w else "")
        for k, (a, b, _s) in enumerate(g):
            if heads[k] not in _SEARCH or any(h in _EXEC_SINKS for h in heads[k + 1:]):
                continue
            seg = cmd[a:b]
            words = _words(seg)
            if not words:
                continue
            kind, h = _head(words)
            new = list(words)
            changed = False
            for j in _pattern_idx(kind, words, h):
                p = words[j]
                if "$(" in p or "`" in p:
                    continue
                if kind == "sed" and _SED_EXEC.search(p):
                    continue
                if kind in ("awk", "gawk", "mawk") and _AWK_EXEC.search(p):
                    continue
                new[j] = "PATTERN"
                changed = True
            if changed:
                lead = seg[: len(seg) - len(seg.lstrip())]
                edits.append((a, b, lead + " ".join(shlex.quote(x) for x in new) + " "))
    for a, b, rep in sorted(edits, reverse=True):
        cmd = cmd[:a] + rep + cmd[b:]
    return cmd


def _key_only(words: list[str]) -> bool:
    """마지막 단계가 키 이름만 내보내는가 — sed 's/=.*//' · cut -d= -f1 · awk -F= '{print $1}'."""
    kind, h = _head(words)
    args = words[h + 1:]
    # 11-03 — 값이 아니라 길이 · 개수 · 해시 · 있고 없음만 나오는 끝 단계(민감한-경로 "늘 Yes" 8번 중 3번이 이 모양)
    if kind in ("wc", "sha256sum", "sha1sum", "md5sum", "b2sum"):
        return True
    if kind in ("grep", "egrep", "rg") and any(a in ("-q", "--quiet", "--silent", "-c", "--count", "-l",
                                                      "--files-with-matches") or re.fullmatch(r"-[a-zA-Z]*[qcl][a-zA-Z]*", a)
                                               for a in args):
        return True
    if kind == "cut":
        j = " ".join(args)
        return bool(re.search(r"(^|\s)(-d\s*=|--delimiter==)", j)) and bool(re.search(r"(^|\s)(-f\s*1|--fields=1)(\s|$)", j))
    if kind == "sed":
        if any(a.startswith("-i") or a.startswith("--in-place") for a in args):
            return False
        scripts = [a for a in args if not a.startswith("-")]
        return bool(scripts) and re.fullmatch(r"s(.)=\.\*\$?\1\1[gp]*", scripts[0]) is not None
    if kind in ("awk", "gawk", "mawk"):
        j = " ".join(args)
        prog = [a for a in args if a.startswith("{")]
        return bool(re.search(r"(^|\s)-F\s*=", j)) and len(prog) == 1 and \
            re.fullmatch(r"\{\s*print\s+\$1\s*;?\s*\}", prog[0]) is not None
    return False


_KEY_PRE = {"cat", "grep", "egrep", "sort", "uniq", "head", "tail", "sed", "tr"}
_TEST_SUBST = re.compile(r"(\btest\s+-[nz]\s+|\[\s+-[nz]\s+)\"\$\(([^()]*)\)\"")


def _blank_key_only(cmd: str) -> str:
    """비밀 파일을 읽어도 키 이름만 나오는 파이프 묶음을 자리표시로. 묶음 안에 리다이렉트 · 다른 명령이 있으면 안 바꾼다."""
    spans = _seg_spans(cmd)
    groups: list[list[tuple[int, int, str]]] = []
    for sp in spans:
        if sp[2] in ("|", "|&") and groups:
            groups[-1].append(sp)
        else:
            groups.append([sp])
    edits = []
    for g in groups:
        a, b = g[0][0], g[-1][1]
        text = cmd[a:b]
        if re.search(r"(?<![0-9&])>|\$\(|`|<\(", text.replace("2>/dev/null", "")):
            continue
        if not _hides([_words(cmd[x:y]) for x, y, _ in g]):
            continue
        edits.append((a, b, " : keys-only "))
    for a, b, rep in sorted(edits, reverse=True):
        cmd = cmd[:a] + rep + cmd[b:]
    # 명령 치환 안도 같은 기준으로(11-03): echo "len $(sed … .env | tr -d '\n' | wc -c)" — 길이만 나온다
    cmd = re.sub(r"\$\(([^()]*)\)", lambda m: "$( : keys-only )" if _pipe_hides_value(m.group(1)) else m.group(0), cmd)
    # test -n "$(sed -n 's/^K=//p' .env)" — 값은 test의 인자로만 가고 화면에는 참 · 거짓만(있다 · 없다)
    return _TEST_SUBST.sub(lambda m: m.group(1) + '"x"' if _pipe_stages_plain(m.group(2)) else m.group(0), cmd)


def _pipe_stages_plain(text: str) -> bool:
    """리다이렉트 · 치환 없이 읽기만 하는 단계들(cat · grep · sed(-i 없음) · tr …)로 된 파이프인가."""
    if re.search(r"(?<![0-9&])>|\$\(|`|<\(", text.replace("2>/dev/null", "")):
        return False
    ws = [_words(p) for p in text.split("|")]
    return all(w and _head(w)[0] in _KEY_PRE and not (_head(w)[0] == "sed" and any(t.startswith("-i") for t in w))
               for w in ws)


_AFTER_HIDE = {"cut", "head", "tail", "tr", "sort", "uniq"}   # 값을 숨긴 단계(길이 · 해시 · 키 이름) 뒤에 와도 되는 가공


def _hides(ws: list[list[str]]) -> bool:
    """파이프 단계들: 앞은 읽기만(cat · grep · sed · tr …), 어딘가 값을 숨기는 단계(_key_only), 그 뒤는 가공만(cut · head …).
    sha256sum | cut -c1-12처럼 해시 앞자리만 보는 것도 된다."""
    if any(w is None or not w for w in ws):
        return False
    for k, w in enumerate(ws):
        if _key_only(w):
            pre_ok = all(_head(x)[0] in _KEY_PRE and not (_head(x)[0] == "sed" and any(t.startswith("-i") for t in x))
                         for x in ws[:k])
            return pre_ok and all(_head(x)[0] in _AFTER_HIDE for x in ws[k + 1:])
    return False


def _pipe_hides_value(text: str) -> bool:
    """명령 치환 안의 파이프가 값 대신 키 이름 · 길이 · 해시만 내는가."""
    if re.search(r"(?<![0-9&])>|\$\(|`|<\(", text.replace("2>/dev/null", "")):
        return False
    return _hides([_words(p) for p in text.split("|")])


def _safe_tmp_rm(cmd: str) -> str:
    """V=$(mktemp -d …) … rm -rf "${V:?}" — 같은 명령에서 V가 mktemp -d로 딱 한 번 정해지고 바뀌지 않으면 그 rm을 자리표시로."""
    assign = r"(?:^|[\s;&|(]){v}=(\"?)\$\(\s*mktemp\s+-d(?:\s+[^$`;&|()\"'\n]*)?\)\1(?=[\s;&|)]|$)"
    names = {m.group(1) for m in re.finditer(assign.replace("{v}", r"([A-Za-z_]\w*)").replace(r"\1", r"\2"), cmd)}
    for v in sorted(names):
        m = re.search(assign.replace("{v}", re.escape(v)), cmd)
        if m is None:
            continue
        if len(re.findall(rf"(?<![\w$]){v}=", cmd)) != 1:
            continue                                # 다시 정했다
        if re.search(rf"\bfor\s+{v}\b|\bread\b[^;&|\n]*\b{v}\b|\$\{{{v}:?[=+-]|\b(declare|typeset|local|readonly|export|unset)\b[^;&|\n]*\b{v}\b|\beval\b|\bsource\b|(^|\s)\.\s",
                     cmd):
            continue                                # 바꿀 수 있는 길이 있다 — 그대로 검사
        rm = re.compile(rf"\brm\s+(?:-[rRfv]+\s+)*(?:--\s+)?\"\$\{{{v}:\?\}}\"(?=\s*($|[;&|)\n]))")
        start = m.end()
        cmd = cmd[:start] + rm.sub(" : tmp-rm ", cmd[start:])
    return cmd


def _safe_header_secret(cmd: str) -> str:
    """비밀 파일 값을 curl 요청 헤더로만 넘기는 모양을 자리표시로(조건은 위 4)."""
    for sa, sb, _ in reversed(_seg_spans(cmd)):
        seg = cmd[sa:sb]
        if not re.match(r"\s*curl\s", seg):
            continue
        ms = list(_HDR.finditer(seg))
        if not ms or not all(re.fullmatch(r"[A-Za-z][A-Za-z-]*:\s*[^%]*%s(\\n)?", m.group("fmt")) for m in ms):
            continue
        rest = _HDR.sub(" ", seg)
        if re.search(r"(^|\s)(-v|--verbose|--trace(-ascii|-time)?|--libcurl|-[a-zA-Z]*v[a-zA-Z]*)(\s|=|$)", rest):
            continue                                # 요청 헤더를 화면 · 파일에 찍는다
        urls = re.findall(r"\S*://\S*", rest)
        hosts = re.findall(r"https?://([^/:\s'\"?#]+)", rest)
        if not hosts or any("$" in u for u in urls) or not all(_LOCAL_HOST.match(h) for h in hosts):
            continue                                # 밖으로 보내면 값이 이 서버를 떠난다
        cmd = cmd[:sa] + _HDR.sub(lambda m: f"{m.group('opt')} @LOCAL_SECRET_HEADER", seg) + cmd[sb:]
    return cmd


# 5. 출력 · 메시지 리터럴(11-03): echo · printf의 따옴표 인자, git commit · tag의 -m 메시지, curl --data 본문.
#    따옴표 안이고 명령 치환($( ) · 백틱)이 없을 때만 글자로 본다. 그대로 검사하는 것:
#    셸 · 해석기로 넘김(| sh · | xargs …), 명령 치환 · 프로세스 치환 안($(echo …) · <(echo …) — 결과가 실행될 수 있다),
#    스크립트 파일로 씀(> x.sh), 따옴표 없는 인자, curl -d @파일(파일을 읽는다). 리다이렉트 대상(> .env)은 남겨 따로 검사한다
_DQ = r'"(?:[^"\\`$]|\\.|\$(?!\())*"'
_SQ = r"'[^']*'"
_LIT = rf"(?:{_DQ}|{_SQ})"
_ECHO = re.compile(rf"(?P<cmd>\b(?:echo|printf))(?P<args>(?:\s+(?:-[neE]{{1,3}}|--))*(?:\s+{_LIT})+)(?=\s*(?:$|[;&|)\n>'\"]|2>))")
_ECHO_PRE = re.compile(r"(?:^|[;&|({\n'\"]|\b(?:do|then|else)\b)\s*$")
_IN_SUBST = re.compile(r"[$<>]\(\s*$")
# 출력이 파이프로 어디든 넘어가면 글자로 보지 않는다 — 받는 프로그램이 실행할 수 있다
# (11-03 다시 돌려 보기: echo "DROP DATABASE …" | docker exec -i … mysql — 셸만 막았더니 mysql이 받는 것을 놓쳤다)
_TO_SINK = re.compile(r"\s*(?:\|(?!\|)|(?:>>?)\s*\S+\.(?:sh|bash|zsh|py)\b)")
_GIT_MSG = re.compile(rf"(\bgit\b[^;&|\n]*?\s(?:-[a-zA-Z]*m|--message)(?:=|\s+))({_LIT})")
_CURL_DATA = re.compile(rf"(\s(?:-d|--data|--data-raw|--data-binary|--data-ascii|--json)(?:=|\s+))({_LIT})")


def _blank_literals(cmd: str) -> str:
    out, last = [], 0
    for m in _ECHO.finditer(cmd):
        pre = cmd[:m.start("cmd")]
        if not _ECHO_PRE.search(pre) or _IN_SUBST.search(pre) or _TO_SINK.match(cmd, m.end()):
            continue
        out.append(cmd[last:m.start("args")] + ' "TEXT"')
        last = m.end("args")
    cmd = "".join(out) + cmd[last:]
    cmd = _GIT_MSG.sub(lambda m: m.group(1) + '"MESSAGE"', cmd)
    return _CURL_DATA.sub(lambda m: m.group(1) + ("'DATA'" if not m.group(2)[1:].startswith("@") else m.group(2)), cmd)


def _safe_scratch_rm(cmd: str, scratchpad: str | None) -> str:
    """세션 스크래치패드 안만 지우는 rm(-r 포함)을 자리표시로(11-03 사용자 요청 — 스크린샷 시험마다 shots/*.png 지우기가 걸렸다).
    조건: 모든 대상이 스크래치패드 **안쪽**(그 자체는 아님) — 부모 디렉토리를 realpath로 풀어 확인(.. · 심볼릭 링크로 밖을 가리키면 빠진다),
    글롭은 마지막 조각에만, 변수는 같은 명령에서 문자 그대로의 경로로 딱 한 번 정한 것만 푼다($( ) · 다시 정하기 · read · for 등이면 빠진다).
    스크래치패드의 부모 /tmp/claude-<uid>는 권한 700 — 다른 계정이 링크를 심을 수 없다."""
    if not scratchpad:
        return cmd
    root = os.path.realpath(scratchpad)
    env: dict[str, str] = {}
    for m in re.finditer(r"(?:^|[\s;&|(])([A-Za-z_]\w*)=(\"?)([^\s\"'$`;&|()]+)\2(?=[\s;&|)]|$)", cmd):
        env[m.group(1)] = m.group(3)
    for v in list(env):
        if len(re.findall(rf"(?<![\w$]){v}=", cmd)) != 1 or re.search(
                rf"\bfor\s+{v}\b|\bread\b[^;&|\n]*\b{v}\b|\$\{{{v}:?[=+-]|\b(declare|typeset|local|readonly|export|unset)\b[^;&|\n]*\b{v}\b|\beval\b|\bsource\b",
                cmd):
            del env[v]

    def inside(tok: str) -> bool:
        m = re.fullmatch(r"\$\{?([A-Za-z_]\w*)(?::\?)?\}?(/.*)?", tok)
        if m:
            if m.group(1) not in env:
                return False
            tok = env[m.group(1)] + (m.group(2) or "")
        if "$" in tok or "`" in tok or not os.path.isabs(os.path.expanduser(tok)):
            return False
        p = os.path.normpath(os.path.expanduser(tok))
        parent, last = os.path.split(p)
        if any(ch in parent for ch in "*?[") or not last or last in (".", ".."):
            return False
        rp = os.path.realpath(parent)
        return (rp == root or rp.startswith(root + os.sep)) and p != root

    edits = []
    for a, b, _sep in _seg_spans(cmd):
        w = _words(cmd[a:b])
        if not w:
            continue
        head, h = _head(w)
        if head != "rm":
            continue
        targets = [t for t in w[h + 1:] if not t.startswith("-")]
        if targets and all(inside(t) for t in targets) and not re.search(r"[<>]|\$\(|`", cmd[a:b]):
            edits.append((a, b, " : scratch-rm "))
    for a, b, rep in sorted(edits, reverse=True):
        cmd = cmd[:a] + rep + cmd[b:]
    return cmd


def _neutralize(cmd: str, scratchpad: str | None = None) -> str:
    try:
        cmd = _safe_scratch_rm(cmd, scratchpad)
        # 키 이름만 · 헤더로만은 sed 스크립트 모양을 보므로 검색어 지우기보다 먼저. 리터럴(5)은 맨 먼저
        return _blank_patterns(_safe_tmp_rm(_safe_header_secret(_blank_key_only(_blank_literals(cmd)))))
    except Exception:  # noqa: BLE001 — 지우기가 실패하면 원문 그대로 검사한다(덜 지우는 쪽으로)
        return cmd


# ── 명령 나누기 ─────────────────────────────────────────────
def _strip_file_heredocs(cmd: str) -> tuple[str, list[str]]:
    """파일에 쓰기만 하는 heredoc(cat > f · cat >> f · tee [-a] f)의 본문을 빼고, 쓰는 파일 목록을 돌려준다.
    해석기로 들어가는 heredoc(bash · python …)이나 받는 쪽을 모르는 것은 그대로 둔다 — 실행되기 때문이다.
    .sh · .bash · .zsh로 쓰는 것도 본문을 남긴다(바로 실행될 가능성이 크다)."""
    written: list[str] = []

    def sub(m: re.Match[str]) -> str:
        # 따옴표 없는 heredoc(<<EOF)은 본문의 $(…) · 백틱을 셸이 실행한다 — 그러면 받는 쪽과 무관하게 검사한다
        quoted = bool(m.group(2))
        if not quoted and re.search(r"\$\(|`", m.group("body")):
            return m.group(0)
        line = m.group("line") + " " + m.group("rest")
        seg = re.split(r"&&|\|\||;", line)[-1] if "|" not in m.group("line").split("<<")[0][-3:] else line
        if any(p.search(seg) for p in TEXT_SINKS):
            # 커밋 · 태그 · 노트 · PR 본문 — 텍스트로 저장만 된다(실측: git commit -F - 본문의 글자로 승인 창)
            return m.group("line") + "<<" + m.group("tag") + m.group("rest") + "\n" + m.group("tag")
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
    """스크립트 파일 실행이면 그 경로 — bash x.sh · sh x · source x · . x · ./x.sh · /path/x.sh.
    bash -n x.sh(문법 검사만 — 실행하지 않는다)는 실행이 아니다(11-02 오탐: 문법 검사한 스크립트 안의 kubectl delete)."""
    if not words:
        return None
    if words[0] in SHELLS:
        flags = [w for w in words[1:] if w.startswith("-") and not w.startswith("--")]
        if any("n" in f[1:] for f in flags) and "-c" not in words:
            return None                         # -n(noexec): 읽기만 한다
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
    # 인자 안의 명령 치환 · 프로세스 치환 · 백틱도 제 명령으로 본다 — git commit -m "$(cat .env)"는 cat이 .env를 찍는다
    # (11-03 다른 구현과 비교하다 찾은 빈틈: 조각의 첫 단어만 명령으로 봐서 head가 git이었다)
    inner = [m.group(1) or m.group(2) or "" for m in re.finditer(r"[$<>]\(([^()]*)\)|`([^`]*)`", body)]
    for seg in [*re.split(r"&&|\|\||[;|\n]", body), *[s for i in inner for s in re.split(r"&&|\|\||[;|\n]", i)]]:
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
        protect_tool_ok=[re.compile(rx) for rx in sens.get("protect_tool_edit_ok", [])],
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
