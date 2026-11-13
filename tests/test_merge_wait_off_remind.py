"""사람 승인 합치기 물음 — 사람이 끈 것은 막대에서도 빼기 · 5일째 한 번 알리기(11-13 사용자, 관리자 318 일감 D).

- 사람이 관리자 머리 위 합치기 물음을 [답 안 해도 됨]으로 끄면: 다시 올리지 않고(관리자가 바뀌어도 · 다시 띄워도) merge_waits에서
  빠진다(승인 막대 숫자 · 작업 세션 머리 위 · 말풍선). 카드는 남고 esc_off_at에 끈 시각. 새 커밋으로 카드가 다시 만들어지면 다시 올린다
- 브리지가 내린 것(합쳐짐 등)은 사람이 끈 것으로 세지 않는다. 7일이 지나 사라진 것도
- 물음이 remind_days(기본 5)째 떠 있으면 텔레그램 바로(later=False) 한 번 — 브리지를 다시 띄워도 한 번(notification.rule)
시각은 시험 안에서 잰다(11-13 2cb36cc). 실제 config/*.toml은 읽지 않는다.
"""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from test_merge_wait_manager import _acts, _card, _char, _mp, _needs, _now, _session, env  # noqa: F401

from bridge import mergeprep as mp
from bridge.api.dashboard import asks_off, merge_waits
from bridge.db.engine import make_engine


class RN:
    """가짜 알림 — 보낸 것을 모으고 진짜처럼 notification에 rule을 남긴다(다시 띄운 뒤 한 번만을 보려고)."""
    def __init__(self, conn):
        self.conn, self.sent = conn, []
        self.rules = SimpleNamespace(for_project=lambda p: SimpleNamespace(prefix="[FM]", digest=True))

    def send_direct(self, project, kind, sid, msg, rule=None, later=None):
        self.sent.append({"kind": kind, "sid": sid, "msg": msg, "rule": rule, "later": later})
        with self.conn.cursor() as c:
            c.execute("INSERT INTO notification (session_id, kind, decision, rule, text) VALUES (%s, %s, 'pending', %s, %s)",
                      (sid, kind, rule, msg))


async def _drain(m):
    while m.h._tasks:
        await asyncio.gather(*list(m.h._tasks))


def _restart(engine, cc, card, notifier=None):
    """다시 띄운 것처럼 — 새 MergePrep에 DB JSON으로 되살린 카드."""
    m2, who = _mp(engine, cc, notifier)
    m2.cards[card.sid] = mp.Card.from_saved(json.loads(mp.card_json(card)))
    return m2, who


@pytest.mark.db
async def test_human_off_leaves_bar_and_is_not_raised_again(env):
    s, conn = env
    ch = _char(conn)
    mgr = _session(conn, ch, "manager", 51)
    cc = f"aaaaaaaa-0000-0000-0000-{51:012d}"
    engine = make_engine(s)
    try:
        m, who = _mp(engine, cc)
        m.cards[7] = _card(7)
        await m.sync()
        eid = m.cards[7].esc_id
        assert eid and 7 in merge_waits(m)
        # 사람이 그 관리자 머리 위 [답 안 해도 됨]
        assert (await asks_off(engine, mgr))["ok"]
        await m.sync()
        c = m.cards[7]
        assert c.esc_off_at and c.esc_id == eid                               # 카드는 쥔 채 — 끈 시각만
        assert 7 not in merge_waits(m)                                        # 승인 막대 · 작업 세션 머리 위 · 말풍선에서 빠짐
        assert "escalate" not in await _needs(engine, mgr)                   # 관리자 머리 위에서도
        v = m.view(project="foreman")["cards"]
        assert [x["sid"] for x in v] == [7] and v[0]["esc_off_at"] == c.esc_off_at   # 관리자 쪽 목록에는 남는다
        await m.sync()
        assert len(_acts(conn, "escalate")) == 1 and len(_acts(conn, "esc-off")) == 1   # 다시 올리지 않고 더 내리지도 않는다
        # 관리자가 바뀌어도 다시 올리지 않는다
        _session(conn, ch, "manager", 52)
        who["cc"] = f"aaaaaaaa-0000-0000-0000-{52:012d}"
        await m.sync()
        assert len(_acts(conn, "escalate")) == 1 and m.cards[7].esc_off_at
        # 다시 띄워도 그대로(카드 JSON)
        m2, _ = _restart(engine, who["cc"], m.cards[7])
        await m2.sync()
        assert len(_acts(conn, "escalate")) == 1 and 7 not in merge_waits(m2)
        # 새 커밋으로 새 카드 → 새 일이니 다시 올린다
        m2.cards[7] = _card(7, head="d" * 40)
        await m2.sync()
        assert len(_acts(conn, "escalate")) == 2 and m2.cards[7].esc_off_at is None and 7 in merge_waits(m2)
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_bridge_close_and_expiry_are_not_human_off(env):
    """브리지가 내린 것(합쳐짐)은 esc_id를 비우니 사람이 끈 것으로 안 센다. 7일이 지나 사라진 물음(esc-off 없음)도 안 센다 — 막대에 남는다."""
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 53)
    engine = make_engine(s)
    try:
        m, _ = _mp(engine, f"aaaaaaaa-0000-0000-0000-{53:012d}")
        m.cards[7] = _card(7)
        m.cards[8] = _card(8, head="c" * 40)
        await m.sync()
        m.cards[7].status = "merged"
        with conn.cursor() as c:                                              # 8의 물음은 7일이 지났다
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate' AND detail LIKE 'question:#merge:8#%%'",
                      (_now() - timedelta(days=8),))
        await m.sync()
        assert m.cards[7].esc_id is None and m.cards[7].esc_off_at is None
        assert m.cards[8].esc_off_at is None and 8 in merge_waits(m)
        assert len(_acts(conn, "escalate")) == 2                             # 지난 것을 다시 올리지도 않는다(지금 동작 그대로)
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_remind_once_on_day_five(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 61)
    cc = f"aaaaaaaa-0000-0000-0000-{61:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, _ = _mp(engine, cc, nt)
        m.cards[7] = _card(7)
        await m.sync()
        await _drain(m)
        eid = m.cards[7].esc_id
        nt.sent.clear()                                                       # 올릴 때의 ❓ 알림은 이 시험 밖
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE id = %s", (_now() - timedelta(days=4, hours=23), eid))
        await m.sync()
        await _drain(m)
        assert nt.sent == []                                                  # 아직 5일 전
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE id = %s", (_now() - timedelta(days=5, minutes=1), eid))
        await m.sync()
        await m.sync()
        await _drain(m)
        assert len(nt.sent) == 1
        x = nt.sent[0]
        assert x["rule"] == f"mergeprep:remind:{eid}" and x["later"] is False and x["sid"] == 7   # 묶음을 켠 프로젝트여도 바로
        assert "⏳ 합치기 카드가 5일째 사람 승인을 기다립니다 — 이틀 뒤 관리자 머리 위에서 사라집니다(카드는 남음)" in x["msg"]
        assert "세션 7 「일 하나」" in x["msg"]
        # 다시 띄워도 한 번
        m2, _ = _restart(engine, cc, m.cards[7], nt)
        await m2.sync()
        await _drain(m2)
        assert len(nt.sent) == 1
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_remind_for_human_off_or_when_off(env):
    s, conn = env
    ch = _char(conn)
    mgr = _session(conn, ch, "manager", 62)
    cc = f"aaaaaaaa-0000-0000-0000-{62:012d}"
    engine = make_engine(s)
    nt = RN(conn)
    try:
        m, _ = _mp(engine, cc, nt)
        m.cards[7] = _card(7)
        await m.sync()
        await _drain(m)
        nt.sent.clear()
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (_now() - timedelta(days=6),))
        assert (await asks_off(engine, mgr))["ok"]                            # 사람이 끔 → 알리지 않는다
        await m.sync()
        await _drain(m)
        assert nt.sent == []
        # remind_days = 0이면 끈다
        m3, _ = _mp(engine, cc, nt)
        m3.cfg.remind_days = 0
        m3.cards[8] = _card(8, head="c" * 40)
        await m3.sync()
        await _drain(m3)
        nt.sent.clear()
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (_now() - timedelta(days=6),))
        await m3.sync()
        await _drain(m3)
        assert nt.sent == []
    finally:
        await engine.dispose()


def test_load_remind_days(tmp_path):
    p = tmp_path / "handoff.toml"
    p.write_text("[merge_prep]\nenabled = true\n", encoding="utf-8")
    assert mp.load(p).remind_days == 5
    p.write_text("[merge_prep]\nremind_days = 0\n", encoding="utf-8")
    assert mp.load(p).remind_days == 0
    p.write_text("[merge_prep]\nremind_days = 7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="remind_days"):
        mp.load(p)


def test_remind_text_counts_days_left():
    m = mp.MergePrep(SimpleNamespace(engine=None, sessions_dir="/x", _tasks=set()), mp.MergePrepCfg(enabled=True, remind_days=6))
    assert "6일째" in m.esc_remind_text(_card(7)) and "하루 뒤" in m.esc_remind_text(_card(7))
