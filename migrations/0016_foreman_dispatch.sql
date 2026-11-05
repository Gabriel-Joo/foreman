-- 0016 포먼 디스패치(11-05, docs/11_foreman_dispatch.md) — 사람이 "뭘 하려는지" 말하면 포먼(claude -p)이 계획을 낸다.
-- 요청 · 포먼의 계획 · 사람이 고친 계획 · 결과를 남긴다(포먼이 자주 틀리는 유형을 찾아 상황 묶음 · 지시문을 고치려고)
--   status  planned(계획만) · started(시작함) · failed(포먼 호출 실패 · 띄우기 실패) · discarded(안 씀)
CREATE TABLE dispatch (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  request        TEXT NOT NULL,
  context_chars  INT UNSIGNED NULL,
  model          VARCHAR(40) NULL,
  plan           JSON NULL,
  edited         JSON NULL,
  status         VARCHAR(10) NOT NULL,
  error          VARCHAR(1000) NULL,
  ms             INT UNSIGNED NULL,
  session_id     BIGINT UNSIGNED NULL,
  created_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  started_at     DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY ix_dispatch_created (created_at)
) ENGINE=InnoDB;
