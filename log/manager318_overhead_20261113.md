# 관리자 318 — 313 정리 · 런슈즈 카드 미룸 · 머리 위 표시 다시 설계 합침 · 21:00 묶음 확인 (2026-11-13 오전, 원본 폴더)

앞 기록: [approval_hell_plan_20261112.md](approval_hell_plan_20261112.md) · [runshoes_manager_20261112.md](runshoes_manager_20261112.md). 309 → 318 인계(r=2a363d).

## 313 · 런슈즈

- 313: 일 안 함 · worktree 변경 0 · 앞 0을 따로 확인 → `action exit` ok(tmux 닫힘) → 사용자 「버려라」 → `worktree discard`(confirm `foreman-4`) ok. 남은 worktree는 원본 하나
- 그때 313 worktree가 코더 머리 위 「맡길 일 1 — 어긋남」(`bridge/reconcile.py` orphan)으로 떴다 — 사용자: 이름이 실제와 다르다 → README 「나중에 할 일」 줄 `8317b77`
- 런슈즈: 인계문의 상태(300 · `runshoes-3`)가 낡았다 — 사용자 「310에게 물어라」. 310 답(11-13, 읽기만): 300은 11-12 저녁 사용자가 지움 · `runshoes-3` 없음 · 살아 있는 작업 세션은 317(`cc/runshoes-2`, 5-2, 앞 2 · 커밋 안 한 변경 있음) · 옛 이력 기반 브랜치 없음 · 의견 「넣기, 단 5-2 합친 뒤」 + 조건 셋(V*.sql · CLAUDE.md · .claude · Jenkinsfile · Dockerfile*은 사람 승인 + 마이그레이션 순서 / 카드 승인과 push / squash 메시지를 런슈즈 꼴로). 그 밖: HISTORY · TODO 충돌, 5-2의 인프라 env 순서
- **사용자 결정**: 5-2 합친 뒤에 넣는다, 조건 셋은 그때. 310에게 전함(delivered) — 카드는 1단계라 push하지 않는다는 것도

## 머리 위 표시 — 확인(사용자 「확인과 제안만」) → 결정 → 319

- 확인: `human_needs`가 역할 · 턴 출처를 안 봐서 코더 보고가 관리자에게 중계돼도 코더에 「보고 옴」, 관리자의 relay · manager_ask 턴 응답도 「보고 옴」. 「…」은 둘(`stuck_turn` 깃발 · WAITING 차오르는 점), 서브에이전트와 뒤에서 도는 일은 머리 위에서 같은 「···」
- 사용자 결정: 신호는 API(「머리글은 글자 하나 틀리면 안 먹는다」) · 권한 거부 · 승인 대기 · 사람 승인 합치기 카드는 작업 세션에 그대로 · 중계 실패 · 관리자 없음이면 지금처럼 사람에게 · 글자 「관리자에게 보고함」 「관리자 답 기다림」 / 「사용자에게 보고함」 「사용자 답 기다림」(말풍선 칸에 맞게. 처음 지시 「사용자 보고 기다림」은 「사용자가 보고하기를 기다린다」로 읽혀 사용자가 고침 — 320)
- 코더 **319**(opus, `/api/spawn`, `.worktrees/foreman-2`) 하나로 — 서버 판정과 그림이 `render.js needMark`에서 만나 나누면 같은 파일을 둘이 고친다. 글자 지시는 뒤에 입력 대기열로
- 319 결과: [overhead_marks_20261113.md](overhead_marks_20261113.md). 역할 권한 observe 기록 0 · Bash 파일 고침 흔적 0(DB `event`)
- 합치기: merge-tree exit 0(따로) → 카드 `{"action":"merge","by":"manager"}` → squash **`580c6d7`** → pytest **797** · node **128** → push → 승인 대기 0 → **브리지 11:07:19**(1008315 → 1907150), 오류 0
- 실제 확인: 319로 escalate → 403(관리자만). 318로 `kind: report` → ok · `notified` · 대시보드 318 `escalate.report` 생김(보고라 21:00 묶음)

## 21:00 묶음 — 나감

- 11-12 21:00:43 `[FOREMAN] 📦 하루 묶음 11-12 — 일상 알림 13건` · 21:00:44 `[인프라] … 5건`(`notification` kind `digest` · sent · 오류 없음). 묶인 행(`bundled`) 합치기 5 + 턴 끝 13 = 18
- 11-13 것은 `digest`로 쌓이는 중

## 사람이 정할 것(319가 올림)

1. CLAUDE.md에 escalate 규칙 줄을 넣을지(안은 319 log) — FOREMAN · 인프라 관리자부터
2. 넘기기 기다림 `RELAY_GRACE` 150초
3. [전체] 지도 방 카드 「답 기다림 N」이 관리자 물음도 센다 — 「사용자 답 기다림」으로 따로 쓸지

## 남은 것

- docs 어긋남: 319 합침 알림의 「고치지 않은 문서」(10_office_design · 11_foreman_dispatch · operations · 11_worktree · style_guide)를 [doc_drift_candidates_20261112.md](doc_drift_candidates_20261112.md)에 더함 → 서기
