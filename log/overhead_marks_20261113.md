# 캐릭터 머리 위 표시 다시 설계 — 2026-11-13 (코더 cc/foreman-2, 관리자 318 일감)

사용자 결정: 사람이 봐야 하는 것은 **관리자 머리 위에만**. 작업 세션(코더 · 서기 · 디자이너)은 관리자에게 넘긴 것을 **작게만**.
머리 위 글자는 사용자 지시 그대로 — 관리자 「사용자에게 보고함」 · 「사용자 답 기다림」, 작업 세션 「관리자에게 보고함」 · 「관리자 답 기다림」.

## 한 일

### 1. 사람에게 올리기 API — `POST /api/sessions/{sid}/escalate {"kind": "report" | "question", "text": "…"}`
- `bridge/api/dashboard.py` `escalate` · `escalate_api`. **역할 manager 세션만**(아니면 403 + 「작업 세션은 관리자에게 보고하면 됩니다」), 숨긴 세션은 404
- 프로젝트 토큰 범위: 이미 있는 `/api/sessions/{sid}[/…]` 줄(그 세션이 이 프로젝트 것일 때)이 그대로 맡는다 — scopetoken은 안 고쳤다
- 저장: **스키마 안 바꿈.** `session_action` 'escalate'(detail = `"<kind>:<글 앞부분>"`, 512자), `created_at`은 `UTC_TIMESTAMP(3)`으로 직접(사람 입력 `turn.started_at`과 비교)
- 사라질 때
  - report: 사람이 그 관리자 패널을 열면 `POST /api/sessions/{sid}/escalate-read?id=` → 'esc-read'(report-read와 같은 방식, 점검 화면 `x-foreman-probe`는 세지 않음)
  - question: 사람이 그 관리자에게 입력(human 턴이 escalate 뒤에 시작) 또는 [답 안 해도 됨](`asks-off`가 asks가 없으면 escalate 물음을 끔 → 'esc-off')
  - 사람이 입력하면 보고도 함께 내린다(그 대화를 보고 있다). 둘 다 종류마다 마지막 하나만, 7일 지난 것은 안 본다
- 알림: question은 「❓ 관리자가 사용자 답을 기다립니다」로 **바로**. report는 「📋 관리자 보고」로, 그 프로젝트가 `digest = true`면 **하루 묶음**(`send_direct(..., later=...)`를 새로 받게 함 — `[digest] kinds`에 없어도 묶음. 묶음 제목 「관리자 보고」)
- 관리자가 알게: 중계 글(`managers.relay_text`) 끝 안내에 `escalate_hint` 한 줄 — 관리자 세션 id까지 넣은 부르는 법 + 「응답 글만으로는 사람 화면에 뜨지 않습니다」. 머리(`[작업 보고 — ` · `[사람에게 올릴 물음 — `)는 그대로라 조립기의 출처 relay 판정은 안 바뀐다

### 2. 판정(`human_needs`) — 역할 · 턴 출처 · 중계 기록을 본다
- 관리자: 마지막 응답의 턴 출처가 `relay` · `manager_ask`면 「답 기다림」 · 「보고 옴」을 내지 않는다. `human` 턴은 지금처럼
- 작업 세션(coder · scribe · designer): 알림이 그 턴을 관리자에게 넘긴 결과를 **작업 세션 쪽에도** `session_action` 'relay-out'(detail `"<kind>:<turn_id>"`, ok)으로 남기게 했다(`notify._relay_out` — 성공 · 실패 · 예외 모두)
  - 같은 턴 · 같은 종류 · ok → `relayed`(사람용 asks · report 대신)
  - ok=0(넘기지 못함) · 기록 없음 · 묻는 말인데 보고로 넘김(relay_questions 꺼짐) → **지금처럼 사람에게**
  - 중계가 켜진 프로젝트는 응답 뒤 `RELAY_GRACE`(150초 — settle 2초 + 넘기기 제한 60초 + 여유) 동안 아무것도 안 띄우고 넘기기를 기다린다. 그 뒤에도 기록이 없으면 사람에게
- 스냅샷에 `relayed` · `escalate` 칸. `escalate`는 관리자가 일하는 중이어도 남는다(사람이 읽거나 답할 때까지)

### 3. 알림 — 관리자 중계 턴의 「묻는 말」은 급함으로 치지 않음
- `notify._decide_inner`: 역할 manager · 출처 relay/manager_ask 턴은 `ask_line`을 보지 않는다 → 턴 끝 알림 자체는 지금처럼 나가되(묶음을 켰으면 묶음) 급함은 escalate 물음(❓)이 맡는다. 화면과 알림이 같은 신호를 쓴다

### 4. 화면
- `render.js needMark` 순서: 권한 거부 > 답 기다림 > **사용자 답 기다림**(노랑) > 합치기 기다림 > **사용자에게 보고함**(초록) > 보고 옴 > **관리자 답 기다림 · 관리자에게 보고함**(tone `quiet`)
  - `humanNeed`에 「사용자 답 기다림」(배지 · [답 안 해도 됨] 버튼). quiet는 humanNeed에 넣지 않아 배지는 쉼 그대로
- `office.js`
  - quiet: 방에서는 작은 글씨(`tpx(10)`, 사람 몫은 12) · 흐린 색(`P.muted`), [전체] 지도에서는 작은 회색 점(반지름 1.5, 사람 몫 2.5)
  - **멈춘 턴 「…」은 빨강**(`P.bad`, 테마 그림 `e_…`은 안 씀) — 자식 일 기다림의 파란 「· ·· ···」과 갈림
  - **기다림 가르기**: 서브에이전트 = 파란 상자에 차오르는 「· ·· ···」, 뒤에서 도는 명령(백그라운드 Bash · Monitor)만 = 어두운 상자 · 파란 테두리에 도는 막대 「| / - \」, 둘 다 = 파란 상자 「··|」. 호버에 「서브에이전트 N개 돎 — 머리 위 「···」」 · 「뒤에서 도는 일 N개 — 머리 위 어두운 상자의 도는 막대」, 멈춘 턴은 「끝났는지 모름(빨간 「…」) — … 」
  - 방 머리줄 「답 기다림 N」에 escalate 물음도 센다
- `opanel.js` 관리자 패널을 열면 escalate 보고 읽음, `store.js escalateRead`
- 시연 장면 `bridge/static/demo/overhead_marks.json`(FOREMAN 관리자 물음 · 코더 보고함/답 기다림 · 서기 보고함 · 서브에이전트/뒤 명령 기다림 · 멈춘 턴, 인프라 관리자 보고 · 코더 답 기다림)

## 확인
- `pytest` 전체 796 통과(1 건너뜀) — 새 `tests/test_overhead_marks.py` 6개(관리자 relay/manager_ask 턴 안 띄움 · human은 그대로, 작업 세션 넘김 성공/실패/종류 다름, 기다림 시간 · 중계 꺼짐, escalate 관리자만 · 묶음/바로 · 읽음 · 끔 · 사람 입력, 중계 글 안내, relay-out 기록). 실제 `config/*.toml`은 읽지 않는다
- `node --test tests/js/` 128 통과 — 새 `overhead_marks.test.mjs`(글자 그대로 · 순서 · quiet · 배지)
- 화면: 미리보기(:8212, 이 worktree 화면 + 지금 브리지 데이터)에서 `tools/screen.py --demo overhead_marks --views foreman,ronanlab-infra,map --no-term`
  - **세 테마 × 1920x1080 · 1366x768 · 1024x700 × 좁게/넓게 = 18 조합 × 세 화면 모두 문제 0건**(gridAudit · layoutAudit · labelAudit · nameAudit · cardAudit · tipAudit · propAudit · 페이지 오류 0), 화면마다 `bubbleAudit()` 0건
  - 사진으로 확인: 가장 좁은 마법학교 1024x700 넓게에서도 「사용자에게 보고함」이 잘리지 않고, 「관리자 답 기다림」은 작게. 오피스 1366에서 빨간 「…」 · 파란 「···」 · 어두운 상자 「/」가 갈려 보임
  - 시연에서 FOREMAN 방 세션 7개 중 마지막(986 멈춘 턴)은 방 자리 수(cap) 때문에 그려지지 않는다 — 전부터 그런 동작이고, 빨간 「…」은 앞 회차(983 자리일 때) 사진으로 봤다

## 설계와 달랐던 점 · 판단 근거
- **중계 성공을 작업 세션 쪽에 따로 남겼다**: 지금 'mgr-relay'는 관리자 세션 id로, 보낸 세션은 detail 글 안에만 있다. 글을 파싱하면 「글자 하나 틀리면 안 먹는」 같은 문제가 생겨 `relay-out`(작업 세션 id · 턴 id)을 새로 둠. 액션 이름 12자 칸 안
- **넘기는 동안(최대 150초) 표시를 안 띄움**: 안 그러면 넘기기 전 몇십 초 동안 사람용 「보고 옴」이 떴다가 바뀐다. 넘기지 못하면 기다림이 끝나는 대로 사람에게 뜨므로 묻히지 않는다. 대가: 중계가 켜진 프로젝트에서 relay가 아예 안 도는 턴(출처가 `origins` 밖 등)은 사람 표시가 최대 2분 30초 늦다
- **관리자 relay 턴 끝 알림은 끄지 않았다**: 끄면 관리자가 escalate를 잊었을 때 아무 데도 안 남는다. 급함 판정만 escalate로 옮겼다
- **escalate 보고 묶음은 `[digest] kinds`와 따로**: 실제 `config/notify.toml` kinds에 'escalate'가 없어도 「묶음을 켠 프로젝트면 묶음」이 일감 문구라 부르는 쪽이 정함(설정 파일은 안 고침)
- 스키마 · `config/*.toml` · CLAUDE.md는 안 고쳤다

## CLAUDE.md에 넣을 규칙 줄 안(사람 승인 뒤 관리자가)
- 「작업 세션의 보고 · 물음은 관리자에게만 간다. **관리자는 사람에게 올릴 것을 `POST /api/sessions/{자기 세션 id}/escalate {"kind": "report"|"question", "text": "…"}`로 올린다** — 응답 글로 쓰기만 하면 사람 화면(관리자 머리 위 「사용자에게 보고함」 · 「사용자 답 기다림」)에도 알림에도 뜨지 않는다. 물음은 바로 알림, 보고는 묶음을 켠 프로젝트면 21:00 묶음」
- (런슈즈 · 펫퍼민트 · 인프라 관리자 규칙에도 같은 줄 — 그 저장소 CLAUDE.md는 그 관리자가)

## 되돌리는 법
- 이 커밋 하나를 `git revert`. DB에 남은 'escalate' · 'esc-read' · 'esc-off' · 'relay-out' 행은 읽는 코드가 없어지면 아무 일도 안 한다(지울 필요 없음)
- 합친 뒤 브리지를 다시 띄워야 서버 쪽(판정 · API · relay-out 기록)이 돈다 — 원본 세션이

## 사람이 정할 것
1. 위 CLAUDE.md 규칙 줄을 넣을지(FOREMAN · 인프라 관리자부터)
2. `RELAY_GRACE` 150초가 괜찮은지 — 짧게 하면 넘기기가 늦을 때 사람용 표시가 잠깐 떴다 바뀐다
3. [전체] 지도 방 카드 글(「멈춤 — 답 기다림 N」)이 escalate 물음도 같이 센다. 「사용자 답 기다림」으로 따로 쓸지
