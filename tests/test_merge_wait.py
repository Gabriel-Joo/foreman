"""합치기 기다림(11-11) — 대시보드가 세션마다 싣는 merge_wait. DB 없이 가짜 MergePrep으로."""

from types import SimpleNamespace

from bridge.api.dashboard import merge_waits


def card(sid, status, made_at="2026-11-11T10:00:00Z", asks=None):
    return {"sid": sid, "status": status, "made_at": made_at, "head8": "abcd1234", "files": ["a.py", "b.py"], "asks": asks}


def fake(cards, enabled=True):
    return SimpleNamespace(cfg=SimpleNamespace(enabled=enabled), view=lambda: {"cards": cards})


def test_only_ready_cards_wait():
    mp = fake([card(1, "ready"), card(2, "merging"), card(3, "merged"), card(4, "conflict_sent"), card(5, "failed")])
    assert set(merge_waits(mp)) == {1}
    assert merge_waits(mp)[1] == {"since": "2026-11-11T10:00:00Z", "head8": "abcd1234", "files": 2, "asks": False}


def test_asks_flag_and_off():
    assert merge_waits(fake([card(7, "ready", asks={"tail": "?"})]))[7]["asks"] is True
    assert merge_waits(fake([card(1, "ready")], enabled=False)) == {}
    assert merge_waits(None) == {}


def test_card_cleared_when_not_ready():
    """승인해 합치면(merged) 다음 대시보드 값에서 빠진다 — 말풍선 · 막대가 사라지는 근거."""
    cards = [card(1, "ready")]
    mp = fake(cards)
    assert 1 in merge_waits(mp)
    cards[0]["status"] = "merged"
    assert merge_waits(mp) == {}
