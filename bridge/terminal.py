"""터미널 패널(7단계) — CC에게 시킬 수 없는 일(sudo 암호 · SSH 패스프레이즈 · 레지스트리 로그인)을 대시보드에서 끝낸다.

구성
  tmux 세션 foreman-shell  ← bash --rcfile deploy/shell/foreman-bashrc (사람이 직접 치는 셸)
    창은 프로젝트마다 하나(runshoes · petmint-rag-chatbot · foreman · ronanlab-infra). 탭마다 그룹 세션 foreman-shell-v-<탭>이 같은 창을 보되
    "보이는 창"만 따로 갖는다(11-10, deploy/shell/foreman-term-view — 연결이 끝나면 사라진다)
  ttyd(.tools/ttyd)        ← 연결마다 foreman-term-view를 띄워 붙는다. TCP 포트를 열지 않고 UNIX 소켓(.run/ttyd.sock, 디렉토리 0700)에만
  브리지 /terminal/*       ← 쿠키 인증을 거쳐 ttyd 소켓으로 그대로 넘긴다(xterm.js 화면 그대로 — 파싱하지 않는다)
  화면 이름은 「셸」(11-14 — 「터미널」에서 바꿈). [셸 비우기]는 셸을 새로 띄우지 않고 화면 · 스크롤백만 비운다(clear)

「CC 화면」(11-14, 세션 패널 [CC 화면] 단추 → 띄우는 창) — 세션 CC 창(권한 · 계획 승인 · 고르기 창 포함)을 브라우저에서 보고 키를 보낸다
  ttyd를 하나 더(.run/ttyd-cc.sock, -b /ccscreen) — 같은 _supervise 틀. 연결마다 deploy/shell/foreman-cc-view가 그 CC 세션의
  tmux 세션에 그룹 세션 ccv-<탭>을 만들어 붙는다. 보는 동안 CC 창을 띄운 창 크기에 맞추고, 마지막 보기가 나가면
  CC_REST_SIZE(80×24)로 되돌린다(11-14 사용자). 브라우저는 세션 번호만 주고,
  붙을 tmux 창은 cc_target이 DB · 살아 있는 프로세스로 정한다. 열고 닫은 것만 session_action(ccview-open · ccview-close)

기록 — 셸의 PROMPT_COMMAND가 명령마다 /hooks/shell로 보낸다. 마스킹해서 event(source=shell, type=shell_cmd)로.
  승인 정책은 걸리지 않는다(사람이 직접 친다). 셸 세션은 character_session.type='shell' — 캐릭터 카드로 보이지 않는다

CC의 부탁 — 턴이 끝나면 그 턴의 assistant 글에서 "이 명령을 실행해 주세요"를 찾는다(코드 · `! 명령` + 부탁하는 말 +
  사람이 쳐야 하는 명령). 찾으면 셸 입력 줄에 미리 채우고(비밀번호 자리는 비우고 커서를 거기에), 패널을 올리라고 WS로 알린다.
  사람이 그 명령을 치면 출력(마스킹)을 부탁한 세션에 3단계 주입으로 돌려준다. 주입이 안 되면 화면에만 보인다.
"""

import asyncio
import hashlib
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.config import Settings
from bridge.inject import Refused, _ancestors, _tmux_env, deliver, tmux
from bridge.liveness import live_sessions
from bridge.mask import Masker
from bridge.models import EventIn, EventSource, EventStatus, EventType

log = logging.getLogger("foreman.terminal")

PROMPT_MARK = "[foreman] "      # foreman-bashrc의 PS1 머리 — 출력 범위를 찾는 표지
# 프로젝트 창은 머리가 창 이름이다("[runshoes] ", 11-10). venv를 다시 activate하면 "(llm_env) "가 앞에 붙는다(256 기록)
_PROMPT_HEAD = re.compile(r"^(?:\([^()\s]+\) )?\[[\w.-]+\] ")


def is_prompt(line: str) -> bool:
    return _PROMPT_HEAD.match(line) is not None
COOKIE = "foreman_term"
# 프로젝트마다 터미널 창(11-10) — 창 이름이 이것이면 그 프로젝트 창이다(bridge/api/dashboard.py PROJECT_ORDER와 같은 이름)
TERM_PROJECTS = ("runshoes", "petmint-rag-chatbot", "foreman", "ronanlab-infra")
# 브라우저 탭 id(11-10) — iframe 주소 · API로 온다. 이 모양만 tmux 세션 이름 · ttyd 인자로 쓴다(deploy/shell/foreman-term-view와 같은 규칙)
TAB_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
# 「CC 화면」(11-14) — 탭 그룹 세션 이름 머리(deploy/shell/foreman-cc-view와 같다) · tmux 창 모양 · 기록 이름(session_action.action은 12자까지)
CC_VIEW_PREFIX = "ccv-"
CC_MARK = "@foreman_ccview"        # 보는 동안 창 크기를 띄우는 창에 맞춰 묶었다는 표시(foreman-cc-view hold · release)
# 마지막 CC 화면이 나갈 때 CC 창을 되돌리는 크기(11-14 사용자) — 이 한 곳. 보기 스크립트에는 ttyd 고정 인자로 넘긴다
CC_REST_SIZE = (80, 24)
PANE_RE = re.compile(r"^%[0-9]{1,7}$")
CC_OPEN, CC_CLOSE = "ccview-open", "ccview-close"

# ── 마스킹(셸 명령 · 출력) ─────────────────────────────────────────
# Masker(정확한 값 · 토큰 모양 · KEY=값)에 더해 명령줄에서 비밀이 오는 자리
_PW_FLAG = re.compile(r"(--(?:password|passwd|passphrase|token|secret)(?:=|\s+))(?!-)(\S+)", re.I)
_LOGIN_P = re.compile(r"(\b(?:docker|podman|nerdctl|buildah|skopeo|oras|helm\s+registry)\s+login\b[^|;&\n]*?\s-p\s*)(?!-)(\S+)")
_MYSQL_P = re.compile(r"(\b(?:mysql|mariadb|mysqldump|mysqladmin)\b[^|;&\n]*?\s-p)([^\s-]\S*)")
_SSHPASS = re.compile(r"(\bsshpass\s+-p\s*)(\S+)")
_ECHO_PIPE = re.compile(
    r"(\b(?:echo|printf)\s+(?:-\w+\s+)*)('[^']*'|\"[^\"]*\"|[^\s|]+)"
    r"(\s*\|\s*(?:sudo\b[^|;&\n]*\s-S\b|[^|;&\n]*--password-stdin|chpasswd|passwd\s+--stdin))")
_URL_CRED = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)([^\s@/]+)(@)", re.I)
_CURL_U = re.compile(r"((?:^|\s)(?:-u|--user)\s+['\"]?[^\s:'\"]+:)([^\s'\"]+)")
M = "«masked»"


def mask_shell(masker: Masker, s: str) -> str:
    s = masker.text(s) or ""
    s = _PW_FLAG.sub(lambda m: m.group(1) + (m.group(2) if m.group(2).startswith("«masked") else M), s)
    s = _LOGIN_P.sub(lambda m: m.group(1) + (m.group(2) if m.group(2).startswith("«masked") else M), s)
    s = _MYSQL_P.sub(lambda m: m.group(1) + M, s)
    s = _SSHPASS.sub(lambda m: m.group(1) + M, s)
    s = _ECHO_PIPE.sub(lambda m: m.group(1) + M + m.group(3), s)
    s = _URL_CRED.sub(lambda m: m.group(1) + M + m.group(3), s)
    s = _CURL_U.sub(lambda m: m.group(1) + M, s)
    return s


def mask_output(masker: Masker, s: str) -> str:
    s = masker.text(s) or ""
    return _URL_CRED.sub(lambda m: m.group(1) + M + m.group(3), s)


# ── CC의 부탁 찾기 ─────────────────────────────────────────────
_FENCE = re.compile(r"```[ \t]*([\w+-]*)[^\n]*\n(.*?)```", re.S)
_INLINE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_BANG_LINE = re.compile(r"^[ \t>*-]*!\s?(\S[^\n]*)$", re.M)
_SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh", "terminal", "text"}
# 사람이 쳐야 하는 명령 — 암호 · 패스프레이즈 · 로그인을 묻는다
HUMAN_CMD = re.compile(
    r"(?:^|[;&|(]\s*)(?:"
    r"(?:sudo|su|ssh-add|ssh-keygen|ssh-copy-id|passwd|kinit)(?:\s|$)"
    r"|(?:docker|podman|nerdctl|buildah|skopeo|oras|npm|vault|az|helm\s+registry)\s+login(?:\s|$)"
    r"|(?:gh|glab|gcloud)\s+auth\s+login(?:\s|$))")
# 부탁하는 말 — 그냥 명령을 보여 주는 글(설명 · 기록)과 가른다
CUE = re.compile(
    r"(?:실행|입력|쳐|치|돌려|붙여넣어)\s*(?:해|하여)?\s*(?:주세요|주십시오|주시겠|주시면|주실|줘|달라)"
    r"|(?:실행|입력)\s*(?:하세요|부탁)|부탁\s*드|직접\s*(?:실행|입력|치|쳐|돌려)|실행이\s*필요"
    r"|\b(?:please|pls)\s+run\b|\brun\s+(?:this|the\s+following|these|it)\b|\byou(?:'ll|\s+will)?\s+need\s+to\s+run\b",
    re.I)


def _clean(line: str) -> str:
    line = line.strip()
    if line.startswith("$ "):
        line = line[2:]
    if line.startswith("!"):
        line = line[1:].lstrip()
    return line.strip()


# 따옴표 안의 말은 부탁이 아니라 인용이다(7단계 실측: 기능을 설명하는 글의 "실행해 주세요"가 부탁으로 잡혔다)
_QUOTED = re.compile(r"\"[^\"\n]{0,120}\"|“[^”\n]{0,120}”|「[^」\n]{0,120}」")
CUE_BEFORE, CUE_AFTER = 300, 150


def _has_cue(msg: str, start: int, end: int) -> bool:
    """명령 가까이(앞 300자 · 뒤 150자, 다른 코드 블록 · 인라인 코드 · 인용 빼고)에 부탁하는 말이 있나."""
    win = msg[max(0, start - CUE_BEFORE):start] + " " + msg[end:end + CUE_AFTER]
    win = _QUOTED.sub(" ", _INLINE.sub(" ", _FENCE.sub(" ", win)))
    return CUE.search(win) is not None


def find_requests(msg: str) -> list[str]:
    """assistant 글에서 사람에게 부탁한 명령(사람이 쳐야 하는 것만). 그 명령 가까이에 부탁하는 말이 있어야 한다 —
    `! 명령` 꼴은 그 자체가 부탁이다."""
    if not msg:
        return []
    found: list[tuple[int, str]] = []

    def add(c: str, start: int, end: int, is_bang: bool = False) -> None:
        c = _clean(c)
        if not c or c.startswith("#") or len(c) > 500 or not HUMAN_CMD.search(c):
            return
        if is_bang or _has_cue(msg, start, end):
            found.append((start, c))

    fences = []
    for m in _FENCE.finditer(msg):
        fences.append((m.start(), m.end()))
        if m.group(1).lower() not in _SHELL_LANGS:
            continue
        body = re.sub(r"\\\n\s*", " ", m.group(2))     # 줄 이음
        for line in body.splitlines():
            add(line, m.start(), m.end(), line.strip().startswith("!"))

    def in_fence(i: int) -> bool:
        return any(a <= i < b for a, b in fences)

    for m in _INLINE.finditer(msg):
        if not in_fence(m.start()):
            add(m.group(1), m.start(), m.end(), m.group(1).strip().startswith("!"))
    for m in _BANG_LINE.finditer(msg):
        if not in_fence(m.start()):
            add(m.group(1).strip("`"), m.start(), m.end(), True)
    out: list[str] = []
    for _, c in sorted(found, key=lambda x: x[0]):
        if c not in out:
            out.append(c)
    return out


# ── 미리 채우기 — 비밀번호 자리는 비우고 커서를 거기에 ──────────────
_PLACEHOLDER = re.compile(
    r"«masked[^»]*»|<[^<>\n]*(?:pass|pw|비밀|암호|패스|token|토큰|secret)[^<>\n]*>|\bYOUR_[A-Z0-9_]+\b|\*{3,}", re.I)
_BLANK = "\0"


def prefill_form(cmd: str) -> tuple[str, int]:
    """(채울 글, 끝에서 왼쪽으로 옮길 칸 수). 비밀번호 값 · 자리표시(<password> 등)는 비운다."""
    s = re.sub(r"[\x00-\x1f\x7f]", " ", cmd).strip()
    s = _PLACEHOLDER.sub(_BLANK, s)
    s = _PW_FLAG.sub(lambda m: m.group(1) + _BLANK, s)
    s = _LOGIN_P.sub(lambda m: m.group(1) + _BLANK, s)
    s = _MYSQL_P.sub(lambda m: m.group(1) + _BLANK, s)
    s = _SSHPASS.sub(lambda m: m.group(1) + _BLANK, s)
    i = s.find(_BLANK)
    if i < 0:
        return s, 0
    return s.replace(_BLANK, ""), len(s[i:].replace(_BLANK, ""))


def _norm(s: str) -> str:
    return " ".join(s.split())


def cmd_matches(typed: str, head: str) -> bool:
    """친 명령이 부탁한 명령인가 — 비운 자리 앞까지 같으면, 아니면 앞 단어 세 개가 같으면."""
    t, h = _norm(typed), _norm(head)
    if not t or not h:
        return False
    if t.startswith(h):
        return True
    tt, ht = t.split(), h.split()
    n = min(3, len(ht))
    return tt[:n] == ht[:n]


def extract_output(lines: list[str], cmd: str, max_lines: int) -> tuple[list[str], bool]:
    """capture-pane 줄에서 그 명령의 출력 — 명령을 친 프롬프트 줄 다음부터 새 프롬프트 앞까지. (줄, 범위를 찾았나)."""
    ls = [x.rstrip() for x in lines]
    while ls and not ls[-1]:
        ls.pop()
    end = len(ls)
    if ls and is_prompt(ls[-1]) and _norm(cmd)[:60] not in _norm(ls[-1]):
        end -= 1
    key = _norm(cmd)[:60]
    for i in range(end - 1, -1, -1):
        if is_prompt(ls[i]) and key and key in _norm(ls[i]):
            return ls[i + 1:end], True
    return ls[max(0, end - max_lines):end], False


# ── 관리자 ────────────────────────────────────────────────────
@dataclass
class Request:
    id: int
    session_id: int
    turn_id: int
    project: str | None
    title: str | None
    cmd: str            # 원래 부탁(마스킹된 글에서)
    fill: str           # 채운 글(비밀번호 자리 비움)
    left: int           # 커서를 끝에서 왼쪽으로
    others: list[str]
    created: float = field(default_factory=time.time)
    prefilled: bool = False
    note: str | None = None
    done: bool = False
    window: str | None = None   # 채운 tmux 창(11-10 — 프로젝트마다 창). 결과 출력도 이 창에서 읽는다

    @property
    def head(self) -> str:
        return self.fill[: len(self.fill) - self.left] if self.left else self.fill

    def public(self, ttl: float) -> dict[str, Any]:
        return {"id": self.id, "session_id": self.session_id, "turn_id": self.turn_id, "project": self.project,
                "title": self.title, "cmd": self.fill, "cursor": len(self.fill) - self.left, "blank": self.left > 0,
                "others": self.others, "prefilled": self.prefilled, "note": self.note,
                "created_at": _iso(self.created), "expires_at": _iso(self.created + ttl)}


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _proc_start(pid: int) -> float | None:
    """프로세스가 뜬 시각(epoch) — /proc/<pid>/stat의 starttime(부팅 뒤 틱) + 부팅 시각."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        ticks = int(stat.rsplit(")", 1)[1].split()[19])
        btime = next(int(ln.split()[1]) for ln in Path("/proc/stat").read_text().splitlines() if ln.startswith("btime "))
        return btime + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        return None


def typed_text(line: str) -> str:
    """커서 줄에서 프롬프트(… $ ) 뒤에 친 글. 프롬프트가 없는 줄(긴 입력이 줄을 넘김)은 줄 전체.
    capture-pane은 줄 끝 공백을 지우므로 빈 프롬프트는 '$'로 끝난다."""
    line = line.rstrip()
    if not line or line.endswith(("$", "#")):
        return ""
    i = line.find("$ ")
    return (line[i + 2:] if i >= 0 else line).strip()


def default_tmux_socket() -> str:
    return f"{os.environ.get('TMUX_TMPDIR', '/tmp')}/tmux-{os.getuid()}/default"


class TerminalManager:
    def __init__(self, engine: AsyncEngine | None, s: Settings, pipeline: Any, masker: Masker,
                 publish: Any = None, on_change: Any = None) -> None:
        self.engine, self.s, self.pipeline, self.mask = engine, s, pipeline, masker
        self.publish = publish or (lambda m: None)
        self.on_change = on_change or (lambda: None)
        self.socket = default_tmux_socket()
        self.target = f"={s.terminal_tmux_session}:"
        self.pending: dict[int, Request] = {}
        self._next = 1
        self._seen_turns: set[int] = set()
        self._cookies: dict[str, float] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        # ttyd 둘(11-14) — "shell"(화면 아래 셸, /terminal) · "cc"(세션 패널 「CC 화면」, /ccscreen). 따로 두어 서로 자리(-m)를 나누지 않는다
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._sups: list[asyncio.Task[None]] = []
        self._stopping = False
        self.shell_session_id: int | None = None
        self.shell_char_id: int | None = None
        self.clients = 0

    # ── 수명 ──
    async def start(self) -> None:
        d = self.s.terminal_socket.parent
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(d, 0o700)
        for sock in (self.s.terminal_socket, self.s.ccscreen_socket):
            if sock.parent != d:
                sock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                os.chmod(sock.parent, 0o700)
        await self.ensure_shell()
        await self.sweep_views(min_age=0)       # 브리지가 내려가 있던 동안 남은 탭 세션(ttyd가 다시 뜨면 탭은 새로 붙는다)
        await self.sweep_views(prefix=CC_VIEW_PREFIX)      # ccv-는 서버 전체에 하나라 막 붙는 중인 것(30초 안)은 둔다
        if self.engine is not None:
            await self._shell_session()
        if not os.access(self.s.ttyd_bin, os.X_OK):
            log.warning("ttyd 없음(%s) — 터미널 패널 화면 · CC 화면은 꺼진다. 기록 · 감지는 그대로", self.s.ttyd_bin)
            return
        self._sups = [
            asyncio.create_task(self._supervise("shell", self._shell_ttyd_args(), self.s.terminal_socket), name="foreman-ttyd"),
            asyncio.create_task(self._supervise("cc", self._cc_ttyd_args(), self.s.ccscreen_socket), name="foreman-ttyd-cc"),
        ]

    async def stop(self) -> None:
        self._stopping = True
        for p in list(self._procs.values()):
            if p.returncode is None:
                p.terminate()
                try:
                    async with asyncio.timeout(3):
                        await p.wait()
                except TimeoutError:
                    p.kill()
        for sup in self._sups:
            sup.cancel()
            try:
                await sup
            except asyncio.CancelledError:
                pass
        for t in list(self._tasks):
            t.cancel()

    def _alive(self, key: str, sock: Path) -> bool:
        p = self._procs.get(key)
        return bool(p and p.returncode is None and sock.exists())

    @property
    def running(self) -> bool:
        return self._alive("shell", self.s.terminal_socket)

    @property
    def cc_running(self) -> bool:
        """「CC 화면」 ttyd가 떠 있나(11-14) — 꺼져 있으면 탭이 까닭을 띄운다."""
        return self._alive("cc", self.s.ccscreen_socket)

    def _shell_cmd(self) -> str:
        return f"bash --rcfile {self.s.terminal_rcfile} -i"

    async def ensure_shell(self) -> None:
        """tmux 세션이 없으면 만든다(사람이 exit로 닫았을 때도). 브리지를 다시 띄워도 셸은 그대로 남는다."""
        try:
            await tmux(self.socket, "has-session", "-t", f"={self.s.terminal_tmux_session}")
            return
        except Refused:
            pass
        await tmux(self.socket, "new-session", "-d", "-s", self.s.terminal_tmux_session, "-x", "160", "-y", "40",
                   "-c", str(Path.home()), self._shell_cmd())
        log.info("터미널 셸 tmux 세션 만듦: %s", self.s.terminal_tmux_session)

    # ── 프로젝트마다 창(11-10 사용자 — "런슈즈에서 터미널을 열었는데 FOREMAN 터미널이 떴다") ──
    # 같은 tmux 세션 안에 프로젝트 이름의 창을 하나씩 둔다(없으면 그 저장소 폴더에서 만든다). 고르면 select-window로 그 창을 보인다.
    # 열 때 그 저장소로 cd를 쳐 넣는 방식은 쓰지 않는다 — 셸에서 명령이 돌고 있으면 그 입력으로 들어가고, 프로젝트를 오가면 앞 위치를 잃는다.
    # 처음부터 있던 창(이름 bash 등)은 FOREMAN 창으로 이름만 바꾼다. 프로젝트를 모르면(라운지 세션) 지금 보이는 창 그대로
    async def _repo_dir(self, project: str) -> str:
        if self.engine is not None:
            try:
                async with self.engine.connect() as c:
                    p = (await c.execute(text("SELECT repo_path FROM project WHERE name = :n"), {"n": project})).scalar()
                if p and Path(p).is_dir():
                    return str(p)
            except Exception as e:  # noqa: BLE001 — 폴더를 못 찾으면 집에서 연다
                log.warning("터미널 프로젝트 폴더 조회 실패 %s: %s", project, type(e).__name__)
        return str(Path.home())

    async def window_for(self, project: str | None) -> str:
        """그 프로젝트의 창 대상(=세션:번호). 없으면 만든다. project가 None이면 지금 보이는 창."""
        if not project:
            return self.target
        await self.ensure_shell()
        sess = self.s.terminal_tmux_session
        rows = [ln.split("\t", 1) for ln in (await tmux(self.socket, "list-windows", "-t", f"={sess}",
                                                       "-F", "#{window_index}\t#{window_name}")).splitlines() if "\t" in ln]
        for idx, name in rows:
            if name == project:
                return f"={sess}:{idx}"
        if project == "foreman" and rows and rows[0][1] not in TERM_PROJECTS:
            await tmux(self.socket, "rename-window", "-t", f"={sess}:{rows[0][0]}", "foreman")   # 처음부터 있던 창
            return f"={sess}:{rows[0][0]}"
        out = await tmux(self.socket, "new-window", "-d", "-P", "-F", "#{window_index}", "-t", f"={sess}:", "-n", project,
                         "-c", await self._repo_dir(project), "-e", f"FOREMAN_PROJECT={project}", self._shell_cmd())
        log.info("터미널 창 만듦: %s (%s)", project, out.strip())
        return f"={sess}:{out.strip()}"

    # ── 탭마다 보이는 창(11-10 사용자 — "방을 옮기면 터미널도 그 방 프로젝트로") ──
    # tmux의 "보이는 창"은 세션 하나에 하나라, 모든 탭이 기준 세션에 붙어 있던 때는 한 탭 · CC 부탁이 창을 바꾸면 다른 탭도 끌려갔다.
    # 이제 ttyd가 연결마다 deploy/shell/foreman-term-view로 그룹 세션 <기준>-v-<탭>을 만든다 — 창(셸)은 함께, 보이는 창은 탭마다.
    # 화면은 탭 id를 iframe 주소와 /open · /window에 같이 준다. 탭 id가 없으면(옛 화면 · screen.py) 기준 세션 — 전과 같다
    def view_name(self, tab: str | None) -> str | None:
        return f"{self.s.terminal_tmux_session}-v-{tab}" if tab and TAB_RE.match(tab) else None

    async def _view(self, tab: str | None, wait: float = 0.0) -> str | None:
        """그 탭의 그룹 세션 대상(=이름:) — 아직 없으면 wait초까지 기다린다(iframe이 막 붙는 중일 수 있다). 끝내 없으면 None."""
        name = self.view_name(tab)
        if not name:
            return None
        for i in range(max(1, int(wait / 0.1) + 1)):
            try:
                await tmux(self.socket, "has-session", "-t", f"={name}")
                return f"={name}:"
            except Refused:
                if i * 0.1 >= wait:
                    break
                await asyncio.sleep(0.1)
        return None

    async def sweep_views(self, min_age: float = 30.0, prefix: str | None = None) -> list[str]:
        """붙은 사람 없이 남은 그룹 세션을 치운다 — 보통은 destroy-unattached로 사라지지만, 붙기 전에 끊기면 남는다.
        막 만들어져 아직 붙는 중인 것(min_age초 안)은 두고 본다. 창 · 셸은 기준 세션에 그대로 남는다.
        prefix=CC_VIEW_PREFIX면 「CC 화면」 탭 세션(ccv-<탭>) — 창(CC)은 CC 세션 쪽에 그대로 남는다."""
        pre = prefix or f"{self.s.terminal_tmux_session}-v-"
        try:
            rows = (await tmux(self.socket, "list-sessions", "-F",
                               "#{session_name}\t#{session_attached}\t#{session_created}")).splitlines()
        except Refused:
            return []
        gone = []
        now = time.time()
        for ln in rows:
            p = ln.split("\t")
            if len(p) == 3 and p[0].startswith(pre) and p[1] == "0" and now - float(p[2] or 0) >= min_age:
                try:
                    await tmux(self.socket, "kill-session", "-t", f"={p[0]}")
                    gone.append(p[0])
                except Refused:
                    pass
        if gone:
            log.info("터미널 남은 탭 세션 치움: %s", ", ".join(gone))
        if prefix == CC_VIEW_PREFIX:
            await self.release_cc_windows()
        return gone

    async def release_cc_windows(self) -> list[str]:
        """「CC 화면」이 보는 동안 묶은 창 크기(window-size manual, 표시 @foreman_ccview)를 보는 CC 화면 세션이 없는데 남아 있으면
        쉴 때 크기(CC_REST_SIZE, 80×24)로 되돌리고 푼다 — 보기 스크립트가 마지막에 하는 것과 같다.
        보통은 foreman-cc-view가 연결이 끝날 때 하지만, 죽거나(kill -9) 함께 끝나 서로 남겨 둔 경우가 있다."""
        try:
            rows = [ln.split("\t") for ln in (await tmux(self.socket, "list-windows", "-a", "-F",
                                                         f"#{{window_id}}\t#{{{CC_MARK}}}\t#{{session_name}}")).splitlines()]
        except Refused:
            return []
        marked = {r[0] for r in rows if len(r) == 3 and r[1] == "1"}
        viewed = {r[0] for r in rows if len(r) == 3 and r[2].startswith(CC_VIEW_PREFIX)}
        freed = []
        for w in sorted(marked - viewed):
            try:
                await tmux(self.socket, "resize-window", "-t", w, "-x", str(CC_REST_SIZE[0]), "-y", str(CC_REST_SIZE[1]))
                await tmux(self.socket, "set-option", "-wu", "-t", w, "window-size")
                await tmux(self.socket, "set-option", "-wu", "-t", w, CC_MARK)
                freed.append(w)
            except Refused:
                pass
        if freed:
            log.info("CC 화면이 묶고 남긴 창 크기를 %dx%d로 되돌리고 풂: %s", *CC_REST_SIZE, ", ".join(freed))
        return freed

    async def open_project(self, project: str | None, tab: str | None = None) -> dict[str, Any]:
        """화면이 [터미널]을 열 때 · 방을 옮길 때 — 그 탭이 그 프로젝트 창을 보게 하고, 실제로 보이는 창 이름 · 폴더를 돌려준다
        (화면이 고른 것과 대 본다). 탭 세션이 아직 없으면 잠깐 기다리고, 끝내 없으면 기준 세션에서 고른다(view=False)."""
        t = await self.window_for(project)
        await self.sweep_views()
        vt = await self._view(tab, wait=3.0)
        if project:
            idx = t.rsplit(":", 1)[1]
            await tmux(self.socket, "select-window", "-t", f"{vt}{idx}" if vt else t)
        return {**await self.current(vt), "view": bool(vt)}

    # ── 스크롤(11-11 사용자 — 긴 출력의 앞부분을 볼 수 없다) ──
    # xterm 화면의 스크롤백은 tmux가 화면을 그려 주므로 비어 있다 → tmux 복사 모드로 올려 본다. 휠은 그룹 세션의 mouse on(foreman-term-view),
    # 단추는 이 길. -e: 맨 아래까지 내려오면 저절로 복사 모드가 끝난다(그대로 두고 쳐도 셸 입력이 먹히지 않는 일이 줄어든다)
    # wheel_up · wheel_down(11-11) — 휠 한 칸(3줄). mouse on을 껐으므로(끌어 고르기) 화면이 휠을 잡아 이 길로 보낸다
    SCROLL_ACTIONS = ("up", "down", "exit", "wheel_up", "wheel_down")
    WHEEL_LINES = "3"

    async def scroll(self, tab: str | None, action: str) -> dict[str, Any]:
        """그 탭의 보이는 창을 한 쪽 위로 · 아래로 · 복사 모드 끝내기. 탭 세션이 없으면 거절(기준 세션을 함께 끌어 가지 않는다)."""
        if action not in self.SCROLL_ACTIONS:
            raise Refused("모르는 스크롤 동작입니다")
        vt = await self._view(tab)
        if not vt:
            raise Refused("이 탭의 셸 연결을 찾지 못했습니다")
        inmode = (await tmux(self.socket, "display-message", "-p", "-t", vt, "#{pane_in_mode}")).strip() == "1"
        if action == "up":
            await tmux(self.socket, "copy-mode", "-eu", "-t", vt)
        elif action == "wheel_up":
            if not inmode:
                await tmux(self.socket, "copy-mode", "-e", "-t", vt)
            await tmux(self.socket, "send-keys", "-X", "-N", self.WHEEL_LINES, "-t", vt, "scroll-up")
        elif action == "wheel_down":
            if inmode:                                           # -e: 맨 아래에 닿으면 저절로 끝난다
                await tmux(self.socket, "send-keys", "-X", "-N", self.WHEEL_LINES, "-t", vt, "scroll-down")
        elif inmode:
            await tmux(self.socket, "send-keys", "-X", "-t", vt, "page-down" if action == "down" else "cancel")
        return {**await self.current(vt), "view": True}

    async def current_view(self, tab: str | None) -> dict[str, Any]:
        """그 탭이 지금 보는 창(바꾸지 않는다). 탭 세션이 없으면 기준 세션의 보이는 창(view=False)."""
        vt = await self._view(tab)
        return {**await self.current(vt), "view": bool(vt)}

    async def current(self, target: str | None = None) -> dict[str, Any]:
        """보이는 창(또는 target 창)의 이름 · 폴더 · 셸이 옛 설정인지(shell_old — 셸이 뜬 뒤 셸 설정 파일이 바뀌었다, 11-10)."""
        out = (await tmux(self.socket, "display-message", "-p", "-t", target or self.target,
                          "#{window_name}\t#{pane_current_path}\t#{pane_pid}\t#{pane_in_mode}")).strip().split("\t")
        name = out[0] if out else ""
        # scrolling = tmux 복사 모드(휠 · [위로])에 들어가 있다 — 이때 친 글은 셸이 아니라 복사 모드로 가므로 화면이 알린다(11-11)
        res: dict[str, Any] = {"project": name if name in TERM_PROJECTS else None, "window": name,
                               "cwd": out[1] if len(out) > 1 else None, "shell_old": None,
                               "scrolling": len(out) > 3 and out[3] == "1"}
        try:
            res["shell_old"] = self.shell_old(int(out[2]))
        except (IndexError, ValueError):
            pass
        return res

    # ── 열린 창을 새 셸로(11-10 사용자 — "열린 창을 새 셸로 바꾸는 방법이 화면에 있어야 한다. 매번 명령을 칠 수는 없다") ──
    # 셸 설정(foreman-bashrc · ~/.bashrc)은 셸이 뜰 때만 읽는다. 설정을 바꿔도 열린 창은 옛 프롬프트 그대로라, 셸이 뜬 시각과
    # 설정 파일 시각을 대 보고 막대에 알린다(조용한 고장). [새 셸]은 respawn-pane -k — 창을 만들 때와 같은 폴더 · FOREMAN_PROJECT · rcfile
    def config_files(self) -> list[Path]:
        return [Path(self.s.terminal_rcfile), Path.home() / ".bashrc"]

    def shell_old(self, pid: int) -> dict[str, Any] | None:
        """셸(pid)이 뜬 뒤 바뀐 셸 설정 파일 — 없으면 None. 못 재면 None(경고하지 않는다)."""
        started = _proc_start(pid)
        if started is None:
            return None
        newer = []
        for f in self.config_files():
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            if mt > started + 1:
                newer.append((mt, f.name))
        if not newer:
            return None
        mt, _ = max(newer)
        return {"files": [n for _, n in sorted(newer)], "changed_at": _iso(mt), "started_at": _iso(started)}

    async def busy(self, target: str) -> dict[str, Any]:
        """새 셸로 바꾸면 사라지는 것 — 돌고 있는 명령(셸이 아닌 것) · 입력 줄에 친 글. 둘 다 없으면 빈 dict."""
        cur = (await tmux(self.socket, "display-message", "-p", "-t", target,
                          "#{pane_current_command}\t#{cursor_y}\t#{pane_in_mode}")).strip().split("\t")
        cmd = cur[0] if cur else ""
        if cmd != "bash":
            return {"cmd": cmd or "?"}
        try:
            y = int(cur[1])
        except (IndexError, ValueError):
            return {}
        line = (await tmux(self.socket, "capture-pane", "-p", "-t", target, "-S", str(y), "-E", str(y))).rstrip("\n")
        typed = typed_text(line)
        return {"typed": mask_shell(self.mask, typed)[:60]} if typed else {}

    async def respawn(self, project: str, force: bool = False) -> dict[str, Any]:
        """그 프로젝트 창의 셸을 새로 띄운다. 명령이 돌고 있거나 친 글이 남아 있으면 force 없이는 띄우지 않고 까닭을 돌려준다."""
        t = await self.window_for(project)
        b = await self.busy(t)
        if b and not force:
            return {"respawned": False, "busy": b}
        await tmux(self.socket, "respawn-pane", "-k", "-t", t, "-c", await self._repo_dir(project),
                   "-e", f"FOREMAN_PROJECT={project}", self._shell_cmd())
        log.info("터미널 창 새 셸: %s%s", project, f" (끝낸 것: {b})" if b else "")
        return {"respawned": True, "busy": b, **await self.current(t)}

    # ── 셸 비우기(11-14 사용자 — [새 셸]은 눌러도 셸이 쌓인다고 느꼈다) ──
    # 셸을 새로 띄우지 않고 지금 셸의 화면과 스크롤백만 비운다. 셸이 입력을 기다리면 readline 화면 지우기(C-l — 기록에 `clear`가 남지 않는다),
    # 명령이 돌고 있으면 그 명령에 글을 넣지 않고 tmux 쪽 화면만 지운다(send-keys -R). 끝에 tmux 스크롤백(clear-history)
    CLEAR_SETTLE_S = 0.2

    async def clear(self, project: str, force: bool = False) -> dict[str, Any]:
        """그 프로젝트 창의 셸 화면 · 스크롤백을 비운다. 돌고 있는 명령이나 친 글이 있으면 force 없이는 비우지 않고 까닭을 돌려준다
        (친 글은 지워진다 · 돌고 있는 명령은 그대로 돌고 지난 출력만 지워진다)."""
        t = await self.window_for(project)
        b = await self.busy(t)
        if b and not force:
            return {"cleared": False, "busy": b}
        if (await tmux(self.socket, "display-message", "-p", "-t", t, "#{pane_in_mode}")).strip() == "1":
            await tmux(self.socket, "send-keys", "-t", t, "-X", "cancel")       # 스크롤(복사 모드) 중이면 먼저 나온다
        if b.get("cmd"):
            await tmux(self.socket, "send-keys", "-R", "-t", t)                # 명령의 입력으로는 아무것도 보내지 않는다
        else:
            if b.get("typed"):
                await tmux(self.socket, "send-keys", "-t", t, "C-e", "C-u")    # 친 글 지우기
            await tmux(self.socket, "send-keys", "-t", t, "C-l")
            await asyncio.sleep(self.CLEAR_SETTLE_S)                           # 지운 화면이 스크롤백으로 밀려난 뒤 지운다
        await tmux(self.socket, "clear-history", "-t", t)
        log.info("터미널 창 비움: %s%s", project, f" (지운 것: {b})" if b else "")
        return {"cleared": True, "busy": b, **await self.current(t)}

    # ── 「CC 화면」 탭(11-14 — 세션에 CC 창이 떠 있으면 FOREMAN에서 볼 수 없어 사용자가 VNC로 들어가 Esc로 닫았다) ──
    # 브라우저는 세션 번호만 보낸다. 붙을 tmux 창은 여기서 정한다: DB의 FOREMAN CC 세션 → 살아 있는 claude 프로세스 → 그 프로세스의
    # TMUX · TMUX_PANE(같은 tmux 서버) → 그 창이 실제로 있고 그 프로세스의 창인지. 그렇게 확인한 창만 ttyd 인자로 넘긴다
    async def cc_target(self, session_id: int) -> dict[str, Any]:
        """{ok, pane, tmux_session, size, running} — 안 되면 {ok: False, reason(「~습니다」), running}."""
        def no(reason: str) -> dict[str, Any]:
            return {"ok": False, "reason": reason, "running": self.cc_running}
        if self.engine is None:
            return no("DB가 없어 세션을 확인하지 못했습니다")
        async with self.engine.connect() as c:
            row = (await c.execute(text("SELECT cc_session_id, type FROM character_session WHERE id = :s"),
                                   {"s": session_id})).first()
        if row is None:
            return no("그런 세션이 없습니다")
        if row[1] != "agent" or not row[0]:
            return no("CC 세션이 아니라 CC 화면이 없습니다")
        ls = live_sessions(self.s.sessions_dir).get(row[0])
        if ls is None:
            return no("세션이 끝나 CC 화면이 없습니다(살아 있는 CC 프로세스가 없습니다)")
        if ls.state == "T":
            return no("멈춰 둔(Ctrl+Z) 세션이라 열지 않습니다 — 사용자가 일부러 멈춰 둔 세션입니다")
        te = _tmux_env(ls.pid)
        if te is None:
            return no("tmux 밖에서 도는 세션이라 CC 화면을 볼 수 없습니다")
        sock, pane = te
        if os.path.realpath(sock) != os.path.realpath(self.socket):
            return no("FOREMAN이 쓰는 tmux 서버가 아닌 곳에서 도는 세션이라 CC 화면을 볼 수 없습니다")
        if not PANE_RE.match(pane):
            return no("tmux 창 표시가 올바르지 않습니다")
        try:
            info = (await tmux(self.socket, "display-message", "-p", "-t", pane,
                               "#{session_name}\t#{pane_pid}\t#{window_width}x#{window_height}\t#{pane_dead}")).strip().split("\t")
        except Refused:
            return no("그 세션의 tmux 창을 찾지 못했습니다")
        if len(info) != 4 or not info[0]:                 # 없는 창이면 tmux가 오류 없이 빈 값을 돌려준다
            return no("그 세션의 tmux 창을 찾지 못했습니다")
        if info[3] == "1":
            return no("그 세션의 tmux 창이 닫혀 있습니다")
        try:
            ppid = int(info[1])
        except ValueError:
            return no("그 세션의 tmux 창을 읽지 못했습니다")
        if ppid != ls.pid and ppid not in _ancestors(ls.pid):
            return no("그 tmux 창의 CC가 이 세션이 아닙니다")
        return {"ok": True, "pane": pane, "tmux_session": info[0], "size": info[2], "running": self.cc_running}

    async def record_action(self, session_id: int, action: str, ok: bool, detail: str) -> None:
        """session_action 한 줄(「CC 화면」을 열고 닫은 것 — 키 하나하나는 남기지 않는다)."""
        if self.engine is None:
            return
        try:
            async with self.engine.begin() as c:
                await c.execute(text("INSERT INTO session_action (session_id, action, pid, ok, detail) "
                                     "VALUES (:s, :a, NULL, :o, :d)"),
                                {"s": session_id, "a": action, "o": ok, "d": detail[:512]})
        except Exception as e:  # noqa: BLE001 — 기록 실패가 화면을 막지 않는다
            log.warning("CC 화면 기록 실패 %s: %s", action, type(e).__name__)

    def _shell_ttyd_args(self) -> list[str]:
        # -a: iframe 주소의 ?arg=<탭>&arg=<프로젝트>가 명령 뒤에 붙는다(WS 프록시가 모양을 거른다) → 탭마다 그룹 세션(11-10)
        return [str(self.s.ttyd_bin), "-i", str(self.s.terminal_socket), "-W", "-a", "-b", "/terminal", "-m", "4", "-d", "3",
                "-t", "disableLeaveAlert=true", "-t", "disableResizeOverlay=true", "-t", "titleFixed=FOREMAN 셸",
                "-t", "fontSize=13",
                str(self.s.terminal_view_script), self.socket, self.s.terminal_tmux_session, str(self.s.terminal_rcfile)]

    def _cc_ttyd_args(self) -> list[str]:
        # 「CC 화면」(11-14) — -a 인자는 브라우저가 아니라 브리지 WS 프록시가 정한다(확인된 tmux 창 · 탭, api/terminal.py cc_ws)
        return [str(self.s.ttyd_bin), "-i", str(self.s.ccscreen_socket), "-W", "-a", "-b", "/ccscreen", "-m", "8", "-d", "3",
                "-t", "disableLeaveAlert=true", "-t", "disableResizeOverlay=true", "-t", "titleFixed=CC 화면",
                "-t", "fontSize=13",
                str(self.s.ccscreen_view_script), self.socket, "%dx%d" % CC_REST_SIZE]

    async def _supervise(self, key: str, args: list[str], sock: Path) -> None:
        """ttyd 하나를 띄우고 죽으면 다시 띄운다(1초부터 30초까지 늘려 가며). 셸 · CC 화면이 같은 틀을 쓴다."""
        delay = 1.0
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        logf = sock.parent / ("ttyd.log" if key == "shell" else f"ttyd-{key}.log")
        while not self._stopping:
            try:
                sock.unlink(missing_ok=True)
                with open(logf, "ab") as lf:
                    proc = self._procs[key] = await asyncio.create_subprocess_exec(
                        *args, stdin=asyncio.subprocess.DEVNULL, stdout=lf, stderr=lf, env=env)
                log.info("ttyd(%s) 시작 pid=%d (소켓 %s)", key, proc.pid, sock)
                started = time.monotonic()
                rc = await proc.wait()
                if self._stopping:
                    break
                log.warning("ttyd(%s) 종료 rc=%s — %.0f초 뒤 다시 띄운다(로그 %s)", key, rc, delay, logf)
                if time.monotonic() - started > 60:
                    delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("ttyd(%s) 띄우기 실패: %s: %s", key, type(e).__name__, str(e)[:200])
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)

    async def _shell_session(self) -> None:
        """셸 세션 행(type='shell', role helper) — 떠돌이 '미분류'에 붙인다(0017: 포먼은 자기 세션을 갖지 않는다, README 2.4).
        카드로 보이지 않는다(대시보드는 type='agent'만)."""
        assert self.engine is not None
        async with self.engine.begin() as c:
            ch = (await c.execute(text(
                "SELECT id FROM `character` WHERE project_id IS NULL AND name = '미분류' LIMIT 1"))).first()
            if ch is None:
                log.warning("미분류 캐릭터가 없다(0004) — 셸 기록은 세션 없이 남긴다")
                return
            self.shell_char_id = ch[0]
            r = (await c.execute(text(
                "SELECT id FROM character_session WHERE type = 'shell' AND detached_at IS NULL "
                "ORDER BY id DESC LIMIT 1"))).first()
            if r:
                self.shell_session_id = r[0]
                return
            res = await c.execute(text(
                "INSERT INTO character_session (character_id, type, role, tmux_pane, cwd, title, wake_reason) "
                "VALUES (:c, 'shell', 'helper', NULL, :cwd, '터미널 패널', 'user')"),
                {"c": self.shell_char_id, "cwd": str(Path.home())})
            self.shell_session_id = res.lastrowid
            log.info("셸 세션 행 만듦 id=%d", self.shell_session_id)

    # ── 쿠키(브라우저 → /terminal/) ──
    def new_cookie(self) -> str:
        now = time.time()
        self._cookies = {k: v for k, v in self._cookies.items() if v > now}
        tok = secrets.token_urlsafe(32)
        self._cookies[hashlib.sha256(tok.encode()).hexdigest()] = now + self.s.terminal_cookie_ttl_s
        return tok

    def cookie_ok(self, tok: str | None) -> bool:
        if not tok:
            return False
        exp = self._cookies.get(hashlib.sha256(tok.encode()).hexdigest())
        return bool(exp and exp > time.time())

    # ── 상태 ──
    def _expire(self) -> None:
        now = time.time()
        for rid in [k for k, r in self.pending.items() if r.done or now - r.created > self.s.terminal_request_ttl_s]:
            del self.pending[rid]

    def snapshot(self) -> dict[str, Any]:
        self._expire()
        return {"enabled": True, "running": self.running, "clients": self.clients,
                "pending": [r.public(self.s.terminal_request_ttl_s) for r in sorted(self.pending.values(), key=lambda r: r.id)]}

    def dismiss(self, rid: int) -> bool:
        r = self.pending.pop(rid, None)
        if r:
            self.publish({"type": "terminal_result", "request_id": rid, "session_id": r.session_id, "ok": False,
                          "dismissed": True, "msg": "닫음"})
            self.on_change()
        return r is not None

    def _spawn(self, coro: Any) -> None:
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _record(self, **kw: Any) -> None:
        try:
            self.pipeline.submit(EventIn(**kw))
        except Exception as e:  # noqa: BLE001 — 기록 실패가 셸을 막지 않는다
            log.warning("터미널 기록 실패: %s", type(e).__name__)

    # ── 사람이 친 명령 ──
    def on_shell(self, body: dict[str, Any]) -> dict[str, Any]:
        cmd = str(body.get("cmd") or "")[:20000]
        try:
            ec = int(body.get("exit") or 0)
        except (TypeError, ValueError):
            ec = -1
        cwd = str(body.get("cwd") or "")[:512]
        masked = mask_shell(self.mask, cmd)
        self._expire()
        match = None
        for r in sorted(self.pending.values(), key=lambda r: -r.id):
            if cmd_matches(cmd, r.head):
                match = r
                break
        self._record(source=EventSource.SHELL, type=EventType.SHELL_CMD, session_id=self.shell_session_id,
                     character_id=self.shell_char_id, target=masked,
                     status=EventStatus.DONE if ec == 0 else EventStatus.ERROR,
                     payload={"exit": ec, "cwd": cwd, **({"request_id": match.id} if match else {})})
        if match:
            match.done = True
            self.pending.pop(match.id, None)
            self._spawn(self._send_result(match, cmd, masked, ec))
        return {"recorded": True, "request_id": match.id if match else None}

    async def _capture(self, target: str | None = None) -> list[str]:
        out = await tmux(self.socket, "capture-pane", "-p", "-J", "-t", target or self.target, "-S", "-3000")
        return out.splitlines()

    async def _send_result(self, r: Request, cmd: str, masked: str, ec: int) -> None:
        try:
            await asyncio.sleep(0.4)    # 훅은 새 프롬프트가 찍히기 전에 불린다
            lines, found = extract_output(await self._capture(r.window), cmd, self.s.terminal_output_lines)
        except Exception as e:  # noqa: BLE001
            lines, found = [f"(출력을 읽지 못했다: {type(e).__name__})"], False
        n = self.s.terminal_output_lines
        cut = max(0, len(lines) - n)
        body = "\n".join(x[:400] for x in lines[cut:])
        body = mask_output(self.mask, body)[-6000:]
        msg = (f"[터미널 패널] 부탁한 명령을 사람이 터미널 패널에서 실행했다 — 종료 코드 {ec}\n"
               f"$ {masked}\n"
               f"출력(마스킹{', 앞 ' + str(cut) + '줄 생략' if cut else ''}{'' if found else ', 범위를 못 찾아 마지막 줄들'}):\n"
               f"```\n{body or '(출력 없음)'}\n```")
        ok, why, info = False, None, {}
        try:
            cc, transcript = await self._session_target(r.session_id)
            if not cc:
                raise Refused("CC 세션 ID가 없다")
            res = await deliver(cc, msg, sessions_dir=self.s.sessions_dir, transcript=transcript)
            ok = bool(res.get("delivered")) or bool(res.get("queued"))
            info = {"queued": res.get("queued"), "verified": bool(res.get("delivered"))}
            if not ok:
                why = "제출이 확인되지 않았다"
        except Refused as e:
            why = str(e)
        except Exception as e:  # noqa: BLE001
            why = f"{type(e).__name__}"
        log.info("터미널 결과 → session=%d: %s", r.session_id, "전달" if ok else f"전달 못 함({why})")
        self._record(source=EventSource.BRIDGE, type=EventType.TERM_RESULT, session_id=r.session_id,
                     turn_id=r.turn_id, target=masked, status=EventStatus.DONE if ok else EventStatus.ERROR,
                     payload={"request_id": r.id, "exit": ec, "lines": len(lines), "delivered": ok,
                              **({"refused": why} if why else {}), **info,
                              **({} if ok else {"output": body[-3000:]})})
        self.publish({"type": "terminal_result", "request_id": r.id, "session_id": r.session_id, "ok": ok,
                      "exit": ec, "msg": "세션에 전달했다" + (" (대기열)" if info.get("queued") else "") if ok
                      else f"세션에 전달 못 함 — {why}", "output": None if ok else body[-3000:]})
        self.on_change()

    async def _session_target(self, session_id: int) -> tuple[str | None, str | None]:
        if self.engine is None:
            raise Refused("DB 없음")
        async with self.engine.connect() as c:
            row = (await c.execute(text(
                "SELECT cs.cc_session_id, tf.path FROM character_session cs "
                "LEFT JOIN transcript_file tf ON tf.id = cs.transcript_file_id WHERE cs.id = :s"), {"s": session_id})).first()
        return (row[0], row[1]) if row else (None, None)

    # ── CC의 부탁 ──
    def on_turn_closed(self, session_id: int, turn_id: int, reason: str, by: str, note: str | None = None) -> None:
        if reason != "stop" or turn_id in self._seen_turns:
            return
        self._seen_turns.add(turn_id)
        if len(self._seen_turns) > 5000:
            self._seen_turns = set(list(self._seen_turns)[-1000:])
        self._spawn(self._check_turn(session_id, turn_id))

    async def _check_turn(self, session_id: int, turn_id: int) -> None:
        try:
            await asyncio.sleep(0.5)
            assert self.engine is not None
            async with self.engine.connect() as c:
                info = (await c.execute(text(
                    "SELECT cs.type, p.name, COALESCE(cs.custom_title, cs.title) FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                    "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :s"), {"s": session_id})).first()
                if info is None or info[0] != "agent":
                    return
                texts = [r[0] for r in (await c.execute(text(
                    "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE turn_id = :t "
                    "AND type = 'assistant_msg' AND subagent_id IS NULL "
                    "AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' ORDER BY id"), {"t": turn_id})).all() if r[0]]
            cands = find_requests("\n\n".join(texts)[-20000:])
            if not cands:
                return
            await self.request(session_id, turn_id, info[1], info[2], cands)
        except Exception as e:  # noqa: BLE001 — 감지 실패가 조립을 멈추면 안 된다
            log.warning("터미널 부탁 감지 실패 turn=%s: %s: %s", turn_id, type(e).__name__, str(e)[:200])

    async def request(self, session_id: int, turn_id: int, project: str | None, title: str | None,
                      cands: list[str]) -> Request:
        self._expire()
        for rid in [k for k, r in self.pending.items() if r.session_id == session_id]:   # 세션마다 최신 하나
            del self.pending[rid]
        fill, left = prefill_form(cands[0])
        r = Request(self._next, session_id, turn_id, project, title, cands[0], fill, left, cands[1:5])
        self._next += 1
        self.pending[r.id] = r
        r.prefilled, r.note = await self.prefill(r)
        log.info("터미널 부탁 #%d session=%d: %s (%s)", r.id, session_id, mask_shell(self.mask, fill),
                 "미리 채움" if r.prefilled else r.note)
        self._record(source=EventSource.BRIDGE, type=EventType.TERM_REQUEST, session_id=session_id, turn_id=turn_id,
                     target=mask_shell(self.mask, fill), status=EventStatus.WAITING,
                     payload={"request_id": r.id, "prefilled": r.prefilled, "blank": left > 0,
                              **({"note": r.note} if r.note else {}), **({"others": r.others} if r.others else {})})
        self.publish({"type": "terminal_request", "request": r.public(self.s.terminal_request_ttl_s)})
        self.on_change()
        return r

    async def prefill(self, r: Request) -> tuple[bool, str | None]:
        """셸 입력 줄을 비우고 채운다. Enter는 누르지 않는다. 셸이 다른 일을 하면(암호 입력 중 등) 건드리지 않는다."""
        try:
            await self.ensure_shell()
            # 부탁한 세션의 프로젝트 창에 채우고 그 창을 보인다(11-10). 프로젝트를 모르면 지금 보이는 창
            proj = r.project if r.project in TERM_PROJECTS else None
            t = r.window = await self.window_for(proj)
            if proj:
                await tmux(self.socket, "select-window", "-t", t)
            cur = (await tmux(self.socket, "display-message", "-p", "-t", t,
                              "#{pane_current_command}\t#{pane_in_mode}")).strip().split("\t")
            if len(cur) == 2 and cur[1] == "1":
                await tmux(self.socket, "send-keys", "-t", t, "-X", "cancel")   # 복사 모드에서 나온다
            if cur[0] != "bash":
                return False, f"셸이 다른 일을 하는 중({cur[0]}) — 직접 붙여넣는다"
            await tmux(self.socket, "send-keys", "-t", t, "C-e", "C-u")
            await tmux(self.socket, "send-keys", "-t", t, "-l", "--", r.fill)
            if r.left:
                await tmux(self.socket, "send-keys", "-t", t, "-N", str(r.left), "Left")
            return True, None
        except Refused as e:
            return False, str(e)
