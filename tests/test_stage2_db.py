"""2단계 조립 — 합성 트랜스크립트로 foreman_test DB에 적재해 본다.  pytest -m db

실측(11-02)에서 본 모양만 쓴다: promptId · turnOrigin · toolUseResult.agentId · <task-notification> 태그 ·
content 블록마다 쪼개진 줄 · api-request 줄 · 개행 없는 마지막 줄.
"""

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
