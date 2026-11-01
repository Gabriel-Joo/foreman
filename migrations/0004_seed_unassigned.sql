-- 0004 떠돌이 캐릭터 '미분류' — 어느 프로젝트 저장소에도 속하지 않는 cwd(~, ~/AI_programming, /tmp 등)에서
-- 돈 CC 세션을 붙여 둘 자리. 2단계는 이미 돌고 있는 세션을 입양만 한다(캐릭터를 새로 만들지 않는다 — 포먼만 채용).
-- 프로젝트 세션은 그 프로젝트의 포먼에, 나머지는 여기에 붙는다. 방(2.5) 밖의 복도에 선다

INSERT INTO `character` (project_id, name, sprite, current_role, status, kind, spawned_by)
VALUES (NULL, '미분류', NULL, 'helper', 'DORMANT', 'agent', 'auto');
