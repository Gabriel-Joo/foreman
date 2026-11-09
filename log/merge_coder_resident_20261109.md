# 코더 상주 worktree(세션 233) 합친 뒤 — 합치기 · 시험 · 브리지 · 「합친 뒤 확인」 (2026-11-09 밤, 원본 폴더)

앞 기록: [coder_resident_20261109.md](coder_resident_20261109.md)(233의 결과), [dispatch_flow_decision_20261109.md](dispatch_flow_decision_20261109.md)(교장 경로 dispatch #152)

## 합치기 전

- 233은 "뒤에서 도는 일은 없다"고 했지만 그 CC 밑에 15분째 도는 셸이 있었다 — `until ! pgrep -f "tools/screen.py" …` 기다리기가 **`pgrep -f`가 자기 명령 글에 걸려** 끝나지 않음. 이대로 끝내면 끝내기 확인 창에 걸린다([old_session_exit_bg_20261109.md](old_session_exit_bg_20261109.md)) → 233에 멈추게 함(TaskStop), 그 실수는 233 기록에(`e37a6aa`)
- 메인도 같은 실수를 했다: 시험 전 "다른 pytest가 도나"를 `pgrep -f 'python -m pytest'`로 봐서 자기 셸에 걸려 "다른 pytest 있음"이 헛나왔다(오늘 세 번). 시험 결과에는 영향 없음 — 앞으로 `pgrep -f`로 자기 글이 든 패턴을 찾지 않는다(대괄호 트릭 `[p]ython` 또는 DB · 파일로)

## 합치기 · 시험 · 브리지

- 양쪽 커밋 안 한 변경 0, `merge-tree` 충돌 없음, 233 하위 프로세스 0 → `POST /api/sessions/233/worktree {merge, end}`: 커밋 3개(`00becd2` · `4139ac3` · `b02fa99`), tmux 닫힘, **스키마 잠금 풀림**
- 메인의 다른 저장소 막음이 233 변경 뒤에도 그대로(`approvals.py` `self.scope` · `다른저장소-쓰기`, `main.py` `RepoScope`)
- 시험 **535 통과**(233은 ④ 전 533), push
- 승인 대기 1건(세션 236, 20:36 새로 온 Bash "cc → auto mode 분류기 · 설정")이 있어 바로 띄우지 않고 0이 될 때까지 DB만 보며 기다림(20:37:37 0) → **20:37:45 브리지 다시 띄움**

## 「합친 뒤 확인」(233 기록의 1~7)

| | 결과 |
|---|---|
| 1 0028 적용 | ✓ `migrate --status` 0028까지 적용. `--status`는 잠금을 잡지 않았다(읽기 명령은 새 패턴 밖) |
| 2 `/api/coder/todo` · `/api/schema-lock/board` 200, `config/scribe.toml` | ✓ 둘 다 200, `[nudge] new_min = 3 · oldest_days = 3` |
| 3 "코더에게" 적기 → 코더 맡길 일 → 계획 | **세션을 띄우기 직전까지만** — API로 "코더에게" 시험 글 #12 → `/api/coder/todo` foreman inbox에 #12, 받는 함 목록 "새로 · 코더에게" → [버리기] → 맡길 일에서 빠짐. [이대로 시작](실제 코더 세션)은 하지 않음. 화면에서 누르는 흐름은 헤드리스로 안 봄 |
| 4 [쉬게 하기] · [이어서] | **안 함** — 실제 worktree 세션을 띄워 쉬게 해야 한다(다음 실제 worktree 때) |
| 5 스키마 잠금 ① 배너 · [풀기] ② 막힘 알림 ③ 일찍 풀기 | **안 함** — 지금 FOREMAN 잠금이 없고, ③은 원본 폴더 세션이 마이그레이션을 적용 · 커밋해야 볼 수 있다(다음 실제 마이그레이션 때) |
| 6 `from bridge.db.migrate import connect` 읽기 조회 | ✓ 잠금이 안 잡힘(`/api/schema-lock`에 foreman 없음) — 오늘 메인이 17:16에 걸렸던 헛걸림이 고쳐짐 |
| 7 `screen.py --ui-scale 1.25` 세 테마 × 세 폭 | ✓ 실제 데이터 [⌂] · [전체] · FOREMAN · 런슈즈 · 펫퍼민트 모두 0. 시연 `coder_resident`(FOREMAN · 런슈즈): office 1024 nameAudit 1 — `s:974` 「서기 — 정리」(시연 세션), 233이 main에도 있다고 한 것 |

- 받는 함에 이미 11줄(사용자가 [＋ 할 일]을 쓰기 시작) — 시험 글 #1 · #12는 「버림」

## 남은 확인

- 4(쉬게 하기 · 이어서 — 같은 cc id로 붙는지 포함) · 5(잠금 배너 · 막힘 알림 · 일찍 풀기)는 실제로 그 상황이 올 때. 상주 코더 말풍선 클릭은 233도 헤드리스로 못 눌러 봄
