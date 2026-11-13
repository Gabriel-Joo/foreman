# 11 — 세션마다 따로 작업(worktree) · 스키마 잠금 · 미리보기 브리지 (2026-11-05)

README 3.4("한 프로젝트에 캐릭터를 둘 이상 붙이면 같은 파일을 덮어쓴다 → git worktree")를 실제로 만든다.
계기: 11-05에 두 세션(포먼 작업 · 177)이 같은 폴더에서 같은 파일을 고쳐, 한쪽이 panel.css를 못 쓰고 office.html에 우회했다.

## 1. 만든 것(사용자 승인 11-05)

| 무엇 | 어떻게 |
|---|---|
| 언제 worktree인가 | 그 프로젝트에 살아 있는 세션이 있을 때 [+ 세션] · 포먼 디스패처 · [새로 띄우기]가 기본으로. 포먼 계획 카드의 "따로 작업(worktree)" 칸으로 끄고 켠다 |
| 자리 | `<repo>/.worktrees/<이름>`, 브랜치 `cc/<이름>`(이름은 tmux 이름에서 `cc-`를 뗀 것). 저장소 안이라 조립기가 같은 프로젝트로 잡고, 폴더 신뢰도 상위를 따른다(시험에서 신뢰 창 안 뜸) |
| git이 안 보게 | `.git/info/exclude`(로컬 전용, 저장소 파일 아님)에 `/.worktrees/` · `/.venv` · `/.env*` · `node_modules` |
| 링크 | 저장소 맨 위 `.venv` · `.env*`와 한 단계 아래 `*/node_modules` → 원본을 가리키는 링크 |
| CC 메모리 | `~/.claude/projects/<worktree 경로>/memory` → 원본 메모리 폴더 링크. 시험 세션이 원본 MEMORY.md 첫 줄을 그대로 말했다 |
| 합치기 | 세션을 끝낸 뒤 패널 [합치기] → 확인 창 → worktree에서 `rebase <base>` → 원본에서 `merge --ff-only` → worktree · 브랜치 지움. **push는 안 한다**(런슈즈는 push = 배포). 11-10부터 실제로는 관리자가 같은 API로 합친다 — 「6. 합치기」 |
| 충돌 | rebase가 멈추면 `rebase --abort`로 되돌리고 충돌 파일 목록을 보여 준다. worktree는 그대로 — 세션을 다시 띄워 풀고 커밋한 뒤 다시 합친다. 합치기 전에 충돌을 미리 보는 법은 「6. 합치기」 |
| 막는 것 | 세션이 살아 있으면 합치기 · 버리기 불가. 커밋 안 된 변경이 있으면 합치기 불가(끝내기 확인 창에서 미리 경고). 버리기는 이름을 그대로 적어야 한다 |
| 스키마 잠금 | `config/worktree.toml` — 프로젝트별 마이그레이션 경로 · 명령. 처음 쓴 세션이 잠금을 갖고, 다른 세션의 같은 시도는 PreToolUse에서 **거부**(승인 모드가 observe인 런슈즈도). 풀림: worktree 세션은 합치기 · 버리기 때, 원본 폴더 세션은 끝날 때, 사람이 `DELETE /api/schema-lock/<프로젝트>`(11-09부터 화면 배너에서도 — 「5.」) |
| 잠겨 있을 때(세션의 방침) | 잠금을 가진 앞 세션이 살아 있으면 스키마 변경 없이 할 수 있는 일부터 하고, 스키마가 필요한 단계를 시작할 때 잠금을 다시 본다. 잠금을 가진 세션이 이미 끝났으면(잠금 파일에 이름이 남아 있어도) 가져가 써도 된다 |

API: `POST /api/spawn`의 `worktree`(null · true · false), `POST /api/sessions/{id}/worktree` `{action: merge|discard, confirm}`, `GET /api/schema-lock`.

## 2. 미리보기 브리지

**11-05 사용자 결정**
- A(화면만 worktree, 데이터는 지금 브리지)로 한다
- 버튼을 누를 때만 띄운다
- 런슈즈 vite는 FOREMAN을 써 본 뒤에 한다

→ 만들었다(`bridge/preview.py` · `bridge/previews.py`).

설계 문서와 다른 점
- 상태는 DB 표 대신 `~/.foreman/previews.json`에 둔다(스키마 잠금과 같은 방식)
- 미리보기 서버 코드는 원본 저장소 것을 쓰고, 화면 파일만 worktree에서 읽는다

아래는 승인 전 설계 그대로다.

worktree에서 고친 화면은 지금 브리지(원본 폴더의 `bridge/static`)에 안 보인다. 합치기 전에 그 worktree의 화면을 보는 자리가 필요하다.

### 2.1 무엇을 띄우나 — 프로젝트마다 명령 하나

`config/worktree.toml`에 프로젝트별 미리보기 명령을 둔다. `{port}` · `{wt}`를 채워 tmux 창에서 띄운다.

```toml
[preview.foreman]
cmd = ".venv/bin/python -m bridge.preview --port {port} --static bridge/static --upstream http://127.0.0.1:8000"
[preview.runshoes]          # 나중에 — 런슈즈 화면(vite). 백엔드는 로컬 Spring을 그대로 쓴다
cmd = "npm --prefix frontend run dev -- --port {port} --strictPort"
```

**FOREMAN은 "화면만 worktree, 데이터는 지금 브리지" 방식(A)을 제안한다** — `bridge/preview.py`(작은 FastAPI):
- `/`, `/classic`, `/static/*`는 worktree의 파일로 준다
- `/api/*` · `/ws`는 지금 브리지(8000)로 그대로 넘긴다(토큰 헤더 포함). 그래서 실시간 데이터가 그대로 보이고,
  DB에 두 번 적재하거나 알림 · 승인 · 웹훅이 두 벌 도는 일이 없다

| | A. 화면만(제안) | B. worktree 브리지 통째(읽기 전용 모드) |
|---|---|---|
| 보이는 것 | worktree의 HTML · JS · CSS · 테마 | 위 + worktree의 백엔드(API) 변경 |
| 데이터 | 지금 브리지 그대로(실시간) | 같은 DB를 읽기만 — 적재 · 알림 · 승인 · 웹훅 · hook 끄는 `FOREMAN_PREVIEW=1` 모드를 만들어야 한다. 실시간 이벤트 없음 |
| 위험 | 거의 없다 | 끄기를 빠뜨리면 두 벌 적재 · 이중 알림. 스키마가 다른 worktree면 깨진다 |
| 만드는 양 | 파일 하나(~100줄) | 브리지 곳곳에 모드 분기 |

화면 작업이 대부분이라 A부터 만들고, 백엔드 미리보기가 필요해지면 B를 따로 정한다.

### 2.2 포트 · 프로세스

- 포트: 8200~8299에서 빈 것(소켓을 열어 본다). 바인드는 지금 브리지와 같은 `127.0.0.1`. 8100은 이미 다른 것이 쓴다
- tmux 세션 `fm-pv-<이름>`에서 돈다 → 브리지를 다시 띄워도 미리보기는 남는다. 포트 · tmux 이름은 DB(새 표 `preview`: 세션 · worktree · 포트 · 시작 시각 · 상태)
- 브리지가 뜰 때 표와 tmux를 맞춰 본다: 표에만 있으면 닫힘, worktree가 없어진 미리보기는 끈다

### 2.3 화면에서

- 패널 "따로 작업" 칸에 **[미리보기 열기]**. 누르면 없으면 띄우고(포트 자동) 새 탭으로 연다. 돌고 있으면 "미리보기 :8203 · [닫기]"
- 토큰: 포트가 다르면 출처(origin)가 달라 브라우저 저장소의 토큰이 없다 → 여는 주소에 `#t=<토큰>`(조각 — 서버로 안 간다)을 붙이고,
  미리보기 페이지가 저장한 뒤 주소에서 바로 지운다(`history.replaceState`). 미리보기 머리말에 **"미리보기 · cc/<이름>"** 띠를 둘러 원본 화면과 헷갈리지 않게
- 미리보기 화면에서도 버튼(입력 · 승인 · 세션 조작)은 지금 브리지로 가서 **진짜로 동작한다**. 띠에 그 사실을 적는다

### 2.4 정리

- 세션을 **끝내면** 미리보기도 끈다(사용자 요청)
- 끝난 뒤에도 worktree가 남아 있으면 [미리보기 열기]로 다시 띄울 수 있다 — 합치기 전에 보고 싶을 때
- 합치기 · 버리기 때 끈다. 브리지가 뜰 때 주인 없는 미리보기를 끈다

### 2.5 정할 것

1. A(화면만, 데이터는 지금 브리지)로 시작해도 되나
2. 미리보기는 버튼을 눌렀을 때만 띄우나(제안), 아니면 worktree 세션을 띄울 때 바로 띄우나
3. 런슈즈 미리보기(vite)도 이번에 같이 하나, FOREMAN만 먼저 하나(제안: FOREMAN 먼저)

## 3. 같이 도는 세션의 범위

- **UI(화면)를 맡은 세션이 다른 세션과 같이 돌 때는 테마 `roles` · 역할 색 · 패널의 캐릭터 · 역할 표시(`render.js` `sessionMeta`)를 건드리지 않는다.** 역할 · 색은 역할 작업 쪽이 갖는다(사용자 합의 — "테마 `roles` · 역할 색 · 패널의 캐릭터 · 역할 표시(`render.js` `sessionMeta`)는 건드리지 마라")

## 4. 쉬게 하기 · 이어서 (11-09, 세션 233) [log:coder_resident_20261109.md]

worktree 세션을 **끝내지 않고 잠깐 내려놓는** 길. 끝내면 합치거나 버리는 것밖에 없어서, 하다 만 일이 "합치기 기다림"으로 남을 곳이 필요했다.

**[쉬게 하기]** — 패널 「세션」 맨 앞, worktree 세션만. `POST /api/sessions/{sid}/rest`
1. 작업 중이거나 뒤에서 도는 일(백그라운드 Bash · Monitor · 서브에이전트 — 대시보드와 같은 기준)이 있으면 **먼저 막고 까닭을 띄운다.** 커밋도 하지 않는다. 그대로 끝내면 CC가 끝내기 확인 창에서 멈춘다 [log:old_session_exit_bg_20261109.md]
2. 없으면 `git add -A` → 넣으면 안 되는 것을 내린다: `.env*`(견본 빼고) · `.venv` · `node_modules` · worktree 밖을 가리키는 링크. 거부가 아니라 **빼고 진행하고, 뺀 것은 결과 글에 적는다**(링크 하나 때문에 진행 중 저장 전체를 못 하는 것보다 낫고, 조용히 빼지 않는다)
3. 커밋 "쉬게 하기: 진행 중 저장 — <제목>". 커밋이 실패하면(pre-commit 등) 거부하고 올린 것을 내린다
4. `/exit`. 안 내려가면 tmux 화면에서 CC 끝내기 확인 창을 찾아 "CC 끝내기 확인 창에 걸렸습니다"로 알린다
- `session_action` `rest`에 남긴다(실패는 ok=0). worktree · 브랜치는 그대로

**[이어서]** — 「따로 작업」, 끝난 worktree 세션. `POST /api/sessions/{sid}/rest-resume`
- 새 tmux 창에서 `claude --resume <cc> [--model]`. 대화 기록 파일이 없거나 45초 안에 안 붙으면 까닭을 띄운다. 이미 살아 있는 세션이면 거부한다
- `rest-resume` · `spawn` 기록을 남긴다(끝낼 때 tmux 정리가 알아보게). 다른 cc id로 이어지면 새 행에 이름 · 역할 · 캐릭터를 물려준다

**「따로 작업」 칸** — "쉬는 중 — 합치기 기다림 · …부터 · N일째"(하루 넘으면 N일째). [합치기] · [버리기]는 그대로. 코더 말풍선과 「코더」 패널의 맡길 일에도 센다(`docs/10_office_design.md` 「코더 상주 · 임시 일꾼 · 맡길 일」)

한계: [쉬게 하기] 뒤 이어 붙인 세션이 다른 cc id를 받는 경우는 시험하지 못했다(CC `--resume`은 같은 id로 잇는 것으로 알고 있다 — 실제 확인 전).

## 5. 스키마 잠금 화면 (11-09, 세션 233) [log:coder_resident_20261109.md]

「1.」의 잠금은 거부만 하고 화면이 없었다. 11-09 원본 폴더 세션이 쥔 잠금 때문에 worktree 코더가 막혔는데, **설계는 "사람이 푼다"인데 누를 곳이 없었고, 막힌 것도 그 세션이 메시지를 보내서야 알았다**(조용한 고장). 그래서 넷을 더했다.

| | 무엇 |
|---|---|
| ① 배너 + [풀기] | 방 배너 줄 "🔒 DB 구조 잠금 — 세션 N(원본 폴더\|worktree x)이 HH:MM부터 쥐고 있습니다(무엇) — 눌러서 풉니다". 누르면 확인 창 → `DELETE /api/schema-lock/{project}`. 화면용 `GET /api/schema-lock/board`가 세션 번호를 붙여 준다. 원본 폴더 세션이 쥔 것도 보인다 |
| ② 막힘 알림 | 다른 세션이 잠금에 막히면 잠금 상태에 `blocked`를 남기고 배너가 "🔒 멈춤 — 세션 M이 스키마 잠금에 막혔습니다. 쥔 세션 N(…부터)"로 바뀐다. 텔레그램은 막힌 세션마다 한 번(`notification.kind = schlock`) |
| ③ 일찍 풀기 | 원본 폴더 세션이 쥔 FOREMAN 잠금은 1분마다 본다 — 그 작업 트리 `migrations/NNNN_*.sql`이 모두 `schema_migrations`에 있고 `git status -- migrations/`가 비면 푼다(`SchemaLock.try_release_early`). 로그 "스키마 잠금을 일찍 풀었다 — …", 배너가 10분 "🔓 잠금을 풀었습니다 — 적용 · 커밋 끝 — …". worktree 세션이 쥔 것은 합치기 전까지 그대로(그 스키마가 main에 없다). **FOREMAN 저장소만** — 런슈즈(flyway)의 적용 기록은 다른 DB라 브리지가 모른다 |
| ④ 잠그는 명령만 | `config/worktree.toml`의 `commands`를 마이그레이션을 **돌리는** 명령으로 좁혔다 |

**④ 명령 패턴** (11-09 사용자 확인 "config 고침")
- FOREMAN: `-m bridge.db.migrate` · `python …bridge/db/migrate.py` — 둘 다 `--status`는 뺀다
- 런슈즈: flyway 실행 작업만(`flywayMigrate` · `flyway migrate` 등)
- 까닭: 전에는 `bridge\.db\.migrate`가 `from bridge.db.migrate import connect`(DB에 붙으려고 가져오기만)에도 맞아 관리자가 17:16에 **읽기만 하고 잠금을 쥐었다.** 20:1x에는 반대로 그 읽기 조회가 코더의 잠금에 거부됐다. 런슈즈 `\bflyway\w*\b`도 `SELECT … FROM flyway_schema_history`(읽기)를 잡았다
- 처음엔 "0027을 적용할 때 잡힌 잠금"으로 기록했다가 확인하고 바로잡았다 [log:dispatch_flow_decision_20261109.md]

## 6. 합치기 — 누가 어떻게 (11-10, 코드 확인) [log:merge_237_242_20261110.md]

합치기의 몸(`bridge/worktree.py` `merge`)은 「1.」 그대로다 — worktree에서 `rebase`, 원본에서 `merge --ff-only`, worktree · 브랜치 지움, push 없음. 달라진 것은 **누가 부르는가**다.

- **관리자(원본 폴더 세션)가 `POST /api/sessions/{sid}/worktree` `{"action":"merge"}`로 합친다.** 사용자가 패널 [합치기]를 누르던 때와 같은 API다
- **사용자가 패널로 하는 길도 남아 있다**(`bridge/static/js/handoff.js`): 끝난 세션의 「따로 작업」 [합치기], 살아 있는 세션의 「세션」 [끝내고 합치기](`end: true`)
- **합치기 전에 충돌을 따로 본다.** 예: `git merge-tree --write-tree <base> cc/<이름>`의 결과를 읽는다. 충돌이 없다고 나온 것을 **본 뒤에** 합치기 API를 부른다. 확인과 합치기를 한 명령에 묶지 않는다
- **충돌이면 `end: true`로 부르지 않는다.** `end: true`는 세션을 먼저 끝낸 뒤 합치므로(`HandoffManager.worktree_act`) 충돌이 나면 풀 세션이 이미 없다. 화면 확인 창도 "충돌이 나면 되돌리고 멈춥니다(세션은 이미 끝난 뒤입니다)"라고 적는다
- **살아 있는 세션의 충돌은 그 세션이 푼다**(main을 가져와 rebase하고 커밋한 뒤 다시 합친다). 세션이 이미 끝났으면 관리자가 푼다 — 예: README 「나중에 할 일」 표처럼 줄만 합치면 되는 충돌을 `git rebase main` 뒤 두 쪽을 다 남기고 `--continue`(CLAUDE.md 「작업 규칙」 관리자 기준 2)
- 합친 뒤 시험 · push · 브리지 다시 띄우기 · 화면 점검은 관리자 몫이다. 커밋 안 된 변경이 있으면 합칠 수 없다 — 세션이 끝내기 전에 커밋을 마친다
- **세션을 살려 둔 채 합칠 때**(API가 「세션이 아직 살아 있습니다」로 거절, 11-11): `merge-tree` 확인을 먼저 따로 한 뒤 원본 폴더에서 손으로 합친다. 브랜치가 main 끝 위에 있으면 `git merge --ff-only cc/<이름>`, main이 그 사이 앞섰으면 `git merge --no-ff cc/<이름>`(11-11 `52ba341` — 디자이너 273). 세션 · worktree는 그대로 남는다

### 6-1. 합치기 준비 — 일을 마친 worktree 세션에 승인 카드 (11-11, `bridge/mergeprep.py`)

- **켜져 있다**(`config/handoff.toml [merge_prep] enabled = true`, `projects = ["foreman", "ronanlab-infra"]`(11-12 — 런슈즈는 관리자 310이 섰지만 아직 넣지 않음), `stage = 1`, 11-11 사용자). 브리지가 LLM 없이 `merge-tree`를 돌려 카드를 만든다. 카드는 「합치기까지」다 — 시험 · push · 브리지 다시 띄우기 · 화면 점검은 여전히 관리자 몫(2단계는 사용자가 1단계를 써 본 뒤 정한다, 아직 없음)
- **언제 만드나**: 세션이 일을 마쳤을 때 — 턴 끝 신호에서 바로(`check_one(via="turn_end")`, 묻는 말이 있어도 만든다) + `every_s`(60초)마다 훑기가 줍는다. 합칠 커밋이 있고(ahead > 0) 커밋 안 한 변경이 0이어야 한다
- **카드**: 브랜치 · 커밋 · 바뀐 파일 · 충돌 여부 · ff 가능 / main이 앞섬 · README 정리 후보 · docs. 상태 `ready` · `merging` · `merged` · `conflict_sent` · `conflict_manager` · `failed`
- **사람이 승인**하면 충돌이 없을 때 살아 있는 세션도 끝내고 합친다(main이 앞섰으면 rebase). 충돌이면 세션을 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보낸다(끝난 세션이면 관리자 세션에). 결과와 「정리 후보」는 관리자 세션에 남는다. API: `GET /api/merge-prep`, `POST /api/sessions/{sid}/merge-prep {"action": "merge" | "skip" | "refresh"}`(`bridge/api/handoff.py`). `skip`은 그 브랜치 끝 커밋이 바뀌기 전까지 카드를 치운다
- **승인자 — 프로젝트별**(11-12 사용자, `config/handoff.toml [merge_prep.per_project.<프로젝트>] approver`): FOREMAN · 인프라는 `approver = "manager"` — 관리자가 `POST /api/sessions/{sid}/merge-prep {"action": "merge", "by": "manager"}`로 합친다. 관리자가 승인하는 카드는 사람 화면(카드 · 「합치기 기다림」 말풍선 · 승인 막대)에 띄우지 않는다. `human_paths`(FOREMAN: `docs/style_guide.md` · `docs/operations.md`, 인프라: 없음)와 **늘 사람에게 올리는 것**(`[merge_prep.human_always]` — `config/*.toml` · `CLAUDE.md` · `.claude/*` · 마이그레이션 · `*values*.yaml` · 자원 크기 키 줄 · 이력을 다시 쓰는 말 · 파일 지움 · 서브모듈)을 건드린 카드만 사람에게 간다. 카드를 받는 관리자는 저장소마다 갈린다(FOREMAN 카드 → FOREMAN 관리자, `ronanlab-infra` 카드 → 인프라 관리자 299) [log:merge_approver_20261112.md]
- **커밋을 하나로 뭉친다**(`squash = true`, FOREMAN · 인프라 11-12부터): 원래 커밋의 제목 · 시각은 합친 커밋 본문 「원래 커밋(오래된 차례)」에 남는다. 합친 커밋 제목은 첫 커밋 제목을 그대로 쓴다(고칠지는 README 「나중에 할 일」)
- **조용한 고장 금지**: 준비 실패 · 훑기가 `stuck_min`(10분) 넘게 안 끝남 · 합치기 실패 · 관리자에게 못 알림은 텔레그램 한 번 + 카드 목록에 사유. 카드가 새로 생길 때도 텔레그램 한 번(`notify_ready` — 11-11 시험에서 실제로 나갔는지는 확인하지 못했다)
- **정리 후보**(11-11 2물결): README 「나중에 할 일」 줄에 점수 — 100 세션 log의 「README에서 뺄 줄」에 그 줄 이름 · 50 근거 칸이 링크한 log를 이번에 고침 · 40 「받은 할 일 #N」이 커밋 글 · log에도 나옴 · 10 바뀐 파일 · 1 드문 낱말(낱말만으로는 셋 넘게 겹쳐야 후보). 낱말만 겹친 것(`weak`)은 카드에서 접는다. docs 줄은 문서마다 묶고, 바뀐 파일을 적었는데 이번에 그 문서를 고치지 않았으면 `stale`(「이번에 안 고침」) — 이 문서를 고치게 된 계기다. 고르고 지우는 것은 사람 승인 뒤 관리자(`doc_candidates`)
- **카드가 보이는 곳**(11-13 바뀜 [log:merge_wait_to_manager_20261113.md]): 세션 패널 「세션」 탭 + 승인 막대 「🔀 합치기 대기 N」(사람 승인 대기 카드를 모두 센다)는 그대로. 머리 위 말풍선은 **사람 승인이 필요한 카드를 관리자 머리 위 「사용자 답 기다림」으로 올린다** — 브리지가 `MergePrep._esc_sync()`로 그 저장소 원본 폴더의 살아 있는 관리자 세션에 `escalate(kind="question")`을 기계적으로 만든다(관리자가 따로 부르지 않는다). 그 말풍선을 누르면 카드 세션 패널의 「세션」 탭이 열린다. 카드가 합쳐짐 · 미뤄짐 · 없어짐(버림 · 다시 일함 · 새 커밋으로 새 카드)이면 브리지가 물음을 내린다(`esc-off`). **관리자가 없거나 · 못 찾거나 · escalate가 거부되면** 카드에 `esc_error`를 달고 작업 세션 머리 위 「합치기 기다림」 말풍선으로 남긴다(툴팁에 까닭). 관리자가 인계로 바뀌면 옛 물음을 내리고 새 관리자에게 다시 올린다. 관리자 승인 카드는 이 물음을 만들지 않는다. 말풍선 겹침 순서 · 문구는 `docs/10_office_design.md` 「머리 위 표시」
- **카드는 DB에 남는다**(11-13 321, `merge_card` 0032 [log:mergeprep_db_20261113.md]): 세션 하나에 한 줄, 카드 전부를 `card` JSON 한 칸에 둔다(`esc_id` · `esc_mgr` · `esc_error`도 거기). 브리지를 다시 띄워도 `MergePrep.restore()`가 첫 훑기 전에 카드 · 정리 후보 · `made_at`을 되살린다 — 합친 뒤 브리지를 다시 띄우면 카드와 정리 후보가 사라지던 조용한 손실을 막았다. 끝난 카드(합침 · 실패 · 충돌 넘김)는 `keep_h`(6시간), **정리 후보가 남은 합친 카드는 `keep_docs_h`(72시간)** 남긴다(기본값, `config/handoff.toml`에는 칸이 없다). 합치는 중(`merging`)에 브리지가 내려간 카드는 되살릴 때 `failed`(「결과를 모릅니다」)로 바꾼다. 같은 커밋이면 main이 앞서 카드를 다시 재도 `made_at`을 잇는다. DB 쓰기 · 읽기가 실패해도 카드는 메모리로 돌고, 처음 실패할 때 텔레그램 한 번 + 카드 목록 `store`/`health.error`에 사유가 뜬다
- **정리 후보를 다 골랐으면** `POST /api/sessions/{sid}/merge-prep {"action": "docs_done", "by": "manager"}` — 합친(`merged`) 카드만 치운다(DB에서도). 대기 · 충돌 카드는 거부. 안 부르면 72시간 뒤 치운다. 합친 결과 글(관리자 입력 칸)에 이 부르는 법이 한 줄 들어간다
- **관리자는 늘 원본 폴더**(11-11 아홉): `spawn_new`가 관리자를 worktree로 띄우려 하면 거절하고(`bridge/handoff.py` `will_worktree(role="manager")` False), 원본 폴더에 관리자가 이미 살아 있으면 둘째를 거절한다(`manager_conflict`). 관리자 인계가 worktree로 떠서 push · 브리지 다시 띄우기를 못 했던 일의 뒤처리다 [log:handoff_misplaced_admin_20261111.md]
- 끄기: `enabled = false` + 브리지 다시 띄우기 — 카드만 사라지고 패널 [합치기] · API 합치기는 그대로

**11-10 실수** (237 합치기): `merge-tree`와 합치기 API를 한 명령에 묶어, 충돌로 "충돌 없음"이 안 찍혔는데도 합치기를 불렀고, `end: true`로 불러 세션 237이 먼저 끝났다(tmux도 닫힘). 다음 242는 살아 있는 채 충돌을 그 세션이 풀게 했다. 이 일로 위 두 줄을 정했다.

**`pgrep -f` 같은 함정**: 시험이 끝났는지 같은 확인을 합치기와 같은 명령에 묶으면 확인용 글자가 자기 셸에 걸린다 → `docs/operations.md` 「4. 작업 규칙의 상세」.

## 7. 다른 저장소는 읽기만 (11-09, `bridge/reposcope.py`) [log:repo_scope_readonly_20261109.md]

FOREMAN 세션은 다른 저장소(runshoes · petmint-rag-chatbot · ronanlab-infra · k8s-cluster)를 **읽기만** 한다. 훅으로 막는다(1단계). 11-09 하루만 봐도 다른 저장소에 쓰는 일이 있었다(Jenkinsfile · values.yaml · 런슈즈 settings.json · CLAUDE.md, 펫퍼민트 fetch).

- 설정: `config/approval.toml [repo_scope]` — `read_only_elsewhere = ["foreman"]`(이 프로젝트의 세션만 대상), 읽기 명령 목록
- 자리: PreToolUse에서 스키마 잠금 바로 뒤. **승인 모드와 상관없이** 거부한다(규칙 이름 `다른저장소-쓰기`)
- 막는 것
  - Edit · Write · MultiEdit · NotebookEdit: 대상이 자기 저장소(+ `.worktrees/*`) 밖의 git 저장소 안일 때
  - git: `-C` · `cd`(줄을 넘어 이어짐) · `--git-dir` · `--work-tree` · `GIT_DIR=`로 다른 저장소를 가리키며 읽기가 아닌 것. `fetch` · `pull`도 막는다(그 저장소 `.git`에 쓴다)
- 막지 않는 것: `/tmp` · 스크래치 아래(복제본), git 저장소가 아닌 곳(`~/.claude` · 메모리), heredoc 본문(커밋 메시지 안 글자)
- 저장소 경로는 DB `project.repo_path`. 프로젝트가 아닌 `ronanlab-infra` · `k8s-cluster`도 git 저장소라 막힌다
- 거부 사유(화면 글): "다른 저장소 쓰기 막힘 — 이 세션은 다른 저장소(runshoes)를 읽기만 합니다(git push). 고칠 것은 그 저장소의 세션에 맡기거나(세션 간 메시지) 사용자에게 요청하세요. 상태만 볼 때는 git ls-remote, 손볼 시험은 /tmp · 스크래치 복제본에서 합니다."
- 상태 보기는 `git ls-remote` · 스크래치 복제본으로
- **관리자도 다른 저장소에 쓸 수 없다**(11-11): 런슈즈 저장소에는 `git cherry`도 막힌다(관리자에게 열린 것은 원본 폴더에서 docs/만 앞선 커밋의 push — `[repo_scope.manager_push]`). 다른 저장소에 남은 worktree는 FOREMAN 버리기 API(`POST /api/sessions/{sid}/worktree` `{"action":"discard","confirm":"<worktree 이름>"}`)로 지운다(11-11 런슈즈 `.worktrees/runshoes-2`)

**시도했던 것** — 지난 7일 FOREMAN 세션 호출(Bash 4,505 · Edit 3,093 · Write 290)에 다시 돌렸다. 첫 판 24건 중 헛거부 4(`git reflog show` · `git remote get-url origin`(`$(…)` 안) · `git apply --check` · `git fetch --dry-run`) → 명령마다 "읽기로 치는 인자"로 고친 뒤 20건, 모두 막으려던 것(다른 저장소 Edit · Write 13, commit · add · pull · fetch 7).

**한계**: Bash의 그 밖 쓰기(`sed -i` · `>` · `cp`)는 보지 않는다(샌드박스 단계). `cd $X`처럼 변수 경로 cd는 따라가지 않고, `git -C $X` 쓰기는 판정할 수 없어 막는다. 이제 그 저장소 일은 그 저장소 세션에 맡기므로 왕복이 하나 는다. 2단계(docs 뒤처짐 신호) · 3단계(역할 나누기)는 README 「나중에 할 일」.
