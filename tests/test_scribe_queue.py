"""서기실 전체 줄(11-19 사용자, bridge/scribe_queue.py)과 줄 세션 합치기 가름(bridge/mergeprep.py _queue_verdict).

임시 git 저장소에 진짜 작업방(worktree)을 만들고 진짜 합치기 준비(MergePrep)와 합치기(wt.merge)를 쓴다. 줄 상태는 시험 DB(0035)에
둔다. 가짜는 세션 쪽뿐이다: 세션 띄우기는 작업방만 만들고, 「세션이 일함」은 그 작업방에 커밋하는 것으로, 세션이 끝남은 살아 있는
세션 목록을 비워 두는 것으로 본다. 실제 서기 세션은 띄우지 않는다(일감: 합친 뒤 관리자가 사용자와 정해 돌린다)."""

import asyncio
import random
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from bridge import mergeprep as mp
from bridge import scribe_queue as sq
from bridge import scribe_room as sr
from bridge import worktree as wt
from bridge.db.engine import make_engine
from bridge.inject import Refused

CC = "a" * 8 + "-0000-0000-0000-0000000000{:02d}"


def sh(cwd, *args, env=None):
    import os
    e = {**os.environ, **(env or {})}
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=e).stdout.strip()


@pytest.fixture(autouse=True)
def _no_squash_hook(monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """notion/ 원고 세 편(가, 나, 다). 셋 다 다루는 코드(bridge/a.py)가 읽은 커밋 뒤 fix로 바뀌었다(코드가 바뀐 편 셋)."""
    from bridge.manuscript import head_text
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    r = tmp_path / "proj"
    for d in ("notion", "bridge", "log", "config"):
        (r / d).mkdir(parents=True)
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"), sh(r, "config", "user.name", "t")
    (r / "bridge" / "a.py").write_text("0\n")
    (r / "log" / "old.md").write_text("옛 기록\n")
    sh(r, "add", "."), sh(r, "commit", "-qm", "feat: 처음")
    base = sh(r, "rev-parse", "--short", "HEAD")
    for slug, title in (("01_a", "가"), ("02_b", "나"), ("03_c", "다")):
        (r / "notion" / f"{slug}.md").write_text(head_text(["bridge/a.py"], base) + f"\n# {title}\n같이 쓰는 줄: 처음\n", encoding="utf-8")
    sh(r, "add", "."), sh(r, "commit", "-qm", "docs: 원고")
    (r / "bridge" / "a.py").write_text("1\n")
    sh(r, "add", "."), sh(r, "commit", "-qm", "fix: 코드 고침")
    return r


class _Pub:
    src = "notion/"


class FakeH:
    """ScribeQueue와 MergePrep이 부르는 HandoffManager 자리. 세션 띄우기는 진짜 작업방만 만든다."""

    def __init__(self, engine, repo, base_sid):
        self.engine, self.sessions_dir, self._tasks = engine, "/nonexistent", set()
        self.repo, self.next_sid = str(repo), base_sid
        self.sessions: dict[int, SimpleNamespace] = {}
        self.spawned: list[dict] = []
        self.acts: list[tuple] = []
        self.mergeprep = None
        self.scribe_queue = None

    async def spawn_new(self, repo, char, name, **kw):
        info = await wt.create(repo, "cc-sq")
        self.next_sid += 1
        sid = self.next_sid
        self.sessions[sid] = SimpleNamespace(id=sid, cc=CC.format(sid % 100), cwd=info["path"], title=name, project=kw.get("_project"))
        self.spawned.append({"sid": sid, "name": name, "path": info["path"], **kw})
        return {"session_id": sid, "tmux": "cc-x", "worktree": info}

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((sid, action, ok, detail))

    async def session(self, sid):
        return self.sessions.get(sid)

    async def _running_work(self, row, pid):
        return []

    async def worktree_act(self, row, act, end=False, title=None):
        name = wt.split(row.cwd)[1]
        if act == "merge":
            res = await wt.merge(self.repo, name, title=title, topic=row.title, sid=row.id)
        else:
            await wt.remove(self.repo, name, force=True)
            res = {"ok": True}
        if res.get("ok"):
            if self.scribe_queue is not None:
                self.scribe_queue.on_worktree(row.id, act, res)
            if self.mergeprep is not None:
                self.mergeprep.worktree_gone(row.id)
        return res


async def settle(*objs):
    """예약된 일(줄 알림, 카드 없이 합치기, 다음 편 띄우기)이 다 끝날 때까지."""
    for _ in range(100):
        await asyncio.sleep(0)
        ts = [t for o in objs for t in list(getattr(o, "_tasks", set())) if not t.done()]
        if not ts:
            return
        await asyncio.gather(*ts, return_exceptions=True)


class World:
    """한 시험의 줄, 합치기 준비, 가짜 세션."""

    def __init__(self, engine, repo, project, monkeypatch, human_paths=(), base_sid=None):
        self.engine, self.repo, self.project = engine, repo, project
        self.h = FakeH(engine, repo, base_sid or random.randint(10**8, 9 * 10**8))
        cfg = mp.MergePrepCfg(enabled=True, notify_ready=False, projects=[], human_always=mp.HumanAlways(paths=list(human_paths)))
        self.m = mp.MergePrep(self.h, cfg)
        self.h.mergeprep = self.m
        self.q = sq.ScribeQueue(self.h, publishers=lambda: {project: _Pub()})
        assert self.m.queue is self.q and self.h.scribe_queue is self.q
        self.check_bad: set[int] = set()
        self.replies: dict[int, str] = {}
        mon = monkeypatch

        async def cands(with_hidden=False):
            return [(s.id, s.cc, s.cwd, s.title, project, "scribe") for s in self.h.sessions.values() if Path(s.cwd).is_dir()]

        async def docs(repo_, base, branch, st):
            sid = next((s.id for s in self.h.sessions.values() if wt.split(s.cwd)[1] and branch.endswith(wt.split(s.cwd)[1])), None)
            if sid in self.check_bad:
                return {"docs": [], "check": {"total": 2, "new": 2, "old": 0, "lines": ["notion/x.md:3: 없는 편 참조"]}}
            return {"docs": [], "check": {"total": 0, "new": 0, "old": 0, "lines": []}}

        async def false(*a, **k):
            return False

        async def none(*a, **k):
            return None

        async def mgr(repo_):
            return ("e" * 8 + "-mgr", str(repo))

        async def deliver(cc, cwd, msg):
            return True

        async def reply(sid):
            return self.replies.get(sid, "")
        mon.setattr(self.m, "_candidates", cands)
        mon.setattr(self.m, "_docs", docs)
        mon.setattr(self.m, "_skipped", false)
        mon.setattr(self.m, "_asks", none)
        mon.setattr(self.m, "manager_of", mgr)
        mon.setattr(self.m, "_deliver", deliver)
        mon.setattr(self.m, "_notify", lambda *a, **k: None)
        mon.setattr(self.q, "_last_reply", reply)

    def sid_of(self, topic):
        return next(s["sid"] for s in self.h.spawned if s["scribe_task"].endswith(" " + topic))

    def path_of(self, sid):
        return Path(self.h.sessions[sid].cwd)

    def work(self, sid, files: dict[str, str], msg="docs: 원고 고침"):
        p = self.path_of(sid)
        for f, body in files.items():
            (p / f).parent.mkdir(parents=True, exist_ok=True)
            (p / f).write_text(body, encoding="utf-8")
        sh(p, "add", *files)
        sh(p, "commit", "-qm", msg)

    async def done(self, sid):
        """세션이 일을 마쳤다(끝남). 턴 끝처럼 합치기 준비가 그 세션을 본다."""
        await self.m.check_one(sid)
        await settle(self.h, self.q, self.m)

    async def items(self):
        v = await sq.view(self.engine, self.project)
        return v, {i["topic"]: i for i in v["items"]} if v else {}


@pytest.fixture
def world(migrated_db, repo, monkeypatch):
    """프로젝트 이름은 시험마다 새로(시험 DB는 한 pytest가 같이 쓴다). 가짜 세션 띄우기에 맞춰 dispatch 기록은 가로챈다."""
    from bridge import foreman
    project = f"sq{random.randint(10**6, 10**7)}"

    async def _no_rec(*a, **k):
        return None
    monkeypatch.setattr(foreman, "record_spawn", _no_rec)
    monkeypatch.setattr(mp, "live_sessions", lambda d: {})
    monkeypatch.setattr(sq, "live_sessions", lambda d: {})
    monkeypatch.setattr(sq, "START_GRACE_S", 0.0)

    def run(fn, **kw):
        async def go():
            eng = make_engine(migrated_db)
            try:
                async with eng.begin() as c:
                    await c.execute(text("INSERT INTO project (name, repo_path) VALUES (:n, :r)"), {"n": project, "r": str(repo)})
                w = World(eng, repo, project, monkeypatch, **kw)
                return await fn(w)
            finally:
                await eng.dispose()
        return asyncio.run(go())
    return run


def test_three_pieces_run_in_order_and_next_sees_previous_fix(world):
    """세 편이 차례로 돈다. 한 편이 main에 합쳐져야 다음 편이 뜨고, 다음 편 작업방은 앞 편이 고친 줄이 든 main에서 갈라진다
    (사용자가 「합쳐졌을 때 끝」을 고른 까닭). 원고 하나만 바뀐 편은 카드 없이 합쳐진다."""
    async def go(w):
        r = await w.q.begin(w.project, "techdoc")
        assert r["items"] == 3
        assert [s["scribe_task"] for s in w.h.spawned] == ["techdoc 01_a"]           # 한꺼번에 띄우지 않는다
        assert "줄로 띄운 세션" in w.h.spawned[0]["first_prompt"] and "사람이 정할 것" in w.h.spawned[0]["first_prompt"]
        s1 = w.sid_of("01_a")
        v, it = await w.items()
        assert v["state"] == "running" and it["01_a"]["state"] == "running" and it["02_b"]["state"] == "waiting"
        assert v["current"]["topic"] == "01_a" and v["current"]["session_id"] == s1
        w.work(s1, {"notion/01_a.md": "# 가\n같이 쓰는 줄: 1편이 고쳤다\n"})
        await w.done(s1)
        assert len(w.h.spawned) == 2
        s2 = w.sid_of("02_b")
        assert "1편이 고쳤다" in (w.path_of(s2) / "notion" / "01_a.md").read_text()   # 앞 편의 고침이 든 main 위
        assert "1편이 고쳤다" in (Path(w.repo) / "notion" / "01_a.md").read_text()
        w.work(s2, {"notion/02_b.md": "# 나\n2편\n"})
        await w.done(s2)
        s3 = w.sid_of("03_c")
        assert (w.path_of(s3) / "notion" / "02_b.md").read_text() == "# 나\n2편\n"
        w.work(s3, {"notion/03_c.md": "# 다\n3편\n"})
        await w.done(s3)
        v, it = await w.items()
        assert v["state"] == "done" and v["current"] is None
        assert [it[t]["state"] for t in ("01_a", "02_b", "03_c")] == ["merged"] * 3
        assert {it[t]["how"] for t in it} == {"auto"} and v["counts"]["auto"] == 3 and v["counts"]["card"] == 0
        # 합친 뒤 관리자에게 가는 「합치기」 알림은 조사 log 길과 같은 자리(_tell_manager)로, 승인 없이 합쳤다고 적는다
        assert any(a[1] == mp.ACT_MERGE and "줄의 원고라 승인 없이" in (a[3] or "") for a in w.h.acts)
    world(go)


def test_piece_and_log_auto_code_file_card_waits_then_merges(world):
    """원고와 log가 함께면 카드 없이 합친다. 코드 파일이 섞이면 카드로 가고, 줄은 그 카드가 합쳐질 때까지 기다린다."""
    async def go(w):
        await w.q.begin(w.project, "techdoc", ["01_a", "02_b"])
        s1 = w.sid_of("01_a")
        w.work(s1, {"notion/01_a.md": "# 가\n고침\n", "log/sq_01.md": "기록\n"})
        await w.done(s1)
        s2 = w.sid_of("02_b")
        _, it = await w.items()
        assert it["01_a"]["state"] == "merged" and it["01_a"]["how"] == "auto"
        w.work(s2, {"notion/02_b.md": "# 나\n고침\n", "bridge/a.py": "2\n"})
        await w.done(s2)
        c = w.m.cards[s2]
        assert c.status == "ready" and c.approver != mp.AUTO and c.queue_id
        v, it = await w.items()
        assert it["02_b"]["state"] == "running" and "bridge/a.py" in it["02_b"]["reason"] and v["state"] == "running"
        assert len(w.h.spawned) == 2
        r = await w.m.approve(s2, by="human")                     # 관리자(여기서는 사람)가 시험 뒤 카드로 합친다
        assert r["ok"]
        await settle(w.h, w.q, w.m)
        v, it = await w.items()
        assert it["02_b"]["state"] == "merged" and it["02_b"]["how"] == "card" and v["state"] == "done"
        assert v["counts"]["auto"] == 1 and v["counts"]["card"] == 1
    world(go)


def test_middle_failures_do_not_stop_the_line(world):
    """가운데 편이 커밋 없이 끝나도 남은 편이 돈다. 문서 점검 틀림, 카드 미룸도 실패로 넣고 넘어간다."""
    async def go(w):
        await w.q.begin(w.project, "techdoc")
        s1 = w.sid_of("01_a")
        w.check_bad.add(s1)
        w.work(s1, {"notion/01_a.md": "# 가\n틀린 참조\n"})
        await w.done(s1)                                            # 점검 틀림 → 실패, 카드는 남는다
        assert w.m.cards[s1].status == "ready" and w.m.cards[s1].approver != mp.AUTO
        s2 = w.sid_of("02_b")
        w.replies[s2] = "고칠 것이 없었다.\n\n## 사람이 정할 것\n- 나 편 제목을 바꿀지\n"
        await w.q.tick(w.project)                                   # 커밋 없이 끝남(살아 있는 세션 없음) → 실패, 작업방을 치운다
        await settle(w.h, w.q, w.m)
        assert not w.path_of(s2).exists()
        s3 = w.sid_of("03_c")
        w.work(s3, {"notion/03_c.md": "# 다\n고침\n", "bridge/a.py": "3\n"})
        await w.done(s3)
        await w.m.skip(s3)                                          # 카드를 미룸 → 실패
        await settle(w.h, w.q, w.m)
        v, it = await w.items()
        assert v["state"] == "done"
        assert it["01_a"]["state"] == "failed" and "문서 점검" in it["01_a"]["reason"]
        assert it["02_b"]["state"] == "failed" and "커밋 없이" in it["02_b"]["reason"]
        assert it["03_c"]["state"] == "failed" and "미뤘" in it["03_c"]["reason"]
        assert v["counts"]["failed"] == 3
        assert it["02_b"]["decisions"] == "- 나 편 제목을 바꿀지"     # 실패한 편의 판단거리도 모은다
    world(go)


def test_human_path_piece_is_held_and_line_moves_on(world):
    """사람 승인 파일을 건드린 편은 기다리지 않고 「미룬 것」. 카드는 사람 승인으로 남는다."""
    async def go(w):
        await w.q.begin(w.project, "techdoc", ["01_a", "02_b"])
        s1 = w.sid_of("01_a")
        w.work(s1, {"notion/01_a.md": "# 가\n고침\n", "config/x.toml": "a = 1\n"})
        await w.done(s1)
        c = w.m.cards[s1]
        assert c.approver == "human" and c.human_why and c.status == "ready"
        _, it = await w.items()
        assert it["01_a"]["state"] == "held" and "config/*.toml" in it["01_a"]["reason"]
        assert it["02_b"]["state"] == "running"                     # 줄은 기다리지 않는다
    world(go, human_paths=["config/*.toml"])


def test_manual_session_still_goes_to_card(world):
    """사람이 손으로 띄운 서기 세션은 원고 하나만 바뀌어도 지금처럼 카드(줄 가름을 쓰지 않는다)."""
    async def go(w):
        res = await sr.start(w.h, w.engine, w.project, "techdoc", "01_a", publishers={w.project: _Pub()})
        sid = res["session_id"]
        assert "줄로 띄운 세션" not in w.h.spawned[0]["first_prompt"]
        w.work(sid, {"notion/01_a.md": "# 가\n손으로\n"})
        await w.done(sid)
        c = w.m.cards[sid]
        assert c.status == "ready" and c.approver != mp.AUTO and not c.queue_id
        assert Path(w.path_of(sid)).exists()                         # 저절로 합치지 않았다
    world(go)


def test_pause_resume_and_decisions_shown_at_end(world):
    """멈추기는 지금 편이 끝나면 다음 편을 띄우지 않는다. 이어가면 다음 편. 판단거리는 줄이 끝날 때만 글까지 보인다."""
    async def go(w):
        await w.q.begin(w.project, "techdoc", ["01_a", "02_b"])
        v, _ = await w.items()
        await w.q.pause(v["id"])
        s1 = w.sid_of("01_a")
        w.replies[s1] = "고쳤다.\n\n## 사람이 정할 것\n1. 가 편을 둘로 나눌지\n"
        w.work(s1, {"notion/01_a.md": "# 가\n고침\n"})
        await w.done(s1)
        v, it = await w.items()
        assert v["state"] == "paused" and len(w.h.spawned) == 1 and it["01_a"]["state"] == "merged"
        assert it["01_a"]["has_decisions"] and "decisions" not in it["01_a"]          # 도는 동안은 수만
        await w.q.tick(w.project)
        assert len(w.h.spawned) == 1                                # 그물도 멈춘 줄을 넘기지 않는다
        with pytest.raises(Refused):
            await w.q.begin(w.project, "portfolio")                  # 한 프로젝트에 줄 하나(두 일이 한 벌)
        await w.q.resume(v["id"])
        s2 = w.sid_of("02_b")
        w.work(s2, {"notion/02_b.md": "# 나\n고침\n"})
        await w.done(s2)
        v, it = await w.items()
        assert v["state"] == "done" and v["counts"]["decisions"] == 1
        assert it["01_a"]["decisions"] == "1. 가 편을 둘로 나눌지" and it["02_b"]["decisions"] == ""
        await w.q.close(v["id"])
        assert await sq.view(w.engine, w.project) is None
    world(go)


def test_line_survives_bridge_restart(world, monkeypatch):
    """브리지가 다시 떠도(줄 객체를 새로 만들어도) DB의 줄이 이어진다. 내려가 있던 사이 합쳐진 편은 그물이 줍는다."""
    async def go(w):
        await w.q.begin(w.project, "techdoc", ["01_a", "02_b", "03_c"])
        s1 = w.sid_of("01_a")
        w.work(s1, {"notion/01_a.md": "# 가\n고침\n"})
        # 브리지가 내려가 있는 사이 사람이 밖에서 합쳤다(줄은 몰랐다)
        name = wt.split(w.h.sessions[s1].cwd)[1]
        await wt.merge(str(w.repo), name)
        async with w.engine.begin() as c:
            await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, 'wt-merge', 1, 'x')"), {"s": s1})
        # 다시 뜸: 새 합치기 준비와 새 줄(세션 자리는 그대로)
        old_sessions, old_spawned = w.h.sessions, w.h.spawned
        w2 = World(w.engine, w.repo, w.project, monkeypatch, base_sid=w.h.next_sid)
        w2.h.sessions, w2.h.spawned = old_sessions, old_spawned
        await w2.q.tick(w.project)
        await settle(w2.h, w2.q, w2.m)
        v, it = await w2.items()
        assert it["01_a"]["state"] == "merged" and it["01_a"]["how"] == "card" and it["02_b"]["state"] == "running"
        s2 = w2.sid_of("02_b")
        w2.work(s2, {"notion/02_b.md": "# 나\n고침\n"})
        await w2.done(s2)
        _, it = await w2.items()
        assert it["02_b"]["how"] == "auto" and it["03_c"]["state"] == "running"
    world(go)


def test_blocked_piece_fails_and_whole_open_refuses(world, monkeypatch):
    """같은 편이 이미 열려 있으면 그 편은 막힘 판정(blocked) 그대로 실패로 넣고 다음 편. 통째 쓰기가 열려 있으면 줄을 세우지 않는다."""
    async def go(w):
        real = sr.open_tasks

        async def opened(engine, project):
            return [{"session_id": 1, "task": "techdoc", "topic": "01_a", "title": "x", "files": sr.touches("techdoc", "01_a")}]
        monkeypatch.setattr(sr, "open_tasks", opened)
        await w.q.begin(w.project, "techdoc", ["01_a", "02_b"])
        _, it = await w.items()
        assert it["01_a"]["state"] == "failed" and "이미 열려" in it["01_a"]["reason"] and it["02_b"]["state"] == "running"

        async def whole(engine, project):
            return [{"session_id": 2, "task": "portfolio", "topic": None, "title": "x", "files": ["portfolio/"]}]
        monkeypatch.setattr(sr, "open_tasks", whole)
        monkeypatch.setattr(sr, "piece_task_ok", lambda *a: None)
        v, _ = await w.items()
        await w.q.pause(v["id"])
        await w.q.close(v["id"])
        with pytest.raises(Refused, match="통째 쓰기가 열려"):
            await w.q.begin(w.project, "portfolio")
        monkeypatch.setattr(sr, "open_tasks", real)
    world(go)


def test_stalled_piece_is_told_once(world, monkeypatch):
    """지금 편이 STALL_MIN분 넘게 안 끝나면 화면에 「오래 안 끝남」, 텔레그램은 편마다 한 번."""
    async def go(w):
        sent = []
        w.q.notifier = SimpleNamespace(rules=SimpleNamespace(for_project=lambda p: None),
                                       send_direct=lambda *a, **k: sent.append((a, k)))
        await w.q.begin(w.project, "techdoc", ["01_a"])
        async with w.engine.begin() as c:
            await c.execute(text("UPDATE scribe_queue_item SET started_at = UTC_TIMESTAMP(3) - INTERVAL 90 MINUTE "
                                 "WHERE session_id = :s"), {"s": w.sid_of("01_a")})
        s1 = w.sid_of("01_a")
        # 세션이 살아서 일하는 중(커밋 없음, 일을 마치지 않음)
        monkeypatch.setattr(sq, "live_sessions", lambda d: {w.h.sessions[s1].cc: SimpleNamespace(pid=1, state="S")})

        async def busy(*a):
            return None
        monkeypatch.setattr(w.m, "_done_live", busy)
        await w.q.tick(w.project)
        await w.q.tick(w.project)
        await settle(w.h, w.q, w.m)
        v, _ = await w.items()
        assert v["current"]["stalled"] and v["current"]["minutes"] >= 60
        assert len(sent) == 1 and "끝나지 않습니다" in sent[0][0][3]
    world(go)


# ── 순수 판정 ──
def test_piece_only_why():
    ch = lambda *ps: [{"status": s, "path": p} for s, p in ps]  # noqa: E731
    assert sq.piece_only_why(ch(("M", "notion/01_a.md")), "techdoc", "01_a", ["log/"]) is None
    assert sq.piece_only_why(ch(("M", "notion/01_a.md"), ("A", "log/x.md"), ("M", "log/y.md")), "techdoc", "01_a", ["log/"]) is None
    assert "bridge/a.py" in sq.piece_only_why(ch(("M", "notion/01_a.md"), ("M", "bridge/a.py")), "techdoc", "01_a", ["log/"])
    assert "notion/02_b.md" in sq.piece_only_why(ch(("M", "notion/01_a.md"), ("M", "notion/02_b.md")), "techdoc", "01_a", ["log/"])
    assert "지웠" in sq.piece_only_why(ch(("D", "notion/01_a.md")), "techdoc", "01_a", ["log/"])
    assert "바뀌지 않았" in sq.piece_only_why(ch(("A", "log/x.md")), "techdoc", "01_a", ["log/"])
    # 포트폴리오는 그 편 .md 하나. 그림(portfolio/img/)과 이름이 앞으로 겹치는 다른 편은 카드로
    assert sq.piece_only_why(ch(("M", "portfolio/01_room.md")), "portfolio", "01_room", ["log/"]) is None
    assert "portfolio/img/01_room_a.png" in sq.piece_only_why(ch(("M", "portfolio/01_room.md"), ("A", "portfolio/img/01_room_a.png")),
                                                              "portfolio", "01_room", ["log/"])
    assert sq.piece_only_why(ch(("M", "notion/10_scribe/03_e.md"), ("A", "records/a.md")), "techdoc", "10_scribe/03_e", ["records/"]) is None


def test_decisions_of():
    assert sq.decisions_of("") == ""
    assert sq.decisions_of("고쳤다. 정할 것 없음") == ""
    assert sq.decisions_of("본문\n\n## 사람이 정할 것\n- 하나\n- 둘\n\n## 확인 못 한 것\n- 셋") == "- 하나\n- 둘"
    assert sq.decisions_of("본문\n**사람이 정할 것**\n1. 하나") == "1. 하나"
    assert sq.decisions_of("본문\n## 사람이 정할 것\n없음") == ""


# ── 이틀 시계(11-19 사용자 덧붙임 1) ──
def _clock_repo(tmp_path):
    r = tmp_path / "clock"
    (r / "notion").mkdir(parents=True)
    sh(r, "init", "-q", "-b", "main"), sh(r, "config", "user.email", "t@t"), sh(r, "config", "user.name", "t")
    (r / "notion" / "01_a.md").write_text("# 가\n")
    sh(r, "add", "."), sh(r, "commit", "-qm", "docs: 처음", env={"GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"})
    (r / "notion" / "01_a.md").write_text("# 가\n편 하나 고침\n")
    sh(r, "add", "."), sh(r, "commit", "-qm", "docs: 편 고침", env={"GIT_COMMITTER_DATE": "2026-03-01T00:00:00Z"})
    return r


def test_techdoc_clock_restarts_only_on_whole_merge(migrated_db, tmp_path):
    """편 하나(편 목록, [갱신], 줄)를 합쳐도 시계가 다시 시작하지 않는다. 통째 쓰기를 합쳤을 때만. 통째 기록이 없으면 notion/ 커밋을
    보되 편 세션을 처음 띄운 때 앞의 커밋만(편 커밋이 시계를 당기지 않게)."""
    r = _clock_repo(tmp_path)
    project = f"ck{random.randint(10**6, 10**7)}"

    async def seed(c, pid, detail, start, merge):
        ch = (await c.execute(text("INSERT INTO `character` (project_id, name, current_role, status, kind, spawned_by) "
                                   "VALUES (:p, :n, 'scribe', 'IDLE', 'agent', 'user')"), {"p": pid, "n": f"c{random.randint(1, 10**9)}"})).lastrowid
        sid = (await c.execute(text("INSERT INTO character_session (character_id, type, role, wake_reason) VALUES (:c, 'agent', 'scribe', 'user')"),
                               {"c": ch})).lastrowid
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail, created_at) VALUES (:s, :a, 1, :d, :t)"),
                        {"s": sid, "a": sr.TASK_ACT, "d": detail, "t": start})
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail, created_at) VALUES (:s, 'wt-merge', 1, 'x', :t)"),
                        {"s": sid, "t": merge})

    async def go():
        eng = make_engine(migrated_db)
        try:
            async with eng.begin() as c:
                pid = (await c.execute(text("INSERT INTO project (name, repo_path) VALUES (:n, :r)"), {"n": project, "r": str(r)})).lastrowid
                await seed(c, pid, "techdoc 01_a", datetime(2026, 2, 1), datetime(2026, 3, 2))
            at, src = await sr.last_techdoc_merge(eng, project, str(r))
            assert (at, src) == (datetime(2026, 1, 1), "commit")     # 편 커밋(3-01)도, 편 합치기(3-02)도 아니다
            async with eng.begin() as c:
                await seed(c, pid, "techdoc", datetime(2026, 4, 1), datetime(2026, 4, 2))
                await seed(c, pid, "techdoc 01_a", datetime(2026, 5, 1), datetime(2026, 5, 2))
            at, src = await sr.last_techdoc_merge(eng, project, str(r))
            assert (at, src) == (datetime(2026, 4, 2), "merge")      # 통째 쓰기만 센다
        finally:
            await eng.dispose()
    asyncio.run(go())
