"""넣기 길 넷이 같은 판정(inject.submitted)을 쓴다(11-20 foreman-161 뒷일). 합치기 준비, 셸 패널, 문서로 옮기기, 인계.

전에는 이 길들이 delivered나 queued만 성공으로 보아, 입력 칸이 비었는데 기록만 늦은 것(unconfirmed)이 실패로 남고 헛된
텔레그램이 갔다. 이제 unconfirmed는 넣은 것으로 보고, 뒤에서 늦게 다시 봐도 끝내 기록에 없으면 실패로 남기고 알린다.
가짜 deliver로 본다(tmux도 다른 세션도 건드리지 않는다).
"""

import asyncio
from types import SimpleNamespace

import pytest

from bridge import handoff as ho
from bridge import mergeprep as mp
from bridge import promote as pr
from bridge import terminal as tm
from bridge.inject import Refused
from bridge.mask import Masker

UNCONFIRMED = {"delivered": None, "queued": False, "outcome": "unconfirmed", "left_in_box": False, "check": "c1"}
LEFT = {"delivered": None, "queued": False, "outcome": "left", "left_in_box": True, "check": "c2"}
DELIVERED = {"delivered": {"as": "prompt", "prompt_id": "p1"}, "queued": False, "outcome": "delivered"}
FOUND = {"as": "prompt", "uuid": "u1", "prompt_id": "p1", "waited_s": 7.5}


def _fake(res, seen):
    async def fake_deliver(cc, msg, **kw):
        seen.update(kw)
        return res
    return fake_deliver


# ── 합치기 준비 ───────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("res,ok", [(DELIVERED, True), (UNCONFIRMED, True), (LEFT, False)])
async def test_mergeprep_deliver_uses_submitted(monkeypatch, res, ok):
    m = mp.MergePrep.__new__(mp.MergePrep)
    m.sessions_dir = "/s"
    monkeypatch.setattr(mp, "deliver", _fake(res, {}))
    assert await m._deliver("aaaaaaaa-1", "/r", "알림") is ok


async def test_mergeprep_late_not_found_notifies_once_per_text(monkeypatch):
    m = mp.MergePrep.__new__(mp.MergePrep)
    m.sessions_dir = "/s"
    sent, seen = [], {}
    m._notify = lambda c, key, msg, check_db=True, later=None: sent.append((c, key, msg, later))
    monkeypatch.setattr(mp, "deliver", _fake(UNCONFIRMED, seen))
    assert await m._deliver("aaaaaaaa-1", "/r", "합치기 결과") is True
    seen["on_late"](FOUND)
    assert sent == []                                  # 늦게 찾았다 = 알릴 것 없다
    seen["on_late"](None)
    assert len(sent) == 1 and sent[0][0] is None and sent[0][1].startswith("mergeprep:late:aaaaaaaa:")
    assert "기록에 남지 않았습니다" in sent[0][2] and sent[0][3] is False   # 묶음 없이 바로


# ── 문서로 옮기기 ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("res,ok", [(DELIVERED, True), (UNCONFIRMED, True), (LEFT, False)])
async def test_promote_send_uses_submitted(monkeypatch, res, ok):
    p = pr.Promoter(SimpleNamespace(sessions_dir="/s"))

    async def fake_resolve(cc, sessions_dir):
        return None, None, False
    monkeypatch.setattr(pr, "resolve", fake_resolve)
    monkeypatch.setattr(pr, "deliver", _fake(res, {}))
    row = SimpleNamespace(cc="aaaaaaaa-1", transcript="/none/x.jsonl", cwd="/r")
    if ok:
        path, offset, prompt_id = await p._send(row, "목록 부탁")
        assert path == "/none/x.jsonl" and offset == 0
        assert prompt_id == ("p1" if res is DELIVERED else None)    # 못 찾았으면 없다. 기다림이 끝내 시간 초과로 알린다
    else:
        with pytest.raises(Refused, match="남아 제출되지 않았습니다"):
            await p._send(row, "목록 부탁")


# ── 인계 ──────────────────────────────────────────────────────────────────────────────────────────

def _handoff(monkeypatch, res, seen):
    h = ho.HandoffManager.__new__(ho.HandoffManager)
    h.sessions_dir = "/s"
    h.notes, h.finished, h.spawned = [], [], []

    async def false(_id):
        return False

    async def new_summary(*a, **k):
        return 7, "req7"

    async def finish(sid, status, *a):
        h.finished.append((sid, status, a[-1] if a else None))

    async def fake_resolve(cc, sessions_dir):
        return None, SimpleNamespace(pid=1), False

    def spawn(coro):
        coro.close()
        h.spawned.append(1)
    h._pending, h._promote_busy, h._new_summary, h._finish, h._spawn_task = false, false, new_summary, finish, spawn
    h._notify = lambda row, msg, kind="handoff", fail=False: h.notes.append((msg, fail))
    monkeypatch.setattr(ho, "resolve", fake_resolve)
    monkeypatch.setattr(ho, "deliver", _fake(res, seen))
    return h


@pytest.mark.parametrize("res,ok", [(DELIVERED, True), (UNCONFIRMED, True), (LEFT, False)])
async def test_handoff_request_live_uses_submitted(monkeypatch, res, ok):
    h = _handoff(monkeypatch, res, {})
    row = SimpleNamespace(id=1, cc="aaaaaaaa-1", transcript="/none/x.jsonl", cwd="/r")
    out = await h.request_live(row)
    assert (out["status"] == "requested") is ok
    assert bool(h.spawned) is ok
    if not ok:
        assert h.finished == [(7, "failed", "입력 칸에 글이 남아 제출되지 않았다")]


async def test_handoff_resend_reads_uses_submitted_and_notifies_late(monkeypatch):
    seen = {}
    h = _handoff(monkeypatch, UNCONFIRMED, seen)

    async def reads(row):
        return {"missing": ["docs/a.md"]}
    h.handoff_reads = reads
    row = SimpleNamespace(id=1, cc="aaaaaaaa-1", transcript="/none/x.jsonl", cwd="/r")
    out = await h.resend_reads(row)
    assert out["delivered"] is True and out["verified"] is False and out["outcome"] == "unconfirmed"
    seen["on_late"](FOUND)
    assert h.notes == []
    seen["on_late"](None)
    assert h.notes and h.notes[-1][1] is True and "기록에 남지 않았습니다" in h.notes[-1][0]


# ── 셸 패널 ───────────────────────────────────────────────────────────────────────────────────────

def _terminal(monkeypatch, res, seen):
    t = tm.TerminalManager.__new__(tm.TerminalManager)
    t.s = SimpleNamespace(sessions_dir="/s", terminal_output_lines=30)
    t.mask = Masker()
    t.recorded, t.published = [], []
    t.publish = t.published.append
    t.on_change = lambda: None
    t._record = lambda **kw: t.recorded.append(kw)

    async def capture(target=None):
        raise OSError("화면을 읽지 않는다")           # 출력은 없어도 된다(안내 글로 대신한다)

    async def session_target(sid):
        return "aaaaaaaa-1", "/none/x.jsonl"
    t._capture, t._session_target = capture, session_target
    monkeypatch.setattr(tm, "deliver", _fake(res, seen))
    monkeypatch.setattr(tm.asyncio, "sleep", lambda s: asyncio.sleep(0))
    return t


def _request():
    return tm.Request(id=3, session_id=9, turn_id=4, project="foreman", title="t", cmd="ls", fill="ls", left=0, others=[])


@pytest.mark.parametrize("res,ok,why", [(DELIVERED, True, None), (UNCONFIRMED, True, None), (LEFT, False, "남아 제출되지 않았다")])
async def test_terminal_result_uses_submitted(monkeypatch, res, ok, why):
    t = _terminal(monkeypatch, res, {})
    await t._send_result(_request(), "ls", "ls", 0)
    ev = t.recorded[-1]
    assert ev["payload"]["delivered"] is ok and t.published[-1]["ok"] is ok
    if why:
        assert why in ev["payload"]["refused"]


async def test_terminal_result_late_not_found_records_failure(monkeypatch):
    seen = {}
    t = _terminal(monkeypatch, UNCONFIRMED, seen)
    await t._send_result(_request(), "ls", "ls", 0)
    assert len(t.recorded) == 1 and t.recorded[0]["payload"]["delivered"] is True
    seen["on_late"](FOUND)
    assert len(t.recorded) == 1                          # 늦게 찾았으면 그대로
    seen["on_late"](None)
    ev = t.recorded[-1]
    assert len(t.recorded) == 2 and ev["payload"]["delivered"] is False and "기록에 없다" in ev["payload"]["refused"]
    assert t.published[-1]["ok"] is False and "전달 못 함" in t.published[-1]["msg"]
