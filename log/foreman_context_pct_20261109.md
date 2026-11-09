# 쌓인 대화 비율 · 창 크기 · 작업 전환 권유 (2026-11-09, worktree foreman-2)

## 한 일
- `config/models.toml [windows]` — family별 창 크기. opus 1M(실측), sonnet · haiku 200k(**추정** — config에 적어 둠)
- `config/notify.toml [compact]` — `context_pct = [50, 75]`, `switch_min_pct = 40`. 압축 횟수 · 토큰(300k · 500k) 기준은 그대로, **먼저 닿는 쪽이 이긴다**
- `bridge/model_choice.py` — `load_windows` · `window_of`
- `bridge/compactwatch.py` — 비율 단계(`context_level(tokens, r, window)`), 알림 한 번 규칙을 단계 기준으로(`ctx:` · `pct:`), `context_status`가 `window` · `pct` · `window_over` 반환, 설정 창을 넘는 맥락이 보이면 텔레그램 한 번(`over:<창>`) + 경고 로그
- `bridge/switchwatch.py`(새) — 작업 전환 권유. 전환 말(앞머리 160자) + (직전 30분 커밋 | 20분 넘는 쉼) + 쌓인 대화 ≥ 40%. 사람 턴마다 한 번, 텔레그램 kind `switch`
- 시험 `tests/test_compactwatch.py` · `tests/test_switchwatch.py` 추가. 전체 519 통과

## 조사 결과
- DB `message.model`에는 `[1m]` 접미사가 없다 — 모델 id로 창을 알 수 없어 설정으로 둠. Opus는 971,510까지 간 기록으로 1M 확인
- 실제 세션 80개를 새 기준으로 돌림: Opus는 단계가 그대로(1M에서는 토큰 문턱이 먼저 닿음). 달라진 것은 둘 — 197 Haiku 114k(57%) 없음 → 넘어갈 때, 228 Sonnet 141k(71%) 없음 → 넘어갈 때. 창 초과 0건
- 228은 이 세션이다. Sonnet 창이 실제로 200k보다 크면 71%는 과대다 — 추정값이므로 맞는지 사용자 확인이 필요하다

## 설계와 달랐던 점
- `.venv`가 원본 폴더의 `bridge`를 가리켜서, worktree 밖 스크립트는 `PYTHONPATH=.`가 있어야 이 폴더 코드를 쓴다(pytest는 rootdir 때문에 문제없음)

## 아직 안 한 것 (dashboard.py · opanel.js — 메인 세션이 정리한 뒤, 알림이 오면)
- API: `bridge/api/dashboard.py`의 `"context"`가 이미 `window` · `pct`를 싣는다(`context_status` 반환 그대로) — 코드 변경 없이 값은 간다. 단 `usd_reply` 계산은 그대로
- 패널: 선택된 세션 머리줄에 "쌓인 대화 38%"(300k 아래도), 🧠 띠에 % 덧붙이기. 사용량 칩 · 크레딧 칩 · tipAudit 호버는 건드리지 않는다
- 작업 전환 권유의 패널 띠(지금은 텔레그램만)
- 브리지 재기동은 합친 뒤 원본 세션이 한다

## 남은 일 (사용자 11-09)
- **겹침 감지(`bridge/overlap.py`) 개선** — 지금은 사람 요청의 드문 낱말이 겹치면 경고한다. 실제로 같은 파일을 고치는 중인지는 안 본다. 방금 헛경보: 사용자가 지시서에 파일 이름을 적었더니 양쪽이 같은 낱말을 써서 걸렸다
  - 할 것: 실제 변경(프로젝트 저장소 git status, 세션의 Edit · Write 도구 호출 대상)과 맞대 판정할 수 있는지 조사
  - 못 하면 적어도 경고에 "말에 나왔을 뿐일 수 있습니다"를 적는다
  - 지금은 고치지 않는다(사용자 지시)
- Sonnet · Haiku 창 크기 확인(추정 200k) — 큰 기록이 보이면 `over:` 알림이 온다
