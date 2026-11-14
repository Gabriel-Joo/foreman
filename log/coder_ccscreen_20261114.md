# 「CC 화면」 탭 · 입력 칸 글 검사 · 이름 정리 · [셸 비우기] (11-14, 코더 세션 368 · worktree foreman-2)

관리자 362의 일감(사용자 지시 11-14). 세션에 CC 창(권한 · 계획 승인 · 안내 · 고르기)이 떠 있으면 FOREMAN에서 볼 수 없어 사용자가 VNC로 들어가 Esc로 닫았다.

## 한 일

### 1. 「CC 화면」 탭
- ttyd를 하나 더: `.run/ttyd-cc.sock`, `-b /ccscreen`, `-m 8`, `-W -a`, 제목 「CC 화면」. 셸 ttyd와 같은 `_supervise` 틀(`bridge/terminal.py` — `_supervise(key, args, sock)`로 일반화, `_procs` 사전, `running` · `cc_running`). 로그 `.run/ttyd-cc.log`
- 보기 스크립트 `deploy/shell/foreman-cc-view <tmux 소켓> <창 %N> <탭>` — 그 창의 tmux 세션에 그룹 세션 `ccv-<탭>-<pid>`를 만들어 `attach -f ignore-size`, 붙은 뒤 `destroy-unattached on`, mouse off. 모양(`%숫자` · 탭 모양) · 창이 실제로 있는지 다시 보고, 아니면 까닭(「~습니다」)을 띄우고 끝낸다
- 브라우저는 세션 번호만: `/ccscreen/?arg=<세션 번호>&arg=<탭>` → WS 프록시 `ccscreen_ws`가 쿠키 · 같은 출처 → `_cc_args`(숫자 · 탭 모양만, 그 밖은 거절) → `TerminalManager.cc_target`(DB `character_session` type=agent → `live_sessions` 살아 있는 claude → `_tmux_env` TMUX · TMUX_PANE → 같은 tmux 서버(소켓 realpath) → `%N` 모양 → `display-message`로 창이 있고 닫히지 않았고 그 pane_pid가 claude 자신이나 조상) → 확인한 `%N`만 ttyd 인자로
- `GET /api/terminal/cc/{sid}` — 붙을 수 있나 / 까닭. ttyd가 죽었으면 「CC 화면 서버(ttyd)가 떠 있지 않습니다 — 브리지 로그(.run/ttyd-cc.log)를 확인해 주세요」. `pane`은 화면에 돌려주지 않는다
- 쿠키: `/api/terminal/session`이 같은 쿠키를 `Path=/terminal` · `Path=/ccscreen` 둘에 붙인다
- 기록: WS가 확인되어 붙을 때 `session_action` `ccview-open`, 끝날 때 `ccview-close`(detail: tmux 세션 · 창 · 크기 · 탭 · 본 초). 키는 남기지 않는다
- 남은 것 치우기: `sweep_views(prefix="ccv-")`(브리지 시작 · CC 화면 연결마다) + `release_cc_windows`(아래 크기 묶음)
- 화면: `bridge/static/js/ccscreen.js`(새) · `opanel.js` `TABS`에 「CC 화면」, 탭이 보일 때만(패널 펼침 · 세션 고름 · 그 탭) iframe을 붙이고 아니면 `about:blank`로 끊는다. 다시 불러올 때 저절로 붙지 않게 이 탭은 기억하지 않는다. 5초마다 다시 물어 까닭을 띄운다. [다시 붙기]. `office.html` CSS `.ptab-cc` 등
- `store.js` `ccState` · `terminalClear`

### 2. 브리지 넣기와 사람 입력이 섞이지 않게
- **확인 결과: 원래 거절하지 않았다.** `screen_state`는 입력 칸이 있으면 그 안 글과 상관없이 「prompt」를 돌려주고(`tests/test_inject_screen.py`의 `PROMPT_DRAFT`도 「prompt」), `clear_screen`은 「prompt」면 바로 돌아가 붙여넣었다. 사람이 반쯤 친 글 뒤에 브리지 글이 붙어 함께 제출될 수 있었다
- 고침: `clear_screen`이 화면을 색 포함(`capture-pane -e`)으로 한 번 떠서, 색을 벗긴 글로 `screen_state`(stallwatch와 같은 판정 — 바꾸지 않음), 색 포함 글로 `typed_in_box`를 본다. 입력 칸(가로줄 사이)에 글이 있으면 Esc · 붙여넣기 · Enter 어느 것도 보내지 않고 `Refused("입력 칸에 사람이 치던 글이 있어 넣지 않았습니다 — 그 세션 대화창(CC 화면)을 확인해 주세요")`. Esc로 안내 창을 닫은 뒤에도 같은 검사. 일하는 중(busy)이든 아니든
- 흐린 안내 · 제안 글(SGR 2, 회색 256색 232~250 · 8 · 90, 회색 24비트)과 커서 칸(반전 SGR 7)은 친 글로 보지 않는다. 빈 칸 실측(11-14 `capture-pane -e`, 쉬는 세션 둘 — 읽기만): `\e[39m❯` + NBSP, 가로줄은 `\e[38;5;244m`
- 로그에는 글자 수만(글은 비밀번호일 수 있어 남기지 않음)
- 시험: `tests/test_inject_screen.py`에 화면 넷(빈 칸 색 · 친 글 색 · 흐린 안내 · 회색 안내) + 거절(일함 · 쉼) · 안내 글은 넣음 · Esc 뒤 친 글 거절

### 3. 이름 정리
- 새 탭 「CC 화면」
- 화면 아래 「터미널」 → 「셸」: 여닫는 단추 「▲ 셸 / ▼ 셸」, 메뉴 「<프로젝트> 셸」, 툴팁 · 안내 · 에러 글(`terminal.js` · `store.js` · `api/terminal.py` · `terminal.py`), iframe aria-label 「FOREMAN 셸」, ttyd `titleFixed=FOREMAN 셸`, 활동 줄 「셸 부탁」 · 「셸 결과」, 글씨 크기 툴팁 「… · 셸 · CC 화면 글씨」, 답 기다림 안내 「패널 입력 칸이나 CC 화면에서 답합니다」(전 「터미널에서」 — CC 콘솔을 뜻했고 이제 CC 화면이 그 길)
  - 그대로 둔 것: 승인 「터미널에서 답했습니다」(`render.js` — 화면 아래 셸이 아니라 CC 콘솔에서 답한 승인), `usage.html` 「아무 CC 터미널에서 /login」, CC에 보내는 결과 글 머리 「[터미널 패널] …」(모델에게 가는 글이라 그대로 — 바꿀지는 관리자 판단)
- 패널 「세션」 탭 → 「세션 정리」: 관리자가 찾은 「세션」 탭 꼴(`opanel.js` · `render.js` · `office.js` · `mergeprep.py` · `api/dashboard.py` · `overhead_marks.json` · `docs/10_office_design.md` · `docs/11_worktree.md`)에 더해 같은 뜻의 **[세션] 탭** 꼴도 바꿨다 — `losscheck.py` · `promote.py`(알림 글) · `handoff.js` · `foremanchat.js` · `scribe.js` · `coder.js`(툴팁 「세션 열기 — 이 세션의 [세션 정리] 탭을 엽니다」) · `render.js` · `opanel.js` · `panel.css`(주석) · `docs/13_demo_capture.md`
- **`docs/operations.md`는 건드리지 않았다(서기 몫)** — 바꿀 줄:
  - 100줄 「(카드는 패널 「세션」 탭 · `GET /api/merge-prep`에 …」 → 「세션 정리」 탭
  - 58 · 63 · 64 · 67줄의 「터미널」(화면 아래 셸을 뜻함) → 「셸」. 67줄 셸 파일 목록에 `deploy/shell/foreman-cc-view` · `bridge/static/js/ccscreen.js`와 「CC 화면」(`/ccscreen`, `.run/ttyd-cc.sock`, `.run/ttyd-cc.log`)을 더할 것
  - 「3. 돌리기 · 확인」에 CC 화면 ttyd(브리지가 함께 띄움 · 로그 `.run/ttyd-cc.log`)를 더할 것

### 4. [새 셸] → [셸 비우기]
- `TerminalManager.clear(project, force)` · `POST /api/terminal/clear`. 셸을 새로 띄우지 않는다(같은 pane_pid). 입력을 기다리는 셸은 readline 화면 지우기 `C-l`(기록 · `/hooks/shell`에 `clear`가 남지 않게 명령으로 치지 않음) → 0.2초 → tmux `clear-history`. 친 글이 있으면 먼저 묻고(`busy.typed`) `C-e C-u`로 지운 뒤 같게. 명령이 돌고 있으면 먼저 묻고(`busy.cmd`), 그 명령의 입력으로는 아무것도 보내지 않고 `send-keys -R`(tmux 쪽 화면 초기화) + `clear-history` — 명령은 그대로 돈다. 스크롤(복사 모드) 중이면 먼저 나온다
- 확인 창 글: 「<프로젝트> 셸을 비웁니다. 입력 줄에 친 글(…)이 지워집니다 / 돌고 있는 명령(…)의 지난 출력이 지워집니다. 명령은 그대로 돕니다. 계속할까요?」
- 옛 셸 알림 글: 「셸 설정이 바뀌었습니다 — 이 창은 옛 설정입니다. 셸에서 exit를 친 뒤 셸을 다시 열면 새 설정을 읽습니다」(exit로 그 창이 닫히면 다음에 고를 때 `window_for`가 새 창 · 새 셸을 만든다)
- **새 셸을 여는 길 제안(만들지 않음)**: 옛 셸 알림 줄(`termProjWarn`, 셸 설정이 바뀌었을 때만 뜸) 안에만 작은 [새 셸로] 단추를 둔다 — 늘 보이는 막대에는 두지 않는다(「눌러도 쌓인다」 느낌을 다시 만들지 않게, 필요한 때만 보이게). 서버 길 `POST /api/terminal/respawn`(respawn-pane -k, 친 글 · 돌고 있는 명령이면 먼저 묻기)과 그 시험은 그대로 남겨 두었다

## 설계와 달랐던 점
- **`attach -f ignore-size`만으로는 CC 창 크기가 바뀌었다**(시험이 잡았다 — 200×50 화면을 붙이니 100×30 창이 200×49가 됐다). tmux는 크기 무시(ignore-size) 손님을 「크기를 따르는 다른 손님이 서버 어딘가에 붙어 있을 때만」 무시한다. CC 세션에는 붙은 손님이 없어(11-14 `list-sessions` 모두 0) 브라우저 크기로 바뀐다. 라이브에서 셸 패널이 열려 있으면 우연히 지켜지고 닫혀 있으면 바뀌는 — 조용한 고장이 될 뻔했다
  - 그래서 **보는 동안만 그 창에 `window-size manual`을 걸고**(창 옵션, 표시 `@foreman_ccview 1`), 그 창을 가진 다른 `ccv-` 세션이 없을 때 나가면서 푼다(`hold` · `release`, HUP · TERM 덫). 창에 이미 다른 `window-size`가 있으면(표시 없음) 건드리지 않는다. 함께 끝나 서로 남기거나 kill -9로 못 푼 것은 브리지 `release_cc_windows`가 푼다(브리지 시작 · CC 화면 연결마다). 보는 동안 VNC 등으로 그 창에 보통 손님이 붙어도 크기가 따라가지 않는다 — 나가면 다시 따라간다
- 그룹 세션 이름은 `ccv-<탭>`이 아니라 **`ccv-<탭>-<pid>`**(연결마다) — 같은 탭이 곧바로 다시 붙을 때 앞 연결의 뒷정리(`kill-session` · `release`)가 새 연결 세션을 지우거나 묶음을 푸는 경합을 막았다. 같은 탭의 앞 연결은 머리 `ccv-<탭>-`로 찾아 치운다
- 기록 이름은 `cc-view-open` · `cc-view-close`가 아니라 **`ccview-open` · `ccview-close`** — `session_action.action`이 `VARCHAR(12)`(0014)라 `cc-view-close`(13자)가 들어가지 않는다. 스키마를 바꾸지 않았다
- 열고 닫음 기록은 화면이 보내는 게 아니라 **WS 프록시가 연결 시작 · 끝에** 남긴다(창을 닫거나 브라우저가 죽어도 「닫음」이 남게). ttyd 화면이 스스로 다시 붙으면 한 번 더 남는다
- 없는 tmux 창을 `display-message -t %없는번호`로 물으면 tmux가 오류 없이 빈 값을 돌려준다(rc 0) — 빈 세션 이름이면 「찾지 못했습니다」로 본다(`cc_target` · 스크립트 둘 다)

## 확인
- 단위 시험: `tests/test_ccscreen.py`(새, 11개) — 보기 스크립트가 200×50 pty로 붙어도 창 100×30 그대로 · 보는 동안 manual · 나가면 풂 · 그룹 세션만 사라짐, 대조(그냥 붙으면 120×39로 바뀜), 두 화면 중 하나가 나가도 묶음 유지, 브리지가 남은 묶음만 풂(남이 정한 `smallest`는 그대로), 잘못된 대상 넷 거절, `cc_target` 열 갈래, WS 인자 모양, [셸 비우기](친 글 · 돌고 있는 명령 묻기, 비운 뒤 history 0 · 같은 셸 · 명령 계속). 모두 시험 전용 tmux 서버(own_sock)에서 — 라이브 세션에 키를 보내지 않았다
- `tests/test_inject_screen.py` 새 시험 포함 통과
- 전체 pytest: 927 통과 · 1 건너뜀(`test_proxy_cookie_origin_ws` — worktree에 `.tools/ttyd`가 없어 건너뜀. `.tools`는 git 무시 목록에 없어 링크를 만들지 않았다 → **합친 뒤 원본 폴더에서 `pytest tests/test_terminal.py -k proxy`로 쿠키 두 경로 · 프록시 고친 것을 확인해 주세요**). 고친 뒤 관련 시험(터미널 · CC 화면 · 주입 · 한국어 검사) 103 통과
- 시험 고정물 `shell`이 CC 화면 소켓(`ccscreen_socket`)도 시험 폴더로 돌린다 — 시험 앱이 worktree `.run/ttyd-cc.sock`을 쓰지 않게
- 브리지 시작 때 `ccv-` 치우기는 `min_age=0`이 아니라 30초 — `ccv-`는 tmux 서버 전체에 하나라(셸 탭 세션은 시험마다 이름이 다르다), 시험이 띄운 매니저가 막 붙는 중인 라이브 CC 화면을 지우지 않게
- node 시험: 172 통과
- **실제 ttyd 끝까지(보기만)**: 원본 `.tools/ttyd` + 새 `foreman-cc-view`를 scratch 소켓에 띄우고, 이 세션 창(`cc-foreman-2` %1348)에 WS로 붙어 첫 인사(200×50)만 보냈다(키 없음). 화면 40KB가 왔고(입력 칸 ❯ · 「auto mode」 줄 보임), 붙은 동안 창 `80x24` 그대로 · window-size `manual`, 끊은 뒤 `80x24` · window-size 풀림 · `ccv-` 세션 없음
- 화면 점검: 미리보기(`POST /api/sessions/368/preview`, 포트 8200, tmux `fm-pv-foreman-2` — 남겨 둠)에 `tools/screen.py --no-term --session 368` — 세 테마 × 세 크기 × 좁게/넓게 **문제 0건**(rc 0, 「audit(고정 안 됨)」 1 · 11 · 14는 문제 수에 들지 않는 값). `--no-term`은 셸을 여는 점검이 라이브 셸 창을 바꾸기 때문(`tools/screen.py` 머리 글). 1024 좁은 패널에 탭 넷(대화 · 활동 40 · CC 화면 · 세션 정리)과 「▲ 셸」이 들어간다(사진 확인)
- 미리보기에서 「CC 화면」 탭을 누르면(도는 브리지는 원본 코드라 `/api/terminal/cc` 없음) 빈 화면이 아니라 까닭이 뜨고 iframe은 붙지 않는다. 처음엔 FastAPI 「Not Found」가 그대로 떠서 404면 「도는 브리지에 CC 화면 길이 없습니다 — 브리지를 새 코드로 다시 띄워야 합니다」로 바꿨다(세션이 없을 때는 200 + 까닭이라 404는 옛 브리지뿐)

## 합친 뒤 관리자 확인 순서(미리보기는 브리지 코드를 못 쓴다 — 서버 쪽은 합친 뒤에만 본다)
1. 승인 대기 0을 본 뒤 `systemctl --user restart foreman-bridge`
2. `.run/ttyd-cc.sock`이 생겼는지, 브리지 로그에 「ttyd(cc) 시작」, `.run/ttyd-cc.log`에 오류 없는지
3. 쉬는 세션 하나를 골라 패널 「CC 화면」 탭 → CC 창이 보이는지. 그 창의 `tmux display -p -t <창> '#{window_width}x#{window_height}'`를 열기 전 · 연 동안 · 닫은 뒤 세 번 — 같아야 한다. 연 동안 `tmux show-options -wqv -t <창> window-size`가 `manual`, 닫은 뒤 빈 값. `tmux ls | grep ccv-`가 닫은 뒤 없어야 한다
4. `SELECT action, detail FROM session_action WHERE action LIKE 'ccview%' ORDER BY id DESC LIMIT 4` — 열고 닫은 두 줄
5. 다른 탭(「대화」)으로 가거나 패널을 접으면 끊기는지(3과 같은 방법), 다른 세션을 고르면 그 세션으로 바뀌는지
6. 끝난 세션 · 멈춰 둔 세션을 고르면 탭에 까닭이 뜨는지(멈춰 둔 세션은 열지 않는다)
7. CC 화면 ttyd 프로세스만 PID로 끝내 보면 탭에 5초 안에 「CC 화면 서버(ttyd)가 떠 있지 않습니다…」가 뜨고, 곧 브리지가 다시 띄우면 [다시 붙기]로 돌아오는지
8. 「▲ 셸」 · 「FOREMAN 셸」 이름, [셸 비우기](친 글이 있으면 먼저 묻기)
9. 넣기 거절: 세션 CC 화면 입력 칸에 글을 반쯤 친 채 패널에서 그 세션에 보내면 「입력 칸에 사람이 치던 글이 있어 넣지 않았습니다 …」로 거절되는지(시험 세션에서)
10. 셸을 연 채 화면 점검은 시험 ttyd 서버로(`tools/screen.py` 머리 글 — :8000에 대고 돌리면 라이브 셸 창이 바뀐다)

## 규칙 위반
- **도구 호출 사이 진행 글이 영어로 세 번 나갔다**(CLAUDE.md 「항상 한국어로 답한다 — 진행 글까지」). 언제: `terminal.py` 고치기 중 「Now sweep_views with prefix, and supervise refactor.」, 「세션」 탭 바꾸기 중 「Now replace all occurrences in each file.」 · 「Now opanel.js · office.js 남은 곳(이미 읽은 파일).」. 왜: 같은 꼴의 Edit를 이어 부르며 진행 글을 확인하지 않고 썼다. 바로잡음: 훅 알림을 받을 때마다 그 자리에서 알리고 다음 글부터 한국어로 썼다. 글 내용 외 결과물(파일 · 화면 글 · 커밋)에는 영향이 없다
- 그 밖(파일은 Edit · Write로만 고침, 새 스크립트 권한은 chmod, `pgrep -f` 안 씀, push · 브리지 다시 띄우기 안 함, `docs/operations.md` · `docs/style_guide.md` 안 건드림, 라이브 세션 tmux에 키 안 보냄)은 지켰다
