# 서기: 오늘 합친 코드에 문서 맞추기 (2026-11-14, worktree foreman-2, 관리자 362 일감)

문서만 고쳤다(코드 · 시험 · 설정은 건드리지 않음). 근거는 현재 main 코드(`bridge/usage.py` · `bridge/stallwatch.py` · `bridge/terminal.py` · `bridge/static/js/ccscreen.js`)와 오늘 log다.

## 고친 곳

| 파일 | 고친 것 | 근거 |
|---|---|---|
| `docs/operations.md` 알림 표 | 줄 셋 더함: 사용 한도 줄이 6시간 넘게 없음 · 오래 도는 백그라운드 `bg_long` · 쉬는 세션 창 `dialog`(`exit_confirm`도 같은 판정이고 안내 창 `notice`는 알리지 않음을 적음) | `6066d90`(`usage.py` `ABSENT_ALERT_H`) · `c0f4c4f` · `cbde3bd`(`judge_bg`) · `0d9de26`(`judge_dialog`), log 358 · 365 · 367 · 364 |
| `docs/operations.md` 「2.」 구조 표 | `terminal.py`를 「셸 · CC 화면」으로 | `375ca61` |
| `docs/operations.md` 「3.」 | 「웹 터미널용 foreman-shell」 → 화면 아래 셸용. screen.py 항목 `termAudit` · 「라이브 셸 창(터미널)」 · 「터미널 글씨 13px」을 셸로. 셸 스크롤 항목 머리를 「셸」로 | `375ca61` |
| `docs/operations.md` 「3.」 새 항목 | [셸 비우기](옛 [새 셸]) 줄과 **CC 화면** 항목(띄우는 창, [CC 화면 ↗], `/ccscreen`, `.run/ttyd-cc.sock` · `.run/ttyd-cc.log`, 그룹 세션 `ccv-<탭>-<pid>`, 보는 동안 띄운 창 크기에 맞추고 닫으면 80×24 `CC_REST_SIZE`, 기록 `ccview-open` · `ccview-close`, 확인 순서) | `375ca61` · `8af171e`, log 368 · 369 |
| `docs/operations.md` 「5.」 | 「세션」 탭 → 「세션 정리」 탭 | `375ca61` |
| `docs/style_guide.md` 「4-1.」 | 화면 말 표 「대화창」 줄에 「CC 화면」 창을 더하고 「CC 화면」 줄을 새로 둠. 기능 이름 줄을 「▲ 셸」 · 「FOREMAN 셸」 · [셸 비우기] · 「CC 화면」으로 바꾸고 대화창과 CC 화면의 관계를 적음. 대화창 말 약속은 그대로 | `375ca61`, `bridge/static/js/office.js` 「패널 입력 칸이나 CC 화면에서 답합니다」, `bridge/stallwatch.py` 「대화창에서 답합니다」 |
| `docs/11_worktree.md` · `docs/12_scribe.md` | 옛 절 이름 「코더 상주 · 임시 일꾼 · 맡길 일」 → 「코더 · 맡길 일」(`docs/10_office_design.md` 90줄 무렵 절 이름과 같게) | 11-13 347 |
| `README.md` 「나중에 할 일」 | 「CC 자체 안내 창이…」 줄을 「된 것」 · 「남은 것」으로 줄임, 「세션이 끝나지 않고 CC 끝내기 확인 창에…」 줄 「된 것」에 한 문장 더함(아래) | `0d9de26`, `log/plan_approve_mode_20261114.md` |

## README 두 줄: 지우지 않았다

- **「CC 자체 안내 창이…」(936 무렵) — 반만 됨.** 「남은 것」은 「쉬는 세션의 tmux 화면에서 고르기 창을 찾아 패널 표시 · 오래가면 알림」이었다. `judge_dialog`로 가르면: 패널 표시는 됨(`dialog` · `notice` 둘 다 화면 `stall`에 뜸). 오래가면 알림은 결정 창 · 모르는 창만 됨(2분 뒤 한 번). 339 때의 자동 압축 권유 창은 `screen_state`가 `dismiss`로 가르고 `judge_dialog`가 `notice`(`notify=False`)로 두어 **알리지 않는다**(`bridge/stallwatch.py` 머리글에도 「알리지 않는다, 일부러 연 창일 수 있다」). 그래서 줄을 지우지 않고 「11-14 된 것」과 「남은 것: 안내 창을 오래 두면 알림, 알릴 기준을 정할 것」으로 줄였다. 오늘 생긴 [CC 화면 ↗]으로 사람이 그 창을 보고 닫을 수 있게 된 것도 「된 것」에 적었다
- **「세션이 끝나지 않고 CC 끝내기 확인 창에 걸린 것 알리기」(896 무렵) — 끝나지 않음.** 「된 것」(알림 2분 · 패널 표시)은 맞고 364가 그것을 `judge_dialog`에 합쳤을 뿐 조건은 같다. 줄의 「아직」(끝내기 전에 뒤에서 도는 일을 보여 주고 묻기)과 「더할 것」 ① ② (뒤에서 도는 일이 끝나면 세션도 끝내기, 옮길 때 넘기기)는 코드에 없다. 지우지 않고 「된 것」에 합쳐진 사실 한 문장만 더했다

## 애매해서 둔 것(사용자가 정할 것)

1. **알림 · 멈춤 안내 글의 「대화창」 대 「CC 화면」**: 이제 사람이 FOREMAN 안에서 CC 창을 볼 수 있으니 `bridge/stallwatch.py`의 「그 세션의 대화창에서 답합니다」 같은 글이 「CC 화면에서」로 바뀔지. 문서에는 현재 코드대로 「대화창은 곳 일반, CC 화면은 그 기능 이름」으로 적었고 말 약속은 건드리지 않았다. 바꾸면 코드 글과 `style_guide.md` 「4-1.」을 함께 고친다
2. **안내 창(`notice`)을 오래 두면 알릴지**와 기준(몇 분 · 합치기가 걸렸을 때만)
3. 368 log의 「바꿀 줄」 중 **「CC 화면」 탭**으로 적힌 것은 369에서 [CC 화면 ↗] 띄우는 창으로 바뀌어 그 뒤 것(코드)에 맞췄다

## 확인한 것 · 못 한 것

- 알림 표의 `bg_long` · `dialog` 조건 숫자(30분 · 15분 · 2분 · 30분 `TIMEOUT_QUIET`)와 열쇠는 `bridge/stallwatch.py`에서 읽었다. 열쇠 `stall:dialog:<세션>:<YYYYMMDDHHMM>`은 `check()`의 기본 열쇠 모양에서 가져왔다
- `ccview-open` · `ccview-close` · 80×24 · `.run/ttyd-cc.sock` · `/ccscreen`은 `bridge/terminal.py` 상수에서 확인. 화면 · tmux를 실제로 돌려 보지는 않았다(문서 일이라)
- `docs/15_usage.md` 6-3절은 358 코더가 이미 썼고 이번에 건드리지 않았다
- `docs/operations.md` 28 · 78줄과 360이 남긴 애매한 줄(`log/done_lines_cleanup_20261114.md`)은 일감 밖이라 두었다

## 규칙

**위반 1건.** 첫 커밋 제목에 가운뎃점(·)을 썼다(11-14, 「커밋 메시지」 규칙: em dash와 가운뎃점 금지). 까닭: 문서 본문 습관대로 쓰고 제목을 규칙과 맞대어 보지 않았다. push 전이라 바로 `--amend`로 고쳤다(제목 「…알림과 CC 화면과 셸 이름에…」, 본문 점 없음). 이 log 파일은 amend 뒤 같은 커밋에 들어가지 않고 아래 두 번째 커밋으로 남긴다.

그 밖에는 위반이 없다. 파일은 Edit · Write로만 고쳤고 `pgrep -f`는 쓰지 않았다. push · 브리지 다시 띄우기 안 함. 진행 글은 한국어였다
