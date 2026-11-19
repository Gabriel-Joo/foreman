-- 0035 서기실 전체 줄(11-19 사용자 결정, bridge/scribe_queue.py)
--
-- 서기실 「포트폴리오 쓰기」와 「기술문서 쓰기」의 [전체]는 편을 한꺼번에 띄우지 않고 줄을 세워 한 편씩 돈다.
-- 한 편이 끝남 = 그 편 세션의 브랜치가 main에 합쳐졌을 때. 브리지를 다시 띄워도 줄이 이어지게 표에 둔다
-- (메모리에만 두면 11-19 덮기 단추처럼 다시 띄운 뒤 사라진다).
--
-- scribe_queue       줄 하나. 한 프로젝트에 도는 줄(running, paused)은 하나뿐이다(코드가 지킨다)
--   project          프로젝트 이름(project.name)
--   task             portfolio, techdoc(서기실 PIECE_TASKS). 두 일이 이 표 한 벌을 나눠 쓴다
--   state            running(도는 중), paused(멈추기. 지금 편이 끝나면 다음 편을 띄우지 않는다), done(남은 편 없음), closed(사람이 닫음)
--   note             사람이 읽는 한 줄(멈춘 까닭 등)
--   stall_told       지금 편이 오래 안 끝난다고 알린 편 id(같은 편을 두 번 알리지 않게)
--
-- scribe_queue_item  줄에 선 편 하나
--   pos              차례(0부터)
--   topic, title     편 이름(원고 폴더 아래 경로에서 .md를 뗀 것)과 제목
--   state            waiting, running, merged, failed, held(사람 승인이라 미룸)
--   session_id       그 편을 맡은 서기 세션(character_session.id)
--   how              merged일 때 auto(카드 없이 합침), card(카드로 합침)
--   reason           failed, held의 까닭, running이면 지금 무엇을 기다리는지
--   decisions        그 편 세션이 마지막 응답에 남긴 「사람이 정할 것」(줄이 끝나면 한 번에 보인다)
--
-- 더하기만. 되돌리기:
--   DROP TABLE scribe_queue_item; DROP TABLE scribe_queue;
--   (0034 코드는 이 표를 모른다. 지워도 돈다. 줄만 사라진다)
CREATE TABLE scribe_queue (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project     VARCHAR(64) NOT NULL,
  task        VARCHAR(16) NOT NULL,
  state       VARCHAR(8) NOT NULL,
  note        VARCHAR(500) NULL,
  stall_told  BIGINT UNSIGNED NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  ended_at    DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY ix_squeue_project (project, state)
) ENGINE=InnoDB;

CREATE TABLE scribe_queue_item (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  queue_id    BIGINT UNSIGNED NOT NULL,
  pos         INT NOT NULL,
  topic       VARCHAR(120) NOT NULL,
  title       VARCHAR(300) NOT NULL,
  state       VARCHAR(8) NOT NULL,
  session_id  BIGINT UNSIGNED NULL,
  how         VARCHAR(8) NULL,
  reason      VARCHAR(1000) NULL,
  decisions   TEXT NULL,
  started_at  DATETIME(3) NULL,
  ended_at    DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY ix_squeue_item_queue (queue_id, pos),
  KEY ix_squeue_item_session (session_id)
) ENGINE=InnoDB;
