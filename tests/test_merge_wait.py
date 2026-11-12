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


def test_manager_cards_hidden_but_human_always_shown():
    """11-12(사용자) — 관리자가 승인하는 카드는 사람 막대 · 말풍선에서 뺀다. 늘-사람 카드 · 승인자가 사람인 카드는 그대로."""
    cards = [card(1, "ready") | {"approver": "manager", "human_why": []},
             card(2, "ready") | {"approver": "manager", "human_why": ["늘 사람 경로(config/*.toml): config/x.toml"]},
             card(3, "ready") | {"approver": "human", "human_why": []},
             card(4, "ready")]                                     # 옛 카드(칸 없음) — 사람
    assert set(merge_waits(fake(cards))) == {2, 3, 4}


async def test_hidden_card_still_listed_for_manager(tmp_path):
    """숨긴 카드도 관리자 API(GET /api/merge-prep?project=)에는 보인다 — view(project)는 approver로 거르지 않는다."""
    from bridge import mergeprep as mp
    m = mp.MergePrep(SimpleNamespace(engine=None, sessions_dir="/x", _tasks=set()), mp.MergePrepCfg(enabled=True))
    m.cards[1] = mp.Card(sid=1, title="t", project="foreman", role="coder", repo="/r", name="w", branch="cc/w", base="main",
                         head="h" * 40, base_head="b", live=False, why="", ahead=1, behind=0, commits=[], files=[], conflict=None,
                         docs=None, approver="manager", made_at="2026-11-12T00:00:00Z")
    assert merge_waits(m) == {}
    assert [c["sid"] for c in m.view("foreman")["cards"]] == [1] and m.view("runshoes")["cards"] == []
