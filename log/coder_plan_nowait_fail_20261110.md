# 코더 foreman-4 — 계획에서 「확인을 기다려라」 빼기 · 계획 받기 실패 다루기 (2026-11-10)

브랜치 `cc/foreman-4`, 커밋 3개(push 안 함 · 브리지 다시 띄우지 않음). 합친 뒤 브리지를 다시 띄워야 서버 쪽(일 1 프롬프트 · 일 2(나))이 적용된다.

## 일 1 — 「확인을 기다려라」 빼기 (`6a2e1bb`)

- 문구가 있던 곳(Grep '시작하기 전에 사용자의 확인' · '확인을 기다려' · '5줄'):
  - `bridge/foreman.py` 디스패처 프롬프트 6번 항목 "끝에 「이해한 것을 5줄 안으로 말하고, 시작하기 전에 사용자의 확인을 기다려라.」" → "받으면 바로 시작하게 쓴다. 확인을 기다리라는 말은 붙이지 마라"로 바꿈. 일 중에 사람이 정할 것(운영 적재 · push 등)에서 멈추라는 말은 '지켜야 할 것'에 남긴다고 적음
  - **브리지가 first_prompt에 덧붙이는 곳이 따로 있었다**: 교장 계획이 인계 모드(summary_id)면 `HandoffManager._finish_spawn`이 first_prompt 뒤에 `inject_prompt`(인계 글)를 붙이는데, 그 글 끝이 "(3) 다음 할 일을 시작하기 전에 사용자의 확인을 기다려라"였다 → `inject_prompt(confirm=False)` 판을 만들어 교장 경로에서만 「바로 시작하라」로 넣음
  - 계획 카드 없이 인계만 하는 [새 세션으로 옮기기]의 인계 글은 그대로 둠(이 일의 까닭인 "계획 카드에서 이미 봤다"가 해당하지 않는다). 2판 인계의 "(1) 규칙 2줄 (2) 문서와 다른 지금" 말하기도 교장 경로에 남김(읽은 것 확인용)
- 관리자: 역할 프롬프트 · CLAUDE.md · 메모리에 "확인을 기다려라" 문구가 없었다. 그래서 CLAUDE.md 작업 규칙에 한 줄 더함 — "일을 받으면(교장 지시서든 사용자가 직접 말한 것이든) 확인을 기다리지 않고 바로 시작한다. 위 규칙이 먼저 묻게 한 것(sudo · 재부팅 · 다른 세션 요청의 설정 바꾸기 등)은 그대로 묻는다"
- `docs/11_foreman_dispatch.md` 「6. 포먼이 틀리면」의 해당 줄 고침. 지난 dispatch · 세션 기록 · `log/` · `bridge/static/demo/stills.json`(데모 그림의 옛 first_prompt)은 고치지 않음
- 시험 `tests/test_no_wait_prompt.py` 3개: 디스패처 프롬프트에 그 줄이 없음 · 교장 경로 인계 글에 「확인을 기다려라」 · 「5줄」이 없고 머리(인계 알아보기)는 그대로 · 인계 단독은 그대로 기다림

## 일 2(가) — 계획 없이 [버리기] (`dd1a59e`)

- **왜 disp가 null인 채 버리기 길로 들어갔나**: `panel.css`의 `.fm-plan { display:flex }`가 `hidden` 속성을 덮었다. 그래서 `reset()`(창을 열 때) · `ask()`(계획을 받을 때)가 `fmPlan.hidden = true`를 해도 지난 계획 카드가 그대로 보였다. 창을 다시 열면 `reset()`이 `disp = null`로 만들고, 계획 받기가 실패해도 옛 카드가 남아 있어 그 [버리기]가 `disp.dispatch_id`에서 터졌다. 새로고침해야 사라진 것도 같은 까닭(카드를 지우는 코드가 없었다)
- 고친 것(`foremanchat.js` · `panel.css`):
  - `.fm-plan[hidden] { display:none; }`
  - `clearPlan()` — disp와 카드(숨김 + 내용 비움)를 함께 치움. `reset()` · `ask()` 시작 · `load()`에서 계획이 없을 때 부름
  - `dropAction(disp)` — 계획이 있고 `planned`일 때만 서버에 버림을 적고, 아니면 서버 없이 카드만 치움. 실패한 계획은 서버에 이미 `failed`로 남으니 버릴 것이 없다
  - `ask()`가 받은 값을 성공한 뒤에만 disp에 넣음(전에는 구조 분해 대입), 묻는 중 Ctrl+Enter · [다시 물어보기]가 겹치지 않게
  - 모듈 끝 DOM 붙이기는 `document`가 있을 때만(node 시험에서 불러오려고)
- 시험 `tests/js/foremanchat_drop.test.mjs` 3개(버리기 판단 · CSS 규칙)
- 화면 점검: worktree 미리보기(:8247, `bridge.preview`)를 직접 띄워 `tools/screen.py --base http://127.0.0.1:8247/ --no-term` — 세 테마 × 세 크기 × 두 너비 **문제 0건**, 페이지 오류 0, 종료 코드 0. 점검 뒤 미리보기 끔. 라이브 :8000 셸 창은 건드리지 않음

## 일 2(나) — 실패 원인 가르기 (`d985d06`)

- `bridge.foreman.diagnose(종료 코드, 답, stderr, json)` → 종류 · 자세히. 화면 글(`FAIL_WHY`):
  - `limit` 「사용량 한도에 막혔습니다」 — 답 · stderr에 usage limit · hit your limit · rate limit 등, 또는 `api_error_status` 429
  - `call` 「claude 호출이 실패했습니다」 — 종료 코드 ≠ 0 또는 `is_error`
  - `empty` 「답이 비어 있습니다」 · `noblock` 「답에 계획(JSON)이 없습니다」 · `broken` 「답의 형식이 깨졌습니다」
- 화면: "계획을 받지 못했습니다 — 답의 형식이 깨졌습니다. 다시 물어보거나 직접 골라 주세요"
- 남기는 것: `dispatch.error`에 "원인 [종류] — 자세히 + 답 앞부분 400자", 깨짐이면 JSON 오류 · 줄 · 칸과 그 자리 앞뒤 60자. 브리지 로그 `계획 받기 실패 dispatch=N [종류] …`. 둘 다 `Masker`로 비밀값을 가림
- 시험 `tests/test_foreman_fail.py` 6개(정상 · 빈 답 · 형식 깨짐 · JSON 없음 · 한도 문구 · 호출 실패)

### 11-10 실패 건(읽기만)

- dispatch **237**(11:55:41, foreman, 사람 요청 "교장 계획에서 「확인을 기다려라」 빼기", 269자)
- `usage_extra`: 출력 **1,675토큰**(앞뒤 계획 2,287~3,014토큰과 같은 규모) — 사용량 한도 · 출력 잘림이 아니고 끝까지 나온 답이다
- 남은 error 앞 300자는 ```json 블록과 첫 칸들(project · mode · role · title)이 멀쩡하다 → `parse_plan`이 JSON을 읽지 못한 것 = 「답의 형식이 깨졌습니다」
- 어디가 깨졌는지는 원문이 300자만 남아 확정할 수 없다. 요청 글에는 큰따옴표가 없었다. 그때 디스패처 프롬프트의 그 문구가 `"이해한 것을 5줄 안으로 … 기다려라."`처럼 큰따옴표로 싸여 있었고, 바로 그 문구를 빼는 일의 first_prompt였으니 따옴표를 이스케이프 없이 옮겼을 가능성이 크다(추정). 이제는 깨진 자리 앞뒤가 남는다

## 시험

- `.venv/bin/python -m pytest -q` — **572 passed, 1 skipped, 1 warning**(84초, 다른 pytest 없음을 확인하고 돌림)
- `node --test tests/js/` — **87 pass, 0 fail**

## 관리자에게

- 합친 뒤 브리지를 다시 띄워야 디스패처 프롬프트 · 인계 덧붙임 · 실패 원인이 적용된다(화면 js · css는 새로고침)
- 이번에 CLAUDE.md에 한 줄 더함(관리자 지시 받기) — 합칠 때 원본 CLAUDE.md와 겹치지 않는지 확인
