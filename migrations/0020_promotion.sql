-- 0020 인계 2판 ① 문서로 옮기기(11-05, docs/11_handoff_v2.md 2장 ①, bridge/promote.py)
-- 세션이 "대화에서 정했지만 문서에 없는 것"을 목록으로 내고(1/2), 사람이 패널에서 고치고 승인한 것만 세션이 문서에 쓰고 커밋한다(2/2).
-- 브리지는 그 커밋을 git으로 확인한다(있나 · 메시지 머리 · 승인한 파일만 바뀌었나) — 조용히 빠지거나 다른 파일을 고치면 write_failed.
--   status   requested(목록 기다림) · listed(사람 차례) · failed · timeout · writing(쓰기 기다림) · written · write_failed
--   items    JSON 배열 — {id, kind, what, quote, dest, section, why, state: pending|approved|dropped}
--   summary_id  목록을 뽑을 때 같이 넣은 인계(그 「문서와 다른 지금」 절). 없으면 NULL
--   base_head   쓰기 요청 때의 HEAD — 확인은 이 뒤의 커밋만 본다
--   result   JSON — 확인 결과 {ok, problems, files, memory, skipped}
-- 되돌리기: DROP TABLE promotion;
CREATE TABLE promotion (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id  BIGINT UNSIGNED NOT NULL,
  summary_id  BIGINT UNSIGNED NULL,
  req         CHAR(6) CHARACTER SET ascii NOT NULL,
  write_req   CHAR(6) CHARACTER SET ascii NULL,
  status      VARCHAR(12) NOT NULL,
  items       MEDIUMTEXT NULL,
  base_head   CHAR(40) CHARACTER SET ascii NULL,
  commit_sha  CHAR(40) CHARACTER SET ascii NULL,
  result      MEDIUMTEXT NULL,
  raw         MEDIUMTEXT NULL,
  error       VARCHAR(512) NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_promotion_req (req),
  KEY ix_promotion_session (session_id, id),
  CONSTRAINT fk_promotion_session FOREIGN KEY (session_id) REFERENCES character_session (id),
  CONSTRAINT fk_promotion_summary FOREIGN KEY (summary_id) REFERENCES summary (id)
) ENGINE=InnoDB;
