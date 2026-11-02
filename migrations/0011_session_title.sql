-- 0011 세션 제목 (6단계 대시보드)
-- 2단계에서 기존 세션을 그 프로젝트의 포먼 캐릭터에 role=coder로 붙였다(입양만, 캐릭터는 포먼만 채용).
-- 그래서 화면에 캐릭터 이름만 쓰면 한 프로젝트의 세션이 모두 "포먼"으로 보였다.
-- 세션을 알아보는 이름은 CC가 스스로 붙이는 제목(트랜스크립트 ai-title 줄의 aiTitle — 대화가 흘러가며 바뀐다)으로 한다.
-- 캐릭터를 세션마다 만들지는 않는다 — 캐릭터는 영속 · 포먼만 채용(README 2.4), 재배치는 캐릭터를 제대로 만들 때
ALTER TABLE character_session
  ADD COLUMN title VARCHAR(255) NULL AFTER cwd;
