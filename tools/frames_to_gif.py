"""프레임(JPEG · PNG) 폴더 → GIF (13, docs/13_demo_capture.md). `.venv`에 PIL이 없어서 시스템 파이썬으로 돈다:

    python3 -I tools/frames_to_gif.py <프레임 폴더> <out.gif> --fps 10 --width 640 --colors 64

- 픽셀 그림이라 색을 줄여도 잘 버틴다. 팔레트는 전체 프레임에서 한 번 뽑아 모두 같은 팔레트로(프레임마다 색이 흔들리지 않게)
- 같은 프레임이 이어지면 하나로 묶고 머무는 시간을 늘린다(쉬는 장면이 공짜가 된다)
- 줄일 때는 NEAREST(픽셀이 뭉개지지 않게). 디더 없음(점무늬가 크기를 키우고 픽셀 그림을 더럽힌다)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=10, help="녹화한 초당 장수")
    ap.add_argument("--every", type=int, default=1, help="n장마다 한 장(초당 장수를 낮춘다)")
    ap.add_argument("--width", type=int, default=0, help="폭(0이면 그대로)")
    ap.add_argument("--colors", type=int, default=128)
    a = ap.parse_args(argv)
    files = sorted(p for p in Path(a.frames).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:: a.every]
    if not files:
        print("프레임이 없습니다", file=sys.stderr)
        return 1
    ims = []
    for f in files:
        im = Image.open(f).convert("RGB")
        if a.width and im.width != a.width:
            im = im.resize((a.width, round(im.height * a.width / im.width)), Image.NEAREST)
        ims.append(im)
    # 공통 팔레트 — 프레임 몇 장을 이어 붙인 그림에서 한 번 뽑는다
    pick = ims[:: max(1, len(ims) // 8)][:8]
    sheet = Image.new("RGB", (pick[0].width, pick[0].height * len(pick)))
    for i, im in enumerate(pick):
        sheet.paste(im, (0, i * im.height))
    pal = sheet.quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in ims]
    step = 1000 / a.fps * a.every
    frames, durs = [q[0]], [step]
    for i in range(1, len(ims)):
        if ImageChops.difference(ims[i - 1], ims[i]).getbbox() is None:   # 앞 장과 같다 — 머무는 시간만 늘린다
            durs[-1] += step
        else:
            frames.append(q[i])
            durs.append(step)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=[round(d) for d in durs], loop=0,
                   optimize=True, disposal=1)
    size = Path(a.out).stat().st_size
    print(f"{a.out} {size / 1e6:.2f}MB · {len(frames)}장(원래 {len(ims)}) · {ims[0].width}×{ims[0].height} · {a.colors}색")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
