"""「CC 화면」 띄우는 창(11-14) · [셸 비우기](11-14).

- deploy/shell/foreman-cc-view — 시험 전용 tmux 서버(own_sock)의 가짜 CC 세션에 pty로 붙여 본다: 그룹 세션 ccv-<탭>이 생기고,
  **CC 창이 띄운 창(pty) 크기를 따르며**(크기를 바꾸면 다시 맞춤, 둘이면 나중에 붙은 쪽), 연결이 끝나면 그룹 세션만 사라지고
  CC 창은 80×24로 돌아간다. 사람이 정한 window-size는 건드리지 않는다. 잘못된 인자는 붙지 않는다
- 실제 ttyd + 보기 스크립트에 WS로 붙어 고르기 메뉴를 화살표 · Enter · Esc로 다뤄 본다(test_ccscreen_ttyd_keys)
- TerminalManager.cc_target — 브라우저가 준 세션 번호를 DB · 살아 있는 프로세스 · tmux 창으로 확인한다(아무 tmux 세션에나 붙지 않게)
- TerminalManager.clear — 셸을 새로 띄우지 않고 화면 · 스크롤백만 비운다. 친 글 · 돌고 있는 명령이 있으면 먼저 묻는다

라이브 tmux 서버(기본 소켓)의 다른 세션에는 키를 보내지 않는다 — 모두 own_sock의 시험 세션에서 한다.
"""

import asyncio
import fcntl
import os
import signal
import struct
import subprocess
import termios
from types import SimpleNamespace

import pytest

import bridge.terminal as term
from bridge.inject import tmux
from bridge.terminal import TerminalManager

from test_terminal import MK, FakePipeline, _wait_pane, own_sock, shell  # noqa: F401 — 고정물


def _env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")} | {"TERM": "xterm-256color"}


async def _fake_cc(sock: str, name: str = "cc-fake", size: tuple[int, int] = (100, 30)) -> str:
    """가짜 CC 세션(창 하나, 셸) — 운영과 같은 window-size latest. 창 대상 %N을 돌려준다."""
    await tmux(sock, "new-session", "-d", "-s", name, "-x", str(size[0]), "-y", str(size[1]), "bash --norc -i")
    await tmux(sock, "set-option", "-g", "window-size", "latest")
    return (await tmux(sock, "display-message", "-p", "-t", f"={name}:", "#{pane_id}")).strip()


async def _size(sock: str, pane: str) -> str:
    return (await tmux(sock, "display-message", "-p", "-t", pane, "#{window_width}x#{window_height}")).strip()


async def _sessions(sock: str) -> dict[str, str]:
    rows = (await tmux(sock, "list-sessions", "-F", "#{session_name}\t#{session_attached}")).splitlines()
    return dict(r.split("\t") for r in rows)


async def _spawn_pty(args: list[str], cols: int = 200, rows: int = 50):
    import pty
    mfd, sfd = pty.openpty()
    fcntl.ioctl(sfd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))   # 브라우저처럼 큰 화면
    proc = await asyncio.create_subprocess_exec(*args, stdin=sfd, stdout=sfd, stderr=sfd, env=_env())
    os.close(sfd)
    return proc, mfd


async def _end(proc, mfd) -> None:
    """ttyd가 연결을 끝낼 때처럼 — pty를 닫고 HUP을 보낸다(tmux 손님이 끝나고 스크립트가 묶음을 푼다)."""
    os.close(mfd)
    proc.send_signal(signal.SIGHUP)
    try:
        await asyncio.wait_for(proc.wait(), 5)
    except TimeoutError:
        proc.kill()
        raise AssertionError("보기 스크립트가 끝나지 않았다") from None


def _script(shell) -> str:  # noqa: F811
    return str(shell.ccscreen_view_script)


async def _views(sock: str, tab: str) -> dict[str, str]:
    return {k: v for k, v in (await _sessions(sock)).items() if k.startswith(f"ccv-{tab}-")}


async def _wait_view(sock: str, tab: str) -> str:
    for _ in range(50):
        v = [k for k, a in (await _views(sock, tab)).items() if a == "1"]
        if v:
            return v[0]
        await asyncio.sleep(0.1)
    raise AssertionError(f"{tab} 그룹 세션에 붙지 않았다")


async def _wait_gone(sock: str, tab: str) -> None:
    for _ in range(30):
        if not await _views(sock, tab):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"{tab} 그룹 세션이 남았다")


async def _held(sock: str, pane: str) -> str:
    return (await tmux(sock, "show-options", "-wqv", "-t", pane, "window-size")).strip()


REST = "%dx%d" % term.CC_REST_SIZE                                 # 마지막 보기가 나가면 되돌리는 크기(80x24)


def _view(shell, sock, pane, tab) -> list[str]:  # noqa: F811
    return [_script(shell), sock, REST, pane, tab]               # 브리지 _cc_ttyd_args와 같은 차례(소켓 · 쉴 크기) + WS 인자


async def _until_size(sock: str, pane: str, want: str) -> str:
    for _ in range(50):
        if (got := await _size(sock, pane)) == want:
            return got
        await asyncio.sleep(0.1)
    return got


async def _until_free(sock: str, pane: str) -> None:
    for _ in range(30):
        if not await _held(sock, pane):
            return
        await asyncio.sleep(0.1)


async def _resize(sock: str, view: str, mfd, cols: int, rows: int) -> None:
    """ttyd가 브라우저 크기를 받았을 때처럼 — pty 크기를 바꾸고 그 보기의 tmux 손님에게만 SIGWINCH(새 크기를 서버에 알린다).
    시험 pty는 제어 단말이 아니라 커널이 SIGWINCH를 보내 주지 않는다."""
    fcntl.ioctl(mfd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    pid = int((await tmux(sock, "list-clients", "-t", f"={view}", "-F", "#{client_pid}")).split()[0])
    os.kill(pid, signal.SIGWINCH)


async def test_cc_view_fits_window_then_restores_80x24(shell, own_sock):  # noqa: F811
    pane = await _fake_cc(own_sock)
    assert await _size(own_sock, pane) == "100x30"
    proc, mfd = await _spawn_pty(_view(shell, own_sock, pane, "tabCCVIEW01"))
    try:
        view = await _wait_view(own_sock, "tabCCVIEW01")
        assert await _until_size(own_sock, pane, "200x50") == "200x50"   # 띄운 창(200×50) 크기 그대로 — 상태줄을 껐다
        assert await _held(own_sock, pane) == "manual"          # 보는 동안 묶는다(VNC 등 다른 손님이 크기를 바꾸지 않게)
        grp = (await tmux(own_sock, "display-message", "-p", "-t", f"={view}:", "#{session_group}")).strip()
        assert grp == "cc-fake"                                  # CC 세션과 창을 함께 쓰는 그룹 세션
        assert (await tmux(own_sock, "show-options", "-t", f"={view}:", "mouse")).strip() == "mouse off"
        assert (await tmux(own_sock, "show-options", "-t", f"={view}:", "status")).strip() == "status off"
        assert (await tmux(own_sock, "show-options", "-t", f"={view}:", "destroy-unattached")).strip() \
            == "destroy-unattached on"
        await _resize(own_sock, view, mfd, 132, 40)                            # 띄운 창 모서리를 끌어 놓음 → 한 번 다시 맞춘다
        assert await _until_size(own_sock, pane, "132x40") == "132x40"
    finally:
        await _end(proc, mfd)
    await _wait_gone(own_sock, "tabCCVIEW01")
    assert "cc-fake" in await _sessions(own_sock)                # 그룹 세션만 사라지고 CC 세션은 그대로
    await _until_free(own_sock, pane)
    assert await _held(own_sock, pane) == ""                     # 나가면 푼다(VNC 등 보통 손님은 전처럼)
    assert await _size(own_sock, pane) == REST == "80x24"        # 원래 100×30이었어도 쉴 때 크기로(사용자 11-14)
    assert (await tmux(own_sock, "show-options", "-wqv", "-t", pane, term.CC_MARK)).strip() == ""


async def test_two_views_later_wins_and_last_restores(shell, own_sock):  # noqa: F811
    """둘이 같은 창 — 나중에 붙은 쪽 크기(사용자 결정 11-14). 나중 것이 먼저 나가면 남은 쪽 크기로, 마지막이 나가면 80×24."""
    pane = await _fake_cc(own_sock)
    a = await _spawn_pty(_view(shell, own_sock, pane, "tabCCVIEWA1"), 200, 50)
    try:
        await _wait_view(own_sock, "tabCCVIEWA1")
        assert await _until_size(own_sock, pane, "200x50") == "200x50"
        b = await _spawn_pty(_view(shell, own_sock, pane, "tabCCVIEWB1"), 150, 45)
        try:
            await _wait_view(own_sock, "tabCCVIEWB1")
            assert await _until_size(own_sock, pane, "150x45") == "150x45"     # 나중에 붙은 B
        finally:
            await _end(*b)
        await _wait_gone(own_sock, "tabCCVIEWB1")
        assert await _until_size(own_sock, pane, "200x50") == "200x50"         # A가 아직 본다 — A 크기로
        assert await _held(own_sock, pane) == "manual"
    finally:
        await _end(*a)
    await _wait_gone(own_sock, "tabCCVIEWA1")
    await _until_free(own_sock, pane)
    assert await _held(own_sock, pane) == "" and await _size(own_sock, pane) == "80x24"


async def test_cc_view_leaves_human_window_size_alone(shell, own_sock):  # noqa: F811
    """사람이 정한 window-size(표시 없음)면 크기를 맞추지도 되돌리지도 않는다 — 보기만 한다."""
    pane = await _fake_cc(own_sock)
    await tmux(own_sock, "set-option", "-w", "-t", pane, "window-size", "manual")
    proc, mfd = await _spawn_pty(_view(shell, own_sock, pane, "tabCCVIEWH1"))
    try:
        await _wait_view(own_sock, "tabCCVIEWH1")
        await asyncio.sleep(0.5)
        assert await _size(own_sock, pane) == "100x30"
    finally:
        await _end(proc, mfd)
    await _wait_gone(own_sock, "tabCCVIEWH1")
    assert await _size(own_sock, pane) == "100x30" and await _held(own_sock, pane) == "manual"


async def test_bridge_releases_stale_hold(shell, own_sock):  # noqa: F811
    """보던 스크립트가 죽어(kill -9) 묶음이 남았다 — 브리지 치우기가 푼다. 남이 정한 window-size(표시 없음)는 건드리지 않는다."""
    pane = await _fake_cc(own_sock)
    other = await _fake_cc(own_sock, "cc-other")
    await tmux(own_sock, "set-option", "-w", "-t", pane, "window-size", "manual")
    await tmux(own_sock, "set-option", "-w", "-t", pane, term.CC_MARK, "1")
    await tmux(own_sock, "set-option", "-w", "-t", other, "window-size", "smallest")
    m = TerminalManager(None, shell, FakePipeline(), MK)
    m.socket = own_sock
    await m.sweep_views(min_age=0, prefix=term.CC_VIEW_PREFIX)
    assert await _held(own_sock, pane) == "" and await _held(own_sock, other) == "smallest"
    assert await _size(own_sock, pane) == "80x24" and await _size(own_sock, other) == "100x30"   # 쉴 때 크기로 되돌림


async def test_plain_attach_would_resize(own_sock):  # noqa: F811
    """대조 — ignore-size 없이 붙으면(window-size latest) 창이 붙은 화면 크기로 바뀐다. 위 시험이 뜻이 있다는 것."""
    pane = await _fake_cc(own_sock, "cc-plain")
    proc, mfd = await _spawn_pty(["tmux", "-S", own_sock, "attach-session", "-t", "=cc-plain"], 120, 40)
    try:
        for _ in range(50):
            if await _size(own_sock, pane) != "100x30":
                break
            await asyncio.sleep(0.1)
        assert await _size(own_sock, pane) == "120x39"            # 상태줄 한 줄을 뺀 높이
    finally:
        await _end(proc, mfd)


@pytest.mark.parametrize("pane,tab", [("cc-fake", "tabCCVIEW02"), ("%1;ls", "tabCCVIEW02"), ("%99999", "tabCCVIEW02"),
                                      ("%0", "../x")])
async def test_cc_view_refuses_bad_target(shell, own_sock, pane, tab):  # noqa: F811
    """모양이 틀리거나 없는 창 — 붙지 않고 까닭을 띄우고 끝낸다(그룹 세션을 만들지 않는다)."""
    await _fake_cc(own_sock)
    r = subprocess.run(_view(shell, own_sock, pane, tab), input=b"x", capture_output=True, env=_env(), timeout=10)
    assert r.returncode == 1
    assert "습니다" in r.stdout.decode()
    assert not [s for s in await _sessions(own_sock) if s.startswith("ccv-")]


async def test_cc_view_refuses_bad_rest_size(shell, own_sock):  # noqa: F811
    pane = await _fake_cc(own_sock)
    r = subprocess.run([_script(shell), own_sock, "80x24;ls", pane, "tabCCVIEW03"], input=b"x", capture_output=True,
                       env=_env(), timeout=10)
    assert r.returncode == 1 and "쉴 때 크기" in r.stdout.decode()


# ── 실제 ttyd + 보기 스크립트에 WS로 — 고르기 창을 화살표 · Enter · Esc로(11-14 사용자 확인 항목) ─────────
MENU = r"""items=(one two three); i=0; msg=start
draw() { printf '\e[H\e[2J'; for k in 0 1 2; do if ((k == i)); then printf '> %s\n' "${items[k]}"; else printf '  %s\n' "${items[k]}"; fi; done; printf '%s\n' "$msg"; }
draw
while IFS= read -rsn1 c; do
  if [[ $c == $'\e' ]]; then
    if read -rsn2 -t 0.3 r; then
      [[ $r == '[B' ]] && i=$(( (i + 1) % 3 )); [[ $r == '[A' ]] && i=$(( (i + 2) % 3 )); msg=moving
    else msg=menu-closed; draw; break; fi
  elif [[ -z $c ]]; then msg="picked-${items[i]}"
  fi
  draw
done
exec sleep 600
"""


def _ttyd_bin():
    """원본 폴더의 .tools/ttyd — worktree에는 없다(.tools는 링크하지 않음). 없으면 건너뛴다."""
    from bridge.config import REPO
    cands = [REPO / ".tools" / "ttyd"]
    if REPO.parent.name == ".worktrees":
        cands.append(REPO.parent.parent / ".tools" / "ttyd")
    return next((p for p in cands if os.access(p, os.X_OK)), None)


async def _screen_has(sock: str, pane: str, needle: str, tries: int = 50) -> str:
    for _ in range(tries):
        scr = await tmux(sock, "capture-pane", "-p", "-t", pane)
        if needle in scr:
            return scr
        await asyncio.sleep(0.1)
    raise AssertionError(f"화면에 {needle!r}이 없다:\n{scr}")


async def test_ccscreen_ttyd_keys(shell, own_sock):  # noqa: F811
    """실제 ttyd(_cc_ttyd_args 그대로) + 새 보기 스크립트를 시험 소켓에 띄우고 WS로 붙는다 — 라이브 세션에는 키를 보내지 않는다.
    붙으면 CC 창 = 띄운 창 크기, ↓ · Enter · Esc가 고르기 메뉴에 가고, 크기를 바꾸면 따라가고, 닫으면 80×24로 돌아온다."""
    import json

    from websockets.asyncio.client import unix_connect
    ttyd = _ttyd_bin()
    if ttyd is None:
        pytest.skip("ttyd 없음")
    d = os.path.dirname(own_sock)
    menu = os.path.join(d, "menu.sh")
    with open(menu, "w") as f:
        f.write(MENU)
    await tmux(own_sock, "new-session", "-d", "-s", "cc-menu", "-x", "100", "-y", "30", f"bash {menu}")
    await tmux(own_sock, "set-option", "-g", "window-size", "latest")
    pane = (await tmux(own_sock, "display-message", "-p", "-t", "=cc-menu:", "#{pane_id}")).strip()
    await _screen_has(own_sock, pane, "> one")
    csock = os.path.join(d, "cc.sock")
    m = TerminalManager(None, shell.model_copy(update={"ttyd_bin": ttyd, "ccscreen_socket": csock}), FakePipeline(), MK)
    m.socket = own_sock
    args = m._cc_ttyd_args()
    assert args[-1] == "80x24"                                    # 쉴 크기는 브리지 상수 하나에서 고정 인자로
    proc = await asyncio.create_subprocess_exec(*args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_env())
    try:
        for _ in range(50):
            if os.path.exists(csock):
                break
            await asyncio.sleep(0.1)
        seen = bytearray()

        async def pump(ws):
            async for msg in ws:
                b = msg if isinstance(msg, bytes) else msg.encode()
                if b[:1] == b"0":
                    seen.extend(b[1:])
        uri = f"ws://localhost/ccscreen/ws?arg={pane.replace('%', '%25')}&arg=tabTTYDKEY1"
        async with unix_connect(csock, uri, subprotocols=["tty"]) as ws:
            reader = asyncio.create_task(pump(ws))
            await ws.send(json.dumps({"AuthToken": "", "columns": 120, "rows": 36}))
            assert await _until_size(own_sock, pane, "120x36") == "120x36"   # 띄운 창 크기로
            await ws.send(b"0\x1b[B")                                         # ↓
            await _screen_has(own_sock, pane, "> two")
            await ws.send(b"0\r")                                             # Enter
            await _screen_has(own_sock, pane, "picked-two")
            await ws.send(b"1" + json.dumps({"columns": 90, "rows": 28}).encode())   # 모서리를 끌어 놓음
            assert await _until_size(own_sock, pane, "90x28") == "90x28"
            await ws.send(b"0\x1b")                                           # Esc — 고르기 창을 닫는다
            await _screen_has(own_sock, pane, "menu-closed")
            for _ in range(30):
                if b"menu-closed" in seen:
                    break
                await asyncio.sleep(0.1)
            assert b"picked-two" in seen and b"menu-closed" in seen          # 브라우저 쪽(ttyd 출력)에도 바뀐 화면이 왔다
            reader.cancel()
        await _wait_gone(own_sock, "tabTTYDKEY1")
        await _until_free(own_sock, pane)
        assert await _size(own_sock, pane) == "80x24"                 # 닫으면 80×24
        assert await _held(own_sock, pane) == ""
    finally:
        proc.terminate()
        await proc.wait()
        if os.path.exists(csock):
            os.unlink(csock)
        os.unlink(menu)


# ── cc_target — 붙을 곳은 브리지가 정한다 ───────────────────────────
class _Conn:
    def __init__(self, row):
        self.row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return SimpleNamespace(first=lambda: self.row)


class _Engine:
    def __init__(self, row):
        self.row = row

    def connect(self):
        return _Conn(self.row)


async def _mgr(shell, sock, row, *, live=None, tmux_env=None, monkeypatch):  # noqa: F811
    m = TerminalManager(_Engine(row), shell, FakePipeline(), MK)
    m.socket = sock
    monkeypatch.setattr(term, "live_sessions", lambda d: live or {})
    monkeypatch.setattr(term, "_tmux_env", lambda pid: tmux_env)
    return m


async def test_cc_target_checks(shell, own_sock, monkeypatch):  # noqa: F811
    pane = await _fake_cc(own_sock)
    shell_pid = int((await tmux(own_sock, "display-message", "-p", "-t", pane, "#{pane_pid}")).strip())
    LS = lambda pid, st="S": {"cc-1": SimpleNamespace(pid=pid, state=st)}   # noqa: E731

    async def t(row, **kw):
        m = await _mgr(shell, own_sock, row, monkeypatch=monkeypatch, **kw)
        return await m.cc_target(5)

    assert (await t(None))["reason"] == "그런 세션이 없습니다"
    assert "CC 세션이 아니라" in (await t(("cc-1", "shell")))["reason"]
    assert "세션이 끝나" in (await t(("cc-1", "agent")))["reason"]
    assert "멈춰 둔" in (await t(("cc-1", "agent"), live=LS(shell_pid, "T")))["reason"]
    assert "tmux 밖" in (await t(("cc-1", "agent"), live=LS(shell_pid)))["reason"]
    assert "tmux 서버가 아닌" in (await t(("cc-1", "agent"), live=LS(shell_pid), tmux_env=("/tmp/other-sock", pane)))["reason"]
    assert "표시가 올바르지" in (await t(("cc-1", "agent"), live=LS(shell_pid), tmux_env=(own_sock, "cc-fake")))["reason"]
    assert "찾지 못했습니다" in (await t(("cc-1", "agent"), live=LS(shell_pid), tmux_env=(own_sock, "%99999")))["reason"]
    # 그 창의 프로세스가 이 세션 claude(또는 그 조상)가 아니다 — 다른 창을 가리키는 TMUX_PANE
    assert "이 세션이 아닙니다" in (await t(("cc-1", "agent"), live=LS(1), tmux_env=(own_sock, pane)))["reason"]
    ok = await t(("cc-1", "agent"), live=LS(shell_pid), tmux_env=(own_sock, pane))
    assert ok["ok"] and ok["pane"] == pane and ok["tmux_session"] == "cc-fake" and ok["size"] == "100x30"
    assert ok["running"] is False                                 # 시험에서는 ttyd를 띄우지 않았다
    m = TerminalManager(None, shell, FakePipeline(), MK)
    assert "DB가 없어" in (await m.cc_target(5))["reason"]


def test_cc_ws_args_only_session_and_tab():
    """WS 주소에서 받는 것은 세션 번호와 탭뿐 — tmux 대상 · 다른 인자는 거절."""
    from starlette.datastructures import QueryParams

    from bridge.api.terminal import _cc_args

    def a(q):
        return _cc_args(SimpleNamespace(query_params=QueryParams(q)))
    assert a("arg=981&arg=ctabAAAA01") == (981, "ctabAAAA01")
    assert a("arg=%251&arg=ctabAAAA01") is None                   # %1(tmux 창)을 직접 줄 수 없다
    assert a("arg=cc-foreman&arg=ctabAAAA01") is None
    assert a("arg=981") is None
    assert a("arg=981&arg=..%2Fx") is None
    assert a("arg=981&arg=ctabAAAA01&arg=x") is None
    assert a("") is None


# ── 셸 비우기 ──────────────────────────────────────────────
async def test_clear_asks_first_then_clears(shell, own_sock):  # noqa: F811
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    t = await m.window_for("runshoes")
    await _wait_pane(m, t, "[foreman] $")
    pid1 = (await tmux(own_sock, "display-message", "-p", "-t", t, "#{pane_pid}")).strip()
    for i in range(60):                                          # 스크롤백이 생기게
        await tmux(own_sock, "send-keys", "-t", t, "-l", f"echo old-out-{i}")
        await tmux(own_sock, "send-keys", "-t", t, "Enter")
    await _wait_pane(m, t, "old-out-59\n")
    hist = int((await tmux(own_sock, "display-message", "-p", "-t", t, "#{history_size}")).strip())
    assert hist > 0
    await tmux(own_sock, "send-keys", "-t", t, "-l", "half")      # 친 글이 남아 있다
    await _wait_pane(m, t, "$ half")
    assert await m.clear("runshoes") == {"cleared": False, "busy": {"typed": "half"}}
    assert "old-out-59" in await tmux(own_sock, "capture-pane", "-p", "-t", t)   # 비우지 않았다
    r = await m.clear("runshoes", force=True)
    assert r["cleared"] and r["project"] == "runshoes"
    await asyncio.sleep(0.3)
    scr = await tmux(own_sock, "capture-pane", "-p", "-J", "-t", t, "-S", "-")
    assert "old-out" not in scr and "half" not in scr and "[foreman] $" in scr
    assert (await tmux(own_sock, "display-message", "-p", "-t", t, "#{history_size}")).strip() == "0"
    assert (await tmux(own_sock, "display-message", "-p", "-t", t, "#{pane_pid}")).strip() == pid1   # 같은 셸(새로 띄우지 않음)
    # 돌고 있는 명령 — 묻고, 비워도 명령은 그대로 돈다(그 입력으로 아무것도 보내지 않는다)
    await tmux(own_sock, "send-keys", "-t", t, "-l", "sleep 30")
    await tmux(own_sock, "send-keys", "-t", t, "Enter")
    for _ in range(30):
        if (await m.busy(t)).get("cmd") == "sleep":
            break
        await asyncio.sleep(0.1)
    assert await m.clear("runshoes") == {"cleared": False, "busy": {"cmd": "sleep"}}
    r = await m.clear("runshoes", force=True)
    assert r["cleared"] and (await m.busy(t)).get("cmd") == "sleep"
    await m.stop()
