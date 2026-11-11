"""세션이 살아 있는지 · 멈췄는지(11-11, bridge/stallwatch.py) — 판정과, 알림이 어떤 조건에서 울리는지."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.stallwatch import LOOP_SAME, Sample, StallWatch, judge

NOW = datetime(2026, 11, 11, 3, 0)
EXIT_SCREEN = "Background work is running\n 1. Exit and stop tasks\n 2. Move to background and exit\n 3. Stay"


def kinds(found):
    return [f["kind"] for f in found]


def test_judge_quiet_cases():
    # 쉬는 세션 · 바쁘지만 기록이 이어지는 세션 · 짧은 작업 — 아무것도 없다
    assert judge(Sample(sid=1, live=True), NOW) == []
    assert judge(Sample(sid=1, live=True, busy=True, turn_started=NOW - timedelta(minutes=50),
                        last_event=NOW - timedelta(minutes=29)), NOW) == []
    # 끝난 세션인데 열린 턴이 없음 — 정상 끝남
    assert judge(Sample(sid=1, live=False), NOW) == []


def test_judge_each_kind():
    assert kinds(judge(Sample(sid=1, live=False, turn_started=NOW - timedelta(minutes=5)), NOW)) == ["died"]
    f = judge(Sample(sid=1, live=True, busy=True, turn_started=NOW - timedelta(minutes=40), last_event=NOW - timedelta(minutes=31),
                     last_tool=("Bash", "until ! pgrep -f x; do sleep 3; done")), NOW)
    assert kinds(f) == ["silent"] and "31분째" in f[0]["detail"] and "Bash until" in f[0]["detail"]
    f = judge(Sample(sid=1, live=True, busy=True, turn_started=NOW - timedelta(minutes=20), last_event=NOW,
                     same=("Bash", "pytest -q", LOOP_SAME)), NOW)
    assert kinds(f) == ["loop"] and "6번" in f[0]["detail"]
    assert kinds(judge(Sample(sid=1, live=True, turn_started=NOW - timedelta(minutes=20), last_event=NOW, errors=8), NOW)) == ["loop"]
    assert kinds(judge(Sample(sid=1, live=True, screen=EXIT_SCREEN), NOW)) == ["exit_confirm"]
    assert kinds(judge(Sample(sid=1, live=True, busy=True, turn_started=NOW - timedelta(hours=3), last_event=NOW), NOW)) == ["long"]


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda n: SimpleNamespace(prefix="[포먼]") if n == "foreman" else None)

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
async def test_alerts_fire_once_per_condition(env):
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    CC_A, CC_B = "aaaaaaaa-0000-0000-0000-00000000005a", "bbbbbbbb-0000-0000-0000-00000000005b"
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'foreman' LIMIT 1")
        (char,) = c.fetchone()
        sids = []
        for cc in (CC_A, CC_B):
            c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                      "VALUES (%s, 'agent', 'coder', %s, '시험', 'user')", (char, cc))
            sids.append(c.lastrowid)
        a, b = sids
        # A: 작업 중 — 35분 전 Bash 하나 뒤로 기록 없음
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (a, now - timedelta(minutes=40)))
        ta = c.lastrowid
        c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, tool, target, payload) VALUES "
                  "(%s, %s, %s, 'transcript', %s, 'tool_use', 'Bash', 'until ! pgrep -f x', %s)",
                  (a, char, ta, now - timedelta(minutes=35), json.dumps({})))
        # B: 같은 파일을 7번 고침 — 보통 코딩이라 맴돎이 아니다(LOOP_QUIET)
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (b, now - timedelta(minutes=10)))
        tb = c.lastrowid
        for i in range(7):
            c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, tool, target, payload) VALUES "
                      "(%s, %s, %s, 'transcript', %s, 'tool_use', 'Edit', 'bridge/api/dashboard.py', %s)",
                      (b, char, tb, now - timedelta(minutes=9 - i), json.dumps({})))
    engine = make_engine(s)
    notifier = FakeNotifier()
    w = StallWatch(engine, notifier, "/없음")
    live = {CC_A: SimpleNamespace(pid=1, state="S"), CC_B: SimpleNamespace(pid=2, state="S")}
    status = {1: "busy", 2: "idle"}
    screens = {2: "> "}
    w.live = lambda d: live
    w.status = lambda d, pid: status[pid]

    async def screen(pid):
        return screens.get(pid)
    w.screen = screen
    try:
        keys = await w.check(now)
        assert [k.split(":")[1] for k in keys] == ["silent"] and notifier.sent[-1][2] == a
        assert notifier.sent[-1][3].startswith("[포먼] ⏸ 응답 없음 — 「시험」(세션")
        assert w.snapshot[a][0]["kind"] == "silent" and b not in w.snapshot
        with conn.cursor() as c:                                    # 진짜 알림기는 rule 키로 남긴다
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('stall', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(minutes=1)) == []        # 같은 멈춤은 한 번

        # B: 끝내기 확인 창 — 처음 본 뒤 2분이 지나야 알린다
        screens[2] = EXIT_SCREEN
        assert await w.check(now + timedelta(minutes=2)) == [] and w.snapshot[b][0]["kind"] == "exit_confirm"
        keys = await w.check(now + timedelta(minutes=4, seconds=1))
        assert [k.split(":")[1] for k in keys] == ["exit_confirm"] and notifier.sent[-1][2] == b
        # 창이 닫히면 화면에서 사라진다
        screens[2] = "> "
        await w.check(now + timedelta(minutes=5))
        assert b not in w.snapshot

        # A: 프로세스가 사라짐(열린 턴은 그대로) → 작업 중 끊김
        del live[CC_A]
        keys = await w.check(now + timedelta(minutes=6))
        assert [k.split(":")[1] for k in keys] == ["died"] and notifier.sent[-1][2] == a
        # 멈춰 둔(T) 세션은 보지 않는다
        live[CC_A] = SimpleNamespace(pid=1, state="T")
        with conn.cursor() as c:
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('stall', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(minutes=7)) == [] and a not in w.snapshot
        # 알림기가 없어도 잰다(화면용)
        del live[CC_A]
        w.notifier = None
        assert await w.check(now + timedelta(minutes=8)) == [] and w.snapshot[a][0]["kind"] == "died"
    finally:
        await engine.dispose()
