# 「CC 화면」 탭 → 띄우는 창 · CC 창 크기 맞추기 (11-14, 코더 세션 369 · worktree foreman-2)

관리자 362의 일감(사용자 지시 11-14). 세션 368이 오늘 만든 「CC 화면」 탭(`375ca61`, `log/coder_ccscreen_20261114.md`)을 고쳤다.

## 한 일

### 1. 탭 → 띄우는 창(`bridge/static/js/ccscreen.js` `createCcWindow`)
- 패널 탭은 셋(「대화」 · 「활동」 · 「세션 정리」), 탭 줄 오른쪽 끝에 **[CC 화면 ↗] 단추**(`#pCcOpen`, 툴팁 「CC 화면 — …」). 누르면 지금 고른 세션의 CC 화면이 띄우는 창으로 뜬다
- 창은 `document.body`에 `position:fixed`, z-index 40(패널 9 · 툴팁 50 · 메뉴 60 사이). 모달이 아니라 패널 조작을 막지 않는다 — 대화 탭을 보면서 함께 둔다
- 머리줄: 「세션 N 제목」 · 「CC 창 WxH」 · [다시 붙기] · ✕. 머리줄을 끌어 옮긴다(포인터 잡기 `setPointerCapture` — iframe 위를 지나도 끌기가 끊기지 않게). 머리줄 일부(120px · 위 40px)는 늘 화면 안에 둔다(다시 잡을 수 있게)
- 오른쪽 아래 모서리(16px)를 끌어 크기. **끄는 동안은 점선 테두리(`.ccwin-ghost`)만 움직이고 놓을 때 한 번 창 크기를 바꾼다** → xterm이 한 번 맞추고 → CC 창도 한 번 바뀐다. 가장 작게 360×220
- 크기 · 자리는 `localStorage` `foreman.ccwin.geo`(try/catch, 못 써도 이 창에서는 됨) — 다음에 열 때 같은 크기. 옮기기만으로는 크기가 바뀌지 않는다
- 붙을 수 없으면 창 안에 까닭(`GET /api/terminal/cc/{sid}` reason 그대로) + [다시 붙기]. 열려 있는 동안 5초마다 다시 묻는다(368과 같음)
- 닫기(✕) → iframe `about:blank` → WS가 끊겨 보기 스크립트가 CC 창을 80×24로 되돌린다
- 패널을 접어도 · 다른 세션을 골라도 창은 그대로(아래 결정). 다시 불러오면 저절로 열리지 않는다
- 지운 것: `opanel.js` `syncCc` · `pTabCc` · `tab-cc`, `office.html` `.pcc-*` · `.ptab-cc`(탭) CSS. `store.js` `ccState` · `terminalSession`은 그대로 쓴다

### 2. CC 창 크기를 띄우는 창에 맞춤(`deploy/shell/foreman-cc-view`, `bridge/terminal.py`)
- 368의 「크기를 바꾸지 않음(보는 동안 manual로 묶기만)」을 바꿨다. 붙을 때 창 옵션 `window-size manual` + 표시 `@foreman_ccview 1`, 그리고 **자기 그룹 세션에 `client-resized` 훅** `run-shell -C 'resize-window -t @창 -x #{client_width} -y #{client_height}'`. 그룹 세션은 `status off`(손님 크기 = 창 크기)
  - 훅은 붙을 때 한 번, 손님 크기가 바뀔 때마다(= 띄우는 창 모서리를 놓을 때 한 번) 불린다
  - ttyd가 보내는 첫 크기를 따로 읽을 필요가 없다 — 붙는 순간 훅이 그 크기로 맞춘다
- **닫을 때(마지막 보기가 나갈 때) `resize-window -x 80 -y 24` → `window-size` · 표시를 푼다.** 풀어도 손님이 없으니 80×24로 남는다(시험으로 확인)
- 80×24는 **`bridge/terminal.py` `CC_REST_SIZE = (80, 24)` 한 곳**. ttyd 고정 인자로 스크립트에 넘긴다(`foreman-cc-view <소켓> 80x24 <창> <탭>` — 뒤 둘은 WS 프록시가 붙이는 `-a` 인자). 스크립트는 모양(`^\d{2,3}x\d{2,3}$`)을 본다
- 브리지 `release_cc_windows`(보기 없이 표시만 남은 창 치우기)도 「80×24로 되돌리고 풂」으로
- 사람이 정한 `window-size`(표시 없음)면 맞추지도 되돌리지도 않고 보기만 한다(368과 같음). 이때 우리 손님이 크기 계산(smallest 등)에 끼지 않게 `attach -f ignore-size`는 남겼다 — ignore-size여도 `client-resized` 훅은 불린다(시험 통과)

### 3. 셸 새로 여는 단추 — 만들지 않았다(사용자). `/api/terminal/respawn`은 그대로

## 사용자 결정(11-14, 관리자 362를 거쳐 받음)
- **띄운 채 다른 세션을 고르면: 띄운 세션 그대로, 머리줄에 세션 번호 · 제목**(따라 바뀌면 헷갈린다). 머리줄 툴팁에도 「패널에서 다른 세션을 골라도 바뀌지 않습니다」. [CC 화면 ↗]를 다른 세션에서 누르면 그때는 그 세션으로 바꾼다(창은 하나 — 사람이 그 세션에서 단추를 누른 것이니 바꾸는 것이 뜻)
- **둘이 같은 세션을 띄우면: 나중에 붙은 쪽 크기**(혼자 써서 거의 없음). 보기마다 자기 그룹 세션에 훅을 거니 붙는 순간 그 크기로 맞춰져 저절로 그렇다. 나중 것이 먼저 나가면 남은 보기의 손님 크기로 다시 맞춘다(`list-clients -t =<남은 보기>`). 마지막 보기가 나가면 80×24

## 설계와 달랐던 점
- 제안은 「붙을 때 manual + resize-window(ttyd 크기)」였는데, 크기를 바꿀 때도 따라가야 해서 tmux `client-resized` 훅으로 했다. **`resize-window -x '#{client_width}'`를 훅에 바로 쓰면 `#{…}`가 풀리지 않는다**(11-14 실험 — 훅은 불렸지만 창 그대로). `run-shell`은 형식을 풀어서 `run-shell -C '…'`(셸 없이 tmux 명령)로 감쌌다
- `set-hook -t =보기`는 「no such session」 — 세션 대상은 `=보기:`로 줘야 했다
- 그룹 세션 상태줄을 껐다 — 켜 두면 창이 손님보다 한 줄 작아(368 대조 시험 120×39) 띄운 창 맨 아래 한 줄이 tmux 상태줄로 쓰인다. 머리줄에 세션이 보이니 필요 없다
- 「창을 닫으면 80×24」 — 원래 크기(예: 100×30)로가 아니라 늘 80×24로 되돌린다(사용자 지시 그대로). 시험도 100×30 창이 닫은 뒤 80×24가 되는 것을 본다

## 확인
- `tests/test_ccscreen.py`(368 시험을 새 방식으로 고치고 더함, 모두 시험 전용 tmux 서버 own_sock — 라이브 세션에 키를 보내지 않음)
  - 붙으면 CC 창 = pty 크기(200×50, 상태줄 꺼짐), pty 크기를 바꾸고 그 손님에게 SIGWINCH → 132×40으로 따라감, 닫으면 80×24 · window-size 풀림 · 표시 없음
  - 둘: A(200×50) 붙음 → B(150×45) 붙으면 150×45 → B가 나가면 A의 200×50 → A가 나가면 80×24
  - 사람이 정한 window-size면 100×30 그대로 · manual 그대로
  - 브리지 `release_cc_windows`가 남은 표시를 80×24로 되돌리고 풂(남이 정한 smallest는 그대로)
  - 쉴 크기 인자가 이상하면(`80x24;ls`) 붙지 않음
  - **실제 ttyd(원본 `.tools/ttyd` 1.7.7) + 새 보기 스크립트**(`test_ccscreen_ttyd_keys`): `_cc_ttyd_args()` 그대로 시험 소켓에 띄우고 WS(unix 소켓, 하위 규약 tty)로 붙어, 가짜 CC 창의 고르기 메뉴(bash 스크립트 — ↓로 고르고 Enter로 정하고 Esc로 닫음)에 `\e[B` → 「> two」, Enter → 「picked-two」, 크기 바꿈 메시지(90×28) → 창 90×28, Esc → 「menu-closed」(tmux 화면과 ttyd 출력 둘 다), 연결을 닫은 뒤 80×24 · window-size 풀림. worktree에는 `.tools`가 없어 원본 폴더 것을 찾는다(없으면 건너뜀)
- `tests/test_ccscreen.py` 14 통과(ttyd 시험 포함 — 건너뛰지 않음)
- 전체 pytest(`python -m pytest` — `.venv/bin/pytest`로 부르면 원본 폴더 `bridge`를 읽어 처음에 수집 오류가 났다): **930 통과 · 1 건너뜀**(368과 같은 `test_proxy_cookie_origin_ws` — 그 시험은 worktree `.tools/ttyd`만 본다. 합친 뒤 원본에서 돈다)
- node 시험: 172 통과
- 화면 점검: 미리보기(`POST /api/sessions/369/preview`, :8200, tmux `fm-pv-foreman-2` — 남겨 둠)에 `tools/screen.py --base http://127.0.0.1:8200/ --no-term --session 369` — **세 테마 × 세 크기 × 좁게/넓게 문제 0건**(rc 0, 「audit(고정 안 됨)」 1 · 11 · 14는 문제 수에 들지 않는 값 — 368과 같음). 1024 좁은 패널에도 탭 셋과 [CC 화면 ↗]이 한 줄에 들어간다(사진 확인)
- 띄운 창 동작(scratchpad 스크립트 — screen.py의 CDP `Page` 틀을 빌려 마우스 이벤트로, 세 테마 × 1366x768 좁은 패널): 단추가 탭 줄 마지막 · 보임 / 열면 기본 760×480 / **머리줄을 끌어 패널 탭 줄 위에 겹쳐 놓고(x 801) 겹친 채 다시 잡아 끌어 옴(x 140)** / 창이 떠 있는 채 패널 「활동」 탭을 마우스로 누르면 탭이 바뀌고 창은 그대로(모달 아님) / 모서리를 끄는 중 점선 테두리만 보이고 창은 그대로 → 놓으면 +140×+90 / `foreman.ccwin.geo`에 저장 / 다른 세션(362)을 골라도 창 머리줄 「세션 369」 그대로 / ✕로 닫고 다시 열면 같은 크기 / 페이지 오류 0. 사진(magic 겹침 · site 끄는 중)을 눈으로 봤다
  - 처음 돌렸을 때 키운 창(1180×750)이 화면 높이(768)를 넘어 모서리를 잡을 수 없었다 → 창 · 끄는 테두리를 화면 안으로 묶었다(다시 돌려 654로 묶임 확인)
  - 미리보기는 `/api` · `/ccscreen`을 라이브 브리지(:8000, 368 코드)로 넘긴다 — 그래서 이 확인 중 띄운 창이 **실제로 이 세션(369) CC 창에 붙었다**(368 보기 스크립트, 보기만 — 마우스는 머리줄 · 모서리 · 패널 탭만 눌렀고 iframe에 키는 가지 않았다). 끝난 뒤 이 창 `80x24` · window-size 빈 값 · `ccv-` 세션 0을 확인했다. 사진의 CC 화면이 80×24 + tmux 상태줄인 것은 옛 스크립트라서다 — 크기 맞추기는 합친 뒤에만 보인다
  - 처음 1024 사진 한 장에 「서버 연결 끊김(1006)」 띠가 있었다 — 미리보기 이벤트 WS가 잠깐 끊긴 것으로, 다른 사진 · 다시 돌린 것에는 「연결됨」. 이 변경과 상관없다

## 합친 뒤 관리자 확인 순서(미리보기는 브리지 코드를 못 쓴다 — 보기 스크립트 · 크기는 합친 뒤에만 실제로 본다)
1. 승인 대기 0을 본 뒤 `systemctl --user restart foreman-bridge` → 브리지 로그 「ttyd(cc) 시작」, `.run/ttyd-cc.log` 오류 없음. `ps -o args= -p <ttyd-cc pid>` 끝이 `… foreman-cc-view <소켓> 80x24`
2. 쉬는 세션 하나를 골라 [CC 화면 ↗] → 띄운 창에 CC 화면. 그 창의 `tmux display -p -t <창> '#{window_width}x#{window_height}'`가 띄운 창 크기(머리줄 「CC 창 WxH」와 같음), `show-options -wqv -t <창> window-size`가 `manual`
3. 모서리를 끌어 놓은 뒤 크기가 한 번 바뀌는지(끄는 동안은 그대로), 머리줄로 패널 위에 끌어 놓아도 다시 잡아 옮길 수 있는지, 대화 탭을 누르고 글을 써도 되는지
4. 다른 세션을 골라도 창 머리줄 세션 번호가 그대로인지
5. ✕로 닫은 뒤 그 창이 `80x24` · window-size 빈 값 · `tmux ls | grep ccv-` 없음. 다시 열면 같은 크기로 열리는지
6. 고르기 창이 뜬 시험 세션(예: 시험 CC에서 `/config`)에서 화살표로 고르고 Esc로 닫히는지 — 라이브 작업 세션에는 하지 않는다
7. 끝난 세션 · 멈춰 둔 세션에서 열면 창 안에 까닭, ttyd(cc)만 PID로 끝내면 5초 안에 「CC 화면 서버(ttyd)가 떠 있지 않습니다…」 → 브리지가 다시 띄운 뒤 [다시 붙기]
8. `SELECT action, detail FROM session_action WHERE action LIKE 'ccview%' ORDER BY id DESC LIMIT 4`

## `docs/operations.md`에 바꿀 줄(서기 몫 — 건드리지 않음)
- 368이 적은 줄(「세션 정리」 · 「셸」 · CC 화면 ttyd)에 더해: 「CC 화면」은 탭이 아니라 세션 패널 탭 줄 끝 [CC 화면 ↗] 단추로 여는 띄우는 창. 보는 동안 CC 창을 띄운 창 크기에 맞추고 닫으면 80×24(`bridge/terminal.py` `CC_REST_SIZE`)로 되돌린다

## 규칙 위반
- **진행 글 머리에 영어 낱말이 두 번 섞였다**(CLAUDE.md 「항상 한국어로 — 진행 글까지」). 언제: `bridge/terminal.py` 상수 고치기 전 「Brief 상수와 브리지 치우기를 고칩니다」, 주석 고치기 전 「Brief: 동작을 틀리게 설명하는 곳…」. 왜: 글 첫머리를 쓰고 다시 보지 않았다. 바로잡음: 그 뒤 글은 쓰기 전에 보았다. 파일 · 화면 글 · 커밋에는 영향이 없다
- 위반은 아니지만 적어 둠: 시험 명령 앞에 아무 일도 하지 않는 `sed -i '' /dev/null`이 잘못 들어갔다(저장소 파일은 건드리지 않음). tmux 실험 파일은 scratchpad에 heredoc으로 만들고 고쳤다(저장소 파일 아님)
- 그 밖(저장소 파일은 Edit · Write로만, `pgrep -f` 안 씀, 긴 pytest는 뒤에서 + `timeout`, push · 브리지 다시 띄우기 안 함, `docs/operations.md` · `docs/style_guide.md` 안 건드림, 라이브 세션 tmux에 키 안 보냄, 토큰은 셸 변수로만 — 길이만 찍음)은 지켰다
