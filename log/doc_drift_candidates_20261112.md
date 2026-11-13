# 문서 차이 후보 목록 — 합침 알림 「고치지 않은 문서」 + 관리자가 뽑은 것 (2026-11-12 오후, 원본 폴더, 관리자 276 인계 세션)

사용자 지시: 4번(문서 차이 맞추기)은 지금 하지 않는다. 304 · 305 · 307 후보를 채워 목록이 다 차면 한 번에 한다. **목록만 — 문서는 고치지 않았다.**

## 어디서 찾았나

- 합침 알림은 브리지가 관리자 입력 칸에 넣은 글이라 지난 관리자 세션(1a8675b5) 대화 파일에 남아 있다(`bridge/mergeprep.py` 703 「이번에 바뀐 파일을 적었는데 고치지 않은 문서: …」). 시각(UTC → KST)을 브리지 다시 띄운 시각과 맞춰 세션을 정했다
- 알림의 판정은 「기록 · 커밋에 그 문서가 다룬 파일 이름이 나오는데 이번에 그 문서를 안 고침」이다 — 낱말이 걸린 것도 섞인다. 그래서 바뀐 파일을 직접 보고 관리자 판단을 붙였다

## 세션별 알림

| 세션 | 알림 시각(KST) | 알림의 후보 |
|---|---|---|
| 287 | 11-11 17:21 | `11_foreman_dispatch` · `10_office_design` · `11_worktree` · `operations` — **11-11 17:39 ~ 17:41 서기가 맞춤**(`docs_four_sync_20261111.md`) |
| 291 | 11-11 17:58 | `11_foreman_dispatch` · `operations` · `10_office_design` · `11_handoff` · `style_guide` |
| 290 | 11-11 18:13 | `11_worktree` · `operations` (operations는 19:11 `6037178`로 시험 DB 반영) |
| 297 | 11-11 19:08 | `style_guide` · `12_scribe` · `14_dispatcher_note_wake` |
| 286? | 11-11 19:22 | `11_worktree` · `11_foreman_dispatch` · `style_guide` · `12_scribe` |
| 302 | 11-12 12:17 | `style_guide` · `11_foreman_dispatch` · `10_office_design` · `11_handoff_v2` · `operations` |
| **304** | 11-12 14:00 | `style_guide` · `11_foreman_dispatch` · `operations` · `10_office_design` · `11_handoff_v2` |
| **305** | 11-12 14:45 | `12_scribe` |
| **307** | 11-12 15:09 | `12_scribe` · `operations` |
| **319** | 11-13 11:0x | `10_office_design` · `11_foreman_dispatch` · `operations` · `11_worktree` · `style_guide` — 머리 위 표시 · escalate API(`580c6d7`, `log/overhead_marks_20261113.md`). 적어도 `10_office_design` 「합치기 기다림」 · 머리 위 말풍선과 `operations` 「5.」 중계 · 묶음은 실제로 바뀜 |
| **320** | 11-13 11:2x | 카드 줄 번호: `10_office_design` 147 · 148 · 149 · 151 · 152 · 156 / `11_foreman_dispatch` 140 · 141 / `11_worktree` 92 / `operations` 24 / `style_guide` 97 — 「사용자에게 보고함」 · 지도 「사용자 답 기다림 N」 · 서브에이전트 ··· 뺌 · RELAY_GRACE 30초(`622d6a1`) |
| **321** | 11-13 11:3x | `operations` 23 · 112 / `10_office_design` 147 / `11_worktree` 142 — 합치기 카드 DB(`merge_card` 0032, 72시간, `4159f5d`). 6-1의 「6시간」 · 「메모리」 설명이 바뀜 |
| **322** | 11-13 12:0x | `10_office_design` 147 · 148 · 149 · 151 · 152 · 156 / `11_foreman_dispatch` 107 · 130 · 132 · 140 · 141 / `11_worktree` 92 · 142 · 147 · 153 / `operations` 23 · 24 · 112 / `11_handoff` 20 — 사람 승인 카드는 관리자 머리 위 「사용자 답 기다림」(브리지가 escalate), `merge-prep docs_done`, 「관리자에게 보고함」이 이김(`b70018b`, `log/merge_wait_to_manager_20261113.md`). 6-1 「카드가 보이는 곳」 · 「합치기 기다림」 말풍선 설명이 바뀜 |

**11-13 323(서기)이 위까지 맞춤(`1e8e4c9`).** 아래는 그 뒤 합친 것 — 다음 서기 몫:

| 세션 | 알림 시각(KST) | 후보 |
|---|---|---|
| **325** | 11-13 12:2x | `11_worktree` 30 · 51 · 147 · 155 / `11_foreman_dispatch` 109 · 132 · 134 / `10_office_design` 153 / `11_handoff` 20 / `operations` 23 — 미리보기 살아 있음 확인(`/__foreman_preview`, 죽었으면 다시 띄움 · 「죽어 있습니다」, `691487e`, `log/preview_alive_20261113.md`). 실제로 바뀐 것은 `11_worktree` 미리보기 절 |
| **324** | 11-13 12:3x | `operations` 23 · 95 · 115 · 116 / `10_office_design` 149 · 154 · 176 / `11_worktree` 135 · 142 / `11_handoff_v2` 79 / `style_guide` 106 — 사람이 끈 합치기 물음은 막대 숫자에서도 뺌 · 5일째 텔레그램(`remind_days`, `28911c6`, `log/merge_wait_off_remind_20261113.md`). 실제로 바뀐 것은 `11_worktree` 6-1 · `operations` 「5.」 표 |
| **326** | 11-13 13:3x | `operations` 23 · 115 / `10_office_design` 149 / `11_worktree` 142 — 브리지가 꺼져 있던 동안 7일이 지나 사라진 합치기 물음도 다시 뜰 때 한 번 알림(`2552526`, `log/merge_remind_catchup_20261113.md`). `config/handoff.toml remind_days = 5`를 적음(`49e2eed`). 실제로 바뀐 것은 `11_worktree` 6-1 · `operations` 「5.」 표의 5일 알림 줄 |

- 같은 글의 알림은 한 번만 셌다. 19:22 알림은 시각으로 286 합침과 가깝지만 확실하지 않다(`?`)

## 바뀐 파일로 본 판단(304 · 305 · 307 중심)

| 문서 | 걸리는 것 | 판단 |
|---|---|---|
| `docs/12_scribe.md` 「5.」 | 305 덮기 줄 · ✋, 307 저장소 설정을 잃으면 멈춤 | **이미 맞춤** — 304는 스스로(`853ae1b`), 305 · 307은 관리자가 `2395477`에서 줄을 더함(123 ~ 126줄). 알림은 그 세션 브랜치 기준이라 떴다 |
| `docs/operations.md` 26줄(설정) | `handoff.toml [move] one_flow` · `managers.toml` · `tokens.toml`을 **「꺼짐」으로 적음** — 11-11 저녁에 켰다(`enable_c_wave2_20261111.md`). `handoff.toml [merge_prep]` projects에 ronanlab-infra 없음. `.foreman/notion.toml`(저장소 게시 설정) · `.run/notion_repo_config.json`(307 기억) · `.env.notion` 언급 없음 | **맞출 것**(304 · 307 · 켜기) |
| `docs/operations.md` 「5. 알림」 표 | Notion 쪽 알림 줄이 없다 — 사람 수정 멈춤 · 한 쪽 게시 ✋(305) · 게시 멈춤 🛑 / 다시 돎(307) · 저장소 설정 깨짐(304) | **맞출 것** |
| `docs/11_foreman_dispatch.md` 152 ~ 162줄 | 「설정 스위치 뒤에 꺼져 있는 것 — 하나도 켜지 않음」, 표의 값이 모두 `false` — 지금은 토큰 · 관리자 · 넘기기 켜짐. 156줄 「프로젝트 토큰은 그 프로젝트 세션 · 방 API만」 — 304부터 자기 프로젝트 `POST /api/publish` · `GET /api/publish?project=` · `/api/publish/pair`도 연다(force · docsync는 관리 토큰만) | **맞출 것**(켜기 · 304) |
| `docs/11_worktree.md` 6-1 | `projects = ["foreman"]` → 지금 `["foreman", "ronanlab-infra"]`. 카드 받는 사람이 저장소마다 갈린다(인프라 → 299) | **맞출 것**(사용자 지시로 4번에 같이) |
| `docs/style_guide.md` · `docs/10_office_design.md` · `docs/11_handoff_v2.md` · `docs/11_handoff.md` · `docs/14_dispatcher_note_wake.md` | 304 · 305 · 307이 화면 · 인계 · 깨우기를 건드리지 않았다(바뀐 파일은 `bridge/notion.py` · `notioncfg.py` · `docsync.py` · `api/publish.py` · `scopetoken.py` · `main.py` · `config/notion.toml`). 291 · 297 · 302 알림의 것은 그 세션 일을 보고 따로 판단해야 한다 | **약함** — 304 · 305 · 307 쪽은 낱말 겹침으로 보인다. 291 · 297 · 302 몫은 그때 서기가 확인 |

## 한 번에 할 때

- 서기(sonnet, worktree)를 교장 경로로 띄워 실제 코드를 보고 맞추게 한다 — 11-11 `docs_four_sync`와 같은 방식, 문서마다 커밋 하나
- 맡길 것: 위 「맞출 것」 넷 + 「약함」 다섯을 291 · 297 · 302 일과 대어 확인
