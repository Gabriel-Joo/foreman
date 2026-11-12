"""합치기 준비(11-11 1물결 A 「하나」 · 「넷」, bridge/mergeprep.py) — 임시 git 저장소 + 가짜 HandoffManager(DB · tmux 없이)."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge import mergeprep as mp
from bridge import worktree as wt
from bridge.inject import Refused
from bridge.liveness import LiveSession

CC = "d" * 8 + "-0000-0000-0000-000000000004"


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


README = """# x

## 6. 로드맵

### 나중에 할 일 (정해 두고 미룬 것)

| 무엇 | 언제 · 조건 | 근거 |
|---|---|---|
| 합치기 승인 카드 만들기 — `bridge/mergeprep.py` | 1물결 | plan |
| 터미널 스크롤 고치기 | 나중 | x |
| 이름표 겹침 손보기(모눈 배치) | 모눈 뒤 | y |

## 7. 다음
| 무엇 | 언제 |
|---|---|
| 표 밖 mergeprep.py | z |
"""


@pytest.fixture(autouse=True)
def _no_squash_hook(monkeypatch):
    """MergePrep이 wt.SQUASH_OF를 넣는다 — 시험 사이에 남지 않게(monkeypatch가 끝에 되돌린다)."""
    monkeypatch.setattr(wt, "SQUASH_OF", None)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"); sh(r, "config", "user.name", "t")
    (r / "a.txt").write_text("one\n")
    (r / "README.md").write_text(README)
    (r / "docs").mkdir(); (r / "docs" / "11_x.md").write_text("설명\n`bridge/mergeprep.py`가 한다\n관계없음\n")
    sh(r, "add", "."); sh(r, "commit", "-qm", "init")
    return r


class FakeH:
    """MergePrep이 부르는 HandoffManager 자리만."""
    def __init__(self, repo, cwd):
        self.engine, self.sessions_dir, self._tasks = None, "/nonexistent", set()
        self.repo, self.cwd = str(repo), cwd
        self.acts, self.merges = [], []

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((action, ok, detail))

    async def session(self, sid):
        return SimpleNamespace(id=sid, cc=CC, cwd=self.cwd, title="t", project="proj")

    async def worktree_act(self, row, act, end=False):
        self.merges.append((act, end))
        r = await wt.merge(self.repo, wt.split(self.cwd)[1])
        if end:
            r["ended"] = {"tmux_closed": True}
        return r


def _mk(repo, monkeypatch, live=False, done="보고 옴"):
    p = Path(wt.split(str(repo / ".worktrees" / "w"))[0]) / ".worktrees" / "w"
    h = FakeH(repo, str(p))
    m = mp.MergePrep(h, mp.MergePrepCfg(enabled=True, notify_ready=False))
    sent = []

    async def deliver(cc, cwd, msg):
        sent.append((cc, msg))
        return True

    async def mgr(repo_):
        return ("e" * 8 + "-mgr", str(repo))

    async def skipped(sid, head):
        return False

    async def done_live(sid, cc, pid):
        return done

    async def no_asks(sid):
        return None
    monkeypatch.setattr(m, "_asks", no_asks)
    monkeypatch.setattr(m, "_deliver", deliver)
    monkeypatch.setattr(m, "manager_of", mgr)
    monkeypatch.setattr(m, "_skipped", skipped)
    monkeypatch.setattr(m, "_done_live", done_live)
    lv = {CC: LiveSession(1, CC, str(p), "S")} if live else {}
    monkeypatch.setattr(mp, "live_sessions", lambda d: lv)
    row = (7, CC, str(p), "일 하나", "proj", "coder")
    return m, h, sent, row, lv


# ── 순수 판정 ──
def test_parse_merge_tree():
    assert mp.parse_merge_tree(0, "abc123\n") is None
    assert mp.parse_merge_tree(1, "abc123\nb.txt\na.txt\na.txt\n") == ["a.txt", "b.txt"]
    with pytest.raises(Refused):
        mp.parse_merge_tree(128, "fatal: bad")


def test_doc_candidates_matches_files_and_words():
    rows = mp.readme_rows(README, "나중에 할 일")
    assert [no for no, _ in rows] == [9, 10, 11]                         # 표 밖(## 7.) · 머리 · 구분 줄은 뺀다
    d = mp.doc_candidates(README, "나중에 할 일", {"docs/11_x.md": "설명\n`bridge/mergeprep.py`가 한다\n관계없음\n"},
                          ["bridge/mergeprep.py", "tests/test_mergeprep.py"], ["모눈 배치로 이름표 겹침 없앰"])
    by = {x["line"]: x for x in d["readme"]}
    assert by[9]["files"] == ["bridge/mergeprep.py"]          # 경로가 표 줄에 있다(시험 파일의 줄기 mergeprep은 같은 앞 파일로 묶임)
    assert 11 in by and {"이름표", "겹침"} <= set(by[11]["words"])               # 커밋 글 낱말이 둘 넘게 겹친다
    assert 10 not in by                                                          # 상관없는 줄은 후보가 아니다
    assert d["readme"][0]["line"] == 9                                           # 파일이 걸린 줄이 앞
    assert d["docs"] == [{"where": "docs/11_x.md", "lines": [2], "count": 1, "files": ["bridge/mergeprep.py"], "stale": True}]


README2 = """### 나중에 할 일
| 무엇 | 언제 | 근거 |
|---|---|---|
| **「권한 거부」 표시가 꺼지지 않는다**: 거부 뒤 | 따로 | [기록](log/a.md) |
| **할 일 목록에서 바로 일을 시작**: 고르기 | 교장 뒤 | 받은 할 일 #8 |
| **근거 칸 기록**: 무엇 | 따로 | [기록](log/coder_x_20261111.md) |
| **낱말 둘만**: 카드 승인 | 따로 | x |
| **낱말 셋**: 카드 승인 화면 | 따로 | x |
"""


def test_doc_candidates_ranks_by_evidence():
    """11-11 2물결 「넷」 — 세션 기록 「README에서 뺄 줄」 > 근거 칸 기록 > 받은 할 일 번호 > 파일 > 낱말(셋 넘게만)."""
    logs = {"log/coder_x_20261111.md": "# 결과\n## README에서 뺄 줄(합칠 때)\n- 「「권한 거부」 표시가 꺼지지 않는다」 줄\n"
                                       "- 「없는 줄」이 있으면 그 줄\n## 다음\n- 「할 일 목록에서 바로 일을 시작」은 아님\n"}
    d = mp.doc_candidates(README2, "나중에 할 일", {"docs/x.md": "`bridge/a.py`\n"}, ["log/coder_x_20261111.md", "bridge/a.py"],
                          ["카드 승인 화면 — 받은 할 일 #8"], logs=logs)
    by = {x["line"]: x for x in d["readme"]}
    order = [x["line"] for x in d["readme"]]
    assert order[0] == 4 and by[4]["score"] >= 100 and "README에서 뺄 줄" in by[4]["why"][0]   # 다른 절의 「…」는 세지 않는다
    assert by[6]["score"] >= 50 and "근거 칸" in by[6]["why"][0]
    assert by[5]["score"] >= 40 and by[5]["why"] == ["받은 할 일 #8"]
    assert 7 not in by                                   # 낱말 둘로는 후보가 아니다
    assert by[8]["weak"] is True and not by[4]["weak"]  # 낱말 셋은 후보지만 약하다
    assert d["docs"][0]["stale"] is True
    assert mp.log_drop_lines(logs) == [("log/coder_x_20261111.md", "「권한 거부」 표시가 꺼지지 않는다"),
                                       ("log/coder_x_20261111.md", "없는 줄")]


def test_load_config(tmp_path):
    assert mp.load(tmp_path / "none.toml").enabled is False
    # 실제 config/handoff.toml 대신 시험용 파일을 읽는다(11-12 사용자 — 설정을 켜고 끌 때마다 시험이 깨지지 않게)
    (tmp_path / "on.toml").write_text('[merge_prep]\nenabled = true\nstage = 1\nprojects = ["foreman"]\n')
    real = mp.load(tmp_path / "on.toml")
    assert real.enabled is True and real.stage == 1 and real.projects == ["foreman"]
    (tmp_path / "min.toml").write_text("[merge_prep]\nenabled = true\n")
    dflt = mp.load(tmp_path / "min.toml")
    assert dflt.stage == 1 and dflt.projects == [] and dflt.every_s == 60 and dflt.stuck_min == 10      # 칸이 없으면 기본값
    (tmp_path / "bad.toml").write_text("[merge_prep]\nenabled = true\nevery_s = 1\n")
    with pytest.raises(ValueError):
        mp.load(tmp_path / "bad.toml")


# ── 카드 · 승인 ──
async def test_ended_clean_card_then_merge_tells_manager(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "bridge").mkdir(); (p / "bridge" / "mergeprep.py").write_text("x\n")
    sh(p, "add", "."); sh(p, "commit", "-qm", "합치기 승인 카드")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    card = await m.prep(row, {})
    assert card and card.conflict is None and card.ff and card.ahead == 1 and card.why == "세션이 끝났습니다"
    assert card.files == ["bridge/mergeprep.py"] and card.docs["readme"][0]["line"] == 9
    assert h.acts[0][0] == mp.ACT_CARD
    m.cards[7] = card
    assert await m.prep(row, {}) is card                                        # 같은 커밋이면 같은 카드(다시 알리지 않음)
    r = await m.approve(7)
    assert r["ok"] and r["status"] == "merged" and h.merges == [("merge", False)]   # 끝난 세션 — 끝내기 없이
    assert sh(repo, "log", "-1", "--format=%s") == "합치기 승인 카드" and not p.exists()
    assert len(sent) == 1 and sent[0][0].startswith("eeeeeeee") and "시험 · push" in sent[0][1] and r["manager_told"]


async def test_live_conflict_not_ended_sends_to_session(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "a.txt").write_text("wt\n"); sh(p, "commit", "-qam", "wt")
    (repo / "a.txt").write_text("main\n"); sh(repo, "commit", "-qam", "main")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True)
    card = await m.prep(row, lv)
    assert card.conflict == ["a.txt"] and card.live and not card.ff
    m.cards[7] = card
    r = await m.approve(7)
    assert not r["ok"] and r["status"] == "conflict_sent" and h.merges == []    # 끝내지도 합치지도 않는다
    assert sent[0][0] == CC and "git rebase main" in sent[0][1] and "push" in sent[0][1]
    assert p.is_dir()


async def test_ended_conflict_goes_to_manager(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "a.txt").write_text("wt\n"); sh(p, "commit", "-qam", "wt")
    (repo / "a.txt").write_text("main\n"); sh(repo, "commit", "-qam", "main")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    m.cards[7] = await m.prep(row, {})
    r = await m.approve(7)
    assert r["status"] == "conflict_manager" and r["manager_told"] and sent[0][0].startswith("eeeeeeee")


async def test_live_rebase_check_before_ending(repo, monkeypatch):
    """merge-tree는 깨끗한데(세 갈래로 보면 바뀐 것 없음) 커밋 하나씩 얹는 rebase는 충돌 — 살아 있으면 끝내기 전에 잡는다."""
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "a.txt").write_text("x\n"); sh(p, "commit", "-qam", "바꿈")
    (p / "a.txt").write_text("one\n"); sh(p, "commit", "-qam", "되돌림")
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    (repo / "a.txt").write_text("main\n"); sh(repo, "commit", "-qam", "main")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True)
    card = await m.prep(row, lv)
    assert card.conflict is None and card.behind == 1                            # merge-tree로는 깨끗
    m.cards[7] = card
    r = await m.approve(7)
    assert r["status"] == "conflict_sent" and r["card"]["conflict"] == ["a.txt"] and h.merges == []
    assert sh(repo, "worktree", "list").count("\n") == 1                         # 임시 worktree는 지웠다(원본 + w)


async def test_live_clean_behind_ends_and_rebases(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    (repo / "c.txt").write_text("c\n"); sh(repo, "add", "c.txt"); sh(repo, "commit", "-qm", "c")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True)
    m.cards[7] = await m.prep(row, lv)
    r = await m.approve(7)
    assert r["ok"] and h.merges == [("merge", True)]                             # 살아 있으면 끝내고 합침(end=True와 같은 길)
    assert sh(repo, "log", "--format=%s").splitlines()[:2] == ["b", "c"]
    assert "세션은 끝냈다" in sent[0][1] and "rebase" in sent[0][1]


async def test_new_commit_after_card_refuses(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    m.cards[7] = await m.prep(row, {})
    (p / "c.txt").write_text("c\n"); sh(p, "add", "c.txt"); sh(p, "commit", "-qm", "c")
    with pytest.raises(Refused, match="커밋이 더 생겼습니다"):
        await m.approve(7)
    assert 7 not in m.cards and h.merges == [] and p.is_dir()


async def test_not_done_no_card_and_check_cleans(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True, done=None)
    assert await m.prep(row, lv) is None                                         # 일하는 중 · 묻는 중이면 카드 없음

    async def cands():
        return [row]
    monkeypatch.setattr(m, "_candidates", cands)

    async def done_live(sid, cc, pid):
        return "보고 옴"
    monkeypatch.setattr(m, "_done_live", done_live)
    assert await m.check() == 1 and m.cards[7].status == "ready"
    (p / "d.txt").write_text("d\n")                                              # 다시 일함(커밋 안 한 변경)
    assert await m.check() == 0 and 7 not in m.cards
    assert m.health["ok"]


class _Res:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _Conn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, q, p=None):
        return _Res(None if "FROM turn" in str(q) else (1,))     # 열린 턴 없음 · 응답 있음


async def test_done_live_asks_is_still_done_but_denied_is_not(repo, monkeypatch):
    """11-11 D2 281 — 보고 끝 확인 부탁(답 기다림)이어도 일을 마친 것이다. 권한 거부로 멈춘 것은 아니다."""
    from bridge.api import dashboard
    h = FakeH(repo, str(repo / ".worktrees" / "w"))
    h.engine = SimpleNamespace(connect=lambda: _Conn())
    m = mp.MergePrep(h, mp.MergePrepCfg(enabled=True, notify_ready=False))       # 진짜 _done_live · _asks를 본다
    monkeypatch.setattr(mp, "_status", lambda d, pid: "idle")

    async def no_work(row, pid):
        return False
    h._running_work = no_work
    needs = {7: {"asks": {"at": "x", "tail": "한 번씩 확인해 주세요.", "event_id": 1}}}

    async def hn(c, ids):
        return needs
    monkeypatch.setattr(dashboard, "human_needs", hn)
    assert await m._done_live(7, CC, 1) == "보고 옴 — 일하지 않고 응답을 마쳤습니다"
    assert (await m._asks(7))["tail"] == "한 번씩 확인해 주세요."
    needs[7] = {"denied": {"tool": "Bash"}}
    assert await m._done_live(7, CC, 1) is None


async def test_asks_card_shows_question_and_updates_in_place(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True)
    asks = {"v": {"at": "x", "tail": "한 번씩 확인해 주세요.", "event_id": 1}}

    async def a(sid):
        return asks["v"]
    monkeypatch.setattr(m, "_asks", a)
    m.cfg.notify_ready = True
    notes = []
    monkeypatch.setattr(m, "_notify", lambda c, k, msg: notes.append(msg))

    async def cands():
        return [row]
    monkeypatch.setattr(m, "_candidates", cands)
    assert await m.check() == 1
    c = m.cards[7]
    assert c.status == "ready" and c.asks["tail"] == "한 번씩 확인해 주세요." and c.via == "sweep"
    assert "세션이 묻는 말이 있습니다 — 패널에서 답하십시오" in notes[0] and "묻는 말 있음" in h.acts[-1][2]
    changed = []
    m.on_change = lambda: changed.append(1)
    asks["v"] = None                                                            # 사람이 답 안 해도 됨 — 같은 카드, 표시만
    assert await m.check() == 1 and m.cards[7] is c and c.asks is None and changed and len(notes) == 1


async def test_turn_end_makes_card_without_sweep(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, lv = _mk(repo, monkeypatch, live=True)
    monkeypatch.setattr(mp, "TURN_END_DELAYS", (0.0, 0.0))

    async def cands():
        return [row, (8, "x", "/nope/.worktrees/z", "다른", "proj", "coder")]
    monkeypatch.setattr(m, "_candidates", cands)

    async def no_sweep():
        raise AssertionError("훑기를 부르면 안 된다")
    monkeypatch.setattr(m, "check", no_sweep)
    m.on_turn_closed(99, 1, "stop", "hook")                                     # worktree 세션이 아니면 아무것도 안 한다
    m.on_turn_closed(7, 1, "stop", "hook")
    import asyncio
    await asyncio.gather(*list(m._tasks))
    assert list(m.cards) == [7] and m.cards[7].via == "turn_end" and "턴 끝" in h.acts[-1][2]
    assert m.turn_end["ok"] == 4 and m.turn_end["fail"] == 0
    # 꺼져 있으면 예약하지 않는다
    m.cfg.enabled = False
    m.on_turn_closed(7, 2, "stop", "hook")
    assert not m._tasks


async def test_turn_end_failure_is_picked_up_by_sweep(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, lv = _mk(repo, monkeypatch)
    monkeypatch.setattr(mp, "TURN_END_DELAYS", (0.0,))
    calls = {"n": 0}

    async def cands():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("DB 막힘")
        return [row]
    monkeypatch.setattr(m, "_candidates", cands)
    m.on_turn_closed(7, 1, "stop", "hook")
    import asyncio
    await asyncio.gather(*list(m._tasks))
    assert not m.cards and m.turn_end["fail"] == 1 and "DB 막힘" in m.turn_end["error"]
    assert await m.check() == 1 and m.cards[7].via == "sweep"                   # 그물이 줍는다
    assert m.health["ok"] and m.health["turn_end"]["fail"] == 1                 # 실패 수는 health에 남는다


async def test_prep_failure_becomes_failed_card(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    m, h, sent, row, _ = _mk(repo, monkeypatch)

    async def cands():
        return [row]

    async def boom(*a, **k):
        raise RuntimeError("git 막힘")
    monkeypatch.setattr(m, "_candidates", cands)
    monkeypatch.setattr(m, "prep", boom)
    assert await m.check() == 1
    c = m.cards[7]
    assert c.status == "failed" and "git 막힘" in c.error
    with pytest.raises(Refused, match="준비가 실패한 카드"):
        await m.approve(7)
    assert p.is_dir()


# ── API ──
async def test_api_off_and_on(repo, monkeypatch):
    import httpx
    from fastapi import FastAPI

    from bridge.api import handoff as api
    from bridge.api.auth import require_api_token

    def app_of(mgr):
        a = FastAPI()
        a.include_router(api.router)
        a.dependency_overrides[require_api_token] = lambda: None
        a.state.handoff = mgr
        return a
    off = SimpleNamespace(mergeprep=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_of(off)), base_url="http://t") as c:
        assert (await c.get("/api/merge-prep")).json() == {"enabled": False, "cards": [], "health": None}
        r = await c.post("/api/sessions/7/merge-prep", json={"action": "merge"})
        assert r.status_code == 503 and "꺼져 있습니다" in r.json()["detail"]
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    m.cards[7] = await m.prep(row, {})
    on = SimpleNamespace(mergeprep=m)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_of(on)), base_url="http://t") as c:
        v = (await c.get("/api/merge-prep")).json()
        assert v["enabled"] and v["cards"][0]["sid"] == 7 and v["cards"][0]["ff"] is True
        assert (await c.post("/api/sessions/8/merge-prep", json={"action": "merge"})).status_code == 409   # 카드 없음 — 거부
        r = (await c.post("/api/sessions/7/merge-prep", json={"action": "merge"})).json()
        assert r["ok"] and r["status"] == "merged"


# ── 11-11 버리기 · 카드 밖 합치기 — 막대가 1분 훑기를 기다리지 않는다 ──
def test_worktree_gone_drops_waiting_card_but_not_merging(repo, monkeypatch):
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    for sid, st in ((1, "ready"), (2, "failed"), (3, "conflict_sent"), (4, "merging")):
        m.cards[sid] = SimpleNamespace(status=st)
    assert [m.worktree_gone(s) for s in (1, 2, 3, 4, 9)] == [True, True, True, False, False]
    assert list(m.cards) == [4]                       # 합치는 중 카드는 approve가 마저 쓴다


async def test_handoff_discard_and_outside_merge_clear_card_at_once(repo, monkeypatch):
    from bridge.handoff import HandoffManager
    for act in ("discard", "merge"):
        p = Path((await wt.create(str(repo), f"w{act}"))["path"])
        (p / f"{act}.txt").write_text("x\n"); sh(p, "add", "."); sh(p, "commit", "-qm", act)
        m, h, sent, row, _ = _mk(repo, monkeypatch)
        m.cards[7] = SimpleNamespace(status="ready")
        changes = []

        async def noop(*a, **k):
            return None

        async def not_scribe(sid):
            return None
        fake = SimpleNamespace(
            _wt_of=lambda r: wt.split(r.cwd), _guard_reused=noop, sessions_dir="/nonexistent", _role=not_scribe,
            schema=None, _stop_preview=noop, _retire_wt_characters=noop, _act=noop, on_change=lambda: changes.append(1),
            mergeprep=m)
        r = SimpleNamespace(id=7, cc=None, cwd=str(p), project="proj")
        res = await HandoffManager.worktree_act(fake, r, act)
        assert res["ok"] and 7 not in m.cards and changes == [1], act


# ── 11-12 승인자 · 늘 사람 · squash ──
HA = mp.HumanAlways(paths=["*values*.yaml", "config/*.toml", "CLAUDE.md", "*migrations/*"], resource_keys=["cpu", "memory", "replicas"],
                    history_words=["force push", "filter-branch"])


def test_load_per_project_and_human_always(tmp_path):
    (tmp_path / "a.toml").write_text(
        '[merge_prep]\nenabled = true\n[merge_prep.per_project.foreman]\napprover = "manager"\nsquash = true\nhuman_paths = ["docs/x.md"]\n'
        '[merge_prep.human_always]\npaths = ["config/*.toml"]\nresource_keys = ["cpu"]\n')
    c = mp.load(tmp_path / "a.toml")
    assert c.approver_of("foreman") == "manager" and c.rule("foreman").squash
    assert c.approver_of("runshoes") == "human" and not c.rule("runshoes").squash and c.approver_of(None) == "human"
    assert c.human_paths("foreman") == ["config/*.toml", "docs/x.md"] and c.human_paths("x") == ["config/*.toml"]
    assert c.human_always.deletions and c.human_always.submodules
    (tmp_path / "b.toml").write_text('[merge_prep]\n[merge_prep.per_project.x]\napprover = "robot"\n')
    with pytest.raises(ValueError, match="approver"):
        mp.load(tmp_path / "b.toml")


def test_config_without_project_rules_is_human_and_ff(tmp_path):
    """프로젝트 칸이 없으면 사람 승인 · ff, 칸이 있으면 그 값을 읽는다 — 실제 config/handoff.toml 대신 시험용 파일(11-12 사용자)."""
    (tmp_path / "a.toml").write_text(
        '[merge_prep]\nenabled = true\n[merge_prep.per_project.foreman]\napprover = "manager"\nsquash = true\n'
        '[merge_prep.per_project.ronanlab-infra]\napprover = "human"\nsquash = false\n'
        '[merge_prep.human_always]\npaths = ["config/*.toml"]\nresource_keys = ["cpu"]\nhistory_words = ["force push"]\n')
    c = mp.load(tmp_path / "a.toml")
    for p in ("ronanlab-infra", "runshoes", "petmint-rag-chatbot", "none"):           # 사람 · ff (칸이 없거나 human)
        assert c.approver_of(p) == "human" and not c.rule(p).squash
    assert c.approver_of("foreman") == "manager" and c.rule("foreman").squash         # 칸이 있으면 그 값
    assert c.human_always.paths and c.human_always.resource_keys and c.human_always.history_words


def test_human_reasons():
    ch = lambda s, p, m="100644": {"status": s, "path": p, "old_mode": m, "new_mode": m}   # noqa: E731
    assert mp.human_reasons([ch("M", "bridge/a.py")], "고침", "", HA.paths, HA) == []
    why = mp.human_reasons([ch("M", "config/handoff.toml"), ch("A", "migrations/0030_x.sql"), ch("M", "sub/CLAUDE.md"),
                            ch("M", "charts/app/values-prod.yaml"), ch("D", "old.txt"), ch("M", "vendor/lib", "160000"),
                            ch("M", "k8s/deploy.yaml")],
                           "정리\n\nforce push 했다", "diff --git a/k8s/deploy.yaml b/k8s/deploy.yaml\n--- a/k8s/deploy.yaml\n"
                           "+++ b/k8s/deploy.yaml\n@@ -3 +3 @@\n-  replicas: 1\n+  replicas: 3\n"
                           "diff --git a/charts/app/values-prod.yaml b/charts/app/values-prod.yaml\n+    cpu: 2\n", HA.paths, HA)
    s = "\n".join(why)
    for x in ("config/*.toml", "migrations/0030_x.sql", "sub/CLAUDE.md", "values-prod.yaml", "자원 크기(replicas): k8s/deploy.yaml",
              "지우기 — 파일 1개를 지움: old.txt", "다른 저장소(서브모듈) 바뀜: vendor/lib", "「force push」"):
        assert x in s, x
    assert "자원 크기(cpu)" not in s                    # 이미 경로로 걸린 파일은 두 번 적지 않는다
    off = mp.HumanAlways(paths=[], deletions=False, submodules=False)
    assert mp.human_reasons([ch("D", "old.txt"), ch("M", "v", "160000")], "", "", [], off) == []


def test_parse_raw():
    out = ":100644 100644 aaa bbb M\0a.txt\0:000000 100644 000 ccc A\0dir/b c.txt\0:160000 160000 d e M\0sub\0"
    assert mp.parse_raw(out) == [{"old_mode": "100644", "new_mode": "100644", "status": "M", "path": "a.txt"},
                                 {"old_mode": "000000", "new_mode": "100644", "status": "A", "path": "dir/b c.txt"},
                                 {"old_mode": "160000", "new_mode": "160000", "status": "M", "path": "sub"}]


def _mgr_mode(m, **rule):
    m.cfg.per_project["proj"] = mp.ProjectRule(approver="manager", **rule)
    m.cfg.human_always = HA


async def _drain(h):
    import asyncio
    while h._tasks:
        await asyncio.gather(*list(h._tasks))


async def test_manager_approver_card_tells_manager_and_manager_merges(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    _mgr_mode(m)
    card = await m.prep(row, {})
    await _drain(h)
    assert card.approver == "manager" and card.human_why == [] and card.manager_told is True
    assert "관리자가 승인합니다" in card.note and "승인 manager" in h.acts[0][2]
    assert len(sent) == 1 and '"by":"manager"' in sent[0][1] and "GET /api/merge-prep?project=proj" in sent[0][1]
    m.cards[7] = card
    r = await m.approve(7, by="manager")
    assert r["ok"] and card.approved_by == "manager" and "관리자 승인" in h.acts[-1][2]
    assert sent[-1][1].startswith("[FOREMAN 합치기] 관리자가 승인해")


async def test_manager_refused_for_human_cards(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "config").mkdir(); (p / "config" / "x.toml").write_text("a = 1\n")
    sh(p, "add", "."); sh(p, "commit", "-qm", "설정")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    # 승인자가 사람인 프로젝트 — 관리자는 승인 · 미루기 못 함, 관리자에게 카드 알림도 없다(지금 동작)
    card = await m.prep(row, {})
    await _drain(h)
    assert card.approver == "human" and card.human_why == [] and sent == [] and card.note is None
    m.cards[7] = card
    with pytest.raises(Refused, match="승인자는 사람"):
        await m.approve(7, by="manager")
    with pytest.raises(Refused, match="승인자는 사람"):
        await m.skip(7, by="manager")
    # 승인자가 관리자여도 늘-사람(config/*.toml)이면 사람 카드 — 까닭을 카드 · 관리자 글에
    _mgr_mode(m)
    del m.cards[7]
    card = await m.prep(row, {})
    await _drain(h)
    assert card.approver == "human" and "config/x.toml" in card.human_why[0] and "사람 승인 카드" in card.note
    assert len(sent) == 1 and "**사람 승인**" in sent[0][1] and "config/x.toml" in sent[0][1]
    m.cards[7] = card
    with pytest.raises(Refused, match="사람 승인입니다"):
        await m.approve(7, by="manager")
    assert p.is_dir()
    r = await m.approve(7)                                  # 사람은 된다
    assert r["ok"] and sent[-1][1].startswith("[FOREMAN 합치기] 사람이 승인해")


async def test_manager_mode_without_manager_is_human(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    _mgr_mode(m)

    async def nobody(repo_):
        return None
    monkeypatch.setattr(m, "manager_of", nobody)
    card = await m.prep(row, {})
    assert card.approver == "human" and "관리자 세션이 없어" in card.note and sent == []


async def test_merged_msg_docs_pick_follows_approver(repo, monkeypatch):
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    c = mp.Card(sid=7, title="t", project="proj", role="coder", repo=str(repo), name="w", branch="cc/w", base="main", head="h" * 40,
                base_head="b", live=False, why="", ahead=2, behind=0, commits=[], files=[], conflict=None,
                docs={"readme": [{"line": 9, "text": "x", "score": 10, "why": []}], "docs": []})
    assert "사람 승인 뒤" in m._merged_msg(c, {"merged": 2})
    _mgr_mode(m)
    c.approved_by = "manager"
    s = m._merged_msg(c, {"merged": 2, "squash": "abcdef123456"})
    assert "관리자가 골라 지운다" in s and "squash" in s and "abcdef12" in s and s.startswith("[FOREMAN 합치기] 관리자가")


async def test_squash_for_repo_reads_project_table(repo, monkeypatch):
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    assert await m.squash_for_repo(str(repo)) is False                   # 켠 프로젝트가 없으면 DB를 보지 않는다

    class Rows:
        def all(self):
            return [("proj", str(repo)), ("other", "/x")]

    class Cn(_Conn):
        async def execute(self, q, p=None):
            return Rows()

    class Eng:
        def connect(self):
            return Cn()
    m.engine = Eng()
    m.cfg.per_project["proj"] = mp.ProjectRule(squash=True)
    assert await m.squash_for_repo(str(repo)) is True and await m.squash_for_repo("/nowhere") is False
    assert wt.SQUASH_OF == m.squash_for_repo


async def test_api_project_filter_and_token_is_manager(repo, monkeypatch):
    import httpx
    from fastapi import FastAPI, Request

    from bridge.api import handoff as api
    from bridge.api.auth import require_api_token

    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    m, h, sent, row, _ = _mk(repo, monkeypatch)
    m.cards[7] = await m.prep(row, {})
    scope = {"v": None}

    def tok(request: Request):
        request.state.token_scope = scope["v"]
    a = FastAPI()
    a.include_router(api.router)
    a.dependency_overrides[require_api_token] = tok
    a.state.handoff = SimpleNamespace(mergeprep=m)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a), base_url="http://t") as c:
        assert [x["sid"] for x in (await c.get("/api/merge-prep?project=proj")).json()["cards"]] == [7]
        v = (await c.get("/api/merge-prep?project=other")).json()
        assert v["cards"] == [] and v["approver"] == "human" and v["squash"] is False
        scope["v"] = "proj"
        assert (await c.get("/api/merge-prep")).status_code == 403                       # 프로젝트 토큰은 ?project= 로만
        r = await c.post("/api/sessions/7/merge-prep", json={"action": "merge"})          # 토큰이면 by는 저절로 manager
        assert r.status_code == 409 and "승인자는 사람" in r.json()["refused"]
        scope["v"] = None
        r = (await c.post("/api/sessions/7/merge-prep", json={"action": "merge"})).json()
        assert r["ok"] and r["status"] == "merged"
