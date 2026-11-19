"""tests/test_frames_to_gif.py가 시스템 `python3 -I`로 돌리는 도우미 둘째(`.venv`에는 PIL이 없다).

    python3 -I tests/data/gif_probe_lossy.py <저장소 맨 위> <colors> <문턱>

색을 많이 줄여도 같은 점이 투명으로 남는지 보려는 장면이다. 16×16을 네 칸으로 나눠 (100,100,100), (160,100,100),
(30,200,30), (220,30,30)을 깔고, 색 수를 2로 줄이면 앞 둘이 한 색으로 합쳐져 원본과 30쯤 어긋난다(세 색 차의 합).
- 0번 장: 위 네 칸 그림
- 1번 장: 0번과 완전히 같음
- 2번 장: 0번에 점 하나(8, 8)만 흰색으로 바뀜
`build_frames`를 직접 불러 JSON 한 줄을 찍는다: `durations`는 장마다 머문 ms, `transparent`는 장마다 투명(255번) 점 수
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

repo, colors, thr = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, str(repo / "tools"))

from PIL import Image  # noqa: E402

import frames_to_gif  # noqa: E402

QUADS = [((0, 0), (100, 100, 100)), ((8, 0), (160, 100, 100)), ((0, 8), (30, 200, 30)), ((8, 8), (220, 30, 30))]


def scene(dot: bool) -> Image.Image:
    im = Image.new("RGB", (16, 16))
    for (x0, y0), rgb in QUADS:
        for y in range(y0, y0 + 8):
            for x in range(x0, x0 + 8):
                im.putpixel((x, y), rgb)
    if dot:
        im.putpixel((8, 8), (255, 255, 255))
    return im


ims = [scene(False), scene(False), scene(True)]
frames, durs = frames_to_gif.build_frames(ims, colors, 100.0, True, thr)
print(json.dumps({"durations": [round(d) for d in durs],
                  "transparent": [list(f.getdata()).count(255) for f in frames]}))
