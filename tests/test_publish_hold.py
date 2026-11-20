"""한 쪽 게시가 사람 수정으로 멈출 때도 덮기 줄 · 텔레그램 ✋(11-12) — 가짜 게시기 · 가짜 알림기, Notion 호출 없음."""
import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bridge import docsync as ds
from bridge import notion as nt
from bridge.api import publish as pub_api

TOKEN = "t" * 40
SHA = "a" * 40


class _Notifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda p: None)

    def send_direct(self, project, kind, sid, msg):
        self.sent.append((project, kind, msg))


class _Pub:
    def __init__(self, name="infra", mode="manual"):
        self.project, self.docs_mode, self.repo, self.ref, self.docs_page = name, mode, "/repo", "origin/main", None
        self.held, self.calls, self.saved = {"docs/09.md"}, [], []

    async def publish(self, path, when, force=False, title=None, relink=True):
        self.calls.append((path, force))
        if path in self.held and not force:
            raise nt.HumanEdited(path, ["사람이 고침 1", "사람이 고침 2"], "https://notion/x")
        self.held.discard(path)
        return {"path": path, "action": "updated"}

    async def _save(self, path, **kw):
        self.saved.append(path)


def _setup(monkeypatch, sha=SHA, mode="manual"):
    state = {"sha": sha}
    monkeypatch.setattr(ds, "ref_sha", lambda repo, ref: state["sha"])

    async def fake_status(pub, src=None):
        return {"project": pub.project, "files": ["docs/09.md"], "new": [], "changed": ["docs/09.md"], "deleted": [], "broken": [],
                "ref_sha": state["sha"], "synced": None, "behind_commits": None, "last_commit_at": None, "mode": mode, "ref": "origin/main"}
    monkeypatch.setattr(ds, "status", fake_status)
    pub, n = _Pub(mode=mode), _Notifier()
    dsync = ds.DocSync({"infra": pub}, n)
    app = FastAPI()
    app.include_router(pub_api.router)
    app.state.settings = SimpleNamespace(foreman_api_token=SecretStr(TOKEN))
    app.state.publishers, app.state.docsync, app.state.notifier = {"infra": pub}, dsync, n
    return TestClient(app), pub, dsync, n, state


def _post(c, **body):
    return c.post("/api/publish", json={"project": "infra", "path": "docs/09.md", **body}, headers={"Authorization": f"Bearer {TOKEN}"})


def _todo(dsync, pub):
    return asyncio.run(ds.todo_items(pub, dsync.last.get("infra")))


def _forces(items):
    return [x for x in items if x["act"] == "force"]


def test_one_sided_hold_leaves_force_line_and_one_alert(monkeypatch):
    c, pub, dsync, n, _ = _setup(monkeypatch)
    for _i in range(2):                                  # 두 번 눌러도 알림은 한 번, 줄도 하나
        r = _post(c, action="publish")
        assert r.status_code == 409 and "사람이" in r.json()["refused"]
    f = _forces(_todo(dsync, pub))
    assert len(f) == 1 and f[0]["path"] == "docs/09.md" and "2개" in f[0]["title"]
    assert len(n.sent) == 1 and "✋" in n.sent[0][2] and "docs/09.md" in n.sent[0][2] and n.sent[0][1] == "docsync"


def test_force_clears_line(monkeypatch):
    """단추(서기실: action=docsync force) → 덮이고 줄이 사라진다. 한 쪽 force 게시도 줄을 치운다."""
    c, pub, dsync, n, _ = _setup(monkeypatch)
    _post(c, action="publish")
    assert len(_forces(_todo(dsync, pub))) == 1
    r = _post(c, action="docsync", force=True)
    assert r.status_code == 200 and ("docs/09.md", True) in pub.calls
    assert dsync.last["infra"]["held"] == []
    # 한 쪽 성공도 치운다
    pub.held = {"docs/09.md"}
    _post(c, action="publish")
    assert len(dsync.last["infra"]["held"]) == 1
    assert _post(c, action="publish", force=True).status_code == 200
    assert dsync.last["infra"]["held"] == []


def test_git_moves_on_line_stays_until_next_publish(monkeypatch):
    """11-20 한 편 게시도 묶음 게시와 같은 함수라 멈춤 줄이 git 커밋에 묶이지 않는다. git이 다시 바뀌어도 그 편이 아직 바뀜이면
    덮기 단추가 남고(페이지는 여전히 사람이 고친 채다), 다음 게시가 풀거나 다시 멈춘다. 전에는 한 쪽 게시 줄만 사라졌다."""
    c, pub, dsync, n, state = _setup(monkeypatch)
    _post(c, action="publish")
    state["sha"] = "b" * 40                              # git이 다시 바뀜
    assert len(_forces(_todo(dsync, pub))) == 1


def test_docsync_route_still_works_and_no_duplicate(monkeypatch):
    """[지금 맞추기]로 멈춘 줄은 전처럼 뜨고, 한 쪽 게시와 섞여도 같은 파일에 줄이 둘 생기지 않는다."""
    c, pub, dsync, n, _ = _setup(monkeypatch)
    r = _post(c, action="docsync")
    assert r.status_code == 200 and len(r.json()["held"]) == 1
    assert len(_forces(_todo(dsync, pub))) == 1 and len(n.sent) == 1
    _post(c, action="publish")                           # 한 쪽도 멈춤 — 같은 파일 · 같은 커밋이라 알림 없음, 줄 하나
    assert len(_forces(_todo(dsync, pub))) == 1 and len(n.sent) == 1
    assert len(dsync.last["infra"]["held"]) == 1


def test_no_hold_means_nothing_changes(monkeypatch):
    c, pub, dsync, n, _ = _setup(monkeypatch)
    pub.held = set()
    r = _post(c, action="publish")
    assert r.status_code == 200 and r.json()["action"] == "updated"
    assert dsync.last["infra"]["held"] == [] and n.sent == [] and _forces(_todo(dsync, pub)) == []


def test_docs_off_or_non_docs_path_leaves_nothing(monkeypatch):
    c, pub, dsync, n, _ = _setup(monkeypatch)
    pub.held.add("portfolio/x.md")
    assert _post(c, action="publish", path="portfolio/x.md").status_code == 409
    pub.docs_mode = "off"
    assert _post(c, action="publish").status_code == 409
    assert dsync.last == {} and n.sent == []
