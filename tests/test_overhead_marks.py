"""머리 위 표시 다시 설계(11-13 사용자) — 사람이 봐야 하는 것은 관리자 머리 위에만(escalate), 작업 세션은 관리자에게 넘긴 것을 작게.

- 관리자: 출처 relay · manager_ask 턴의 응답으로는 「보고 옴」 · 「답 기다림」을 내지 않는다. human 턴은 그대로
- 작업 세션: 알림이 관리자에게 넘긴 기록(relay-out ok, 같은 종류 · 같은 턴)이 있으면 relayed. 실패 · 기록 없음 · 중계 꺼짐이면 사람에게
- escalate: 관리자만. 보고는 읽으면, 물음은 사람이 입력하거나 [답 안 해도 됨]이면 사라진다
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest
from fastapi import HTTPException

from bridge.api.dashboard import RELAY_GRACE, asks_off, escalate, escalate_read, human_needs
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.managers import RELAY_QUESTION, RELAY_REPORT, escalate_hint, relay_text


@pytest.fixture
def env():
    s = Settings(mysql_database="foreman_test", watch_enabled=False)
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute("SET FOREIGN_KEY_CHECKS = 0")
        c.execute("SHOW TABLES")
        for (t,) in c.fetchall():
            c.execute(f"DROP TABLE `{t}`")
        c.execute("SET FOREIGN_KEY_CHECKS = 1")
    assert migrate_main([], settings=s) == 0
    yield s, conn
    conn.close()


NOW = datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _char(conn, project="foreman"):
    with conn.cursor() as c:
        c.execute("SELECT ch.id FROM `character` ch JOIN project p ON p.id = ch.project_id WHERE p.name = %s LIMIT 1", (project,))
        return c.fetchone()[0]


def _session(conn, char, role, n):
    with conn.cursor() as c:
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', %s, %s, 't', 'user')", (char, role, f"aaaaaaaa-0000-0000-0000-{n:012d}"))
        return c.lastrowid


def _turn(conn, sid, seq, origin, at):
    with conn.cursor() as c:
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at, ended_at) VALUES (%s, %s, %s, %s, %s)",
                  (sid, seq, origin, at, at + timedelta(seconds=5)))
        return c.lastrowid


def _reply(conn, sid, char, tid, at, txt):
    with conn.cursor() as c:
        c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, payload) VALUES "
                  "(%s, %s, %s, 'transcript', %s, 'assistant_msg', %s)", (sid, char, tid, at, json.dumps({"block": "text", "text": txt})))
        return c.lastrowid


def _act(conn, sid, action, ok, detail):
    with conn.cursor() as c:
        c.execute("INSERT INTO session_action (session_id, action, ok, detail) VALUES (%s, %s, %s, %s)", (sid, action, ok, detail))


async def _needs(engine, sid, relay=None):
    async with engine.connect() as c:
        return (await human_needs(c, f"({sid})", relay)).get(sid) or {}


@pytest.mark.db
async def test_manager_relay_turn_not_shown_human_turn_kept(env):
    s, conn = env
    ch = _char(conn)
    m = _session(conn, ch, "manager", 1)
    t1 = _turn(conn, m, 1, "relay", NOW - timedelta(minutes=10))
    _reply(conn, m, ch, t1, NOW - timedelta(minutes=9), "코더 보고를 받았습니다.\n\n이대로 합칠까요?")
    engine = make_engine(s)
    try:
        assert await _needs(engine, m) == {}                              # 중계 턴 — 묻는 말이어도 안 띄움
        t2 = _turn(conn, m, 2, "manager_ask", NOW - timedelta(minutes=8))
        _reply(conn, m, ch, t2, NOW - timedelta(minutes=7), "부탁 받은 것을 마쳤습니다.")
        assert await _needs(engine, m) == {}                              # 관리자끼리 부탁 — 보고 옴도 안 띄움
        t3 = _turn(conn, m, 3, "human", NOW - timedelta(minutes=6))
        _reply(conn, m, ch, t3, NOW - timedelta(minutes=5), "정리했습니다.\n\n어느 쪽으로 할까요?")
        assert "asks" in await _needs(engine, m)                          # 사람이 연 턴 — 지금처럼
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_worker_relayed_quiet_failed_or_off_stays_human(env):
    s, conn = env
    ch = _char(conn)
    w = _session(conn, ch, "coder", 2)
    t1 = _turn(conn, w, 1, "human", NOW - timedelta(minutes=10))
    _reply(conn, w, ch, t1, NOW - timedelta(minutes=9), "합치기 준비를 마쳤습니다.")
    engine = make_engine(s)
    try:
        assert "report" in await _needs(engine, w)                        # 넘긴 기록 없음 · 중계 설정 모름 — 사람에게
        _act(conn, w, "relay-out", 0, f"report:{t1}")
        assert "report" in await _needs(engine, w, {"foreman": (True, True)})   # 넘기기 실패 — 사람에게(묻히지 않게)
        _act(conn, w, "relay-out", 1, f"report:{t1}")
        n = await _needs(engine, w)
        assert n.get("relayed", {}).get("kind") == "report" and "report" not in n
        assert n["relayed"]["kinds"] == ["report"]                        # 넘기지 못한 기록(ok=0)은 kinds에 안 든다
        # 묻는 말인데 보고로 넘겼으면(relay_questions 꺼짐) 사람에게 물음 그대로
        t2 = _turn(conn, w, 2, "human", NOW - timedelta(minutes=8))
        _reply(conn, w, ch, t2, NOW - timedelta(minutes=7), "두 길이 있습니다.\n\n(가)로 할지 (나)로 할지 정해 주세요")
        _act(conn, w, "relay-out", 1, f"report:{t2}")
        n = await _needs(engine, w)
        assert "asks" in n and "relayed" not in n
        _act(conn, w, "relay-out", 1, f"question:{t2}")
        n = await _needs(engine, w)
        assert n.get("relayed", {}).get("kind") == "question" and "asks" not in n
        # 같은 턴(t2)을 보고로도 넘겼다 — kinds에 둘 다(화면은 「관리자에게 보고함」이 이긴다, 11-13 사용자)
        assert n["relayed"]["kinds"] == ["question", "report"]
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_worker_grace_only_when_relay_on(env):
    s, conn = env
    ch = _char(conn)
    w = _session(conn, ch, "scribe", 3)
    # 모듈의 NOW는 불러올 때 시각이라 전체 시험에서는 수십 초 낡아 RELAY_GRACE(30초) 밖으로 나간다(11-13 관리자 — 그 자리에서 잰다)
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    t1 = _turn(conn, w, 1, "human", now - timedelta(seconds=30))
    _reply(conn, w, ch, t1, now - timedelta(seconds=10), "적었습니다.")
    engine = make_engine(s)
    try:
        assert await _needs(engine, w, {"foreman": (True, True)}) == {}           # 넘기는 중 — 잠깐 안 띄움
        assert "report" in await _needs(engine, w, {"foreman": (False, False)})   # 중계 꺼짐 — 사람에게
        assert "report" in await _needs(engine, w, {"runshoes": (True, True)})    # 다른 프로젝트만 켜짐
        with conn.cursor() as c:                                                  # 넘기는 시간이 지나도 기록 없음 — 사람에게
            c.execute("UPDATE event SET ts = %s WHERE session_id = %s", (now - RELAY_GRACE - timedelta(seconds=5), w))
            c.execute("UPDATE turn SET started_at = %s WHERE session_id = %s", (now - RELAY_GRACE - timedelta(seconds=30), w))
        assert "report" in await _needs(engine, w, {"foreman": (True, True)})
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_escalate_manager_only_read_and_answer(env):
    s, conn = env
    ch = _char(conn)
    m = _session(conn, ch, "manager", 4)
    w = _session(conn, ch, "coder", 5)
    sent = []

    class N:
        rules = SimpleNamespace(for_project=lambda p: SimpleNamespace(prefix="[FM]", digest=True))

        def send_direct(self, project, kind, sid, msg, rule=None, later=None):
            sent.append((project, kind, sid, msg, later))
    engine = make_engine(s)
    try:
        with pytest.raises(HTTPException) as e:
            await escalate(engine, w, "report", "보고", N())
        assert e.value.status_code == 403
        r = await escalate(engine, m, "report", "오늘 세 가지를 합쳤습니다", N())
        assert r["ok"] and sent[-1][1] == "escalate" and sent[-1][4] is True     # 보고 — 묶음
        q = await escalate(engine, m, "question", "런슈즈 배포를 오늘 할까요?", N())
        assert sent[-1][4] is False and "❓" in sent[-1][3]                       # 물음 — 바로(급함)
        n = await _needs(engine, m)
        assert n["escalate"]["report"]["id"] == r["id"] and n["escalate"]["question"]["text"].startswith("런슈즈")
        assert (await escalate_read(engine, m, r["id"]))["ok"]
        n = await _needs(engine, m)
        assert "report" not in n["escalate"] and "question" in n["escalate"]
        assert (await asks_off(engine, m))["ok"]                                  # [답 안 해도 됨] — 관리자가 올린 물음을 끔
        assert "escalate" not in await _needs(engine, m)
        # 새 물음 — 사람이 그 관리자에게 입력하면 사라진다
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (NOW - timedelta(minutes=5),))
        await escalate(engine, m, "question", "하나 더 묻습니다", N())
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (NOW - timedelta(minutes=5),))
        assert "question" in (await _needs(engine, m))["escalate"]
        _turn(conn, m, 1, "human", NOW - timedelta(minutes=1))
        assert "escalate" not in await _needs(engine, m)
    finally:
        await engine.dispose()


def test_relay_text_tells_how_to_escalate():
    for kind, head in (("report", RELAY_REPORT), ("question", RELAY_QUESTION)):
        t = relay_text(kind, "세션 280", "foreman", "끝남", 318)
        assert t.startswith(head)                                  # 머리는 그대로 — 조립기가 출처 relay를 가른다
        assert "POST /api/sessions/318/escalate" in t
    assert "{관리자 세션 id}" in escalate_hint(None)


def test_notify_records_relay_out(monkeypatch):
    """넘긴 결과를 작업 세션 쪽에 남긴다(성공 · 실패 모두). 실패면 지금처럼 바로 알린다."""
    from bridge import notify as nt
    rec = []

    async def fake_out(self, sid, ok, detail):
        rec.append((sid, ok, detail))

    async def fake_emit(self, c, rule, sid, tid, reason, msg, urgent, relayed):
        rec.append(("emit", urgent, relayed))
        return None

    class Eng:
        def begin(self):
            class C:
                async def __aenter__(self_):
                    return None

                async def __aexit__(self_, *a):
                    return None
            return C()

    class M:
        def __init__(self, ok):
            self.ok = ok

        async def relay(self, *a):
            return {"delivered": self.ok, "manager": True, "reason": None if self.ok else "x"}
    monkeypatch.setattr(nt.Notifier, "_relay_out", fake_out)
    monkeypatch.setattr(nt.Notifier, "_emit_turn", fake_emit)
    n = nt.Notifier(Eng(), nt.Rules(), None, None)
    plan = {"rule": None, "project": "foreman", "relay": "question", "session_id": 7, "turn_id": 99, "label": "x",
            "body": "b", "msg": "m", "urgent": True, "reason": "stop"}
    n.managers = M(True)
    asyncio.run(n._relay_turn(plan))
    assert rec[0] == (7, True, "question:99") and rec[1] == ("emit", False, "question")
    rec.clear()
    n.managers = M(False)
    asyncio.run(n._relay_turn(plan))
    assert rec[0] == (7, False, "question:99") and rec[1][1] is True       # 못 넘김 — 바로 알림
