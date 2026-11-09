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
