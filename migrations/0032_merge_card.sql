-- 0032 합치기 카드를 DB에 남김(11-13 사용자 결정, log/mergeprep_db_20261113.md)
-- 11-13: 관리자가 319 카드를 승인해 합친 뒤 브리지를 다시 띄우자 카드(메모리에만 있었다)와 정리 후보 6개가 사라졌다.
-- 카드 하나 = 세션 하나(bridge/mergeprep.py MergePrep.cards의 열쇠와 같다). 카드 전부(Card의 칸 — 커밋 · 바뀐 파일 · 충돌 ·
-- 정리 후보 · 승인자 · human_why · 결과 · 오류 …)는 card JSON에 담고, 고를 때 쓰는 것만 칸으로 뺀다.
--   head        브랜치 끝 커밋(바뀌면 카드를 다시 만든다)
--   status      ready · merging · merged · conflict_sent · conflict_manager · failed
--   made_at     카드를 처음 만든 시각(「오래됨」의 기준 — 브리지를 다시 띄워도 그대로)
--   updated_at  카드가 마지막으로 바뀐 시각(끝난 카드를 남기는 시간의 기준)
-- 브리지가 메모리 카드와 맞춘다: 바뀐 카드는 쓰고, 메모리에서 치운 카드는 지운다. 뜰 때 이 표에서 되살린다.
-- 더하기만 — 되돌리기: DROP TABLE merge_card;  (0031 코드는 이 표를 모른다 — 지워도 돈다. 카드는 메모리로만 돈다)
CREATE TABLE merge_card (
  session_id  BIGINT UNSIGNED NOT NULL,
  project     VARCHAR(64) NULL,
  head        VARCHAR(64) NOT NULL,
  status      VARCHAR(20) NOT NULL,
  card        JSON NOT NULL,
  made_at     DATETIME(3) NOT NULL,
  updated_at  DATETIME(3) NOT NULL,
  saved_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (session_id),
  KEY ix_mcard_project (project)
) ENGINE=InnoDB;
