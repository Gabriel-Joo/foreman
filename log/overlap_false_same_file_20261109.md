# "같은 파일" 겹침 알림 첫 실제 건 — 헛경보 (2026-11-09 저녁, 원본 폴더)

화면 worktree 기록([foreman-2_screen_ctx_switch_overlap_20261109.md](foreman-2_screen_ctx_switch_overlap_20261109.md) 「남은 것」): "같은 파일 알림을 실제로 받아 본 적은 없다 — 처음 받으면 오탐인지 보고, 오탐이면 파일 이름을 기록한다"

## 알림

- 브리지 로그 `foreman.overlap 같은 파일 session=230 ~ 233` — 19:57:18 · 20:00:18 · 20:09:18, 파일 bridge/api/scribe.py · bridge/main.py · bridge/scribe_room.py · bridge/static/css/panel.css · bridge/static/js/office.js · bridge/static/js/todoinbox.js · tests/test_stage2_db.py · bridge/approvals.py
- 사용자에게 "233도 scribe.py, approvals.py, main.py 외 5개를 고쳤다"로 옴

## 맞대 본 것(git)

- 230(메인)이 고친 것: 17:3x 다른 저장소 막음(`3ec3294` — approvals.py · main.py), 19:3x 할 일 받는 칸(`5e2692a` 19:36 커밋 — scribe.py · scribe_room.py · office.js · panel.css · todoinbox.js · test_stage2_db.py). 둘 다 커밋 · push
- 233의 바탕(`git merge-base main cc/foreman-2`) = **`5e2692a`** — 230의 변경을 이미 다 갖고 시작했다
- 바탕 뒤 main 변경은 log 한 파일(`log/dispatch_flow_decision_20261109.md`)뿐 → 233이 무엇을 고치든 코드 충돌은 날 수 없다(합칠 때 rebase가 log 커밋 위로 얹을 뿐)
- 233이 230의 것을 지우지 않았는지: worktree approvals.py에 `self.scope` · `다른저장소-쓰기` 그대로(233은 스키마 막힘 알림을 그 옆에 더함), main.py `RepoScope` 그대로

## 판단

- 헛경보. 감지기는 "두 세션이 같은 파일에 Edit했다"만 보고, 한쪽 변경이 이미 커밋돼 다른 쪽 바탕에 들어 있는지는 보지 않는다
- 230의 변경을 되돌릴 필요 없음(되돌리면 233이 그 위에 쌓은 것 — todoinbox.js 받는 사람 고르기 등 — 이 깨진다)
- 미리 맞대기: 233 커밋은 `git merge-tree --write-tree main cc/foreman-2`, 커밋 안 한 변경은 바탕 뒤 main 변경 파일과 겹치는지(`git diff --name-only <바탕> main`)로 233이 끝나기 전에도 본다 — 이번엔 겹치는 파일 0
- 고칠 것은 README 「나중에 할 일」에 — A의 파일 중 커밋돼 B 바탕에 든 것은 빼고 맞댄다
