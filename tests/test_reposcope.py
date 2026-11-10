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


CFG_INFRA = CFG.replace('["foreman"]', '["foreman", "ronanlab-infra"]') + """
[repo_scope.writable]
ronanlab-infra = ["runshoes/docs/", "petmint-rag-chatbot/docs/", "foreman/../x/", "nopath"]
"""


def test_infra_may_edit_docs_of_listed_repos_only(tmp_path):
    """11-10 — 인프라는 다른 저장소 읽기만, 단 런슈즈 · 펫퍼민트 docs/는 Edit · Write로 고친다. git 쓰기 · 다른 경로 · worktree는 막는다."""
    fm, rs, pm, inf = (tmp_path / n for n in ("foreman", "runshoes", "petmint", "infra"))
    for d in (fm, rs, pm, inf):
        (d / ".git").mkdir(parents=True)
    (rs / ".worktrees" / "rs-2").mkdir(parents=True)
    (rs / ".worktrees" / "rs-2" / ".git").write_text("gitdir: x")
    cfg = tmp_path / "approval.toml"
    cfg.write_text(CFG_INFRA)
    s = RepoScope(cfg, repos=lambda: {"foreman": str(fm), "runshoes": str(rs), "petmint-rag-chatbot": str(pm),
                                      "ronanlab-infra": str(inf)}, free=())
    cwd = str(inf)

    def ed(p, tool="Edit"):
        return s.check("ronanlab-infra", cwd, tool, {"file_path": str(p)})

    assert not ed(rs / "docs" / "ops" / "nodes.md")
    assert not ed(pm / "docs" / "README.md", "Write")
    assert not ed(inf / "anything.yaml")                            # 자기 저장소
    assert ed(rs / "backend" / "a.java")                            # docs 밖
    assert ed(rs / "docsx" / "a.md")                                # docs/로 시작하는 다른 폴더
    assert ed(rs / "docs" / ".." / "CLAUDE.md")                     # .. 로 빠져나가기
    assert ed(fm / "docs" / "a.md")                                 # 적지 않은 저장소
    assert ed(fm / "x" / "a.md")                                    # 설정의 ".." 항목은 버린다
    assert ed(rs / ".worktrees" / "rs-2" / "docs" / "a.md")         # 그 저장소의 worktree는 아니다
    assert s.check("ronanlab-infra", cwd, "Bash", {"command": f"git -C {rs} push"})   # push는 그대로
    assert not s.check("ronanlab-infra", cwd, "Bash", {"command": f"git -C {pm} status"})
    # FOREMAN 세션은 예외가 없다
    assert s.check("foreman", str(fm), "Edit", {"file_path": str(rs / "docs" / "a.md")})
    assert s.check("foreman", str(fm), "Bash", {"command": f"git -C {rs} add docs/a.md"})


def test_infra_docs_git_add_commit(tmp_path):
    """11-10 사용자 — 예외 저장소에서 add는 경로를 적은 docs/만, commit 허용(스테이지에 docs 밖이 있으면 막음), push는 막는다."""
    import subprocess
    rs, inf = tmp_path / "runshoes", tmp_path / "infra"
    for d in (rs, inf):
        subprocess.run(["git", "init", "-q", str(d)], check=True)
    (rs / "docs").mkdir()
    cfg = tmp_path / "approval.toml"
    cfg.write_text(CFG_INFRA)
    s = RepoScope(cfg, repos=lambda: {"runshoes": str(rs), "ronanlab-infra": str(inf)}, free=())

    def bash(c, cwd=str(inf)):
        return s.check("ronanlab-infra", cwd, "Bash", {"command": c})

    # add — 경로를 적은 docs/만
    assert not bash(f"git -C {rs} add docs/ops/nodes.md docs/README.md")
    assert not bash(f"cd {rs} && git add -- docs/a.md")
    assert not bash(f"git -C {rs}/docs add a.md")                 # docs 안에서 상대 경로
    assert not bash(f"git -C {rs} add docs")                      # docs 폴더 통째(그 안만 담긴다)
    for c in (f"git -C {rs} add -A", f"git -C {rs} add .", f"git -C {rs} add --all", f"git -C {rs} add -u",
              f"git -C {rs} add", f"git -C {rs} add CLAUDE.md", f"git -C {rs} add docs/a.md backend/x.java",
              f"git -C {rs} add ../infra/x", f"git -C {rs} add :/", f"git -C {rs} add -f docs/a.md",
              f"cd {rs}/docs && git add ."):
        assert bash(c), c
    # commit — 경로를 적으면 docs/만, -a · --amend 막음
    assert not bash(f"git -C {rs} commit -m 'docs: 노드' -- docs/a.md")
    assert not bash(f"cd {rs} && git add docs/a.md && git commit -F - <<'EOF'\n노드 문서\n\nCo-Authored-By: x\nEOF")
    assert not bash(f"git -C {rs} add docs/a.md 2>&1 > /tmp/out.txt")   # 리디렉션은 경로가 아니다
    for c in (f"git -C {rs} commit -a -m x", f"git -C {rs} commit --amend -m x", f"git -C {rs} commit -am x",
              f"git -C {rs} commit -m x -- src/a.py", f"git -C {rs} commit -i docs/a.md backend/b"):
        assert bash(c), c
    # commit — 경로 없이: 스테이지가 docs/만이면 허용, 다른 세션이 올려 둔 docs 밖이 있으면 막음
    (rs / "docs" / "a.md").write_text("a")
    subprocess.run(["git", "-C", str(rs), "add", "docs/a.md"], check=True)
    assert not bash(f"git -C {rs} commit -m x")
    (rs / "app.py").write_text("x")
    subprocess.run(["git", "-C", str(rs), "add", "app.py"], check=True)
    why = bash(f"git -C {rs} commit -m x")
    assert why and "app.py" in why
    assert not bash(f"git -C {rs} commit -m x -- docs/a.md")       # 경로를 적으면 그 경로만 커밋된다
    # push · 그 밖은 막는다
    for c in (f"git -C {rs} push", f"git -C {rs} push origin main", f"git -C {rs} reset --hard",
              f"git -C {rs} checkout -- docs/a.md", f"git -C {rs} add docs/a.md && git -C {rs} push"):
        assert bash(c), c


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


# ── 관리자 세션의 docs 전용 push(11-10 사용자) — 실제 git 저장소 + 로컬 bare 원격 ──────────────
import subprocess  # noqa: E402

CFG_MGR = CFG_INFRA + """
[repo_scope.manager_push]
foreman = ["runshoes/docs/", "petmint-rag-chatbot/docs/"]
"""


def _g(repo, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "HOME": str(repo), "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def _commit(repo, files, msg="c"):
    for f in files:
        p = repo / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(p.read_text() + "x\n" if p.exists() else "x\n")
        _g(repo, "add", f)
    _g(repo, "commit", "-q", "-m", msg)
    return _g(repo, "rev-parse", "HEAD").strip()


def _mgr_setup(tmp_path):
    fm, rs, pm, inf = (tmp_path / n for n in ("foreman", "runshoes", "petmint", "infra"))
    for d in (fm, pm, inf):
        (d / ".git").mkdir(parents=True)
    (fm / ".worktrees" / "foreman-2").mkdir(parents=True)
    (fm / ".worktrees" / "foreman-2" / ".git").write_text("gitdir: x")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    rs.mkdir()
    _g(rs, "init", "-q", "-b", "main")
    _commit(rs, ["README.md", "docs/a.md"], "init")
    _g(rs, "remote", "add", "origin", str(bare))
    _g(rs, "push", "-q", "-u", "origin", "main")
    cfg = tmp_path / "approval.toml"
    cfg.write_text(CFG_MGR)
    s = RepoScope(cfg, repos=lambda: {"foreman": str(fm), "runshoes": str(rs), "petmint-rag-chatbot": str(pm),
                                      "ronanlab-infra": str(inf)}, free=())
    return s, fm, rs, bare, inf


def _push(s, fm, cmd, role="manager", cwd=None):
    return s.check("foreman", str(cwd or fm), "Bash", {"command": cmd}, None, role)


def test_manager_push_docs_only_ahead_allowed(tmp_path):
    s, fm, rs, bare, _ = _mgr_setup(tmp_path)
    assert not _push(s, fm, f"git -C {rs} push origin main")          # 앞선 커밋 0개 — 할 일 없음
    _commit(rs, ["docs/ops/nodes.md"])
    _commit(rs, ["docs/a.md", "docs/b.md"])
    for cmd in (f"git -C {rs} push origin main", f"git -C {rs} push", f"git -C {rs} push origin",
                f"cd {rs} && git push origin main", f"git -C {rs} push -q origin main 2>&1"):
        assert not _push(s, fm, cmd), cmd
    assert not _push(s, fm, f"git -C {rs} push origin main", cwd=fm / "bridge")   # 원본 폴더 아래 하위 폴더도
    assert s.wants_role("Bash", {"command": f"git -C {rs} push"})
    assert not s.wants_role("Bash", {"command": f"git -C {rs} status"})
    assert not s.wants_role("Edit", {"file_path": "push"})


def test_manager_push_denied_when_any_commit_touches_outside_docs(tmp_path):
    s, fm, rs, _, _ = _mgr_setup(tmp_path)
    _commit(rs, ["docs/a.md"])
    bad = _commit(rs, ["docs/b.md", "backend/App.java"])
    _commit(rs, ["docs/c.md"])
    why = _push(s, fm, f"git -C {rs} push origin main")
    assert why and "backend/App.java" in why and bad[:8] in why and "docs/" in why
    assert "docs/b.md" not in why
    # docs로 시작하는 다른 폴더도 밖이다
    s2, fm2, rs2, _, _ = _mgr_setup(tmp_path / "2")
    _commit(rs2, ["docsx/a.md"])
    assert "docsx/a.md" in _push(s2, fm2, f"git -C {rs2} push")


def test_manager_push_denied_behind_diverged_merge(tmp_path):
    s, fm, rs, bare, _ = _mgr_setup(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _commit(other, ["docs/z.md"])
    _g(other, "push", "-q", "origin", "main")
    # 뒤처짐 — 원격 머리를 갖고 있지 않다
    why = _push(s, fm, f"git -C {rs} push origin main")
    assert why and "갖고 있지 않습니다" in why
    # 갈라짐 — 가져왔지만 로컬 main이 원격을 품지 않는다
    _commit(rs, ["docs/a.md"])
    _g(rs, "fetch", "-q", "origin")
    why = _push(s, fm, f"git -C {rs} push origin main")
    assert why and "앞선 상태가 아닙니다" in why
    # 머지 커밋 — 원격을 합친 뒤에는 앞섰지만 머지가 끼어 있다
    _g(rs, "merge", "-q", "--no-edit", "origin/main")
    why = _push(s, fm, f"git -C {rs} push origin main")
    assert why and "머지 커밋" in why


def test_manager_push_shape_narrow(tmp_path):
    s, fm, rs, _, _ = _mgr_setup(tmp_path)
    _commit(rs, ["docs/a.md"])
    for cmd in (f"git -C {rs} push --force origin main", f"git -C {rs} push -f", f"git -C {rs} push origin +main",
                f"git -C {rs} push --force-with-lease origin main", f"git -C {rs} push origin --delete main",
                f"git -C {rs} push --mirror", f"git -C {rs} push --tags", f"git -C {rs} push --all",
                f"git -C {rs} push origin dev", f"git -C {rs} push upstream main", f"git -C {rs} push origin main:main",
                f"git -C {rs} push origin main dev", f"git -C {rs} push origin HEAD", f"git -C {rs} push -u origin main"):
        assert _push(s, fm, cmd), cmd
    # 다른 브랜치에 있으면 브랜치를 적지 않은 push는 막는다(그 브랜치가 올라간다)
    _g(rs, "checkout", "-q", "-b", "dev")
    assert "main가 아닙니다" in _push(s, fm, f"git -C {rs} push")
    assert not _push(s, fm, f"git -C {rs} push origin main")
    _g(rs, "checkout", "-q", "main")
    # push 설정이 무엇이 올라갈지 바꾸면 막는다
    _g(rs, "config", "remote.origin.push", "refs/heads/*:refs/heads/*")
    assert "remote.origin.push" in _push(s, fm, f"git -C {rs} push origin main")


def test_manager_push_only_manager_in_original_folder(tmp_path):
    s, fm, rs, _, inf = _mgr_setup(tmp_path)
    _commit(rs, ["docs/a.md"])
    cmd = f"git -C {rs} push origin main"
    for role in (None, "coder", "scribe", "inspector"):
        assert "읽기만 합니다(git push)" in _push(s, fm, cmd, role=role), role
    assert "읽기만 합니다(git push)" in _push(s, fm, cmd, cwd=fm / ".worktrees" / "foreman-2")   # worktree 관리자
    # 인프라 세션 push는 그대로 막힘(역할과 상관없이)
    assert s.check("ronanlab-infra", str(inf), "Bash", {"command": cmd}, None, "manager")
    # 적지 않은 저장소(인프라)는 관리자도 막힘
    assert _push(s, fm, f"git -C {inf} push origin main")


def test_manager_push_denied_when_remote_unreadable(tmp_path):
    s, fm, rs, _, _ = _mgr_setup(tmp_path)
    _commit(rs, ["docs/a.md"])
    _g(rs, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))
    why = _push(s, fm, f"git -C {rs} push origin main")
    assert why and "읽지 못해" in why
