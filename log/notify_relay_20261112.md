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
