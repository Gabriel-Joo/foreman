-- 0006 서브에이전트 결과 전달(hand-back)로 열린 턴을 따로 분류한다 (4단계 실측)
-- 서브에이전트가 끝나면 부모 세션에 <agent-message from="agentId"> … 메타 입력이 와서 턴을 연다(task-notification보다 먼저).
-- 2단계는 이것을 meta로 분류했고, 알림이 서브에이전트마다 개별로 나갔다. 묶음 대상으로 바꾼다.
-- 다른 세션이 보낸 메시지("Another Claude session sent a message: <agent-message …")는 agent_message 그대로.
-- 재적재 금지 원칙(README 5장) — 트랜스크립트를 다시 읽지 않고 이미 있는 행을 고친다
UPDATE turn SET origin = 'subagent_message'
WHERE origin = 'meta' AND prompt_text LIKE '<agent-message%';
