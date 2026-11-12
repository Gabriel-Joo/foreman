# 한 쪽 게시가 사람 수정으로 멈출 때도 덮기 줄 · 텔레그램 ✋ (2026-11-12, 코더 foreman-2)

## 한 일
- `bridge/docsync.py` — `DocSync.hold(project, path, edits, url)` · `DocSync.release(project, path)` 추가
  - `hold`: 한 쪽 게시가 `HumanEdited`로 멈추면 [지금 맞추기]의 「지난 결과」(`self.last[project]["held"]`)에 같은 꼴(`path · edits · count · url`)로 넣는다. 같은 경로의 옛 줄은 바꿔 끼워 **한 파일에 줄이 둘 생기지 않는다**. 알림은 기존 `_alert` 그대로(같은 문구 · 같은 키 `held:<프로젝트>:<커밋>:<경로>`) — 같은 파일 · 같은 커밋이면 두 길이 섞여도 한 번
  - `release`: 한 쪽 게시가 성공하면 그 파일의 줄을 치운다
  - `todo_items`: `hold`가 남긴 줄은 `ref_sha`를 달고 있어, git이 그 뒤 또 바뀌면(현재 ref 커밋과 다르면) 사라진다. [지금 맞추기]가 남긴 줄은 전처럼 `st["changed"]`에 있을 때만 뜬다
- `bridge/api/publish.py` — `POST /api/publish`의 `HumanEdited` 처리에서 `action = "publish"`이고 `force`가 아니면 `ds.hold(...)` 부르기(실패해도 409 응답은 그대로), 한 쪽 게시 성공 시 `ds.release(...)`
- 서기실 단추는 고치지 않았다 — 줄이 `act: "force"`로 같은 꼴이라 `scribe.js`가 그대로 [Notion 수정 버리고 덮기]를 그린다(누르면 `action: "docsync", force`, 관리 토큰)
- 시험: `tests/test_publish_hold.py` 새로 6개(가짜 게시기 · 가짜 알림기 · 가짜 status, Notion · `.env.notion` 안 씀). `tests/test_publish_scope.py`의 가짜 DocSync에 `hold` · `release` 한 줄씩

## 정한 것
- 남기는 자리는 **합쳤다**(새 표 없음) — 두 길이 같은 `last[project]["held"]`를 쓴다
- `docs/` 경로만 남긴다 — 서기 할 일 덮기 줄은 기술문서(`status`)만 다루므로 `portfolio/` 등은 줄을 만들 수 없다(409 응답만, 전과 같음). `docs = "off"`인 프로젝트도 남기지 않는다
- 프로젝트 토큰의 force 403은 그대로(사용자 결정)

## 확인할 것
- [x] 한 쪽 게시가 멈추면 그 프로젝트 서기 할 일에 덮기 줄 + 텔레그램 ✋ 한 번(두 번 눌러도 한 번) — `test_one_sided_hold_leaves_force_line_and_one_alert`
- [x] 단추(force)를 누르면 덮이고 줄이 사라진다 — `test_force_clears_line`
- [x] git이 다시 바뀌면 줄이 사라진다 — `test_git_moves_on_line_disappears`
- [x] [지금 맞추기]로 멈춰도 전처럼 뜨고 줄이 두 번 생기지 않는다 — `test_docsync_route_still_works_and_no_duplicate`
- [x] 멈춤이 없으면 아무것도 달라지지 않는다(런슈즈 · 펫퍼민트 포함) — `test_no_hold_means_nothing_changes`
- [x] pytest 748 통과(1 skipped) · node 123 통과
- [ ] 실제 브리지에서 인프라 09로 확인 — 합친 뒤 브리지를 다시 띄워야 한다(worktree에서는 하지 않음)

## 되돌리는 법
- 이 커밋을 `git revert`하고 브리지를 다시 띄운다(`systemctl --user restart foreman-bridge`, 승인 대기 0 확인 뒤). DB 변경 없음 · 설정 변경 없음
- 브리지가 다시 뜨면 메모리의 `last`가 비므로 남은 줄은 사라진다(다음 [지금 맞추기]가 다시 만든다)

## README에서 뺄 줄
- 없다
