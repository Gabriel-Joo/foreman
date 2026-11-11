# 1물결 A — 세션 생명주기: 아홉 · 하나 · 넷 (2026-11-11, worktree foreman-2, 코더 277)

계획: `log/plan_structure_20261111.md` 「1물결 — A」. 커밋 `5b46912`(아홉) · `1f1cc50`(하나 · 넷). 브랜치 `cc/foreman-2`, push 안 함.

## 한 일

### 아홉 — 관리자는 늘 원본 폴더 (`5b46912`)
- `HandoffManager.spawn_new`: `role == "manager"`이면 tmux · worktree를 만들기 **전에** 판단한다
  - worktree를 강제로 켰거나(`worktree=True`) worktree 폴더를 골랐으면 거절 — 「관리자는 원본 폴더에서만 띄웁니다」
  - 원본 폴더에 역할 관리자가 살아 있으면 거절 + 사유(세션 번호). 옮기기의 옛 세션(`exclude_cc`)은 세지 않는다 → 관리자 옮기기는 원본 폴더로 간다
  - 아니면 `worktree=False`
- `will_worktree(cwd, exclude_cc, role)` — 관리자는 False. 코더 · 서기 · 디자이너는 그대로(살아 있는 세션이 있으면 worktree)
- 새 `_live_in_base` · `manager_conflict` — 원본 폴더(.worktrees/ 밖)에서 살아 있는 세션의 마지막 행 역할을 본다. worktree에 잘못 뜬 관리자는 원본 자리를 막지 않는다
- `injection()` 미리보기에 `role` · `manager_block`. 패널(`handoff.js` `wtNext`)이 「관리자라 원본 폴더에서 뜹니다」 또는 거절 사유를 보이고, 띄우기 단추(이 글을 넣고 시작 · 요약 없이 시작 · 이대로 보내기 · 덧붙여서 보내기)를 끈다. 넣을 때(`target_cwd` 있음)는 보지 않는다 — 그때는 새 관리자가 이미 살아 있다
- 교장 경로(`foreman.py` → `spawn_new(worktree=bool(...))`)도 같은 함수라 함께 막힌다. `newsession.js`(C1 몫)는 고치지 않았다 — 거절 사유가 서버 응답으로 간다

### 하나 — 합치기 준비 · 승인 카드 (`1f1cc50`, 1단계)
- 새 `bridge/mergeprep.py` `MergePrep` — `every_s`(60초)마다 훑는다. 브리지가 기계로 하고 LLM은 쓰지 않는다
  - 후보: worktree 폴더(`cwd LIKE %/.worktrees/%`)마다 마지막 세션, 숨기지 않은 것, worktree가 있는 것. `projects`로 좁힐 수 있다
  - 일을 마침: 살아 있으면 — busy 아님 · 열린 턴 없음 · 응답이 하나 이상 · 마지막 응답이 묻는 말 아님 · 권한 거부 없음(대시보드 `human_needs`와 같은 판정) · 뒤에서 도는 일 없음(`_running_work`). 아니면 「세션이 끝났습니다」. 멈춰 둔(T) 세션은 보지 않는다
  - 그리고 `ahead > 0` · 커밋 안 한 변경 0
  - 카드: 브랜치 · 커밋 · 바뀐 파일 · 충돌(`git merge-tree --write-tree --name-only`) · ff 가능 / main에 새 커밋 N(rebase) · 정리 후보(넷). 열쇠는 (브랜치 끝 커밋, main 끝 커밋, 살아 있음) — 그대로면 다시 만들지 않는다
- [합치기] 승인(`POST /api/sessions/{sid}/merge-prep {"action":"merge"}`): 다시 잰다
  - 카드 뒤에 커밋이 생겼거나 커밋 안 한 변경이 생겼으면 거절하고 아무것도 하지 않는다
  - 충돌: 살아 있으면 끝내지 않고 그 세션에 「`git rebase main`으로 가져와 풀고 커밋한 뒤 보고, push 하지 마라」 → `conflict_sent`. 끝났으면 관리자 세션에 → `conflict_manager`
  - 깨끗함: `worktree_act("merge", end=살아 있음)` — 기존 [끝내고 합치기]와 같은 길(main이 앞섰으면 `worktree.merge`가 rebase). **살아 있고 main이 앞섰으면 끝내기 전에 임시 worktree(분리된 HEAD)에서 rebase가 되는지 먼저 본다** — 아래 「설계와 달랐던 점」
  - 결과는 관리자 세션(원본 폴더의 역할 manager, `deliver`)에: 「합쳤다 — 1단계라 시험 · push · 브리지 다시 띄우기 · 화면 점검은 관리자」 + 정리 후보 수
- [나중에](`skip`): `session_action 'mprep-skip'`(detail = 브랜치 끝 커밋) — 그 커밋이 바뀌기 전까지 다시 안 띄운다
- 2단계 자리: `after_merge` — `stage = 2`여도 지금은 「2단계는 아직 없다」를 카드 · 로그에 남기기만 한다
- 기록: `session_action` `mprep-card` · `mprep-merge` · `mprep-conf` · `mprep-skip`(칼럼이 12자라 짧게). 카드는 브리지 메모리 — 다시 띄우면 다음 훑기에서 다시 만든다(마이그레이션 없음)
- 화면: 세션 패널 맨 위 「합치기 승인」(`handoff.js` `mpSection`, 내보내서 node 시험). 상태 · 충돌 파일 · 커밋/파일 접기 · 정리 후보 접기 · [합치기] · [나중에]
- API: `GET /api/merge-prep`(모든 카드 + health), `POST /api/sessions/{sid}/merge-prep` `{merge|skip|refresh}`, `GET /api/sessions/{sid}/handoff`에 `merge_prep`
- 스위치: `config/handoff.toml [merge_prep] enabled = false`로 커밋. 꺼져 있으면 감시가 돌지 않고, API는 503(목록은 `enabled:false`), 패널 카드도 없다

### 넷 — 정리 후보 (`1f1cc50`)
- `doc_candidates` — main 쪽 `README.md`(git show)의 「나중에 할 일」 제목 아래 표 줄과 `docs/*.md` 줄을 바뀐 파일 · 커밋 글과 맞댄다. 고르기 · 지우기는 하지 않는다
  - README 줄: 바뀐 파일의 경로 · 이름 · 줄기(4자 이상)가 **낱말 경계로** 있거나, 커밋 글의 **드문** 낱말(표 줄 10분의 1 넘게 · 적어도 3줄 넘게 나오는 것은 뺌)이 둘 넘게 겹치면. 파일이 걸린 줄이 앞
  - docs: 바뀐 파일 경로 · 이름을 적은 줄을 문서마다 묶어(줄 번호 8개까지 + 수)

### 조용한 고장 — 무엇이 막히면 어떻게 아는가
| 막힘 | 알림 |
|---|---|
| 한 세션 준비 실패(git 오류 등) | 카드 `failed` + 사유, 텔레그램 한 번(세션 · 시간마다) |
| 한 번 훑기가 `stuck_min`(10분) 넘게 안 끝남 · 훑기 자체 예외 | `health.ok=false` + 사유(패널 카드 자리에 빨간 줄, `GET /api/merge-prep`), 텔레그램 한 번(시간마다) |
| 승인 뒤 합치기 실패 · 거부 | 카드 `failed` + 사유, 텔레그램, 세션이 끝났으면 관리자에게 |
| 충돌 풀기를 세션에 못 보냄 | 카드 사유 + 텔레그램 |
| 관리자 세션이 없음 · 못 보냄 | 텔레그램으로 같은 글, 카드에 「관리자 세션에는 알리지 못했습니다」 |
| 설정이 깨져 못 켬 | 브리지 로그 error + 텔레그램(main.py) |
| 카드가 새로 생김 | 텔레그램 한 번(`notify_ready`, 세션 · 브랜치 끝 커밋마다) |

## 조사 결과

- 운영 DB에 **읽기만으로** SQL · 판정을 맞대 봄(스크래치 스크립트, `_act` · deliver · 알림 안 부름):
  - `manager_conflict(원본)` → 「관리자(세션 276)가 이미 살아 있습니다」, `manager_of` → 276의 cc
  - 후보 worktree 세션 6: 279 디자이너(마침, 커밋 0 → 카드 없음) · 278 · 277(일하는 중) · **260 펫퍼민트 서기(마침, 커밋 8, 충돌 없음 → 카드)** · **259 런슈즈 코더(마침, 커밋 4 → 카드)** · 250(커밋 0)
  - 켜면 런슈즈 · 펫퍼민트에도 카드 · 텔레그램이 간다 → `projects` 설정을 더했다(처음엔 `["foreman"]` 권함)
- 처음 맞대기는 헛걸림이 많았다 — `handoff` 줄기가 `stage11_handoff_result`에, 「관리자 · 폴더 · 원본」 같은 흔한 낱말 둘로 걸림 → 낱말 경계 · 드문 낱말로 고친 뒤 이 브랜치(커밋 1개) 기준 README 후보 5 → 1(「원본 폴더」 줄은 남음 — 후보라 둠)

## 설계와 달랐던 점 · 판단 근거

- **「보고 옴」을 조건으로 쓰지 않았다** — 대시보드의 `report`는 사람이 패널을 열면 읽음으로 사라진다. 읽은 뒤에도 일을 마친 것은 같으므로 「묻지 않고 응답을 마치고 쉼」으로 봤다(같은 `human_needs`의 asks · denied는 씀)
- **살아 있는 세션 + main이 앞섬이면 끝내기 전에 rebase를 따로 본다** — merge-tree는 세 갈래 합치기라, 브랜치 안에서 바꿨다가 되돌린 줄이 있으면 「충돌 없음」인데 커밋을 하나씩 얹는 rebase는 충돌한다(시험 `test_live_rebase_check_before_ending`). `end:true`로 끝낸 뒤 알면 풀 세션이 없다(docs/11 「6.」 11-10 실수). 임시 worktree는 `/tmp/foreman-mprep-*`에 만들고 바로 지운다
- 카드 · 「나중에」 외 상태는 DB가 아니라 메모리 — A는 마이그레이션을 하지 않는다(지시). 기록은 `session_action`에 남는다
- 「시험 결과」는 카드에 넣지 않았다(계획 A의 카드 항목에 있으나 1단계는 시험을 하지 않음 — 2단계 몫)
- 텔레그램 `kind`는 `merge`(칼럼 8자)
- 하나 · 넷은 같은 파일(`mergeprep.py`)이라 커밋 하나로 묶었다

## 시험

- 새 시험: `tests/test_manager_seat.py`(3), `tests/test_mergeprep.py`(12 — 임시 git 저장소: 끝난 세션 깨끗 → 합침 → 관리자 알림, 살아 있는 충돌 → 세션에 보냄 · 끝내지 않음, 끝난 충돌 → 관리자, rebase 사전 확인, 카드 뒤 새 커밋 거절, 다시 일하면 카드 치움, 준비 실패 카드, API 꺼짐 · 켜짐), `tests/js/mergeprep.test.mjs`(3)
- `pytest -m "not db"` 567 통과 · 1 오류(`test_pipeline` DB 교착 — 그때 다른 세션이 `test_stage2_db.py`를 돌림, 아래 「DB 시험」), `node --test tests/js/` 94 통과
- DB 시험: 아래 덧붙임

## 되돌리는 법

| 단계 | 끄기(설정) | revert | 브리지 |
|---|---|---|---|
| 하나 · 넷 | `config/handoff.toml [merge_prep] enabled = false`(커밋된 기본값) — 감시 · 카드 · API가 멈춘다. 기존 [합치기] · [끝내고 합치기] · 합치기 API는 그대로 | `git revert 1f1cc50` (main.py 몇 줄 · api/handoff.py · handoff.js 카드 · `handoff.py`의 `mergeprep` 속성 한 줄 · 새 파일) | 값을 바꾸거나 revert하면 다시 띄운다(승인 대기 0 확인 뒤) |
| 아홉 | 스위치 없음(띄우기 판단만 바뀜 — 관리자 아닌 역할은 그대로) | `git revert 5b46912` | 다시 띄운다 |

- 띄우기 · 끝내기 길이 묶일 수 있는 곳: 아홉이 관리자 띄우기를 거절하는 경우뿐(원본에 관리자가 살아 있음). 급하면 그 관리자를 끝내거나 [새 세션으로 옮기기](옛 세션 제외)로 띄운다. 그래도 안 되면 revert
- 하나는 켜기 전까지 끝내기 · 합치기 길을 바꾸지 않는다(새 API · 새 감시만 더함)

## 합친 뒤 관리자가 할 일

1. merge-tree 확인 → 합치기 → pytest · node → push → 승인 대기 0 확인 뒤 브리지 다시 띄우기(꺼진 채로 뜨는지 — 로그에 「합치기 준비 켬」이 없어야 함)
2. 켜 보기: `enabled = true`, `projects = ["foreman"]`로 바꾸고 브리지 다시 띄움 → 시험 세션 하나를 worktree로 띄워 파일 하나 커밋 · 보고하게 함 → 1분 안에 카드 · 텔레그램 → [합치기] → 관리자 세션에 「합쳤다」가 오는지. 충돌 길도 하나(main에서 같은 줄을 고쳐 둠). 끝나면 시험 세션은 `hidden_reason='test'`로 숨김
3. 써 본 뒤 `projects`를 넓힐지 · 2단계를 할지는 사용자
4. README에서 뺄 줄(합칠 때): 「운영 → 브리지」 줄의 합치기 준비 부분(1단계만 — 시험 · push 자동은 남음), 「합치기를 순서대로」는 C1 몫과 겹치니 확인
5. 남은 것: 카드는 세션 패널에만 뜬다 — 여러 카드를 한 곳에서 보는 자리(사무실 화면 · 승인 막대)는 맡은 파일 밖이라 만들지 않았다. `GET /api/merge-prep`이 그 자리의 데이터다
