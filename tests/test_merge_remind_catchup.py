"""브리지가 꺼져 있던 동안 지난 5일째 알림을 다시 떴을 때 보내기(11-13 사용자, 관리자 318 일감 F).

브리지가 내려가 있던 사이 시각이 흘렀다고 보고 escalate 시각을 앞당긴 뒤, 새 MergePrep(다시 띄운 것)으로 맞춘다.
5~7일 사이 · 7일 넘음 · 이미 보냄 · 끈 카드 · 합친 카드. 시각은 시험 안에서 잰다. 실제 config/*.toml은 읽지 않는다.
"""

import json
from datetime import timedelta

import pytest
from test_merge_wait_manager import _card, _char, _now, _session, env  # noqa: F401
from test_merge_wait_off_remind import RN, _drain, _restart

from bridge import mergeprep as mp
from bridge.api.dashboard import asks_off
from bridge.db.engine import make_engine


def _age(conn, eid, delta):
    with conn.cursor() as c:
        c.execute("UPDATE session_action SET created_at = %s WHERE id = %s", (_now() - delta, eid))


async def _first(engine, conn, mid, cc, nt):
    """카드 7을 올려 두고 (m, eid)를 돌려준다 — 올릴 때의 알림은 지운다."""
    from test_merge_wait_manager import _mp
    m, _ = _mp(engine, cc, nt)
    m.cards[7] = _card(7)
    await m.sync()
    await _drain(m)
    nt.sent.clear()
    return m, m.cards[7].esc_id


@pytest.mark.db
async def test_catchup_between_five_and_seven_days(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 71)
    cc = f"aaaaaaaa-0000-0000-0000-{71:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, eid = await _first(engine, conn, 71, cc, nt)
        _age(conn, eid, timedelta(days=6, hours=3))                          # 브리지가 내려가 있던 사이 6일이 지났다
        m2, _ = _restart(engine, cc, m.cards[7], nt)                         # 다시 떴다
        await m2.sync()
        await m2.sync()
        await _drain(m2)
        assert len(nt.sent) == 1 and nt.sent[0]["rule"] == f"mergeprep:remind:{eid}" and nt.sent[0]["later"] is False
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_catchup_after_seven_days_once(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 72)
    cc = f"aaaaaaaa-0000-0000-0000-{72:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, eid = await _first(engine, conn, 72, cc, nt)
        _age(conn, eid, timedelta(days=9))                                   # 7일도 넘겨 머리 위에서 사라졌다
        m2, _ = _restart(engine, cc, m.cards[7], nt)
        await m2.sync()
        await m2.sync()
        await _drain(m2)
        assert len(nt.sent) == 1
        x = nt.sent[0]
        assert x["rule"] == f"mergeprep:remind:{eid}" and x["later"] is False and x["sid"] == 7
        assert "7일이 지나 관리자 머리 위에서 사라졌습니다 — 카드는 남아 있습니다 · 세션 7 「일 하나」" in x["msg"]
        assert "브리지가 꺼져 있던 동안 지났습니다" in x["msg"]
        m3, _ = _restart(engine, cc, m2.cards[7], nt)                        # 또 다시 떠도 한 번
        await m3.sync()
        await _drain(m3)
        assert len(nt.sent) == 1
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_catchup_when_already_sent(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 73)
    cc = f"aaaaaaaa-0000-0000-0000-{73:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, eid = await _first(engine, conn, 73, cc, nt)
        _age(conn, eid, timedelta(days=5, minutes=1))
        await m.sync()                                                       # 브리지가 살아 있어 5일째 알림이 나갔다
        await _drain(m)
        assert len(nt.sent) == 1
        _age(conn, eid, timedelta(days=8))
        m2, _ = _restart(engine, cc, m.cards[7], nt)
        await m2.sync()
        await _drain(m2)
        assert len(nt.sent) == 1                                             # 같은 열쇠 — 다시 안 보낸다
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_catchup_for_off_or_merged_cards(env):
    s, conn = env
    ch = _char(conn)
    mgr = _session(conn, ch, "manager", 74)
    cc = f"aaaaaaaa-0000-0000-0000-{74:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, eid = await _first(engine, conn, 74, cc, nt)
        m.cards[8] = _card(8, head="c" * 40)
        await m.sync()
        await _drain(m)
        nt.sent.clear()
        assert (await asks_off(engine, mgr))["ok"]                           # 사람이 둘 다 끔(떠 있을 때, 한 번에 하나씩) → 알리지 않는다
        assert (await asks_off(engine, mgr))["ok"]
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (_now() - timedelta(days=9),))
        m2, _ = _restart(engine, cc, m.cards[7], nt)                         # 다시 떠서 esc_off_at을 아직 모르는 카드
        m2.cards[7].esc_off_at = None
        m2.cards[8] = mp.Card.from_saved(json.loads(mp.card_json(m.cards[8])))
        m2.cards[8].esc_off_at = None
        await m2.sync()
        await _drain(m2)
        assert nt.sent == [] and m2.cards[7].esc_off_at and m2.cards[8].esc_off_at
        # 합친 카드는 대기 카드가 아니니 알리지 않는다
        m3, _ = _restart(engine, cc, m.cards[7], nt)
        m3.cards[7].status, m3.cards[7].esc_off_at = "merged", None
        await m3.sync()
        await _drain(m3)
        assert nt.sent == []
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_catchup_when_remind_days_zero(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 75)
    cc = f"aaaaaaaa-0000-0000-0000-{75:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, eid = await _first(engine, conn, 75, cc, nt)
        _age(conn, eid, timedelta(days=9))
        m2, _ = _restart(engine, cc, m.cards[7], nt)
        m2.cfg.remind_days = 0
        await m2.sync()
        await _drain(m2)
        assert nt.sent == []
    finally:
        await engine.dispose()
