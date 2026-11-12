"""프로젝트 토큰 범위(11-11, bridge/scopetoken.py · bridge/api/auth.py) — DB 없이 가짜 엔진으로."""

import asyncio
import os
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bridge import scopetoken as st
from bridge.api.auth import require_api_token

ADMIN = "a" * 40
RUN = "r" * 40
PET = "p" * 40
SESS = {1: "foreman", 2: "runshoes"}
REPOS = {"foreman": "/home/x/foreman", "runshoes": "/home/x/runshoes"}


class _Res:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Conn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, sql, params=None):
        q = str(sql)
        if "SELECT name FROM project" in q:
            return _Res([(n,) for n in ["foreman", "runshoes", "petmint-rag-chatbot"]])
        if "FROM character_session" in q:
            p = SESS.get(params["s"])
            return _Res([(p,)] if p else [])
        if "repo_path FROM project" in q:
            r = REPOS.get(params["n"])
            return _Res([(r,)] if r else [])
        raise AssertionError(q)


def _app(tmp_path, enabled=True):
    f = tmp_path / ".env.project_tokens"
    f.write_text(f"FOREMAN_TOKEN_RUNSHOES={RUN}\nFOREMAN_TOKEN_PETMINT_RAG_CHATBOT={PET}\nFOREMAN_TOKEN_SHORT=abc\n")
    app = FastAPI(dependencies=[Depends(require_api_token)])
    app.state.settings = SimpleNamespace(foreman_api_token=SecretStr(ADMIN))
    app.state.store = SimpleNamespace(engine=SimpleNamespace(connect=lambda: _Conn()))
    app.state.token_book = st.TokenBook(st.TokenConfig(enabled=enabled, file=f))

    from fastapi import Request

    @app.get("/api/sessions/{sid}/conversation")
    def conv(sid: int, request: Request):
        return {"scope": request.state.token_scope}

    @app.post("/api/spawn")
    def spawn(body: dict):
        return {"ok": True}

    @app.post("/api/foreman/plan")
    def plan(body: dict):
        return {"ok": True}

    @app.get("/api/dashboard")
    def dash():
        return {"ok": True}
    return TestClient(app)


def h(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_token_opens_everything(tmp_path):
    c = _app(tmp_path)
    assert c.get("/api/dashboard", headers=h(ADMIN)).status_code == 200
    assert c.get("/api/sessions/1/conversation", headers=h(ADMIN)).json() == {"scope": None}
    assert c.get("/api/dashboard").status_code == 401
    assert c.get("/api/dashboard", headers=h("x" * 40)).status_code == 401


def test_project_token_only_own_project(tmp_path):
    c = _app(tmp_path)
    assert c.get("/api/sessions/2/conversation", headers=h(RUN)).json() == {"scope": "runshoes"}
    r = c.get("/api/sessions/1/conversation", headers=h(RUN))
    assert r.status_code == 403 and "다른 프로젝트(foreman)" in r.json()["detail"]
    r = c.get("/api/dashboard", headers=h(RUN))
    assert r.status_code == 403 and "관리 토큰" in r.json()["detail"]
    # 띄우기 — 그 저장소 · worktree 안만
    assert c.post("/api/spawn", json={"cwd": "/home/x/runshoes/.worktrees/a"}, headers=h(RUN)).status_code == 200
    r = c.post("/api/spawn", json={"cwd": "/home/x/foreman"}, headers=h(RUN))
    assert r.status_code == 403 and "/home/x/foreman" in r.json()["detail"]
    assert c.post("/api/spawn", json={"cwd": "/home/x/runshoes-evil"}, headers=h(RUN)).status_code == 403
    # 교장 계획 — 그 프로젝트만
    assert c.post("/api/foreman/plan", json={"text": "x", "project": "runshoes"}, headers=h(RUN)).status_code == 200
    assert c.post("/api/foreman/plan", json={"text": "x", "project": "foreman"}, headers=h(RUN)).status_code == 403
    # 펫퍼민트 토큰은 런슈즈 세션에 못 닿는다
    assert c.get("/api/sessions/2/conversation", headers=h(PET)).status_code == 403


def test_off_means_project_tokens_401(tmp_path):
    c = _app(tmp_path, enabled=False)
    assert c.get("/api/sessions/2/conversation", headers=h(RUN)).status_code == 401
    assert c.get("/api/dashboard", headers=h(ADMIN)).status_code == 200


def test_short_token_dropped_and_reported(tmp_path):
    f = tmp_path / "t"
    f.write_text("FOREMAN_TOKEN_SHORT=abc\n")
    b = st.TokenBook(st.TokenConfig(enabled=True, file=f))
    assert b.project_of("abc", ["short"]) is None
    assert "FOREMAN_TOKEN_SHORT" in (b.error or "")


def test_cli_writes_without_printing_value(tmp_path, capsys):
    f = tmp_path / ".env.project_tokens"
    k = st.write_token("petmint-rag-chatbot", f)
    k2 = st.write_token("petmint-rag-chatbot", f)       # 다시 만들면 바꾼다(줄 하나)
    assert k == k2 == "FOREMAN_TOKEN_PETMINT_RAG_CHATBOT"
    lines = f.read_text().splitlines()
    assert len(lines) == 1 and len(lines[0].split("=", 1)[1]) >= 32
    assert oct(os.stat(f).st_mode & 0o777) == "0o600"


def test_config_load(tmp_path):
    p = tmp_path / "tokens.toml"
    p.write_text('[project_tokens]\nenabled = true\nfile = "/x/y"\n')
    c = st.TokenConfig.load(p)
    assert c.enabled and str(c.file) == "/x/y"
    p.write_text("[[[")
    assert st.TokenConfig.load(p).error
    assert st.TokenConfig.load(tmp_path / "none.toml").enabled is False


def test_in_repo():
    assert st.in_repo("/home/x/runshoes", "/home/x/runshoes")
    assert not st.in_repo("/home/x/runshoes2", "/home/x/runshoes")
    assert asyncio.run(st.why_out_of_scope("runshoes", "GET", "/api/managers", {}, None, None, None)) is None


@pytest.mark.parametrize("path", ["/api/foreman/state", "/api/foreman/merge-order", "/api/merge-prep"])
def test_foreman_query(path):
    ok = asyncio.run(st.why_out_of_scope("runshoes", "GET", path, {"project": "runshoes"}, None, None, None))
    bad = asyncio.run(st.why_out_of_scope("runshoes", "GET", path, {"project": "foreman"}, None, None, None))
    assert ok is None and bad


def test_merge_prep_list_own_project_only():
    """11-12 — 관리자(프로젝트 토큰)가 자기 프로젝트 합치기 카드만 모아 본다. ?project= 없거나 남의 것은 403."""
    run = lambda q: asyncio.run(st.why_out_of_scope("runshoes", "GET", "/api/merge-prep", q, None, None, None))  # noqa: E731
    assert run({"project": "runshoes"}) is None
    assert run({}) and run({"project": "foreman"})
    assert asyncio.run(st.why_out_of_scope("runshoes", "POST", "/api/merge-prep", {"project": "runshoes"}, None, None, None))
