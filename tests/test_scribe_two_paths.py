"""서기 두 길 합치기(11-15, log/foreman-7_scribe_design_20261115.md 6-2 안 1).
서기실 [시키기] · 계획 [시작] · 직접 띄우기로 띄운 서기 세션이 같은 기록(scribe-task + dispatch_session)에 잡혀
서기실 열린 일 · 겹침 막기와 계획 겹침(file_conflicts)이 서로를 안다. 서기 동시 개수 상한은 없다."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from bridge import foreman as fm
from bridge import scribe_room as sr
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.handoff import SCRIBE_TASK_ACT, HandoffManager


# ── 기록 한 곳: spawn_new → _finish_spawn ───────────────────────
class _Eng:
    def begin(self):
        return _Conn()

    connect = begin


class _Conn:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def execute(self, q, params=None):
        return SimpleNamespace(scalar=lambda: "later 옛것")


def _hm(monkeypatch):
    m = HandoffManager.__new__(HandoffManager)
    m.engine, m.on_change, m.acts = _Eng(), None, []

    async def ensure_row(cc, cwd, title): return 77
    async def character_for(cwd, role): return None
    async def act(sid, action, pid, ok, detail): m.acts.append((sid, action, detail))
    monkeypatch.setattr(m, "_ensure_row", ensure_row, raising=False)
    monkeypatch.setattr(m, "_character_for", character_for, raising=False)
    monkeypatch.setattr(m, "_act", act, raising=False)
    return m


@pytest.mark.parametrize("role,task,src,want", [
    ("scribe", "later", None, "later"),            # 서기실 [시키기] · 계획 task · 직접 띄우기 task
    ("scribe", None, None, "plan"),                  # 계획 길 · 직접 띄우기에 일 종류가 없으면
    ("scribe", None, 5, "later 옛것"),              # 옮기기 — 옛 서기 세션의 일을 물려받는다
    ("coder", "later", None, None),                 # 서기가 아니면 남기지 않는다
])
def test_finish_spawn_records_scribe_task_once(monkeypatch, role, task, src, want):
    m = _hm(monkeypatch)
    asyncio.run(m._finish_spawn("cc-x", "%1", "/r", None, "t", src, cc="c", pid=1, role=role, scribe_task=task))
    got = [d for s, a, d in m.acts if a == SCRIBE_TASK_ACT and s == 77]
    assert got == ([want] if want else [])
    assert SCRIBE_TASK_ACT == sr.TASK_ACT


def test_plan_start_passes_task_and_sessions_of_keeps_it():
    ss = fm.sessions_of({"sessions": [{"role": "scribe", "task": "later"}, {"role": "scribe", "task": "Bad Task"}], "sessions_edit": True})
    assert [s["task"] for s in ss] == ["later", None]
    assert "task" in fm.S_FIELDS and 'role "scribe"일 때만' in fm.INSTRUCTIONS


def test_instructions_scribe_tasks_follow_tasks():
    """11-17. 교장 지시문의 서기 일 이름은 scribe_room.TASKS 한 곳에서 온다(손으로 적은 목록이 sync, loss를 말하고 techdoc이 빠졌다)."""
    line = next(ln for ln in fm.INSTRUCTIONS.splitlines() if "서기실 일 이름(" in ln)
    names = line.split("서기실 일 이름(")[1].split(")")[0].split(", ")
    assert set(names) == set(sr.TASKS) - {"publish"}                  # publish는 세션이 아니라 버튼
    role = next(ln for ln in fm.INSTRUCTIONS.splitlines() if "scribe 일감" in ln)
    assert all(f"({k})" in role for k in names) and "(sync)" not in role and "(loss)" not in role
    assert "{SCRIBE_" not in fm.INSTRUCTIONS


def test_plan_start_hands_task_to_spawn_new(tmp_path, monkeypatch):
    from bridge import foreman_note
    from tests.test_foreman_multi import _HM, _aw, _disp, _Eng
    hm = _HM()
    d = _disp(tmp_path, hm, monkeypatch)
    d.engine = _Eng()
    monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
    monkeypatch.setattr(foreman_note, "apply", lambda *a, **k: _aw([]))
    asyncio.run(d.start(5, {"project": "zz", "mode": "new", "sessions_edit": True,
                            "sessions": [{"role": "scribe", "title": "R", "first_prompt": "r", "task": "later"},
                                         {"role": "scribe", "title": "P", "first_prompt": "p"}]}))
    assert [c[2]["scribe_task"] for c in hm.calls] == ["later", None]     # 없으면 spawn_new가 plan으로 남긴다


# ── DB (foreman_test) ────────────────────────────────────────
def _db(fn):
    async def run():
        s = Settings(mysql_database="foreman_test")
        assert migrate_main([], settings=s) == 0
        eng = make_engine(s)
        proj = "zz-sc2-" + uuid.uuid4().hex[:6]
        async with eng.begin() as c:
            pid = (await c.execute(text("INSERT INTO project (name, repo_path) VALUES (:p, '/nowhere')"), {"p": proj})).lastrowid
            ch = (await c.execute(text("INSERT INTO `character` (project_id, name, current_role, status, kind, spawned_by) "
                                       "VALUES (:p, '서기', 'scribe', 'IDLE', 'agent', 'foreman')"), {"p": pid})).lastrowid
        try:
            await fn(eng, proj, ch)
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE ds FROM dispatch_session ds JOIN dispatch d ON d.id = ds.dispatch_id WHERE d.project = :p"), {"p": proj})
                await c.execute(text("DELETE FROM dispatch WHERE project = :p"), {"p": proj})
                await c.execute(text("DELETE sa FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
                                     "WHERE cs.character_id = :c"), {"c": ch})
                await c.execute(text("DELETE FROM character_session WHERE character_id = :c"), {"c": ch})
                await c.execute(text("DELETE FROM `character` WHERE id = :c"), {"c": ch})
                await c.execute(text("DELETE FROM project WHERE name = :p"), {"p": proj})
            await eng.dispose()
    asyncio.run(run())


async def _sess(eng, ch, wt_path, role="scribe", task=None, title="서기"):
    async with eng.begin() as c:
        sid = (await c.execute(text(
            "INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, title, wake_reason, worktree_path) "
            "VALUES (:ch, 'agent', :r, :cc, :w, :t, 'user', :w)"),
            {"ch": ch, "r": role, "cc": uuid.uuid4().hex, "w": str(wt_path) if wt_path else None, "t": title})).lastrowid
        if task:
            await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                            {"s": sid, "a": sr.TASK_ACT, "d": task})
    return sid


async def _merged(eng, sid):
    async with eng.begin() as c:
        await c.execute(text("INSERT INTO session_action (session_id, action, ok) VALUES (:s, 'wt-merge', 1)"), {"s": sid})


@pytest.mark.db
def test_plan_scribe_counts_in_room_and_room_scribe_in_plan_conflicts(tmp_path, monkeypatch):
    async def go(eng, proj, ch):
        (tmp_path / "wt1").mkdir(), (tmp_path / "wt2").mkdir(), (tmp_path / "wt3").mkdir()
        # 1) 계획 길로 띄운 서기 — scribe-task plan(spawn_new가 남김) + dispatch_session(맡을 파일 CLAUDE.md, docs/)
        plan = await _sess(eng, ch, tmp_path / "wt1", task="plan", title="CLAUDE.md 정리 서기")
        await fm.record_spawn(eng, "human", proj, {"role": "scribe", "title": "CLAUDE.md 정리 서기", "files": ["CLAUDE.md", "docs/style_guide.md"]},
                              {"session_id": plan})
        # 2) 11-15 전 계획 길 서기 — scribe-task 없이 dispatch_session만
        old = await _sess(eng, ch, tmp_path / "wt2", title="옛 계획 서기")
        await fm.record_spawn(eng, "spawn", proj, {"role": "scribe", "title": "옛 계획 서기", "files": ["log/doccheck_20261115.md"]},
                              {"session_id": old})
        # 3) 서기실 [시키기] — scribe-task later + _record(dispatch origin scribe)
        room = await _sess(eng, ch, tmp_path / "wt3", task="later", title="서기 — 나중에 할 일 정리")
        await sr._record(eng, proj, "서기 — 나중에 할 일 정리", "later", None, {"session_id": room})
        # 4) worktree 폴더가 사라진 것(합치기 기록 없이) · 합친 것 — 열려 있지 않다
        gone = await _sess(eng, ch, tmp_path / "없음", task="later")
        done = await _sess(eng, ch, tmp_path / "wt1", task="portfolio 00_a")
        await _merged(eng, done)

        opened = await sr.open_tasks(eng, proj)
        assert [(o["session_id"], o["task"]) for o in opened] == [(plan, "plan"), (old, "plan"), (room, "later")]
        assert opened[0]["files"] == ["CLAUDE.md", "docs/style_guide.md"] and opened[2]["files"] == ["README.md"]
        assert gone not in [o["session_id"] for o in opened] and done not in [o["session_id"] for o in opened]
        # 서기실 겹침 막기가 계획 길 서기를 안다
        assert f"세션 {plan}" in sr.blocked("trim", opened) and "CLAUDE.md" in sr.blocked("trim", opened)
        assert f"세션 {old}" in sr.blocked("doccheck", opened)
        assert "이미 열려" in sr.blocked("later", opened) and "README.md" in sr.blocked("docfix", [opened[2]])
        assert sr.blocked("portfolio", opened, "00_a") is None                    # 셋 열려 있어도 파일이 다르면 막지 않는다
        # 서기실 todo의 열린 일 · 막힘 글도 같은 판단(todo는 저장소가 있어야 돌아 여기서는 open_tasks · blocked만)

        # 계획 겹침이 서기실 서기를 안다(CC가 살아 있지 않아도 합치지 않은 worktree면)
        monkeypatch.setattr(fm, "live_sessions", lambda _d: {})
        d = fm.ForemanDispatcher(eng, tmp_path, None, lambda: [(str(tmp_path), 1, proj, 1)])
        ov, fw = await d.file_conflicts(proj, fm.sessions_of({"title": "README 서기", "role": "scribe", "files": ["README.md", "CLAUDE.md"]}))
        assert not fw
        got = {(o["with"], tuple(o["files"])) for o in ov if o["kind"] == "claimed"}
        assert got == {(room, ("README.md",)), (plan, ("CLAUDE.md",))}
        assert any("합치지 않은 세션" in o["text"] for o in ov)
        ov, _ = await d.file_conflicts(proj, fm.sessions_of({"files": ["README.md"]}), exclude_session=room)
        assert ov == []
    _db(go)


@pytest.mark.db
def test_room_scribe_without_dispatch_record_still_in_plan_conflicts(tmp_path, monkeypatch):
    """11-15 전 서기실 세션 — dispatch 기록이 없어도 scribe-task로 계획 겹침에 잡힌다."""
    async def go(eng, proj, ch):
        (tmp_path / "w").mkdir()
        sid = await _sess(eng, ch, tmp_path / "w", task="trim", title="서기 — CLAUDE.md 정리")
        monkeypatch.setattr(fm, "live_sessions", lambda _d: {})
        d = fm.ForemanDispatcher(eng, tmp_path, None, lambda: [(str(tmp_path), 1, proj, 1)])
        ov, fw = await d.file_conflicts(proj, fm.sessions_of({"files": ["docs/12_scribe.md"]}))
        assert not fw and [(o["kind"], o["with"], o["files"]) for o in ov] == [("claimed", sid, ["docs/12_scribe.md"])]
        assert "열려 있는 서기 세션" in ov[0]["text"]
    _db(go)


@pytest.mark.db
def test_many_scribes_not_capped(tmp_path):
    """서기를 셋 넘게 띄워도 막히지 않는다(11-15 사용자 「동시 상한을 두지 마라」) — 파일이 다르면 몇 개든."""
    async def go(eng, proj, ch):
        for i, task in enumerate(("later", "trim", "doccheck", "portfolio 00_a", "portfolio 01_b")):
            (tmp_path / f"w{i}").mkdir()
            await _sess(eng, ch, tmp_path / f"w{i}", task=task)
        opened = await sr.open_tasks(eng, proj)
        assert len(opened) == 5
        assert sr.blocked("portfolio", opened, "02_c") is None
        assert sr.blocked("plan", opened) is None
        assert "이미 열려" in sr.blocked("portfolio", opened, "01_b")
    _db(go)
