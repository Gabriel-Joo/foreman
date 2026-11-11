# 교장 ① 여러 세션 계획 · ④ 모든 띄우기 기록 · 일곱 맡을 파일 · 합칠 순서 · 같은 파일 헛경보 (2026-11-11, 코더 C1 — worktree foreman-3)

계획: [plan_structure_20261111.md](plan_structure_20261111.md) 「1물결 — C1」.

## 한 일

| 커밋 | 무엇 |
|---|---|
| `a399081` | `bridge/overlap.py` — 같은 파일 헛경보 고침 · 합칠 순서 판정 `merge_order` |
| `dbde093` | `migrations/0030_dispatch_session.sql` · `bridge/foreman.py` · `bridge/api/foreman.py` · `bridge/api/handoff.py`(기록 몇 줄) — ① · ④ · 일곱 |
| `c569632` | `bridge/static/js/newsession.js` — + 새 세션 창에 「맡을 파일」 칸 |
| `9e5f064` | 세션이 둘 이상이면 경고 줄에 [시작]이 띄울 세션을 모두 적음(지금 카드는 첫 세션만 보인다) |

### ① 한 계획에 여러 세션
- 계획 JSON에 `sessions[]` — 세션마다 `role · model · title · first_prompt · read_only · worktree · files(맡을 파일) · merge_order · on`. 최대 6
- 교장 지시문(INSTRUCTIONS) 10번 `sessions` — 기본 하나, 여럿은 사람이 개수를 말했거나 맡을 파일이 안 겹치게 나눌 때만, 여럿이면 각 첫 글에 맡을 파일과 「밖은 묻는다」
- **옛 계획 · 옛 카드 그대로 읽힘**: `sessions`가 없으면 위쪽 칸(role · title · first_prompt …)으로 하나를 만든다(`sessions_of`). 위쪽 칸은 늘 `sessions[0]`과 같게 둔다(`_mirror`). 옛 카드(`foremanchat.js`)는 위쪽 칸만 고쳐 보내므로 `sessions_edit`가 없으면 위쪽 칸이 첫 세션을 이긴다. 세션별로 고치는 카드는 `sessions_edit: true`를 보낸다
- [시작](`start`) — 켠 세션을 차례로 `spawn_new`. 둘째부터 worktree 기본 켬(첫 세션이 살아 있게 되니). handoff 요약은 첫 세션에만
  - 첫 세션이 못 뜨면 거절 — 아무것도 안 띄운 것이라 계획은 `planned`로 남아 다시 누를 수 있다(전과 같음)
  - 둘째부터 못 뜨면 띄운 것은 두고 `out.failed` · `out.note`(화면) + **텔레그램 한 번**(`api/foreman.py` `alert`)
  - 결과 `out.sessions[]`(세션마다 session_id · tmux · worktree · model · error). 위쪽 키(session_id · tmux …)는 첫 세션 것 — 옛 카드 글이 그대로 돈다
- `dispatch_session`(0030) — 세션마다 한 줄(`started` · `failed` · `off`), 맡을 파일 · 합칠 순서 · 세션 번호 · cwd. `dispatch.session_id`는 첫 세션(옛 읽는 쪽 그대로)
- 보내기(attach)는 하나만 — 둘째부터 끄고 경고

### ④ 모든 띄우기가 dispatch 기록
- `foreman.record_spawn` — 계획 카드와 같은 모양(sessions 한 칸)으로 `dispatch` + `dispatch_session`. `origin` 값 둘 추가: `spawn`(`POST /api/spawn` — + 새 세션 창 · 관리자) · `move`(`POST /api/sessions/{sid}/spawn` 옮기기)
- `/api/spawn` 몸에 `files` · `request`(무엇을 하려는지, 기록용) 칸 추가. 실패한 띄우기도 `failed`로 남김
- 기록이 실패해도 띄우기는 되돌리지 않는다 — 대신 응답 `note` + 텔레그램 한 번(조용한 고장 금지)
- 옮기기는 역할을 옛 세션에서 물려받으므로 새 세션 행에서 읽어 적는다

### 일곱 — 맡을 파일 · 합칠 순서
- `ForemanDispatcher.file_conflicts` — 세션의 맡을 파일이 (1) 이 계획의 다른 세션 (2) 살아 있는 세션이 맡은 파일(`dispatch_session`) (3) 살아 있는 세션이 **이미 고치고 있는 파일**(그 작업 트리의 바탕 뒤 변경 — 맡을 파일을 안 적은 세션도 잡힘) (4) 아직 시작 안 한 다른 계획(하루 안)과 겹치면 경고. 겹침 판정은 같은 경로 · 폴더 안 · 글롭(`files_overlap`)
- 계획을 받을 때 · 다시 열 때 · [시작] 때 다시 본다. 지난번 붙인 자동 경고는 빼고 새로(`auto_warnings`) — 풀린 겹침은 사라지고 같은 경고가 쌓이지 않는다
- 못 본 것(0030 전 DB · git 실패)은 「보지 못했습니다」 경고로 — 겹침 없음과 가른다
- + 새 세션 창: 「맡을 파일」 칸 → 띄운 뒤 겹치면 결과 글(`note`, 노랑)에
- **합칠 순서** `GET /api/foreman/merge-order?project=foreman[&branches=cc/a,cc/b]` → `{branches:[{branch, cwd, session_id, dispatch_id, merge_order, files, uncommitted}], pairs:[{a, b, files, conflict}], order:[…], reasons:[…], errors:[…], main}`
  - 브랜치: 그 저장소 `git worktree list`의 `cc/*`. 바뀐 파일 = `main...브랜치`(커밋) + 그 worktree의 커밋 안 한 것
  - `conflict` = 둘의 커밋끼리 `git merge-tree --write-tree`(ref · 작업 트리는 안 바꿈, 커밋 안 한 것은 못 봄). 못 돌리면 null
  - 순서: 같은 계획에서 둘 이상이 함께 합칠 때 사람이 정한 `merge_order` → 다른 브랜치와 겹치는 파일 적은 것 → 커밋 안 한 변경 없는 것 → 바뀐 파일 적은 것 → 이름
  - 부딪치는 쌍은 reasons에 「⚠ … 뒤 것은 앞 것을 합친 뒤 main을 가져와 풀어야 합니다」

### 같은 파일 헛경보(`overlap.py`)
- `scan_files`가 두 세션이 둘 다 Edit한 파일 중 **두 쪽 모두 둘의 바탕(merge-base) 뒤에 바뀐 것만** 남긴다(커밋 · 커밋 안 함 · 새 파일). 같은 폴더 두 세션이면 바탕 = HEAD라 커밋 안 한 것끼리
- 11-09 230 ~ 233 모양을 git 저장소로 재현한 시험(`test_real_changes_drops_what_is_already_in_base`) — 230이 커밋한 a.py는 빠지고 둘이 커밋 안 한 채 고친 b.py는 남음
- git을 못 읽거나 세션 폴더를 모르면 **걸러내지 않고 알린다**(놓치는 것보다 헛경보가 낫다) + 로그 「바탕 뒤 변경을 git으로 읽지 못해 …」
- 뺀 파일은 로그 「바탕에 이미 든 것 뺌 …」(info)

## 시험

- `tests/test_foreman_multi.py` 8개(옛 계획 하나로 읽기 · 교장 답의 sessions가 이김 → 옛 카드 고침은 첫 세션에 · 겹침 판정 · 세션별 역할 · 모델 · worktree · 경고 안 쌓임 · 여럿 시작 + 둘째 실패 · 첫 실패면 아무것도 안 띄움 · 다 끔/빈 첫 글 거절 · `record_spawn` + 다른 계획 겹침 — `foreman_test`)
- `tests/test_overlap_base.py` 3개(바탕 뒤 변경 — 실제 git · 헛경보 거르기 · git 실패면 거르지 않음 · 합칠 순서 — 실제 worktree 셋, 충돌 쌍 · 계획 순서)
- 전체 pytest 626 통과 · 1 건너뜀, node 91 통과. 처음 전체를 돌릴 때 `test_stage2_db`가 `foreman_test.character` 없음으로 한 번 깨졌다 — 따로 돌리면 통과, 다시 전체도 통과(같은 때 다른 세션 시험과 표가 겹친 것으로 봄)
- 화면(+ 새 세션 칸 하나)은 미리보기로 보지 못했다 — 칸 하나 · 입력 하나라 자리 점검은 관리자가 합친 뒤 한 번 봐 주면 된다

## 조사 결과 · 설계와 달랐던 점

- **계획 카드는 맡은 파일 밖이다.** 지시서의 「계획 카드에서 세션별로 고치고 끄기, [시작]은 고른 것 모두」는 `bridge/static/js/foremanchat.js`(계획 창) 일인데, 맡은 화면 파일은 `newsession.js`(+ 새 세션 창 — 교장을 거치지 않는 직접 띄우기)뿐이다. 그래서 **세션별 카드는 아직 안 했다**(관리자에게 물음 — 아래 「남은 것」). 그 사이 지금 카드로도 안전하게:
  - 위쪽 칸 = 첫 세션이라 카드는 첫 세션을 보여 주고 고친다
  - 세션이 둘 이상이면 경고 줄 맨 위에 「이 계획은 세션 N개를 띄웁니다: 1「…」(역할 · 모델 · 따로 작업), 2「…」」 — 카드에 안 보이는 세션을 [시작] 전에 안다
- 스위치(`config/*.toml`)는 두지 않았다 — config는 맡은 파일이 아니고, 바뀐 길이 조용히 막히지 않게 짰다: 세션 하나짜리 계획은 전과 같은 `spawn_new` 한 번, 기록(`record_spawn` · `save_sessions`)은 실패해도 띄우기를 막지 않고 글 + 텔레그램. 되돌리기는 revert(아래)
- 「지난 디스패치」(교장 상황 묶음, `foreman_note.recent_dispatches`)에 직접 띄운 것도 「시작함, 고친 것 없음」으로 섞여 들어간다. 그 함수는 맡은 파일 밖이라 손대지 않고, 대신 요청 글을 「(바로 띄움) 이름」 · 「(옮기기) 세션 N에서」로 적어 구별되게 했다. 거슬리면 `origin`으로 가르는 한 줄(C2 때)
- 서기 띄우기(`bridge/scribe_room.py` `spawn_new`)는 기록이 없다 — 맡은 파일 밖(2물결 D2 몫). 「모든 띄우기」의 남은 하나
- `merge-tree --write-tree`는 트리 객체를 저장소에 남긴다(ref는 안 바뀜). 관리자가 손으로 돌리던 것과 같다

## 생명주기(A)와 이을 자리

- 합치기 승인 카드(`bridge/mergeprep.py`)가 끝난 세션의 카드를 만들 때 `GET /api/foreman/merge-order?project=<p>`(또는 파이썬 `app.state.foreman.merge_order(project)`)를 불러, 합칠 브랜치가 둘 이상이면 `pairs`(같은 파일 · conflict)와 `order` · `reasons`를 카드에 붙인다. 브랜치 하나면 `pairs` 비고 `order` 하나
- 판정은 저장소를 안 바꾼다(git diff · status · merge-tree만)
- 「충돌이면 끝내지 않는다」는 A의 규칙과 같은 판단: `conflict: true`인 쌍의 뒤 브랜치는 앞 것을 합친 뒤 그 세션이 main을 가져와 푼다

## 합친 뒤 관리자가 할 일

1. 마이그레이션 적용: `.venv/bin/python -m bridge.db.migrate`(0030 — 표 하나 더하기. 스키마 잠금이 잡힌다 — 적용 · 커밋 뒤 1분 안에 일찍 풀림)
2. 브리지 다시 띄우기(승인 대기 0 확인 뒤) — 파이썬(`foreman.py` · `overlap.py` · `api/*`)이 바뀌었다
3. 확인
   - + 새 세션 창에 「맡을 파일」 칸이 보이는지(세 테마 `tools/screen.py` — 창 안 칸 하나라 자리 영향은 없을 것)
   - 시험 세션 하나를 + 새 세션 창으로 맡을 파일과 함께 띄워 `SELECT origin, status FROM dispatch ORDER BY id DESC LIMIT 1` = `spawn · started`, `dispatch_session` 한 줄. 끝낸 뒤 `hidden_reason='test'`로 숨김
   - `curl -s -H "Authorization: Bearer $FOREMAN_API_TOKEN" 'http://127.0.0.1:<포트>/api/foreman/merge-order?project=foreman'` — 지금 worktree들의 쌍 · 순서
   - 「둘 띄워줘」 같은 요청으로 계획을 받아 경고 줄에 「이 계획은 세션 2개를 띄웁니다」가 뜨는지(실제 [시작]은 시험 세션으로)
4. 「같은 파일」 알림이 다음에 오면 로그 `바탕에 이미 든 것 뺌`이 있는지 · 남은 파일이 진짜 겹침인지 본다

## 되돌리는 법

스위치는 없다. 단계마다 revert + 브리지 다시 띄우기. 마이그레이션은 더하기만이라 코드만 되돌려도 DB는 그대로 돈다(`dispatch_session` 표가 남아도 옛 코드는 모른다).

| 무엇이 탈 나면 | revert | 브리지 |
|---|---|---|
| 같은 파일 알림이 이상(진짜 겹침을 놓침 · git이 느림) | `a399081`(overlap.py만 — 합칠 순서 판정도 같이 빠짐: 그러면 `dbde093`의 merge-order API가 import에서 깨지니 **둘 다** 또는 `_since_base` 호출 두 줄만 손으로 빼는 것을 권함) | 다시 띄움 |
| [시작] · 계획 받기가 이상(여러 세션 · 경고) | `9e5f064` → `dbde093` 차례로(이 둘이면 계획 · 시작 · /api/spawn이 이 일 전과 같다) | 다시 띄움 |
| /api/spawn 응답이 느리거나 기록이 이상 | `dbde093`의 `bridge/api/handoff.py` 두 곳(`record_direct` 부르는 줄)만 빼도 된다 | 다시 띄움 |
| + 새 세션 창 | `c569632` | 필요 없음(정적 파일 — 새로고침) |
| DB까지 지우려면 | 코드를 되돌린 뒤 `DROP TABLE dispatch_session;`(0030 줄의 주석). `dispatch.origin`이 `spawn` · `move`인 행은 둬도 된다 | — |

- 띄우기 길: [시작]은 여전히 `HandoffManager.spawn_new`만 부른다(`bridge/handoff.py`는 안 고침). 세션이 묶일 수 있는 자리는 「여러 세션 중 중간에 실패」뿐이고, 그때도 띄운 것은 살아 있고 결과 · 텔레그램에 무엇이 안 떴는지 나온다

## README에서 뺄 줄(합칠 때 관리자)

- 「교장 ④ 모든 띄우기가 계획 기록(dispatch)을 남김」 — 서기 띄우기(`scribe_room`)만 남음. 그 한 마디로 줄이거나 D2 줄에 붙이기
- 「겹침 감지 "같은 파일" 헛경보」 — 고침(실제 알림으로 한 번 확인 전이면 「확인 기다림」으로 남겨도 됨)
- 「교장 ① 한 번에 여러 세션 계획」 · 「합치기를 순서대로」 · 「같은 파일을 두 세션이 건드리는 것 미리 막기」 — **바탕(API · 기록 · 경고)은 됨**, 세션별 계획 카드(`foremanchat.js`)와 합치기 카드에 순서 붙이기(A)가 남음. 카드가 끝나면 뺀다

## 남은 것

- **세션별 계획 카드**(`foremanchat.js`) — 세션마다 역할 · 모델 · 이름 · 첫 글 · 맡을 파일 · 합칠 순서를 고치고 끄기, [시작]은 켠 것 모두(`sessions_edit: true`로 보냄), 결과 `out.sessions[]` · `out.failed` 보이기. 맡은 파일 밖이라 관리자 276에게 물음
- 서기 띄우기 기록(`scribe_room.py`) — D2
- 지난 디스패치 목록에서 직접 띄운 것 가르기(`foreman_note.py`) — C2
