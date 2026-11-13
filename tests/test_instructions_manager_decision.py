"""교장 지시문: 관리자 띄우기는 thread가 아니라 decision(「X 관리자가 있다」)으로 쓴다(11-13 사용자, log/note_manager_decision_20261113.md).
교장(LLM)을 실제로 부르지는 않는다 — 지시문에 그 문장이 있는지만 본다."""
from bridge.foreman import INSTRUCTIONS


def _section() -> str:
    start = INSTRUCTIONS.index("9. note_updates")
    return INSTRUCTIONS[start:INSTRUCTIONS.index("10. sessions", start)]


def test_manager_spawn_is_decision_not_thread():
    s = _section()
    assert "역할 manager 세션을 띄우는 계획이면 thread를 쓰지 마라" in s
    assert "관리자가 있다(세션 N, 원본 폴더)" in s
    assert "관리자가 바뀌면" in s and "그 줄을 update" in s


def test_manager_spawn_with_other_work_keeps_thread_for_that_work_only():
    assert "그 X만 thread로 쓴다" in _section()
