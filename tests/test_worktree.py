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


async def test_tools_link_follows_and_is_never_committed(repo):
    """.tools(ttyd 등)도 .venv처럼 원본을 가리키는 링크로 따라온다. 커밋 후보에서 빠진다."""
    (repo / ".tools").mkdir(); (repo / ".tools" / "ttyd").write_text("bin\n")
    p = Path((await wt.create(str(repo), "tl"))["path"])
    assert (p / ".tools").is_symlink() and (p / ".tools").resolve() == (repo / ".tools").resolve()
    assert sh(repo, "status", "--porcelain") == ""
    (repo / ".git" / "info" / "exclude").write_text("/.worktrees/\n")   # 무방비 저장소 - 제외 목록이 없어도 막는다
    (p / "new.txt").write_text("x\n")
    r = await wt.save_progress(str(p), "쉬게 하기: 진행 중 저장 - 시험")
    assert ".tools" in r["skipped"]
    assert not any(t.startswith(".tools") for t in sh(p, "ls-tree", "-r", "--name-only", "HEAD").split())


async def test_no_tools_link_when_origin_has_none(repo):
    p = Path((await wt.create(str(repo), "nt"))["path"])
    assert not (p / ".tools").exists() and not (p / ".tools").is_symlink()


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


SCHEMA_LOCK_TOML = r"""
[schema_lock.foreman]
paths = ["migrations/"]
commands = ['-m\s+bridge\.db\.migrate\b(?![^\n;&|]*--status)', '\bpython[\w.]*\s+(\S*/)?bridge/db/migrate\.py\b(?![^\n;&|]*--status)']

[schema_lock.runshoes]
paths = ["backend/src/main/resources/db/migration/"]
commands = ['\bflyway(Migrate|Clean|Repair|Baseline|Undo)\b', '\bflyway\s+(migrate|clean|repair|baseline|undo)\b']
"""


def test_schema_lock_commands_only_running_migrations(tmp_path):
    """11-09 — config/worktree.toml의 명령 규칙: 마이그레이션을 돌리는 명령만 스키마 시도다. 가져오기만 하는 읽기 조회 · --status ·
    flyway_schema_history 읽기는 잠금을 잡지도 막히지도 않는다(메인의 읽기 조회가 잠금을 쥐고, 또 막혔다).
    11-14 — 실제 설정 대신 그 규칙(11-14 실제 값 그대로)을 쓴 시험용 파일을 읽는다(설정을 바꿀 때마다 시험이 깨지지 않게)."""
    cfg = tmp_path / "worktree.toml"
    cfg.write_text(SCHEMA_LOCK_TOML, encoding="utf-8")
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


async def test_in_base_outside_merge(repo):
    """11-11(받은 할 일 #17) — 밖에서 git merge --ff-only로 합친 브랜치 · rebase로 같은 변경이 들어간 브랜치를 알아챈다."""
    info = await wt.create(str(repo), "y")
    p = Path(info["path"])
    assert await wt.in_base(str(repo), "y") is True             # 갈라진 뒤 커밋 없음
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b")
    assert await wt.in_base(str(repo), "y") is False
    sh(repo, "merge", "-q", "--ff-only", "cc/y")                  # 밖에서 합침
    assert await wt.in_base(str(repo), "y") is True
    # rebase로 합쳐 커밋 id가 다름 — git cherry가 같은 변경으로 본다
    (p / "e.txt").write_text("e\n"); sh(p, "add", "e.txt"); sh(p, "commit", "-qm", "e")
    (repo / "f.txt").write_text("f\n"); sh(repo, "add", "f.txt"); sh(repo, "commit", "-qm", "f")
    sh(repo, "cherry-pick", "cc/y")
    assert await wt.in_base(str(repo), "y") is True
    await wt.remove(str(repo), "y", force=True)
    assert await wt.in_base(str(repo), "y") is None              # 브랜치 없음


# ── squash 합치기(11-12, 프로젝트마다 켬) ──
async def test_squash_merge_one_commit_with_titles_and_dates(repo, monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    p = Path((await wt.create(str(repo), "s"))["path"])
    for i, n in enumerate(("첫 일", "둘째 일", "기록")):
        (p / f"f{i}.txt").write_text(f"{i}\n"); sh(p, "add", f"f{i}.txt")
        sh(p, "commit", "-qm", f"{n}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
           f"--date=2026-11-12T1{i}:0{i}:00")
    (repo / "c.txt").write_text("c\n"); sh(repo, "add", "c.txt"); sh(repo, "commit", "-qm", "c")   # 원본이 앞서감 → rebase 뒤 squash
    before = sh(repo, "rev-parse", "main")
    r = await wt.merge(str(repo), "s", squash=True)
    assert r["ok"] and r["merged"] == 3 and r["squash"] and "커밋 하나" in r["note"]
    assert sh(repo, "rev-list", "--count", f"{before}..main") == "1"            # 커밋 하나만 더해졌다
    assert sh(repo, "rev-parse", "main^") == before
    msg = sh(repo, "log", "-1", "--format=%B")
    lines = msg.splitlines()
    assert lines[0] == "합침(cc/s, 커밋 3개): 첫 일 외 2건"                     # 세션 제목이 없으면 「첫 제목 외 N건」(11-13)
    assert r["title"] == lines[0] and lines[2] == "이 브랜치의 일을 커밋 3개에서 하나로 묶었다. 작업한 브랜치는 cc/s이다."
    items = [ln for ln in lines if ln.startswith("- ")]
    assert [ln.split(" ", 4)[1:3] + [ln.split(" ", 4)[4]] for ln in items] == [
        ["2026-11-12", "10:00", "첫 일"], ["2026-11-12", "11:01", "둘째 일"], ["2026-11-12", "12:02", "기록"]]   # 오래된 차례
    assert msg.count("Co-Authored-By:") == 1                                    # 겹치지 않게 하나로
    assert all((repo / f"f{i}.txt").exists() for i in range(3))
    assert not p.exists() and "cc/s" not in sh(repo, "branch")                  # 조상이 아니어도 -D로 지웠다
    # 원래 커밋 찾기 — 브랜치는 지웠지만 숨은 ref가 남아 본문의 해시를 그대로 볼 수 있다(11-13)
    ref = r["orig_ref"]
    assert ref.startswith(wt.SQUASH_REF) and f"git log {ref}" in msg and ref in r["note"]
    assert sh(repo, "log", "--format=%s", f"main..{ref}").splitlines() == ["기록", "둘째 일", "첫 일"]
    for ln in items:                                                            # 본문 해시가 모두 살아 있다
        h = ln.split(" ")[3]
        assert sh(repo, "log", "-1", "--format=%s", h) == ln.split(" ", 4)[4]
    assert sh(repo, "branch", "--list") == "* main" and sh(repo, "tag") == ""   # 브랜치 · 태그 목록은 어지럽히지 않는다
    found = sh(repo, "log", "--format=%H", "--grep", "둘째 일", "main").splitlines()
    assert len(found) == 1 and found[0].startswith(r["squash"])                 # 원래 제목 낱말로 묶음 커밋을 찾는다


async def test_squash_hook_and_single_commit_is_plain_ff(repo, monkeypatch):
    seen = []

    async def hook(r):
        seen.append(r)
        return True
    monkeypatch.setattr(wt, "SQUASH_OF", hook)
    p = Path((await wt.create(str(repo), "one"))["path"])
    (p / "b.txt").write_text("b\n"); sh(p, "add", "b.txt"); sh(p, "commit", "-qm", "b 하나")
    r = await wt.merge(str(repo), "one")                                         # squash=None → 훅이 정한다
    assert seen == [str(repo)] and r["ok"] and "squash" not in r                 # 커밋 하나는 묶을 것이 없다
    assert sh(repo, "log", "-1", "--format=%s") == "b 하나"


async def test_squash_conflict_same_as_before(repo, monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    p = Path((await wt.create(str(repo), "y"))["path"])
    (p / "a.txt").write_text("wt\n"); sh(p, "commit", "-qam", "wt")
    (p / "z.txt").write_text("z\n"); sh(p, "add", "z.txt"); sh(p, "commit", "-qm", "z")
    (repo / "a.txt").write_text("main\n"); sh(repo, "commit", "-qam", "main")
    r = await wt.merge(str(repo), "y", squash=True)
    assert not r["ok"] and r["conflict"] == ["a.txt"]
    assert p.is_dir() and sh(p, "status", "--porcelain") == "" and sh(repo, "log", "-1", "--format=%s") == "main"
    assert sh(repo, "for-each-ref", wt.SQUASH_REF) == ""                        # 못 합쳤으면 ref도 남기지 않는다


# ── squash 커밋 제목(11-13 337) — 묶은 일 전체 · 그 저장소 꼴 · 원래 커밋 찾기 ──
async def _branch(repo, name, subjects):
    p = Path((await wt.create(str(repo), name))["path"])
    for i, s in enumerate(subjects):
        (p / f"{name}{i}.txt").write_text(f"{i}\n"); sh(p, "add", "."); sh(p, "commit", "-qm", s)
    return p


async def test_squash_title_uses_session_title_and_number(repo, monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    await _branch(repo, "foreman-4", ["squash 제목 함수", "시험", "기록: squash 제목"])
    r = await wt.merge(str(repo), "foreman-4", squash=True, topic="squash 합친 커밋 제목", sid=337)
    lines = sh(repo, "log", "-1", "--format=%B").splitlines()
    assert lines[0] == "합침(cc/foreman-4, 세션 337, 커밋 3개): squash 합친 커밋 제목" == r["title"]
    assert lines[2] == "세션 337의 일(squash 합친 커밋 제목)을 커밋 3개에서 하나로 묶었다. 작업한 브랜치는 cc/foreman-4이다."


def _conv_claude_md(repo):
    (repo / "CLAUDE.md").write_text("## 커밋 메시지\n\n꼴: `타입: 설명`. 설명은 한글로, 50자 안\n")
    sh(repo, "add", "CLAUDE.md"); sh(repo, "commit", "-qm", "docs: 규칙")


async def test_squash_title_conventional_repo_from_claude_md(repo, monkeypatch):
    """런슈즈 · 인프라 · 펫퍼민트 꼴 — CLAUDE.md가 `타입: 설명`을 적었다. 타입은 원래 커밋 중 가장 무거운 것, 설명 50자 안."""
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    _conv_claude_md(repo)
    assert await wt.commit_style(str(repo), "main") == "conventional"
    await _branch(repo, "runshoes-2", ["docs: 09 16절 5-2", "fix: 챗봇 5-2 9차 수정", "feat: 검색 색인", "기록"])
    r = await wt.merge(str(repo), "runshoes-2", squash=True, topic="챗봇 5-2 검색 색인 · 경험·후기", sid=40)
    assert r["title"] == "feat: 챗봇 5-2 검색 색인, 경험, 후기"                  # 기호는 쉼표로, 커밋 수는 본문으로(11-13)
    assert wt.CONV_RE.match(r["title"]) and len(wt.CONV_RE.match(r["title"]).group(3)) <= wt.CONV_DESC_MAX
    assert sh(repo, "log", "-1", "--format=%s") == r["title"]
    msg = sh(repo, "log", "-1", "--format=%B")
    assert "세션 40의 일(챗봇 5-2 검색 색인, 경험, 후기)을 커밋 4개에서 하나로 묶었다." in msg
    assert not any(c in msg for c in "—·→")                                     # 본문(원래 커밋 목록 포함)에도 기호가 없다


def test_foreman_claude_md_is_conventional():
    """11-13부터 FOREMAN CLAUDE.md도 `타입: 설명`을 적었다 — 「합침(…): 제목」 free 꼴은 FOREMAN에서 더 쓰이지 않는다."""
    text = (Path(__file__).resolve().parents[1] / "CLAUDE.md").read_text(encoding="utf-8")
    assert wt._DECLARED_CONV.search(text)


def test_plain_symbols_to_commas():
    """em dash · 가운뎃점 · 화살표를 쉼표로 바꾸는 한 곳(11-13 사용자 결정)."""
    assert wt.plain("A — B · C → D") == "A, B, C, D"
    assert wt.plain("챗봇 검색 색인 · 경험·후기") == "챗봇 검색 색인, 경험, 후기"              # 한글 문장 안 가운뎃점(빈칸 없이)
    assert wt.plain("A, — B") == "A, B" and wt.plain("A —, B") == "A, B"                 # 옆에 이미 쉼표
    assert wt.plain("A — · B") == "A, B"                                                  # 기호가 겹쳐도 쉼표 하나
    assert wt.plain("— 앞 기호, 끝 기호 —") == "앞 기호, 끝 기호"                           # 앞뒤 쉼표는 뺀다
    assert wt.plain("끝 마침표.") == "끝 마침표" and wt.plain("  A   —B  ") == "A, B"
    assert wt.plain("1,000건 · 1–3단계") == "1,000건, 1–3단계"                           # 숫자 쉼표 · en dash는 그대로
    assert wt.plain("가・나") == "가, 나" and wt.plain(None) == "" and wt.plain("—") == ""
    assert wt.plain_title("docs(11_worktree): 6-1 — 합치기 · 제목") == "docs: 6-1, 합치기, 제목"   # 범위 표시도 뺀다
    assert wt.plain_title("feat!: 끊는 바꿈 → 새 API") == "feat!: 끊는 바꿈, 새 API"
    assert wt.plain_title("기록: 330 · 331 합침 — 판단 줄") == "기록: 330, 331 합침, 판단 줄"


def test_squash_title_rules():
    conv = ["fix: 가", "docs: 나"]
    assert wt.squash_title("conventional", conv, "cc/x") == "fix: 가 외 1건"                   # 세션 제목 없음 → 첫 설명 외 N건
    assert wt.squash_title("conventional", ["기록", "고침"], "cc/x", "합치기 제목") == "chore: 합치기 제목"   # 타입 없음 → chore
    assert wt.squash_title("conventional", ["ops: a", "docs: b"], "cc/x", "docs: 이미 타입.") == "ops: 이미 타입"
    assert wt.squash_title("conventional", conv, "cc/x", "판정 — 빈 worktree · 겹침 낱말") == "fix: 판정, 빈 worktree, 겹침 낱말"
    assert wt.squash_title("conventional", ["docs(a): 첫 — 일", "x"], "cc/x") == "docs: 첫, 일 외 1건"
    assert wt.squash_title("conventional", conv, "cc/x", " — ") == "fix: 가 외 1건"            # 기호만인 세션 제목은 없는 것과 같다
    long = wt.squash_title("conventional", conv, "cc/x", "가" * 80)
    assert len(wt.CONV_RE.match(long).group(3)) == wt.CONV_DESC_MAX and long.endswith("가…")
    cut = wt.squash_title("conventional", conv, "cc/x", "가" * 48 + " · 나나")
    assert cut == "fix: " + "가" * 48 + "…"                                     # 자른 자리에 쉼표가 남지 않는다
    assert wt.squash_title("free", ["첫", "둘"], "cc/foreman") == "합침(cc/foreman, 커밋 2개): 첫 외 1건"
    assert wt.squash_title("free", ["첫", "둘"], "cc/f", "가 · 나", 3) == "합침(cc/f, 세션 3, 커밋 2개): 가, 나"
    assert len(wt.squash_title("free", ["첫", "둘"], "cc/f", "나" * 300, 1)) == wt.FREE_TITLE_MAX
    # 사람이 넘긴 제목 — 그 저장소 꼴로
    assert wt.check_title("conventional", "  feat: 새 색인 ") == "feat: 새 색인"
    for bad in ("새 색인", "feat: " + "가" * 51, "feat: 끝.", "feat: 가\n둘째 줄", "  "):
        with pytest.raises(Refused):
            wt.check_title("conventional", bad)
    assert wt.check_title("free", "아무 꼴 제목") == "아무 꼴 제목"
    with pytest.raises(Refused):
        wt.check_title("free", "가" * 121)
    # 기호 · 범위 표시는 거부하지 않는다(merge가 바꾸고 note에 적는다). 길이는 바꾼 뒤 모양으로
    assert wt.check_title("conventional", "fix(x): 가 — 나") == "fix(x): 가 — 나"
    with pytest.raises(Refused):
        wt.check_title("conventional", "fix: " + "가·" * 25)                       # 바꾸면 74자
    with pytest.raises(Refused, match="비어"):
        wt.check_title("conventional", "fix: —")


async def test_commit_style_from_log_when_claude_md_silent(repo):
    assert await wt.commit_style(str(repo), "main") == "free"                    # FOREMAN — 한글 자유 꼴(「기록:」은 타입이 아니다)
    for i, s in enumerate(["feat: a", "fix: b", "docs(x): c", "ops: d", "기록: e", "합침(cc/a, 커밋 2개): f"]):
        (repo / f"l{i}").write_text("x"); sh(repo, "add", "."); sh(repo, "commit", "-qm", s)
    assert await wt.commit_style(str(repo), "main") == "conventional"           # 4/6(합침 빼고) > 60%


async def test_squash_human_title_and_refusal_before_anything(repo, monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    _conv_claude_md(repo)
    p = await _branch(repo, "h", ["fix: 가", "docs: 나"])
    before = sh(repo, "rev-parse", "main")
    with pytest.raises(Refused):                                                 # 꼴이 틀리면 아무것도 하지 않는다
        await wt.merge(str(repo), "h", squash=True, title="그냥 제목")
    assert sh(repo, "rev-parse", "main") == before and p.is_dir() and sh(repo, "for-each-ref", wt.SQUASH_REF) == ""
    r = await wt.merge(str(repo), "h", squash=True, title="fix: 사람이 정한 제목", topic="세션 제목")
    assert r["ok"] and sh(repo, "log", "-1", "--format=%s") == "fix: 사람이 정한 제목"
    assert "이 일(세션 제목)을 커밋 2개에서" in sh(repo, "log", "-1", "--format=%b")
    assert "바꿨습니다" not in r["note"] and "뺐습니다" not in r["note"]


async def test_squash_human_title_symbols_replaced_and_said(repo, monkeypatch):
    """사람이 넘긴 제목의 기호 · 범위 표시는 바꿔서 쓰고 note에 그렇다고 적는다(조용히 바꾸지 않게, 11-13)."""
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    _conv_claude_md(repo)
    await _branch(repo, "k", ["fix(a): 가 — 나", "docs: 다 → 라"])
    r = await wt.merge(str(repo), "k", squash=True, title="fix(bridge): 제목 — 기호 · 빼기")
    assert r["ok"] and r["title"] == "fix: 제목, 기호, 빼기" == sh(repo, "log", "-1", "--format=%s")
    assert "제목의 em dash · 가운뎃점 · 화살표를 쉼표로 바꿨습니다" in r["note"] and "범위 표시 (bridge)를 뺐습니다" in r["note"]
    body = sh(repo, "log", "-1", "--format=%b")
    assert [ln.split(" ", 4)[4] for ln in body.splitlines() if ln.startswith("- ")] == ["fix: 가, 나", "docs: 다, 라"]
    assert not any(c in body for c in "—·→")


async def test_title_unused_when_not_squashed(repo, monkeypatch):
    monkeypatch.setattr(wt, "SQUASH_OF", None)
    await _branch(repo, "one", ["하나뿐"])
    r = await wt.merge(str(repo), "one", squash=True, title="넘긴 제목")
    assert r["ok"] and "squash" not in r and "넘긴 제목은 쓰지 않았습니다" in r["note"]
    assert sh(repo, "log", "-1", "--format=%s") == "하나뿐" and sh(repo, "for-each-ref", wt.SQUASH_REF) == ""
