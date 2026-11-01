# 01 kickoff — 실행 결과

- **실행일**: 2026-11-02
- **범위**: 1(읽기) · 2(환경 조사) · 3(설계 검토, 범위 축소: 트랜스크립트 · 턴 경계 · message.id 조립 · send-keys · 스키마 + Ctrl+Z/정지 상태). 4 · 5는 미실행.

## 실제로 한 일

- 서버 PC 환경을 명령으로 조사 (tmux, CC 프로세스, `~/.claude`, 트랜스크립트, 텔레그램, MySQL, 런타임)
- 트랜스크립트 전체를 스크립트로 통계 분석 (턴 경계, message.id 분할, timestamp 순서, 공백 구간, 줄 크기)
- CC 바이너리(2.1.316)에서 문자열을 뽑아 hook 이벤트 · 입력 필드 · 붙여넣기 처리 · `cleanupPeriodDays` 확인
- 별도 소켓 `tmux -L foreman-probe`에서 입력 반향 스크립트로 send-keys / paste-buffer 동작 실측 (CC는 띄우지 않음, 실험 후 서버 종료)
- `~/.claude/settings.json`에 `cleanupPeriodDays` 추가 — 처음 365, 사용자 결정으로 120으로 변경 (백업: `~/.claude/backups/settings.json.before-cleanupPeriodDays`)
- README 반영: 상태 SUSPENDED, 3.1 입력 주입 · 트랜스크립트 읽기, 3.2 턴 경계, 스키마(turn 재정의 · message 신설 · event/character_session 컬럼), 인덱스, 적재 제외, 로드맵 0 · 2 · 3

부수 효과: m-k8s 직접 ssh 시도로 `~/.ssh/known_hosts`에 `192.168.121.64` 추가. `~/.claude/sessions/*.key`(세션 간 통신 토큰) 내용이 조사 출력에 찍힘 — 기록에는 옮기지 않음.

## 조사 결과

| 항목 | 결과 |
|---|---|
| tmux | 3.6 설치, 서버 없음 (세션 0개) |
| CC | 2.1.316. 프로세스 7개 모두 tmux 밖 (xfce4-terminal, `DISPLAY=:2.0`). 실행 중 2 (runshoes `c5320140`, petmint `cddadc68`), Ctrl+Z 정지 4 (사용자가 의도적으로 보존), 조사 세션 1 |
| PID ↔ 세션 | `~/.claude/sessions/<pid>.json`에 sessionId · cwd · version · startedAt |
| hook | user · project · plugin 어디에도 없음 |
| 트랜스크립트 경로 | `~/.claude/projects/<cwd의 / _ → ->/<sessionId>.jsonl`, 서브에이전트 `<sessionId>/subagents/agent-<id>.jsonl` |
| 트랜스크립트 크기 | 전체 1.31GB (21일, 하루 약 62MB). runshoes 한 파일 561MB / 49,454줄, 전체 파싱 3.2초, 최대 줄 0.94MB |
| 바이트 구성 | api-request 76%, user 11%, assistant 6%, api-request-blob 3% |
| 텔레그램 | CLAUDE.md "알림" 절 → 모델이 `scripts/notify-telegram.sh` 실행 → curl `sendMessage`. hook · cron · systemd 없음. 호출 runshoes 75회, petmint 14회 |
| MySQL | 클러스터 파드 `petmint/mysql-0`, `runshoes/runshoes-mysql-0` (headless ClusterIP). 호스트 → 파드 IP 연결 불가, kubectl은 m-k8s 안에만. 로그인 미시도 → 접속 가능 여부 불명. 호스트 도커에 `mysql`(0.0.0.0:3306, 출처 불명) · `runshoes-mysql-dev`(127.0.0.1:3307) |
| 런타임 | Python 3.14.4 (`~/llm_env` venv), Node v20.20.2, ttyd 미설치 |
| inotify | 사용 가능 (ext4, watches 65536, instances 128). inotifywait · watchdog 미설치 |
| 디스크 | `/` 915G 중 144G 여유 (84%) |

### JSONL 구조

- 대화 외 type이 많다: mode, permission-mode, attachment, api-request(-blob), file-history-snapshot, last-prompt, ai-title, queue-operation, system(turn_duration · away_summary · compact_boundary · informational · local_command)
- 한 줄 = content 블록 1개 (8,954줄 전부). API 메시지 3,801개 중 2,970개가 여러 줄로 분할. 같은 `message.id`의 줄은 usage가 2,970/2,970 동일
- 4,975줄이 앞줄보다 이른 timestamp (중앙값 0.05초, 최대 521초)
- compact 요약은 `type: user`, `isCompactSummary: true`
- queue-operation: enqueue 720 / dequeue 345 / remove 373

### 턴 경계 실측

| 종료 상황 | turn_duration |
|---|---|
| 정상 종료 | 625/625 |
| 사용자 중단 (Esc) | 15/29 |
| API 에러 | 2/2 |
| 세션 종료 (파일 끝에서 끊김) | 0/5 |
| 턴 도중 auto-compact | 1건, compact 뒤로 이어짐 |

바이너리 확인: Stop 입력 = 공통(session_id, transcript_path, cwd) + `stop_hook_active`, `last_assistant_message`. API 에러는 `StopFailure`(error, error_details). `SessionEnd`(reason), `UserPromptSubmit`(prompt) 존재. 사용자 중단 시 Stop 미발동은 공식 문서 기준 — 실측 아님.

### send-keys 실측 (반향 스크립트, CC 아님)

```
입력: line1 "q" $HOME `x` \ 's' ⏎ line2 한글 ; ⏎ ⇥line3

A send-keys -l           b'line1 "q" $HOME `x` \\ \'s\'\nline2 한글 ;\n\tline3'
B paste-buffer -p        b'\x1b[200~line1 … \'s\'\rline2 한글 ;\r\tline3\x1b[201~'
C paste-buffer -p -r     b'\x1b[200~line1 … \'s\'\nline2 한글 ;\n\tline3\x1b[201~'
  + send-keys Enter      b'\r'
```

CC 바이너리: `[200~`/`[201~` → paste-start/paste-end. CC 자신의 pty 입력 코드가 `\x1B[200~${text}\x1B[201~` 후 10ms 뒤 `\r`.

### Ctrl+Z 정지 기간

1시간 이상 공백 53곳의 공백 뒤 첫 줄: user 42, queue-operation 10, informational 1. 복귀 기록 없음. `away_summary`는 공백 **앞**(정지 전 대기 중)에 찍힌다. fg 복귀 동작은 기존 프로세스를 건드리지 않아 미실측.

## 설계와 달랐던 점

- **"두 세션"** — 실제 CC 프로세스는 7개. 한 bash에 claude가 여러 개 얹혀 있다(pts/8에 3개).
- **"출력은 JSONL에서 읽는다" (단순 읽기 가정)** — 파일이 수백 MB이고 76%가 대화와 무관한 api-request. offset tail · 선필터 필요.
- **트랜스크립트는 영구 보존된다는 암묵적 가정** — `cleanupPeriodDays` 기본 30일로 자동 삭제. 설정에 값 없었음.
- **"JSONL 폴링은 늦다"** — inotify를 쓸 수 있어 폴링 지연은 문제가 아니다.
- **"턴 경계는 Stop hook으로 판정"** — 사용자 중단 · 세션 종료에서 Stop과 turn_duration 모두 빠질 수 있다.
- **turn 테이블 (role + content + token 한 행)** — 실제는 프롬프트 → API 메시지 N → 블록 M의 3단 구조. 줄 단위 usage 합산은 토큰 중복 집계.
- **token_in / token_out 두 칸** — 실제 입력의 대부분은 cache_read (샘플 input 2 / cache_read 27,464).
- **상태 3개 (ACTIVE / IDLE / DORMANT)** — 정지(T) 프로세스가 어느 쪽에도 맞지 않는다.
- **"현재 텔레그램은 CC가 봇 API 직접 호출"** — 정확히는 CLAUDE.md 지시로 모델이 셸 스크립트를 실행하는 방식.
- **"MySQL (클러스터 내 파드)"** — FOREMAN용 DB · 네임스페이스는 아직 없고, 호스트에서 파드로 직접 연결 불가.
- **브리프 02의 "기존 두 systemd 유닛"** — `/etc/systemd/system`에는 `cloudflared-ollama.service`만. runshoes 터널은 클러스터 `cloudflared` 네임스페이스에서 돈다(INFRA.md).

## 판단 근거

- **`cleanupPeriodDays` = 120**: 서버를 쓸 수 있는 기간에 맞춘 값(사용자 결정). 하루 약 64MB(1.32GB / 20.6일) × 120 ≈ 7.7GB. 처음 제안한 365(≈ 23GB)는 서버 사용 기간보다 길고 디스크가 84%라 줄였다. 값은 양의 정수만 허용(무기한 옵션 없음). 브리지 적재가 안정되면 `event` 보관 정책과 함께 재조정.
- **offset tail + inode + uuid UNIQUE**: append-only 확인, 회전 없음, 삭제는 있음 → 같은 파일인지 inode로, 중복은 uuid로 막는 것이 재시작 · 재적재에 가장 단순.
- **timestamp 정렬 금지**: 역전 4,975줄 실측.
- **턴 종료 = 신호 합집합 + `end_reason`**: 어느 단일 신호도 다섯 상황을 모두 덮지 못함(실측 표). turn_duration은 durationMs 제공용으로 유지.
- **message 테이블 분리**: 줄마다 usage 동일 2,970/2,970 → message.id 단위가 아니면 토큰이 블록 수만큼 부풀려진다.
- **방법 C**: tmux 실측에서 괄호 + LF 유지 확인, CC 자체가 같은 패턴(괄호 + 10ms 후 CR)을 쓴다.
- **pane당 claude 하나 · 주입 전 `pane_current_command` 확인 · SUSPENDED 주입 차단**: send-keys는 포그라운드 프로세스로 간다. CC가 정지되면 포그라운드는 bash → 프롬프트가 셸 명령으로 실행된다.
- **SUSPENDED 별도 상태**: IDLE과 달리 입력 · hook 불가, DORMANT와 달리 요약 주입 없이 원래 컨텍스트로 복귀. 트랜스크립트로 판별 불가 → `/proc/<pid>/stat` 폴링이 유일한 근거.
- **ACTIVE 중 입력 = 대기열**: queue-operation 기록 실측.

## 남은 미검증

- 사용자 중단 시 Stop hook 미발동 (문서 기준)
- CC에서 방법 C 실제 동작, 긴 붙여넣기 접힘의 트랜스크립트 기록, 첫 글자 `/` `!`, `@` 자동완성 중 Enter
- Ctrl+Z 후 fg 시 입력 버퍼 · 진행 중 API 스트림 처리
- 트랜스크립트 rewind 시 파일 중간 수정 여부
- 실행 중인 CC 7개가 바뀐 `cleanupPeriodDays`를 다시 읽는지 (정리는 시작 시 실행되는 것으로 보임 — `.last-cleanup` 11-01)
