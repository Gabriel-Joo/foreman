# 코더 상주 · 임시 일꾼 · 쉬게 하기 · 맡길 일 · 정리 제안 + 스키마 잠금 화면 (2026-11-09 밤, worktree `cc/foreman-2`, 세션 233)

앞 기록: [todo_inbox_20261109.md](todo_inbox_20261109.md) · [dispatch_flow_decision_20261109.md](dispatch_flow_decision_20261109.md) · [old_session_exit_bg_20261109.md](old_session_exit_bg_20261109.md)

## 정한 것(사용자 11-09)

- 임시 일꾼의 겉모습: **반투명 + 이름표**(물어서 고름) — 세션 그림 그대로 60% 비침, 이름표 "임시 · <세션 제목>" + 점선 테두리, 끝나면 연기로 사라짐
- 맡길 일에 **걸린 승인**(승인 대기 · 권한 거부)도 센다(메인 230 보충)
- 7번 스키마 잠금 ①~③(메인 230 보충, 사용자 — "설계는 사람이 푼다인데 누를 곳이 없다")

## 한 일

**코더 상주(office.js · theme.json)**
- 방마다 코더가 늘 있다. 살아 있는 코더 세션(역할 없음 · coder)이 없으면 테마의 `coder_home` 자리에서 쉬는 동작(오피스 라운지 coffee · 마법학교 대강당 read · 현장 함바 coffee), 머리 위 말풍선
- 코더 세션이 붙으면 가장 먼저 뜬 세션이 상주 코더의 그림 · 색을 쓰고 자리에서 책상으로 걸어간다. 끝나면 그 자리에서 다시 쉬는 자리로 걸어 돌아온다(끝난 코더 세션은 3분 흐리게 남기지 않는다)
- 둘째 코더 세션부터 임시 일꾼. 상주 코더 호버 "코더 · 일 N — … 나머지 N개는 임시 일꾼이 합니다", 임시 일꾼 호버 "세션 N을 맡았습니다"
- 자리: `layoutAudit` 기준 빈 곳을 탐색해 고름(오피스 (7.5, 12.8) · 마법학교 (7.6, 11.0) · 현장 (4.3, 12.8)). 첫 짐작 오피스 (6.6, 12.4)는 강아지 소품 안, 마법학교 (7.5, 10.1)은 탁자에 걸렸다

**맡길 일(coder.js · bridge/coder_room.py · /api/coder/todo)**
- 셈: 코더에게 받은 할 일(새로) + 쉬게 한 일(합치기 기다림) + 파이프라인 실패(`chains[0].broke`) + 빌드 알림 없음(`watch.state = missing`) + 승인 대기(질문 제외) + 권한 거부(`s.denied`). 앞 둘은 DB, 나머지는 화면이 이미 받는 store 값 — 새로 판정하지 않는다
- 말풍선: 쉬게 한 일만이면 "맡은 일 N — 합치기 기다림 · N일째"(하루 넘으면), 섞이면 "맡길 일 N · 합치기 기다림 M"
- 코더를 누르면 패널 「코더」: 맡길 일(받은 할 일 줄 [계획으로] · [버리기], 그 밖 [세션 열기]) · 지금 일(상주 · 임시) · [＋ 할 일 적기](코더에게를 고른 채)
- [계획으로] → [＋ 세션] 창의 감독실 말하기 칸에 글을 채우기만 한다(바로 띄우지 않음). [이대로 시작]에 `inbox_id`가 실려 그 세션이 가져간다(`taken_by`)

**받는 사람(0028 · scribe_room.py · todoinbox.js)**
- `todo_inbox.assignee`(scribe 기본 · coder). 운영 DB 적용(20:0x). [＋ 할 일]에 "누구에게: 서기 정리 / 코더에게"
- 상태 이름이 받는 사람마다: 코더 몫은 "코더가 하는 중" → 합쳐지면(또는 원본 폴더 세션이 끝나면) **"끝남"**, 서기 몫은 그대로 "옮김". 서기 「나중에 할 일 정리」는 서기 몫만 가져간다

**쉬게 하기 · 이어서(handoff.py · worktree.py · handoff.js)**
- [쉬게 하기](worktree 세션 패널 「세션」 맨 앞): 작업 중 · 뒤에서 도는 일(백그라운드 Bash · Monitor · 서브에이전트 — 대시보드와 같은 기준)이 있으면 **먼저 막고 까닭을 띄운다**(커밋도 안 함). 없으면 `git add -A` → 넣으면 안 되는 것(`.env*`(견본 빼고) · `.venv` · `node_modules` · worktree 밖 링크)은 내리고 결과에 적음 → 커밋 "쉬게 하기: 진행 중 저장 — <제목>" → /exit. 안 내려가면 tmux 화면에서 CC 끝내기 확인 창을 찾아 "CC 끝내기 확인 창에 걸렸습니다"로 알린다. `session_action` `rest`(실패도 ok=0으로)
- [이어서](「따로 작업」, 끝난 worktree 세션): 새 tmux 창에서 `claude --resume <cc> [--model]`. 대화 기록 파일이 없거나 45초 안에 안 붙으면 까닭을 띄운다. `rest-resume` · `spawn` 기록(끝낼 때 tmux 정리가 알아보게). 다른 cc id로 이어지면 새 행에 이름 · 역할 · 캐릭터를 물려준다
- 「따로 작업」에 "쉬는 중 — 합치기 기다림 · …부터 · N일째". [합치기] · [버리기]는 그대로

**서기 "정리할까요?"(config/scribe.toml · scribe.js)**
- 서기 몫 새로가 `new_min`(3)개 이상이거나 가장 오래된 것이 `oldest_days`(3)일이면 서기 머리 위 "정리할까요?". 누르면 서기 창이 「나중에 할 일 정리」 줄을 밝히고 그 [시키기]를 primary로 연다 — 세션은 사람이 [시키기]를 눌러야 뜬다

**스키마 잠금(7번, schemalock.py · approvals.py · main.py · office.js)**
- ① 방 배너 줄: "🔒 DB 구조 잠금 — 세션 N(원본 폴더|worktree x)이 HH:MM부터 쥐고 있습니다(무엇) — 눌러서 풉니다", 누르면 확인 창 → `DELETE /api/schema-lock/{project}`. 화면용 `GET /api/schema-lock/board`(세션 번호 붙임). 원본 폴더 세션이 쥔 것도 보인다
- ② 막힘: 다른 세션이 잠금에 막히면 잠금 상태에 `blocked`를 남기고 배너가 "🔒 멈춤 — 세션 M이 스키마 잠금에 막혔습니다. 쥔 세션 N(…부터)"로 바뀐다. 텔레그램은 막힌 세션마다 한 번(`notification.kind = schlock`)
- ③ 일찍 풀기: 원본 폴더 세션이 쥔 FOREMAN 잠금은 1분마다 — 그 작업 트리 `migrations/NNNN_*.sql`이 모두 `schema_migrations`에 있고 `git status -- migrations/`가 비면 푼다. 로그 "스키마 잠금을 일찍 풀었다 — …", 배너 10분 "🔓 잠금을 풀었습니다 — 적용 · 커밋 끝 — …". worktree 세션이 쥔 것은 합치기 전까지 그대로. FOREMAN 저장소(`bridge/db/migrate.py`가 있는 곳)만 — 다른 저장소의 DB는 브리지가 모른다

- ④ 잠금 명령 패턴(`config/worktree.toml`, 메인 보충 · 사용자 확인 "config 고침"): 마이그레이션을 **돌리는** 명령만 — FOREMAN `-m bridge.db.migrate` · `python …bridge/db/migrate.py`(둘 다 `--status`는 뺌), 런슈즈 flyway 실행 작업(`flywayMigrate` · `flyway migrate` 등). 전에는 `from bridge.db.migrate import connect`(읽기 조회)도 시도로 잡혀 메인이 17:16에 읽기만 하고 잠금을 쥐었고, 20:1x에는 읽기 조회가 막혔다. 런슈즈 `\bflyway\w*\b`도 `SELECT … FROM flyway_schema_history`를 잡았다

**시연 장면** `bridge/static/demo/coder_resident.json` — 쉬는 코더(런슈즈: 쉬게 한 일 2일째, 펫퍼민트: 받은 할 일) · 상주 + 임시 둘(FOREMAN) · 정리할까요?(펫퍼민트) · 잠금 막힘(FOREMAN) · 일찍 푼 것(런슈즈)

## 확인

- 시험: 새 파이썬 4 — `test_save_progress_never_commits_links`(.gitignore · info/exclude 없이도 `.env.bridge` · `.venv` · `web/node_modules` · 밖 링크 안 들어감, 견본은 들어감, 뺀 것을 올린 채 두지 않음) · `test_save_progress_commit_failure_unstages`(pre-commit 실패 → 거부 · 내림) · `test_schema_lock_blocked_notice_and_early_release` · `test_inbox_assignee_coder_jobs_and_rest`(받는 사람 분리 · 코더 끝남 · 쉬게 한 일 셈(실패 ok=0 안 셈, 합치면 빠짐) · 제안 기준). `test_schema_lock_commands_only_running_migrations`(실제 config — import만 하는 읽기 · `--status` · `grep … migrate.py` · `flyway_schema_history` 읽기 · `flywayInfo`는 잡지도 막히지도 않음, 돌리는 명령은 잡음). JS `coder.test.mjs` 5(맡길 일 · 말풍선 · 코더 판정 · 상태 호버 · 날수). 전체 pytest 533 통과 · 1 건너뜀(④ 시험 더하기 전, 다른 pytest 없을 때) — ④ 뒤 `tests/test_worktree.py` 9 통과
- 화면(미리보기 :8200, `--ui-scale 1.25`, 시연 `coder_resident`): 세 테마 × 1920 · 1366 · 1024 × [⌂] · [전체] · 펫퍼민트 · 런슈즈 · FOREMAN — layoutAudit · cardAudit · tipAudit · propAudit 0, `coder_home`의 audit(가구 안 · 가림) 0
  - **nameAudit 1(오피스 1024 FOREMAN 「서기 — 정리」)은 이번 변경 전부터 있다** — main 화면에 같은 still 장면을 띄워도 같은 1건. 실제 데이터 화면의 오피스 1366 「서기」 1건도 main에서 같은 자리 · 같은 값(지금 도는 세션 배치 때문). 고치지 않았다
- 사진으로 본 것: 런슈즈 오피스 1366 라운지의 코더 + "맡은 일 1 — 합치기 기다림 · 2일째", 마법학교 FOREMAN의 "임시 · 코더 — 조사" · "임시 · 코더 — 시험" 점선 이름표, 현장 펫퍼민트의 "맡길 일 1" · 서기 "정리할까요?"

## 설계와 다른 점 · 판단 근거

- 상주 코더의 몸은 세션 캐릭터 키(`s:<id>`)를 그대로 두고 그림 · 색만 바꿨다 — `openSession` · 서브에이전트 부모 키 · 패널이 모두 `s:<id>`를 찾는다. 걷기는 위치를 넘겨 이었다(쉬는 자리 ↔ 책상)
- 상주 코더가 일하는 중에 그 캐릭터를 누르면 세션이 열린다(코더 목록이 아님). 일하는 중의 맡길 일은 말풍선 · 호버로 보이고, 목록은 세션이 없을 때 코더를 누르면 열린다 — 아래 「남은 것」
- 서기 할 일은 화면을 연 순간 한 번 읽고 1분마다 다시 읽는다(전부터). 시연 장면에서는 대본이 붙기 전에 읽어 첫 1분 동안 "정리할까요?"가 비었다 — 실제 화면에는 상관없어 그대로 두고 63초 기다려 찍었다
- 쉬게 하기 커밋은 `git add -A` 뒤 막을 것을 내린다(거부가 아니라 빼고 진행, 뺀 것은 결과 글에) — `.env` 링크 하나 때문에 진행 중 저장 전체를 못 하는 것보다 낫고, 조용히 빼지 않는다
- 스키마 잠금 일찍 풀기는 FOREMAN 저장소만 — 런슈즈(flyway)의 적용 기록은 다른 DB라 브리지가 볼 수 없다. config를 바꾸지 않으려고(다른 세션 요청만으로 `config/*.toml`을 바꾸지 않는다) 규칙은 코드에 두었다

## 합친 뒤 확인(브리지를 다시 띄운 세션)

1. `.venv/bin/python -m bridge.db.migrate --status` — 0028 적용됨(이 세션이 20:0x에 운영 DB에 적용, 파일은 그 뒤로 안 바꿈)
2. `GET /api/coder/todo` · `GET /api/schema-lock/board` 200, `config/scribe.toml`을 읽는다(없으면 기본 3 · 3)
3. [＋ 할 일] "코더에게"로 하나 적기 → 그 방 코더 "맡길 일 1" → 누르고 [계획으로] → 말하기 칸에 글이 채워짐 → [이대로 시작] → 받은 할 일 목록에 "코더가 하는 중"(시험 글이면 끝나고 [버리기])
4. worktree 세션 하나로 [쉬게 하기]: 커밋 "쉬게 하기: 진행 중 저장 — …"에 `.env*` · `.venv`가 없는지(`git show --stat`), 코더 "맡은 일 1 — 합치기 기다림" → [이어서]로 같은 대화가 붙는지 → [합치기]. 뒤에서 도는 일이 있을 때 [쉬게 하기]가 까닭과 함께 막히는지
5. 스키마 잠금: ① 잠금이 있으면 방 배너 줄 · 누르면 확인 창 · 풀림 ② 다른 세션이 막히면 배너 "멈춤 — … 막혔습니다" + 텔레그램 한 번 ③ 원본 폴더 세션이 마이그레이션을 적용 · 커밋하면 1분 안에 풀리고 브리지 로그 "스키마 잠금을 일찍 풀었다", 배너 "🔓 잠금을 풀었습니다"
6. ④ 브리지를 다시 띄운 뒤 `from bridge.db.migrate import connect`로 읽기 조회 → 잠금 안 잡힘(`GET /api/schema-lock`에 새 항목 없음)
7. `tools/screen.py --ui-scale 1.25` 세 테마 × 세 폭(실제 데이터) — 상주 코더 자리 0. 모든 방에 코더 세션이 있으면 상주 코더는 일하는 중이라 쉬는 자리가 안 보인다 — 쉬는 모습은 `--demo coder_resident`

## 남은 것

- 상주 코더가 일하는 중에는 캐릭터를 누르면 세션이, **머리 위 말풍선을 누르면 코더 목록**이 열린다(말풍선 클릭은 헤드리스로 눌러 보지 않았다)
- **지금 FOREMAN 스키마 잠금은 이 세션(233, worktree)이 0028 적용 때 쥐었다** — 합치면(`wt-merge`) 풀린다. 합치기 전에는 메인의 마이그레이션 · (옛 패턴이라) 읽기 조회가 막힌다
- [쉬게 하기] 뒤 이어 붙인 세션이 다른 cc id를 받는 경우는 시험하지 못했다(CC `--resume`은 같은 id로 잇는 것으로 알고 있다 — 실제로 확인 전)
- 상주 코더 · 임시 일꾼은 도형 테마(plain)에는 없다(`coder_home` 없음)
