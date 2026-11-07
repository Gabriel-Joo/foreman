# 로드맵 0단계 — 런슈즈 · 펫퍼민트 CC를 tmux로 (결과)

2026-11-02에는 FOREMAN 세션(`cc-foreman`)만 옮기고, 런슈즈 · 펫퍼민트는 FOREMAN이 실제로 동작하는 것을 확인한 뒤로 미뤘다.
11-05 사용자 결정으로 런슈즈부터 옮겼다. 펫퍼민트는 런슈즈 결과를 보고 사용자가 알려 줄 때.

## 옮기는 방법(11-05 조사 — 그 자리 이전은 안 된다)

- 돌던 프로세스를 그대로 tmux로 옮길 방법이 없다: reptyr 없음 · `ptrace_scope`=1(sudo 필요), `legacy_tiocsti`=0(다른 터미널에 키 넣기 막힘)
- 그래서 **사용자가 그 터미널에서 `/exit` → tmux 안에서 `claude --resume <id>`**. `--fork-session`은 붙이지 않는다
  - `--resume <id>`는 같은 세션 ID로 같은 jsonl에 이어 쓴다 → DB에서도 같은 세션 행 · 턴 번호가 이어진다(9599d666 시험 · 아래 런슈즈 실측)
  - `--fork-session`은 새 ID로 앞 줄을 uuid째 복사한다 — 11-03 bb19f9d2 적재 막힘이 이 모양이었다(CC 백그라운드 세션이 `--fork-session --resume`을 쓴다)
- 주의: `/exit`만 친다. 터미널 창을 닫거나 셸을 끝내면 같은 tty에 멈춰 둔 CC(`T` 상태)가 죽는다. 멈춘 프로세스가 살아 있는 동안 그 세션을 resume하지 않는다

## 런슈즈 (11-05 11:20)

- 사용자가 pts/8의 런슈즈 CC(pid 1309470)를 `/exit`. pts/8의 멈춘 CC 2개(1301867 · 3872105)는 그대로 `T`
- `tmux new-session -d -s cc-runshoes -c ~/AI_programming/runshoes` → 그 안에서 `claude --resume c5320140-b09b-4b80-b370-c55384ce71b3`(pid 3628431, pane `%134`). 셸 pane이라 CC가 끝나도 pane은 남는다
- 확인
  - 대화 이어짐: CC 화면에 직전 응답(발볼 조사 정리)이 그대로, DB는 같은 세션 행 156 · 턴 번호 593 → 594로 이어짐(새 행 없음)
  - 픽셀 화면: 런슈즈 세션을 열면 입력 칸이 열림(`injectable: true`, pane `%134`)
  - 시험 입력: 픽셀 화면 패널에서 Ctrl+Enter로 "[포먼 시험] … '확인'이라고만" → "보냈다 — 새 턴", CC가 "확인" 응답, 턴 5745 `origin=human` · stop hook으로 닫힘, 텔레그램 `[런슈즈] 끝남 · 5초` 보냄
  - 적재: `/api/dashboard` ingest `ok` · 막힘 0, 그 뒤 알림에 "적재 막힘" 없음
- 그 뒤 사용자가 같은 pane에서 직접 입력해 쓰고 있다

## fork 턴의 prompt_uuid가 빈 원인 · 고침

시험 fork 세션(91b57a64, `claude --fork-session --resume 9599d666`)의 새 턴이 `prompt_uuid = NULL`이었다.

- **원인**: `--fork-session`은 앞 세션 줄을 uuid · 시각째 복사하면서 사람 줄의 `promptId`를 **새 프롬프트의 promptId로 바꿔** 쓴다(줄 단위 비교: 복사 줄에서 바뀐 것은 `sessionId` · `promptId`뿐).
  11-03의 방어는 "복사 줄은 promptId가 빠져 있다"(백그라운드 fork, bb19f9d2)는 모양만 봤다 → promptId가 있는 복사 줄은 그대로 지나갔다
  - 첫 복사 줄("one")이 새 promptId로 새 턴에 붙고, 그 uuid는 앞 세션 턴이 이미 가져서 `_free_uuid`가 NULL로 비웠다
  - 진짜 새 프롬프트 줄("three")은 같은 promptId라 "이미 있는 턴"으로 지나가 uuid도 start 이벤트도 안 남았다
  - 시험에서는 UserPromptSubmit hook이 턴을 먼저 열어 본문이 맞게 남았지만, hook보다 트랜스크립트가 먼저 읽히면 **턴 본문이 옛 프롬프트("one")**가 된다(고치기 전 코드로 시험에서 재현)
  - 복사 구간의 turn_duration · 중단 표시 줄이 새 세션의 열린 턴을 옛 시각으로 닫을 수도 있었다
  - 이벤트는 uuid UNIQUE라 겹쳐 쌓이지 않았다
- **고침**(`bridge/assembler.py`): promptId가 아니라 **uuid로** 복사 줄을 가린다 — 사람 줄의 uuid가 다른 세션의 이벤트나 턴에 있으면 복사 구간 시작.
  복사 구간에서는 응답 · 도구 결과 · system · attachment 줄을 건너뛰고, 사람 줄은 첫 새 프롬프트가 나올 때까지 복사로 본다.
  같은 턴의 둘째 user 줄처럼 DB에 이벤트가 없는 복사 줄은 시각으로 가린다(복사 줄은 원래 시각 — 복사 구간 앞의 이 세션 줄보다 이르다). 복사 줄의 옛 시각으로 `last_ts`를 되돌리지 않는다
- 시험 `test_cli_fork_copied_lines_with_new_prompt_id`(실측 모양: queue-operation → 복사 줄 · 둘째 user 줄 · 중단 표시 · turn_duration → 새 프롬프트). 고치기 전 코드에서는 실패(본문 "첫 지시", uuid NULL). Python 349 · JS 19 통과
- 브리지 다시 띄움(11:27경, 10초 남짓 끊김)
- 이미 적재된 턴 5733(시험 세션)은 고치지 않았다 — 시험용이고 본문은 맞다

## 펫퍼민트 (11-08 08:1x, 사용자 지시)

- 11-06 정전 뒤 펫퍼민트 CC 프로세스는 없었다(살아 있는 CC는 런슈즈 122348 · FOREMAN 137786뿐, 멈춘 `T` 프로세스도 재부팅으로 없음)
- 마지막 세션은 `bb19f9d2-97d8-493b-adbc-0bc198b20777`(DB 세션 170): 3.5MB, 마지막 대화 11-05 02:29 UTC. 이 파일은 `cddadc68`(DB 155, 375MB · 압축 12번, 마지막 대화 11-02 21:48 UTC)의 끝에 `continued-in → bb19f9d2`로 이어진 것이고, 앞 세션의 마지막 압축 요약(10-28)과 그 뒤 줄을 이어받아 시작한다(11-03 적재 막힘이 난 그 파일)
- `tmux new-session -d -s cc-petmint -c ~/AI_programming/petmint-rag-chatbot` → `claude --resume bb19f9d2-…`(pid 264138, pane `%66`). `--fork-session` 없음
- 확인: CC 화면에 직전 응답(11-05 11:29)이 그대로 · DB는 같은 행 170(`IDLE`, `injectable: true`, 새 행 없음) · 적재 ok · 막힘 0
- **시험 입력은 하지 않았다** — 화면에 주간 한도 88% 사용이 떠 있었고, 다시 띄운 세션의 첫 턴은 맥락 전체를 새로 읽는다. 사람의 첫 입력이 그 확인을 대신한다
- 압축 손실 점검은 돌리지 않았다(사용자에게 의견만). 점검 대상은 170이 아니라 155(`cddadc68`) — 압축 12번의 역사가 거기 있다
