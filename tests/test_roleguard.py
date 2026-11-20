"""역할 권한(11-11, bridge/roleguard.py) — 판정 · 관찰/막기 · 예외가 PreToolUse를 막지 않음."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.approval import load_policy
from bridge.approvals import ApprovalManager
from bridge.roleguard import RoleGuard, RolesConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"   # 실제 config/ 대신(11-14)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "foreman"
    (r / ".git").mkdir(parents=True)
    (r / "bridge").mkdir()
    (r / "log").mkdir()
    w = r / ".worktrees" / "foreman-2"
    w.mkdir(parents=True)
    (w / ".git").write_text("gitdir: x")
    return r


def g(mode="observe"):
    return RoleGuard(RolesConfig(mode=mode, projects=["foreman"]), free=())   # 시험 저장소가 /tmp 아래다


def bash(gd, cmd, cwd, role="coder", scratch=None):
    return gd.check("foreman", role, str(cwd), "Bash", {"command": cmd}, scratch)


def test_bash_file_edit(repo, tmp_path):
    gd = g()
    w = repo / ".worktrees" / "foreman-2"
    hits = [
        "sed -i 's/a/b/' bridge/x.py",
        "cat >> log/a.md <<'EOF'\n본문 > 꺾쇠\nEOF",
        "cat > tests/t.py <<EOF\nx\nEOF",
        "echo hi > bridge/y.py",
        "git show HEAD:a > bridge/z.py",
        "echo x | tee -a log/b.md",
        "cd bridge && sed -i.bak -e 's/a/b/' x.py",
        "perl -pi -e 's/a/b/' bridge/x.py",
    ]
    for cmd in hits:
        h = bash(gd, cmd, w)
        assert h and h.rule == "역할-Bash파일고침", cmd
        assert "Edit · Write" in h.reason
    misses = [
        "git log --oneline > /tmp/x.txt",
        "pytest -q 2>&1 | tail -3",
        "ls 2>/dev/null; echo ok >/dev/null",
        "cd /tmp/s && cat > x.sh <<'EOF'\na > b\nEOF",                  # 앞 조각의 cd를 따라간다
        f"cd {tmp_path} && echo x > notrepo.txt",                       # git 저장소 밖
        "git commit -q -m \"$(cat <<'EOF'\n제목 > 꺾쇠\n\n본문\nEOF\n)\"",  # 커밋 글 heredoc
        "git commit -m '줄 하나\n> 인용\n끝'",                             # 여러 줄 따옴표 안의 >
        "sed -n 1,20p bridge/x.py",                                       # -i 없음
        "sed -i.bak '' /dev/null 2>/dev/null",                            # 2>/dev/null의 2는 파일이 아니다
        "python3 - <<'EOF' || python3 - <<'EOF2'\nopen('bridge/x.py','w')\nEOF\nx > y\nEOF2",   # heredoc 둘
        "S=/x; cd $S && echo a > b",                                      # 모르는 곳(cd $S)은 막지 않는다
        "echo '- [x](y.md)' >> ~/.claude/projects/p/memory/MEMORY.md",
    ]
    for cmd in misses:
        assert bash(gd, cmd, w) is None, cmd
    s = tmp_path / "scratch"
    s.mkdir()
    assert bash(gd, f"echo a > {s}/x", w, scratch=str(s)) is None


def test_worktree_push(repo):
    gd = g()
    w = repo / ".worktrees" / "foreman-2"
    h = bash(gd, "git push origin cc/foreman-2", w)
    assert h and h.rule == "역할-worktree push" and "관리자" in h.reason
    assert bash(gd, "git push", repo, role="manager") is None            # 원본 폴더 관리자는 된다
    assert bash(gd, "git commit -m 'push 하지 않음'", w) is None             # 따옴표 안의 낱말
    assert bash(gd, "git log --oneline origin/main..HEAD", w) is None


def test_manager_and_scribe_edits(repo):
    gd = g()
    ed = lambda role, path, cwd=repo: gd.check("foreman", role, str(cwd), "Edit", {"file_path": str(repo / path)})  # noqa: E731
    assert ed("manager", "bridge/x.py").rule == "역할-관리자코드"
    for ok in ("config/notify.toml", "log/a.md", "docs/TODO.md"):
        assert ed("manager", ok) is None, ok
    assert ed("manager", "README.md").rule == "역할-관리자코드"   # README는 생성물이라 관리자 허용에서 뺐다(11-20)
    assert ed("manager", "docs/00_design.md").rule == "역할-관리자코드"
    assert ed("coder", "bridge/x.py") is None
    assert ed("scribe", "bridge/x.py").rule == "역할-서기코드"
    assert ed("scribe", "docs/a.md") is None
    # 관리자라도 worktree에서 도는 세션(잘못 뜬 것)은 관리자 규칙 밖 — 아홉이 막는다
    w = repo / ".worktrees" / "foreman-2"
    assert gd.check("foreman", "manager", str(w), "Edit", {"file_path": str(w / "bridge/x.py")}) is None


def test_off_project_and_rule_switch(repo):
    assert g("off").check("foreman", "coder", str(repo), "Bash", {"command": "sed -i s/a/b/ bridge/x.py"}) is None
    assert g().check("runshoes", "coder", str(repo), "Bash", {"command": "sed -i s/a/b/ bridge/x.py"}) is None
    c = RolesConfig(mode="observe", projects=["foreman"])
    c.rules["bash-file-edit"] = False
    assert RoleGuard(c).check("foreman", "coder", str(repo), "Bash", {"command": "sed -i s/a/b/ bridge/x.py"}) is None


def test_config_load(tmp_path):
    # 실제 config/roles.toml 대신 시험용 파일(11-14 — 막기로 켜도 시험이 깨지지 않게. 실제 설정의 모양은 test_live_config_shape)
    ok = tmp_path / "roles.toml"
    ok.write_text('[roles]\nmode = "observe"\nprojects = ["foreman"]\n\n[roles.rules]\nworktree-push = true\n'
                  'bash-file-edit = true\nmanager-code = true\nscribe-code = true\n')
    real = RolesConfig.load(ok)
    assert real.mode == "observe" and real.error is None and all(real.rules.values())    # 처음엔 관찰(막지 않음)
    p = tmp_path / "r.toml"
    p.write_text('[roles]\nmode = "막기"\n')
    bad = RolesConfig.load(p)
    assert bad.mode == "off" and "mode" in bad.error
    assert RolesConfig.load(tmp_path / "none.toml").mode == "off"


def test_check_error_is_reported_not_raised(repo, monkeypatch):
    errs = []
    gd = RoleGuard(RolesConfig(mode="enforce", projects=["foreman"]), on_error=errs.append)
    monkeypatch.setattr(gd, "_check", lambda *a: 1 / 0)
    assert gd.check("foreman", "coder", str(repo), "Bash", {"command": "x"}) is None
    gd.check("foreman", "coder", str(repo), "Bash", {"command": "x"})
    assert len(errs) == 1 and "ZeroDivisionError" in errs[0]          # 시간마다 한 번


def _mgr(repo, mode):
    asm = SimpleNamespace(_project_for=lambda cwd, d: ("foreman", None), ids_for=None)
    m = ApprovalManager(None, load_policy(FIXTURES / "approval_now.toml"), asm, SimpleNamespace(submit=lambda e: None), None)
    m.roles = RoleGuard(RolesConfig(mode=mode, projects=["foreman"]), free=())
    recs = []

    async def rec(p, tool, inp, dec, mode_, enforced, summary=None, extra=None):
        recs.append((dec, extra))
    m._record_pre = rec
    return m, recs


def test_approvals_observe_records_enforce_denies(repo):
    w = repo / ".worktrees" / "foreman-2"
    p = {"tool_name": "Bash", "tool_input": {"command": "sed -i s/a/b/ bridge/x.py"}, "cwd": str(w), "session_id": "c"}

    async def go(mode):
        m, recs = _mgr(repo, mode)
        out = m.pre_tool_use(dict(p), session_role="coder")
        await asyncio.sleep(0)
        return out, recs
    out, recs = asyncio.run(go("observe"))
    assert recs[0][1]["role_rule"] == "역할-Bash파일고침"                 # 관찰: 판정은 그대로, 기록에만
    assert not out or out["hookSpecificOutput"]["permissionDecision"] != "deny"
    out, recs = asyncio.run(go("enforce"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Edit · Write" in out["hookSpecificOutput"]["permissionDecisionReason"]   # 무엇이 왜 막혔는지
    assert recs[0][0].rule == "역할-Bash파일고침"
