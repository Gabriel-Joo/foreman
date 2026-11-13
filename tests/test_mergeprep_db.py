"""합치기 카드를 DB에 남기기(11-13, bridge/mergeprep.py · migrations/0032_merge_card.sql) — 임시 git 저장소 + 세션 시험 DB.

브리지를 다시 띄운 것처럼 새 MergePrep을 만들어 되살린다: 카드 · 정리 후보 · made_at 그대로, 합친 카드의 남김 시간,
DB 쓰기 실패 때 텔레그램 한 번 + 목록에 사유.
"""

import asyncio
import subprocess
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pymysql
import pytest

from bridge import mergeprep as mp
from bridge import worktree as wt
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main

CC = "f" * 8 + "-0000-0000-0000-000000000032"
SID = 32

README = """# x

### 나중에 할 일

| 무엇 | 언제 | 근거 |
|---|---|---|
| 합치기 카드 남기기 — `bridge/mergeprep.py` | 지금 | x |
"""


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(autouse=True)
def _no_squash_hook(monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"); sh(r, "config", "user.name", "t")
    (r / "README.md").write_text(README)
    (r / "docs").mkdir(); (r / "docs" / "11_x.md").write_text("`bridge/mergeprep.py`가 한다\n")
    sh(r, "add", "."); sh(r, "commit", "-qm", "init")
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
    yield s, conn, r
    conn.close()


class FakeH:
    """HandoffManager 자리 — engine만 진짜(시험 DB)."""
    def __init__(self, engine, repo, cwd):
        self.engine, self.sessions_dir, self._tasks = engine, "/nonexistent", set()
        self.repo, self.cwd = str(repo), cwd
        self.acts = []

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((action, ok, detail))

    async def session(self, sid):
        return SimpleNamespace(id=sid, cc=CC, cwd=self.cwd, title="t", project="foreman")

    async def worktree_act(self, row, act, end=False, title=None):
        return await wt.merge(self.repo, wt.split(self.cwd)[1], title=title)


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda p: None)

    def send_direct(self, project, kind, sid, msg, rule=None):
        self.sent.append((rule, msg))


def make(engine, repo, monkeypatch, notifier=None, **cfg):
    """새 MergePrep — 브리지를 다시 띄운 것과 같다(메모리 카드 없음)."""
    p = repo / ".worktrees" / "w"
    h = FakeH(engine, repo, str(p))
    m = mp.MergePrep(h, mp.MergePrepCfg(enabled=True, notify_ready=False, **cfg), notifier)
    row = (SID, CC, str(p), "카드 남기기", "foreman", "coder")

    async def cands():
        return [row]

    async def deliver(cc, cwd, msg):
        return True

    async def mgr(repo_):
        return None

    async def skipped(sid, head):
        return False

    async def no_asks(sid):
        return None
    monkeypatch.setattr(m, "_candidates", cands)
    monkeypatch.setattr(m, "_deliver", deliver)
    monkeypatch.setattr(m, "manager_of", mgr)
    monkeypatch.setattr(m, "_skipped", skipped)
    monkeypatch.setattr(m, "_asks", no_asks)
    monkeypatch.setattr(mp, "live_sessions", lambda d: {})       # 끝난 세션 — 일을 마친 것
    return m, h


async def worktree_with_commit(repo, msg="합치기 카드 남기기"):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "bridge").mkdir(exist_ok=True)
    (p / "bridge" / "mergeprep.py").write_text(msg + "\n")
    sh(p, "add", "."); sh(p, "commit", "-qm", msg)
    return p


def db_rows(conn):
    with conn.cursor() as c:
        c.execute("SELECT session_id, head, status, made_at FROM merge_card")
        return c.fetchall()


def ago(h):
    return mp._iso(mp._now() - timedelta(hours=h))


async def test_restart_restores_card_docs_and_made_at(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m1, _ = make(engine, repo, monkeypatch)
        await m1.restore()                                   # 빈 DB — 아무것도 없다
        assert await m1.check() == 1
        c1 = m1.cards[SID]
        assert c1.docs["readme"] and c1.docs["docs"]        # 정리 후보가 있다
        c1.made_at = ago(3)                                  # 세 시간 기다린 카드
        await m1.sync()
        rows = db_rows(conn)
        assert len(rows) == 1 and rows[0][0] == SID and rows[0][1] == c1.head and rows[0][2] == "ready"
        assert rows[0][3].isoformat(timespec="seconds") + "Z" == c1.made_at
        want = c1.view()

        m2, h2 = make(engine, repo, monkeypatch)            # 브리지를 다시 띄웠다
        assert m2.cards == {}
        assert await m2.restore() == 1
        assert m2.cards[SID].view() == want                 # 카드 · 정리 후보 · made_at 그대로
        assert await m2.check() == 1                         # 같은 커밋 — 다시 만들지 않는다
        assert m2.cards[SID].made_at == want["made_at"] and m2.cards[SID].docs == want["docs"]
        assert h2.acts == []                                 # 카드 새로 만듦 기록 · 알림 없음
        assert m2.view()["store"]["ok"] and m2.view()["store"]["restored"] == 1
    finally:
        await engine.dispose()


async def test_restored_card_with_new_commit_is_remade(env, monkeypatch):
    s, conn, repo = env
    p = await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m1, _ = make(engine, repo, monkeypatch)
        await m1.restore()
        await m1.check()
        m1.cards[SID].made_at = ago(3)
        await m1.sync()
        old_head = m1.cards[SID].head
        (p / "b.txt").write_text("more\n"); sh(p, "add", "."); sh(p, "commit", "-qm", "더")   # 꺼져 있는 사이 커밋
        m2, h2 = make(engine, repo, monkeypatch)
        await m2.restore()
        await m2.check()
        c = m2.cards[SID]
        assert c.head != old_head and c.ahead == 2 and c.made_at > ago(0.1)     # 지금처럼 다시 만든다
        assert h2.acts and h2.acts[0][0] == mp.ACT_CARD
        assert db_rows(conn)[0][1] == c.head
    finally:
        await engine.dispose()


async def test_main_moved_keeps_made_at(env, monkeypatch):
    """main만 앞섰다(같은 브랜치 끝 커밋) — 카드는 다시 재지만 「오래됨」 시각은 잇는다."""
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m, _ = make(engine, repo, monkeypatch)
        await m.restore()
        await m.check()
        m.cards[SID].made_at = ago(5)
        made = m.cards[SID].made_at
        (repo / "c.txt").write_text("main\n"); sh(repo, "add", "."); sh(repo, "commit", "-qm", "main 앞섬")
        await m.check()
        assert m.cards[SID].behind == 1 and m.cards[SID].made_at == made
    finally:
        await engine.dispose()


async def test_merged_card_keep_time_from_db(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m1, _ = make(engine, repo, monkeypatch)
        await m1.restore()
        await m1.check()
        r = await m1.approve(SID)
        assert r["ok"] and m1.cards[SID].status == "merged" and m1.cards[SID].has_docs()
        assert db_rows(conn)[0][2] == "merged"               # 합친 결과가 DB에 있다

        m1.cards[SID].updated_at = ago(7)                    # 6시간 넘음 — 정리 후보가 남았으니 둔다
        await m1.sync()
        m2, _ = make(engine, repo, monkeypatch)
        await m2.restore()
        await m2.check()
        assert m2.cards[SID].status == "merged" and m2.cards[SID].updated_at == m1.cards[SID].updated_at

        m2.cards[SID].updated_at = ago(73)                   # keep_docs_h(72) 넘음 — 치우고 DB에서도 지운다
        await m2.check()
        assert SID not in m2.cards and db_rows(conn) == ()

        m3, _ = make(engine, repo, monkeypatch)              # 다시 띄워도 돌아오지 않는다
        assert await m3.restore() == 0
    finally:
        await engine.dispose()


async def test_merged_card_without_docs_goes_after_keep_h(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m1, _ = make(engine, repo, monkeypatch)
        await m1.restore()
        await m1.check()
        await m1.approve(SID)
        c = m1.cards[SID]
        c.docs = {"readme": [], "docs": [], "readme_rows": 0}
        c.updated_at = ago(5)
        await m1.sync()
        m2, _ = make(engine, repo, monkeypatch)
        await m2.restore()
        await m2.check()
        assert SID in m2.cards                                # 6시간 안
        m2.cards[SID].updated_at = ago(7)
        await m2.check()
        assert SID not in m2.cards and db_rows(conn) == ()
    finally:
        await engine.dispose()


async def test_merging_card_restored_as_failed(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    try:
        m1, _ = make(engine, repo, monkeypatch)
        await m1.restore()
        await m1.check()
        m1.cards[SID].status = "merging"                     # 합치는 중에 브리지가 내려갔다
        await m1.sync()
        m2, _ = make(engine, repo, monkeypatch)
        await m2.restore()
        c = m2.cards[SID]
        assert c.status == "failed" and "결과를 모릅니다" in c.error
        assert db_rows(conn)[0][2] == "failed"
    finally:
        await engine.dispose()


async def test_db_write_failure_tells_once_and_keeps_cards(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    note = FakeNotifier()
    try:
        m, h = make(engine, repo, monkeypatch, notifier=note)
        await m.restore()
        with conn.cursor() as c:
            c.execute("RENAME TABLE merge_card TO merge_card_off")       # 표가 없다(마이그레이션 전에 띄운 것과 같다)
        assert await m.check() == 1                                       # 카드는 메모리로 돈다
        await asyncio.sleep(0.05)
        v = m.view()
        assert v["cards"][0]["sid"] == SID
        assert not v["store"]["ok"] and "DB에 남기지 못했습니다" in v["store"]["error"]
        assert not v["health"]["ok"] and "DB에 남기지 못했습니다" in v["health"]["error"]   # 패널 「합치기 승인」에 사유
        assert len(note.sent) == 1 and note.sent[0][0].startswith("mergeprep:db:save") and "⚠" in note.sent[0][1]

        m.cards[SID].note = "바뀜"                                        # 또 실패 — 다시 보내지 않는다
        await m.check()
        await asyncio.sleep(0.05)
        assert len(note.sent) == 1 and not m.view()["health"]["ok"]

        with conn.cursor() as c:
            c.execute("RENAME TABLE merge_card_off TO merge_card")
        await m.check()                                                   # 다시 된다 — 사유가 사라지고 밀린 카드를 쓴다
        assert m.view()["store"]["ok"] and m.view()["health"]["ok"]
        assert db_rows(conn)[0][0] == SID
    finally:
        await engine.dispose()


async def test_db_read_failure_on_restore_tells_and_runs(env, monkeypatch):
    s, conn, repo = env
    await worktree_with_commit(repo)
    engine = make_engine(s)
    note = FakeNotifier()
    try:
        with conn.cursor() as c:
            c.execute("DROP TABLE merge_card")
        m, _ = make(engine, repo, monkeypatch, notifier=note)
        assert await m.restore() == 0
        await asyncio.sleep(0.05)
        assert not m.view()["store"]["ok"] and "되살리지 못했습니다" in m.view()["store"]["error"]
        assert len(note.sent) == 1 and note.sent[0][0].startswith("mergeprep:db:load")
        assert await m.check() == 1                                       # 훑기는 돈다
    finally:
        await engine.dispose()


def test_load_keep_hours(tmp_path):
    (tmp_path / "a.toml").write_text("[merge_prep]\nenabled = true\n")
    c = mp.load(tmp_path / "a.toml")
    assert c.keep_h == 6 and c.keep_docs_h == 72
    (tmp_path / "b.toml").write_text("[merge_prep]\nenabled = true\nkeep_h = 6\nkeep_docs_h = 2\n")
    with pytest.raises(ValueError):
        mp.load(tmp_path / "b.toml")


def test_from_saved_ignores_unknown_fields():
    c = mp.Card(sid=1, title=None, project=None, role=None, repo="/r", name="w", branch="cc/w", base="main", head="h" * 40,
                base_head="b" * 40, live=False, why="", ahead=1, behind=0, commits=["x"], files=["a"], conflict=None, docs=None,
                made_at="2026-11-13T00:00:00Z", updated_at="2026-11-13T00:00:00Z")
    d = {**c.view(), "새칸": 1}                                            # view의 ff · head8 · 뒤 버전 칸은 버린다
    assert mp.Card.from_saved(d) == c
