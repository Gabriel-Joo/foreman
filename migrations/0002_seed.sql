-- 0002 시드: 프로젝트 3개 + 프로젝트마다 포먼 하나(README 2.4 — 프로젝트마다 상주)
-- 포먼은 평소 세션 없이 서 있으므로 DORMANT. sprite · home_position은 10단계에서 정한다(NULL)
-- repo_url은 지금의 git 원격(GitHub). GitLab은 로드맵 9단계에서 바뀐다

INSERT INTO project (name, repo_path, repo_url, namespace) VALUES
  ('runshoes',            '/home/kopo17/AI_programming/runshoes',            'https://github.com/Gabriel-Joo/runshoes.git',            'runshoes'),
  ('petmint-rag-chatbot', '/home/kopo17/AI_programming/petmint-rag-chatbot', 'https://github.com/Gabriel-Joo/petmint-rag-chatbot.git', 'petmint'),
  ('foreman',             '/home/kopo17/AI_programming/foreman',             'https://github.com/Gabriel-Joo/foreman.git',             NULL);

INSERT INTO `character` (project_id, name, sprite, current_role, status, kind, spawned_by)
SELECT id, '포먼', NULL, 'foreman', 'DORMANT', 'agent', 'user' FROM project ORDER BY id;
