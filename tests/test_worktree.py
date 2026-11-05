"""따로 작업(worktree) · 스키마 잠금(11-05) — 임시 git 저장소로."""

import subprocess
from pathlib import Path

import pytest

from bridge import worktree as wt
from bridge.inject import Refused
from bridge.schemalock import SchemaLock


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"); sh(r, "config", "user.name", "t")
    (r / "a.txt").write_text("one\n")
    (r / ".gitignore").write_text(".venv/\n.env*\n")
    (r / "web").mkdir(); (r / "web" / "index.js").write_text("x\n")     # 추적되는 파일이 있어야 worktree에 폴더가 생긴다
    sh(r, "add", "."); sh(r, "commit", "-qm", "init")
    (r / ".venv").mkdir(); (r / ".env.bridge").write_text("X=1\n")
    (r / "web" / "node_modules").mkdir()
    mem = wt.cc_project_dir(r) / "memory"
    mem.mkdir(parents=True); (mem / "MEMORY.md").write_text("- x\n")
    return r


async def test_create_links_and_status(repo):
    info = await wt.create(str(repo), "foreman-2")
    p = Path(info["path"])
    assert info["branch"] == "cc/foreman-2" and p == repo / ".worktrees" / "foreman-2"
    assert (p / ".venv").is_symlink() and (p / ".env.bridge").is_symlink() and (p / "web" / "node_modules").is_symlink()
    assert (wt.cc_project_dir(p) / "memory" / "MEMORY.md").read_text() == "- x\n"
    assert sh(repo, "status", "--porcelain") == ""          # .worktrees · 링크가 git에 안 보인다
    st = await wt.status(str(repo), "foreman-2")
    assert st["dirty"] == [] and st["ahead"] == 0
    again = await wt.create(str(repo), "foreman-2")
    assert again["name"] == "foreman-2-2"
    assert wt.split(str(p / "web")) == (str(repo), "foreman-2")


async def test_merge_rebases_and_cleans(repo):
    info = await wt.create(str(repo), "x")
    p = Path(info["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    (repo / "c.txt").write_text("c\n"); sh(repo, "add", "c.txt"); sh(repo, "commit", "-qm", "c")   # 원본이 앞서감
    (p / "d.txt").write_text("d\n")
    with pytest.raises(Refused):                            # 커밋 안 된 변경
        await wt.merge(str(repo), "x")
    (p / "d.txt").unlink()
    r = await wt.merge(str(repo), "x")
    assert r["ok"] and r["merged"] == 1
    assert sh(repo, "log", "--format=%s") .splitlines()[:2] == ["b", "c"]
    assert not p.exists() and "cc/x" not in sh(repo, "branch")


async def test_conflict_stops_and_keeps(repo):
    p = Path((await wt.create(str(repo), "y"))["path"])
    (p / "a.txt").write_text("wt\n"); sh(p, "commit", "-qam", "wt")
    (repo / "a.txt").write_text("main\n"); sh(repo, "commit", "-qam", "main")
    r = await wt.merge(str(repo), "y")
    assert not r["ok"] and r["conflict"] == ["a.txt"]
    assert p.is_dir() and sh(p, "status", "--porcelain") == ""   # rebase를 되돌렸다
    assert sh(repo, "log", "-1", "--format=%s") == "main"


async def test_discard(repo):
    p = Path((await wt.create(str(repo), "z"))["path"])
    (p / "e.txt").write_text("e\n"); sh(p, "add", "e.txt"); sh(p, "commit", "-qm", "e")
    await wt.remove(str(repo), "z", force=True)
    assert not p.exists() and "cc/z" not in sh(repo, "branch")


def test_schema_lock(tmp_path):
    cfg = tmp_path / "w.toml"
    cfg.write_text('[schema_lock.foreman]\npaths = ["migrations/"]\ncommands = [\'bridge\\.db\\.migrate\']\n')
    alive = {"A", "B"}
    sl = SchemaLock(cfg, alive=lambda cc: cc in alive, state=tmp_path / "lock.json")
    repo = tmp_path / "foreman"
    w1 = repo / ".worktrees" / "f-2"
    w1.mkdir(parents=True)
    (repo / ".git").mkdir(); (w1 / ".git").write_text("gitdir: x\n")   # 원본은 폴더, worktree는 파일
    edit = lambda p: {"file_path": str(p)}  # noqa: E731
    assert sl.check("foreman", "A", str(w1), "Write", edit(w1 / "migrations" / "0017_x.sql")) is None   # A가 잡는다
    assert sl.check("foreman", "A", str(w1), "Edit", edit(w1 / "migrations" / "0017_x.sql")) is None
    assert sl.check("foreman", "B", str(repo), "Edit", edit(repo / "bridge" / "x.py")) is None          # 스키마 밖은 상관없다
    why = sl.check("foreman", "B", str(repo), "Bash", {"command": ".venv/bin/python -m bridge.db.migrate"})
    assert why and "스키마 잠금" in why
    assert sl.check("runshoes", "B", str(repo), "Write", edit(repo / "migrations" / "a.sql")) is None    # 규칙 없는 프로젝트
    alive.discard("A")                                       # A가 끝나도 worktree가 남았으면 계속 잠김
    assert sl.check("foreman", "B", str(repo), "Write", edit(repo / "migrations" / "0017_y.sql"))
    assert SchemaLock(cfg, alive=lambda cc: False, state=tmp_path / "lock.json").state["foreman"]["cc"] == "A"   # 다시 떠도 남는다
    assert sl.release("foreman", "f-2")
    assert sl.check("foreman", "B", str(repo), "Write", edit(repo / "migrations" / "0017_y.sql")) is None
    assert sl.state["foreman"]["cc"] == "B" and sl.state["foreman"]["wt"] is None
    alive.discard("B")                                       # 원본 폴더 세션은 끝나면 풀린다
    assert sl.check("foreman", "C", str(repo), "Write", edit(repo / "migrations" / "0018.sql")) is None
