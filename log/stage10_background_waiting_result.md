# 백그라운드가 도는데 캐릭터가 잔다 — 기다림 표시 결과 (2026-11-06)

계기: d단계 Sonnet 판정(백그라운드 Bash, 7분)이 도는 동안 이 세션 캐릭터가 IDLE이라 엎드려 자고 있었다. 사용자 지적 — "설계에 '부모가 IDLE이어도 자식은 돈다'고 적어 뒀는데 화면에 반영이 안 된다".

## 원인

- 상태는 CC가 적는 status(busy/idle)만 봤다. 서브에이전트가 돌면 이름 아래 "일꾼 n"은 떴지만 몸은 IDLE 변형(자기 · 먹기 · 눕기)이었다
- **백그라운드 Bash · Monitor는 아예 추적하지 않았다**
  - 조립기가 그 완료 알림을 "서브에이전트가 아니다"라며 버렸다(`assembler.py` `_notification`)
  - 설계 3.11의 "IDLE + 백그라운드 n개" 배지는 만든 적이 없었다
- 끝 알림이 오는 자리가 셋이다(이 세션 트랜스크립트 실측)
  - 턴 사이: 사람 줄(origin task-notification)
  - 턴 도중: `queue-operation` enqueue와 `attachment` queued_command로만 온다 — Monitor 완료가 그랬다

## 한 일

- **조립기**
  - 도구 결과에 `backgroundTaskId`(Bash) · `taskId`(Monitor)가 있으면 `bg_start` 이벤트. 설명은 그 도구 입력의 description
  - `<task-notification>`에 status가 있으면 `bg_end`(세 자리 모두). uuid = 세션 + 작업 id라 한 번만 남는다
  - Monitor 중간 이벤트(status 없음)는 끝이 아니다
- **대시보드**: 세션마다 `background` = 끝 없는 `bg_start`(24시간 안)
  - 살아 있는 세션만 본다
  - 지금 CC 프로세스가 뜬 시각(`sessions/<pid>.json` `startedAt`) 전에 시작한 것은 뺀다(프로세스와 같이 죽었다)
- **화면**(`theme.js` `viewState`): IDLE인데 서브에이전트 + 백그라운드가 있으면 **WAITING**
  - 테마 넷에 `states.WAITING = {anim: wait, go: desk}`. 테마에 없어도 자는 모습으로 떨어지지 않게 기본값을 둔다
  - 책상에 서서 머리 위 "…"이 차오른다(시트 · 도형 둘 다)
  - 이름 아래 "백그라운드 n · 설명". 일꾼 줄이 있으면 그 아래
  - 툴팁 "기다리는 중" + 백그라운드 목록
  - 현장 집계 · 머리말 프로젝트 버튼 · 전체 "작업" 수에 작업으로 센다
- 서버 상태 값은 늘리지 않았다(설계 3.11 그대로 IDLE). IDLE을 보는 다른 곳은 그대로다(입력 주입 · 인계 요청은 CC의 busy를 따로 본다)

## 확인

- 시험: Python 401(+1 — Bash · Monitor 시작, 보통 Bash 제외, Monitor 중간 이벤트 제외, 같은 끝 알림 세 번 → 한 번, 프로세스 재시작 전 작업 제외), JS 40(+1 — WAITING 판정 · 테마 넷 · 테마에 없을 때)
- 실제 브리지: 다시 띄운 뒤 `sleep 150`을 백그라운드로 돌리자 행 189에 `background: [{task, tool: Bash, description}]`가 나왔다

## 설계와 다른 점 · 판단 근거

- **사용자는 "ACTIVE로"를 말했지만 서버 상태는 IDLE로 두고 화면만 WAITING으로 그렸다**
  - 설계 3.11이 상태 값을 늘리지 않기로 했다
  - IDLE/ACTIVE를 보는 다른 판단(정렬 · 끝 신호 없는 턴 표시 등)을 흔들지 않는다
  - 대신 사용자가 본 문제(자는 모습 · 배지 없음 · 현장이 쉼으로 보임)는 모두 화면에서 고쳤다
- **같은 묶음에 같은 uuid가 둘이면 적재가 통째로 실패한다**
  - 여러 행 `INSERT … ON DUPLICATE KEY UPDATE id = id`가 MySQL 1869(Auto-increment … conflicts)로 거부됐다
  - 큐 · 첨부로 같은 알림이 한 덩어리에 오면 실제로 생기는 일이다. 시험에서 잡았다
  - `bg_end`는 묶음 안에서 한 번만 넣는다
  - 다른 이벤트도 같은 묶음에 같은 uuid가 오면 같은 실패가 난다. 지금까지는 uuid가 줄마다 달라 생기지 않았다

## 남은 것

- 고치기 전에 적재된 백그라운드(브리지 재시작 전 시작분)는 `bg_start`가 없어 세지 않는다. 앞으로 시작하는 것부터 보인다
- 서브에이전트 · 백그라운드가 끝나지 않고 프로세스도 살아 있는데 끝 알림이 빠지면, 24시간 동안 "기다림"으로 남는다
  - 같은 날 실제로 생겼다(아래)

## 이어서(11-06) — TaskStop으로 멈춘 작업이 끝나지 않은 채 남았다

- 사용자: "답이 다 왔는데 캐릭터는 계속 작업 중으로 보여"
- 확인
  - 직전 턴(5870)은 18:27:47에 `stop`(hook)으로 제대로 닫혔다
  - `sleep 150`(b6lgivx98) · 3차 판정(bke7bzeuo)은 끝 기록(completed)이 있었다
  - **bi55inwkw만 시작만 있고 끝이 없었다**
    - 세션 탭을 확인하려던 node 스크립트였다. 2분 제한에 걸려 백그라운드로 넘어갔고 TaskStop으로 멈췄다
    - TaskStop으로 멈춘 작업에는 `<task-notification>`이 오지 않는다. 대신 TaskStop 결과(`toolUseResult`)에 `task_id`가 남는다
  - 그래서 답을 마친 뒤에도 IDLE + 백그라운드 1 → 기다림(현장 집계는 작업)으로 보였다
- 고침
  - TaskStop · KillShell 결과의 `task_id`로 `bg_end`(stopped)를 남긴다(오류 결과는 빼고)
  - 시험에 Monitor 작업을 TaskStop으로 멈추는 경우를 더했다
- 이미 적재된 bi55inwkw는 새 코드가 다시 읽지 않는다
  - 조립기와 같은 uuid로 `bg_end`를 한 번 넣었다(payload에 `fixed` 표시, 다시 적재돼도 겹치지 않음)
  - 대시보드 `background`가 `[]`가 됐다
- 남은 위험
  - 끝을 알리는 다른 길이 또 있으면 같은 일이 생긴다. 예: CC 안에서 사람이 작업을 끄는 화면, 세션의 `/clear`
  - 프로세스가 다시 뜨면 그 전 작업은 세지 않으므로 거기서는 풀린다
  - 그 밖에는 24시간 안에서만 센다
