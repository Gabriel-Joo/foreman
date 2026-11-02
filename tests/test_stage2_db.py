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
