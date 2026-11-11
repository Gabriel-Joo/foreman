"""화면의 worktree 상태를 실제와 맞추기(11-11) — 밖에서 합친 · 이름이 다시 쓰인 「합치기 기다림」(받은 할 일 #17)."""

import subprocess
from pathlib import Path

import pymysql
import pytest

from bridge import coder_room as cr
from bridge import worktree as wt
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main


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


def _session(conn, cwd, cc):
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'foreman' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', %s, %s, 't', 'user')", (char, cc, cwd))
        return c.lastrowid


def _rest(conn, sid):
    with conn.cursor() as c:
        c.execute("INSERT INTO session_action (session_id, action, ok, detail) VALUES (%s, 'rest', 1, 'x')", (sid,))


@pytest.mark.db
async def test_rested_skips_outside_merge_and_reused_name(env, monkeypatch):
    s, conn, repo = env
    monkeypatch.setattr(cr, "live_sessions", lambda d: {})
    engine = make_engine(s)
    try:
        info = await wt.create(str(repo), "foreman")
        p = Path(info["path"])
        (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
        a = _session(conn, str(p), "aaaaaaaa-0000-0000-0000-000000000017")
        _rest(conn, a)
        got = await cr.rested(engine, "/없음", "foreman")
        assert [x["session_id"] for x in got] == [a]                 # 합칠 커밋 1 — 진짜 합치기 기다림
        assert await cr.rest_stale(engine, a, str(p)) is None

        sh(repo, "merge", "-q", "--ff-only", "cc/foreman")            # 합치기 API가 거부해 밖에서 합침
        assert await cr.rested(engine, "/없음", "foreman") == []
        why = await cr.rest_stale(engine, a, str(p))
        assert why and "원본에 들어 있습니다" in why

        # 같은 이름을 뒤 세션이 다시 씀 — 옛 쉬게 하기 기록은 지금 폴더(뒤 세션 것)와 상관없다
        await wt.remove(str(repo), "foreman", force=True)
        info2 = await wt.create(str(repo), "foreman")
        p2 = Path(info2["path"])
        (p2 / "c.txt").write_text("c\n"); sh(p2, "add", "c.txt"); sh(p2, "commit", "-qm", "c")
        b = _session(conn, str(p2), "bbbbbbbb-0000-0000-0000-000000000017")
        assert await cr.rested(engine, "/없음", "foreman") == []
        why = await cr.rest_stale(engine, a, str(p))
        assert why and f"세션 {b}" in why
        async with engine.connect() as c:
            assert await cr.reused_by(c, a, str(p)) == b
            assert await cr.reused_by(c, b, str(p2)) is None
    finally:
        await engine.dispose()
