"""「CC 화면」 탭(11-14) · [셸 비우기](11-14).

- deploy/shell/foreman-cc-view — 시험 전용 tmux 서버(own_sock)의 가짜 CC 세션에 pty로 붙여 본다: 그룹 세션 ccv-<탭>이 생기고,
  **CC 창 크기가 바뀌지 않으며**(attach -f ignore-size, window-size latest), 연결이 끝나면 그룹 세션만 사라진다. 잘못된 인자는 붙지 않는다
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


async def test_cc_view_attaches_without_resizing_then_cleans_up(shell, own_sock):  # noqa: F811
    pane = await _fake_cc(own_sock)
    assert await _size(own_sock, pane) == "100x30"
    proc, mfd = await _spawn_pty([_script(shell), own_sock, pane, "tabCCVIEW01"])
    try:
        view = await _wait_view(own_sock, "tabCCVIEW01")
        await asyncio.sleep(0.5)
        assert await _size(own_sock, pane) == "100x30"          # 200×50 화면이 붙어도 CC 창 크기는 그대로
        assert await _held(own_sock, pane) == "manual"          # 보는 동안만 묶는다
        grp = (await tmux(own_sock, "display-message", "-p", "-t", f"={view}:", "#{session_group}")).strip()
        assert grp == "cc-fake"                                  # CC 세션과 창을 함께 쓰는 그룹 세션
        assert (await tmux(own_sock, "show-options", "-t", f"={view}:", "mouse")).strip() == "mouse off"
        assert (await tmux(own_sock, "show-options", "-t", f"={view}:", "destroy-unattached")).strip() \
            == "destroy-unattached on"
    finally:
        await _end(proc, mfd)
    await _wait_gone(own_sock, "tabCCVIEW01")
    assert "cc-fake" in await _sessions(own_sock)                # 그룹 세션만 사라지고 CC 세션은 그대로
    assert await _size(own_sock, pane) == "100x30"
    for _ in range(20):
        if not await _held(own_sock, pane):
            break
        await asyncio.sleep(0.1)
    assert await _held(own_sock, pane) == ""                     # 나가면 묶음을 푼다(VNC 등 보통 손님은 전처럼)


async def test_two_views_keep_hold_until_last_leaves(shell, own_sock):  # noqa: F811
    pane = await _fake_cc(own_sock)
    a = await _spawn_pty([_script(shell), own_sock, pane, "tabCCVIEWA1"])
    b = await _spawn_pty([_script(shell), own_sock, pane, "tabCCVIEWB1"], 150, 45)
    try:
        await _wait_view(own_sock, "tabCCVIEWA1")
        await _wait_view(own_sock, "tabCCVIEWB1")
        await _end(*a)
        await _wait_gone(own_sock, "tabCCVIEWA1")
        await asyncio.sleep(0.3)
        assert await _held(own_sock, pane) == "manual"          # B가 아직 본다
        assert await _size(own_sock, pane) == "100x30"
    finally:
        await _end(*b)
    await _wait_gone(own_sock, "tabCCVIEWB1")
    for _ in range(20):
        if not await _held(own_sock, pane):
            break
        await asyncio.sleep(0.1)
    assert await _held(own_sock, pane) == "" and await _size(own_sock, pane) == "100x30"


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
    r = subprocess.run([_script(shell), own_sock, pane, tab], input=b"x", capture_output=True, env=_env(), timeout=10)
    assert r.returncode == 1
    assert "습니다" in r.stdout.decode()
    assert not [s for s in await _sessions(own_sock) if s.startswith("ccv-")]


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
