"""실행 중인 foreman-mysql(127.0.0.1:3308)과 .env.db · .env.bridge가 필요하다.  pytest -m db"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bridge.config import get_settings
from bridge.main import create_app

pytestmark = pytest.mark.db


@pytest.fixture
def client():
    with TestClient(create_app(get_settings())) as c:
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
