# 입력 칸 높이 손잡이: 눌렀을 때도 골라진 표시 + 호버 글 (foreman-8, 11-15)

## 한 일
- `bridge/static/office.html`: 손잡이 CSS를 `:focus-visible`에서 `:focus`로 바꾸고(가운데 막대 색), `.pgrip:focus`에 브라우저 기본과 같은 테두리(`outline: auto 1px -webkit-focus-ring-color`)를 직접 그렸다
- `bridge/static/js/opanel.js`: 호버 글을 「클릭한 뒤 ↑↓로도 바꿉니다」로 고쳤다. 끌기 · 더블클릭 · 키보드 코드는 그대로다

## 원인 (사진과 숫자로 확인)
- 418 log의 「마우스로 눌러도 `:focus-visible` 참」은 틀렸다. 이번 측정에서 마우스로 누른 뒤 `:focus`는 참, `:focus-visible`은 거짓이었다. (브라우저는 마우스 이벤트 직후 스크립트가 준 포커스에 `:focus-visible`을 켜지 않는다.) ↑↓를 한 번 누르고 나서야 참이 됐다. 418 때는 ↑ 이후 값을 읽었던 것으로 보인다
- 손잡이가 포커스를 가졌다는 표시는 두 가지다. 가운데 막대 색(호버와 같은 색이라 마우스가 위에 있으면 구별이 안 된다)과 브라우저 기본 흰 테두리(`:focus-visible` 전용). 마우스로 눌렀을 때는 둘 다 `:focus-visible`에 매여 있어 아무것도 안 그려졌다
- 끌기 클래스 `drag`가 표시를 덮는 것은 아니었다(끝난 뒤 `drag`는 빠지고 포커스는 남는다)
- 고침: `:focus`로 그리면 포커스를 가진 동안은 어떤 방식으로 얻었든 같은 모양이다. 브라우저 판정에 기대지 않는다

## 사진 (헤드리스 크로미움, 진짜 마우스 · 키 이벤트, 1366 × 768, 세션 423 패널, 3배 확대)
경로는 `/tmp/claude-1000/-home-kopo17-AI-programming-foreman--worktrees-foreman-8/69baf4b6-1b5a-4450-8eae-03b49df683ed/scratchpad/` 아래(재부팅 · 청소로 지워질 수 있음).
- `after/a_tab.png`, `after/b2_click_away.png`: 고치기 전. (가) 탭은 흰 테두리 + 막대 색, (나) 마우스 뒤는 막대 색만이라 호버와 구별이 안 됨
- `after2/a_tab.png` (가) 탭으로 짚음, `after2/b2_click_away.png` (나) 눌렀다 떼고 마우스를 치움: **두 사진이 같은 표시**(흰 테두리 + 밝은 막대)
- `after2/c1_convo.png` (다) 대화 칸을 누른 뒤, `after2/c2_input.png` 입력 칸을 누른 뒤: 손잡이 표시 없음(막대는 기본 회색)
- `after2/b1_click_hover.png` 눌렀다 뗀 직후(마우스 위), `after2/d_after_drag.png` 끌고 난 뒤도 같은 표시

## 숫자 (418 표와 같은지)
| 단계 | 활성 요소 / 칸 높이 | 418 |
|---|---|---|
| (가) Shift+Tab | pGrip / 42, `:focus` 참, `:focus-visible` 참 | 같음 |
| (나) 눌렀다 뗌 | pGrip / 42, `:focus` 참, `:focus-visible` 거짓 | 달랐던 것은 표시뿐 |
| ↑ 한 번 / ↓ 한 번 | 66 / 42 | 66 / 42 |
| (다) 대화 칸 · 입력 칸 누름 | BODY · pText, 손잡이 `:focus` 거짓 | |
| 위로 80 끌기 | 131 | 131 |
| 위로 20 자리로 되돌림 | 64 | 64 |
| 위 끝 넘김 | 345 | 345 |
| 끝에서 30 되돌림 | 312 | 312 |
| 더블클릭 | 42 | 42 |

- 호버 글 확인: `높이 조절 — 끌어서 입력 칸 높이를 바꿉니다. 클릭한 뒤 ↑↓로도 바꿉니다. 더블클릭하면 원래 높이로 돌아갑니다.`
- 페이지 오류 0. `node --test tests/js/` 198개 통과. `tools/screen.py --base http://127.0.0.1:8201/ --no-term` 세 테마 문제 0건(tipAudit 0/301 · 0/326)
- 다만 Firefox 등 다른 브라우저의 테두리 모양은 보지 못했다(`outline: auto`와 `-webkit-focus-ring-color`는 Firefox도 받아들이는 값이다)

## docs
이 손잡이를 적은 docs 절이 없어 고치지 않았다. `docs/operations.md` · `docs/style_guide.md`는 건드리지 않았다.

## 되돌리는 법
`git revert <이 커밋>`. 화면 파일만 바뀌어 새로고침이면 된다. 미리보기(:8201)는 껐고 서브에이전트 · 예약은 없다.

## 규칙 위반
규칙 위반 없음.
