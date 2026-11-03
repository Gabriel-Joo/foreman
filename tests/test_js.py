"""화면 쪽 순수 함수(테마 매핑, 10단계)는 node --test로 시험한다 — pytest 한 번에 같이 돌게."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_units():
    r = subprocess.run(["node", "--test", str(REPO / "tests" / "js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
