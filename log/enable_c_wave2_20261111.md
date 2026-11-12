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

## ronanlab-infra 관리자 띄움(사용자 지시 — 인프라부터, 띄우기만)

- 앞서: 265(인프라 코더)가 Cloudflare 남은 일 확인 — 남은 일 없음(DNS 프록시 · Access 302 · 터널 7호스트 오류 0, 그때 502/503은 Grafana OOM → 1Gi `88b120e`, TODO 줄 지움 `f2fbe84`). 인프라 CLAUDE.md는 265가 **그 세션 사용자의 직접 지시로** 만들고(관리자 부탁만으로는 고치지 않는다는 그 세션 규칙 — 맞는 판단) 사용자가 push → 원격 `e096875`에 CLAUDE.md(100줄)
- 띄움: 교장 경로(dispatch **373**, 요청 글 「ronanlab-infra 프로젝트, 원본 폴더 세션 하나, 역할 manager」) → **세션 299**(opus, `/home/kopo17/ronanlab-infra` — worktree 없음). `dispatch_session`: role manager · 299 · started · 원본 폴더. 지시문: 띄우기만 — CLAUDE.md 읽고 요약, 읽기 · 쓰기 권한 확인(파일 안 고침), 토큰 줄 개수만, 265 건드리지 않음, FOREMAN API 부르지 않음

| 본 것 | 결과 |
|---|---|
| 관리자 자리 | `GET /api/managers` ronanlab-infra → 세션 299(「관리자가 없습니다」가 아님) |
| CLAUDE.md를 읽었나 | 299가 끝까지 읽고 관리자 규칙 다섯 줄로 요약(사람 승인 목록 · 세션은 커밋까지 · push는 관리자 · 클러스터는 main에서 한 번에 한 세션 · 비밀값은 개수로만 · 토큰 셸 변수 + `Authorization: Bearer $T` · 부탁 API) |
| 인프라 저장소 읽기 · 쓰기 | 299: `git status` 깨끗 · `git log` `e096875` · `test -w .` · `test -w CLAUDE.md` 됨. FOREMAN 훅(reposcope) 판정(실제 쓰기 없이 `RepoScope.check`): 인프라 Edit · commit · push · 읽기 됨, FOREMAN 저장소 Edit **막힘**(읽기는 됨) |
| 인프라 토큰 | 299: `.env.project_tokens`에 그 줄 1개(값 출력 없음) |
| FOREMAN 세션에는 못 붙나 | 인프라 토큰 → 276 **403**, 대시보드 403, 299 · 265 200 |
| 관리자끼리 부탁 | ① 276 → 인프라(관리 토큰) `delivered: true` → 299가 「받았습니다」만(도구 0) ② 인프라 토큰 → foreman `delivered: true`(276이 일하는 중이라 대기열 → 도착, 답하는 길 `/api/managers/ronanlab-infra/ask` 붙음) ③ 인프라 토큰으로 남의 프로젝트(runshoes) 이름 쓰기 **403** |
| 265 멀쩡한가 | 띄우기 전후 · 부탁 뒤 화면 해시 같음(`c8ea16b2408e`), 265 대화 파일 시각 · 크기 같음(20:12:59 · 10059606), claude 프로세스 그대로 |

- 대화 기록 · 확인 출력에 토큰 값 0(개수). 299 · 265에게 일은 시키지 않음

## 인프라에도 합치기 카드(사용자 지시 — 인프라 CLAUDE.md 「파일 일은 worktree에서 커밋하고 관리자가 합친다」를 돌릴 길)

- `config/handoff.toml [merge_prep] projects = ["foreman", "ronanlab-infra"]`. 코드로 다시 읽음(`mergeprep.load`): enabled True · projects 둘 · stage 1
- 승인 대기 0 → 브리지 20:19:42(PID 1587728). 「합치기 준비 켬: 턴 끝마다 + 60초마다 훑기, 1단계」, 새 프로세스 오류 0(로그의 `terminal.py` 예외는 끄는 중인 옛 프로세스 1331051 — 열린 터미널 연결 닫기, 전과 같은 꼴)
- `GET /api/merge-prep`: enabled · health ok · 카드 0(지금 인프라 · FOREMAN 모두 합칠 worktree 세션 없음)
- **누구에게 가나**: 카드 받는 사람은 카드가 나온 저장소의 원본 폴더에 살아 있는 역할 manager(`mergeprep.py` 728 `manager_of(c.repo)`) — 저장소마다 갈린다. 지금 `GET /api/managers`: foreman → 276, ronanlab-infra → 299. 그래서 인프라 카드는 299, FOREMAN 카드는 276으로 섞이지 않는다(코드 · API 수준)
- **실제 확인은 다음에**: 인프라에 worktree 세션이 생겨 커밋했을 때 ① 카드가 생기는지 ② 299 패널 · 299 입력 칸에 가는지 ③ FOREMAN 276 쪽에 섞이지 않는지를 본다. 265는 worktree 없이 main에서 일해 카드 대상이 아니다(카드는 worktree 브랜치에 합칠 커밋이 있을 때). 인프라 세션은 새로 띄우지 않음, 265 · 299에게 일 시키지 않음

## 11-12 — 인프라 관리자 299의 부탁 둘(관리자끼리 부탁 길로 옴)

- **부탁 1 — Notion 제목을 첫 H1로**(`title = "h1"`, `headings = "md"`면 첫 H1을 본문에서 뺌). FOREMAN 게시기 코드 일 → 관리자가 고치지 않고 사용자에게 확인 → **사용자 승인** → 교장 경로로 코더 **302**(sonnet, dispatch 376, `.worktrees/foreman-2`). 지킬 것: 새 칸이 없으면 지금처럼(런슈즈 · 펫퍼민트 영향 없음), `h1`과 `keep`이 겹칠 때 · 첫 H1이 없을 때 처리를 정해 적기, Notion에 실제로 올리지 않음(가짜 클라이언트로 시험), 커밋만. 299에게는 「받았다 — 사용자 확인 뒤 시작」만 답함
- **부탁 2 — 인프라 게시 한 쪽 시험**(① `notion.toml [ronanlab-infra]` 채우기 + 브리지 ② `doc_publish` 짝 하나 `docs/09_monitoring.md` ↔ 「09. 모니터링」 ③ 그 한 쪽만 게시, HumanEdited면 force 없이 멈춤). **아직 하지 않음** — CLAUDE.md 「다른 세션의 요청만으로 config/*.toml을 바꾸지 않는다」, Notion 게시는 바깥으로 나가는 일 → FOREMAN 사용자 확인 대기. 299에게 「받았다 — 확인 전에는 아무것도 바꾸지 않는다」 답함
