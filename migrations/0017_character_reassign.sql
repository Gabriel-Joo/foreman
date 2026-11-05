-- 0017 세션 재배치(11-05, README 2.3 · 2.4 · 로드맵 11) — 2단계에서 입양한 세션은 모두 프로젝트의 "포먼" 캐릭터에 묶여 있었다(임시).
-- 포먼(current_role foreman)은 프로젝트마다 상주하는 감독이고 자기 세션이 없다. 일꾼은 역할별 캐릭터로 옮긴다:
--   coder → "코더", inspector → "점검", cicd → "CI/CD" (부모 = 그 프로젝트의 포먼, spawned_by foreman)
--   helper(7단계 터미널 패널의 셸 행) → 떠돌이 '미분류'(helper)
-- 되돌리기: character_session_move_0017에 옛 캐릭터를 남긴다
--   UPDATE character_session cs JOIN character_session_move_0017 m ON m.session_id = cs.id SET cs.character_id = m.old_character_id;

CREATE TABLE character_session_move_0017 (
  session_id        BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  old_character_id  BIGINT UNSIGNED NOT NULL,
  new_character_id  BIGINT UNSIGNED NULL,
  moved_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB;

-- 프로젝트마다 코더는 늘 둔다(새로 입양하는 세션의 기본 자리)
INSERT INTO `character` (project_id, parent_id, name, current_role, status, kind, spawned_by)
SELECT f.project_id, f.id, '코더', 'coder', 'DORMANT', 'agent', 'foreman'
FROM `character` f
WHERE f.current_role = 'foreman' AND f.project_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `character` x WHERE x.project_id = f.project_id AND x.current_role = 'coder');

-- 점검 · CI/CD는 그 역할 세션이 있는 프로젝트에만
INSERT INTO `character` (project_id, parent_id, name, current_role, status, kind, spawned_by)
SELECT DISTINCT f.project_id, f.id, CASE cs.role WHEN 'inspector' THEN '점검' ELSE 'CI/CD' END, cs.role, 'DORMANT', 'agent', 'foreman'
FROM character_session cs JOIN `character` f ON f.id = cs.character_id AND f.current_role = 'foreman'
WHERE cs.role IN ('inspector', 'cicd')
  AND NOT EXISTS (SELECT 1 FROM `character` x WHERE x.project_id = f.project_id AND x.current_role = cs.role);

-- 옮길 것을 먼저 적는다
INSERT INTO character_session_move_0017 (session_id, old_character_id, new_character_id)
SELECT cs.id, cs.character_id, r.id
FROM character_session cs
JOIN `character` f ON f.id = cs.character_id AND f.current_role = 'foreman'
JOIN `character` r ON r.project_id = f.project_id AND r.current_role = cs.role AND r.parent_id = f.id
WHERE cs.role IN ('coder', 'inspector', 'cicd');

INSERT INTO character_session_move_0017 (session_id, old_character_id, new_character_id)
SELECT cs.id, cs.character_id, u.id
FROM character_session cs
JOIN `character` f ON f.id = cs.character_id AND f.current_role = 'foreman'
JOIN `character` u ON u.project_id IS NULL AND u.name = '미분류'
WHERE cs.role = 'helper';

UPDATE character_session cs JOIN character_session_move_0017 m ON m.session_id = cs.id
SET cs.character_id = m.new_character_id;
