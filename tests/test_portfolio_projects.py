"""포트폴리오 게시를 프로젝트별로(11-17 사용자). 가짜 저장소 둘(FOREMAN, 인프라)과 portfolio/ 없는 저장소 하나, 가짜 Notion 나무 하나,
같은 doc_publish 표 하나. 한 프로젝트 게시가 다른 프로젝트 페이지를 건드리지 않는지, 자리가 없는 프로젝트는 아무 데도 올리지 않는지 본다."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bridge import notion as nt
from bridge import scopetoken as st
from bridge.api import publish as pub_api
from test_notion import FakeNotion
from test_scopetoken import ADMIN, h
from test_techdoc import FakeDB, _commit, _git


def _repo(path, files):
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _commit(path, files, "init")
    return path


def _tree():
    """프로젝트 > FOREMAN 루트 > [포트폴리오], 프로젝트 > 인프라 루트 > [포트폴리오], 프로젝트 > 새 프로젝트 루트(자리 없음)."""
    f = FakeNotion(see_all=True)
    f.pages["port"] = {"parent": "root", "title": "[포트폴리오]", "archived": False}
    f.pages["iroot"] = {"parent": "proj", "title": "인프라", "archived": False}
    f.pages["iport"] = {"parent": "iroot", "title": "[포트폴리오]", "archived": False}
    f.pages["nroot"] = {"parent": "proj", "title": "새 프로젝트", "archived": False}
    return f


@pytest.fixture
def world(tmp_path):
    fr = _repo(tmp_path / "foreman", {"portfolio/01_a.md": "# FOREMAN 글\n\n본문입니다.\n"})
    ir = _repo(tmp_path / "infra", {"portfolio/01_x.md": "# 인프라 글\n\n본문입니다.\n", "portfolio/02_y.md": "# 인프라 둘\n\n둘.\n"})
    nr = _repo(tmp_path / "plain", {"docs/a.md": "# 문서\n"})
    db, f = FakeDB(), _tree()
    pubs = {
        "foreman": nt.Publisher(db, f, "root", str(fr), project="foreman", ref="HEAD", portfolio_page="port"),
        "ronanlab-infra": nt.Publisher(db, f, "iroot", str(ir), project="ronanlab-infra", ref="HEAD", portfolio_page="iport"),
        "plain": nt.Publisher(db, f, "nroot", str(nr), project="plain", ref="HEAD"),        # portfolio_page 없음
    }
    return SimpleNamespace(db=db, f=f, pubs=pubs, fr=fr, ir=ir, nr=nr)


def run(c):
    return asyncio.run(c)


def test_each_project_publishes_under_its_own_portfolio_page(world):
    w = world
    a = run(w.pubs["foreman"].publish("portfolio/01_a.md", "t"))
    x = run(w.pubs["ronanlab-infra"].publish("portfolio/01_x.md", "t"))
    assert a["action"] == x["action"] == "created"
    assert w.f.pages[a["page_id"]]["parent"] == "port" and w.f.pages[x["page_id"]]["parent"] == "iport"
    assert set(w.db.rows) == {("foreman", "portfolio/01_a.md"), ("ronanlab-infra", "portfolio/01_x.md")}
    before = list(w.f.blocks[a["page_id"]])
    # 인프라 글을 고쳐 다시 올려도 FOREMAN 페이지 블록과 제목은 그대로
    _commit(w.ir, {"portfolio/01_x.md": "# 인프라 글\n\n고친 본문입니다.\n"}, "edit")
    assert run(w.pubs["ronanlab-infra"].publish("portfolio/01_x.md", "t"))["action"] == "updated"
    assert w.f.blocks[a["page_id"]] == before and w.f.pages[a["page_id"]]["title"].endswith("FOREMAN 글")
    # 같은 경로라도 프로젝트가 다르면 다른 기록(FOREMAN 목록에 인프라 글이 섞이지 않는다)
    assert [d["path"] for d in run(w.pubs["foreman"].list())] == ["portfolio/01_a.md"]
    assert [d["path"] for d in run(w.pubs["ronanlab-infra"].list())] == ["portfolio/01_x.md", "portfolio/02_y.md"]


def test_scope_refuses_other_projects_page(world):
    """인프라 게시기의 기록이 FOREMAN 페이지를 가리켜도(잘못 짝지음) FOREMAN 페이지를 덮지 않는다(Scope)."""
    w = world
    a = run(w.pubs["foreman"].publish("portfolio/01_a.md", "t"))
    before = list(w.f.blocks[a["page_id"]])
    w.db.rows[("ronanlab-infra", "portfolio/01_x.md")] = {
        "project": "ronanlab-infra", "path": "portfolio/01_x.md", "kind": "doc", "status": "published", "notion_page_id": a["page_id"],
        "parent_page_id": "port", "title": "x", "content_hash": "old", "commit_sha": None, "url": "u", "updated_at": None}
    r = run(w.pubs["ronanlab-infra"].publish("portfolio/01_x.md", "t"))
    assert r["action"] == "created" and w.f.pages[r["page_id"]]["parent"] == "iport"     # 범위 밖이라 새로 만든다
    assert w.f.blocks[a["page_id"]] == before and not w.f.pages[a["page_id"]]["archived"]
    with pytest.raises(nt.OutOfScope):
        run(w.pubs["ronanlab-infra"].pair("portfolio/02_y.md", a["page_id"]))


def test_prune_and_reorder_touch_only_own_project(world):
    w = world
    a = run(w.pubs["foreman"].publish("portfolio/01_a.md", "t"))
    x = run(w.pubs["ronanlab-infra"].publish("portfolio/01_x.md", "t"))
    y = run(w.pubs["ronanlab-infra"].publish("portfolio/02_y.md", "t"))
    _commit(w.fr, {"portfolio/01_a.md": None, "portfolio/02_b.md": "# 새 글\n"}, "rename")   # FOREMAN 쪽에도 원본 없는 페이지를 만든다
    _commit(w.ir, {"portfolio/02_y.md": None}, "drop")
    r = run(w.pubs["ronanlab-infra"].prune_portfolio())
    assert r["done"] == ["portfolio/02_y.md"] and w.f.pages[y["page_id"]]["archived"]
    assert not w.f.pages[a["page_id"]]["archived"] and not w.f.pages[x["page_id"]]["archived"]
    assert w.db.rows[("foreman", "portfolio/01_a.md")]["status"] == "published"
    moves = len([c for c in w.f.calls if c[0] == "move"])
    r = run(w.pubs["ronanlab-infra"].reorder_portfolio())
    assert r["order"] == ["portfolio/01_x.md"] and w.f.pages[x["page_id"]]["parent"] == "iport"
    assert w.f.pages[a["page_id"]]["parent"] == "port"
    moved = [c[1] for c in w.f.calls[moves:] if c[0] == "move"]
    assert x["page_id"] in moved and a["page_id"] not in moved


def test_no_place_refuses_and_writes_nothing(world):
    """자리(portfolio_page)가 없는 프로젝트는 루트 아래로 조용히 떨어지지 않고 거절한다(11-17, 전에는 root 아래로)."""
    w = world
    _commit(w.nr, {"portfolio/01_p.md": "# 글\n"}, "add")
    n = len(w.f.pages)
    with pytest.raises(nt.OutOfScope, match="포트폴리오 Notion 자리가 정해지지 않았습니다"):
        run(w.pubs["plain"].publish("portfolio/01_p.md", "t"))
    with pytest.raises(nt.OutOfScope, match="자리가 정해지지 않았습니다"):
        run(w.pubs["plain"].reorder_portfolio())
    assert len(w.f.pages) == n and not [c for c in w.f.calls if c[0] == "create"] and ("plain", "portfolio/01_p.md") not in w.db.rows
    assert w.pubs["plain"].portfolio_state()["place"] is False


def test_portfolio_state_has_dir(world):
    w = world
    assert w.pubs["ronanlab-infra"].portfolio_state() | {"place_why": None} == {"has_dir": True, "place": True, "ref": "HEAD", "place_why": None}
    s = w.pubs["plain"].portfolio_state()
    assert s["has_dir"] is False and s["place"] is False and "Notion 자리가 정해지지 않았습니다" in s["place_why"]
    assert run(w.pubs["plain"].list()) == []
    # 원본 커밋을 못 읽으면 「없음」이 아니라 None, 목록은 오류로(빈 목록으로 삼키지 않는다)
    bad = nt.Publisher(w.db, w.f, "iroot", str(w.ir), project="ronanlab-infra", ref="origin/main", portfolio_page="iport")
    assert bad.portfolio_state()["has_dir"] is None
    with pytest.raises(OSError):
        run(bad.list())


def test_list_reads_ref_not_worktree(world):
    """목록은 게시가 읽는 판(ref)과 같게 센다. 커밋 안 된 작업 폴더 파일은 목록에 없다."""
    w = world
    (w.ir / "portfolio" / "03_wip.md").write_text("# 쓰는 중\n", encoding="utf-8")
    _git(w.ir, "add", "portfolio/03_wip.md")          # 색인에만 있다(ls-files는 잡았다)
    assert "portfolio/03_wip.md" not in [d["path"] for d in run(w.pubs["ronanlab-infra"].list())]


# ── /api/publish(진짜 라우터, 진짜 게시기) ─────────────────────────────

def _app(tmp_path, pubs):
    f = tmp_path / ".env.project_tokens"
    f.write_text("")
    app = FastAPI()
    app.include_router(pub_api.router)
    app.state.settings = SimpleNamespace(foreman_api_token=SecretStr(ADMIN))
    app.state.token_book = st.TokenBook(st.TokenConfig(enabled=False, file=f))
    app.state.publishers = pubs
    app.state.publisher = pubs["foreman"]
    return TestClient(app)


def test_api_get_and_post_by_project(tmp_path, world):
    w = world
    c = _app(tmp_path, w.pubs)
    r = c.get("/api/publish?project=ronanlab-infra", headers=h(ADMIN)).json()
    assert r["portfolio"]["has_dir"] is True and [d["path"] for d in r["docs"]] == ["portfolio/01_x.md", "portfolio/02_y.md"]
    r = c.get("/api/publish?project=plain", headers=h(ADMIN)).json()
    assert r["enabled"] and r["portfolio"]["has_dir"] is False and r["portfolio"]["place"] is False and r["docs"] == []
    r = c.get("/api/publish?project=foreman", headers=h(ADMIN)).json()
    assert [d["path"] for d in r["docs"]] == ["portfolio/01_a.md"] and r["portfolio"]["place"] is True
    r = c.post("/api/publish", json={"project": "ronanlab-infra", "path": "portfolio/01_x.md"}, headers=h(ADMIN))
    assert r.status_code == 200 and w.f.pages[r.json()["page_id"]]["parent"] == "iport"
    assert ("foreman", "portfolio/01_x.md") not in w.db.rows
    _commit(w.nr, {"portfolio/01_p.md": "# 글\n"}, "add")
    r = c.post("/api/publish", json={"project": "plain", "path": "portfolio/01_p.md"}, headers=h(ADMIN))
    assert r.status_code == 409 and "Notion 자리가 정해지지 않았습니다" in r.json()["refused"]
    r = c.post("/api/publish", json={"project": "plain", "path": "portfolio/", "action": "reorder"}, headers=h(ADMIN))
    assert r.status_code == 409 and "자리가 정해지지 않았습니다" in r.json()["refused"]
