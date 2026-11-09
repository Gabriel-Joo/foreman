-- 0028 받는 함의 받는 사람(11-09 사용자 — 코더 상주 · "맡길 일 N", log/coder_resident_20261109.md)
-- [＋ 할 일]에서 누구에게 줄지 고른다: scribe(서기 정리 — 「나중에 할 일 정리」가 README 표로 옮김, 기본) · coder(코더에게 — 그 방 코더의 "맡길 일")
-- 상태는 여전히 계산한다(bridge/scribe_room.py _INBOX_STATE). 코더 몫은 합쳐지면 "옮김" 대신 "끝남"
--   되돌리기: ALTER TABLE todo_inbox DROP KEY ix_inbox_assignee, DROP COLUMN assignee;  (0027 코드는 이 칸을 모른다 — 지워도 돈다)
ALTER TABLE todo_inbox
  ADD COLUMN assignee VARCHAR(8) NOT NULL DEFAULT 'scribe' AFTER body,
  ADD KEY ix_inbox_assignee (project, assignee, dropped_at);
