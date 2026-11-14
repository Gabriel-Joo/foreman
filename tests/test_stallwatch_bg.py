"""뒤에서 도는 일이 오래 걸리는지(11-14, bridge/stallwatch.py judge_bg) — 판정만 시험한다(DB · tmux 없이)."""

import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.stallwatch import BG_LONG, BG_QUIET, Sample, StallWatch, bg_output_mtime, bg_output_stat, fmt_elapsed, judge, judge_bg

NOW = datetime(2026, 11, 14, 8, 0)


def bg(task="bT", tool="Bash", mins=60, quiet_mins=None, desc="pytest 전체", size=100):
    return {"task": task, "tool": tool, "description": desc, "since": NOW - timedelta(minutes=mins),
            "out_mtime": None if quiet_mins is None else NOW - timedelta(minutes=quiet_mins),
            "out_size": None if quiet_mins is None else size}


def test_never_output_is_plain_notice_not_stalled():
    # 끝에서만 출력하는 명령(`| tail`) — 파일이 비어 있다. 만든 때가 오래돼도 「멈춤」이 아니다
    f = judge_bg(Sample(sid=1, live=True, bg=[bg(mins=130, quiet_mins=130, size=0)]), NOW)
    assert len(f) == 1 and f[0]["stalled"] is False and "한 번도 없습니다" in f[0]["detail"]
    assert "멈췄을 수" not in f[0]["detail"] and "2시간 10분째" in f[0]["detail"]
    # 빈 파일이 방금 만들어졌어도(30분 넘게 돌았다면) 오래 돈다는 알림은 한 번 간다
    assert len(judge_bg(Sample(sid=1, live=True, bg=[bg(mins=40, quiet_mins=1, size=0)]), NOW)) == 1
    # 30분 안이면 조용
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(mins=20, quiet_mins=20, size=0)]), NOW) == []


def test_output_then_stopped_is_stalled_and_growing_is_normal():
    f = judge_bg(Sample(sid=1, live=True, bg=[bg(mins=130, quiet_mins=60, size=5)]), NOW)
    assert len(f) == 1 and f[0]["stalled"] is True and "멈췄을 수 있습니다" in f[0]["detail"]
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(mins=130, quiet_mins=3, size=5)]), NOW) == []


def test_short_background_is_quiet():
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(mins=29, quiet_mins=29)]), NOW) == []
    assert BG_LONG == timedelta(minutes=30)


def test_long_with_growing_output_is_normal():
    # 오래 돌아도 출력이 계속 늘면 정상(헛경보 없음)
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(mins=180, quiet_mins=2)]), NOW) == []
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(mins=180, quiet_mins=14)]), NOW) == []


def test_long_with_quiet_output_is_stalled():
    f = judge_bg(Sample(sid=7, live=True, bg=[bg(mins=130, quiet_mins=125)]), NOW)
    assert len(f) == 1 and f[0]["kind"] == "bg_long" and f[0]["stalled"] is True
    assert f[0]["key"] == "stall:bg_long:7:bT" and f[0]["since"] == NOW - timedelta(minutes=130)
    assert "2시간 10분째" in f[0]["detail"] and "멈췄을 수 있습니다" in f[0]["detail"]
    f = judge_bg(Sample(sid=7, live=True, bg=[bg(mins=40, quiet_mins=BG_QUIET.seconds // 60)]), NOW)
    assert len(f) == 1 and f[0]["stalled"] is True


def test_long_without_output_file_is_plain_notice():
    f = judge_bg(Sample(sid=1, live=True, bg=[bg(mins=45)]), NOW)
    assert len(f) == 1 and f[0]["stalled"] is False and "출력 파일을 찾지 못했습니다" in f[0]["detail"]


def test_monitor_and_dead_session_are_skipped():
    assert judge_bg(Sample(sid=1, live=True, bg=[bg(tool="Monitor", mins=300, quiet_mins=300)]), NOW) == []
    assert judge_bg(Sample(sid=1, live=False, bg=[bg(mins=300, quiet_mins=300)]), NOW) == []


def test_one_finding_per_task_and_judge_includes_it():
    s = Sample(sid=3, live=True, bg=[bg("a", mins=90, quiet_mins=80), bg("b", mins=50, quiet_mins=1), bg("c", mins=70)])
    assert [f["task"] for f in judge_bg(s, NOW)] == ["a", "c"]
    # 쉬는 세션(턴 닫힘 · busy 아님)이어도 judge가 낸다
    assert [f["kind"] for f in judge(s, NOW)] == ["bg_long", "bg_long"]


def test_elapsed_text():
    assert [fmt_elapsed(timedelta(minutes=m)) for m in (5, 60, 130, 25 * 60)] == ["5분", "1시간", "2시간 10분", "1일 1시간"]


def test_output_mtime_reads_task_file_and_rejects_odd_ids(tmp_path, monkeypatch):
    root = tmp_path / f"claude-{os.getuid()}" / "proj" / "cc-1" / "tasks"
    root.mkdir(parents=True)
    f = root / "bx.output"
    f.write_text("..")
    t = datetime(2026, 11, 14, 1, 2, 3, tzinfo=UTC).timestamp()
    os.utime(f, (t, t))
    monkeypatch.setattr("bridge.stallwatch.glob.glob", lambda pat: [str(f)] if "cc-1/tasks/bx.output" in pat else [])
    assert bg_output_mtime("cc-1", "bx") == datetime(2026, 11, 14, 1, 2, 3)
    assert bg_output_stat("cc-1", "bx") == (datetime(2026, 11, 14, 1, 2, 3), 2)
    empty = root / "be.output"
    empty.write_text("")
    monkeypatch.setattr("bridge.stallwatch.glob.glob", lambda pat: [str(empty)] if "tasks/be.output" in pat else [str(f)])
    assert bg_output_stat("cc-1", "be")[1] == 0               # 크기 0 = 한 번도 출력이 안 나옴
    monkeypatch.setattr("bridge.stallwatch.glob.glob", lambda pat: [str(f)] if "cc-1/tasks/bx.output" in pat else [])
    assert bg_output_mtime("cc-2", "bx") is None
    assert bg_output_mtime("../x", "bx") is None and bg_output_mtime("cc-1", "a/b") is None and bg_output_mtime(None, "bx") is None


# ---- DB를 거친 길: 끝 없는 bg_start → 화면 snapshot + 알림 한 번 ----
@pytest.mark.db
async def test_bg_long_check_alerts_once_and_clears_on_end():
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
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    CC = "cccccccc-0000-0000-0000-0000000000bg"
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'foreman' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', %s, '시험', 'user')", (char, CC))
        sid = c.lastrowid
        for task, tool, mins in (("bLong", "Bash", 90), ("bShort", "Bash", 5), ("bMon", "Monitor", 300)):
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, target, payload) VALUES "
                      "(%s, %s, 'transcript', %s, 'bg_start', %s, %s, %s)",
                      (sid, char, now - timedelta(minutes=mins), tool, task, json.dumps({"description": "pytest 전체"})))

    class Notifier:
        def __init__(self):
            self.sent = []
            self.rules = SimpleNamespace(for_project=lambda n: None)

        def send_direct(self, project, kind, session_id, msg, rule=None):
            self.sent.append((session_id, msg, rule))

    engine = make_engine(s)
    n = Notifier()
    w = StallWatch(engine, n, "/없음")
    w.live = lambda d: {CC: SimpleNamespace(pid=1, state="S")}
    w.status = lambda d, pid: "idle"                  # 턴을 닫고 쉬는 세션

    async def screen(pid):
        return None
    w.screen = screen
    try:
        keys = await w.check(now)
        assert keys == [f"stall:bg_long:{sid}:bLong"] and n.sent[0][0] == sid
        assert "뒤에서 도는 일이 오래 걸림" in n.sent[0][1] and "pytest 전체" in n.sent[0][1]
        assert [f["kind"] for f in w.snapshot[sid]] == ["bg_long"]
        with conn.cursor() as c:                      # 진짜 알림기는 rule 키를 남긴다 → 다시 재도 한 번뿐
            c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('stall', 'sent', %s, 'x')", (keys[0],))
        assert await w.check(now + timedelta(minutes=1)) == []
        with conn.cursor() as c:
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, target, payload) VALUES "
                      "(%s, %s, 'transcript', %s, 'bg_end', 'bLong', %s)", (sid, char, now, json.dumps({})))
        await w.check(now + timedelta(minutes=2))
        assert sid not in w.snapshot                  # 끝 알림이 오면 사라진다
    finally:
        await engine.dispose()
        conn.close()
