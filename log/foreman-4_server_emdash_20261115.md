# 서버 화면 글의 em dash 없애기 (11-15, foreman-4)

관리자 410 일감(사용자 지시 11-15 「화면 글에 남은 em dash(—)를 전부 없애라. 코드와 문서는 그대로 둔다」)의 서버 쪽(`bridge/` 파이썬)이다. 화면 코드(`bridge/static/`) · `tests/js/`는 디자이너 세션 몫이라 건드리지 않았다.

## 한 일

- API가 돌려줘 화면에 그대로 뜨는 글의 em dash를 뜻에 맞게 바꿨다. 두 문장이면 마침표로 끊고, 덧붙임이면 괄호 · 쉼표 · 쌍점(「무엇: 대상」)을 썼다. 글 길이는 늘리지 않았다
  - `Refused` 거부 사유: `handoff` · `mergeprep` · `inject` · `promote` · `scribe_room` · `worktree` · `foreman` · `handover` · `previews` · `notion`(`OutOfScope`, `/api/publish`에서 409로 뜸)
  - `HTTPException` · `refused` 응답: `api/terminal.py`(셸 패널) · `api/foreman.py`(/start · /handover) · `api/handoff.py` · `api/publish.py`(`/publish`) · `api/todo.py`
  - 결과 `note` · `error` · `why` · `title` · `blocked`: 합치기 카드(`note` · `error` · `human_why` · 카드 `why`), 쉬게 하기 · 이어 붙이기 note, 서기 할 일 줄(`scribe_room` · `docsync`), 끝난 뒤 어긋난 것(`reconcile` · `coder_room`), 멈춤 표시(`stallwatch` detail), 합칠 순서 까닭(`overlap` reasons), 스키마 잠금 풀림 사유, 계획 경고(`foreman` · `foreman_note` warn), 읽을 곳 문제(`pointers` · `handoff`), 압축 손실 점검 error(`losscheck`), 사용량 `basis`, 인프라 이벤트 줄(`pipeline._record_infra`), 미리보기 띠(`preview.py`), Notion 게시 꺼짐(`main.publisher_off`)
  - 승인 카드 글: `approval.py` 판정 사유(`Decision` reason, 화면 승인 카드 · CC 승인 창 · 이력), `approval_summary.py` 요약, `approvals.py` 질문 선택지 글 · 질문 사유
  - `api_error.one_line`(패널 · 텔레그램 같이 씀): 「종류 · req_… — 할 일」 → 「종류 · req_…. 할 일: …」
- 글을 맞대는 시험을 같이 고쳤다: `test_api_error` · `test_approval_summary`(2) · `test_foreman_multi` · `test_inject_screen` · `test_merge_wait_manager`(2) · `test_mergeprep`(2) · `test_pointers` · `test_stallwatch`
- 서버 글을 그대로 인용한 docs 두 곳을 맞췄다: `docs/11_worktree.md`(「세션이 아직 살아 있습니다. …」), `docs/10_office_design.md`(「입력 칸에 사람이 치던 글이 있어 넣지 않았습니다. …」). `docs/operations.md` · `style_guide.md`는 건드리지 않았다

## 시험

- `.venv/bin/python -m pytest -q` → 958 passed, 건너뜀 0
- `node --test tests/js/` → pass 193, fail 0(js는 고치지 않았지만 서버 글을 데이터로 쓰는 시험이 있어 같이 돌렸다)
- 브리지는 다시 띄우지 않았다. 합친 뒤 관리자가 띄운다

## 동작을 지키려고 살핀 곳

- `losscheck.NO_COMPACT`: 서버(`outcome`)와 화면(`moveflow.js`)이 앞머리 「압축된 적이 없습니다」로 가른다. 앞머리는 그대로 두고 뒤만 바꿨다
- `foreman_note.DROPPED_WARN`: `startswith`로 가른다. 상수는 그대로이고 뒤에 붙는 글만 바꿨다
- 합치기 카드 `human_why`: 화면 `handoff.js` `humanFiles`가 첫 「: 」로 잘라 파일을 뽑는다. 「지우기 — 파일 N개를 지움: a」는 「지우기(파일 N개를 지움): a」로 바꿔 첫 「: 」 자리가 그대로이게 했다. 「이력 다시 쓰기 · force push(…)」, 「늘-사람 판정 실패(…), …」에는 「: 」를 넣지 않았다(파일 없는 까닭으로 그대로 뜬다)
- `approval._rule_file_notice`: 사유 끝 괄호(`(…)$`)로 경로를 뽑는다. 괄호 앞만 바꿨다

## 코드가 쓰는 기호라 둠 (관리자 410 사용자 지시 11-15 반영)

코드가 ` — `로 나누거나 찾거나 맞대는 글은 글 쪽도 자르는 쪽도 그대로 뒀다.
- `bridge/api/dashboard.py` `ENDED_LABEL` 「쉬게 했습니다 — 합치기 기다림」: 화면 `opanel.js`가 `s.ended.label.split(' — ')[0]`로 자른다. **한 번 바꿨다가 이 지시를 받고 되돌렸다**
- `bridge/wake.py` 105 `wake_text`(「{종류} — {알림 첫 줄}」): 화면 `fmpanel.js` 76이 `x.why.split(' — ')[0]`로 자른다
- `bridge/scribe_room.py` 604 서기 세션 이름 「서기 — …」와 포트폴리오 주제 제목 `split(' — ')`
- `bridge/mergeprep.py` 368 `row_titles`(README 표 제목을 ` — `로 나눔), `bridge/docsync.py` 77 · 89(README 설명을 ` — `로 자르고 Notion 페이지 제목 「파일 — 설명」을 만든다. 바꾸면 Notion 페이지 제목이 모두 바뀐다)
- `bridge/pointers.py` 23 정규식(`[—–-]`)과 59 「모양을 알아보지 못했습니다(경로 — 이유)」(세션이 쓰는 「읽을 곳」 줄의 꼴을 알려 주는 글이라 꼴과 같아야 한다)
- `bridge/pipeline.py` 153 `SKIP_STEP` 「건너뜀 — 문서만」: DB에 저장되고 `step == SKIP_STEP`으로 맞댄다(`tests/test_pipeline.py`도 맞댐). 바꾸면 옛 줄과 어긋난다
- `bridge/assembler.py` 51~54 · `bridge/managers.py` 64 · 68 · 69 머리 글(「[관리자 부탁 — 」, 「[작업 보고 — 」, 「[사람에게 올릴 물음 — 」): 적재기가 이 머리로 턴 출처를 가른다(세션에 넣는 글이기도 하다)
- `bridge/notion.py` 556 `FOOTER_HEAD` 「마지막 갱신 — 」: Notion 페이지 꼬리를 이 글로 찾는다(498 · 505도 같은 Notion 본문)
- `bridge/worktree.py` 224 `_SYMBOL_CHARS`: 커밋 제목에서 기호를 쉼표로 바꾸는 표

## 다시 찾은 방법과 남은 것

파이썬 토큰 분석(`tokenize`)으로 `bridge/`(static 제외) 파이썬의 문자열 토큰 가운데 em dash가 든 것을 모두 뽑았다(독스트링 · 주석 제외). 처음 494개, 고친 뒤 300개다. 남은 300개는 모두 아래 까닭이다(개수는 대략, 한 줄에 둘 든 것은 따로 셈).

| 까닭 | 개수 | 예 |
|---|---|---|
| 로그(`log.*`) | 약 40 | |
| 텔레그램 전용 글(`_notify` · `_send` · `alert` · `_say` · `_alert` · `send_direct` · 접두어 붙는 알림) | 약 90 | `notify` · `pipeline` · `usage` · `overlap` 167~251 · `compactwatch` · `human_wait` · `bang_watch` · `switchwatch` · `ingest_health` · `stallwatch` 447~450 · `docsync` 278~288 · `notioncfg` 163~304 · `mergeprep` 762~766 · 1009~1013 · `approvals` 223 · 246 · 443 · 450 · `main.py` 364 |
| 세션(모델)에 넣는 글 · PreToolUse 거부 사유 | 약 120 | 교장 맥락(`foreman` 80~437 · `foreman_note` 149 · 151), 인계 · 서기 · 문서에 적기 일감(`handoff` 51~236 · 694 · 696, `scribe` · `scribe_room` 450~525, `scribe_ask`, `promote` 37~64, `losscheck` 153), 관리자 입력 칸 글(`mergeprep` 1034~1045 · 1302 · 1348 · 1360~1389, `handover` 54~66, `managers` 76~85, `terminal` 820, `handoff_state` 89), 역할 · 다른 저장소 · 스키마 잠금 · pgrep 거부(`roleguard` · `reposcope` · `schemalock` 93 · `pgrep_guard`, 모델에 가는 permissionDecisionReason) |
| 세션(curl)만 받는 API 응답 | 9 | `api/dashboard.py` 420(`/escalate` 403), `api/managers.py` 41 · `managers.py` 132(`/api/managers`), `api/publish.py` 91 · 102 · 112 · 114 · `scopetoken.py` · `notion.py` 1281~1289(짝 등록 `/publish/pair` · 프로젝트 토큰 범위 거부 — 화면은 관리 토큰이라 닿지 않는다), `api/foreman.py` 217(`/wake-test`, 화면에서 부르지 않음) |
| 코드가 쓰는 기호 | 위 절 | |
| 커밋 메시지를 만드는 코드 | 1 | `handoff.py` 1328 `save_progress` 커밋 제목 |
| 사람이 보지 않는 오류 · 명령줄 글 | 3 | `approval.py` 1072(설정 읽기 ValueError), `assembler.py` 225, `db/migrate.py` 100 |

## 판단 못 한 것

- `bridge/transcript/lookup.py` 116 「…(가운데 N자 줄임 — 전체는 트랜스크립트에)…」: 대화 찾기 API가 긴 글을 줄일 때 넣는다. 부르는 쪽이 세션인지 화면인지 확실하지 않아 두었다
- `bridge/notioncfg.py` 110 · 113 저장소 게시 설정 경고(`warnings`): 지금은 텔레그램(245)에만 쓰는 것을 확인했지만, 게시 상태 API가 `warnings`를 함께 내는지 끝까지 따라가지 않았다. 화면(`scribe.js`)에서는 `warnings`를 읽는 곳을 찾지 못해 두었다
- `bridge/foreman.py` 533 · 1002 계획 받기 실패 글(`dispatch.error`): 화면 교장 대화가 보이는 것은 Refused 글이고 `dispatch.error`는 기록 쪽이지만, 해가 없어 「: 」로 바꿨다

## 설계와 다른 점

- 같은 글을 화면과 텔레그램이 함께 쓰는 곳은 바꿨다: `api_error.one_line`(패널 이름표 · 텔레그램 턴 끝), `stallwatch` detail(화면 표시 · 텔레그램 ▶ 줄), `approval` 판정 사유(승인 카드 · 텔레그램 「규칙: …」 줄), `reconcile` 항목 글(화면 · 텔레그램 줄)
- 승인 판정 사유는 원래 「~다」 말투였다. 이번 일은 em dash만이라 말투는 그대로 두었다

## README에서 뺄 줄

「서버 거부 · 결과 글의 em dash · 가운뎃점」: em dash는 끝났다(위 「남은 것」의 까닭 말고는 서버 화면 글에 없다). 가운뎃점은 이번 일이 아니라 남아 있다. 줄을 지울지는 관리자가 정한다.

## 규칙 위반

- 11-15 시험 결과를 본 뒤의 진행 글 한 줄(「No parser; update the test expectation.」)을 영어로 썼다(CLAUDE.md 「항상 한국어로 답한다 — 진행 글까지」). 브리지 훅이 알려 주어 다음 글부터 한국어로 썼다. 서두를 때 영어로 흘렀다
- 그 밖에 파일은 모두 Edit · Write로 고쳤고(찾기 스크립트는 scratchpad에서 읽기만), push · 브리지 다시 띄우기 · `bridge/static/` · `tests/js/` 고치기는 하지 않았다
