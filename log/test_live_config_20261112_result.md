# 합치기 설정 시험이 실제 config를 읽지 않게 (11-12)

## 한 일
- `tests/test_mergeprep.py`의 `test_live_config_starts_as_today`(실제 `config/handoff.toml`을 읽어 FOREMAN · 인프라가 human · squash 꺼짐이기를 기대)를 `test_config_without_project_rules_is_human_and_ff`로 바꿨다.
- 시험용 임시 설정(`tmp_path`)을 만들어 읽는다. 뜻은 그대로: 칸이 없거나 human이면 사람 승인 · ff, 칸이 있으면(foreman = manager · squash) 그 값을 읽는다. `human_always` 칸도 시험용 파일에 넣어 확인한다.
- 11-12 302(`test_mergeprep.py:163` · `test_moveflow.py:11`)와 같은 방식. `config/handoff.toml`은 고치지 않았다.

## 확인
- pytest 790 통과 1 건너뜀 · node 124 통과.
- 이 worktree의 `config/handoff.toml`을 foreman · 인프라 `approver = "manager"` · `squash = true`로 임시로 바꿔도 같은 결과로 통과했고, 바로 `git checkout`으로 되돌렸다(커밋하지 않음).

## 되돌리는 법
- 이 커밋을 `git revert` (시험 파일 하나만 바뀜).
