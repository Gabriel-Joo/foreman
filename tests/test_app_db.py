"""실행 중인 foreman-mysql(127.0.0.1:3308)과 .env.db · .env.bridge가 필요하다.  pytest -m db"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bridge.config import get_settings
from bridge.main import create_app

pytestmark = pytest.mark.db


@pytest.fixture
def client():
    # 테스트에서는 와처를 끈다 — 켜면 실제 ~/.claude/projects를 운영 DB에 적재한다.
    # 터미널 패널도 끈다 — 켜면 운영 tmux 셸 · ttyd 소켓을 건드린다(터미널은 tests/test_terminal.py가 따로 띄운다)
    with TestClient(create_app(get_settings().model_copy(update={"watch_enabled": False, "notify_enabled": False,
                                                                 "terminal_enabled": False,
                                                                 "pipeline_enabled": False}))) as c:
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
    token = get_settings().foreman_api_token.get_secret_value()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "hello"


def _auth():
    return {"Authorization": f"Bearer {get_settings().foreman_api_token.get_secret_value()}"}


def test_emit_requires_token(client):
    assert client.post("/api/debug/emit", json={}).status_code == 401
    assert client.post("/api/debug/emit", json={}, headers={"Authorization": "Bearer " + "x" * 40}).status_code == 401


def test_emit_reaches_ws_and_db(client):
    token = get_settings().foreman_api_token.get_secret_value()
    long_target = "echo " + "a" * 2000
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
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
    assert get_settings().foreman_api_token.get_secret_value() not in e.value.reason


def test_hooks_reject_paths(client):
    hook = get_settings().foreman_hook_token.get_secret_value()
    api = get_settings().foreman_api_token.get_secret_value()
    body = {"hook_event_name": "Stop", "session_id": "x"}
    assert client.post("/hooks", json=body).status_code == 401
    assert client.post("/hooks", json=body, headers={"Authorization": f"Bearer {api}"}).status_code == 401  # API 토큰으론 안 된다
    assert client.post("/hooks", content=b"nope", headers={"Authorization": f"Bearer {hook}"}).status_code == 400
    assert client.post("/hooks", json={"x": 1}, headers={"Authorization": f"Bearer {hook}"}).status_code == 400
    assert client.post("/hooks", json=body, headers={"Authorization": f"Bearer {hook}"}).status_code == 503  # 와처 꺼짐


def test_dashboard_snapshot_and_pages(client):
    """6단계 — 운영 DB를 읽기만 한다."""
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
