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
from bridge.inject import tmux
from bridge.mask import Masker
from bridge.terminal import (TerminalManager, cmd_matches, default_tmux_socket, extract_output, find_requests,
                             mask_shell, prefill_form)

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
