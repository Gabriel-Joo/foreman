# 01 kickoff — 실행 결과

- **실행일**: 2026-11-02
- **범위**: 1(읽기) · 2(환경 조사) · 3(설계 검토). **4(기존 구현 조사) · 5(단계 0 실행 계획)는 미실행.**
  - 3번은 사용자가 범위를 좁혔다: 트랜스크립트 읽기 · 턴 경계 · message.id 조립 · send-keys · 스키마 + Ctrl+Z/정지 상태. 뒤에 서브에이전트 · 호스트 서비스 감시가 더해졌다
- 서버 PC에서 같은 날 바꾼 것(포트 · milvus · search-service 등)은 [`infra_20261102_host-changes.md`](infra_20261102_host-changes.md)

## 실제로 한 일

- 서버 PC 환경을 명령으로 조사 (tmux, CC 프로세스, `~/.claude`, 트랜스크립트, 텔레그램, MySQL, 런타임)
- 트랜스크립트 전체(1.32GB)를 스크립트로 통계 분석 — 턴 경계, message.id 분할, timestamp 순서, 공백 구간, 줄 크기, 서브에이전트
- CC 바이너리(2.1.316)에서 문자열을 뽑아 hook 이벤트 · 입력 필드 · 붙여넣기 처리 · `cleanupPeriodDays` · OTel 메트릭 확인
- 별도 소켓 `tmux -L foreman-probe`에서 입력 반향 스크립트로 send-keys / paste-buffer 실측(CC는 띄우지 않음, 실험 뒤 그 tmux 서버는 종료)
- `~/.claude/settings.json`에 `cleanupPeriodDays` 추가 — 처음 365, 사용자 결정으로 120 (백업 `~/.claude/backups/settings.json.before-cleanupPeriodDays`)
- README 반영: SUSPENDED, 3.1 입력 주입 · 트랜스크립트 읽기, 3.2 턴 경계, 2.2 호스트 서비스 감시, 2.5 공간 구성, 3.8 서브에이전트 렌더링, 3.11 서브에이전트, 스키마 · 인덱스 · 적재 제외, 로드맵 0 · 2 · 3 · 10
- foreman git 저장소 생성(원격 GitHub `Gabriel-Joo/foreman`), 임시 텔레그램 알림(`scripts/notify-telegram.sh`, `CLAUDE.md`)

부수 효과: m-k8s 직접 ssh 시도로 `~/.ssh/known_hosts`에 `192.168.121.64` 추가. `~/.claude/sessions/*.key`(세션 간 통신 토큰) 내용이 조사 출력에 찍힘 — 기록에는 옮기지 않음.

## 조사 결과

### 환경 (11-02 조사 시점)

| 항목 | 결과 |
|---|---|
| tmux | 3.6 설치, 서버 없음(세션 0개) |
| CC | 2.1.316. 프로세스 7개 모두 tmux 밖(xfce4-terminal, `DISPLAY=:2.0`). 실행 중 2(runshoes `c5320140` pts/8, petmint `cddadc68` pts/7), Ctrl+Z 정지 4(pts/8: PID 1301867 `~` · 3872105 petmint / pts/7: 1895956 · 1906162 petmint — **사용자가 프로젝트별로 의도적으로 보존, 건드리지 않는다**), 조사 세션 1(pts/3, 이 킥오프 세션) |
| PID ↔ 세션 | `~/.claude/sessions/<pid>.json`에 sessionId · cwd · version · startedAt |
| hook | user · project · plugin 어디에도 없음 |
| 트랜스크립트 | `~/.claude/projects/<cwd의 / _ → ->/<sessionId>.jsonl`, 서브에이전트 `<sessionId>/subagents/agent-<agentId>.jsonl` + `.meta.json` |
| 크기 | 전체 1.32GB(20.6일, 하루 약 64MB). runshoes 한 파일 561MB / 49,454줄, 전체 파싱 3.2초, 최대 줄 0.94MB. 바이트의 76%가 api-request |
| 텔레그램 | CLAUDE.md "알림" 절 → 모델이 `scripts/notify-telegram.sh` 실행 → curl `sendMessage`. hook · cron · systemd 없음. 호출 runshoes 75회, petmint 14회 |
| MySQL | 클러스터 파드 `petmint/mysql-0`, `runshoes/runshoes-mysql-0`(headless ClusterIP, 둘 다 운영). 호스트 → 파드 IP 직접 연결 불가, kubectl은 m-k8s VM 안에만. FOREMAN용 DB · 네임스페이스는 아직 없음. 호스트 도커 `mysql`(펫퍼민트 로컬 개발 · 측정, 지금 127.0.0.1:3306) · `runshoes-mysql-dev`(127.0.0.1:3307) |
| 런타임 | Python 3.14.4(`~/llm_env` venv), Node v20.20.2, **ttyd 미설치** |
| inotify | 사용 가능(ext4, watches 65536, instances 128). inotifywait · watchdog 미설치 |
| 디스크 | `/` 915G. 조사 때 84% → ollama-old 삭제 후 80% |

### JSONL 구조

- 한 줄 = JSON 하나, append-only. compact도 같은 파일에 `compact_boundary`로, `--resume`도 같은 sessionId로 이어 쓴다. 회전 없음. **삭제는 있다** — `cleanupPeriodDays`(기본 30일)
- 대화 외 type이 많다: mode, permission-mode, attachment, api-request(-blob), file-history-snapshot, last-prompt, ai-title, queue-operation, system(turn_duration · away_summary · compact_boundary · informational · local_command)
- **한 줄 = content 블록 1개**(8,954줄 전부). API 메시지 3,801개 중 2,970개가 여러 줄로 분할, 같은 `message.id`의 줄은 usage가 2,970/2,970 동일 → 줄 단위로 더하면 중복 집계
- **timestamp 역전**: 49,454줄 중 4,975줄이 앞줄보다 이른 timestamp(중앙값 0.05초, 최대 521초)
- compact 요약은 `type: user`, `isCompactSummary: true`
- queue-operation: enqueue 720 / dequeue 345 / remove 373 — ACTIVE 중 입력은 대기열로 들어간다
- 토큰: 실제 입력의 대부분은 cache_read(샘플 input 2 / cache_read 27,464)

### 턴 경계

| 종료 상황 | turn_duration | hook |
|---|---|---|
| 정상 종료 | 625/625 | Stop |
| 사용자 중단(Esc) | 15/29 | Stop 미발동(공식 문서 기준, 실측 아님) — 트랜스크립트 `[Request interrupted by user]` 줄로 잡는다 |
| API 에러 | 2/2 | StopFailure(error, error_details) |
| 세션 종료(파일 끝에서 끊김) | 0/5 | SessionEnd(reason) |
| 턴 도중 auto-compact | 1건, compact 뒤로 이어짐 | — |

바이너리 확인: Stop 입력 = 공통(session_id, transcript_path, cwd, permission_mode, agent_id, agent_type, effort) + `stop_hook_active`, `last_assistant_message`. hook 이벤트 목록에 UserPromptSubmit · SessionStart/End · SubagentStart/Stop · PreCompact/PostCompact · Notification · PermissionRequest 등이 있다.

### send-keys (반향 스크립트 실측, CC 아님)

```
입력: line1 "q" $HOME `x` \ 's' ⏎ line2 한글 ; ⏎ ⇥line3

A send-keys -l           b'line1 "q" $HOME `x` \\ \'s\'\nline2 한글 ;\n\tline3'
B paste-buffer -p        b'\x1b[200~line1 … \'s\'\rline2 한글 ;\r\tline3\x1b[201~'
C paste-buffer -p -r     b'\x1b[200~line1 … \'s\'\nline2 한글 ;\n\tline3\x1b[201~'
  + send-keys Enter      b'\r'
```

CC 바이너리: `[200~`/`[201~` → paste-start/paste-end. CC 자신의 pty 입력 코드가 `\x1B[200~${text}\x1B[201~` 후 10ms 뒤 `\r`.

### Ctrl+Z 정지 기간

1시간 이상 공백 53곳의 공백 뒤 첫 줄: user 42, queue-operation 10, informational 1 — 복귀 기록 없음. `away_summary`는 공백 **앞**(정지 전 대기 중)에 찍힌다. 정지된 프로세스는 쓰지도 hook을 띄우지도 못하므로 트랜스크립트로는 "정지"와 "쉬는 중"을 구별할 수 없다. 판별은 `/proc/<pid>/stat`의 `T`뿐. fg 복귀 동작은 기존 프로세스를 건드리지 않아 미실측.

### 서브에이전트

- **병렬은 CC 세션 여러 개가 아니라 한 세션 안의 `Agent` 도구**(이 버전 이름은 `Task`가 아니라 `Agent`, `Task` 0회)
  - 런슈즈: 세션 1개, 두 세션이 같은 10분 구간에 일한 적 0. `Agent` 132회(백그라운드 지정 122), 한 응답에서 최대 9개, 실제 동시 최대 10. general-purpose 131, claude-code-guide 1
  - 펫퍼민트: 세션 25개 중 2개가 같은 10분 구간에 프롬프트를 받은 구간 270개 중 14개(최대 2). `Agent` 47회(4개 세션), 동시 최대 6. general-purpose 43, fork 4
  - 179회 전부 `toolUseResult.status = async_launched` — 결과는 나중에 부모의 새 입력(`<agent-message …> [Subagent hand-back]`, `<task-notification>`)으로 온다
- 파일: runshoes 132쌍 160.7MB(399KB / 964KB / 7.1MB), petmint 47쌍 48.4MB(111KB / 1.07MB / 3.3MB)
- 구조: 기록 종류 · 필드는 부모와 같고 `agentId`, `isSidechain: true`, `slug`, `attributionAgent`, `toolEndsTurn`이 더해진다. **`sessionId`가 부모와 같다.** 첫 줄 `parentUuid`는 null. **system 기록 없음**(turn_duration 없음)
- 연결: 부모 `tool_use(name=Agent).id` = meta.json `toolUseId` = `<task-notification><tool-use-id>` / 부모 `toolUseResult.agentId` = 파일 이름 = 자식 줄 `agentId` = `<task-id>`
- 토큰(입력 쪽): runshoes 서브에이전트 cache_read 2.11억 = 부모 16.4억의 약 11%, petmint `cddadc68` 약 3%

### 서브에이전트 출력 토큰

- 서브에이전트 줄의 usage는 **응답 시작 시점 값**으로 보인다 — `stop_reason` null, output_tokens 글자당 0.002(부모 0.77, 예: 10,603자 블록에 8). 입력 쪽은 그럴듯하지만 미검증
- **SubagentStop hook 입력에 usage 없음**(2.1.316 바이너리): 공통 필드 + `stop_hook_active`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`, `session_crons`
- `<task-notification>`의 **일부**에 합계가 있다: `<usage><subagent_tokens>N</subagent_tokens><tool_uses>N</tool_uses><duration_ms>N</duration_ms></usage>`. 런슈즈 서브에이전트 140개 중 34개, 펫퍼민트 `cddadc68` 18개 중 11개(completed 알림 81건 중 39건 / 79건 중 17건). 종류 구분 없는 합계 하나, 입력 포함 여부 미확인. 처음엔 알림 두 건만 보고 "없다"고 잘못 판단했다가 전수로 정정
- foreground 결과로 합계를 받는 경로는 없다(179회 전부 async)
- 후보: OTel 메트릭 `claude_code.token.usage` — 최종 usage를 type(input · output · cacheRead · cacheCreation)별로, 속성 `model` · `query_source` · `effort`. 서브에이전트 구분 가능 여부는 미실측(방법은 README 3.11)

### 부수적으로 확인한 것 (FOREMAN 브리지에 그대로 해당)

- **timeout 없는 클라이언트는 응답 없는 서버 앞에서 끝없이 멈춘다.** pymilvus `MilvusClient`로 재현: 서버를 `docker pause`하면 40초 넘게 멈춤, timeout 10초 + 새 연결로 한 번 재시도하는 래퍼는 6초에 실패하고 서버 복귀 뒤 다시 붙음(펫퍼민트 "검색 중" 멈춤 사고, petmint-rag-chatbot `5331ebd`). 브리지의 모든 외부 호출(tmux, DB, 텔레그램, 웹훅 대상, 프로메테우스)에 timeout을 건다
- **"죽지 않고 계속 다시 뜨는" 상태는 지금 어떤 감시에도 안 걸린다.** `milvus-port-forward.service` 10-01부터 567,740회 재시작, milvus 컨테이너 17분 크래시 루프([`infra_20261102_milvus-port-forward.md`](infra_20261102_milvus-port-forward.md)) → README 2.2

## 설계와 달랐던 점

- **"두 세션"** — 실제 CC 프로세스는 7개. 한 bash에 claude가 여러 개 얹혀 있다(pts/8에 3개). 그중 정지 4개는 보관용
- **"출력은 JSONL에서 읽는다"(단순 읽기 가정)** — 파일이 수백 MB이고 76%가 대화와 무관한 api-request
- **트랜스크립트는 영구 보존된다는 암묵적 가정** — `cleanupPeriodDays` 기본 30일로 삭제
- **"JSONL 폴링은 늦다"** — inotify를 쓸 수 있어 문제가 아니다
- **"턴 경계는 Stop hook으로 판정"** — 사용자 중단 · 세션 종료에서 Stop과 turn_duration 모두 빠질 수 있다
- **turn 테이블(role + content + token 한 행)** — 실제는 프롬프트 → API 메시지 N → 블록 M의 3단 구조
- **token_in / token_out 두 칸** — 입력의 대부분은 cache_read
- **상태 3개(ACTIVE / IDLE / DORMANT)** — 정지(T) 프로세스가 어느 쪽에도 맞지 않는다
- **"현재 텔레그램은 CC가 봇 API 직접 호출"** — 정확히는 CLAUDE.md 지시로 모델이 셸 스크립트를 실행
- **"MySQL(클러스터 내 파드)"** — FOREMAN용 DB · 네임스페이스는 없고, 호스트에서 파드로 직접 연결 불가
- **서브에이전트가 설계에 없었다** — 실제로는 한 세션에서 10개까지 동시에 돈다. 캐릭터 · 세션 어느 쪽 모델에도 안 맞는다
- **인프라 생존 = 웹훅 + 엔드포인트 폴링** — 재시작 루프를 못 잡는다
- **서브에이전트 토큰은 트랜스크립트로 셀 수 있다는 가정** — output은 못 믿을 값, hook에도 없음. 완료 알림의 합계는 일부에만 있다
- **브리프 02의 "기존 두 systemd 유닛"** — `/etc/systemd/system`에는 `cloudflared-ollama.service`만. runshoes 터널은 클러스터 `cloudflared` 네임스페이스(runshoes `docs/INFRA.md`)

## 판단 근거

- **`cleanupPeriodDays` = 120**: 서버를 쓸 수 있는 기간에 맞춘 값(사용자 결정). 하루 약 64MB × 120 ≈ 7.7GB. 처음 제안한 365(≈ 23GB)는 사용 기간보다 길고 디스크 84%라 줄였다. 양의 정수만 허용(무기한 없음)
- **offset tail + inode + uuid UNIQUE**: append-only, 회전 없음, 삭제는 있음 → 같은 파일인지 inode로, 중복은 uuid로
- **timestamp 정렬 금지**: 역전 4,975줄 실측. 순서는 파일 기록 순서와 parentUuid 체인
- **턴 종료 = 신호 합집합 + `end_reason`**: 어느 단일 신호도 다섯 상황을 다 덮지 못한다. 먼저 온 신호가 턴을 닫는다. turn_duration은 durationMs용
- **message 테이블 분리**: 줄마다 usage 동일 2,970/2,970 → message.id 단위가 아니면 토큰이 블록 수만큼 부풀려진다
- **send-keys 방법 C**: tmux 실측에서 괄호 + LF 유지 확인, CC 자체가 같은 패턴(괄호 + 10ms 후 CR)을 쓴다
- **pane당 claude 하나 · 주입 전 `pane_current_command` 확인 · SUSPENDED 주입 차단**: send-keys는 포그라운드로 간다. CC가 정지되면 포그라운드는 bash → 프롬프트가 셸 명령으로 실행된다
- **SUSPENDED 별도 상태**: IDLE과 달리 입력 · hook 불가, DORMANT와 달리 요약 주입 없이 복귀. 판별은 `/proc` 폴링뿐
- **ACTIVE 중 입력 = 대기열 표시**: queue-operation 실측
- **서브에이전트는 캐릭터가 아니다 · 렌더러는 일꾼으로 그린다**: 몇 분짜리가 10개씩 뜨므로 영속 캐릭터 · "포먼만 채용"을 깨지 않도록 `subagent_run`으로 두고, 화면은 사용자의 목표 장면("에이전트들이 돌아다니며 일하는")에 맞춰 부모 스프라이트 축소판으로 그린다(사용자 결정). 접는 것은 10개 초과만
- **서브에이전트 토큰은 띄운 턴에 귀속**: 179회 전부 async라 결과 받는 턴이 다를 수 있다. output은 `output_tokens_reliable=false`
- **호스트 유닛 · 컨테이너는 캐릭터가 아니라 신호**: 서버 유닛 전부를 캐릭터로 만들 수 없다. 프로젝트 연결은 `character.watch_targets`, 나머지는 포먼 경고 목록. 세션 없는 이벤트를 위해 `event.session_id` nullable + `event.character_id`(사용자 승인)
- **여러 방 보여주기는 10단계로**: 데이터가 어떻게 생겼는지 안 뒤에 렌더러를 설계한다는 기존 원칙. 의견은 줌

## 남은 미검증

- 사용자 중단 시 Stop hook 미발동(문서 기준)
- CC에서 방법 C 실제 동작, 긴 붙여넣기 `[Pasted text #N +M lines]`의 트랜스크립트 기록, 첫 글자 `/` `!`, `@` 자동완성 중 Enter — 로드맵 3단계 전에 실측
- Ctrl+Z 후 fg 시 입력 버퍼 · 진행 중 API 스트림 처리
- 트랜스크립트 rewind 시 파일 중간 수정 여부
- SubagentStart/SubagentStop hook의 실제 입력(바이너리로 필드만 확인), OTel `query_source`로 서브에이전트 output을 셀 수 있는지
- 실행 중인 CC가 바뀐 `cleanupPeriodDays`를 다시 읽는지(정리는 시작 시 도는 것으로 보임)

## 다음 단계

(2026-11-02 갱신 — 킥오프 뒤 같은 날 정한 것 반영)

- **브리프 01의 4(기존 구현 조사)** — 아직 안 함
- **브리프 01의 5(로드맵 0단계 tmux 이전)** — 보류(사용자 결정). 런슈즈 · 펫퍼민트 세션(14일 · 17일째)은 옮기다 컨텍스트를 날릴 위험이 커서 FOREMAN이 실제로 동작하는 것을 확인한 뒤에 옮긴다. 지금 tmux에서 도는 것은 FOREMAN 작업 세션 `cc-foreman`과 브리지 `foreman-bridge`뿐. 정지 4개는 대상이 아니다. 세션 이름 규칙은 옮길 때 정한다
- **DB 위치 · 브리지 배치** — 결정됨: 호스트 도커 FOREMAN 전용 MySQL(`127.0.0.1:3308`), 브리지는 호스트 프로세스. 근거는 README 3.12(감시하는 쪽과 감시받는 쪽의 장애 범위 분리)
- **로드맵 1단계** — 완료. [`stage1_bridge_db_result.md`](stage1_bridge_db_result.md). 남은 것은 집 PC 브라우저 접속 확인
- **로드맵 2단계**(hook 수신 + JSONL 와처 + 턴 판정) — 다음
- 서브에이전트 output 토큰: `<task-notification>`의 `subagent_tokens`는 소수에만 있어 보조 검증용. 주 경로 후보 OTel 실측은 여전히 필요(README 3.11)
- 브리프 02는 로드맵 6단계 뒤에 실행. 그 전에 "기존 systemd 유닛 2개" 전제를 실제(유닛 1개 + 클러스터 터널)에 맞게 고쳐야 한다. 노션 문서 위치 · Access 허용 이메일은 사용자에게 받는다. 실행 전에 `DEBUG_ENDPOINTS=false`
- 3번에서 검토하지 않은 관점: 승인 정책 · 인과 체인(여러 커밋이 한 빌드에 묶일 때) · 수명 정책(DORMANT 부활 시 요약만으로 충분한가). `build` · `summary` 테이블은 이 검토 뒤(9 · 11단계)
- 미정: 동시 서브에이전트 상한, 여러 방 표시 방식(10단계)
