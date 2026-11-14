# worktree에 .tools 링크 + 건너뛴 까닭 표시 (foreman-3, 11-14)

관리자 362의 일감. 370의 제안(`log/test_isolation_20261114.md` 2절)을 그대로 했다.

## 한 일
- `bridge/worktree.py`: `LINK_TOP`에 `.tools`, `EXCLUDE`에 `/.tools`, 커밋 후보 검사 `_forbidden`에 `.tools`. 원본에 `.tools`가 없으면 링크를 만들지 않는다(`.venv`와 같게). 이미 떠 있는 worktree는 건드리지 않았다
- `pyproject.toml`: pytest `addopts = "-rs"`. `-l`은 넣지 않았다(토큰이 찍힐 수 있다)
- `tests/test_worktree.py`: `.tools` 링크가 원본을 가리킴 · git에 안 보임 · 커밋 후보에서 빠짐(제외 목록이 없는 저장소에서도), 원본에 없으면 링크 없음 시험 2개
- `docs/11_worktree.md`: 링크 목록 두 곳과 쉬게 하기 제외 목록에 `.tools`

## 확인
- `tests/test_worktree.py` 24개 통과
- 이 worktree(foreman-3)는 고침 전에 만들어져 `.tools`가 없다. 여기서 전체 pytest를 돌리니 요약에 `SKIPPED [1] tests/test_terminal.py:526: ttyd 없음`이 찍혔다(건너뛴 까닭이 보인다)
- 전체 결과 `1 failed, 953 passed, 1 skipped`: 실패 1은 내가 새로 쓴 시험의 첫 판(`.tools`가 `info/exclude`에 걸려 처음부터 후보에 안 올라 skipped가 빔)이었고, 시험에서 제외 목록을 비우게 고쳐 통과했다(고친 뒤 test_worktree만 다시 돌림, 전체는 다시 안 돌림)

## 설계와 달랐던 점
- 없음. 다만 `.tools`는 `EXCLUDE`로 git이 처음부터 안 보므로 `_forbidden`은 제외 목록이 없는 저장소의 안전망이다(`.venv`와 같다)

## CLAUDE.md에서 관리자가 바꿀 글
「`.venv` · `.env*` · `node_modules` · CC 메모리는 원본을 가리키는 링크다」 줄에 `.tools`를 더한다(새로 만드는 worktree부터).

## README에서 뺄 줄
「시험 — `.tools/`가 worktree에 따라오지 않아 ttyd 시험이 조용히 건너뛴다」

## 규칙 위반
- 진행 글 영어: 11-14, 코드 고친 직후 "Edit the code."와 "Now the docs section while the tests run." 두 줄을 영어로 썼다. 한국어 규칙을 쓰기 전에 확인하지 않았다. 훅 알림을 받고 바로 한국어로 돌렸고, 이후 글은 모두 한국어
- 그 밖에는 없음(sed · heredoc 저장 · pgrep -f 쓰지 않음, Edit · Write만 사용)
