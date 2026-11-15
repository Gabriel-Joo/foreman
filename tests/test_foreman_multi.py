"""교장 ① 한 계획에 여러 세션 · ④ 모든 띄우기 기록 · 일곱 맡을 파일 · 합칠 순서 · 같은 파일 헛경보(11-11, 코더 C1)."""

import asyncio
import json
import uuid
from types import SimpleNamespace

from sqlalchemy import text

from bridge import foreman as fm
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main


# ── 세션 목록 정리 ──────────────────────────────────────────
def test_old_plan_reads_as_one_session():
    old = {"project": "foreman", "mode": "new", "role": "inspector", "title": "가", "first_prompt": "봐라", "read_only": True}
    ss = fm.sessions_of(old)
    assert len(ss) == 1 and ss[0]["role"] == "inspector" and ss[0]["title"] == "가" and ss[0]["read_only"]
    assert ss[0]["files"] == [] and ss[0]["merge_order"] == 1 and ss[0]["on"] and ss[0]["worktree"] is None


def test_llm_sessions_win_then_old_card_edits_first():
    ans = {"project": "foreman", "mode": "new", "role": "coder", "title": "옛",
           "sessions": [{"role": "coder", "title": "A", "first_prompt": "a", "files": ["bridge/a.py", "./b.py", "/etc/x", "../y"]},
                        {"role": "designer", "title": "B", "first_prompt": "b", "files": "bridge/static/js/x.js, tests/js/"}]}
    p = fm.adopt_sessions(ans)
    ss = fm.sessions_of(p)
    assert [s["title"] for s in ss] == ["A", "B"]                      # 교장의 sessions가 위쪽 칸을 이긴다
    assert ss[0]["files"] == ["bridge/a.py", "b.py"]                   # 절대 경로 · .. 은 뺀다
    assert ss[1]["files"] == ["bridge/static/js/x.js", "tests/js/"] and ss[1]["merge_order"] == 2
    p = fm._mirror({**p, "sessions": ss})
    assert p["title"] == "A" and "sessions_edit" not in p
    # 옛 카드 — 위쪽 칸만 고쳐 보낸다: 첫 세션에 들어가고 둘째는 그대로
    edited = {**p, "title": "A 고침", "first_prompt": "a2"}
    ss2 = fm.sessions_of(edited)
    assert (ss2[0]["title"], ss2[0]["first_prompt"], ss2[1]["title"]) == ("A 고침", "a2", "B")
    # 새 카드 — sessions_edit면 세션 칸이 이긴다
    ss3 = fm.sessions_of({**edited, "sessions_edit": True, "sessions": [{**ss[0], "title": "새"}, {**ss[1], "on": False}]})
    assert ss3[0]["title"] == "새" and ss3[1]["on"] is False


def test_files_overlap():
    assert fm.files_overlap(["bridge/a.py"], ["bridge/a.py", "c.py"]) == ["bridge/a.py"]
    assert fm.files_overlap(["migrations/"], ["migrations/0030_x.sql"]) == ["migrations/0030_x.sql"]
    assert fm.files_overlap(["migrations"], ["migrations/0030_x.sql"]) == ["migrations/0030_x.sql"]
    assert fm.files_overlap(["tests/test_foreman*.py"], ["tests/test_foreman_multi.py"]) == ["tests/test_foreman_multi.py"]
    assert fm.files_overlap(["bridge/handoff.py"], ["bridge/api/handoff.py"]) == []
    assert fm.files_overlap(["bridge/a.py"], []) == []


# ── check · start (DB 없이 되는 길) ─────────────────────────
class _Models:
    def pick(self, m, role):
        return m or {"designer": "sonnet"}.get(role, "opus")


class _HM:
    def __init__(self, fail_at=None):
        self.models, self.calls, self.fail_at = _Models(), [], fail_at

    async def spawn_new(self, repo, summary_id, title, **kw):
        self.calls.append((summary_id, title, kw))
        if self.fail_at is not None and len(self.calls) - 1 == self.fail_at:
            raise fm.Refused("tmux 창을 못 만들었습니다")
        return {"session_id": 900 + len(self.calls), "tmux": f"cc-x-{len(self.calls)}", "model": kw.get("model"),
                "worktree": {"branch": "cc/x"} if kw.get("worktree") else None, "cwd": repo, "project": "zz"}


def _disp(tmp_path, hm, monkeypatch):
    monkeypatch.setattr(fm, "live_sessions", lambda _d: {})
    d = fm.ForemanDispatcher(None, tmp_path, hm, lambda: [(str(tmp_path), 1, "zz", 1)])

    async def no_conf(project, ss, did=None, exclude_session=None):
        return [], []
    d.file_conflicts = no_conf
    return d


def test_check_per_session_role_model_worktree(tmp_path, monkeypatch):
    d = _disp(tmp_path, _HM(), monkeypatch)
    plan = {"project": "zz", "mode": "new", "sessions_edit": True,
            "sessions": [{"role": "inspector", "title": "봄", "first_prompt": "a"},
                         {"role": "designer", "title": "화면", "first_prompt": "b", "worktree": False}]}

    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    async def go():
        from bridge import foreman_note
        monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
        d.engine = SimpleNamespace(connect=lambda: C())
        return await d.check(plan)
    p = asyncio.run(go())
    s0, s1 = p["sessions"]
    assert s0["read_only"] and "세션 1: 역할이 조사라 읽기 전용으로 시작합니다" in p["warnings"]
    assert not s0["log_only"] and not p["log_only"]                      # 역할 권한이 막지 않는 프로젝트 — 예전처럼 읽기 전용
    assert (s0["model"], s1["model"]) == ("opus", "sonnet")
    assert s0["worktree"] is False and s1["worktree"] is False          # 첫 세션: 살아 있는 세션 없음 · 둘째: 사람이 끔
    assert p["title"] == "봄" and p["role"] == "inspector"              # 위쪽 칸 = 첫 세션(옛 카드가 보인다)
    # 옛 카드는 첫 세션만 보인다 — [시작]이 띄울 것을 경고 줄에 모두
    assert "이 계획은 세션 2개를 띄웁니다: 1「봄」(조사 · opus), 2「화면」(디자이너 · sonnet)" in p["warnings"]
    # 관리자는 둘째여도 따로 작업을 기본으로 켜지 않는다(11-11 아홉 — 켜면 spawn_new가 거절)
    pm = asyncio.run(_again(d, {"project": "zz", "mode": "new", "sessions_edit": True,
                                "sessions": [{"title": "코더", "first_prompt": "a"}, {"role": "manager", "title": "관리", "first_prompt": "b"}]}))
    assert [s["worktree"] for s in pm["sessions"]] == [False, False]
    # 다시 맞춰도 경고가 쌓이지 않는다
    p2 = asyncio.run(_again(d, p))
    assert p2["warnings"].count("세션 1: 역할이 조사라 읽기 전용으로 시작합니다") <= 1


def test_check_inspector_log_only(tmp_path, monkeypatch):
    """11-15 — 역할 권한이 조사를 log만 쓰게 막는 프로젝트면 조사는 보통 모드(읽기 전용 끔), 사람이 카드에서 켜면 그대로."""
    d = _disp(tmp_path, _HM(), monkeypatch)
    d.inspector_log_only = lambda project: project == "zz"

    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    async def go(plan):
        from bridge import foreman_note
        monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
        d.engine = SimpleNamespace(connect=lambda: C())
        return await d.check(plan)
    p = asyncio.run(go({"project": "zz", "mode": "new", "sessions_edit": True,
                        "sessions": [{"role": "inspector", "title": "봄", "first_prompt": "a", "read_only": True},
                                     {"role": "coder", "title": "고침", "first_prompt": "b"}]}))
    s0, s1 = p["sessions"]
    assert not s0["read_only"] and s0["log_only"] and p["log_only"]       # 교장이 read_only를 켜 보내도 끈다(plan 모드면 log도 승인)
    assert not s1["log_only"]
    assert not any("읽기 전용" in w for w in p["warnings"])
    # 사람이 카드에서 읽기 전용을 켰으면 그대로
    p = asyncio.run(go({"project": "zz", "mode": "new", "sessions_edit": True,
                        "sessions": [{"role": "inspector", "title": "봄", "first_prompt": "a", "read_only": True, "read_only_set": True}]}))
    assert p["sessions"][0]["read_only"] and p["sessions"][0]["log_only"]
    # 자동 기상 계획은 막는 프로젝트여도 읽기 전용(사람이 없는 사이에 커밋이 쌓이지 않게)
    p = asyncio.run(go({"project": "zz", "mode": "new", "wake": True, "sessions_edit": True,
                        "sessions": [{"role": "inspector", "title": "봄", "first_prompt": "a"}]}))
    assert p["sessions"][0]["read_only"] and "역할이 조사라 읽기 전용으로 시작합니다" in p["warnings"]


def test_check_dropped_decision_warns_on_card(tmp_path, monkeypatch):
    """11-13 — 없앤 칸(규칙 · 판단)을 쌓자는 제안은 빠지고 계획 카드에 경고, 다른 노트 다듬기는 로그로만."""
    d = _disp(tmp_path, _HM(), monkeypatch)

    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    async def go():
        from bridge import foreman_note
        dropped = f"{foreman_note.DROPPED_WARN}. 진행 중인 일만 쌓습니다(…): 글씨 배율 90%"
        monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [dropped, "노트 제안이 300자를 넘어 잘랐습니다"])))
        d.engine = SimpleNamespace(connect=lambda: C())
        return dropped, await d.check({"project": "zz", "mode": "new", "title": "t", "first_prompt": "a",
                                       "note_updates": [{"op": "add", "kind": "decision", "body": "글씨 배율 90%"}]})
    dropped, p = asyncio.run(go())
    assert dropped in p["warnings"] and not any(w.startswith("노트 ") for w in p["warnings"])
    assert p["note_updates"] == []


async def _aw(v):
    return v


async def _again(d, p):
    return await d.check(dict(p))


class _Eng:
    """start가 쓰는 DB 자리만 — dispatch 상태 · UPDATE · dispatch_session INSERT를 적어 둔다."""
    def __init__(self):
        self.sql = []

    def connect(self):
        return _Conn(self)

    def begin(self):
        return _Conn(self)


class _Conn:
    def __init__(self, e): self.e = e
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def execute(self, q, params=None):
        s = str(q)
        self.e.sql.append((s, params))
        return SimpleNamespace(scalar=lambda: "planned", first=lambda: None, all=lambda: [], rowcount=1, lastrowid=1)


def test_start_spawns_each_on_session_and_reports_partial_failure(tmp_path, monkeypatch):
    hm = _HM(fail_at=1)
    d = _disp(tmp_path, hm, monkeypatch)
    d.engine = _Eng()
    from bridge import foreman_note
    monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
    monkeypatch.setattr(foreman_note, "apply", lambda *a, **k: _aw([]))
    plan = {"project": "zz", "mode": "new", "sessions_edit": True,
            "sessions": [{"role": "coder", "title": "A", "first_prompt": "a", "files": ["a.py"]},
                         {"role": "coder", "title": "B", "first_prompt": "b"},
                         {"role": "coder", "title": "C", "first_prompt": "c", "on": False},
                         {"role": "designer", "title": "D", "first_prompt": "d"}]}
    out = asyncio.run(d.start(5, plan))
    assert [c[1] for c in hm.calls] == ["A", "B", "D"]                # 끈 C는 안 띄운다
    assert [c[2]["worktree"] for c in hm.calls] == [False, True, True]  # 둘째부터 따로 작업
    assert out["session_id"] == 901 and [f["title"] for f in out["failed"]] == ["B"]
    assert "세션 2「B」은 띄우지 못했습니다" in out["note"]
    assert [s["session_id"] for s in out["sessions"]] == [901, None, None, 903]
    ins = [p for s, p in d.engine.sql if "INSERT INTO dispatch_session" in s]
    assert [(p["i"], p["s"]) for p in ins] == [(0, "started"), (1, "failed"), (2, "off"), (3, "started")]
    assert json.loads(ins[0]["f"]) == ["a.py"] and ins[1]["e"].startswith("tmux")


def test_start_first_failure_refuses_and_starts_nothing(tmp_path, monkeypatch):
    hm = _HM(fail_at=0)
    d = _disp(tmp_path, hm, monkeypatch)
    d.engine = _Eng()
    from bridge import foreman_note
    monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
    plan = {"project": "zz", "mode": "new", "sessions_edit": True,
            "sessions": [{"title": "A", "first_prompt": "a"}, {"title": "B", "first_prompt": "b"}]}
    try:
        asyncio.run(d.start(5, plan))
        raise AssertionError("거절해야 한다")
    except fm.Refused:
        pass
    assert len(hm.calls) == 1 and not any("UPDATE dispatch SET edited" in s for s, _ in d.engine.sql)


def test_start_refuses_when_all_off_or_empty_prompt(tmp_path, monkeypatch):
    d = _disp(tmp_path, _HM(), monkeypatch)
    d.engine = _Eng()
    from bridge import foreman_note
    monkeypatch.setattr(foreman_note, "check_ops", lambda c, p, o: _aw(([], [])))
    for ss, why in (([{"first_prompt": "a", "on": False}], "켠 세션이 없습니다"),
                    ([{"first_prompt": "a"}, {"first_prompt": " "}], "넣을 첫 글이 비었습니다(세션 2)")):
        try:
            asyncio.run(d.start(5, {"project": "zz", "mode": "new", "sessions_edit": True, "sessions": ss}))
            raise AssertionError("거절해야 한다")
        except fm.Refused as e:
            assert why in str(e)


# ── DB: 직접 띄우기 기록 · 세션 기록 · 겹침 (foreman_test) ─────────
def _db(fn):
    async def run():
        s = Settings(mysql_database="foreman_test")
        assert migrate_main([], settings=s) == 0
        eng = make_engine(s)
        proj = "zz-c1-" + uuid.uuid4().hex[:6]
        try:
            await fn(eng, proj)
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE ds FROM dispatch_session ds JOIN dispatch d ON d.id = ds.dispatch_id WHERE d.project = :p"), {"p": proj})
                await c.execute(text("DELETE FROM dispatch WHERE project = :p"), {"p": proj})
            await eng.dispose()
    asyncio.run(run())


def test_record_spawn_and_conflicts_with_planned(tmp_path, monkeypatch):
    async def go(eng, proj):
        did = await fm.record_spawn(eng, "spawn", proj, {"role": "coder", "title": "직접", "files": ["bridge/x.py"]},
                                    {"session_id": None, "model": "opus", "cwd": "/r"}, None, None)
        bad = await fm.record_spawn(eng, "spawn", proj, {"title": "못 뜸"}, None, "폴더가 없습니다")
        async with eng.connect() as c:
            rows = (await c.execute(text("SELECT origin, status, error, JSON_EXTRACT(plan, '$.sessions[0].files') FROM dispatch WHERE id IN (:a, :b) ORDER BY id"),
                                    {"a": did, "b": bad})).all()
            ds = (await c.execute(text("SELECT dispatch_id, status, model, error FROM dispatch_session WHERE dispatch_id IN (:a, :b) ORDER BY dispatch_id"),
                                  {"a": did, "b": bad})).all()
        assert [(r[0], r[1]) for r in rows] == [("spawn", "started"), ("spawn", "failed")] and rows[1][2] == "폴더가 없습니다"
        assert json.loads(rows[0][3]) == ["bridge/x.py"]
        assert [(r[1], r[2]) for r in ds] == [("started", "opus"), ("failed", None)] and ds[1][3] == "폴더가 없습니다"
        # 아직 시작 안 한 다른 계획의 맡을 파일과 겹침
        async with eng.begin() as c:
            r = await c.execute(text("INSERT INTO dispatch (origin, project, request, status, plan) VALUES ('human', :p, 'x', 'planned', :pl)"),
                                {"p": proj, "pl": json.dumps({"mode": "new", "title": "남", "files": ["bridge/"]})})
            other = r.lastrowid
        monkeypatch.setattr(fm, "live_sessions", lambda _d: {})
        d = fm.ForemanDispatcher(eng, tmp_path, _HM(), lambda: [(str(tmp_path), 1, proj, 1)])
        ov, fw = await d.file_conflicts(proj, fm.sessions_of({"title": "나", "files": ["bridge/x.py", "docs/"]}))
        assert not fw and [(o["kind"], o["with"], o["files"]) for o in ov] == [("planned", other, ["bridge/x.py"])]
        assert "아직 시작하지 않은 계획" in ov[0]["text"] and ov[0]["text"].endswith("겹칩니다: bridge/x.py")
        ov, _ = await d.file_conflicts(proj, fm.sessions_of({"files": ["bridge/x.py"]}), other)   # 자기 계획은 빼고 본다
        assert ov == []
    _db(go)
