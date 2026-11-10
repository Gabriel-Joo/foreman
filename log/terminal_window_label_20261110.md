# 터미널 이름표가 거짓이 되던 것 — 보이는 창을 열려 있는 동안 확인 (2026-11-10, worktree `cc/foreman`)

사용자 보고(11-10): 이름표는 「런슈즈 터미널」인데 프롬프트는 petmint-rag-chatbot 폴더, tmux 상태줄은 `1:petmint-rag-chatbot 2:runshoes-`.

## 조사
- tmux 실제 상태: 보이는 창 = 1번 `petmint-rag-chatbot`(폴더 petmint). 0번 `foreman` 창의 폴더도 petmint-rag-chatbot
- 까닭: 이름표는 [▲ 터미널]을 열 때 `/api/terminal/open`이 돌려준 값(`shown`)을 그대로 쥔다. 그 뒤 다시 묻지 않는다.
  tmux의 "보이는 창"은 세션 하나에 하나라, 다른 탭 · CC 부탁 미리 채우기(`terminal.py prefill`의 select-window) · tmux 키가 바꾸면 이름표만 남는다
- "고른 것과 다른 터미널입니다" 경고는 고른 것 ↔ 그때 돌려받은 값만 비교해, 창이 바뀐 뒤에는 뜨지 않았다
- 누가 이번에 창을 바꿨는지는 확인하지 못했다

## 한 일
- `GET /api/terminal/window` — `current()`(창을 바꾸지 않음)를 돌려준다 (`bridge/api/terminal.py`)
- `store.terminalWindow()`, `terminal.js checkWindow` — 터미널이 열려 있는 동안 3초마다 확인, 바뀌면 이름표(`shown`)를 따라가고 고른 것과 다르면 "고른 것(런슈즈)과 다른 터미널입니다 — 지금 보이는 것은 FOREMAN 터미널입니다". 못 읽으면 "지금 보이는 창을 확인하지 못했습니다"
- 시험: `test_proxy_cookie_origin_ws`에 창 읽기(인증 401 · 열기 뒤 같은 창 · 바꾼 뒤 따라감). 전체 pytest 551 통과(1 건너뜀) · JS 시험 전부 통과

## 고치지 않은 것 · 남은 것
- 근본 해결(탭마다 자기 창을 보게 — tmux 그룹 세션 `new-session -t` 또는 프로젝트별 ttyd): 브리지 구조 변경이라 따로. 지금은 어긋남을 알리기만 한다
- 왼쪽 잘림 · 이름표가 프롬프트 줄을 가림: 원인 미확정. 사용자 측정(터미널 접힌 채): dpr 0.698(브라우저 확대 약 70%), 창 2752 CSS px, 글씨 18px, xterm 134칸 → 칸 너비 약 10.8px면 약 1447px로 터미널 칸 1376px보다 넓을 수 있다(열린 채 재측정 필요). 소수 배율에서 xterm 칸 계산이 어긋난다는 가설
- 화면 확인은 못 했다(라이브 셸을 건드리지 않으려 screen.py 안 돌림). 브리지(파이썬)가 바뀌어 합친 뒤 원본 세션이 다시 띄워야 한다

## 추가 (같은 날, 사용자 재보고)
- 사용자: 100% · 글씨 100%에서도 같음. FOREMAN 창인데 프롬프트는 `~/AI_programming/petmint-rag-chatbot` 폴더(`[foreman] … petmint-rag-chatbot$`)
- 까닭: 창 이름(`foreman`)은 맞고, 그 셸이 `cd`로 petmint 폴더에 들어가 있었다(tmux 버퍼에 `cd … && git push`). 창 이름만 보는 이름표 확인으로는 못 잡는다
- 한 일: 창의 폴더 경로에 다른 프로젝트 이름이 든 폴더가 있으면 막대에 "FOREMAN 터미널인데 셸은 펫퍼민트 폴더에 들어가 있습니다" (`terminal.js drawProj`, 저장소 경로가 화면에 없어 경로 조각으로 비교)
- 측정(100%, 터미널 연 채): 이름표 줄 y 310~346 · iframe 346부터 · xterm 5,5 안 928×323, 116칸, 스크롤 없음 — 배치는 정상. tmux 버퍼에는 `git push`가 온전 → 잘림은 브라우저가 그리는 단계
- 사용자 관찰: 입력 커서가 줄 끝이 아니라 `chatbot`의 `b` 위치 → 칸 폭(8.0px로 잰 값, 14px 글씨의 실제 글자 폭은 약 8.4px)과 글자 폭이 달라 글자와 커서가 어긋난 것으로 보인다. 미확정 — 콘솔 측정(캔버스/DOM 렌더러 · 첫 칸 위치) 대기
