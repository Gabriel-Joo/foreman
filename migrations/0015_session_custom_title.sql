-- 0015 세션 이름을 사람이 붙인다(11-05 사용자 요청)
-- title은 CC가 붙이는 ai-title(대화가 흘러가며 바뀐다). custom_title은 사람이 패널에서 붙인 이름 — 있으면 이것을 먼저 쓴다.
-- 세션을 다시 띄워도(claude --resume — 같은 cc_session_id) 같은 행이라 그대로 남는다. NULL로 되돌리면 자동 제목
ALTER TABLE character_session
  ADD COLUMN custom_title VARCHAR(255) NULL AFTER title;
