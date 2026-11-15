"""2단계 조립 — 합성 트랜스크립트로 foreman_test DB에 적재해 본다.  pytest -m db

실측(11-02)에서 본 모양만 쓴다: promptId · turnOrigin · toolUseResult.agentId · <task-notification> 태그 ·
content 블록마다 쪼개진 줄 · api-request 줄 · 개행 없는 마지막 줄.
"""

import asyncio
import json
from pathlib import Path

import pymysql
import pytest

from bridge.assembler import Assembler
from bridge.config import Settings
from bridge.db.migrate import main as migrate_main
from bridge.db.engine import make_engine
from bridge.mask import Masker
from bridge.transcript.watcher import Watcher


def _fake_live_session(sessions_dir, status):
    """테스트 프로세스 자신을 살아 있는 CC로 꾸민다(procStart를 /proc에서 맞춘다)."""
    import os
    pid = os.getpid()
    start = open(f"/proc/{pid}/stat").read().rsplit(") ", 1)[1].split()[19]
    (sessions_dir / f"{pid}.json").write_text(json.dumps({"pid": pid, "sessionId": SID, "cwd": CWD,
                                                         "procStart": start, "status": status}), encoding="utf-8")


async def test_abandoned_when_next_prompt_comes_much_later(env):
    """응답 없는 입력 뒤 다음 입력이 1시간 넘어 오면 merged가 아니라 abandoned(Esc가 첫 응답 전에 눌린 경우 등)."""
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("\n".join([
        user(U(901), "a1", "잘못 붙여넣은 입력", origin={"kind": "human"}, ts="2026-10-01T00:00:00.000Z"),
        user(U(902), "a2", "두 시간 뒤 입력", origin={"kind": "human"}, ts="2026-10-01T02:00:00.000Z"),
        user(U(903), "a3", "곧바로 다음 입력", origin={"kind": "human"}, ts="2026-10-01T02:00:20.000Z"),
    ]) + "\n", encoding="utf-8")
    await run(s)
    assert q(s, "SELECT prompt_id, end_reason FROM turn ORDER BY seq") == (
        ("a1", "abandoned"), ("a2", "merged"), ("a3", None))
    assert q(s, "SELECT ended_at FROM turn WHERE prompt_id = 'a1'")[0][0].hour == 0   # 마지막 활동 시각으로 닫는다


async def test_sweep_abandons_idle_live_session_turn(env, tmp_path):
    """프로세스는 살아 있는데 CC가 일하지 않고 열린 턴이 1시간 넘게 조용하면 정리 작업이 abandoned로 닫는다."""
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text(user(U(911), "b1", "Esc로 바로 중단한 입력", origin={"kind": "human"}) + "\n", encoding="utf-8")
    _fake_live_session(tmp_path / "sessions", "busy")
    asm = await run(s)
    assert await asm.sweep() == 0                                                  # CC가 일하는 중 — 닫지 않는다
    _fake_live_session(tmp_path / "sessions", "idle")
    assert await asm.sweep() == 1
    assert q(s, "SELECT end_reason, closed_by FROM turn WHERE prompt_id = 'b1'") == (("abandoned", "sweep"),)
    assert q(s, "SELECT detached_at FROM character_session")[0][0] is None          # 세션은 살아 있다


async def test_session_title_from_ai_title(env):
    """6단계 — 세션을 알아보는 이름은 CC의 ai-title(대화가 흘러가며 바뀐다). 바뀔 때만 쓴다, 빈 칸은 채운다."""
    s, main = env
    main.write_text("\n".join([
        MAIN[0],
        dumps({"type": "ai-title", "sessionId": SID, "aiTitle": "첫 제목"}),
        dumps({"type": "ai-title", "sessionId": SID, "aiTitle": "첫 제목"}),
        dumps({"type": "ai-title", "sessionId": SID, "aiTitle": f"배포 정리 MY_TOKEN={SECRET}"}),
    ]) + "\n", encoding="utf-8")
    asm = await run(s)
    title = q(s, "SELECT title FROM character_session")[0][0]
    assert title.startswith("배포 정리") and SECRET not in title
    q_conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                             password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    q_conn.cursor().execute("UPDATE character_session SET title = NULL")
    q_conn.close()
    assert await asm.fill_titles() == 1
    assert q(s, "SELECT title FROM character_session")[0][0].startswith("배포 정리")

pytestmark = pytest.mark.db

CWD = "/home/kopo17/AI_programming/foreman"
PROJ = "-home-kopo17-AI-programming-foreman"
SID = "11111111-2222-4333-8444-555555555555"
SECRET = "supersecretvalue123"


def U(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))  # CC가 쓰는 모양(공백 없음)


def line(**kw) -> str:
    base = {"sessionId": SID, "cwd": CWD, "version": "2.1.316"}
    return dumps(base | kw)


def user(uuid, pid, text, **kw):
    return line(type="user", uuid=uuid, promptId=pid, timestamp=kw.pop("ts", "2026-10-01T00:00:00.000Z"),
                message={"role": "user", "content": text}, **kw)


def asst(uuid, mid, block, out=10, ts="2026-10-01T00:00:01.000Z", **kw):
    return line(type="assistant", uuid=uuid, timestamp=ts, requestId="req_1",
                message={"id": mid, "model": "claude-opus-5-5", "stop_reason": None, "content": [block],
                         "usage": {"input_tokens": 2, "output_tokens": out, "cache_read_input_tokens": 100,
                                   "cache_creation_input_tokens": 5}}, **kw)


def result(uuid, pid, tuid, body, err=False, tur=None):
    kw = {"toolUseResult": tur} if tur else {}
    return line(type="user", uuid=uuid, promptId=pid, timestamp="2026-10-01T00:00:02.000Z",
                message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": tuid, "content": body,
                                                      "is_error": err}]}, **kw)


def system(uuid, sub, **kw):
    return line(type="system", subtype=sub, uuid=uuid, timestamp="2026-10-01T00:00:03.000Z", **kw)


NOTIF = ("<task-notification>\n<task-id>abc123</task-id>\n<tool-use-id>toolu_A</tool-use-id>\n"
         "<output-file>/tmp/x</output-file>\n<status>completed</status>\n<summary>sub done</summary>\n"
         "<usage><subagent_tokens>777</subagent_tokens><tool_uses>3</tool_uses><duration_ms>4000</duration_ms></usage>\n"
         "</task-notification>")

MAIN = [
    user(U(1), "p1", "첫 지시", origin={"kind": "human"}, turnOrigin="human", promptSource="typed"),
    asst(U(2), "msg_1", {"type": "thinking", "thinking": "음"}),
    asst(U(3), "msg_1", {"type": "tool_use", "id": "toolu_A", "name": "Agent",
                         "input": {"description": "sub task", "prompt": "go", "subagent_type": "general-purpose",
                                   "run_in_background": True}}),
    result(U(4), "p1", "toolu_A", "launched", tur={"agentId": "abc123", "status": "async_launched"}),
    asst(U(5), "msg_2", {"type": "tool_use", "id": "toolu_B", "name": "Bash",
                         "input": {"command": f"MY_TOKEN={SECRET} " + "echo " + "a" * 1500}}),
    result(U(6), "p1", "toolu_B", "x" * 5000),
    dumps({"type": "api-request", "body": "big"}),
    asst(U(7), "msg_3", {"type": "text", "text": "끝"}),
    system(U(8), "turn_duration", durationMs=1234, messageCount=7),
    user(U(9), "p2", "두 번째", origin={"kind": "human"}, turnOrigin="human"),
    asst(U(10), "msg_4", {"type": "text", "text": "하는 중"}),
    user(U(11), "p2", "[Request interrupted by user]"),
    system(U(12), "turn_duration", durationMs=500),
    user(U(13), "p3", NOTIF, origin={"kind": "task-notification"}, turnOrigin="task_notification"),
    asst(U(14), "msg_5", {"type": "text", "text": "알림 받음"}),
    dumps({"type": "queue-operation", "operation": "enqueue", "sessionId": SID,
                "timestamp": "2026-10-01T00:00:04.000Z", "content": "나중에"}),
    user(U(15), "p4", "네 번째", origin={"kind": "human"}, turnOrigin="human", ts="2026-10-01T00:00:05.000Z"),
]
PARTIAL = asst(U(16), "msg_6", {"type": "text", "text": "쓰는 중"})

SUB = [
    user(U(101), "sp1", "go", isSidechain=True, agentId="abc123"),
    asst(U(102), "msg_s1", {"type": "tool_use", "id": "toolu_S", "name": "Read", "input": {"file_path": "/x"}}, out=2,
         isSidechain=True, agentId="abc123"),
    result(U(103), "sp1", "toolu_S", "file body"),
    asst(U(104), "msg_s2", {"type": "text", "text": "다 읽음"}, out=3, isSidechain=True, agentId="abc123"),
]
META = {"agentType": "general-purpose", "description": "sub task", "toolUseId": "toolu_A", "spawnDepth": 1,
        "requestShape": "background", "finished": True}


@pytest.fixture
def env(tmp_path: Path):
    s = Settings(mysql_database="foreman_test", projects_root=tmp_path / "projects",
                 sessions_dir=tmp_path / "sessions", watch_enabled=False, ingest_chunk_bytes=4096)
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute("SET FOREIGN_KEY_CHECKS = 0")
        c.execute("SHOW TABLES")
        for (t,) in c.fetchall():
            c.execute(f"DROP TABLE `{t}`")
        c.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.close()
    assert migrate_main([], settings=s) == 0
    d = tmp_path / "projects" / PROJ
    (d / SID / "subagents").mkdir(parents=True)
    (tmp_path / "sessions").mkdir()
    main = d / f"{SID}.jsonl"
    main.write_text("\n".join(MAIN) + "\n" + PARTIAL, encoding="utf-8")
    (d / SID / "subagents" / "agent-abc123.jsonl").write_text("\n".join(SUB) + "\n", encoding="utf-8")
    (d / SID / "subagents" / "agent-abc123.meta.json").write_text(json.dumps(META), encoding="utf-8")
    return s, main


def q(s: Settings, sql: str, *args):
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database)
    with conn.cursor() as c:
        c.execute(sql, args)
        rows = c.fetchall()
    conn.close()
    return rows


ENGINES: list = []


@pytest.fixture(autouse=True)
async def _dispose():
    yield
    while ENGINES:
        await ENGINES.pop().dispose()


async def run(s: Settings) -> Assembler:
    engine = make_engine(s)
    ENGINES.append(engine)
    asm = Assembler(engine, s, Masker())
    await asm.load()
    await Watcher(s, asm).backfill()
    return asm


async def test_turns_messages_subagent(env):
    s, main = env
    asm = await run(s)
    turns = q(s, "SELECT prompt_id, origin, end_reason, closed_by, duration_ms FROM turn ORDER BY seq")
    assert turns == (("p1", "human", "stop", "transcript", 1234),
                     ("p2", "human", "interrupted", "transcript", 500),   # 중단이 먼저, duration은 나중에 채움
                     ("p3", "task_notification", "no_signal", "transcript", None),
                     ("p4", "human", None, None, None))
    # message.id 단위 — msg_1은 두 줄이지만 한 행. 개행 없는 msg_6은 아직 없다
    assert q(s, "SELECT COUNT(*) FROM message")[0][0] == 7
    assert q(s, "SELECT COUNT(*) FROM message WHERE id = 'msg_6'")[0][0] == 0
    assert asm.stats.skipped_api == 1
    sub = q(s, "SELECT s.agent_type, s.mode, s.status, s.reported_tokens, s.output_tokens_reliable, s.token_output, "
               "t1.prompt_id, t2.prompt_id FROM subagent_run s JOIN turn t1 ON t1.id = s.spawn_turn_id "
               "JOIN turn t2 ON t2.id = s.result_turn_id")
    assert sub == (("general-purpose", "background", "done", 777, 0, 5, "p1", "p3"),)
    # 자식 메시지 · 이벤트는 띄운 턴(p1)에 귀속
    assert q(s, "SELECT DISTINCT t.prompt_id FROM message m JOIN turn t ON t.id = m.turn_id WHERE m.subagent_id IS NOT NULL") == (("p1",),)
    assert q(s, "SELECT COUNT(*) FROM event WHERE subagent_id IS NOT NULL AND turn_id IS NULL")[0][0] == 0


async def test_target_mask_and_no_tool_body(env):
    s, _ = env
    await run(s)
    tgt, trunc, payload = q(s, "SELECT target, target_truncated, payload FROM event WHERE tool = 'Bash' AND type = 'tool_use'")[0]
    assert trunc == 1 and len(tgt) == 1024 and tgt.endswith("…")
    assert SECRET not in tgt and SECRET not in payload and "«masked»" in tgt
    body = q(s, "SELECT payload FROM event WHERE type = 'tool_result' AND tool = 'Bash'")[0][0]
    assert "xxxxx" not in body and json.loads(body)["chars"] == 5000


async def test_partial_then_complete_and_reread_no_dup(env):
    s, main = env
    await run(s)
    before = q(s, "SELECT (SELECT COUNT(*) FROM event), (SELECT COUNT(*) FROM message), (SELECT COUNT(*) FROM turn)")
    with main.open("a", encoding="utf-8") as f:
        f.write("\n")  # 쓰던 줄이 끝났다
    await run(s)
    assert q(s, "SELECT COUNT(*) FROM message WHERE id = 'msg_6'")[0][0] == 1
    mid = q(s, "SELECT (SELECT COUNT(*) FROM event), (SELECT COUNT(*) FROM message), (SELECT COUNT(*) FROM turn)")
    assert mid[0][1] == before[0][1] + 1
    q(s, "UPDATE transcript_file SET read_offset = 0")  # 처음부터 다시
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    conn.cursor().execute("UPDATE transcript_file SET read_offset = 0")
    conn.close()
    states = q(s, "SELECT prompt_id, end_reason, closed_by, ended_at, duration_ms, compacted FROM turn ORDER BY seq")
    await run(s)
    after = q(s, "SELECT (SELECT COUNT(*) FROM event), (SELECT COUNT(*) FROM message), (SELECT COUNT(*) FROM turn)")
    assert after == mid
    # 수만이 아니라 상태도 같아야 한다 — 마지막 턴(p4)은 여전히 열려 있다(옛 turn_duration이 닫으면 안 된다)
    assert q(s, "SELECT prompt_id, end_reason, closed_by, ended_at, duration_ms, compacted FROM turn ORDER BY seq") == states
    assert states[-1][:2] == ("p4", None)


async def test_sweep_closes_dead_session(env):
    s, _ = env
    asm = await run(s)
    assert await asm.sweep() == 1   # sessions/ 가 비어 있다 = 프로세스 없음
    assert q(s, "SELECT end_reason, closed_by FROM turn WHERE prompt_id = 'p4'") == (("session_end", "sweep"),)
    assert q(s, "SELECT detached_at IS NOT NULL FROM character_session")[0][0] == 1


async def test_hook_first_then_transcript_same_turn(env):
    s, main = env
    main.write_text("", encoding="utf-8")
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    asm = await run(s)
    hp = {"session_id": SID, "cwd": CWD, "transcript_path": str(main), "prompt": f"hook prompt MY_TOKEN={SECRET}"}
    await asm.apply_hook("UserPromptSubmit", hp)
    main.write_text(MAIN[0] + "\n", encoding="utf-8")       # 트랜스크립트가 뒤따라온다
    await Watcher(s, asm).backfill()
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD})
    with main.open("a", encoding="utf-8") as f:
        f.write(MAIN[7] + "\n")                              # 응답 줄이 Stop hook보다 늦게 쓰인다(실측)
        f.write(MAIN[8] + "\n")                              # turn_duration은 더 늦게
    await Watcher(s, asm).backfill()
    rows = q(s, "SELECT prompt_id, end_reason, closed_by, duration_ms, prompt_text FROM turn")
    assert len(rows) == 1
    pid, reason, by, dur, ptext = rows[0]
    assert (pid, reason, by, dur) == ("p1", "stop", "hook", 1234)
    assert SECRET not in ptext
    assert q(s, "SELECT COUNT(*) FROM event WHERE source = 'hook'")[0][0] == 2
    assert q(s, "SELECT COUNT(*) FROM event WHERE type = 'assistant_msg' AND turn_id IS NULL")[0][0] == 0


async def test_input_without_response_is_merged(env):
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("\n".join([
        user(U(201), "q1", NOTIF.replace("abc123", "zzz"), origin={"kind": "task-notification"}, turnOrigin="task_notification"),
        user(U(202), "q2", "Another Claude session sent a message: hi", isMeta=True),
        asst(U(203), "msg_q", {"type": "text", "text": "둘 다 봤다"}),
        system(U(204), "turn_duration", durationMs=10),
    ]) + "\n", encoding="utf-8")
    await run(s)
    assert q(s, "SELECT prompt_id, origin, end_reason FROM turn ORDER BY seq") == (
        ("q1", "task_notification", "merged"), ("q2", "agent_message", "stop"))


async def test_prompt_hook_while_turn_open_is_queued_input(env):
    """바쁠 때 보낸 입력에도 UserPromptSubmit이 불린다(3단계 실측) — 진행 중인 턴을 닫거나 새로 열면 안 된다."""
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text(MAIN[0] + "\n", encoding="utf-8")       # p1 열림(2026-10-01, 15초보다 오래 전)
    asm = await run(s)
    await asm.apply_hook("UserPromptSubmit", {"session_id": SID, "cwd": CWD, "prompt": "바쁠 때 보낸 것"})
    assert q(s, "SELECT prompt_id, end_reason FROM turn") == (("p1", None),)
    assert q(s, "SELECT type FROM event WHERE source = 'hook'") == (("queued",),)


# ── 4단계 알림 ──────────────────────────────────────────────
class FakeTG:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)


def _rules(tmp_path):
    from bridge.notify import load_rules
    p = tmp_path / "notify.toml"
    p.write_text('[telegram]\nsettle_s = 0\nmin_interval_s = 0\n[projects.foreman]\nprefix = "[포먼]"\n', encoding="utf-8")
    return load_rules(p)


async def _live(s, tmp_path):
    from bridge.notify import Notifier
    asm = await run(s)
    tg = FakeTG()
    n = Notifier(asm.engine, _rules(tmp_path), tg, Masker())
    n.start()
    await n.baseline()
    asm.on_turn_closed = n.on_turn_closed
    asm.on_subagents_changed = n.on_subagents_changed
    asm.live = True
    return asm, n, tg


async def _append(s, asm, main, *lines):
    with main.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    await Watcher(s, asm).backfill()


async def test_notify_stop_interrupt_and_dedupe(env, tmp_path):
    s, main = env
    main.write_text("\n".join(MAIN) + "\n", encoding="utf-8")     # p4가 열린 채
    asm, n, tg = await _live(s, tmp_path)
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD, "last_assistant_message": f"다 했다\nMY_TOKEN={SECRET}"})
    await n.drain()
    assert len(tg.sent) == 1 and tg.sent[0].startswith("[포먼] 끝남 · ")
    assert "요청: 네 번째" in tg.sent[0] and "응답: 다 했다" in tg.sent[0] and SECRET not in tg.sent[0]
    tid = q(s, "SELECT id FROM turn WHERE prompt_id = 'p4'")[0][0]
    n.on_turn_closed(1, tid, "stop", "transcript", None)                # 같은 턴의 두 번째 신호
    await _append(s, asm, main, user(U(301), "p5", "다섯 번째", origin={"kind": "human"}),
                  user(U(302), "p5", "[Request interrupted by user]"))
    await n.drain()
    assert len(tg.sent) == 2 and tg.sent[1].startswith("[포먼] ⏹ 중단됨(사용자)")
    assert q(s, "SELECT decision, COUNT(*) FROM notification GROUP BY decision") == (("sent", 2),)
    await n.stop()


async def test_notify_subagent_summary_hold_and_batch(env, tmp_path):
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await _append(s, asm, main,
                  user(U(401), "h1", "서브에이전트 띄워", origin={"kind": "human"}),
                  asst(U(402), "msg_h1", {"type": "tool_use", "id": "toolu_C", "name": "Agent",
                                          "input": {"description": "긴 조사", "subagent_type": "general-purpose",
                                                    "run_in_background": True}}),
                  result(U(403), "h1", "toolu_C", "launched", tur={"agentId": "sub2", "status": "async_launched"}),
                  asst(U(404), "msg_h2", {"type": "text", "text": "백그라운드로 돌린다"}),
                  system(U(405), "turn_duration", durationMs=900))
    await n.drain()
    assert len(tg.sent) == 1 and "서브에이전트 1 — 진행 1" in tg.sent[0]
    bash_notif = NOTIF.replace("<tool-use-id>toolu_A</tool-use-id>\n", "").replace("abc123", "bash1")
    await _append(s, asm, main,
                  user(U(406), "n1", bash_notif, origin={"kind": "task-notification"}, turnOrigin="task_notification"),
                  system(U(407), "turn_duration", durationMs=50))
    await n.drain()
    assert len(tg.sent) == 1                                            # 서브에이전트가 아직 돈다 → 보류
    assert q(s, "SELECT decision, rule FROM notification WHERE kind = 'batch'") == (("held", "subagents_running:1"),)
    done = NOTIF.replace("abc123", "sub2").replace("toolu_A", "toolu_C")
    await _append(s, asm, main,
                  user(U(408), "n2", done, origin={"kind": "task-notification"}, turnOrigin="task_notification"),
                  asst(U(409), "msg_n2", {"type": "text", "text": "결과 정리"}),
                  system(U(410), "turn_duration", durationMs=70))
    await n.drain()
    assert len(tg.sent) == 2 and tg.sent[1].startswith("[포먼] 백그라운드 서브에이전트 1개 모두 끝남")
    assert "- 긴 조사 (완료)" in tg.sent[1]
    await n.stop()


async def test_notify_skips_unassigned_and_merged(env, tmp_path):
    from bridge.notify import compose_turn
    s, main = env
    asm, n, tg = await _live(s, tmp_path)
    n.rules.projects.clear()                                            # 접두어 있는 프로젝트가 없다 = 미분류 취급
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD})
    await n.drain()
    assert tg.sent == [] and q(s, "SELECT rule FROM notification") == (("project:foreman",),)
    assert compose_turn("[x]", "stop_failure", "human", 5, "요청", None, "overloaded", []).startswith("[x] ⚠ API 오류로 멈춤 · 5초")
    await n.stop()


async def test_batch_sent_when_subagents_finish_without_turn_close(env, tmp_path):
    """완료 알림 줄은 기록됐지만 CC가 그 입력으로 모델 턴을 돌리지 않는 경우(4단계 실측) — 턴이 안 닫혀도 묶음은 나간다.
    사람 턴이 진행 중일 때는 보류(그 턴의 종료 알림이 요약해 싣는다)."""
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await _append(s, asm, main,
                  user(U(501), "h1", "띄워", origin={"kind": "human"}),
                  asst(U(502), "msg_b1", {"type": "tool_use", "id": "toolu_D", "name": "Agent",
                                          "input": {"description": "조사 D", "run_in_background": True}}),
                  result(U(503), "h1", "toolu_D", "launched", tur={"agentId": "subD", "status": "async_launched"}))
    done = NOTIF.replace("abc123", "subD").replace("toolu_A", "toolu_D")
    await asm.apply_hook("SubagentStop", {"session_id": SID, "cwd": CWD, "agent_id": "subD"})   # h1이 아직 열려 있다
    await n.drain()
    assert tg.sent == []                                                  # 부모 턴 진행 중 → 보류
    await _append(s, asm, main, system(U(504), "turn_duration", durationMs=10))   # 부모 턴 끝 → 요약에 실림
    await n.drain()
    assert len(tg.sent) == 1 and "서브에이전트 1 — 완료 1" in tg.sent[0]
    await _append(s, asm, main, user(U(505), "n9", done, origin={"kind": "task-notification"}, turnOrigin="task_notification"))
    await n.drain()                                                       # 완료 알림 턴(안 닫힘) — 이미 알렸으니 묶음 없음
    assert len(tg.sent) == 1
    await n.stop()


async def test_batch_after_parent_closed_by_subagent_stop_only(env, tmp_path):
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await _append(s, asm, main,
                  user(U(601), "h1", "띄워", origin={"kind": "human"}),
                  asst(U(602), "msg_c1", {"type": "tool_use", "id": "toolu_E", "name": "Agent",
                                          "input": {"description": "조사 E", "run_in_background": True}}),
                  result(U(603), "h1", "toolu_E", "launched", tur={"agentId": "subE", "status": "async_launched"}),
                  system(U(604), "turn_duration", durationMs=10))
    await n.drain()
    assert len(tg.sent) == 1 and "진행 1" in tg.sent[0]
    await asm.apply_hook("SubagentStop", {"session_id": SID, "cwd": CWD, "agent_id": "subE"})   # 턴은 안 닫힌다
    await n.drain()
    assert len(tg.sent) == 2 and tg.sent[1].startswith("[포먼] 백그라운드 서브에이전트 1개 모두 끝남")
    await n.stop()


async def test_subagent_fields_filled_after_hook_created_row(env, tmp_path):
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await _append(s, asm, main, user(U(701), "h1", "띄워", origin={"kind": "human"}))
    await asm.apply_hook("SubagentStart", {"session_id": SID, "cwd": CWD, "agent_id": "subF"})  # hook이 먼저 — 설명 없음
    await _append(s, asm, main,
                  asst(U(702), "msg_f1", {"type": "tool_use", "id": "toolu_F", "name": "Agent",
                                          "input": {"description": "조사 F", "subagent_type": "general-purpose"}}),
                  result(U(703), "h1", "toolu_F", "launched", tur={"agentId": "subF", "status": "async_launched"}))
    assert q(s, "SELECT description, agent_type, tool_use_id FROM subagent_run WHERE agent_id = 'subF'") == (
        ("조사 F", "general-purpose", "toolu_F"),)
    await n.stop()


async def test_hook_opened_handback_turn_is_batch_origin(env, tmp_path):
    s, main = env
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await asm.apply_hook("UserPromptSubmit", {"session_id": SID, "cwd": CWD, "prompt": '<agent-message from="abc123">\n결과'})
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD, "last_assistant_message": "받음"})
    await n.drain()
    assert tg.sent == []
    assert q(s, "SELECT origin, end_reason FROM turn") == (("subagent_message", "stop"),)
    await n.stop()


async def test_internal_subagent_stop_without_type_is_ignored(env, tmp_path):
    s, main = env
    main.write_text("", encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    await asm.apply_hook("SubagentStop", {"session_id": SID, "cwd": CWD, "agent_id": "internal1", "agent_type": ""})
    await n.drain()
    assert q(s, "SELECT COUNT(*) FROM subagent_run WHERE agent_id = 'internal1'")[0][0] == 0 and tg.sent == []
    await n.stop()


async def test_agent_message_from_own_subagent_vs_other_session(env, tmp_path):
    s, main = env
    main.write_text("\n".join(MAIN) + "\n", encoding="utf-8")   # 개행 없는 마지막 줄을 빼고 시작
    asm, n, tg = await _live(s, tmp_path)      # MAIN에 abc123 서브에이전트가 있다
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD})
    await _append(s, asm, main,
                  user(U(801), "g1", 'Another Claude session sent a message: <agent-message from="abc123">결과</agent-message>', isMeta=True),
                  system(U(802), "turn_duration", durationMs=5),
                  user(U(803), "g2", 'Another Claude session sent a message: <agent-message from="zzz-other">안녕</agent-message>', isMeta=True),
                  system(U(804), "turn_duration", durationMs=5))
    assert q(s, "SELECT prompt_id, origin FROM turn WHERE prompt_id IN ('g1', 'g2') ORDER BY prompt_id") == (
        ("g1", "subagent_message"), ("g2", "agent_message"))
    await n.stop()


# ── 5단계 승인 ──────────────────────────────────────────────
class FakePipe:
    def __init__(self):
        self.events, self.published = [], []

    def submit(self, ev):
        self.events.append(ev)

    def publish(self, msg):
        self.published.append(msg)


class FakeNotifier:
    def __init__(self):
        self.sent = []
        from bridge.notify import Rules
        self.rules = Rules()

    def send_direct(self, project, kind, session_id, msg):
        self.sent.append(msg)


async def _mgr(s, wait_s=5.0):
    from bridge.approval import load_policy
    from bridge.approvals import ApprovalManager
    asm = await run(s)
    pol = load_policy(Path(__file__).resolve().parent / "fixtures" / "approval_now.toml")   # 실제 설정 대신 11-14 고정물
    for pp in [pol.defaults, *pol.projects.values()]:
        pp.wait_s = wait_s
    pipe, notif = FakePipe(), FakeNotifier()
    mgr = ApprovalManager(asm.engine, pol, asm, pipe, Masker(), notif)
    await mgr.start()
    asm.on_tool_result = mgr.on_tool_result
    return mgr, pipe, notif


def _p(cmd, tuid="toolu_X", cwd=CWD, event="PreToolUse"):
    return {"session_id": SID, "cwd": cwd, "hook_event_name": event, "tool_name": "Bash",
            "tool_input": {"command": cmd}, "tool_use_id": tuid, "prompt_id": "p4", "permission_mode": "auto"}


async def test_pre_tool_use_enforce_and_observe(env):
    s, _ = env
    mgr, pipe, _ = await _mgr(s)
    out = mgr.pre_tool_use(_p("git status"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    out = mgr.pre_tool_use(_p("kubectl delete pvc data-x"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "데이터-삭제" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert mgr.pre_tool_use(_p("make build")) is None                         # pass — CC가 정한다
    assert mgr.pre_tool_use(_p("kubectl delete pvc data-x", cwd="/home/kopo17/AI_programming/runshoes")) is None  # 관찰
    await asyncio.sleep(0.3)
    got = [(e.payload["decision"], e.payload["enforced"]) for e in pipe.events]
    assert got == [("allow", True), ("ask", True), ("pass", False), ("ask", False)]   # 자동 통과 · 관찰도 기록


async def test_pre_tool_use_pgrep_self_match_denied_even_in_observe(env):
    """11-11 — pgrep -f가 자기 셸에 걸리면 승인 모드(관찰)와 상관없이 거부(bridge/pgrep_guard.py)."""
    s, _ = env
    mgr, _, _ = await _mgr(s)
    for cwd in (CWD, "/home/kopo17/AI_programming/runshoes"):
        out = mgr.pre_tool_use(_p('until ! pgrep -f "tools/screen.py"; do sleep 3; done', cwd=cwd))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "pgrep-자기걸림" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert mgr.pre_tool_use(_p("pgrep -af '[p]ytest' || echo 없음")) is None or \
        mgr.pre_tool_use(_p("pgrep -af '[p]ytest' || echo 없음"))["hookSpecificOutput"]["permissionDecision"] != "deny"


async def test_permission_browser_allow_and_deny(env):
    s, _ = env
    mgr, pipe, notif = await _mgr(s)
    mgr.pre_tool_use(_p("kubectl delete pvc data-x", tuid="toolu_B1"))
    task = asyncio.create_task(mgr.permission_request(_p("kubectl delete pvc data-x", event="PermissionRequest")))
    while not mgr.waiting:
        await asyncio.sleep(0.01)
    aid = next(iter(mgr.waiting))
    assert mgr.decide(aid, "allow", None) == "ok"
    out = await task
    assert out["hookSpecificOutput"]["decision"] == {"behavior": "allow"}
    assert notif.sent and "🔐 승인 대기 · Bash" in notif.sent[0] and "데이터-삭제" in notif.sent[0]
    assert q(s, "SELECT status, decided_by, rule, tool_use_id FROM approval WHERE id = %s", aid) == (
        ("allowed", "browser", "데이터-삭제", "toolu_B1"),)
    assert mgr.decide(aid, "deny", None) == "gone"                           # 이미 결정됨
    task = asyncio.create_task(mgr.permission_request(_p("kubectl delete pvc data-x", event="PermissionRequest")))
    while not mgr.waiting:
        await asyncio.sleep(0.01)
    mgr.decide(next(iter(mgr.waiting)), "deny", "운영 배포는 내가 직접 한다")
    out = await task
    assert out["hookSpecificOutput"]["decision"] == {"behavior": "deny", "message": "운영 배포는 내가 직접 한다"}


async def test_permission_browser_allow_exit_plan_mode(env):
    """11-14 — 패널에서 계획 승인을 허용하면 원래 입력(updatedInput) + setMode auto를 돌려준다.
    updatedInput이 없으면 CC가 계획 승인 창을 그대로 두고(359), setMode가 없으면 plan으로 띄운 세션이 manual로 떨어진다(362)."""
    s, _ = env
    mgr, _, _ = await _mgr(s)
    inp = {"planFilePath": "/home/kopo17/.claude/plans/x.md"}
    p = {**_p("x", event="PermissionRequest"), "tool_name": "ExitPlanMode", "tool_input": inp, "permission_mode": "plan"}
    task = asyncio.create_task(mgr.permission_request(p))
    while not mgr.waiting:
        await asyncio.sleep(0.01)
    assert mgr.decide(next(iter(mgr.waiting)), "allow", None) == "ok"
    out = await task
    assert out["hookSpecificOutput"]["decision"] == {
        "behavior": "allow", "updatedInput": inp,
        "updatedPermissions": [{"type": "setMode", "mode": "auto", "destination": "session"}]}


async def test_permission_terminal_first_and_timeout(env):
    s, _ = env
    mgr, pipe, _ = await _mgr(s, wait_s=0.5)
    mgr.pre_tool_use(_p("git push origin main", tuid="toolu_T1"))
    task = asyncio.create_task(mgr.permission_request(_p("git push origin main", event="PermissionRequest")))
    while not mgr.waiting:
        await asyncio.sleep(0.01)
    mgr.on_tool_result("toolu_T1", {"decision": "accept", "source": "user_temporary"})   # 터미널에서 먼저 답했다
    assert await task is None
    await asyncio.sleep(0.2)
    assert q(s, "SELECT status, decided_by, terminal_decision FROM approval")[0] == ("terminal", "terminal", "accept")
    out = await mgr.permission_request(_p("echo hi", event="PermissionRequest"))      # CC 자체 판단 · 아무도 안 답함
    assert out is None
    assert q(s, "SELECT status, rule FROM approval ORDER BY id DESC LIMIT 1") == (("timeout", "cc"),)


# ── 11-03 적재가 조용히 막힌 일 — resume · fork 세션, 재시도 안전장치, 스스로 알리기 ─────────────
SID2 = "22222222-3333-4444-8555-666666666666"


def _fork_lines() -> list[str]:
    """resume · fork로 만든 세션: 앞 세션 줄을 uuid째 복사하고 sessionId만 바꾸고 promptId는 뺀다(실측 bb19f9d2)."""
    copied = json.loads(MAIN[0])
    copied.pop("promptId")
    copied["sessionId"] = SID2
    a = json.loads(MAIN[1])
    a["sessionId"] = SID2
    return [dumps(copied), dumps(a),
            dumps(json.loads(user(U(201), "f1", "포크한 세션의 새 입력", origin={"kind": "human"},
                                  ts="2026-10-02T00:00:00.000Z")) | {"sessionId": SID2})]


async def test_forked_session_copied_prompt_does_not_block(env):
    s, main = env
    asm = await run(s)
    before = q(s, "SELECT COUNT(*) FROM turn")[0][0]
    (main.parent / f"{SID2}.jsonl").write_text("\n".join(_fork_lines()) + "\n", encoding="utf-8")
    w = Watcher(s, asm)
    await w.backfill()
    assert w.failures == {}                                            # 전에는 IntegrityError(uq_turn_prompt)로 영원히 재시도
    rows = q(s, "SELECT t.prompt_id, cs.cc_session_id FROM turn t JOIN character_session cs ON cs.id = t.session_id "
                "WHERE cs.cc_session_id = %s", SID2)
    assert rows == (("f1", SID2),)                                     # 복사된 앞 세션 프롬프트는 새 턴이 아니다
    assert q(s, "SELECT COUNT(*) FROM turn")[0][0] == before + 1
    assert asm.stats.copied_prompts == 1
    # 원래 세션의 턴 · 이벤트는 그대로(복사 줄의 이벤트는 uuid가 같아 겹쳐 버려진다)
    assert q(s, "SELECT cs.cc_session_id FROM turn t JOIN character_session cs ON cs.id = t.session_id "
                "WHERE t.prompt_uuid = %s", U(1)) == ((SID,),)


def _cli_fork_lines() -> list[str]:
    """claude --fork-session --resume로 만든 세션(11-05 실측 91b57a64): 복사 줄의 promptId가 빠지지 않고 새 프롬프트의
    promptId(f1)로 바뀐다. 앞에 이 세션의 queue-operation, 복사 구간에 DB에 이벤트가 없는 같은 턴의 둘째 user 줄."""
    def fork(raw: str, **kw) -> str:
        return dumps(json.loads(raw) | {"sessionId": SID2} | kw)
    return [dumps({"type": "queue-operation", "operation": "enqueue", "sessionId": SID2,
                   "timestamp": "2026-10-01T23:59:00.000Z", "content": "포크한 세션의 새 입력"}),
            fork(MAIN[0], promptId="f1"), fork(MAIN[1]), fork(MAIN[7]), fork(MAIN[8]),
            fork(user(U(300), "p1", "같은 턴의 둘째 줄"), promptId="f1"),
            fork(MAIN[9], promptId="f1"), fork(MAIN[10]), fork(MAIN[11], promptId="f1"), fork(MAIN[12]),
            fork(user(U(201), "f1", "포크한 세션의 새 입력", origin={"kind": "human"}, ts="2026-10-02T00:00:00.000Z")),
            fork(asst(U(202), "msg_f1", {"type": "text", "text": "새 답"}, ts="2026-10-02T00:00:01.000Z")),
            fork(system(U(203), "turn_duration", durationMs=900), timestamp="2026-10-02T00:00:02.000Z")]


async def test_cli_fork_copied_lines_with_new_prompt_id(env):
    s, main = env
    asm = await run(s)
    src = q(s, "SELECT id, prompt_text, prompt_uuid, ended_at, end_reason FROM turn ORDER BY id")
    (main.parent / f"{SID2}.jsonl").write_text("\n".join(_cli_fork_lines()) + "\n", encoding="utf-8")
    w = Watcher(s, asm)
    await w.backfill()
    assert w.failures == {}
    rows = q(s, "SELECT t.prompt_id, t.prompt_uuid, t.prompt_text, t.end_reason FROM turn t "
                "JOIN character_session cs ON cs.id = t.session_id WHERE cs.cc_session_id = %s", SID2)
    # 전에는 첫 복사 줄(첫 지시)이 이 턴을 열어 본문이 옛 프롬프트, prompt_uuid는 겹쳐서 NULL이었다
    assert rows == (("f1", U(201), "포크한 세션의 새 입력", "stop"),)
    assert asm.stats.copied_prompts == 4                                # 첫 지시 · 둘째 줄 · 두 번째 · 중단 표시
    assert q(s, "SELECT id, prompt_text, prompt_uuid, ended_at, end_reason FROM turn ORDER BY id")[:len(src)] == src
    ev = q(s, "SELECT e.type FROM event e JOIN character_session cs ON cs.id = e.session_id "
              "WHERE cs.cc_session_id = %s ORDER BY e.id", SID2)
    assert [r[0] for r in ev] == ["queued", "start", "assistant_msg", "stop"]


async def _retry(w: Watcher) -> None:
    for f in w.failures.values():
        f.retry_at = 0
    w._requeue()
    await w._drain()


async def test_failure_does_not_block_other_files_then_tolerant_then_skip(env):
    from bridge.transcript import watcher as wmod
    s, main = env
    engine = make_engine(s)
    ENGINES.append(engine)
    asm = Assembler(engine, s, Masker())
    await asm.load()
    real = asm._main_user

    async def bad(c, st, b, d, uid, ts, par):                          # 한 줄이 늘 결정적으로 실패한다
        if uid == U(9):
            raise ValueError("나쁜 줄")
        return await real(c, st, b, d, uid, ts, par)
    asm._main_user = bad
    w = Watcher(s, asm)
    await w.backfill()
    f = w.failures[str(main)]
    assert f.n == 1 and not f.transient and f.retry_at > 0
    assert q(s, "SELECT COUNT(*) FROM subagent_run")[0][0] == 1         # 다른 파일(서브에이전트)은 기다리지 않고 적재됐다
    for _ in range(wmod.TOLERANT_AFTER - 1):
        await _retry(w)
    assert w.failures[str(main)].n == wmod.TOLERANT_AFTER
    await _retry(w)                                                    # 너그러운 모드 — 나쁜 줄만 버린다
    assert str(main) not in w.failures
    assert [x["kind"] for x in w.skips] == ["records"] and w.skips[0]["count"] == 1
    assert {r[0] for r in q(s, "SELECT prompt_id FROM turn")} >= {"p1", "p3", "p4"}   # 나머지는 들어왔다
    assert asm.stats.skipped_records == 1


async def test_skip_chunk_last_resort_but_never_on_transient(env):
    from sqlalchemy.exc import OperationalError
    from bridge.transcript import watcher as wmod
    s, main = env
    engine = make_engine(s)
    ENGINES.append(engine)
    asm = Assembler(engine, s, Masker())
    await asm.load()
    kind = {"e": OperationalError("x", {}, Exception("연결 끊김"))}

    async def boom(*a, **k):                                           # 줄 밖(덩어리 단위)에서 실패 — 너그러운 모드로도 못 푼다
        raise kind["e"]
    asm._flush = boom
    w = Watcher(s, asm)
    await w.backfill()
    for _ in range(wmod.SKIP_AFTER + 2):
        await _retry(w)
    f = w.failures[str(main)]
    assert f.transient and f.n >= wmod.SKIP_AFTER and not w.skips      # DB 끊김은 건너뛰지 않는다 — 줄을 잃지 않는다
    kind["e"] = KeyError("결정적")
    f.n = 0
    for _ in range(wmod.SKIP_AFTER):
        await _retry(w)
    assert any(x["kind"] == "chunk" and x["path"] == str(main) for x in w.skips)
    assert q(s, "SELECT read_offset > 0 FROM transcript_file WHERE path = %s", str(main))[0][0] == 1


async def test_ingest_monitor_alerts_once_and_recovers(env):
    from types import SimpleNamespace
    from bridge.ingest_health import IngestMonitor
    from bridge.transcript.watcher import Failure
    s, main = env
    asm = await run(s)
    asm.live = True
    w = Watcher(s, asm)
    sent = []
    notifier = SimpleNamespace(rules=SimpleNamespace(for_project=lambda n: SimpleNamespace(prefix="[포먼]")),
                               send_direct=lambda p, k, sid, msg: sent.append((k, msg)))
    mon = IngestMonitor(w, asm, notifier, alert_s=60, tick_alert_s=120)
    import time as _t
    w.failures[str(main)] = Failure(9, _t.time() - 600, 0, "IntegrityError: (1062, Duplicate)", 0, False)
    mon.check()
    mon.check()
    assert len(sent) == 1 and sent[0][0] == "ingest" and "적재 막힘" in sent[0][1] and "[포먼]" in sent[0][1]
    assert mon.snapshot()["stuck"] and not mon.snapshot()["ok"]
    del w.failures[str(main)]
    mon.check()
    assert "적재 회복" in sent[-1][1] and mon.snapshot()["ok"]
    w.last_tick = _t.time() - 300                                      # 루프가 멈췄다
    mon.check()
    assert "와처 멈춤" in sent[-1][1]
    w.last_tick = _t.time()
    mon.check()
    assert "다시 돈다" in sent[-1][1]
    w._skip_note(type("K", (), {"path": str(main), "cc_session_id": SID})(), "chunk", 0, 100, 3, "KeyError")
    mon.check()
    mon.check()
    assert sum("건너뛰었다" in m for _, m in sent) == 1


# ── 11-05 세션 인계 — 요청 → 세션이 쓴 표지 → 저장 · 고치기 · 넣을 글, 되살리기는 FOREMAN이 멈춘 것만 ─────────
async def test_handoff_request_extract_edit_inject_preview(env, monkeypatch, tmp_path):
    from bridge import handoff as h
    from bridge.liveness import LiveSession
    s, main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    mgr = h.HandoffManager(engine, s.sessions_dir)
    mgr.wait_s = 20
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    row = await mgr.session(sid)
    sent = []

    async def fake_resolve(cc, d):
        return None, LiveSession(4242, cc, "/x", "S"), False

    async def fake_deliver(cc, text_, **kw):
        sent.append(text_)
        req = h.REQ_RE.search(text_).group(1)
        with open(main, "a", encoding="utf-8") as f:     # 세션이 답한 것처럼 — 요청 줄 + 표지 응답
            f.write("\n" + json.dumps({"type": "user", "message": {"content": text_}}, ensure_ascii=False) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text":
                    f"<<<FOREMAN-HANDOFF r={req}>>>\n## 다음 할 일\n- 시험\n<<<END r={req}>>>"}]}},
                    ensure_ascii=False) + "\n")
        return {"delivered": {"as": "prompt", "prompt_id": None}, "steps": [], "queued": False}
    monkeypatch.setattr(h, "resolve", fake_resolve)
    monkeypatch.setattr(h, "deliver", fake_deliver)
    monkeypatch.setattr(h, "live_sessions", lambda d: {SID: LiveSession(4242, SID, "/x", "S")})

    r = await mgr.request_live(row, "snapshot")
    assert r["status"] == "requested", r
    try:
        await mgr.request_live(row, "snapshot")
        raise AssertionError("두 번째 요청이 들어갔다")
    except h.Refused as e:
        assert "이미" in str(e)
    for _ in range(40):
        await asyncio.sleep(0.2)
        st = q(s, "SELECT status, body FROM summary WHERE id = %s", r["summary_id"])[0]
        if st[0] != "requested":
            break
    assert st == ("ok", "## 다음 할 일\n- 시험")
    e = await mgr.edit(r["summary_id"], "## 다음 할 일\n- 고친 것")
    assert q(s, "SELECT source, parent_id FROM summary WHERE id = %s", e["summary_id"]) == (("edited", r["summary_id"]),)
    assert (await mgr.latest_ok(sid))["id"] == e["summary_id"]
    inj = await mgr.injection(e["summary_id"])
    assert inj["text"].startswith(f"[FOREMAN 인계 r={e['req']}]") and "고친 것" in inj["text"] and not inj["cut"]
    assert "이 세션이 뜬 자리" not in inj["text"] and inj["worktree_next"] is False   # project_of 없음 — 예측 안 함
    # 받는 세션이 worktree면 넣는 글에 그 사실이 들어간다(본문보다 앞) — 11-09
    inj = await mgr.injection(e["summary_id"], "/r/proj/.worktrees/proj-2")
    t = inj["text"]
    assert "브랜치 `cc/proj-2`" in t and t.index("이 세션이 뜬 자리") < t.index("고친 것") and inj["worktree_next"] is False

    # 11-15 관리자 410 — 읽을 곳 줄 범위가 틀린 판 → 고친 본 저장 → 고친 판 id로 다시 검사하면 넣을 수 있다. 옛 판은 그대로 막힌다
    # (화면 [다시 시도]가 옛 판 id를 다시 보내 같은 글이 났다 — moveflow.js retrySummaryId가 고친 판을 고른다)
    doc = tmp_path / "w.md"
    doc.write_text("# w\n## 6. 합치기\nx\n", encoding="utf-8")
    bad = await mgr.edit(e["summary_id"], f"## 다음 할 일\n- 이어서\n## 읽을 곳\n- `{doc}:224-260` — 합치기")
    inj = await mgr.injection(bad["summary_id"])
    assert inj["blocked"].startswith("읽을 곳이 틀렸습니다.") and "파일은 3줄" in inj["blocked"] and "「6. 합치기」" in inj["blocked"]
    good = await mgr.edit(bad["summary_id"], f"## 다음 할 일\n- 이어서\n## 읽을 곳\n- `{doc}` 「6. 합치기」 — 합치기")
    assert (await mgr.injection(good["summary_id"]))["blocked"] is None
    assert (await mgr.injection(bad["summary_id"]))["blocked"]                     # 옛 판은 여전히 막힘
    try:
        await mgr.ensure_injectable(bad["summary_id"])
        raise AssertionError("옛 판이 넣어졌다")
    except h.Refused as e3:
        assert "줄 범위가 맞지 않습니다" in str(e3)
    # 고친 판도 틀리면 지금처럼 멈추고 까닭을 보인다
    worse = await mgr.edit(good["summary_id"], f"## 다음 할 일\n- 이어서\n## 읽을 곳\n- `{doc}` 「없는 절」 — x")
    assert "「없는 절」을(를) 찾지 못했습니다" in (await mgr.injection(worse["summary_id"]))["blocked"]

    # 되살리기 — FOREMAN이 멈춘 기록이 없으면 거부(사람이 멈춘 CC는 건드리지 않는다)
    monkeypatch.setattr(h, "live_sessions", lambda d: {SID: LiveSession(4242, SID, "/x", "T")})
    try:
        await mgr.action(row, "resume")
        raise AssertionError("사람이 멈춘 세션을 되살렸다")
    except h.Refused as e2:
        assert "FOREMAN이 멈춘" in str(e2)
    c = await mgr.controls(row)
    assert c["can"]["resume"] is False and "사람이 멈춤" in c["why"]
    await mgr._act(sid, "stop", 4242, True, "시험")
    assert (await mgr.controls(row))["can"]["resume"] is True


@pytest.mark.db
async def test_reassign_role_and_worktree_characters(env):
    """0017 재배치 · 띄울 때 캐릭터 고르기(11-05) — 새 세션은 포먼이 아니라 역할 캐릭터, worktree는 그 자리의 일꾼."""
    from bridge import handoff as h
    s, _ = env
    asm = await run(s)
    repo, _pid, name, char = asm.projects[0]
    foreman, coder = q(s, "SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = %s "
                          "AND c.current_role = 'foreman'", name)[0][0], char
    assert q(s, "SELECT name, current_role, parent_id FROM `character` WHERE id = %s", coder) == (("코더", "coder", foreman),)
    mgr = h.HandoffManager(asm.engine, s.sessions_dir, project_of=lambda cwd: asm._project_for(cwd, ""))
    assert await mgr._character_for(repo, "coder") == coder                       # 원본 폴더 코더는 하나
    insp = await mgr._character_for(repo, "inspector")
    assert q(s, "SELECT name, parent_id, spawned_by FROM `character` WHERE id = %s", insp) == (("조사", foreman, "foreman"),)
    # 11-15 점검 → 조사: 옛 이름 캐릭터가 있으면 새로 만들지 않고 이름을 바꿔 이어 쓴다
    from sqlalchemy import text as _t
    async with asm.engine.begin() as c:
        await c.execute(_t("UPDATE `character` SET name = '점검' WHERE id = :i"), {"i": insp})
    assert await mgr._character_for(repo, "inspector") == insp
    assert q(s, "SELECT name FROM `character` WHERE id = %s", insp) == (("조사",),)
    w = await mgr._character_for(f"{repo}/.worktrees/{name}-2", "coder")
    assert q(s, "SELECT name FROM `character` WHERE id = %s", w) == ((f"코더 {name}-2",),)
    row = h.SessionRow(1, None, w, f"{repo}/.worktrees/{name}-2", None, name, None)
    await mgr._retire_wt_characters(row, f"{name}-2")
    assert q(s, "SELECT retired_at IS NOT NULL FROM `character` WHERE id = %s", w) == ((1,),)
    assert await mgr._character_for(f"{repo}/.worktrees/{name}-2", "coder") == w   # 같은 이름이면 되살린다
    assert q(s, "SELECT retired_at FROM `character` WHERE id = %s", w) == ((None,),)
    assert await mgr._character_for("/tmp/elsewhere", "coder") is None             # 떠돌이는 그대로


# ── 11-05 인계 2판 ① 문서로 옮기기 — 목록(받은 인계의 「문서와 다른 지금」 같이) → 사람 고침 → 쓰기 → git 확인 ─────────
async def test_promote_list_edit_write_verify(env, monkeypatch, tmp_path):
    import subprocess
    from bridge import handoff as h
    from bridge import promote as pm
    from bridge.liveness import LiveSession
    s, main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    mgr = h.HandoffManager(engine, s.sessions_dir)
    mgr.promote = pr = pm.Promoter(mgr)
    pr.wait_s = 20
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    row = await mgr.session(sid)
    repo = tmp_path / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (repo / "CLAUDE.md").write_text("## 작업 규칙\n- a\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "처음")

    # 이 세션이 받은 2판 인계 — 그 「문서와 다른 지금」이 목록 요청에 같이 들어가야 한다
    v2 = "## 지금 상태\n- x\n## 문서와 다른 지금\n- 시험 세션은 끝낸 뒤 숨겨 왔음\n## 읽을 곳\n- `CLAUDE.md` — 규칙"
    async with engine.begin() as c:
        from sqlalchemy import text as T
        await c.execute(T("INSERT INTO summary (session_id, req, kind, source, status, body, injected_cc_session) "
                          "VALUES (:s, 'aaaaaa', 'handoff', 'self', 'ok', :b, :c)"), {"s": sid, "b": v2, "c": SID})
    sent, reply = [], {}

    async def fake_resolve(cc, d):
        return None, LiveSession(4242, cc, "/x", "S"), False

    async def fake_deliver(cc, text_, **kw):
        sent.append(text_)
        req = h.REQ_RE.search(text_).group(1)
        body = reply["fn"](req)
        with open(main, "a", encoding="utf-8") as f:
            f.write("\n" + json.dumps({"type": "user", "message": {"content": text_}}, ensure_ascii=False) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": body}]}},
                               ensure_ascii=False) + "\n")
        return {"delivered": {"as": "prompt", "prompt_id": None}, "steps": [], "queued": False}

    async def fake_root(cwd):
        return str(repo)
    monkeypatch.setattr(pm, "resolve", fake_resolve)
    monkeypatch.setattr(pm, "deliver", fake_deliver)
    monkeypatch.setattr(pm, "live_sessions", lambda d: {SID: LiveSession(4242, SID, "/x", "S")})
    monkeypatch.setattr(pm.ho, "repo_root", fake_root)

    async def settle(pid, wait_for):
        for _ in range(60):
            await asyncio.sleep(0.2)
            st = q(s, "SELECT status FROM promotion WHERE id = %s", pid)[0][0]
            if st not in wait_for:
                return st
        return st

    reply["fn"] = lambda r: (f"<<<FOREMAN-PROMOTE r={r}>>>\n" + json.dumps([
        {"kind": "기준", "what": "시험 세션은 끝낸 뒤 hidden_reason='test'로 숨긴다", "quote": "", "dest": "CLAUDE.md",
         "section": "작업 규칙", "why": "매번 지킬 것"},
        {"kind": "결정", "what": "그때뿐", "dest": "drop"}], ensure_ascii=False) + f"\n<<<END r={r}>>>")
    r = await pr.request(row)
    assert r["summary_id"] is not None and "시험 세션은 끝낸 뒤 숨겨 왔음" in sent[-1]
    try:
        await mgr.request_live(row, "snapshot")              # 옮기기를 기다리는 동안 인계 요청은 막는다
        raise AssertionError("겹쳐 보냈다")
    except h.Refused as e:
        assert "이미" in str(e)
    assert await settle(r["promotion_id"], ("requested",)) == "listed"
    lst = await pr.list(sid)
    assert [i["state"] for i in lst[0]["items"]] == ["pending", "dropped"] and lst[0]["items"][0]["check"]["ok"]
    assert (await mgr.latest_ok(sid))["req"] == "aaaaaa"     # 옮기기 목록은 인계 요약으로 섞이지 않는다

    try:
        await pr.write(r["promotion_id"])
        raise AssertionError("승인 없이 썼다")
    except h.Refused as e:
        assert "승인한 항목이 없습니다" in str(e)
    await pr.edit(r["promotion_id"], [{"id": 1, "state": "approved", "what": "시험 세션은 끝낸 뒤 숨긴다(test)"}])

    def do_write(req):                                       # 세션이 쓰고 커밋한 것처럼
        (repo / "CLAUDE.md").write_text("## 작업 규칙\n- a\n- 시험 세션은 끝낸 뒤 숨긴다(test)\n", encoding="utf-8")
        g("commit", "-qam", "인계 전 결정 기록: 시험 세션 숨김")
        return f"<<<FOREMAN-PROMOTED r={req}>>>\n" + json.dumps({"commit": g("rev-parse", "HEAD"), "files": ["CLAUDE.md"]}) + f"\n<<<END r={req}>>>"
    reply["fn"] = do_write
    w = await pr.write(r["promotion_id"])
    assert w["approved"] == 1 and '"what": "시험 세션은 끝낸 뒤 숨긴다(test)"' in sent[-1] and "그때뿐" not in sent[-1]
    assert await settle(r["promotion_id"], ("writing",)) == "written"
    p = (await pr.list(sid))[0]
    assert p["result"]["ok"] and p["commit_sha"] == g("rev-parse", "HEAD") and p["result"]["files"] == ["CLAUDE.md"]

    # 다시 써 보면 — 세션이 다른 파일까지 커밋하면 write_failed(조용히 지나가지 않는다)
    async with engine.begin() as c:
        await c.execute(T("UPDATE promotion SET status = 'listed' WHERE id = :i"), {"i": r["promotion_id"]})

    def bad_write(req):
        (repo / "CLAUDE.md").write_text("x\n", encoding="utf-8")
        (repo / "other.md").write_text("몰래\n", encoding="utf-8")
        g("add", "."), g("commit", "-qm", "인계 전 결정 기록: 몰래")
        return f"<<<FOREMAN-PROMOTED r={req}>>>\n{{}}\n<<<END r={req}>>>"
    reply["fn"] = bad_write
    await pr.write(r["promotion_id"])
    assert await settle(r["promotion_id"], ("writing",)) == "write_failed"
    assert "other.md" in q(s, "SELECT error FROM promotion WHERE id = %s", r["promotion_id"])[0][0]

    # 같이 넣을 인계가 여럿이면 말없이 첫째를 고르지 않는다(11-06 첫 사례 — #6 대신 #7이 들어갔다)
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO summary (session_id, req, kind, source, status, body) "
                          "VALUES (:s, 'bbbbbb', 'handoff', 'self', 'ok', :b)"), {"s": sid, "b": v2})
    n = len(sent)
    try:
        await pr.request(row)
        raise AssertionError("여럿인데 골랐다")
    except h.Refused as e:
        assert "골라" in str(e) and len(sent) == n                 # 보내지도 않는다
    reply["fn"] = lambda r: f"<<<FOREMAN-PROMOTE r={r}>>>\n[]\n<<<END r={r}>>>"
    r2 = await pr.request(row, no_input=True)
    assert r2["summary_id"] is None
    assert await settle(r2["promotion_id"], ("requested",)) == "listed"


async def test_background_bash_and_monitor_start_end(env):
    """백그라운드 Bash · Monitor(11-06) — 결과의 backgroundTaskId · taskId로 bg_start, 끝 알림으로 bg_end.
    끝 알림은 큐(enqueue) · 첨부(queued_command) · 사람 줄 어디로 와도 한 번만. Monitor 중간 이벤트(status 없음)는 끝이 아니다."""
    from bridge.api.dashboard import background_running
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm = await run(s)
    note = lambda task, tu, st: (f"<task-notification>\n<task-id>{task}</task-id>\n<tool-use-id>{tu}</tool-use-id>\n"  # noqa: E731
                                 + (f"<status>{st}</status>\n" if st else "<event>줄</event>\n") + "</task-notification>")
    await _append(s, asm, main,
                  user(U(601), "b1", "돌려", origin={"kind": "human"}),
                  asst(U(602), "msg_g1", {"type": "tool_use", "id": "toolu_B", "name": "Bash",
                                          "input": {"command": "sleep 99", "description": "판정 돌리기", "run_in_background": True}}),
                  result(U(603), "b1", "toolu_B", "started", tur={"stdout": "", "backgroundTaskId": "bgB"}),
                  asst(U(604), "msg_g2", {"type": "tool_use", "id": "toolu_M", "name": "Monitor",
                                          "input": {"command": "until x", "description": "브리지 기다림"}}),
                  result(U(605), "b1", "toolu_M", "started", tur={"taskId": "bgM", "timeoutMs": 60000}),
                  asst(U(606), "msg_g3", {"type": "tool_use", "id": "toolu_F", "name": "Bash", "input": {"command": "ls"}}),
                  result(U(607), "b1", "toolu_F", "a b", tur={"stdout": "a b"}),           # 보통 Bash는 아니다
                  line(type="queue-operation", operation="enqueue", timestamp="2026-10-01T00:00:04.000Z",
                       content=note("bgM", "toolu_M", None)))                               # Monitor 중간 이벤트
    rows = q(s, "SELECT type, tool, target, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.description')) FROM event "
                "WHERE type IN ('bg_start', 'bg_end') ORDER BY id")
    assert rows == (("bg_start", "Bash", "bgB", "판정 돌리기"), ("bg_start", "Monitor", "bgM", "브리지 기다림"))
    await _append(s, asm, main,
                  line(type="queue-operation", operation="enqueue", timestamp="2026-10-01T00:00:05.000Z",
                       content=note("bgB", "toolu_B", "completed")),
                  line(type="attachment", uuid=U(608), timestamp="2026-10-01T00:00:05.500Z",
                       attachment={"type": "queued_command", "prompt": note("bgB", "toolu_B", "completed")}),
                  user(U(609), "n1", note("bgB", "toolu_B", "completed"), origin={"kind": "task-notification"},
                       turnOrigin="task_notification"))
    ends = q(s, "SELECT target, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.status')) FROM event WHERE type = 'bg_end'")
    assert ends == (("bgB", "completed"),)                                  # 세 곳으로 왔어도 한 번
    # TaskStop으로 멈추면 알림이 오지 않는다 — 결과의 task_id로 끝(11-06)
    await _append(s, asm, main,
                  asst(U(610), "msg_g4", {"type": "tool_use", "id": "toolu_S", "name": "TaskStop", "input": {"task_id": "bgM"}}),
                  result(U(611), "n1", "toolu_S", '{"message":"Successfully stopped task: bgM"}',
                         tur={"message": "Successfully stopped task: bgM", "task_id": "bgM", "task_type": "local_bash"}))
    ends = q(s, "SELECT target, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.status')) FROM event WHERE type = 'bg_end' ORDER BY id")
    assert ends == (("bgB", "completed"), ("bgM", "stopped"))
    from datetime import datetime
    t0, t1 = datetime(2026, 10, 1, 0, 0, 2), datetime(2026, 10, 1, 0, 0, 9)
    rows = [("bgM", "Monitor", "브리지 기다림", t0)]
    assert [x["task"] for x in background_running(rows, None)] == ["bgM"]
    assert background_running(rows, t1) == []                              # 프로세스가 다시 뜬 뒤 — 그 전 작업은 죽었다


async def test_losscheck_run_list_recover_and_promote_input(env, monkeypatch, tmp_path):
    """[잃은 것 보기](d 2부, 11-06) — 시작 → 묶음마다 진행 → 끝 · 목록(사라짐 · 약해짐만), 같은 세션 겹침 막기,
    브리지 재시작 때 running 정리, 문서로 옮기기(c)의 같이 넣을 것."""
    from bridge import handoff as h
    from bridge import losscheck as lc
    from bridge import promote as pm
    from sqlalchemy import text as T
    s, main = env
    main.write_text("\n".join([
        user(U(701), "q1", "커밋은 의미 단위로 나눠", origin={"kind": "human"}, ts="2026-10-01T00:00:01.000Z"),
        user(U(702), "q2", "ttyd는 밖에 열지 마", origin={"kind": "human"}, ts="2026-10-01T00:00:02.000Z"),
        line(type="user", uuid=U(703), isCompactSummary=True, timestamp="2026-10-01T00:00:03.000Z",
             message={"role": "user", "content": "요약 0"}),
        user(U(704), "q3", "압축 뒤 지시", origin={"kind": "human"}, ts="2026-10-01T00:00:04.000Z"),
    ]) + "\n", encoding="utf-8")
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    mgr = h.HandoffManager(engine, s.sessions_dir)
    mgr.promote = pr = pm.Promoter(mgr)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# 규칙\n", encoding="utf-8")

    async def fake_root(cwd):
        return str(repo)
    monkeypatch.setattr(h, "repo_root", fake_root)
    monkeypatch.setattr(lc, "memory_dir", lambda cwd: tmp_path / "없는-메모리")
    chk = mgr.losscheck = lc.LossChecker(mgr, model="sonnet", root=tmp_path / "lcwork")
    seen = {}
    gate = asyncio.Event()

    async def fake_judge(wd, names, n_sum, repo_, req, on_group=None, **kw):
        seen.update(names=names, n_sum=n_sum, files=sorted(p.name for p in wd.iterdir()), model=kw.get("model"))
        items = [{"id": "구간0-0-a", "ts": "", "kind": "지시", "quote": "커밋은 의미 단위로 나눠", "gist": "커밋을 의미 단위로",
                  "status": "사라짐", "where": "", "dropped_at": "summary_00", "missing": "", "why_matters": "w"},
                 {"id": "구간0-1-a", "ts": "", "kind": "금지", "quote": "ttyd는 밖에 열지 마 MY_TOKEN=" + SECRET,
                  "gist": "ttyd 외부 노출 금지", "status": "약해짐", "where": "repo:README.md", "dropped_at": "summary_00",
                  "missing": "이유", "why_matters": ""},
                 {"id": "구간0-1-b", "ts": "", "kind": "결정", "quote": "", "gist": "옛 결정", "status": "뒤집힘", "where": "",
                  "dropped_at": None, "missing": "", "why_matters": ""}]
        runs = [{"group": "prompts_A.md", "prompts": 2, "items": 3, "empty": 0, "skipped": [], "ms": 10, "cost_usd": 0.12,
                 "usage": {"input_tokens": 5, "output_tokens": 7}, "error": None}]
        await gate.wait()
        await on_group(items, runs)
        return {"items": items, "runs": runs}
    chk.judge = fake_judge
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    row = await mgr.session(sid)
    r = await chk.start(row)
    try:
        await chk.start(row)
        raise AssertionError("겹쳐 돌렸다")
    except h.Refused as e:
        assert "이미" in str(e)
    gate.set()
    for _ in range(50):
        await asyncio.sleep(0.1)
        if q(s, "SELECT status FROM loss_check WHERE id = %s", r["loss_check_id"])[0][0] != "running":
            break
    assert seen["n_sum"] == 1 and [len(i) for _, i in seen["names"]] == [2] and seen["model"] == "sonnet"
    assert {"prompts_A.md", "summary_00.md", "current_context.md"} <= set(seen["files"])
    got = (await chk.list(sid))[0]
    assert got["status"] == "done" and got["prompts"] == 2 and got["groups_done"] == 1 and got["cost_usd"] == 0.12
    assert got["outcome"] == "found" and got["groups_failed"] == 0 and got["skipped"] == 0      # 11-13 없음 · 실패 가르기
    assert got["counts"] == {"사라짐": 1, "약해짐": 1, "뒤집힘": 1}
    assert [x["status"] for x in got["lost"]] == ["사라짐", "약해짐"]                 # 뒤집힘은 내지 않는다
    assert SECRET not in json.dumps(got, ensure_ascii=False)                          # 비밀값은 가려서 남긴다
    assert "usage" not in got["runs"][0] and got["runs"][0]["tokens"] == 12
    # c — 같이 넣을 것 맨 앞에 이 점검, 넣는 글에 사라짐 · 약해짐만
    ins = await pr.inputs(row)
    assert ins[0]["id"] == f"lc:{r['loss_check_id']}" and ins[0]["why"] == "사라짐 1 · 약해짐 1"
    body = await pr._loss_body(r["loss_check_id"], sid)
    assert "커밋을 의미 단위로" in body and "옛 결정" not in body
    assert "뒤집힌) 결정은 넣지 마라" in pm.list_prompt("abc123", loss=body, loss_id=r["loss_check_id"])
    try:
        await pr._loss_body(r["loss_check_id"], sid + 999)
        raise AssertionError("다른 세션의 점검을 넣었다")
    except h.Refused:
        pass
    # 브리지 재시작 — 돌던 것은 failed로
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO loss_check (session_id, status) VALUES (:s, 'running')"), {"s": sid})
    assert await chk.recover() == 1
    assert (await chk.list(sid))[0]["status"] == "failed"


async def test_notion_publish_update_unchanged_archive_and_scope(env, tmp_path):
    """Notion 게시(12c, 11-06) — main에 커밋된 원본만, 처음은 「회고」 아래 새 페이지, 같은 내용은 건너뜀, 바뀌면 같은 페이지 갈아 끼우기,
    내리기는 우리가 만든 페이지만 · 루트 아래일 때만. Notion에서 지워졌으면 새로 만든다."""
    import subprocess
    from bridge import notion as nt
    from tests.test_notion import FakeNotion
    s, _main = env
    engine = make_engine(s)
    ENGINES.append(engine)
    repo = tmp_path / "repo"
    (repo / "log").mkdir(parents=True)
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    f = repo / "log" / "retro_20261105_foreman.md"
    f.write_text("# 11-05 회고\n\n- 하나 [c:abc1234] [t:9]\n  - 둘\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "retro")
    fake = FakeNotion()
    pub = nt.Publisher(engine, fake, "root", str(repo))
    path = "log/retro_20261105_foreman.md"

    r1 = await pub.publish(path, "11-06 05:00")
    assert r1["action"] == "created" and fake.pages[r1["page_id"]]["title"] == "11-05 회고"
    sec = fake.pages[r1["page_id"]]["parent"]
    assert fake.pages[sec]["title"] == "회고" and fake.pages[sec]["parent"] == "root"        # 루트 > 회고 > 글
    top = fake.blocks[r1["page_id"]]
    assert top[0]["type"] == "callout" and "사본" in nt.plain(top[0]["callout"]["rich_text"])  # 맨 위 안내
    assert len(fake.blocks[top[1]["_id"]]) == 1                                              # 중첩 목록은 만든 뒤 붙였다
    assert "9" not in nt.plain(top[1]["bulleted_list_item"]["rich_text"])                    # 턴 번호 뺐다

    assert (await pub.publish(path))["action"] == "unchanged"                                # 같은 내용은 건너뛴다
    f.write_text("# 11-05 회고(고침)\n\n- 바뀐 줄\n", encoding="utf-8")
    assert (await pub.publish(path))["action"] == "unchanged"                                # 커밋 전 — main 원본만 본다
    assert all(not x["path"].startswith("log/") for x in await pub.list())                  # 회고는 게시 목록에 없다(11-06)
    g("commit", "-qam", "retro 고침")
    r3 = await pub.publish(path)
    assert r3["action"] == "updated" and r3["page_id"] == r1["page_id"]                      # 같은 페이지 · 같은 URL
    assert fake.pages[r1["page_id"]]["title"] == "11-05 회고(고침)"
    assert [b["type"] for b in fake.blocks[r1["page_id"]]] == ["callout", "bulleted_list_item"]   # 옛 블록은 지웠다
    assert len([c for c in fake.calls if c[0] == "create" and c[2] == "회고"]) == 1           # 묶음 페이지는 한 번만

    # 옮기기 — 루트 아래 다른 묶음 페이지로(목적지도 범위 확인)
    mv = await pub.move(path, "지난 회고")
    newsec = fake.pages[r1["page_id"]]["parent"]
    assert mv["action"] == "moved" and fake.pages[newsec]["title"] == "지난 회고" and fake.pages[newsec]["parent"] == "root"
    with pytest.raises(nt.OutOfScope):
        await pub.move("log/retro_없음.md", "회고")
    await pub.move(path, "회고")
    # 범위 — 우리가 만들지 않은 글은 내리지 않는다
    with pytest.raises(nt.OutOfScope):
        await pub.archive("log/retro_없음.md")
    # 사람이 Notion에서 그 페이지를 범위 밖으로 옮겼다 — 내리지 않는다
    fake.pages[r1["page_id"]]["parent"] = "other"
    with pytest.raises(nt.OutOfScope):
        await pub.archive(path)
    assert ("archive", r1["page_id"]) not in fake.calls
    fake.pages[r1["page_id"]]["parent"] = sec
    assert (await pub.archive(path))["action"] == "archived" and fake.pages[r1["page_id"]]["archived"]
    # 휴지통으로 간 뒤 다시 게시하면 새 페이지
    g("commit", "-q", "--allow-empty", "-m", "빈")
    r4 = await pub.publish(path)
    assert r4["action"] == "created" and r4["page_id"] != r1["page_id"]
    with pytest.raises(FileNotFoundError):
        await pub.publish("log/retro_커밋안됨.md")

    # 포트폴리오(11-06) — 묶음 없이 루트 바로 아래, 번호 붙은 제목. 예전 「포트폴리오」 아래 페이지는 다시 게시할 때 루트로 옮긴다
    (repo / "portfolio").mkdir()
    (repo / "portfolio" / "00_overview.md").write_text("# 한눈에\n\n- 무엇\n", encoding="utf-8")
    (repo / "portfolio" / "01_loss.md").write_text("# 압축 손실\n\n- 숫자\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "portfolio")
    p0 = await pub.publish("portfolio/00_overview.md")
    assert p0["action"] == "created" and fake.pages[p0["page_id"]]["parent"] == "root"
    assert fake.pages[p0["page_id"]]["title"] == "00 한눈에"
    oldsec = await pub._section("포트폴리오")                                                 # 예전 자리를 흉내 낸다
    p1 = await pub.publish("portfolio/01_loss.md")
    fake.pages[p1["page_id"]]["parent"] = oldsec
    await pub._save("portfolio/01_loss.md", parent_page_id=oldsec, title="압축 손실")
    again = await pub.publish("portfolio/01_loss.md")
    assert again["action"] == "unchanged" and fake.pages[p1["page_id"]]["parent"] == "root"   # 내용이 같아도 옮기고
    assert fake.pages[p1["page_id"]]["title"] == "01 압축 손실"                               # 제목도 고친다
    assert (await pub.archive_section("포트폴리오"))["action"] == "archived"                  # 비었으니 내린다
    with pytest.raises(nt.OutOfScope):
        await pub.archive_section("회고")                                                     # 아래에 다시 게시한 회고(r4)가 남았다
    # 사이에 끼운 새 주제 — 다시 세우면 번호순으로 루트 끝에 차례로 붙는다(페이지 id 그대로)
    (repo / "portfolio" / "00_5_mid.md").write_text("# 끼운 글\n\n- 가운데\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "mid")
    pm = await pub.publish("portfolio/00_5_mid.md")
    fake.calls.clear()
    ro = await pub.reorder_portfolio()
    assert ro["order"] == ["portfolio/00_5_mid.md", "portfolio/00_overview.md", "portfolio/01_loss.md"]
    back = [c[1] for c in fake.calls if c[0] == "move" and c[2] == "root"]
    assert back == [pm["page_id"], p0["page_id"], p1["page_id"]]                              # 번호(파일 이름)순으로 되돌림
    assert all(fake.pages[x]["parent"] == "root" for x in back)
    assert [k["child_page"]["title"] for k in await fake.children(fake.pages[back[0]]["parent"]) if k["type"] == "child_page"
            and k["child_page"]["title"] == "정렬 중"] == []                                    # 임시 묶음은 내렸다


async def test_later_since_counts_only_merged_runs(env):
    """나중에 할 일 정리의 기준점(11-06) — 띄운 정리가 합쳐졌을 때만. 버린 것 · 아직 안 합친 것은 세지 않는다(처음부터)."""
    from datetime import datetime
    from sqlalchemy import text as T
    from bridge import scribe_room as sr
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    assert await sr.later_since(engine, proj) is None
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                        {"s": sid, "a": sr.LATER_ACT, "d": "2026-11-06T06:05:00 미룬 말 3개"})
    assert await sr.later_since(engine, proj) is None                         # 띄웠지만 아직 안 합쳤다
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-discard', 1, 'x')"), {"s": sid})
    assert await sr.later_since(engine, proj) is None                         # 버렸다
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-merge', 1, 'x 합칠 커밋이 없어')"), {"s": sid})
    assert await sr.later_since(engine, proj) == datetime(2026, 11, 6, 6, 5)  # 합쳤다(커밋 0개여도) → 그 뒤부터


async def test_postit_states_close_and_limit(env):
    """포스트잇(11-15, 0033) — 받는 함이 곧 포스트잇. 적으면 열림, [x] 삭제, [→] 알려진 한계(서기 「알려진 한계 쓰기」가 가져가
    합치면 README에 씀, 버리면 다시 쓸 줄), 같은 근거는 두 번 안 들어가고 그물의 확인 전 줄은 관리자가 올리면 확인된 줄이 된다."""
    from sqlalchemy import text as T
    from bridge import postit as pi
    from bridge import scribe_room as sr
    from bridge.inject import Refused
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    for bad in ("  ", "x" * (sr.INBOX_MAX + 1)):
        with pytest.raises(Refused):
            await sr.inbox_add(engine, proj, bad)
    with pytest.raises(Refused):
        await sr.inbox_add(engine, "없는-프로젝트", "할 일")
    with pytest.raises(Refused):
        await sr.inbox_add(engine, proj, "할 일", "nobody")
    a = await sr.inbox_add(engine, proj, "질문 카드: 답한 뒤 한 줄로 접기\n둘째 줄")
    b = await sr.inbox_add(engine, proj, "터미널 입력 칸 겹침")

    async def state():
        return {r["id"]: r["state"] for r in await sr.inbox_list(engine, proj)}
    assert await state() == {a: "new", b: "new"}
    assert [x["id"] for x in await pi.items(engine, proj)] == [a, b]            # 열린 것은 오래된 것부터
    assert await sr.inbox_new(engine, proj) == [] and await sr.inbox_new(engine, proj, "coder") == []
    todo = await sr.todo(engine)
    assert todo[proj]["postit"]["open"] == 2 and not any(i["kind"] == "later" for i in todo[proj]["items"])  # 열린 포스트잇은 서기 몫이 아니다
    # [→] 알려진 한계 — 서기 「알려진 한계 쓰기」 몫이 된다
    assert await pi.close(engine, a, "limit", "못 푼다") is True and await pi.close(engine, a, "drop") is False
    assert [x["id"] for x in await sr.inbox_new(engine, proj)] == [a]
    todo = await sr.todo(engine)
    assert any(i["title"] == "알려진 한계 쓰기: 쓸 줄 1, 뺄 줄 0" for i in todo[proj]["items"])
    await sr._inbox_take(engine, [a], sid)
    assert (await state())[a] == "limit_writing" and await sr.inbox_new(engine, proj) == []
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-discard', 1, 'x')"), {"s": sid})
    assert (await state())[a] == "limit"                                       # 쓰기를 버렸다 → 다시 쓸 줄
    assert await sr.inbox_drop(engine, b) is True and await sr.inbox_drop(engine, b) is False
    async with engine.begin() as c:
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-merge', 1, 'x')"), {"s": sid})
    assert await state() == {a: "limit_written", b: "drop"}
    assert q(s, "SELECT dropped_at IS NOT NULL FROM todo_inbox WHERE id = %s", b)[0][0] == 1   # 옛 칸도 함께(0032 코드가 읽어도 버림)
    assert [x["id"] for x in await pi.items(engine, proj, open_only=False)] == [b, a]   # 닫힌 것은 최근 닫은 것부터
    with pytest.raises(Refused):
        await pi.close(engine, b, "없는까닭")
    # 같은 근거는 한 번만 · 그물의 확인 전 줄을 관리자가 같은 턴으로 올리면 확인된 줄로
    r1 = await pi.add(engine, proj, "그물이 찾음", "chat", "t:999999", confirmed=False)
    r2 = await pi.add(engine, proj, "그물이 또 찾음", "chat", "t:999999", confirmed=False)
    assert r1["created"] and not r2["created"] and r2["id"] == r1["id"]
    r3 = await pi.add(engine, proj, "관리자가 올림", "said", "t:999999")
    assert r3["id"] == r1["id"] and r3["created"] and r3["upgraded"]       # 확인 전 줄이 확인된 줄로
    row = q(s, "SELECT source, confirmed, body FROM todo_inbox WHERE id = %s", r1["id"])[0]
    assert row == ("said", 1, "관리자가 올림")
    # 같은 근거에 글이 다른 여러 장은 모두 들어가고(p:51), 같은 글만 겹침으로 말한다
    r4 = await pi.add(engine, proj, "둘째 글", "said", "t:999999")
    r5 = await pi.add(engine, proj, "셋째 글", "said", "t:999999")
    assert r4["created"] and r5["created"] and len({r1["id"], r4["id"], r5["id"]}) == 3
    r6 = await pi.add(engine, proj, "  둘째 글 ", "said", "t:999999")
    assert r6["created"] is False and r6["id"] == r4["id"] and r6["duplicate"] and r6["reason"]
    assert q(s, "SELECT COUNT(*) FROM todo_inbox WHERE source_ref = %s", "t:999999")[0][0] == 3
    r7 = await pi.add(engine, proj, "그물이 한 번 더", "chat", "t:999999", confirmed=False)   # 그물은 근거 하나에 한 장
    assert r7["created"] is False and r7["duplicate"]
    c2 = await pi.add(engine, proj, "확인 전 하나", "chat", "t:999998", confirmed=False)
    assert await pi.confirm(engine, [c2["id"]]) == 1 and await pi.confirm(engine, [c2["id"]]) == 0
    # 코더 [띄우기] — 계획으로 띄운 세션이 가져가면 coder가 되고, 그 세션이 합쳐져도 닫히지 않는다(사람 · [갱신]이 닫는다)
    k = await sr.inbox_add(engine, proj, "코더에게 맡길 일")
    assert await sr.inbox_take_pick(engine, k, sid) is True and await sr.inbox_take_pick(engine, k, sid) is False
    assert (await state())[k] == "merged" and k in [x["id"] for x in await pi.items(engine, proj)]
    assert q(s, "SELECT assignee FROM todo_inbox WHERE id = %s", k)[0][0] == "coder"


async def test_postit_net_sweep(env):
    """그물(11-15) — 사람 턴에서 미룬 말을 찾아 확인 전으로. 띄운 세션의 첫 턴(일감 글) · 합치기 카드 · 아직 열린 턴은 빼고,
    한 번 올린 턴은 다시 올리지 않으며, 관리자가 그 세션으로 올리면 그 줄이 확인된 줄이 된다."""
    from datetime import datetime
    from sqlalchemy import text as T
    from bridge import postit as pi
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    first = q(s, "SELECT id FROM turn WHERE session_id = %s ORDER BY seq LIMIT 1", sid)[0][0]
    seq = q(s, "SELECT MAX(seq) FROM turn WHERE session_id = %s", sid)[0][0]
    async with engine.begin() as c:
        # 이 세션은 브리지가 띄웠다 — 첫 턴은 띄울 때 넣은 일감 글이다
        await c.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'spawn', 1, :d)"),
                        {"s": sid, "d": f"cc-x %1 cc=abc 새 세션 행 {sid}"})
        await c.execute(T("UPDATE turn SET prompt_text = '끝낸 줄은 「나중에 할 일」에 적어 넣어라', origin = 'human' WHERE id = :i"), {"i": first})
        ids = []
        for n, (txt, origin, ended) in enumerate([
                ("[FOREMAN 합치기 카드] 세션 3 「x」 — 「나중에 할 일」에 올려라", "merge_card", True),
                ("이건 「포스트잇」에 올려라. 지금 맡기지 마라", "human", False),
                ("오늘 일은 끝", "human", True),
                ("이건 「포스트잇」에 올려라. 지금 맡기지 마라", "human", True)], 1):
            r = await c.execute(T("INSERT INTO turn (session_id, seq, prompt_text, started_at, ended_at, origin) VALUES "
                                  "(:s, :q, :t, UTC_TIMESTAMP(3), IF(:e, UTC_TIMESTAMP(3), NULL), :o)"),
                                {"s": sid, "q": seq + n, "t": txt, "e": ended, "o": origin})
            ids.append(r.lastrowid)
    card, open_t, plain, real = ids
    since = datetime(2000, 1, 1)
    got = {x["id"] for x in await pi.candidates(engine, since)}
    assert real in got and not {first, card, open_t, plain} & got           # 첫 턴 · 카드 · 열린 턴 · 미룬 말 없음은 뺀다
    assert await pi.sweep(engine, since) >= 1
    row = q(s, "SELECT source, confirmed, project FROM todo_inbox WHERE source_ref = %s", f"t:{real}")[0]
    assert row == ("chat", 0, proj)
    assert real not in {x["id"] for x in await pi.candidates(engine, since)}
    assert await pi.sweep(engine, since) == 0                                # 이미 올린 턴은 다시 올리지 않는다
    # 관리자가 같은 세션으로 올림 — 근거는 그 세션의 마지막 사람 턴(= real). 확인 전 줄이 확인된 줄이 된다
    r = await pi.add(engine, proj, "포스트잇에 올림", "said", session=sid)
    assert r["created"] and r["upgraded"]
    assert q(s, "SELECT source, confirmed FROM todo_inbox WHERE source_ref = %s", f"t:{real}")[0] == ("said", 1)
    # p:51 — 같은 세션(같은 근거)에서 글이 다른 세 장은 세 장, 같은 글을 또 올리면 겹침을 말한다
    more = [await pi.add(engine, proj, f"다른 글 {n}", "said", session=sid) for n in range(3)]
    assert all(m["created"] for m in more)
    dup = await pi.add(engine, proj, "다른 글 1", "said", session=sid)
    assert dup["created"] is False and dup["duplicate"] and dup["id"] == more[1]["id"] and dup["reason"]
    assert q(s, "SELECT COUNT(*) FROM todo_inbox WHERE source_ref = %s", f"t:{real}")[0][0] == 4
    assert await pi.sweep(engine, since) == 0                                # 그물은 이 턴을 다시 올리지 않는다


async def test_postit_check_collect_and_resolve(env, tmp_path):
    """[갱신](11-15) — 조사 세션의 마지막 응답에서 결과 블록을 읽는다. 코드 자리 없는 「끝남」은 모름으로, 결과가 들어오면 다시 읽지 않고,
    사람이 [닫기]를 누를 때만 포스트잇이 닫힌다(자동으로 지우지 않는다)."""
    from sqlalchemy import text as T
    from bridge import handoff as h
    from bridge import postit as pi
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    a = (await pi.add(engine, proj, "질문 카드 접기"))["id"]
    b = (await pi.add(engine, proj, "터미널 스크롤"))["id"]
    tr = tmp_path / "check.jsonl"
    block = (f"<<<{pi.CHECK_TAG} r=rq1>>>\n" + json.dumps([
        {"id": f"p:{a}", "verdict": "끝남", "evidence": "bridge/static/js/opanel.js:120", "reason": "접힌다"},
        {"id": f"p:{b}", "verdict": "끝남", "evidence": "c0ffee1", "reason": "커밋만"}], ensure_ascii=False) + "\n<<<END r=rq1>>>")
    tr.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": block}]}}, ensure_ascii=False) + "\n",
                  encoding="utf-8")

    class M:
        sessions_dir = s.sessions_dir

        async def session(self, i):
            return h.SessionRow(i, "cc-check", None, str(tmp_path), str(tr), proj, "점검")

        async def _act(self, i, action, pid, ok, detail):
            async with engine.begin() as c:
                await c.execute(T("INSERT INTO session_action (session_id, action, pid, ok, detail) VALUES (:s, :a, :p, :o, :d)"),
                                {"s": i, "a": action, "p": pid, "o": ok, "d": detail})
    m = M()
    await m._act(sid, pi.CHECK_ACT, None, True, f"{proj} rq1 p2 L0")
    pi._KNOWN[(sid, "rq1")] = {f"p:{a}": "질문 카드 접기", f"p:{b}": "터미널 스크롤"}
    summ = await pi.summary(engine, proj)
    assert summ["check"]["state"] == "running"
    assert await pi.collect(m, engine) == 2
    assert await pi.collect(m, engine) == 0                                   # 결과를 받은 세션은 다시 읽지 않는다
    by = {k["item"]: k for k in await pi.checks(engine, proj)}
    assert by[f"p:{a}"]["verdict"] == "done" and by[f"p:{b}"]["verdict"] == "unknown"
    summ = await pi.summary(engine, proj)
    assert summ["check"]["state"] == "done" and summ["likely_done"] == 1 and summ["open"] == 2   # 판정만으로는 닫히지 않는다
    assert (await pi.resolve_check(engine, by[f"p:{b}"]["id"], "keep"))["ok"]
    assert (await pi.resolve_check(engine, by[f"p:{a}"]["id"], "close"))["ok"]
    assert (await pi.resolve_check(engine, by[f"p:{a}"]["id"], "close"))["ok"] is False
    row = q(s, "SELECT closed_reason, closed_note FROM todo_inbox WHERE id = %s", a)[0]
    assert row[0] == "done" and "opanel.js:120" in row[1]
    assert [x["id"] for x in await pi.items(engine, proj)] == [b]


async def test_promote_postit_only_skips_session(env, monkeypatch):
    """옮기기 2/2(11-15) — 승인한 것이 모두 dest postit(할 일인 미완)이면 세션에 쓰기 요청을 보내지 않고 브리지가 포스트잇에 넣는다.
    같은 항목을 다시 써도 포스트잇은 하나다(근거 pr:<id>:<항목>)."""
    from sqlalchemy import text as T
    from bridge import handoff as h
    from bridge import promote as pm
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    mgr = h.HandoffManager(engine, s.sessions_dir)
    mgr.promote = pr = pm.Promoter(mgr)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    sent = []

    async def fake_deliver(*a, **kw):
        sent.append(a)
        return {"delivered": None}
    monkeypatch.setattr(pm, "deliver", fake_deliver)
    items = [{"id": 1, "kind": "미완", "what": "질문 카드 접기를 끝낸다", "quote": "접어라", "dest": "postit", "section": "", "why": "", "state": "approved"},
             {"id": 2, "kind": "결정", "what": "그때뿐", "quote": "", "dest": "drop", "section": "", "why": "", "state": "dropped"}]
    async with engine.begin() as c:
        r = await c.execute(T("INSERT INTO promotion (session_id, req, status, items) VALUES (:s, 'pp1', 'listed', :i)"),
                            {"s": sid, "i": json.dumps(items, ensure_ascii=False)})
        pid = r.lastrowid
    out = await pr.write(pid)
    assert out["status"] == "written" and len(out["postit"]) == 1 and sent == []
    row = q(s, "SELECT source, source_ref, body FROM todo_inbox WHERE id = %s", out["postit"][0])[0]
    assert row[0] == "promote" and row[1] == f"pr:{pid}:1" and "사람 말: 「접어라」" in row[2]
    assert q(s, "SELECT status FROM promotion WHERE id = %s", pid)[0][0] == "written"


async def test_inbox_assignee_coder_jobs_and_rest(env, tmp_path):
    """쉬게 한 일은 합치거나 버리기 전까지(그리고 다시 살아나지 않은 동안) 코더 맡길 일에 든다.
    11-15 「코더에게」 받은 할 일은 포스트잇 코더 추천으로 옮겨 코더 맡길 일의 inbox는 늘 비어 있다."""
    from datetime import datetime, timedelta
    from sqlalchemy import text as T
    from bridge import coder_room as cr
    from bridge import scribe_room as sr
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    c = await sr.inbox_add(engine, proj, "옛 코더 몫", "coder")
    assert await sr.inbox_new(engine, proj, "coder") == []
    assert await sr.inbox_take_coder(engine, c, sid) is True and await sr.inbox_take_coder(engine, c, sid) is False
    # 쉬게 한 일 — worktree 폴더가 있고 세션이 살아 있지 않으면 센다. 합치면 빠진다
    wtp = tmp_path / "proj" / ".worktrees" / "rest-a"
    wtp.mkdir(parents=True)
    async with engine.begin() as cn:
        await cn.execute(T("UPDATE character_session SET cwd = :w, worktree_path = :w WHERE id = :s"), {"w": str(wtp), "s": sid})
        await cn.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'rest', 0, '커밋 실패')"), {"s": sid})
    assert await cr.rested(engine, s.sessions_dir) == []                                 # 실패한 쉬게 하기는 세지 않는다
    async with engine.begin() as cn:
        await cn.execute(T("INSERT INTO session_action (session_id, action, ok, detail, created_at) VALUES "
                           "(:s, 'rest', 1, 'rest-a 커밋 abc', UTC_TIMESTAMP(3) - INTERVAL 2 DAY)"), {"s": sid})
    r = await cr.rested(engine, s.sessions_dir, proj)
    assert [(x["session_id"], x["branch"], x["days"]) for x in r] == [(sid, "cc/rest-a", 2)]
    todo = await cr.todo(engine, s.sessions_dir)
    assert todo[proj]["rested"][0]["session_id"] == sid and todo[proj]["inbox"] == []    # 코더 몫은 이미 가져갔다
    async with engine.begin() as cn:
        await cn.execute(T("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-merge', 1, 'x')"), {"s": sid})
    assert await cr.rested(engine, s.sessions_dir) == []
    # 서기 제안 — 새로 3개 이상 또는 가장 오래된 것 3일(config/scribe.toml)
    now = datetime(2026, 11, 9, 12, 0)
    one = [{"created_at": now - timedelta(hours=1)}]
    conf = {"new_min": 3, "oldest_days": 3}
    assert sr.nudge_of([], conf, now) is None and sr.nudge_of(one, conf, now) is None
    assert sr.nudge_of(one * 3, conf, now)["n"] == 3
    old = sr.nudge_of([{"created_at": now - timedelta(days=4)}], conf, now)
    assert old["days"] == 4 and "4일째" in old["why"]
    assert sr.nudge_conf(tmp_path / "없음.toml") == sr.NUDGE_DEFAULT


# ── 11-06 사람이 붙인 이름이 항상 이긴다 ─────────────
async def test_custom_title_survives_ai_title_and_passes_to_handoff(env):
    from types import SimpleNamespace
    from bridge.handoff import HandoffManager
    s, main = env
    asm = await run(s)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute("UPDATE character_session SET custom_title = '내 이름' WHERE id = %s", (sid,))
        c.execute("INSERT INTO summary (session_id, req, kind, source, status) VALUES (%s, 'abc123', 'handoff', 'self', 'ok')", (sid,))
        sum_id = c.lastrowid
    conn.close()
    for t in ("CC가 새로 지은 제목", "CC가 또 지은 제목"):           # 대화 중에 CC가 제목을 다시 짓는다
        await _append(s, asm, main, dumps({"type": "ai-title", "aiTitle": t, "sessionId": SID}))
    assert q(s, "SELECT title, custom_title FROM character_session WHERE id = %s", sid) == (("CC가 또 지은 제목", "내 이름"),)
    fake = SimpleNamespace(engine=asm.engine)
    assert await HandoffManager._inherited_title(fake, sum_id) == "내 이름"     # 인계로 띄운 새 세션이 물려받는다


# ── 11-06 겹침 알림 — 살아 있는 다른 세션의 최근 요청과 겹치면 알린다(막지 않는다) ─────────────
async def test_overlap_alert_on_human_prompt(env, tmp_path):
    import os
    from bridge.overlap import OverlapWatch
    s, main = env
    pid = os.getpid()
    start = open(f"/proc/{pid}/stat").read().rsplit(") ", 1)[1].split()[19]
    for n, sid in enumerate((SID, SID2)):     # 두 세션 모두 살아 있게(같은 테스트 프로세스)
        (s.sessions_dir / f"{pid}-{n}.json").write_text(json.dumps(
            {"pid": pid, "sessionId": sid, "cwd": CWD, "procStart": start, "status": "idle"}), encoding="utf-8")
    asm, n, tg = await _live(s, tmp_path)
    ow = OverlapWatch(asm.engine, n, n.rules, tmp_path / "없음.toml", s.sessions_dir)
    ow.rules.edit_scan_sec = 0                    # 같은 파일 훑기(주기 작업)는 test_overlap.py에서 따로 본다
    asm.on_human_prompt = ow.on_prompt

    async def prompt(sid, text):
        await asm.apply_hook("UserPromptSubmit", {"session_id": sid, "cwd": CWD, "prompt": text,
                                                  "transcript_path": str(main.parent / f"{sid}.jsonl")})
        await asyncio.gather(*list(ow._tasks))
        await n.drain()

    await prompt(SID2, "jenkins-0 Unknown · harbor-jobservice CrashLoopBackOff 원인 조사해줘")
    assert tg.sent == []                                                   # 다른 세션의 요청은 오래전(10-01) 것뿐
    await prompt(SID, "tmux 이름 고쳐줘. jenkins-0이랑 harbor-jobservice CrashLoopBackOff 원인도 봐줘")
    me, other = (q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", x)[0][0] for x in (SID, SID2))
    # 11-09 — 낱말 겹침은 패널 띠만(텔레그램 없음). 상대가 그 파일을 고친 흔적이 없으면 "말에 나왔을 뿐"(weak)
    assert tg.sent == [] and q(s, "SELECT kind FROM notification WHERE kind = 'overlap'") == ()
    band = ow.for_session(me)
    assert band["with"] == other and band["words"][:2] == ["harbor-jobservice", "jenkins-0"]
    assert band["weak"] is True and band["edited"] == []
    # 같은 두 세션은 한 시간 안에 다시 띄우지 않는다 · 겹치지 않는 요청 · 서기 일감은 보지 않는다
    await prompt(SID, "jenkins-0 harbor-jobservice 다시 봐줘")
    assert ow.for_session(me)["at"] == band["at"]
    await prompt(SID2, "Notion 게시 기능 만들자")
    await prompt(SID2, "[FOREMAN 서기 일감 — 문서 점검] jenkins-0 harbor-jobservice crashloopbackoff")
    assert other not in ow.recent and tg.sent == []

    # 11-08 — 인계로 이어받은 세션은 겹침이 아니다(세션 214 ~ 211 헛알림). 인계 글이 넣음 기록보다 먼저 적재돼
    # summary.injected_cc_session이 아직 비어 있어도 글의 r=로 알아본다. 그 뒤 기록이 차면 r= 없는 요청도 뺀다
    ow2 = OverlapWatch(asm.engine, n, n.rules, tmp_path / "없음.toml", s.sessions_dir)   # 한 시간 막기를 비운 새 감시
    ow2.rules.edit_scan_sec = 0
    asm.on_human_prompt = ow2.on_prompt
    ow = ow2
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute("INSERT INTO summary (session_id, req, kind, source, status) VALUES (%s, 'e83d1c', 'handoff', 'self', 'ok')", (other,))
    await prompt(SID, "[FOREMAN 인계 r=e83d1c] 직전 세션의 인계다. jenkins-0 harbor-jobservice CrashLoopBackOff 이어서")
    with conn.cursor() as c:
        c.execute("UPDATE summary SET injected_cc_session = %s WHERE req = 'e83d1c'", (SID,))
    conn.close()
    await prompt(SID, "jenkins-0 harbor-jobservice CrashLoopBackOff 마저 봐줘")
    await prompt(SID2, "jenkins-0 harbor-jobservice CrashLoopBackOff 넘긴 쪽에서 다시")    # 넘겨준 쪽에서도
    assert tg.sent == [] and ow2.recent == {}
    await n.stop()


async def test_todo_edit_pick_and_handover_columns(env):
    """11-11 C 2물결 — 할 일 목록에서 고치기(edited_at) · 골라 가져가기(서기 몫도 코더 몫으로) · 관리자에게 넘긴 계획(0031)."""
    import json as _json
    from sqlalchemy import text as T
    from bridge import scribe_room as sr
    from bridge.foreman import ForemanDispatcher
    from bridge.inject import Refused
    s, _main = env
    await run(s)
    engine = make_engine(s)
    ENGINES.append(engine)
    sid = q(s, "SELECT id FROM character_session WHERE cc_session_id = %s", SID)[0][0]
    proj = q(s, "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "JOIN project p ON p.id = ch.project_id WHERE cs.id = %s", sid)[0][0]
    a = await sr.inbox_add(engine, proj, "서기 몫")
    b = await sr.inbox_add(engine, proj, "코더 몫", "coder")
    assert await sr.inbox_edit(engine, a, "  고친 글 ") is True
    assert q(s, "SELECT body, edited_at IS NOT NULL FROM todo_inbox WHERE id = %s", a)[0] == ("고친 글", 1)
    with pytest.raises(Refused):
        await sr.inbox_edit(engine, a, "  ")
    assert await sr.inbox_take_pick(engine, a, sid) is True                # 서기 몫도 사람이 고르면 코더 몫으로 가져간다
    assert q(s, "SELECT assignee, taken_by FROM todo_inbox WHERE id = %s", a)[0] == ("coder", sid)
    assert await sr.inbox_edit(engine, a, "다시") is False                  # 가져간 것은 고치지 않는다
    assert await sr.inbox_drop(engine, b) is True and await sr.inbox_take_pick(engine, b, sid) is False   # 버린 것은 못 가져간다
    # 관리자에게 넘긴 계획 — 저장된 계획 · 넘긴 기록
    async with engine.begin() as c:
        r = await c.execute(T("INSERT INTO dispatch (origin, project, request, status, plan, edited, handed_to, handed_at) "
                              "VALUES ('human', :p, 'x', 'planned', :pl, :ed, :h, UTC_TIMESTAMP(3))"),
                            {"p": proj, "pl": _json.dumps({"mode": "new"}), "ed": _json.dumps({"mode": "new", "inbox_ids": [a]}), "h": sid})
        did = r.lastrowid
    d = ForemanDispatcher(engine, s.sessions_dir, None, lambda: [], None)
    assert (await d.saved_plan(did))["inbox_ids"] == [a]                   # 고친 계획(edited)이 이긴다
    h = await d.handed(did)
    assert h["to_session"] == sid and h["alerted"] is False


# ── 11-12 승인 지옥 줄이기 ② · ③ · ④(log/notify_relay_20261112.md) ──────────────
class FakeMgr:
    def __init__(self, result):
        self.result, self.calls = result, []

    async def relay(self, project, kind, sid, label, body):
        self.calls.append((project, kind, sid, label, body))
        return dict(self.result)


class FlakyTG(FakeTG):
    """하루 묶음(📦)만 거부한다 — 짧은 실패 알림은 간다."""
    async def send(self, msg):
        if "📦" in msg:
            raise RuntimeError("HTTP 400")
        self.sent.append(msg)


def ex(s: Settings, sql: str, *args):
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute(sql, args)
    conn.close()


async def _live_relay(s, tmp_path, role="coder", mgr=None, tg=None, **sw):
    from bridge.notify import Notifier, load_rules
    p = tmp_path / "notify_relay.toml"
    p.write_text('[telegram]\nsettle_s = 0\nmin_interval_s = 0\n[projects.foreman]\nprefix = "[포먼]"\n'
                 + "".join(f"{k} = {str(v).lower()}\n" for k, v in sw.items()), encoding="utf-8")
    main = s.projects_root / PROJ / f"{SID}.jsonl"
    main.write_text("\n".join(MAIN) + "\n", encoding="utf-8")     # p4가 열린 채
    asm = await run(s)
    ex(s, "UPDATE character_session SET role = %s", role)
    tg = tg or FakeTG()
    n = Notifier(asm.engine, load_rules(p), tg, Masker())
    n._worker = asyncio.create_task(n._sender())     # 하루 묶음 고리는 시험이 digest_tick으로 직접 부른다
    n.managers = mgr
    asm.on_turn_closed = n.on_turn_closed
    asm.live = True
    return asm, n, tg


async def _stop(asm, n, reply):
    await asm.apply_hook("Stop", {"session_id": SID, "cwd": CWD, "last_assistant_message": reply})
    await n.drain()


async def test_relay_report_goes_to_manager_not_telegram(env, tmp_path):
    s, _ = env
    mgr = FakeMgr({"delivered": True, "manager": True})
    asm, n, tg = await _live_relay(s, tmp_path, mgr=mgr, relay_reports=True)
    await _stop(asm, n, "다 고쳤습니다.\n\n커밋 abc123에 남겼습니다.")
    assert tg.sent == []
    (project, kind, _sid, label, body), = mgr.calls
    assert (project, kind) == ("foreman", "report") and label.endswith("(coder)")
    assert "맡은 일: 네 번째" in body and "커밋 abc123" in body
    assert q(s, "SELECT decision, rule FROM notification WHERE kind = 'turn'") == (("skipped", "relayed:report"),)
    await n.stop()


async def test_relay_question_manager_relays_and_relay_origin(env, tmp_path):
    from bridge.assembler import Assembler
    from bridge.managers import relay_text
    s, _ = env
    mgr = FakeMgr({"delivered": True, "manager": True})
    asm, n, tg = await _live_relay(s, tmp_path, mgr=mgr, relay_questions=True)
    await _stop(asm, n, "두 가지 방법이 있습니다.\n\nA안과 B안 중 어느 쪽으로 할까요?")
    assert tg.sent == [] and mgr.calls[0][1] == "question" and "물음: A안과 B안 중" in mgr.calls[0][4]
    text_ = relay_text("question", "세션 1", "foreman", mgr.calls[0][4])
    assert "관리자가 답하지 않습니다" in text_
    # 관리자 입력 칸에 들어간 글로 열린 턴은 사람 입력이 아니다(relay) — 겹침 · 답 기다림 셈에서 빠진다
    assert Assembler._origin({}, text_) == "relay"
    assert Assembler._origin({}, relay_text("report", "세션 1", "foreman", "끝")) == "relay"
    await n.stop()


async def test_relay_off_or_no_manager_or_failed(env, tmp_path):
    s, _ = env
    # 관리자가 없으면 지금처럼 바로
    mgr = FakeMgr({"delivered": False, "manager": False, "reason": "없음"})
    asm, n, tg = await _live_relay(s, tmp_path, mgr=mgr, relay_reports=True)
    await _stop(asm, n, "다 했다")
    assert len(tg.sent) == 1 and "관리자에게 넘기지 못했습니다" not in tg.sent[0]
    await n.stop()


async def test_relay_failed_with_manager_is_sent_now(env, tmp_path):
    s, _ = env
    mgr = FakeMgr({"delivered": False, "manager": True, "reason": "입력 칸에 넣었는지 확인하지 못했습니다"})
    asm, n, tg = await _live_relay(s, tmp_path, mgr=mgr, relay_reports=True, digest=True)
    await _stop(asm, n, "다 했다")
    assert len(tg.sent) == 1 and "⚠ 관리자에게 넘기지 못했습니다 — 입력 칸에" in tg.sent[0]
    await n.stop()


async def test_manager_role_not_relayed(env, tmp_path):
    s, _ = env
    mgr = FakeMgr({"delivered": True, "manager": True})
    asm, n, tg = await _live_relay(s, tmp_path, role="manager", mgr=mgr, relay_reports=True, relay_questions=True)
    await _stop(asm, n, "다 했다")
    assert mgr.calls == [] and len(tg.sent) == 1
    await n.stop()


async def test_digest_holds_routine_sends_urgent_then_bundles(env, tmp_path):
    from datetime import UTC, datetime, time
    s, _ = env
    asm, n, tg = await _live_relay(s, tmp_path, digest=True)
    await _stop(asm, n, "다 했다")
    assert tg.sent == [] and q(s, "SELECT decision FROM notification WHERE kind = 'turn'") == (("digest",),)
    # 일상(합치기 카드)은 모으고, ⚠가 있는 것 · kinds에 없는 것(승인 대기)은 바로
    n.send_direct("foreman", "merge", None, "[포먼] ⑂ 합치기 준비됨 — 「가」")
    n.send_direct("foreman", "merge", None, "[포먼] ⚠ 합치기 실패")
    n.send_direct("foreman", "approval", None, "[포먼] 승인 대기")
    await n.drain()
    assert sorted(tg.sent) == ["[포먼] ⚠ 합치기 실패", "[포먼] 승인 대기"]
    day = datetime.now(UTC).replace(tzinfo=None).date()
    assert await n.digest_tick(datetime.combine(day, time(11, 0))) == []          # 20:00 KST — 아직
    assert await n.digest_tick(datetime.combine(day, time(12, 30))) == ["sent:foreman"]
    d = tg.sent[-1]
    assert d.startswith("[포먼] 📦 하루 묶음") and "일상 알림 2건" in d and "■ 턴 끝 1건" in d and "■ 합치기 1건" in d
    assert "끝남 · " in d and "합치기 준비됨 — 「가」" in d
    assert q(s, "SELECT COUNT(*) FROM notification WHERE decision = 'bundled'")[0][0] == 2
    assert await n.digest_tick(datetime.combine(day, time(12, 31))) == []         # 오늘은 이미 보냄
    await n.stop()


async def test_digest_question_turn_is_urgent(env, tmp_path):
    s, _ = env
    asm, n, tg = await _live_relay(s, tmp_path, digest=True)
    await _stop(asm, n, "A안과 B안 중 어느 쪽으로 할까요?")
    assert len(tg.sent) == 1 and q(s, "SELECT decision FROM notification WHERE kind = 'turn'") == (("sent",),)
    await n.stop()


async def test_digest_send_failure_and_late_are_reported(env, tmp_path):
    from datetime import UTC, datetime, time
    s, _ = env
    asm, n, tg = await _live_relay(s, tmp_path, tg=FlakyTG(), digest=True)
    await _stop(asm, n, "다 했다")
    day = datetime.now(UTC).replace(tzinfo=None).date()
    assert await n.digest_tick(datetime.combine(day, time(12, 30))) == ["failed:foreman"]
    await n.drain()
    assert len(tg.sent) == 1 and tg.sent[0].startswith("[포먼] ⚠ 하루 묶음을 보내지 못했습니다(HTTP 400)")
    # 시험은 가짜 시각으로 부른다 — 실패 기록 시각을 그 시각에 맞춘다
    ex(s, "UPDATE notification SET created_at = %s WHERE kind = 'digest' AND decision = 'failed'",
       datetime.combine(day, time(12, 30)))
    assert await n.digest_tick(datetime.combine(day, time(12, 35))) == []          # 10분 안에는 다시 안 함
    assert await n.digest_tick(datetime.combine(day, time(12, 41))) == ["failed:foreman"]
    await n.drain()
    assert len(tg.sent) == 1                                                       # 실패 알림은 그날 한 번
    # 모아 둔 것이 26시간 넘게 남으면 알린다
    ex(s, "UPDATE notification SET created_at = created_at - INTERVAL 30 HOUR WHERE decision = 'digest'")
    assert "late:foreman" in await n.digest_tick(datetime.combine(day, time(11, 0)))
    await n.drain()
    assert "하루 묶음이 26시간 넘게 나가지 않았습니다" in tg.sent[-1]
    await n.stop()


async def test_bash_description_to_live_event_and_dashboard(env):
    """Bash description(11-14) — 실시간 tool_use 이벤트와 대시보드 마지막 활동에 실린다. 비밀값은 가려진 채, 200자 안.
    Bash가 아닌 도구 · 설명이 없는 Bash는 None."""
    from bridge.api.dashboard import latest_tool_acts
    s, main = env
    for p in (main.parent / SID / "subagents").iterdir():
        p.unlink()
    main.write_text("", encoding="utf-8")
    asm = await run(s)
    pub: list = []
    asm.publish = pub.append
    asm.live = True
    await _append(s, asm, main,
                  user(U(701), "d1", "돌려", origin={"kind": "human"}),
                  asst(U(702), "msg_d1", {"type": "tool_use", "id": "toolu_D1", "name": "Bash",
                                          "input": {"command": "pytest -q", "description": f"Run tests MY_TOKEN={SECRET} " + "x" * 300}}),
                  asst(U(703), "msg_d2", {"type": "tool_use", "id": "toolu_D2", "name": "Read", "input": {"file_path": "/x"}}),
                  asst(U(704), "msg_d3", {"type": "tool_use", "id": "toolu_D3", "name": "Bash", "input": {"command": "ls"}}))
    evs = [m["event"] for m in pub if m.get("type") == "event" and m["event"]["type"] == "tool_use"]
    by_tool = {(e["tool"], e["target"]): e["description"] for e in evs}
    d = by_tool[("Bash", "pytest -q")]
    assert d.startswith("Run tests") and SECRET not in d and len(d) <= 200
    assert by_tool[("Read", "/x")] is None and by_tool[("Bash", "ls")] is None
    sid = q(s, "SELECT id FROM character_session")[0][0]
    async with asm.engine.connect() as c:
        acts = await latest_tool_acts(c, f"({int(sid)})")
    assert acts[sid][0] == "Bash" and acts[sid][4] in (None, "null")                    # 마지막은 설명 없는 ls
    ex(s, "DELETE FROM event WHERE tool = 'Bash' AND target = 'ls'")
    ex(s, "DELETE FROM event WHERE tool = 'Read' AND type = 'tool_use' AND target = '/x'")
    async with asm.engine.connect() as c:
        acts = await latest_tool_acts(c, f"({int(sid)})")
    assert acts[sid][0] == "Bash" and acts[sid][4].startswith("Run tests") and SECRET not in acts[sid][4]
