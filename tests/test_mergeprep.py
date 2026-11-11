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
    assert d["docs"] == [{"where": "docs/11_x.md", "lines": [2], "count": 1, "files": ["bridge/mergeprep.py"]}]


def test_load_config(tmp_path):
    assert mp.load(tmp_path / "none.toml").enabled is False
    real = mp.load(Path(__file__).resolve().parent.parent / "config" / "handoff.toml")
    assert real.enabled is True and real.stage == 1 and real.projects == ["foreman"]   # 11-11 시험 세션 뒤 켬(fdc78f3) — FOREMAN만, 1단계
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
