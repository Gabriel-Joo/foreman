"""사람 수정으로 멈춘 편(덮기 단추 자료)이 브리지를 다시 띄운 뒤에도 남는다(11-19 사용자 결정 S4).
전에는 DocSync.last(메모리)에만 있어, 다시 띄우면 「멈춤 N」 글자만 있고 누를 단추가 없었다."""
import asyncio
from datetime import UTC, datetime

from bridge import docsync as ds
from test_docsync_last import _world

SHA = "a" * 40


def run(c):
    return asyncio.run(c)


def _fake_status(monkeypatch, changed=("docs/b.md",), sha=SHA):
    async def fake_status(p, src=None):
        return {"project": "infra", "files": ["docs/a.md", "docs/b.md"], "new": [], "changed": list(changed), "deleted": [], "broken": [],
                "ref_sha": sha, "synced": None, "behind_commits": None, "last_commit_at": None, "mode": "manual", "ref": "HEAD"}
    monkeypatch.setattr(ds, "status", fake_status)


def _forces(items):
    return [x for x in items if x.get("act") == "force"]


def _sync_holding(monkeypatch, held):
    async def fake_sync(p, when, force=frozenset(), src=None, only=None):
        return {"project": "infra", "ref_sha": SHA, "done": [], "held": held, "failed": [], "warnings": []}
    monkeypatch.setattr(ds, "sync", fake_sync)


def test_held_from_sync_survives_new_docsync(tmp_path, monkeypatch):
    pub, db, st = _world(tmp_path)
    _fake_status(monkeypatch)
    _sync_holding(monkeypatch, [{"path": "docs/b.md", "edits": ["사람이 고친 문단", "더한 메모"], "count": 2, "url": "https://notion/b"}])
    d = ds.DocSync({"infra": pub})
    before = st._snap()
    run(d.run_one("infra"))
    st.after(before, datetime.now(UTC).replace(tzinfo=None))
    assert len(_forces(run(ds.todo_items(pub, d.last["infra"])))) == 1
    d2 = ds.DocSync({"infra": pub})                                        # 브리지를 다시 띄운 꼴(메모리 빔)
    last, err = run(d2.last_for("infra"))
    assert err is None and last["held"][0]["path"] == "docs/b.md"
    f = _forces(run(ds.todo_items(pub, last)))
    assert len(f) == 1 and f[0]["path"] == "docs/b.md" and "2개" in f[0]["title"]
    # 「마지막으로 올림」의 멈춤 수는 그대로 @docs-last에서(되살린 것은 at이 없어 그 행을 가리지 않는다)
    assert run(ds.last_published(pub, last))["held"] == 1


def test_one_piece_hold_and_release_reach_db(tmp_path, monkeypatch):
    """한 편 게시(only, 11-20 묶음 게시와 같은 함수)가 멈춘 줄도 DB에 남고(고친 곳 목록은 512자 안), 그 편이 풀리면 released가 되어
    다시 띄워도 되살아나지 않는다. 다른 편의 멈춤 줄은 한 편 게시가 건드리지 않는다."""
    pub, db, _ = _world(tmp_path)
    _fake_status(monkeypatch, changed=("docs/a.md", "docs/b.md"))
    _sync_holding(monkeypatch, [{"path": "docs/a.md", "edits": ["a 고침"], "count": 1, "url": None}])
    d = ds.DocSync({"infra": pub})
    run(d.run_one("infra"))
    _sync_holding(monkeypatch, [{"path": "docs/b.md", "edits": ["x" * 300] * 5, "count": 9, "url": None}])
    run(d.run_one("infra", only={"docs/b.md"}))
    row = db.rows[("infra", ds.HELD_PRE + "docs/b.md")]
    assert row["status"] == "held" and len(row["error"]) <= 512
    assert db.rows[("infra", ds.HELD_PRE + "docs/a.md")]["status"] == "held"            # 다른 편 줄은 그대로
    d2 = ds.DocSync({"infra": pub})
    last, _ = run(d2.last_for("infra"))
    assert sorted(h["path"] for h in last["held"]) == ["docs/a.md", "docs/b.md"] and len(_forces(run(ds.todo_items(pub, last)))) == 2
    _sync_holding(monkeypatch, [])
    run(d2.run_one("infra", only={"docs/b.md"}))
    assert db.rows[("infra", ds.HELD_PRE + "docs/b.md")]["status"] == "released"
    assert db.rows[("infra", ds.HELD_PRE + "docs/a.md")]["status"] == "held"
    last, _ = run(ds.DocSync({"infra": pub}).last_for("infra"))
    assert [h["path"] for h in last["held"]] == ["docs/a.md"]


def test_next_sync_without_hold_releases_rows(tmp_path, monkeypatch):
    pub, db, _ = _world(tmp_path)
    _fake_status(monkeypatch)
    _sync_holding(monkeypatch, [{"path": "docs/b.md", "edits": ["x"], "count": 1, "url": None}])
    d = ds.DocSync({"infra": pub})
    run(d.run_one("infra"))
    _sync_holding(monkeypatch, [])
    run(d.run_one("infra"))
    assert run(ds.load_held(pub)) == []


def test_unreadable_held_rows_say_so(tmp_path):
    """못 읽으면 멈춘 편이 없다고 하지 않고 까닭을 돌려준다(화면이 「읽지 못했습니다」)."""
    pub, db, _ = _world(tmp_path)

    class Broken:
        def connect(self):
            raise OSError("DB 연결 끊김")
    pub.e = Broken()
    last, err = run(ds.DocSync({"infra": pub}).last_for("infra"))
    assert last is None and "OSError" in err


def test_held_list_missing_tells_two_cases_apart(tmp_path, monkeypatch):
    """「멈춤 N」인데 목록이 없는 것(옛 브리지가 행을 안 남김)과, 목록은 있는데 지금 덮을 편이 0인 것을 가른다(11-19)."""
    pub, db, st = _world(tmp_path)
    _fake_status(monkeypatch, changed=())                       # git이 다시 바뀌어 덮을 편이 0인 꼴
    summ = {"last": {"held": 5}}
    # (가) 멈춘 수만 있고 @docs-held 행이 없음 -> 목록을 모름, 수를 돌려준다
    last, err = run(ds.DocSync({"infra": pub}).last_for("infra"))
    assert last is None and ds.held_list_missing(summ, last, err) == 5
    # (나) 행은 있는데 지금 덮을 편이 0 -> 목록을 아니까 None(「지금 덮을 편이 없습니다」 글이 맞는 경우)
    _sync_holding(monkeypatch, [{"path": "docs/b.md", "edits": ["x"], "count": 1, "url": None}])
    run(ds.DocSync({"infra": pub}).run_one("infra"))
    last, err = run(ds.DocSync({"infra": pub}).last_for("infra"))
    assert last["held"] and ds.held_list_missing(summ, last, err) is None
    assert _forces(run(ds.todo_items(pub, last))) == []
    # 멈춘 수가 0이거나 목록을 못 읽은 때는 이 글이 아니다(못 읽은 것은 held_error 글이 따로 말한다)
    assert ds.held_list_missing({"last": {"held": 0}}, None, None) is None
    assert ds.held_list_missing({"last": None}, None, None) is None
    assert ds.held_list_missing(summ, None, "OSError: 끊김") is None
