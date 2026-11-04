"""FOREMAN이 직접 그린 픽셀 소품(10단계) — 에셋 팩에 없는 것. 결과는 CC0(LICENSES.md).

    ~/llm_env/bin/python scripts/draw_props.py      # Pillow가 있는 파이썬

마법학교: 원탁(돌) · 초상화 · 밀랍 도장 · 부엉이 횃대(눈 깜빡임 4프레임).
오피스 · 현장 소품도 여기에 더한다. 외곽선은 그리지 않는다 — 렌더러가 1px 외곽선을 덧그린다(theme.json defs의 외곽선 칸).
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "bridge/static/themes"


def canvas(w, h):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def px(d, pts, c):
    for p in pts:
        d.point(p, fill=c)


# ── 마법학교 ─────────────────────────────────────────────
def round_table():
    """돌 원탁 32x24 — 위에서 비스듬히 본 타원 상판 + 두께 + 받침, 상판에 새긴 원."""
    im, d = canvas(32, 24)
    d.rectangle((12, 15, 19, 22), fill="#4d4a57")                    # 받침
    d.rectangle((10, 21, 21, 23), fill="#3f3c48")
    d.ellipse((1, 4, 30, 19), fill="#5b5866")                        # 두께(아래쪽이 보인다)
    d.ellipse((1, 1, 30, 15), fill="#8d8a99")                        # 상판
    d.ellipse((3, 2, 22, 10), fill="#a3a0af")                        # 빛
    d.ellipse((1, 1, 30, 15), outline="#6c6979")
    d.ellipse((8, 4, 23, 12), outline="#6c6979")                     # 새긴 원
    px(d, [(15, 8), (16, 8), (15, 7), (16, 7)], "#b9e4ff")           # 가운데 보석
    return im


def portrait():
    """초상화 16x20 — 금테, 어두운 바탕, 흰 수염 마법사 반신."""
    im, d = canvas(16, 20)
    d.rectangle((0, 0, 15, 19), fill="#8a6d15")
    d.rectangle((1, 1, 14, 18), fill="#c9a227")
    d.rectangle((2, 2, 13, 17), fill="#2e3b33")
    d.polygon([(4, 17), (5, 11), (10, 11), (11, 17)], fill="#5b3a7a")   # 로브
    d.ellipse((5, 5, 10, 10), fill="#e8c7a0")                        # 얼굴
    d.polygon([(5, 9), (10, 9), (9, 14), (6, 14)], fill="#eeeeee")   # 수염
    d.polygon([(4, 6), (7, 1), (11, 6)], fill="#3e2a5c")             # 모자
    px(d, [(6, 7), (9, 7)], "#1a1620")
    px(d, [(1, 1), (14, 1), (1, 18), (14, 18)], "#f2d36b")            # 테 모서리
    return im


def wax_seal():
    """밀랍 도장 16x16 — 붉은 밀랍 웅덩이에 찍힌 문양 + 옆에 놓인 나무 도장."""
    im, d = canvas(16, 16)
    d.ellipse((1, 7, 10, 15), fill="#7a1519")
    d.ellipse((1, 6, 10, 14), fill="#b3242a")
    d.ellipse((3, 7, 8, 12), outline="#7a1519")
    px(d, [(5, 9), (6, 9), (5, 10), (6, 10), (4, 9), (7, 10)], "#d94a4f")
    d.rectangle((11, 3, 13, 11), fill="#7a5530")                     # 도장 손잡이
    d.ellipse((10, 1, 14, 5), fill="#9b7040")
    d.rectangle((10, 11, 14, 14), fill="#c9a227")                    # 놋쇠 머리
    px(d, [(12, 12)], "#8a6d15")
    return im


def owl_perch():
    """부엉이 횃대 16x32 × 4프레임(눈: 뜸 · 뜸 · 뜸 · 감음) — 나무 T자 횃대 위."""
    sheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    for f in range(4):
        im, d = canvas(16, 32)
        d.rectangle((7, 14, 8, 30), fill="#6b4a2a")                  # 기둥
        d.rectangle((3, 29, 12, 31), fill="#4f361f")                 # 받침
        d.rectangle((1, 13, 14, 14), fill="#7a5530")                 # 가로대
        d.ellipse((3, 3, 12, 14), fill="#8b5a2b")                    # 몸
        d.ellipse((5, 8, 10, 14), fill="#c49a6c")                    # 배
        px(d, [(4, 2), (4, 3), (11, 2), (11, 3)], "#6b4220")         # 귀깃
        if f < 3:
            d.ellipse((4, 5, 7, 8), fill="#f4f0e0"); d.ellipse((8, 5, 11, 8), fill="#f4f0e0")
            px(d, [(5, 6), (6, 6), (9, 6), (10, 6)], "#1a1620")
            px(d, [(5, 6), (9, 6)], "#f2c14e")
        else:
            d.line((4, 7, 7, 7), fill="#4f361f"); d.line((8, 7, 11, 7), fill="#4f361f")
        px(d, [(7, 8), (8, 8), (7, 9)], "#e09a2a")                   # 부리
        px(d, [(5, 14), (6, 14), (9, 14), (10, 14)], "#e09a2a")      # 발
        sheet.alpha_composite(im, (f * 16, 0))
    return sheet


def main() -> int:
    magic = OUT / "magic/sprites/foreman"
    magic.mkdir(parents=True, exist_ok=True)
    for name, fn in (("round_table", round_table), ("portrait", portrait), ("wax_seal", wax_seal), ("owl_perch", owl_perch)):
        fn().save(magic / f"{name}.png")
        print(magic / f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
