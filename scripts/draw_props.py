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


# ── 오피스(2dPig 화풍 — 정면, 밝은 색, 둥근 모서리) ─────────────
def server_rack():
    """서버랙 16x32 × 2프레임(LED 깜빡임)."""
    sheet = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for f in range(2):
        im, d = canvas(16, 32)
        d.rounded_rectangle((1, 1, 14, 31), 2, fill="#2b2f3a")
        d.rectangle((2, 2, 13, 3), fill="#3d4352")
        for k in range(6):                                           # 서버 6대
            y = 5 + k * 4
            d.rectangle((3, y, 12, y + 2), fill="#3d4352")
            on = (k + f) % 3 != 0
            d.point((4, y + 1), fill="#5dff8a" if on else "#1f5f35")
            d.point((6, y + 1), fill="#5aa2ff" if (k + f) % 2 else "#1f3a66")
            d.line((8, y + 1, 11, y + 1), fill="#262a33")
        sheet.alpha_composite(im, (f * 16, 0))
    return sheet


def whiteboard():
    """화이트보드 32x22 — 다리 달린 판, 그래프와 글씨."""
    im, d = canvas(32, 22)
    d.rectangle((3, 16, 4, 21), fill="#8a8f99"); d.rectangle((27, 16, 28, 21), fill="#8a8f99")
    d.rectangle((0, 0, 31, 16), fill="#c3c8d0")
    d.rectangle((1, 1, 30, 15), fill="#f6f8fa")
    d.line((3, 12, 8, 8, 13, 10, 18, 4), fill="#2f7de0")             # 그래프
    for k in range(3):
        d.line((20, 4 + k * 3, 28, 4 + k * 3), fill="#e0503a" if k == 0 else "#6b7280")
    d.rectangle((2, 16, 29, 16), fill="#8a8f99")                     # 받침
    d.point((25, 15), fill="#e0503a"); d.point((27, 15), fill="#2f7de0")
    return im


def copier():
    """복합기 20x20."""
    im, d = canvas(20, 20)
    d.rounded_rectangle((1, 4, 18, 19), 2, fill="#d9dde3")
    d.rectangle((2, 1, 17, 5), fill="#eef1f4")                       # 뚜껑
    d.rectangle((3, 8, 10, 10), fill="#2b2f3a")                      # 화면
    d.point((4, 9), fill="#5dff8a")
    d.rectangle((12, 8, 16, 9), fill="#9aa0aa")
    d.rectangle((3, 13, 16, 15), fill="#b8bec7")                     # 용지함
    d.rectangle((5, 11, 14, 12), fill="#ffffff")                     # 나온 종이
    return im


def bean_bag():
    """빈백 18x13."""
    im, d = canvas(18, 13)
    d.ellipse((0, 3, 17, 12), fill="#b3443a")
    d.ellipse((2, 1, 13, 9), fill="#d9594c")
    d.ellipse((4, 2, 9, 5), fill="#ee7a6c")
    return im


def coffee_machine():
    """커피머신 12x18."""
    im, d = canvas(12, 18)
    d.rounded_rectangle((0, 0, 11, 17), 2, fill="#3b3f4a")
    d.rectangle((2, 2, 9, 4), fill="#5aa2ff")                        # 화면
    d.rectangle((3, 7, 8, 8), fill="#23262e")                        # 추출구
    d.rectangle((4, 11, 7, 15), fill="#f4f0e0")                      # 컵
    d.point((5, 10), fill="#8a5a2b")
    d.point((10, 3), fill="#5dff8a")
    return im


def build_monitor():
    """빌드 모니터 26x20 — 받침 달린 큰 화면(상태 색은 렌더러가 덧칠)."""
    im, d = canvas(26, 20)
    d.rectangle((11, 15, 14, 18), fill="#5b616e"); d.rectangle((7, 18, 18, 19), fill="#5b616e")
    d.rounded_rectangle((0, 0, 25, 15), 2, fill="#23262e")
    d.rectangle((2, 2, 23, 13), fill="#11151c")
    for k in range(3):
        d.line((4, 4 + k * 3, 4 + 6 + k * 4, 4 + k * 3), fill="#5dd39e")
    return im


def phone():
    """휴대폰 5x8 — 라운지에서 누워 폰 보는 사람 손에."""
    im, d = canvas(5, 8)
    d.rectangle((0, 0, 4, 7), fill="#23262e")
    d.rectangle((1, 1, 3, 5), fill="#7fd1ff")
    d.point((2, 6), fill="#5b616e")
    return im


def main() -> int:
    groups = {
        "magic/sprites/foreman": (("round_table", round_table), ("portrait", portrait), ("wax_seal", wax_seal), ("owl_perch", owl_perch)),
        "office/sprites/foreman": (("server_rack", server_rack), ("whiteboard", whiteboard), ("copier", copier),
                                   ("bean_bag", bean_bag), ("coffee_machine", coffee_machine), ("build_monitor", build_monitor),
                                   ("phone", phone)),
    }
    for sub, items in groups.items():
        out = OUT / sub
        out.mkdir(parents=True, exist_ok=True)
        for name, fn in items:
            fn().save(out / f"{name}.png")
            print(out / f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
