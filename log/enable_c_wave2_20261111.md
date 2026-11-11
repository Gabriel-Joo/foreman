# 286(C 2물결) 기능 켜기 — 토큰 → 관리자 → 넘기기 → 옮기기, 하나씩 (2026-11-11 저녁, 원본 폴더, 관리자 276)

앞 기록: [merge_token_docs_20261111.md](merge_token_docs_20261111.md). 켜는 차례 · 켠 뒤 볼 것: [coder_c_wave2_20261111.md](coder_c_wave2_20261111.md) 「켜는 차례 · 켠 뒤 볼 것」(관리자가 코드를 보고 채움). 사용자 지시: 하나씩, 켤 때마다 승인 대기 0 → 브리지 → 볼 것 → 기록, 이상이면 그것만 끄고 멈춤. 역할 권한 막기는 켜지 않음.

## 1. 토큰 범위 — 이상 없음

- `python -m bridge.scopetoken new ronanlab-infra` → `.env.project_tokens`(권한 600, git 밖)에 `FOREMAN_TOKEN_RONANLAB_INFRA`(값 출력 없음). 첫 토큰을 인프라로 한 까닭: 관리자를 실제로 띄울 첫 프로젝트(사용자)
- `config/tokens.toml enabled = true` → 승인 대기 0 → 브리지 19:31:10(PID 1322212), 오류 없음

| 본 것 | 결과 |
|---|---|
| 관리 토큰 `GET /api/dashboard` | 200 |
| 인프라 토큰 `GET /api/dashboard` | **403** — 「프로젝트 토큰(ronanlab-infra)은 이 API(GET /api/dashboard)에 닿지 않습니다 — 관리 토큰(FOREMAN_API_TOKEN)이 필요…」 |
| 인프라 토큰 `GET /api/managers` | 200 |
| 인프라 토큰 `GET /api/sessions/265/handoff`(인프라 세션) | 200 |
| 인프라 토큰 `GET /api/sessions/276/handoff`(FOREMAN) | **403** |
| 틀린 토큰 | 401 |
| 브리지 로그 「프로젝트 토큰 거절」 | 2줄, 그 안에 인프라 · 관리 토큰 값 0(`/usr/bin/grep -cF`) |

## 2. 프로젝트별 관리자 — 이상 없음(관리자는 띄우지 않음)

- `config/managers.toml [managers] enabled = true`(`projects = []` 그대로 — 모든 프로젝트) → 승인 대기 0 → 브리지 19:31:54(PID 1326163), 오류 없음
- `GET /api/managers` `enabled: true` — **관리자 자리 넷**: runshoes · petmint-rag-chatbot · ronanlab-infra 「관리자가 없습니다 — 부탁을 보내면 텔레그램으로 남깁니다」, foreman → 세션 276 「FOREMAN admin」
- 부탁(`/ask`)은 보내지 않았다(관리자가 없는 곳은 텔레그램으로 간다 — 확인용으로 알림을 만들지 않음)
- **펫퍼민트 b7(tmux `cc-petmint-rag-chatbot-2`) 영향 없음**: 켜기 전후 화면 해시 같음(`b672bee0d8d3`), 펫퍼민트 대화 파일 셋의 시각 · 크기 같음, 브리지 로그에 넣기 · 부탁 줄 0

## 3. 계획 넘기기 — 이상 없음(넘기지는 않음)

- `config/managers.toml [handover] enabled = true` → 승인 대기 0 → 브리지 19:32:21(PID 1328881), 오류 없음
- 기동 로그 「계획 넘기기 켬: 넘긴 뒤 15분 안에 시작하지 않으면 알림」
- `GET /api/foreman/handover`: `enabled: true` · `wait_min: 15` · `health: {ok: true}` · `managers: {runshoes: null, petmint-rag-chatbot: null, foreman: 276, ronanlab-infra: null}`
- **못 본 것**: 계획 카드의 [관리자에게 보내기] 단추(관리자 있는 FOREMAN은 켜짐, 없는 곳은 꺼짐 + 툴팁) — 카드를 띄우려면 교장 계획을 새로 받아야 해(비용) API로만 확인. 실제 넘기기 · 15분 알림도 하지 않음(넘기면 관리자 276 입력 칸에 계획이 들어가고 감시가 돈다)

## 4. 옮기기 한 흐름 — 이상 없음(옮기지는 않음)

- `config/handoff.toml [move] one_flow = true` → 승인 대기 0 → 브리지 19:32:46(PID 1331051), 오류 없음(이 스위치는 파일을 다시 읽어 브리지가 필요 없지만 지시대로 다시 띄움)
- `GET /api/sessions/{sid}/handoff`의 **`controls.move_flow`**: 276 `True` · 265 `True`. 처음에 응답 맨 위에서 찾아 `None`으로 보였다 — 칸이 `controls` 안에 있다(`handoff.py` 432 `controls()`), 관리자 읽기 실수
- 점검 화면(`probe=1`)으로 276 패널 「세션」 탭: [새 세션으로 옮기기]의 툴팁이 한 흐름 것(`MOVE_TIP` 「…압축으로 잊은 것을 찾고, 문서에 넣을 후보를 보여 드립니다. 고르시면 문서에 쓰고…」), 페이지 오류 0. 단추는 꺼짐 — 276은 일하는 중인 관리자 세션이라 요약을 만들 수 없는 때(`can.summary`). 누르지 않음(누르면 잊은 것 찾기 비용 · 새 세션)

## 켜지 않은 것

- 역할 권한: `config/roles.toml mode = "observe"` 그대로(바뀐 줄 없음), 마지막 기동 로그 「역할 권한 observe: worktree-push, bash-file-edit, manager-code, scribe-code」

## 지금 스위치

| 칸 | 값 |
|---|---|
| `tokens.toml [project_tokens] enabled` | true(토큰: ronanlab-infra 하나) |
| `managers.toml [managers] enabled` · `projects` | true · `[]`(넷 모두) |
| `managers.toml [handover] enabled` | true |
| `handoff.toml [move] one_flow` | true |
| `handoff.toml [merge_prep]` | true · `["foreman"]` · 1단계(앞서 켬) |
| `roles.toml [roles] mode` | observe |

- 되돌리기: 그 칸을 false로(역할은 그대로) + 승인 대기 0 뒤 브리지 다시 띄우기 — `coder_c_wave2_20261111.md` 「되돌리는 법」. 토큰을 끄면 프로젝트 토큰은 401, 관리 토큰은 그대로
