"""다른 저장소는 읽기만(bridge/reposcope.py, 11-09)."""

from pathlib import Path

from bridge.reposcope import RepoScope

CFG = """
[repo_scope]
read_only_elsewhere = ["foreman"]
read = ["status", "log", "show", "diff", "ls-remote", "rev-parse"]
"""


def _setup(tmp_path: Path):
    fm, rs, sc = tmp_path / "foreman", tmp_path / "runshoes", tmp_path / "scratch" / "clone"
    for d in (fm, rs, sc):
        (d / ".git").mkdir(parents=True)
    (fm / ".worktrees" / "foreman-2").mkdir(parents=True)
    (fm / ".worktrees" / "foreman-2" / ".git").write_text("gitdir: x")
    (tmp_path / "plain").mkdir()
    cfg = tmp_path / "approval.toml"
    cfg.write_text(CFG)
    sc_root = str(tmp_path / "scratch")
    s = RepoScope(cfg, repos=lambda: {"foreman": str(fm), "runshoes": str(rs)}, free=())
    return s, fm, rs, sc_root


def test_edit_other_repo_denied_own_and_free_allowed(tmp_path):
    s, fm, rs, sc = _setup(tmp_path)
    cwd = str(fm)
    assert s.check("foreman", cwd, "Write", {"file_path": str(rs / ".claude" / "settings.json")}, sc)
    assert "runshoes" in s.check("foreman", cwd, "Edit", {"file_path": str(rs / "CLAUDE.md")}, sc)
    assert s.check("foreman", cwd, "Edit", {"file_path": "../runshoes/a.py"}, sc)          # 상대 경로
    assert not s.check("foreman", cwd, "Edit", {"file_path": str(fm / "README.md")}, sc)
    assert not s.check("foreman", str(fm / ".worktrees" / "foreman-2"), "Edit",
                       {"file_path": str(fm / ".worktrees" / "foreman-2" / "x.py")}, sc)  # 자기 worktree
    assert not s.check("foreman", cwd, "Write", {"file_path": sc + "/clone/x.md"}, sc)    # 스크래치 복제본
    assert not s.check("foreman", cwd, "Write", {"file_path": str(tmp_path / "plain" / "m.md")}, sc)  # 저장소 아님
    # 목록에 없는 프로젝트(런슈즈 세션)는 보지 않는다
    assert not s.check("runshoes", str(rs), "Edit", {"file_path": str(fm / "README.md")}, sc)


def test_git_writes_in_other_repo(tmp_path):
    s, fm, rs, sc = _setup(tmp_path)
    cwd = str(fm)

    def bash(c):
        return s.check("foreman", cwd, "Bash", {"command": c}, sc)

    assert bash(f"git -C {rs} commit -m x")
    assert bash(f"git -C {rs} push")
    assert bash(f"git -C {rs} fetch")                       # fetch도 .git에 쓴다
    assert bash(f"cd {rs} && git add a && git commit -m 'a'")
    assert bash(f"cd {rs}\ngit push origin main")           # 줄을 넘어 cd가 이어진다
    assert bash(f"GIT_DIR={rs}/.git git commit -m x")
    assert bash(f"git --git-dir={rs}/.git --work-tree={rs} commit -m x")
    assert bash(f"git -C {rs} branch -D old")
    # 읽기는 그대로
    assert not bash(f"git -C {rs} log --oneline -5")
    assert not bash(f"git -C {rs} ls-remote origin")
    assert not bash(f"cd {rs} && git status && git diff")
    assert not bash(f"git -C {rs} branch -a")
    assert not bash(f"git -C {rs} remote -v")
    assert not bash(f"git -C {rs} -c core.pager=cat show HEAD")
    # 지난 7일 다시 돌려 본 헛거부(11-09) — 목록 보기 · 시험만 하기
    assert not bash(f"cd {rs} && git reflog show --date=iso origin/main")
    assert not bash(f"U=$(git -C {rs} remote get-url origin)")
    assert not bash(f"git -C {rs} apply --check /x.patch")
    assert not bash(f"git -C {rs} fetch -q --dry-run")
    assert not bash(f"git -C {rs} config --get remote.origin.url")
    assert bash(f"git -C {rs} apply /x.patch")
    assert bash(f"git -C {rs} fetch -n")
    assert bash(f"git -C {rs} remote add x y")
    assert bash(f"git -C {rs} reflog expire --all")
    assert bash(f"git -C {rs} branch new-b")
    assert bash(f"git -C {rs} tag -d v1")
    # 자기 저장소 · 스크래치 복제본 쓰기는 그대로
    assert not bash("git add a && git commit -m x && git push")
    assert not bash(f"git -C {sc}/clone fetch && git -C {sc}/clone commit -m x")
    assert not bash(f"git clone {rs} {sc}/clone2")
    # 커밋 메시지(heredoc) 안의 글은 명령이 아니다
    assert not bash(f"git commit -q -F - <<'EOF'\ncd {rs} && git push\nEOF\ngit push")


def test_reason_text(tmp_path):
    s, fm, rs, sc = _setup(tmp_path)
    why = s.check("foreman", str(fm), "Bash", {"command": f"git -C {rs} push"}, sc)
    assert why.startswith("다른 저장소 쓰기 막힘 — ") and "읽기만 합니다(git push)" in why and "ls-remote" in why
