-- 0008 0007 뒤에 생긴 같은 경우 — 서브에이전트 결과 전달이 트랜스크립트 프롬프트 줄 없이 UserPromptSubmit hook으로만 와서
-- hook이 연 턴이 human으로 남았다(4단계 세 번째 실측). 코드는 hook 프롬프트 내용으로 출처를 가르게 고쳤고, 이미 생긴 행을 고친다
UPDATE turn SET origin = 'subagent_message'
WHERE origin = 'human' AND prompt_text LIKE '<agent-message%';
