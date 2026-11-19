"""프레임(JPEG · PNG) 폴더 → GIF (13, docs/13_demo_capture.md). `.venv`에 PIL이 없어서 시스템 파이썬으로 돈다:

    python3 -I tools/frames_to_gif.py <프레임 폴더> <out.gif> --fps 10 --width 640 --colors 64
    python3 -I tools/frames_to_gif.py <프레임 폴더> <out.gif> --delta --delta-threshold 24     # 바뀐 곳만 담기

- 픽셀 그림이라 색을 줄여도 잘 버틴다. 팔레트는 전체 프레임에서 한 번 뽑아 모두 같은 팔레트로(프레임마다 색이 흔들리지 않게)
- 같은 프레임이 이어지면 하나로 묶고 머무는 시간을 늘린다(쉬는 장면이 공짜가 된다)
- 줄일 때는 NEAREST(픽셀이 뭉개지지 않게). 디더 없음(점무늬가 크기를 키우고 픽셀 그림을 더럽힌다)
- `--delta`(11-19, 마법학교 돌바닥 무늬처럼 JPEG 잡음이 많은 장면용): 보이는 화면과 거의 같은 점(세 색 차의 합이 문턱 아래)을
  투명으로 두고 바뀐 곳만 담는다. 문턱 기본 120, 글씨가 바뀌는 장면은 잔상이 남아 24쯤으로 낮춘다. 투명 칸 하나를 쓰니 색은 최대 255
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops

DELTA_THRESHOLD = 120   # 기본 문턱(R, G, B 차의 합). 낮을수록 작은 변화도 담는다(잔상이 줄고 크기가 는다)


def _changed_mask(canvas: Image.Image, im: Image.Image, threshold: int) -> Image.Image:
    """보이는 화면(canvas)과 새 프레임(im)이 문턱 이상 다른 점은 255, 나머지는 0인 'L' 그림. 둘 다 원본 RGB여야 한다(색을 줄인 그림이면 같은 점도 달라 보인다)."""
    r, g, b = ImageChops.difference(canvas, im).split()
    total = ImageChops.add(ImageChops.add(r, g), b)      # 255에서 잘린다. 문턱은 255 안에서만 뜻이 있다
    return total.point(lambda v: 255 if v >= threshold else 0)


def build_frames(ims: list[Image.Image], colors: int, step: float, delta: bool = False,
                 threshold: int = DELTA_THRESHOLD) -> tuple[list[Image.Image], list[float]]:
    """원본 RGB 프레임들 → (GIF에 담을 팔레트 프레임들, 프레임마다 머무는 ms)."""
    if delta:
        colors = min(colors, 255)                         # 투명 칸 하나(255번)를 비워 둔다
    # 공통 팔레트 — 프레임 몇 장을 이어 붙인 그림에서 한 번 뽑는다
    pick = ims[:: max(1, len(ims) // 8)]                  # 8등분 간격(장이 적으면 전부). 많아야 15장쯤
    sheet = Image.new("RGB", (pick[0].width, pick[0].height * len(pick)))
    for i, im in enumerate(pick):
        sheet.paste(im, (0, i * im.height))
    pal = sheet.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in ims]
    frames, durs = [q[0]], [step]
    if not delta:
        for i in range(1, len(ims)):
            if ImageChops.difference(ims[i - 1], ims[i]).getbbox() is None:   # 앞 장과 같다 — 머무는 시간만 늘린다
                durs[-1] += step
            else:
                frames.append(q[i])
                durs.append(step)
        return frames, durs
    transparent = 255
    # 지금 보이는 화면을 원본 RGB로 든다. 앞 원본 장과 견주면 잡음이 장마다 쌓여 번지고, 색을 줄인 그림과 견주면 줄인 오차가
    # 문턱에 더해져 같은 점이 달라 보인다(투명이 줄고 GIF가 커진다). 그려 넣은 점만 새 원본 값으로 바꾼다
    canvas = ims[0]
    for i in range(1, len(ims)):
        mask = _changed_mask(canvas, ims[i], threshold)
        if mask.getbbox() is None:                        # 문턱 아래로만 달라졌다, 머무는 시간만 늘린다
            durs[-1] += step
            continue
        f = q[i].copy()
        f.paste(transparent, mask=mask.point(lambda v: 255 - v))   # 안 바뀐 점은 투명
        f.info["transparency"] = transparent
        frames.append(f)
        durs.append(step)
        canvas = Image.composite(ims[i], canvas, mask)
    return frames, durs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=10, help="녹화한 초당 장수")
    ap.add_argument("--every", type=int, default=1, help="n장마다 한 장(초당 장수를 낮춘다)")
    ap.add_argument("--width", type=int, default=0, help="폭(0이면 그대로)")
    ap.add_argument("--colors", type=int, default=128)
    ap.add_argument("--delta", action="store_true", help="앞 장과 거의 같은 점을 투명으로 두고 바뀐 곳만 담는다(색은 최대 255)")
    ap.add_argument("--delta-threshold", type=int, default=DELTA_THRESHOLD,
                    help=f"--delta에서 이 값 아래로 달라진 점은 안 바뀐 것으로 본다(R, G, B 차의 합, 기본 {DELTA_THRESHOLD}. 글씨가 바뀌면 24쯤)")
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
    step = 1000 / a.fps * a.every
    frames, durs = build_frames(ims, a.colors, step, a.delta, a.delta_threshold)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=[round(d) for d in durs], loop=0,
                   optimize=not a.delta, disposal=1, **({"transparency": 255} if a.delta else {}))
    size = Path(a.out).stat().st_size
    colors = min(a.colors, 255) if a.delta else a.colors
    tail = f" · 바뀐 곳만(문턱 {a.delta_threshold})" if a.delta else ""
    print(f"{a.out} {size / 1e6:.2f}MB · {len(frames)}장(원래 {len(ims)}) · {ims[0].width}×{ims[0].height} · {colors}색{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
