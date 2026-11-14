# 계획 승인 뒤 모드 지키기 · 쉬는 세션에 뜬 창 알리기 (2026-11-14, worktree foreman-3, 관리자 362 일감)

> 앞 조사: `log/silent_finish_20261114.md`(359) 1 · 4절. CC 2.1.325에서 시험

## 0단계 — 모드를 지킬 길이 있나: 있다

시험 세션: 따로 띄운 tmux 서버 `tmux -L t362`, 스크래치 폴더 `…/scratchpad/mt`, `claude --model sonnet --setting-sources project,local --permission-mode plan`(사용자 훅 뺌). 그 폴더 `.claude/settings.json`에 시험 훅 하나 — ExitPlanMode면 `VARIANT` 파일의 JSON을 돌려주고, 다른 도구는 입력을 남기고 plain allow.

| # | 계획 전 모드 | 훅이 돌려준 것 | 결과 |
|---|---|---|---|
| 1 | default(plan으로 띄움) | `allow` + `updatedInput {}` + `updatedPermissions [{setMode, auto, session}]` | 계획 바로 진행, **auto mode on**. 그 뒤 Write · Bash 둘은 훅에 묻지 않음(out.log에 ExitPlanMode 하나뿐) |
| 2 | acceptEdits(시프트+탭으로 plan) | `allow` + `updatedInput {}` | 진행, **accept edits on** — 계획 전 모드로 돌아감 |
| 3 | manual(`/plan`으로 plan) | `allow` + `updatedInput {}` | 진행, **manual mode on**. 그 뒤 Write 1 · Bash 2가 **하나하나 PermissionRequest로 물음**(훅 기록 15:15:19 · 21 · 24) |
| 4 | manual | 결정 없음(`{}`) | 터미널 창: `❯ 1. Yes, and use auto mode / 2. Yes, manually approve edits / 3. Tell Claude what to change` — 계획 전이 manual이어도 기본 선택은 auto |

- **(a) manual이 된 뒤 정말 매번 묻는가 — 묻는다**(3번). 실제 환경에서는 그 물음이 모두 PermissionRequest로 브리지에 와 승인 카드 · 텔레그램이 된다. 관찰(observe) 프로젝트(runshoes · petmint · infra)는 PreToolUse가 아무것도 돌려주지 않으니 CC가 묻는 것 전부, foreman(enforce)은 정책 `allow`가 아닌 것(`pass`)이 카드가 된다
- 359에서 manual이 된 까닭: 시험 세션을 `--permission-mode plan`으로 띄워 「계획 전 모드」가 default였다. **브리지가 읽기 전용 세션을 바로 그렇게 띄운다**(`bridge/handoff.py` 844) — 그래서 setMode 없이는 실제로 manual로 떨어진다
- **(b) `updatedPermissions` `setMode`로 모드가 유지되는가 — 된다**(1번)
- **(c) 터미널 「1. Yes, and use auto mode」와 같은 결과** = `updatedInput`(원래 입력) + `setMode auto`(destination `session`). 계획 전 모드를 따로 기억하지 않고 늘 auto로 했다 — 터미널 기본 선택도 계획 전 모드와 상관없이 auto라서(4번)
- 훅 입력에는 `permission_suggestions`도 계획 전 모드도 없었다(`permission_mode: "plan"`만)

## 1단계 — 고친 것

### `bridge/approvals.py`
- `allow_decision(tool, inp)`: 패널 허용의 결정 모양. `NEEDS_INPUT = {"ExitPlanMode"}`면 `updatedInput` = 원래 입력, ExitPlanMode는 `updatedPermissions = [{"type": "setMode", "mode": PLAN_EXIT_MODE("auto"), "destination": "session"}]`. 그 밖 도구는 예전대로 `{"behavior": "allow"}`
- AskUserQuestion 답 갈래(answers)는 그대로 — 그 앞에서 돌려준다. 답 없이 「허용」만 온 AskUserQuestion은 예전처럼 plain allow로 뒀다(답 없는 updatedInput이 CC에서 어떻게 되는지 시험 안 함)
- 시험: `tests/test_stage2_db.py` `test_permission_browser_allow_exit_plan_mode`

### `bridge/stallwatch.py` — 「쉬는 세션 다시 보기」 중 창(A)
- 판정을 따로: `dialog_key(s)` · `judge_dialog(s, now, since)`. `judge()`는 예전 `EXIT_RE` 두 줄 자리에서 `judge_dialog`를 부를 뿐이다
- `Sample`에 칸 덧붙임(끝에): `cc_status` · `pending` · `last_appr`. `samples()`에 쿼리 둘(세션별 pending 승인 수 · 마지막 승인의 status · decided_at)
- 판정(살아 있고 busy 아님):

  | 화면(`inject.screen_state`) | 조건 | kind | 알림 |
  |---|---|---|---|
  | `prompt` | — | 없음 | — |
  | 끝내기 확인(또는 `EXIT_RE`) | — | `exit_confirm`(예전과 같음) | 2분 뒤 한 번 |
  | `dismiss`(/model · /config · 자동 압축 권유 …) | — | `notice` 「안내 창이 떠 있음」 | 안 함(화면만) |
  | `decision` | pending 없음 | `dialog` 「창에서 답을 기다림」 | 2분 뒤 한 번. 마지막 승인이 30분 안의 `timeout`이면 화면만(브리지가 이미 「대화창에서만」을 보냈다) |
  | `unknown` | pending 없음 + status `waiting` | `dialog`(「알 수 없는 창」) | 2분 뒤 한 번 |
  | 화면 못 읽음(tmux 밖) | status `waiting` + pending 없음 | `dialog` | 2분 뒤 한 번 |

- 「처음 본 때」는 `dialog_seen[세션] = (열쇠, 시각)` — 창이 바뀌면(열쇠가 다르면) 다시 잰다. 모르는 창은 열쇠에 status를 넣어, 늘 「모름」으로 보이던 화면이 waiting으로 바뀌면 그때부터 2분
- 화면 찍기를 `capture-pane -p -J`로(inject `_capture`와 같게 — 359가 짚은 위험)
- 359 위험 대응: ① 일부러 연 창 — `dismiss`는 알리지 않음 ② 판정 오인 — `unknown`은 CC도 `waiting`일 때만 ③ 1분마다 tmux 호출은 예전과 같은 수(busy 아닌 세션만)
- 시험: `tests/test_stallwatch.py` — 순수 판정 3개(실측 화면은 `test_inject_screen`의 것 + 오늘 찍은 계획 승인 창), DB 흐름에 359 꼴(카드가 기다리는 동안 조용 → 패널 허용 뒤에도 창이 남으면 처음 본 때부터 2분 뒤 한 번 → 창이 닫히면 사라짐)

### 다른 코더(B, `bg_long`)와 겹침
- 판정 함수 · 시험을 따로 뒀다. 공용 부분에서 바꾼 곳: `Sample` 끝에 칸 셋, `samples()` 쿼리 둘 · Sample 만드는 줄, `check()`의 「처음 본 때」(`exit_seen` → `dialog_seen`, 이름이 바뀜), `ALERT_AFTER` · `LABEL`에 줄 더함, `_send` 문구 표에 한 줄. B가 `exit_seen`을 쓰면 겹친다

### main 위로 rebase(관리자 362 요청)
- 그 사이 main에 `bg_long`(코더 B)과 367 「출력 없는 백그라운드 헛경보 없애기」(`cbde3bd`)가 들어와 `bridge/stallwatch.py`가 다섯 곳에서 충돌했다. 모두 양쪽이 덧붙인 것이라 둘 다 살렸다: `ALERT_AFTER`에 `bg_long` · `dialog` 둘, `Sample`에 `bg` 다음 내 칸 셋, `bg_output_stat` · `judge_bg` · `fmt_elapsed` 다음 `dialog_key` · `judge_dialog`, `samples()`에 bg 쿼리 다음 승인 쿼리 둘, `_send` 문구 표에 두 줄
- 고친 것 하나: 367의 bg 반복이 `st = bg_output_stat(…)`로 이름 `st`를 다시 써서, 내 쪽 CC status 변수(`st`)가 덮였을 것이다. 내 쪽을 `cc_st`로 바꿨다

## 화면 쪽(이번에 안 고침 — 응답 모양)
- `/api/dashboard` 세션의 `stall` 칸에 새 kind가 실린다: `{"kind": "dialog"|"notice", "label", "since", "detail", "notify": bool}`(exit_confirm에도 `notify: true`가 붙음. 예전 kind에는 없음 = 알림)
- `bridge/static/js/render.js` `stallChip`은 `long`이 아니면 툴팁에 「텔레그램으로도 알립니다.」를 붙인다 → `notice`(그리고 timeout 뒤 조용한 `dialog`)에서 틀린 말이 된다. `f.notify === false`면 빼고 `muted`로 보이게 고칠 것(화면 담당)
- 대시보드 `char_state`가 status `waiting`을 IDLE로 보이는 것(359 4절)은 그대로

## docs
- README 승인 절에 「계획 승인(ExitPlanMode)도 updatedInput을 붙여 돌려준다(11-14)」 문단을 더함(질문 문단 뒤). 멈춤 종류 설명은 `bridge/stallwatch.py` 머리글(따로 docs 절이 없음)
- README 「나중에 할 일」 「CC 자체 안내 창이 세션을 붙잡는 것 알리기」 줄의 「남은 것: 일하지 않는 세션의 tmux 화면에서 고르기 창을 찾아 패널 표시 · 오래가면 알림」이 이번 것으로 됐다 — 로드맵 표는 원본 세션이 고친다(이 브랜치에서 안 건드림). 「끝내기 확인 창」 줄의 exit_confirm 설명도 그대로 맞음
- `docs/operations.md` · `docs/style_guide.md`는 안 건드림. 고칠 곳 없음

## 확인 못 한 것
- auto mode를 못 쓰는 계정 · 모델에서 `setMode auto`가 오면 CC가 어떻게 하는지(결정 전체를 버리는지)
- `bypassPermissions`로 돌던 세션의 계획 승인 — 터미널 1번이 무엇인지 안 봄. 지금 코드는 auto로 바꾼다(FOREMAN이 띄우는 세션은 bypass를 쓰지 않는다)
- 질문 창(AskUserQuestion)의 화면은 `screen_state` 표에 없어 `unknown` — status `waiting`일 때만 dialog로 잡힌다(시험 세션에서 질문 창 status는 안 봄)
- 실제 브리지에서의 끝까지 시험(합친 뒤 브리지를 다시 띄워야 함 — 관리자 몫): 읽기 전용 세션 계획을 패널에서 허용 → 진행 · auto 유지 확인

## 쓴 시험 세션
- CC 세션 id `3ce49324-66e8-46a6-a53f-0950abbdd8fb`, **브리지에 세션 366으로 잡혔다 — 관리자가 `hidden_reason='test'`로 숨겨 주세요**
- 한 일: 폴더 신뢰 Yes, 계획 → ExitPlanMode 네 번(위 표), 마지막 창은 Esc로 거부, `/exit`, `tmux -L t362 kill-server`(닫힘 확인). 다른 세션 tmux에는 키를 보내지 않았다. 스크래치 폴더에 a~f.txt · g/(시험 세션이 만든 것)가 남아 있다

## 규칙
- 규칙 위반 없음. 저장소 파일은 Edit · Write로만 고쳤다. Bash의 `printf >`는 스크래치 폴더의 시험 설정(`settings.json` · `VARIANT`)에만 썼다. pytest는 처음부터 뒤에서 + `timeout`. `pgrep -f` 안 씀. push · 브리지 다시 띄우기 안 함
