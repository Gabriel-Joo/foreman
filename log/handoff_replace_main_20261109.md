# [새 세션으로 옮기기]는 옛 세션을 빼고 worktree 판단 — 원본 폴더에서 뜬다 (2026-11-09, 원본 폴더)

앞 기록: `log/handoff_flow_check_20261109.md` 「남은 것」 — 사용자 결정(11-08 세션 218): 옮기기는 같은 세션을 잇는 일이라 원본 폴더에서 띄운다. 옛 세션 끝내기가 실패하면 [옛 세션 다시 끝내기]가 뜨니 이 방식으로 간다.

## 고친 것

- `bridge/handoff.py`
  - `will_worktree(cwd, exclude_cc=None)` — 살아 있는 세션(`live_sessions`, 키가 CC 세션 id) 중 `exclude_cc`는 세지 않는다
  - `spawn(row, summary_id, replace=False)` — replace면 `spawn_new(..., exclude_cc=row.cc)`. `spawn_new`은 `worktree=None`일 때 그 값으로 판단
  - `injection(summary_id, target_cwd=None, replace=False)` — 미리보기의 `worktree_next`도 같은 판단(옛 세션 = 요약을 쓴 세션 `row.cc`)
- `bridge/api/handoff.py` — `/sessions/{sid}/spawn` 본문 `replace: bool = False`, `/summaries/{id}/injection?replace=1`
- `bridge/static/js/handoff.js` — 옮기기 흐름 `flowGo`는 `replace: true`, ② 확인 미리보기(`flowPreview`)는 `?replace=1`. [새 세션만 띄우기]는 옛 세션이 남으니 그대로(worktree). ⑂ 줄 툴팁 "(이 세션 포함)" → "(옮기기는 이 세션을 빼고 셉니다)"

## 확인

- 새 시험 `test_will_worktree_replace_excludes_old_session`: 옛 세션 하나뿐 → 빼지 않으면 worktree, 빼면 원본 폴더 / 다른 세션(같은 프로젝트의 worktree 안)이 하나 더 → 빼도 worktree
- 전체 477 통과 · JS 48 통과
- 브리지 다시 띄움(승인 대기 0건 확인 뒤): PID 856159 → 980920, 기동 정상. 운영 API `injection` · `injection?replace=1` 둘 다 응답(요약 12의 세션 214는 이미 끝났고 이 세션이 원본 폴더에 살아 있어 둘 다 True — 맞는 값)
- **실제 옮기기는 아직 안 해 봤다** — 다음 [새 세션으로 옮기기] 때 ② 확인에 ⑂ 줄이 없고, 받은 세션 cwd가 원본 폴더인지 본다

## 알아둘 것

- 이 세션의 셸에는 `XDG_RUNTIME_DIR`가 비어 있어 `systemctl --user`가 "Process org.freedesktop.systemd1 exited with status 1"로 실패했다(샌드박스 밖에서도). `XDG_RUNTIME_DIR=/run/user/1000`을 주면 된다
- 옛 세션이 worktree 안에 있던 경우도 이제 원본 폴더에서 뜬다(다른 살아 있는 세션이 없으면). 전에도 옛 worktree가 아니라 **새** worktree였으니 옛 브랜치를 못 보는 건 같다 — 옛 worktree는 끝낸 뒤 [합치기]로 합친다
- 끝내기가 실패하면 잠깐 원본 폴더에 두 세션이 붙는다(사용자가 받아들인 대가)
