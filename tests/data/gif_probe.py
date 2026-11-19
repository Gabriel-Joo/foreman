"""tests/test_frames_to_gif.py가 시스템 `python3 -I`로 돌리는 도우미(`.venv`에는 PIL이 없다).

    python3 -I tests/data/gif_probe.py <저장소 맨 위> <임시 폴더> [변환 옵션...]

가짜 프레임 4장(16×16 회색 바탕)을 만들어 `tools/frames_to_gif.py`로 GIF를 만든 뒤 JSON 한 줄을 찍는다.
- 0번 장: 바탕 (100,100,100)
- 1번 장: 바탕이 (110,110,110)으로 조금 달라짐(JPEG 잡음 같은 작은 변화, 세 색 차의 합 30)
- 2번 장: 점 하나가 빨강(200,20,20)(큰 변화)
- 3번 장: 2번과 완전히 같음
`frames`는 파일에 든 장 수, `durations`는 장마다 머문 ms, `dot`은 이어 붙여 본 마지막 화면의 점 색, `transparent`는 담긴 장마다 투명 점 수
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

repo, work, opts = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
sys.path.insert(0, str(repo / "tools"))

from PIL import Image, ImageSequence  # noqa: E402

import frames_to_gif  # noqa: E402

frames = work / "frames"
frames.mkdir()
W = H = 16
for i, (bg, dot) in enumerate([(100, None), (110, None), (100, (200, 20, 20)), (100, (200, 20, 20))]):
    im = Image.new("RGB", (W, H), (bg, bg, bg))
    if dot:
        im.putpixel((8, 8), dot)
    im.save(frames / f"f{i:05d}.png")

out = work / "out.gif"
rc = frames_to_gif.main([str(frames), str(out), "--colors", "16", *opts])

# 담기로 한 장마다 투명(255번) 점이 몇 개인가, 같은 설정으로 변환 함수를 직접 불러 센다
ims = [Image.open(p).convert("RGB") for p in sorted(frames.iterdir())]
delta = "--delta" in opts
thr = int(opts[opts.index("--delta-threshold") + 1]) if "--delta-threshold" in opts else frames_to_gif.DELTA_THRESHOLD
fr, _ = frames_to_gif.build_frames(ims, 16, 100.0, delta, thr)
transparent = [list(f.getdata()).count(255) for f in fr] if delta else [0] * len(fr)

g = Image.open(out)
durs, last = [], None
for f in ImageSequence.Iterator(g):
    durs.append(f.info.get("duration"))
    last = f.convert("RGB")
print(json.dumps({"rc": rc, "frames": len(durs), "durations": durs, "transparent": transparent,
                  "dot": list(last.getpixel((8, 8))) if last else None}))
