"""교장 계획으로 띄운 세션은 「확인을 기다려라」 없이 바로 시작한다(11-10 사용자 — 계획 카드에서 이미 봤다)."""
from bridge import handoff as h
from bridge.foreman import INSTRUCTIONS

V2 = "## 다음 할 일\n- x\n## 읽을 곳\n- `README.md` — 왜"


def test_dispatcher_prompt_has_no_wait_line():
    assert "시작하기 전에 사용자의 확인을 기다려라" not in INSTRUCTIONS
    assert "이해한 것을 5줄 안으로" not in INSTRUCTIONS
    assert "바로 시작" in INSTRUCTIONS


def test_dispatch_handoff_inject_starts_right_away():
    for body in (V2, "## 주의\n- x"):
        t = h.inject_prompt("abc123", "s", body, confirm=False)
        assert "확인을 기다려라" not in t and "5줄" not in t
        assert "바로 시작하라" in t
        assert t.startswith(h.IN_HEAD.format(r="abc123"))      # 인계 넣은 글로 알아보는 머리는 그대로


def test_plain_handoff_still_waits():
    # 새 세션으로 옮기기(계획 카드 없이 인계만) — 확인 단계는 그대로
    assert "확인을 기다려라" in h.inject_prompt("abc123", "s", V2)
    assert "확인을 기다려라" in h.inject_prompt("abc123", "s", "## 주의\n- x")
