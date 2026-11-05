from pathlib import Path

from bridge.compactwatch import CompactRules, level, load_rules, message, short_streak

REPO = Path(__file__).resolve().parent.parent


def test_level_thresholds():
    r = CompactRules()
    assert [level(n, r) for n in range(6)] == [None, None, "due", "due", "late", "late"]


def test_short_streak_needs_two_short_gaps():
    r = CompactRules(short_turns=3)
    assert not short_streak([2], r)
    assert not short_streak([2, 8], r)
    assert short_streak([9, 3, 1], r)


def test_repo_config_and_missing_file(tmp_path):
    r = load_rules(REPO / "config" / "notify.toml")
    assert (r.due_at, r.late_at, r.notify_at) == (2, 4, (2, 4))
    assert load_rules(tmp_path / "없음.toml") == CompactRules()


def test_message_wording():
    m = message("[포먼]", "인계 2판", 2, "due", False)
    assert m.startswith("[포먼] 세션 「인계 2판」 압축 2번 — 넘어갈 때입니다.") and "인계 요약 받기" in m
    m = message("[런슈즈]", "발볼", 4, "late", True)
    assert "늦었습니다" in m and "간격도 짧습니다" in m
