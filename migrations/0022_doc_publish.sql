-- 0022 Notion 게시 기록(11-06, docs/12_scribe.md 「5. Notion 연동」, bridge/notion.py)
-- 원본은 git 마크다운, Notion은 게시판. 같은 원본은 같은 Notion 페이지에 내용을 갈아 끼운다(URL 그대로).
--   path        저장소 기준 원본 경로(log/retro_20261105_foreman.md). 묶음 페이지(「회고」)는 '@section/<이름>'
--   kind        doc · section
--   notion_page_id  우리가 만든 페이지(대시 없이). 고치기 · 내리기는 이 페이지만, 매번 루트 아래인지 Notion에서 다시 본다
--   commit_sha · content_hash  마지막으로 올린 원본 — 해시가 같으면 다시 올리지 않는다, 다르면 "원본이 바뀜"
--   status      published · archived(휴지통 — Notion에서 30일 되살릴 수 있다) · failed
-- 되돌리기: DROP TABLE doc_publish;
CREATE TABLE doc_publish (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project         VARCHAR(64) NOT NULL,
  path            VARCHAR(255) NOT NULL,
  kind            VARCHAR(8) NOT NULL DEFAULT 'doc',
  title           VARCHAR(255) NULL,
  notion_page_id  CHAR(32) CHARACTER SET ascii NULL,
  parent_page_id  CHAR(32) CHARACTER SET ascii NULL,
  commit_sha      VARCHAR(40) CHARACTER SET ascii NULL,
  content_hash    CHAR(64) CHARACTER SET ascii NULL,
  status          VARCHAR(10) NOT NULL DEFAULT 'published',
  url             VARCHAR(512) NULL,
  error           VARCHAR(512) NULL,
  created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_doc_publish_path (project, path)
) ENGINE=InnoDB;
