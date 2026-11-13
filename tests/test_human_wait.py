"""권한 거부 30분 알림(11-09, bridge/human_wait.py) — foreman_test DB에 세션 · 사람 턴 · CC 거부 이벤트를 넣고 판정."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.human_wait import DeniedWatch

CC = "dddddddd-0000-0000-0000-000000000000"
DENY = ("Permission for this action was denied by the Claude Code auto mode classifier. "
        "Reason: [External System Writes]. If you have other tasks ...")


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda n: SimpleNamespace(prefix="[런슈즈]") if n == "runshoes" else None)

    def send_direct(self, project, kind, session_id, msg, rule=None):
        self.sent.append((project, kind, session_id, msg, rule))


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


@pytest.mark.db
async def test_denied_alert_after_30min_once_and_not_while_busy(env):
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'runshoes' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', %s, '비교 페이지', 'user')", (char, CC))
        sid = c.lastrowid
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (sid, now - timedelta(hours=1)))
        c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, status, payload) VALUES "
                  "(%s, %s, 'transcript', %s, 'tool_result', 'Bash', 'error', %s)",
                  (sid, char, now - timedelta(minutes=40), json.dumps({"error_preview": DENY})))
    engine = make_engine(s)
    notifier = FakeNotifier()
    w = DeniedWatch(engine, notifier, "/nonexistent")
    state = {"status": "idle"}
    w.live = lambda d: {CC: SimpleNamespace(pid=1, state="S")}
    w.status = lambda d, pid: state["status"]
    try:
        # 일하는 중이면(거부 뒤 다른 방법으로 이어 감) 알리지 않는다
        state["status"] = "busy"
        assert await w.check(now) == []
        # 쉬는 중 · 거부 뒤 40분 → 한 번
        state["status"] = "idle"
        assert await w.check(now - timedelta(minutes=15)) == []                  # 거부 뒤 25분 — 아직
        keys = await w.check(now)
        assert len(keys) == 1 and notifier.sent[-1][1] == "denied" and notifier.sent[-1][2] == sid
        msg = notifier.sent[-1][3]
        assert msg.startswith("[런슈즈] ✋ 권한 거부 40분째") and "Bash · 이유 [External System Writes]" in msg
        with conn.cursor() as c:                                                  # 진짜 알림기는 rule 키로 남긴다
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('denied', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(minutes=5)) == []                   # 같은 거부는 다시 안 보낸다
        # 사람이 다시 입력하면 풀린다
        with conn.cursor() as c:
            c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 2, 'human', %s)", (sid, now))
        conn.commit()
        assert await w.check(now + timedelta(hours=2)) == []
        # 꺼진 세션은 보지 않는다
        w.live = lambda d: {}
        assert await w.check(now + timedelta(hours=3)) == []
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_denied_clears_when_session_moves_on(env):
    """11-11 펫퍼민트 227 — 거부 뒤 다른 방법으로 지나가면(도구 결과가 더 옴) · 다음 턴이 시작되면 사람 입력 없이도 꺼진다.
    거부 뒤 글만 쓰고 멈추면 그대로 남는다."""
    from bridge.api.dashboard import human_needs
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'runshoes' LIMIT 1")
        (char,) = c.fetchone()
        sids = []
        for i in range(3):
            c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                      "VALUES (%s, 'agent', 'coder', %s, 't', 'user')", (char, CC[:-1] + str(i)))
            sid = c.lastrowid
            sids.append(sid)
            c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (sid, now - timedelta(hours=1)))
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, status, payload) VALUES "
                      "(%s, %s, 'transcript', %s, 'tool_result', 'Bash', 'error', %s)",
                      (sid, char, now - timedelta(minutes=40), json.dumps({"error_preview": DENY})))
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, status, payload) VALUES "
                      "(%s, %s, 'transcript', %s, 'assistant_msg', 'working', %s)",
                      (sid, char, now - timedelta(minutes=39), json.dumps({"block": "text", "text": "막혔습니다."})))
        a, b, d = sids
        # a: 거부 뒤 다른 명령이 지나감(같은 시각이어도 id가 뒤면 뒤)
        c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, status, payload) VALUES "
                  "(%s, %s, 'transcript', %s, 'tool_result', 'Bash', 'done', '{}')", (a, char, now - timedelta(minutes=40)))
        # b: 다음 턴(사람 아닌 주입)이 시작됨
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 2, 'inject', %s)", (b, now - timedelta(minutes=5)))
    engine = make_engine(s)
    try:
        async with engine.connect() as cn:
            needs = await human_needs(cn, "(" + ",".join(map(str, sids)) + ")")
        assert "denied" not in (needs.get(a) or {})
        assert "denied" not in (needs.get(b) or {})
        assert needs[d]["denied"]["tool"] == "Bash"           # 글만 쓰고 멈춤 — 남는다
        # 남은 세션도 다시 거부되면 다시 뜬다(마지막 거부 기준)
        with conn.cursor() as c:
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, status, payload) VALUES "
                      "(%s, %s, 'transcript', %s, 'tool_result', 'Bash', 'error', %s)",
                      (a, char, now - timedelta(minutes=1), json.dumps({"error_preview": DENY})))
        async with engine.connect() as cn:
            needs = await human_needs(cn, f"({a})")
        assert needs[a]["denied"]["at"]
    finally:
        await engine.dispose()


SAFEGUARD = ("API Error: Claude Code is unable to respond to this request, which appears to violate our Usage Policy. "
             "Details: [reasoning_extraction] req_011CAbCdEfGh12345")


@pytest.mark.db
async def test_api_stop_snapshot_and_reminder_once(env):
    """11-13 API 오류로 멈춘 세션 — 마지막 턴이 stop_failure로 닫혔고 새 턴이 없으면 api_stops에 실리고(대시보드 · 화면),
    30분 지나도 그대로면 텔레그램 한 번 더(키 apistop:<세션>:<턴>). 일하는 중 · 멈춰 둔(T) · 꺼진 세션은 빼고, 새 턴이 시작되면 풀린다."""
    from bridge.api.dashboard import api_stops
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    ended = now - timedelta(minutes=45)
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'runshoes' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', %s, '첫 턴', 'user')", (char, CC))
        sid = c.lastrowid
        # 앞 턴은 보통 끝, 마지막 턴은 API 오류로 끝(첫 턴 17초 — 11-12 코더 311 꼴)
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at, ended_at, end_reason) VALUES (%s, 1, 'human', %s, %s, 'stop')",
                  (sid, now - timedelta(hours=2), now - timedelta(hours=2) + timedelta(minutes=3)))
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at, ended_at, end_reason) VALUES (%s, 2, 'human', %s, %s, 'stop_failure')",
                  (sid, ended - timedelta(seconds=17), ended))
        tid = c.lastrowid
        # hook 쪽(error 값만)과 트랜스크립트 쪽(글) — 글이 있는 것이 이긴다
        c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, payload) VALUES "
                  "(%s, %s, %s, 'transcript', %s, 'error', %s)", (sid, char, tid, ended, json.dumps({"error": "invalid_request", "text": SAFEGUARD})))
        c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, payload) VALUES "
                  "(%s, %s, %s, 'hook', %s, 'error', %s)", (sid, char, tid, ended, json.dumps({"error": "invalid_request"})))
    engine = make_engine(s)
    notifier = FakeNotifier()
    w = DeniedWatch(engine, notifier, "/nonexistent")
    state = {"status": "idle", "proc": "S"}
    w.live = lambda d: {CC: SimpleNamespace(pid=1, state=state["proc"])}
    w.status = lambda d, pid: state["status"]
    try:
        async with engine.connect() as cn:
            a = (await api_stops(cn, f"({sid})"))[sid]
        assert (a["turn_id"], a["kind"], a["detail"], a["request_id"]) == (tid, "safeguard", "reasoning_extraction", "req_011CAbCdEfGh12345")
        assert a["at"] == ended.isoformat(timespec="seconds") + "Z" and a["line"].startswith("안전 분류기 거부 [reasoning_extraction]")
        # 일하는 중 · 멈춰 둔(T) 세션은 다시 알리지 않는다
        state["status"] = "busy"
        assert await w.check(now) == []
        state["status"], state["proc"] = "idle", "T"
        assert await w.check(now) == []
        state["proc"] = "S"
        assert await w.check(now - timedelta(minutes=20)) == []                    # 끝난 뒤 25분 — 아직
        keys = await w.check(now)
        assert keys == [f"apistop:{sid}:{tid}"]
        _, kind, ssid, msg, rule = notifier.sent[-1]
        assert (kind, ssid, rule) == ("apistop", sid, keys[0])
        assert msg.startswith("[런슈즈] ⚠ API 오류로 멈춤 45분째 — 「첫 턴」") and "▶ 안전 분류기 거부 [reasoning_extraction]" in msg
        with conn.cursor() as c:                                                    # 진짜 알림기는 rule 키로 남긴다
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('apistop', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(hours=1)) == []                       # 한 번만(브리지를 다시 띄워도 — DB 키)
        # 꺼진 세션은 보지 않는다
        w.live = lambda d: {}
        notifier.sent.clear()
        with conn.cursor() as c:
            c.execute("DELETE FROM notification WHERE rule = %s", (keys[0],))
        assert await w.check(now) == []
        # 다음 턴이 시작되면(어떤 출처든) 풀린다
        with conn.cursor() as c:
            c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 3, 'agent_message', %s)", (sid, now))
        async with engine.connect() as cn:
            assert await api_stops(cn, f"({sid})") == {}
    finally:
        await engine.dispose()
