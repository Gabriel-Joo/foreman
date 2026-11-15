# 노션 기술문서 원고 첫 판 (서기, FOREMAN, 2026-11-15)

관리자 410이 넘긴 서기 일감(기술문서 쓰기). 목차는 사람이 정한 것(`log/foreman-5_notion_toc_20261115.md` 2절 + 사용자 결정 다섯)을 따랐다. Notion에는 올리지 않았다(사람이 [Notion에 올리기]).

## 한 일

- `notion/`에 원고 50편을 처음 썼다. 맨 위 17편, 하위 33편, 모두 12,325줄(약 1.8MB). 편마다 서브에이전트 하나가 코드, docs, log를 읽고 썼고, 서기 세션은 목차와 「다루는 곳」을 정하고 돌아온 원고를 맞댔다
- 읽은 커밋: 모든 편 `e5d584b`(아래 「판단」)
- 맞대기: 근거 확인기(`bridge/evidence.check_text`)로 50편 모두 틀린 근거 0, 머리 주석 읽힘. 코드 파일(bridge, config, migrations, scripts, tools, deploy, .claude, 빈 `__init__`, 시연 대본, 테마 그림 뺌)은 모두 어느 편의 「다루는 곳」에 들었다(덮지 못한 코드 0). 편 사이 「→ 편 제목」이 새 번호와 제목에 맞는지 보았다. 원고에서 IP, 도메인, 토큰 모양을 찾았고 없었다(localhost, 127.0.0.1만)
- 시험: 원고를 처음 썼을 때 pytest 1,060개 가운데 화면 말 시험 하나만 실패, 1,059 통과(js 209 포함). 실패는 시험이 `[code:]` 근거 표시를 버튼 인용으로 읽은 것(1,539곳 전부)이었고, 관리자가 main에서 고쳤다(`e5d584b`). rebase 뒤 화면 말 시험 17개 통과
- 그 고침에 맞춰 원고 세 곳(14-5 「4-7.」, 16 「4.」, 10-3 「다른 검사기와 맞춰야 한다」)을 「지금 실패한다」에서 지난 일과 지금 꼴로 고쳤다

| 편 | 줄 | 편 | 줄 |
|---|---|---|---|
| 00_foreman | 188 | 08_handoff | 150 |
| 01_structure | 253 | 08/01_loss · 02_summary · 03_promote · 04_move | 326 · 246 · 282 · 221 |
| 01/01_placement · 02_startup | 273 · 228 | 09_dispatcher | 113 |
| 02_ingest | 138 | 09/01_plan · 02_note_wake · 03_overlap · 04_managers | 308 · 262 · 288 · 306 |
| 02/01_transcript · 02_hooks · 03_turns · 04_bus | 196 · 138 · 221 · 254 | 10_scribe | 116 |
| 03_session | 410 | 10/01_room · 02_postit · 03_evidence · 04_notion | 249 · 280 · 182 · 284 |
| 04_approval | 165 | 11_notify | 316 |
| 04/01_rules · 02_flow · 03_summary | 367 · 312 · 167 | 12_pipeline | 334 |
| 05_roles | 160 | 13_usage | 351 |
| 05/01_roles · 02_guards · 03_keys | 266 · 320 · 252 | 14_screen | 158 |
| 06_sessions | 232 | 14/01_store · 02_office · 03_panel · 04_shell · 05_check | 279 · 394 · 288 · 302 · 278 |
| 07_merge | 152 | 15_db | 205 |
| 07/01_card · 02_reconcile | 261 · 127 | 15/01_tables · 02_migrate | 499 · 116 |
| | | 16_tests | 112 |

(줄 수는 고친 뒤 값과 몇 줄 다를 수 있다. 문단을 길게 써서 줄 수보다 분량이 크다)

## 판단 근거

- **읽은 커밋을 `b97ff43`에서 `e5d584b`로 올렸다.** 쓸 때 읽은 것은 `b97ff43`이다. 그 뒤 main에 들어온 코드 변경은 `e5d584b`의 `tests/screen_words.py`, `tests/test_screen_words.py`뿐이고(나머지는 log), 그 내용은 원고 세 곳에 반영했다. `b97ff43`으로 두면 이 fix 커밋 때문에 14-5, 16이 합치자마자 「코드가 바뀐 편」이 된다. 「한 벌이 한 커밋의 사진」이라 50편을 같이 올렸고, 올린 뒤 「코드가 바뀐 편」 0을 확인했다
- **자주 바뀌는 파일은 그 기능을 깊게 다루는 편에만 「다루는 곳」으로 두었다.** 지난 7일 커밋 수: `bridge/static/js/handoff.js` 35, `bridge/handoff.py` 33, `bridge/api/dashboard.py` 31, `bridge/foreman.py` 27. 여러 편이 근거로 짚지만 모두 「다루는 곳」에 넣으면 그 편들이 늘 「코드가 바뀐 편」이 된다. 그래서 `dashboard.py`는 「데이터 계층」만, 03(권한 거부, API 오류 판정)과 09-4(escalate)는 근거 표시로만 단다. 대가: 그 판정이 바뀌어도 03, 09-4는 바뀐 편으로 세지 않는다. 반대로 `bridge/api/sessions.py`(7일 7커밋)는 모델 바꾸기 몸통이라 13에도 더했다
- 서브에이전트가 표와 다르게 둔 「다루는 곳」은 그대로 받았다: 01-2 `bridge/__main__.py`, 04-2 `migrations/0010_approval.sql`, 05-2 `config/roles.toml`, 11 `deploy/mysql/backup.sh`, 15-2 `tests/testdb.py`, `tests/conftest.py`. 모두 그 편이 깊게 설명하는 파일이고 자주 바뀌지 않는다
- 지시된 목차와 코드가 달랐던 곳은 코드대로 썼다: 텔레그램은 승인 결정을 받는 길이 아니다(04, 04-2, 11). `character_session_move`는 옮기기와 무관한 0017 되돌리기 표다(08-4). 서기 일감 표는 코드 `TASKS`(doccheck, later, trim, techdoc, portfolio, docfix, publish)이고 sync, loss, polish는 없다(10, 10-1). 에셋은 CC0, MIT만이 아니라 CC-BY도 있다(14-2). plain 테마는 모눈을 같이 쓰지 않는다(14-2). escalate는 `bridge/api/dashboard.py`에 있다(09-4)

## 코드에서 찾은 것 (원고에 사실로 적음, 고치지 않음)

조용한 고장 쪽:
- 이 프로젝트를 만든 까닭인 「호스트 서비스 재시작 반복」 감시가 README 2.2 설계에만 있고 코드에는 없다(`RESTART_LOOP` 이벤트 이름만). README 3절 그림의 GitLab 웹훅, LLM 지표, 재시작 추세 폴링도 없다(00, 01)
- 브리지 유닛이 300초 안에 10번 실패해 포기하면 알릴 주체가 없다(텔레그램은 브리지가 보낸다)(01-1)
- CI/CD 체인 시작 실패, 자동 기상, 웹훅 포트를 켜지 못한 것이 경고 로그로만 남는다(01-2)
- 브리지가 답하지 못하면 PreToolUse 막기 넷(역할, 다른 저장소, 스키마, pgrep)이 판정 없이 통과하고 그 사실이 어디에도 남지 않는다(05-2). 통과는 설계로 두고, 뒤에 489, 493이 기록과 브리지 밖 포기 알림을 더함(`cd14ed6`, `58f9f03`)
- 지금 승인 설정에서 특정 명령 꼴의 삭제가 묻지 않고 통과하고, 작업방 안 규칙 파일 편집이 알림 없이 통과한다(04-1). 뒤에 490이 고침(`7ccb55f`), 일부 꼴은 미해결(11-15 공개 전 정리: 꼴은 뺐다)
- `deploy/hooks/foreman-hooks.json`의 PermissionRequest 한도 900초가 실제 설정 3660초보다 짧다. 견본대로 다시 깔면 15분에 끊기고 브리지만 계속 기다린다(04-2, 02-2)
- submit 대기열이 꽉 차 기록을 놓는 일이 로그에만 남는다(02-4)
- 낱개 텔레그램 알림이 세 번 실패하면 다시 보내지 않는다(11)
- 끝난 뒤 맞추기 알림 키에 끝이 없어, 이름이 다시 쓰인 폴더가 또 어긋나도 텔레그램이 다시 가지 않는다(07-2)
- 계획 세우기로 띄운 세션은 `drift`가 저장되지 않아 패널 「바뀐 것」이 빈 목록이다(넣는 글에는 붙는다)(08-2)
- 작업방 세션도 패널 머리 띠의 [새 세션으로 옮기기]로 옮기기를 시작할 수 있고, 새 세션은 원본 폴더나 새 작업방에 뜬다(08-4)
- 교장 지시문의 서기 일 이름에 techdoc이 없어, 계획 길로 띄운 기술문서 서기가 일 종류 없이 남는다(`techdoc_state`는 `notion/` 커밋 시각으로 대신 잰다)(10-1)
- mask가 정확한 값으로 가리는 비밀 파일이 `.env.db`, `.env.bridge`, `.env.telegram` 셋뿐이다(05-3)
- README 5절 보관 정책대로 오래된 행을 지우는 코드, FK 대신 두기로 한 고아 행 점검 쿼리가 없다(15)

낡은 글(코드와 다른 주석, docs, 화면 글):
- 서버 텔레그램 글에 옛 칸 이름 「넘기기 전 정리」가 남았다(`bridge/promote.py`, `bridge/losscheck.py`). 화면 말 목록에 없어 시험이 못 잡는다(08-1, 08-3)
- 머리 주석: `bridge/bus.py`, `bridge/store.py`, `migrations/0001`(event 쓰는 곳 하나), `bridge/notion.py`, `bridge/notioncfg.py`, `bridge/__main__.py`, `bridge/config.py`, `deploy/mysql/backup.sh`, `migrations/0021`, `migrations/0026`, `bridge/scopetoken.py`, `config/scribe.toml`, `config/wake.toml [note]`
- docs: `docs/12_scribe.md` 1, 2절 일감 표, `docs/14_dispatcher_note_wake.md`(테마 이름, 「제안 N」, Cloudflare 로그인 뒤), `docs/11_worktree.md` 2.2(미리보기 상태 자리), `docs/operations.md` 5절 접두어, README 3.3(시간 초과 10분, 규칙 이름), 3.9, 3.10, 3.1 경로 규칙
- 남은 코드: `coder_room.todo()`의 받는 함, `scribe_room.nudge_of`(불리는 곳 없음), 화면에서 부르지 않는 `GET /api/foreman/merge-order`

## 확인하지 못한 것

- 화면을 띄워 보지 않았다. 원고의 화면 설명은 코드, CSS, log로만 썼다
- log의 실측 수치는 다시 재지 않고 옮겼다(편마다 근거 표시). 15는 운영 DB를 읽기 전용으로 조회해 표 수와 크기를 넣었다
- 서브에이전트가 「추론」이라고 밝힌 곳(까닭이 기록에 없는 설정 값 등)은 본문에도 추론으로 적혀 있다

## 규칙 위반

- 서기 세션이 원고 검사 스크립트(스크래치패드의 `check.py`, 저장소 밖)를 Bash heredoc으로 만들었다. 「파일은 Edit, Write로」에 어긋난다. 그 자리에서 알아채고 뒤의 스크립트(`coverage.py`)부터는 Write로 만들었다
- 07 합치기 편 서브에이전트가 화면 말 시험 결과를 걸러 보려고 읽기 전용 파이썬 한 줄을 heredoc으로 돌렸다(파일을 만들거나 고치지 않음). 그 밖의 서브에이전트 49개는 모두 「규칙 위반 없음」으로 보고했다
