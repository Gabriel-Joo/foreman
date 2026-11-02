"""터미널 패널(7단계) — CC에게 시킬 수 없는 일(sudo 암호 · SSH 패스프레이즈 · 레지스트리 로그인)을 대시보드에서 끝낸다.

구성
  tmux 세션 foreman-shell  ← bash --rcfile deploy/shell/foreman-bashrc (사람이 직접 치는 셸)
  ttyd(.tools/ttyd)        ← 그 tmux 세션에 붙는다. TCP 포트를 열지 않고 UNIX 소켓(.run/ttyd.sock, 디렉토리 0700)에만
  브리지 /terminal/*       ← 쿠키 인증을 거쳐 ttyd 소켓으로 그대로 넘긴다(xterm.js 화면 그대로 — 파싱하지 않는다)

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
from bridge.inject import Refused, deliver, tmux
from bridge.mask import Masker
from bridge.models import EventIn, EventSource, EventStatus, EventType

log = logging.getLogger("foreman.terminal")

PROMPT_MARK = "[foreman] "      # foreman-bashrc의 PS1 머리 — 출력 범위를 찾는 표지
COOKIE = "foreman_term"

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


def find_requests(msg: str) -> list[str]:
    """assistant 글에서 사람에게 부탁한 명령(사람이 쳐야 하는 것만). 부탁하는 말이 없으면 `! 명령` 꼴만 인정한다."""
    if not msg:
        return []
    out: list[str] = []
    bang: set[str] = set()
    prose = _FENCE.sub(" ", msg)

    def add(c: str, is_bang: bool = False) -> None:
        c = _clean(c)
        if c and not c.startswith("#") and len(c) <= 500 and HUMAN_CMD.search(c) and c not in out:
            out.append(c)
        if is_bang and c:
            bang.add(c)

    for m in _FENCE.finditer(msg):
        if m.group(1).lower() not in _SHELL_LANGS:
            continue
        body = re.sub(r"\\\n\s*", " ", m.group(2))     # 줄 이음
        for line in body.splitlines():
            add(line, line.strip().startswith("!"))
    for m in _INLINE.finditer(prose):
        add(m.group(1), m.group(1).strip().startswith("!"))
    for m in _BANG_LINE.finditer(prose):
        add(m.group(1).strip("`"), True)
    if CUE.search(prose):
        return out
    return [c for c in out if c in bang]


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
    if ls and ls[-1].startswith(PROMPT_MARK) and _norm(cmd)[:60] not in _norm(ls[-1]):
        end -= 1
    key = _norm(cmd)[:60]
    for i in range(end - 1, -1, -1):
        if ls[i].startswith(PROMPT_MARK) and key and key in _norm(ls[i]):
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
        self._proc: asyncio.subprocess.Process | None = None
        self._sup: asyncio.Task[None] | None = None
        self._stopping = False
        self.shell_session_id: int | None = None
        self.shell_char_id: int | None = None
        self.clients = 0

    # ── 수명 ──
    async def start(self) -> None:
        d = self.s.terminal_socket.parent
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(d, 0o700)
        await self.ensure_shell()
        if self.engine is not None:
            await self._shell_session()
        if not os.access(self.s.ttyd_bin, os.X_OK):
            log.warning("ttyd 없음(%s) — 터미널 패널 화면은 꺼진다. 기록 · 감지는 그대로", self.s.ttyd_bin)
            return
        self._sup = asyncio.create_task(self._supervise(), name="foreman-ttyd")

    async def stop(self) -> None:
        self._stopping = True
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                async with asyncio.timeout(3):
                    await self._proc.wait()
            except TimeoutError:
                self._proc.kill()
        if self._sup:
            self._sup.cancel()
            try:
                await self._sup
            except asyncio.CancelledError:
                pass
        for t in list(self._tasks):
            t.cancel()

    @property
    def running(self) -> bool:
        return bool(self._proc and self._proc.returncode is None and self.s.terminal_socket.exists())

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

    async def _supervise(self) -> None:
        delay = 1.0
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        args = [str(self.s.ttyd_bin), "-i", str(self.s.terminal_socket), "-W", "-b", "/terminal", "-m", "4", "-d", "3",
                "-t", "disableLeaveAlert=true", "-t", "disableResizeOverlay=true", "-t", "titleFixed=FOREMAN 터미널",
                "-t", "fontSize=13",
                "tmux", "-S", self.socket, "new-session", "-A", "-s", self.s.terminal_tmux_session,
                "-c", str(Path.home()), self._shell_cmd()]
        logf = self.s.terminal_socket.parent / "ttyd.log"
        while not self._stopping:
            try:
                self.s.terminal_socket.unlink(missing_ok=True)
                with open(logf, "ab") as lf:
                    self._proc = await asyncio.create_subprocess_exec(
                        *args, stdin=asyncio.subprocess.DEVNULL, stdout=lf, stderr=lf, env=env)
                log.info("ttyd 시작 pid=%d (소켓 %s)", self._proc.pid, self.s.terminal_socket)
                started = time.monotonic()
                rc = await self._proc.wait()
                if self._stopping:
                    break
                log.warning("ttyd 종료 rc=%s — %.0f초 뒤 다시 띄운다(로그 %s)", rc, delay, logf)
                if time.monotonic() - started > 60:
                    delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("ttyd 띄우기 실패: %s: %s", type(e).__name__, str(e)[:200])
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)

    async def _shell_session(self) -> None:
        """셸 세션 행(type='shell') — 포먼 프로젝트의 포먼에 붙인다. 카드로 보이지 않는다(대시보드는 type='agent'만)."""
        assert self.engine is not None
        async with self.engine.begin() as c:
            ch = (await c.execute(text(
                "SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id "
                "WHERE p.name = 'foreman' AND c.current_role = 'foreman' LIMIT 1"))).first()
            if ch is None:
                log.warning("포먼 캐릭터가 없다 — 셸 기록은 세션 없이 남긴다")
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

    async def _capture(self) -> list[str]:
        out = await tmux(self.socket, "capture-pane", "-p", "-J", "-t", self.target, "-S", "-3000")
        return out.splitlines()

    async def _send_result(self, r: Request, cmd: str, masked: str, ec: int) -> None:
        try:
            await asyncio.sleep(0.4)    # 훅은 새 프롬프트가 찍히기 전에 불린다
            lines, found = extract_output(await self._capture(), cmd, self.s.terminal_output_lines)
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
                    "SELECT cs.type, p.name, cs.title FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
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
            cur = (await tmux(self.socket, "display-message", "-p", "-t", self.target,
                              "#{pane_current_command}\t#{pane_in_mode}")).strip().split("\t")
            if len(cur) == 2 and cur[1] == "1":
                await tmux(self.socket, "send-keys", "-t", self.target, "-X", "cancel")   # 복사 모드에서 나온다
            if cur[0] != "bash":
                return False, f"셸이 다른 일을 하는 중({cur[0]}) — 직접 붙여넣는다"
            await tmux(self.socket, "send-keys", "-t", self.target, "C-e", "C-u")
            await tmux(self.socket, "send-keys", "-t", self.target, "-l", "--", r.fill)
            if r.left:
                await tmux(self.socket, "send-keys", "-t", self.target, "-N", str(r.left), "Left")
            return True, None
        except Refused as e:
            return False, str(e)
