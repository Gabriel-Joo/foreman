"""7단계 터미널 패널 — 부탁 감지 · 미리 채우기 · 마스킹 · 출력 범위(순수 함수), 시험용 tmux 셸에서 채우기 → 결과,
브리지를 거친 ttyd(쿠키 · Origin · HTTP · WS).

tmux를 쓰는 시험은 시험 전용 세션(foreman-shell-test-<pid>)만 만들고 지운다. 운영 셸(foreman-shell) · ttyd 소켓은 건드리지 않는다.
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path

import pymysql
import pytest

from bridge.config import Settings, get_settings
from bridge.inject import Refused, tmux
from bridge.mask import Masker
from bridge.terminal import (TerminalManager, cmd_matches, default_tmux_socket, extract_output, find_requests,
                             mask_shell, prefill_form, typed_text)

MK = Masker(env_paths=[])


# ── 부탁 감지 ──────────────────────────────────────────────
def test_find_sudo_in_code_block_with_cue():
    msg = "ttyd를 apt로 깔려면 sudo가 필요합니다. 아래 명령을 실행해 주세요.\n\n```bash\nsudo apt install -y ttyd\n```"
    assert find_requests(msg) == ["sudo apt install -y ttyd"]


def test_find_inline_and_bang():
    assert find_requests("터미널에서 `sudo systemctl restart foo` 쳐 주세요") == ["sudo systemctl restart foo"]
    # 부탁하는 말이 없어도 `! 명령` 꼴은 부탁이다(CC가 권하는 모양)
    assert find_requests("다음을 입력하면 됩니다: `! sudo journalctl -u x`") == ["sudo journalctl -u x"]
    assert find_requests("! ssh-add ~/.ssh/id_ed25519") == ["ssh-add ~/.ssh/id_ed25519"]


def test_find_login_commands():
    msg = "레지스트리 로그인이 필요합니다. 직접 실행해 주세요:\n```\ndocker login harbor.local -u admin\n```"
    assert find_requests(msg) == ["docker login harbor.local -u admin"]
    assert find_requests("please run `gh auth login` first") == ["gh auth login"]


def test_find_ignores_without_cue_or_human_command():
    # 설명 · 기록에 나온 sudo — 부탁하는 말이 없다
    assert find_requests("어제 `sudo apt install ttyd`로 깔았던 것과 같은 버전입니다.") == []
    # 부탁은 있지만 사람이 칠 필요가 없는 명령
    assert find_requests("다음을 실행해 주세요: `ls -al`") == []
    # 셸이 아닌 코드 블록
    assert find_requests("실행해 주세요\n```python\nos.system('sudo reboot')\n```") == []


def test_find_ignores_feature_description():
    # 7단계 실측: 기능을 설명한 보고가 부탁으로 잡혀 셸에 `echo 값 | sudo -S`가 채워졌다.
    # 부탁하는 말은 따옴표 안(인용)이었고, 명령과 멀리 떨어져 있었다
    msg = ("- **기록:** 마스킹 대상: `--password 값`, `echo 값 | sudo -S`, URL에 든 `user:암호@`.\n"
           "- **셸은 캐릭터로 안 보입니다:** `character_session.type='shell'`.\n"
           "- **부탁 감지:** 턴이 끝나면 아래 세 조건을 봅니다.\n"
           "  - sudo, ssh-add, docker login처럼 사람이 쳐야 하는 명령\n"
           "  - \"실행해 주세요\" 같은 부탁하는 말\n")
    assert find_requests(msg) == []
    assert find_requests('"이 명령 실행해 주세요" 감지: `sudo true`') == []
    # 멀리 떨어진 부탁은 그 명령의 부탁이 아니다
    assert find_requests("`sudo a b`" + "가" * 400 + " 다음을 실행해 주세요: `ls`") == []


def test_find_multiple_and_comments():
    msg = "실행해 주세요.\n```bash\n# 먼저\n$ sudo systemctl stop a\nsudo systemctl start b\n```"
    assert find_requests(msg) == ["sudo systemctl stop a", "sudo systemctl start b"]


def test_find_chained_sudo():
    assert find_requests("실행 부탁드립니다: `cd /opt/x && sudo make install`") == ["cd /opt/x && sudo make install"]


# ── 미리 채우기 ────────────────────────────────────────────
def test_prefill_plain_sudo_keeps_command():
    assert prefill_form("sudo apt install -y ttyd") == ("sudo apt install -y ttyd", 0)


def test_prefill_blanks_password_placeholder_cursor_there():
    fill, left = prefill_form("docker login -u admin -p <password> harbor.local")
    assert fill == "docker login -u admin -p  harbor.local"
    assert fill[: len(fill) - left] == "docker login -u admin -p "


def test_prefill_blanks_flag_values_and_masked():
    assert prefill_form("mysql -u root -pS3cret db") == ("mysql -u root -p db", 3)
    assert prefill_form("vault login --password=«masked»") == ("vault login --password=", 0)
    assert prefill_form("echo hi\nsudo x") == ("echo hi sudo x", 0)   # 줄바꿈이 Enter가 되지 않게


# ── 마스킹 ────────────────────────────────────────────────
@pytest.mark.parametrize("cmd,leak", [
    ("docker login -u admin -p hunter22 harbor.local", "hunter22"),
    ("mysql -u root -phunter22 foreman", "hunter22"),
    ("echo hunter22 | sudo -S apt update", "hunter22"),
    ("echo 'hunter22' | docker login -u a --password-stdin r", "hunter22"),
    ("git clone https://user:hunter22@github.com/x/y", "hunter22"),
    ("curl -u admin:hunter22 http://x", "hunter22"),
    ("sshpass -p hunter22 ssh host", "hunter22"),
    ("helm registry login r --password hunter22", "hunter22"),
    ("MYSQL_PASSWORD=hunter22 ./run.sh", "hunter22"),
])
def test_mask_shell(cmd, leak):
    out = mask_shell(MK, cmd)
    assert leak not in out and "«masked" in out


def test_mask_shell_keeps_plain_commands():
    for c in ("sudo apt install -y ttyd", "mysql -p foreman", "docker login --password-stdin r"):
        assert mask_shell(MK, c) == c


# ── 맞춰 보기 · 출력 범위 ─────────────────────────────────────
def test_cmd_matches():
    assert cmd_matches("docker login -u admin -p s3cret harbor.local", "docker login -u admin -p ")
    assert cmd_matches("sudo  apt install -y ttyd", "sudo apt install -y ttyd")
    assert cmd_matches("sudo apt install ttyd", "sudo apt install -y ttyd")      # 앞 세 단어
    assert not cmd_matches("sudo apt update", "sudo apt install -y ttyd")
    assert not cmd_matches("ls", "sudo apt install -y ttyd")


def test_extract_output():
    lines = ["[foreman] u@h:~$ ls", "a", "[foreman] u@h:~$ sudo apt install ttyd", "[sudo] password for u: ",
             "Reading package lists...", "Done", "[foreman] u@h:~$ ", ""]
    out, found = extract_output(lines, "sudo apt install ttyd", 60)
    assert found and out == ["[sudo] password for u:", "Reading package lists...", "Done"]   # 줄 끝 공백은 지운다
    out, found = extract_output(["x", "y", "[foreman] $ "], "nothing here", 1)
    assert not found and out == ["y"]


def test_extract_output_project_window_prompt():
    """11-10 — 프로젝트 창 프롬프트는 머리가 창 이름("[runshoes] ")이고, venv를 다시 켜면 "(llm_env) "가 앞에 붙는다."""
    lines = ["[runshoes] (llm_env) ~/r$ sudo ls /root", "a", "b", "(llm_env) [runshoes] ~/r$ "]
    out, found = extract_output(lines, "sudo ls /root", 60)
    assert found and out == ["a", "b"]


def test_typed_text():
    assert typed_text("[foreman] (llm_env) ~/x$") == ""                  # capture-pane이 끝 공백을 지운다
    assert typed_text("[petmint-rag-chatbot] ~/p$ sf") == "sf"
    assert typed_text("kopo17@host:~/p$ git st  ") == "git st"           # 옛 프롬프트도
    assert typed_text("") == ""
    assert typed_text("ong-input-continued") == "ong-input-continued"   # 긴 입력이 줄을 넘긴 줄


# ── 시험용 tmux 셸: 채우기 → 사람이 친다 → 결과 ────────────────────
class FakePipeline:
    def __init__(self):
        self.events, self.msgs = [], []

    def submit(self, ev):
        self.events.append(ev)

    def publish(self, m):
        self.msgs.append(m)


@pytest.fixture
def shell(tmp_path: Path):
    name = f"foreman-shell-test-{os.getpid()}"
    rc = tmp_path / "rc"
    rc.write_text("PS1='[foreman] $ '\nHISTFILE=\n", encoding="utf-8")
    s = get_settings().model_copy(update={
        "terminal_tmux_session": name, "terminal_rcfile": rc, "ttyd_bin": tmp_path / "no-ttyd",
        "terminal_socket": tmp_path / "run" / "ttyd.sock"})
    yield s
    subprocess.run(["tmux", "-S", default_tmux_socket(), "kill-session", "-t", f"={name}"], capture_output=True)


async def _screen(m: TerminalManager) -> str:
    return await tmux(m.socket, "capture-pane", "-p", "-J", "-t", m.target)


async def _wait_for(m: TerminalManager, needle: str, timeout: float = 5.0) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        scr = await _screen(m)
        if needle in scr:
            return scr
        await asyncio.sleep(0.1)
    raise AssertionError(f"화면에 {needle!r} 없음:\n{await _screen(m)}")


async def test_prefill_then_result(shell):
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    await m.start()
    await _wait_for(m, "[foreman] $")
    r = await m.request(7, 70, "foreman", "시험", ["echo ok-a --password <pw> ok-b"])
    assert r.prefilled and r.fill == "echo ok-a --password  ok-b" and r.left == len(" ok-b")
    await _wait_for(m, "echo ok-a --password  ok-b")
    # 커서가 비밀번호 자리에 있다 — 거기에 친 글이 들어간다
    await tmux(m.socket, "send-keys", "-t", m.target, "-l", "s3cretpw")
    await tmux(m.socket, "send-keys", "-t", m.target, "Enter")
    scr = await _wait_for(m, "ok-a --password s3cretpw ok-b\n")
    assert "[foreman] $ echo ok-a --password s3cretpw ok-b" in scr
    res = m.on_shell({"cmd": "echo ok-a --password s3cretpw ok-b", "exit": 0, "cwd": "/tmp"})
    assert res["request_id"] == r.id and r.id not in m.pending
    ev = p.events[-1]
    assert ev.type == "shell_cmd" and "s3cretpw" not in ev.target and ev.payload["request_id"] == r.id
    for _ in range(40):
        if any(x["type"] == "terminal_result" for x in p.msgs):
            break
        await asyncio.sleep(0.1)
    out = next(x for x in p.msgs if x["type"] == "terminal_result")
    assert out["ok"] is False and "DB 없음" in out["msg"]          # 세션이 없으니 화면에만
    assert out["output"].strip() == "ok-a --password s3cretpw ok-b"   # 출력은 마스킹 규칙(URL · 토큰 모양)에 안 걸린다
    await m.stop()


async def test_project_windows(shell):
    """11-10 — 프로젝트마다 창: 고르면 그 창이 보이고(없으면 만든다 · FOREMAN_PROJECT), 처음 창은 foreman으로 이름만 바뀐다.
    부탁은 부탁한 세션의 프로젝트 창에 채운다."""
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    await m.start()
    await _wait_for(m, "[foreman] $")
    cur = await m.open_project("runshoes")
    assert cur["project"] == "runshoes" and cur["window"] == "runshoes"
    await tmux(m.socket, "send-keys", "-t", m.target, "-l", "echo P=$FOREMAN_PROJECT")
    await tmux(m.socket, "send-keys", "-t", m.target, "Enter")
    await _wait_for(m, "P=runshoes")
    again = await m.open_project("runshoes")               # 두 번 골라도 창은 하나
    assert again["window"] == "runshoes"
    names = (await tmux(m.socket, "list-windows", "-t", f"={shell.terminal_tmux_session}", "-F", "#{window_name}")).split()
    assert names.count("runshoes") == 1 and len(names) == 2
    cur = await m.open_project("foreman")                  # 처음 창 — 새로 만들지 않고 이름만
    assert cur["project"] == "foreman"
    names = (await tmux(m.socket, "list-windows", "-t", f"={shell.terminal_tmux_session}", "-F", "#{window_name}")).split()
    assert sorted(names) == ["foreman", "runshoes"]
    assert (await m.open_project(None))["project"] == "foreman"      # 모르면 지금 창 그대로
    r = await m.request(9, 90, "runshoes", None, ["echo from-runshoes"])
    assert r.prefilled and r.window and (await m.current())["project"] == "runshoes"
    await _wait_for(m, "echo from-runshoes")
    await m.stop()


@pytest.fixture
def own_sock():
    """시험만의 tmux 서버(소켓) — 라이브 tmux 서버(기본 소켓)에 세션을 만들지 않는다. 짧은 경로(UNIX 소켓 108자)."""
    import tempfile
    d = tempfile.mkdtemp(prefix="ft", dir="/tmp")
    sock = f"{d}/t"
    yield sock
    subprocess.run(["tmux", "-S", sock, "kill-server"], capture_output=True)
    Path(sock).unlink(missing_ok=True)
    os.rmdir(d)


async def _pane(m: TerminalManager, t: str, fmt: str) -> str:
    return (await tmux(m.socket, "display-message", "-p", "-t", t, fmt)).strip()


async def _wait_pane(m: TerminalManager, t: str, needle: str, tries: int = 50) -> str:
    for _ in range(tries):
        scr = await tmux(m.socket, "capture-pane", "-p", "-J", "-t", t)
        if needle in scr:
            return scr
        await asyncio.sleep(0.1)
    raise AssertionError(f"{t}에 {needle!r} 없음")


async def test_respawn_asks_first_then_new_shell(shell, own_sock):
    """11-10 [새 셸] — 친 글 · 돌고 있는 명령이 있으면 force 없이는 띄우지 않고 까닭을 돌려준다. 띄우면 같은 창 · FOREMAN_PROJECT · 새 pid.
    셸이 뜬 뒤 셸 설정 파일이 바뀌면 shell_old로 알린다."""
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    await m.open_project("runshoes")
    t = await m.window_for("runshoes")
    await _wait_pane(m, t, "[foreman] $")
    assert (await m.current(t))["shell_old"] is None
    pid1 = await _pane(m, t, "#{pane_pid}")
    assert await m.busy(t) == {}
    await tmux(m.socket, "send-keys", "-t", t, "-l", "sf")                 # 친 글이 남아 있다(사용자 펫퍼민트 창처럼)
    await _wait_pane(m, t, "$ sf")
    r = await m.respawn("runshoes")
    assert r == {"respawned": False, "busy": {"typed": "sf"}}
    assert await _pane(m, t, "#{pane_pid}") == pid1                       # 띄우지 않았다
    r = await m.respawn("runshoes", force=True)
    assert r["respawned"] and r["project"] == "runshoes" and r["busy"] == {"typed": "sf"}
    assert await _pane(m, t, "#{pane_pid}") != pid1
    await _wait_pane(m, t, "[foreman] $")
    await tmux(m.socket, "send-keys", "-t", t, "-l", "echo P=$FOREMAN_PROJECT")
    await tmux(m.socket, "send-keys", "-t", t, "Enter")
    await _wait_pane(m, t, "P=runshoes")
    # 돌고 있는 명령
    await tmux(m.socket, "send-keys", "-t", t, "-l", "sleep 30")
    await tmux(m.socket, "send-keys", "-t", t, "Enter")
    for _ in range(30):
        if (await m.busy(t)).get("cmd") == "sleep":
            break
        await asyncio.sleep(0.1)
    assert (await m.respawn("runshoes")) == {"respawned": False, "busy": {"cmd": "sleep"}}
    # 셸 설정이 셸보다 새것 → shell_old, 새 셸 뒤에는 없다
    now = time.time()
    os.utime(shell.terminal_rcfile, (now + 2, now + 2))
    old = (await m.current(t))["shell_old"]
    assert old and old["files"] == [Path(shell.terminal_rcfile).name]
    await asyncio.sleep(2.2)
    r = await m.respawn("runshoes", force=True)
    assert r["respawned"] and r["busy"] == {"cmd": "sleep"} and r["shell_old"] is None
    await _wait_pane(m, t, "[foreman] $")
    assert await m.busy(t) == {}
    names = (await tmux(m.socket, "list-windows", "-t", f"={shell.terminal_tmux_session}", "-F", "#{window_name}")).split()
    assert names.count("runshoes") == 1                                   # 같은 창(새 창을 만들지 않는다)
    await m.stop()


async def test_tab_views_do_not_drag_each_other(shell, own_sock):
    """11-10 — 탭마다 그룹 세션: 한 탭에서 창을 골라도 다른 탭 · 기준 세션의 보이는 창은 그대로. 탭 세션이 없으면 기준 세션(view=False).
    붙은 사람 없이 남은 탭 세션은 치운다(창 · 셸은 남는다)."""
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    base = shell.terminal_tmux_session
    await m.window_for("foreman")
    await m.window_for("runshoes")
    for tab in ("tabAAAA01", "tabBBBB02"):
        await tmux(m.socket, "new-session", "-d", "-t", f"={base}", "-s", f"{base}-v-{tab}")
    a = await m.open_project("runshoes", "tabAAAA01")
    assert a["project"] == "runshoes" and a["view"] is True
    b = await m.open_project("foreman", "tabBBBB02")
    assert b["project"] == "foreman" and b["view"] is True
    assert (await m.current_view("tabAAAA01"))["project"] == "runshoes"    # B가 골라도 A는 그대로
    assert (await m.current_view("tabBBBB02"))["project"] == "foreman"
    base_win = (await m.current())["window"]
    await m.open_project("petmint-rag-chatbot", "tabAAAA01")
    assert (await m.current())["window"] == base_win                       # 기준 세션은 끌려가지 않는다
    assert (await m.current_view("tabBBBB02"))["project"] == "foreman"
    # 없는 탭 · 모양이 틀린 탭 → 기준 세션
    assert (await m.current_view("tabZZZZ99"))["view"] is False
    assert m.view_name("../x;rm") is None and m.view_name("short") is None
    t0 = time.monotonic()
    r = await m.open_project("runshoes", "tabZZZZ99")
    assert r["view"] is False and r["project"] == "runshoes" and time.monotonic() - t0 < 4.5
    # 치우기 — 막 만든 것(30초 안)은 두고, min_age=0이면 붙은 사람 없는 탭 세션만
    assert await m.sweep_views() == []
    gone = sorted(await m.sweep_views(min_age=0))
    assert gone == [f"{base}-v-tabAAAA01", f"{base}-v-tabBBBB02"]
    names = (await tmux(m.socket, "list-windows", "-t", f"={base}", "-F", "#{window_name}")).split()
    assert {"foreman", "runshoes", "petmint-rag-chatbot"} <= set(names)
    await m.stop()


async def test_scroll_enters_and_leaves_copy_mode_per_tab(shell, own_sock):
    """11-11 — [위로]는 그 탭의 보이는 창을 복사 모드로 올리고(scrolling=True), [입력으로]가 끝낸다. 다른 탭은 그대로, 없는 탭은 거절."""
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    base = shell.terminal_tmux_session
    await m.window_for("foreman")
    for tab in ("tabAAAA01", "tabBBBB02"):
        await tmux(m.socket, "new-session", "-d", "-t", f"={base}", "-s", f"{base}-v-{tab}")
    assert (await m.current_view("tabAAAA01"))["scrolling"] is False
    r = await m.scroll("tabAAAA01", "up")
    assert r["scrolling"] is True and r["view"] is True
    assert (await m.current_view("tabAAAA01"))["scrolling"] is True
    # 같은 창을 보고 있어도 복사 모드는 탭(그룹 세션)마다 따로가 아니라 창의 칸(pane) 것이다 — 그래도 없는 탭은 거절한다
    r = await m.scroll("tabAAAA01", "down")                  # 맨 아래에 닿으면 -e로 저절로 끝나거나 그대로 — 어느 쪽이든 오류는 없다
    assert "scrolling" in r
    await m.scroll("tabAAAA01", "up")
    r = await m.scroll("tabAAAA01", "exit")
    assert r["scrolling"] is False
    r = await m.scroll("tabAAAA01", "wheel_down")            # 스크롤 중이 아니면 아래로는 아무 일도 없다
    assert r["scrolling"] is False
    r = await m.scroll("tabAAAA01", "wheel_up")              # 휠 위로 = 복사 모드로 들어가 3줄 올림
    assert r["scrolling"] is True
    r = await m.scroll("tabAAAA01", "exit")
    assert r["scrolling"] is False
    r = await m.scroll("tabAAAA01", "exit")                # 복사 모드가 아닐 때 [입력으로]는 아무 일도 하지 않는다
    assert r["scrolling"] is False
    with pytest.raises(Refused):
        await m.scroll("tabZZZZ99", "up")
    with pytest.raises(Refused):
        await m.scroll("tabAAAA01", "rm -rf")
    await m.stop()


class _RepoEngine:
    """_repo_dir만 읽는 가짜 엔진 — SELECT repo_path FROM project WHERE name = :n."""

    def __init__(self, repos: dict[str, str]):
        self.repos = repos

    def connect(self):
        eng = self

        class _C:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, _q, params):
                class _R:
                    def scalar(self_inner):
                        return eng.repos.get(params["n"])
                return _R()
        return _C()


async def test_infra_window_opens_in_its_repo(shell, own_sock, tmp_path):
    """11-10 인프라 등록 — [ronanlab-infra] 창이 그 저장소 폴더에서 열리고(FOREMAN_PROJECT), 탭 그룹 세션에서 골라도
    다른 탭은 끌려가지 않는다. 시험만의 tmux 서버(own_sock) — 라이브 foreman-shell에 창을 만들지 않는다."""
    repo = tmp_path / "ronanlab-infra"
    repo.mkdir()
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    m.engine = _RepoEngine({"ronanlab-infra": str(repo)})
    base = shell.terminal_tmux_session
    await m.window_for("foreman")
    for tab in ("tabINFRA001", "tabOTHER002"):
        await tmux(m.socket, "new-session", "-d", "-t", f"={base}", "-s", f"{base}-v-{tab}")
    b = await m.open_project("foreman", "tabOTHER002")
    a = await m.open_project("ronanlab-infra", "tabINFRA001")
    assert a["project"] == "ronanlab-infra" and a["window"] == "ronanlab-infra" and a["view"] is True
    assert a["cwd"] == str(repo)
    assert (await m.current_view("tabOTHER002"))["project"] == "foreman" == b["project"]
    t = await m.window_for("ronanlab-infra")
    await tmux(m.socket, "send-keys", "-t", t, "-l", "echo P=$FOREMAN_PROJECT")
    await tmux(m.socket, "send-keys", "-t", t, "Enter")
    await _wait_pane(m, t, "P=ronanlab-infra")
    names = (await tmux(m.socket, "list-windows", "-t", f"={base}", "-F", "#{window_name}")).split()
    assert names.count("ronanlab-infra") == 1
    await m.stop()


async def test_view_script_attaches_then_cleans_up(shell, own_sock):
    """deploy/shell/foreman-term-view — ttyd가 연결마다 띄우는 것을 pty로 띄운다: 탭 세션이 그 프로젝트 창으로 붙고,
    연결이 끝나면(프로세스 끝) 사라진다. 처음에 destroy-unattached를 붙기 전에 걸어 그 자리에서 사라지던 것 · 대상 표기(=이름:)를 다시 막는다."""
    import pty
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    m.socket = own_sock
    await m.start()
    base = shell.terminal_tmux_session
    await m.window_for("runshoes")
    mfd, sfd = pty.openpty()
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")} | {"TERM": "xterm-256color"}
    proc = await asyncio.create_subprocess_exec(str(shell.terminal_view_script), own_sock, base, str(shell.terminal_rcfile),
                                                "tabPTY0001", "runshoes", stdin=sfd, stdout=sfd, stderr=sfd, env=env)
    os.close(sfd)
    try:
        view = None
        for _ in range(50):
            view = await m._view("tabPTY0001")
            if view:
                rows = await tmux(m.socket, "list-sessions", "-F", "#{session_name}\t#{session_attached}")
                if f"{base}-v-tabPTY0001\t1" in rows:
                    break
            await asyncio.sleep(0.1)
        assert view, "탭 세션이 안 생겼다"
        cur = await m.current_view("tabPTY0001")
        assert cur["view"] and cur["project"] == "runshoes"
        opt = await tmux(m.socket, "show-options", "-t", f"{view}", "destroy-unattached")
        assert opt.strip() == "destroy-unattached on"
        # 11-11 — 마우스는 tmux가 받지 않는다(mouse on이면 끌기를 가져가 글을 끌어 고를 수 없었다). 휠은 화면이 scroll API로 보낸다
        assert (await tmux(m.socket, "show-options", "-t", f"{view}", "mouse")).strip() == "mouse off"
        assert (await tmux(m.socket, "show-options", "-t", f"={base}:", "mouse")).strip() in ("", "mouse off")
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 3)
        except TimeoutError:
            proc.kill()
        os.close(mfd)
    for _ in range(30):
        if await m._view("tabPTY0001") is None:
            break
        await asyncio.sleep(0.1)
    assert await m._view("tabPTY0001") is None                              # 연결이 끝나면 사라진다
    assert (await m.current())["window"] is not None                       # 기준 세션 · 창은 남는다
    await m.stop()


def test_ttyd_args_filter():
    from bridge.api.terminal import _ttyd_args

    class W:
        def __init__(self, q):
            from starlette.datastructures import QueryParams
            self.query_params = QueryParams(q)
    assert _ttyd_args(W("arg=tabAAAA01&arg=runshoes")) == "?arg=tabAAAA01&arg=runshoes"
    assert _ttyd_args(W("arg=tabAAAA01&arg=")) == "?arg=tabAAAA01"
    assert _ttyd_args(W("arg=tabAAAA01&arg=a%3Bb")) == "?arg=tabAAAA01"       # 프로젝트 모양이 틀리면 탭만
    assert _ttyd_args(W("arg=..%2Fx&arg=runshoes")) == ""                      # 탭 모양이 틀리면 아무것도
    assert _ttyd_args(W("")) == ""


async def test_prefill_refuses_when_shell_busy(shell):
    p = FakePipeline()
    m = TerminalManager(None, shell, p, MK, publish=p.publish)
    await m.start()
    await _wait_for(m, "[foreman] $")
    await tmux(m.socket, "send-keys", "-t", m.target, "-l", "sleep 5")
    await tmux(m.socket, "send-keys", "-t", m.target, "Enter")
    await asyncio.sleep(0.5)
    r = await m.request(7, 71, "foreman", None, ["sudo true"])
    assert not r.prefilled and "sleep" in (r.note or "")
    await m.stop()


# ── 브리지를 거친 ttyd(실제 ttyd, 시험 소켓) ─────────────────────
@pytest.mark.db
def test_proxy_cookie_origin_ws(shell, tmp_path):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from bridge.config import REPO
    from bridge.main import create_app
    ttyd = REPO / ".tools" / "ttyd"
    if not os.access(ttyd, os.X_OK):
        pytest.skip("ttyd 없음")
    s = shell.model_copy(update={"ttyd_bin": ttyd, "mysql_database": "foreman_test", "watch_enabled": False,
                                 "notify_enabled": False, "pipeline_enabled": False, "usage_enabled": False})
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    conn.close()
    tok = s.foreman_api_token.get_secret_value()
    with TestClient(create_app(s)) as c:
        for _ in range(50):
            if s.terminal_socket.exists():
                break
            time.sleep(0.1)
        assert (s.terminal_socket.parent.stat().st_mode & 0o777) == 0o700
        assert c.get("/terminal/").status_code == 401
        assert c.post("/api/terminal/session").status_code == 401
        r = c.post("/api/terminal/session", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        sc = r.headers["set-cookie"].lower()
        assert "httponly" in sc and "samesite=strict" in sc and "path=/terminal" in sc
        r = c.get("/terminal/")
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        assert r.headers["x-frame-options"] == "SAMEORIGIN"
        # Origin이 없거나 다르면 거절(다른 사이트가 쿠키로 셸을 여는 것)
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/terminal/ws", subprotocols=["tty"]) as ws:
                ws.receive_bytes()
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/terminal/ws", subprotocols=["tty"], headers={"origin": "http://evil.example"}) as ws:
                ws.receive_bytes()
        with c.websocket_connect("/terminal/ws", subprotocols=["tty"], headers={"origin": "http://testserver"}) as ws:
            ws.send_text('{"AuthToken":"","columns":100,"rows":30}')
            ws.send_bytes(b"0echo via-ttyd-$((40+2))\r")
            seen = b""
            for _ in range(200):
                m = ws.receive()
                seen += m.get("bytes") or (m.get("text") or "").encode()
                if b"via-ttyd-42" in seen:
                    break
            assert b"via-ttyd-42" in seen
        st = c.get("/api/terminal", headers={"Authorization": f"Bearer {tok}"}).json()
        assert st["enabled"] and st["running"]
        # 11-10 보이는 창 읽기 — 창을 바꾸지 않고, 밖에서(다른 탭 · tmux 키) 바뀐 것을 따라간다
        h = {"Authorization": f"Bearer {tok}"}
        assert c.get("/api/terminal/window").status_code == 401
        w0 = c.post("/api/terminal/open", headers=h, json={"project": "runshoes"}).json()
        assert w0["project"] == "runshoes"
        assert c.get("/api/terminal/window", headers=h).json()["project"] == "runshoes"
        c.post("/api/terminal/open", headers=h, json={"project": "foreman"})
        w1 = c.get("/api/terminal/window", headers=h).json()
        assert w1["project"] == "foreman" and w1["window"] == "foreman"
        # 11-10 탭마다 그룹 세션 — iframe 주소의 ?arg=<탭>&arg=<프로젝트>가 WS 프록시 → ttyd -a → foreman-term-view로 간다
        tab = "tabPROXY01"
        with c.websocket_connect(f"/terminal/ws?arg={tab}&arg=runshoes", subprotocols=["tty"],
                                 headers={"origin": "http://testserver"}) as ws:
            ws.send_text('{"AuthToken":"","columns":100,"rows":30}')
            for _ in range(50):
                v = c.get(f"/api/terminal/window?tab={tab}", headers=h).json()
                if v["view"]:
                    break
                time.sleep(0.1)
            assert v["view"] and v["project"] == "runshoes"
            v = c.post("/api/terminal/open", headers=h, json={"project": "foreman", "tab": tab}).json()
            assert v["view"] and v["project"] == "foreman"
            assert c.get("/api/terminal/window", headers=h).json()["project"] == "foreman"   # 기준 세션 그대로
            c.post("/api/terminal/open", headers=h, json={"project": "runshoes", "tab": tab})
            assert c.get("/api/terminal/window", headers=h).json()["project"] == "foreman"   # 탭이 골라도 기준은 안 끌려감
        for _ in range(50):
            if not c.get(f"/api/terminal/window?tab={tab}", headers=h).json()["view"]:
                break
            time.sleep(0.1)
        assert c.get(f"/api/terminal/window?tab={tab}", headers=h).json()["view"] is False   # 연결이 끝나면 탭 세션도 끝
