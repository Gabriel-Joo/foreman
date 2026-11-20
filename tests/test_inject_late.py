"""제출 확인 못 함을 실패와 가르기(11-20 foreman-161, foreman-41). bridge/inject.deliver의 outcome과 늦게 다시 보기.

11-20 하루 20번 「주입 제출 확인 안 됨 … 입력 칸에 없다(제출된 것으로 보임)」였고, 글은 실제로 들어갔다(CC가 기록을
10초 넘게 늦게 썼다). 세션 692는 트랜스크립트 경로가 DB에 아직 없어 확인을 건너뛰고 바로 504였다. 가짜 tmux, 가짜 세션으로 본다.
"""

import asyncio
import json

import pytest

import bridge.inject as inj
from bridge import managers as mg
from bridge.api.sessions import input_http_status
from tests.test_managers import _mgrs

SID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
R = "─" * 80
EMPTY = f"지난 글\n\n{R}\n❯ \n{R}\n  ⏵⏵ auto mode on\n"


def _left(text):
    return f"지난 글\n\n{R}\n❯ {text}\n{R}\n  ⏵⏵ auto mode on\n"


def _fake(monkeypatch, screens):
    """clear_screen이 보는 첫 화면은 빈 입력 칸, 그 뒤(left_in_box)는 screens[1]. 보낸 tmux 명령을 모은다."""
    t = inj.Target("/s", "%8", 1, SID)
    sent, seen = [], [0]

    async def fake_resolve(session_id, sessions_dir):
        return t, None, False

    async def fake_tmux(socket, *args, **kw):
        if args[0] == "capture-pane":
            seen[0] += 1
            return screens[min(seen[0] - 1, len(screens) - 1)]
        sent.append(args)
        return ""
    monkeypatch.setattr(inj, "resolve", fake_resolve)
    monkeypatch.setattr(inj, "tmux", fake_tmux)
    monkeypatch.setattr(inj, "LATE_EVERY_S", 0.05)
    return sent


def _user_line(text, uuid="u1", prompt_id="p1"):
    return json.dumps({"type": "user", "uuid": uuid, "promptId": prompt_id, "message": {"role": "user", "content": text}},
                      ensure_ascii=False) + "\n"


async def _wait_check(cid, secs=3.0):
    for _ in range(int(secs / 0.05)):
        if inj.check_state(cid)["state"] != "checking":
            return inj.check_state(cid)
        await asyncio.sleep(0.05)
    raise AssertionError("늦게 다시 보기가 끝나지 않았다")


async def test_unconfirmed_then_found_late(monkeypatch, tmp_path):
    """기록이 늦게 쓰이는 경우. 10초(여기선 0.3초) 안에 못 찾고 입력 칸은 비었다 → unconfirmed, 202.
    그 뒤 기록이 쓰이면 늦게 다시 보기가 찾아 delivered로 바꾸고 on_late에 찾은 것을 넘긴다."""
    _fake(monkeypatch, [EMPTY, EMPTY])
    tr = tmp_path / "t.jsonl"
    tr.write_text(_user_line("앞서 들어간 같은 글", "u0"), encoding="utf-8")   # offset 앞의 같은 글은 세지 않는다
    got = []
    out = await inj.deliver(SID, "보낸 글", sessions_dir="/s", transcript=str(tr), verify_s=0.3, late_s=3.0,
                            on_late=got.append)
    assert out["outcome"] == "unconfirmed" and out["left_in_box"] is False and out["delivered"] is None
    assert inj.submitted(out) and input_http_status(out) == 202
    assert inj.check_state(out["check"])["state"] == "checking"
    with tr.open("a", encoding="utf-8") as f:
        f.write(_user_line("보낸 글"))
    c = await _wait_check(out["check"])
    assert c["state"] == "delivered" and c["delivered"]["uuid"] == "u1"
    # 찾은 것에는 걸린 초(waited_s)가 붙는다. 120초(LATE_S)를 맞출 근거다
    assert len(got) == 1 and {k: got[0][k] for k in ("as", "uuid", "prompt_id")} == {"as": "prompt", "uuid": "u1", "prompt_id": "p1"}
    assert isinstance(got[0]["waited_s"], float) and got[0]["waited_s"] == c["waited_s"]


async def test_unconfirmed_never_found(monkeypatch, tmp_path):
    """입력 칸은 비었는데 끝내 기록에 없다 → not_found, on_late(None). 실패를 늦게라도 알린다(조용히 넘어가지 않게)."""
    _fake(monkeypatch, [EMPTY, EMPTY])
    tr = tmp_path / "t.jsonl"
    tr.write_text("", encoding="utf-8")
    got = []
    out = await inj.deliver(SID, "보낸 글", sessions_dir="/s", transcript=str(tr), verify_s=0.3, late_s=0.3,
                            on_late=got.append)
    c = await _wait_check(out["check"])
    assert c["state"] == "not_found" and got == [None]


async def test_left_in_box_is_failure(monkeypatch, tmp_path):
    """입력 칸에 보낸 글이 그대로 남았다 → left, 504, 넣은 것으로 다루지 않는다."""
    _fake(monkeypatch, [EMPTY, _left("보낸 글이 입력 칸에 남았다")])
    tr = tmp_path / "t.jsonl"
    tr.write_text("", encoding="utf-8")
    out = await inj.deliver(SID, "보낸 글이 입력 칸에 남았다", sessions_dir="/s", transcript=str(tr), verify_s=0.3, late_s=0.2)
    assert out["outcome"] == "left" and not inj.submitted(out) and input_http_status(out) == 504
    assert (await _wait_check(out["check"]))["state"] == "not_found"


async def test_new_session_transcript_created_by_the_send(monkeypatch, tmp_path):
    """692 — 트랜스크립트 파일이 보낸 그 글로 처음 생긴다(보내기 전엔 없다). 파일이 생기면 그 글을 찾는다."""
    tr = tmp_path / "new.jsonl"
    _fake(monkeypatch, [EMPTY])

    async def paste(t, text, **kw):
        tr.write_text(_user_line(text), encoding="utf-8")
        return ["load-buffer", "paste-buffer -p -r", "Enter"]
    monkeypatch.setattr(inj, "paste_and_submit", paste)
    out = await inj.deliver(SID, "첫 글", sessions_dir="/s", transcript=str(tr), verify_s=1.0)
    assert out["outcome"] == "delivered" and out["delivered"]["uuid"] == "u1" and "check" not in out
    assert input_http_status(out) == 202


async def test_slash_command_not_watched(monkeypatch, tmp_path):
    """슬래시 명령은 기록 모양이 달라 끝내 못 맞춘다 — 늦게 다시 보지 않는다(헛된 「찾지 못함」 줄을 남기지 않게)."""
    _fake(monkeypatch, [EMPTY, EMPTY])
    tr = tmp_path / "t.jsonl"
    tr.write_text("", encoding="utf-8")
    out = await inj.deliver(SID, "/model sonnet", sessions_dir="/s", transcript=str(tr), command=True, verify_s=0.3)
    assert out["outcome"] == "unconfirmed" and "check" not in out


@pytest.mark.parametrize("res,code", [
    ({"delivered": {"as": "prompt"}, "outcome": "delivered"}, 202),
    ({"delivered": {"as": "queued"}, "outcome": "queued"}, 202),
    ({"delivered": None, "outcome": "unconfirmed"}, 202),
    ({"delivered": None, "outcome": "left"}, 504),
    ({"delivered": None, "outcome": "unknown"}, 504),
])
def test_http_status(res, code):
    assert input_http_status(res) == code


async def test_input_api_new_session_and_late_line(monkeypatch):
    """입력 API. DB에 트랜스크립트 경로가 없으면(새 세션 692) CC가 쓰는 자리로 확인하고, unconfirmed는 202에
    check 번호. 늦게 찾으면 「들어갔습니다」 활동 줄(input 이벤트, payload.late)을 남기고, 번호로 물으면 결과를 준다."""
    from types import SimpleNamespace

    from fastapi import HTTPException

    import bridge.api.sessions as api
    from bridge.handoff import transcript_path
    from bridge.models import EventStatus

    events, seen = [], {}
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(sessions_dir="/s", approval_config=None),
        pipeline=SimpleNamespace(submit=events.append))))

    async def row(request, session_id):
        return (692, SID, 7, None, "ronanlab-portfolio", "코더", "/r/portfolio")

    async def fake_deliver(cc, sent, **kw):
        seen.update(kw)
        return {"pane": "%1", "queued": False, "guarded": False, "delivered": None, "esc": 0, "dialog": None,
                "left_in_box": False, "outcome": "unconfirmed", "check": "c9"}

    async def turn_for_app(app, sid, delivered):
        return 55 if delivered else None
    monkeypatch.setattr(api, "_row", row)
    monkeypatch.setattr(api, "deliver", fake_deliver)
    monkeypatch.setattr(api, "_turn_for_app", turn_for_app)
    resp = await api.inject_input(692, api.InputIn(text="첫 글"), req)
    j = json.loads(resp.body)
    assert resp.status_code == 202 and j["verified"] is False and j["check"] == "c9"
    assert seen["transcript"] == transcript_path("/r/portfolio", SID)
    assert events[-1].status == EventStatus.WORKING and events[-1].payload["outcome"] == "unconfirmed"
    # 「늦게 확인:」 앞말은 화면이 payload.late로 붙인다(11-20). 걸린 시간은 payload.waited_s로 남는다(LATE_S를 맞출 근거)
    monkeypatch.setattr(api, "check_state", lambda cid: {"id": cid, "state": "delivered", "waited_s": 12.3})
    await seen["on_late"]({"as": "prompt", "uuid": "u1", "prompt_id": "p1", "waited_s": 12.3})
    ev = events[-1]
    assert ev.target.startswith("들어갔습니다: 첫 글") and ev.payload["late"] == "delivered"
    assert ev.payload["check"] == "c9" and ev.turn_id == 55 and ev.payload["waited_s"] == 12.3
    monkeypatch.setattr(api, "check_state", lambda cid: {"id": cid, "state": "not_found", "waited_s": 120.0})
    await seen["on_late"](None)
    assert events[-1].status == EventStatus.ERROR and events[-1].target.startswith("기록에서 찾지 못했습니다")
    assert events[-1].payload["waited_s"] == 120.0

    monkeypatch.setattr(api, "check_state", lambda cid: {"id": cid, "state": "delivered", "session": SID} if cid == "c9" else None)
    got = json.loads((await api.input_check(692, "c9", req)).body)
    assert got == {"id": "c9", "state": "delivered"}
    with pytest.raises(HTTPException):
        await api.input_check(692, "nope", req)


@pytest.mark.parametrize("outcome,now,late_found,marked", [
    ("delivered", True, None, ["now"]),          # 기록으로 확인 → 바로 넣음 기록(drift 함께)
    ("unconfirmed", False, True, ["late"]),     # 입력 칸은 비었고 늦게 찾음 → 그때 기록
    ("unconfirmed", False, False, []),          # 끝내 못 찾음 → 넣음으로 남기지 않는다
    ("left", False, None, []),                  # 입력 칸에 남음 → 넣음으로 남기지 않는다
])
async def test_plan_first_prompt_marks_after_confirm(monkeypatch, outcome, now, late_found, marked):
    """foreman-41 — 계획 카드로 띄운 세션의 넣음 기록은 제출을 확인한 뒤에, 받은 세션 패널 「바뀐 것」(drift)과 함께."""
    from bridge import handoff as h
    m = h.HandoffManager.__new__(h.HandoffManager)
    m.sessions_dir = "/s"
    got, state = [], {"stage": "now"}

    async def mark(summary_id, cc, drift):
        got.append((state["stage"], summary_id, drift))

    async def fake_deliver(cc, body, **kw):
        state["on_late"] = kw["on_late"]
        return {"delivered": {"as": "prompt"} if now else None, "queued": False, "outcome": outcome}
    m._mark_injected = mark
    monkeypatch.setattr(h, "deliver", fake_deliver)
    out = await m._send_first("cc1", "/r", "첫 글", 31, [{"path": "a.py"}])
    assert out["injected"] is (outcome != "left") and out["verified"] is now
    if outcome == "left":
        assert "남아 제출되지 않았습니다" in out["note"]
    state["stage"] = "late"
    if late_found is not None:
        r = state["on_late"]({"as": "prompt"} if late_found else None)
        if r is not None:
            await r
    assert [g[0] for g in got] == marked
    assert all(g[1:] == (31, [{"path": "a.py"}]) for g in got)


def test_manager_ask_unconfirmed_is_not_failure(monkeypatch):
    """관리자 부탁 — 입력 칸이 비었으면 넣은 것(텔레그램 「넣지 못했습니다」를 보내지 않는다). 늦게 봐도 없으면 그때 알린다."""
    m, actions, n = _mgrs()
    late = []

    async def fake_deliver(cc, msg, **kw):
        late.append(kw["on_late"])
        return {"delivered": None, "queued": False, "outcome": "unconfirmed", "left_in_box": False, "check": "c1"}
    monkeypatch.setattr(mg, "deliver", fake_deliver)
    out = asyncio.run(m.ask("foreman", "부탁", "runshoes"))
    assert out["delivered"] is True and out["verified"] is False and out["check"] == "c1"
    assert not n.sent and actions[-1]["o"] is True
    asyncio.run(late[0](None))
    assert n.sent and "기록에 남지 않았습니다" in n.sent[-1][2] and actions[-1]["o"] is False


def test_manager_relay_left_is_failure(monkeypatch):
    m, _, _ = _mgrs()

    async def fake_deliver(cc, msg, **kw):
        return {"delivered": None, "queued": False, "outcome": "left", "left_in_box": True, "check": "c2"}
    monkeypatch.setattr(mg, "deliver", fake_deliver)
    out = asyncio.run(m.relay("foreman", "report", 280, "세션 280", "끝"))
    assert out["delivered"] is False and "남아 제출되지 않았습니다" in out["reason"]
