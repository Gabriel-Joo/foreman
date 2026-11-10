# 인프라(ronanlab-infra)를 FOREMAN 프로젝트로 등록 (2026-11-10, worktree `cc/foreman`)

관리자 세션 244 지시(사용자 11-10). 세션 265(인프라, 클러스터 작업 중)는 건드리지 않았다.

## 한 일

### 1. `project` 표 — 기존 셋과 같은 길(마이그레이션 시드)
- 기존 셋은 `migrations/0002_seed.sql`(project + 포먼)과 `0017`(코더)로 들어갔다. 시작 때 채우는 길 · 설정으로 넣는 길은 없다
- **`migrations/0029_seed_ronanlab_infra.sql`** — 행만 더한다(DDL 없음, 스키마 변경 아님): project(`ronanlab-infra`, `/home/kopo17/ronanlab-infra`, GitHub 원격, namespace NULL) + 포먼(foreman, DORMANT) + 코더(coder, 부모 = 포먼). 되돌리기 SQL은 파일 머리에
- `migrations/`를 써서 **이 worktree가 FOREMAN 스키마 잠금을 쥐었다** — 합치기에서 풀린다
- 시험 DB(`tests/test_stage2_db.py` env)가 0001~0029를 실제로 적용한 뒤 돈다 — 통과

### 2. 박힌 곳 목록(`petmint-rag-chatbot` · `runshoes`를 다시 훑음)
| 곳 | 한 것 |
|---|---|
| `bridge/terminal.py` `TERM_PROJECTS` · 머리 주석 | 더함(맨 뒤) |
| `bridge/api/dashboard.py` `PROJECT_ORDER` · `LABEL` | 더함 — 화면 이름 「인프라」 |
| `bridge/overlap.py` `_PROJ_KO` · `_STOP` | 「인프라」, 멈춤말에 `ronanlab`(경로 조각). `infra`는 겹침 신호일 수 있어 넣지 않음 |
| `bridge/static/js/office.js` `KNOWN` | 더함(맨 뒤 — 기존 방 자리 그대로) + `NO_SHIP` |
| `bridge/static/js/terminal.js` `PROJ` | 더함(창 고르기 · cwd 조각 대조가 이걸 본다) |
| `tools/demo_from_db.py` `LABEL` | 더함 |
| `config/approval.toml` · `notify.toml` · `notion.toml` · `pipeline.toml` | 아래 3 |
| `config/worktree.toml` | 안 함 — 인프라에 FOREMAN이 아는 DB 스키마 · 미리보기가 없다 |
| `config/portfolio.toml` · `deploy/cicd/argocd-notifications-foreman.yaml` | 안 함 — 포트폴리오 · ArgoCD 앱 아님 |
| `deploy/shell/foreman-term-view` | 그대로 — 프로젝트 모양 `^[A-Za-z0-9_.-]{1,40}$`에 맞는다 |

### 3. 설정 값
- `approval.toml` `[projects.ronanlab-infra] mode = "observe"` — 주석: 묶음 1 동안 승인 카드를 풀었다 · 관리자가 `[defaults]`를 임시 observe로 둠 · 합친 뒤 defaults를 enforce로, 묶음 1이 끝나면 이 줄도 enforce로(사용자 확인 뒤). 이 worktree의 `[defaults]`는 `enforce` 그대로다(관리자의 임시 변경은 원본 폴더에만 있음)
- `notify.toml` `[projects.ronanlab-infra] prefix = "[인프라]"` — 접두어가 있어야 텔레그램을 보낸다. 지금 떠돌이(미분류)인 265는 안 가고 있었다
- `notion.toml` `[ronanlab-infra]` 칸만 — `root = ""`, `docs = "off"`, github · ref(origin/main). root가 비면 `bridge/main.py`가 게시기를 만들지 않고 건너뛴다(확인). root · docs_page · portfolio_page는 **사용자에게 물을 것**(notion.toml 구조 그림의 「인프라」 페이지 — 지금은 사람이 쓴 문서 — 를 쓸지, 새 프로젝트 페이지를 만들지)
- `pipeline.toml` — 넣지 않음, 끝에 이유 주석. `pipeline.start`는 pipeline.toml의 프로젝트만 보므로 인프라는 출하 단계 · 빌드 알림 감시(watch)에 걸리지 않는다

### 4. 방(화면) — 출하장 비우기
- 같은 모눈(`themes/_shared/grid.json`) 그대로. 방 자리 · 칸은 다른 현장과 같다(세 테마 방 자리 비교 "같음")
- `office.js` `NO_SHIP = new Set(['ronanlab-infra'])` → 방에 `noShip`. 그런 방은
  - 배송 담당(courier) 없음, 단계 칸 테두리 · 단계 가구(`infra_decor`) · 바닥 화살표 ①②③ 없음(바닥 칸 색만 남김)
  - 이름표는 「출하장 없음」 하나(단계 이름표 셋 없음). 호버 "출하 라인 없음 — 빌드해 내보내는 앱이 아니라 빌드 → 이미지 → 배포 줄이 없습니다. …"
  - 도형 테마(`drawRoom`)도 단계 상자를 그리지 않음
- 머리줄 방 단추 · [전체] 카드(「인프라 · 세션 없음」) · [⌂] 현황판 칸이 저절로 넷째로 뜬다(현황판은 현장 수로 판을 나눈다)
- **현황판이 다섯 칸(현장 넷 + 라운지)이 되자 1024 넓게에서 「FOREMAN」이 낱말 가운데서 끊겼다**(cardAudit 1, 세 테마). 띄어쓰기 없는 이름만 글씨를 8px까지 더 줄이게 한 줄 고쳐 0건 — 다만 그 크기에서 「FOREMAN」은 작다 → 남은 것

### 5. 터미널
- 인프라 방에서 열면 `[ronanlab-infra]` 창이 `project.repo_path`(=/home/kopo17/ronanlab-infra) 폴더 · `FOREMAN_PROJECT=ronanlab-infra`로 만들어진다(`window_for` — 코드 변경 없이 `TERM_PROJECTS`만)
- 시험 `test_infra_window_opens_in_its_repo` — **자기 tmux 소켓**(`own_sock`, /tmp 짧은 경로). 탭 그룹 세션 둘: 한 탭이 인프라를 골라도 다른 탭(foreman)은 그대로, 창 폴더 = 저장소, `P=ronanlab-infra`. 시험 앞뒤로 라이브 tmux 세션 목록 차이 없음 확인

## 세션 265는 어떻게 옮겨지나 — 저절로 안 옮겨진다
- 세션 → 프로젝트: 처음 볼 때(`assembler._session`, 행 없음) `cwd`를 `project.repo_path`와 대 맞는 프로젝트의 코더 캐릭터에 붙인다. **이미 행이 있으면 그 `character_id`를 그대로 읽는다** — 265는 '미분류'(project_id NULL)에 붙어 있으므로 0029를 적용하고 브리지를 다시 띄워도 라운지에 남는다
- 옮기는 길 둘(관리자가 고른다, 둘 다 0029 적용 뒤):
  1. SQL 한 줄(되돌리기 쉬움 — 옛 값은 '미분류' 캐릭터 id) → 그 뒤 브리지 다시 띄우기(어셈블러가 세션 상태를 메모리에 쥐고 있다)
     ```sql
     UPDATE character_session SET character_id = (SELECT ch.id FROM `character` ch JOIN project p ON p.id = ch.project_id
       WHERE p.name = 'ronanlab-infra' AND ch.name = '코더') WHERE id = 265;
     ```
  2. 브리지를 다시 띄운 뒤 역할 바꾸기 API(`POST /api/sessions/265/role`) — `_character_for`가 cwd로 인프라 코더를 고른다. 단 같은 역할이면 아무것도 안 하므로 다른 역할 → coder 두 번(session_action에 두 줄 남음). 1이 깔끔하다
- 브리지를 다시 띄운 뒤 **새로 뜨는** 인프라 세션은 저절로 인프라 코더에 붙는다

## 합친 뒤 관리자가 할 일
1. `git merge-tree`로 충돌 확인 → 합치기(스키마 잠금이 풀린다)
2. `.venv/bin/python -m bridge.db.migrate` — 0029 적용(`--status`로 먼저 확인)
3. 세션 265 옮기기(위 1번 SQL) — 승인 대기가 없는지 본 뒤
4. 브리지 다시 띄우기(approval · notify · notion · pipeline.toml · 파이썬 바뀜)
5. `approval.toml` `[defaults] mode`를 enforce로 되돌리기(원본 폴더의 임시 변경) — 인프라 줄은 observe 그대로
6. 확인: 머리줄 「인프라」 단추 · 방에 265가 코더 자리 · 출하장 「출하장 없음」 · [전체] 카드 · [⌂] 현황판 넷째 칸 · 인프라 방에서 터미널 → `[ronanlab-infra]` 창 · 폴더 · 265 턴 끝 텔레그램이 `[인프라]`로 오는지 · `/api/publish` 등 Notion 쪽 오류 없이 인프라 게시기만 빠지는지(브리지 로그)

## 시험
- pytest **561 통과** · 1 건너뜀(JS 시험 포함, 0029까지 적용한 시험 DB, 인프라 터미널 시험 포함)
- `tools/screen.py`(미리보기 `python -m bridge.preview --port 8277 --upstream :8000` + `--no-term`) — 세 테마 × 1920 · 1366 · 1024 × 좁게 · 넓게 × 인프라 방 · [전체] · [⌂] · foreman · runshoes: **문제 0건**, 세 테마 방 자리 같음. audit(고정 안 됨) 1 · 11 · 14는 문제 수에 들지 않는 기존 값
  - 미리보기는 라이브 DB(0029 미적용)를 본다 — 인프라 방은 `KNOWN`으로 서고 세션은 비어 있다. 265가 들어간 모습은 합친 뒤 :8000에서 본다

## 남은 것
- **Notion 자동 게시 켜기** — 인프라 저장소에 `docs/`가 생긴 뒤(인프라 세션 묶음 1 문서 단계). root 페이지를 사용자에게 묻고 `docs = "auto"`
- **[⌂] 현황판 다섯 칸 자리**(디자이너 몫) — 1024 넓게에서 칸이 약 60px라 「FOREMAN」이 8px까지 줄어든다. 현장이 더 늘면 줄 바꿈 · 줄임으로도 못 버틴다(판 두 줄 · 라운지 칸 빼기 등)
- 인프라 묶음 1이 끝나면 `approval.toml` 인프라 줄을 enforce로(사용자 확인)
- 인프라 세션도 `repo_scope.read_only_elsewhere`(다른 저장소 읽기만)에 넣을지 — 지금은 foreman만. 인프라 일이 다른 저장소를 고칠 수 있는지 사용자에게
