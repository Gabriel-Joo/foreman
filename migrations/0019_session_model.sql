-- 0019 세션 모델(11-05 사용자 요청) — 띄울 때 고른 모델(`claude --model` 값). NULL이면 CC 설정을 따랐다(또는 입양한 세션).
-- 실제로 쓴 모델은 message.model(응답마다)이 기준이다 — 세션 안에서 /model로 바꿀 수 있어서 이 칸과 다를 수 있다
ALTER TABLE character_session
  ADD COLUMN model VARCHAR(40) NULL AFTER role;
