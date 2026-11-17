# 11 — 세션 인계 · 세션 조작 (설계, 2026-11-05)

로드맵 11단계 중 "세션 인계"를 먼저 한다(런슈즈 세션이 730MB · 17일째 · auto-compact 17번 — 사용자 판단으로 앞당김).
캐릭터 재배치 · 포먼 채용은 11단계에 남는다.

## 결정 (11-05 사용자)

- 요약은 **그 세션 자신이 쓴다**(컨텍스트를 들고 있는 당사자). 별도 LLM을 부르지 않는다
- 죽은 세션 요약(headless resume)은 **버튼을 누를 때만** — 토큰을 쓴다
- 새 세션에 넣기 전에 **요약을 보여주고 확인받는다**
- 런슈즈 적용은 미룬다 — **버리는 세션으로 한 바퀴**(짧은 대화 → 요약 → 확인 → 새로 띄우기) 돌린 뒤
- CC 프롬프트 제안(회색 플레이스홀더)은 켜 둔다. 빈칸 · 공백만인 입력은 보내지 않는다

## 1. 요약 요청 프롬프트

브리지가 기존 입력 경로(방법 C — 붙여넣기 + Enter)로 보낸다. `r=`은 요청 ID(6자 hex).

```
[FOREMAN 인계 요청 r=7f3a9c]
(본문 — bridge/handoff.py REQUEST_PROMPT)
<<<FOREMAN-HANDOFF r=7f3a9c>>>
## 목표 · 맥락 / ## 한 일 / ## 진행 중 · 미완 / ## 다음 할 일 / ## 주의 / ## 참고
<<<END r=7f3a9c>>>
```

- 파일을 고치거나 커밋 · 배포하지 않는다. 읽기(git status · log)는 된다
- 승인 대기 · 돌고 있는 서브에이전트 · 타이머는 반드시 적는다
- 직전 인계를 받고 시작한 세션이면 그 내용도 지금 기준으로 **갱신**한다(이어 쓰기가 아니라) — 그래서 주입은 늘 최신 하나만
- 4000자 안

## 2. 돌아온 요약 받기 — 일반 응답과 구분

- 프롬프트 첫 줄 `[FOREMAN 인계 요청 r=…]` → 조립기가 그 턴을 `origin='handoff'`로 단다
  - 알림 규칙(`origins = human, meta`)에 없으므로 보통의 "끝남" 텔레그램은 나가지 않는다. 대신 "[런슈즈] 인계 요약 저장 (n자)"
  - 대화 목록에서 "인계 요청"으로 보인다
- 브리지가 보낸 직후의 트랜스크립트 offset부터 **assistant 줄의 text 블록만** 읽어 `<<<FOREMAN-HANDOFF r=X>>> … <<<END r=X>>>`의 마지막 짝을 꺼낸다
  - 표지는 프롬프트에도 있다 — user 줄은 보지 않는다. `r=`이 같아야 하므로 다른 턴 · 인용된 예시와 섞이지 않는다
- 그 턴이 닫혔는데 표지가 없거나 10분이 지나면 `failed` · `timeout` + 응답 원문(raw)을 남긴다
- **실패 알림은 바로 간다**(11-17 사용자, 「실패는 묶어서 늦게 알 이유가 없다」). 종류 `handoff`는 `config/notify.toml [digest] kinds`에 있어 묶음을 켠 프로젝트면 성공(「인계 요약 저장」, 「새 세션에 인계 넣음」)은 21:00 묶음으로 간다. 실패는 `HandoffManager._notify(fail=True)`가 글 앞에 ⚠를 달고 `later=False`로 보내 묶음을 켠 프로젝트여도 바로 나간다
  - 바로 가는 것: 「⚠ 인계 요약 실패, 표지가 없습니다」, 「⚠ 인계 요약 실패, 기다리는 중에 세션이 끝났습니다」, 「⚠ 인계 요약 시간 초과」, 죽은 세션(`claude -p --resume`)의 「⚠ 죽은 세션 인계 요약 실패, 표지가 없습니다」, 「… claude를 띄우지 못했습니다」, 「⚠ 죽은 세션 인계 요약 시간 초과」
  - 세션이 끝남과 죽은 세션 실패 셋은 전에는 알림이 없었다(뒤에서 돌아 화면을 떠난 사람이 몰랐다). 요청을 보내지 못한 실패(입력 칸에 못 넣음)는 버튼을 누른 사람에게 바로 돌려주므로 알림을 더하지 않았다 [log:foreman-5_fail_now_unpriced_20261117.md]

## 3. 세션이 응답 못 하는 상태

| 상태 | 처리 |
|---|---|
| 일하는 중(busy) | 대기열에 넣지 않는다 — 거부("작업이 끝난 뒤에"). 일 중간에 끼면 작업과 섞인다 |
| 정지(T) | 거부. FOREMAN이 멈춘 세션이면 "되살리기" 뒤에 |
| tmux 밖 | 주입 불가 — 아래 죽은 세션 방법만(프로세스가 살아 있으면 그것도 불가) |
| 죽음(프로세스 없음) | ① 버튼: `claude -p --resume <id>`로 같은 프롬프트(같은 컨텍스트를 불러 그 세션이 쓴다, fork 아님). 그 세션을 잡은 살아 있는 프로세스가 없을 때만 ② 버튼: 마지막 auto-compact 요약(CC가 쓴 것) + 그 뒤 프롬프트 · 마지막 응답(`source=compact`) |
| 컨텍스트 가득 | CC가 먼저 압축하고 답한다. 그래도 실패하면 ② |

사람이 직접 `/exit`한 세션은 그 순간 요약을 받을 수 없다(SessionEnd 때는 이미 답할 수 없다) — 패널에 ①②.

## 4. 새 세션에 넣기 · 분량

- **새로 띄우기**: tmux 세션 `cc-<프로젝트>-<n>`을 원래 세션 cwd로 만들고 `claude`(resume 아님). 입력 칸이 뜨면 인계 프롬프트
  `[FOREMAN 인계 r=…] 직전 세션 <id>의 인계다 …`를 기존 입력 경로로. 트랜스크립트에 턴으로 남아 무엇을 넘겼는지 보인다
- **넣기 전에 확인**: 패널이 넣을 글 전체를 보여주고 [넣고 시작]을 눌러야 띄운다
- **분량**: 넣는 글 8000자 상한. 넘으면 진행 중 · 미완 · 다음 할 일 · 주의는 전부, 한 일 · 맥락 · 참고는 각 절 앞부분만 넣고
  전체는 `~/.foreman/handoff/<id>.md`에 두고 "전체는 이 파일을 Read하라"를 붙인다
- 폴더 신뢰 창(처음 보는 cwd)이 뜨면 넣지 않고 알린다 — 사람이 답할 것

## 5. 세션 조작

| 버튼 | 하는 일 | 조건 |
|---|---|---|
| 지금 요약 | 1~2 (`kind=snapshot`) | tmux 안 · 살아 있음 · IDLE |
| 요약하고 끝내기 | 요약 저장 → 사람이 확인 → `/exit`(슬래시 명령 경로) | 같음 |
| 끝내기 | `/exit`만 | tmux 안 · IDLE |
| 새로 띄우기 | 4 | 프로젝트 cwd |
| 멈춤 | pane에 `Ctrl+Z`(사람이 멈추는 것과 같은 키) | tmux 안 · IDLE · 포그라운드가 claude |
| 되살리기 | pane에 `fg` + Enter | **FOREMAN이 멈춘 것만**(session_action 기록), pane 포그라운드가 셸, 그 pid가 T |
| 작업 중단 | pane에 `Escape` | 일하는 중일 때 |

- 멈춤 · 되살리기를 `kill -STOP/-CONT`로 하지 않는 이유: 셸이 멈춘 작업을 배경으로 돌리므로 밖에서 CONT를 보내면 배경에서 돌다 터미널을 읽으려는 순간 다시 멈춘다. 사람이 하는 키(Ctrl+Z · fg)를 그대로 쓴다
- 사용자가 남겨 둔 정지 CC 4개(pts/7 · pts/8, tmux 밖)는 FOREMAN이 멈춘 것이 아니므로 되살리기가 열리지 않는다(CLAUDE.md 규칙)
- 모든 조작은 `session_action`에 남긴다(누가 · 무엇을 · 결과)

## 6. 테이블 (0014)

```
summary          id, character_id, session_id, req, kind(handoff|snapshot), source(self|self_headless|compact|edited),
                 status(requested|ok|failed|timeout), turn_id, body, chars, raw, parent_id, injected_cc_session, injected_at, created_at
session_action   id, session_id, action, pid, ok, detail, created_at
```

고치기는 덮어쓰지 않고 `source=edited` · `parent_id=원본`으로 새 행. 넣을 때는 그 세션의 마지막 `ok` 행.

## 7. API

- `GET  /api/sessions/{id}/summaries` — 이력(최근 순)
- `POST /api/sessions/{id}/summary` `{kind, mode: live|headless|compact}`
- `PUT  /api/summaries/{id}` `{body}` → 새 행(edited)
- `GET  /api/summaries/{id}/injection` — 넣을 글 미리보기(분량 처리 뒤)
- `POST /api/sessions/{id}/spawn` `{summary_id|null}` — 같은 cwd로 새 세션
- `POST /api/sessions/{id}/action` `{action: exit|stop|resume|interrupt}`

## 8. 압축(auto-compact)으로 잃은 것

- 트랜스크립트 파일에는 압축 전 원문이 **그대로 남는다**(CC는 파일을 지우지 않고 요약 줄을 더할 뿐). 잃는 것은 모델의 컨텍스트이지 기록이 아니다
- 그래서 "무엇을 잃었나"는 압축 구간마다 원문(사람 프롬프트 · 결정 · 파일 경로 · 커밋)과 그 구간을 대신한 요약을 맞대 보면 안다 — 결과는 log/stage11_handoff_result.md
- 인계 요약은 세션이 **지금 기억하는 것**으로 쓴다 — 이미 잃은 것은 스스로 되살리지 못한다. 보완하려면 원문에서 사람이 한 지시 · 결정을 뽑아 세션에게 "요약에 빠진 게 있나" 대조시킨다(다음 할 일)
