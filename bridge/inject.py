"""CC 세션에 입력 주입 — 방법 C (README 3.1)

    tmux load-buffer -b <buf> -                 # 텍스트를 버퍼에(stdin)
    tmux paste-buffer -p -r -d -b <buf> -t <pane>   # 괄호 붙여넣기, LF 유지, 버퍼 지움
    (잠깐 대기)
    tmux send-keys -t <pane> Enter              # 제출

tmux는 셸이 아니라 인자 목록으로 부른다(따옴표 · $ · 백틱 · 백슬래시 · 한글이 그대로 지난다).

주입 전에 막는 것 — 하나라도 걸리면 아무것도 보내지 않고 이유를 돌려준다(로그에도 남긴다):
  - 살아 있는 CC 프로세스가 아니다(~/.claude/sessions/<pid>.json + procStart)
  - 정지(T, SUSPENDED) — 포그라운드가 bash라 프롬프트가 셸 명령으로 실행된다
  - tmux 밖 세션 — 프로세스 환경변수 TMUX · TMUX_PANE이 없다
  - pane의 포그라운드가 claude가 아니다(#{pane_current_command})
  - 그 pane의 claude가 이 세션의 프로세스가 아니다(pane_pid의 자손인지)
바쁜 세션(CC가 sessions json에 status=busy)에 보낸 입력은 새 턴이 아니라 대기열로 들어간다 — queued=True로 알린다.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from bridge.liveness import LiveSession, live_sessions

log = logging.getLogger("foreman.inject")

TMUX_TIMEOUT_S = 3.0


@dataclass(frozen=True)
class Target:
    socket: str       # tmux 서버 소켓 경로
    pane: str         # %N
    pid: int          # claude 프로세스
    session_id: str


@dataclass
class Result:
    ok: bool
    reason: str | None = None
    queued: bool = False
    target: Target | None = None
    first_char: str | None = None
    steps: list[str] = field(default_factory=list)


class Refused(Exception):
    pass


def _tmux_env(pid: int) -> tuple[str, str] | None:
    """claude 프로세스 환경변수에서 TMUX(소켓,서버pid,세션) · TMUX_PANE만 읽는다. 다른 값은 보지 않는다."""
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return None
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if item.startswith((b"TMUX=", b"TMUX_PANE=")):
            k, _, v = item.partition(b"=")
            env[k.decode()] = v.decode(errors="replace")
    if "TMUX" not in env or "TMUX_PANE" not in env:
        return None
    return env["TMUX"].split(",")[0], env["TMUX_PANE"]


def _ancestors(pid: int, limit: int = 32) -> list[int]:
    out = []
    for _ in range(limit):
        try:
            ppid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if ppid <= 1:
            break
        out.append(ppid)
        pid = ppid
    return out


async def tmux(socket: str, *args: str, stdin: bytes | None = None, timeout: float = TMUX_TIMEOUT_S) -> str:
    proc = await asyncio.create_subprocess_exec(
        "tmux", "-S", socket, *args,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        async with asyncio.timeout(timeout):
            out, err = await proc.communicate(stdin)
    except TimeoutError:
        proc.kill()
        raise Refused(f"tmux가 {timeout:g}초 동안 응답하지 않았습니다({args[0]})") from None
    if proc.returncode != 0:
        raise Refused(f"tmux {args[0]}에 실패했습니다: {err.decode(errors='replace').strip()[:200]}")
    return out.decode(errors="replace")


async def resolve(session_id: str, sessions_dir: str | Path) -> tuple[Target, LiveSession, bool]:
    """주입 가능한 대상인지 확인하고 (대상, 프로세스, 바쁨 여부)를 돌려준다. 안 되면 Refused."""
    live = live_sessions(sessions_dir)
    ls = live.get(session_id)
    if ls is None:
        raise Refused("세션이 끝났습니다(살아 있는 CC 프로세스가 없습니다)")
    if ls.state == "T":
        raise Refused("멈춘 세션입니다. 지금 보내면 셸 명령으로 실행되므로 보내지 않았습니다")
    te = _tmux_env(ls.pid)
    if te is None:
        raise Refused("tmux 밖에서 도는 세션이라 보낼 수 없습니다")
    socket, pane = te
    info = (await tmux(socket, "display-message", "-p", "-t", pane,
                       "#{pane_current_command}\t#{pane_pid}\t#{pane_dead}")).strip().split("\t")
    if len(info) != 3:
        raise Refused(f"tmux 창 정보를 읽지 못했습니다({pane})")
    cmd, pane_pid, dead = info
    if dead == "1":
        raise Refused(f"tmux 창이 닫혀 있습니다({pane})")
    if cmd != "claude":
        raise Refused(f"그 tmux 창에서 지금 claude가 아니라 {cmd}이(가) 돌고 있어 보내지 않았습니다")
    if int(pane_pid) != ls.pid and int(pane_pid) not in _ancestors(ls.pid):
        raise Refused("그 tmux 창의 claude가 이 세션이 아닙니다")
    busy = _status(sessions_dir, ls.pid) == "busy"
    return Target(socket, pane, ls.pid, session_id), ls, busy


def _status(sessions_dir: str | Path, pid: int) -> str | None:
    try:
        return json.loads(Path(sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError):
        return None


# 첫 글자 처리 — 3단계 실측(CC 2.1.316, 괄호 붙여넣기 + Enter):
#   '/' → 슬래시 명령으로 실행된다(모델에 안 감)          → 앞에 공백 한 칸. command=True일 때만 그대로
#   '!' → bash 모드로 셸 명령이 실행된다                    → 11-09부터 입력 API가 bang_check(승인 규칙 ask · sudo · 여러 줄만 막음)
#                                                            를 거쳐 command=True로 그대로 보낸다. 전엔 늘 공백을 붙였다
#   '@' → 새지 않는다(끝에 와도 자동완성이 Enter를 먹지 않았다) → 그대로
#   폭 없는 공백(U+200B) 보호는 쓰지 않는다 — Enter가 제출되지 않고 입력 칸에 남아 다음 입력과 이어 붙었다
GUARD = " "
LEADING = ("/", "!")


def guarded(text: str, command: bool = False) -> tuple[str, bool]:
    """(보낼 텍스트, 보호를 붙였나). command=True면 '/' · '!'를 그대로(명령으로) — '!'는 입력 API가 승인 규칙을 먼저 본다(11-09).
    전엔 '!'에 늘 공백을 붙였다: 사용자가 보낸 "!bash …dump.sh" · "!scripts/load-prod.sh --apply" 7건이 실행되지 않고
    모델에게 글로 갔고, 아무도 몰랐다(조용한 고장)."""
    first = text[:1]
    if first in LEADING and not command:
        return GUARD + text, True
    return text, False


def bang_check(text: str, decide: Any) -> str:
    """'!' 셸 명령(bash 모드)을 보내도 되나 — 보낼 명령을 돌려주고, 안 되면 Refused(이유 · 어떻게 하면 되는지).
    bash 모드는 CC 도구 호출이 아니라 승인 훅(approval.toml)을 거치지 않는다. 그래서 같은 명령을 Bash 도구로 쳤을 때
    승인을 묻는 규칙에 걸리면 여기서 막는다 — 그 밖은 보낸다(11-09 사용자: 명령에 공백은 당연히 들어간다, 막을 것만 막아라)."""
    cmd = text[1:].strip()
    if not cmd:
        raise Refused("! 뒤에 명령이 없습니다 — 예: !ls -la")
    if "\n" in cmd:
        raise Refused("! 명령은 한 줄만 보냅니다 — 여러 줄은 && 로 잇거나 스크립트 파일로 실행해 주세요")
    if re.search(r"(^|[;&|]\s*)sudo\b", cmd):
        raise Refused("sudo는 비밀번호를 물어 그 세션 입력이 멈춥니다 — 서버 터미널에서 직접 쳐 주세요(CLAUDE.md: sudo는 사람이 친다)")
    d = decide("Bash", {"command": cmd})
    if d.verdict == "ask":
        raise Refused(f"승인 규칙 '{d.rule}'에 걸리는 명령입니다({d.reason}). ! 명령은 승인 창을 거치지 않아 패널에서 보내지 않습니다 — "
                      f"그 세션에 \"{cmd[:60]} 실행해 줘\"처럼 맡기면 승인을 묻고 실행합니다")
    return "!" + cmd


def recorded_forms(sent: str) -> set[str]:
    """트랜스크립트 user 줄에 남을 모양. 여러 줄 붙여넣기는 <pasted_content id=…>로 감싸이고(정규식으로 확인),
    탭은 공백 4칸이 된다(실측). 앞뒤 공백 · 빈 줄은 CC가 다듬어 기록한다(11-05 실측: "확인\n" → "확인",
    끝에 빈 줄 둘인 붙여넣기 → 감싼 안쪽 끝이 한 줄) — 그래서 앞뒤 공백을 빼고 맞댄다."""
    s = sent.replace("\t", "    ").strip()
    if s.startswith("!"):
        # 11-09 실측 — bash 모드('!')는 "<bash-input>명령</bash-input>"으로 남는다(사용자가 패널에서 !echo HELLO WORLD)
        return {s, f"<bash-input>{s[1:].strip()}</bash-input>"}
    return {s}


_WRAP = re.compile(r'\n\n<pasted_content id="([0-9a-f]+)">\n(.*)\n</pasted_content id="\1">\n', re.S)


def unwrap(s: str) -> str:
    m = _WRAP.fullmatch(s)
    return m.group(2) if m else s


def find_delivery(path: str, offset: int, sent: str) -> dict | None:
    """offset 뒤에 보낸 글이 프롬프트(user 줄) 또는 대기열(queue-operation enqueue)로 기록됐는지."""
    forms = recorded_forms(sent)
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return None
    for raw in data.split(b"\n"):
        if not raw.strip() or b'"type":"api-request' in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        t = d.get("type")
        if t == "user" and not d.get("isMeta"):
            c = (d.get("message") or {}).get("content")
            if isinstance(c, str) and unwrap(c).strip() in forms:
                return {"as": "prompt", "uuid": d.get("uuid"), "prompt_id": d.get("promptId")}
        elif t == "queue-operation" and d.get("operation") == "enqueue":
            c = d.get("content")
            if isinstance(c, str) and unwrap(c).strip() in forms:
                return {"as": "queued"}
    return None

_locks: dict[str, asyncio.Lock] = {}


async def paste_and_submit(t: Target, text: str, *, delay_s: float = 0.15, guard: str | None = None) -> list[str]:
    """방법 C. 보낸 그대로 붙여넣는다 — 첫 글자 보호는 guarded()로 먼저 한다(guard 인자는 실측 스크립트용)."""
    if guard and text[:1] in ("/", "!", "@"):
        text = guard + text
    buf = f"foreman-{uuid.uuid4().hex[:12]}"
    lock = _locks.setdefault(f"{t.socket}:{t.pane}", asyncio.Lock())
    steps = []
    async with lock:  # 같은 pane에 두 입력이 섞이지 않게
        await tmux(t.socket, "load-buffer", "-b", buf, "-", stdin=text.encode("utf-8"))
        steps.append("load-buffer")
        try:
            await tmux(t.socket, "paste-buffer", "-p", "-r", "-d", "-b", buf, "-t", t.pane)
            steps.append("paste-buffer -p -r")
        except Refused:
            await tmux(t.socket, "delete-buffer", "-b", buf)
            raise
        await asyncio.sleep(delay_s)
        await tmux(t.socket, "send-keys", "-t", t.pane, "Enter")
        steps.append("Enter")
    return steps


async def deliver(session_id: str, text: str, *, sessions_dir: str | Path, transcript: str | None,
                  command: bool = False, delay_s: float = 0.15, verify_s: float = 10.0) -> dict:
    """확인 → 보호 → 방법 C → 제출 확인. 거부면 Refused. 결과 dict: queued · guarded · delivered(as/uuid)."""
    if not text.strip():
        # 빈칸 · 공백만 — 붙여넣을 것 없이 Enter만 가는 셈이다. 입력 칸에 CC의 프롬프트 제안(회색)이 떠 있으면
        # Enter가 그 제안을 제출하는지 문서에 없다(11-05) — 사람이 쓰지 않은 글이 실행될 수 있으니 보내지 않는다
        raise Refused("빈 입력입니다 — 공백이나 줄바꿈만으로는 보내지 않습니다")
    t, _ls, busy = await resolve(session_id, sessions_dir)
    escs = await clear_screen(t, busy)
    send, guarded_ = guarded(text, command)
    offset = os.path.getsize(transcript) if transcript and os.path.exists(transcript) else None
    steps = await paste_and_submit(t, send, delay_s=delay_s)
    delivered = None
    if transcript:
        loop = asyncio.get_running_loop()
        end = loop.time() + verify_s
        while loop.time() < end:
            await asyncio.sleep(0.25)
            path_ok = os.path.exists(transcript)
            delivered = find_delivery(transcript, offset or 0, send) if path_ok else None
            if delivered:
                break
    out = {"pane": t.pane, "queued": busy or bool(delivered and delivered["as"] == "queued"), "guarded": guarded_,
           "steps": (["Escape"] * escs) + steps, "esc": escs, "delivered": delivered, "chars": len(text), "lines": text.count("\n") + 1}
    if transcript and not delivered:
        # 기록에서 못 찾았다 — 화면의 입력 칸을 직접 본다(11-05). 보낸 글 앞부분이 입력 칸(❯ 줄 아래)에 보이면 남은 것,
        # 안 보이면 제출된 것(기록 모양이 달라 못 맞췄을 뿐 — 11-05 끝 공백 건이 그랬다). 사람이 쓰던 글일 수 있어 지우지 않는다
        out["left_in_box"] = await left_in_box(t, send)
        log.warning("주입 제출 확인 안 됨 %s %s(%d자) — 입력 칸에 %s", session_id[:8], t.pane, len(text),
                    "남아 있다" if out["left_in_box"] else "없다(제출된 것으로 보임)" if out["left_in_box"] is False else "모름")
    return out


ESC_TRIES = 3
ESC_WAIT_S = 0.6          # Esc 뒤 화면이 바뀔 때까지(끝내기에서 쓰던 값)


async def clear_screen(t: Target, busy: bool, tries: int = ESC_TRIES) -> int:
    """입력 줄(❯)이 없으면 CC가 설정 · 사용량 같은 다른 화면을 띄운 것이다 — 거기 붙여넣은 글은 제출되지 않는다
    (11-08 cc-foreman-2 /usage, 11-09 하루 세 번 — 사용자: "보내기 전에 Esc를 자동으로 보내고 다시 시도"). 사람이 하듯
    Esc로 닫고 입력 줄이 돌아오는지 본다(최대 tries번, 끝내기와 같은 방식). 보낸 Esc 수를 돌려준다.
    **작업 중이면 Esc를 보내지 않는다** — Esc는 작업을 끊고, 승인 · 질문 창(도구가 도는 중이라 busy)에서는 거부 · 취소가 된다.
    그래도 안 풀리면 Refused — 화면에 그 이유가 뜬다(조용히 실패하지 않게)."""
    if await prompt_showing(t):
        return 0
    if busy:
        raise Refused("CC가 입력 줄 대신 다른 화면을 띄워 두고 있습니다. 작업 중이라 Esc를 보내지 않았습니다"
                      "(작업이 끊길 수 있습니다) — 그 세션 터미널에서 확인해 주세요")
    for n in range(1, tries + 1):
        await tmux(t.socket, "send-keys", "-t", t.pane, "Escape")
        await asyncio.sleep(ESC_WAIT_S)
        if await prompt_showing(t):
            log.warning("입력 줄이 없어 Esc %d번으로 닫음 %s", n, t.pane)
            return n
    log.warning("Esc %d번에도 입력 줄이 돌아오지 않음 %s", tries, t.pane)
    raise Refused(f"CC가 입력 줄 대신 다른 화면을 띄워 두고 있고, Esc를 {tries}번 보내도 닫히지 않았습니다 — "
                  "그 세션 터미널에서 확인해 주세요")


async def prompt_showing(t: Target) -> bool:
    """화면에 CC 입력 줄(❯)이 있나. 작업 중에도 입력 줄은 남아 있다(11-08 실측 — 다른 pane 4개)."""
    screen = await tmux(t.socket, "capture-pane", "-p", "-J", "-t", t.pane)
    return any(ln.lstrip().startswith("❯") for ln in screen.splitlines())


async def left_in_box(t: Target, sent: str) -> bool | None:
    """입력 칸(마지막 ❯ 줄부터 아래)에 보낸 글 앞부분이 보이나. 화면을 못 읽으면 None."""
    try:
        screen = await tmux(t.socket, "capture-pane", "-p", "-J", "-t", t.pane)
    except Refused:
        return None
    lines = screen.rstrip("\n").splitlines()
    idx = max((i for i, ln in enumerate(lines) if ln.lstrip().startswith("❯")), default=None)
    if idx is None:
        return None
    box = re.sub(r"\s+", "", "".join(lines[idx:]))
    head = re.sub(r"\s+", "", sent.strip())[:20]
    return bool(head) and head in box
