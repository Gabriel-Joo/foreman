# 글씨 배율 범위 80~110% · 터미널 글자 그리기 어긋남 (2026-11-10, worktree `cc/foreman-3`, 세션 254 디자이너)

커밋 둘(나눔): `c6b5e0f` 배율 범위 → `82f98b3` 터미널 칸 폭 · 툴팁 · 버튼 접힘 → 이 기록 커밋(screen.py 단계 훑기 순서 한 줄 포함).
기준은 main(`1b023f1`)이다. cc/foreman의 `e409e1f` · `439ba6a`(창 이름표 확인 · 폴더 경고)는 이 브랜치에 없다 — **terminal.js가 겹친다**(아래 「합칠 때」).

## 1. 글씨 배율 범위 (사용자 11-10 — 브라우저 100% 기준, 90%가 보기 좋다)
- `uiscale.js` `STEPS = [0.8 … 1.1]`(5씩) · `DEF = 0.9`(export). 저장된 값은 `snapScale` — 없음 · 숫자 아님 → 0.9, 범위 밖 · 계단 밖 → 가장 가까운 계단(옛 1.2 → 1.1)
  - `localStorage.getItem`이 없을 때 `null` → `Number(null)=0`이라 그대로 맞추면 80%가 된다 → 없음은 따로 DEF
- 기본값이 박혀 있던 곳: `var(--ui-zoom, 1.2)` 대체값 7곳(office.html 2 · usage.html 2 · panel.css 툴팁 2 · 새 세션 창 1) → 대체값을 없애고 처음 값은 `:root { --ui-zoom:0.9 }` 한 줄(panel.css · usage.html — usage는 panel.css를 안 쓴다)
  - CSS가 JS 상수를 읽을 수는 없어 두 줄이 남는다 → `tests/js/uiscale_range.test.mjs`가 `var(--ui-zoom, …)` 대체값이 없고 두 줄이 `DEF`와 같은지 본다
- `office.js FZ = uiScale() × 1.2`의 1.2는 기본 배율이 아니라 캔버스 이름표 ↔ 탭 글씨 비율이다(11-09) — 그대로, 주석만. 이미 `uiScale()`을 따르므로 범위가 같다
- 터미널 글씨 `14 × 배율` → 11 · 12 · 13 · 14 · 15px(90% = 13px). TERM_BASE 그대로
- docs: style_guide 「4-1」 글씨 줄 · operations `--ui-scale` 예(0.8 · 1.1) · screen.py 도움말

## 2. 터미널 글자 어긋남 — 조사
라이브 셸을 건드리지 않으려고 시험 ttyd(bash 하나, UNIX 소켓) + 작은 라우터(스크래치, `bridge.preview.create_app`을 감싸 `/terminal/*` → 시험 ttyd, `/api/terminal/{session,open,window}` → 가짜 답, 나머지 → :8000 읽기)로 봤다.
- 칸 폭 공식(헤드리스로 잼): **장치 칸 = floor(글자 폭 × dpr) + round(letterSpacing)**, `letterSpacing`은 장치 px(dpr을 곱하지 않는다). 14px: 칸 8 · 글자 8.40, 13px: 7 · 7.80 — 사용자 측정과 같다. 116칸도 같다
- 헤드리스(캔버스 렌더러)에서는 글자가 칸에 눌려 겹쳐 그려지고 커서는 칸에 맞는다. 사용자 브라우저의 "커서가 `b` 자리 · 왼쪽 잘림"은 렌더러가 달라(글자가 제 폭으로 흐름) 보이는 것으로 본다 — **사용자 브라우저에서의 모습은 확인하지 못했다**
- ③ 이름표가 프롬프트를 가림 — 배치 문제가 아니었다: `terminal.js`가 iframe에 `title="런슈즈 터미널"`을 달고, `tip.js`가 title을 `data-tip`으로 옮겨 **마우스가 터미널에 들어가는 순간 툴팁을 iframe 왼쪽 아래(r.bottom 근처 → 화면 아래로 넘쳐 위로 올림) = 프롬프트 줄 위에** 띄운다. iframe 안 마우스는 부모 문서에 mouseout · mousedown을 주지 않아 **나갈 때까지 남는다**. 열고 닫는 순간 · 창이 바뀌는 순간에 마우스가 그 자리에 있으면 생긴다
- 덤으로 찾음: 막대의 경고 글(`flex:none`)이 길면 [▼ 터미널] 버튼이 줄어 "터/미"로 세로로 접혀 높이 107px — 막대(`overflow:hidden`) 밖 터미널 쪽으로 나간다(잘려서 버튼이 안 읽힘)

## 3. 한 일 (`82f98b3`)
- `uiscale.js cellSpacing(글자, dpr)` = ceil(g·dpr) − floor(g·dpr)(0 또는 1, 소수 오차 0.02) → `applyTermFont`가 글씨와 함께 `letterSpacing`을 맞추고 바뀌면 resize. 글씨 크기는 안 바꾼다
- `onDprChange` — `matchMedia('(resolution: Ndppx)')` change에서 다시 맞춤(terminal.js 한 줄). xterm 자신도 같은 방식으로 dpr을 따라간다
- iframe `title` → `aria-label`, `tip.js`는 iframe을 건너뜀(다른 iframe이 생겨도 같은 일이 없게)
- panel.css: 버튼은 `flex:none; nowrap`, 줄어드는 것은 경고 글(말줄임)
- `screen.py termAudit` 연 채로: xterm 칸 폭 ≥ 글자 폭(장치 px 올림) · 터미널 글씨 = 배율 글씨 · 이름표 줄(과 그 안 버튼 · 칸) ↔ iframe 겹침 · 툴팁 · 안내가 터미널을 덮나, 마우스를 터미널에 올린 뒤 한 번 더, 배율 전 단계 × dpr 1 · 0.7(`--no-term-sweep`으로 끔)
- JS 시험 `term_cell` 3개 · `uiscale_range` 4개

## 4. 확인
- 보정 전 화면(`c6b5e0f`)에 같은 점검: **31건**(11~14px · dpr 0.7의 15px 칸 < 글자, 버튼 겹침, 마우스 올린 뒤 「런슈즈 터미널」 툴팁이 터미널을 덮음). 보정 뒤 0건
- 세 테마 × 1920 · 1366 · 1024, **80% · 110% 모두 문제 0건**(layout · name · card · tip · prop · term). 시험 서버 :8792(위 2절) — :8000은 쓰지 않았다
- JS 77 통과, pytest 551 통과(1 건너뜀)

## 5. 설계와 달랐던 점 · 판단
- **헤드리스 `Emulation.setDeviceMetricsOverride`로 dpr을 바꾸면 `matchMedia` change가 부모 · iframe 어디에도 오지 않고, xterm도 칸을 다시 재지 않는다**(3초 기다려도 그대로). 그래서 "dpr 바꾼 직후" 점검은 헤드리스로 할 수 없어 뺐고, dpr 0.7에서 배율을 바꿀 때마다 재는 것으로 대신했다. `onDprChange`의 실제 동작(브라우저 확대 Ctrl+−)은 **미검증**
  - 같은 까닭으로 처음에 80%에서 돌리면 dpr 0.7 첫 단계가 옛 칸(css 7.00 = 장치 4.9)으로 잡혀 헛경보 9건 → 단계 훑기가 맨 위로 갔다 내려와 첫 측정 전에 글씨가 꼭 바뀌게 고침(이 기록 커밋)
- screen.py의 터미널 여는 점검은 `/api/terminal/open`(select-window)을 부른다 — screen.py 설명에 ":8000에서는 `--no-term`, 아니면 시험 ttyd 서버를 `--base`로"라고 적었다
- ttyd를 시험으로 띄울 때 알게 된 것: 명령 뒤 인자(`bash --rcfile … -i`)를 ttyd가 자기 옵션으로 읽어 segfault → 래퍼 스크립트로. UNIX 소켓 경로가 108자를 넘으면 잘려 실패 → 짧은 0700 폴더. 다 끝나고 끄고 지웠다

## 6. 합칠 때 (관리자)
- `terminal.js`: cc/foreman `e409e1f` · `439ba6a`의 `drawProj` 둘레와 겹친다 — 이쪽은 `frame.title = …` 한 줄을 `frame.setAttribute('aria-label', …)`로 바꾼 것, import 한 줄 · `onDprChange` 한 줄. 세션 253도 terminal.js를 고쳤다고 패널에 떴다
- 브리지(파이썬)는 안 바꿨다 — 화면 파일만이라 브리지를 다시 띄울 필요는 없다(브라우저 새로고침)
- 사용자 브라우저에서 볼 것: 100% · 90%에서 긴 줄 끝의 커서 위치, 터미널에 마우스를 올려도 이름표가 안 뜨는지, Ctrl+− · Ctrl+0 뒤 글자 간격
