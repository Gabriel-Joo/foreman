"""조사 세션 스스로 끝내기(11-15 사용자, bridge/inspector_close.py). 임시 git 저장소 + 가짜 HandoffManager(DB, tmux 없이).
mergeprep는 진짜를 쓰고(승인자 auto 카드, approve), DB를 읽는 자리만 바꾼다."""

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge import inspector_close as ic
from bridge import mergeprep as mp
from bridge import worktree as wt
from bridge.liveness import LiveSession
from bridge.managers import RELAY_REPORT

CC = "f" * 8 + "-0000-0000-0000-000000000009"


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(autouse=True)
def _no_squash_hook(monkeypatch):
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
    (r / "log").mkdir(); (r / "log" / "old.md").write_text("옛 기록\n")
    sh(r, "add", "."); sh(r, "commit", "-qm", "init")
    return r


class FakeH:
    """InspectorClose와 MergePrep이 부르는 HandoffManager 자리만."""
    def __init__(self, repo, cwd):
        self.engine, self.sessions_dir, self._tasks = None, "/nonexistent", set()
        self.repo, self.cwd = str(repo), cwd
        self.acts, self.merges, self.actions = [], [], []
        self.mergeprep = None
        self.live: dict = {}

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((action, ok, detail))

    async def session(self, sid):
        return SimpleNamespace(id=sid, cc=CC, cwd=self.cwd, title="조사 하나", project="foreman")

    async def _running_work(self, row, pid):
        return []

    async def action(self, row, act):
        self.actions.append(act)
        self.live.clear()                    # 끝남
        return {"ok": True}

    async def worktree_act(self, row, act, end=False, title=None):
        self.merges.append((act, end))
        if end:
            self.live.clear()
        name = wt.split(self.cwd)[1]
        if act == "merge":
            r = await wt.merge(self.repo, name, title=title, topic=row.title, sid=row.id)
        else:
            await wt.remove(self.repo, name, force=True)
            r = {"ok": True}
        if end:
            r["ended"] = {"tmux_closed": True}
        if r.get("ok") and self.mergeprep is not None:
            self.mergeprep.worktree_gone(row.id)
        return r


DONE = {"state": "S", "busy": False, "open_turn": False, "turn_id": 5, "last_turn": 5, "approval": False, "replied": True,
        "denied": False, "asks": None, "esc_q": None, "work": []}


def _mk(repo, monkeypatch, cwd=None, role="inspector", facts=None, asks=None):
    cwd = cwd or str(Path(wt.split(str(repo / ".worktrees" / "w"))[0]) / ".worktrees" / "w")
    h = FakeH(repo, cwd)
    h.live = {CC: LiveSession(1, CC, cwd, "S")}
    m = mp.MergePrep(h, mp.MergePrepCfg(enabled=True, notify_ready=False, projects=["foreman"]))
    h.mergeprep = m
    sent, notes = [], []

    async def deliver(cc, cwd_, msg):
        sent.append(msg)
        return True

    async def mgr(repo_):
        return ("e" * 8 + "-mgr", str(repo))

    async def skipped(sid, head):
        return False

    async def done_live(sid, cc, pid):
        return "보고 옴"

    async def asks_of(sid):
        return asks

    async def cands(with_hidden=False):
        return [(7, CC, cwd, "조사 하나", "foreman", role)]
    monkeypatch.setattr(m, "_asks", asks_of)
    monkeypatch.setattr(m, "_deliver", deliver)
    monkeypatch.setattr(m, "manager_of", mgr)
    monkeypatch.setattr(m, "_skipped", skipped)
    monkeypatch.setattr(m, "_done_live", done_live)
    monkeypatch.setattr(m, "_candidates", cands)
    monkeypatch.setattr(m, "_notify", lambda c, key, msg, **k: notes.append(msg))
    monkeypatch.setattr(mp, "live_sessions", lambda d: h.live)
    monkeypatch.setattr(ic, "live_sessions", lambda d: h.live)

    x = ic.InspectorClose(h, ic.InspectorCloseCfg(settle_s=0.0))
    assert m.auto is x

    async def who(sid):
        return {"role": role, "project": "foreman", "repo": str(repo), "cwd": cwd, "cc": CC, "title": "조사 하나"}

    async def fx(sid, turn_id, ls):
        return dict(facts or DONE)

    async def nothing(*a, **k):
        return True

    async def reply(sid):
        return "결과는 log/foreman-x.md에 적었습니다."
    monkeypatch.setattr(x, "_who", who)
    monkeypatch.setattr(x, "_facts", fx)
    monkeypatch.setattr(x, "_wait_relay", nothing)
    monkeypatch.setattr(x, "_postit_first", nothing)
    monkeypatch.setattr(x, "_last_reply", reply)
    monkeypatch.setattr(x, "_notify", lambda project, sid, key, msg: notes.append(msg))
    return x, m, h, sent, notes


async def _drain(h):
    while h._tasks:
        await asyncio.gather(*list(h._tasks))


async def _wt_with(repo, files):
    p = Path((await wt.create(str(repo), "w"))["path"])
    for f, body in files.items():
        (p / f).parent.mkdir(parents=True, exist_ok=True)
        (p / f).write_text(body)
    sh(p, "add", "."); sh(p, "commit", "-qm", "docs: 조사 결과")
    return p


# ── 순수 판정 ──
def test_finished_why():
    assert ic.finished_why(DONE) == (None, None)
    assert ic.finished_why(DONE | {"busy": True})[1] == ic.BUSY
    assert ic.finished_why(DONE | {"open_turn": True})[1] == ic.BUSY
    assert ic.finished_why(DONE | {"last_turn": 6})[0] == "그 뒤 새 턴이 시작됐습니다"
    assert ic.finished_why(DONE | {"approval": True})[0] == "승인 대기가 있습니다"
    assert ic.finished_why(DONE | {"replied": False})[1] == ic.BUSY
    assert ic.finished_why(DONE | {"work": ["셸: 시험"]})[1] == ic.BUSY
    assert ic.finished_why(DONE | {"state": "T"})[1] == ic.BUSY
    assert ic.finished_why(DONE | {"asks": {"tail": "어느 쪽으로 할까요?"}}) == ("묻는 말을 남겼습니다(답을 받아야 합니다)", ic.WAIT)
    assert ic.finished_why(DONE | {"esc_q": {"id": 1}})[1] == ic.WAIT
    assert ic.finished_why(DONE | {"denied": True})[1] == ic.WAIT
    assert ic.finished_why(DONE | {"turn_id": None, "last_turn": 9}) == (None, None)       # 그물(턴 모름)


def test_log_only_why():
    A = lambda p, s="A": {"path": p, "status": s, "old_mode": "0", "new_mode": "100644"}   # noqa: E731
    assert mp.log_only_why([A("log/x.md"), A("log/y.md")]) is None
    assert "밖" in mp.log_only_why([A("log/x.md"), A("bridge/a.py")])
    assert "고치거나 지웠습니다" in mp.log_only_why([A("log/old.md", "M")])
    assert "고치거나 지웠습니다" in mp.log_only_why([A("log/old.md", "D")])
    assert mp.log_only_why([]) == "바뀐 파일이 없습니다"


def test_load_defaults_and_off(tmp_path):
    assert ic.load(tmp_path / "none.toml") == ic.InspectorCloseCfg()
    (tmp_path / "h.toml").write_text("[merge_prep]\nenabled = true\n")
    c = ic.load(tmp_path / "h.toml")
    assert c.enabled and c.projects == ["foreman"]                            # 칸이 없으면 켜짐, foreman만
    (tmp_path / "off.toml").write_text("[inspector_close]\nenabled = false\n")
    assert ic.load(tmp_path / "off.toml").enabled is False
    (tmp_path / "bad.toml").write_text("[inspector_close]\nevery_s = 1\n")
    with pytest.raises(ValueError):
        ic.load(tmp_path / "bad.toml")


# ── 작업방 조사 ──
async def test_worktree_log_only_merges_ends_and_removes(repo, monkeypatch):
    p = await _wt_with(repo, {"log/foreman-w_x.md": "조사 결과\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    x.on_turn_closed(7, 5, "stop", "hook")
    await _drain(x)
    await _drain(h)
    card = m.cards[7]
    assert card.approver == mp.AUTO and card.status == "merged" and card.approved_by == mp.AUTO and card.auto_why is None
    assert h.merges == [("merge", True)] and not p.exists() and not h.live                  # 세션 끝, 작업방 지움
    assert (repo / "log" / "foreman-w_x.md").read_text() == "조사 결과\n"                   # log는 main에
    assert sh(repo, "branch", "--list", "cc/w") == ""
    assert len(sent) == 1 and sent[0].startswith("[FOREMAN 합치기] 조사 세션 7") and "log/foreman-w_x.md" in sent[0]
    assert "push는 관리자가 한다" in sent[0]
    assert ("insp-close", True, "작업방 조사, log 1개를 main에 합치고 끝냄") in h.acts
    assert "승인 auto" in [a for a in h.acts if a[0] == mp.ACT_CARD][0][2]
    assert not notes and x.health["closed"] == 1
    # 사람 화면 기준: auto 카드는 사람이 누를 것이 없다
    assert mp.MergePrep.human_card(mp.Card(**{**card.__dict__, "status": "ready"})) is False
    from bridge.api.dashboard import manager_card
    assert manager_card({"approver": "auto", "human_why": []}) and not manager_card({"approver": "auto", "human_why": ["x"]})


async def test_worktree_outside_log_keeps_card_and_alerts(repo, monkeypatch):
    p = await _wt_with(repo, {"log/foreman-w_x.md": "조사\n", "bridge/a.py": "x\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    r = await x.close(7, 5)
    assert r["closed"] is False and "log/ 밖 파일" in r["why"] and "bridge/a.py" in r["why"]
    card = m.cards[7]
    assert card.approver == "human" and card.status == "ready" and "bridge/a.py" in card.auto_why
    assert h.merges == [] and p.exists() and h.live                                          # 합치지도 끝내지도 않음
    assert len(notes) == 1 and "스스로 끝내고 합치지 않았습니다" in notes[0]                 # 조용히 묻히지 않게
    with pytest.raises(mp.Refused):
        await m.approve(7, by=mp.AUTO)                                                       # auto가 아닌 카드는 스스로 못 합친다


async def test_worktree_existing_log_edit_is_not_auto(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    (p / "log" / "old.md").write_text("다른 세션 기록을 고침\n"); sh(p, "commit", "-qam", "docs: 고침")
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    r = await x.close(7, 5)
    assert r["closed"] is False and "있던 log" in m.cards[7].auto_why and h.merges == []


async def test_worktree_conflict_is_not_auto(repo, monkeypatch):
    p = await _wt_with(repo, {"log/same.md": "작업방\n"})
    (repo / "log" / "same.md").write_text("main\n"); sh(repo, "add", "."); sh(repo, "commit", "-qm", "main 쪽")
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    r = await x.close(7, 5)
    assert r["closed"] is False and m.cards[7].auto_why.startswith("충돌") and h.merges == [] and p.exists()


async def test_worktree_no_commit_discards(repo, monkeypatch):
    p = Path((await wt.create(str(repo), "w"))["path"])
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    r = await x.close(7, 5)
    assert r == {"closed": True, "how": "discard"} and h.merges == [("discard", True)] and not p.exists()
    assert len(sent) == 1 and sent[0].startswith(RELAY_REPORT) and "커밋 없이" in sent[0]


async def test_worktree_dirty_is_kept_and_alerted(repo, monkeypatch):
    p = await _wt_with(repo, {"log/a.md": "a\n"})
    (p / "log" / "b.md").write_text("커밋 안 함\n")
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    r = await x.close(7, 5)
    assert r["closed"] is False and "커밋 안 된 변경 1개" in r["why"] and h.merges == [] and p.exists()
    assert len(notes) == 1 and len(sent) == 1 and sent[0].startswith("[FOREMAN 합치기, 조사 세션 끝내기]")
    assert ("insp-close", False) == h.acts[-1][:2]
    await x.close(7, 5)                                                                      # 다시 만나도 관리자에게는 한 번
    assert len(sent) == 1


async def test_question_turn_is_not_closed_and_auto_card_demoted(repo, monkeypatch):
    p = await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch, facts=DONE | {"esc_q": {"id": 3, "text": "어느 쪽?"}})
    card = await m.check_one(7)                                                              # mergeprep 턴 끝이 먼저 만든 auto 카드
    assert card.approver == mp.AUTO and not sent
    r = await x.close(7, 5)
    assert r == {"closed": False, "why": "사람 답을 기다립니다"} and h.merges == [] and p.exists() and h.live
    assert card.approver == "human" and card.auto_why == "사람 답을 기다립니다" and len(notes) == 1   # 지금처럼 카드로, 알림 한 번


async def test_asks_in_reply_is_not_auto(repo, monkeypatch):
    await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch, asks={"tail": "이대로 둘까요?"})
    card = await m.check_one(7)
    assert card.approver == "human" and card.auto_why == "세션이 묻는 말을 남겼습니다"


async def test_busy_is_not_closed_quietly(repo, monkeypatch):
    await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch, facts=DONE | {"last_turn": 6})
    r = await x.close(7, 5)
    assert r["closed"] is False and h.merges == [] and not notes and x.health["kept"] == 1   # 다음 턴 끝에서 다시 본다


async def test_ended_session_auto_card_picked_by_sweep(repo, monkeypatch):
    p = await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    h.live.clear()                                                                           # 사람이 먼저 끝냄
    card = await m.check_one(7)
    assert card.approver == mp.AUTO and card.live is False
    assert await x.sweep() == 1
    assert h.merges == [("merge", False)] and not p.exists() and m.cards[7].status == "merged"


# ── 원본 폴더 조사 ──
async def test_base_folder_inspector_only_exits(repo, monkeypatch):
    x, m, h, sent, notes = _mk(repo, monkeypatch, cwd=str(repo))
    head = sh(repo, "rev-parse", "HEAD")
    r = await x.close(7, 5)
    assert r == {"closed": True, "how": "exit"} and h.actions == ["exit"] and h.merges == []
    assert sh(repo, "rev-parse", "HEAD") == head                                             # push도 합치기도 없음
    assert len(sent) == 1 and sent[0].startswith(RELAY_REPORT + "세션 7 「조사 하나」(조사) → foreman 관리자]")
    assert "log/foreman-x.md" in sent[0]


async def test_base_folder_postit_is_read_before_exit(repo, monkeypatch):
    x, m, h, sent, notes = _mk(repo, monkeypatch, cwd=str(repo))
    order = []

    async def postit_first(sid):
        order.append("postit")
    orig = h.action

    async def action(row, act):
        order.append(act)
        return await orig(row, act)
    monkeypatch.setattr(x, "_postit_first", postit_first)
    monkeypatch.setattr(h, "action", action)
    await x.close(7, 5)
    assert order == ["postit", "exit"]


async def test_postit_collect_reads_ended_session_transcript(tmp_path, monkeypatch):
    """끝난 세션 트랜스크립트도 읽힌다. collect는 트랜스크립트 파일만 읽고, 살아 있는지는 결과가 없을 때만 본다(bridge/postit.py)."""
    from bridge import postit
    t = tmp_path / "t.jsonl"
    import json
    body = f"<<<{postit.CHECK_TAG} r=r1>>>\n- p:1 | 끝남 | bridge/a.py:3 | 됨\n<<<END r=r1>>>"
    t.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": body}]}}) + "\n")
    from bridge import handoff as ho
    got = ho.assistant_text(str(t), 0)
    from bridge.promote import extract
    assert extract(got, postit.CHECK_TAG, "r1") is not None


async def test_base_folder_exit_failure_alerts(repo, monkeypatch):
    x, m, h, sent, notes = _mk(repo, monkeypatch, cwd=str(repo))

    async def bad(row, act):
        return {"ok": False, "note": "45초 안에 끝나지 않았습니다."}
    monkeypatch.setattr(h, "action", bad)
    r = await x.close(7, 5)
    assert r["closed"] is False and "끝내지 못했습니다" in r["why"] and len(notes) == 1 and len(sent) == 1


# ── 다른 역할 ──
@pytest.mark.parametrize("role", ["coder", "designer", "scribe", "manager"])
async def test_other_roles_untouched(repo, monkeypatch, role):
    p = await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch, role=role)
    r = await x.close(7, 5)
    assert r["closed"] is False and h.merges == [] and h.actions == [] and p.exists()
    card = await m.check_one(7)
    assert card.approver == "human" and card.auto_why is None                                 # 카드는 지금 그대로


async def test_other_project_untouched(repo, monkeypatch):
    await _wt_with(repo, {"log/a.md": "a\n"})
    x, m, h, sent, notes = _mk(repo, monkeypatch)
    x.cfg.projects = ["runshoes"]
    assert (await x.close(7, 5))["closed"] is False and h.merges == []
    assert (await m.check_one(7)).approver == "human"


async def test_failure_inside_close_is_not_silent(repo, monkeypatch):
    x, m, h, sent, notes = _mk(repo, monkeypatch)

    async def boom(sid):
        raise RuntimeError("DB 끊김")
    monkeypatch.setattr(x, "_who", boom)
    x.on_turn_closed(7, 5, "stop", "hook")
    await _drain(x)
    assert len(notes) == 1 and "DB 끊김" in notes[0] and x.health["fail"] == 1
