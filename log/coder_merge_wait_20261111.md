# 합치기 카드가 보이게 — 머리 위 「합치기 기다림」 · 승인 막대 건수 (코더 foreman-2, 11-11)

카드는 제때 만들어지는데 세션 패널 「세션」 탭 안에만 그려져 사람이 몰랐다(조용한 고장). 표시 둘을 붙였다.

## 한 일
- `bridge/api/dashboard.py` — `merge_waits(mp)`: `mergeprep.view()`의 `status == "ready"` 카드를 세션 id별 `merge_wait {since, head8, files, asks}`로. 세션 항목에 `"merge_wait"`. `mergeprep.py`는 고치지 않았다
- `bridge/static/js/render.js` — `needMark`에 합치기 기다림 추가, `mergeWaits(sessions)`(가장 오래된 카드부터)
- `bridge/static/js/office.js` — `markColor`에 보라, 머리말 경고 줄에 `#oMerge` 버튼, 클릭 시 가장 오래된 세션 패널
- 시험 `tests/test_merge_wait.py` · `tests/js/merge_wait.test.mjs`, 시연 장면 `bridge/static/demo/merge_wait.json`
- 커밋: 말풍선 `edf5ef1`, 막대 + 시연 장면 `983a975`

## 286과 겹침
시작 때 `git diff --name-only main...cc/foreman-4` · foreman-4 `status`를 봤다. 286 파일 목록에 `office.js` · `dashboard.py` · `render.js`는 없었다 → 겹침 없음. foreman-4 작업 트리는 깨끗(커밋됨).

## 겹침 기준(머리 위에는 하나만 보인다)
**권한 거부 > 답 기다림 > 합치기 기다림 > 보고 옴.** (테마 승인 대기 말풍선 `act.bubble`은 기존대로 가장 먼저)
- 앞의 둘은 세션이 막혀 지금 사람 손이 먼저 필요하다. 답 기다림 + 합치기가 겹치면 11-11 턴 끝 카드 규칙 때문에 실제로 자주 생기는데, 답을 하면 합치기 기다림으로 바뀐다(막대에는 그 세션도 센다)
- 합치기는 사람이 눌러야 끝나는 일이라 읽기만 하면 되는 보고 옴보다 위
- 코드 주석: `render.js` `needMark`

## 색
합치기 기다림 = 보라 `#c9a7ff`(`P.merge`가 있으면 그것). 초록(보고) · 노랑(답/거부/승인 대기) · 빨강(실패) · 파랑(`act` — 쉼 점 · `+N`)이 이미 쓰여서, 세 테마 팔레트에 없는 색을 골랐다.

## 정한 것 · 한계
- 대기 = `ready`만. `failed` · `conflict_*` 카드는 세지 않는다(필요하면 따로 — 이번 범위 밖)
- 끝난(DORMANT) 세션은 말풍선이 없고(기존 `needMark` 규칙), 막대에는 센다 — 캐릭터가 없어도 카드가 남아 있으면 알 수 있게
- 카드를 승인해 `merged`가 되거나 치우면 다음 대시보드 값(`mergeprep.on_change`로 무효화)에서 `merge_wait`가 빠져 둘 다 사라진다
- 막대 버튼은 사무실 화면(`office.js`)만. 클래식 대시보드 머리말은 손대지 않았다
- 눌러서 열리는 패널의 「세션」 탭 선택은 `handoff.js`(286 몫)라 건드리지 않았다 — 패널이 마지막 탭을 열 수 있다
- 합치기 카드를 한곳에 모은 목록은 만들지 않았다(지시대로)

## 확인 체크리스트
- [x] 카드 뜬 세션 머리 위 말풍선 — 시험(`needMark`) · 시연 장면 `/?demo=merge_wait`. 실제 카드로는 합친 뒤 관리자가 라이브에서
- [x] 카드를 치우면 사라짐 — 시험(`merge_waits`가 ready 아니면 빠짐, `needMark` null)
- [x] 셋 겹침 기준 — 시험 `겹침 기준` + 시연 장면 981(합치기) · 982(답 기다림) · 983(합치기, 보고 아래)
- [x] 막대 건수 = 대기 수 — 시험(`mergeWaits` 3건) · 시연 장면 3건
- [x] 막대 클릭 → 가장 오래된 세션 — `mergeWaits()[0]`(시험으로 981 확인). 클릭 핸들러 자체는 화면에서 안 눌러 봤다
- [x] 0건이면 비어 있음 — `mergeWaits([])` 빈 목록, 버튼은 `mwait.length`일 때만 그림(화면에서는 안 봄)
- [x] pytest `653 passed, 1 failed, 1 skipped` · node `112 pass`
  - 실패 1건 `tests/test_foreman_multi.py::test_record_spawn_and_conflicts_with_planned` — "DB에는 있는데 파일이 없다: 0031_handover_todo_edit". 시험 DB를 같이 쓰는 286(foreman-4)이 0031을 올렸고 이 브랜치엔 그 파일이 없어서 마이그레이션이 실패한다. 내 변경과 무관, 286을 합치면 풀릴 것으로 본다(합친 뒤 다시 확인 필요)
- 브라우저로 직접 화면을 눌러 본 것은 없다(화면 확인은 관리자 몫)

## 되돌리는 법
- 막대만: 막대 커밋 revert(`git log --oneline -3`의 「승인 막대에 합치기 대기」)
- 말풍선까지: `edf5ef1`도 revert. 파이썬(`dashboard.py`)이 바뀌므로 **합친 뒤 브리지를 다시 띄워야** 새 값이 실린다(화면 JS는 새로 고침). revert하면 브리지를 다시 띄워야 필드가 빠진다
- README에서 뺄 줄: 없음
