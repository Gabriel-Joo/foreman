"""사람이 해야 풀리는 대기(11-09) — 글로 묻고 끝난 응답 판정 · CC auto mode 거부 문구."""

import json
from datetime import UTC, datetime, timedelta

import pymysql
import pytest

from bridge.api.dashboard import DENIED_PREFIX, _DENY_REASON, ask_line, asks_off, asks_text, human_needs, report_read
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
    # 가운데 문단에서 말을 가리키기만 함(「정해 주세요」는 지난 일) — 끝은 할 일 알림.
    # 11-11 끝 세 문단으로 넓히며 낫표 · 따옴표 안은 지우고 본다. 이 시험이 가리키던 565194 원문은 실제로
    # 「push를 누가 할지 정해 주세요. 1. … 2. …」로 묻는 글이었다(옛 판정도 걸었다)
    assert not asks_text("합쳤습니다.\n\n둘 중 어느 쪽으로 할지 「정해 주세요」는 지난 일입니다.\n\n"
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


def test_asks_text_last_few_paragraphs():
    """11-11(사용자) — 마지막 문단만 보니 너무 좁았다. 끝 세 문단 · 「정할 것:」 · 「~주십시오」 · 줄 가운데 「까요?」."""
    # 코더 274 보고(570485) — 묻는 문단 뒤에 「자세한 내용은 log에」 문단
    t = ("**합친 뒤 관리자가 할 일**\n1. 브리지를 다시 띄웁니다.\n\n"
         "**사용자가 정할 것:** 인프라 265 같은 경우도 울리지 않게 하려면, 실패 판정을 좁히면 됩니다.\n\n"
         "자세한 내용은 `log/stallwatch_loop_fix_20261111.md`에 적었습니다.")
    assert ask_line(t).startswith("**사용자가 정할 것:**")
    assert asks_text("결과입니다.\n\n이대로 2단계로 넘어갈지 알려 주십시오.\n\n기록은 log에 있습니다.")
    assert asks_text("정리했습니다.\n\n어느 쪽으로 할지 정해 주시면 진행하겠습니다.\n\n커밋은 아직입니다.")
    assert asks_text("**승인 요청:** 10개를 모두 이대로 반영할까요? 뺄 번호가 있으면 알려 주세요. 반영하면 커밋합니다.")
    assert asks_text("**정해 주실 것:**\n- 가 안\n- 나 안\n\n자세한 것은 log에.")
    # 네 문단 위의 물음은 보지 않는다
    assert not asks_text("어떻게 할까요?\n\n하나.\n\n둘.\n\n셋.")


def test_asks_text_human_must_act():
    """11-11(사용자) — 끝 「참고할 것」 목록 안이어도 사람이 움직여야 이어지는 글은 답 기다림(인프라 265, 567293)."""
    t = ("**Cloudflare 대시보드에서 하실 일 — 이 순서로 해 주세요**\n\n1. Access에 두 줄을 더합니다.\n\n"
         "**참고할 것**\n- **사설망 경로:** VIP에는 Access가 없습니다.\n"
         "- **2번을 제가 할 경우:** 제가 만들 수도 있습니다. 1번을 마쳤다고 알려 주시면 그때 하겠습니다.\n"
         "- **고친 파일:** 주석 한 줄을 고쳤습니다.")
    assert "알려 주시면 그때 하겠습니다" in ask_line(t)
    assert asks_text("커밋 초안입니다. 승인해 주시면 커밋하고 push하겠습니다.")
    assert asks_text("Sync하셨다고 알려 주시면 바로 확인하겠습니다.")
    # 일을 마친 뒤의 제안 — 사람이 안 해도 일은 끝났다(227, 563188 · 「있으면 … 알려 주시면」)
    assert not asks_text("수동 실행만 확인했습니다. 내일 정기 실행이 끝난 뒤 확인하라고 하시면 그때 체크하겠습니다.")
    assert not asks_text("세션을 눌러 상세를 봐 주세요. 이상한 점이 있으면 알려 주시면 바로 고치겠습니다.")


def test_report_read_refuses_probe():
    """11-11(사용자) — 점검 도구(screen.py ?probe=1 → 헤더 X-Foreman-Probe)가 연 패널은 읽음으로 세지 않는다."""
    import asyncio
    from types import SimpleNamespace
    from bridge.api.dashboard import report_read_api
    req = SimpleNamespace(headers={"x-foreman-probe": "1"}, app=None)        # app에 닿으면 터진다 — 닿기 전에 거절
    r = asyncio.run(report_read_api(1, req, 5))
    assert r["ok"] is False and "점검" in r["note"]


def test_asks_text_not_asking():
    """끝 문단을 넓히며 실제 DB에서 본 거짓 꼴(11-11)."""
    # 인용 안의 말 — 챗봇 문장 · 화면 문구
    assert not asks_text('- 신발이 1켤레만 남으면 표 대신 "한 켤레 더 골라 주세요"를 띄웁니다.')
    assert not asks_text("1. **금액 되묻기 문장을 바꿉니다.** 「치료비 총액을 알려 주세요」로 묻습니다.")
    # FAQ · ?로 끝나는 제목 줄
    assert not asks_text("- **Q:** 동물등록 할인 대신 그 돈을 기부할 수 있다던데요?\n- **A:** 아닙니다.")
    assert not asks_text("## Is changing the ConfigMap enough this evening?\n\n네, 충분합니다.")
    # 조건부 제안 — 일은 끝났다(문장 가운데여도)
    assert not asks_text("커밋했습니다.\n\n다르게 원하시면 알려 주세요.")
    assert not asks_text("- 개별 리뷰로 바꾸길 원하시면 말씀해 주세요. BITR 리뷰에도 38이 있습니다.")
    assert not asks_text("- 실수로 체크하셨다면 알려 주세요.")
    # 같은 줄에 진짜 물음과 제안이 같이 있으면 물음으로 본다
    assert asks_text("어느 쪽으로 할지 정해 주시면, 고치고 넘어가겠습니다. 바꿀 것이 있으면 함께 말씀해 주세요.")
    assert asks_text("**이대로 진행할까요?** 바꿀 곳이 있으면 말씀해 주세요.")


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


@pytest.mark.db
async def test_report_until_read(env):
    """보고 옴(11-11) — 묻지 않고 끝난 응답은 report. 읽으면 사라지고, 다음 응답이 오면 다시. 묻는 응답은 asks(report 아님)."""
    s, conn = env
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    def reply(sid, char, ts, txt):
        with conn.cursor() as c:
            c.execute("INSERT INTO event (session_id, character_id, source, ts, type, payload) VALUES (%s, %s, 'transcript', %s, "
                      "'assistant_msg', %s)", (sid, char, ts, json.dumps({"block": "text", "text": txt})))
            return c.lastrowid
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', 'aaaaaaaa-0000-0000-0000-000000000014', 't', 'user')", (char,))
        sid = c.lastrowid
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 1, 'human', %s)", (sid, now - timedelta(hours=1)))
    e1 = reply(sid, char, now - timedelta(minutes=5), "고쳤고 커밋했습니다.\n\n자세한 내용은 log에 적었습니다.")
    engine = make_engine(s)
    try:
        async with engine.connect() as c:
            n = (await human_needs(c, f"({sid})"))[sid]
        assert n["report"]["event_id"] == e1 and "asks" not in n
        assert not (await report_read(engine, sid, e1 + 999))["ok"]   # 그사이 바뀐 응답이면 읽음으로 하지 않는다
        assert (await report_read(engine, sid, e1))["ok"]
        async with engine.connect() as c:
            assert sid not in await human_needs(c, f"({sid})")
        e2 = reply(sid, char, now - timedelta(minutes=1), "하나 더 고쳤습니다.")
        async with engine.connect() as c:
            assert (await human_needs(c, f"({sid})"))[sid]["report"]["event_id"] == e2
        reply(sid, char, now, "이대로 진행할까요?")                   # 묻는 응답 — 보고가 아니라 답 기다림
        async with engine.connect() as c:
            n = (await human_needs(c, f"({sid})"))[sid]
        assert "asks" in n and "report" not in n
        # 사람이 다시 입력하면 둘 다 풀린다 · 하루 넘은 응답은 보고로 띄우지 않는다
        with conn.cursor() as c:
            c.execute("INSERT INTO turn (session_id, seq, origin, started_at) VALUES (%s, 2, 'human', %s)", (sid, now + timedelta(seconds=1)))
        async with engine.connect() as c:
            assert sid not in await human_needs(c, f"({sid})")
        with conn.cursor() as c:                                       # 사람 입력을 26시간 전으로 옮기고, 그 뒤 25시간 전 응답
            c.execute("UPDATE turn SET started_at = %s WHERE session_id = %s AND seq = 2", (now - timedelta(hours=26), sid))
        reply(sid, char, now - timedelta(hours=25), "끝났습니다.")
        async with engine.connect() as c:
            assert "report" not in (await human_needs(c, f"({sid})")).get(sid, {})
    finally:
        await engine.dispose()


def test_visible_rows_reused_worktree_name():
    """11-11(UI 불만 (나)) — 이름이 다시 쓰인 worktree의 옛 끝난 세션은 목록에 남기지 않는다."""
    from bridge.api.dashboard import ended_info, visible_rows
    now = datetime(2026, 11, 11, 3, 0)
    old = now - timedelta(days=3)
    wt = "/r/.worktrees/foreman-3"
    row = lambda i, cc, cwd, ts: (i, cc, cwd, None, None, "c", "foreman", ts)
    rows = [row(188, "a", wt, old), row(258, "b", wt, old), row(270, "c", wt, old),     # 옛 세션 셋 — 합침 · 그냥 끝남
            row(272, "d", wt, now),                                                    # 지금 세션
            row(300, "e", "/r/.worktrees/x", old),                                     # 쉬게 한 뒤 남은 worktree(마지막 세션)
            row(301, "f", "/r/.worktrees/y", old)]                                     # 마지막 세션인데 합침
    done = {258: ("wt-merge", old), 270: ("wt-merge", old), 300: ("rest", old), 301: ("wt-merge", old)}
    got = [r[0] for r in visible_rows(rows, {"d": 1}, now - timedelta(hours=48), done, isdir=lambda p: True)]
    assert got == [272, 300]
    # 지금 세션이 끝나도 그 폴더의 마지막이면 남는다
    got = [r[0] for r in visible_rows(rows, {}, now + timedelta(days=5), done, isdir=lambda p: True)]
    assert got == [272, 300]
    assert ended_info(done[258], None)["kind"] == "merged" and ended_info(None, old)["kind"] == "gone"


def test_no_crew():
    """11-13 사용자 — 코더 상주 · 임시 구분을 없앴다. 서버는 crew 값을 더 만들지 않는다(화면 배지도 역할만)."""
    import bridge.api.dashboard as d
    assert not hasattr(d, "mark_crew")
