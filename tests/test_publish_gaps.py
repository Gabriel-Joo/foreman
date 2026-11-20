"""게시기 빈틈 넷(11-20 관리자 410 일감, 펫퍼민트와 런슈즈가 실제로 올려 보고 찾음). 진짜 git 저장소, 가짜 Notion, 메모리 게시 기록.
실제 Notion에는 올리지 않는다.

1. 파일 이름만 바꾼 포트폴리오 편(글은 같음)도 제목이 새 번호로 맞춰진다
2. 한 편 게시가 그 편을 기다리던 「링크만」 편을 다시 잇고, 그 편 부모의 차례를 맞춘다
3. 게시 잠금이 프로젝트마다다. 같은 프로젝트를 기다리다 한도를 넘으면 까닭과 함께 409, Notion 요청 간격은 함께 지킨다
4. 원본이 사라진 편의 페이지를 사람이 Notion에서 지웠으면 게시 기록을 맞추고 실패로 남기지 않는다
"""
import asyncio
import subprocess

from bridge import docsync as ds
from bridge import notion as nt
from test_portfolio_sync import FILES, _app, _links, _pid, _world, run
from test_scopetoken import ADMIN, RUN, h
from test_techdoc import _commit


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _wrote(f, pid):
    """가짜 Notion 호출 기록에서 그 페이지(또는 그 페이지의 블록)에 글을 쓴 것이 있나. 옮기기(move)와 제목은 글이 아니다."""
    ids = {pid} | {b["_id"] for b in f.blocks.get(pid, [])}
    return any(x[0] in ("append", "update") and x[1] in ids for x in f.calls)


# ── 1. 이름만 바꾼 편의 제목 ─────────────────────────────────

def test_renamed_portfolio_piece_gets_new_number_in_title(tmp_path):
    w = _world(tmp_path)
    run(w.d.run_one(w.project, src=ds.PORT))
    pid = _pid(w, "portfolio/02_c.md")
    assert w.f.pages[pid]["title"] == "02 셋째"
    w.f.calls.clear()
    # 글은 그대로 이름만 바꾼다. 관리자가 게시 기록 짝을 새 경로로 옮긴 것처럼 행을 옮긴다(펫퍼민트 08_limits → 09_limits)
    _git(w.repo, "mv", "portfolio/02_c.md", "portfolio/03_c.md")
    _git(w.repo, "commit", "-qm", "rename")
    row = w.db.rows.pop((w.project, "portfolio/02_c.md"))
    w.db.rows[(w.project, "portfolio/03_c.md")] = {**row, "path": "portfolio/03_c.md"}
    st = run(ds.status(w.pub, ds.PORT))
    assert st["changed"] == ["portfolio/03_c.md"] and st["titles"]["portfolio/03_c.md"] == "03 셋째"
    # 한 편 게시(펫퍼민트가 쓰는 길)로도 맞는다. 전에는 「바뀌지 않음」으로 끝나 게시기를 부르지 않았다
    r = run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/03_c.md"}))
    assert [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/03_c.md", "retitled")]
    assert w.f.pages[pid]["title"] == "03 셋째" and w.db.rows[(w.project, "portfolio/03_c.md")]["title"] == "03 셋째"
    assert not _wrote(w.f, pid)                                                 # 글은 같아 제목만 바꿨다
    assert run(ds.status(w.pub, ds.PORT))["changed"] == []


def test_keep_title_portfolio_is_not_counted_as_changed(tmp_path):
    w = _world(tmp_path)
    run(w.d.run_one(w.project, src=ds.PORT))
    w.db.rows[(w.project, "portfolio/02_c.md")]["title"] = "사람이 붙인 제목"
    assert run(ds.status(w.pub, ds.PORT))["changed"] == ["portfolio/02_c.md"]
    w.pub.keep_title = True                       # 제목을 건드리지 않는 프로젝트는 제목 차이를 바뀜으로 세지 않는다
    assert run(ds.status(w.pub, ds.PORT))["changed"] == []


# ── 2. 한 편 게시 뒤 다시 잇기와 차례 ─────────────────────────

def test_one_piece_relinks_waiting_piece_and_reorders_its_parent(tmp_path):
    w = _world(tmp_path)
    # 00(「승인 카드」를 가리킴)과 02를 먼저 한 편씩 올린다. 01은 아직 없어 00은 「링크만」으로 남는다
    for p in ("portfolio/00_a.md", "portfolio/02_c.md"):
        run(w.d.run_one(w.project, src=ds.PORT, only={p}))
    assert run(ds.status(w.pub, ds.PORT))["relink"] == ["portfolio/00_a.md"]
    a, c = _pid(w, "portfolio/00_a.md"), _pid(w, "portfolio/02_c.md")
    assert _links(w.f, a) == []
    w.f.calls.clear()
    r = run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/01_b.md"}))
    b = _pid(w, "portfolio/01_b.md")
    assert [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/01_b.md", "created"), ("portfolio/00_a.md", "relinked")]
    assert not r["failed"] and not r["held"]
    assert _links(w.f, a) == [("「승인 카드」", w.db.rows[(w.project, "portfolio/01_b.md")]["url"])]
    assert w.db.rows[(w.project, "portfolio/00_a.md")]["content_hash"]          # 「링크만」이 풀렸다
    assert run(ds.status(w.pub, ds.PORT))["relink"] == []
    assert _wrote(w.f, a) and not _wrote(w.f, c)                                # 기다리지 않던 편은 쓰지 않는다
    # 새 편은 Notion이 부모 끝에 붙인다. 그 부모 아래를 번호 차례로 다시 세운다(페이지를 옮기기만)
    back = [x[1] for x in w.f.calls if x[0] == "move" and x[2] == "port"]
    assert back == [a, b, c]


def test_one_piece_does_not_rewrite_piece_that_waits_for_another(tmp_path):
    w = _world(tmp_path)
    run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/00_a.md"}))       # 「승인 카드」를 기다린다
    w.f.calls.clear()
    r = run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/02_c.md"}))   # 02는 「승인 카드」가 아니다
    assert [d["path"] for d in r["done"]] == ["portfolio/02_c.md"]
    assert not _wrote(w.f, _pid(w, "portfolio/00_a.md"))


def test_one_piece_keep_order_does_not_move(tmp_path):
    w = _world(tmp_path)
    w.pub.keep_order = True
    run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/02_c.md"}))
    run(w.d.run_one(w.project, src=ds.PORT, only={"portfolio/00_a.md"}))
    assert not [x for x in w.f.calls if x[0] == "move"]


def test_api_one_piece_reply_shows_relinked_others(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    w = _world(repo, project="runshoes")
    c = _app(tmp_path, w)
    c.post("/api/publish", json={"project": "runshoes", "path": "portfolio/00_a.md"}, headers=h(RUN))
    r = c.post("/api/publish", json={"project": "runshoes", "path": "portfolio/01_b.md"}, headers=h(RUN))
    j = r.json()
    assert r.status_code == 200 and j["action"] == "created"
    assert [(d["path"], d["action"]) for d in j["others"]["done"]] == [("portfolio/00_a.md", "relinked")]


# ── 3. 프로젝트마다 잠금, 기다림 한도, 요청 간격 ─────────────────

def test_lock_is_per_project_and_busy_after_wait(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _world(tmp_path / "a", project="foreman")
    b = _world(tmp_path / "b", project="runshoes")
    d = ds.DocSync({"foreman": a.pub, "runshoes": b.pub})

    async def go():
        lk = d.lock("foreman")
        await lk.acquire()                         # FOREMAN 큰 맞추기가 도는 중이라 치자
        d.busy["foreman"] = {"what": "기술문서 한꺼번에", "since": 0}
        try:
            r = await asyncio.wait_for(d.run_one("runshoes", src=ds.PORT, only={"portfolio/00_a.md"}, wait=1), 5)
            assert [x["path"] for x in r["done"]] == ["portfolio/00_a.md"]      # 다른 프로젝트는 기다리지 않는다
            try:
                await d.run_one("foreman", src=ds.PORT, only={"portfolio/00_a.md"}, wait=0.05)
            except ds.Busy as e:
                assert e.what == "기술문서 한꺼번에" and "다시 눌러 주세요" in str(e)
            else:
                raise AssertionError("Busy가 나야 한다")
        finally:
            lk.release()
        r = await d.run_one("foreman", src=ds.PORT, only={"portfolio/00_a.md"}, wait=0.05)   # 풀리면 된다
        assert [x["path"] for x in r["done"]] == ["portfolio/00_a.md"] and "foreman" not in d.busy
    run(go())


def test_api_busy_is_409_with_what(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    w = _world(repo, project="runshoes")
    c = _app(tmp_path, w)
    old = ds.API_WAIT_S
    ds.API_WAIT_S = 0.05
    class Held:
        """다른 게시가 잡고 있는 잠금(TestClient는 자기 이벤트 루프에서 돌아 진짜 asyncio.Lock을 밖에서 잡아 둘 수 없다)."""
        def locked(self):
            return True

        async def acquire(self):
            await asyncio.sleep(10)

    w.d.lock = lambda name: Held()
    try:
        w.d.busy["runshoes"] = {"what": "포트폴리오 한꺼번에", "since": 0}
        r = c.post("/api/publish", json={"project": "runshoes", "path": "portfolio/00_a.md"}, headers=h(RUN))
        assert r.status_code == 409 and r.json()["busy"]["what"] == "포트폴리오 한꺼번에" and "다시 눌러 주세요" in r.json()["refused"]
        r = c.post("/api/publish", json={"project": "runshoes", "action": "docsync", "path": "portfolio/"}, headers=h(ADMIN))
        assert r.status_code == 409 and "busy" in r.json()
    finally:
        ds.API_WAIT_S = old
    assert not w.f.calls


def test_notion_client_spaces_requests_across_callers():
    c = nt.NotionClient("x", gap=0.05)
    starts = []

    async def one():
        await c._wait_turn()
        starts.append(asyncio.get_running_loop().time())

    async def go():
        await asyncio.gather(*(one() for _ in range(4)))
        await c.close()
    run(go())
    starts.sort()
    assert all(b - a >= 0.045 for a, b in zip(starts, starts[1:]))


# ── 4. 사람이 Notion에서 지운 페이지 ───────────────────────────

def _deleted_world(tmp_path, archive):
    w = _world(tmp_path)
    w.pub.archive_ok = archive
    run(w.d.run_one(w.project, src=ds.PORT))
    pid = _pid(w, "portfolio/02_c.md")
    _git(w.repo, "rm", "-q", "portfolio/02_c.md")
    _git(w.repo, "commit", "-qm", "rm")
    return w, pid


def test_gone_page_clears_failure_when_archive_off(tmp_path):
    w, pid = _deleted_world(tmp_path, archive=False)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [f["path"] for f in r["failed"]] == ["portfolio/02_c.md"]          # 아직 Notion에 있으면 전처럼 실패(사람이 보고 정한다)
    w.f.pages[pid]["archived"] = True                                         # 사람이 Notion에서 지웠다(휴지통)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert not r["failed"] and [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/02_c.md", "gone")]
    row = w.db.rows[(w.project, "portfolio/02_c.md")]
    assert row["status"] == "archived" and "사람이 지웠습니다" in row["error"]
    assert run(ds.status(w.pub, ds.PORT))["deleted"] == []
    last = run(ds.last_published(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))
    assert last["failed"] == 0
    assert not [x for x in w.f.calls if x[0] == "archive"]                    # Notion에는 쓰지 않았다


def test_gone_page_404_and_archive_on(tmp_path):
    w, pid = _deleted_world(tmp_path, archive=True)
    del w.f.pages[pid]                                                        # 아예 없음(404)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert not r["failed"] and [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/02_c.md", "gone")]


def test_moved_out_of_root_is_not_gone(tmp_path):
    w, pid = _deleted_world(tmp_path, archive=False)
    w.f.pages[pid]["parent"] = "other"                                        # 지우지 않고 범위 밖으로 옮김
    assert run(w.pub.gone("portfolio/02_c.md")) is False
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [f["path"] for f in r["failed"]] == ["portfolio/02_c.md"]


def test_files_fixture_unchanged():
    # 위 시험들은 이 세 편의 참조(00 → 「승인 카드」, 01 → 「한눈에」)에 기대어 있다
    assert set(FILES) == {"portfolio/00_a.md", "portfolio/01_b.md", "portfolio/02_c.md"}
