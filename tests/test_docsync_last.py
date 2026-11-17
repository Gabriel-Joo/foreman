"""서기방 기술문서 줄의 「마지막으로 올림」을 DB에서 읽는다(11-17 사용자 결정).
한 편씩 올린 게시, 자동 맞추기, 브리지를 다시 띄운 꼴(메모리 비움), 정말 없을 때, 못 읽을 때."""
import asyncio
import time
from datetime import UTC, datetime, timedelta

from bridge import docsync as ds
from bridge import notion as nt
from test_notion import FakeNotion
from test_techdoc import FakeDB, _commit, _git


def run(c):
    return asyncio.run(c)


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


class Stamped:
    """FakeDB는 updated_at을 채우지 않는다. 동작 하나 뒤 바뀐 행에 시각을 찍는다(MySQL의 ON UPDATE 대신)."""

    def __init__(self, db):
        self.db = db

    def _snap(self):
        return {k: {c: v for c, v in r.items() if c != "updated_at"} for k, r in self.db.rows.items()}

    def after(self, before, at):
        for k, r in self.db.rows.items():
            if before.get(k) != {c: v for c, v in r.items() if c != "updated_at"}:
                r["updated_at"] = at


def _world(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, {"docs/a.md": "# A\n\n본문입니다.\n", "docs/b.md": "# B\n\n본문입니다.\n"}, "init")
    f = FakeNotion(see_all=True)
    f.pages["docs"] = {"parent": "root", "title": "[기술문서]", "archived": False}
    db = FakeDB()
    pub = nt.Publisher(db, f, "root", str(repo), project="infra", ref="HEAD", docs_page="docs", docs_mode="manual")
    return pub, db, Stamped(db)


def _one(pub, db, st, path, at):
    before = st._snap()
    run(pub.publish(path, "t"))
    st.after(before, at)


def test_one_piece_publish_counts_as_last_published(tmp_path):
    """한 편씩 올린 게시(맞추기 없이)도 마지막으로 올린 때에 들어간다. 메모리는 비어 있다."""
    pub, db, st = _world(tmp_path)
    assert run(ds.last_published(pub, None)) is None                     # 정말 없을 때만 None
    at = _now() - timedelta(minutes=3)
    _one(pub, db, st, "docs/a.md", at)
    got = run(ds.last_published(pub, None))
    assert got["done"] == 1 and got["held"] == 0 and got["failed"] == 0
    assert abs(got["at"] - at.replace(tzinfo=UTC).timestamp()) < 1


def test_many_one_by_one_in_a_window_are_counted_together(tmp_path):
    pub, db, st = _world(tmp_path)
    t = _now() - timedelta(minutes=2)
    _one(pub, db, st, "docs/a.md", t - timedelta(minutes=1))
    _one(pub, db, st, "docs/b.md", t)
    assert run(ds.last_published(pub, None))["done"] == 2
    # 한 시간 전에 올린 편은 이번 묶음이 아니다
    db.rows[("infra", "docs/a.md")]["updated_at"] = t - timedelta(hours=1)
    got = run(ds.last_published(pub, None))
    assert got["done"] == 1 and abs(got["at"] - t.replace(tzinfo=UTC).timestamp()) < 1


def test_docsync_result_survives_restart(tmp_path, monkeypatch):
    """맞추기 뒤 멈춤, 실패 수와 첫 실패가 DB에 남아, 메모리(DocSync.last)를 비워도 같은 글이 나온다."""
    pub, db, st = _world(tmp_path)
    held = [{"path": "docs/b.md", "edits": ["x"], "count": 1, "url": None}]
    failed = [{"path": "docs/c.md", "error": "거부됨"}]

    async def fake_sync(p, when, force=frozenset()):
        await p.publish("docs/a.md", when)
        return {"project": "infra", "ref_sha": "f" * 40, "done": [{"path": "docs/a.md"}], "held": held, "failed": failed, "warnings": []}
    monkeypatch.setattr(ds, "sync", fake_sync)
    d = ds.DocSync({"infra": pub})
    before = st._snap()
    run(d.run_one("infra"))
    st.after(before, _now())
    live = run(ds.last_published(pub, d.last["infra"]))
    assert (live["done"], live["held"], live["failed"], live["failed_first"]) == (1, 1, 1, "docs/c.md: 거부됨")
    d.last.clear()                                                           # 브리지를 다시 띄운 꼴
    again = run(ds.last_published(pub, None))
    assert (again["done"], again["held"], again["failed"], again["failed_first"]) == (1, 1, 1, "docs/c.md: 거부됨")
    assert abs(again["at"] - live["at"]) < 5


def test_one_piece_publish_after_sync_is_the_latest(tmp_path, monkeypatch):
    """맞추기 뒤에 한 편을 더 올리면 때는 그 한 편의 때이고, 지난 맞추기의 실패 수가 새 묶음에 딸려 오지 않는다."""
    pub, db, st = _world(tmp_path)
    failed = [{"path": "docs/c.md", "error": "거부됨"}]

    async def fake_sync(p, when, force=frozenset()):
        return {"project": "infra", "ref_sha": "f" * 40, "done": [], "held": [], "failed": failed, "warnings": []}
    monkeypatch.setattr(ds, "sync", fake_sync)
    d = ds.DocSync({"infra": pub})
    before = st._snap()
    run(d.run_one("infra"))
    st.after(before, _now() - timedelta(hours=2))
    _one(pub, db, st, "docs/b.md", _now() - timedelta(minutes=1))
    got = run(ds.last_published(pub, None))
    assert got["done"] == 1 and got["failed"] == 0 and got["failed_first"] is None


def test_summary_reads_db_and_marks_unreadable(tmp_path, monkeypatch):
    """summary: DB에서 읽은 값을 last로, 못 읽으면 last는 비우고 last_error를 둔다(없다고 하지 않는다)."""
    pub, db, st = _world(tmp_path)

    async def fake_status(p):
        return {"project": "infra", "files": ["docs/a.md"], "new": [], "changed": [], "deleted": [], "broken": [], "ref_sha": "f" * 40,
                "synced": None, "behind_commits": None, "last_commit_at": None, "mode": "manual", "ref": "HEAD"}
    monkeypatch.setattr(ds, "status", fake_status)
    r = run(ds.summary(pub, None))
    assert r["last"] is None and r["last_error"] is None                      # 기록이 정말 없다
    _one(pub, db, st, "docs/a.md", _now())
    assert run(ds.summary(pub, None))["last"]["done"] == 1

    class Broken:
        def connect(self):
            raise OSError("DB 연결 끊김")
    pub.e = Broken()
    r = run(ds.summary(pub, None))
    assert r["last"] is None and "OSError" in r["last_error"]


def test_memory_only_still_shows_when_db_has_nothing(tmp_path):
    """DB 행이 아직 없고 메모리에만 있는 결과(한 쪽 게시가 사람 수정으로 멈춘 줄)도 버리지 않는다."""
    pub, db, st = _world(tmp_path)
    mem = {"at": time.time(), "done": [], "held": [{"path": "docs/b.md"}], "failed": []}
    got = run(ds.last_published(pub, mem))
    assert got["held"] == 1 and got["done"] == 0
