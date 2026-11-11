# 계획에서 확인 기다리기 빼기 · 계획 받기 실패 다루기(268) 합침 (2026-11-11 아침, 원본 폴더, 관리자 244)

앞 기록: [infra_bundle1_launch_20261110.md](infra_bundle1_launch_20261110.md). 결과: [coder_plan_nowait_fail_20261110.md](coder_plan_nowait_fail_20261110.md)

## 합침

- `cc/foreman-4` 커밋 넷: `6a2e1bb` 교장 지시서 · 교장 계획 인계 글에서 「확인을 기다려라」 뺌(CLAUDE.md 한 줄) · `dd1a59e` 계획 받기 실패 뒤 [버리기] 「disp is null」 · `d985d06` 실패 원인 가르기(한도 · 호출 실패 · 빈 답 · JSON 없음 · 형식 깨짐) · 기록
- 사용자가 함께 보라고 한 `cc/foreman` `49d1585`(관리자 docs push)는 11-10 21:00에 이미 main — 순서 문제 없음. main ← 268 `merge-tree` 충돌 없음(0), 커밋 안 된 변경 0
- 268이 쉬는 중이라 `end:true`로 합침(→ `12a17ed` · `753e3e3` · `642251f` · `e65538f`). 다른 시험 없음 확인 뒤 **pytest 579 통과 · node 87 통과** → push(`e65538f`). 승인 대기 0 → **브리지 09:37:04**(경고 없음)

## 「확인을 기다려라」가 사라졌나

- 교장에게 시험 계획(dispatch 247 — 세션은 띄우지 않음)을 받아 `first_prompt`를 봄: 끝이 「지켜야 할 것 …」으로 끝나고 "확인을 기다 · 기다려 · 5줄" 낱말 0. 시험 계획은 버림(`/dispatch/247/discard`)
- 세션을 띄울 때 붙는 인계 글: `bridge/handoff.py` `inject_prompt(confirm=False)` → `INJECT_PROMPT_GO` "「다음 할 일」을 바로 시작하라(사람이 계획 카드에서 이미 봤다)" — 교장 계획으로 띄울 때(`ensure_injectable(..., confirm=False)`, 863줄). 인계만 하는 새 세션으로 옮기기는 그대로 확인을 기다린다
- 실제로 세션을 띄워 첫 응답을 본 것은 아니다 — 다음 교장 띄우기 때 본다
