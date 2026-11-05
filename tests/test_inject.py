"""3단계 입력 주입 — tmux · 프로세스를 가짜로 바꿔 거부 규칙과 제출 확인을 본다(실제 CC 실측은 log/stage3)."""

import json

import pytest

import bridge.inject as inj
from bridge.liveness import LiveSession

SID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def test_guarded():
    assert inj.guarded("/compact") == (" /compact", True)
    assert inj.guarded("/compact", command=True) == ("/compact", False)
    assert inj.guarded("!rm -rf x", command=True) == (" !rm -rf x", True)   # '!'는 언제나 막는다
    assert inj.guarded("@file 봐줘") == ("@file 봐줘", False)
    assert inj.guarded("보통 입력") == ("보통 입력", False)


def _write(path, *objs):
    with open(path, "w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n")


def test_find_delivery_wrapped_paste_and_tabs(tmp_path):
    p = tmp_path / "t.jsonl"
    sent = "a\n\tb `x` \\ 한글"
    wrapped = '\n\n<pasted_content id="6bfc">\n' + sent.replace("\t", "    ") + '\n</pasted_content id="6bfc">\n'
    _write(p, {"type": "user", "uuid": "u1", "promptId": "p1", "message": {"content": wrapped}})
    assert inj.find_delivery(str(p), 0, sent) == {"as": "prompt", "uuid": "u1", "prompt_id": "p1"}
    assert inj.find_delivery(str(p), 0, "다른 글") is None


def test_find_delivery_trailing_blank_lines_trimmed_by_cc(tmp_path):
    # 11-05 실측: 끝에 줄바꿈이 붙은 입력을 CC가 다듬어 기록 — 제출됐는데 "확인 안 됨"으로 떴다
    p = tmp_path / "t.jsonl"
    sent = "첫 줄\n\n둘째 줄\n\n"
    wrapped = '\n\n<pasted_content id="2c4f">\n첫 줄\n\n둘째 줄\n\n</pasted_content id="2c4f">\n'
    _write(p, {"type": "user", "uuid": "u1", "promptId": "p1", "message": {"content": wrapped}},
           {"type": "user", "uuid": "u2", "promptId": "p2", "message": {"content": "확인"}})
    assert inj.find_delivery(str(p), 0, sent)["uuid"] == "u1"
    assert inj.find_delivery(str(p), 0, "확인\n")["uuid"] == "u2"


async def test_deliver_refuses_blank(monkeypatch):
    for blank in ("", " ", "\n\n", " \t\n"):
        with pytest.raises(inj.Refused, match="빈 입력"):
            await inj.deliver(SID, blank, sessions_dir="/nonexistent", transcript=None)


def test_find_delivery_queue_and_offset(tmp_path):
    p = tmp_path / "t.jsonl"
    _write(p, {"type": "user", "uuid": "old", "promptId": "p0", "message": {"content": "바쁠 때"}})
    off = p.stat().st_size
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "queue-operation", "operation": "enqueue", "content": "바쁠 때"}) + "\n")
    assert inj.find_delivery(str(p), off, "바쁠 때") == {"as": "queued"}   # offset 앞의 같은 글은 세지 않는다


@pytest.fixture
def fake(monkeypatch):
    state = {"proc": "S", "cmd": "claude", "pane_pid": 100, "ancestors": [100], "tmux": ("/tmp/sock", "%1")}
    monkeypatch.setattr(inj, "live_sessions", lambda d: {SID: LiveSession(200, SID, "/x", state["proc"])})
    monkeypatch.setattr(inj, "_tmux_env", lambda pid: state["tmux"])
    monkeypatch.setattr(inj, "_ancestors", lambda pid: state["ancestors"])
    monkeypatch.setattr(inj, "_status", lambda d, pid: "idle")

    async def tmux(socket, *args, **kw):
        assert args[0] == "display-message", args   # resolve는 읽기만 한다
        return f"{state['cmd']}\t{state['pane_pid']}\t0\n"
    monkeypatch.setattr(inj, "tmux", tmux)
    return state


async def test_resolve_ok(fake):
    t, ls, busy = await inj.resolve(SID, "/s")
    assert (t.socket, t.pane, t.pid, busy) == ("/tmp/sock", "%1", 200, False)


@pytest.mark.parametrize("change, why", [
    ({"proc": "T"}, "SUSPENDED"),
    ({"tmux": None}, "tmux 밖"),
    ({"cmd": "bash"}, "claude가 아니다(bash)"),
    ({"pane_pid": 999, "ancestors": [100, 50]}, "이 세션의 프로세스가 아니다"),
])
async def test_resolve_refusals(fake, change, why):
    fake.update(change)
    with pytest.raises(inj.Refused, match=why.replace("(", r"\(").replace(")", r"\)")):
        await inj.resolve(SID, "/s")


async def test_resolve_dead(fake, monkeypatch):
    monkeypatch.setattr(inj, "live_sessions", lambda d: {})
    with pytest.raises(inj.Refused, match="살아 있는 CC 프로세스가 없다"):
        await inj.resolve(SID, "/s")


async def test_left_in_box(monkeypatch):
    t = inj.Target("/s", "%1", 1, SID)
    screens = {}

    async def fake_tmux(socket, *args, **kw):
        return screens["s"]
    monkeypatch.setattr(inj, "tmux", fake_tmux)
    screens["s"] = "● 답\n────\n❯ 기존 발볼 120켤레 검증 시작해라\n────\n  ⏵⏵ auto mode on"     # 회색 제안 — 보낸 글이 아니다
    assert await inj.left_in_box(t, "이미 들어가 있던 발볼 120켤레를 검증해라.\n\n190개") is False
    screens["s"] = "❯ 이미 들어가 있던 발볼 120켤레를\n  검증해라.\n────"
    assert await inj.left_in_box(t, "이미 들어가 있던 발볼 120켤레를 검증해라.") is True
    screens["s"] = "로딩 중"
    assert await inj.left_in_box(t, "아무거나") is None
