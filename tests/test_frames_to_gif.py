"""tools/frames_to_gif.py `--delta`(바뀐 곳만 담기, 11-19). 시스템 `python3`의 PIL로 도는 도구라 도우미(tests/data/gif_probe.py)를
`python3 -I`로 따로 돌려 JSON을 받는다. 시스템 파이썬에 PIL이 없으면 건너뛴다."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "tests" / "data" / "gif_probe.py"


def _has_pil() -> bool:
    if not shutil.which("python3"):
        return False
    return subprocess.run(["python3", "-I", "-c", "import PIL"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not _has_pil(), reason="시스템 python3에 PIL이 없어 GIF 시험을 건너뜁니다")


def probe(tmp_path: Path, *opts: str) -> dict:
    r = subprocess.run(["python3", "-I", "-W", "ignore", str(PROBE), str(REPO), str(tmp_path), *opts],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_default_is_unchanged_without_delta(tmp_path):
    """옵션이 없으면 전과 같다: 같은 프레임만 묶고 투명 점이 없다(잡음 같은 작은 변화도 새 장이다)."""
    r = probe(tmp_path)
    assert r["frames"] == 3 and r["durations"] == [100, 100, 200]
    assert r["transparent"] == [0, 0, 0] and r["dot"] == [200, 20, 20]


def test_delta_keeps_only_changed_pixels(tmp_path):
    """문턱 120: 작은 변화(합 30)는 무시해 앞 장에 묶고, 점 하나가 바뀐 장은 그 점만 담고 나머지 255칸은 투명이다."""
    r = probe(tmp_path, "--delta")
    assert r["frames"] == 2 and r["durations"] == [200, 200]
    assert r["transparent"] == [0, 255]
    assert r["dot"] == [200, 20, 20]          # 투명 위로 이어 붙여도 점은 새 색이다


def test_delta_threshold_changes_result(tmp_path):
    """문턱을 24로 낮추면 작은 변화(30)도 담긴다. 문턱이 아주 높으면 아무것도 안 바뀐 장면이 되어 첫 장 하나만 남는다."""
    (tmp_path / "low").mkdir()
    (tmp_path / "high").mkdir()
    low = probe(tmp_path / "low", "--delta", "--delta-threshold", "24")
    assert low["frames"] == 3 and low["durations"] == [100, 100, 200]
    high = probe(tmp_path / "high", "--delta", "--delta-threshold", "300")
    assert high["frames"] == 1 and high["durations"] == [400] and high["dot"] == [100, 100, 100]
