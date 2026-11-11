# 문서 넷을 지금 코드에 맞추기 (서기, worktree foreman-4, 2026-11-11)

287 합침 알림의 「이번에 바뀐 파일을 적었는데 고치지 않은 문서」 넷(`docs/11_foreman_dispatch.md` · `10_office_design.md` · `11_worktree.md` · `operations.md`)을 실제 코드를 보고 맞췄다. 코드 · 설정 · 시험 · README는 고치지 않았다. 브랜치 `cc/foreman-4`, push 안 함.

시작할 때 겹침 확인: `git worktree list`(main · foreman-2 · foreman-3 · foreman-4 모두 `8b9e0a5`), 각 브랜치 `git diff --name-only main...<브랜치>` 비어 있음, 각 worktree `status --short` 깨끗 → 맡은 파일이 다른 두 세션과 겹치지 않아 그대로 시작했다.

## 커밋 (문서마다 하나)

| 커밋 | 문서 |
|---|---|
| `67082e2` | `docs/11_worktree.md` |
| `528b741` | `docs/11_foreman_dispatch.md` |
| `7450587` | `docs/10_office_design.md` |
| `a6976cb` | `docs/operations.md` |

## 문서별 결과 (넷 모두 어긋난 곳이 있어 「어긋남 없음」은 없다)

### `docs/11_worktree.md` — 고침
- 「6.」 뒤에 **「6-1. 합치기 준비」** 한 절을 더했다(전에는 합치기 카드가 이 문서에 한 줄도 없었다). 켜져 있음(`enabled = true`, `projects = ["foreman"]`, `stage = 1`), 카드를 만드는 때(턴 끝 + 60초 훑기), 카드 상태 · API(`GET /api/merge-prep`, `POST /api/sessions/{sid}/merge-prep` merge · skip · refresh), 충돌이면 세션에 「main을 가져와 풀라」, 조용한 고장 알림, 정리 후보 점수(286), 카드가 보이는 곳(287 → office_design), 끄는 법
- **관리자는 늘 원본 폴더 · 하나**(11-11 아홉)
- 본 곳: `config/handoff.toml:13`(enabled) · `bridge/mergeprep.py:193`(`doc_candidates` 점수) · `:284`(상태 목록) · `:498`(`check_one(via="turn_end")`) · `bridge/api/handoff.py:110-135`(merge-prep API) · `bridge/handoff.py:816`(관리자 worktree 거절) · `:863`(`will_worktree(role=…)`) · `:888`(`manager_conflict`) · `bridge/static/js/handoff.js:55-61`(후보 접기 · 「이번에 안 고침」)

### `docs/11_foreman_dispatch.md` — 고침
- §9-1 「`/api/spawn`은 기록을 남기지 않는다」가 틀려졌다 → 11-11부터 `record_direct`로 `spawn` · `move`도 `dispatch`에 남는다고 고침(약속이라는 점은 그대로)
- §9-3 할 일 넷: ① · ④는 됐다고 덧붙임(② · ③은 README에 남음 — README `:902` 줄을 확인)
- §10 관리자: 늘 원본 폴더 · 하나
- 새 **§11** 한 절: 여러 세션(`sessions[]`, 최대 6, 0030), 맡을 파일 겹침 경고, 받은 할 일에서 바로(#8), 그리고 **꺼진 기능 다섯과 켜는 법**(표 + 켜는 법 줄)
- 본 곳: `bridge/foreman.py:174`(`MAX_SESSIONS`) · `:205`(`sessions_of`) · `:519`(관리자 worktree 끔) · `bridge/api/foreman.py:93-100`(`/handover`) · `:110`(`record_direct`) · `:143`(`/merge-order`) · `bridge/api/handoff.py:260,338`(`record_direct` 부르는 곳) · `bridge/api/todo.py:14-21`(`PUT /api/todo/{iid}`) · `bridge/managers.py:36-48` · `bridge/handover.py` 머리말 · `config/tokens.toml:11` · `config/managers.toml:9,17` · `config/roles.toml:11` · `config/handoff.toml:31`

### `docs/10_office_design.md` — 고침
- 「관리자 자리 · 이름표 · 머리줄」 뒤에 **「머리 위 말풍선 · 승인 막대」** 한 절: 합치기 기다림 말풍선(보라 `#c9a7ff`, `P.merge`), 겹침 기준(권한 거부 > 답 기다림 > 합치기 기다림 > 보고 옴), 승인 막대 「🔀 합치기 대기 N」, 대기 = `ready`만, 라이브 확인 결과
- 나머지(구상 · 에셋 조사 · 코더 상주 · 관리자 · 디자이너 자리)는 코드와 어긋남을 찾지 못해 건드리지 않았다. 단 아래 「확인 못 한 것」
- 본 곳: `bridge/api/dashboard.py:298`(`merge_waits`) · `bridge/static/js/render.js:62-75`(`needMark` · `mergeWaits`) · `bridge/static/js/office.js:2039`(`markColor`), `:3077`(`#oMerge`), `:3333-3340`(클릭)
- **디자이너 세션이 고치는 중**: 막대를 누르면 코드 주석(`office.js:3335`)과 `render.js:68`의 툴팁은 「세션」 탭이라고 하지만 라이브에서는 「대화」 탭이 열린다(`log/merge_merge_wait_20261111.md`). 카드를 **버리면** 최대 1분 남는다. 둘 다 막대 디자이너가 바꾸는 중이라 **지금 main 코드 기준으로 적고 문서에 그 사실을 밝혀 두었다.** 그 세션이 합쳐지면 이 두 문장을 고쳐야 한다

### `docs/operations.md` — 고침
- §2 구조: 브리지 파일 줄에 `mergeprep.py` · `managers.py` · `handover.py` · `scopetoken.py` · `roleguard.py` · `terminal.py`, 설정 줄에 `handoff.toml` · `managers.toml` · `tokens.toml` · `roles.toml`(켜짐 / 꺼짐 / 관찰 표시) · `wake` · `usage` · `portfolio` · `notion`(전에는 빠져 있었다), `.env.project_tokens`
- §3: 프로젝트 토큰 만들기, **터미널 스크롤 · 끌어 고르기**(11-11 휠 → `mouse on`이 끌기를 가져가 `mouse off` + 화면이 휠을 보냄) 한 묶음
- §4: **역할 권한(관찰)** 한 줄
- §5 알림 표: 합치기 카드 알림, 계획 넘긴 뒤 안 띄움 알림 두 줄
- 본 곳: `deploy/shell/foreman-term-view:31`(`mouse off`) · `bridge/terminal.py:435`(`SCROLL_ACTIONS`) · `bridge/static/js/terminal.js:197-219`(휠) · `bridge/roleguard.py` · `bridge/mergeprep.py:456,559,609,623,666,735`(알림 규칙 키) · `bridge/handover.py:137` · `bridge/managers.py:152`

## 꺼진 기능은 꺼져 있다는 것과 켜는 법을 적었다 (`docs/11_foreman_dispatch.md` §11 표 · 켜는 법 줄)

| 기능 | 스위치 | 문서에 적은 상태 |
|---|---|---|
| 토큰 범위 | `tokens.toml [project_tokens] enabled = false` | 꺼짐 |
| 프로젝트별 관리자 | `managers.toml [managers] enabled = false` | 꺼짐(목록은 읽힘 · 부탁 503) |
| 계획 넘기기 | `managers.toml [handover] enabled = false` | 꺼짐 |
| 역할 권한 | `roles.toml [roles] mode = "observe"` | **관찰 — 막지 않고 기록만** |
| 옮기기 한 흐름 | `handoff.toml [move] one_flow = false` | 꺼짐 |
| 합치기 준비 | `handoff.toml [merge_prep] enabled = true`, `projects = ["foreman"]`, 1단계 | **켜짐** |

- 켜는 법은 `log/coder_c_wave2_20261111.md` 「켤 때 차례」 · 「합친 뒤 관리자가 할 일」에 있는 것만 옮겼다(토큰 · 관리자 다섯 단계, `[handover]` · `[move]` 켜 볼 때 확인, 역할 권한 하루 관찰 뒤 enforce는 사용자)
- **「기능 사이에 무엇을 먼저 켤지」와 「enforce로 켠 뒤 무엇을 볼지」는 지어내지 않고 「정해지지 않았다」고 적었다**

## 체크리스트
- [x] 문서 넷을 하나씩 보고 결과를 적었다(넷 모두 고침 — 「어긋남 없음」 문서는 없음)
- [x] 고친 곳은 실제 코드를 보고 맞췄다(위 「본 곳」 파일:줄)
- [x] 꺼진 기능은 꺼져 있다는 것과 켜는 법이 적혔다
- [x] 문서마다 커밋을 나눴다(4개)
- [x] 커밋 묶는 기준에 대한 의견을 아래에 적었다

## 커밋 묶는 기준에 대한 의견 (한 줄)
문서마다 하나로 나눈 것이 알맞았다 — 문서마다 근거 코드가 달라 한 커밋에 묶으면 되돌릴 때 문서 하나만 빼기 어렵고, 합치기 알림의 「고치지 않은 문서」 목록과도 1:1로 맞는다(다만 한 문서의 고침이 두 줄뿐이면 다른 문서와 묶어도 무방해 보인다).

## 설계와 달랐던 점 · 판단 근거
- 「새 절을 크게 더하지 않는다」였지만 `docs/11_worktree.md`에는 합치기 카드 설명이 아예 없어 **6-1을 한 절** 더했다(`docs/11_foreman_dispatch.md` §11도 같다). 줄이면 켜는 법 · 꺼진 기능 상태가 문서에 안 남는다
- 그 앞 11-11 합친 것 중 **터미널 휠 · 끌어 고르기**는 넷 중 맞는 문서가 `operations.md` 「3. 돌리기 · 확인」뿐이라 거기에 넣었다
- 교장 여러 세션은 `docs/11_foreman_dispatch.md`에 넣었다(§9-3 할 일 ①이 이미 그 문서에 있었다)

## 확인 못 한 것 · 남은 것
- `docs/operations.md` 「3.」의 「서기 세션은 아직 tmux 세션 `foreman-bridge` 안에 있다」와 CLAUDE.md 「브리지(tmux `foreman-bridge`)」는 서로 다르게 읽힌다(브리지는 11-06부터 systemd 유닛). 지금 실제를 보지 않아 **고치지 않았다**
- `docs/operations.md` 「2.」 시험 줄(「두 세션이 동시에 돌리지 않는다」)은 시험 DB 코더가 시험 DB를 가르는 중이라 건드리지 않았다. 그 일이 합쳐지면 맞춰야 한다
- `docs/10_office_design.md` 「코더 상주…」 표의 자리 · 좌표와 도형 테마 설명은 코드 대조를 하지 않았다
- 합치기 카드 텔레그램(`notify_ready`)이 실제로 나갔는지는 `log/mergeprep_on_20261111.md`에서도 확인 못 했다고 적혀 있어 그대로 옮겼다
- 시험은 돌리지 않았다(문서만 바꿈)

## 지킨 것 · 어긴 것
- 파일은 Edit · Write로만 고쳤다. Bash는 읽기 · `git add` · `git commit`만. push · 브리지 다시 띄우기 안 함
- **진행 글이 한 번 영어로 흘렀다**(도구 호출 사이 두 줄 — hook이 알려 바로잡음). 11-05 · 11-11 286과 같은 실수다

## 되돌리는 법
- 문서별: `git revert 67082e2`(11_worktree) · `528b741`(11_foreman_dispatch) · `7450587`(10_office_design) · `a6976cb`(operations) — 서로 다른 파일이라 순서와 상관없이 따로 되돌릴 수 있다. 코드 · 설정은 건드리지 않았으니 브리지 재시작 필요 없음

## README에서 뺄 줄
없음(README는 고치지 않았다).
