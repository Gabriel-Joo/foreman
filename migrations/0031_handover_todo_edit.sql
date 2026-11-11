-- 0031 교장 계획을 관리자에게 넘김 · 받은 할 일 고치기(11-11 C 2물결 「셋」 · 「여섯」, log/coder_c_wave2_20261111.md)
-- dispatch
--   handed_to        계획을 넘겨받은 관리자 세션(character_session.id). 넘긴 뒤에도 status는 planned — 관리자가 /api/foreman/start로 시작한다
--   handed_at        넘긴 시각
--   handed_alert_at  넘긴 지 오래(config/managers.toml [handover] wait_min)인데 시작하지 않아 사람에게 알린 시각(한 번만)
-- todo_inbox
--   edited_at        사람이 목록에서 글을 고친 시각(마지막)
-- 더하기만 — 되돌리기:
--   ALTER TABLE dispatch DROP COLUMN handed_to, DROP COLUMN handed_at, DROP COLUMN handed_alert_at;
--   ALTER TABLE todo_inbox DROP COLUMN edited_at;
--   (0030 코드는 이 칸들을 모른다 — 지우지 않아도 돈다)
ALTER TABLE dispatch
  ADD COLUMN handed_to BIGINT UNSIGNED NULL,
  ADD COLUMN handed_at DATETIME(3) NULL,
  ADD COLUMN handed_alert_at DATETIME(3) NULL;
ALTER TABLE todo_inbox
  ADD COLUMN edited_at DATETIME(3) NULL;
