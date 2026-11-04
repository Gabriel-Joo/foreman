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


# ── 현장(Ninja Adventure 화풍에 맞춤 — 채도 높고, 렌더러가 굵은 외곽선을 덧그린다) ──
STEEL, STEEL_L, STEEL_D = "#6d7f91", "#93a5b6", "#4a5866"
YEL, YEL_D, DARK = "#f2c14e", "#c98f1e", "#2b2f3a"


def forklift():
    """지게차 32x28 — 노란 몸통, 앞 포크, 운전석 지붕."""
    im, d = canvas(32, 28)
    d.rectangle((2, 4, 3, 26), fill=STEEL_D)                          # 마스트
    d.rectangle((0, 22, 9, 24), fill=STEEL)                          # 포크
    d.rectangle((10, 12, 29, 23), fill=YEL)
    d.rectangle((10, 20, 29, 23), fill=YEL_D)
    d.rectangle((12, 2, 13, 12), fill=DARK); d.rectangle((26, 2, 27, 12), fill=DARK)   # 지붕 기둥
    d.rectangle((11, 1, 28, 3), fill=DARK)
    d.rectangle((16, 8, 23, 12), fill="#3d4352")                      # 의자
    d.ellipse((12, 20, 19, 27), fill=DARK); d.ellipse((22, 20, 29, 27), fill=DARK)
    d.ellipse((14, 22, 17, 25), fill=STEEL); d.ellipse((24, 22, 27, 25), fill=STEEL)
    return im


def shutter():
    """롤셔터 32x32 × 2프레임(닫힘 · 반쯤 열림) — 벽에 붙는다."""
    sheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    for f in range(2):
        im, d = canvas(32, 32)
        d.rectangle((0, 0, 31, 3), fill=STEEL_D)                     # 상자
        d.rectangle((1, 4, 30, 31), fill=DARK)                       # 바깥(어둠)
        low = 31 if f == 0 else 16
        d.rectangle((1, 4, 30, low), fill=STEEL)
        for y in range(6, low, 3):
            d.line((1, y, 30, y), fill=STEEL_D)
        d.rectangle((13, low - 2, 18, low), fill=STEEL_L)            # 손잡이
        for x in range(0, 32, 6):                                     # 안전 줄무늬
            d.polygon([(x, 0), (x + 3, 0), (x + 1, 3), (x - 2, 3)], fill=YEL)
        sheet.alpha_composite(im, (f * 32, 0))
    return sheet


def compressor():
    """컴프레서 24x18 — 빨간 탱크, 바퀴, 게이지."""
    im, d = canvas(24, 18)
    d.rounded_rectangle((1, 6, 22, 14), 4, fill="#c0392b")
    d.line((4, 8, 19, 8), fill="#e0605a")
    d.rectangle((6, 2, 15, 6), fill=DARK)                             # 모터
    d.ellipse((16, 1, 21, 6), fill="#eeeeee"); d.point((18, 3), fill=DARK)
    d.ellipse((2, 13, 7, 17), fill=DARK); d.ellipse((16, 13, 21, 17), fill=DARK)
    return im


def drum(color):
    def f():
        im, d = canvas(12, 16)
        d.rectangle((1, 2, 10, 15), fill=color[0])
        d.ellipse((1, 0, 10, 4), fill=color[1])
        d.line((1, 6, 10, 6), fill=color[2]); d.line((1, 11, 10, 11), fill=color[2])
        d.ellipse((6, 1, 8, 2), fill=DARK)
        return im
    return f


def tool_wall():
    """공구벽 32x24 — 구멍판에 망치 · 렌치 · 드라이버 · 톱."""
    im, d = canvas(32, 24)
    d.rectangle((0, 0, 31, 23), fill="#b48a5a")
    for y in range(2, 23, 3):
        for x in range(2, 31, 3):
            d.point((x, y), fill="#8a6640")
    d.rectangle((3, 3, 4, 13), fill="#7a5530"); d.rectangle((1, 2, 6, 5), fill=STEEL_D)        # 망치
    d.line((10, 3, 10, 15), fill=STEEL, width=2); d.ellipse((8, 1, 12, 5), outline=STEEL)    # 렌치
    d.rectangle((16, 8, 17, 16), fill=STEEL_L); d.rectangle((15, 3, 18, 8), fill="#e0803a")  # 드라이버
    d.polygon([(22, 4), (29, 4), (29, 8), (22, 12)], fill=STEEL_L); d.rectangle((20, 3, 23, 6), fill="#7a5530")  # 톱
    d.rectangle((3, 17, 28, 21), fill="#8a6640")                       # 선반
    d.rectangle((5, 15, 9, 17), fill="#c0392b"); d.rectangle((12, 14, 15, 17), fill=YEL)
    return im


def workbench():
    """철제 작업대 + 바이스 32x20."""
    im, d = canvas(32, 20)
    d.rectangle((2, 8, 3, 19), fill=STEEL_D); d.rectangle((28, 8, 29, 19), fill=STEEL_D)
    d.rectangle((0, 5, 31, 8), fill=STEEL)
    d.line((0, 5, 31, 5), fill=STEEL_L)
    d.rectangle((2, 15, 29, 16), fill=STEEL_D)                         # 아래 선반
    d.rectangle((22, 1, 29, 5), fill="#2f6fb0"); d.rectangle((20, 2, 21, 4), fill=DARK)    # 바이스
    d.rectangle((5, 3, 9, 5), fill="#e0803a")                          # 공구
    return im


def cot():
    """간이침대 32x14 — 녹색 천, 접이식 다리, 베개."""
    im, d = canvas(32, 14)
    d.line((2, 9, 6, 13), fill=STEEL_D, width=1); d.line((6, 9, 2, 13), fill=STEEL_D)
    d.line((25, 9, 29, 13), fill=STEEL_D); d.line((29, 9, 25, 13), fill=STEEL_D)
    d.rectangle((0, 4, 31, 9), fill="#5d7f3a")
    d.line((0, 4, 31, 4), fill="#7da24f")
    d.rectangle((1, 2, 8, 6), fill="#eeeeee")                          # 베개
    return im


def inspect_bench():
    """검사대 28x22 × 2프레임(램프: 초록 · 빨강) — 게이지 달린 대 + 위 램프."""
    sheet = Image.new("RGBA", (56, 22), (0, 0, 0, 0))
    for f in range(2):
        im, d = canvas(28, 22)
        d.rectangle((1, 10, 26, 13), fill=STEEL)
        d.rectangle((3, 13, 4, 21), fill=STEEL_D); d.rectangle((23, 13, 24, 21), fill=STEEL_D)
        d.ellipse((5, 3, 12, 10), fill="#eeeeee"); d.ellipse((5, 3, 12, 10), outline=DARK)   # 게이지
        d.line((8, 7, 11, 5), fill="#c0392b")
        d.rectangle((18, 1, 21, 10), fill=DARK)                         # 램프 기둥
        d.ellipse((16, 0, 23, 5), fill="#5dd39e" if f == 0 else "#ff5b4a")
        sheet.alpha_composite(im, (f * 28, 0))
    return sheet


def blueprint_table():
    """도면 탁자 36x22 — 나무 탁자 위 파란 도면 + 두루마리통."""
    im, d = canvas(36, 22)
    d.rectangle((3, 12, 4, 21), fill="#6b4a2a"); d.rectangle((31, 12, 32, 21), fill="#6b4a2a")
    d.rectangle((0, 6, 35, 12), fill="#a0673a")
    d.rectangle((4, 4, 24, 10), fill="#2f6fb0")                        # 도면
    for x in range(6, 24, 4):
        d.line((x, 5, x, 9), fill="#7fb7ff")
    d.rectangle((8, 6, 16, 8), outline="#ffffff")
    d.rectangle((27, 0, 31, 9), fill="#c49a6c"); d.ellipse((27, 0, 31, 2), fill="#e8d3a8")   # 통
    return im


def steel_shelf():
    """철제 선반 32x30 — 자재 상자 · 파이프 묶음."""
    im, d = canvas(32, 30)
    d.rectangle((0, 0, 1, 29), fill=STEEL_D); d.rectangle((30, 0, 31, 29), fill=STEEL_D)
    for y in (8, 18, 28):
        d.rectangle((0, y, 31, y + 1), fill=STEEL)
    d.rectangle((3, 2, 11, 8), fill="#c49a6c"); d.rectangle((13, 4, 20, 8), fill="#a0673a")
    for k in range(4):
        d.ellipse((3 + k * 6, 12, 8 + k * 6, 17), fill=STEEL_L); d.ellipse((5 + k * 6, 14, 6 + k * 6, 15), fill=DARK)   # 파이프 끝
    d.rectangle((4, 22, 13, 28), fill="#5d7f3a"); d.rectangle((16, 23, 27, 28), fill="#c0392b")
    return im


def fan():
    """선풍기 12x20."""
    im, d = canvas(12, 20)
    d.rectangle((5, 10, 6, 18), fill=STEEL_D); d.rectangle((2, 18, 9, 19), fill=STEEL_D)
    d.ellipse((0, 0, 11, 11), fill="#bfe8ff"); d.ellipse((0, 0, 11, 11), outline=STEEL)
    d.line((2, 5, 9, 6), fill=STEEL); d.line((5, 2, 6, 9), fill=STEEL); d.ellipse((4, 4, 7, 7), fill=STEEL_D)
    return im


def cone():
    im, d = canvas(10, 12)
    d.rectangle((0, 10, 9, 11), fill=DARK)
    d.polygon([(2, 10), (7, 10), (5, 0), (4, 0)], fill="#f07a2a")
    d.line((3, 6, 6, 6), fill="#ffffff"); d.line((3, 3, 5, 3), fill="#ffffff")
    return im


def pallet():
    """팔레트 + 상자 24x18."""
    im, d = canvas(24, 18)
    d.rectangle((0, 14, 23, 17), fill="#a0673a")
    for x in (1, 10, 19):
        d.rectangle((x, 15, x + 3, 17), fill="#6b4a2a")
    d.rectangle((2, 4, 12, 14), fill="#c49a6c"); d.rectangle((12, 7, 21, 14), fill="#b48a5a")
    d.line((2, 9, 12, 9), fill="#8a6640"); d.line((7, 4, 7, 14), fill="#8a6640")
    d.rectangle((13, 9, 17, 10), fill="#ffffff")                       # 송장
    return im


def truck():
    """트럭 48x30 — 짐칸 + 운전석(출하 끝)."""
    im, d = canvas(48, 30)
    d.rectangle((0, 4, 31, 22), fill="#d9dde3"); d.rectangle((0, 4, 31, 6), fill=STEEL_L)
    d.rectangle((3, 10, 28, 12), fill="#2f6fb0")                        # 줄무늬
    d.rectangle((32, 10, 46, 22), fill="#2f6fb0"); d.rectangle((35, 12, 43, 16), fill="#bfe8ff")
    d.rectangle((30, 20, 47, 23), fill=DARK)
    for x in (4, 20, 37):
        d.ellipse((x, 20, x + 8, 28), fill=DARK); d.ellipse((x + 3, 23, x + 5, 25), fill=STEEL)
    return im


def gauge():
    im, d = canvas(10, 10)
    d.ellipse((0, 0, 9, 9), fill="#eeeeee"); d.ellipse((0, 0, 9, 9), outline=DARK)
    d.line((5, 5, 7, 2), fill="#c0392b"); d.point((5, 5), fill=DARK)
    return im


def helmet_rack():
    """안전모 걸이 20x20 — 벽 걸이에 노랑 · 하양 · 파랑."""
    im, d = canvas(20, 20)
    d.rectangle((0, 2, 19, 3), fill="#6b4a2a")
    for k, c in enumerate((YEL, "#eeeeee", "#2f6fb0")):
        x = 1 + k * 6
        d.pieslice((x, 4, x + 6, 12), 180, 360, fill=c); d.rectangle((x - 1, 8, x + 7, 9), fill=c)
    d.rectangle((2, 13, 17, 19), fill="#a0673a"); d.rectangle((4, 14, 9, 18), fill="#eeeeee")   # 서류철
    return im


def radio():
    im, d = canvas(6, 10)
    d.rectangle((0, 3, 5, 9), fill=DARK); d.rectangle((1, 0, 1, 3), fill=DARK)
    d.rectangle((1, 4, 4, 6), fill="#5dd39e"); d.point((3, 8), fill="#c0392b")
    return im


def mug_s():
    im, d = canvas(7, 7)
    d.rectangle((0, 1, 4, 6), fill="#eeeeee"); d.rectangle((5, 2, 6, 4), outline="#eeeeee")
    d.line((1, 1, 3, 1), fill="#6b4220")
    return im


def newspaper():
    im, d = canvas(10, 8)
    d.rectangle((0, 0, 9, 7), fill="#e8e4d8")
    for y in (2, 4, 6):
        d.line((1, y, 8, y), fill="#8a8f99")
    d.rectangle((1, 1, 4, 3), fill="#5b616e")
    return im


def main() -> int:
    groups = {
        "magic/sprites/foreman": (("round_table", round_table), ("portrait", portrait), ("wax_seal", wax_seal), ("owl_perch", owl_perch)),
        "office/sprites/foreman": (("server_rack", server_rack), ("whiteboard", whiteboard), ("copier", copier),
                                   ("bean_bag", bean_bag), ("coffee_machine", coffee_machine), ("build_monitor", build_monitor),
                                   ("phone", phone)),
        "site/sprites/foreman": (("forklift", forklift), ("shutter", shutter), ("compressor", compressor),
                                 ("drum_blue", drum(("#2f6fb0", "#4f8fd0", "#1f4f80"))), ("drum_red", drum(("#c0392b", "#e0605a", "#80201a"))),
                                 ("tool_wall", tool_wall), ("workbench", workbench), ("cot", cot), ("inspect_bench", inspect_bench),
                                 ("blueprint_table", blueprint_table), ("steel_shelf", steel_shelf), ("fan", fan), ("cone", cone),
                                 ("pallet", pallet), ("truck", truck), ("gauge", gauge), ("helmet_rack", helmet_rack),
                                 ("radio", radio), ("mug", mug_s), ("newspaper", newspaper)),
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
