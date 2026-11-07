-- 0025 디스패처 노트 · 자동 기상 2단계(11-08, docs/14_dispatcher_note_wake.md)
-- 디스패처는 여전히 부를 때만 claude -p 한 번이다(상주하면 압축 손실). 대신 프로젝트마다 크기를 정한 "노트"를 상황 묶음에 넣는다.
--   kind      thread(진행 중인 일 줄기) · decision(사람이 정한 판단). 구조 · 명령은 쌓지 않는다(CC 메모리 · docs에 있다 — 사본은 낡는다)
--   source    출처: "세션 N" · "log/…md" · "docs/…md" · "dispatch #N"(사람의 요청 글)
--   refs      {"sessions": [..], "summary_id": N, "head": "<그때 HEAD>"} — 확인 뒤 바뀐 것(세션 활동 · 커밋)을 기계로 붙인다
--   고치기는 디스패처가 계획에 제안하고 사람이 [시작]을 누를 때 같이 반영한다. 바꾸면 옛 줄은 retired_at, 새 줄을 넣는다(이력)
CREATE TABLE foreman_note (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project      VARCHAR(64) NOT NULL,
  kind         VARCHAR(10) NOT NULL,
  body         VARCHAR(600) NOT NULL,
  source       VARCHAR(300) NOT NULL,
  refs         JSON NULL,
  checked_at   DATETIME(3) NOT NULL,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  retired_at   DATETIME(3) NULL,
  replaced_by  BIGINT UNSIGNED NULL,
  dispatch_id  BIGINT UNSIGNED NULL,
  PRIMARY KEY (id),
  KEY ix_note_project (project, retired_at)
) ENGINE=InnoDB;

-- 자동 기상 2단계 — 실패 이벤트가 오면 디스패처가 계획만 만들고 사람에게 [시작]?을 묻는다
--   origin    human(사람이 말함) · wake(실패 이벤트)
--   project   계획의 프로젝트(노트 · 지난 디스패치를 프로젝트별로 찾는다)
--   wake_key  같은 실패로 두 번 계획하지 않게(예: build:runshoes:jenkins:runshoes-app#73)
ALTER TABLE dispatch
  ADD COLUMN origin VARCHAR(10) NOT NULL DEFAULT 'human' AFTER id,
  ADD COLUMN project VARCHAR(64) NULL AFTER origin,
  ADD COLUMN wake_key VARCHAR(200) NULL AFTER project,
  ADD COLUMN wake_text VARCHAR(1000) NULL AFTER wake_key,
  ADD KEY ix_dispatch_wake (wake_key),
  ADD KEY ix_dispatch_project (project, created_at);
UPDATE dispatch SET project = JSON_UNQUOTE(JSON_EXTRACT(COALESCE(edited, plan), '$.project')) WHERE project IS NULL AND plan IS NOT NULL;
