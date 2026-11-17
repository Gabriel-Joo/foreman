"""관리자 물음의 번호(11-17 사용자 결정 (다), 인프라 #3058 건).

사람이 관리자에게 무엇이든 입력하면 물음이 사라지던 것을 셋으로 가른다:
- 입력 글에 물음 번호(#id)가 있으면 그 물음은 끝난 것(화면에 안 띄움)
- 번호 없이 입력하면 「아직 안 본 물음」(unseen)으로 남는다. 여러 물음이면 번호가 든 것만 끝난다
- 사람이 [봤다](esc-seen)로 하나씩 지운다. 합치기 카드 물음은 지금처럼 카드가 남는 동안 남는다
"""

from datetime import timedelta

import pytest

from bridge.api.dashboard import escalate, escalate_seen, esc_numbers, merge_tag
from bridge.db.engine import make_engine
from bridge.managers import escalate_hint
from tests.test_overhead_marks import NOW, _char, _needs, _session, env  # noqa: F401  (env는 fixture)


def _human(conn, sid, seq, at, prompt):
    with conn.cursor() as c:
        c.execute("INSERT INTO turn (session_id, seq, origin, prompt_text, started_at, ended_at) VALUES (%s, %s, 'human', %s, %s, %s)",
                  (sid, seq, prompt, at, at + timedelta(seconds=5)))


def _back(conn, minutes):
    """방금 올린 escalate를 과거로(사람 입력보다 앞에 두려고)."""
    with conn.cursor() as c:
        c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (NOW - timedelta(minutes=minutes),))


def _acts(conn, action):
    with conn.cursor() as c:
        c.execute("SELECT detail FROM session_action WHERE action = %s ORDER BY id", (action,))
        return [r[0] for r in c.fetchall()]


def test_esc_numbers():
    assert esc_numbers("#3058 승인, #12도") == {3058, 12}
    assert esc_numbers("세션 3058") == set() and esc_numbers(None) == set()
    assert 3058 not in esc_numbers("#30581")                       # 뒤에 숫자가 더 붙으면 다른 번호


def test_hint_tells_number():
    assert "번호(#id" in escalate_hint(318) and "아직 안 본 물음" in escalate_hint(318)


@pytest.mark.db
async def test_number_answers_only_that_question(env):
    """번호를 넣은 입력: 그 물음만 끝나고, 같이 떠 있던 다른 물음은 번호 없이 넘어간 것(unseen)."""
    s, conn = env
    m = _session(conn, _char(conn), "manager", 11)
    engine = make_engine(s)
    try:
        a = (await escalate(engine, m, "question", "배포를 오늘 할까요?"))
        b = (await escalate(engine, m, "question", "둘 중 무엇으로 할까요?"))
        assert "#" + str(a["id"]) in a["note"]                       # 관리자에게 번호를 돌려준다
        _back(conn, 5)
        n = await _needs(engine, m)
        assert n["escalate"]["question"]["id"] == b["id"] and "unseen" not in n["escalate"]   # 입력 전: 지금처럼
        _human(conn, m, 1, NOW - timedelta(minutes=1), f"#{a['id']} 승인합니다")
        n = await _needs(engine, m)
        assert "question" not in n["escalate"]
        assert [u["id"] for u in n["escalate"]["unseen"]] == [b["id"]]     # a는 끝남(목록에 없음), b는 아직 안 본 것
        # 나중에 b도 번호로 답하면 목록에서 빠진다
        _human(conn, m, 2, NOW - timedelta(seconds=30), f"#{b['id']}는 (가)로")
        assert "escalate" not in await _needs(engine, m)
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_number_keeps_unseen_and_seen_clears(env):
    """번호 없는 입력: 물음이 「아직 안 본 물음」으로 남고, [봤다]로 하나씩 지운다."""
    s, conn = env
    m = _session(conn, _char(conn), "manager", 12)
    engine = make_engine(s)
    try:
        a = await escalate(engine, m, "question", "하나")
        b = await escalate(engine, m, "question", "둘")
        _back(conn, 5)
        _human(conn, m, 1, NOW - timedelta(minutes=1), "다른 얘기인데, 로그 좀 봐 줘")
        n = await _needs(engine, m)
        assert "question" not in n["escalate"]
        assert [u["id"] for u in n["escalate"]["unseen"]] == [a["id"], b["id"]]
        assert n["escalate"]["unseen"][0]["text"] == "하나"
        r = await escalate_seen(engine, m, a["id"])
        assert r["ok"] and _acts(conn, "esc-seen") == [str(a["id"])]
        assert [u["id"] for u in (await _needs(engine, m))["escalate"]["unseen"]] == [b["id"]]
        assert not (await escalate_seen(engine, m, a["id"]))["ok"]     # 이미 지운 것
        assert (await escalate_seen(engine, m, b["id"]))["ok"]
        assert "escalate" not in await _needs(engine, m)                  # 목록이 저절로 비었다
        # 아직 떠 있는(입력 전) 물음은 [봤다]로 지울 수 없다. [답 안 해도 됨]이 그 몫
        c = await escalate(engine, m, "question", "셋")
        assert not (await escalate_seen(engine, m, c["id"]))["ok"]
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_merge_card_question_unchanged(env):
    """합치기 카드 물음은 번호 없는 입력에도 그대로(카드가 남는 동안), unseen으로 가지 않는다."""
    s, conn = env
    m = _session(conn, _char(conn), "manager", 13)
    engine = make_engine(s)
    try:
        await escalate(engine, m, "question", "합칠까요?", tag=merge_tag(77))
        _back(conn, 5)
        _human(conn, m, 1, NOW - timedelta(minutes=1), "다른 얘기")
        e = (await _needs(engine, m))["escalate"]
        assert e["question"]["merge_sid"] == 77 and e["merges"] == [77] and "unseen" not in e
    finally:
        await engine.dispose()
