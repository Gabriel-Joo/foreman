"""브리지 밖 포기 알림(11-15 조사 A 1) — scripts/foreman-bridge-alert.sh와 systemd 유닛 모양.

진짜 텔레그램은 보내지 않는다(가짜 API 서버 · 시험 모드). systemd 상태를 못 읽게 해서(버스 없음) 알리는 쪽 길을 탄다.
실제 OnFailure 호출은 시험용 사용자 유닛으로 한 번 확인했다(log/foreman-6_bridge_alert_20261115.md).
"""

import http.server
import os
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "foreman-bridge-alert.sh"
UNITS = ROOT / "deploy" / "systemd"


class _Tg(http.server.BaseHTTPRequestHandler):
    seen: list[tuple[str, str]] = []

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        _Tg.seen.append((self.path, body))
        ok = "/botgood/" in self.path
        out = b'{"ok":true}' if ok else b'{"ok":false}'
        self.send_response(200 if ok else 401)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def tg():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Tg)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _run(tmp_path, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("DBUS_SESSION_BUS_ADDRESS", "FOREMAN_ALERT_DRYRUN")}
    e.update({"XDG_RUNTIME_DIR": str(tmp_path / "no-bus"), "MONITOR_SERVICE_RESULT": "start-limit-hit"}, **env)
    return subprocess.run([str(SCRIPT), "foreman-alerttest-none.service"], capture_output=True, text=True, env=e, timeout=30)


def _env(tmp_path, token="good"):
    p = tmp_path / "tg.env"
    p.write_text(f'TELEGRAM_BOT_TOKEN="{token}"\nTELEGRAM_CHAT_ID=42\n', encoding="utf-8")
    return str(p)


def test_dry_run_writes_message_only(tmp_path):
    out = tmp_path / "out.txt"
    r = _run(tmp_path, FOREMAN_ALERT_DRYRUN=str(out), FOREMAN_ALERT_ENV=str(tmp_path / "none"))
    assert r.returncode == 0, r.stderr
    msg = out.read_text(encoding="utf-8")
    assert msg.startswith("[FOREMAN] 브리지가 멈췄습니다(systemd가 다시 띄우기를 포기)")
    assert "결과: start-limit-hit" in msg and "오류 종류" in msg


def test_send_ok(tmp_path, tg):
    _Tg.seen.clear()
    r = _run(tmp_path, FOREMAN_ALERT_ENV=_env(tmp_path), FOREMAN_ALERT_API=tg)
    assert r.returncode == 0 and "알림 보냄" in r.stdout
    path, body = _Tg.seen[0]
    assert path == "/botgood/sendMessage" and "chat_id=42" in body and "%5BFOREMAN%5D" in body


def test_telegram_refused_is_loud(tmp_path, tg):
    r = _run(tmp_path, FOREMAN_ALERT_ENV=_env(tmp_path, "bad"), FOREMAN_ALERT_API=tg)
    assert r.returncode == 1 and "텔레그램 HTTP 401" in r.stderr
    assert "bad" not in r.stderr + r.stdout                          # 토큰은 출력에 나오지 않는다


@pytest.mark.parametrize("env,why", [
    ({"FOREMAN_ALERT_API": "http://127.0.0.1:1"}, "curl 종료 코드 7"),
    ({"FOREMAN_ALERT_ENV": "/nonexistent/tg.env"}, "토큰 파일을 읽을 수 없습니다"),
])
def test_failures_are_loud(tmp_path, env, why):
    r = _run(tmp_path, **{"FOREMAN_ALERT_ENV": _env(tmp_path), **env})
    assert r.returncode == 1 and why in r.stderr


def test_units_wired():
    bridge = (UNITS / "foreman-bridge.service").read_text(encoding="utf-8")
    alert = (UNITS / "foreman-bridge-alert.service").read_text(encoding="utf-8")
    unit_part = bridge.split("[Service]")[0]
    assert "OnFailure=foreman-bridge-alert.service" in unit_part           # [Unit] 절에 있어야 한다
    assert "Type=oneshot" in alert and "scripts/foreman-bridge-alert.sh foreman-bridge.service" in alert
    assert os.access(SCRIPT, os.X_OK)
    code = SCRIPT.read_text(encoding="utf-8").split("\nset -u\n", 1)[1]       # 주석 뒤 실제 코드
    assert "python" not in code and ".venv" not in code and "notify.toml" not in code   # 브리지와 함께 죽지 않게
