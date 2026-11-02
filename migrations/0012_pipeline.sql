-- 0012 CI/CD 인과 체인 (로드맵 8단계 — 11-02에 9단계와 순서를 바꿨다)
--
-- 축은 커밋 SHA다. 캐릭터가 파일을 고쳤다 → 이 커밋 → 이 빌드 → 이 태그 → 이 리비전 동기화 → 실패, 여기서.
--
-- git_commit   프로젝트 저장소(같은 서버의 로컬 git)에서 본 커밋. GitLab은 돌고 있지 않고 원격은 GitHub(Access에 막혀 웹훅이 못 온다)
--              이므로 커밋 단계는 로컬 저장소를 폴링한다. 어느 세션이 만들었는지(session_id · event_id)와 push 여부(pushed_at)
-- build        단계 실행 하나가 한 행 — stage = jenkins harbor argocd (README 5장 build, 1단계에서 보류했던 것.
--              README의 gitlab 단계는 git_commit이 맡는다). commit_sha는 그 단계가 다룬 머리 커밋
--              (Jenkins GIT_COMMIT · Harbor 태그 · ArgoCD 이미지 태그가 가리키는 것)
--              external_id: jenkins = '<job>#<번호>', harbor = '<repo>@<digest>', argocd = '<app>@<리비전>'
-- build_commit 빌드 하나에 묶인 커밋들 — Jenkins는 2분마다 폴링하므로 그 사이 push된 커밋 여럿이 빌드 하나가 된다
--              (킥오프 설계 검토에서 지적한 것). 머리 커밋이 아닌 내 커밋도 이 표로 그 빌드를 찾는다
-- character.last_seen_at  인프라 캐릭터 생존(폴링) — 마지막으로 응답한 때

CREATE TABLE git_commit (
  sha           CHAR(40) CHARACTER SET ascii PRIMARY KEY,
  project_id    BIGINT UNSIGNED NOT NULL,
  session_id    BIGINT UNSIGNED NULL,          -- 커밋을 만든 CC 세션(Bash git commit 도구 호출로 찾는다). 사람이 쳤으면 null
  character_id  BIGINT UNSIGNED NULL,
  event_id      BIGINT UNSIGNED NULL,          -- 그 tool_use 이벤트(event.commit_sha도 채운다)
  author        VARCHAR(128) NULL,
  subject       VARCHAR(512) NULL,
  files         INT UNSIGNED NULL,
  committed_at  DATETIME(3) NOT NULL,
  seen_at       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  pushed_at     DATETIME(3) NULL,              -- origin/<브랜치>에 들어간 것을 본 때
  KEY ix_gc_project (project_id, committed_at),
  KEY ix_gc_session (session_id),
  CONSTRAINT fk_gc_project FOREIGN KEY (project_id) REFERENCES project(id)
) ENGINE=InnoDB;

CREATE TABLE build (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  project_id    BIGINT UNSIGNED NOT NULL,
  character_id  BIGINT UNSIGNED NULL,          -- 이 변경을 만든 캐릭터(머리 커밋의 세션 캐릭터)
  infra_character_id BIGINT UNSIGNED NULL,     -- 이 단계를 맡은 인프라 캐릭터(Jenkins · Harbor · ArgoCD)
  stage         VARCHAR(8)  NOT NULL,          -- git jenkins harbor argocd
  external_id   VARCHAR(255) NOT NULL,
  commit_sha    CHAR(40) CHARACTER SET ascii NULL,
  tag           VARCHAR(128) NULL,             -- 이미지 태그(커밋 12자리)
  status        VARCHAR(8)  NOT NULL,          -- running success failed
  step          VARCHAR(64) NULL,              -- 깨진 곳(Jenkins 스테이지 이름 · ArgoCD 단계)
  started_at    DATETIME(3) NOT NULL,
  ended_at      DATETIME(3) NULL,
  log_url       VARCHAR(512) NULL,
  message       TEXT NULL,                     -- 실패 사유(마스킹)
  payload       JSON NULL,
  updated_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_build_ext (project_id, stage, external_id),
  KEY ix_build_commit (commit_sha),
  KEY ix_build_tag (tag),
  KEY ix_build_recent (project_id, started_at),
  CONSTRAINT fk_build_project FOREIGN KEY (project_id) REFERENCES project(id)
) ENGINE=InnoDB;

CREATE TABLE build_commit (
  build_id    BIGINT UNSIGNED NOT NULL,
  commit_sha  CHAR(40) CHARACTER SET ascii NOT NULL,
  PRIMARY KEY (build_id, commit_sha),
  KEY ix_bc_commit (commit_sha),
  CONSTRAINT fk_bc_build FOREIGN KEY (build_id) REFERENCES build(id)
) ENGINE=InnoDB;

ALTER TABLE `character` ADD COLUMN last_seen_at DATETIME(3) NULL AFTER watch_targets;
