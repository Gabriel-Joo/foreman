# 작업 참고 — 환경 · 구조 · 돌리기 (CLAUDE.md에서 옮긴 상세)

> 상태: 2026-11-06 서기 `trim`으로 CLAUDE.md에서 옮겼다(`log/trim_20261106.md`). 꼭 지킬 금지 · 결정은 CLAUDE.md에 남아 있고, 여기는 그 상세와 참고다. 내용은 옮기기만 했고 다시 확인하지 않았다.

## 1. 관련 경로 · 환경

| 무엇 | 위치 |
|---|---|
| 런슈즈(쇼핑몰, Spring + React) | `~/AI_programming/runshoes` — 인프라는 `docs/INFRA.md` |
| 펫퍼민트(RAG 챗봇) | `~/AI_programming/petmint-rag-chatbot` — 호스트 서비스는 `deploy/host/`(milvus compose, search-service 유닛) |
| 클러스터 매니페스트 | `~/ronanlab-infra`(GitHub private), ArgoCD가 본다 |
| k8s VM(m-k8s · w1~w3, libvirt) | `~/k8s-cluster` — kubectl은 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'` |
| Python | 브리지는 저장소의 전용 `.venv`(시스템 python 3.14, 1단계 결정). `~/llm_env`는 LLM · 펫퍼민트 작업용 |
| 접속 구조 | 집 PC → 교육 PC → 서버 PC(VNC `DISPLAY=:2`). 서버 PC가 GPU 호스트이고 클러스터 VM도 여기서 돈다 |
| CC 전역 설정 | `~/.claude/settings.json`에 **model 기본값을 두지 않는다**(원래 상태, 사용자 — "손으로 여는 claude만 opus로 뜨는데, 그건 기본값 없이 두는 게 낫다"). 세션 모델은 FOREMAN이 띄울 때 정한다. `/model`이 전역 기본값을 다시 써 넣으면 지운다 |

서버의 현재 포트 · 컨테이너 · 유닛 상태와 작업 시 주의는 `log/infra_20261102_host-changes.md`.

## 2. 이 저장소의 구조

| 무엇 | 위치 |
|---|---|
| 브리지(FastAPI, 수집 · API · WS · 알림 · 승인 · 입력 주입 · 인계) | `bridge/` — 시작 `bridge/main.py`, 트랜스크립트 적재 `assembler.py` · `transcript/`, 입력 `inject.py`, 인계 · 세션 조작 `handoff.py`, 파이프라인 `pipeline.py`, 승인 `approval*.py`, 알림 `notify.py` |
| 화면 | `bridge/static/` — `/` 픽셀 화면(`office.html` · `js/office.js` · `js/opanel.js`), `/classic` 카드 목록(`dashboard.html` · `js/render.js`), 공통 CSS `css/panel.css`, 테마 `themes/<이름>/theme.json`(magic · office · site · plain) |
| DB(MySQL, 호스트 도커 `127.0.0.1:3308`) | 마이그레이션 `migrations/NNNN_*.sql` — `.venv/bin/python -m bridge.db.migrate` |
| 설정 | `config/approval.toml` · `notify.toml` · `pipeline.toml` · `worktree.toml` · `models.toml`(세션 모델 · 역할 기본값) · `scribe.toml`(서기 "정리할까요?" 기준, `docs/12_scribe.md` 「11-4.」), 비밀은 `.env.bridge` · `.env.telegram`(커밋 안 함) |
| 설계 · 브리프 / 결과 | `README.md`, `docs/NN_*.md` / `log/*.md` |
| 시험 | `.venv/bin/python -m pytest -q`(DB `foreman_test`), `node --test tests/js/` — 두 세션이 동시에 돌리지 않는다(같은 `foreman_test` 표를 서로 지워 11-09 31건 실패 → 혼자 돌려 통과 [log:repo_scope_readonly_20261109.md]). `tests/test_app_db.py`는 운영 DB에 대고 앱을 띄우므로 설정 `losscheck_recover`를 끈다 — 켜 두면 앱이 뜰 때 도는 압축 손실 점검을 모두 failed로 바꾼다(11-09 시험만 돌렸는데 운영 점검 #2가 실패로 적혔다) [log:cross_paste_20261109.md] |

## 3. 돌리기 · 확인

- 브리지는 systemd 사용자 유닛 `foreman-bridge`가 돌린다(11-06, `deploy/systemd/foreman-bridge.service`, linger 켬 — 부팅 때 자동 기동). 상태 · 로그: `systemctl --user status foreman-bridge`, `journalctl --user -u foreman-bridge -n 100`. 다시 띄우기(승인 대기 — `/api/dashboard`의 approvals pending — 가 없는지 본 뒤): `systemctl --user restart foreman-bridge`(10초 남짓 끊김)
  - CC 세션 셸에서는 `systemctl --user`가 `Process org.freedesktop.systemd1 exited with status 1`로 실패한다(세션 환경의 DBUS가 VNC 쪽 버스를 가리키고 `XDG_RUNTIME_DIR`가 비어 있다, 11-08 — 11-09에도 세 세션이 같은 일을 겪었다, 샌드박스 밖에서도). 앞에 `XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`를 붙인다(`journalctl --user`도 같다) [log:screen_argocd_read_20261109.md] [log:handoff_replace_main_20261109.md]
    ```
    XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart foreman-bridge
    ```
  - **브리지를 다시 띄워야 하는 것은 파이썬(브리지) 변경뿐**이다. js · css · html은 재시작 없이 바로 나간다(`cache-control: no-cache`). 열린 탭은 화면 코드 지문(`bridge/uiver.py` — static 아래 파일 이름 · 크기 · 수정 시각, WS `hello` · `/api/dashboard`의 `ui`)이 바뀌면 맨 위 노란 띠 "화면 코드가 바뀌었습니다 — [새로 고침]"이 뜬다(저절로 고치지 않는다 — 입력 칸 글이 날아간다) [log:pixel_bigger_question_card_20261109.md] [log:screen_mismatch_waits_20261109.md]
- 브리지 주소는 `127.0.0.1:8000`이다(API 시험 때)
- CC 세션 tmux: 서기 세션은 아직 tmux 세션 `foreman-bridge` 안에 있다(11-06 이름 변경 보류 — `cc-foreman`이 이미 있어서. 정하면 바꾼다). 런슈즈 `cc-runshoes`(11-05 이전, 11-06 정전 뒤 사라짐). 펫퍼민트는 아직 tmux 밖(pts/7) — 입력 주입 불가
- 화면 자리 점검 도구 `.venv/bin/python tools/screen.py`
  - 헤드리스 크로미움으로 세 테마 × 세 크기의 `layoutAudit()` · `propAudit()` + PNG. 문제가 있으면 종료 코드 1
  - **화면마다 `nameAudit()` · `cardAudit()` · `tipAudit()`도 기본으로 센다**(11-09 — 전엔 `--eval`로 따로 불러야 봐서 빠뜨리면 안 보였다). 줄 끝에 `layoutAudit N · nameAudit N · cardAudit N · tipAudit 문제/호버 수 · propAudit N`, 모두 문제 수에 든다 [log:screen_argocd_read_20261109.md] [log:tips_and_credit_signal_20261109.md]
    - `cardAudit` — [전체] 카드 겹침 · 그림 덮음 · 화면 밖 · 줄 어긋남 · 잘림, [⌂] 현황판 이름 겹침 · 칸 밖 · 낱말 가운데 끊김
    - `tipAudit` — 툴팁 넘침 · 낱말 끊김 · 화면보다 큼(`docs/style_guide.md` 「4-1. 화면 글」)
    - `labelAudit`(화면마다, 11-10) — 지금 그린 그대로: 이름표(구역 · 출하 라인 · 캐릭터 이름 · 말풍선) ↔ 사람 몸, 이름표끼리, 구역 · 출하 라인 이름표 ↔ 가구(그림의 불투명 범위). `layoutAudit`은 좌석 자리 기준이라 이 겹침을 못 봤다. `layoutAudit()`를 콘솔에서 부르면 둘 다 나온다 [log:foreman_term_office_three_20261110.md]
    - `termAudit`(테마 × 크기마다, 11-10) — 패널 입력 칸이 패널 · 창 밖으로 넘치나, 터미널과 겹치나, 패널 · 터미널 겹침, xterm 글자 칸이 터미널보다 넓은가. 닫힌 채 한 번, 터미널을 연 채 한 번(`<…>_term.png`). `--no-term`이면 닫힌 채만 [log:designer_screen_six_20261110.md]
    - `gridAudit`(테마 × 크기마다, 11-10 모눈) — 두 방이 같은 칸 · 방도 복도도 아닌 칸 · 끊긴 복도 · 복도에 안 닿는 방(grid.json, `js/grid.js gridProblems`), 복도에서 걸어서 못 가는 자리, 방 밖으로 나간 가구 · 자리, 이름표가 방 왼쪽 위 칸이 아니거나 가구 · 자리 몸에 걸림(배율 1과 지금 배율). 끝에 **테마 셋의 방 자리가 같은지** 견준다 [log:designer_grid_20261110.md]
  - 패널 너비는 좁게 · 넓게 두 값뿐이라(11-10) 크기마다 둘 다 본다(`--panel narrow,wide` 기본, 넓게는 크기 이름 끝 `w`)
  - 옵션: `--views hq,map,<현장>` · `--session <id>` · `--base`(미리보기 82xx) · `--eval` · `--ui-scale <배율>`(사용자가 보는 글씨 배율로 찍는다 — 범위 0.8~1.1 · 5씩, 처음 값 0.9(11-10). 양 끝 예 0.8 · 1.1) [log:pixel_bigger_question_card_20261109.md]
  - 통과는 "고른 화면에서 문제 0"일 뿐이다 — 사용자가 말한 화면을 [⌂] · [전체] 같은 탭 글자로 확인하고 그 화면을 고른다 [log:screen_mismatch_waits_20261109.md]
  - 자동 재배치 계획은 `--eval "window.office.layoutPlan()"`
- API 토큰은 `.env.bridge`의 `FOREMAN_API_TOKEN` — 셸 변수로만 쓴다

## 4. 작업 규칙의 상세

- **멈춰 둔 CC 프로세스**(11-02 기준 4개): pts/8 — PID 1301867 · 3872105, pts/7 — 1895956 · 1906162. 조사 경위는 `log/01_kickoff_result.md`
- **한국어 진행 글**: 11-05에 최종 답은 한국어인데 중간 진행 글이 영어로 흘러 패널 대화에 그대로 보였다. 컨텍스트가 길어져도 · 요약 뒤에 이어 갈 때도 · 도구 결과(로그 · 코드 · 영문 메시지)가 영어여도 마찬가지다
- **sudo**: 비대화형 sudo가 안 된다. 11-02에 "쳤다"는 명령이 실제로는 실행되지 않은 적이 있어, 쳤다고 하면 journal 등으로 확인한다
- **CI/CD**(11-03 결정, README 3.12): FOREMAN은 한 덩어리로 두고 배포는 systemd, 시험은 GitHub Actions. 둘 다 아직 만들지 않았다(옮기기 전 CLAUDE.md 문구 그대로 — 11-06에 다시 확인하지 않았다)
- **시험 세션 숨김**: 0018 `hidden_at` — `hidden_reason='test'`로 숨기면 카드 · 토큰 집계 · 디스패처 상황 묶음에서 빠지고 행은 남는다
- **worktree 링크**: `.venv` · `.env*` · `node_modules` · CC 메모리는 원본을 가리키는 링크다(그대로 쓰면 된다). 단 `.venv`가 원본 폴더의 `bridge`를 가리켜서, worktree에서 pytest 밖 스크립트는 `PYTHONPATH=.`를 붙여야 이 폴더 코드를 쓴다(pytest는 rootdir 때문에 괜찮다) [log:foreman_context_pct_20261109.md]. 합치기(rebase → fast-forward) · 미리보기(82xx) · 스키마 잠금 상세는 `docs/11_worktree.md`
- **`pgrep -f`는 자기 셸에 걸린다**(11-09 · 11-10 실제). CC는 Bash 명령 전체를 `bash -c '…'`로 돌려, 그 셸의 명령 글에 패턴이 들어 있다 → `pgrep -f "<패턴>"`이 자기 자신을 찾는다 [log:coder_resident_20261109.md] [log:merge_237_242_20261110.md]
  - 11-09 관리자는 "다른 pytest 있음"을 세 번 헛보았고, 코더 233은 `until ! pgrep -f "tools/screen.py"; do sleep 3; done` 셸이 영원히 안 끝나 합치기 직전에 걸렸다(그대로 끝냈으면 CC 끝내기 확인 창)
  - 대괄호 트릭(`pgrep -af '[p]ython -m pytest'`)은 패턴 글자가 자기와 다르게 해 준다. **그러나 같은 명령 안에서 그 프로그램을 돌리면** 뒤쪽 글자(`.venv/bin/python -m pytest …`)에 또 걸린다(11-10 관리자)
  - 그래서: **확인과 실행을 따로 친다.** 기다릴 때는 `pgrep -f`로 자기를 찾지 말고 그 작업의 PID나 결과 파일을 본다
  - 11-11부터 브리지가 PreToolUse에서 거부한다(`bridge/pgrep_guard.py`, 규칙 `pgrep-자기걸림`, 승인 모드와 상관없이) — 판정은 "`-f` 패턴 정규식이 이 명령 글 자체에 걸리는가"(명령 자리의 호출만, heredoc 본문 · echo 글은 빼고). 브리지 코드라 합친 뒤 브리지를 다시 띄워야 켜진다 [log:coder_screen_state_20261111.md]

## 5. 알림(텔레그램) 상세

- 턴 종료 신호(Stop hook 등)로 브리지가 보낸다 — 로드맵 4단계, README 3.2. 규칙은 `config/notify.toml`
- 보낸 것 · 안 보낸 것(+규칙)은 DB `notification`
- 브리지 밖 알림(백업 실패 등): `.venv/bin/python -m bridge.telegram "제목" "줄" …`
- 토큰 · chat_id는 저장소 맨 위 `.env.telegram`(권한 600, `.gitignore`의 `.env*`)
- 접두어: `[런슈즈]` · `[펫퍼민트]` · `[포먼]`. 토큰은 FOREMAN의 `.env.telegram` 하나다(11-02 결정)
- 보낼 때 · 조건 · 한 번만 보내는 규칙은 아래 표처럼 알림마다 `notification.rule` 키로 지킨다 — DB에 같은 키가 있으면 보내지 않으므로 **브리지를 다시 띄워도 한 번**이다(메모리로만 기억하는 것은 따로 적었다)
- 겹침 알림(11-06, `bridge/overlap.py`, `notify.toml [overlap]`) — **(11-09 바뀜) 낱말 겹침은 패널 띠만, 텔레그램은 같은 파일을 두 세션이 고쳤을 때 · 다른 프로젝트에 같은 글을 붙였을 때만.** 막지 않는다. 포먼의 서기 일감은 맞대지 않는다 [log:foreman-2_screen_ctx_switch_overlap_20261109.md]
  - ~~사람 입력이 같은 프로젝트의 다른 세션 요청과 드문 낱말로 겹치면 텔레그램~~ — 11-09 하루 4건이 모두 헛경보였다(사용자가 두 세션에 보낸 지시서의 파일 이름 · 커밋 id가 겹침). 사용자 결정: "텔레그램으로 올 만한 게 아니었다. 조사형 겹침은 패널 띠로 보이면 충분하다. 놓쳐서 문제가 생기면 그때 되돌리자"
  - **낱말 겹침**(사람 입력 때): 같은 프로젝트의 살아 있는 다른 세션이 최근 3시간(`window_min`)에 받은 요청과 드문 낱말로 겹치면 패널 띠만. 상대가 그 낱말의 파일을 실제로 고쳤으면 🔁 겹침(노랑, `edited`), 아니면 🔁 겹칠 수도(옅게, `weak`). 띠 모양은 `docs/style_guide.md` 「4-1. 화면 글」
  - **같은 파일**: `edit_scan_sec`(60초, 코드 기본값 — 0이면 끔)마다 같은 프로젝트의 살아 있는(멈춘 T 아님) 두 세션이 최근 `window_min`(180분) 안에 같은 파일을 Edit · Write · NotebookEdit · MultiEdit 했나 본다(`OverlapWatch.scan_files`). 걸리면 텔레그램(kind `overlap`) "같은 파일 — 세션 A와 세션 B가 둘 다 고쳤습니다: …" + 두 세션 모두 📝 띠. **새로 겹친 파일이 생길 때만** 다시 알린다(브리지 메모리 — 다시 띄우면 다시 알릴 수 있다)
    - 경로는 저장소 기준으로 맞춘다(`.worktrees/<이름>/bridge/x.py` = 원본 `bridge/x.py`). 세션 폴더 밖(메모리 · scratchpad · 다른 저장소)은 보지 않는다. 인계로 이어진 두 세션은 뺀다. 서브에이전트가 고친 것은 그 세션 것으로 센다. Bash(sed 등)로 고친 파일은 보이지 않는다
    - 훑기는 첫 사람 입력 때 띄운다(`start_scan`)
    - `README.md` 같은 파일을 미리 빼지 않는다(사용자 — "지금 빼면 진짜 겹침도 놓칠 수 있다"). 오탐이 나면 어떤 파일이었는지 기록하고 그때 뺀다
  - **다른 프로젝트에 같은 글(📋)**: 사람 글이 **다른 프로젝트**의 살아 있는 세션이 최근 180분에 받은 사람 글과 낱말 집합 자카드 ≥ 0.8(양쪽 낱말 12개 이상, `same_text`)이면 텔레그램 + 패널 띠 「📋 다른 프로젝트 — 이 글은 런슈즈 세션 217에 14:14에 들어간 글과 거의 같습니다. 잘못된 창에 붙여 넣었을 수 있습니다」, 작업 중이면 [이 세션 작업 중단](Esc). 지난 7일 다시 돌림 9쌍 모두 실제 잘못 붙여 넣기 [log:cross_paste_20261109.md]
  - 같은 두 세션은 1시간(`repeat_min`)에 한 번

| 알림 | 코드 · kind | 보낼 때 · 조건 | 한 번만(rule 키) |
|---|---|---|---|
| 권한 거부 30분 | `bridge/human_wait.py` · `denied` | 60초마다 화면 판정(`human_needs` — 마지막 사람 입력 뒤 CC auto mode 거부, 이벤트 `error_preview` "Permission for this action was denied")을 보고, **거부 뒤 30분** 지났고 그 세션이 살아 있고(멈춘 T 아님) **지금 일하지 않으면**(CC status ≠ busy). 일하는 중을 빼는 까닭 — 거부 뒤 CC가 다른 방법으로 이어 가는 일이 많고 그건 막힌 것이 아니다. 글 "[런슈즈] ✋ 권한 거부 40분째 — 「…」 세션이 CC 자체 검사에 막힌 뒤 멈춰 있습니다 / ▶ 막힌 도구 Bash · 이유 [External System Writes] / FOREMAN 승인 카드로 오지 않습니다. 그 세션에 허용하거나 다른 방법을 지시해 주세요". "답 기다림"(글로 묻고 끝남)은 알리지 않는다 — 턴 끝 알림이 그 물음이다 | `denied:<세션>:<거부 시각>` |
| '!'가 글로 들어감 | `bridge/bang_watch.py` · `bang` | 사람 글(UserPromptSubmit 훅, 대기열 입력 포함)이 앞 공백 · 줄바꿈 뒤 `!`로 시작하면 실행되지 않고 모델에게 글로 간 것. 제대로 실행된 `!`는 UserPromptSubmit 훅이 오지 않아 걸리지 않는다(11-09 실측). 글 "⚠ '!' 명령이 실행되지 않고 글로 들어갔습니다 — 「…」 세션 / ▶ !… / 돌리려면 터미널에서 맨 앞에 '!'(공백 없이) 또는 그 세션에 '… 실행해 줘'". 막지 않는다(이미 들어갔다). 입력 API 쪽 처리는 README 3.1 「첫 글자」 | `bang:<세션>:<시각>` |
| ArgoCD Sync 대기 | `bridge/pipeline.py` `check_sync_wait` · `syncwait` | README 3.6 — 처음 1시간 뒤 한 번, 풀릴 때까지 24시간마다 | `sync_wait:<프로젝트>:<기준 시각>:<회차>` |
| 배포가 끝나지 않음 | `check_argo_running` · `argorun` | README 3.6 — Sync 작업 시작 뒤 30분 | `argo_stuck:<프로젝트>:<행>` |
| 쌓인 대화 · 창 초과 · 작업 전환 | `bridge/compactwatch.py` · `context` · `switch` | `docs/11_handoff_v2.md` 「쌓인 대화 비율 · 작업 전환 권유 (11-09)」 | `ctx:` · `pct:` · `over:` · `switch:<턴>` |
| 사용 한도 80 · (막혔으면 90) · 95% | `bridge/usage.py` | `docs/15_usage.md` 「6. 화면」 · 「6-2.」 | `usage:<한도>:<문턱>:<리셋>` |

[log:alerts_denied_xmsg_bang_20261109.md] [log:screen_mismatch_waits_20261109.md] [log:screen_argocd_read_20261109.md]

- **세션 간 메시지 읽음(`bridge/xmsg.py`) — 텔레그램이 아니라 패널 표시다**(11-09 사용자 — 보낸 쪽은 받는 쪽이 읽었는지 모른다). 패널 활동 탭의 SendMessage 줄 끝에 "— ✓ 읽음 15:01 (받는 프로젝트 · 세션)" · "· 작업 중에" · "— 도착 15:01, 아직 안 읽음" · "— 도착 기록 없음(받는 세션이 꺼졌거나 FOREMAN이 보지 않는 세션)" [log:alerts_denied_xmsg_bang_20261109.md]
  - 받는 쪽 트랜스크립트의 `queue-operation enqueue`(`<cross-session-message from-name="…">` + 본문) = 도착, 그다음 `dequeue`(쉬던 세션이 가져감) 또는 `remove`(`absorbed_mid_turn`) · `queued_command` = 읽음(작업 중에). 적재기가 이미 event type `queued`로 넣던 줄이다
  - 짝짓기: 보낸 본문 앞 60자(공백 정리) = 받는 쪽 enqueue 본문 앞 60자, 보낸 뒤 10분 안. 이름 · 소켓을 풀지 않는다
  - `to`가 에이전트 id(`a?[0-9a-f]{12,}`)면 서브에이전트 이어 부르기라 표시하지 않는다
  - 활동을 다시 받을 때(세션을 고를 때) 이미 있는 줄도 고친다
