# 「끝났는데 아무도 모른다」 네 가지 — 원인 조사 (2026-11-14, worktree foreman-4, 관리자 318 일감)

> 상태: 조사만. 코드 · 설정 · docs는 안 고쳤다. CC 2.1.325(시험), 11-13 당시 세션은 2.1.32x. 시각은 UTC로 적고 괄호에 KST

## 한 줄씩

| # | 원인 | 뿌리 |
|---|---|---|
| 1 | **CC가 ExitPlanMode에서는 PermissionRequest 훅의 `allow`(updatedInput 없음)를 무시한다.** 브리지는 패널 승인을 끝난 것으로 적고 카드를 닫지만, CC 계획 승인 창은 터미널에 그대로 떠 있다. 335는 사용자가 입력 칸으로 보낸 글의 Enter가 그 창의 기본 선택(1. Yes)을 눌러서 움직였다 | A |
| 2 | **pytest가 끝나지 않았다.** 330의 첫 pytest(120초 넘어 CC가 자동으로 백그라운드로 옮긴 것)가 약 45%에서 2시간 10분 멈췄다. 끝나지 않았으니 CC 완료 알림도 없었다 — CC는 맞게 동작했다. 아무도 「백그라운드 일이 너무 오래 돈다」를 보지 않았다 | B |
| 3 | **2와 같은 사건이다.** 「뒤에서 도는 일 1」은 프로세스가 실제로 살아 있어 남은 것이고, 330이 kill한 뒤 알림이 오자 `bg_end`가 들어가 지워졌다. 표시는 틀리지 않았다 — 「오래 돈다 · 멈췄을 수 있다」를 못 보여 준 것이 문제 | B |
| 4 | **stallwatch는 쉬는 세션 화면에서 「끝내기 확인 창」 글만 찾는다.** 다른 창(계획 승인 · 시간 지난 권한 · 질문 창 등)은 못 본다. CC는 그때 status `waiting`을 쓰지만 대시보드는 `waiting`을 IDLE로 보인다 | A |

**같은 뿌리인가 — 둘로 갈린다.**
- **A(1 · 4): CC는 「사람을 기다린다」(status `waiting` · 화면에 창)인데 브리지 쪽에는 기다리는 것이 없다.** 브리지는 자기가 받은 신호(훅 · 트랜스크립트)로만 상태를 정하고, CC가 직접 적는 `waiting`과 맞대어 보지 않는다. 1은 4의 한 경우다(브리지가 「승인함」으로 닫은 뒤 창이 남음)
- **B(2 · 3): 브리지는 「돈다」를 맞게 알지만 「얼마나 오래 · 정상인가」를 보지 않는다.** 감시(stallwatch `silent` · `long`)는 열린 턴 · busy에만 걸려, 턴을 끝내고 쉬며 백그라운드만 기다리는 세션은 아무것도 재지 않는다
- 사용자의 짐작 「끝났는데 아무도 모른다」는 A에 맞다. B는 반대로 「안 끝났는데(멈췄는데) 아무도 모른다」다. 공통은 **쉬는(IDLE) 세션을 아무도 다시 보지 않는다** — 고칠 자리도 같은 감시 루프(stallwatch)다

## 1. 플랜 승인 뒤 안 이어짐

### 증거
- 335 트랜스크립트(`646ec258…jsonl`): `ExitPlanMode` 호출 06:50:49.670(15:50:49) → 도구 결과 「User has approved your plan」 **06:54:16.068**(15:54:16) → 바로 다음 턴
- DB `approval` #103: ExitPlanMode, `allowed` · `browser`, decided_at **06:51:06.221**. 브리지 로그 15:51:06 「브라우저 결정 #103: allow」, `POST /hooks/permission 200` — 훅은 그 순간 allow를 돌려줬다
- 그 3분 동안 CC는 움직이지 않았다. 15:54:16에 `POST /api/sessions/335/input`(8자, 15:54:26 504 「주입 제출 확인 안 됨 — 입력 칸에 없다」)이 들어갔다 = 사용자의 입력 칸 글. **이 글은 대화에 남지 않았다** — 글이 창에 들어가고 Enter가 창의 기본 선택 「1. Yes, and use auto mode」를 확정했다(결과 뒤 `auto_mode` 첨부가 그 증거)
- 과거 ExitPlanMode 승인 다섯 건이 모두 같은 꼴:

  | 승인 | 결정 | 결정 시각 | CC 도구 결과 |
  |---|---|---|---|
  | #72 (228) | 패널 거부 | 11-09 07:44:35.966 | 07:44:35.972 — 바로 |
  | #73 (228) | 패널 허용 | 11-09 07:45:29.970 | 07:47:30 — 2분 뒤 |
  | #86 (252) | 터미널 | 11-10 02:12:33.699 | 02:12:33 — 바로 |
  | #93 (253) | 패널 허용 | 11-10 03:34:56.853 | 03:36:59 — 2분 뒤 |
  | #103 (335) | 패널 허용 | 11-13 06:51:06.221 | 06:54:16 — 3분 뒤 |

  패널 거부 · 터미널은 바로, **패널 허용만 늦다**(다른 입력이 창을 누를 때까지)
- **시험 세션으로 재현**(아래 「쓴 시험 세션」): 3초 뒤 allow를 돌려주는 훅만 둔 CC를 플랜 모드로.
  - `{"decision":{"behavior":"allow"}}` → 훅은 14:38:33에 끝났는데 **60초 뒤에도 「Would you like to proceed?」 창 그대로**, CC status `waiting`. 같은 시험 한 번 더(14:40:38) → 30초 뒤에도 그대로
  - `{"decision":{"behavior":"allow","updatedInput":{}}}` → **바로 「User approved Claude's plan · Allowed by PermissionRequest hook」, 다음 턴 진행**. 다만 끝난 뒤 모드가 auto가 아니라 **manual**이었다(터미널에서 「1. Yes, and use auto mode」를 고르면 auto)
- 같은 이유로 AskUserQuestion은 지금 잘 된다 — 브리지가 `updatedInput`(answers)을 붙여 돌려준다(`bridge/approvals.py` 323~332). 그냥 allow 줄(334)만 updatedInput이 없다

### 원인
CC는 사람 상호작용이 필요한 도구(ExitPlanMode 등)에서 updatedInput 없는 훅 allow를 결정으로 받지 않고 자기 창을 그대로 둔다(CC 코드는 번들이라 해당 분기를 글로는 못 찾았다 — 시험으로 확인). 브리지는 이것을 모르고 카드를 「허용됨」으로 닫는다 → 패널에는 기다리는 것이 없고, 대시보드는 status `waiting`을 IDLE로 보인다 → 「끝났다」로 보임.
패널에서 했는지 대화창(터미널)에서 했는지에 따라 다르다: **터미널은 바로, 패널 허용만 멈춘다.** 패널 거부는 된다.

### 덧: 지금은 입력 칸으로도 못 푼다
351의 `screen_state`(11-13 저녁 합침)는 계획 승인 창을 「결정 창」으로 보고 입력을 거부한다. 335 때처럼 입력 칸 글이 우연히 창을 누르는 일은 이제 없고, 대화창(터미널)에서만 풀린다. 안전해진 대신, 1이 생기면 더 오래 묶인다.

### 고치는 길
- `bridge/approvals.py` `permission_request`의 allow 갈래: 도구가 ExitPlanMode면 `updatedInput`에 원래 입력(`inp`, 비어 있어도 `{}`)을 붙인다. 모드도 정하려면 `updatedPermissions`에 `setMode`(plan 전 모드 — 대개 auto)를 함께 — 이 모양은 아직 시험 안 함
- 더 넓게: requiresUserInteraction 도구 전체(ExitPlanMode · AskUserQuestion · 그 밖 CC 창을 띄우는 도구)는 allow에 늘 updatedInput을 붙인다
- 안전망(4와 같은 것): 결정을 돌려준 뒤 그 세션 status가 30초 넘게 `waiting`이면 「승인을 보냈는데 창이 그대로입니다 — 대화창에서 확인해 주세요」를 카드 · 알림으로
- 고칠 파일: `bridge/approvals.py`, 시험 `tests/test_approvals*.py`, docs 승인 절
- 위험: ① 모드가 manual로 바뀌어 그 뒤 편집마다 묻게 될 수 있다(setMode를 같이 시험해야 함) ② CC 판마다 이 동작이 바뀔 수 있다 — 시험 세션으로 재는 시험을 남겨 두면 좋다 ③ 계획 「고치라고 하기(3번)」는 패널에 없다 — 지금 패널 거부 메시지가 그 몫

## 2. 「뒤에서 도는 일」이 끝나도 안 깨어남

### 증거
- 330 트랜스크립트(`291ea753…jsonl`): 04:52:15 `pytest -q 2>&1 | tail -8; node --test …`(포그라운드, 기본 120초) → **04:54:16 「Command did not complete within its 120s timeout and was moved to the background (ID: bycw4v30o)」** = CC가 자동으로 백그라운드로 옮김
- 330은 「끝나면 알림이 옵니다」 → `sleep 100; cat …`(CC가 막음) → 빈 출력 파일 Read → `Monitor`(입력 오류로 실패) → 「pytest 전체가 끝나기를 기다리는 중입니다」로 **04:54:58 턴을 끝냄**
- 07:02:33(16:02) 사람 「pytest 끝났나 보고 이어서 해라」 → 330이 `ps`: pytest 셸 **etime 02:10:27, 살아 있음** → kill → 07:02:54 `<task-notification>` bycw4v30o(셸이 `; node --test`까지 끝나 status completed)
- 출력 파일 `tasks/bycw4v30o.output`: 점 줄이 약 45%(837개 중 330번째 근처)에서 끊김. 다음 `-v` 실행(bwu3vv3yp)은 141초에 836 통과로 끝났고 **07:05:27에 알림이 와서 330이 스스로 깨어났다** — CC의 백그라운드 완료 알림 자체는 정상이다
- DB: bg_start 04:54:16 → bg_end 07:02:54(128분). 11-12 이후 20분 넘는 백그라운드는 이것과 309의 28분 두 건뿐

### 원인
- 알림이 안 온 것은 **일이 끝나지 않아서**다. CC 완료 알림은 작업 프로세스가 끝날 때 `queue-operation enqueue <task-notification>`으로 들어오고, 세션이 쉬고 있으면 그것이 새 턴을 연다(07:05:27 실제)
- 왜 멈췄는지는 못 찾았다(관리자 기록: `test_human_wait.py` 근처, 시험 DB를 다른 세션과 같이 쓴 것으로 짐작). 자동으로 백그라운드로 옮겨진 명령은 **120초 시간 제한이 사라진다** — 그래서 끝없이 돌 수 있었다
- 330의 실수도 있다: 「알림이 옵니다」라고 하고 기댄 것은 맞지만, 기대 시간(2~3분)을 넘으면 다시 볼 장치(Monitor · 시간 제한)를 못 걸었다
- 브리지 쪽: stallwatch `silent`는 busy일 때만, `long`은 열린 턴일 때만 잰다. 330은 턴을 닫고 idle이었다 → 2시간 동안 아무 감시에도 안 걸림

### 고치는 길
- stallwatch에 kind 하나(예: `bg_long`): 살아 있고 쉬는 세션에 `bg_start`만 있고 `bg_end`가 없는 것이 N분(예: 30분) 넘으면 화면 + 알림 한 번. 출력 파일(`tasks/<id>.output`) 크기가 그 동안 안 늘었으면 「멈췄을 수 있음」으로 더 세게
- 세션 쪽 규칙(CLAUDE.md · 일감 지시문): pytest 같은 긴 시험은 처음부터 `run_in_background` + `timeout 600` 등으로 감싼다 — 120초 자동 옮김에 기대지 않는다
- 고칠 파일: `bridge/stallwatch.py`(Sample에 bg 목록 · 판정 · 문구), `bridge/api/dashboard.py`는 이미 bg 목록이 있어 그대로 씀, 시험 `tests/test_stallwatch.py`
- 위험: 일부러 오래 도는 백그라운드(Monitor · 감시 루프)는 정상 — Monitor는 빼거나 출력이 늘면 정상으로. 알림 키는 `stall:bg_long:<세션>:<task>`로 한 번만

## 3. 「뒤에서 도는 일」이 끝나도 머리 위 표시가 안 지워짐

### 증거 · 원인
- 「뒤에서 도는 일 N」은 서버 `bridge/api/dashboard.py` `background_running` — 살아 있는 세션의 `bg_start`에 같은 task의 `bg_end`가 없는 것(24시간 안, 지금 프로세스가 뜬 뒤 시작). 화면은 `office.js` 2653(이름표 아래 줄 — 11-13 331 기록대로 사용자가 본 것은 이 줄) · 2257(머리 위 막대)이 `s.background` 길이를 그린다
- 끝남은 `<task-notification>`(큐 enqueue · queued_command 첨부 · 사람 줄 셋 중 어디든, `assembler._bg_end`)과 TaskStop · KillShell 결과(`_bg_end_task`)로만 안다
- 330: bycw4v30o는 **실제로 2시간 10분 살아 있었다**(`ps` etime). 표시가 남은 것은 맞는 값이다. kill → 알림 → 07:02:54 bg_end → 대시보드 캐시 2초 → 지워짐. 07:05:27 bwu3vv3yp도 바로 지워졌다
- 지금 DB(3일 안)에 끝 없는 bg_start는 0건. 11-12 이후 bg_end가 20분 넘게 늦은 것은 위 두 건(실제로 오래 돈 것)뿐 — 「끝났는데 안 지워진」 다른 경우는 못 찾았다
- 즉 사용자에게는 「pytest는 2~3분이면 끝나는데 표시가 남아 있다 = 끝났는데 안 지워졌다」로 보였지만, 실제는 「멈춘 채 돌고 있었다」 → **2와 같은 뿌리 B**

### 고치는 길
- 2의 `bg_long`을 같은 자리에 보인다: 「뒤에서 도는 일 1 — 2시간째(출력 멈춤)」. 호버에 시작 시각 · 경과 · 출력 파일 마지막 변경
- 고칠 파일: `bridge/api/dashboard.py`(경과 · 출력 크기 더하기), `bridge/static/js/office.js` 이름표 줄 · 호버 — **office.js는 지금 디자이너 356이 고치는 중**이라 그 뒤에
- 끝 알림 없이 사라진 경우(CC 프로세스가 죽음 · `/exit` 2번 「뒤로 보내고 끝내기」)는 이미 「지금 프로세스가 뜬 뒤」 거르기로 안 보인다 — 다만 그 일이 실제로 계속 도는지는 아무도 모른다(이번 범위 밖, 확인 못 함)

## 4. 쉬는 세션에 뜬 창을 패널에 보이고 알리기

### 지금 보는 것 · 못 보는 것
- `bridge/stallwatch.py`: 1분마다 살아 있는 세션 중 **busy가 아닌** 세션의 tmux 화면(`capture-pane -p`)을 찍는다(`samples`). 판정은 `EXIT_RE`(「Background work is running」 등) 하나 → `exit_confirm`. 화면을 이미 찍고 있으니 더 볼 자리는 있다
- 못 보는 것: 계획 승인 창(1의 경우 — 브리지가 허용을 보냈는데 남은 창), 승인 대기 시간(`wait_s`)이 지나 화면 카드가 닫힌 뒤 남은 권한 창 · 질문 창, 자동 압축 권유 · 효과 바꾸기 권유, `/model` 등 사람이 열어 둔 창, 폴더 신뢰 창(새 세션)
- CC 자신은 이때 sessions json status를 `waiting`으로 쓴다(시험 세션에서 계획 창 동안 `waiting` 확인, 351 기록: 권한 창도 `waiting`). 대시보드 `char_state`는 busy만 ACTIVE, 나머지는 IDLE → **`waiting`이 화면에서 「쉼」으로 보인다**

### `inject.screen_state`를 쓸 수 있나 — 쓸 수 있다
- 입력은 같은 `capture-pane` 화면 글이고, 돌려주는 값이 `("decision"|"dismiss"|"unknown", 창 이름)`이라 그대로 카드 문구가 된다. 표(`DECISION` · `DISMISS`)에 계획 승인(「Would you like to proceed?」)이 이미 있다
- 다만 inject는 `-J`(줄 이음)로 찍고 stallwatch는 `-p`만 쓴다 — 같게 맞춰야 한다. 테두리 · 가로줄 꼴은 120×40 실측이라 다른 크기 창에서는 시험이 더 필요
- 판정 제안: 살아 있고 · busy 아니고 · `screen_state`가 `prompt`가 아니고 · **그 세션에 브리지가 기다리는 승인(approval `pending`)이 없을 때** 2분 넘으면 kind `dialog`(「○○ 창에서 멈춤」) 화면 + 알림 한 번. 브리지가 기다리는 승인이 있으면 카드가 이미 보이므로 겹치지 않게 뺀다. `exit_confirm`은 이 판정의 한 경우로 합칠 수 있다
- 보조 신호: status `waiting`이 2분 넘게 이어지는데 pending 승인이 없으면 화면을 못 읽어도(tmux 밖 세션) 「CC가 사람을 기다립니다」
- 고칠 파일: `bridge/stallwatch.py`(판정 · 문구), `bridge/inject.py`는 `screen_state`를 그대로 가져다 씀(고칠 것 없음, 찍는 옵션만 맞춤), `bridge/api/dashboard.py`(stall 칸은 이미 있음), 화면 문구(`office.js` 등은 356 뒤), 시험 `tests/test_stallwatch.py`
- 위험: ① 사람이 일부러 열어 둔 `/config` 같은 닫아도 되는 창에도 알림 — `dismiss` 갈래는 화면만, 알림은 `decision` · `unknown`만 ② 화면 판정 오인(351이 보인 대로 지난 사용자 글의 `❯`) — `screen_state`가 이미 거른다 ③ 1분마다 세션 수만큼 tmux 호출 — 지금도 하고 있어 더 늘지 않음

## 한 번에 고친다면
stallwatch에 「쉬는 세션 다시 보기」 하나로 묶는다: 살아 있고 busy 아닌 세션마다 (a) 화면 `screen_state` · status `waiting` vs 브리지의 pending 승인 → A(1 · 4), (b) 끝 없는 bg의 경과 · 출력 증가 → B(2 · 3). 여기에 1의 원인 고치기(`approvals.py` updatedInput)를 따로 하나. 넷을 한 일감으로 하면 stallwatch · approvals · dashboard에 걸치고, 화면 쪽(office.js)은 356이 끝난 뒤 따로.

## 확인 못 한 것
- CC 코드에서 「updatedInput 없는 allow를 무시하는」 분기 자체(번들 바이트코드라 글로 못 찾음 — 시험 두 번 · 과거 세 건으로만 확인)
- `updatedPermissions` `setMode`로 모드를 auto로 돌리는 모양(시험 안 함)
- 330 첫 pytest가 왜 멈췄는지(어느 시험 · 시험 DB 겹침인지)
- 사용자가 본 3이 330 말고 다른 세션이었는지 — DB에 다른 후보는 없었다
- `/exit` 「뒤로 보내고 끝내기」로 남은 백그라운드가 실제로 계속 도는지

## 쓴 시험 세션
- 따로 띄운 tmux 서버 `tmux -L plantest`, 세션 `p`, 스크래치 폴더 `…/scratchpad/plantest`에서 `claude --model sonnet --setting-sources project,local --permission-mode plan` — **사용자 설정(브리지 훅)을 빼서** 패널 · 텔레그램에 승인 카드가 안 가게 했고, 그 폴더 `.claude/settings.json`에 시험용 PermissionRequest 훅만 뒀다
- CC 세션 id `52b8cc28-3edb-435d-aa11-89181937c877`(PID 3173407), **브리지에 세션 361로 잡혔다 — 관리자가 `hidden_reason='test'`로 숨겨 주세요**(숨기는 API를 찾지 않았다)
- 한 일: 폴더 신뢰 「Yes」, 계획 → ExitPlanMode 세 번(plain allow 둘 · updatedInput 하나), Esc로 창 거부, `/exit`(tmux 서버 닫힘 확인). 다른 세션 tmux에는 키를 보내지 않았다

## 규칙
- **위반 1건 — 진행 글을 영어로 썼다**: 시험 세션 재현 직후 「Reproduced: the hook returned allow … Waiting 60 more seconds to confirm it stays put.」(11-14 14:39 무렵). 까닭: 시험 결과(영어 화면)를 보고 바로 짧게 쓰다 한국어 확인을 건너뛰었다. 브리지 훅이 알려 준 뒤 바로 한국어로 바꿨고, 그 뒤로는 한국어
- 그 밖: 저장소 파일은 이 기록 하나를 Write로만 썼다. heredoc · `cat >`는 스크래치 폴더의 조회 · 시험 스크립트(DB 읽기 `q.py`, 트랜스크립트 요약, 시험 훅)에만 썼다. CC 바이너리 `grep`이 120초를 넘어 자동으로 백그라운드로 옮겨진 것은 TaskStop으로 멈췄다. 코드 · 설정 · docs · CLAUDE.md는 안 고쳤다. 비밀값은 보지 않았다(토큰 줄은 335 트랜스크립트의 명령 앞머리만 지나감, 값 없음)
