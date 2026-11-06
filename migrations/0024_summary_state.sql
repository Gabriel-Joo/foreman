-- 0024 인계 검증 (11-06) — 인계가 낡았는지 기계로 본다(조용한 고장과 같은 모양: 받은 세션이 지난 상태를 사실로 믿고 일한다)
--   state  인계를 만들 때의 git · 잠금 상태(JSON): 저장소 · worktree · 브랜치 · HEAD · 기준 브랜치 HEAD · 스키마 잠금 · 시각
--   drift  넣을 때 지금과 비교해 인계 앞에 붙인 "인계 뒤 바뀐 것"(JSON 줄 목록) — 받은 세션 패널에 보인다
ALTER TABLE summary
  ADD COLUMN state JSON NULL AFTER body,
  ADD COLUMN drift JSON NULL AFTER injected_at;
