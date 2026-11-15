# 프로젝트 띠 「오늘 읽은 양」 점검 (2026-11-15, 세션 420)

관리자 410의 점검 일감(사용자 지시 11-15). 확인 · 보고만 했고 코드 · 설정 · 문서 · 시험은 고치지 않았다. DB는 SELECT만 했다.

## 결론 — 맞다

호버의 「오늘 읽은 양」은 **이 프로젝트 세션들(관리자 · 코더 · 디자이너 등, 오늘 끝난 세션 포함)이 오늘 KST 0시부터 API를 부를 때마다 읽은 입력의 합**이다. 서브에이전트, 숨긴 시험 세션, 브리지가 부르는 `claude -p`는 빠진다. 거의 전부(약 98%)가 쌓인 대화를 다시 읽는 캐시 읽기다.

사용자가 본 21.6M은 foreman의 **KST 11-15 09:23:55 무렵 값과 맞는다(21.63M)**. 사용자 지시는 09:09 관리자 410에 하나(09:17 짧은 덧붙임 하나)였지만, 그 지시가 세션 셋으로 퍼져 **API 호출 149번**이 났고 호출마다 **평균 141.8k 토큰**을 다시 읽었다. 149 × 141.8k ≈ 21.1M(캐시 읽기) + 캐시 쓰기 0.50M ≈ 21.6M.

## 1. 값이 어디서 오나

| 단계 | 자리 | 내용 |
|---|---|---|
| 화면 | `bridge/static/js/office.js:3524` | `오늘 읽은 양 ${fmt(rs.tin)} 토큰 (대화 다시 읽기 포함)` |
| 방 합 | `office.js:512` | 방 세션마다 `s.tokens.today_input`을 더한다. 방은 `/api/dashboard`의 프로젝트 이름별 세션 목록(`office.js:321`). 512줄은 `dormantGone`(끝나고 3분 뒤 화면에서 사라짐) 확인보다 앞이라 끝난 세션도 더한다 |
| 서버 | `bridge/api/dashboard.py:586-590` `dashboard()` | `SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0))`, `FROM message m JOIN turn t`, **`m.subagent_id IS NULL`** |
| 세션 고르기 | `dashboard.py:545-558` · `visible_rows`(471) | `cs.type='agent' AND cs.hidden_at IS NULL`(숨긴 시험 세션 뺌), 살아 있거나 48시간 안 활동. 오늘 메시지가 있는 세션은 모두 들어간다 |
| 표 · 칸 | `message` | `token_input`(=`input_tokens`), `token_cache_read`(=`cache_read_input_tokens`), `token_cache_creation`(=`cache_creation_input_tokens`), `created_at`. 적재는 `bridge/assembler.py:444` `_message` |

- 들어가는 것: 생 입력 + 캐시 읽기 + 캐시 쓰기. 출력은 안 들어간다(출력은 윗줄 「오늘 쓴 글」)
- 빠지는 것: 서브에이전트(`subagent_id IS NOT NULL`), `claude -p`(교장 계획 등, `usage_extra` 표에 따로 쌓여 이 쿼리에 없다), 숨긴 세션, 다른 프로젝트

## 2. 날짜 끊기 — KST 0시 맞다

- `dashboard.py:530` `_today_utc()`: 지금 UTC에 9시간 더해 KST 날짜를 얻고, 그 0시에서 9시간 빼 UTC로 비교한다. 실제 실행 값 `2026-11-14 15:00:00`(UTC) = KST 11-15 00:00
- DB 시각은 UTC다: `assembler.py:71` `_ts`가 대화 파일 시각(Z)을 UTC로 바꿔 tz 없이 넣고, MySQL `@@session.time_zone` · `@@global.time_zone` 모두 `+00:00`
- 실제 값으로: 오늘 · 어제(11-14)는 KST 00~09시 기록이 0건이라 이 두 날로는 갈리지 않는다. 그 시간대 기록이 있는 날은 11-02 · 03 · 05 · 06 · 08 · 09 · 11(예: 11-09 746호출 161.16M). 비교식이 UTC 0시였다면 이 날들의 새벽 값이 전날로 갔을 것이다. 코드 식이 KST 0시라 바르게 들어간다

## 3. 범위

- 방 하나 = 프로젝트 하나(대시보드 `p.name`별)
- 끝난 세션: 들어간다(오늘 메시지가 있으면 `visible_rows`에 남고, 화면 합은 `dormantGone` 앞에서 더한다)
- 숨긴(test) 세션: 빠진다(`hidden_at IS NULL`)
- 서브에이전트: 빠진다. **눈여겨볼 점** — 바로 윗줄 「오늘 쓴 글」은 `by_model`(서브에이전트 포함)으로 세고 「읽은 양」은 본 대화만이라 두 줄 기준이 다르다. 틀린 값은 아니지만 맞추려면 `office.js:512`를 `by_model[].today_input` 합으로 바꾸면 된다(제안만, 이번에 고치지 않음)

## 4. 21.6M 다시 세기

foreman, KST 11-15 00:00 ~ 09:23:55, 본 대화 · 숨기지 않은 세션:

| 세션 | 역할 | 턴 | 턴 출처 | API 호출 | 읽은 양 | 호출당 캐시 읽기 평균 | 최대 맥락 |
|---|---|---|---|---|---|---|---|
| 410 | 관리자 | 6 | human, relay | 32 | 6.02M | 182.7k | 202.7k |
| 412 | 디자이너 | 5 | human, meta, task_notification | 53 | 5.84M | 107.8k | 148.9k |
| 413 | 코더 | 1 | human | 64 | 9.77M | 149.5k | 230.5k |
| 합 | | 12 | | 149 | **21.63M** | 141.8k | |

- 합의 구성: 캐시 쓰기 0.50M, 생 입력 322토큰, 나머지 약 21.13M이 캐시 읽기(약 97.7%)
- 같은 시각 빠진 몫: 서브에이전트 10.54M(89호출), `claude -p`(dispatch) 오늘 전체 0.48M
- 턴 출처: 410의 human 턴은 09:09 사용자 지시, 09:17 사용자 덧붙임, 09:22 합치기 카드(브리지가 넣은 것도 human으로 찍힌다). 412 · 413의 human 턴은 관리자가 넣은 일감. 나머지는 보고 전달(relay) · 백그라운드 알림
- 오늘 전체(11:0x 기준, 본 대화): foreman 60.46M(턴 30 · 호출 412), runshoes 53.40M(턴 32 · 호출 324), ronanlab-infra 2.13M
- 오늘 21.6M을 넘은 시각: foreman 09:23:54, runshoes 09:55:25. 지시 하나 조건에 맞는 것은 foreman(runshoes 관리자 310은 사람 턴 23번)

## 5. 호버 글 제안

지금: `오늘 읽은 양 21.6M 토큰 (대화 다시 읽기 포함)` — 무엇의 합인지, 왜 큰지 알기 어렵다.

제안(두 줄):

```
오늘 읽은 양 21.6M 토큰
(이 프로젝트 세션들이 응답할 때마다 쌓인 대화를 다시 읽은 양의 합, 오늘 0시부터, 서브에이전트 빼고)
```

호출 수를 함께 보이면(예: 「응답 149번, 한 번에 평균 14만」) 왜 큰지 바로 보이지만, 지금 대시보드는 호출 수를 내지 않아 서버 쿼리를 늘려야 한다(글만 바꾸는 범위 밖).

## 6. 어떻게 셌나

모두 `.venv/bin/python -c`로 `bridge.db.engine.make_engine(Settings())`에 SELECT 문을 인자로 넘겨 돌렸다(비밀번호는 설정 안에서만 쓰여 화면에 나오지 않았다). `_today_utc()`도 같은 방식으로 불러 값을 찍었다. 주요 쿼리:

21.6M을 넘은 시각(누적):
```sql
SELECT name, MIN(ts_kst) FROM (
 SELECT p.name, m.created_at + INTERVAL 9 HOUR ts_kst,
  SUM(m.token_input+m.token_cache_read+m.token_cache_creation) OVER (PARTITION BY p.name ORDER BY m.created_at, m.id) run
 FROM message m JOIN turn t ON t.id=m.turn_id JOIN character_session cs ON cs.id=t.session_id
 JOIN `character` ch ON ch.id=cs.character_id LEFT JOIN project p ON p.id=ch.project_id
 WHERE m.created_at >= '2026-11-14 15:00:00' AND m.subagent_id IS NULL AND cs.hidden_at IS NULL AND cs.type='agent') x
WHERE run >= 21.6e6 GROUP BY name;
```

세션별 분해(4절 표):
```sql
SELECT cs.id, cs.role, COUNT(DISTINCT t.id) turns, GROUP_CONCAT(DISTINCT t.origin), COUNT(*) calls,
 SUM(m.token_input+m.token_cache_read+m.token_cache_creation) tin, AVG(m.token_cache_read),
 MAX(m.token_input+m.token_cache_read+m.token_cache_creation), SUM(m.token_cache_creation), SUM(m.token_input)
FROM message m JOIN turn t ON t.id=m.turn_id JOIN character_session cs ON cs.id=t.session_id
JOIN `character` ch ON ch.id=cs.character_id JOIN project p ON p.id=ch.project_id
WHERE p.name='foreman' AND m.created_at >= '2026-11-14 15:00:00' AND m.created_at < '2026-11-15 00:23:55'
 AND m.subagent_id IS NULL AND cs.hidden_at IS NULL AND cs.type='agent' GROUP BY cs.id, cs.role WITH ROLLUP;
```
(서브에이전트 몫은 같은 식에 `m.subagent_id IS NOT NULL`, `claude -p` 몫은 `usage_extra`를 `created_at >= '2026-11-14 15:00:00'`로 묶어 셌다)

KST 00~09시 기록이 있는 날:
```sql
SELECT DATE(created_at + INTERVAL 9 HOUR), COUNT(*), SUM(token_input+token_cache_read+token_cache_creation)
FROM message WHERE created_at >= '2026-11-01' AND HOUR(created_at) >= 15 GROUP BY 1;
```

## 규칙 위반

규칙 위반 없음.
