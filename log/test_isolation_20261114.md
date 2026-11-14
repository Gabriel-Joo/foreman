# 시험 혼자 돌리기 · 실제 설정 읽기 · `-l` 토큰 — 고침 (11-14, worktree foreman-3, 관리자 362 일감)

브랜치 `cc/foreman-3`. `tests/`만 고쳤다(`bridge/` 코드 안 고침). push · 브리지 다시 띄우기 안 함.

## 1. 앞선 시험에 기대는 시험 — 파일마다 혼자 돌림

시험 파일 77개(+ 새로 만든 1개)를 하나씩 `timeout 300 pytest -q <파일>`로 혼자 돌렸다(뒤에서).
고치기 전 결과와 고친 뒤 결과를 맞대면 아래 표다. 하나만 빼고 모두 혼자서도 통과했다.

| 파일 | 고치기 전 혼자 | 고친 뒤 혼자 |
|---|---|---|
| test_usage.py | **5 failed**(`Table 'foreman_test_foreman_3_<pid>.usage_observation' doesn't exist`) | 16 passed |
| test_terminal.py | 33 passed, **1 skipped**(ttyd 없음 — 아래 2절. 이 skip이 혼자 돌리면 깨지는 것을 가렸다) | 33 passed, 1 skipped. ttyd를 잠깐 가리켜 혼자 돌리면 끝까지 돈다(3절 확인) |
| test_ccscreen.py | 11 passed | 11 passed(둘째 단독 돌리기 때 1 error — 내가 test_terminal.py에 잠깐 낸 문법 오류 때문, 아래 「규칙 · 실수」. 고친 뒤 다시 돌려 통과) |
| test_live_config_shape.py | (새 파일) | 20 passed |
| 나머지 73개 | 모두 passed | 모두 passed(개수 같음) |

나머지 73개: test_api_error · test_app_db · test_approval · test_approval_now · test_approval_summary · test_bang_watch · test_compactwatch ·
test_docsync · test_evidence · test_foreman · test_foreman_ctx · test_foreman_fail · test_foreman_multi · test_foreman_note · test_handoff ·
test_handoff_state · test_handover · test_human_needs · test_human_wait · test_inject · test_inject_screen · test_instructions_note_threads ·
test_js · test_korean_check · test_lookup · test_losscheck · test_manager_seat · test_managers · test_merge_remind_catchup · test_merge_wait ·
test_merge_wait_manager · test_merge_wait_off_remind · test_mergeprep · test_mergeprep_db · test_model_choice · test_moveflow ·
test_no_wait_prompt · test_note_auto_retire · test_notion · test_notion_h1 · test_notion_prev · test_notioncfg · test_notioncfg_halt ·
test_overhead_marks · test_overlap · test_overlap_base · test_pgrep_guard · test_pipeline · test_pointers · test_preview · test_promote ·
test_publish_hold · test_publish_scope · test_reconcile · test_reposcope · test_roleguard · test_scopetoken · test_scribe · test_scribe_ask ·
test_scribe_room · test_session_role · test_stage2_db · test_stallwatch · test_stallwatch_bg · test_switchwatch · test_testdb · test_units ·
test_worktree · test_wt_end · test_wt_truth · test_xmsg. `test_foreman*` · `test_ccscreen`(다른 세션 몫)도 혼자서 통과 — 고칠 것 없음.

- 첫 단독 돌리기는 내가 시험을 고치는 동안 같이 돌았다. test_usage의 실패는 설정 고침과 상관없음을 따로 다시 돌려 확인했다(DB 표 없음 5건)

**고친 것** — 공용 고정물 `migrated_db`(`tests/conftest.py`, pytest 한 번에 한 번 시험 DB에 이 worktree의 `migrations/`를 올리고
그 Settings를 준다). 표를 쓰는데 스스로 올리지 않던 시험이 이것을 받는다:
- `test_terminal.py::test_proxy_cookie_origin_ws` — 브리지 시작(`create_app`)이 `project` 표를 읽는다(관리자가 찾은 것)
- `test_usage.py`의 DB 시험 6개(`test_record_cli_writes_rows` · `test_monitor_absent_session_line_is_not_a_failure` ·
  `test_monitor_observe_fail_alert_recover_and_status` · `test_alerts_thresholds_eta_once_and_after_restart` ·
  `test_credit_signal_from_cc_limit_messages` · `test_alerts_90_when_credits_blocked`)
- 다른 DB 시험은 이미 각자 `migrate_main`을 부른다(14 파일) — 그대로 뒀다. 고정물로 모으는 것은 뜻이 같아 따로 하지 않았다

**설계와 달랐던 점** — `test_usage.py::test_record_cli_writes_rows`는 `Settings()`(운영 DB `foreman`)의 `usage_extra`에 줄을 쓰고 지우고 있었다.
혼자 돌려도 통과한 까닭이 운영 DB에 표가 있어서였다. 시험 DB(`migrated_db`)로 바꿨다 — 시험 뜻(쓰고 읽고 지움)은 같다.

## 2. `.tools/`가 worktree에 없어 ttyd 시험이 조용히 건너뜀 — 제안만(만들지 않음)

**고른 것: 따라오게 한다** — worktree를 만들 때 `.tools`도 `.venv`처럼 원본을 가리키는 링크로.
- `bridge/worktree.py` `LINK_TOP`에 `\.tools` 더하기, `EXCLUDE`에 `"/.tools"` 더하기(링크는 파일이라 `.gitignore`의 `.tools/`에 안 걸린다 — `.venv`와 같은 까닭)
- 커밋에 안 들어가게 하는 검사 `_forbidden`(166~171줄)에 `top == ".tools"`를 더하기
- 시험: `tests/test_worktree.py`에 만든 worktree에 `.tools` 링크가 있고 커밋 후보에서 빠지는지

**까닭**
- 보이게만 하면(skip 사유를 요약에) 건너뛴다는 것은 알지만 시험은 여전히 합치기 전에 돌지 않는다. worktree에서 바뀌는 것이 바로 그 코드(터미널 프록시)일 때 가장 필요한 시험이 빠진다. 따라오게 하면 skip이 아예 생기지 않는다
- ttyd는 바이너리 하나(빌드해 넣은 것, 저장소 코드 아님)라 원본을 가리켜도 worktree의 변경과 섞일 것이 없다 — `.venv`와 같은 성격
- 사람 몫 지점: 위 셋은 `bridge/` 코드라 이 일감 범위 밖(코더 일감으로)

**곁들여(관리자 의견에 동의, 선택)**: 그래도 없을 때를 위해 skip 사유를 기본 요약에 — 이 저장소엔 `pytest.ini` · `pyproject`의 `addopts`가 없다.
`-rs`를 기본으로 넣으면 `-l`처럼 출력이 늘지 않고 skip 줄만 생긴다. 지금 `-q` 마지막 줄에도 「1 skipped」 개수는 보이지만 까닭은 안 보인다.

## 3. `pytest -l`로 토큰이 찍힘 — 고침

시험 안에서 토큰 문자열을 지역 변수로 들고 있던 곳을, 가린 값을 담는 사전(`_Masked`, repr이 값마다 `'***'`)만 들게 바꿨다.
- `tests/test_terminal.py::test_proxy_cookie_origin_ws` — `tok` 없앰. `h = _bearer(<토큰>)` 하나를 처음부터 쓴다
- `tests/test_app_db.py` — `test_ws_auth_hello` · `test_emit_reaches_ws_and_db`의 `token`, `test_hooks_reject_paths`의 `hook` · `api`
  → `_ws_auth()`(ws 인증 글도 가린 사전) · `_hook_auth()` · `_auth()`. `_Masked.__repr__`가 키를 그대로, 값을 모두 `***`로 낸다(전에는 `Authorization` 하나만 가정)
- 다른 시험 파일에서 진짜 토큰을 꺼내는 곳은 없다(`grep get_secret_value` — 남은 것은 MySQL 비밀번호를 연결 인자로 바로 넘기는 줄뿐, 지역 변수 아님)

**확인**(값은 셸 변수로만, 개수만):
- `test_app_db.py::test_hooks_reject_paths` 끝에 일부러 실패하는 줄(`assert hook is None` + `_auth()` · `_ws_auth()`를 지역 변수로)을 잠깐 넣고 `pytest -l` → 출력 안 API 토큰 **0**, 훅 토큰 **0**. 지역 변수는 `{'Authorization': '***'}` · `{'type': '***', 'token': '***'}`로 찍힘
- `test_terminal.py::test_proxy_cookie_origin_ws` — ttyd 경로를 원본 폴더의 `.tools/ttyd`로 잠깐 바꾸고 끝에 일부러 실패 줄을 넣어 **혼자** `pytest -l -k proxy` → 시험이 끝까지 돌고(1절 고침 확인 — `doesn't exist` 없음) 일부러 넣은 줄에서 실패, 출력 안 API 토큰 **0**, `h = {'Authorization': '***'}`
- 임시 줄은 모두 지웠고(`LCHECK` 0줄) 출력 파일도 지웠다

## 4. 실제 설정 파일을 읽는 시험

README 929줄의 열 파일을 하나씩 보니 실제로 `config/*.toml`을 읽는 것은 일곱이었고, 목록 밖에 넷이 더 있었다.
나머지 셋은 `config/…` 글자를 판정 입력 · 기대 문자열로만 쓴다(읽지 않음 — 고칠 것 없음).

| 파일 | 읽던 것 | 고친 것 |
|---|---|---|
| test_approval_now | 원본 폴더의 `config/approval.toml`(절대 경로 — worktree에서도 원본 것을 읽었다) | `tests/fixtures/approval_now.toml`(11-14 실제 설정을 그대로 옮긴 고정물, `approval_strict.toml`과 같은 방식) |
| test_approval | 원본 폴더의 `tests/fixtures/approval_strict.toml`(절대 경로) | 시험 파일 옆 고정물 — worktree에서 고친 고정물이 시험되지 않던 것 |
| test_roleguard | `config/roles.toml`(mode가 observe인지까지) · `config/approval.toml` | `tmp_path` roles 파일 · 고정물 |
| test_stage2_db | `config/approval.toml`(상대 경로 — 돌리는 폴더에 따라 달랐다) | 고정물 |
| test_units | `config/notify.toml`(상대 경로) | `tmp_path` notify 파일 |
| test_usage | `config/usage.toml`(모듈 맨 위 `CFG`) | 같은 값을 쓴 글을 임시 파일로 읽음 |
| test_worktree | `config/worktree.toml`의 스키마 잠금 정규식 | 같은 정규식을 쓴 `tmp_path` 파일 |
| test_approval_summary · test_promote · test_scribe_room | 읽지 않음(문자열만 · 이미 `tmp_path`) | 없음 |
| **목록 밖** test_compactwatch | `config/notify.toml` [compact] + 옆의 `models.toml` [windows] | `tmp_path/config/` 두 파일 |
| **목록 밖** test_managers | `config/notify.toml`(상대 경로) | `tmp_path` notify 파일 |
| **목록 밖** test_overlap | `config/notify.toml` [overlap] | `tmp_path` notify 파일 |
| **목록 밖** test_pipeline | `config/pipeline.toml`(9곳) | 같은 값을 쓴 글을 임시 파일로 읽는 `_rules()` |

- 옮긴 값은 고친 날의 실제 설정과 같은지 기계적으로 맞대 봤다(usage · pipeline 주석 뺀 줄 diff 0, worktree 정규식 tomllib로 같음, 승인 고정물은 복사본)
- 시험 이름 `test_repo_config_and_missing_file`(compactwatch · overlap) · `test_repo_windows_and_pct_config`는 이제 저장소 설정을 안 읽어 `repo_`를 뺐다

**실제 설정을 읽어 모양만 보는 시험 하나 — `tests/test_live_config_shape.py`(새로)**
- 까닭: 오타 · 빠진 칸이 있으면 브리지는 여러 곳에서 기본값으로 조용히 넘어간다(roles.toml을 못 읽으면 역할 검사가 off, 없는 [compact]는 기본 문턱). 시험이 모두 임시 파일을 읽으면 그런 고장을 잡을 곳이 없어진다 — 이 프로젝트가 잡으려는 조용한 고장이다
- 보는 것: `config/*.toml` 모두 읽히는지, 승인 규칙에 묻는 규칙이 있는지, notify 프로젝트마다 prefix, roles 오류 없음 · mode가 셋 중 하나, 스키마 잠금 정규식이 컴파일되고 foreman 칸이 있는지, usage 가격 · 한도 줄 · `[credits] as_of`(test_usage에 있던 「실제 설정에 칸이 있다」를 옮김), pipeline infra · projects 있음
- 값(켬 · 끔 · 문턱 · 가격)을 바꾸는 것으로는 깨지지 않는다

**남은 것 세기** — `grep -rln 'config/' tests/`: 고치기 전 20 → 고친 뒤 25. 바꾼 자리마다 「실제 config/… 대신」 주석을 달아 글자 수로는 늘었다.
실제로 `config/`를 읽는 시험 파일은 **10 → 1**(`test_live_config_shape.py`, 일부러). 남은 24개는 판정 입력 · 기대 문자열 · 주석 · `tmp_path/config`다.
(`test_foreman*` · `test_ccscreen`은 다른 세션 몫이라 보지 않았다 — grep으로는 `config/` 글자가 없다)

## 시험

- 전체 pytest(`-rs`): **947 passed, 1 skipped**(`tests/test_terminal.py:526: ttyd 없음` — 2절, worktree라서). 실패 0
- 파일별 단독: 위 1절 표(고친 뒤 실패 0)

## 바뀐 파일

`tests/conftest.py` · `tests/fixtures/approval_now.toml`(새로) · `tests/test_live_config_shape.py`(새로) · test_app_db · test_approval ·
test_approval_now · test_compactwatch · test_managers · test_overlap · test_pipeline · test_roleguard · test_stage2_db · test_terminal ·
test_units · test_usage · test_worktree. docs에는 이 시험들을 설명하는 절이 없어 고치지 않았다.

## `docs/operations.md`에 바꿀 줄(서기 몫 — 이 브랜치는 안 건드림)

- 41줄 「시험 DB는 세션마다 따로다」 뒤에: 「표를 쓰는 시험은 스스로 마이그레이션하거나 `migrated_db` 고정물(`tests/conftest.py`)을 받는다 — 앞선 시험이 올린 표에 기대지 않는다(11-14)」
- 시험이 실제 `config/*.toml`을 읽지 않는다는 줄: 「시험은 임시 파일 · `tests/fixtures/`를 읽는다. 실제 설정은 `tests/test_live_config_shape.py` 하나가 모양만 본다(11-14)」

## README에서 뺄 줄

- 「실제 설정 파일을 읽는 시험 — 설정을 켤 때마다 깨진다」(929)
- 「시험 — `pytest -l`이면 지역 변수 `tok`이 출력에 한 번 나온다」(932)
- 「시험 — `.tools/`가 worktree에 따라오지 않아 …」(930)은 **남긴다** — 위 2절 제안을 관리자가 정해 만들 때까지. 할 것 칸을 2절 제안으로 바꾸면 된다

## 규칙 · 실수

- **규칙 위반 한 번**: 진행 글 한 줄을 영어로 썼다(시험 결과를 기다리며 「The background run hasn't finished yet; …」). CLAUDE.md 「항상 한국어로 — 도구 호출 사이의 짧은 진행 글까지」 위반. 훅이 바로 알렸고 그 뒤로 한국어로 썼다
- 실수(규칙 위반은 아님): 3절 확인용 임시 줄을 Edit로 지울 때 앞 줄바꿈까지 지워 `test_terminal.py`에 문법 오류를 냈다 — 그동안 돈 전체 pytest가 수집 오류로 멈췄고 단독 돌리기의 test_ccscreen이 1 error. 바로 고치고(줄바꿈 · 파일 끝 줄바꿈 · test_app_db 함수 사이 빈 줄) 다시 돌렸다
- 판단: 승인 고정물은 `cp config/approval.toml tests/fixtures/approval_now.toml`로 만들었다(새 파일 복사, 내용 고치기는 Edit로 머리 주석만). sed · heredoc 리디렉션으로 저장소 파일을 고치지 않았다
- 확인용으로 ttyd는 원본 폴더의 `.tools/ttyd`를 시험 안에서 가리켰을 뿐 worktree에 링크를 만들지 않았다(11-11 기록에서 범위 밖이었던 일)
