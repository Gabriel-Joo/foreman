# 로드맵 2단계 — 트랜스크립트 와처 · 조립 · 턴 판정 · hook 수신 결과

- **실행일**: 2026-11-02
- **범위**: inotify 와처, offset tail 적재, message · turn · subagent_run · event 조립, 턴 종료 판정(트랜스크립트 + hook), hook 수신 엔드포인트와 스크립트. hook을 실제 설정 파일에 설치하는 것은 하지 않았다(사용자 결정 — 아래)
- **커밋**: `e3d0419` 스키마 · 마스킹 · `91c9032` 와처 · 조립기 · `47a55ad` 실데이터 시험에서 찾은 오류 고침 · `ad01c9c` 브리지 연결 · hook · 확인 페이지 · (이 문서와 마스킹 범위 수정은 다음 커밋)

## 실제로 한 일

| 무엇 | 위치 |
|---|---|
| 스키마 | `0003`: `turn.prompt_id`(UNIQUE) · `origin` · `closed_by`, `character_session.cwd`. `0004`: 떠돌이 캐릭터 '미분류' |
| 읽기 | `bridge/transcript/reader.py` — offset tail + inode, 개행 없는 마지막 줄 보류, `"type":"api-request` 바이트 선필터 |
| 와처 | `bridge/transcript/watcher.py` — inotify를 디렉토리 단위로(루트 · 프로젝트 · 세션 · `subagents/`), inotify 먼저 → 백필 → 실시간, 60초 크기 재확인 · 30초 정리 · 30초 서브에이전트 연결 |
| 조립 | `bridge/assembler.py` — 덩어리 하나 = 트랜잭션 하나(offset 포함), 쓰는 작업 하나 |
| 프로세스 생존 | `bridge/liveness.py` — `~/.claude/sessions/<pid>.json`만(`.key`는 열지 않음), `procStart`로 PID 재사용 거름 |
| 마스킹 | `bridge/mask.py` — `.env.*`의 비밀 이름 키 값, 알려진 토큰 형식, 키=값 |
| hook | `/hooks`(hook 토큰, 바로 202), `scripts/foreman-hook.sh`(2초, 출력 없음, 항상 exit 0), `deploy/hooks/foreman-hooks.json`(설치 안 함) |
| 일회성 적재 | `python -m bridge.ingest [--reread]` |
| 확인 페이지 | 한 줄 요약 · 턴 열림/닫힘 · 수집 상태(`/api/ingest`) |
| 테스트 DB | 같은 인스턴스에 `foreman_test`(앱 계정에 권한). 테스트 24개 |

## 조사 결과 — 트랜스크립트 구조 (킥오프 뒤 새로 확인한 것)

전체 31개 본 파일 + 188개 서브에이전트 파일, CC 2.1.296~2.1.316.

- **`promptId`가 턴의 열쇠다.** 모든 user 줄(프롬프트 · tool_result · 중단 표시 · compact 요약 · 메타)에 있고(빠진 줄 0), 한 턴의 user 줄이 모두 같은 값을 갖는다. assistant · system 줄에는 없다. promptId 묶음 1,067개 중 625개가 (프롬프트 + tool_result)
- **턴을 연 것이 무엇인지 줄에 있다**: `turnOrigin`(human · task_notification), `origin.kind`(human · task-notification), `promptSource`(typed · suggestion_accepted), `turnPosition`(promptIndex · turnIndex). 옛 줄은 `turnOrigin`이 null
- **task-notification은 그 자체로 턴을 연다**(새 promptId, `turnOrigin=task_notification`). 형식은 셋 — 서브에이전트(`task-id` = agentId + `tool-use-id`), 백그라운드 Bash(`tool-use-id` 없음), Monitor(`event`)
- **메타 user 줄 대부분은 다른 세션이 보낸 메시지**(`Another Claude session sent a message…`, 134줄) — 이것도 턴을 연다. 나머지는 이미지 설명 · 사용량 한도 안내 등
- **ACTIVE 중 입력은 `attachment/queued_command`로 들어간다**(319줄: 사람 프롬프트 · task-notification) — 새 턴이 아니다
- 중단 표시는 두 가지: `[Request interrupted by user for tool use]`(22) · `[Request interrupted by user]`(8)
- Agent 입력 키: `description · prompt · subagent_type` + 백그라운드면 `run_in_background`. meta.json: `requestShape`(background), 포크는 `isFork` · `model`
- `~/.claude/sessions/<pid>.json`에 `sessionId` · `procStart` · `status` · (tmux 안이면) `tmux` — 살아 있는 프로세스 7개 모두 `procStart`가 `/proc/<pid>/stat`과 일치, 정지 4개는 상태 `T`

## 검증

### 전체 적재 (서버 없이 `bridge.ingest`)

| 항목 | 값 |
|---|---|
| 대상 | `~/.claude/projects` 1.4GB — 런슈즈 본 파일 608MB, 펫퍼민트 디렉토리 557MB. 파일 222개 |
| 시간 | **17.3~17.9초**(5회), 최대 메모리 146MB |
| 줄 | 적재 124,659 · api-request 건너뜀 29,963 · JSON 아닌 줄 0 · 경고 0 |
| 결과 행 | 세션 32 · 턴 1,075 · 메시지 14,237 · 서브에이전트 190 · 이벤트 53,878 |
| 턴 종료 | stop 982 · merged 54 · interrupted 30 · session_end 6 · stop_failure 2 · 열림 1(이 세션) |
| 서브에이전트 | 190개 모두 띄운 턴 연결, 결과 받은 턴 49, `reported_tokens` 48, done 180 · stopped 2 · running 7(부모가 살아 있음) |
| 연결 깨짐 | 이벤트 → 없는 턴 0, 턴 없는 메시지 0. 턴 없는 이벤트는 턴 사이의 큐 조작 · compact 등 731 |
| DB 크기 | event 79MB · message 7MB · turn 3MB (트랜스크립트 20일치 1.4GB → 약 90MB) |

킥오프 실측과 맞는다: 중단 30(킥오프 29 + 이후), API 오류 2, 파일 끝에서 끊긴 세션 종료 5(+ hook 시험 세션 1).

### 다시 읽어도 중복 없음

`--reread`(offset을 0으로)로 처음부터 다시 읽음 16.7~16.8초. 행 수는 그사이 진행 중인 세션이 쓴 몫만 늘었고(이벤트 +5 등, 모두 그 1분 안의 timestamp), uuid 중복 0, promptId당 턴 1개. **턴 상태도 비교했다**: 5분 넘은 턴 1,071개의 종료 이유 · 출처 · 종료 시각 · 소요 시간 · compact 여부가 다시 읽기 전후로 같다.

### 실시간

브리지를 띄운 채로 이 세션과 런슈즈 세션의 새 줄이 WS로 들어왔다. 줄의 timestamp → WS 수신: tool_result 0.13~0.17초, tool_use 0.5~0.8초(assistant 줄은 응답을 다 받은 뒤에 쓰인다). 확인 페이지(`/`)에서 한 줄 요약으로 보인다.

### hook

버리는 디렉토리에서 headless CC(`claude -p … --model haiku --settings deploy/hooks/foreman-hooks.json`)를 두 번 실행. UserPromptSubmit hook이 턴을 먼저 열고(7ms) 트랜스크립트의 프롬프트 줄이 같은 턴에 합류, Stop hook이 트랜스크립트보다 먼저 닫음(`closed_by=hook`), SessionEnd 수신. 이 세션들의 트랜스크립트는 '미분류'로 남는다.

### 마스킹

실제 적재 데이터에서 `.env.*`의 비밀값 5개(텔레그램 토큰 · API/hook 토큰 · DB 비밀번호 둘)가 든 행 0, 텔레그램 토큰 모양 0. `sk-ant-` 1건은 `mask.py`의 정규식 원문(키 모양 아님). 마스크가 적용된 이벤트 151.

## 시험에서 찾은 것

- **다시 읽기가 진행 중인 턴을 닫았다.** 처음부터 다시 읽을 때 지나가는 옛 턴의 줄을, 메모리의 "가장 최근 열린 턴"(지금 진행 중인 이 세션의 턴)에 붙였다 → 옛 turn_duration이 지금 턴을 닫았고 `ended_at`(22:35)이 `started_at`(23:08)보다 앞섰다. **첫 중복 시험은 행 수만 비교해서 통과했다** — 상태 비교로 강화한 테스트가 바로 재현했고, 고친 뒤 실데이터 1,071개 턴 상태가 같음을 확인. 이미 있는 promptId의 줄을 만나면 그 턴을 문맥으로 삼는다(닫힌 턴을 다시 닫는 것은 아무것도 바꾸지 않는다)
- **`no_signal` 54건은 신호 누락이 아니었다.** 전부 모델 활동(assistant · tool_use)이 0 — task-notification 46 · 다른 세션 메시지 5 · 사람 3이 응답 없이 다음 입력과 함께 처리됐다. `merged`로 나누고, 활동이 있었는데 안 닫힌 것만 `no_signal`(지금 0)
- **hook이 이기면 늦은 트랜스크립트 줄이 갈 곳을 잃었다.** headless CC에서 Stop hook이 마지막 assistant 줄보다 먼저 도착 → 그 줄이 턴 없이 적재. 열린 턴이 없을 때의 assistant 줄은 직전 턴으로
- **마스킹이 비밀 아닌 값까지 가렸다** — `.env.db`의 `MYSQL_USER`(foreman_app). 정확값 마스킹은 이름이 비밀인 키만
- 테스트 데이터가 실제와 달라서 생긴 실패 둘 — `json.dumps` 기본값은 `": "`라 실제 줄(`":"`)과 달라 선필터를 못 탔다, 미래 timestamp는 "조용함" 판정에 안 걸린다. 테스트를 실제 형식에 맞춤
- **다시 만들면 hook 이벤트는 사라진다.** 파생 데이터를 지우고 트랜스크립트에서 다시 만들었을 때 hook 시험 세션의 턴은 hook이 아니라 sweep(`session_end`)으로 닫혔다. 1단계에 적은 "다시 만들 수 없는 것"이 실제로 확인됨 — hook을 설치한 뒤에는 전체 재구성을 하지 않는다
- 중복으로 무시된 INSERT도 AUTO_INCREMENT를 쓴다 — 다시 읽을 때마다 event.id에 빈 번호가 생긴다(5만 개씩). 순서(단조 증가)는 그대로, BIGINT라 문제없음

## 설계와 달랐던 점

- **턴 = 프롬프트부터 종료 신호까지**(README 3.2) → 실제 경계는 CC의 `promptId`. 열기는 "새 promptId를 가진 user 줄"이고 사람 프롬프트만이 아니다(task-notification · 다른 세션 메시지). `turn.origin`으로 구분
- **end_reason 5종** → `merged` · `no_signal`이 더해졌다. `closed_by`(transcript · hook · sweep)로 "먼저 온 신호"를 기록
- **프로세스 소멸 = process_lost** → hook을 한 번도 못 받은 세션은 정상 종료와 구분할 수 없어 `session_end`, hook을 받던 세션이면 `process_lost`
- **서브에이전트 행은 자식 파일에서 만든다는 암묵적 가정** → 부모의 `Agent` tool_result(`toolUseResult.agentId`)에서 만든다. 백필이 부모 파일을 먼저 읽으므로 띄운 턴이 바로 붙고, 자식 파일이 먼저 와도(실시간) 30초 연결 작업이 채운다
- **기존 세션을 어디에 붙이나**(설계에 없음) → 프로젝트 cwd면 그 프로젝트의 포먼 캐릭터, 아니면 '미분류'. 세션 역할은 coder. 캐릭터는 만들지 않는다
- **이벤트 payload** → tool_result 본문은 저장하지 않는다(길이 · 오류 여부, 오류면 앞 300자). assistant 글은 전부, thinking은 길이만, tool_use 입력은 문자열마다 2,000자

## 판단 근거

- **덩어리 = 트랜잭션, offset도 같이**: 커밋되지 않은 줄은 다시 읽히고, 다시 읽어도 uuid · message.id · promptId 유일성으로 같은 결과
- **uuid 없는 줄(큐 조작)과 한 줄의 두 번째 블록은 uuid5(경로, offset · 블록 번호)**: 같은 파일을 다시 읽으면 같은 값
- **tool_result 본문 미저장**: 형식을 모르는 비밀(킥오프 때 `~/.claude/sessions/*.key`가 출력에 찍혔다)은 마스킹으로 못 잡는다. 원문은 트랜스크립트에 120일 있다
- **백필 중에는 WS로 안 낸다**: 5만 개를 브라우저에 쏟지 않는다. 턴 열기 · 닫기와 실시간 이벤트만
- **hook은 바로 202, 적재는 뒤에서**: hook이 CC를 붙잡지 않게. 스크립트는 2초 타임아웃 · 항상 exit 0(브리지가 꺼져 있어도 CC는 그대로)

## 아직 안 한 것 · 남은 미검증

- ~~hook 설치~~ → 3단계 때 사용자 설정에 설치, 실행 중인 CC도 다음 프롬프트부터 다시 읽음을 실측([stage3](stage3_inject_result.md))
- 사용자 중단 시 Stop hook 미발동(문서 기준) — hook을 설치한 실세션에서 확인
- `PreToolUse` · `PostToolUse` hook은 받지 않는다(트랜스크립트와 같은 정보, 승인 정책은 5단계)
- 서브에이전트 출력 토큰 — 여전히 `output_tokens_reliable=false`, OTel 실측 필요
- 고아 행 점검 쿼리(event FK 없음) — 지금은 이 문서의 검증 쿼리로만
- SUSPENDED 판정(`/proc` 상태 T) — liveness가 상태 문자를 이미 읽지만 캐릭터 상태 전환은 뒤 단계

## 11-03 사고 — 한 세션의 적재가 몇 시간 조용히 막혔다

- **증상**: 펫퍼민트 세션 `bb19f9d2`(rag-1_6806건 rebuild)의 트랜스크립트가 06:48(KST)부터 같은 덩어리에서 `IntegrityError (1062) uq_turn_prompt`로 실패를 되풀이했다(로그 104회). 3.38MB 중 661바이트까지만 적재 — 이 세션의 대화 · 도구 호출이 대시보드 · 알림 판정에 없었다. 로그에만 남았고, 8단계 작업 중 브리지 로그를 보다 우연히 찾았다
- **원인**: 이 세션은 앞 세션(`cddadc68`)의 기록을 **복사해서 시작한 세션**(resume · fork)이다. CC가 앞 세션 줄을 `uuid` 그대로, `sessionId`만 바꾸고 `promptId`는 뺀 채 새 파일 앞에 붙인다(앞 811줄, 사람 입력 18개). 조립기는 `promptId` 없는 사람 줄을 새 턴으로 열고 `turn.prompt_uuid`(UNIQUE)에 그 uuid를 넣다가, 원래 세션의 턴이 이미 가진 값이라 충돌했다. 이벤트는 `uuid` 충돌을 `ON DUPLICATE KEY`로 넘기지만 턴은 아니었다
- **다른 세션**: 전체 트랜스크립트를 훑어보니 다른 세션 프롬프트를 복사한 세션은 이것 하나(11-03 기준). 하지만 resume · fork를 하면 언제든 생긴다
- **안전장치가 없었다**: 실패하면 그 자리에서 `min(2^n, 60)`초 잠들고 같은 덩어리를 영원히 다시 시도했다 — ① 잠드는 동안 **다른 모든 파일의 적재도 밀렸다**(와처가 하나) ② 실패하면 조립기가 파일 offset을 메모리에서 지워 **재시도마다 파일을 처음부터 다시 읽었다** ③ 몇 번을 실패해도 알림이 없었다

### 고친 것

| | 전 | 후 |
|---|---|---|
| 원인 | `promptId` 없는 사람 줄은 늘 새 턴 | 그 uuid의 턴이 **다른 세션**에 있으면 복사된 기록 — 새 턴을 열지 않는다(원래 세션에 있다). **같은 세션**이면 다시 읽기 — 그 턴을 문맥으로. `prompt_uuid`를 쓰는 세 곳(INSERT · hook 턴 채우기 · meta→human)은 다른 턴이 가진 값이면 NULL로(`_free_uuid`) — 값 하나로 덩어리 전체가 막히지 않게 |
| 실패한 파일 | 그 자리에서 잠듦 — 모든 파일이 밀림 | 다음 시도 시각까지 미뤄 두고 **다른 파일은 계속** |
| 재시도 위치 | 처음부터 다시 읽음 | 실패한 덩어리부터(롤백이라 DB offset도 그 앞) |
| 같은 자리 3번 실패 | 계속 같은 방식 | **너그러운 모드** — 줄마다 SAVEPOINT, 실패한 줄만 버리고 나머지 적재(버린 줄은 알림) |
| 6번(약 2분 반) | 영원히 | 오류가 **결정적**이면 그 덩어리를 건너뜀(마지막 수단, 범위를 로그 · 알림). **DB 끊김 · 시간 초과는 건너뛰지 않는다** — 기다리면 돌아오고 줄을 잃지 않는다 |
| 알림 | 없음(로그뿐) | `bridge/ingest_health.py` — 30초마다: 한 파일이 **5분** 넘게 막힘 → 텔레그램 `[포먼] ⚠ 적재 막힘`, 풀리면 `✅ 적재 회복` · 버린 줄 · 건너뛴 덩어리 → 그때마다 · 감시 루프가 **2분** 넘게 안 돎 → `⚠ 와처 멈춤`. 대시보드 머리에 같은 띠(`/api/dashboard`의 `ingest`), `/api/ingest`에 `health` |

재시작(08:25) 뒤 `bb19f9d2`를 끝까지 적재했다 — offset = 파일 크기, 턴 8 · 이벤트 169, 복사된 프롬프트 17개 건너뜀, 원래 세션 턴은 그대로, 실패 0. 시험 197개(새로 4: 복사 세션 · 다른 파일 안 막힘 → 너그러운 모드 · 건너뛰기는 결정적 오류만 · 알림 한 번 · 회복 · 멈춤).

설정: `ingest_alert_s = 300`, `ingest_tick_alert_s = 120`(`bridge/config.py`), `TOLERANT_AFTER = 3` · `SKIP_AFTER = 6`(`bridge/transcript/watcher.py`).
