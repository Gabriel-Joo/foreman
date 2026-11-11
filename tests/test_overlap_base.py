"""같은 파일 헛경보 고침 · 합칠 순서(11-11, 코더 C1) — 바탕(merge-base)에 이미 든 변경은 빼고, 브랜치끼리 겹침 · 충돌 · 순서."""

import asyncio
import subprocess
from datetime import datetime
from types import SimpleNamespace

from bridge.overlap import OverlapWatch, merge_order, real_changes


def _g(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


def _repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _g(r, "init", "-q", "-b", "main")
    _g(r, "config", "user.email", "t@t")
    _g(r, "config", "user.name", "t")
    for f in ("a.py", "b.py", "c.py"):
        (r / f).write_text("1\n2\n3\n")
    _g(r, "add", "-A")
    _g(r, "commit", "-qm", "init")
    return r


def test_real_changes_drops_what_is_already_in_base(tmp_path):
    """11-09 헛경보 재현 — 원본(main)이 a.py를 커밋한 뒤 worktree가 그 위에서 시작해 a.py를 또 고쳤다."""
    r = _repo(tmp_path)
    (r / "a.py").write_text("main\n2\n3\n")
    _g(r, "commit", "-qam", "main a")
    wt = tmp_path / "wt"
    _g(r, "worktree", "add", "-q", "-b", "cc/w", str(wt))
    (wt / "a.py").write_text("main\n2\nwt\n")                         # worktree는 커밋 안 한 채
    (r / "b.py").write_text("x\n")                                     # 둘 다 b.py를 커밋 안 한 채 고침 — 진짜 겹침
    (wt / "b.py").write_text("y\n")
    (wt / "new.py").write_text("n\n")
    a, b = asyncio.run(real_changes(str(r), str(wt)))
    assert "a.py" not in a and "a.py" in b and {"b.py"} <= a and {"b.py", "new.py"} <= b
    assert asyncio.run(real_changes(str(r), str(tmp_path / "없음"))) is None


def test_scan_files_skips_files_already_in_partner_base(tmp_path, monkeypatch):
    import bridge.liveness as lv
    t = datetime(2026, 11, 11, 8, 0)
    root = "/x/foreman"

    class P:
        state = "S"
    monkeypatch.setattr(lv, "live_sessions", lambda _d: {"cc-a": P(), "cc-b": P()})

    class Res:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class C:
        async def execute(self, q, *_a, **_k):
            s = str(q)
            if "FROM event e" in s:
                return Res([(1, f"{root}/a.py", t, root), (2, f"{root}/.worktrees/w/a.py", t, f"{root}/.worktrees/w"),
                            (1, f"{root}/b.py", t, root), (2, f"{root}/.worktrees/w/b.py", t, f"{root}/.worktrees/w")])
            if "FROM summary" in s:
                return Res([])
            return Res([(1, 7, "foreman", "main", "cc-a", root), (2, 7, "foreman", "w", "cc-b", f"{root}/.worktrees/w")])
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class N:
        def __init__(self): self.sent = []
        def send_direct(self, *a): self.sent.append(a)

    class Rules:
        def for_project(self, _p): return SimpleNamespace(prefix="[FOREMAN]")

    n = N()
    w = OverlapWatch(SimpleNamespace(connect=lambda: C()), n, Rules(), tmp_path / "없음.toml", tmp_path)

    async def changes(ca, cb):
        assert (ca, cb) == (root, f"{root}/.worktrees/w")
        return {"b.py"}, {"a.py", "b.py"}                              # a.py는 1이 커밋해 2의 바탕에 든 것
    w.git_changes = changes
    assert asyncio.run(w.scan_files(t)) == [(1, 2, ["b.py"])] and len(n.sent) == 1

    async def broken(ca, cb):
        return None                                                    # git을 못 읽으면 걸러내지 않는다
    w2 = OverlapWatch(SimpleNamespace(connect=lambda: C()), n, Rules(), tmp_path / "없음.toml", tmp_path)
    w2.git_changes = broken
    assert asyncio.run(w2.scan_files(t)) == [(1, 2, ["a.py", "b.py"])]


def test_merge_order_pairs_conflict_and_order(tmp_path):
    r = _repo(tmp_path)
    wts = []
    for name, f, body in (("a", "a.py", "A\n2\n3\n"), ("b", "a.py", "B\n2\n3\n"), ("c", "c.py", "C\n2\n3\n")):
        wt = tmp_path / f"wt-{name}"
        _g(r, "worktree", "add", "-q", "-b", f"cc/{name}", str(wt))
        (wt / f).write_text(body)
        _g(wt, "commit", "-qam", name)
        wts.append({"branch": f"cc/{name}", "cwd": str(wt), "session_id": None, "dispatch_id": None, "merge_order": None})
    (tmp_path / "wt-c" / "b.py").write_text("dirty\n")                 # c는 커밋 안 한 변경 하나
    out = asyncio.run(merge_order(str(r), wts))
    assert out["pairs"] == [{"a": "cc/a", "b": "cc/b", "files": ["a.py"], "conflict": True}]
    assert out["order"] == ["cc/c", "cc/a", "cc/b"]                    # 겹침 없는 c 먼저
    assert any("부딪칩니다" in x and "cc/b는" in x for x in out["reasons"])
    assert any("커밋 안 한 변경 1개" in x for x in out["reasons"]) and not out["errors"]
    # 같은 계획에서 사람이 정한 순서가 있으면 그것이 먼저
    wts[0].update(dispatch_id=9, merge_order=2)
    wts[1].update(dispatch_id=9, merge_order=1)
    assert asyncio.run(merge_order(str(r), wts))["order"][:2] == ["cc/b", "cc/a"]
