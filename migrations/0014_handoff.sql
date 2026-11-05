-- 0014 세션 인계 · 세션 조작 (11-05, docs/11_handoff.md)
-- summary: 세션이 스스로 쓴 인계 요약. 고치기는 새 행(source=edited, parent_id=원본). 넣을 때는 그 세션의 마지막 ok 행
--   kind    handoff(끝내기 전) · snapshot(지금 요약만)
--   source  self(살아 있는 세션에 물음) · self_headless(죽은 세션을 claude -p --resume으로) · compact(마지막 auto-compact 요약) · edited
--   status  requested · ok · failed · timeout
-- session_action: 끝내기 · 멈춤 · 되살리기 · 작업 중단 · 새로 띄우기 기록. 되살리기는 FOREMAN이 멈춘 것만(이 표로 가린다)
CREATE TABLE summary (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  character_id        BIGINT UNSIGNED NULL,
  session_id          BIGINT UNSIGNED NOT NULL,
  req                 CHAR(6) CHARACTER SET ascii NOT NULL,
  kind                VARCHAR(10) NOT NULL,
  source              VARCHAR(14) NOT NULL,
  status              VARCHAR(10) NOT NULL,
  turn_id             BIGINT UNSIGNED NULL,
  body                MEDIUMTEXT NULL,
  chars               INT UNSIGNED NULL,
  raw                 MEDIUMTEXT NULL,
  error               VARCHAR(512) NULL,
  parent_id           BIGINT UNSIGNED NULL,
  injected_cc_session CHAR(36) CHARACTER SET ascii NULL,
  injected_at         DATETIME(3) NULL,
  created_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_summary_req (req),
  KEY ix_summary_session (session_id, id),
  CONSTRAINT fk_summary_session FOREIGN KEY (session_id) REFERENCES character_session (id),
  CONSTRAINT fk_summary_parent FOREIGN KEY (parent_id) REFERENCES summary (id)
) ENGINE=InnoDB;

CREATE TABLE session_action (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id  BIGINT UNSIGNED NULL,
  action      VARCHAR(12) NOT NULL,
  pid         INT UNSIGNED NULL,
  ok          BOOLEAN NOT NULL,
  detail      VARCHAR(512) NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_action_session (session_id, id),
  KEY ix_action_pid (pid, id)
) ENGINE=InnoDB;
