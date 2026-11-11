# C 묶음 2물결 — 토큰 범위 · 프로젝트별 관리자 · 계획을 관리자에게 · 표 정리 후보 · 역할 권한 · 할 일 목록에서 바로 · 옮기기 한 흐름 (2026-11-11, worktree foreman-4, 구조 코더)

계획: [plan_structure_20261111.md](plan_structure_20261111.md) 「2물결 B · E」 · 「3물결 C2」 · 「넷」. 브랜치 `cc/foreman-4`, push 안 함.
새 기능은 모두 스위치 뒤에 **꺼짐**(역할 권한만 **관찰** — 막지 않고 기록만). 켜는 것은 사용자가.

| 커밋 | 일 | 스위치(커밋된 값) |
|---|---|---|
| `799bc74` | 1 프로젝트 토큰 범위 | `config/tokens.toml [project_tokens] enabled = false` |
| `dd21a88` | 2 프로젝트별 관리자 주소 · 부탁 | `config/managers.toml [managers] enabled = false` |
| `3898328` | 3 교장 계획 → 관리자에게 바로(0031) | `config/managers.toml [handover] enabled = false` |
| `3495060` | 4 합치기 카드 정리 후보 | 없음(카드 표시만 — 합치기 준비 스위치를 따름) |
| `aaee1fd` | 5 역할 권한 가드 | `config/roles.toml [roles] mode = "observe"` |
| `d111a6f` | 연결(맡은 파일 밖 — 관리자 허락 11-11) | — |
| `fbb57c0` | 6 할 일 목록에서 바로 시작 | 없음(화면 · API 더하기만) |
| `dc6e538` | 연결: `/api/todo` 라우터(맡은 파일 밖) | — |
| `0e71f00` | 7 옮기기 한 흐름 · 단추 말 | `config/handoff.toml [move] one_flow = false` |

## 1. 토큰 범위 (`799bc74`, 3에서 `/start use_saved` 한 줄 더함)

- 새 `bridge/scopetoken.py` · `bridge/api/auth.py`. 관리 토큰(`FOREMAN_API_TOKEN`)은 그대로 모든 API(`request.state.token_scope = None`)
- 프로젝트 토큰: `.env.project_tokens`(권한 600, `.env*`라 git 밖)에 `FOREMAN_TOKEN_<프로젝트>=값`. 만들기 `python -m bridge.scopetoken new <프로젝트>` — **값은 화면에 안 찍고 파일에만**(키 이름 · 파일만 출력). `list`는 키 이름만
- 닿는 곳: `/api/sessions/{sid}/…`(그 세션이 이 프로젝트 것일 때) · `POST /api/spawn`(cwd가 그 저장소 · worktree 안) · `GET /api/spawn/options` · `/api/foreman/plan · start · handover`(project가 같을 때, `use_saved`면 dispatch의 project) · `GET /api/foreman/state · notes · context · merge-order ?project=` · `/api/managers`. 나머지는 **403 + 사유**(「프로젝트 토큰(runshoes)은 이 API(GET /api/dashboard)에 닿지 않습니다 — 관리 토큰이 필요합니다」), 로그 warning(값 없이). WS · 터미널은 관리 토큰만
- 꺼져 있으면 프로젝트 토큰은 401(전과 같음). 설정이 깨지면 로그 error, 받지 않음. DB를 못 읽으면 프로젝트 토큰만 401(관리 토큰은 그대로)
- **한계**: 같은 유닉스 사용자로 도는 세션은 `.env.bridge`도 읽을 수 있다 — 벽이 아니라 **잘못 부르는 것을 막는 칸막이**다

## 2. 프로젝트별 관리자 (`dd21a88`)

- 새 `bridge/managers.py` · `bridge/api/managers.py`. 관리자 = 그 프로젝트 원본 폴더에서 살아 있는 역할 `manager`(A 「아홉」과 같은 판정)
- `GET /api/managers` — 프로젝트마다 관리자 세션 또는 「관리자가 없습니다」(설정이 꺼져 있어도 읽힘)
- `POST /api/managers/{project}/ask {text, from_project?, from_session?}` — 그 관리자 입력 칸에 「[관리자 부탁 — runshoes 관리자(세션 N 「…」) → foreman 관리자]」 + 본문 + 답하는 길(`/api/managers/runshoes/ask`)을 넣는다. 프로젝트 토큰으로 부르면 보낸 쪽은 토큰의 프로젝트로 고정(남의 이름으로 못 보냄)
- **조용한 고장 금지**: 관리자가 없거나 · 넣지 못하면 텔레그램 한 번 + 응답 `delivered:false, reason`. 보낸 것 · 실패는 `session_action mgr-ask`
- 세션 간 메시지 읽음 표시(`xmsg.label_of`)에 받는 쪽이 원본 폴더 관리자면 「runshoes 관리자 · …」
- 합치기 카드는 이미 그 저장소의 관리자(`mergeprep.manager_of(c.repo)`)에게 결과를 보낸다 — 프로젝트별로 이미 갈라져 있다. **`[merge_prep] projects`는 넓히지 않았다**(지금 `["foreman"]`). 다른 저장소에 관리자가 뜬 뒤 넓힐지는 사용자
- **다른 저장소에 관리자를 실제로 띄우지 않았다**(지시). 아래 「다른 저장소 관리자 — CLAUDE.md 초안」

## 3. 교장 계획이 관리자에게 바로 (`3898328`, 마이그레이션 0031)

- 계획 카드 [관리자에게 보내기](`foremanchat.js` `handButton`) — `[handover] enabled`일 때만 보인다. 그 프로젝트 관리자가 없으면 꺼진 단추 + 툴팁 「…에 관리자 세션이 없습니다. [이대로 시작]으로 직접 띄웁니다.」
- `POST /api/foreman/handover {dispatch_id, plan, inbox_ids?}`(`bridge/handover.py`): 계획 확인(`check`) → `dispatch.edited` 저장 · `handed_to` · `handed_at` → 관리자 입력 칸에 계획 요약(세션마다 역할 · 모델 · 따로 작업 · 맡을 파일) + 그대로 칠 시작 명령(`curl … -d '{"dispatch_id": N, "use_saved": true}' …/api/foreman/start`, 토큰은 `$T` 셸 변수)
- 관리자는 `/api/foreman/start {"dispatch_id": N, "use_saved": true}` — 교장 [시작]과 **같은 길**이라 `dispatch` · `dispatch_session` 기록이 그대로 이어 붙는다(교장 ④). 넘긴 할 일 번호도 계획에 실려 시작한 세션이 가져간다
- 못 넘기면 `handed_*`를 되돌리고 카드에 「넘기지 못했습니다(…) — [이대로 시작]으로 직접 띄울 수 있습니다」 + 텔레그램(Managers.ask)
- 넘긴 뒤 `wait_min`(15)분 안에 시작하지 않으면 텔레그램 한 번(`handed_alert_at` — 브리지를 다시 띄워도 한 번). 감시 자체가 실패하면 시간마다 한 번 텔레그램 + `GET /api/foreman/handover`의 `health`
- 계획을 다시 열면 넘긴 것은 「관리자(세션 N)에게 넘긴 계획입니다 — 관리자가 아직 띄우지 않았습니다」
- 0031: `dispatch.handed_to · handed_at · handed_alert_at`, `todo_inbox.edited_at` — **더하기만**. 0031 전 DB에서도 `get`은 넘김 표시만 빠지고 돈다

## 4. 합치기 카드 정리 후보 (`3495060`)

- `doc_candidates` 점수: 100 세션 log(이번에 바뀐 `log/*.md`)의 「README에서 뺄 줄」 절에 그 줄 이름(「…」)을 적음 · 50 표 줄 근거 칸이 링크한 log를 이번에 고침 · 40 표 줄의 「받은 할 일 #N」이 커밋 글 · 세션 log에도 나옴 · 10 바뀐 파일 · 1 드문 낱말. **낱말만으로는 셋 넘게 겹쳐야** 후보(전에는 둘). 후보마다 `why`(까닭) · `weak`(낱말만)
- docs 묶음에 `stale` — 바뀐 파일을 적었는데 이번에 그 문서를 고치지 않음(설계가 바뀌었으면 맞출 후보)
- 카드: 근거 있는 후보를 까닭과 함께 앞에, 낱말만 겹친 것은 「낱말만 겹친 후보 N개」로 접음, 문서에 「이번에 안 고침」. 관리자에게 가는 글에 근거 있는 후보(점수 40 이상) · 안 고친 문서를 바로 적고 「판단이 필요하면 사람에게 묻고, 혼자 지우지 않는다」

### 지난 카드로 잰 것(`git show`로 그때 README · 커밋 · log를 다시 맞댐, 읽기만)

| 카드 | 표 줄 | 옛 후보 | 새 후보 | 맞는 줄(실제로 뺀 줄) |
|---|---|---|---|---|
| 282(`6c7f9d2..51178c3`) | 50 | 14 | **7** | 「「권한 거부」 표시가 꺼지지 않는다」 옛 2순위(점수 5) → **1순위(105, 세션 기록 「README에서 뺄 줄」)** |
| 280(`fdc78f3..8af40be`, 시험 커밋) | 49 | 3 | **1** | 없음(시험 커밋 — 남은 1은 낱말만 · weak로 접힘) |

- 282의 남은 6개 중 5개는 낱말만(weak, 접힘), 1개는 바뀐 파일을 적은 「겹침 감지 헛경보」(옛 1순위 — 파일 이름이 걸림)
- 관리자 log 282: 「README 정리 후보 15개는 낱말 겹침 헛걸림이 많다」(카드는 14 + docs 1)

## 5. 역할 권한 (`aaee1fd` 본문 · `d111a6f` 연결)

- 새 `bridge/roleguard.py`, `config/roles.toml`. PreToolUse에서 pgrep_guard · reposcope와 같은 자리
  - `worktree-push`: worktree 세션의 `git push`
  - `bash-file-edit`: Bash로 저장소 파일 고치기 — `sed -i` · `perl -i` · `>`/`>>`(heredoc `cat >> f <<EOF` 포함) · `tee`. 명령 안의 `cd`를 따라가고, /tmp · 세션 스크래치 · git 저장소 밖(~/.claude)은 보지 않는다
  - `manager-code`: 관리자(원본 폴더)가 `config/*.toml` · `log/` · `README.md` 밖을 Edit · Write
  - `scribe-code`: 서기가 `bridge/` · `tests/` · `migrations/` · `tools/`를 Edit · Write
- 모드 `observe`(커밋된 값): 막지 않고 그 호출의 `approval_req` 이벤트 payload에 `role_rule` · `role_reason`. `enforce`: 거부 + 사유가 세션에 간다(「파일은 Edit · Write로 고칩니다 — Bash로 저장소 파일(log/a.md)을 고치려 했습니다(sed -i · 리디렉션 · heredoc · tee). … 임시 파일은 /tmp나 세션 스크래치에 씁니다」). `off`
- 역할은 세션마다 DB에서 60초 기억(`role_of`). 판정 · 역할 읽기 예외는 **막지 않고** 로그 error + 텔레그램 시간마다 한 번

### 지난 7일 FOREMAN 호출로 다시 돌림(운영 DB 읽기만 — Bash 6,822 · Edit 4,143 · Write 455)

- 첫 판 헛걸림: ① 명령 안의 `cd /tmp/…스크래치 && cat > x.sh`를 저장소 파일로 봄 ② 여러 줄 따옴표(커밋 글 · `python -c '…'`)를 줄마다 잘라 그 안의 `>`를 리디렉션으로 봄 ③ `sed -i … 2>/dev/null`의 `2`를 파일로 봄 ④ 한 줄에 heredoc 둘(`<<'EOF' || … <<'EOF2'`) ⑤ 해석기 안 `open(…,'w')` — 대부분 화면 시험용 JSON 만들기. → `cd` 따라가기 · 명령 전체를 한 번에 토큰(줄바꿈은 구분 기호) · 리디렉션을 인자에서 뺌 · heredoc 표지 여럿 · 해석기 안은 보지 않음(한계)
- 고친 뒤 **Bash로 파일 고치기 89건 — 모두 규칙이 막으려던 것**(`cat >> log/… <<EOF` · `cat >> tests/… <<EOF` · `sed -i` 소스 고치기 · `git show … > tests/fixtures/…`). 11-11 282 · 281 · 277 · 274 · 272의 heredoc 덧붙이기 포함
- 관리자 코드 37건: 29건은 11-09 관리자가 코드를 직접 짠 것(CLAUDE.md가 「이 기준으로는 worktree 몫이었다」고 적은 그것) · 11-11 관리자 docs 3건(구조 3단계 「관리자는 docs를 고치지 않는다」). **막기로 켜면 걸릴 정당한 것 1건**: 11-11 276이 합친 뒤 `tests/test_mergeprep.py`를 고친 것(CLAUDE.md 예외 1 「합친 뒤 깨진 것 몇 줄」) — enforce 뒤엔 사람이 잠시 `observe`로 돌리거나 코더에게 맡긴다. (지금은 지워진 worktree의 README 3건은 다시 돌릴 때만 생기는 착시 — 실시간 판정은 그 worktree 맨 위를 본다.) 11-09 CLAUDE.md 1건은 사용자 지시
- 서기 코드: 0건

## 6. 할 일 목록에서 바로 시작 (`fbb57c0` · `dc6e538`, 받은 할 일 #8)

- [＋ 할 일] 창의 「받은 할 일」 목록: 새로인 줄마다 고르기 체크 · [고치기](그 자리에서 글 고침, `PUT /api/todo/{id}` — 새로인 것만, `edited_at`) · [버리기](전과 같음)
- [고른 것으로 계획 받기 (N)] → 고른 글을 묶어(「겹치거나 이미 된 것은 까닭과 함께 빼고, 맡을 파일이 겹치지 않게 세션을 나눠도 됩니다」 + `#번호` · 본문) 교장 계획 창을 열고 **바로 계획을 받는다**(교장 ① 여러 세션). [이대로 시작] · [관리자에게 보내기]가 그 번호들을 가져간다
- 가져가기는 `inbox_take_pick` — 서기 정리 몫도 사람이 골랐으면 코더 몫으로 바꿔 가져간다(새로인 것만). 코더 「맡길 일」 하나짜리 길은 그대로
- 누가 맡을지: **교장**이 묶어 계획(사람이 고르고 「이거 해라」 하는 자리가 교장 계획 창이라). 서기의 「나중에 할 일 정리」는 그대로

## 7. 새 세션으로 옮기기 한 흐름 (`0e71f00`)

- `[move] one_flow = true`면 [새 세션으로 옮기기] 하나가 이어서 한다(`bridge/static/js/moveflow.js`):
  ① 잊은 것 찾기 → ② 문서 후보 목록(①의 사라짐 · 약해짐을 같이 넣음) → **③ 문서에 넣을 것 고르기(사람이 멈추는 곳은 여기 하나 — 항목마다 체크, 단추 [고른 N개를 문서에 쓰고 옮기기] / [문서에 넣지 않고 옮기기])** → ④ 문서에 쓰기(브리지가 커밋 확인) → ⑤ 요약 → ⑥ 새 세션(**요약 확인 창 없음**) → ⑦ 옛 세션 끝내기
- 시작할 때 확인 한 번(잊은 것 찾기 비용 — 말 20개당 약 0.4달러). 후보가 없으면 ③ · ④를 건너뛴다. ①이 실패하면 그 결과 없이 ②. 쓰기 확인이 실패하면 ③으로 돌아와 문제를 보인다
- 넘어간 글은 **새 세션 패널 「넘겨받은 글 — 세션 N 「…」에서」**에 보인다(한 시간 안이면 펼침, `controls.received`)
- 한 단계가 10분 넘게 그대로면 「멈춘 것 같습니다」 + [다시 시도] · [멈추기](조용히 서 있지 않게). 패널을 닫으면 멈췄다가 다시 열면 이어 간다(이 브라우저에 세션마다 기억 — 옛 흐름과 같은 `foremanFlow:` 열쇠, `v: 2`로 가름)
- 역할에 맞는 자리(관리자는 원본 폴더)는 옛 흐름과 같은 `POST /api/sessions/{sid}/spawn replace` 길이라 그대로
- 끝난 세션은 옛 흐름(문서에 쓸 세션이 없다)
- 단추 말: 「문서에 적기로 넘기기」 → **「잊은 것으로 문서 후보 묻기」**, 「목록 뽑기」 → **「문서 후보 묻기」**, 「승인한 것 쓰기」 → **「고른 것을 문서에 쓰기」**(옛 흐름 칸에도)

## 설계와 달랐던 점 · 판단 근거

- 역할 권한은 띄울 때 넘기는 `--allowedTools`/`--disallowedTools`가 아니라 **PreToolUse 훅**으로 했다 — 명령 글을 보고 가려야 하는 규칙(heredoc · `cd` 뒤 경로 · worktree 여부)이라 CC 도구 목록 문법으로는 못 쓴다. 지금 pgrep_guard · reposcope와 같은 자리라 끄기 · 관찰이 한 설정에 모인다
- 해석기 안 쓰기(`python -c "open(…,'w')"`)는 보지 않는다 — 다시 돌려 보니 걸린 것이 대부분 데이터 만들기였다. 소스를 해석기로 고치는 것은 막지 못한다(한계)
- 옮기기 한 흐름은 **화면이 단계를 잇는다**(서버 오케스트레이터 아님) — 옛 흐름과 같은 자리 · 같은 API를 써서 바뀐 길이 작다. 대신 패널을 닫으면 멈춘다(다시 열면 이어 감). 서버가 이어 받는 것은 다음 일 후보
- 3의 「관리자가 안 받으면」은 「넘긴 뒤 N분 안에 시작하지 않으면」으로 쟀다 — 관리자가 받았는지(읽었는지)는 입력 칸에 넣은 것까지만 확인된다
- 할 일 목록의 묶기는 서버가 아니라 화면(`planText`)이 한다 — 교장에게 가는 글이라 사람이 계획 창에서 보고 고칠 수 있다
- 맡은 파일 밖: `bridge/approvals.py` · `bridge/api/hooks.py` · `bridge/main.py` 연결 줄만(**관리자 허락 11-11**, 본문은 새 파일). `tests/test_stage2_db.py`에 DB 시험 하나를 끝에 더했다(새 함수 하나 — 다른 세션 몫 시험은 안 건드림). `terminal.js` · `opanel.js` · 터미널 쪽 · `test_terminal.py`는 손대지 않음

## 시험

- 새 시험: `tests/test_scopetoken.py` · `test_managers.py` · `test_handover.py` · `test_roleguard.py` · `test_moveflow.py`, `test_mergeprep.py`(근거 순위 1), `test_stage2_db.py::test_todo_edit_pick_and_handover_columns`(DB), node `handover` · `todopick` · `moveflow` · `mergeprep`(후보 1)
- 다른 pytest가 없는 것을 따로 본 뒤 혼자 한 번: **pytest 682 통과 · 1 건너뜀**, **node 118 통과**
- 화면(계획 카드 단추 · 할 일 목록 체크 · 옮기기 한 흐름)은 **미리보기로 보지 못했다**. 넘기기 · 한 흐름은 꺼져 있어 안 보이고, 할 일 목록 체크 · [고치기]는 바로 보인다(css는 맡은 파일 밖이라 안 건드림 — 줄 안에 체크박스가 그대로 붙는다). 합친 뒤 관리자가 [＋ 할 일] 창을 한 번 봐 주면 된다

## 되돌리는 법

| 일 | 끄기(설정) | revert | 브리지 |
|---|---|---|---|
| 1 토큰 | `tokens.toml enabled = false`(커밋 값) | `3898328`(auth · scopetoken 한 줄씩 겹침) 뒤 `799bc74` — **역순으로** | 다시 띄움 |
| 2 관리자 | `managers.toml [managers] enabled = false`(커밋 값 — 부탁만 503, 목록은 읽힘) | `dd21a88`(연결 `d111a6f`가 `managers_api`를 import — 함께) | 다시 띄움 |
| 3 넘기기 | `[handover] enabled = false`(커밋 값 — 단추 · API · 감시 없음, [이대로 시작] 그대로) | `3898328`. 0031은 더하기만이라 코드만 되돌려도 돈다. DB까지: 0031 머리 주석의 `ALTER … DROP` | 다시 띄움 |
| 4 후보 | 없음 | `3495060`(mergeprep · handoff.js 카드 몇 줄) | 다시 띄움 |
| 5 역할 | `roles.toml mode = "off"`(관찰도 끔) | 연결 `d111a6f` → 본문 `aaee1fd` | 다시 띄움 |
| 6 할 일 | 없음(더하기만) | `dc6e538` → `fbb57c0`(foreman.py 가져가기가 옛 `inbox_take_coder`로 돌아감) | 다시 띄움(파이썬), 화면은 새로고침 |
| 7 옮기기 | `handoff.toml [move] one_flow = false`(커밋 값 — 옛 흐름. 화면이 다음에 그릴 때 읽음, 브리지 필요 없음) | `0e71f00`(단추 말도 함께 돌아감) | 다시 띄움(handoff.py `received`) |

- 띄우기 · 끝내기 길이 묶일 수 있는 곳: 3을 켰는데 관리자가 안 띄움 → 15분 뒤 텔레그램, 계획 카드 [이대로 시작]은 그대로 된다. 7을 켰는데 단계가 멈춤 → 10분 뒤 패널에 「멈춘 것 같습니다」, [멈추기]는 어느 단계에서나(옛 [새 세션으로 옮기기]의 [더보기] 길도 그대로). 5를 enforce로 켰는데 일상 명령이 막힘 → `mode = "observe"` + 브리지 다시 띄우기
- 마이그레이션 0031 적용: 합친 뒤 관리자가 `.venv/bin/python -m bridge.db.migrate`(이 세션이 스키마 잠금을 쥐고 있다 — 합치면 풀림)

## README에서 뺄 줄(합칠 때, 관리자)

- 「프로젝트별 관리자」 — **토큰 범위 · 관리자 주소 · 부탁 · 계획 넘기기는 됨(꺼진 채)**. 남은 것: 켜기 · 다른 저장소에 관리자를 실제로 띄우기(그 저장소 CLAUDE.md 규칙 — 아래 초안)로 줄인다
- 「역할 규칙을 글이 아니라 권한으로 막기」 — **관찰로 돎**. 남은 것: 관찰 기록을 보고 enforce 켜기(사용자), 해석기 안 쓰기는 못 막음
- 「할 일 목록에서 바로 일을 시작」 — 뺀다(받은 할 일 #8)
- 「교장 ①~④」 줄 중 「계획을 사람이 복사해 관리자에게 옮김」 부분이 있으면 그 부분
- 「구조 3단계 — 역할 나누기」 — 관리자 docs · 코드 고치기는 이제 관찰로 보인다(enforce 전까지 남김)
- 「운영(합치기 뒤 절차) → 브리지」 — 그대로(이번 일 밖 — 합치기 카드 2단계 몫)
- 합치기 카드 정리 후보 헛걸림 줄이 있으면 — 282 1순위로 맞음, 낱말만은 접음

## 다른 저장소 관리자 — CLAUDE.md 초안(띄울 때 그 저장소에 넣을 줄, 지금은 넣지 않음)

```markdown
## 관리자(원본 폴더 세션) — FOREMAN 프로젝트별 관리자(11-11)

- 이 저장소의 관리자는 원본 폴더에서 도는 역할 manager 세션 하나다. 코드는 worktree 코더가 고치고, 관리자는 합치기 · 시험 · push · 기록을 한다
- FOREMAN API는 이 프로젝트 토큰으로만 부른다: `T=$(sed -n 's/^FOREMAN_TOKEN_<프로젝트 대문자>=//p' ~/AI_programming/foreman/.env.project_tokens)` — 값은 화면 · 로그 · 커밋에 내지 않는다. 이 토큰은 이 프로젝트 세션 · 방 API만 연다(다른 프로젝트는 403)
- 다른 프로젝트에 부탁할 일은 그 프로젝트 관리자에게: `POST http://127.0.0.1:8000/api/managers/<프로젝트>/ask {"text": "…"}`. 관리자가 없으면 사람에게 텔레그램으로 간다
- 교장이 넘긴 계획(입력 칸에 「[교장 계획 #N …]」)은 고칠 것이 없으면 적힌 명령(`/api/foreman/start` `use_saved`)으로 띄운다. 틀렸으면 띄우지 말고 사람에게 묻는다
- worktree 세션은 커밋만 하고 push하지 않는다. 파일은 Edit · Write로만(브리지가 관찰 · 막기로 본다 — config/roles.toml)
```

- 켤 때 차례(사용자): ① `python -m bridge.scopetoken new <프로젝트>` ② `tokens.toml enabled = true` · `managers.toml [managers] enabled = true` ③ 그 저장소 CLAUDE.md에 위 줄(그 저장소 세션에 부탁) ④ 관리자 세션을 원본 폴더에 띄움(역할 manager) ⑤ 필요하면 `roles.toml projects` · `handoff.toml [merge_prep] projects`에 그 프로젝트를 더함

## 합친 뒤 관리자가 할 일

1. merge-tree 확인 → 합치기 → `bridge.db.migrate`(0031) → pytest · node → push → 승인 대기 0 확인 뒤 브리지 다시 띄우기. 로그에 「역할 권한 observe: worktree-push, bash-file-edit, manager-code, scribe-code」가 떠야 하고, 「계획 넘기기 켬」은 없어야 한다(꺼짐)
2. 역할 관찰 확인: 하루 뒤 `SELECT JSON_UNQUOTE(JSON_EXTRACT(payload,'$.role_rule')) r, COUNT(*) FROM event WHERE type='approval_req' AND JSON_EXTRACT(payload,'$.role_rule') IS NOT NULL GROUP BY r` — 헛걸림을 보고 enforce는 사용자가
3. [＋ 할 일] 창에서 체크 · [고치기] · [고른 것으로 계획 받기]를 한 번(세 테마는 창 안이라 자리 영향 없음)
4. 켜 볼 때(사용자): `[move] one_flow = true`로 시험 세션 하나를 옮겨 ①~⑦과 새 세션 패널 「넘겨받은 글」 확인 · `[handover] enabled = true`로 시험 계획 하나를 관리자에게 넘겨 15분 알림까지 — 끝나면 시험 세션은 `hidden_reason='test'`

## 지킨 것 · 어긴 것

- 파일은 Edit · Write로만 고쳤다(스크래치의 재기 스크립트도 Write). push · 브리지 다시 띄우기 안 함. 스키마는 이 세션만(0031)
- 진행 글이 한 번 영어로 흘렀다(hook이 알려 바로잡음). 쓸모없는 셸 heredoc 한 번(`python3 - <<'EOF'` 빈 본문 — 파일은 안 건드림)
