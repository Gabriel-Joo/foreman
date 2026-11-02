-- 0007 0006의 보완 — 서브에이전트 결과 전달(<agent-message from=…>)이 isMeta 없이 사람 입력처럼(origin human) 올 때도 있다
-- (4단계 두 번째 실측, 턴이 개별 알림으로 나갔다). 내용으로 가른다. 재적재하지 않고 행을 고친다(README 5장)
UPDATE turn SET origin = 'subagent_message'
WHERE origin = 'human' AND prompt_text LIKE '<agent-message%';
