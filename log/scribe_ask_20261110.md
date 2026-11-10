# 서기 물어보기 (11-10, foreman-3)

## 한 일
- 서기 패널(세션 없음)에 입력 칸이 없음을 확인: `office.js:538-543,2726-2728` → `opanel.js:623-626` `scribe.html()`만 그리고 `sessionMode(false)`가 `#pForm`을 숨긴다(`opanel.js:517`). 입력 칸은 세션 패널(`opanel.js:67-68,581`)에만 있다
- 사용자 승인("재료 묶음까지 읽기")으로 구현: `bridge/scribe_ask.py`(새), `POST /api/scribe/ask`(`bridge/api/scribe.py`), 화면 「물어보기」(`scribe.js`), `opanel.js` 4줄(서기 분기 안 — input/keydown 전달, 다시 그려도 포커스 유지), `usage.py` 라벨 1개
- 시험 `tests/test_scribe_ask.py` 3개(가짜 claude로 인자 · 도구 제한 · 거절). 전체 549 통과 · 1 건너뜀

## 판단 근거
- 읽기 전용 질문은 diff가 없어 worktree · 합치기 원칙과 부딪치지 않는다. 고치는 일은 [시키기]로만
- 교장 경로(`/api/foreman/plan`)는 계획 JSON만 돌려줘 답을 못 한다 → 같은 `claude -p` 방식으로 따로 둠

## 남은 것
- 화면을 실제로 열어 본 시험 없음(`tools/screen.py` · 패널 미리보기 미실시). 브리지는 원본 세션이 합친 뒤 다시 띄워야 `/api/scribe/ask`가 열린다
- `opanel.js`는 251(디자이너)과 같은 파일 — 합치기 전 `git merge-tree`로 확인
