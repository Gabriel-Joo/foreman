from pathlib import Path

from bridge.compactwatch import (CompactRules, context_level, context_message, context_rule, level, load_rules, message,
                                 short_streak)

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
    assert r.context_at == (300_000, 500_000)
    assert load_rules(tmp_path / "없음.toml") == CompactRules()


def test_context_level_and_rule_once_per_threshold():
    r = CompactRules()
    assert [context_level(n, r) for n in (0, 299_999, 300_000, 499_999, 500_000)] == [None, None, "due", "due", "late"]
    assert context_rule(250_000, set(), r) is None
    assert context_rule(439_000, set(), r) == "ctx:300000"
    assert context_rule(450_000, {"ctx:300000"}, r) is None                  # 같은 문턱은 한 번
    assert context_rule(520_000, {"ctx:300000"}, r) == "ctx:500000"          # 다음 문턱은 또 한 번
    assert context_rule(520_000, {"ctx:500000"}, r) is None
    assert context_rule(350_000, {"ctx:500000", None}, r) is None            # 높은 것을 보냈으면(압축으로 줄었다 다시 커져도) 안 보낸다
    assert context_rule(600_000, set(), r) == "ctx:500000"                   # 한 번에 둘을 넘으면 높은 것 하나만


def test_context_message_wording():
    m = context_message("[런슈즈]", "클러스터 이주", 439_000, "due", 0.0878)
    assert m.startswith("[런슈즈] 세션 「클러스터 이주」 맥락 439k — 넘어갈 때입니다. 응답 하나에 맥락 읽기만 약 $0.09입니다.")
    assert "인계 요약 받기" in m
    assert "$" not in context_message("[포먼]", "x", 510_000, "late", None) and "늦었습니다" in context_message("[포먼]", "x", 510_000, "late", None)


def test_message_wording():
    m = message("[포먼]", "인계 2판", 2, "due", False)
    assert m.startswith("[포먼] 세션 「인계 2판」 압축 2번 — 넘어갈 때입니다.") and "인계 요약 받기" in m
    m = message("[런슈즈]", "발볼", 4, "late", True)
    assert "늦었습니다" in m and "간격도 짧습니다" in m
