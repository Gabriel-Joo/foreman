-- 0005 알림 기록 (4단계 — 텔레그램을 브리지 경유로)
--
-- 보낸 것만이 아니라 "보내지 않기로 한 것"과 그 규칙도 남긴다 — 누락인지 규칙인지를 나중에 가릴 수 있게
-- (모델이 스크립트를 부르던 때는 런슈즈 75회 · 펫퍼민트 14회의 차이가 누락인지 규칙인지 구분할 수 없었다).
--   kind      turn(턴 종료) · batch(백그라운드 서브에이전트 묶음) · direct(백업 실패 등 브리지 밖)
--   decision  sent · skipped · failed · held(묶음 대기 — 아직 도는 서브에이전트가 있다)
--   rule      skipped · held의 이유(config/notify.toml의 어느 규칙)
-- turn_id + kind UNIQUE — 한 턴에 같은 종류 알림은 한 번(재시작 · 신호 중복에도)

CREATE TABLE notification (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id  BIGINT UNSIGNED NULL,
  turn_id     BIGINT UNSIGNED NULL,
  kind        VARCHAR(8)  NOT NULL,
  end_reason  VARCHAR(16) NULL,
  decision    VARCHAR(8)  NOT NULL,
  rule        VARCHAR(64) NULL,
  text        TEXT NULL,
  error       VARCHAR(255) NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  sent_at     DATETIME(3) NULL,
  UNIQUE KEY uq_notif_turn_kind (turn_id, kind),
  KEY ix_notif_session (session_id, created_at)
) ENGINE=InnoDB;

-- 서브에이전트가 어느 알림에 실렸나 — 부모 턴 알림 · 묶음 알림에서 같은 서브에이전트를 두 번 세지 않는다
ALTER TABLE subagent_run ADD COLUMN notified_at DATETIME(3) NULL AFTER reported_duration_ms;
