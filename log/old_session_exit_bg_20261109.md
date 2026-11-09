# 옛 메인 세션이 안 꺼짐 — CC 끝내기 확인 창에 걸림 (2026-11-09 저녁, 원본 폴더)

## 본 것 (17:2x KST, 보기만 — 아무것도 끄지 않음)

- 옛 세션 = 111a592a, CC PID 1112244, tmux `cc-foreman-4`(창 `%196`), 원본 폴더
- 그 밑의 셸(PID 1637635, 17:07쯤 시작): 런슈즈 서브에이전트 응답(07:58 UTC 이후)을 1분마다 최대 120번 보는 반복 — **최대 2시간**. 응답이 생기면 2분 뒤 결과를 찍고 끝남. 인계에는 "이 세션과 함께 끝남"이라고 적혔지만 실제로는 남아 있었다
- tmux 화면: 마지막 턴 "done 5:07 PM · 1 shell still running" 아래에 CC 확인 창
  - "Background work is running / The following will stop when you exit: shell · S=… / 1. Exit and stop tasks / 2. Move to background and exit / 3. Stay"
- 런슈즈 감시는 둘: 옛 세션 것(위) · 새 세션 168ece53 것(PID 1700763, 같은 일, 조인은 `subagent_run` 기준). 새 세션 것이 있으니 옛 것을 멈춰도 확인이 끊기지 않는다

## 판단

- 꺼지지 않는 구조가 아니라 **CC가 끝내기 전에 묻고 기다리는 것**이다. 답하지 않으면 그 창에 계속 머문다. 2번(Move to background)을 고르면 세션이 뒤로 가서 그 일이 끝날 때(최대 2시간)까지 산다
- FOREMAN 화면에는 "뒤에서 도는 일 1"만 보이고 "끝내기 확인 창에서 멈춤"은 보이지 않는다 → 조용한 고장. README 「나중에 할 일」에 넣음

## 안전하게 끄는 법 (사용자가 함)

- 옛 창에서 **1. Exit and stop tasks** → 옛 감시 셸이 멈추고 세션이 끝난다. 런슈즈 확인은 새 세션 감시가 이어 받는다
