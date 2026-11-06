"""인계 검증(11-06) — 임시 저장소에서 r=690cec와 같은 상황을 만든다:
worktree 세션이 인계를 쓴 뒤 그 브랜치가 main에 합쳐지고 worktree가 없어지고, main에 커밋이 더 생기고, 잠금 주인이 바뀌었다."""

import subprocess
from pathlib import Path

from bridge import handoff_state as hs


def sh(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def commit(cwd, name, text, msg):
    (Path(cwd) / name).parent.mkdir(parents=True, exist_ok=True)
    (Path(cwd) / name).write_text(text, encoding="utf-8")
    sh(cwd, "add", name)
    sh(cwd, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)


class FakeLock:
    def __init__(self, cc):
        self.cc = cc

    def view(self):
        return {"foreman": {"cc": self.cc, "wt": None, "held": True}} if self.cc else {}


def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    commit(r, "docs/a.md", "a\n", "첫 커밋")
    return r


async def test_no_change_gives_no_lines(tmp_path):
    r = repo(tmp_path)
    st = await hs.snapshot(str(r), "foreman", FakeLock("65d05e2c-xx"))
    assert st["worktree"] is None and st["branch"] == "main" and st["base"] == "main" and st["lock"] == {"cc": "65d05e2c", "wt": None}
    assert await hs.drift(st, "foreman", FakeLock("65d05e2c-xx"), ["docs/a.md"]) == []
    assert hs.block([]) == ""


async def test_worktree_merged_and_gone_main_moved_lock_changed(tmp_path):
    r = repo(tmp_path)
    sh(r, "worktree", "add", "-q", "-b", "cc/foreman-2", str(r / ".worktrees" / "foreman-2"))
    w = r / ".worktrees" / "foreman-2"
    commit(w, "bridge/promote.py", "c\n", "인계 2판 c")
    st = await hs.snapshot(str(w), "foreman", FakeLock("65d05e2c"))
    assert st["worktree"] == "foreman-2" and st["branch"] == "cc/foreman-2" and st["repo"] == str(r)
    # 그 사이: 합치고 worktree를 지우고, main에 커밋이 더 생기고(읽을 곳 파일도 바뀜), 잠금이 다른 세션으로
    sh(r, "merge", "-q", "--ff-only", "cc/foreman-2")
    sh(r, "worktree", "remove", str(w))
    sh(r, "branch", "-q", "-d", "cc/foreman-2")
    commit(r, "docs/a.md", "a2\n", "d 잃은 것 보기")
    lines = await hs.drift(st, "foreman", FakeLock("1f9f5903"), ["docs/a.md", "bridge/promote.py"])
    text = "\n".join(lines)
    assert lines[0].startswith("인계를 쓴 지")
    assert "worktree `foreman-2`(브랜치 `cc/foreman-2`)는 지금 없습니다" in text and "`main`에 합쳐졌습니다" in text
    assert "`main`에 인계 뒤 커밋이 2개 생겼습니다" in text and "d 잃은 것 보기" in text   # 합친 c + d
    assert "`docs/a.md`" in text and "`bridge/promote.py`" in text
    assert "스키마 잠금이 세션 65d05e2c에서 세션 1f9f5903로 바뀌었습니다" in text
    b = hs.block(lines)
    assert b.startswith("## 인계 뒤 바뀐 것") and "다시 판단하라" in b


async def test_worktree_discarded_without_merge(tmp_path):
    r = repo(tmp_path)
    sh(r, "worktree", "add", "-q", "-b", "cc/x", str(r / ".worktrees" / "x"))
    w = r / ".worktrees" / "x"
    commit(w, "f.txt", "x\n", "버릴 일")
    st = await hs.snapshot(str(w), None)
    sh(r, "worktree", "remove", "--force", str(w))
    sh(r, "branch", "-q", "-D", "cc/x")
    text = "\n".join(await hs.drift(st, None))
    assert "`main`에 없습니다(합치지 않고 버렸을 수 있습니다)" in text


async def test_not_a_repo_and_missing_state(tmp_path):
    assert await hs.snapshot(str(tmp_path), "foreman") is None
    assert await hs.drift(None, "foreman") == []
    assert await hs.drift({"repo": str(tmp_path / "없음")}, None) == [f"인계 때 저장소 `{tmp_path / '없음'}`가 지금은 없습니다."]
