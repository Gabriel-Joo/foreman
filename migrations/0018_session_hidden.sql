-- 0018 세션 숨기기 · 킥오프 세션 자리(11-05 사용자 결정)
-- hidden_at: 지우지 않고 화면 · 집계 · 최근 폴더 · 문서화 재료에서 뺀다. hidden_reason은 짧은 사유(test 등).
--   되돌리기: UPDATE character_session SET hidden_at = NULL, hidden_reason = NULL WHERE hidden_reason = 'test';
ALTER TABLE character_session
  ADD COLUMN hidden_at     DATETIME(3) NULL AFTER detached_at,
  ADD COLUMN hidden_reason VARCHAR(32) NULL AFTER hidden_at;

-- 미분류의 시험 세션 — /tmp 아래에서 hook · probe · 권한 · 재개 · 인계를 시험하느라 띄운 것(12개, 기록 없는 빈 행 2개 포함)
UPDATE character_session cs JOIN `character` u ON u.id = cs.character_id
SET cs.hidden_at = UTC_TIMESTAMP(3), cs.hidden_reason = 'test'
WHERE u.project_id IS NULL AND u.name = '미분류' AND cs.cwd LIKE '/tmp/%' AND cs.hidden_at IS NULL;

-- "Foreman 토이 프로젝트 킥오프"(~/AI_programming, 11-01) — foreman 폴더가 생기기 전의 설계 대화. 포먼 프로젝트의 코더로.
-- 되돌리기는 0017과 같은 표(옛 캐릭터)
INSERT INTO character_session_move_0017 (session_id, old_character_id, new_character_id)
SELECT cs.id, cs.character_id, c.id
FROM character_session cs
JOIN `character` u ON u.id = cs.character_id AND u.project_id IS NULL AND u.name = '미분류'
JOIN project p ON p.name = 'foreman'
JOIN `character` c ON c.project_id = p.id AND c.name = '코더' AND c.current_role = 'coder'
WHERE cs.cc_session_id = '683920dd-d9df-40fd-bd69-ad82103f0296';

UPDATE character_session cs JOIN character_session_move_0017 m ON m.session_id = cs.id
SET cs.character_id = m.new_character_id
WHERE cs.cc_session_id = '683920dd-d9df-40fd-bd69-ad82103f0296';
