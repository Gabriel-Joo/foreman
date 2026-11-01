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
