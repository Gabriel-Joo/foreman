-- 0009 서브에이전트 결과 전달을 보낸 쪽으로 가른다 + hook만으로 생긴 가짜 서브에이전트 행 정리 (4단계 실측)
--
-- 1) "<agent-message from=X>"의 X가 같은 세션의 서브에이전트면 subagent_message, 아니면 agent_message.
--    2단계는 "Another Claude session sent a message"를 다른 세션 메시지(agent_message)로 봤지만, 실측 143턴 전부가
--    자기 서브에이전트(SendMessage)가 보낸 것이었다. 같은 입력이 hook에는 "<agent-message …"로 와서 0006~0008이 생겼다
UPDATE turn t
SET t.origin = IF(EXISTS (SELECT 1 FROM subagent_run sr WHERE sr.session_id = t.session_id
                          AND sr.agent_id = REGEXP_SUBSTR(t.prompt_text, '(?<=<agent-message from=")[^"]+')),
                  'subagent_message', 'agent_message')
WHERE t.prompt_text LIKE '%<agent-message from=%' AND t.origin IN ('agent_message', 'subagent_message', 'meta', 'human');

-- 2) agent_type이 빈 SubagentStop hook으로만 생긴 행(CC 내부 보조 에이전트 — Start도 트랜스크립트도 없다).
--    코드는 더 만들지 않게 고쳤다. 가리키던 hook 이벤트의 subagent_id를 비우고 행을 지운다
UPDATE event e JOIN subagent_run sr ON sr.id = e.subagent_id
SET e.subagent_id = NULL
WHERE sr.agent_type = 'unknown' AND sr.tool_use_id = '' AND sr.description IS NULL
  AND sr.transcript_file_id IS NULL AND sr.spawn_turn_id IS NULL;
DELETE FROM subagent_run
WHERE agent_type = 'unknown' AND tool_use_id = '' AND description IS NULL
  AND transcript_file_id IS NULL AND spawn_turn_id IS NULL;
