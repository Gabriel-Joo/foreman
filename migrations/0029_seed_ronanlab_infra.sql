-- 0029 프로젝트 넷째 — 인프라(ronanlab-infra, 11-10 사용자). 0002 시드 · 0017 재배치와 같은 행만 더한다(DDL 없음)
-- 클러스터 · 노드 · 가용성 일이 이어진다(묶음 1: 노드 증설 · 가용성, 묶음 2: Harbor · ArgoCD 이사 · MySQL Replica · 모니터링).
-- 빌드하는 앱이 아니라 출하장(Jenkins → Harbor → ArgoCD)은 없다 — config/pipeline.toml에 넣지 않는다. k8s 네임스페이스도 없다(NULL)
-- 브리지가 시작할 때 project 표를 읽으므로(assembler.load) 이 파일을 적용한 뒤 브리지를 다시 띄워야 새 세션이 이 방으로 간다.
-- 이미 '미분류'에 붙은 세션은 저절로 옮겨지지 않는다(character_session 행을 그대로 읽는다) — log/coder_infra_project_20261110.md
--   되돌리기: DELETE ch FROM `character` ch JOIN project p ON p.id = ch.project_id WHERE p.name = 'ronanlab-infra';
--             DELETE FROM project WHERE name = 'ronanlab-infra';   (그 사이 붙은 세션이 있으면 먼저 '미분류'로 옮긴다)

INSERT INTO project (name, repo_path, repo_url, namespace) VALUES
  ('ronanlab-infra', '/home/kopo17/ronanlab-infra', 'https://github.com/Gabriel-Joo/ronanlab-infra.git', NULL);

-- 포먼(상주 감독, 자기 세션 없음) — 0002와 같다
INSERT INTO `character` (project_id, name, sprite, current_role, status, kind, spawned_by)
SELECT id, '포먼', NULL, 'foreman', 'DORMANT', 'agent', 'user' FROM project WHERE name = 'ronanlab-infra';

-- 코더(새로 입양하는 세션의 기본 자리) — 0017과 같다
INSERT INTO `character` (project_id, parent_id, name, current_role, status, kind, spawned_by)
SELECT f.project_id, f.id, '코더', 'coder', 'DORMANT', 'agent', 'foreman'
FROM `character` f JOIN project p ON p.id = f.project_id
WHERE p.name = 'ronanlab-infra' AND f.current_role = 'foreman';
