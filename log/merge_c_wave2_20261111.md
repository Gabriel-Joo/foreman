# 286(C 묶음 2물결) 합침 · 0031 · 스위치 전부 꺼진 채 · 새 브리지 (2026-11-11 저녁, 원본 폴더, 관리자 276)

앞 기록: [merge_term_inputh_20261111.md](merge_term_inputh_20261111.md). 세션 결과: [coder_c_wave2_20261111.md](coder_c_wave2_20261111.md)

## 합치기 전 확인(사용자 지시 — 확인만, 그다음 합치기)

- merge-tree main ↔ `cc/foreman-4`: `27b8d3a…` exit 0. 286 ↔ 287(`cc/foreman-2`)도 exit 0
- 고친 파일: 286 39개, 287 8개(커밋 `dashboard.py` · `office.js` · `render.js` · 시험 둘 + 작업 트리 `office.js` · 시험 · `demo/merge_wait.json`) — **겹침 0**. 287은 `approvals.py`를 건드리지 않음
- 맞물림: 287 `dashboard.py`가 `mergeprep.view()` 카드의 `sid` · `made_at` · `head8` · `files` · `asks` · `status`를 읽는다 — 286에서도 `Card` 칸 그대로
- 0031은 더하기만(dispatch 칸 셋 · todo_inbox 칸 하나). 287은 스키마를 건드리지 않음 → 286 먼저 합쳐도 부딪히지 않음. 단 **0031은 브리지 다시 띄우기보다 먼저**(286 코드가 새 칸을 쓴다)

## 합침(사용자 승인)

- 카드 286 `ready` · 032eb54 · 커밋 10 · 충돌 없음, merge-tree 따로 다시 exit 0 → 카드 승인 → `merged`, 커밋 10개 main(끝 `5e351d6`), 286 끝냄 · 스키마 잠금 풀림. 관리자 세션에 「합쳤다 · 정리 후보 18개」
- **17:16:55 `bridge.db.migrate` → 0031 적용**(브리지 다시 띄우기 17:19:09보다 먼저). 칸 넷 확인: `dispatch.handed_to`(bigint unsigned) · `handed_at` · `handed_alert_at`(datetime(3)) · `todo_inbox.edited_at`(datetime(3)), 모두 NULL 허용
- 다른 pytest 없음 확인 뒤 혼자: **pytest 683 · node 118 통과** → push(`5e351d6`)

## 스위치 — 하나도 켜지 않음

| 파일 · 칸 | 값 |
|---|---|
| `config/tokens.toml [project_tokens]` | `enabled = false` |
| `config/managers.toml [managers]` | `enabled = false` |
| `config/managers.toml [handover]` | `enabled = false` |
| `config/roles.toml [roles]` | `mode = "observe"` |
| `config/handoff.toml [move]` | `one_flow = false`(이 칸은 `enabled`가 아니라 `one_flow`) |
| `config/handoff.toml [merge_prep]` | `enabled = true`(앞서 켜 둔 그대로, foreman만) |

## 새 브리지

- 승인 대기 0 → 다시 띄움: 옛 PID 398849 → **새 PID 521991**(17:19:08 시작), HTTP 200, 오류 줄 없음
- 기동 로그: 「역할 권한 observe: worktree-push, bash-file-edit, manager-code, scribe-code」 있음, 「합치기 준비 켬: 턴 끝마다 + 60초마다 훑기」, 프로젝트 토큰 · 관리자 · 계획 넘기기 켬 줄 없음(꺼짐)
- 화면: `screen.py` office · magic · site × 1366 좁게 × [⌂] · FOREMAN — 점검 문제 0 · 페이지 오류 0, 세 테마 방 자리 같음
- 꺼진 기능 새어 나옴: 화면 글에서 「관리자에게 보내기」 · 「고른 것으로 계획」 · 「넘겨받은」은 없음. 「한 흐름 · 프로젝트 토큰 · 역할 권한」이 FOREMAN 방에서 보였으나 셋 다 패널에 저절로 열린 관리자 세션 276의 **대화 글**(`msg out` · `msg in`)이었다 — 단추 · 칸이 아니다. 새어 나온 것 없음

## 켜는 순서가 기록에 있는가 — 일부만

- `coder_c_wave2_20261111.md` 149줄 「켤 때 차례(사용자)」: **토큰 · 관리자만** ① 토큰 만들기 ② `tokens.toml` · `managers.toml [managers]` 켬 ③ 그 저장소 CLAUDE.md ④ 관리자 세션 띄움 ⑤ 필요하면 `roles.toml` · `merge_prep projects` 넓힘. 켠 뒤 무엇을 볼지는 없음
- 「합친 뒤 관리자가 할 일」 4: `[move] one_flow`와 `[handover]`는 켜 볼 때 볼 것이 있음(옮기기 ①~⑦ · 「넘겨받은 글」, 넘긴 계획 15분 알림)
- `roles` enforce: 관찰 쿼리(하루 뒤 규칙별 수)만 있고 enforce로 켜는 차례 · 켠 뒤 볼 것은 없음
- **기능 사이의 켜는 순서(무엇을 먼저 켤지)는 없음.** 관리자는 이번에 적지 않음(사용자 지시)
