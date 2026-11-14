"""세션 역할 관리자(manager) · 역할 바꾸기(11-09) — 허용 값 · 거부 · 기록, 인계 역할 물려주기. DB · tmux 없이."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bridge import foreman, handoff as h, wake
from bridge.api import handoff as api
from bridge.api.auth import require_api_token
from bridge.inject import Refused
from bridge.model_choice import Models


class _Conn:
    """execute한 SQL · 값을 모은다. SELECT role은 지금 역할을 돌려준다."""

    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, q, params=None):
        sql = " ".join(str(q).split())
        self.db["sql"].append((sql, params))
        if sql.startswith("SELECT role, model FROM character_session"):
            return SimpleNamespace(first=lambda: (self.db["role"], self.db.get("model")))
        if sql.startswith("SELECT role FROM character_session"):
            return SimpleNamespace(first=lambda: (self.db["role"],))
        if sql.startswith("UPDATE character_session SET role"):
            self.db["role"] = params["r"]
        return SimpleNamespace(first=lambda: None, rowcount=1)


def _mgr(role="coder", char=None):
    db = {"role": role, "sql": []}
    eng = SimpleNamespace(connect=lambda: _Conn(db), begin=lambda: _Conn(db))
    m = h.HandoffManager.__new__(h.HandoffManager)
    m.engine, m.on_change, m.project_of = eng, None, None
    changed = []
    m.on_change = lambda: changed.append(1)

    async def char_for(cwd, r):
        db["char_for"] = (cwd, r)
        return char
    m._character_for = char_for
    return m, db, changed


ROW = h.SessionRow(id=230, cc="c" * 36, character_id=5, cwd="/repo/foreman", transcript=None, project="foreman", title="FOREMAN main")


def test_role_lists_agree():
    """세션 역할 목록이 한곳만 바뀌지 않게 — 화면 이름(ROLE_KO) · 교장 계획 · API · 알림 글 · 모델 기본값."""
    assert set(h.ROLE_KO) == set(foreman.ROLES) == set(api.SessionRole.__args__) == set(wake.ROLE_KO)
    assert h.ROLE_KO["manager"] == "관리자" and "foreman" not in h.ROLE_KO     # foreman은 감독실 캐릭터 몫
    assert h.ROLE_KO["designer"] == "디자이너"                                 # 11-10 화면 담당
    assert Models().pick(None, "manager") == "claude-opus-5-5"
    assert Models().pick(None, "designer") == "claude-opus-5-5"
    assert "designer" in foreman.INSTRUCTIONS                                  # 교장이 화면 일 · 코더 일을 나누는 기준


class _CharConn(_Conn):
    """_character_for — 포먼 캐릭터는 있고, 같은 이름 캐릭터는 없어 새로 만든다."""

    async def execute(self, q, params=None):
        sql = " ".join(str(q).split())
        self.db["sql"].append((sql, params))
        if "current_role = 'foreman'" in sql:
            return SimpleNamespace(first=lambda: (1, 9))
        if sql.startswith("INSERT INTO `character`"):
            return SimpleNamespace(lastrowid=88)
        return SimpleNamespace(first=lambda: None)


@pytest.mark.parametrize("cwd,name", [("/repo/foreman", "디자이너"), ("/repo/foreman/.worktrees/foreman-6", "디자이너 foreman-6")])
async def test_designer_character_name(cwd, name):
    """디자이너 캐릭터(11-10) — 관리자와 같은 규칙: 원본 폴더 "디자이너", worktree "디자이너 foreman-N"."""
    db = {"sql": []}
    m = h.HandoffManager.__new__(h.HandoffManager)
    m.engine = SimpleNamespace(begin=lambda: _CharConn(db))
    m.project_of = lambda c: ("foreman", None)
    assert await m._character_for(cwd, "designer") == 88
    ins = [p for s, p in db["sql"] if s.startswith("INSERT INTO `character`")]
    assert ins == [{"pid": 9, "f": 1, "n": name, "r": "designer"}]


async def test_set_role_updates_and_records():
    m, db, changed = _mgr("coder", char=77)
    out = await m.set_role(ROW, "manager")
    assert out == {"id": 230, "role": "manager", "old": "coder", "character_id": 77, "changed": True}
    assert db["role"] == "manager" and db["char_for"] == ("/repo/foreman", "manager")
    up = [p for s, p in db["sql"] if s.startswith("UPDATE character_session SET role")]
    assert up == [{"r": "manager", "ch": 77, "i": 230}]
    act = [p for s, p in db["sql"] if s.startswith("INSERT INTO session_action")]
    assert act == [{"s": 230, "a": "role", "p": None, "o": True, "d": "coder → manager 캐릭터 77"}]
    assert changed == [1]


async def test_set_role_same_is_noop_and_unknown_refused():
    m, db, _ = _mgr("manager")
    assert (await m.set_role(ROW, "manager"))["changed"] is False
    assert not any(s.startswith(("UPDATE", "INSERT")) for s, _ in db["sql"])
    for bad in ("foreman", "boss", ""):
        with pytest.raises(Refused):
            await m.set_role(ROW, bad)


async def test_handoff_spawn_inherits_manager_role():
    """새 세션으로 옮기기([새로 띄우기]) — 옛 세션이 관리자면 새 세션도 관리자(ROLE_KO에 없으면 None으로 떨어졌다)."""
    m, db, _ = _mgr("manager")
    seen = {}

    async def spawn_new(cwd, summary_id, title, **kw):
        seen.update(kw)
        return {"ok": True}
    m.spawn_new = spawn_new
    await m.spawn(ROW, None, replace=True)
    assert seen["role"] == "manager" and seen["src_session"] == 230


def _app(mgr):
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_api_token] = lambda: None
    app.state.handoff = mgr
    return app


async def test_role_api_allows_only_known_roles():
    calls = []

    async def session(sid):
        return ROW if sid == 230 else None

    async def set_role(row, role):
        calls.append((row.id, role))
        return {"id": row.id, "role": role, "changed": True}
    mgr = SimpleNamespace(session=session, set_role=set_role)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(mgr)), base_url="http://t") as c:
        r = await c.put("/api/sessions/230/role", json={"role": "manager"})
        assert r.status_code == 200 and r.json()["role"] == "manager"
        assert (await c.put("/api/sessions/230/role", json={"role": "designer"})).status_code == 200
        for bad in ("foreman", "boss", None):
            assert (await c.put("/api/sessions/230/role", json={"role": bad})).status_code == 422
        assert (await c.put("/api/sessions/999/role", json={"role": "coder"})).status_code == 404
    assert calls == [(230, "manager"), (230, "designer")]


async def test_role_api_refused_is_409():
    async def session(sid):
        return ROW

    async def set_role(row, role):
        raise Refused("바꿀 수 없는 역할입니다")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(SimpleNamespace(session=session, set_role=set_role))),
                                 base_url="http://t") as c:
        r = await c.put("/api/sessions/230/role", json={"role": "coder"})
    assert r.status_code == 409 and r.json() == {"refused": "바꿀 수 없는 역할입니다"}


def test_new_session_accepts_manager():
    assert api.NewIn(cwd="/repo", role="manager").role == "manager"
    assert api.NewIn(cwd="/repo", role="designer").role == "designer"
