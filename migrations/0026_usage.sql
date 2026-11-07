-- 0026 사용량 · 한도 역산(11-08, docs/15_usage.md)
-- usage_extra  트랜스크립트에 남지 않는 claude -p(디스패처 · 압축 손실 점검 — --no-session-persistence)의 사용량.
--              `--output-format json`의 modelUsage를 모델마다 한 행. cost_usd는 CC가 정가로 계산한 값
--   source  dispatch · losscheck   ref_id  dispatch.id · loss_check.id
CREATE TABLE usage_extra (
  id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source                VARCHAR(16) NOT NULL,
  ref_id                BIGINT UNSIGNED NULL,
  project               VARCHAR(64) NULL,
  model                 VARCHAR(64) NOT NULL,
  token_input           INT UNSIGNED NOT NULL DEFAULT 0,
  token_output          INT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_read      BIGINT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_creation  INT UNSIGNED NOT NULL DEFAULT 0,
  cost_usd              DECIMAL(12,6) NULL,
  created_at            DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_ue_created (created_at),
  KEY ix_ue_source (source, ref_id)
) ENGINE=InnoDB;

-- usage_observation  한도 %를 본 것 하나 — 사람이 넣거나(human) CC tmux 화면에서 읽었거나(screen)
--   limit_key  session_5h · weekly_all · weekly_<모델> …(사용자가 CC에서 확인해 알려 준 종류)
--   seen_usd   그 시각 그 창에서 FOREMAN이 본 환산액(넣을 때 계산해 둔다 — 가중치를 바꾸면 다시 계산)
CREATE TABLE usage_observation (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  limit_key    VARCHAR(32) NOT NULL,
  pct          DECIMAL(5,2) NOT NULL,
  observed_at  DATETIME(3) NOT NULL,
  reset_at     DATETIME(3) NULL,
  source       VARCHAR(8) NOT NULL,
  raw          VARCHAR(300) NULL,
  seen_usd     DECIMAL(12,4) NULL,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY ix_uo_limit (limit_key, observed_at),
  UNIQUE KEY uq_uo_raw (limit_key, source, raw)
) ENGINE=InnoDB;
