"""세션이 살아 있는지 · 멈췄는지(11-11, bridge/stallwatch.py) — 판정과, 알림이 어떤 조건에서 울리는지."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.stallwatch import LOOP_SAME, Sample, StallWatch, judge, most_repeated, same_key

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


SCR = "/tmp/claude-1000/-home-kopo17-AI-programming-foreman--worktrees-foreman/650c0556-d474-4162-a78f-0d9bba82f90a/scratchpad"


def test_same_key_strips_prefixes():
    # 11-11 디자이너 273: 앞머리 S=<긴 경로>; 만 같고 뒤가 다른 명령
    assert same_key("Bash", f"S={SCR}; for t in a b; do .venv/bin/python $S/shot.py $t; done") == \
        "for t in a b; do .venv/bin/python $S/shot.py $t; done"
    T = 'T=$(grep FOREMAN_API_TOKEN .env | cut -d= -f2-); curl -s -H "Authorization: Bearer $T" http://127.0.0.1:8000/api/x'
    assert same_key("Bash", T) == 'curl -s -H "Authorization: Bearer $T" http://127.0.0.1:8000/api/x'
    assert same_key("Bash", "cd /a/b && export X=1; set -e; timeout 60 env A=1 B=2 .venv/bin/pytest -q") == ".venv/bin/pytest -q"
    assert same_key("Bash", "FOO=1 pytest   -q") == "pytest -q"
    assert same_key("Bash", "# 확인\nsource .venv/bin/activate && ls") == "ls"
    # 파이프 앞은 명령의 일부 · 앞머리뿐인 명령은 그대로 · 다른 도구는 대상 그대로
    assert same_key("Bash", "cat a | grep b") == "cat a | grep b"
    assert same_key("Bash", "cd /a") == "cd /a"
    assert same_key("Read", "/x/y.py") == "/x/y.py"


def test_loop_prefix_only_same_is_not_loop():
    # 앞머리만 같은 여덟 명령 — 예전(앞 160자로 묶기)엔 8번, 이제는 1번씩
    evs = [("Bash", f"S={SCR}; .venv/bin/python $S/shot.py {t} > $S/o_{i}.txt") for i, t in enumerate("abcdefgh")]
    assert most_repeated(evs)[2] == 1


def test_loop_true_repeat_is_caught():
    # 진짜 같은 명령 되풀이(앞머리가 달라도 같은 일) — 잡는다
    evs = [("Bash", f"cd /w{i % 2} && .venv/bin/pytest -q tests/test_x.py") for i in range(LOOP_SAME)]
    r = most_repeated(evs)
    assert r == ("Bash", ".venv/bin/pytest -q tests/test_x.py", LOOP_SAME)
    f = judge(Sample(sid=1, live=True, busy=True, turn_started=NOW - timedelta(minutes=20), last_event=NOW, same=r), NOW)
    assert kinds(f) == ["loop"] and "pytest" in f[0]["detail"]
    # 사이에 읽기 · 찾기만 끼어도 맴돎이다(고친 것이 없다)
    evs2 = [e for x in evs for e in (x, ("Read", "tests/test_x.py"), ("Grep", "foo"))]
    assert most_repeated(evs2)[2] == LOOP_SAME


def test_loop_fix_and_rerun_is_progress():
    # 고치고 다시 돌리기 — 사이에 Edit(또는 MCP 쓰기)이 있으면 처음부터 센다
    evs = []
    for i in range(10):
        evs += [("Bash", ".venv/bin/pytest -q"), ("Edit", "bridge/x.py")]
    assert most_repeated(evs)[2] == 1
    evs = [e for _ in range(8) for e in (("mcp__claude_ai_Notion__notion-update-page", "p1"), ("Bash", "git diff"))]
    assert most_repeated(evs)[2] == 1


def test_loop_counts_per_subagent():
    # 병렬 서브에이전트 아홉이 저마다 같은 준비 동작 — 맴돎이 아니다(10-21 런슈즈 156)
    evs = [("ToolSearch", "select:WebSearch", sub) for sub in range(820, 829)]
    assert most_repeated(evs)[2] == 1
    # 한 서브에이전트가 혼자 되풀이하면 잡는다 · 다른 에이전트의 Edit은 그 셈을 지우지 않는다
    evs = [e for _ in range(LOOP_SAME) for e in (("Bash", "curl -s x", 5), ("Edit", "a.py", 6))]
    assert most_repeated(evs)[2] == LOOP_SAME


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
        # B: 앞머리(S=<긴 경로>;)만 같고 뒤가 다른 Bash 8개 — 맴돎이 아니다(11-11 디자이너 273 오판)
        for i in range(8):
            c.execute("INSERT INTO event (session_id, character_id, turn_id, source, ts, type, tool, target, payload) VALUES "
                      "(%s, %s, %s, 'transcript', %s, 'tool_use', 'Bash', %s, %s)",
                      (b, char, tb, now - timedelta(minutes=2, seconds=-i), f"S={SCR}; ls $S/o_{i}.png", json.dumps({})))
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
