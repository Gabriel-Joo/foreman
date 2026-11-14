"""실행 중인 foreman-mysql(127.0.0.1:3308)과 .env.db · .env.bridge가 필요하다.  pytest -m db

11-11부터 운영 DB(foreman)가 아니라 이 세션의 시험 DB(tests/testdb.py)에 앱을 띄운다 — 동시에 돈 두 pytest가
운영 DB의 디버그 이벤트를 서로 지워 깨졌다. 토큰이 든 헤더는 _bearer()로 만든다(실패해도 출력에 값이 풀리지 않게)."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bridge.config import get_settings, resolve_test_db
from bridge.db.migrate import main as migrate_main
from bridge.main import create_app

pytestmark = pytest.mark.db


class _Masked(dict):
    """repr에 값을 내지 않는 사전(헤더 · ws 인증 글) — pytest가 실패한 assert의 호출 인자를 풀어 쓸 때 값이 찍혔다(11-11).
    보내는 값(json · 헤더)은 그대로다. 시험은 토큰 문자열을 지역 변수로 두지 않고 이것만 든다 — pytest -l이 실패한 시험의
    지역 변수를 찍는다(11-14)."""

    def __repr__(self) -> str:
        return "{" + ", ".join(f"{k!r}: '***'" for k in self) + "}"


def _bearer(token: str) -> dict:
    return _Masked(Authorization=f"Bearer {token}")


def _hook_auth() -> dict:
    return _bearer(get_settings().foreman_hook_token.get_secret_value())


def _ws_auth() -> dict:
    return _Masked(type="auth", token=get_settings().foreman_api_token.get_secret_value())


@pytest.fixture
def client():
    # 테스트에서는 와처를 끈다 — 켜면 실제 ~/.claude/projects를 DB에 적재한다.
    # 터미널 패널도 끈다 — 켜면 운영 tmux 셸 · ttyd 소켓을 건드린다(터미널은 tests/test_terminal.py가 따로 띄운다)
    s = get_settings().model_copy(update={"mysql_database": resolve_test_db("foreman_test")})
    assert migrate_main([], settings=s) == 0
    with TestClient(create_app(s.model_copy(update={"watch_enabled": False, "notify_enabled": False,
                                                                 "terminal_enabled": False,
                                                                 "pipeline_enabled": False,
                                                                 "losscheck_recover": False,   # 켜면 운영 브리지에서 도는 점검을 failed로 바꾼다(11-09)
                                                                 "usage_enabled": False}))) as c:   # 켜면 claude -p "/usage"를 부르고 운영 DB에 관찰을 남긴다
        yield c


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


def test_docs_closed(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_ws_wrong_token_closed_1008(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": "wrong" * 10})
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 1008


def test_ws_non_json_closed_1008(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("hello")
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 1008


def test_ws_auth_hello(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_ws_auth())
        assert ws.receive_json()["type"] == "hello"


def _auth():
    return _bearer(get_settings().foreman_api_token.get_secret_value())


def test_emit_requires_token(client):
    assert client.post("/api/debug/emit", json={}).status_code == 401
    assert client.post("/api/debug/emit", json={}, headers={"Authorization": "Bearer " + "x" * 40}).status_code == 401


def test_emit_reaches_ws_and_db(client):
    long_target = "echo " + "a" * 2000
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_ws_auth())
        assert ws.receive_json()["type"] == "hello"
        r = client.post("/api/debug/emit", json={"target": long_target, "character_id": 1}, headers=_auth())
        assert r.status_code == 201, r.text
        event_id = r.json()["id"]
        msg = ws.receive_json()
        assert msg["type"] == "event"
        ev = msg["event"]
        assert ev["id"] == event_id
        assert ev["source"] == "debug"
        assert ev["target_truncated"] is True
        assert len(ev["target"]) == 1024
        assert ev["payload"]["target_full"] == long_target
    assert client.delete("/api/debug/events", headers=_auth()).json()["deleted"] >= 1


def test_emit_unknown_character_422(client):
    r = client.post("/api/debug/emit", json={"character_id": 999999}, headers=_auth())
    assert r.status_code == 422


def test_emit_duplicate_uuid_409(client):
    u = "00000000-0000-4000-8000-0000000000aa"
    assert client.post("/api/debug/emit", json={"uuid": u}, headers=_auth()).status_code == 201
    assert client.post("/api/debug/emit", json={"uuid": u}, headers=_auth()).status_code == 409
    client.delete("/api/debug/events", headers=_auth())


def test_ws_wrong_token_reason_has_length_only(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": "z" * 61})
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 1008
    assert "61" in e.value.reason
    leaked = get_settings().foreman_api_token.get_secret_value() in e.value.reason
    assert not leaked, "거부 사유에 토큰이 들어 있다"


def test_hooks_reject_paths(client):
    hook = _hook_auth()   # 토큰 문자열 대신 가린 헤더만 든다(11-14, pytest -l)
    body = {"hook_event_name": "Stop", "session_id": "x"}
    assert client.post("/hooks", json=body).status_code == 401
    assert client.post("/hooks", json=body, headers=_auth()).status_code == 401  # API 토큰으론 안 된다
    assert client.post("/hooks", content=b"nope", headers=hook).status_code == 400
    assert client.post("/hooks", json={"x": 1}, headers=hook).status_code == 400
    assert client.post("/hooks", json=body, headers=hook).status_code == 503  # 와처 꺼짐


def test_dashboard_snapshot_and_pages(client):
    """6단계 — 시험 DB를 읽기만 한다(다른 시험이 남긴 행이 있을 수 있다)."""
    assert client.get("/api/dashboard").status_code == 401
    r = client.get("/api/dashboard", headers=_auth())
    assert r.status_code == 200
    j = r.json()
    assert {"projects", "approvals", "generated_at", "hidden_dormant"} <= j.keys()
    for p in j["projects"]:
        for s in p["sessions"]:
            assert s["state"] in ("ACTIVE", "IDLE", "DORMANT", "SUSPENDED")
            assert {"activity", "open_turn", "subagents_running", "tokens", "injectable"} <= s.keys()
    assert client.get("/api/sessions/999999/conversation", headers=_auth()).status_code == 404
    if j["projects"] and j["projects"][0]["sessions"]:
        sid = j["projects"][0]["sessions"][0]["id"]
        c = client.get(f"/api/sessions/{sid}/conversation?limit=2", headers=_auth()).json()
        assert len(c["turns"]) <= 2
    assert client.get("/").status_code == 200 and b"office.js" in client.get("/").content          # 10b: / 는 픽셀 화면
    assert client.get("/classic").status_code == 200 and b"render.js" in client.get("/classic").content
    assert client.get("/static/css/panel.css").status_code == 200
    assert client.get("/debug").status_code == 200
    assert client.get("/static/js/render.js").status_code == 200


def test_char_state_rule():
    from bridge.api.dashboard import char_state
    assert char_state(None, None, False) == "DORMANT"
    assert char_state("T", "busy", True) == "SUSPENDED"
    assert char_state("S", "busy", False) == "ACTIVE"
    assert char_state("S", "idle", True) == "IDLE"      # 끝 신호 없이 멈춘 턴 — CC가 일하지 않으면 IDLE(stuck_turn으로 따로 표시)
    assert char_state("S", "shell", True) == "IDLE"
    assert char_state("S", None, True) == "ACTIVE"      # CC status를 모를 때만 열린 턴을 본다
    assert char_state("S", "idle", False) == "IDLE"
