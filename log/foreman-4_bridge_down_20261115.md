# 조사 A: 브리지가 죽으면 아무도 모른다 (11-15, foreman-4 조사)

관리자 410의 조사 일감. 코드는 고치지 않았다. 바꾼 것은 이 파일 하나다.

## 요약

- 1(재시작 반복 감시): **설계만 있고 구현은 0이다.** 이벤트 이름, DB 칸 주석, 문서 표에만 있다. 폴러, 판정, 캐릭터 반영, 경고 목록, 알림이 하나도 없다
- 2(systemd가 포기했을 때): **알릴 주체가 없다.** 유닛에 `OnFailure=`가 없고, 바깥 감시 타이머 · cron도 없다. 브리지 밖 알림 길(`python -m bridge.telegram`)은 있지만 아무도 부르지 않고, 브리지와 같은 설정 · 코드를 읽어 같은 원인으로 함께 죽을 수 있다
- 3(막기 넷이 조용히 통과): 스크립트 쪽 7갈래(재현함)와 브리지 안 5갈래가 모두 **판정 없이 통과하고, 어디에도 세지 않는다.** 통과 자체는 의도된 설계(README 3.3)이고, 빠진 것은 「통과했다는 사실을 알리는 것」이다
- 원인: 2와 3은 **같은 원인**이다. 감시하는 것, 알리는 것, 막는 것이 모두 브리지 프로세스 하나에 들어 있고, 그 프로세스를 지켜보는 것이 없다. 1은 **다른 원인**(만들지 않음)이지만, 고칠 때 2와 같은 자리(브리지 밖 감시)에 두면 한 번에 풀린다
- 추천: 브리지 밖 작은 알림 스크립트를 먼저 만들고(2의 포기 순간), 훅 스크립트가 통과를 파일에 적게 하고(3), 그 다음 바깥 감시 타이머가 브리지와 호스트 유닛 · 컨테이너의 재시작 추세를 함께 본다(1, 2의 나머지). 브리지 안 화면 반영(캐릭터 STALE, 경고 목록)은 마지막

## 1. 재시작 반복 감시 (README 2.2)

### 있는 것

| 곳 | 무엇 |
|---|---|
| `bridge/models.py:56` | `EventType.RESTART_LOOP = "restart_loop"` 이름 하나 |
| `migrations/0001_init.sql:160` | `event.session_id` 주석 「호스트 감시 이벤트(restart_loop)는 세션이 없다」 |
| `migrations/0001_init.sql:41` | `character.watch_targets JSON NULL` 칸(「systemd 유닛 · docker 컨테이너 이름(2.2)」) |
| README 2.2(75 ~ 80줄), 3절 그림(「폴링 … systemd 유닛·docker 컨테이너 재시작 추세 (2.2)」), 5절 표(781, 789줄) | 설계와 표 |

### 없는 것 (근거)

- 이벤트를 만드는 곳: `grep -rn -i "RESTART_LOOP\|restart_loop\|NRestarts\|restart.loop\|재시작 반복"`을 `*.py *.sql *.js *.sh *.toml *.service *.timer` 전체(notion/ 원고 제외)에 쳤다 → 위 두 줄뿐. `EventType.RESTART_LOOP`를 쓰는 곳이 없다
- 폴러: `grep -rn "\"docker\"\|'docker'\|\"systemctl\"\|'systemctl'\|journalctl\|NRestarts\|RestartCount\|watch_targets" bridge/ --include=*.py` → 0건. 브리지는 docker도 systemd도 읽지 않는다
- `watch_targets`를 읽거나 쓰는 코드: 위 grep 0건. 칸은 있지만 늘 NULL
- 화면: `bridge/static/js/*.js`에서 `restart_loop` · `watch_targets` 0건. 포먼의 경고 목록도 없다
- 비슷한 것으로 있는 것은 **인프라 캐릭터 생존 폴링**(`bridge/pipeline.py:814` `poll_infra`, `config/pipeline.toml [infra]`)뿐이다. Jenkins · Harbor · ArgoCD HTTP 응답만 보고(응답 없음 3번 → STALE, 5번 → 텔레그램 `pipeline.py:73`), README 2.2가 짚은 「죽지 않고 계속 다시 뜨는」 상태는 응답이 오므로 못 잡는다
- 다른 저장소: `~/ronanlab-infra`(읽기만)에서 `NRestarts|restart.*loop|RestartCount|OnFailure|crashloop`를 찾았다 → 문서 속 CrashLoopBackOff 트러블슈팅 글과 deployment 주석뿐. `apps/monitoring`(프로메테우스 · 그라파나)은 클러스터 안이고, 호스트 systemd 유닛 재시작을 보는 규칙 · 알림 설정은 찾지 못했다(알림매니저 규칙 파일 없음 — `grep -rln alertmanager`가 monitoring 앱 정의만 걸림)

### 짓는 데 걸림돌이 없는지

- sudo 없이 읽힌다: `systemctl show milvus-port-forward -p NRestarts,ActiveState,SubState` → 읽힘(지금 `inactive/dead`, `NRestarts=0` — 11-02 뒤 꺼 둔 상태). `docker inspect -f '{{.RestartCount}}'` → 읽힘(`milvus-standalone-old` 10, 나머지 0)
- 이 조사 세션의 샌드박스에서는 `systemctl --user`가 사용자 버스에 닿지 않았다(「Process org.freedesktop.systemd1 exited with status 1」). 브리지는 사용자 매니저 안에서 돌므로 거기서는 될 것으로 보지만 **확인하지 않았다**

## 2. systemd가 포기하면 알릴 주체가 없다

### 지금 설정

- `deploy/systemd/foreman-bridge.service` = 실제 `~/.config/systemd/user/foreman-bridge.service`(그 파일을 가리키는 링크, 내용 같음)
  - `StartLimitIntervalSec=300`, `StartLimitBurst=10`(6, 7줄), `Restart=on-failure`, `RestartSec=5`(12, 13줄)
  - **`OnFailure=` 없음**, `WatchdogSec=` 없음(`Type=simple`, 브리지에 `sd_notify` · `NOTIFY_SOCKET` 코드 없음 — grep 0건)
- 사용자 타이머: `~/.config/systemd/user/timers.target.wants/`에 snap 펌웨어 알림 하나뿐
- crontab: FOREMAN 백업(04:30), 펫퍼민트 dev 백업(일요일 05:00) 둘뿐
- linger: `/var/lib/systemd/linger/kopo17` 있음, `Linger=yes`(11-06 `log/infra_20261106_systemd-bridge.md` 3번). 그래서 **사용자 타이머로 바깥 감시를 돌릴 수 있다**

### 브리지 밖 알림 길

- `bridge/telegram.py`(`python -m bridge.telegram 제목 줄…`) — 서버가 꺼져 있어도 보낸다(5줄). 지금 부르는 곳은 `deploy/mysql/backup.sh:16`(백업 실패) 하나
- 이 길을 OnFailure에 그대로 쓰면 **브리지와 함께 죽는 경우**가 있다. 이 모듈이 읽는 것:
  - `bridge.config.get_settings()` — 브리지와 같은 설정(필수 값이 빠지면 둘 다 실패)
  - `config/notify.toml`을 `load_rules`로(`bridge/notify.py:103`) — 문법 오류, `[digest] at` 꼴 오류, 없는 시간대면 예외(117 ~ 119줄). 브리지도 기동 때 같은 함수를 부르므로(`bridge/main.py:104`) **notify.toml이 깨져 브리지가 기동 실패를 되풀이하면 이 알림도 같이 실패한다**
  - `bridge.notify`가 `bridge.roles`를 import(38줄) — 합친 뒤 이 모듈들이 깨지면 같이 깨진다
  - `[telegram] enabled = false`면 둘 다 조용하다
- 그 밖: `deploy/mysql/backup.sh` 2줄 주석 「systemd user timer는 linger가 꺼져 있어 못 쓴다」는 11-06부터 낡았다(linger 켬)

### 실측 (journal, 읽기만)

- 11-06 12:31 ~ 11-15 18:56 사이 브리지 시작 160번, 정지 159번. **실패 · 자동 재시작 · 시작 제한 걸림은 0번**(`journalctl --user -t systemd`에서 `foreman-bridge` 줄을 종류별로 셈). 아직 한 번도 이 구멍에 빠지지 않았다
- 그래서 「포기」가 실제로 어떻게 나타날지는 재현하지 않았다(브리지를 멈추지 않는다는 일감 조건). 유닛 설정만으로 본 경로:
  - 기동 실패가 빠르면(설정 파일 문법 오류, import 오류 등) 5초 간격으로 10번 → 약 1분 남짓에 `start-limit-hit`으로 failed. 그 뒤 아무도 안 띄운다. 화면은 브라우저가 열려 있을 때만 끊김으로 보인다(README 3.10, 534줄)
  - **포기하지 않는 반복도 조용하다**: 30초보다 길게 살다 죽기를 되풀이하면 300초 창 안에 10번이 안 차서 systemd가 끝없이 다시 띄운다. `NRestarts`만 오른다 — milvus-port-forward와 같은 모양이 브리지 자신에게 생긴다. `OnFailure=`는 이 경우 불리지 않는다(자동 재시작 중에는 failed 상태가 아님)
  - **멈춤(살아 있지만 답하지 않음)**: Watchdog이 없어 systemd는 active로 본다. 이 경우 3의 4초 시간 초과 길로 막기 넷이 모두 통과한다
- 브리지가 다시 떴을 때 「다시 떴다, 꺼져 있던 시간」을 알리는 코드도 없다(`bridge/main.py` lifespan, 기동 때 알림은 claude 실행 파일 없음 393 ~ 400줄과 C 2물결 설정 실패 418 ~ 433줄뿐). `ApprovalManager.start()`가 끊긴 승인 대기를 `abandoned`로 바꾸는 것도 로그 한 줄뿐(`bridge/approvals.py:121`, `main.py:174`)

## 3. 브리지가 없거나 늦으면 막기 넷이 조용히 통과한다

훅 설정: 사용자 설정 `~/.claude/settings.json` PreToolUse `*` → `/home/kopo17/AI_programming/foreman/scripts/foreman-decide.sh pre`, 한도 6초(견본 `deploy/hooks/foreman-hooks.json`과 같음). 프로젝트 `.claude/settings.json`에는 PostToolUse 한국어 검사만 있다. 원본 폴더 스크립트를 부르므로 worktree에서도 같은 스크립트다.

### 3-1. 스크립트 쪽 (`scripts/foreman-decide.sh`)

| 경우 | 줄 | 결과 | 재현 |
|---|---|---|---|
| `.env.bridge`가 없거나 `FOREMAN_HOOK_TOKEN` 줄이 없음 | 9, 10 | 출력 없이 exit 0 | 코드로 확인 |
| 연결 거부(브리지 꺼짐, 재시작 틈) | 16, 17 `|| exit 0` | 출력 없이 exit 0 | `127.0.0.1:1` → rc=0, 0.0초, 출력 없음 |
| 4초 넘게 답 없음 | 16 `-m 4` | 출력 없이 exit 0 | 6초 뒤 deny를 주는 가짜 서버 → rc=0, 4.0초, 출력 없음(deny가 버려짐) |
| 5xx | 16 `-f` | 출력 없이 exit 0 | 500 → rc=0, 출력 없음 |
| 401(토큰 어긋남) | 16 `-f` | 출력 없이 exit 0 | 401 → rc=0, 출력 없음 |
| 200 빈 본문 | 18 | 출력 없이 exit 0 | rc=0, 출력 없음 |
| 200 깨진 JSON | 18 | **깨진 글을 그대로 stdout으로** exit 0 | rc=0, 깨진 JSON이 그대로 나감. CC는 exit 0의 JSON 아닌 stdout을 판정으로 쓰지 않으므로 통과로 본다(CC 쪽 동작은 **추론**, 실제 세션으로 확인하지 않음) |
| 스크립트 자체가 6초를 넘김 | 훅 한도 6초 | CC가 훅 오류로 보고 진행(비차단). curl 4초가 먼저 끊으므로 실제로는 드묾 | 확인 안 함 |

재현은 스크래치패드의 가짜 서버(`127.0.0.1:18999`, 경로별 고장)와 `FOREMAN_HOOK_BASE`로 했다. 실제 훅 설정 · 브리지는 건드리지 않았다. 대조군(정상 deny 200)은 deny가 그대로 나갔다. 7갈래 모두 **어디에도 기록되지 않는다**(stderr도 `2>/dev/null`).

### 3-2. 브리지 안 (`bridge/api/hooks.py`, `bridge/approvals.py`, `bridge/main.py`)

| 경우 | 곳 | 결과 | 알림 |
|---|---|---|---|
| `approvals`가 없음(`approval_enabled=false`, 와처 꺼짐, 또는 기동 중 ApprovalManager 생성 전) | `hooks.py:48-50` | 204 → 통과(넷 모두) | 없음 |
| 역할 읽기(DB) 실패 | `hooks.py:52-56` | 역할 없음(`srole=None`)으로 판정 → **지금 막는 유일한 역할 규칙 `inspector-write`(`config/roles.toml:18`)가 꺼짐** | 로그 warning만. roleguard의 `on_error` 알림(`roleguard.py:213`)을 타지 않는다 |
| 역할 판정 중 예외 | `approvals.py:158-163`, `roleguard.py:203-206` | 통과 | 로그 error + 텔레그램 시간마다 한 번(`_c2_alert`) — 넷 중 유일하게 알린다 |
| 스키마 잠금 · 다른 저장소 · pgrep 판정 중 예외 | `approvals.py:166, 170, 174`(try 없음) | 500 → 스크립트 `-f`로 exit 0 → 통과 | 없음(uvicorn 로그의 500 트레이스뿐) |
| `session_role`(git push 때 DB) 실패 | `approvals.py:133-150` | None = 관리자 예외 없음 → **막는 쪽**(이건 닫힌 채 실패) | 로그 warning |
| 응답이 4초를 넘김(역할 · 세션 역할 DB 읽기가 느림, 이벤트 루프가 동기 작업에 막힘) | `hooks.py:53, 57` | 3-1의 시간 초과 길로 통과 | 없음. 응답 시간을 재는 곳도 없다(얼마나 자주인지 **모른다**) |

덧붙여: 스키마 잠금은 **처음 건드린 세션이 잡는** 방식이다(`schemalock.py` `check`가 잡기와 판정을 같이 한다). 브리지가 꺼져 있는 동안 migrations를 고친 세션은 잠금을 잡지 못하고, 다시 뜬 뒤 다른 세션이 먼저 잡을 수 있다 — 통과뿐 아니라 잠금 주인이 뒤바뀐다.

`config/worktree.toml`(스키마 잠금) · `config/approval.toml`(다른 저장소) 문법 오류는 `SchemaLock.__init__` · `RepoScope.__init__`에서 예외(`schemalock.py:43`, `reposcope.py:145`, try 없음) → lifespan 실패 → **브리지가 기동 실패를 되풀이 → 2의 포기 경로**로 이어진다. 3과 2가 같은 사슬이라는 한 예다.

### 3-3. 얼마나 열려 있었나 (실측)

- 11-06 ~ 11-15 재시작 159번. 정지 시작부터 `Uvicorn running on http://127.0.0.1:8000`까지 평균 1.4초, 최대 10.7초, 합 217초(약 4분). 이 틈에 들어온 PreToolUse는 모두 판정 없이 지났다(몇 건이었는지는 세지 않았다)
- 11-06 09:32 ~ 12:31 정전 · 수동 기동 전 약 3시간(그때는 systemd 이전)

### 3-4. 뒤늦게라도 찾는 코드가 있나

없다. `grep -rn approval_req bridge/*.py`(approvals.py 밖) → models 정의와 roleguard 주석뿐. 감시가 있는 것은 적재 막힘(`bridge/ingest_health.py`)과 Jenkins 웹훅 끊김(`pipeline.py:672`)이다. 트랜스크립트 백필로 tool_use 이벤트는 다시 적재되므로, 「tool_use는 있는데 approval_req가 없는 호출」을 세는 재료는 이미 DB에 있다.

## 셋이 같은 원인인가

- **2 = 3, 같은 원인**: 「감시자 · 알림 발신자 · 경비가 브리지 한 프로세스이고, 그 프로세스를 지켜보는 것이 없다」. 2는 그 프로세스가 사라지는 순간이고, 3은 그 프로세스가 사라졌거나 늦은 동안 훅이 혼자 내린 결정이다. 3-2의 설정 문법 오류처럼 한 고장이 3 → 2로 이어지기도 한다
- **1은 다른 원인**: 만들다 만 것이다(설계 11-02, 구현 없음). 다만 1이 보려는 것(호스트 유닛 · 컨테이너가 계속 다시 뜸)과 2의 「포기하지 않는 반복」은 같은 모양이고, 1을 브리지 안에만 지으면 브리지가 죽었을 때 1도 같이 죽는다. 그래서 **고치는 자리는 같다** — 브리지 밖

## 고치는 안 비교

| 안 | 무엇 | 1 | 2 | 3 | 크기 | 약점 |
|---|---|---|---|---|---|---|
| A. 브리지 안에서만 | 브리지에 restart_loop 폴러, 기동 때 「다시 떴다 · 꺼진 시간 · 판정 없이 지난 호출 N건」 | ○ | △ 다시 뜬 뒤에만. 포기 · 멈춤 · 느린 반복은 못 잡음 | △ 뒤늦게 | 중 | 감시자가 감시 대상과 같이 죽는다(README 3.12의 「장애 범위를 나눈다」와 어긋남) |
| B. OnFailure만 | 유닛에 `OnFailure=foreman-bridge-alert.service`, 알림은 독립 스크립트 | × | △ 포기 순간만. 느린 반복 · 멈춤은 못 잡음 | × | 소 | `python -m bridge.telegram`을 쓰면 notify.toml · 브리지 import와 함께 죽음 → curl과 `.env.telegram`만 쓰는 따로 스크립트여야 함 |
| C. 바깥 감시 타이머 | 사용자 타이머(1분)가 독립 스크립트로: `is-active`, `NRestarts` 증가, `/healthz` 2초 응답, 호스트 유닛 `NRestarts` · docker `RestartCount` 추세. 상태 파일에 적고 바뀔 때만 curl 텔레그램 | ○(브리지가 죽어도) | ○ 포기 · 느린 반복 · 멈춤 모두 | △ 「브리지가 꺼졌다」는 알림이 곧 「지금 막기가 열려 있다」는 뜻 | 중 | 알림 규칙(접두어, 묶음)이 notify.toml과 따로 놂. 새 코드 길 하나를 따로 지켜야 함 |
| D. 훅 쪽 닫힌 채 실패 | 브리지가 없으면 deny | — | — | ○ | 소 | **안 됨에 가깝다**: 재시작 159번마다 모든 프로젝트(런슈즈 · 펫퍼민트 포함) 도구 호출이 막히고, README 3.3이 정한 「CC가 스스로 정한다」와 반대. 사용자 결정 사항 |
| E. 훅 쪽 기록 + 부분 로컬 판정 | `foreman-decide.sh`가 통과 갈래마다 `~/.foreman/hook_miss.log`에 한 줄(시각, 갈래 — curl 종료 코드, 세션, 도구). 브리지 · 바깥 감시가 읽어 「판정 없이 지난 PreToolUse N건(이유별)」을 알림. 선택: 입력만으로 정해지는 pgrep 막기만 스크립트 안에서 로컬로 판정 | — | — | ○ 4초 초과(브리지가 살아 있을 때)까지 셈 | 소 | 로컬 판정은 호출마다 파이썬 기동 비용(수백 ms)이 붙는다 — pgrep은 bash 정규식으로 옮기면 가볍지만 판정 두 벌이 됨 |

**추천: B'(B를 독립 스크립트로) + E(기록만) → C → A의 화면 부분.** D는 하지 않는다(사용자가 정할 일로 남김).

## 고치는 순서와 크기

| 순서 | 일 | 크기 | 누가 · 무엇이 필요한가 |
|---|---|---|---|
| 1 | 독립 알림 스크립트(`scripts/` 아래, curl + `.env.telegram`만, 브리지 import 없음) + 유닛 `OnFailure=` + 알림 유닛 하나. `backup.sh`도 브리지가 아닌 이것을 쓰게 할지 같이 정함 | 소(스크립트 30줄 남짓, 유닛 둘) | 코더(sonnet 가능). 유닛 바꾼 뒤 `systemctl --user daemon-reload` — sudo 없음. 실제로 failed가 되는지는 브리지를 일부러 죽여야 확인되므로 **사람이 확인할 것** |
| 2 | `foreman-decide.sh` 통과 갈래 기록 + 브리지 안 3-2의 조용한 갈래 정리: `hooks.py` 역할 읽기 실패를 roleguard `_fail`로, 스키마 · 저장소 · pgrep 판정 예외를 잡아 알림(지금은 500), `/hooks/pre` 응답 시간 기록 | 소 ~ 중(스크립트 몇 줄, 브리지 두 파일 + 시험) | 코더. 브리지 재시작 필요(관리자) |
| 3 | 바깥 감시 타이머(C): 브리지 자신 + README 2.2 호스트 감시(감시 목록은 설정 파일). 2의 기록 파일도 여기서 세어 알림 | 중(스크립트 하나 + 설정 + 사용자 타이머, 시험) | 코더. 감시할 유닛 · 컨테이너 목록과 알림 문턱은 **사용자가 정할 것** |
| 4 | 브리지 쪽 화면 반영(A의 나머지): 바깥 감시의 상태 파일을 읽어 `restart_loop` 이벤트, `watch_targets`로 인프라 캐릭터 STALE · 경고, 포먼 경고 목록, 기동 때 「꺼져 있던 동안 판정 없이 지난 호출」 맞대기 | 중 ~ 대(브리지 + 화면 + 시험, 마이그레이션은 없음 — 칸과 이벤트 이름이 이미 있다) | 코더 + 디자이너 |

## 확인 체크리스트

- [x] 세 항목 각각 코드 위치(파일, 줄)가 적혔는가 — 1: `bridge/models.py:56`, `migrations/0001_init.sql:41,160`, `bridge/pipeline.py:73,814`. 2: `deploy/systemd/foreman-bridge.service:6,7,12,13`, `bridge/telegram.py`, `bridge/notify.py:38,103-119`, `bridge/main.py:104,393-400`, `deploy/mysql/backup.sh:2,16`. 3: `scripts/foreman-decide.sh:9,10,16-18`, `bridge/api/hooks.py:48-57`, `bridge/approvals.py:133-150,158-174`, `bridge/roleguard.py:203-219`, `bridge/schemalock.py:43`, `bridge/reposcope.py:145`
- [x] 「없다」의 근거가 있는가 — 1 · 3-4의 grep 꼴을 그대로 적었다. 2는 유닛 파일 · 사용자 유닛 폴더 · crontab · journal을 읽었다
- [x] 고치는 안이 두 개 이상 비교되었는가 — A ~ E 다섯
- [x] 코드를 고치지 않았는가 — 바꾼 것은 이 log 하나. 재현용 가짜 서버는 스크래치패드(저장소 밖)에 Write로 만들고 끝낸 뒤 프로세스를 껐다

## 사람이 확인할 것

- 실제 「포기」 상태에서 OnFailure 알림이 가는지(브리지를 일부러 실패시켜야 함 — 이 조사에서는 하지 않음)
- 사용자 매니저 안에서 `systemctl --user show foreman-bridge -p NRestarts`가 읽히는지(이 세션 샌드박스에서는 사용자 버스가 막혔다)
- D(닫힌 채 실패)를 할지 — 하지 않는 것을 추천하지만 정책 결정이다

## 규칙 위반

규칙 위반 없음. 파일은 Write로만 만들었다(저장소 안은 이 log, 밖은 스크래치패드의 재현용 서버). `pgrep -f` · sudo를 쓰지 않았고, 브리지 · 훅 설정 · 다른 저장소를 바꾸지 않았다. 서브에이전트는 띄우지 않았다.
