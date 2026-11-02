-- 0010 승인 대기 (로드맵 5단계)
--
-- 승인 창이 뜨면(우리 정책의 ask든 CC 자체 판단이든) PermissionRequest hook이 브리지에 와서 한 행이 생긴다.
-- 터미널 · 브라우저 · 시간 초과 중 먼저 온 것이 결정한다(실측: 터미널에서 먼저 답하면 기다리던 hook과 무관하게 진행).
--   status      pending allowed denied terminal timeout abandoned
--               terminal = 터미널에서 답했다(결과는 tool_result의 permissionDecision — terminal_decision)
--               abandoned = 브리지가 다시 떠서 기다리던 연결이 끊겼다(터미널 승인 창은 그대로 남는다)
--   rule        우리 정책의 규칙 이름, CC 자체 판단으로 뜬 창이면 cc
-- 자동 통과 · pass를 포함한 모든 PreToolUse 판정은 event(type=approval_req)에 남는다 — 여기는 사람이 답해야 했던 것만

CREATE TABLE approval (
  id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id         BIGINT UNSIGNED NULL,
  turn_id            BIGINT UNSIGNED NULL,
  tool_use_id        VARCHAR(64) CHARACTER SET ascii NULL,
  tool               VARCHAR(64) NOT NULL,
  target             VARCHAR(1024) NULL,            -- 마스킹 후
  rule               VARCHAR(64) NULL,
  reason             VARCHAR(255) NULL,
  status             VARCHAR(12) NOT NULL,
  decided_by         VARCHAR(12) NULL,              -- browser terminal timeout bridge
  message            VARCHAR(255) NULL,             -- 거부 이유(모델에게 간다)
  terminal_decision  VARCHAR(16) NULL,              -- 터미널에서 답했을 때 CC가 기록한 결정(accept / reject)
  created_at         DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  decided_at         DATETIME(3) NULL,
  KEY ix_appr_status (status, created_at),
  KEY ix_appr_session (session_id, created_at),
  KEY ix_appr_tool_use (tool_use_id)
) ENGINE=InnoDB;
