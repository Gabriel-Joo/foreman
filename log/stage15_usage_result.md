# 15 결과 — 사용량 · 한도 역산 (2026-11-08~)

설계: `docs/15_usage.md`(사용자 승인 — 새 페이지 + 머리 칩 + 캐릭터 열기, API 정가 비율로 시작, 역산은 하한으로).

## 1. claude -p 사용량 기록 (11-08)

- 빠진 것: 디스패처 · 압축 손실 점검은 `--no-session-persistence`라 트랜스크립트가 없어 `message` 표에 안 들어왔다. 인계 요약(`claude -p --resume`)은 그 세션 트랜스크립트에 이어 써져 이미 들어온다(요약 시각 근처 메시지 확인)
- 실제로 빠진 양은 작았다: 디스패처 약 8번, 기계 점검 1번(실패). 11-05 손 점검은 세션 안 서브에이전트라 집계돼 있다. 앞으로 자동 기상이 하루 5번까지 부르므로 지금 막았다
- `claude -p --output-format json`의 `modelUsage`(실측, Haiku "1"): 모델마다 inputTokens · outputTokens · cacheReadInputTokens · cacheCreationInputTokens · **costUSD(CC가 정가로 계산)** · 캐시 쓰기 5분/1시간 나눔. CC는 캐시를 1시간짜리로 쓴다 → 캐시 쓰기 정가는 입력의 2배(설계 2절 표를 그에 맞춤)
- `bridge/usage.py`(`cli_rows` · `record_cli`) → `usage_extra`(0026, 관찰 표 `usage_observation`도 같이). 디스패처는 계획마다, 점검은 묶음마다. 기록 실패는 호출한 쪽을 막지 않는다
- 실제 확인: 디스패처 #25(〔시험〕, 버림) → `claude-sonnet-5-5` 출력 246 · 캐시 읽기 10,885 · 캐시 쓰기 27,732 · $0.1145 — 1시간 캐시 정가로 손계산한 값과 맞는다
- 그 사이 정정: 주간 88% 관찰의 환산을 캐시 쓰기 1.25배로 셈한 $759 → 2배로 **$838**, 하한 약 $950
- 시험: `tests/test_usage.py`(실제 JSON 모양 · 모델 둘 · 옛 모양 · DB 기록). 전체 461 통과
