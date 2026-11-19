-- 0034 포스트잇이 다른 저장소에 커밋한 일의 기록(11-19 사용자 결정 E1)
--
-- 사람이 포스트잇 창에서 [TODO로] 또는 TODO 항목의 [지우기]를 누르면 브리지가 그 저장소 원본 폴더에 직접 커밋한다.
-- 누른 것마다 한 줄을 남긴다. 성공만이 아니라 거부도 남겨, 창을 다시 열어도 까닭이 보이게 한다
-- (열린 포스트잇에는 메모 칸이 없어 닫힌 칸 closed_note를 거부에 쓸 수 없다).
--
-- postit_repo_log
--   project    프로젝트 이름(project.name)
--   repo       저장소 폴더 이름(경로 끝, 사람이 어느 저장소인지 알아보게)
--   postit_id  누른 포스트잇(todo_inbox.id). TODO 항목 [지우기]는 포스트잇이 없어 NULL
--   action     add([TODO로]가 항목을 더함) · remove(TODO 항목을 지움)
--   ok         1 = 커밋했다, 0 = 거부했다
--   todo_id    TODO 번호(예: infra-12). [TODO로]를 거부한 때는 번호를 아직 못 정해 NULL
--   commit     커밋 짧은 해시(성공일 때만)
--   note       사람이 읽는 한 줄(무엇을 어느 저장소에 넣었다 · 왜 못 했다)
--
-- 되돌리기:
--   DROP TABLE postit_repo_log;
CREATE TABLE postit_repo_log (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project     VARCHAR(64) NOT NULL,
  repo        VARCHAR(128) NOT NULL,
  postit_id   BIGINT UNSIGNED NULL,
  action      VARCHAR(8) NOT NULL,
  ok          BOOLEAN NOT NULL,
  todo_id     VARCHAR(40) NULL,
  `commit`    VARCHAR(16) NULL,
  note        VARCHAR(1000) NOT NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_repolog_project (project, id),
  KEY ix_repolog_postit (postit_id)
) ENGINE=InnoDB;
