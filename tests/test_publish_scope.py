"""프로젝트 토큰으로 자기 프로젝트 Notion 게시(11-12) — 진짜 /api/publish 라우터 · 가짜 게시기(Notion · 토큰 없음)."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bridge import scopetoken as st
from bridge.api import publish as pub_api
from test_scopetoken import ADMIN, PET, RUN, _Conn, h


class FakePub:
    def __init__(self, name):
        self.project, self.root, self.docs_mode, self.calls = name, f"root-{name}", "manual", []

    async def publish(self, path, when, force=False):
        self.calls.append(("publish", path, force))
        return {"path": path, "action": "updated"}

    async def list(self):
        return [{"path": f"docs/{self.project}.md"}]

    async def pair(self, path, page_id):
        self.calls.append(("pair", path, page_id))
        return {"path": path, "action": "paired"}


class FakeDocSync:
    """calls에는 한꺼번에 맞추기만 적는다. 한 편 게시(only, 11-20 같은 함수)는 게시기 publish를 불러 게시기 calls에 남는다."""

    def __init__(self, pubs=None):
        self.calls, self.pubs = [], pubs or {}

    def lock(self, name):
        import asyncio
        return asyncio.Lock()

    async def run_one(self, name, force=frozenset(), src=None, only=None, wait=None):
        if only is None:
            self.calls.append((name, set(force)))
            return {"done": [], "held": [], "failed": []}
        done = [await self.pubs[name].publish(p, "지금", force=p in force) for p in sorted(only)]
        return {"done": done, "held": [], "failed": [], "warnings": []}


def _app(tmp_path):
    f = tmp_path / ".env.project_tokens"
    f.write_text(f"FOREMAN_TOKEN_RUNSHOES={RUN}\nFOREMAN_TOKEN_PETMINT_RAG_CHATBOT={PET}\n")
    app = FastAPI()
    app.include_router(pub_api.router)
    app.state.settings = SimpleNamespace(foreman_api_token=SecretStr(ADMIN))
    app.state.store = SimpleNamespace(engine=SimpleNamespace(connect=lambda: _Conn()))
    app.state.token_book = st.TokenBook(st.TokenConfig(enabled=True, file=f))
    app.state.publishers = {n: FakePub(n) for n in ("foreman", "runshoes", "petmint-rag-chatbot")}
    app.state.publisher = app.state.publishers["foreman"]
    app.state.docsync = FakeDocSync(app.state.publishers)
    return TestClient(app), app


def test_project_token_publishes_own_project_only(tmp_path):
    c, app = _app(tmp_path)
    r = c.post("/api/publish", json={"project": "runshoes", "path": "docs/a.md"}, headers=h(RUN))
    assert r.status_code == 200 and r.json()["action"] == "updated"
    assert app.state.publishers["runshoes"].calls == [("publish", "docs/a.md", False)]
    for body in ({"project": "petmint-rag-chatbot", "path": "docs/a.md"}, {"path": "docs/a.md"}):   # 남의 것 · 기본값 foreman
        r = c.post("/api/publish", json=body, headers=h(RUN))
        assert r.status_code == 403 and "이 프로젝트 문서만" in r.json()["detail"]
    assert app.state.publishers["petmint-rag-chatbot"].calls == [] and app.state.publishers["foreman"].calls == []


@pytest.mark.parametrize("extra", [{"force": True}, {"force": "true"}, {"force": 1}, {"action": "docsync"}])
def test_project_token_cannot_force_or_docsync(tmp_path, extra):
    c, app = _app(tmp_path)
    r = c.post("/api/publish", json={"project": "runshoes", "path": "docs/a.md", **extra}, headers=h(RUN))
    assert r.status_code == 403
    assert "force · 한꺼번에 맞추기는 FOREMAN 관리자에게 부탁합니다" in r.json()["detail"]
    assert app.state.publishers["runshoes"].calls == [] and app.state.docsync.calls == []


def test_admin_token_does_everything(tmp_path):
    c, app = _app(tmp_path)
    assert c.post("/api/publish", json={"project": "runshoes", "path": "docs/a.md", "force": True}, headers=h(ADMIN)).status_code == 200
    assert c.post("/api/publish", json={"project": "petmint-rag-chatbot", "path": "docs/b.md"}, headers=h(ADMIN)).status_code == 200
    assert c.post("/api/publish", json={"project": "runshoes", "action": "docsync"}, headers=h(ADMIN)).status_code == 200
    assert app.state.publishers["runshoes"].calls == [("publish", "docs/a.md", True)]
    assert app.state.docsync.calls == [("runshoes", set())]


def test_status_read_by_project(tmp_path):
    c, _ = _app(tmp_path)
    assert c.get("/api/publish", headers=h(ADMIN)).json()["root"] == "root-foreman"        # 없으면 지금처럼 FOREMAN
    assert c.get("/api/publish?project=runshoes", headers=h(ADMIN)).json()["root"] == "root-runshoes"
    assert c.get("/api/publish?project=runshoes", headers=h(RUN)).json()["docs"] == [{"path": "docs/runshoes.md"}]
    assert c.get("/api/publish", headers=h(RUN)).status_code == 403                         # 기본값 foreman
    assert c.get("/api/publish?project=petmint-rag-chatbot", headers=h(RUN)).status_code == 403
    r = c.get("/api/publish?project=없는것", headers=h(ADMIN)).json()
    assert r["enabled"] is False and "없는것" in r["why"]


def test_pair_api_own_project_only(tmp_path):
    c, app = _app(tmp_path)
    body = {"project": "runshoes", "path": "docs/a.md", "page_id": "a" * 32}
    assert c.post("/api/publish/pair", json=body, headers=h(RUN)).json()["action"] == "paired"
    r = c.post("/api/publish/pair", json={**body, "project": "petmint-rag-chatbot"}, headers=h(RUN))
    assert r.status_code == 403 and "이 프로젝트 짝만" in r.json()["detail"]
    assert c.post("/api/publish/pair", json={**body, "project": "petmint-rag-chatbot"}, headers=h(ADMIN)).status_code == 200
    assert app.state.publishers["runshoes"].calls == [("pair", "docs/a.md", "a" * 32)]


def test_status_shows_config_source(tmp_path):
    c, app = _app(tmp_path)
    app.state.notion_cfg = SimpleNamespace(state={"runshoes": {"source": "foreman", "error": None, "warnings": []}})
    r = c.get("/api/publish?project=runshoes", headers=h(RUN)).json()
    assert r["config"]["source"] == "foreman" and r["config"]["docs_mode"] == "manual"


def test_scope_function_directly():
    w = st.why_out_of_scope
    assert asyncio.run(w("runshoes", "POST", "/api/publish", {}, {"project": "runshoes", "force": False}, None, None)) is None
    assert asyncio.run(w("runshoes", "DELETE", "/api/publish", {}, {"project": "runshoes"}, None, None))
