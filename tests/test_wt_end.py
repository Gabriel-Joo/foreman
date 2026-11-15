"""끝내고 합치기 · 끝내고 버리기(11-06) — 끝내기 누르고 합치기를 또 찾아 눌러야 하던 것을 한 번에."""

import asyncio
from types import SimpleNamespace

import pytest

from bridge import handoff as h


def _mgr(monkeypatch, *, dirty, exit_ok=True):
    live = {"cc1": SimpleNamespace(pid=1, state="S")}
    calls = []
    m = h.HandoffManager(None, "/tmp/없음")

    async def status(repo, name):
        return {"dirty": list(dirty)}

    async def merge(repo, name, **kw):
        calls.append("merge")
        return {"ok": True, "note": "합쳤습니다."}

    async def remove(repo, name, force=False):
        calls.append("remove")

    async def action(row, act):
        calls.append(act)
        if exit_ok:
            live.clear()
        return {"ok": exit_ok, "tmux_closed": exit_ok, "note": None if exit_ok else "15초 안에 끝나지 않았습니다."}

    async def noop(*a, **k):
        return False

    monkeypatch.setattr(h, "live_sessions", lambda d: live)
    monkeypatch.setattr(h.wt, "status", status)
    monkeypatch.setattr(h.wt, "merge", merge)
    monkeypatch.setattr(h.wt, "remove", remove)
    m.action = action
    m._act = noop

    async def role(sid):
        return None                   # 서기가 아니다 — 12b 검토를 건너뛴다
    m._role = role
    m._stop_preview = noop
    row = SimpleNamespace(id=1, cc="cc1", cwd="/repo/.worktrees/scribe-1", project=None, title=None)
    return m, row, calls


def test_live_without_end_is_refused(monkeypatch):
    m, row, calls = _mgr(monkeypatch, dirty=[])
    with pytest.raises(h.Refused, match="끝내고 합치기"):
        asyncio.run(m.worktree_act(row, "merge"))
    assert calls == []


def test_end_merge_dirty_refuses_before_exit(monkeypatch):
    m, row, calls = _mgr(monkeypatch, dirty=["log/a.md", "docs/b.md"])
    with pytest.raises(h.Refused) as e:
        asyncio.run(m.worktree_act(row, "merge", end=True))
    assert "커밋 안 된 변경이 2개" in str(e.value) and "log/a.md" in str(e.value) and "끝내지 않았습니다" in str(e.value)
    assert calls == []                                   # 세션을 끝내지 않았다 — 그 세션에게 커밋을 시킬 수 있다


def test_end_merge_clean_exits_then_merges(monkeypatch):
    m, row, calls = _mgr(monkeypatch, dirty=[])
    r = asyncio.run(m.worktree_act(row, "merge", end=True))
    assert calls == ["exit", "merge"] and r["ok"] and r["ended"] == {"tmux_closed": True}


def test_end_exit_fails_no_merge(monkeypatch):
    m, row, calls = _mgr(monkeypatch, dirty=[], exit_ok=False)
    with pytest.raises(h.Refused, match="끝나지 않아"):
        asyncio.run(m.worktree_act(row, "merge", end=True))
    assert calls == ["exit"]


def test_end_discard_ignores_dirty(monkeypatch):
    m, row, calls = _mgr(monkeypatch, dirty=["x.md"])
    r = asyncio.run(m.worktree_act(row, "discard", end=True))
    assert calls == ["exit", "remove"] and r["ok"]


def test_rest_on_ended_session_points_to_branch_box(monkeypatch):
    """끝난 세션의 [쉬게 하기] 거부는 세 버튼이 있는 「브랜치 이름」 칸을 가리킨다(11-15, 전 「따로 작업」)."""
    m, row, calls = _mgr(monkeypatch, dirty=[])
    monkeypatch.setattr(h, "live_sessions", lambda d: {})
    with pytest.raises(h.Refused) as e:
        asyncio.run(m.rest(row))
    assert str(e.value) == "이미 끝난 세션입니다. 「브랜치 이름」 칸에서 [이어서], [합치기], [버리기]를 고릅니다"
    assert calls == []
