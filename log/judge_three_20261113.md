# 판정 셋 — 빈 worktree · 겹침 낱말 헛경보 · 정리 후보 헛짚기 (11-13, 코더 foreman-3, 일감 B)

관리자 318 일감. 셋 모두 「판정이 겉모양만 본다」는 같은 뿌리라 한 기록에 적는다.

## 3. 빈 worktree

한 일
- `bridge/reconcile.py`: 끝난 세션의 worktree가 **커밋 안 한 변경 0 · 합치기/버리기/쉬게 하기 기록 없음 · 브랜치가 원본에 모두 들어 있음(`wt.in_base` True — 앞선 커밋 0 또는 같은 변경이 원본에 있음)**이면 `orphan`이 아니라 새 kind `empty`로 둔다. 앞서 있거나(`in_base` False) 변경이 있으면(`dirty`) 지금처럼 어긋남
- `Reconciler.run_once`: `empty`는 텔레그램에서 뺀다(고장이 아니라 치울 것. 화면에는 남는다)
- `bridge/static/js/coder.js`: `coderJobs`가 `empty`를 맡길 일에서 빼고(말풍선 「맡길 일 N」에도 안 센다), `emptyWorktrees()`가 따로 뽑아 **「치울 것 — 빈 worktree N」** 칸을 맡길 일 칸 바로 아래에 보인다. 줄마다 [세션 열기] · [버리기]. [버리기]는 확인 창 → `POST /api/sessions/{sid}/worktree {"action":"discard","confirm":"<worktree 이름>"}`(이름은 `where`의 마지막 칸)
- `bridge/api/coder.py`는 고치지 않았다 — `drift`에 `empty`가 그대로 실려 오고 화면이 가른다

판단
- 표시 자리: 코더 패널 안의 **별도 칸**이다. 코더 머리 위 말풍선 · `dashboard.py` · `render.js` · `office.js` · `store.js` 모두 `drift`를 읽지 않으므로 금지 파일을 건드릴 필요가 없었다(`drift`는 `coder.js`만 읽는다). 사람 화면에 「맡길 일」로 세지 않는다 — 비면 말풍선도 없다
- `wt-merge`/`wt-discard` 기록이 있는데 폴더가 남은 `orphan`은 그대로 둔다(합치고 지우다 만 것이라 어긋남이 맞고, 기존 시험이 기대한다)
- 빈 worktree 알림을 뺀 것은 내 판단이다. 되돌리려면 `run_once`의 `found = [f … != "empty"]` 한 줄을 지운다

## 4. 겹침 「요청 낱말」 헛경보

한 일
- `bridge/overlap.py`: `_check`의 상대 세션 목록에 역할(`cs.role`)을 더하고, 이 세션이 dispatch로 띄워진 것이면(`_dispatched` — `dispatch.session_id` 또는 `dispatch_session.session_id`가 이 세션) 같은 프로젝트의 **관리자 역할 세션**을 맞대기에서 뺀다(`without_spawner`). 다른 코더 · 역할 없는 세션과는 그대로 맞댄다

띄운 쪽이 기록에 있는지(확인)
- **없다.** `record_spawn`(`bridge/foreman.py` 855)은 `dispatch.session_id`에 **띄워진 새 세션**을 적고, `/api/spawn` 요청에는 부른 세션 id가 없다(토큰 범위로 「관리자 길인지」만 안다). 그래서 「같은 프로젝트의 관리자 역할 세션 = 띄운 쪽」으로 본다. 스키마를 바꾸지 않으려는 선택이다
- 약점 둘: ① 한 프로젝트에 관리자가 둘이면 둘 다 뺀다 ② 첫 지시문이 `dispatch` 기록보다 먼저 적재되면(`record_direct`는 띄운 뒤에 적는다) 그 한 번은 못 뺀다 — 적재는 tmux로 넣은 뒤라 보통 늦다. 정확히 하려면 spawn 요청에 부른 세션 id를 받아 `dispatch`에 적어야 한다(스키마 — 이번 일감 밖)
- 「같은 파일」 경보(`scan_files`)는 건드리지 않았다

## 5. 합치기 카드 README 정리 후보 헛짚기

한 일
- `bridge/mergeprep.py`: 「README에서 뺄 줄」 절의 줄 이름은 **README 표 줄 첫 칸의 굵은 글씨 제목 전체**(`row_titles`)와 같을 때만 맞다. 「화면 — 제목」처럼 앞에 말이 붙은 제목은 「 — 」 뒤쪽도 제목으로 센다(앞말 없이 적어도 잡히게). 부분 문자열 · 낱말로는 맞추지 않는다
- 줄 번호로 적은 것(`log_drop_numbers`) — 「941」 · 「README 941줄」 · 본문의 「941줄」 — 은 그 줄 번호의 표 줄에 100점. `log_drop_lines`는 번호만 적은 따옴표를 이름에서 뺀다
- 시험(`tests/test_mergeprep.py`)에 오늘 네 기록의 해당 절 줄을 **그대로** 넣어 헛짚기 0을, 진짜 둘(`mergeprep_db`의 「오래됨」 줄 · `docs_sync`의 941 「docs 어긋남 맞추기」)이 잡히는 것을 확인한다. 실제 README · log 파일을 읽는 시험은 아니다(파일이 바뀌면 깨지므로 발췌)

판단
- `mergeprep_db`의 진짜 줄은 README 제목이 「화면 — 브리지를 … 다시 잡힌다」인데 log는 「브리지를 … 다시 잡힌다」로 적었다. 굵은 제목 **전체**만 보면 이 진짜가 빠지므로 「 — 」 뒤쪽 제목도 센다
- 줄 번호는 README가 바뀌면 틀어질 수 있다(카드를 만들 때의 README 기준). 줄 이름과 번호를 함께 적으면 하나라도 맞으면 잡힌다

## 시험

- pytest 전체 · `node --test tests/js/` — 아래 「결과」 참고
- 새 시험: `test_empty_worktree_is_separate_from_drift_and_not_alerted`(reconcile, DB) · `test_spawned_session_is_not_matched_against_its_manager`(overlap) · `test_drop_lines_*` 둘(mergeprep) · `coder.test.mjs` 빈 worktree 한 개

## 되돌리는 법

- 셋 모두 이 브랜치 커밋 하나를 `git revert`. 3번만: `reconcile.py`의 `empty` 분기를 지우면 옛 동작. 4번만: `without_spawner` 호출 줄을 지운다. 5번만: `doc_candidates`의 `named = …` 한 줄을 `q in title`로 되돌린다
- 스키마 · `config/*.toml` · 브리지 재시작 필요: 브리지(파이썬)가 바뀌었으므로 합친 뒤 원본 세션이 브리지를 다시 띄워야 한다(3 · 4 · 5 모두 파이썬, 3은 화면 js도)

## 규칙 위반

1. **진행 글이 영어로 나갔다 — 11-13, 시험 쓰기 직전("Now the tests. First the mergeprep…") 한 번.** 도구 결과가 영어였던 틈에 흘렀다. 훅이 알려 바로 한국어로 돌아왔고, 글을 다시 쓸 방법은 없어 여기에 적는다
2. **Bash에 heredoc 형태를 한 번 썼다 — 11-13, `cat >> /dev/null <<'EOF'` (빈 입력).** 파일에는 아무것도 쓰지 않았고(대상이 `/dev/null`, 내용 없음) 쓰려던 시험 파일은 Edit로 넣었다. 규칙 취지(heredoc으로 파일 쓰기 금지)에 닿지는 않았지만 형태가 같아 적는다. 이후 쓰지 않았다
3. 그 밖에 `sed -i` · `cp` · `python -c` 파일 쓰기, push, 브리지 재시작, 스키마 · config · README · docs 수정은 없다

## README에서 뺄 줄

- 줄 번호로만: **943**(정리 후보 헛짚기) · **944**(빈 worktree) · **938**(요청 낱말 헛경보) — 이 기록으로 풀린다. 번호는 이 브랜치가 갈라질 때(`da42cc2`)의 README 기준이니 관리자가 합칠 때 다시 확인한다

## 결과

- `pytest` 전체: **836 통과 · 1 건너뜀** (141초). `node --test tests/js/`: **134 통과**
- 처음 돌린 pytest 전체는 `tests/test_human_wait.py` 근처에서 2시간 넘게 멈춰 내가 `kill`하고 다시 돌렸다(다시 돌리니 통과). 원인은 확인하지 못했다 — 시험 DB `foreman_test`를 다른 세션이 동시에 쓴 것으로 짐작할 뿐이다. 멈춤이 되풀이되면 따로 볼 일
