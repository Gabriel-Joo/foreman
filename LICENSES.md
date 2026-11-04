# 에셋 출처 · 라이선스

FOREMAN 코드와 별개로, 픽셀 오피스(10단계)가 쓰는 그림 파일의 출처와 라이선스다. 파일은 **원본 그대로** 넣었다 — 자르기 · 외곽선 · 색조는 렌더러가 브라우저에서 한다(`bridge/static/js/sprites.js`). 원본 압축 파일은 저장소에 넣지 않는다(`.assets-raw/`, `.gitignore`).

## 마법학교 테마 — `bridge/static/themes/magic/sprites/`

| 팩 | 저작자 | 라이선스 | 출처 | 이 저장소의 파일 |
|---|---|---|---|---|
| Medieval Tileset (interior) | **Calciumtrice** | **CC-BY 3.0** — 출처 표시 의무 | https://opengameart.org/content/medieval-tileset | `calciumtrice/medieval_interior.png` |
| 16x16 DungeonTileset II v1.7 | 0x72 | CC0 1.0 | https://0x72.itch.io/dungeontileset-ii | `0x72/atlas.png`, `0x72/tile_list_v1.7.txt` |
| Ninja Adventure Asset Pack | Pixel-boy, AAA | CC0 1.0 | https://pixel-boy.itch.io/ninja-adventure-asset-pack | `ninja/chars/*/Walk.png · Idle.png`(16명), `ninja/items/*`, `ninja/fx/*`, `ninja/LICENSE.txt` · `README.md`(원본) |

### 출처 표시 (CC-BY 3.0)

> Medieval Tileset by **Calciumtrice**, licensed under [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/). Source: https://opengameart.org/content/medieval-tileset
> 변경: 렌더러가 표시할 때 1px 바깥 외곽선을 덧그린다(파일 자체는 원본).

작가 요청 문구(원본 dungeon tileset 안내문): "Credit should be given to Calciumtrice."

### CC0 팩 — 표시 의무는 없지만 남긴다

- **Ninja Adventure** — Pixel-boy(https://pixel-boy.itch.io/) · AAA. 원본 `README.md`: "They are released under the Creative Commons Zero (CC0) license … Attribution is not required but appreciated." 원본 `LICENSE.txt`(CC0 1.0 전문)를 함께 넣었다
- **0x72 DungeonTileset II** — 압축 안 README에는 라이선스 문장이 없고, 배포 페이지의 Asset license 칸이 "Creative Commons Zero v1.0 Universal"(2026-11-05 확인). 배포 페이지 댓글에서 작가가 출처는 "0x72"면 충분하다고 했다

## 오피스 테마 — 받아 두었지만 아직 저장소에 없다

| 팩 | 저작자 | 라이선스 | 출처 |
|---|---|---|---|
| Pixel Office | 2dPig | CC0 1.0(압축 안 `LICENSE.txt`) | https://2dpig.itch.io/pixel-office |

오피스 테마를 시트로 바꿀 때 위 표에 옮긴다.

## 받은 날 · 경로

2026-11-05. Calciumtrice는 OpenGameArt에서 직접, itch 세 팩은 사용자가 브라우저로 받았다(스크립트 다운로드는 itch가 막았다 — 공식 미러는 없었다, `docs/10_office_design.md`).
