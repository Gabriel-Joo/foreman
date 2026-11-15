"""조사 B 고치기(11-15, log/foreman-7_silent_delete_fix_20261115.md) — heredoc 본문 · 실행 스크립트 · 작업 폴더 경로 ·
작업방 규칙 파일 편집 · 합칠 때 규칙 파일 표시. 규칙은 tests/fixtures/approval_now.toml."""

import os
from pathlib import Path

import pytest

from bridge.approval import load_policy, rule_files

FIX = Path(__file__).resolve().parent / "fixtures" / "approval_now.toml"
POL = load_policy(FIX)
HOME = os.path.expanduser("~")
REPO = f"{HOME}/AI_programming/foreman"
WT = f"{REPO}/.worktrees/foreman-6"
RS = f"{HOME}/AI_programming/runshoes"
BODY = "rm -rf ~/AI_programming/runshoes"


def bash(cmd, cwd=REPO):
    return POL.decide("Bash", {"command": cmd}, cwd, None, "foreman")


def tool(name, path):
    return POL.decide(name, {"file_path": path, "old_string": "a", "new_string": "b", "content": "x"}, REPO, None, "foreman")


@pytest.mark.parametrize("cmd", [
    f"bash <<'EOF'\n{BODY}\nEOF",
    f"sh <<EOF\n{BODY}\nEOF",
    f"bash -s <<'EOF'\n{BODY}\nEOF",
    f"ssh host bash <<'EOF'\n{BODY}\nEOF",
    f"cat <<'EOF' | bash\n{BODY}\nEOF",
    f"sudo zsh <<'EOF'\necho a\n{BODY}\nEOF",
])
def test_shell_heredoc_body(cmd):
    r = bash(cmd)
    assert (r.verdict, r.rule) == ("ask", "통째로-삭제")


@pytest.mark.parametrize("make", [
    lambda p: f"bash {p}",
    lambda p: p,
    lambda p: f"source {p}",
])
def test_script_body(tmp_path, make):
    p = tmp_path / "whole.sh"
    p.write_text(f"#!/bin/bash\nset -e\n{BODY}\n", encoding="utf-8")
    r = bash(make(str(p)), cwd=str(tmp_path))
    assert (r.verdict, r.rule) == ("ask", "통째로-삭제")


def test_script_written_in_same_command(tmp_path):
    r = bash(f"cat > new.sh <<'EOF'\n{BODY}\nEOF\nbash new.sh", cwd=str(tmp_path))
    assert (r.verdict, r.rule) == ("ask", "통째로-삭제")


@pytest.mark.parametrize("cmd", [
    'rm -rf "$(pwd)"',
    "rm -rf `pwd`",
    'rm -rf "$PWD"',
    'rm -rf "$(git rev-parse --show-toplevel)"',
    'd=$(pwd) && rm -rf "$d"',
    'rm -rf "$(dirname "$PWD")"',
    "rm -rf $(pwd)",
    "rm -rf ${PWD}/",
    "if true; then rm -rf ~/AI_programming/runshoes; fi",
])
def test_workdir_forms(cmd):
    if not os.path.isdir(RS):
        pytest.skip("런슈즈 폴더가 없다")
    r = bash(cmd, cwd=RS)
    assert (r.verdict, r.rule) == ("ask", "통째로-삭제")


@pytest.mark.parametrize("name, path", [
    ("Edit", f"{WT}/config/approval.toml"),
    ("Write", f"{WT}/config/notify.toml"),
    ("Write", f"{WT}/scripts/foreman-decide.sh"),
    ("Edit", f"{REPO}/config/approval.toml"),
])
def test_workroom_rule_file_edit_notifies(name, path):
    r = tool(name, path)
    assert (r.verdict, r.rule) == ("allow", "규칙파일-편집")


def test_workroom_rule_file_bash_notifies():
    r = bash("sed -i 's/a/b/' config/approval.toml", cwd=WT)
    assert (r.verdict, r.rule) == ("pass", "규칙파일-편집")


def test_workroom_other_files_plain():
    assert tool("Edit", f"{WT}/bridge/approval.py").rule == "편집"
    assert tool("Edit", f"{WT}/config/handoff.toml").rule == "편집"


# ── 대조군: 지금도 묻는 것 ─────────────────────────────
@pytest.mark.parametrize("cmd, rule", [
    (BODY, "통째로-삭제"),
    (f"bash -c '{BODY}'", "통째로-삭제"),
    ("cd ~/AI_programming/runshoes && rm -rf .", "통째로-삭제"),
    ('rm -rf "$HOME"', "통째로-삭제"),
    ("bash <<'EOF'\ngit push --force origin main\nEOF", "git-강제push"),
])
def test_still_asks(cmd, rule):
    assert (bash(cmd).verdict, bash(cmd).rule) == ("ask", rule)


# ── 대조군: 평소 명령은 묻지 않는다 ─────────────────────
@pytest.mark.parametrize("cmd", [
    "bash <<'EOF'\nls -la\nrm -rf build node_modules/.cache\nEOF",
    "ssh host bash <<'EOF'\nuptime\nEOF",
    f"cat > notes.md <<'EOF'\n{BODY}\nEOF",
    f"git commit -F - <<'EOF'\n{BODY}\nEOF",
    'rm -rf "${PWD:?}/tmp.abc"',
    'rm -rf "$(pwd)/build"',
    "rm -rf .venv build",
    'cd "$(dirname "$0")/.." && rm -rf "$OUT"',
    "bash -n whole.sh",
])
def test_everyday_not_ask(cmd):
    r = bash(cmd, cwd=RS if os.path.isdir(RS) else REPO)
    assert r.verdict != "ask", r


def test_contract_script_shape_not_ask(tmp_path):
    (tmp_path / "contract").mkdir()
    p = tmp_path / "contract" / "run-local.sh"
    p.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")/.."\nSET=${1:-main}\nOUT=contract/run/x${SET/main/}\n'
        '[ "$SET" != main ] && OUT=contract/run/x-$SET\ncleanup() {\n  docker stop "$DB" >/dev/null 2>&1 || true\n}\n'
        'trap cleanup EXIT\ndocker run -d --rm --name "$DB" --tmpfs /var/lib/mysql img\n'
        'JWT=${JWT:-$(openssl rand -base64 48)}\nrm -rf "$OUT"\nmkdir -p "$OUT"\nnode contract/record.mjs "$OUT"\n',
        encoding="utf-8")
    r = bash("contract/run-local.sh", cwd=str(tmp_path))
    assert r.verdict != "ask", r
    r = bash("bash contract/run-local.sh v6", cwd=str(tmp_path))
    assert r.verdict != "ask", r


def test_real_contract_script_not_ask():
    p = Path(RS) / "contract" / "run-spring-local.sh"
    if not p.is_file():
        pytest.skip("런슈즈 계약 시험 스크립트가 없다")
    r = POL.decide("Bash", {"command": "contract/run-spring-local.sh"}, RS, None, "runshoes")
    assert r.verdict != "ask", r


# ── D2: 합칠 때 규칙 파일 ───────────────────────────────
def test_rule_files_on_merge():
    files = ["config/approval.toml", "bridge/approval.py", "scripts/foreman-decide.sh", "config/handoff.toml",
             "docs/x.md", ".claude/settings.json"]
    assert rule_files(REPO, files, FIX) == ["config/approval.toml", "scripts/foreman-decide.sh", ".claude/settings.json"]
    assert rule_files(RS, ["config/approval.toml", "README.md"], FIX) == []
