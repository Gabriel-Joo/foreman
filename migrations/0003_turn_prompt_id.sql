-- 0003 턴을 CC의 promptId로 묶는다 (2단계 트랜스크립트 실측, log/stage2_transcript_result.md)
--
-- 실측(11-02, 2.1.296~2.1.316): 모든 user 줄에 promptId(uuid)가 있고, 한 턴의 프롬프트 · tool_result ·
-- 중단 표시 · compact 요약이 같은 promptId를 갖는다. assistant · system 줄에는 없다.
-- 턴을 시작한 것은 turnOrigin · origin.kind로 갈린다: human / task_notification / 다른 세션의 메시지(isMeta).
--
--   prompt_id  CC의 promptId. 다시 읽기 · hook과 트랜스크립트 합치기의 키. hook이 먼저 연 턴은 잠깐 NULL
--   origin     human task_notification agent_message meta (TRIGGER는 예약어라 origin)
--   closed_by  턴을 닫은 신호의 출처: transcript hook sweep. 먼저 온 신호가 닫는다(README 3.2)
--   character_session.cwd  입양한 세션의 작업 디렉토리(프로젝트 판정 근거, 화면 표시)

ALTER TABLE turn
  ADD COLUMN prompt_id  CHAR(36) CHARACTER SET ascii NULL AFTER seq,
  ADD COLUMN origin     VARCHAR(20) NOT NULL DEFAULT 'human' AFTER prompt_id,
  ADD COLUMN closed_by  VARCHAR(10) NULL AFTER end_reason,
  ADD UNIQUE KEY uq_turn_prompt_id (prompt_id),
  ADD KEY ix_turn_open (session_id, ended_at);

ALTER TABLE character_session
  ADD COLUMN cwd VARCHAR(512) NULL AFTER cc_session_id;
