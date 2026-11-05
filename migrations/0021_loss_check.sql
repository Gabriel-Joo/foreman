-- 0021 인계 2판 d [잃은 것 보기](11-06, docs/11_handoff_v2.md 3장, bridge/losscheck.py)
-- 세션 트랜스크립트에서 압축 구간별 사람 프롬프트를 뽑아 `claude -p`(기본 Sonnet, config/models.toml [tasks])로 판정한다 —
-- 오래 지켜야 하는 지시 · 결정이 지금 맥락에 남았나(살아 있음 · 약해짐 · 사라짐 · 뒤집힘 · 끝남).
--   status   running · done · failed (브리지가 다시 뜨면 남은 running은 failed — 조용히 멈춘 채 남지 않게)
--   items    JSON 배열 — 판정 항목 {id, ts, kind, quote, gist, status, where, dropped_at, missing, why_matters}(비밀값 가림)
--   runs     JSON 배열 — 묶음마다 {group, prompts, items, empty, skipped, ms, cost_usd, error}
--   workdir  판정 재료(프롬프트 원문 · 요약 전문)가 있는 저장소 밖 폴더(~/.foreman/losscheck-*, 700)
-- promotion.loss_check_id — 문서로 옮기기(c) 목록을 뽑을 때 같이 넣은 점검(사라짐 · 약해짐)
-- 되돌리기: ALTER TABLE promotion DROP FOREIGN KEY fk_promotion_loss_check, DROP COLUMN loss_check_id; DROP TABLE loss_check;
CREATE TABLE loss_check (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id    BIGINT UNSIGNED NOT NULL,
  status        VARCHAR(12) NOT NULL,
  model         VARCHAR(40) NULL,
  workdir       VARCHAR(512) NULL,
  segments      INT NULL,
  prompts       INT NULL,
  groups_total  INT NULL,
  groups_done   INT NOT NULL DEFAULT 0,
  items         MEDIUMTEXT NULL,
  runs          MEDIUMTEXT NULL,
  cost_usd      DECIMAL(10,4) NULL,
  error         VARCHAR(512) NULL,
  created_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_loss_check_session (session_id, id),
  CONSTRAINT fk_loss_check_session FOREIGN KEY (session_id) REFERENCES character_session (id)
) ENGINE=InnoDB;

ALTER TABLE promotion
  ADD COLUMN loss_check_id BIGINT UNSIGNED NULL AFTER summary_id,
  ADD CONSTRAINT fk_promotion_loss_check FOREIGN KEY (loss_check_id) REFERENCES loss_check (id);
