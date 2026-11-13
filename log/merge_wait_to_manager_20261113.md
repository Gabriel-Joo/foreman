# 사람 승인 합치기 카드를 관리자 머리 위로 · 정리 후보 다 골랐다 · 시험 시각 — 2026-11-13 (코더 cc/foreman-2, 관리자 318 일감 C)

사용자: 「나는 관리자하고만 이야기한다. 코더 머리 위는 볼 일이 없다. 내가 눌러야 하는 카드여도 관리자가 올리면 된다.」

## 한 일

### 1. 사람 승인 카드 → 관리자 머리 위 「사용자 답 기다림」 (`bridge/mergeprep.py` · `bridge/api/dashboard.py` · `render.js` · `office.js`)
- **브리지가 기계적으로 올린다**: `MergePrep._esc_sync()` — `sync()`(훑기 · 턴 끝 · 승인 · 미루기 · 관리자 알림 뒤마다 불림) 안에서 돈다. 사람 승인 카드(`status = ready`이고 관리자 승인 카드가 아닌 것 = `merge_waits`와 같은 기준 `human_card`)마다 그 저장소 원본 폴더의 살아 있는 관리자 세션에 `escalate(kind="question")`을 부른다. 저장 · 알림 길은 escalate 그대로
  - 글: 「세션 N 「제목」 합치기 카드 — 사람 승인이 필요합니다(사유: …). [충돌 파일 N개.] 패널 [합치기]를 눌러 주십시오(세션 N 패널 「세션」 탭)」. 사유는 `human_why`, 없으면 카드 note, 그것도 없으면 「이 프로젝트의 합치기 승인자는 사람입니다」
  - detail 앞에 기계 표시 `#merge:<카드 세션 id># `(`dashboard.merge_tag`). 사람에게 보이는 글 · 텔레그램에는 안 붙는다(`human_needs`가 떼고 `merge_sid`로 싣는다)
  - 카드에 `esc_id` · `esc_mgr` · `esc_error` 칸 — 카드 JSON이라 DB(`merge_card`)에 같이 남는다. **스키마 안 바꿈**
- **내릴 때**: 매번 DB에서 떠 있는 합치기 물음(`question:#merge:%`, esc-off 없음, 7일 안)을 읽어, 그것을 쥔 대기 카드가 없으면 `esc-off`. 합쳐짐(merging 이후) · 미뤄짐 · 카드 없어짐(버림 · 다시 일함 · 새 커밋으로 새 카드) 모두 같은 길. 메모리가 아니라 DB를 보므로 다시 띄운 사이 것도 줍는다
- **관리자가 바뀌면**(인계) 옛 물음을 내리고 새 관리자에게 다시 올린다. **관리자가 없거나 · 찾다 실패하거나 · escalate가 거부되면** `esc_error`에 까닭을 달고 지금처럼 작업 세션 머리 위 「합치기 기다림」(툴팁에 까닭). 관리자가 뜨면 다음 맞추기에서 올린다
- `merge_waits`에 `to_manager`(올린 관리자 세션 id) · `esc_error`. `needMark`는 `to_manager`가 있으면 작업 세션의 「합치기 기다림」을 안 띄운다. 승인 막대 「🔀 합치기 대기 N」 · 패널 [합치기]는 그대로(`mergeWaits`는 안 바뀜)
- `human_needs`: 합치기 물음은 **사람이 그 관리자에게 입력해도 남는다**(카드가 남았으니). 내리는 것은 브리지 esc-off와 사람의 [답 안 해도 됨]. 관리자의 다른 물음과 서로 덮지 않는다 — 머리 위에는 가장 최근 물음 하나, 합치기 물음이 여럿이면 `escalate.merges`에 카드 세션 id 모두
- 화면: 관리자 말풍선을 누르면 그 카드 세션 패널 「세션」 탭(`office.js` 클릭 — 말풍선 칸만. 캐릭터를 누르면 지금처럼 관리자 대화). 툴팁 「사용자 답 기다림 — 세션 N의 합치기 카드가 사람 승인을 기다립니다. 말풍선을 누르면 …」. 방 머리줄 · 지도 호버 글을 「관리자 패널에서 답하거나, 합치기 카드면 말풍선을 누릅니다」로
- 관리자에게 가는 카드 글(`_card_msg`, 늘-사람 카드)에 「브리지가 관리자 머리 위로 올린다 — 따로 escalate하지 않는다」
- 관리자 승인 카드(approver = manager, human_why 없음)는 지금처럼 안 올린다

### 1-1. 관리자 318이 더한 사용자 결정(작업 중 받음)
- 「관리자 답 기다림」은 **남긴다**(코더가 관리자 답을 기다리느라 멈춰 있다)
- 「관리자에게 보고함」과 겹치면 **「관리자에게 보고함」이 이긴다**. 서버가 같은 턴을 넘긴 종류(ok) 모두를 `relayed.kinds`로 싣고, `render.js workerMark`가 report가 있으면 보고함을 고른다. 작업 세션 갈래는 `workerMark` 한 곳에 모았다
  - 지금 넘기기는 턴마다 한 종류라 실제로 겹치는 것은 relay_questions가 꺼진 때 묻는 말을 보고로 넘긴 뒤 물음으로도 넘긴 경우 정도다

### 2. 「정리 후보를 다 골랐다」 — `POST /api/sessions/{sid}/merge-prep {"action": "docs_done", "by": "manager"}`
- `MergePrep.docs_done` — 합친(`merged`) 카드만 치운다(DB `merge_card`에서도, `session_action` 'mprep-docs'). 대기 · 충돌 카드는 거부(「skip으로」). 72시간(`keep_docs_h`)은 그대로 — 안 부르면 그때 치운다
- 관리자에게 가는 합친 결과 글(`_merged_msg`)에 정리 후보가 있을 때 부르는 법 한 줄(관리자가 고르는 프로젝트 · 사람 승인 뒤 고르는 프로젝트 둘 다)
- 프로젝트 토큰은 이미 있는 `/api/sessions/{sid}[/…]` 범위(그 세션이 이 프로젝트 것일 때)로 자기 프로젝트 카드만 — scopetoken은 안 고침

### 3. 시험 시각
- 오늘 생긴 시험(`tests/test_overhead_marks.py` · `tests/test_mergeprep_db.py` · `tests/js/overhead_marks.test.mjs`)을 훑었다. 시간 창에 기대며 모듈 시각을 쓰던 곳은 관리자가 `2cb36cc`로 막은 하나뿐이었다
  - `test_overhead_marks.py` 모듈 `NOW`의 나머지 쓰임은 24시간(REPORT_FRESH) · 7일(ESC_KEEP) 창 안의 서로 상대 비교라 수십 초 · 몇 분 낡아도 결과가 같다 → 두었다
  - `test_mergeprep_db.py`는 함수 안에서 `mp._now()`를 부른다. `test_stallwatch.py` · `test_usage.py`의 `NOW`는 고정 시각이다
- 새 시험 `tests/test_merge_wait_manager.py`는 시각을 시험 안에서 잰다

## 확인
- `pytest` 전체 815 통과 · 1 건너뜀. 새 `tests/test_merge_wait_manager.py` 9개(합치기 물음이 사람 입력에도 남음 · 다른 물음을 덮지 않음 · 글에 표시 없음 / 올림 · 다시 안 만듦 · 합쳐지면 내림 / 없어짐 · 미룸 · 다시 띄움 / 관리자 없음 → 작업 세션, 뜨면 올림, 인계면 옮김 / escalate 거부 → 작업 세션 / 관리자 승인 카드는 안 올림 · notify_ready면 알림 두 번 안 보냄 / docs_done / 결과 글 / API). `test_overhead_marks.py`에 `kinds` 확인, `test_merge_wait.py` 기대값에 새 칸. 실제 `config/*.toml`을 읽는 시험은 없다
- `node --test tests/js/` 132 통과 — 새 `merge_wait_manager.test.mjs`(관리자에게 올린 카드는 작업 세션에서 빠지고 막대는 셈 · 못 올리면 남음 · 관리자 말풍선 mergeSid · 보고함이 답 기다림을 이김)
- 화면: 시연 `overhead_marks`에 FOREMAN 관리자 980의 합치기 카드 물음(코더 981 카드, `to_manager`) · 인프라 코더 991의 못 올린 카드를 더했다. `tools/screen.py --demo overhead_marks --views foreman,ronanlab-infra,map --no-term` 세 테마 × 1920 · 1366 · 1024 × 좁게/넓게 18조합 모두 문제 0, 화면마다 `bubbleAudit()` 빈 목록. 사진: 오피스 1366 관리자 「사용자 답 기다림」 · 코더 981은 「관리자에게 보고함」만 · 막대 「합치기 대기 2」, 인프라 코더 991 「합치기 기다림」, 마법학교 1024 넓게에서 머리줄이 두 줄로 접혀 잘리지 않음

## 설계와 달랐던 점 · 판단 근거
- **물음을 무엇으로 알아보나** — detail 글 앞의 기계 표시. 브리지만 쓰는 글이라 「글자 하나 틀리면 안 먹는」 걱정이 없고, 카드가 사라진 뒤에도 어느 물음이 합치기 물음인지 알아야(사람 입력으로 안 내리기 · 다른 물음과 안 덮기) 해서 메모리 표 대신 골랐다
- **사람이 그 관리자에게 입력해도 남긴다** — 카드는 [합치기]를 눌러야 끝나는 일이라 말로 답해도 카드가 남는다. 사람이 「안 봐도 된다」고 하면 [답 안 해도 됨]으로 끈다(끈 뒤에는 같은 카드로 다시 올리지 않는다 — 막대는 그대로 센다)
- **알림 두 번 안 보냄** — `notify_ready`가 켜져 있으면 카드가 생길 때 「⑂ 합치기 준비됨」이 이미 나간다. 그때는 escalate 알림(❓)을 빼고 화면에만 올린다. 꺼져 있으면 escalate가 ❓로 바로 알린다
- **내리기는 DB 기준** — 카드를 지운 뒤 esc-off가 실패해도 다음 맞추기에서 다시 내린다. 맞추기마다 session_action을 한 번 읽는다(7일 · 합치기 물음만)
- 「관리자 답 기다림」을 남길지 묻던 것은 위 1-1로 정해졌다

## 따로 찾은 것 — 미리보기 조용한 고장 (고치지 않음)
- 화면 점검 때 `POST /api/sessions/322/preview`가 `{"port": 8200, "tmux": "fm-pv-foreman-2", since 11-13 02:45 UTC}`를 돌려줬지만 tmux `fm-pv-foreman-2`는 없었고 127.0.0.1:8200에 듣는 것도 없었다(192.168.122.1:8200은 11-11부터 도는 다른 서비스 `model_service`). 미리보기 기록(`~/.foreman/previews.json`)만 남고 서버는 죽은 채 「있음」으로 답한다
- 이번 점검은 같은 명령(`python -m bridge.preview --port 8231 …`)을 이 세션에서 직접 띄워 하고 껐다
- 고칠 곳 후보: `bridge/previews.py` — 있다고 답하기 전에 tmux · 포트가 살아 있는지 보고, 죽었으면 다시 띄우거나 「죽었음」으로 답하기. 관리자 판단으로 worktree 일감

## 되돌리는 법
- 이 커밋을 `git revert`. 카드 JSON의 `esc_*` 칸은 옛 코드가 `from_saved`에서 버린다. 떠 있던 합치기 물음은 옛 코드에서 보통 물음으로 보이니, 되돌린 뒤 `INSERT INTO session_action (session_id, action, ok, detail) SELECT session_id, 'esc-off', 1, id FROM session_action WHERE action='escalate' AND detail LIKE 'question:#merge:%'`로 내린다(관리자가)
- 합친 뒤 브리지를 다시 띄워야 서버 쪽(올리기 · docs_done · kinds)이 돈다 — 원본 세션이. 화면(JS)은 새로 고침

## 사람이 정할 것
1. 합치기 물음을 사람이 [답 안 해도 됨]으로 끈 뒤 카드가 남아 있으면 다시 올리지 않는다(막대만 남음). 일정 시간 뒤 다시 올릴지
2. 7일(ESC_KEEP)을 넘긴 대기 카드는 관리자 머리 위 물음이 사라지고 막대만 남는다. 그 전에 따로 알릴지
3. 위 미리보기 고장을 worktree 일감으로 낼지

## README에서 뺄 줄
- 없음(README 「나중에 할 일」에 이 일감 줄이 있으면: 「합치기 카드 정리 후보를 다 골랐다는 신호가 없다 — 시간이 지나야 치운다」 류)
