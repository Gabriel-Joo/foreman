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
| CC 전역 설정 | `~/.claude/settings.json`에 **model 기본값을 두지 않는다**(원래 상태, 사용자 — "손으로 여는 claude만 opus로 뜨는데, 그건 기본값 없이 두는 게 낫다"). 세션 모델은 FOREMAN이 띄울 때 정한다. `/model`이 전역 기본값을 다시 써 넣으면 지운다 — 패널 모델 창(「이 세션의 모델」)으로 바꾼 것은 브리지가 바로 지운다(`bridge/api/sessions.py` `_restore_model_setting`). 세션 안에서 손으로 `/model`을 친 것은 지우지 않으니 사람이 지운다(11-14 CC 2.1.325도 전체 id로 바꾸면 써 넣는다 — 시험 뒤 지움 [log:foreman-3_model_menu_20261114.md]) |

서버의 현재 포트 · 컨테이너 · 유닛 상태와 작업 시 주의는 `log/infra_20261102_host-changes.md`.

## 2. 이 저장소의 구조

| 무엇 | 위치 |
|---|---|
| 브리지(FastAPI, 수집 · API · WS · 알림 · 승인 · 입력 주입 · 인계) | `bridge/` — 시작 `bridge/main.py`, 트랜스크립트 적재 `assembler.py` · `transcript/`, 입력 `inject.py`, 인계 · 세션 조작 `handoff.py`, 파이프라인 `pipeline.py`, 승인 `approval*.py`, 알림 `notify.py`, 합치기 카드 `mergeprep.py`(카드는 DB `merge_card`에 남는다, 0032), 프로젝트별 관리자 · 계획 넘기기 `managers.py` · `handover.py`, 프로젝트 토큰 `scopetoken.py`, 역할 권한 `roleguard.py`, 셸 · 세션 화면 `terminal.py`(11-14 「터미널」을 「셸」로 바꿈 `375ca61`) |
| 화면 | `bridge/static/` — `/` 픽셀 화면(`office.html` · `js/office.js` · `js/opanel.js`), `/classic` 카드 목록(`dashboard.html` · `js/render.js`), 공통 CSS `css/panel.css`, 테마 `themes/<이름>/theme.json`(magic · office · site · plain) |
| DB(MySQL, 호스트 도커 `127.0.0.1:3308`) | 마이그레이션 `migrations/NNNN_*.sql` — `.venv/bin/python -m bridge.db.migrate` |
| 설정 | `config/approval.toml` · `notify.toml` · `pipeline.toml` · `worktree.toml` · `models.toml`(세션 모델 · 역할 기본값. 11-14부터 버전까지 적은 전체 id(`claude-opus-5-5` 등)로 쓰고, 옛 별칭 opus · sonnet · haiku · fable은 `[aliases]`가 id로 바꿔 받는다. 창 크기 `[windows]`는 모델 id가 먼저, 없으면 family [log:foreman-3_model_menu_20261114.md]) · `scribe.toml`(서기 "정리할까요?" 기준, `docs/12_scribe.md` 「11-4.」) · `handoff.toml`(`[merge_prep]` 합치기 카드 — **켜짐**, `projects = ["foreman", "ronanlab-infra", "petmint-rag-chatbot", "runshoes"]`(11-13 사용자: 펫퍼민트 · 런슈즈를 더함 — `6194ef7` · `9fa7831`), 네 프로젝트 모두 승인자 `manager` · `squash`(런슈즈는 `human_paths`에 마이그레이션 `V*.sql` · `CLAUDE.md` · `.claude/*` · `Jenkinsfile` · `Dockerfile*`), `remind_days = 5`(11-13 — 사람 승인 합치기 물음 5일째 알림), `[move] one_flow` — **켜짐**) · `managers.toml`(`[managers]` · `[handover]` — **켜짐**, 11-11) · `tokens.toml`(`[project_tokens]` — **켜짐**, 11-11) · `roles.toml`(`mode = "observe"` — 관찰, `projects = ["foreman"]`). 이 넷의 뜻 · 켜는 법은 `docs/11_foreman_dispatch.md` 「11.」 · `docs/11_worktree.md` 「6-1.」 [log:enable_c_wave2_20261111.md]. `notify.toml`은 FOREMAN · 인프라(11-12)와 펫퍼민트 · 런슈즈(11-13 사용자, 합치기 카드와 함께)에 `relay_reports` · `relay_questions` · `digest`가 **켜짐**(아래 「5.」). `notion.toml`은 프로젝트마다 root · 페이지 칸이고, 저장소 `.foreman/notion.toml`(origin/main)이 있으면 게시 방식 칸은 그 파일 것이다(인프라가 그렇게 돈다, 11-12). `wake.toml`은 자동 기상 설정에 더해 교장 노트 `[note]`(11-13 `81aa3ea`) — `stale_days = 3` · `stale_commits = 150`(끝남을 기계로 못 가르는 「진행 중인 일」 줄을 「낡음: 확인 필요」로 보이는 문턱, 표시만 하고 내리지 않는다) · `manager_spawn_done = false`(「관리자 띄우기」 줄을 첫 턴 끝에 기계로 내리는 규칙, 11-13 사용자: 끔 — 대신 교장 지시문이 관리자 띄우기를 진행 중인 일에 쓰지 않게 한다, `docs/14_dispatcher_note_wake.md` 3절). 그 밖에 `usage.toml` · `portfolio.toml`. 비밀은 `.env.bridge` · `.env.telegram` · `.env.notion`(Notion 통합 토큰) · `.env.project_tokens`(프로젝트 토큰 — 커밋 안 함). 저장소 설정을 한 번이라도 읽은 프로젝트의 기억은 `.run/notion_repo_config.json` — 그 파일을 잃으면 게시를 멈춘다(`bridge/notioncfg.py`, 11-12) [log:notion_repo_config_halt_20261112.md] |
| 설계 · 브리프 / 결과 | `README.md`, `docs/NN_*.md` / `log/*.md` |
| 시험 | `.venv/bin/python -m pytest -q`, `node --test tests/js/`. **pytest는 세션마다 시험 DB를 따로 만들어 쓰고 끝나면 지운다**(11-11, `tests/conftest.py` · `tests/testdb.py` [log:test_db_per_session_20261111.md]) — 예전엔 공용 `foreman_test`라 두 세션이 동시에 돌리면 서로의 표를 지워 11-09 31건이 실패했다 [log:repo_scope_readonly_20261109.md]. 이 변경을 합친 뒤부터 맞고, 아직 합치지 않은 worktree는 예전처럼 공용 `foreman_test`다. 상세는 아래 「3. 돌리기 · 확인」 시험 DB 항목 |

(`tests/test_app_db.py`는 11-11부터 운영 DB가 아니라 세션 시험 DB에 앱을 띄운다. 설정 `losscheck_recover`를 끈 채 띄우는 것은 그대로다 — 켜 두면 앱이 뜰 때 도는 압축 손실 점검을 모두 failed로 바꾼다(11-09 시험만 돌렸는데 운영 점검 #2가 실패로 적혔다) [log:cross_paste_20261109.md].)

## 3. 돌리기 · 확인

- 브리지는 systemd 사용자 유닛 `foreman-bridge`가 돌린다(11-06, `deploy/systemd/foreman-bridge.service`, linger 켬 — 부팅 때 자동 기동). 상태 · 로그: `systemctl --user status foreman-bridge`, `journalctl --user -u foreman-bridge -n 100`. 다시 띄우기(승인 대기 — `/api/dashboard`의 approvals pending — 가 없는지 본 뒤): `systemctl --user restart foreman-bridge`(10초 남짓 끊김)
  - CC 세션 셸에서는 `systemctl --user`가 `Process org.freedesktop.systemd1 exited with status 1`로 실패한다(세션 환경의 DBUS가 VNC 쪽 버스를 가리키고 `XDG_RUNTIME_DIR`가 비어 있다, 11-08 — 11-09에도 세 세션이 같은 일을 겪었다, 샌드박스 밖에서도). 앞에 `XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`를 붙인다(`journalctl --user`도 같다) [log:screen_argocd_read_20261109.md] [log:handoff_replace_main_20261109.md]
    ```
    XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart foreman-bridge
    ```
  - **브리지를 다시 띄워야 하는 것은 파이썬(브리지) 변경뿐**이다. js · css · html은 재시작 없이 바로 나간다(`cache-control: no-cache`). 열린 탭은 화면 코드 지문(`bridge/uiver.py` — static 아래 파일 이름 · 크기 · 수정 시각, WS `hello` · `/api/dashboard`의 `ui`)이 바뀌면 맨 위 노란 띠 "화면 코드가 바뀌었습니다. 새로 고쳐야 바뀐 기능이 보입니다."와 [새로 고침] 버튼이 뜬다(저절로 고치지 않는다 — 입력 칸 글이 날아간다) [log:pixel_bigger_question_card_20261109.md] [log:screen_mismatch_waits_20261109.md]
- 브리지 주소는 `127.0.0.1:8000`이다(API 시험 때)
- **시험 DB는 세션마다 따로다**(11-11, 합친 뒤부터 [log:test_db_per_session_20261111.md]). 그래서 "다른 pytest가 도는지 보고 기다린다 / 혼자 돌린다"는 이제 필요 없다(pgrep 확인도 하지 않는다)
  - 이름: `foreman_test_<자리>_<pid>` — `<자리>`는 `.worktrees/<이름>`이면 그 이름(소문자 · 24자까지), 원본 폴더면 `main`. pid는 pytest 프로세스 것이라 같은 worktree에서 둘을 같이 돌려도 겹치지 않는다. 마이그레이션도 그 DB에 이 폴더의 `migrations/`를 올려서 세션마다 갈린다
  - 시작 머리글에 `시험 DB: <이름>`이 찍힌다. 끝나면 지우고(Ctrl+C도 같다), 죽어서(`kill -9` · 세션 종료) 남은 것은 **다음 pytest가 뜰 때** 이름 끝 pid가 죽은 것만 치운다(자리 이름은 보지 않는다 — 다른 세션의 살아 있는 시험은 안 지운다)
  - **경고 `공용 foreman_test로 돈다`**가 머리글 · 끝 요약에 나오면 세션 DB를 만들지 못한 것이다(MySQL이 꺼짐 · `foreman\_test\_%` 권한 없음). 그대로 돌면 다시 다른 세션과 같은 표를 쓰니 원인부터 본다(조용히 넘어가지 않게 낸 경고다)
  - 손으로: `.venv/bin/python tests/testdb.py`(목록 — 살아 있음/남음), `.venv/bin/python tests/testdb.py --clean`(남은 것만 지움)
  - 새 시험이 DB를 쓰면 `Settings(mysql_database="foreman_test")`라고 쓰면 자동으로 세션 DB가 된다(`bridge/config.py` `resolve_test_db`). `model_copy(update=…)`로 바꿀 때는 `resolve_test_db("foreman_test")`. 운영 `Settings()` · `get_settings()`로 DB에 쓰지 않는다. 운영 DB `foreman`과 공용 `foreman_test`는 이 도구가 만들지도 지우지도 않는다
  - 토큰이 든 헤더를 assert 줄 안에서 만들지 않는다 — 실패하면 pytest가 호출 인자를 풀어 값을 그대로 출력한다. `tests/test_app_db.py`의 `_bearer()`(repr이 `Bearer ***`)처럼 쓴다
  - 아직 운영 DB에 쓰는 시험 둘: `test_foreman_note.py` · `test_usage.py::test_record_cli_writes_rows`(무작위 이름으로 쓰고 자기 행만 지운다 — 동시 실행은 겹치지 않지만 시험이 죽으면 `zz…` 행이 남을 수 있다)
  - DB 권한은 사용자가 준 것이다(`foreman_app`에 `foreman\_test\_%`.*). 되돌리는 명령은 위 기록의 「되돌리는 법」
- CC 세션 tmux(11-11 직접 확인): 세션은 프로젝트마다 tmux 세션 `cc-<프로젝트>[-N]`에 뜬다(예: `cc-foreman` · `cc-foreman-2` · `cc-runshoes-3`; `-N`은 같은 프로젝트의 둘째 이후 세션). tmux `foreman-bridge`에는 11-06부터 빈 bash 하나만 있고 세션이 없다(브리지는 위의 systemd 유닛이 돌린다 — tmux와 무관). 화면 아래 셸용 `foreman-shell`(창 4개)은 따로 있다(11-14 전에는 「웹 터미널」이라 불렀다). `cc-petmint`와 `cc-runshoes`는 창의 현재 명령이 `bash`로 보인다(`claude`가 아니다 — 11-11 확인 시점. 그 안에서 CC가 따로 돌고 있는지는 확인하지 못했다). 확인: `tmux ls`, `tmux list-panes -a -F '#{session_name} #{pane_pid} #{pane_current_command}'`
- 화면 자리 점검 도구 `.venv/bin/python tools/screen.py`
  - 헤드리스 크로미움으로 세 테마 × 세 크기의 `layoutAudit()` · `propAudit()` + PNG. 문제가 있으면 종료 코드 1
  - **화면마다 `nameAudit()` · `cardAudit()` · `tipAudit()`도 기본으로 센다**(11-09 — 전엔 `--eval`로 따로 불러야 봐서 빠뜨리면 안 보였다). 줄 끝에 `layoutAudit N · nameAudit N · cardAudit N · tipAudit 문제/호버 수 · propAudit N`, 모두 문제 수에 든다 [log:screen_argocd_read_20261109.md] [log:tips_and_credit_signal_20261109.md]
    - `cardAudit` — [전체] 카드 겹침 · 그림 덮음 · 화면 밖 · 줄 어긋남 · 잘림, [⌂] 현황판 이름 겹침 · 칸 밖 · 낱말 가운데 끊김
    - `tipAudit` — 툴팁 넘침 · 낱말 끊김 · 화면보다 큼(`docs/style_guide.md` 「4-1. 화면 글」)
    - `labelAudit`(화면마다, 11-10) — 지금 그린 그대로: 이름표(구역 · 출하 라인 · 캐릭터 이름 · 말풍선) ↔ 사람 몸, 이름표끼리, 구역 · 출하 라인 이름표 ↔ 가구(그림의 불투명 범위). `layoutAudit`은 좌석 자리 기준이라 이 겹침을 못 봤다. `layoutAudit()`를 콘솔에서 부르면 둘 다 나온다 [log:foreman_term_office_three_20261110.md]
    - `stackAudit`(화면마다, 11-13 `2819d41`) — 머리 위 표시 덩어리: 카드 ↔ 사람 몸(자기 몸 포함), 카드가 머리 위에 있나, 선 칸 위(복도 · 다른 방)로 넘침, 동작 카드가 글씨 카드 아래인가. 줄 끝 `stackAudit N`이 문제 수에 든다 [log:overhead_stack_20261113.md]. 말풍선이 화면 밖으로 잘리는 것은 `window.office.bubbleAudit()`(`--eval`)
    - `termAudit`(테마 × 크기마다, 11-10) — 패널 입력 칸이 패널 · 창 밖으로 넘치나, 셸과 겹치나, 패널 · 셸 겹침, xterm 글자 칸이 셸보다 넓은가. 닫힌 채 한 번, 셸을 연 채 한 번(`<…>_term.png`). `--no-term`이면 닫힌 채만(화면 이름이 「셸」로 바뀐 11-14 `375ca61` 뒤에도 점검 이름 `termAudit`은 그대로) [log:designer_screen_six_20261110.md]
    - `gridAudit`(테마 × 크기마다, 11-10 모눈) — 두 방이 같은 칸 · 방도 복도도 아닌 칸 · 끊긴 복도 · 복도에 안 닿는 방(grid.json, `js/grid.js gridProblems`), 복도에서 걸어서 못 가는 자리, 방 밖으로 나간 가구 · 자리, 이름표가 방 왼쪽 위 칸이 아니거나 가구 · 자리 몸에 걸림(배율 1과 지금 배율). 끝에 **테마 셋의 방 자리가 같은지** 견준다 [log:designer_grid_20261110.md]
  - 패널 너비는 좁게 · 넓게 두 값뿐이라(11-10) 크기마다 둘 다 본다(`--panel narrow,wide` 기본, 넓게는 크기 이름 끝 `w`)
  - 옵션: `--views hq,map,<현장>` · `--session <id>` · `--base`(미리보기 82xx) · `--eval` · `--ui-scale <배율>`(사용자가 보는 글씨 배율로 찍는다 — 범위 0.8~1.1 · 5씩, 처음 값 0.9(11-10). 양 끝 예 0.8 · 1.1) [log:pixel_bigger_question_card_20261109.md]
  - 통과는 "고른 화면에서 문제 0"일 뿐이다 — 사용자가 말한 화면을 [⌂] · [전체] 같은 탭 글자로 확인하고 그 화면을 고른다 [log:screen_mismatch_waits_20261109.md]
  - **screen.py를 브리지 `:8000`에 대고 돌리면 사용자가 보는 라이브 셸 창이 바뀐다** — 셸을 볼 때는 미리보기 서버(`--base`) · ttyd로 확인한다(11-10, 이름은 11-14에 터미널 → 셸)
  - **셸 글씨 13px은 정상이다**(사용자가 글씨 배율 90% 기준으로 재서 작게 나온 것 — 고칠 일이 아니다, 11-10). 11-13까지 교장 노트(1096)에만 있던 것을 옮겼다 [log:note_threads_only_20261113.md]
  - 자동 재배치 계획은 `--eval "window.office.layoutPlan()"`
- API 토큰은 `.env.bridge`의 `FOREMAN_API_TOKEN` — 셸 변수로만 쓴다. 프로젝트 토큰(`tokens.toml` **켜짐**, 11-11)은 `.env.project_tokens`의 `FOREMAN_TOKEN_<프로젝트>` — 만들기 `python -m bridge.scopetoken new <프로젝트>`(값은 화면에 안 찍힘), `list`는 키 이름만
- 셸(화면 아래 막대 「▲ 셸」 · iframe 「FOREMAN 셸」, `bridge/static/js/terminal.js` · `bridge/terminal.py` · `deploy/shell/foreman-term-view`. 11-14 「터미널」에서 이름을 바꿈 `375ca61`)의 스크롤과 글자 끌어 고르기(11-11) [log:d1_terminal_scroll_inputh_20261111.md] [log:d2_terminal_select_20261111.md]
  - xterm 스크롤백은 tmux가 화면을 그려 비어 있어 **tmux 복사 모드**로 올려 본다. `POST /api/terminal/scroll {tab, action}` — `up` · `down` · `exit`(막대 「▲ 위로」 · 「▼ 아래로」 · 「입력으로」)와 `wheel_up` · `wheel_down`(휠 한 칸 = 3줄)
  - **그룹 세션은 `mouse off`다**(처음엔 `mouse on`으로 휠을 받았지만 tmux가 끌기를 가져가 글을 끌어 고를 수 없어 바꿨다). 휠은 `terminal.js`가 iframe 안 `wheel`을 잡아 위 API로 보내고, 끌어 고르기는 브라우저(xterm.js) 선택이 받는다(복사 Ctrl+Shift+C). 선택은 지금 보이는 화면 안에서만 된다
  - **복사 모드에 들어간 채 입력하면** 친 글은 셸이 아니라 복사 모드 키로 간다 — 막대 「입력으로」를 먼저 누른다. `wheel_*`는 새 브리지 코드라 옛 브리지에서는 막대 경고(422)가 뜨고, `mouse off`는 그룹 세션을 만들 때 한 번 걸리므로 이미 열린 탭은 닫았다 열어야 바뀐다
  - 접힌 채에도 따라가기 타이머가 돌아 막대 이름이 방을 따라간다(tmux 창은 펼칠 때 고른다)
  - **[셸 비우기]**(11-14, 옛 [새 셸]. `POST /api/terminal/clear {project, force}`, `TerminalManager.clear`) — 셸을 새로 띄우지 않고(같은 pane) 화면 · 스크롤백만 비운다. 입력을 기다리는 셸은 `C-l` 뒤 tmux `clear-history`(`/hooks/shell` 기록에 `clear`가 남지 않게 명령으로 치지 않는다). 입력 줄에 친 글이 있거나 명령이 돌고 있으면 먼저 확인 창을 띄운다(돌고 있는 명령은 그대로 돈다). 셸 설정이 바뀐 옛 셸을 새로 여는 길은 옛 셸 알림 줄 안의 [새 셸로]뿐이다 [log:coder_ccscreen_20261114.md] (`375ca61`)
- **세션 화면**(11-14, 전 이름 「CC 화면」 — 사용자 지시 「영어 약자가 혼자 섞여 있다」, `fcd4b68`. 코드 이름 `ccscreen` · `/ccscreen` · `.run/ttyd-cc.sock` · `ccview-open`은 그대로. `bridge/static/js/ccscreen.js` · `bridge/terminal.py` · `deploy/shell/foreman-cc-view`) — 세션의 Claude Code 창(권한 · 계획 승인 · 안내 · 고르기 창까지)을 FOREMAN에서 보고 키(화살표 · Esc · 숫자 · Enter)를 보낸다. 전에는 이런 창이 떠 있으면 VNC로 들어가 Esc로 닫아야 했다 [log:coder_ccscreen_20261114.md] [log:coder_ccwindow_20261114.md]
  - 여는 곳: 패널 탭 줄 끝(「대화」 · 「활동」 · 「세션 정리」 오른쪽) [세션 화면 ↗] 단추 → **패널 위에 뜨는 창**(모달 아님 — 대화 탭을 보면서 함께 둔다). 처음엔 탭이었으나(`375ca61`) 사용자 지시로 띄우는 창으로 바꿨다(`8af171e`). 머리줄을 끌어 옮기고 **네 모서리 어디로든** 크기를 바꾼다(`fcd4b68` 전엔 오른쪽 아래뿐. 끄는 동안은 점선 테두리만, 놓을 때 한 번만 적용. 왼쪽 · 위 모서리는 반대쪽 모서리를 붙들고 자리도 함께 바뀐다. 가장 작게 360×220). 끄는 순간 떠 있던 툴팁(호버)은 꺼진다. 머리줄 글은 지금 「세션 창 109×37」(그 세션의 Claude Code 창 크기 — 띄우는 창 크기가 아니다. 글을 바꿀지는 사용자가 정한다). 크기 · 자리는 그 브라우저에만 기억한다(`localStorage` `foreman.ccwin.geo`). 띄운 뒤 다른 세션을 골라도 띄운 세션 그대로(창은 하나, 머리줄에 세션 번호), 다른 세션에서 단추를 누르면 그 세션으로 바뀐다. 창이 탭 줄 단추를 덮어 누를 수 없으면 패널에서 고른 세션이 다를 때 **창 머리줄에 「세션 N로」 단추**가 떠서 누르면 그 세션으로 바뀐다(같아지면 사라진다) [log:coder_sessionscreen_20261114.md]
  - 서버: ttyd를 하나 더 띄운다(UNIX 소켓 `.run/ttyd-cc.sock`, 경로 `/ccscreen`, 로그 `.run/ttyd-cc.log`. 브리지가 셸 ttyd와 함께 띄우고 감독한다). 브라우저는 세션 번호만 보내고 붙을 tmux 창은 브리지(`cc_target`)가 DB · 살아 있는 프로세스로 정한다. 연결마다 `foreman-cc-view`가 그 CC 세션의 tmux 세션에 그룹 세션 `ccv-<탭>-<pid>`를 만들어 붙는다. 끝난 세션 · 멈춰 둔(T) 세션은 열지 않고 창 안에 까닭을 보인다. 붙을 수 없으면(ttyd가 죽음 등) 5초 안에 「세션 화면 서버(ttyd)가 떠 있지 않습니다…」와 [다시 붙기](ttyd 창 제목도 「세션 화면」)
  - **크기**: 보는 동안 그 세션의 Claude Code 창(tmux)을 띄운 창(세션 화면) 크기에 맞춘다(창 옵션 `window-size manual` + 표시 `@foreman_ccview`, 손님 크기가 바뀔 때마다 맞춤 — 띄우는 창 모서리를 놓을 때 한 번). **닫으면(✕) 80×24(`bridge/terminal.py` `CC_REST_SIZE`)로 되돌리고 옵션을 푼다.** 사람이 정한 `window-size`(표시 없음)는 건드리지 않는다. 남은 묶음은 브리지가 시작할 때와 세션 화면에 붙을 때마다 풀어 준다(`release_cc_windows`)
  - 기록: 열고 닫은 것만 `session_action`에 `ccview-open` · `ccview-close`(WS 프록시가 연결 시작 · 끝에 남긴다 — 이름은 `action VARCHAR(12)` 때문에 12자 안). 키 하나하나는 남기지 않는다
  - 확인: 쉬는 세션 하나를 골라 [세션 화면 ↗] → 그 창의 `tmux display -p -t <창> '#{window_width}x#{window_height}'`가 띄운 창 크기, 닫은 뒤 `80x24`, `tmux ls | grep ccv-`가 닫은 뒤 없음. `SELECT action, detail FROM session_action WHERE action LIKE 'ccview%' ORDER BY id DESC LIMIT 4`. 고르기 창이 뜬 시험 세션에서 화살표 · Esc로 닫히는지(라이브 작업 세션에는 하지 않는다)

## 4. 작업 규칙의 상세

- **멈춰 둔 CC 프로세스**(11-02 기준 4개): pts/8 — PID 1301867 · 3872105, pts/7 — 1895956 · 1906162. 조사 경위는 `log/01_kickoff_result.md`
- **한국어 진행 글**: 11-05에 최종 답은 한국어인데 중간 진행 글이 영어로 흘러 패널 대화에 그대로 보였다. 컨텍스트가 길어져도 · 요약 뒤에 이어 갈 때도 · 도구 결과(로그 · 코드 · 영문 메시지)가 영어여도 마찬가지다
- **sudo**: 비대화형 sudo가 안 된다. 11-02에 "쳤다"는 명령이 실제로는 실행되지 않은 적이 있어, 쳤다고 하면 journal 등으로 확인한다
- **CI/CD**(11-03 결정, README 3.12): FOREMAN은 한 덩어리로 두고 배포는 systemd, 시험은 GitHub Actions. 둘 다 아직 만들지 않았다(옮기기 전 CLAUDE.md 문구 그대로 — 11-06에 다시 확인하지 않았다)
- **시험 세션 숨김**: 0018 `hidden_at` — `hidden_reason='test'`로 숨기면 카드 · 토큰 집계 · 디스패처 상황 묶음에서 빠지고 행은 남는다
- **worktree 링크**: `.venv` · `.env*` · `node_modules` · CC 메모리는 원본을 가리키는 링크다(그대로 쓰면 된다). `.tools`도 원본을 가리키는 링크이고 11-14 `1b286ca`부터 새로 만드는 worktree에만 있다(없으면 `.tools/ttyd`가 필요한 시험이 건너뛰어진다). pytest 기본 옵션이 `-rs`라(`pyproject.toml` `addopts`) 건너뛴 시험의 까닭이 요약에 찍힌다 [log:coder_sessionscreen_20261114.md] 단 `.venv`가 원본 폴더의 `bridge`를 가리켜서, worktree에서 pytest 밖 스크립트는 `PYTHONPATH=.`를 붙여야 이 폴더 코드를 쓴다(pytest는 rootdir 때문에 괜찮다) [log:foreman_context_pct_20261109.md]. 합치기(rebase → fast-forward) · 미리보기(82xx) · 스키마 잠금 상세는 `docs/11_worktree.md`
- **`pgrep -f`는 자기 셸에 걸린다**(11-09 · 11-10 실제). CC는 Bash 명령 전체를 `bash -c '…'`로 돌려, 그 셸의 명령 글에 패턴이 들어 있다 → `pgrep -f "<패턴>"`이 자기 자신을 찾는다 [log:coder_resident_20261109.md] [log:merge_237_242_20261110.md]
  - 11-09 관리자는 "다른 pytest 있음"을 세 번 헛보았고, 코더 233은 `until ! pgrep -f "tools/screen.py"; do sleep 3; done` 셸이 영원히 안 끝나 합치기 직전에 걸렸다(그대로 끝냈으면 CC 끝내기 확인 창)
  - 대괄호 트릭(`pgrep -af '[p]ython -m pytest'`)은 패턴 글자가 자기와 다르게 해 준다. **그러나 같은 명령 안에서 그 프로그램을 돌리면** 뒤쪽 글자(`.venv/bin/python -m pytest …`)에 또 걸린다(11-10 관리자)
  - 그래서: **확인과 실행을 따로 친다.** 기다릴 때는 `pgrep -f`로 자기를 찾지 말고 그 작업의 PID나 결과 파일을 본다
  - 11-11부터 브리지가 PreToolUse에서 거부한다(`bridge/pgrep_guard.py`, 규칙 `pgrep-자기걸림`, 승인 모드와 상관없이) — 판정은 "`-f` 패턴 정규식이 이 명령 글 자체에 걸리는가"(명령 자리의 호출만, heredoc 본문 · echo 글은 빼고). 브리지 코드라 합친 뒤 브리지를 다시 띄워야 켜진다 [log:coder_screen_state_20261111.md]
- **값(토큰 등)을 셀 때는 `/usr/bin/grep -cF`**(11-11 18:46 실제): 셸의 `grep`은 CC 실행 파일에 기대는 함수라, CC가 스스로 업데이트하는 순간 「claude native binary not installed」로 실패해 개수가 0으로 보일 수 있다 — 못 센 것과 0을 가르지 못한다. 값 자체는 출력하지 않는다(CLAUDE.md 비밀값 줄)
- **역할 권한 — 관찰 중**(11-11, `bridge/roleguard.py`, `config/roles.toml`): CLAUDE.md 글로만 있던 규칙(worktree 세션은 push 안 함 · 파일은 Edit · Write로만 · 관리자는 코드를 안 고침 · 서기는 `bridge/` 등을 안 고침)을 PreToolUse에서 본다. 지금 `mode = "observe"`라 **막지 않고** 그 호출의 `approval_req` 이벤트 payload에 `role_rule` · `role_reason`만 남긴다. 규칙: `worktree-push` · `bash-file-edit` · `manager-code` · `scribe-code`(하나씩 끌 수 있다). `enforce`로 올리는 것은 사용자가 하고, 판정이 실패해도 막지 않고 로그 error + 텔레그램 시간마다 한 번. 해석기 안 쓰기(`python -c "open(…,'w')"`)는 못 막는다. 기동 로그에 「역할 권한 observe: …」가 떠야 한다 [log:coder_c_wave2_20261111.md]

## 5. 알림(텔레그램) 상세

- 턴 종료 신호(Stop hook 등)로 브리지가 보낸다 — 로드맵 4단계, README 3.2. 규칙은 `config/notify.toml`
- 보낸 것 · 안 보낸 것(+규칙)은 DB `notification`
- 브리지 밖 알림(백업 실패 등): `.venv/bin/python -m bridge.telegram "제목" "줄" …`
- 토큰 · chat_id는 저장소 맨 위 `.env.telegram`(권한 600, `.gitignore`의 `.env*`)
- 접두어: `[런슈즈]` · `[펫퍼민트]` · `[포먼]`. 토큰은 FOREMAN의 `.env.telegram` 하나다(11-02 결정)
- 보낼 때 · 조건 · 한 번만 보내는 규칙은 아래 표처럼 알림마다 `notification.rule` 키로 지킨다 — DB에 같은 키가 있으면 보내지 않으므로 **브리지를 다시 띄워도 한 번**이다(메모리로만 기억하는 것은 따로 적었다)
- **관리자 중계 · 하루 묶음**(11-12 사용자, `config/notify.toml` `relay_reports` · `relay_questions` · `digest` — FOREMAN · 인프라, 11-13부터 펫퍼민트 · 런슈즈도): 세션 보고는 관리자가 받아 판단한다. 사람에게 올릴 물음은 관리자가 판단하지 않고 「사람에게 올릴 물음」으로 중계만 한다. 관리자끼리 묻고 답한 턴(`manager_ask`)은 텔레그램으로 보내지 않는다. 사람에게 갈 것은 매일 21:00(Asia/Seoul) 묶음으로 보낸다(`notification.decision = 'digest'`). 텔레그램 자체는 끄지 않는다
  - **사람에게 올리는 길은 관리자의 escalate 하나다**(11-13 사용자, `POST /api/sessions/{관리자 세션 id}/escalate {"kind": "report" | "question", "text": "…"}`, `bridge/api/dashboard.py`) — 응답 글로 쓰기만 하면 사람 화면에도 알림에도 뜨지 않는다. **물음 = 「❓ 관리자가 사용자 답을 기다립니다」를 바로**, **보고 = 「📋 관리자 보고」** — `digest = true`인 프로젝트면 21:00 묶음(`[digest] kinds`에 없어도 묶음, 묶음 제목 「관리자 보고」). 역할 manager 세션만 부를 수 있다(아니면 403). 관리자 relay · manager_ask 턴의 끝 알림은 나가되 「묻는 말」을 급함으로 치지 않는다 — 급함은 escalate 물음이 맡는다 [log:overhead_marks_20261113.md]
  - 중계가 켜진 프로젝트에서 작업 세션이 넘긴 것을 관리자가 받았는지 기다리는 시간 `RELAY_GRACE`는 30초(11-13, 잰 값: 작업 턴 끝 → 관리자 입력 칸 2.5초 ×3 · 17.4초 ×3, 실패 0). 그 사이 사람용 표시를 안 띄우고, 넘기지 못했거나 기록이 없으면 사람에게 뜬다 [log:overhead_fix_20261113.md]
  - **사람 승인 합치기 카드도 브리지가 이 길로 올린다**(11-13): 사람이 눌러야 하는 카드(`human_paths`에 걸린 카드, 관리자가 없는 카드)가 생기면 `mergeprep._esc_sync`가 그 저장소 관리자에게 `question`을 기계적으로 올린다(detail 앞 기계 표시 `#merge:<세션>#`, 알림 글에는 안 붙음). `notify_ready`가 켜져 있으면 카드 생김 알림(⑂)이 이미 나갔으므로 ❓는 빼고 화면에만 올린다. 관리자가 없거나 올리지 못하면 작업 세션 머리 위 「합치기 기다림」으로 남는다. 사람이 그 물음을 [답 안 해도 됨]으로 끄면 다시 올리지 않고 승인 막대 숫자 · 작업 세션 머리 위 · 말풍선에서도 뺀다(카드는 패널 「세션 정리」 탭 · `GET /api/merge-prep`에 끈 시각과 남고, 새 커밋이면 다시 올림). 물음은 7일 뒤 사라지므로 5일째에 텔레그램 바로 한 번 알린다(아래 알림 표 「합치기 카드 · 실패 · 멈춤」) [log:merge_wait_to_manager_20261113.md] [log:merge_wait_off_remind_20261113.md] [log:merge_remind_catchup_20261113.md]
- 겹침 알림(11-06, `bridge/overlap.py`, `notify.toml [overlap]`) — **(11-09 바뀜) 낱말 겹침은 패널 띠만, 텔레그램은 같은 파일을 두 세션이 고쳤을 때 · 다른 프로젝트에 같은 글을 붙였을 때만.** 막지 않는다. 포먼의 서기 일감은 맞대지 않는다 [log:foreman-2_screen_ctx_switch_overlap_20261109.md]
  - ~~사람 입력이 같은 프로젝트의 다른 세션 요청과 드문 낱말로 겹치면 텔레그램~~ — 11-09 하루 4건이 모두 헛경보였다(사용자가 두 세션에 보낸 지시서의 파일 이름 · 커밋 id가 겹침). 사용자 결정: "텔레그램으로 올 만한 게 아니었다. 조사형 겹침은 패널 띠로 보이면 충분하다. 놓쳐서 문제가 생기면 그때 되돌리자"
  - **낱말 겹침**(사람 입력 때): 같은 프로젝트의 살아 있는 다른 세션이 최근 3시간(`window_min`)에 받은 요청과 드문 낱말로 겹치면 패널 띠만. 상대가 그 낱말의 파일을 실제로 고쳤으면 🔁 겹침(노랑, `edited`), 아니면 🔁 겹칠 수도(옅게, `weak`). **(11-13 `e4a901c` 바뀜) 이 세션이 교장 경로(dispatch)로 띄워진 것이면 같은 프로젝트의 관리자 역할 세션은 맞대지 않는다**(`overlap.py` `without_spawner`) — 관리자가 넘긴 일감과 관리자 자신의 요청이 낱말로 겹쳐 헛경보가 나던 것. 다른 코더 · 역할 없는 세션과는 그대로 맞댄다. 띄운 쪽을 기록에서 알 수는 없어서(`record_spawn`은 띄워진 새 세션만 적는다) 「같은 프로젝트의 관리자 역할 세션 = 띄운 쪽」으로 본다 — 한 프로젝트에 관리자가 둘이면 둘 다 빠지고, 첫 지시문이 `dispatch` 기록보다 먼저 적재되면 그 한 번은 못 뺀다. 「같은 파일」 경보는 그대로 [log:judge_three_20261113.md]. 띠 모양은 `docs/style_guide.md` 「4-1. 화면 글」
  - **같은 파일**: `edit_scan_sec`(60초, 코드 기본값 — 0이면 끔)마다 같은 프로젝트의 살아 있는(멈춘 T 아님) 두 세션이 최근 `window_min`(180분) 안에 같은 파일을 Edit · Write · NotebookEdit · MultiEdit 했나 본다(`OverlapWatch.scan_files`). 걸리면 텔레그램(kind `overlap`) "같은 파일 — 세션 A와 세션 B가 둘 다 고쳤습니다: …" + 두 세션 모두 📝 띠. **새로 겹친 파일이 생길 때만** 다시 알린다(브리지 메모리 — 다시 띄우면 다시 알릴 수 있다)
    - 경로는 저장소 기준으로 맞춘다(`.worktrees/<이름>/bridge/x.py` = 원본 `bridge/x.py`). 세션 폴더 밖(메모리 · scratchpad · 다른 저장소)은 보지 않는다. 인계로 이어진 두 세션은 뺀다. 서브에이전트가 고친 것은 그 세션 것으로 센다. Bash(sed 등)로 고친 파일은 보이지 않는다
    - 훑기는 첫 사람 입력 때 띄운다(`start_scan`)
    - `README.md` 같은 파일을 미리 빼지 않는다(사용자 — "지금 빼면 진짜 겹침도 놓칠 수 있다"). 오탐이 나면 어떤 파일이었는지 기록하고 그때 뺀다
  - **다른 프로젝트에 같은 글(📋)**: 사람 글이 **다른 프로젝트**의 살아 있는 세션이 최근 180분에 받은 사람 글과 낱말 집합 자카드 ≥ 0.8(양쪽 낱말 12개 이상, `same_text`)이면 텔레그램 + 패널 띠 「📋 다른 프로젝트: 이 글은 런슈즈 세션 217에 14:14에 들어간 글과 거의 같습니다. 잘못된 창에 붙여 넣었을 수 있습니다.」, 작업 중이면 [이 세션 작업 중단](Esc). 지난 7일 다시 돌림 9쌍 모두 실제 잘못 붙여 넣기 [log:cross_paste_20261109.md]
  - 같은 두 세션은 1시간(`repeat_min`)에 한 번

| 알림 | 코드 · kind | 보낼 때 · 조건 | 한 번만(rule 키) |
|---|---|---|---|
| 권한 거부 30분 | `bridge/human_wait.py` · `denied` | 60초마다 화면 판정(`human_needs` — 마지막 사람 입력 뒤 CC auto mode 거부, 이벤트 `error_preview` "Permission for this action was denied")을 보고, **거부 뒤 30분** 지났고 그 세션이 살아 있고(멈춘 T 아님) **지금 일하지 않으면**(CC status ≠ busy). 일하는 중을 빼는 까닭 — 거부 뒤 CC가 다른 방법으로 이어 가는 일이 많고 그건 막힌 것이 아니다. 글 "[런슈즈] ✋ 권한 거부 40분째 — 「…」 세션이 CC 자체 검사에 막힌 뒤 멈춰 있습니다 / ▶ 막힌 도구 Bash · 이유 [External System Writes] / FOREMAN 승인 카드로 오지 않습니다. 그 세션에 허용하거나 다른 방법을 지시해 주세요". "답 기다림"(글로 묻고 끝남)은 알리지 않는다 — 턴 끝 알림이 그 물음이다 | `denied:<세션>:<거부 시각>` |
| API 오류로 멈춤 30분 | `bridge/human_wait.py` `DeniedWatch.check` · `apistop` | 권한 거부 30분과 같은 틀 · 같은 1분 고리(11-13 `1a61703` [log:screen_api_error_bar_20261113.md]). 턴 끝 알림 「⚠ API 오류로 멈춤」이 먼저 나가고, **그 뒤 30분**(`API_AFTER`) 지나도 새 턴이 없으면 한 번 더 — 화면에서는 쉬는 세션과 비슷해 보여 첫 알림을 놓치면 아무도 모른다(11-12 코더 311이 첫 턴 17초 만에 멈췄다). 살아 있지 않은 · 멈춘(T) · 일하는(busy) 세션은 뺀다. 글 "[접두] ⚠ API 오류로 멈춤 N분째 — 「제목」 세션이 API 오류로 턴을 끝낸 뒤 새 입력이 없습니다 / ▶ 종류 한 줄 / 화면에서는 쉬는 세션과 비슷해 보입니다. …". ⚠가 급함 표시라 묶음으로 미루지 않는다. 화면 표시는 `docs/10_office_design.md` 「머리 위 표시 (11-13)」 | `apistop:<세션>:<턴>`(DB `notification.rule` — 브리지를 다시 띄워도 한 번) |
| '!'가 글로 들어감 | `bridge/bang_watch.py` · `bang` | 사람 글(UserPromptSubmit 훅, 대기열 입력 포함)이 앞 공백 · 줄바꿈 뒤 `!`로 시작하면 실행되지 않고 모델에게 글로 간 것. 제대로 실행된 `!`는 UserPromptSubmit 훅이 오지 않아 걸리지 않는다(11-09 실측). 글 "⚠ '!' 명령이 실행되지 않고 글로 들어갔습니다 — 「…」 세션 / ▶ !… / 돌리려면 터미널에서 맨 앞에 '!'(공백 없이) 또는 그 세션에 '… 실행해 줘'". 막지 않는다(이미 들어갔다). 입력 API 쪽 처리는 README 3.1 「첫 글자」 | `bang:<세션>:<시각>` |
| ArgoCD Sync 대기 | `bridge/pipeline.py` `check_sync_wait` · `syncwait` | README 3.6 — 처음 1시간 뒤 한 번, 풀릴 때까지 24시간마다 | `sync_wait:<프로젝트>:<기준 시각>:<회차>` |
| 배포가 끝나지 않음 | `check_argo_running` · `argorun` | README 3.6 — Sync 작업 시작 뒤 30분 | `argo_stuck:<프로젝트>:<행>` |
| 쌓인 대화 · 창 초과 · 작업 전환 | `bridge/compactwatch.py` · `context` · `switch` | `docs/11_handoff_v2.md` 「쌓인 대화 비율 · 작업 전환 권유 (11-09)」 | `ctx:` · `pct:` · `over:` · `switch:<턴>` |
| 합치기 카드 · 실패 · 멈춤 | `bridge/mergeprep.py` · `merge` | `docs/11_worktree.md` 「6-1.」 — 카드가 새로 생길 때 · 준비 실패 · 훑기가 10분 넘게 안 끝남 · 합치기 실패 · 충돌 풀기를 못 보냄 · 관리자에게 못 알림 · **카드를 DB에 쓰지 못함 / 되살리지 못함**(11-13 — 처음 실패할 때 한 번, 카드는 메모리로 계속 돈다). 묶음을 켠 프로젝트(`kinds`에 merge)는 21:00 묶음. **사람 승인 합치기 물음이 5일째**(`handoff.toml [merge_prep] remind_days = 5`, 0이면 끔) 관리자 머리 위에서 7일 뒤 사라지기 전에 한 번 — 이것과, 브리지가 꺼져 있던 동안 7일이 지나 사라진 물음을 다시 뜰 때 알리는 것은 **묶음을 켠 프로젝트여도 바로** 나간다. 사람이 [답 안 해도 됨]으로 끈 물음은 알리지 않는다(11-13 `28911c6` · `2552526`) | `mergeprep:ready:<세션>:<끝 커밋>` · `fail` · `mfail` · `cfail` · `mgr` · `mergeprep:db:save\|load:…` · `mergeprep:remind:<escalate id>`(5일째와 7일 뒤 알림이 같은 열쇠 — 한 번만) |
| 관리자가 사용자 답을 기다림 · 관리자 보고 | `bridge/api/dashboard.py` `escalate` · `escalate` | 관리자가 `POST /api/sessions/{sid}/escalate`를 부를 때. 물음 「❓」은 바로, 보고 「📋」는 묶음을 켠 프로젝트면 21:00 묶음. 사람 승인 합치기 카드는 브리지가 대신 올린다(위 「관리자 중계」) | `escalate:<session_action id>` |
| Notion 기술문서 — 사람이 고친 곳이 있어 덮지 않음 ✋ · 자동 게시 실패 ⚠ | `bridge/docsync.py` · `docsync` | `docs/12_scribe.md` 「5.」 — 자동 맞추기(`docs = "auto"`)와 한 쪽 게시(`POST /api/publish`, 11-12)가 사람이 Notion에서 고친 블록을 만나 멈췄을 때 · 게시가 실패했을 때. 묶음을 켠 프로젝트는 ✋ 줄이 21:00 묶음(`kinds`에 docsync), ⚠는 바로 | 규칙 키 없음 — 이 브리지 프로세스 메모리로 한 번(`held:<프로젝트>:<커밋>:<경로>` · `fail:…`). **브리지를 다시 띄우면 같은 것이 다시 나갈 수 있다** |
| Notion 게시 설정 — 깨짐 · 경고 · 🛑 멈춤 · 다시 돎 | `bridge/notioncfg.py` · `docsync` | 프로젝트 저장소 `.foreman/notion.toml`(origin/main)이 깨졌을 때(옛 설정 그대로 / FOREMAN 칸으로 돎) · 경고 · 한 번이라도 쓴 프로젝트가 그 파일을 잃어 **게시를 멈췄을 때(🛑)** · 다시 읽혀 돌 때 · 기억 파일 `.run/notion_repo_config.json`을 읽지 못함 · 쓰지 못함 · 지움. 멈춤은 시작할 때 · 사유가 바뀔 때, 브리지를 다시 띄우면 멈춘 채일 때 한 번 더. `GET /api/publish?project=`의 `config.halted`와 서기 화면 할 일에도 뜬다 [log:notion_repo_config_halt_20261112.md] | 같은 글은 이 프로세스 안에서 한 번(`_alert`), 멈춤 · 다시 돎은 바뀔 때만 |
| 계획 넘긴 뒤 안 띄움 · 관리자 부탁 못 넣음 | `bridge/handover.py` · `bridge/managers.py` · `manager` | `docs/11_foreman_dispatch.md` 「11.」 — 넘긴 지 15분(`wait_min`) 안에 시작하지 않음 / 관리자가 없거나 입력 칸에 못 넣음. **켜짐**(11-11 `[managers]` · `[handover]`) | 안 띄움: `dispatch.handed_alert_at`(넘김마다 한 번). 부탁 못 넣음은 규칙 키 없이 부를 때마다 |
| 사용 한도 80 · 95% | `bridge/usage.py` | `docs/15_usage.md` 「6. 화면」. 「추가 사용이 막혀 있으면 90%에 한 번 더」는 11-14에 뺐다 — CC 한도 글로 막힘을 판정하던 길(`credit_signal`)을 지우면서(`docs/15_usage.md` 「6-2.」). 옛 `usage:<한도>:90:<리셋>` 기록은 DB에 그대로 있다 | `usage:<한도>:<문턱>:<리셋>` |
| 사용 한도 줄이 6시간 넘게 없음 | `bridge/usage.py` `ABSENT_ALERT_H` | CC가 서버에서 값을 못 받으면 `/usage`에서 그 한도 줄(예: 5시간)을 뺀다. 줄이 **6시간 넘게 없으면** 한 번 — 그동안 그 한도의 80 · 95% 알림이 멈춰 있어서(조용한 고장). 빠진 한도는 옛 값을 지금 값처럼 내지 않고 읽기 실패로도 세지 않는다. 모델별 한도(Fable 등)는 요금제 · 서버에 따라 나타났다 사라지는 줄이라 알리지 않고 화면에만 둔다. 줄이 다시 나오면 평소대로 돌아온다. 빠진 때는 브리지 메모리라 다시 띄우면 그때부터 다시 센다. `docs/15_usage.md` 6-3절 [log:usage_missing_line_20261114.md] (`6066d90`) | `usage:<한도>:absent:<빠진 때 MMDDHHMM>` |
| 오래 도는 백그라운드(`bg_long`) | `bridge/stallwatch.py` `judge_bg` · `stall` | 뒤에서 도는 일(백그라운드 Bash, Monitor는 뺌)이 **30분 넘게**(`BG_LONG`) 끝 알림 없이 돌 때, 세션이 턴을 닫고 쉬어도 1분마다 잰다. 출력 파일이 나온 적 있고 15분(`BG_QUIET`) 안에 바뀌었으면 정상. ① 출력이 나오다 15분 넘게 그대로면 「멈췄을 수 있습니다」 ② **출력이 한 번도 없으면(파일 크기 0, `\| tail`처럼 끝에서만 찍는 명령)** 멈춤 여부를 모르니 「오래 돕니다」만 ③ 출력 파일을 못 찾으면 「끝 알림 없이 돕니다. 출력 파일을 찾지 못했습니다」. 알릴 때 안내 「대화창에서 그 일을 보고, 멈췄으면 세션에 멈추라고 지시합니다」. 화면은 세션 `stall`(`bg_long`) [log:bg_long_20261114.md] [log:bg_quiet_fix_20261114.md] (`c0f4c4f` · `cbde3bd`) | `stall:bg_long:<세션>:<task>` |
| 쉬는 세션에 창이 떠 있음(`dialog`) | `bridge/stallwatch.py` `judge_dialog` · `stall` | 일하지 않는 세션의 tmux 화면에 CC 결정 창(계획 승인 · 도구 권한 · 폴더 신뢰 …)이나 모르는 창이 떠 있는데 패널에는 기다리는 승인 카드가 없을 때, **2분 뒤** 한 번(「창에서 답을 기다림」 — 그 세션의 대화창에서 답해야 이어진다). 모르는 창은 CC status가 `waiting`일 때만, 화면을 못 읽는 세션(tmux 밖)은 `waiting`만으로 본다. 브리지가 이미 「대화창에서만」을 알린 창(마지막 승인이 30분 안의 `timeout`)은 화면에만. 끝내기 확인 창(`exit_confirm`)도 같은 판정이 가르고 2분 뒤 한 번 알린다. **안내 창**(`notice` — 자동 압축 권유 · /model · /config)도 같은 2분 뒤 한 번 알린다(글: 「안내 창이 떠 있어 세션이 입력을 못 받습니다. 대화창을 확인해 주세요」. 전에는 일부러 연 창일 수 있어 알리지 않았다. 기준은 결정 창과 같은 2분, 11-14 사용자) [log:notice_alert_20261114.md] (`6157a5c`). 창을 처음 본 때는 브리지 메모리라 다시 띄우면 한 번 더 갈 수 있다. 사람은 패널의 [세션 화면]으로 그 창을 보고 답할 수 있다(위 「3.」) [log:plan_approve_mode_20261114.md] (`0d9de26`) | `stall:dialog:<세션>:<창을 처음 본 시각 YYYYMMDDHHMM>` |

[log:alerts_denied_xmsg_bang_20261109.md] [log:screen_mismatch_waits_20261109.md] [log:screen_argocd_read_20261109.md]

- **세션 간 메시지 읽음(`bridge/xmsg.py`) — 텔레그램이 아니라 패널 표시다**(11-09 사용자 — 보낸 쪽은 받는 쪽이 읽었는지 모른다). 패널 활동 탭의 SendMessage 줄 끝에 ", ✓ 읽음 15:01 (받는 프로젝트 · 세션)" · "· 작업 중에" · ", 도착 15:01, 아직 안 읽음" · ", 도착 기록 없음(받는 세션이 꺼졌거나 FOREMAN이 보지 않는 세션)" [log:alerts_denied_xmsg_bang_20261109.md]
  - 받는 쪽 트랜스크립트의 `queue-operation enqueue`(`<cross-session-message from-name="…">` + 본문) = 도착, 그다음 `dequeue`(쉬던 세션이 가져감) 또는 `remove`(`absorbed_mid_turn`) · `queued_command` = 읽음(작업 중에). 적재기가 이미 event type `queued`로 넣던 줄이다
  - 짝짓기: 보낸 본문 앞 60자(공백 정리) = 받는 쪽 enqueue 본문 앞 60자, 보낸 뒤 10분 안. 이름 · 소켓을 풀지 않는다
  - `to`가 에이전트 id(`a?[0-9a-f]{12,}`)면 서브에이전트 이어 부르기라 표시하지 않는다
  - 활동을 다시 받을 때(세션을 고를 때) 이미 있는 줄도 고친다
