"""사람이 해야 풀리는 대기(11-09) — 글로 묻고 끝난 응답 판정 · CC auto mode 거부 문구."""

import json
from datetime import UTC, datetime, timedelta

import pymysql
import pytest

from bridge.api.dashboard import DENIED_PREFIX, _DENY_REASON, asks_off, asks_text, human_needs
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main


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


def test_asks_text():
    assert asks_text("셋 중 하나를 골라 주세요.\n- (가) 직접 반영\n- (나) 허용 규칙")
    assert asks_text("둘 다 받으실지, 하나라도 빼실지 알려 주세요.\n2. 다음")
    assert asks_text("이대로 진행할까요?")
    assert not asks_text("커밋했고 push했습니다. 시험 487 통과입니다.")
    assert not asks_text(None)
    # 앞쪽(600자 밖)에 있던 물음은 보지 않는다 — 끝에 남은 말만
    assert not asks_text("어떻게 할까요?\n" + "결과를 정리했습니다. " * 60)


def test_denied_text():
    t = ("Permission for this action was denied by the Claude Code auto mode classifier. "
         "Reason: [External System Writes]. If you have other tasks ...")
    assert t.startswith(DENIED_PREFIX)
    assert _DENY_REASON.search(t).group(1) == "External System Writes"


def test_asks_text_last_paragraph_only():
    """11-11(받은 할 일 #13) — 11-10 실제로 묻지 않는 보고가 답 기다림이 된 꼴들. 마지막 문단만 본다."""
    # 관리자 244 합치기 보고(565194) — 가운데 문단의 "정해 주세요", 끝은 할 일 알림
    assert not asks_text("합쳤습니다.\n\n둘 중 어느 쪽으로 할지 정해 주세요는 지난 일입니다.\n\n"
                         "1. 런슈즈 서기 259, 펫퍼민트 서기 260에 맡깁니다.\n2. 커밋이 쌓이면 제가 확인하고 push하겠습니다.")
    # 할 일 이름 「UI 불만 (가)(나)(다)」를 가리키기만 함(262)
    assert not asks_text("다음 서기에게 넘길 일감(UI 불만 (가)(나)(다))도 적었습니다. 이제 관리자가 합칠 차례입니다.")
    # 다른 세션에게 넘기는 부탁(247)
    assert not asks_text("README 줄은 남겼습니다. 합친 뒤 sonnet이 막히지 않는지는 관리자가 확인해 주세요.")
    # 다음에 할 일을 말한 끝맺음(펫퍼민트, 받은 할 일 #13)
    assert not asks_text("계획은 위와 같습니다.\n\n시작하라는 말씀을 기다리겠습니다.")
    # 진짜 묻는 것은 그대로
    assert asks_text("결과입니다.\n\n이대로 시작해도 될까요?")
    assert asks_text("정리했습니다.\n\n노션 인프라 페이지는 (가) 새로 만들기 · (나) 있는 것 쓰기 중 하나를 골라 주세요.")
    assert asks_text("두 길이 있습니다.\n\n(가)로 할지 (나)로 할지 정해 주세요")


@pytest.mark.db
async def test_asks_off_until_next_reply(env):
    """[답 안 해도 됨] — 그 응답만 끈다. 다음 응답이 묻는 말이면 다시 켜진다."""
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', 'aaaaaaaa-0000-0000-0000-000000000013', 't', 'user')", (char,))
        sid = c.lastrowid
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (sid, now - timedelta(hours=1)))
        c.execute("INSERT INTO event (session_id, character_id, source, ts, type, payload) VALUES (%s, %s, 'transcript', %s, "
                  "'assistant_msg', %s)", (sid, char, now - timedelta(minutes=5), json.dumps({"block": "text", "text": "할까요?"})))
    engine = make_engine(s)
    try:
        async with engine.connect() as c:
            assert "asks" in (await human_needs(c, f"({sid})"))[sid]
        r = await asks_off(engine, sid)
        assert r["ok"]
        async with engine.connect() as c:
            assert sid not in await human_needs(c, f"({sid})")
        assert not (await asks_off(engine, sid))["ok"]               # 이미 꺼짐
        with conn.cursor() as c:
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, payload) VALUES (%s, %s, 'transcript', %s, "
                      "'assistant_msg', %s)", (sid, char, now, json.dumps({"block": "text", "text": "그럼 이쪽으로 갈까요?"})))
        async with engine.connect() as c:
            assert "asks" in (await human_needs(c, f"({sid})"))[sid]  # 새 응답 — 다시 판정
    finally:
        await engine.dispose()
