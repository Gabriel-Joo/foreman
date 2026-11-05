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
    pol = load_policy("config/approval.toml")
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
async def test_handoff_request_extract_edit_inject_preview(env, monkeypatch):
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
    assert q(s, "SELECT name, parent_id, spawned_by FROM `character` WHERE id = %s", insp) == (("점검", foreman, "foreman"),)
    w = await mgr._character_for(f"{repo}/.worktrees/{name}-2", "coder")
    assert q(s, "SELECT name FROM `character` WHERE id = %s", w) == ((f"코더 {name}-2",),)
    row = h.SessionRow(1, None, w, f"{repo}/.worktrees/{name}-2", None, name, None)
    await mgr._retire_wt_characters(row, f"{name}-2")
    assert q(s, "SELECT retired_at IS NOT NULL FROM `character` WHERE id = %s", w) == ((1,),)
    assert await mgr._character_for(f"{repo}/.worktrees/{name}-2", "coder") == w   # 같은 이름이면 되살린다
    assert q(s, "SELECT retired_at FROM `character` WHERE id = %s", w) == ((None,),)
    assert await mgr._character_for("/tmp/elsewhere", "coder") is None             # 떠돌이는 그대로
