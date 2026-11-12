# 승인 지옥 줄이기 — 알림 · 중계 (11-12, 코더 B · worktree foreman-3)

사용자 결정(11-12). 오늘 텔레그램: 관리자 턴 끝 86(그중 41이 관리자끼리 부탁으로 연 턴), 코더 턴 끝 28, docsync 47.

## ① 관리자끼리 부탁으로 연 턴은 텔레그램을 보내지 않는다

### 한 일
- `bridge/assembler.py` `_origin` — 프롬프트 머리 120자에 `[관리자 부탁 — `가 있으면 출처 `manager_ask`(새 값, `turn.origin` VARCHAR(20)에 11자).
  단 `[관리자 부탁 — 사람 관리자`(계획 카드 [관리자에게 보내기] — `handover.py`가 from 없이 부름)는 사람이 누른 것이라 `human` 그대로
- `config/notify.toml` `[defaults] origins`는 그대로(`human` · `meta`) — `manager_ask`가 목록에 없으니 기본 규칙에서 `skipped origin:manager_ask`로 남는다. 주석에 까닭
- `bridge/notify.py` 출처 이름 `manager_ask` → 「관리자 부탁」(규칙을 바꿔 보내게 했을 때의 문장용)
- 시험 `tests/test_managers.py::test_manager_ask_turn_origin_and_no_telegram` — `ask_text` 결과 · `<pasted_content>`로 감싼 것 · 같은 프로젝트끼리 → `manager_ask`, 「사람 관리자」 · 보통 입력 → `human`, 네 프로젝트 규칙 모두 안 보냄

### 방법을 고른 까닭
- 출처 표시(새 origin)로 갈랐다. 이미 `handoff` · `handoff_in`을 같은 방식(글 머리 표지)으로 가른다. 알림만 막는 것(notify에서 글 보고 거르기)으로는 화면 · 기록에서 사람 입력처럼 보이는 문제가 남는다
- 새 출처라 `origin = 'human'`을 세는 곳(겹침 알림 `overlap.py` · 「답 기다림」 마지막 사람 입력 `api/dashboard.py` · 압축 사이 사람 턴 `compactwatch.py` · 서기 `scribe*.py` · 작업 전환 `switchwatch.py` · 관리자 최근 요청 `foreman.py`)에서 부탁 턴이 저절로 빠진다 — 사람이 한 말이 아니므로 맞다
- 오늘 실제 41건을 DB에서 보낸 쪽으로 나눔: foreman 관리자(276) 12 · foreman 관리자(309) 11 · runshoes 12 · ronanlab-infra 6, 「사람 관리자」 0 — 모두 이번 변경으로 안 나간다

### 설계와 달랐던 점 · 남은 것
- **화면 이름표**: `bridge/static/js/render.js` `ORIGIN_LABEL`에 `manager_ask`가 없어 대화 패널에 `manager_ask` 글자 그대로, 열린 턴 줄에는 빈칸으로 나온다(이제 「나」로는 안 보인다). 맡은 파일 밖이라 고치지 않았다 — 한 줄(`manager_ask: '관리자 부탁'`)
- 이미 들어간 옛 부탁 턴은 `human`으로 남는다(되채우기는 마이그레이션 — 하지 않음)
- 부탁 턴이 연 서브에이전트의 묶음 알림은 그대로 나간다(`_batch`의 진행 중 판정이 `human` · `meta`만 본다) — 드물어 두었다

### 되돌리는 법
- 커밋 하나를 `git revert`. 또는 `config/notify.toml` `[defaults] origins`에 `"manager_ask"`를 더하고 브리지를 다시 띄우면 예전처럼 보낸다
- 관리자 309가 main에 합침(e9d5247, 18:49:07 브리지 다시 띄움). 화면 이름표 한 줄(`render.js` `manager_ask: '관리자 부탁'`)은 관리자 허락으로 따로 커밋 `9499739`

## ② 보고를 관리자에게 · ③ 묻는 말은 관리자가 중계만 · ④ 하루 한 번 묶음

스위치는 `config/notify.toml` `[projects.<이름>]`의 `relay_reports` · `relay_questions` · `digest` — **모두 false로 넣었다**. 켜기는 관리자가(FOREMAN · 인프라). ② · ③은 `config/managers.toml [managers] enabled`도 켜져 있어야 한다(지금 true).

### 한 일
- `bridge/managers.py` `relay(project, kind, from_session, label, body)` — 그 프로젝트 원본 폴더의 역할 manager 입력 칸에 넣는다(`ask`와 같은 `deliver`).
  머리 「[작업 보고 — 세션 N 「제목」(coder) → foreman 관리자]」 · 「[사람에게 올릴 물음 — …]」, 끝에 안내 한 줄
  (물음: 「이 물음에 관리자가 답하지 않습니다 — 판단은 사람이 합니다. 다른 물음과 모아 사람에게 올리고, 사람의 답을 그 세션에 전합니다」).
  관리자마다 잠가 동시에 둘이 붙여 넣지 않는다. 기록은 session_action `mgr-relay`. 텔레그램은 스스로 보내지 않는다(부른 쪽이 정함).
  `Managers`가 만들어질 때 `notifier.managers = self`로 스스로 걸어 main.py를 고치지 않았다
- `bridge/assembler.py` — 그 두 머리로 연 관리자 턴은 출처 `relay`(사람 입력으로 세지 않음)
- `bridge/notify.py` 턴 끝 판정:
  - 역할 coder · scribe · designer 세션의 턴이 지금 규칙으로 보낼 턴이면, 마지막 응답이 묻는 말(대시보드 `ask_line` — 「답 기다림」과 같은 판정, 읽기만)이고 `relay_questions`면 물음으로, 아니고 `relay_reports`면 보고로 관리자에게 넘긴다(DB 트랜잭션 밖, 60초 안)
  - 넘겼으면: 그 턴은 묶음(`digest` 켬) 또는 안 보냄(`skipped relayed:report|question`). 물음을 넘긴 턴도 급하지 않게 본다 — 관리자가 올린다
  - 관리자가 있는데 못 넣었으면: 「⚠ 관리자에게 넘기지 못했습니다 — 사유」를 붙여 바로. 관리자가 없으면(펫퍼민트 · 지금의 런슈즈 밖) 지금처럼
  - 출처 `relay`(관리자가 받은 보고 · 물음으로 연 턴)는 `origins`와 상관없이 판정한다 — 관리자가 사람에게 올리는 길이 이것이다. 관리자 응답이 묻는 말로 끝나면 급한 것이라 바로 나간다
- ④ 묶음: 일상 알림을 `notification.decision = 'digest'`로 남기고, 1분마다 도는 고리가 `[digest] at`(기본 21:00, Asia/Seoul)이 지났고 그날 아직 안 보냈으면 프로젝트마다 한 통(종류별 · 시각 순, 3,500자 넘으면 「외 N건」). 보낸 것은 `bundled`, 묶음 한 통은 kind `digest` · rule `digest:<날짜>:<프로젝트>`
  - **DB 스키마는 바꾸지 않았다** — 있는 `notification` 표에 decision 값 `digest` · `bundled`와 kind `digest`만 더했다(VARCHAR(8) 안). 표에 프로젝트 칸이 없어 **글 머리의 접두어(`[FOREMAN]` 등)로 프로젝트를 가른다** — 모든 알림 글이 그 접두어로 시작한다
  - 묶음을 끈 프로젝트도 모아 둔 것이 남아 있으면 그 시각에 내보낸다(끄는 순간 갇히지 않게)
- 조용한 고장 막기: 묶음 전송 실패 → 그날 한 번 「⚠ 하루 묶음을 보내지 못했습니다(사유) — N건이 남아 있고 10분마다 다시」 바로 + 10분마다 다시. 모아 둔 것 중 가장 오래된 것이 `late_h`(26시간) 넘으면 「⚠ 하루 묶음이 26시간 넘게 나가지 않았습니다」 그날 한 번. 고리는 예외를 삼키고 다음 분에 다시 돈다. `[digest] at` · `tz`가 틀리면 `load_rules`가 실패해 브리지가 뜨지 않는다(조용히 다른 시각에 보내지 않게 — toml 문법 오류와 같은 꼴)

### 급한 것(바로) · 일상(묶음) 목록
- 묶음(`[digest] kinds`): 턴 끝 「끝남」(turn · stop) · 서브에이전트 묶음(batch, 실패가 없을 때) · 합치기 카드(merge) · 옮기기 요약 · 결정 문서 적기(handoff) · Notion 문서 ✋ 덮지 않음(docsync) · 끝난 뒤 어긋남(recon)
- 바로:
  - 턴 끝 중 API 오류 · 중단 · 세션 종료 · 프로세스 사라짐(`URGENT_REASONS`), **사람에게 묻는 말로 끝난 턴**(관리자에게 물음을 넘긴 것은 빼고)
  - 위 kinds에 없는 종류 전부: 승인 대기(approval) · 승인 시간 지남(appr_to) · 권한 거부(denied) · 응답 없음(stall) · 파이프라인 · 배포 대기(pipeline · syncwait · argorun) · 사용량(usage) · 적재(ingest) · 자동 기상(wake) · 겹침(overlap) · 맥락 · 압축 · 전환 권유(context · compact · switch) · 스키마 잠금 · 규칙 파일(schlock · rulefile) · 관리자 부탁 실패(manager) · 게시 실패(publish) · ! 명령(bang) · 브리지 안 오류(direct) · 묶음 자체의 실패(digest)
  - kinds에 있어도 글에 ⚠ · ❌ · 🛑 · ⏰ · ❓가 있는 것(예: 「⚠ Notion 기술문서 자동 게시 실패」 · 「⚠ Notion 게시 설정」 · 합치기 실패)
- 맥락 · 압축 · 겹침은 실패는 아니지만 하루 늦으면 소용이 없어(압축 전에 옮기기 · 같은 일 겹침) 바로로 두었다. 바꾸려면 `kinds`에 더한다

### 설계와 달랐던 점
- 「일꾼 보고」 대신 **「작업 보고」** — `docs/style_guide.md` 4-1이 화면 글에 「일꾼」을 새로 쓰지 않게 한다(관리자 입력 칸 · 대화 패널에 보이는 글)
- 보고를 넘긴 턴의 텔레그램: 묶음이 꺼져 있으면 **안 보낸다**(관리자가 받았다). 대신 관리자 쪽 relay 턴이 지금 규칙대로 나가므로 사람이 받는 수는 일꾼 몫이 관리자 몫으로 옮겨 갈 뿐이다 — 줄이려면 `digest`를 같이 켠다
- 묶음 자리를 새 표로 만들지 않았다(위). 마이그레이션 없음
- 하루 묶음은 `tg.send`를 바로 부른다(대기열 밖) — 결과(성공 · 실패)를 보고 `bundled`로 바꿔야 해서

### 남은 것 · 묻는 것
- **`render.js` `ORIGIN_LABEL`에 `relay` 이름표가 없다** — 대화 패널에 `relay` 글자로 보인다. 맡은 파일 밖이라 넣지 않았다(제안: `relay: '작업 세션 보고'`)
- 관리자 relay 턴이 띄운 서브에이전트 묶음 알림 판정(`_batch` 진행 중 턴 판정이 `human` · `meta`만 본다)은 그대로
- 실제 관리자 입력 칸에 넣는 것(deliver)은 가짜로만 시험했다 — 켠 뒤 첫 보고에서 관리자 화면 · session_action `mgr-relay`를 본다

### 시험
- `tests/test_stage2_db.py` 8개(보고 넘김 · 물음 넘김 + relay 출처 · 관리자 없음 · 넘기기 실패 바로 · 관리자 역할 안 넘김 · 묶음 모음/급한 것 바로/한 통 · 묻는 턴 바로 · 묶음 실패 알림/다시/26시간 늦음), `tests/test_managers.py` relay 1개
- 전체 pytest 770 통과 · node 123 통과

### 되돌리는 법(② ~ ④)
- 끄기만: `config/notify.toml`의 세 칸을 false로(지금 기본) → 브리지 다시 띄우기. 남아 있던 `digest` 알림은 그날 `[digest] at`에 한 번 나간다(묶음을 꺼도 남은 것은 내보낸다)
- 코드째: 이 커밋 `git revert`. DB에 남은 decision `digest` · `bundled` · kind `digest` 행은 그대로 둬도 된다(옛 코드는 읽지 않는다). 남은 `digest` 행을 바로 보고 싶으면 `SELECT … FROM notification WHERE decision = 'digest'`

## README에서 뺄 줄
- 「나중에 할 일」에 승인 지옥 줄이기(알림 · 중계) 줄이 있으면 ①~④를 뺀다. 남길 것: 「런슈즈 켜기(관리자 생긴 뒤)」 · 「render.js relay 이름표」
