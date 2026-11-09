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


async def test_save_progress_never_commits_links(repo):
    """[쉬게 하기](11-09) — `git add -A`로 커밋하되 .env* · .venv · node_modules 링크와 worktree 밖 링크는 넣지 않는다.
    .gitignore · info/exclude가 없어도 막는다(빠진 것은 결과에 적는다). 견본(.env*.example)은 넣는다."""
    p = Path((await wt.create(str(repo), "rest"))["path"])
    assert (p / ".env.bridge").is_symlink() and (p / ".venv").is_symlink()
    assert await wt.save_progress(str(p), "쉬게 하기: 진행 중 저장 — 빈 것") == {"commit": None, "files": 0, "skipped": []}
    # 무방비 저장소 — .gitignore를 지우고 info/exclude도 비운다(다른 프로젝트에서 이럴 수 있다)
    (p / ".gitignore").unlink()
    (repo / ".git" / "info" / "exclude").write_text("/.worktrees/\n")
    (p / "web" / "index.js").write_text("y\n")
    (p / "new.txt").write_text("새 파일\n")
    (p / ".env.example").write_text("X=\n")
    (p / "outside").symlink_to(repo.parent)                       # worktree 밖을 가리키는 링크
    r = await wt.save_progress(str(p), "쉬게 하기: 진행 중 저장 — 시험")
    assert r["commit"] and set(r["skipped"]) >= {".env.bridge", ".venv", "web/node_modules", "outside"}
    tree = sh(p, "ls-tree", "-r", "--name-only", "HEAD").split()
    assert {"new.txt", ".env.example", "web/index.js"} <= set(tree)
    assert not any(t.startswith((".env.bridge", ".venv", "outside")) or "node_modules" in t for t in tree)
    assert sh(p, "log", "-1", "--format=%s") == "쉬게 하기: 진행 중 저장 — 시험"
    assert sh(p, "diff", "--cached", "--name-only") == ""          # 뺀 것을 올린 채 두지 않는다
    assert (p / ".env.bridge").is_symlink()                       # 작업 트리에서는 그대로


async def test_save_progress_commit_failure_unstages(repo, monkeypatch):
    """커밋이 실패하면 Refused(세션은 끝내지 않는다) — 올려 둔 것은 내린다."""
    p = Path((await wt.create(str(repo), "rest2"))["path"])
    (p / "a.txt").write_text("two\n")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n"); hook.chmod(0o755)
    with pytest.raises(Refused, match="커밋하지 못했습니다"):
        await wt.save_progress(str(p), "쉬게 하기: 진행 중 저장 — 실패")
    assert sh(p, "diff", "--cached", "--name-only") == "" and "a.txt" in sh(p, "status", "--porcelain")


def test_schema_lock_blocked_notice_and_early_release(tmp_path):
    """11-09 — 막힌 세션은 한 번만 알리고(같은 세션이 또 막혀도 다시 안 보냄), 원본 폴더 세션의 잠금은
    migrations/가 모두 적용되고 커밋 안 한 변경이 없을 때 저절로 푼다. worktree 세션이 쥔 잠금은 풀지 않는다."""
    cfg = tmp_path / "w.toml"
    cfg.write_text('[schema_lock.foreman]\npaths = ["migrations/"]\ncommands = []\n')
    repo = tmp_path / "foreman"
    (repo / "migrations").mkdir(parents=True)
    sh(repo, "init", "-q", "-b", "main"); sh(repo, "config", "user.email", "t@t"); sh(repo, "config", "user.name", "t")
    (repo / "migrations" / "0001_a.sql").write_text("x;\n")
    sl = SchemaLock(cfg, alive=lambda cc: True, state=tmp_path / "lock.json")
    edit = {"file_path": str(repo / "migrations" / "0002_b.sql")}
    assert sl.check("foreman", "A", str(repo), "Write", edit) is None                  # A(원본 폴더)가 쥔다
    assert sl.state["foreman"]["top"] == str(repo)
    assert sl.check("foreman", "B", str(repo), "Write", edit)                           # B가 막힌다
    n = sl.take_blocked_notice("foreman")
    assert n and n["cc"] == "B" and n["holder"] == "A"
    assert sl.check("foreman", "B", str(repo), "Write", edit) and sl.take_blocked_notice("foreman") is None   # 한 번만
    assert sl.view()["foreman"]["blocked"]["cc"] == "B"
    # 일찍 풀기 — 파일이 적용 안 됐거나 커밋 안 됐으면 그대로
    (repo / "migrations" / "0002_b.sql").write_text("y;\n")
    assert sl.try_release_early("foreman", {"0001_a"}) is None                          # 0002 미적용
    assert sl.try_release_early("foreman", {"0001_a", "0002_b"}) is None                # 커밋 안 됨
    sh(repo, "add", "."); sh(repo, "commit", "-qm", "m")
    why = sl.try_release_early("foreman", {"0001_a", "0002_b"})
    assert why and "적용 · 커밋 끝" in why and "foreman" not in sl.state and sl.released_view()["foreman"]["cc"] == "A"
    # worktree 세션이 쥔 잠금은 일찍 풀지 않는다
    w1 = repo / ".worktrees" / "f-2"
    (w1 / "migrations").mkdir(parents=True); (w1 / ".git").write_text("gitdir: x\n")
    assert sl.check("foreman", "C", str(w1), "Write", {"file_path": str(w1 / "migrations" / "0003_c.sql")}) is None
    assert sl.try_release_early("foreman", {"0001_a", "0002_b", "0003_c"}) is None and sl.state["foreman"]["cc"] == "C"


def test_schema_lock_commands_only_running_migrations(tmp_path):
    """11-09 — 실제 config/worktree.toml: 마이그레이션을 돌리는 명령만 스키마 시도다. 가져오기만 하는 읽기 조회 · --status ·
    flyway_schema_history 읽기는 잠금을 잡지도 막히지도 않는다(메인의 읽기 조회가 잠금을 쥐고, 또 막혔다)."""
    cfg = Path(__file__).resolve().parent.parent / "config" / "worktree.toml"
    sl = SchemaLock(cfg, alive=lambda cc: True, state=tmp_path / "lock.json")
    repo = tmp_path / "foreman"
    (repo / ".git").mkdir(parents=True)
    bash = lambda c: {"command": c}  # noqa: E731
    reads = [".venv/bin/python -c 'from bridge.db.migrate import connect; c = connect(); print(1)'",
             ".venv/bin/python -m bridge.db.migrate --status",
             "python bridge/db/migrate.py --status | tail -3",
             "grep -n migrate bridge/db/migrate.py"]
    for c in reads:
        assert sl.touches("foreman", "Bash", bash(c), str(repo)) is None, c
        assert sl.check("foreman", "A", str(repo), "Bash", bash(c)) is None
    assert "foreman" not in sl.state                                               # 읽기는 잠금을 잡지 않는다
    assert sl.touches("foreman", "Bash", bash(".venv/bin/python -m bridge.db.migrate"), str(repo))
    assert sl.touches("foreman", "Bash", bash(".venv/bin/python -m bridge.db.migrate --status && .venv/bin/python -m bridge.db.migrate"), str(repo))
    assert sl.touches("foreman", "Bash", bash("python bridge/db/migrate.py"), str(repo))
    assert sl.check("foreman", "A", str(repo), "Bash", bash(".venv/bin/python -m bridge.db.migrate")) is None   # A가 쥔다
    for c in reads:                                                                # 쥔 뒤에도 B의 읽기는 막히지 않는다
        assert sl.check("foreman", "B", str(repo), "Bash", bash(c)) is None, c
    assert sl.check("foreman", "B", str(repo), "Bash", bash(".venv/bin/python -m bridge.db.migrate"))
    rs = tmp_path / "runshoes"
    assert sl.touches("runshoes", "Bash", bash("mysql -e 'SELECT * FROM flyway_schema_history'"), str(rs)) is None
    assert sl.touches("runshoes", "Bash", bash("./gradlew flywayInfo"), str(rs)) is None
    assert sl.touches("runshoes", "Bash", bash("./gradlew flywayMigrate"), str(rs))
    assert sl.touches("runshoes", "Bash", bash("flyway migrate -url=x"), str(rs))


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
