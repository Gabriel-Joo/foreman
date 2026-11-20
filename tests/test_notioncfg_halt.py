"""저장소 게시 설정을 잃으면 알리고 게시를 멈춘다(11-12 사용자 지시) — 진짜 git(tmp) · 가짜 알림기 · 가짜 게시기, Notion 호출 없음."""
import asyncio
import json

from bridge import docsync as ds
from bridge import notioncfg as nc
from test_notioncfg import BASE, _git, _new_publisher, _Notifier, _repo
from test_publish_scope import ADMIN, RUN, _app, h

INFRA = "ronanlab-infra"
CFG = 'docs = "auto"\nquiet_min = 5\ncreate = true\narchive = true\n'


def _cfg(tmp_path, sent, base=BASE):
    return nc.NotionConfig(base, _Notifier(sent), memory=tmp_path / "run" / nc.MEMORY_FILE)


def _rm_file(repo_dir):
    _git(repo_dir, "rm", "-q", ".foreman/notion.toml")
    _repo(repo_dir)


def _halts(sent):
    return [m for _, _, m in sent if "게시를 멈췄습니다" in m]


def test_file_removed_while_running_halts_alerts_once_and_resumes(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd, CFG)
    cfg = _cfg(tmp_path, sent)
    pub = _new_publisher(cfg, INFRA, repo)
    cfg.mark({INFRA: pub})
    assert pub.config_halt is None and pub.docs_mode == "auto" and cfg.state[INFRA]["source"] == "repo"
    mem = json.loads((tmp_path / "run" / nc.MEMORY_FILE).read_text())
    assert INFRA in mem and mem[INFRA]["ref"] == "origin/main"                  # 기억이 파일에 남았다
    n0 = len(sent)

    _rm_file(rd)
    cfg.refresh({INFRA: pub})
    st = cfg.state[INFRA]
    assert st["halted"] and st["source"] == "repo" and "origin/main에 파일이 없습니다" in st["error"]
    assert pub.config_halt and "게시를 멈췄습니다" in pub.config_halt and "되살리거나" in pub.config_halt
    # FOREMAN 칸(manual · create false · title keep)이 아니라 가장 좁은 칸 — 그리고 게시는 config_halt로 모두 막힌다
    assert pub.create is False and pub.archive_ok is False and pub.keep_order and pub.docs_mode == "manual"
    assert len(_halts(sent[n0:])) == 1
    for _ in range(3):                                                           # 같은 상태면 다시 알리지 않는다
        cfg.refresh({INFRA: pub})
    assert len(sent) == n0 + 1

    _repo(rd, CFG)                                                               # 파일이 돌아옴
    assert cfg.refresh({INFRA: pub}) == [INFRA]
    assert pub.config_halt is None and pub.docs_mode == "auto" and pub.create is True and not cfg.state[INFRA]["halted"]
    assert len(sent) == n0 + 2 and "다시 돌립니다" in sent[-1][2]
    cfg.refresh({INFRA: pub})
    assert len(sent) == n0 + 2                                                   # 다시 돎도 한 번

    _rm_file(rd)                                                                 # 또 사라지면 또 한 번
    cfg.refresh({INFRA: pub})
    assert pub.config_halt and len(_halts(sent[n0:])) == 2


def test_after_restart_missing_or_broken_file_halts_not_foreman(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd, CFG)
    _new_publisher(_cfg(tmp_path, sent), INFRA, repo)                           # 한 번 저장소 파일로 돎 → 기억

    _repo(rd, "docs = [\n")                                                      # 브리지가 내려가 있는 동안 깨짐
    cfg2 = _cfg(tmp_path, sent)                                                  # 다시 띄움 — 마지막 판이 메모리에 없다
    pub = _new_publisher(cfg2, INFRA, repo)
    cfg2.mark({INFRA: pub})
    assert pub.config_halt and "깨짐" in cfg2.state[INFRA]["error"] and cfg2.state[INFRA]["halted"]
    assert pub.create is False and not any("FOREMAN config/notion.toml 칸으로" in m for _, _, m in sent)

    _rm_file(rd)                                                                 # 다시 띄운 뒤 파일이 없음
    cfg3 = _cfg(tmp_path, sent)
    pub3 = _new_publisher(cfg3, INFRA, repo)
    cfg3.mark({INFRA: pub3})
    assert pub3.config_halt and "파일이 없습니다" in cfg3.state[INFRA]["error"]

    _repo(rd, CFG)                                                               # 멈춘 채 다시 띄운 뒤 돌아옴 — 그래도 「다시 돌립니다」
    cfg4 = _cfg(tmp_path, sent)
    pub4 = _new_publisher(cfg4, INFRA, repo)
    cfg4.mark({INFRA: pub4})
    assert pub4.config_halt is None and pub4.docs_mode == "auto" and "다시 돌립니다" in sent[-1][2]
    assert "halted" not in json.loads((tmp_path / "run" / nc.MEMORY_FILE).read_text())[INFRA]
    n = len(sent)
    _new_publisher(_cfg(tmp_path, sent), INFRA, repo)                            # 한 번 더 띄우면 멈춤 · 다시 돎 알림은 없다
    assert not any("멈췄습니다" in m or "다시 돌립니다" in m for _, _, m in sent[n:])


def test_broken_while_running_keeps_last_version_as_before(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd, CFG)
    cfg = _cfg(tmp_path, sent)
    pub = _new_publisher(cfg, INFRA, repo)
    _repo(rd, 'docs = "Auto"\n')
    cfg.refresh({INFRA: pub})
    st = cfg.state[INFRA]
    assert pub.config_halt is None and pub.docs_mode == "auto" and st.get("stale") and not st["halted"]
    assert "옛 설정을 그대로" in sent[-1][2]
    _rm_file(rd)                                                                 # 깨진 채 도는 중에 지워지면 멈춤
    cfg.refresh({INFRA: pub})
    assert pub.config_halt


def test_projects_that_never_used_repo_file_are_unchanged(tmp_path):
    sent = []
    for name in ("runshoes", "petmint-rag-chatbot", INFRA):
        rd = tmp_path / name
        rd.mkdir()
        repo = _repo(rd)
        cfg = _cfg(tmp_path, sent)
        pub = _new_publisher(cfg, name, repo)
        cfg.refresh({name: pub})
        assert pub.config_halt is None and cfg.state[name]["source"] == "foreman" and not cfg.state[name]["halted"]
        assert pub.docs_mode == BASE[name]["docs"]
    _repo(tmp_path / INFRA, "docs = [\n")                                        # 쓴 적 없는 프로젝트가 처음부터 깨짐 — 지금처럼 FOREMAN 칸 + 알림
    cfg = _cfg(tmp_path, sent)
    pub = _new_publisher(cfg, INFRA, str(tmp_path / INFRA))
    cfg.mark({INFRA: pub})
    assert pub.config_halt is None and cfg.state[INFRA]["error"] and "FOREMAN config/notion.toml 칸으로" in sent[-1][2]
    assert not (tmp_path / "run" / nc.MEMORY_FILE).exists()                      # 기억할 것이 없었다


def test_ref_follows_foreman_column(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd)
    before = _git(rd, "rev-parse", "HEAD")                                       # 파일이 생기기 전 커밋
    _repo(rd, CFG, push=False)                                                   # 커밋했지만 push 안 함
    head = {**BASE, INFRA: {**BASE[INFRA], "ref": "HEAD"}}
    cfg = _cfg(tmp_path, sent, head)
    pub = _new_publisher(cfg, INFRA, repo)
    assert cfg.state[INFRA]["ref"] == "HEAD" and cfg.state[INFRA]["source"] == "repo" and pub.docs_mode == "auto"
    no_ref = {**BASE, INFRA: {k: v for k, v in BASE[INFRA].items() if k != "ref"}}
    assert nc.NotionConfig(no_ref).ref_for(INFRA) == "origin/main"
    # 관리자 라이브 시험 길: FOREMAN 칸 ref만 그 파일이 생기기 전 커밋으로 → 「파일이 사라짐」 → 멈춤
    cfg.base = {**BASE, INFRA: {**BASE[INFRA], "ref": before}}
    cfg.refresh({INFRA: pub})
    assert pub.config_halt and f"{before}에 파일이 없습니다" in cfg.state[INFRA]["error"]


def test_forget_returns_to_foreman_columns(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd, CFG)
    cfg = _cfg(tmp_path, sent)
    pub = _new_publisher(cfg, INFRA, repo)
    _rm_file(rd)
    cfg.refresh({INFRA: pub})
    assert pub.config_halt
    assert cfg.forget(INFRA, pub) is True
    assert pub.config_halt is None and pub.docs_mode == "manual" and pub.keep_title and cfg.state[INFRA]["source"] == "foreman"
    assert INFRA not in json.loads((tmp_path / "run" / nc.MEMORY_FILE).read_text())
    cfg2 = _cfg(tmp_path, sent)                                                  # 다시 띄워도 잊은 채
    assert _new_publisher(cfg2, INFRA, repo).docs_mode == "manual" and INFRA not in cfg2.halted


def test_broken_memory_file_alerts_and_is_kept_aside(tmp_path):
    sent = []
    mem = tmp_path / "run" / nc.MEMORY_FILE
    mem.parent.mkdir()
    mem.write_text("{깨짐")
    cfg = _cfg(tmp_path, sent)
    assert cfg.seen == {} and any("읽지 못했습니다" in m for _, _, m in sent)
    assert (tmp_path / "run" / (nc.MEMORY_FILE + ".broken")).exists()


# ── 멈춘 게시기는 아무 길로도 쓰지 않는다 ──────────────────────────
def test_api_refuses_publish_pair_docsync_when_halted(tmp_path):
    c, app = _app(tmp_path)
    p = app.state.publishers["runshoes"]
    p.config_halt = nc.halt_message("runshoes", "origin/main에 파일이 없습니다")
    for body in ({"path": "docs/a.md"}, {"path": "docs/a.md", "action": "docsync"}, {"path": "docs/a.md", "force": True},
                 {"path": "portfolio/", "action": "docsync"}):
        r = c.post("/api/publish", json={"project": "runshoes", **body}, headers=h(ADMIN))
        assert r.status_code == 409 and r.json()["halted"] and "게시를 멈췄습니다" in r.json()["refused"]
    r = c.post("/api/publish/pair", json={"project": "runshoes", "path": "docs/a.md", "page_id": "a" * 32}, headers=h(RUN))
    assert r.status_code == 409 and r.json()["halted"]
    assert p.calls == [] and app.state.docsync.calls == []
    # 다른 프로젝트는 그대로
    assert c.post("/api/publish", json={"project": "petmint-rag-chatbot", "path": "docs/a.md"}, headers=h(ADMIN)).status_code == 200


def test_get_publish_shows_halt_in_config(tmp_path):
    sent = []
    rd = tmp_path / "repo"
    rd.mkdir()
    repo = _repo(rd, CFG)
    cfg = _cfg(tmp_path, sent, {**BASE, "runshoes": {**BASE[INFRA]}})
    c, app = _app(tmp_path)
    p = app.state.publishers["runshoes"]
    p.repo = repo
    p.configure = lambda **kw: None
    cfg.refresh({"runshoes": p})
    _rm_file(rd)
    cfg.refresh({"runshoes": p})
    app.state.notion_cfg = cfg
    j = c.get("/api/publish?project=runshoes", headers=h(ADMIN)).json()
    assert j["config"]["halted"] is True and j["config"]["source"] == "repo" and "게시를 멈췄습니다" in j["config"]["error"]


def test_forget_api_is_admin_only(tmp_path):
    c, app = _app(tmp_path)
    called = []

    class Cfg:
        state = {}

        def forget(self, name, pub=None):
            called.append(name)
            return True
    app.state.notion_cfg = Cfg()
    assert c.delete("/api/publish/repo-config?project=runshoes", headers=h(RUN)).status_code == 403
    assert called == []
    r = c.delete("/api/publish/repo-config?project=runshoes", headers=h(ADMIN))
    assert r.status_code == 200 and r.json()["forgot"] is True and called == ["runshoes"]


class _SyncPub:
    def __init__(self, halt):
        self.project, self.docs_mode, self.quiet_min, self.config_halt = INFRA, "auto", 0, halt
        self.calls = []

    async def publish(self, *a, **kw):
        self.calls.append(a)
        raise AssertionError("멈춘 게시기가 올렸습니다")


def test_auto_sync_and_sync_do_nothing_when_halted(monkeypatch):
    called = []

    async def fake_status(pub, src=None):
        called.append(pub.project)
        return {"new": ["docs/a.md"], "changed": [], "deleted": [], "broken": [], "last_commit_at": None}
    monkeypatch.setattr(ds, "status", fake_status)
    pub = _SyncPub("멈춤")
    d = ds.DocSync({INFRA: pub})
    asyncio.run(d.tick())
    assert called == [] and pub.calls == []
    r = asyncio.run(ds.sync(pub, "now"))
    assert r["halted"] == "멈춤" and r["done"] == [] and pub.calls == [] and called == []


def test_todo_line_when_halted():
    pub = _SyncPub(nc.halt_message(INFRA, "origin/main에 파일이 없습니다"))
    items = asyncio.run(ds.todo_items(pub, None))
    assert len(items) == 1 and items[0]["act"] == "docsync" and items[0]["halted"] and "게시를 멈췄습니다" in items[0]["why"]
