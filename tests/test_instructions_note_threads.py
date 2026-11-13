"""교장 지시문: 노트는 「진행 중인 일」 하나만 · 규칙 · 판단은 쌓지 않음 · 관리자 띄우기는 노트에 쓰지 않음 · 첫 글에 확인 기다리기 안 붙임
(11-13 사용자, log/note_threads_only_20261113.md). 교장(LLM)을 실제로 부르지는 않는다 — 지시문에 그 문장이 있는지만 본다."""
from bridge.foreman import INSTRUCTIONS


def _section(start_mark: str, end_mark: str) -> str:
    start = INSTRUCTIONS.index(start_mark)
    return INSTRUCTIONS[start:INSTRUCTIONS.index(end_mark, start)]


def _notes() -> str:
    return _section("9. note_updates", "10. sessions")


def test_only_threads_no_decision_kind():
    s = _notes()
    assert "쌓는 것은 하나뿐" in s and "진행 중인 일" in s
    assert "decision" not in INSTRUCTIONS                    # 칸 이름조차 꺼내지 않는다 — 꺼내면 쓴다
    assert "thread|decision" not in INSTRUCTIONS


def test_rules_and_design_decisions_not_stacked():
    s = _notes()
    assert "쌓지 마라: 규칙 · 금지 · 설계 결정 · 사람이 정한 판단" in s
    assert "CLAUDE.md · docs에 적게" in s                     # 오래 지킬 규칙은 세션이 문서로
    assert "'지켜야 할 것'에 넣는다" in s                     # 요청 글의 「사용자 지시」는 이번 첫 글로


def test_manager_spawn_not_in_notes():
    s = _notes()
    assert "관리자 띄우기는 진행 중인 일에 쓰지 않는다(관리자 자리는 /api/managers에 있다)" in s
    assert "그 일만 thread로" in s
    assert "관리자가 있다" not in INSTRUCTIONS


def test_first_prompt_no_wait_for_confirm():
    s = _section("6. first_prompt", "7. reasons")
    assert "이해한 것 N줄 말하고 확인 기다려라" in s and "붙이지 마라" in s
    assert "[계획 받기]에서 이미" in s and "세션은 받으면 바로 시작한다" in s
