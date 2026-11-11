"""끝난 뒤 어긋난 것 훑기(11-11, bridge/reconcile.py) — 임시 git 저장소 + foreman_test DB."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pymysql
import pytest

from bridge import worktree as wt
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.reconcile import Reconciler, sweep


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"); sh(r, "config", "user.name", "t")
    (r / "a.txt").write_text("one\n")
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


def _session(conn, cwd, cc, *acts):
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'foreman' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', %s, %s, 't', 'user')", (char, cc, str(cwd)))
        sid = c.lastrowid
        for a in acts:
            c.execute("INSERT INTO session_action (session_id, action, ok, detail) VALUES (%s, %s, 1, 'x')", (sid, a))
        return sid


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda n: None)

    def send_direct(self, project, kind, session_id, msg, rule=None):
        self.sent.append((project, kind, msg, rule))


async def _wt(repo, name, commit=False):
    p = Path((await wt.create(str(repo), name))["path"])
    if commit:
        (p / f"{name}.txt").write_text("x\n"); sh(p, "add", "."); sh(p, "commit", "-qm", name)
    return p


@pytest.mark.db
async def test_sweep_finds_each_kind_and_alerts_once(env):
    s, conn, repo = env
    live_p = await _wt(repo, "live", commit=True)
    _session(conn, live_p, "cc-live")                                   # 도는 세션 — 보지 않는다
    dirty_p = await _wt(repo, "dirty")
    (dirty_p / "x.txt").write_text("x\n")
    d_sid = _session(conn, dirty_p, "cc-dirty")                         # 끝났는데 커밋 안 된 변경
    left_p = await _wt(repo, "left", commit=True)
    sh(repo, "merge", "-q", "--ff-only", "cc/left")
    l_sid = _session(conn, left_p, "cc-left", "wt-merge")               # 합쳤다는 기록인데 폴더가 남음
    rest_p = await _wt(repo, "rested", commit=True)
    _session(conn, rest_p, "cc-rest", "rest")                           # 진짜 합치기 기다림 — 어긋남 아님
    stale_p = await _wt(repo, "stale", commit=True)
    sh(repo, "merge", "-q", "--ff-only", "cc/stale")
    st_sid = _session(conn, stale_p, "cc-stale", "rest")                # 밖에서 합친 합치기 기다림
    await _wt(repo, "nobody")                                           # 이 폴더를 쓴 세션이 없음
    br = await _wt(repo, "br", commit=True)
    sh(repo, "worktree", "remove", str(br))                             # 브랜치만 남음(합치지 않은 커밋)
    gone = await _wt(repo, "gone")
    subprocess.run(["rm", "-rf", str(gone)], check=True)                # git이 아는데 폴더 없음

    engine = make_engine(s)
    try:
        found = await sweep(engine, "/없음", {str(repo): "foreman"}, live={"cc-live": object()})
        got = [(f["kind"], f.get("session_id")) for f in found]
        assert ("dirty", d_sid) in got and ("orphan", l_sid) in got and ("stale_rest", st_sid) in got
        assert any(k == "orphan" and sid is None for k, sid in got)     # nobody
        assert any(f["kind"] == "branch" and "cc/br" in f["where"] and "합치지 않은 일" in f["detail"] for f in found)
        assert any(f["kind"] == "prunable" for f in found)
        assert not any(str(live_p) == f["where"] or str(rest_p) == f["where"] for f in found)

        # 알림 — 프로젝트마다 한 통, 다음 훑기에서는 같은 것을 다시 알리지 않는다
        rc = Reconciler(engine, FakeNotifier(), "/없음", debounce_s=0)
        import bridge.reconcile as rmod
        orig = rmod.sweep

        async def fixed(engine_, dir_):
            return await orig(engine_, dir_, {str(repo): "foreman"}, live={"cc-live": object()})
        rmod.sweep = fixed
        try:
            keys = await rc.run_once()
            assert len(keys) == len(found) and len(rc.notifier.sent) == 1
            assert rc.notifier.sent[0][2].startswith("[foreman] 🧹 끝난 뒤 어긋난 것")
            with conn.cursor() as c:                                    # 진짜 알림기는 첫 키를 남긴다
                c.execute("INSERT INTO notification (kind, decision, rule, text) VALUES ('recon', 'sent', %s, 'x')",
                          (rc.notifier.sent[0][3],))
            assert await rc.run_once() == [] and len(rc.notifier.sent) == 1
            assert {f["kind"] for f in rc.for_project("foreman")} >= {"dirty", "orphan", "stale_rest", "branch", "prunable"}
        finally:
            rmod.sweep = orig
    finally:
        await engine.dispose()
