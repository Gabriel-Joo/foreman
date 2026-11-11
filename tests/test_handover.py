"""교장 계획을 관리자에게 바로(11-11, bridge/handover.py) — DB 없이 가짜 엔진으로."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from bridge import handover as ho
from bridge.inject import Refused


class _Res:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, status="planned"):
        self.d = {"status": status, "request": "런슈즈 발볼", "handed_to": None, "handed_at": None, "edited": None, "alert": None}
        self.stale = []

    def conn(self):
        db = self

        class C:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, sql, p=None):
                q = str(sql)
                if q.startswith("SELECT status, request"):
                    return _Res([(db.d["status"], db.d["request"])])
                if "SET edited" in q:
                    db.d.update(edited=json.loads(p["e"]), handed_to=p["m"], handed_at="now")
                    return _Res([])
                if "SET handed_to = NULL" in q:
                    db.d.update(handed_to=None, handed_at=None)
                    return _Res([])
                if "TIMESTAMPDIFF" in q:
                    return _Res(db.stale)
                if "SET handed_alert_at" in q:
                    db.d["alert"] = p["i"]
                    return _Res([])
                raise AssertionError(q)
        return C()


PLAN = {"project": "foreman", "repo": "/r/foreman", "mode": "new",
        "sessions": [{"title": "코더", "role": "coder", "model": "opus", "worktree": True, "on": True,
                      "first_prompt": "해라", "files": ["bridge/a.py"]}]}


def _ho(db, manager=True, delivered=True):
    asks = []

    async def check(plan, did):
        return plan

    async def manager_of(repo):
        return {"session_id": 276, "cc_session_id": "c", "cwd": repo} if manager else None

    async def ask(project, msg, frm):
        asks.append((project, msg))
        if not manager:
            return {"delivered": False, "reason": "foreman에 관리자 세션이 없습니다", "notified": True}
        return {"delivered": delivered, "to_session": 276, "reason": None if delivered else "넣지 못했습니다: x", "notified": not delivered}
    eng = SimpleNamespace(connect=db.conn, begin=db.conn)
    f = SimpleNamespace(engine=eng, check=check)
    m = SimpleNamespace(manager_of=manager_of, ask=ask)
    sent = []
    n = SimpleNamespace(rules=None, send_direct=lambda *a, **k: sent.append(a))
    return ho.Handover(f, m, ho.HandoverConfig(enabled=True, wait_min=15), n), asks, sent


def test_send_saves_and_tells_manager():
    db = _DB()
    h, asks, _ = _ho(db)
    out = asyncio.run(h.send(7, dict(PLAN), [3, 4]))
    assert out["handed"] and out["to_session"] == 276
    assert db.d["handed_to"] == 276 and db.d["edited"]["inbox_ids"] == [3, 4]
    msg = asks[0][1]
    assert msg.startswith("[교장 계획 #7") and "use_saved" in msg and "\"dispatch_id\": 7" in msg
    assert "맡을 파일 bridge/a.py" in msg and "$T" in msg and "FOREMAN_API_TOKEN\"" not in msg


def test_send_without_manager_rolls_back():
    db = _DB()
    h, _, _ = _ho(db, manager=False)
    out = asyncio.run(h.send(7, dict(PLAN)))
    assert not out["handed"] and "관리자 세션이 없습니다" in out["reason"] and "[이대로 시작]" in out["note"]
    assert db.d["handed_to"] is None and db.d["handed_at"] is None


def test_send_refuses_started_or_ask():
    h, _, _ = _ho(_DB(status="started"))
    with pytest.raises(Refused):
        asyncio.run(h.send(7, dict(PLAN)))
    h, _, _ = _ho(_DB())
    with pytest.raises(Refused):
        asyncio.run(h.send(7, {**PLAN, "mode": "ask"}))
    with pytest.raises(Refused):
        asyncio.run(h.send(7, {**PLAN, "sessions": [{**PLAN["sessions"][0], "first_prompt": " "}]}))


def test_stale_alerts_once():
    db = _DB()
    db.stale = [(7, "foreman", 276, 20)]
    h, _, sent = _ho(db)
    assert asyncio.run(h.check_stale()) == [7]
    assert db.d["alert"] == 7 and sent and "아직 시작하지 않았습니다" in sent[0][3]


def test_config(tmp_path):
    p = tmp_path / "m.toml"
    p.write_text("[handover]\nenabled = true\nwait_min = 5\n")
    c = ho.HandoverConfig.load(p)
    assert c.enabled and c.wait_min == 5
    assert ho.HandoverConfig.load(tmp_path / "none").enabled is False
