# 노션 원고 범위 검사 결과 고치기 (서기, foreman-6, 2026-11-17)

관리자 410의 서기 일감(사용자 지시 19 뒤 2번). 검사 log `log/foreman-5_notion_evidence_scope_20261117.md`의 「확실히 틀린 것」 11건과 「글만 다듬으면 되는 것」을 `notion/`에서 고쳤다. 검사 뒤 합친 코드 변경(비밀값 가리기, `[nudge]`, 🛡 알림, 출하 라인)이 닿는 줄도 지금 코드(main `5e0f7c5`)대로 고쳤다. 원고 29편, 고친 편 머리 「읽은 커밋」은 모두 `5e0f7c5`.

방법: 원고를 다섯 묶음(승인과 역할, 알림과 합치기, 서기, 구조와 적재와 DB와 화면, 교장과 인계)으로 나눠 서브에이전트 다섯이 병렬로 고쳤고, 각자 근거 원문을 다시 열었다. 이 세션이 보고를 받아 남은 줄 둘(`02_postit`, `03_keys`)을 고치고 커밋 표시를 맞췄다. 서브에이전트 다섯은 모두 끝났다.

## 1. 확실히 틀린 것

| # | 고친 곳 | 전 → 후 | 다시 확인한 근거 |
|---|---|---|---|
| 1 | `04_approval.md:74` | 넷 모두 observe여도 막음 → 스키마 잠금, 다른 저장소, pgrep 셋은 늘 막고, 역할 규칙은 mode가 enforce이거나 그 규칙에 enforce가 붙을 때만. 지금은 FOREMAN 조사 세션의 log 밖 쓰기 하나만 막고 나머지는 기록만 | `bridge/approvals.py`(`mode == "enforce" or role_hit.enforce`), `bridge/roleguard.py`, `config/roles.toml` |
| 2 | `11_notify.md` 머리, 226, 240~241, 246, 256, 289, 319 | 브리지 밖 길 하나 → 둘(`bridge.telegram` 백업 실패, systemd `OnFailure`가 부르는 `scripts/foreman-bridge-alert.sh`). 「보내는 길이 하나」 문장, 「어디서 오나」 표에 포기 알림 줄, 「다루는 곳」에 두 파일 | 스크립트 본문, `deploy/systemd/foreman-bridge.service`, `cd14ed6`. 토큰, 주소, 경로 값은 쓰지 않음 |
| 3 | `10_scribe.md:74~83`, `10_scribe/01_room.md:230` | `[nudge]`가 쓰인다 → 말풍선 기준은 `[postit]`(20, 7, 7) 하나이고 `bridge/postit.py`가 읽는다. `[nudge]`는 11-17에 뺐다. 틀린 값과 모르는 칸은 경고. 다시 띄우지 않아도 다음에 서기실을 읽을 때 반영 | `config/scribe.toml`, `bridge/postit.py` `conf`, `nudge_of`, `408e4ed` |
| 4 | `10_scribe/04_notion.md:285` | 처음 올라갈 때가 첫 실제 시험 → 11-15에 50편을 실제로 올려 자리와 차례를 확인. 아직 못 본 것은 사람이 고친 블록에서 멈추는지, 사람이 둔 글이 섞일 때 둘 | `log/foreman-4_notion_first_publish_20261115.md` |
| 5 | `02_ingest/02_hooks.md:124` | 하루 수백 번 → 11-08~11-15 하루 PreToolUse 호출 1,336~9,373번(11-15에 브리지 로그로 셈), 다른 hook은 빠진 수 | `log/manager410_overhead_20261115.md:246`, `deploy/hooks/foreman-hooks.json` |
| 6 | `01_structure/01_placement.md:63`, 표 | MySQL 셋 → 넷(파드 둘, 호스트 도커 둘). 표에 3307 줄. 얹지 않은 까닭은 「따로 따진 까닭은 기록에 없다」. 「마지막 줄」 → 「3306 줄」 | `log/01_kickoff_result.md:33`, `log/runshoes_manager_20261112.md:8` |
| 7 | `15_db/01_tables.md:7`, `:23` | 스물아홉 + 하나 → 마이그레이션이 만든 28 + `schema_migrations` 1 = 29. 지우거나 이름을 바꾼 마이그레이션 없음 | `migrations/*.sql` 직접 셈(CREATE 28, DROP과 RENAME은 주석 안 되돌리기 SQL뿐), `bridge/db/migrate.py` |
| 8 | `14_screen/05_check.md:240`, `:259` | 서기 몫 7줄 → 지금(5e0f7c5) 0줄, 처음 쓸 때 수와 바뀐 커밋 셋. 요약 예시 「13줄」은 보기이고 언제 값인지 기록에 없다고 밝힘 | `tests/data/screen_words.toml` 직접 셈(rename 35, promise 7, skip 4, code_exception 8, button 5, scribe 0), `6fcf7ad`, `9ac4527`, `408e4ed`, `tests/screen_words.py` |
| 9 | `09_dispatcher/03_overlap.md:76` | 스물세 개 → 스물네 개 | `bridge/overlap.py` `_JOSA`(11 + 13) |
| 10 | `09_dispatcher/01_plan.md:70` | 세 저장소 수백 KB → 설계 때(11-05) 잰 런슈즈 193KB, 펫퍼민트 495KB, 지금 등록 프로젝트 넷. 80줄과 맞음 | `docs/11_foreman_dispatch.md:9`, `migrations/0029_seed_ronanlab_infra.sql` |
| 11 | `09_dispatcher/02_note_wake.md:86` | 셋 × 2000 → 셋은 상한을 정한 11-08의 수, 11-10부터 넷, 넷 × 2000 = 8000도 묶음 안 | `docs/14_dispatcher_note_wake.md:75`(첫 커밋 `8907665`), `bridge/foreman_note.py` `TOKEN_CAP` |

## 2. 글만 다듬으면 되는 것

| 검사 log 줄 | 고친 곳 | 무엇을 | 근거 |
|---|---|---|---|
| 3번 넘게 | `04_approval.md:123`, `04_approval/02_flow.md:298` | 「3번 이상」 | `bridge/api/approvals.py` `n >= 3` |
| 18건과 19번 | `04_approval/01_rules.md:236` | 승인 18건, 거부 1건으로 나눔(18건이라 쓴 27, 16줄은 맞아 그대로) | `log/stage5_approval_result.md` 표 |
| push 79건 | `04_approval/01_rules.md:236` | push 79는 런슈즈, kubectl 132(60과 72), rm -r 60(41과 19)은 두 프로젝트 합계 | 같은 log 22행 |
| 역할판정예외 | `04_approval/02_flow.md:65`, `:98` | 역할 판정 예외 갈래와 그때 남는 한 줄 | `bridge/approvals.py`, `bridge/roleguard.py` `hookmiss.record("역할판정예외")` |
| 05_roles 통과 기록 | `05_roles.md:67`, `05_roles/01_roles.md:90` | 판정이 예외로 실패하면 `.run/hook_miss.log` 한 줄, 텔레그램은 한 시간에 한 번 | `bridge/roleguard.py`, `bridge/hookmiss.py`, `cd14ed6` |
| 모듈 지도 | `01_structure.md` 승인 무리 | `hookmiss.py` 줄 | `bridge/hookmiss.py`와 import 하는 곳 셋 |
| 3307 줄 | `01_structure/01_placement.md` 표 | 위 확실 6과 함께 | 같음 |
| 다섯 덩어리 | `15_db/01_tables.md:7` | 기능 표 27개를 다섯 덩어리(1~5절), 되돌리기용 표 하나는 6절 | 본문 절 짜임 |
| 여섯과 다섯 갈래 | `08_handoff/04_move.md:95`, `08_handoff/01_loss.md:172` | 둘 다 「끝난 결과 다섯, 도는 중을 더하면 서버 값 여섯」 | `bridge/losscheck.py` `OUTCOMES`, `bridge/static/js/moveflow.js` |
| 17.4초 근거 | `09_dispatcher/04_managers.md:198` | `[log:manager318_overhead_20261113.md]`, `[log:overhead_fix_20261113.md]` 더함(150초 문장의 기존 근거는 맞아 그대로) | 두 log에 17.4초 ×3 있음, `bridge/api/dashboard.py` `RELAY_GRACE` |
| 인프라 칸 | `10_scribe/04_notion.md:145` | 「쓰기 범위만」 → `root`, `docs_page`, `portfolio_page`, `github`, `ref`. 게시 방식 칸은 그 저장소 `.foreman/notion.toml` | `config/notion.toml` |
| 542 | `10_scribe.md:88` | 잰 때에 따라 542~546개 | `log/foreman-4_scribe_retro_removal_20261115.md:12, 32, 35` |

## 3. 11-17 코드 변경으로 함께 고친 줄

- 비밀값 가리기(`5e3a51d`)
  - `02_ingest/04_bus.md:99` 「비밀 파일 셋」 → 저장소 맨 위 `.env*`에서 예시 꼬리를 뺀 전부와 config가 가리키는 토큰 파일. 11-17 전 손 목록 때문에 두 파일이 빠졌던 것과 지키는 시험 한 문단, 형식 표에 Notion 통합 토큰 줄. 파일 이름은 `ls`로만 봤고 `.env*`는 열지 않았다
  - `05_roles/03_keys.md:234`, `:236`, `:248`: 정확한 값을 세 파일에서만 읽고 프로젝트 토큰과 Notion 토큰은 정확한 값으로 안 가려진다는 줄 → 지금 고르는 방식과 11-17 전 이력으로. 형식에 Notion 토큰. 근거 `bridge/mask.py` `secret_env_files`, `configured_secret_files`
- 서기 말풍선 설정(`408e4ed`)
  - 확실 3의 두 편, 그리고 `10_scribe/02_postit.md:239`에 11-17부터 생긴 설정 경고(틀린 값, 모르는 칸과 표, 읽기 실패. 파일이 없을 때는 경고 없음). 근거 `bridge/postit.py` `conf`
- 교장 지시문 서기 일 이름(`408e4ed`)
  - `10_scribe/01_room.md:149`, `09_dispatcher/01_plan.md:139`: 이제 `TASKS`에서 만들고 `publish`만 뺀 여섯(doccheck, trim, later, docfix, portfolio, techdoc). 근거 `bridge/foreman.py` `SCRIBE_SESSION_TASKS`
- 🛡 「합치기 준비됨」과 관리자에게 못 전한 합치기 알림 둘을 바로(`408e4ed`)
  - `11_notify.md:202`, `:205`, `:210~211`, `:307`, `07_merge/01_card.md:102`, `:260`, `:263`, `07_merge.md:136`. 근거 `bridge/mergeprep.py` `rule_urgent`, `_tell_manager_card`, `_tell_manager`(`later=False`), `bridge/notify.py`
- 「비공개 저장소」를 까닭으로 쓴 줄(저장소는 지금 공개, 링크를 걸지 않는 동작은 그대로)
  - `10_scribe/04_notion.md:64`: 정할 때(포트폴리오 11-06, 원고 11-15)는 비공개라 404였고, 공개 뒤에도 그대로 둔 까닭은 기록에 없다
  - `04_notion.md:247`, `:263`, `10_scribe/03_evidence.md:47`: 비공개를 까닭으로 쓴 말을 뺐다. 03_evidence 47줄은 설계 기록에 「뗀다」만 있고 까닭이 없어 「까닭은 적혀 있지 않다」로
- 출하 라인과 Harbor 칸(`9ac4527`)
  - `12_pipeline.md:156`: push 단계 실패 ✗, push 뒤 단계 실패 ✓, push 앞이나 모르는 단계는 「기록 없음」(`shipstate.js` `harborStatus`). `12_pipeline.md:287`, `14_screen/02_office.md:352`: FOREMAN 방도 출하 라인 없음(`office.js` `NO_SHIP`)
- 경고등 호버 옛 글: `notion/`에 없었다

## 4. 코드 세션 뒤 볼 줄 (고치지 않음)

- 513(서기실 포트폴리오 패널과 게시를 프로젝트별로)
  - `notion/10_scribe/01_room.md:222`: 포트폴리오 쓰기, 포트폴리오 게시, 기술문서 게시 묶음
  - `notion/10_scribe/04_notion.md:271`: `GET /api/publish?project=` 표의 포트폴리오 게시 상태 줄
- 514(실패 알림 바로 보내기, Fable 가격 칸)
  - `notion/11_notify.md:203`: 「옮기기 요약(`handoff`)」이 묶음으로 미루는 쪽
  - `notion/11_notify.md:306`: 「어디서 오나」의 옮기기 요약 줄 「묶음」
  - `notion/08_handoff/02_summary.md:60`: 「실패와 시간 초과도 알림으로 간다」
  - `notion/08_handoff/01_loss.md:310`: 점검 실패 텔레그램
  - `notion/08_handoff/03_promote.md:172`: 확인 실패 알림
  - `notion/09_dispatcher/02_note_wake.md:221`: 계획을 세우지 못함 알림
  - `notion/13_usage.md:57`: Fable 가격 줄(10, 50, 0.25, 20)

## 5. 판단이 필요한 것: 그대로 둠

검사 log 「판단이 필요한 것」 1~13(`00_foreman.md:147` 인프라 관찰, `04_approval` 「세 프로젝트 모두 자동 모드」, `01_placement.md:260` 토큰 셋, `02_startup.md:179` 「조용히」, `03_session.md:332` 48곳, `14_screen/02_office.md:88` 구역 다섯, `04_managers.md:28` 네 프로젝트 관리자, `08_handoff` 압축 비율, `06_sessions.md:44` FOREMAN에서만 15, `02_guards.md:314` 200건, `02_summary.md:177` 네 가지, `10_scribe.md:22` 색, `15_db.md:19-20` 행 수와 크기)은 모두 손대지 않았다.

## 6. 확인

- `.venv/bin/python -m pytest -q`: 1190 passed(화면 말 시험 서기 몫 0줄). `node --test tests/js/`: 218 pass, 0 fail
- 근거 확인기(`bridge.evidence.check_text`)를 고친 29편에 읽기만으로 돌렸다. 모든 표시가 맞고, 표시 없는 문장은 고치기 전보다 늘지 않았다(바꾼 문장 하나에 표시를 달았다)
- 새로 단 `[c:]`는 모두 main 이력 안이다. 서브에이전트가 처음 단 `e7b131f`, `ee1d57f`는 작업방 브랜치 커밋이라 main에 하나로 묶여 들어간 `408e4ed`로 바꿨다
- 새로 쓴 글에 em dash와 가운뎃점 0. diff에 걸린 둘(CLAUDE.md 인용의 줄표, Jenkins 단계 이름의 가운뎃점)은 원래 있던 글이다

## 7. 알릴 것

- `notion/10_scribe/04_notion.md:263`의 `[c:dc4944e]`(11-15 「포트폴리오 원고가 노션 편 페이지로 링크를 걺」)는 원래 있던 표시인데 이제 어느 브랜치에도 없는 커밋이다(작업방 브랜치가 지워진 것으로 보임). 근거 확인기는 커밋 객체가 있어 통과하지만 공개 독자는 열 수 없다. main에서 그 변경을 담은 커밋으로 바꿀지 다음 서기 몫
- 코드가 이상해 보이는 곳(고치지 않음)
  - `bridge/api/approvals.py:87` 주석은 「3번 넘게」, 식은 `>= 3`
- docs 쪽(서기 몫, 이번 일감은 `docs/` 금지): `docs/12_scribe.md:162`가 아직 「비공개 저장소 링크를 걸지 않는다」
- 검사 log의 `bridge/hookmiss.py:4` 「7갈래」는 지금 「8갈래」로 이미 맞다

## 규칙 위반

규칙 위반 없음. 파일은 Edit, Write로만 고쳤다. `python -I -c`는 근거 확인기를 읽기만으로 돌리는 데 두 번 썼고 파일을 쓰지 않았다. `pgrep -f`, push, 브리지 다시 띄우기, 노션 게시는 하지 않았다. 서브에이전트 다섯도 모두 「규칙 위반 없음」으로 보고했다.
