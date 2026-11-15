"""판정 없이 통과한 PreToolUse 기록(11-15 조사 A 3) — 스크립트 7갈래 + 브리지 안 5갈래, 판정은 그대로."""

import asyncio
import http.server
import json
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from bridge import hookmiss
from bridge.api import hooks as hooks_api
from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.roleguard import RoleGuard, RolesConfig

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
SECRET = "SECRETVALUE-do-not-log"
SID = "11111111-2222-3333-4444-555555555555"
BODY = json.dumps({"session_id": SID, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": f"echo {SECRET}"}, "cwd": "/x"})
DENY = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": "FOREMAN 시험"}})


@pytest.fixture
def miss_log(tmp_path, monkeypatch):
    p = tmp_path / "run" / "hook_miss.log"
    monkeypatch.setenv("FOREMAN_HOOK_MISS_LOG", str(p))
    return p


def _lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


# ── 스크립트 쪽 ──────────────────────────────────────────

class _Fake(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        kind = self.path.split("/")[1]
        if kind == "slow":
            time.sleep(5)
        code, body = {"deny": (200, DENY), "c204": (204, ""), "c500": (500, "x"), "c401": (401, "x"),
                      "empty": (200, ""), "broken": (200, "not json{"), "slow": (200, DENY)}[kind]
        self.send_response(code)
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        if body:
            self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def fake_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def script(tmp_path):
    """스크립트를 시험용 저장소로 복사한다 — 진짜 .env.bridge 토큰을 가짜 서버로 보내지 않게."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    s = repo / "scripts" / "foreman-decide.sh"
    shutil.copy2(ROOT / "scripts" / "foreman-decide.sh", s)
    (repo / ".env.bridge").write_text("FOREMAN_HOOK_TOKEN=test-token\n", encoding="utf-8")
    return s


def _run(script, base, miss_log, mode="pre", body=BODY):
    env = {**os.environ, "FOREMAN_HOOK_BASE": base, "FOREMAN_HOOK_MISS_LOG": str(miss_log)}
    t = time.monotonic()
    r = subprocess.run([str(script), mode], input=body, capture_output=True, text=True, env=env, timeout=20)
    return r, time.monotonic() - t


@pytest.mark.parametrize("kind,branch,why,out", [
    ("c500", "서버오류", "http=500", ""),
    ("c401", "인증실패", "http=401", ""),
    ("empty", "빈본문", "http=200", ""),
    ("broken", "깨진JSON", "http=200", "not json{\n"),       # 지금처럼 그대로 내보낸다
])
def test_script_branches_logged_output_unchanged(script, fake_server, miss_log, kind, branch, why, out):
    r, _ = _run(script, f"{fake_server}/{kind}", miss_log)
    assert r.returncode == 0 and r.stdout == out
    (line,) = _lines(miss_log)
    assert f" script-pre {branch} {why} session={SID} tool=Bash" in line
    assert SECRET not in line and "echo" not in line


def test_script_connection_refused(script, miss_log):
    r, _ = _run(script, "http://127.0.0.1:1", miss_log)
    assert r.returncode == 0 and r.stdout == ""
    assert " 연결거부 curl=7 " in _lines(miss_log)[0]


def test_script_no_token(script, miss_log):
    (script.parent.parent / ".env.bridge").unlink()
    r, _ = _run(script, "http://127.0.0.1:1", miss_log)
    assert r.returncode == 0 and r.stdout == ""
    assert " 토큰없음 - session=" in _lines(miss_log)[0]


def test_script_timeout(script, fake_server, miss_log):
    r, took = _run(script, f"{fake_server}/slow", miss_log)
    assert r.returncode == 0 and r.stdout == "" and took < 5.5      # deny는 지금처럼 버려진다
    assert " 시간초과 curl=28 " in _lines(miss_log)[0]


def test_script_normal_paths_write_nothing(script, fake_server, miss_log):
    r, _ = _run(script, f"{fake_server}/deny", miss_log)
    assert r.returncode == 0 and json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    r, _ = _run(script, f"{fake_server}/c204", miss_log)       # 브리지가 판정하지 않기로 함 = 정상
    assert r.returncode == 0 and r.stdout == ""
    assert not miss_log.exists()


def test_script_permission_mode_and_unknown_mode(script, miss_log):
    _run(script, "http://127.0.0.1:1", miss_log, mode="permission")
    assert " script-permission 연결거부 " in _lines(miss_log)[0]
    r, _ = _run(script, "http://127.0.0.1:1", miss_log, mode="other")
    assert r.returncode == 0 and len(_lines(miss_log)) == 1


def test_script_ignores_tool_name_inside_input(script, miss_log):
    body = json.dumps({"session_id": "a b\"c", "tool_name": "Bash", "tool_input": {"x": '"tool_name":"Evil"'}})
    _run(script, "http://127.0.0.1:1", miss_log, body=body)
    assert _lines(miss_log)[0].endswith("session=- tool=Bash")        # 이상한 세션 값은 쓰지 않는다


def test_script_rotates_once(script, miss_log):
    miss_log.parent.mkdir(parents=True)
    miss_log.write_text("x" * (1048576 + 10), encoding="utf-8")
    _run(script, "http://127.0.0.1:1", miss_log)
    old = miss_log.with_name("hook_miss.log.1")
    assert old.stat().st_size > 1048576 and len(_lines(miss_log)) == 1
    _run(script, "http://127.0.0.1:1", miss_log)
    assert len(_lines(miss_log)) == 2 and not miss_log.with_name("hook_miss.log.2").exists()


def test_script_concurrent_lines_not_mixed(script, miss_log):
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda _: _run(script, "http://127.0.0.1:1", miss_log), range(32)))
    lines = _lines(miss_log)
    assert len(lines) == 32 and all(ln.endswith(f"session={SID} tool=Bash") for ln in lines)


# ── 브리지 쪽 ────────────────────────────────────────────

def test_record_format_and_sanitize(miss_log):
    hookmiss.record("판정예외", "스키마-잠금:Key Error", "bad id!", "Bash; rm")
    (line,) = _lines(miss_log)
    assert " bridge 판정예외 스키마-잠금:Key_Error session=- tool=-" in line
    assert oct(miss_log.stat().st_mode & 0o777) == "0o600"


def test_record_write_failure_does_not_raise(tmp_path, monkeypatch):
    f = tmp_path / "file"
    f.write_text("x")
    monkeypatch.setenv("FOREMAN_HOOK_MISS_LOG", str(f / "under-a-file.log"))
    hookmiss.record("승인꺼짐", "준비전", SID, "Bash")                  # 예외 없음


def _app(mgr, enabled=True):
    app = FastAPI()
    app.include_router(hooks_api.router)
    app.state.settings = SimpleNamespace(foreman_hook_token=SecretStr("t"), approval_enabled=enabled)
    app.state.approvals = mgr
    return app


async def _post(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.post("/hooks/pre", content=BODY, headers={"Authorization": "Bearer t"})


@pytest.mark.parametrize("enabled,why", [(True, "준비전"), (False, "설정꺼짐")])
def test_bridge_no_manager(miss_log, enabled, why):
    r = asyncio.run(_post(_app(None, enabled)))
    assert r.status_code == 204
    assert f" bridge 승인꺼짐 {why} session={SID} tool=Bash" in _lines(miss_log)[0]


class _FakeMgr:
    def __init__(self, out=None, role_err=False, slow=0.0):
        self.out, self.engine, self.slow = out, None, slow
        self.roles = SimpleNamespace(active=True, role_of=self._role_of) if role_err else None
        self.seen_role = "unset"

    async def _role_of(self, engine, sid):
        raise ConnectionError("db down")

    async def session_role(self, body):
        await asyncio.sleep(self.slow)
        return None

    def pre_tool_use(self, body, role=None, session_role=None):
        self.seen_role = session_role
        return self.out


def test_bridge_role_read_failure_logged_decision_unchanged(miss_log):
    deny = json.loads(DENY)
    m = _FakeMgr(out=deny, role_err=True)
    r = asyncio.run(_post(_app(m)))
    assert r.status_code == 200 and r.json() == deny and m.seen_role is None
    assert " bridge 역할읽기실패 ConnectionError " in _lines(miss_log)[0]


def test_bridge_slow_response_logged(miss_log, monkeypatch):
    monkeypatch.setattr(hooks_api, "HOOK_PRE_MAX_S", 0.05)
    r = asyncio.run(_post(_app(_FakeMgr(slow=0.1))))
    assert r.status_code == 204
    assert " bridge 늦은응답 " in _lines(miss_log)[0]


def test_bridge_normal_path_writes_nothing(miss_log):
    r = asyncio.run(_post(_app(_FakeMgr())))
    assert r.status_code == 204 and not miss_log.exists()


def _mgr():
    asm = SimpleNamespace(_project_for=lambda cwd, d: ("foreman", None), ids_for=None)
    m = ApprovalManager(None, load_policy(FIXTURES / "approval_now.toml"), asm, SimpleNamespace(submit=lambda e: None), None)

    async def rec(*a, **k):
        pass
    m._record_pre = rec
    return m


def _boom(*a, **k):
    raise KeyError("x")


P = {"tool_name": "Bash", "tool_input": {"command": f"echo {SECRET}"}, "cwd": "/x", "session_id": SID}


def test_role_check_exception_logged(miss_log, tmp_path):
    gd = RoleGuard(RolesConfig(mode="enforce", projects=["foreman"]), free=())
    gd._check = _boom
    assert gd.check("foreman", "coder", str(tmp_path), "Bash", {}, session=SID) is None
    assert " bridge 역할판정예외 KeyError session=" + SID + " tool=Bash" in _lines(miss_log)[0]


@pytest.mark.parametrize("which,rule", [("schema", "스키마-잠금"), ("scope", "다른저장소-쓰기"), ("pgrep", "pgrep-자기걸림")])
def test_lock_check_exception_passes_and_logged(miss_log, monkeypatch, which, rule):
    async def go():
        m = _mgr()
        if which == "schema":
            m.schema = SimpleNamespace(check=_boom)
        elif which == "scope":
            m.scope = SimpleNamespace(check=_boom)
        else:
            monkeypatch.setattr("bridge.approvals.pgrep_guard.check", _boom)
        return m.pre_tool_use(dict(P))
    assert asyncio.run(go()) is None                                   # 전에는 500 → 통과. 지금도 통과
    (line,) = _lines(miss_log)
    assert f" bridge 판정예외 {rule}:KeyError session={SID} tool=Bash" in line and SECRET not in line


def test_lock_denies_unchanged(miss_log):
    async def go(p, schema=None):
        m = _mgr()
        m.schema = schema
        return m.pre_tool_use(dict(p))
    out = asyncio.run(go(P, SimpleNamespace(check=lambda *a: "잠김", take_blocked_notice=lambda p: None)))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    out = asyncio.run(go({**P, "tool_input": {"command": "pgrep -f foo"}}))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not miss_log.exists()
