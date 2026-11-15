"""조사(inspector) 세션은 자기 log만 쓴다(11-15 사용자, bridge/roleguard.py inspector-write).

조사는 보통 모드로 뜨고 브리지가 막는다 — log/ 아래 새 파일 쓰기 · 커밋은 승인 없이, 저장소의 다른 파일은 거부.
이 규칙은 [roles] enforce에 들어 있으면 mode가 observe여도 막는다(다른 역할 규칙은 관찰 그대로)."""

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.roleguard import RoleGuard, RolesConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "roles.toml"


def _git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "foreman"
    (r / "bridge").mkdir(parents=True)
    (r / "log").mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    (r / "bridge" / "x.py").write_text("a = 1\n")
    (r / "log" / "old.md").write_text("다른 세션의 기록\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "처음")
    return r


@pytest.fixture
def scratch(tmp_path):
    s = tmp_path / "scratch"
    s.mkdir()
    return s


def gd(mode="observe", enforce=("inspector-write",)):
    return RoleGuard(RolesConfig(mode=mode, projects=["foreman"], enforce=list(enforce)), free=())   # 시험 저장소가 /tmp 아래다


def edit(g, repo, path, tool="Write", session="s1"):
    return g.check("foreman", "inspector", str(repo), tool, {"file_path": str(path)}, None, session=session)


def bash(g, repo, cmd, scratch=None, role="inspector"):
    return g.check("foreman", role, str(repo), "Bash", {"command": cmd}, str(scratch) if scratch else None, session="s1")


def test_edit_only_own_log(repo, scratch):
    g = gd()
    # 허용: log 아래 새 파일 · 그 세션이 이어 고치기 · 저장소 밖(스크래치)
    assert edit(g, repo, repo / "log" / "inspect_x_20261115.md") is None
    (repo / "log" / "inspect_x_20261115.md").write_text("결과\n")
    assert edit(g, repo, repo / "log" / "inspect_x_20261115.md", tool="Edit") is None
    assert edit(g, repo, scratch / "note.md") is None
    # 브리지가 다시 떠 기억을 잃어도: 아직 커밋 안 한 log면 허용
    assert edit(gd(), repo, repo / "log" / "inspect_x_20261115.md", tool="Edit") is None
    # 거부: 코드 · 다른 세션이 커밋한 log · CLAUDE.md
    for p in (repo / "bridge" / "x.py", repo / "log" / "old.md", repo / "CLAUDE.md"):
        h = edit(g, repo, p, tool="Edit")
        assert h and h.rule == "역할-조사쓰기" and h.enforce, p
        assert h.reason.startswith("조사 세션은 log 파일만 쓸 수 있습니다")
    assert "만든 파일이 아닙니다" in edit(g, repo, repo / "log" / "old.md", tool="Edit").reason
    assert g.check("foreman", "inspector", str(repo), "NotebookEdit", {"notebook_path": str(repo / "bridge" / "n.ipynb")}).rule == "역할-조사쓰기"


def test_bash_allow(repo, scratch):
    g = gd()
    (repo / "log" / "new.md").write_text("결과\n")
    ok = [
        "git status", "git log --oneline -5", "git diff HEAD~1", "git show HEAD:bridge/x.py", "git branch", "git branch -a",
        "git worktree list", "git stash list", "git merge-tree --write-tree main HEAD", "grep -rn foo bridge/",
        "git add log/new.md", "git add log/new.md && git commit -m '조사 결과를 기록함'",
        "git restore --staged bridge/x.py",
        f"cat bridge/x.py > {scratch}/copy.py", f"cp bridge/x.py {scratch}/", f"rm -f {scratch}/copy.py",
        f"cd {scratch} && echo hi > a.txt && git init -q t && cd t && git add -A",   # 저장소 밖 시험 저장소는 자유
        ".venv/bin/python -m pytest -q", "ls 2>/dev/null > /dev/null",
    ]
    for c in ok:
        assert bash(g, repo, c, scratch) is None, c


def test_bash_deny(repo, scratch):
    g = gd()
    no = [
        "echo x > bridge/x.py", "echo x >> log/new.md", "sed -i s/a/b/ bridge/x.py", "tee log/a.md < /dev/null",
        "rm bridge/x.py", "mv bridge/x.py bridge/y.py", f"cp {scratch}/a bridge/x.py", "touch bridge/z.py", "mkdir bridge/n",
        "git push", "git push origin cc/x", "git checkout -- bridge/x.py", "git reset --hard", "git stash",
        "git add -A", "git add .", "git add bridge/x.py", "git add log/a.md bridge/x.py",
        "git commit -am '고침'", "git commit -a -m x", "git commit -m x bridge/x.py",
        "git branch -D cc/x", "git branch new", "git tag v1", "git worktree add ../w", "git rebase main", "git merge cc/x",
        "git -C . restore bridge/x.py",
    ]
    for c in no:
        h = bash(g, repo, c, scratch)
        assert h and h.rule == "역할-조사쓰기", c


def test_commit_checks_stage(repo):
    g = gd()
    (repo / "bridge" / "x.py").write_text("a = 2\n")
    _git(repo, "add", "bridge/x.py")                    # 누가 먼저 log 밖을 올려 둠
    h = bash(g, repo, "git commit -m '조사 결과'")
    assert h and "스테이지에 log 밖 파일(bridge/x.py)" in h.reason
    _git(repo, "restore", "--staged", "bridge/x.py")
    (repo / "log" / "r.md").write_text("결과\n")
    _git(repo, "add", "log/r.md")
    assert bash(g, repo, "git commit -m '조사 결과'") is None


def test_other_roles_and_observe(repo):
    # 조사 규칙은 조사에게만
    assert bash(gd(), repo, "git add bridge/x.py", role="coder") is None
    # enforce에 없으면 관찰(기록만) — Hit는 나오지만 막지 않는다
    h = bash(gd(enforce=()), repo, "git add bridge/x.py")
    assert h and not h.enforce
    g = gd()
    assert g.enforces("inspector-write", "foreman") and not g.enforces("inspector-write", "runshoes")
    assert not g.enforces("bash-file-edit", "foreman")                  # 다른 규칙은 관찰 그대로
    assert not gd(enforce=()).enforces("inspector-write", "foreman")


def test_live_config_enforces_only_inspector():
    c = RolesConfig.load(CONFIG)
    assert c.error is None and c.enforce == ["inspector-write"] and c.rules["inspector-write"]
    assert c.inspector_allow == ["log/*"]


def test_config_unknown_enforce(tmp_path):
    p = tmp_path / "r.toml"
    p.write_text('[roles]\nmode = "observe"\nenforce = ["없는규칙"]\n')
    c = RolesConfig.load(p)
    assert c.mode == "off" and "enforce" in c.error


def test_approvals_denies_inspector_even_in_observe(repo):
    asm = SimpleNamespace(_project_for=lambda cwd, d: ("foreman", None), ids_for=None)
    m = ApprovalManager(None, load_policy(FIXTURES / "approval_now.toml"), asm, SimpleNamespace(submit=lambda e: None), None)
    m.roles = gd("observe")
    recs = []

    async def rec(p, tool, inp, dec, mode_, enforced, summary=None, extra=None):
        recs.append(dec)
    m._record_pre = rec

    async def go(inp, tool="Edit"):
        recs.clear()
        out = m.pre_tool_use({"tool_name": tool, "tool_input": inp, "cwd": str(repo), "session_id": "c"}, session_role="inspector")
        await asyncio.sleep(0)
        return out
    out = asyncio.run(go({"file_path": str(repo / "bridge" / "x.py"), "old_string": "a", "new_string": "b"}))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "조사 세션은 log 파일만 쓸 수 있습니다" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert recs[0].rule == "역할-조사쓰기"                                # 막힌 것은 기록에 남는다(조용히 묻히지 않게)
    out = asyncio.run(go({"file_path": str(repo / "log" / "inspect.md"), "content": "x"}, tool="Write"))
    assert not out or out["hookSpecificOutput"]["permissionDecision"] != "deny"
