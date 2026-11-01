-- 0001 초기 스키마 (README 5장, 2026-11-02 1단계 설계 승인분)
--
-- 공통
--   InnoDB · utf8mb4. 시간은 전부 UTC DATETIME(3) (서버 default-time-zone '+00:00')
--   enum은 MySQL ENUM이 아니라 VARCHAR + 애플리케이션 검사(bridge/models.py). 값이 단계마다 늘어 ALTER를 피한다
--   `character`는 MySQL 예약어 — SQL에서는 항상 백틱
--
-- README와 달라진 점(승인됨)
--   transcript_file 분리: 읽기 위치(inode · offset · last_uuid)를 파일 단위로. --resume은 같은 파일에 이어 쓰므로
--     한 파일이 여러 character_session에 걸치고, 와처는 어느 캐릭터 것인지 알기 전에 파일을 먼저 발견한다
--   character_session.token_usage 없음: message에서 집계한다
--   subagent_run.reported_*: <task-notification>의 subagent_tokens 등. 소수에만 있어 보조 검증용(3.11)
--   build · summary는 이 파일에 없다: 인과 체인 · 수명 정책을 검토한 뒤(9 · 11단계) 마이그레이션을 더한다
--   character.sprite NULL 허용: 테마·스프라이트는 10단계. 임의값을 넣지 않는다(NULL = 아직 안 정함)
--   event에 FK 없음: 아래 event 주석
--   event.target_truncated: target은 1,024자에서 자르고 원문은 payload에(실측 Bash 명령의 25%가 1,024자 초과)

CREATE TABLE project (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(64)  NOT NULL,
  repo_path   VARCHAR(512) NOT NULL,
  repo_url    VARCHAR(512) NULL,
  namespace   VARCHAR(63)  NULL,                 -- k8s 네임스페이스
  created_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_project_name (name)
) ENGINE=InnoDB;

CREATE TABLE `character` (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  project_id      BIGINT UNSIGNED NULL,          -- null = 떠돌이
  parent_id       BIGINT UNSIGNED NULL,          -- 누가 낳았나
  name            VARCHAR(64)  NOT NULL,
  sprite          VARCHAR(64)  NULL,             -- 10단계(테마 렌더러)에서 정한다
  current_role    VARCHAR(16)  NOT NULL,         -- foreman coder cicd inspector helper infra
  status          VARCHAR(16)  NOT NULL,         -- ACTIVE IDLE DORMANT SUSPENDED STALE
  kind            VARCHAR(8)   NOT NULL,         -- agent infra
  infra_type      VARCHAR(32)  NULL,             -- jenkins harbor argocd prometheus llm
  infra_source    VARCHAR(8)   NULL,             -- k8s host external
  infra_endpoint  VARCHAR(512) NULL,
  home_position   JSON NULL,
  watch_targets   JSON NULL,                     -- systemd 유닛 · docker 컨테이너 이름(2.2)
  spawned_by      VARCHAR(8)   NOT NULL,         -- user foreman cicd auto
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  retired_at      DATETIME(3)  NULL,
  UNIQUE KEY uq_character_name (project_id, name),
  CONSTRAINT fk_character_project FOREIGN KEY (project_id) REFERENCES project(id),
  CONSTRAINT fk_character_parent  FOREIGN KEY (parent_id)  REFERENCES `character`(id)
) ENGINE=InnoDB;

CREATE TABLE transcript_file (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  path           VARCHAR(512) NOT NULL,
  cc_session_id  CHAR(36) CHARACTER SET ascii NOT NULL,
  agent_id       VARCHAR(64) CHARACTER SET ascii NULL,   -- 서브에이전트 파일이면
  inode          BIGINT UNSIGNED NOT NULL,
  read_offset    BIGINT UNSIGNED NOT NULL DEFAULT 0,      -- 어디까지 읽었나(바이트). 끝나지 않은 마지막 줄 앞
  last_uuid      CHAR(36) CHARACTER SET ascii NULL,
  first_seen_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_tf_path (path),
  KEY ix_tf_session (cc_session_id)
) ENGINE=InnoDB;

CREATE TABLE character_session (
  id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  character_id        BIGINT UNSIGNED NOT NULL,
  type                VARCHAR(8)  NOT NULL,      -- agent shell
  role                VARCHAR(16) NOT NULL,      -- 이 세션에서의 역할(캐릭터 역할과 별개로 이력 보존)
  tmux_pane           VARCHAR(16) NULL,          -- %N. tmux 밖 기존 세션을 입양하면 null
  pid                 INT UNSIGNED NULL,
  cc_session_id       CHAR(36) CHARACTER SET ascii NULL,   -- --resume은 같은 ID — 여러 행에 걸칠 수 있다
  transcript_file_id  BIGINT UNSIGNED NULL,
  worktree_path       VARCHAR(512) NULL,
  branch              VARCHAR(255) NULL,
  wake_reason         VARCHAR(16) NOT NULL,      -- user auto_failure foreman
  attached_at         DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  detached_at         DATETIME(3) NULL,
  KEY ix_cs_cc_session (cc_session_id),
  KEY ix_cs_attached (character_id, detached_at),
  CONSTRAINT fk_cs_character  FOREIGN KEY (character_id)       REFERENCES `character`(id),
  CONSTRAINT fk_cs_transcript FOREIGN KEY (transcript_file_id) REFERENCES transcript_file(id)
) ENGINE=InnoDB;

CREATE TABLE turn (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id   BIGINT UNSIGNED NOT NULL,
  seq          INT UNSIGNED NOT NULL,
  prompt_uuid  CHAR(36) CHARACTER SET ascii NULL,
  prompt_text  MEDIUMTEXT NULL,                  -- 실측 최대 18,395자 / 32,688바이트. TEXT(64KB)도 들어가지만 긴 지시서를 붙여넣으므로 여유
  started_at   DATETIME(3) NOT NULL,
  ended_at     DATETIME(3) NULL,
  end_reason   VARCHAR(16) NULL,                 -- stop stop_failure interrupted session_end process_lost
  duration_ms  INT UNSIGNED NULL,                -- system/turn_duration의 durationMs
  compacted    BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE KEY uq_turn_seq (session_id, seq),
  UNIQUE KEY uq_turn_prompt (prompt_uuid),
  CONSTRAINT fk_turn_session FOREIGN KEY (session_id) REFERENCES character_session(id)
) ENGINE=InnoDB;

CREATE TABLE subagent_run (
  id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id              BIGINT UNSIGNED NOT NULL,      -- 부모 character_session
  transcript_file_id      BIGINT UNSIGNED NULL,
  agent_id                VARCHAR(64) CHARACTER SET ascii NOT NULL,
  tool_use_id             VARCHAR(64) CHARACTER SET ascii NOT NULL,
  spawn_turn_id           BIGINT UNSIGNED NULL,          -- 띄운 턴. 토큰 · 이벤트는 여기에 귀속
  result_turn_id          BIGINT UNSIGNED NULL,          -- hand-back을 받은 턴
  agent_type              VARCHAR(64) NOT NULL,
  mode                    VARCHAR(12) NOT NULL,          -- foreground background fork
  spawn_depth             TINYINT UNSIGNED NOT NULL DEFAULT 1,
  description             VARCHAR(512) NULL,
  started_at              DATETIME(3) NULL,              -- 첫 · 마지막 줄 timestamp(system 기록 없음)
  ended_at                DATETIME(3) NULL,
  status                  VARCHAR(8) NOT NULL,           -- running done failed stopped
  token_input             INT UNSIGNED NOT NULL DEFAULT 0,
  token_output            INT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_read        BIGINT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_creation    INT UNSIGNED NOT NULL DEFAULT 0,
  output_tokens_reliable  BOOLEAN NOT NULL DEFAULT FALSE,  -- 서브에이전트 줄의 output은 응답 시작 시점 값
  reported_tokens         INT UNSIGNED NULL,             -- <task-notification> subagent_tokens (보조 검증용)
  reported_tool_uses      INT UNSIGNED NULL,
  reported_duration_ms    INT UNSIGNED NULL,
  UNIQUE KEY uq_sr_agent (agent_id),
  KEY ix_sr_running (session_id, status),
  KEY ix_sr_spawn (spawn_turn_id),
  CONSTRAINT fk_sr_session    FOREIGN KEY (session_id)         REFERENCES character_session(id),
  CONSTRAINT fk_sr_transcript FOREIGN KEY (transcript_file_id) REFERENCES transcript_file(id),
  CONSTRAINT fk_sr_spawn_turn FOREIGN KEY (spawn_turn_id)      REFERENCES turn(id),
  CONSTRAINT fk_sr_result_turn FOREIGN KEY (result_turn_id)    REFERENCES turn(id)
) ENGINE=InnoDB;

-- API 응답 하나(message.id)가 한 행. 트랜스크립트에서는 content 블록마다 줄이 쪼개지지만 usage는 같다
CREATE TABLE message (
  id                    VARCHAR(64) CHARACTER SET ascii PRIMARY KEY,   -- msg_…
  turn_id               BIGINT UNSIGNED NULL,     -- 서브에이전트 메시지는 띄운 턴. 턴을 못 찾은 줄(입양 직후 등)은 null
  subagent_id           BIGINT UNSIGNED NULL,
  model                 VARCHAR(64) NOT NULL,
  stop_reason           VARCHAR(32) NULL,
  request_id            VARCHAR(64) CHARACTER SET ascii NULL,
  token_input           INT UNSIGNED NOT NULL DEFAULT 0,
  token_output          INT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_read      INT UNSIGNED NOT NULL DEFAULT 0,
  token_cache_creation  INT UNSIGNED NOT NULL DEFAULT 0,
  created_at            DATETIME(3) NOT NULL,
  KEY ix_msg_turn (turn_id),
  KEY ix_msg_subagent (subagent_id),
  CONSTRAINT fk_msg_turn     FOREIGN KEY (turn_id)     REFERENCES turn(id),
  CONSTRAINT fk_msg_subagent FOREIGN KEY (subagent_id) REFERENCES subagent_run(id)
) ENGINE=InnoDB;

-- event: FK를 두지 않는다(애플리케이션이 보장 — 쓰는 곳은 bridge/store.py 하나)
--   - hook 이벤트가 그 사건을 만드는 트랜스크립트 줄(message · turn 행)보다 먼저 온다. FK가 있으면 순서를 강제하거나 나중에 채워야 한다
--   - 가장 자주 쓰는 테이블. 행마다 부모 조회 다섯 번 + FK용 보조 인덱스 유지를 없앤다
--   - (참고) 보관 기간 일괄 삭제는 event가 자식이라 FK 검사가 걸리지 않는다. 느려지는 것은 부모(turn · message)를 지울 때다
--   고아 행은 정기 점검 쿼리로 찾는다. 정렬 키는 id(적재 순서 = 파일 기록 순서). ts는 표시용
CREATE TABLE event (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  uuid              CHAR(36) CHARACTER SET ascii NULL,   -- 트랜스크립트 줄 uuid. 재적재 · hook 중복 방지
  parent_uuid       CHAR(36) CHARACTER SET ascii NULL,
  session_id        BIGINT UNSIGNED NULL,      -- 호스트 감시 이벤트(restart_loop)는 세션이 없다
  character_id      BIGINT UNSIGNED NULL,      -- 둘 다 없으면 포먼 경고 목록
  turn_id           BIGINT UNSIGNED NULL,
  message_id        VARCHAR(64) CHARACTER SET ascii NULL,
  subagent_id       BIGINT UNSIGNED NULL,
  tool_use_id       VARCHAR(64) CHARACTER SET ascii NULL,
  source            VARCHAR(10) NOT NULL,      -- hook transcript poll debug
  ts                DATETIME(3) NOT NULL,      -- 표시용. 정렬에 쓰지 않는다
  type              VARCHAR(24) NOT NULL,
  tool              VARCHAR(64) NULL,
  target            VARCHAR(1024) NULL,        -- 마스킹 후 1,024자까지
  target_truncated  BOOLEAN NOT NULL DEFAULT FALSE,   -- 잘렸으면 원문(마스킹 후)은 payload.target_full
  status            VARCHAR(10) NULL,
  commit_sha        CHAR(40) CHARACTER SET ascii NULL,
  payload           JSON NULL,
  UNIQUE KEY uq_event_uuid (uuid),
  KEY ix_ev_session_ts (session_id, ts),
  KEY ix_ev_turn (turn_id),
  KEY ix_ev_char (character_id, type, ts),
  KEY ix_ev_subagent (subagent_id),
  KEY ix_ev_tool_use (tool_use_id),
  KEY ix_ev_commit (commit_sha),
  KEY ix_ev_ts (ts)                            -- 보관 기간 지난 것 일괄 삭제(LIMIT 묶음)
) ENGINE=InnoDB;
