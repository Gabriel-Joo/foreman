-- 0027 할 일 받는 함(11-09 사용자 — "할 일에 넣어라"가 메인 세션에 몰려 맥락이 쌓였다, log/dispatch_flow_decision_20261109.md)
-- 사람이 머리줄 [＋ 할 일]에 적은 글을 세션 없이 그대로 둔다. 정리 · 우선순위는 서기가 「나중에 할 일 정리」로 몰아서 한다.
-- 상태는 칸으로 두지 않고 계산한다(bridge/scribe_room.py inbox):
--   taken_by 없음 → 새로 / taken_by 세션이 합쳐짐 → 옮김 / 버려짐 → 다시 새로 / 아직 열림 → 서기가 정리 중
--   dropped_at → 사람이 [버리기]
CREATE TABLE todo_inbox (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project     VARCHAR(64) NOT NULL,
  body        TEXT NOT NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  taken_by    BIGINT UNSIGNED NULL,      -- 이 글을 재료로 받은 서기 세션(character_session.id)
  taken_at    DATETIME(3) NULL,
  dropped_at  DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY ix_inbox_project (project, dropped_at)
) ENGINE=InnoDB;
