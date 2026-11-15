"""사람 승인 합치기 카드를 관리자 머리 위로(11-13 사용자 — 「나는 관리자하고만 이야기한다」) · 정리 후보 다 골랐다(docs_done).

- 사람 승인 카드가 생기면 브리지가 그 프로젝트 관리자에게 escalate 물음을 기계적으로 만든다 → 관리자 머리 위 「사용자 답 기다림」
- 카드가 합쳐지거나 · 미뤄지거나 · 없어지면 그 물음을 내린다(esc-off). 사람이 그 관리자에게 입력해도 카드가 남으면 남긴다
- 관리자가 없거나 올리지 못하면 작업 세션 머리 위 「합치기 기다림」으로 남긴다(merge_waits to_manager None)
시각은 시험 안에서 잰다(모듈을 불러올 때 시각은 전체 실행에서 낡는다 — 11-13 2cb36cc).
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pymysql
import pytest

from bridge import mergeprep as mp
from bridge.api.dashboard import asks_off, escalate, human_needs, merge_tag, merge_waits
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.inject import Refused


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


def _now():
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _char(conn, project="foreman"):
    with conn.cursor() as c:
        c.execute("SELECT ch.id FROM `character` ch JOIN project p ON p.id = ch.project_id WHERE p.name = %s LIMIT 1", (project,))
        return c.fetchone()[0]


def _session(conn, char, role, n):
    with conn.cursor() as c:
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', %s, %s, 't', 'user')", (char, role, f"aaaaaaaa-0000-0000-0000-{n:012d}"))
        return c.lastrowid


def _human_turn(conn, sid, at):
    with conn.cursor() as c:
        c.execute("INSERT INTO turn (session_id, seq, origin, started_at, ended_at) VALUES (%s, 1, 'human', %s, %s)",
                  (sid, at, at + timedelta(seconds=5)))


def _acts(conn, action):
    with conn.cursor() as c:
        c.execute("SELECT session_id, detail FROM session_action WHERE action = %s ORDER BY id", (action,))
        return c.fetchall()


async def _needs(engine, sid):
    async with engine.connect() as c:
        return (await human_needs(c, f"({sid})")).get(sid) or {}


class N:
    """가짜 알림 — 보낸 것을 모은다."""
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda p: SimpleNamespace(prefix="[FM]", digest=False))

    def send_direct(self, project, kind, sid, msg, rule=None, later=None):
        self.sent.append((kind, sid, msg))


class FakeH:
    def __init__(self, engine):
        self.engine, self.sessions_dir, self._tasks = engine, "/nonexistent", set()
        self.acts = []

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((sid, action, ok, detail))


def _card(sid, **kw):
    base = dict(sid=sid, title="일 하나", project="foreman", role="coder", repo="/r", name=f"w{sid}", branch=f"cc/w{sid}",
                base="main", head="a" * 40, base_head="b" * 40, live=False, why="세션이 끝났습니다", ahead=1, behind=0,
                commits=["x"], files=["migrations/0099_x.sql"], conflict=None, docs=None,
                human_why=["마이그레이션: migrations/0099_x.sql"], note="사람 승인 카드입니다",
                made_at=mp._iso(mp._now()), updated_at=mp._iso(mp._now()))
    return mp.Card(**(base | kw))


def _mp(engine, mgr_cc, notifier=None, notify_ready=False):
    m = mp.MergePrep(FakeH(engine), mp.MergePrepCfg(enabled=True, notify_ready=notify_ready), notifier)
    m._restored = True
    who = {"cc": mgr_cc}

    async def manager_of(repo):
        return (who["cc"], "/r") if who["cc"] else None
    m.manager_of = manager_of
    return m, who


@pytest.mark.db
async def test_merge_question_survives_human_input_and_does_not_hide_other_question(env):
    """합치기 카드 물음은 사람이 입력해도 남고(카드가 남았으니), 관리자의 다른 물음을 덮거나 지우지 않는다. 글에 기계 표시는 안 보인다."""
    s, conn = env
    ch = _char(conn)
    m = _session(conn, ch, "manager", 1)
    engine = make_engine(s)
    try:
        q = await escalate(engine, m, "question", "배포를 오늘 할까요?")
        mq = await escalate(engine, m, "question", "세션 7 「일」 합치기 카드에 사람 승인이 필요합니다", tag=merge_tag(7))
        n = (await _needs(engine, m))["escalate"]
        assert n["question"]["id"] == mq["id"] and n["question"]["merge_sid"] == 7 and n["merges"] == [7]
        assert not n["question"]["text"].startswith("#merge")              # 사람에게 보이는 글에는 표시가 없다
        # 카드 물음을 내려도(브리지 esc-off) 앞의 다른 물음은 그대로 보인다
        with conn.cursor() as c:
            c.execute("INSERT INTO session_action (session_id, action, ok, detail) VALUES (%s, 'esc-off', 1, %s)", (m, str(mq["id"])))
        n = (await _needs(engine, m))["escalate"]
        assert n["question"]["id"] == q["id"] and "merges" not in n
        # 새 카드 물음 → 사람이 그 관리자에게 입력: 다른 물음은 풀리고 카드 물음은 남는다
        mq2 = await escalate(engine, m, "question", "세션 8 합치기 카드", tag=merge_tag(8))
        with conn.cursor() as c:
            c.execute("UPDATE session_action SET created_at = %s WHERE action = 'escalate'", (_now() - timedelta(minutes=5),))
        _human_turn(conn, m, _now() - timedelta(minutes=1))
        n = (await _needs(engine, m))["escalate"]
        assert n["question"]["id"] == mq2["id"] and n["question"]["merge_sid"] == 8
        # 사람이 [답 안 해도 됨]을 누르면 그 카드 물음도 꺼진다
        assert (await asks_off(engine, m))["ok"]
        assert "escalate" not in await _needs(engine, m)
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_human_card_goes_to_manager_and_comes_down(env):
    s, conn = env
    ch = _char(conn)
    mgr = _session(conn, ch, "manager", 11)
    engine = make_engine(s)
    nt = N()
    try:
        m, _who = _mp(engine, f"aaaaaaaa-0000-0000-0000-{11:012d}", nt)
        m.cards[7] = _card(7)
        await m.sync()
        c = m.cards[7]
        assert c.esc_id and c.esc_mgr == mgr and c.esc_error is None
        rows = _acts(conn, "escalate")
        assert len(rows) == 1 and rows[0][0] == mgr and rows[0][1].startswith("question:#merge:7# 세션 7 「일 하나」 합치기 카드에 사람 승인이 필요합니다")
        assert "패널 [합치기]" in rows[0][1] and "마이그레이션" in rows[0][1]
        assert nt.sent and nt.sent[-1][0] == "escalate" and "#merge" not in nt.sent[-1][2]   # 알림 글에는 표시가 없다
        w = merge_waits(m)[7]
        assert w["to_manager"] == mgr                                         # 작업 세션 머리 위에는 안 띄운다(막대는 센다)
        n = (await _needs(engine, mgr))["escalate"]["question"]
        assert n["merge_sid"] == 7
        # 다시 맞춰도 또 만들지 않는다
        await m.sync()
        assert len(_acts(conn, "escalate")) == 1
        # 합쳐짐 → 내린다
        eid = c.esc_id
        m.cards[7].status = "merged"
        await m.sync()
        assert [d for _, d in _acts(conn, "esc-off")] == [str(eid)]
        assert m.cards[7].esc_id is None and "escalate" not in await _needs(engine, mgr)
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_card_gone_or_skipped_brings_question_down(env):
    s, conn = env
    ch = _char(conn)
    mgr = _session(conn, ch, "manager", 12)
    engine = make_engine(s)
    try:
        m, _ = _mp(engine, f"aaaaaaaa-0000-0000-0000-{12:012d}")
        m.cards[7] = _card(7)
        m.cards[8] = _card(8, head="c" * 40)
        await m.sync()
        assert len(_acts(conn, "escalate")) == 2
        del m.cards[7]                                                        # 카드가 없어짐(버림 · 다시 일함)
        await m.sync()
        await m.skip(8)                                                       # 미룸
        assert len(_acts(conn, "esc-off")) == 2 and "escalate" not in await _needs(engine, mgr)
        # 다시 띄운 것처럼 새 MergePrep — 내릴 것이 없으면 아무것도 안 한다
        m2, _ = _mp(engine, f"aaaaaaaa-0000-0000-0000-{12:012d}")
        await m2.sync()
        assert len(_acts(conn, "esc-off")) == 2
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_no_manager_stays_on_worker_then_manager_comes_and_changes(env):
    s, conn = env
    ch = _char(conn)
    engine = make_engine(s)
    try:
        m, who = _mp(engine, None)
        m.cards[7] = _card(7)
        await m.sync()
        assert m.cards[7].esc_id is None and "관리자 세션이 없습니다" in m.cards[7].esc_error
        assert merge_waits(m)[7]["to_manager"] is None                       # 작업 세션 머리 위 「합치기 기다림」으로 남는다
        assert len(_acts(conn, "escalate")) == 0
        a = _session(conn, ch, "manager", 21)                                 # 관리자가 뜸 → 올린다
        who["cc"] = f"aaaaaaaa-0000-0000-0000-{21:012d}"
        await m.sync()
        assert m.cards[7].esc_mgr == a and m.cards[7].esc_error is None
        first = m.cards[7].esc_id
        b = _session(conn, ch, "manager", 22)                                 # 관리자 인계 → 옛 것 내리고 새 관리자에게
        who["cc"] = f"aaaaaaaa-0000-0000-0000-{22:012d}"
        await m.sync()
        assert m.cards[7].esc_mgr == b and m.cards[7].esc_id != first
        assert [tuple(r) for r in _acts(conn, "esc-off")] == [(a, str(first))]
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_escalate_refused_stays_on_worker(env):
    """관리자로 찾은 세션이 관리자가 아니면(escalate 403) 작업 세션 머리 위로 남고 까닭을 단다."""
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "coder", 31)
    engine = make_engine(s)
    try:
        m, _ = _mp(engine, f"aaaaaaaa-0000-0000-0000-{31:012d}")
        m.cards[7] = _card(7)
        await m.sync()
        assert m.cards[7].esc_id is None and "관리자에게 올리지 못했습니다" in m.cards[7].esc_error
        assert merge_waits(m)[7]["to_manager"] is None and merge_waits(m)[7]["esc_error"]
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_manager_card_not_raised_and_notify_ready_skips_double_alert(env):
    s, conn = env
    ch = _char(conn)
    _session(conn, ch, "manager", 41)
    engine = make_engine(s)
    nt = N()
    try:
        m, _ = _mp(engine, f"aaaaaaaa-0000-0000-0000-{41:012d}", nt, notify_ready=True)
        m.cards[7] = _card(7, approver="manager", human_why=[], note=None)    # 관리자가 승인하는 카드 — 사람 화면에 안 띄운다
        m.cards[8] = _card(8, approver="human", human_why=[], note=None)      # 승인자가 사람인 프로젝트 — 올린다
        await m.sync()
        assert m.cards[7].esc_id is None and m.cards[8].esc_id
        assert "이 프로젝트의 합치기 승인자는 사람입니다" in _acts(conn, "escalate")[0][1]
        assert nt.sent == []                                                  # 「⑂ 합치기 준비됨」이 이미 나갔다 — 두 번 안 보냄
    finally:
        await engine.dispose()


# ── 정리 후보를 다 골랐다(docs_done) ──
@pytest.mark.db
async def test_docs_done_clears_merged_card_and_db(env):
    s, conn = env
    engine = make_engine(s)
    try:
        m, _ = _mp(engine, None)
        docs = {"readme": [{"line": 9, "text": "x", "score": 100}], "docs": []}
        m.cards[7] = _card(7, status="merged", docs=docs, human_why=[])
        m.cards[8] = _card(8, head="c" * 40)
        await m.sync()
        with conn.cursor() as c:
            c.execute("SELECT session_id FROM merge_card ORDER BY session_id")
            assert [r[0] for r in c.fetchall()] == [7, 8]
        with pytest.raises(Refused):
            await m.docs_done(8, by="manager")                               # 대기 카드는 skip으로
        with pytest.raises(Refused):
            await m.docs_done(99)
        r = await m.docs_done(7, by="manager")
        assert r["ok"] and 7 not in m.cards and "정리 후보 1개" in r["note"]
        assert m.h.acts[-1][:3] == (7, mp.ACT_DOCS, True)
        with conn.cursor() as c:
            c.execute("SELECT session_id FROM merge_card")
            assert [r[0] for r in c.fetchall()] == [8]
    finally:
        await engine.dispose()


def test_merged_msg_tells_docs_done():
    m = mp.MergePrep(SimpleNamespace(engine=None, sessions_dir="/x", _tasks=set()), mp.MergePrepCfg(enabled=True))
    c = _card(7, docs={"readme": [{"line": 9, "text": "x", "score": 10}], "docs": []}, human_why=[], approved_by="human")
    msg = m._merged_msg(c, {"merged": 1})
    assert 'POST /api/sessions/7/merge-prep {"action":"docs_done","by":"manager"}' in msg
    assert f"{m.cfg.keep_docs_h}시간 뒤 치운다" in msg
    assert "docs_done" not in m._merged_msg(_card(7, docs=None, human_why=[]), {"merged": 1})   # 정리 후보가 없으면 안 적는다


def test_api_accepts_docs_done():
    from bridge.api.handoff import MergePrepIn
    assert MergePrepIn(action="docs_done", by="manager").action == "docs_done"
