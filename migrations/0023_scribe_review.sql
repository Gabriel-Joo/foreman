-- 0023 서기 검토 기록(12b, 11-06, bridge/evidence.py) — 서기 브랜치를 합칠 때 남긴다.
--   marks · bad · unsupported  근거 표시 수 · 틀린 근거 · 근거 없는 줄(의심)
--   draft_lines · revision_lines  서기 첫 초안의 줄 수 · 사람이 의견을 준 뒤 고친 줄 수(더한 + 뺀). 고친 양이 줄어드는지가
--                                 12d 하루 끝 자동 초안을 열지 정하는 숫자다(docs/12_scribe.md 「4.」 6)
--   detail  JSON — 파일별 틀린 근거 · 근거 없는 줄
-- 되돌리기: DROP TABLE scribe_review;
CREATE TABLE scribe_review (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id      BIGINT UNSIGNED NOT NULL,
  task            VARCHAR(16) NULL,
  branch          VARCHAR(128) NULL,
  marks           INT NOT NULL DEFAULT 0,
  bad             INT NOT NULL DEFAULT 0,
  unsupported     INT NOT NULL DEFAULT 0,
  draft_lines     INT NOT NULL DEFAULT 0,
  revision_lines  INT NOT NULL DEFAULT 0,
  detail          MEDIUMTEXT NULL,
  merged_at       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_scribe_review_session (session_id),
  CONSTRAINT fk_scribe_review_session FOREIGN KEY (session_id) REFERENCES character_session (id)
) ENGINE=InnoDB;
