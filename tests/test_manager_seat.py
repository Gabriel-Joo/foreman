"""11-11 아홉 — 옮기기 · 새로 띄우기에서 역할 관리자는 늘 원본 폴더, 원본에 관리자가 이미 살아 있으면 거절. DB · tmux 없이."""

import os
from types import SimpleNamespace

import pytest

from bridge import handoff as h
from bridge.liveness import LiveSession

OLD, CODER, MGR = ("a" * 8 + "-0000-0000-0000-000000000001", "b" * 8 + "-0000-0000-0000-000000000002",
                   "c" * 8 + "-0000-0000-0000-000000000003")


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        ccs = set((params or {}).get("c") or [])
        rows = [r for r in self.rows if r[0] in ccs]
        return SimpleNamespace(all=lambda: rows)


class _Engine:
    """character_session (cc, id, role) 행만 돌려주는 가짜 — manager_conflict가 부르는 SELECT 하나."""
    def __init__(self, rows):
        self.rows = rows

    def connect(self):
        return _Conn(self.rows)


def _mgr(tmp_path, live, rows):
    repo = tmp_path / "foreman"
    (repo / ".worktrees" / "foreman-2").mkdir(parents=True)
    m = h.HandoffManager.__new__(h.HandoffManager)
    m.engine, m.sessions_dir = _Engine(rows), str(tmp_path / "s")
    m.project_of = lambda c: ("foreman" if str(c).startswith(str(repo)) else None, 1)
    h_live = {cc: LiveSession(1, cc, str(repo / sub) if sub else str(repo), "S") for cc, sub in live.items()}
    return m, repo, h_live


async def test_manager_never_worktree_and_conflict(tmp_path, monkeypatch):
    # 옛 관리자(OLD, 원본) · 코더(CODER, worktree)가 살아 있다 — 11-11에 관리자가 worktree로 간 모양
    m, repo, live = _mgr(tmp_path, {OLD: "", CODER: ".worktrees/foreman-2"},
                         [(OLD, 10, "manager"), (CODER, 11, "coder")])
    monkeypatch.setattr(h, "live_sessions", lambda d: live)
    assert m.will_worktree(str(repo), OLD) is True                  # 역할을 안 보면 — 코더가 살아 있어 worktree(옛 동작)
    assert m.will_worktree(str(repo), OLD, "coder") is True         # 코더 · 서기 · 디자이너는 지금 규칙 그대로
    assert m.will_worktree(str(repo), OLD, "manager") is False      # 관리자는 늘 원본 폴더
    assert m._live_in_base(str(repo)) == [OLD]                      # worktree 세션은 원본 폴더로 세지 않는다
    assert await m.manager_conflict(str(repo), OLD) is None         # 옮기기 — 옛 관리자는 세지 않는다
    why = await m.manager_conflict(str(repo))                       # 새로 띄우기 — 옛 관리자가 살아 있다
    assert why and "세션 10" in why and "이미 살아 있습니다" in why
    # worktree에 있는 관리자는 원본 자리를 막지 않는다(11-11에 잘못 뜬 관리자 등)
    m2, repo2, live2 = _mgr(tmp_path / "x", {CODER: ".worktrees/foreman-2"}, [(CODER, 11, "manager")])
    monkeypatch.setattr(h, "live_sessions", lambda d: live2)
    assert await m2.manager_conflict(str(repo2)) is None


async def test_manager_conflict_uses_latest_row(tmp_path, monkeypatch):
    """같은 cc의 행이 여럿이면 마지막 행의 역할 — 역할을 관리자에서 코더로 바꾼 세션은 막지 않는다."""
    m, repo, live = _mgr(tmp_path, {OLD: ""}, [(OLD, 10, "manager"), (OLD, 12, "coder")])
    monkeypatch.setattr(h, "live_sessions", lambda d: live)
    assert await m.manager_conflict(str(repo)) is None


async def test_spawn_new_manager_refusals(tmp_path, monkeypatch):
    m, repo, live = _mgr(tmp_path, {OLD: ""}, [(OLD, 10, "manager")])
    monkeypatch.setattr(h, "live_sessions", lambda d: live)
    m.models = SimpleNamespace(valid=lambda x: True, pick=lambda mo, r: mo)
    m.socket = "/nonexistent"

    async def no_tmux(*a, **k):
        raise AssertionError("거절해야 하는데 tmux까지 왔다")
    monkeypatch.setattr(h, "tmux", no_tmux)
    with pytest.raises(h.Refused, match="원본 폴더에서만"):          # worktree를 강제로 켜도 관리자는 안 된다
        await m.spawn_new(str(repo), None, None, role="manager", worktree=True)
    with pytest.raises(h.Refused, match="원본 폴더에서만"):          # worktree 폴더를 골라도
        await m.spawn_new(str(repo / ".worktrees" / "foreman-2"), None, None, role="manager")
    with pytest.raises(h.Refused, match="이미 살아 있습니다"):        # 원본에 관리자가 있다
        await m.spawn_new(str(repo), None, None, role="manager")
    # 옮기기(옛 관리자 제외)면 원본 폴더로 간다 — worktree를 만들지 않고 tmux로 넘어간다
    seen = {}

    async def fake_tmux(sock, *args):
        seen.setdefault("cmds", []).append(args)
        raise h.Refused("여기서 멈춤")
    monkeypatch.setattr(h, "tmux", fake_tmux)

    async def no_create(*a, **k):
        raise AssertionError("관리자인데 worktree를 만들었다")
    monkeypatch.setattr(h.wt, "create", no_create)
    with pytest.raises(h.Refused, match="여기서 멈춤"):
        await m.spawn_new(str(repo), None, None, role="manager", exclude_cc=OLD)
    assert seen["cmds"][0][0] == "list-sessions"
    assert os.path.isdir(repo)
