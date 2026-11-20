"""포트폴리오 게시를 기술문서와 같은 함수로(11-20 사용자 결정). 진짜 git 저장소, 가짜 Notion, 메모리 게시 기록, 진짜 DocSync와
/api/publish. 바뀐 편만 올라가는지, 사람이 고친 편은 멈추고 덮기 줄이 포트폴리오 칸으로 가는지, 실패가 기술문서와 같은 자리
(마지막 결과 행, 서기 할 일, 텔레그램)에 남는지, 프로젝트 토큰은 한꺼번에 올리기를 못 하는지 본다. 실제 Notion에는 올리지 않는다."""
import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bridge import docsync as ds
from bridge import notion as nt
from bridge import scopetoken as st
from bridge.api import publish as pub_api
from test_publish_hold import _Notifier
from test_scopetoken import ADMIN, RUN, _Conn, h
from test_techdoc import FakeDB, _commit, _fake_notion, _git

FILES = {"portfolio/00_a.md": "# 한눈에\n\n자세한 것은 → 「승인 카드」.\n",
         "portfolio/01_b.md": "# 승인 카드\n\n처음으로 → 「한눈에」.\n",
         "portfolio/02_c.md": "# 셋째\n\n본문입니다.\n"}


def run(c):
    return asyncio.run(c)


def _world(tmp_path, project="foreman"):
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, FILES, "init")
    db, f = FakeDB(), _fake_notion()
    pub = nt.Publisher(db, f, "root", str(tmp_path), project=project, ref="HEAD", docs_page="docs", portfolio_page="port",
                       docs_mode="manual", opts={"src": "notion/", "title": "h1", "header": "footer"})
    pub._me_id = "bot"                                  # 사람 수정 검사를 켠다(가짜 Notion은 /users/me가 없다)
    n = _Notifier()
    return SimpleNamespace(repo=tmp_path, db=db, f=f, pub=pub, n=n, d=ds.DocSync({project: pub}, n), project=project)


def _pid(w, path):
    return w.db.rows[(w.project, path)]["notion_page_id"]


def _links(f, pid):
    out = []
    for b in f.blocks.get(pid, []):
        for t in (b.get(b["type"]) or {}).get("rich_text") or []:
            if (t["text"].get("link") or {}).get("url"):
                out.append((t["text"]["content"], t["text"]["link"]["url"]))
    return out


def test_one_press_uploads_all_then_only_changed(tmp_path):
    w = _world(tmp_path)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [(d["path"], d["action"]) for d in r["done"]] == [(p, "created") for p in FILES] and not r["failed"] and not r["warnings"]
    a, b = _pid(w, "portfolio/00_a.md"), _pid(w, "portfolio/01_b.md")
    assert _links(w.f, a) == [("「승인 카드」", w.db.rows[(w.project, "portfolio/01_b.md")]["url"])]   # 첫 게시에서 서로 걸렸다
    assert _links(w.f, b) == [("「한눈에」", w.db.rows[(w.project, "portfolio/00_a.md")]["url"])]
    assert all(w.db.rows[(w.project, p)]["content_hash"] for p in FILES)
    appends = [c[1] for c in w.f.calls if c[0] == "append"]
    assert sorted(appends) == sorted(_pid(w, p) for p in FILES)                 # 한 요청 안에서 페이지마다 한 번
    assert w.f.pages[a]["parent"] == "port" and w.f.pages[a]["title"] == "00 한눈에"
    assert w.db.rows[(w.project, ds.PORT_MARK)]["commit_sha"] and (w.project, ds.MARK) not in w.db.rows   # 포트폴리오 행만
    assert run(w.d.run_one(w.project, src=ds.PORT))["done"] == []              # 바뀐 것이 없으면 아무것도 쓰지 않는다
    _commit(w.repo, {"portfolio/02_c.md": "# 셋째\n\n고친 본문입니다.\n"}, "edit")
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/02_c.md", "updated")]
    assert f"{w.project}#{ds.PORT}" in w.d.last and w.project not in w.d.last  # 기술문서 결과와 섞이지 않는다
    s = run(ds.summary(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))
    assert s["total"] == 3 and s["published"] == 3 and s["changed"] == 0 and s["last"]["done"] >= 1


def test_human_edit_holds_and_force_line_goes_to_portfolio(tmp_path):
    w = _world(tmp_path)
    run(w.d.run_one(w.project, src=ds.PORT))
    b = _pid(w, "portfolio/01_b.md")
    blk = next(x for x in w.f.blocks[b] if x["type"] == "paragraph")
    blk["paragraph"] = {"rich_text": [{"type": "text", "text": {"content": "사람이 Notion에서 고친 문단"}}]}
    blk["last_edited_by"] = {"object": "user", "id": "human"}
    _commit(w.repo, {"portfolio/01_b.md": "# 승인 카드\n\n처음으로 → 「한눈에」. 더한 줄.\n",
                     "portfolio/02_c.md": "# 셋째\n\n고친 본문입니다.\n"}, "edit")
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [h_["path"] for h_ in r["held"]] == ["portfolio/01_b.md"] and [d["path"] for d in r["done"]] == ["portfolio/02_c.md"]
    assert not r["failed"] and (w.project, ds.PORT_MARK) in w.db.rows
    # 텔레그램 ✋: 기술문서와 같은 꼴, 묶음 이름과 단추 자리만 포트폴리오
    msg = [m for _, k, m in w.n.sent if "✋" in m]
    assert len(msg) == 1 and "Notion 포트폴리오" in msg[0] and "「포트폴리오 게시」" in msg[0] and "portfolio/01_b.md" in msg[0]
    # 서기 할 일: 덮기 줄은 src가 portfolio/(화면이 포트폴리오 칸에 단다), 뒤처짐 한 줄도 포트폴리오
    items = run(ds.todo_items(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))
    force = [x for x in items if x["act"] == "force"]
    assert len(force) == 1 and force[0]["src"] == ds.PORT and force[0]["path"] == "portfolio/01_b.md"
    assert any(x["act"] == "docsync" and x["title"].startswith("Notion 포트폴리오") for x in items)
    assert w.db.rows[(w.project, ds.HELD_PRE + "portfolio/01_b.md")]["status"] == "held"
    # 브리지를 다시 띄워도 덮기 줄이 남고, 기술문서 쪽 목록에는 섞이지 않는다
    d2 = ds.DocSync({w.project: w.pub})
    last, err = run(d2.last_for(w.project, ds.PORT))
    assert err is None and [x["path"] for x in last["held"]] == ["portfolio/01_b.md"]
    assert run(d2.last_for(w.project)) == (None, None)
    assert run(ds.last_published(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))["held"] == 1    # 「마지막으로 올림」 멈춤 1
    # 덮기(그 편만 force): 풀리고 DB 행도 released
    r = run(d2.run_one(w.project, {"portfolio/01_b.md"}, src=ds.PORT))
    assert r["held"] == [] and [d["path"] for d in r["done"]] == ["portfolio/01_b.md"]
    assert w.db.rows[(w.project, ds.HELD_PRE + "portfolio/01_b.md")]["status"] == "released"


def test_failure_is_reported_like_techdoc_and_leaves_no_orphan_page(tmp_path, monkeypatch):
    w = _world(tmp_path)
    orig = w.f.append

    async def broken_append(bid, children, after=None):
        if w.f.pages.get(bid, {}).get("title") == "02 셋째":
            raise nt.NotionError(400, "Can't edit block that is archived")
        return await orig(bid, children, after)
    monkeypatch.setattr(w.f, "append", broken_append)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [f["path"] for f in r["failed"]] == ["portfolio/02_c.md"] and r["failed"][0]["kind"] == "notion"
    assert len(r["done"]) == 2
    # 짝 없는 페이지가 남지 않는다: 빈 페이지와 짝이 남고 「바뀜」으로 보인다
    row = w.db.rows[(w.project, "portfolio/02_c.md")]
    assert row["notion_page_id"] and row["content_hash"] is None and row["commit_sha"] is None
    st_ = run(ds.status(w.pub, ds.PORT))
    assert st_["changed"] == ["portfolio/02_c.md"] and st_["relink"] == []      # 링크만이 아니라 다시 올려야 하는 편
    assert len([p for p, x in w.f.pages.items() if x["title"] == "02 셋째"]) == 1
    # 같은 자리에 알린다: 텔레그램 ⚠, 마지막 결과 행, 서기 할 일의 까닭, 맞춘 커밋 행은 옮기지 않음
    assert any("⚠ Notion 포트폴리오 게시 실패 1개" in m and "portfolio/02_c.md" in m for _, _, m in w.n.sent)
    assert w.db.rows[(w.project, ds.PORT_LAST)]["error"].startswith("portfolio/02_c.md")      # 마지막 결과 행(다시 띄워도 남는다)
    last = run(ds.last_published(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))
    assert last["failed"] == 1 and last["failed_first"].startswith("portfolio/02_c.md")
    items = run(ds.todo_items(w.pub, w.d.last[f"{w.project}#{ds.PORT}"], ds.PORT))
    assert items[0]["why"].startswith("게시 실패, portfolio/02_c.md")
    assert (w.project, ds.PORT_MARK) not in w.db.rows
    # 다음 누름에서 같은 페이지에 채운다(새로 만들지 않는다)
    monkeypatch.setattr(w.f, "append", orig)
    r = run(w.d.run_one(w.project, src=ds.PORT))
    assert [(d["path"], d["action"]) for d in r["done"]] == [("portfolio/02_c.md", "updated")]
    assert len([p for p, x in w.f.pages.items() if x["title"] == "02 셋째"]) == 1


def _app(tmp_path, w):
    f = tmp_path / ".env.project_tokens"
    f.write_text(f"FOREMAN_TOKEN_RUNSHOES={RUN}\n")
    app = FastAPI()
    app.include_router(pub_api.router)
    app.state.settings = SimpleNamespace(foreman_api_token=SecretStr(ADMIN))
    app.state.store = SimpleNamespace(engine=SimpleNamespace(connect=lambda: _Conn()))
    app.state.token_book = st.TokenBook(st.TokenConfig(enabled=True, file=f))
    app.state.publishers = {w.project: w.pub}
    app.state.docsync, app.state.notifier = w.d, w.n
    return TestClient(app)


def test_api_project_token_cannot_sync_portfolio_but_one_piece_goes_same_way(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    w = _world(repo, project="runshoes")
    c = _app(tmp_path, w)
    for body in ({"action": "docsync", "path": "portfolio/"}, {"path": "portfolio/00_a.md", "force": True}):
        r = c.post("/api/publish", json={"project": "runshoes", **body}, headers=h(RUN))
        assert r.status_code == 403 and "FOREMAN 관리자에게 부탁합니다" in r.json()["detail"]
    assert not w.f.calls
    # 한 편 게시는 프로젝트 토큰도 된다. 묶음과 같은 함수로 가서 결과가 포트폴리오 마지막 결과에 남는다
    r = c.post("/api/publish", json={"project": "runshoes", "path": "portfolio/00_a.md"}, headers=h(RUN))
    assert r.status_code == 200 and r.json()["action"] == "created" and w.f.pages[r.json()["page_id"]]["parent"] == "port"
    assert "가리킨 편이 아직 Notion에 없어" in r.json()["warnings"][-1]          # 한 편만 올려 링크를 못 걸었다(경고로 보인다)
    assert [d["path"] for d in w.d.last["runshoes#portfolio/"]["done"]] == ["portfolio/00_a.md"]
    lst = {d["path"]: d for d in run(w.pub.list())}
    assert lst["portfolio/00_a.md"]["relink"] and lst["portfolio/00_a.md"]["changed"]   # 화면 「링크를 다시 걸어야 함」
    # 관리 토큰의 [Notion에 올리기] 한 번이 나머지를 올리고 링크를 건다. 휴지통으로 보낸 것도 done에
    r = c.post("/api/publish", json={"project": "runshoes", "action": "docsync", "path": "portfolio/"}, headers=h(ADMIN))
    j = r.json()
    assert r.status_code == 200 and j["src"] == ds.PORT and not j["failed"]
    assert sorted(d["path"] for d in j["done"]) == sorted(FILES)
    assert not run(w.pub.list())[0]["relink"]
