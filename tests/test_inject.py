"""3단계 입력 주입 — tmux · 프로세스를 가짜로 바꿔 거부 규칙과 제출 확인을 본다(실제 CC 실측은 log/stage3)."""

import json

import pytest

import bridge.inject as inj
from bridge.liveness import LiveSession

SID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def test_guarded():
    assert inj.guarded("/compact") == (" /compact", True)
    assert inj.guarded("/compact", command=True) == ("/compact", False)
    # 11-09 '!'도 command=True면 그대로(입력 API가 bang_check로 승인 규칙을 먼저 본다). 글로 보낼 때만 공백 보호
    assert inj.guarded("!ls -la", command=True) == ("!ls -la", False)
    assert inj.guarded("!ls -la") == (" !ls -la", True)
    assert inj.guarded("@file 봐줘") == ("@file 봐줘", False)
    assert inj.guarded("보통 입력") == ("보통 입력", False)


def test_bang_check():
    """11-09 — 공백이 든 명령은 보내고, 승인을 묻는 규칙 · sudo · 여러 줄 · 빈 명령만 막는다(이유와 할 일을 글로)."""
    from types import SimpleNamespace as NS
    allow = lambda t, i: NS(verdict="pass", rule="unmatched", reason="")              # noqa: E731
    ask = lambda t, i: NS(verdict="ask", rule="git-강제push", reason="되돌릴 수 없는 명령")  # noqa: E731
    assert inj.bang_check("!  bash ~/x/dump.sh --apply ", allow) == "!bash ~/x/dump.sh --apply"
    for bad, why in [("!git push --force", "승인 규칙 'git-강제push'"), ("!sudo systemctl restart x", "sudo"),
                     ("!echo a\necho b", "한 줄"), ("!   ", "명령이 없습니다")]:
        try:
            inj.bang_check(bad, ask if "push" in bad else allow)
            raise AssertionError(bad)
        except inj.Refused as e:
            assert why in str(e), (bad, str(e))


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
    ({"proc": "T"}, "멈춘 세션"),
    ({"tmux": None}, "tmux 밖"),
    ({"cmd": "bash"}, "claude가 아니라 bash"),
    ({"pane_pid": 999, "ancestors": [100, 50]}, "이 세션이 아닙니다"),
])
async def test_resolve_refusals(fake, change, why):
    fake.update(change)
    with pytest.raises(inj.Refused, match=why.replace("(", r"\(").replace(")", r"\)")):
        await inj.resolve(SID, "/s")


async def test_resolve_dead(fake, monkeypatch):
    monkeypatch.setattr(inj, "live_sessions", lambda d: {})
    with pytest.raises(inj.Refused, match="살아 있는 CC 프로세스가 없습니다"):
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


MODAL = "Settings  Status  Config  Usage  Stats\nTotal cost: $102.85\n"
PROMPT = "● 답\n────\n❯ \n────\n  ⏵⏵ auto mode on"


def _overlay(monkeypatch, *, busy, closes_after):
    """입력 줄이 없는 화면 — Esc를 closes_after번 받으면 입력 줄이 돌아온다(None이면 안 닫힘). 보낸 tmux 명령을 모은다."""
    t = inj.Target("/s", "%8", 1, SID)
    sent: list[tuple] = []

    async def fake_resolve(session_id, sessions_dir):
        return t, None, busy

    async def fake_tmux(socket, *args, **kw):
        if args[0] == "capture-pane":
            escs = sum(1 for a in sent if a[-1] == "Escape")
            return PROMPT if closes_after is not None and escs >= closes_after else MODAL
        sent.append(args)
        return ""
    monkeypatch.setattr(inj, "resolve", fake_resolve)
    monkeypatch.setattr(inj, "tmux", fake_tmux)
    monkeypatch.setattr(inj, "ESC_WAIT_S", 0)
    return sent


async def test_deliver_escapes_overlay_then_sends(monkeypatch):
    """11-09 사용자: 설정 화면에 입력이 막히는 게 반복된다 — Esc를 보내 닫고 보낸다(끝내기와 같게)."""
    sent = _overlay(monkeypatch, busy=False, closes_after=2)
    out = await inj.deliver(SID, "슬래시 없는 글", sessions_dir="/s", transcript=None)
    assert out["esc"] == 2 and out["steps"][:2] == ["Escape", "Escape"]
    kinds = [a[0] if a[0] != "send-keys" else a[-1] for a in sent]
    assert kinds == ["Escape", "Escape", "load-buffer", "paste-buffer", "Enter"]   # Esc로 닫은 뒤에야 붙여넣는다


async def test_deliver_refuses_when_escape_does_not_help(monkeypatch):
    """Esc 3번에도 입력 줄이 안 돌아오면 붙여넣지 않고 알린다(글이 모달로 새지 않게 — 11-08)."""
    sent = _overlay(monkeypatch, busy=False, closes_after=None)
    with pytest.raises(inj.Refused, match="Esc를 3번 보내도 닫히지 않았습니다"):
        await inj.deliver(SID, "슬래시 없는 글", sessions_dir="/s", transcript=None)
    assert [a[-1] for a in sent] == ["Escape"] * 3      # 붙여넣지 않았다


async def test_deliver_no_escape_while_busy(monkeypatch):
    """작업 중이면 Esc를 보내지 않는다 — 작업이 끊기고, 승인 · 질문 창(busy)에서는 거부 · 취소가 된다."""
    sent = _overlay(monkeypatch, busy=True, closes_after=1)
    with pytest.raises(inj.Refused, match="작업 중이라 Esc를 보내지 않았습니다"):
        await inj.deliver(SID, "슬래시 없는 글", sessions_dir="/s", transcript=None)
    assert sent == []
