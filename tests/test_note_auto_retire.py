"""끝난 「진행 중인 일」 노트 줄 내리기 · 낡음 표시(11-13, log/note_auto_retire_20261113.md) — 임시 git 저장소 + foreman_test DB.

11-13 운영 DB의 진행 중 15줄(FOREMAN 13 · 펫퍼민트 1 · 런슈즈 1)과 같은 모양을 만들어 12줄이 내려가고 3줄이 남는지 본다.
"""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pymysql
import pytest

from bridge import foreman_note as notes
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


def _session(conn, cwd, cc, *acts, role="coder", ended=True):
    with conn.cursor() as c:
        c.execute("SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id WHERE p.name = 'foreman' LIMIT 1")
        (char,) = c.fetchone()
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, title, wake_reason, detached_at, hidden_at, hidden_reason) "
                  "VALUES (%s, 'agent', %s, %s, %s, 't', 'user', %s, NOW(3), 'test')",
                  (char, role, cc, str(cwd), datetime.now(UTC).replace(tzinfo=None) if ended else None))
        sid = c.lastrowid
        for a in acts:
            c.execute("INSERT INTO session_action (session_id, action, ok, detail) VALUES (%s, %s, 1, 'x')", (sid, a))
        return sid


def _note(conn, project, sids, kind="thread", days=1.0, source="dispatch #1", dispatch_id=None, extra=None):
    refs = {"head": "x", **({"sessions": sids} if sids is not None else {}), **(extra or {})}
    with conn.cursor() as c:
        c.execute("INSERT INTO foreman_note (project, kind, body, source, refs, checked_at, dispatch_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (project, kind, f"줄 {sids}", source, json.dumps(refs),
                   datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days), dispatch_id))
        return c.lastrowid


def _wtpath(repo, name):
    return Path(repo) / wt.WT_DIR / name          # 폴더는 없다 — 이미 지워진 worktree 자리


async def _mk_wt(repo, name, commit=False):
    p = Path((await wt.create(str(repo), name))["path"])
    if commit:
        (p / f"{name}.txt").write_text("x\n"); sh(p, "add", "."); sh(p, "commit", "-qm", name)
    return p


def _shape(conn, repo, other_repo):
    """11-13 운영 DB 15줄과 같은 모양 → {줄 이름: note id}."""
    W = lambda n: _wtpath(repo, n)  # noqa: E731
    ids = {}
    s247 = _session(conn, W("foreman"), "c247", "wt-merge")
    s248 = _session(conn, repo, "c248", "role")                                   # 원본 폴더 시험 세션 — 끝남
    s249 = _session(conn, W("foreman"), "c249", "wt-merge")
    ids[994] = _note(conn, "foreman", [s247, s248, s249], days=3.2)
    ids[1098] = _note(conn, "foreman", [_session(conn, W("foreman-4"), "c255", "wt-discard")], days=3.1)
    ids[1170] = _note(conn, "foreman", [_session(conn, W("foreman"), "c257", "rest", "wt-discard", "wt-merge")], days=3.0)
    s262 = _session(conn, W("foreman-9"), "c262")                                 # 기록 없이 끝남 — 같은 자리를 뒤 세션이 씀
    _session(conn, W("foreman-9"), "c263", "wt-merge")
    ids[1200] = _note(conn, "foreman", [s262], days=3.0)
    for k in (1247, 1334, 1350, 1395):
        ids[k] = _note(conn, "foreman", [_session(conn, W(f"m{k}"), f"c{k}", "wt-merge")], days=2.5)
    for k in (1396, 1439):
        ids[k] = _note(conn, "foreman", [_session(conn, W(f"d{k}"), f"c{k}", "wt-discard")], days=2.2)
    s311 = _session(conn, W("foreman-8"), "c311", "report-read")                  # check_watch — 커밋 0으로 끝, 일은 314가 합침
    _session(conn, W("foreman-8"), "c314", "wt-merge")
    ids[2239] = _note(conn, "foreman", [s311], days=0.9)
    ids[2241] = _note(conn, "foreman", [_session(conn, W("foreman-7"), "c312", "mprep-card", "report-read", "wt-discard")], days=0.9)
    # 남는 3줄
    ids[113] = _note(conn, "foreman", [_session(conn, repo, "c211")], days=5.3)                    # 원본 폴더 세션뿐
    ids[509] = _note(conn, "petmint-rag-chatbot", [_session(conn, other_repo, "c223")], days=4.2)   # 원본 폴더 세션뿐
    s310 = _session(conn, other_repo, "c310", "mgr-ask", role="manager", ended=False)
    ids[2238] = _note(conn, "runshoes", [s310], days=0.9, source="dispatch #406", dispatch_id=406)   # 관리자 — 살아 있음
    with conn.cursor() as c:
        c.execute("INSERT INTO dispatch_session (dispatch_id, idx, role, status, session_id) VALUES (406, 0, 'manager', 'started', %s)", (s310,))
        c.execute("INSERT INTO turn (session_id, seq, started_at, ended_at) VALUES (%s, 1, NOW(3), NOW(3))", (s310,))
    return ids


@pytest.mark.db
async def test_fifteen_lines_twelve_retired_three_kept(env, tmp_path):
    s, conn, repo = env
    other = tmp_path / "other"
    other.mkdir()
    ids = _shape(conn, repo, other)
    dec = _note(conn, "foreman", None, kind="decision", days=9)                 # 사람이 정한 판단 — 건드리지 않는다
    eng = make_engine(s)
    try:
        live = {"c310"}
        async with eng.begin() as c:
            dry = []
            for p in ("foreman", "petmint-rag-chatbot", "runshoes"):
                dry += await notes.sweep(c, p, live, dry_run=True)
            assert sum(r["verdict"] == "done" for r in dry) == 12 and not any(r["retired"] for r in dry)
            res = {}
            for p in ("foreman", "petmint-rag-chatbot", "runshoes"):
                for r in await notes.sweep(c, p, live):
                    res[r["id"]] = r
        down = {k for k, i in ids.items() if res[i]["retired"]}
        assert down == {994, 1098, 1170, 1200, 1247, 1334, 1350, 1395, 1396, 1439, 2239, 2241}
        assert res[ids[113]]["verdict"] == "unknown" and "원본 폴더 세션뿐" in res[ids[113]]["why"]
        assert res[ids[509]]["verdict"] == "unknown"
        assert res[ids[2238]]["verdict"] == "unknown" and "살아 있음" in res[ids[2238]]["why"]
        assert "합침" in res[ids[994]]["why"] and "끝남(원본 폴더)" in res[ids[994]]["why"]
        assert "자리를 세션" in res[ids[1200]]["why"] and "자리를 세션" in res[ids[2239]]["why"]
        with conn.cursor() as c:
            c.execute("SELECT retired_at IS NULL, JSON_EXTRACT(refs, '$.auto_retired.why') FROM foreman_note WHERE id = %s", (ids[994],))
            alive, why = c.fetchone()
            assert not alive and why.startswith('"자동: 세션')                  # 지우지 않고 까닭을 남김
            c.execute("SELECT retired_at IS NULL FROM foreman_note WHERE id = %s", (dec,))
            assert c.fetchone()[0] == 1
        async with eng.begin() as c:
            # 다시 훑어도 같은 줄을 두 번 내리지 않는다
            again = await notes.sweep(c, "foreman", live)
            assert not any(r["retired"] for r in again)
            # 화면 「자동으로 내린 줄」 · 되살리기 — 되살린 줄은 다시 자동으로 내리지 않는다
            auto = await notes.auto_retired(c, "foreman")
            assert len(auto) == 12 and all(a["why"].startswith("자동:") for a in auto)
            assert await notes.restore(c, ids[1098]) and not await notes.restore(c, ids[1098])
            assert not await notes.restore(c, dec)                                  # 자동으로 내린 줄이 아니다
            again = await notes.sweep(c, "foreman", live)
            assert ids[1098] not in {r["id"] for r in again}
            assert ids[1098] in {n["id"] for n in await notes.active(c, "foreman")}
            # 관리자 띄우기 줄 — 규칙을 켜면 띄운 dispatch · 첫 턴 끝으로 끝(기본은 끔)
            r = await notes.sweep(c, "runshoes", live, notes.NoteRules(manager_spawn_done=True))
            assert r[0]["retired"] and "관리자 띄움 끝" in r[0]["why"]
    finally:
        await eng.dispose()


@pytest.mark.db
async def test_git_truth_for_unrecorded_worktree(env):
    s, conn, repo = env
    merged = await _mk_wt(repo, "merged", commit=True)
    sh(repo, "merge", "-q", "--ff-only", "cc/merged")
    left = await _mk_wt(repo, "left", commit=True)                              # 합치지 않은 커밋이 남음
    gone = _wtpath(repo, "gone")                                                # 폴더 · 브랜치 모두 없음
    a = _note(conn, "foreman", [_session(conn, merged, "m1")])
    b = _note(conn, "foreman", [_session(conn, left, "l1")])
    c_ = _note(conn, "foreman", [_session(conn, gone, "g1")])
    d = _note(conn, "foreman", [_session(conn, _wtpath(repo, "alive"), "x1", ended=False)])   # 살아 있음 — live=None이면 detached_at으로
    e = _note(conn, "foreman", [])                                              # 붙은 세션 없음
    eng = make_engine(s)
    try:
        async with eng.begin() as c:
            res = {r["id"]: r for r in await notes.sweep(c, "foreman", None)}
    finally:
        await eng.dispose()
    assert res[a]["retired"] and "커밋이 원본에 들어 있음" in res[a]["why"]
    assert res[b]["verdict"] == "open" and not res[b]["retired"]
    assert res[c_]["retired"] and "폴더 · 브랜치 없어짐" in res[c_]["why"]
    assert res[d]["verdict"] == "unknown" and res[e]["verdict"] == "unknown"


def test_verdict_repo_error_is_not_done():
    f = {"alive": False, "wt": "x", "repo": "/r", "acts": set(), "card": None, "later": None, "in_base": "error", "dir": True}
    assert notes.verdict([1], {1: f})[0] == "open"
    assert notes.verdict([1, 2], {1: dict(f, in_base=True)})[0] == "unknown"      # 세션 2를 못 찾음 — 내리지 않는다
    assert notes.verdict([1], {1: dict(f, card="merged")}) == ("done", "자동: 세션 1 합침(카드)")


def test_stale_rule_days_and_commits():
    now = datetime(2026, 11, 13, 12)
    r = notes.NoteRules()
    n = {"kind": "thread", "checked_at": now - timedelta(days=5.3), "commits": 347}
    assert notes.stale_why(n, r, now) == ["확인 뒤 5일", "확인 뒤 커밋 347개"]
    assert notes.stale_why(dict(n, checked_at=now - timedelta(days=0.9), commits=219), r, now) == ["확인 뒤 커밋 219개"]
    assert notes.stale_why(dict(n, checked_at=now - timedelta(days=0.9), commits=54), r, now) == []
    assert notes.stale_why(dict(n, kind="decision"), r, now) == []                # 판단 줄은 낡음으로 보지 않는다


def test_load_rules(tmp_path):
    p = tmp_path / "w.toml"
    p.write_text("enabled = true\n[note]\nstale_days = 5\nmanager_spawn_done = true\n", encoding="utf-8")
    r = notes.load_rules(p)
    assert (r.stale_days, r.stale_commits, r.manager_spawn_done) == (5.0, 150, True)
    assert notes.load_rules(tmp_path / "없음.toml") == notes.NoteRules()


@pytest.mark.db
async def test_render_splits_stale(env):
    s, conn, repo = env
    _note(conn, "foreman", [], days=5.3)                                        # 낡음
    fresh = _note(conn, "foreman", [], days=0.1)
    _note(conn, "foreman", None, kind="decision", days=9)

    async def git(repo_, *args):
        return "219" if args[0] == "rev-list" else ""
    eng = make_engine(s)
    try:
        async with eng.connect() as c:
            r = await notes.render(c, "foreman", "y", git, "/r", rules=notes.NoteRules(stale_commits=10 ** 6))
    finally:
        await eng.dispose()
    lines = r["text"].splitlines()
    assert len(lines) == 3 and f"[노트 {fresh} · 진행 중인 일]" in lines[0]
    assert "사람이 정한 판단" in lines[1] and "낡음(확인 필요" in lines[2]       # 낡은 줄은 맨 뒤 · 따로
    assert [bool(n["stale"]) for n in r["notes"]] == [False, False, True]
