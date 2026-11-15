"""세션이 살아 있는지 · 멈췄는지(11-11, bridge/stallwatch.py) — 판정과, 알림이 어떤 조건에서 울리는지."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.stallwatch import LOOP_SAME, Sample, StallWatch, dialog_key, judge, judge_dialog, most_repeated, same_key
from test_inject_screen import HEAD, MODEL, PERMISSION, PROMPT, UNKNOWN

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


# 계획 승인 창 — CC 2.1.325 실측(11-14 362 시험, 120×40). 패널이 updatedInput 없이 허용하면 이 창이 그대로 남았다(359)
PLAN = HEAD + f"""
● Updated plan
  ⎿  /plan to preview
  {"─" * 116}
   Ready to code?
   Here is Claude's plan:
  {"╌" * 116}
   Plan
   Run ls.
  {"╌" * 116}
  {"─" * 116}
   Claude has written up a plan and is ready to execute. Would you like to proceed?
   ❯ 1. Yes, and use auto mode
     2. Yes, manually approve edits
     3. Tell Claude what to change
        shift+tab to approve with this feedback
   ctrl+g to edit in Vim · ~/.claude/plans/test-only-plan-1-peppy-cosmos.md
"""


def test_judge_dialog_kinds():
    """11-14 362 — 쉬는 세션에 뜬 창: 결정 창 · 모르는 창(+ waiting) · 안내 창 · 브리지 카드가 있으면 뺌."""
    idle = dict(sid=1, live=True, cc_status="waiting")
    f = judge_dialog(Sample(**idle, screen=PLAN), NOW)
    assert kinds(f) == ["dialog"] and "「계획 승인」 창" in f[0]["detail"] and f[0]["notify"]
    assert kinds(judge_dialog(Sample(**idle, screen=PERMISSION), NOW)) == ["dialog"]
    assert kinds(judge(Sample(**idle, screen=PLAN), NOW)) == ["dialog"]                   # judge에도 실린다
    # 브리지가 기다리는 승인이 있으면 카드가 이미 보인다 — 겹치지 않는다
    assert judge_dialog(Sample(**idle, screen=PLAN, pending=1), NOW) == []
    # 입력 칸만 — 아무것도 없다(CC가 waiting을 적었어도)
    assert judge_dialog(Sample(**idle, screen=PROMPT), NOW) == []
    # 모르는 창은 CC도 기다린다고 적었을 때만
    assert kinds(judge_dialog(Sample(**idle, screen=UNKNOWN), NOW)) == ["dialog"]
    assert judge_dialog(Sample(sid=1, live=True, cc_status="idle", screen=UNKNOWN), NOW) == []
    # 안내 창(/model) — 화면에만
    f = judge_dialog(Sample(sid=1, live=True, cc_status="idle", screen=MODEL), NOW)
    assert kinds(f) == ["notice"] and f[0]["notify"] is True       # 11-14 — 안내 창도 오래 떠 있으면 알린다(2분)
    assert "안내 창이 떠 있어 세션이 입력을 못 받습니다. 대화창을 확인해 주세요" in f[0]["detail"]
    # 끝내기 확인 창은 예전 kind 그대로
    assert kinds(judge_dialog(Sample(sid=1, live=True, screen=EXIT_SCREEN), NOW)) == ["exit_confirm"]
    # 화면을 못 읽음(tmux 밖) — status waiting + 승인 없음이면
    assert kinds(judge_dialog(Sample(**idle), NOW)) == ["dialog"]
    assert judge_dialog(Sample(**idle, pending=2), NOW) == []
    assert judge_dialog(Sample(sid=1, live=True, cc_status="idle"), NOW) == []
    # 일하는 중 · 끝난 세션은 보지 않는다
    assert judge_dialog(Sample(sid=1, live=True, busy=True, screen=PLAN), NOW) == []
    assert judge_dialog(Sample(sid=1, live=False, screen=PLAN), NOW) == []


def test_judge_dialog_after_timeout_is_quiet():
    """승인 대기 시간이 지나 브리지가 이미 「대화창에서만」을 알렸으면 30분 동안은 화면에만."""
    s = Sample(sid=1, live=True, cc_status="waiting", screen=PERMISSION, last_appr=("timeout", NOW - timedelta(minutes=5)))
    f = judge_dialog(s, NOW)
    assert kinds(f) == ["dialog"] and f[0]["notify"] is False and "대기 시간이 지나" in f[0]["detail"]
    s.last_appr = ("timeout", NOW - timedelta(minutes=31))
    assert judge_dialog(s, NOW)[0]["notify"] is True
    s.last_appr = ("allowed", NOW - timedelta(minutes=1))       # 359 — 허용을 보냈는데 창이 남음 → 알린다
    assert judge_dialog(s, NOW)[0]["notify"] is True


def test_dialog_key_changes_with_window():
    assert dialog_key(Sample(sid=1, live=True, screen=PROMPT)) is None
    assert dialog_key(Sample(sid=1, live=True, screen=PLAN)) == "decision:계획 승인"
    assert dialog_key(Sample(sid=1, live=True, screen=PERMISSION)) == "decision:도구 권한 묻기"
    assert dialog_key(Sample(sid=1, live=True, cc_status="waiting")) == "waiting"
    assert dialog_key(Sample(sid=1, live=True, busy=True, screen=PLAN)) is None


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

        # B: 계획 승인 창(11-14 359 꼴) — 브리지 카드가 기다리는 동안은 조용하고, 패널이 허용했는데 창이 남으면 2분 뒤 한 번
        status[2] = "waiting"
        screens[2] = PLAN
        with conn.cursor() as c:
            c.execute("INSERT INTO approval (session_id, tool, rule, status) VALUES (%s, 'ExitPlanMode', 'cc', 'pending')", (b,))
            appr = c.lastrowid
        assert await w.check(now + timedelta(minutes=5, seconds=10)) == [] and b not in w.snapshot
        with conn.cursor() as c:
            c.execute("UPDATE approval SET status = 'allowed', decided_by = 'browser', decided_at = %s WHERE id = %s",
                      (now + timedelta(minutes=5, seconds=20), appr))
        assert await w.check(now + timedelta(minutes=6)) == [] and w.snapshot[b][0]["kind"] == "dialog"
        keys = await w.check(now + timedelta(minutes=7, seconds=11))     # 처음 본 때(5분 10초)에서 2분
        assert [k.split(":")[1] for k in keys] == ["dialog"] and notifier.sent[-1][2] == b
        assert "「계획 승인」 창" in notifier.sent[-1][3] and "대화창에서 답합니다" in notifier.sent[-1][3]
        status[2], screens[2] = "idle", "> "
        await w.check(now + timedelta(minutes=7, seconds=30))
        assert b not in w.snapshot

        # B: 안내 창(/model 꼴, 11-14) — 결정 창과 같게 처음 본 뒤 2분이 지나야 한 번 알린다
        screens[2] = MODEL
        assert await w.check(now + timedelta(minutes=8)) == [] and w.snapshot[b][0]["kind"] == "notice"
        assert await w.check(now + timedelta(minutes=9, seconds=50)) == []       # 1분 50초 — 아직
        keys = await w.check(now + timedelta(minutes=10, seconds=1))
        assert [k.split(":")[1] for k in keys] == ["notice"] and notifier.sent[-1][2] == b
        assert "안내 창이 떠 있어 세션이 입력을 못 받습니다" in notifier.sent[-1][3]
        with conn.cursor() as c:
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('stall', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(minutes=11)) == []                  # 같은 창은 한 번
        screens[2] = "> "
        await w.check(now + timedelta(minutes=12))
        assert b not in w.snapshot                                               # 창이 닫히면 사라진다

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
