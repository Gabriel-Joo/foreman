"""pgrep -f 자기 걸림 막기(11-11, bridge/pgrep_guard.py) — 11-09 · 11-10 실제 명령 꼴."""

import pytest

from bridge.pgrep_guard import check


def bash(cmd):
    return check("Bash", {"command": cmd})


@pytest.mark.parametrize("cmd", [
    'until ! pgrep -f "tools/screen.py"; do sleep 3; done',              # 11-09 코더 233 — 영원히 안 끝남
    "pgrep -f 'python -m pytest' && echo 다른 pytest 있음",             # 11-09 관리자 헛봄
    "pgrep -af '[p]ython -m pytest'; .venv/bin/python -m pytest -q",     # 11-10 관리자 — 대괄호도 뒤쪽 실행 글에 걸림
    "pkill -f foreman-preview",                                           # 자기 셸을 죽인다
    "ps x | grep foo; pgrep --full 'sleep 30'",
    "pgrep -u kopo17 -f bridge.main",
])
def test_denied(cmd):
    why = bash(cmd)
    assert why and why.startswith("pgrep-자기걸림") and "확인과 실행을 따로" in why


@pytest.mark.parametrize("cmd", [
    "pgrep -af '[p]ytest' || echo 없음",                                 # 대괄호 + 확인만 — 안 걸림
    "pgrep python",                                                       # -f 없음 — 프로세스 이름만 본다
    "pgrep -f \"$PAT\"",                                                  # 변수 — 글로 못 가림
    "echo pgrep -f 는 쓰지 않는다",                                       # 명령 자리가 아니다
    "git log --grep pgrep",
    "git commit -q -F - <<'EOF'\npgrep -f 함정 막기\n`pgrep -f x`가 자기에 걸림\nEOF",   # 커밋 글(heredoc) 안의 낱말
    'git commit -m "pgrep -f 막기"',
])
def test_allowed(cmd):
    assert bash(cmd) is None, cmd


def test_other_tools_and_fix_hint():
    assert check("Edit", {"command": "pgrep -f x"}) is None
    why = check("Monitor", {"command": 'until ! pgrep -f "tools/screen.py"; do sleep 3; done'})
    assert why and "`[t]ools/screen.py`" in why
    assert "자기 셸을 죽입니다" in bash("pkill -f foreman-preview")
