from pathlib import Path

from bridge.compactwatch import (CompactRules, context_level, context_message, context_pct, context_rule, level, load_rules,
                                 message, short_streak, window_over_message)
from bridge.model_choice import window_of

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


OPUS, SMALL = 1_000_000, 200_000


def test_repo_windows_and_pct_config():
    r = load_rules(REPO / "config" / "notify.toml")
    assert r.context_pct == (50, 75) and r.switch_min_pct == 40
    assert r.windows["opus"] == 1_000_000 and r.windows["sonnet"] == 200_000 and r.windows["haiku"] == 200_000
    assert window_of(r.windows, "claude-opus-5-5") == 1_000_000 and window_of(r.windows, "claude-haiku-5-5") == 200_000
    assert window_of(r.windows, "claude-mystery-9") is None and window_of(r.windows, None) is None


def test_pct_and_level_by_window():
    r = CompactRules()
    assert context_pct(380_000, OPUS) == 38 and context_pct(2_000_000, OPUS) == 100 and context_pct(5, None) is None
    # 1M 창: 토큰 문턱(300k=30% · 500k=50%)이 먼저 닿아 예전 동작 그대로
    assert [context_level(n, r, OPUS) for n in (299_999, 300_000, 500_000, 760_000)] == [None, "due", "late", "late"]
    # 200k 창: 300k는 도달 불가지만 비율로 100k=due, 150k=late
    assert [context_level(n, r, SMALL) for n in (99_999, 100_000, 149_999, 150_000)] == [None, "due", "due", "late"]
    # 창을 모르면 토큰 문턱만
    assert context_level(120_000, r, None) is None and context_level(300_000, r, None) == "due"


def test_pct_alert_comes_before_compaction():
    """압축 0번 세션이 비율 75%에 닿으면 압축(대개 80~90%) 전에 알림이 간다 — 창 200k: 150k에서 late."""
    r = CompactRules()
    assert context_rule(100_000, set(), r, SMALL) == "pct:50"
    assert context_rule(110_000, {"pct:50"}, r, SMALL) is None                 # 같은 단계는 한 번
    assert context_rule(160_000, {"pct:50"}, r, SMALL) == "pct:75"             # late는 또 한 번
    assert context_rule(170_000, {"pct:75"}, r, SMALL) is None
    assert context_rule(120_000, {"pct:75"}, r, SMALL) is None                 # 높은 단계를 보냈으면(줄었다 커져도) 안 보낸다
    # 토큰 문턱과 섞여도 단계 기준으로 한 번씩: 300k에서 ctx를 보냈으면 같은 due를 pct로 또 보내지 않는다
    assert context_rule(520_000, {"ctx:300000"}, r, OPUS) == "ctx:500000"
    assert context_rule(310_000, {"pct:50"}, r, OPUS) is None


def test_context_message_wording_with_pct_and_window_over():
    assert "쌓인 대화 439k(44%) · 응답당 약 $0.09" in context_message("[런슈즈]", "x", 439_000, "due", 0.0878, 44)
    m = window_over_message("[포먼]", "t", "claude-sonnet-5-5", 230_000, 200_000)
    assert "창 크기 값이 틀렸습니다" in m and "230k" in m and "200k" in m


def test_context_message_wording():
    m = context_message("[런슈즈]", "클러스터 이주", 439_000, "due", 0.0878)
    assert m.startswith("[런슈즈] 세션 「클러스터 이주」 지금까지 쌓인 대화 439k · 응답당 약 $0.09. 새 세션으로 옮길 때입니다.")
    assert "[새 세션으로 옮기기]" in m and "인계" not in m                     # 11-09 화면 말 통일
    assert "$" not in context_message("[포먼]", "x", 510_000, "late", None) and "늦었습니다" in context_message("[포먼]", "x", 510_000, "late", None)


def test_message_wording():
    m = message("[포먼]", "인계 2판", 2, "due", False)
    assert m.startswith("[포먼] 세션 「인계 2판」 압축 2번 — 넘어갈 때입니다.") and "[새 세션으로 옮기기]" in m
    m = message("[런슈즈]", "발볼", 4, "late", True)
    assert "늦었습니다" in m and "간격도 짧습니다" in m
