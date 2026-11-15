"""승인 대기 한도 세 값의 순서 — 견본이 실제 설정보다 짧아 15분에 끊긴 일(11-15)을 다시 만들지 않게.

브리지 wait_s < 스크립트 curl max < CC hook timeout 이어야 한다. 홈의 ~/.claude/settings.json은 기계마다 달라 보지 않는다.
"""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _wait_s() -> int:
    d = tomllib.loads((ROOT / "config" / "approval.toml").read_text(encoding="utf-8"))
    return int(d["defaults"]["wait_s"])


def _script_max() -> int:
    src = (ROOT / "scripts" / "foreman-decide.sh").read_text(encoding="utf-8")
    m = re.search(r"permission\)\s+url=[^;]*;\s*max=(\d+)", src)
    assert m, "foreman-decide.sh에서 permission max를 찾지 못했습니다"
    return int(m.group(1))


def _sample_timeout() -> int:
    d = json.loads((ROOT / "deploy" / "hooks" / "foreman-hooks.json").read_text(encoding="utf-8"))
    return int(d["hooks"]["PermissionRequest"][0]["hooks"][0]["timeout"])


def test_permission_timeouts_ordered():
    wait_s, script_max, hook_timeout = _wait_s(), _script_max(), _sample_timeout()
    assert wait_s < script_max < hook_timeout, (
        f"승인 대기 한도 순서가 어긋났습니다: wait_s={wait_s}, curl max={script_max}, 견본 hook timeout={hook_timeout}")
