"""프로젝트별 관리자 주소 · 부탁(11-11, bridge/managers.py · bridge/api/managers.py) — DB 없이 가짜 엔진으로."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bridge import managers as mg
from bridge.api import managers as api
from bridge.api.auth import require_api_token
from bridge.xmsg import label_of

PROJ = [("foreman", "/r/foreman"), ("runshoes", "/r/runshoes")]
LIVE = {"/r/foreman": ["cc-mgr", "cc-coder"], "/r/runshoes": ["cc-run"]}
ROWS = {"cc-mgr": (276, "manager", "/r/foreman", "관리자"), "cc-coder": (280, "coder", "/r/foreman", "코더"),
        "cc-run": (290, "coder", "/r/runshoes", "런")}


class _Res:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Conn:
    def __init__(self, log):
        self.log = log

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, sql, params=None):
        q = str(sql)
        if "FROM project" in q:
            return _Res(PROJ)
        if "INSERT INTO session_action" in q:
            self.log.append(params)
            return _Res([])
        if "WHERE cc_session_id IN" in q:
            return _Res([(cc, *ROWS[cc]) for cc in params["c"]])
        if "WHERE id = :s" in q:
            return _Res([("런슈즈 코더",)])
        raise AssertionError(q)


class _Notifier:
    rules = None

    def __init__(self):
        self.sent = []

    def send_direct(self, project, kind, sid, msg, **kw):
        self.sent.append((project, kind, msg))


def _mgrs(enabled=True):
    actions = []
    eng = SimpleNamespace(connect=lambda: _Conn(actions), begin=lambda: _Conn(actions))
    h = SimpleNamespace(engine=eng, sessions_dir="/x", _live_in_base=lambda repo: LIVE.get(repo, []))
    n = _Notifier()
    return mg.Managers(h, mg.ManagersConfig(enabled=enabled), n), actions, n


def test_board_finds_base_manager_only():
    m, _, _ = _mgrs()
    b = asyncio.run(m.board())
    assert b[0]["manager"]["session_id"] == 276
    assert b[1]["manager"] is None and "관리자가 없습니다" in b[1]["note"]


def test_ask_delivers_and_records(monkeypatch):
    m, actions, n = _mgrs()
    got = {}

    async def fake_deliver(cc, msg, **kw):
        got.update(cc=cc, msg=msg)
        return {"delivered": {"as": "prompt"}}
    monkeypatch.setattr(mg, "deliver", fake_deliver)
    out = asyncio.run(m.ask("foreman", "안내 문구를 고쳐 주세요", "runshoes", 290))
    assert out["delivered"] and out["to_session"] == 276 and got["cc"] == "cc-mgr"
    assert got["msg"].startswith("[관리자 부탁 — runshoes 관리자(세션 290 「런슈즈 코더」) → foreman 관리자]")
    assert "/api/managers/runshoes/ask" in got["msg"]
    assert actions[-1]["o"] is True and actions[-1]["s"] == 276
    assert n.sent == []


def test_ask_without_manager_tells_human(monkeypatch):
    m, actions, n = _mgrs()

    async def boom(*a, **k):
        raise AssertionError("관리자가 없으면 넣지 않는다")
    monkeypatch.setattr(mg, "deliver", boom)
    out = asyncio.run(m.ask("runshoes", "배포 확인", "foreman"))
    assert not out["delivered"] and "관리자 세션이 없습니다" in out["reason"]
    assert n.sent and n.sent[0][0] == "runshoes" and "넣지 못했습니다" in n.sent[0][2]
    assert actions[-1]["o"] is False


def test_ask_refused_tells_human(monkeypatch):
    from bridge.inject import Refused
    m, _, n = _mgrs()

    async def refuse(*a, **k):
        raise Refused("세션이 일하는 중")
    monkeypatch.setattr(mg, "deliver", refuse)
    out = asyncio.run(m.ask("foreman", "x", "runshoes"))
    assert not out["delivered"] and "세션이 일하는 중" in out["reason"] and n.sent


@pytest.mark.parametrize("enabled", [False, True])
def test_api(monkeypatch, enabled):
    m, _, _ = _mgrs(enabled)

    async def fake_deliver(cc, msg, **kw):
        return {"queued": True}
    monkeypatch.setattr(mg, "deliver", fake_deliver)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_api_token] = lambda: None
    app.state.managers = m
    c = TestClient(app)
    b = c.get("/api/managers").json()
    assert b["enabled"] is enabled and b["projects"][0]["manager"]["session_id"] == 276
    r = c.post("/api/managers/foreman/ask", json={"text": "부탁"})
    if not enabled:
        assert r.status_code == 503
        return
    assert r.json()["delivered"] is True
    assert c.post("/api/managers/nope/ask", json={"text": "x"}).status_code == 404


def test_label_of():
    assert label_of("runshoes", "관리", "manager", None) == "runshoes 관리자 · 관리"
    assert label_of("runshoes", "코더", "manager", "/w") == "runshoes · 코더"


def test_manager_ask_turn_origin_and_no_telegram():
    """11-12 ① — 관리자끼리 부탁으로 연 턴은 사람 입력(human)이 아니고, 기본 규칙에서 텔레그램을 보내지 않는다."""
    from bridge.assembler import Assembler
    from bridge.notify import load_rules
    o = Assembler._origin
    msg = mg.ask_text("runshoes", "세션 290 「런슈즈 코더」", "foreman", "안내 문구를 고쳐 주세요")
    assert o({}, msg) == "manager_ask"
    assert o({"origin": {"kind": "human"}}, f'<pasted_content id="1a2b">\n{msg}\n</pasted_content id="1a2b">') == "manager_ask"
    assert o({}, mg.ask_text("foreman", None, "foreman", "본문")) == "manager_ask"
    # 계획 카드 [관리자에게 보내기](from 없음 — 사람이 누름)는 사람 요청 그대로
    assert o({}, mg.ask_text(None, None, "foreman", "계획")) == "human"
    assert o({}, "관리자 부탁 이야기를 하는 보통 입력") == "human"
    r = load_rules("config/notify.toml")
    for p in ("foreman", "runshoes", "ronanlab-infra", "petmint-rag-chatbot"):
        rule = r.for_project(p)
        assert "manager_ask" not in rule.origins and "manager_ask" not in rule.batch_origins
