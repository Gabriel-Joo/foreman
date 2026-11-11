# FOREMAN

> AI 코딩 에이전트가 만든 변경이 배포까지 가는 전 과정을, 브라우저 한 화면에서 보고 지시하는 관제실.

🔧 **매일 쓰는 중** (2026-11-08 기준) — 로드맵 **0 ~ 8 · 11 · 13 · 14 완료**, 10(테마 렌더러 — 10a 사용자 확인 대기) · 12(서기) · 15(사용량 — 1만)는 일부, 9(LLM 지표)는 보류. 런슈즈 · 펫퍼민트 · FOREMAN 세션이 모두 tmux에서 돌고, 브리지는 systemd 사용자 유닛이 돌린다(11-06). 단계별 상태 · 결과 링크는 「6. 로드맵」, 서버 PC 변경 기록은 [`log/`](log/). 킥오프(2026-11-02) 설계 검토는 [`log/01_kickoff_result.md`](log/01_kickoff_result.md) — 브리프 01의 4는 남음

**접속**: 서버 PC(VNC) 브라우저나 `ssh -L 8000:localhost:8000`으로 붙는다. **터널로 밖에 열지 않는다**(2026-11-03 결정, 근거 3.13) — 밖에서는 텔레그램으로 받는다. 화면은 `http://localhost:8000/`(픽셀 화면 — 승인 · 대화 · 입력 · 터미널이 다 여기서, 테마는 마지막에 본 것), 카드 목록은 `/classic`, 확인 · 디버그 페이지는 `/debug`.

---

## 1. 왜 만드는가

Claude Code 세션 두 개를 터미널 두 개로 띄워놓고 쓰다가 생긴 불편에서 출발했다.

| 불편 | 임시 대응 | FOREMAN의 해결 |
|---|---|---|
| 언제 끝날지 모름 | 텔레그램 봇 직접 연동 | 턴 종료를 hook으로 기계 판정, 브리지가 발송 |
| 뭘 하고 있는지 안 보임 | 창 전환해서 확인 | 세션 상태를 실시간 시각화 |
| 서버 PC 다운을 모름 | — | WebSocket 끊김으로 감지, 화면 전체 표시 |
| 승인 요청이 끝없이 뜸 | 매번 수동 승인 | 정책 기반 자동 승인 + 원격 승인 |

여기에 더해, 원격 구조(집 PC → 교육 PC → 서버 PC VNC)에서 VNC를 거치지 않고 집 PC 브라우저로 서버 PC의 작업을 직접 통제하는 것이 실질적인 목표다.

---

## 2. 핵심 개념

### 2.1 캐릭터와 세션은 다르다

```
캐릭터 (character)   영속. DB에 계속 존재한다.
  └ 세션 (session)   임시. 붙었다 떨어진다.
```

캐릭터는 "누가 있는가"이고, 세션은 "지금 깨어 있는가"다. 세션이 붙어 있는 캐릭터만 화면에서 움직인다. 나머지는 자기 자리에 서 있다.

| 상태 | 의미 | 토큰 | 화면 |
|---|---|---|---|
| `ACTIVE` | 세션 살아있고 작업 중 | 쓴다 | 돌아다님 |
| `IDLE` | 세션 살아있고 대기 | 안 쓴다 | 책상에 앉아 있음 |
| `DORMANT` | 세션 죽음, 요약만 남음 | 안 쓴다 | 자리에 서 있음 |
| `SUSPENDED` | 프로세스 정지(Ctrl+Z, `T` 상태). 컨텍스트는 메모리에 있으나 입력·hook 불가 | 안 쓴다 | 자리에서 얼어붙음 (회색) |

```
ACTIVE    → IDLE       턴 종료 (3.2의 종료 신호 중 먼저 온 것)
IDLE      → ACTIVE     새 지시
IDLE      → DORMANT    N시간 무활동 / 컨텍스트 임계 / 수동
DORMANT   → IDLE       말 걸면 부활 (직전 요약을 주입하고 시작)
ACTIVE/IDLE → SUSPENDED  폴링에서 프로세스 상태 T 감지
SUSPENDED → 직전 상태   폴링에서 S/R 복귀 감지 (요약 주입 불필요 — 원래 컨텍스트 그대로)
```

IDLE은 토큰을 쓰지 않는다. CC는 요청이 있을 때만 토큰을 쓴다. DORMANT로 내리는 이유는 비용이 아니라 **컨텍스트 한계와 메모리**다.

SUSPENDED는 트랜스크립트로는 판별할 수 없다. 정지된 프로세스는 아무것도 쓰지 못하므로 정지 기간이 "그냥 쉬는 중"과 똑같이 보인다(1시간 이상 공백 53곳 모두 복귀 기록 없음). `/proc/<pid>/stat`의 상태 문자만이 근거다. FOREMAN은 SIGCONT를 직접 보내지 않으며, SUSPENDED 캐릭터에는 입력 주입을 차단한다(3.1 참고). ACTIVE 도중 정지됐다면 그 사실도 표시한다.

### 2.2 캐릭터는 인프라의 거울이다

캐릭터는 버튼으로 만드는 것이 아니라, 대응하는 실체가 생기면 등장한다.

```
새 프로젝트          포먼만 있음
  ↓ "파이프라인 깔아줘"
포먼이 코더를 띄움    코더 등장
  ↓ Jenkinsfile 작성, 커밋, 첫 빌드
웹훅 최초 수신       Jenkins 캐릭터 등장
  ↓ 첫 이미지 push
                    Harbor 캐릭터 등장
```

따라서 **캐릭터 구성이 곧 프로젝트 성숙도**다. 포먼만 있으면 맨땅, 코더가 붙으면 개발 중, 인프라 캐릭터가 서 있으면 파이프라인 가동 중.

등장은 이벤트 기반이지만 **생존은 폴링 기반**이다. 웹훅은 "사라졌다"는 신호를 보내지 않으므로, 주기적으로 엔드포인트를 확인해 응답이 없으면 `STALE` → 일정 시간 후 퇴장시킨다. 덤으로 인프라 헬스체크가 공짜로 생긴다.

**호스트의 systemd 유닛과 docker 컨테이너도 감시한다.** 웹훅과 엔드포인트 응답만으로는 "죽지 않고 계속 다시 뜨는" 상태가 잡히지 않는다. 2026-11-02에 이런 것이 둘 나왔고 둘 다 어느 경로에도 걸리지 않았다 — `milvus-port-forward.service`는 10-01부터 567,740회 재시작했고(실행 파일 없음), milvus 컨테이너는 재시작 크래시 루프를 17분 돌았다(재시작 중에도 잠깐씩 응답).

- **신호는 상태보다 재시작 추세다.** systemd `NRestarts` · `ActiveState`/`SubState` · `ExecMainStatus`, docker `RestartCount` · `State`를 폴링하고, 시간 창 안에서 재시작 횟수가 계속 늘면 `restart_loop` 이벤트를 낸다. 한 번의 실패는 잡음일 수 있다.
- **유닛·컨테이너는 캐릭터로 만들지 않는다.** 서버의 유닛 전부를 캐릭터로 만들 수는 없다.
  - 프로젝트에 연결된 것(예: `petmint-search`, `cloudflared-ollama`, milvus, ollama 컨테이너)은 대응하는 인프라 캐릭터의 상태에 반영한다 — 재시작 루프면 그 캐릭터가 `STALE`·경고가 된다. 연결은 `character.watch_targets`에 둔다.
  - 어느 캐릭터에도 속하지 않는 것(이번의 `milvus-port-forward` 같은 것)은 포먼의 경고 목록에 띄운다.

### 2.3 역할은 바뀐다

Jenkins 캐릭터에게 "왜 터졌어?"라고 물으면 inspector 세션이 붙고, "고쳐줘"라고 하면 같은 캐릭터에 coder 세션이 붙는다. 캐릭터는 그대로이고 세션 이력이 쌓인다.

### 2.4 포먼만이 채용한다

새 캐릭터를 만들 수 있는 것은 포먼뿐이다. 프로젝트마다 하나씩 상주한다.

- 프로젝트 컨텍스트 보유
- 작업 분배 — 누구를 띄울지, 무엇을 시킬지
- 세션 요약·인계 작성
- CI/CD 결과 수신 후 후속 조치 판단

포먼도 평소에는 세션 없이 서 있다가, 말을 걸면 붙는다.

> **⚠ (11-05 해소 — 0017 재배치, log/stage11_roles_result.md) 아래는 그때까지의 임시 상태다(2026-11-02).** FOREMAN이 생기기 전부터 돌던 세션(런슈즈 · 펫퍼민트 · 포먼의 기존 CC 세션)은 2단계에서 **모두 그 프로젝트의 포먼 캐릭터 하나에 `role = coder`로 묶어 두었다**(입양만 — 캐릭터는 포먼만 채용하므로 브리지가 캐릭터를 만들지 않았다). 프로젝트 밖 cwd의 세션은 떠돌이 '미분류'에 묶였다. 그래서 대시보드는 캐릭터 이름 대신 **세션 제목**(CC가 붙이는 `ai-title`, `character_session.title`)으로 세션을 구분한다(6단계). **11단계에서 포먼이 캐릭터를 제대로 만들 때 이 세션들을 각각 올바른 캐릭터로 재배치해야 한다**(로드맵 11 할 일).

UI에서는 부모-자식 관계를 트리로 그리지 않는다. **공간으로 표현한다.** 포먼에게는 프로젝트 방 안에 별도의 자리(구석 사무실 / 사서 데스크)를 주고, 일꾼은 공용 작업장에 둔다(2.5).

### 2.5 공간 구성

- **프로젝트마다 별도의 방이다.** 런슈즈와 펫퍼민트는 다른 방에 있다. 방 안에 포먼의 자리, 일꾼의 공용 작업장, 파이프라인 구역(3.6), 인프라 캐릭터의 자리가 있다.
- **서브에이전트는 부모 옆에서 돈다**(3.11). 그러므로 자동으로 부모와 같은 방 안이다.
- **떠돌이 캐릭터**(`project_id`가 null, 예: '미분류' — 프로젝트 밖 폴더의 세션. 포트폴리오는 11-05에 프로젝트마다 두는 서기로 바꿨다, `docs/12_scribe.md`)는 어느 방에도 속하지 않으므로 방 밖의 별도 공간이 필요하다(예: 복도·라운지).
- **방이 여러 개일 때 화면을 어떻게 보여줄지는 10단계(테마 렌더러)에서 정한다.** 선택지와 지금의 의견만 적어 둔다.

| 선택지 | 좋은 점 | 문제 |
|---|---|---|
| 나란히 | 모든 방이 한 번에 보인다 | 방이 3개를 넘으면 각 방이 작아져, 서브에이전트 10개가 도는 장면이 안 보인다 |
| 탭 | 한 방을 크게 본다 | 다른 방에서 생긴 사고가 안 보인다 — "모르고 있던 것을 보이게 한다"는 목적과 부딪힌다 |
| 줌 (전체 지도 → 방 확대) | 축소 상태에서도 방마다 경고·ACTIVE·재시작 루프가 보이고, 알림이 온 방으로 들어가기 자연스럽다 | 지도·확대 전환을 만들어야 한다 |

의견: **줌**. 방 수가 늘어도 전체 상태 요약이 한 화면에 남고, 확대하면 한 방의 장면을 크게 볼 수 있어 둘 다 잃지 않는다.

---

## 3. 아키텍처

```
집 PC 브라우저
  ├─ 캐릭터 화면 (테마 렌더러)
  ├─ 패널 (선택된 캐릭터와의 대화)
  └─ 터미널 (접이식, ttyd + xterm.js)
        ↕ WebSocket
─────────────────────────────────────────────
서버 PC
  브리지 (FastAPI)
    ├─ 입력        tmux load-buffer → paste-buffer -p -r → Enter
    ├─ 출력        JSONL 트랜스크립트 와처 (inotify + offset tail, <sessionId>/subagents/ 포함)
    ├─ 상태        CC hooks (UserPromptSubmit / PreToolUse / PostToolUse / Stop / StopFailure / SessionEnd
    │                        / SubagentStart / SubagentStop)
    │              + 프로세스 상태 폴링 (/proc/<pid>/stat)
    ├─ 승인 정책   PreToolUse에서 allow / ask 판정
    ├─ 수명 관리   tmux 생성·종료, git worktree add·remove
    ├─ 적재        MySQL — 호스트 도커의 FOREMAN 전용 인스턴스 (127.0.0.1:3308, 3.12)
    ├─ 발신        텔레그램
    ├─ 수신        웹훅 (GitLab · Jenkins · Harbor · ArgoCD)
    └─ 폴링        인프라 생존 확인, LLM 지표, 프로메테우스 쿼리,
                   systemd 유닛·docker 컨테이너 재시작 추세 (2.2)
        ↕
  tmux 세션들
    ├─ agent 세션  claude 실행 → 캐릭터로 표시
    └─ shell 세션  bash → 캐릭터 아님, 터미널 패널에 직결
```

### 3.1 입력과 출력의 경로가 다르다

CC는 TUI라서 tmux 화면을 긁으면 ANSI 이스케이프와 화면 갱신이 섞여 깨끗한 텍스트가 안 나온다.

- **입력**은 `tmux send-keys`로 주입한다.
- **출력**은 `~/.claude/projects/*.jsonl` 트랜스크립트에서 읽는다.

같은 세션에 꽂으므로 컨텍스트가 유지된다. 별도 세션(headless)은 쓰지 않는다. **"내가 보는 것과 실제가 동일해야 한다"**가 이 프로젝트의 전제다.

shell 세션은 트랜스크립트가 없으므로 `tmux capture-pane`으로 긁고, 파싱하지 않고 xterm.js로 화면을 그대로 띄운다.

#### 입력 주입 (방법 C)

```
tmux load-buffer -b <buf> -          # 텍스트를 버퍼에 적재 (stdin)
tmux paste-buffer -p -r -b <buf> -t <pane>   # 괄호 붙여넣기(\e[200~ … \e[201~), LF 유지
(잠깐 대기)
tmux send-keys -t <pane> Enter       # 제출
```

`send-keys -l`로 직접 치면 LF가 그대로 들어가 CC가 중간에 제출할 수 있다. `paste-buffer -p`는 앱이 괄호 붙여넣기를 켰을 때만 괄호를 씌우고, `-r`이 없으면 LF를 CR로 바꾼다. CC 바이너리는 `[200~`/`[201~`를 paste-start/end로 해석하고, CC 자신도 pty에 `\x1B[200~…\x1B[201~`를 쓴 뒤 10ms 후 `\r`을 보내는 같은 패턴을 쓴다. tmux는 셸 문자열이 아니라 인자 목록(subprocess argv)으로 호출한다 — 따옴표·`$`·백틱·백슬래시·한글은 tmux 계층에서 그대로 통과한다(실측).

- **pane 하나에 claude 하나.** job control(Ctrl+Z, `&`, `fg`)을 쓰지 않는다. send-keys는 pane의 포그라운드 프로세스로 가므로, bash 하나에 claude 여럿이 얹히면 대상이 모호해진다.
- **주입 전 `#{pane_current_command}` 확인.** claude가 아니면 주입하지 않는다. CC가 정지되면 포그라운드는 bash가 되고, 보낸 프롬프트가 **셸 명령으로 실행된다.** 따라서 SUSPENDED 캐릭터에는 주입을 차단한다.
- **ACTIVE 중 입력은 새 턴이 아니라 대기열로 들어간다**(트랜스크립트 `queue-operation` enqueue/dequeue/remove). UI는 캐릭터별 대기열을 표시한다.
- **실측 결과(3단계, [기록](log/stage3_inject_result.md))**: 따옴표 · `$` · 백틱 · 백슬래시 · 한글 · 들여쓰기는 그대로, 긴 붙여넣기(3천 자)도 원문이 트랜스크립트에 남는다. 다만 **여러 줄은 `<pasted_content id="…">` 태그로 감싸여 모델에 "붙여넣은 글"로 가고, 탭은 공백 4칸이 된다.**
- **첫 글자**: `/`는 슬래시 명령으로, **`!`는 셸 명령으로 실행된다** → `/`는 앞에 공백 한 칸을 붙인다(일부러 명령을 보낼 때만 그대로). `@`는 새지 않는다. 폭 없는 공백 보호는 Enter가 안 먹혀 입력 칸에 남았다 — 쓰지 않는다
  - `!`(11-09 바뀜): ~~언제나 공백을 붙여 막는다~~ — 그래서 사람이 실행하려던 명령 7건이 글로 갔고 아무도 몰랐다. 이제 입력 API가 앞뒤 공백을 떼고, 같은 명령을 Bash 도구 호출처럼 승인 규칙에 넣어 **묻는 규칙(ask) · sudo · 여러 줄 · 빈 명령만 막고**(이유 · 할 일을 글로) 그 밖은 bash 모드로 실행한다(`inject.bang_check`). bash 모드는 승인 훅을 거치지 않는다. 그래도 `!`가 글로 들어가면 텔레그램으로 알린다(`bridge/bang_watch.py`) [log:petmint_docs_move_20261109.md] [log:alerts_denied_xmsg_bang_20261109.md]
- **입력 줄이 가려져 있으면 Esc로 닫고 보낸다(11-09)**: CC가 설정 화면 등을 띄워 두면 입력이 막혔다(하루 세 번). 붙여넣기 전에 입력 줄(❯)이 없으면 Esc를 보내고 0.6초 뒤 다시 본다, 최대 3번(`inject.clear_screen` — `deliver`가 부르므로 패널 입력 · 옮기기 넣기 · 감독실 [보내기] · 끝내기 모두 같은 길). 열리면 결과 글 "보냈습니다. 떠 있던 설정 화면을 Esc N번으로 닫고 보냈습니다."(입력 이벤트에 `esc` 수), 3번에도 안 되면 "Esc를 3번 보내도 닫히지 않았습니다 — 그 세션 터미널에서 확인해 주세요". **작업 중(busy)이면 Esc를 보내지 않는다** — Esc는 작업을 끊고 승인 · 질문 창에서는 거부가 된다. 실제 설정 화면이 Esc로 닫히는지는 아직 못 봤다 [log:plan_dialog_escape_retry_20261109.md]
- **제출 확인**: 보낸 글이 트랜스크립트에 프롬프트나 대기열(`queue-operation enqueue`)로 기록됐는지 본다. 안 되면 실패로 알리되 입력 칸은 자동으로 비우지 않는다(사람의 초안을 지울 수 있다)
- **바쁨 판정은 CC가 `~/.claude/sessions/<pid>.json`에 적는 `status`(busy · idle · shell)**. 바쁠 때 보낸 입력에도 UserPromptSubmit hook이 불린다 — 열린 턴이 있으면 새 턴을 열지 않는다

#### 트랜스크립트 읽기

경로는 `~/.claude/projects/<cwd의 / 와 _ 를 - 로 바꾼 이름>/<sessionId>.jsonl`, 서브에이전트는 `<sessionId>/subagents/agent-<id>.jsonl`. 한 줄이 JSON 하나이고 append-only다(compact도 같은 파일에 `compact_boundary`로, `--resume`도 같은 sessionId로 이어 쓴다). 대신 `cleanupPeriodDays`(기본 30일) 경과 시 파일이 **삭제**되므로 DB가 원본 보존 수단이 된다.

- **offset tail + inode 확인.** 세션별 `(inode, offset, last_uuid)`를 DB에 둔다. 재시작 시 inode가 같고 size ≥ offset이면 이어 읽고, 아니면 처음부터 다시 읽는다.
- **inotify로 감시.** 파일이 아니라 프로젝트 디렉토리 단위로 걸어 새 세션 파일 생성도 잡는다. 폴링 지연이 없다.
- **`api-request` 줄 선필터.** JSON 파싱 전에 `"type":"api-request` 문자열로 건너뛴다(561MB 중 76%).
- **개행으로 끝나지 않은 마지막 줄은 보류**하고 다음 읽기에서 처리한다(쓰는 중).
- **uuid UNIQUE로 중복 방지.** 다시 읽어도, hook과 트랜스크립트가 같은 사건을 두 번 만들어도 한 건만 남는다.
- **순서는 파일 기록 순서와 `parentUuid` 체인으로 잡는다. timestamp로 정렬하지 않는다.** 실측 49,454줄 중 4,975줄이 앞줄보다 이른 timestamp를 가졌다(최대 521초 역전).
- **API 메시지 하나가 content 블록마다 한 줄씩 쪼개진다**(한 줄 = 블록 1개). 같은 `message.id`의 줄은 usage가 전부 동일하므로, 토큰은 `message.id` 단위로 한 번만 센다.
- compact 요약은 `type: user`, `isCompactSummary: true`로 들어온다. 사용자 프롬프트로 세지 않는다.

### 3.2 턴 경계는 단일 신호로 판정하지 않는다

어느 신호도 혼자서는 모든 종료를 잡지 못한다(전체 트랜스크립트 실측).

| 종료 상황 | `turn_duration` | hook | 보완 신호 |
|---|---|---|---|
| 정상 종료 | 625/625 | Stop | — |
| 사용자 중단(Esc) | 29건 중 15건만 | Stop 미발동 (4단계 실측) | 트랜스크립트 `[Request interrupted by user]` 줄 — **첫 응답 전에 누르면 이 줄도 없다**(아래) |
| API 에러 | 2/2 | StopFailure (error, error_details) | — |
| 세션 종료 (창 닫힘·exit) | 0/5 | SessionEnd (reason) | 프로세스 소멸 폴링 |
| 턴 도중 auto-compact | 턴이 `compact_boundary`를 넘어 이어짐 | — | — |

그래서 턴에 `end_reason`을 두고, **먼저 도착한 신호가 턴을 닫는다**(`closed_by`에 출처: transcript · hook · sweep). 시작은 UserPromptSubmit hook, 실시간 종료 트리거는 Stop / StopFailure / SessionEnd hook, 중단은 interrupt 마커, 비정상 소멸은 폴링이 맡는다. `turn_duration`은 소요시간(`durationMs`)과 사후 대조에 쓴다.

**턴의 경계는 CC의 `promptId`다**(2단계 실측). 한 턴의 user 줄(프롬프트 · tool_result · 중단 표시 · compact 요약)이 모두 같은 `promptId`를 갖는다. 새 `promptId`를 가진 user 줄이 턴을 연다 — 사람 프롬프트만이 아니라 task-notification과 다른 세션의 메시지도 연다(`turn.origin`). 앞 턴이 안 닫힌 채 다음 턴이 열리면, 앞 턴에 모델 활동이 없었으면 `merged`(응답 없이 다음 입력과 함께 처리 — 실측 54건 전부), 있었으면 `no_signal`. 프로세스가 사라진 세션은 hook을 받던 세션이면 `process_lost`, 아니면 `session_end`. hook이 트랜스크립트보다 먼저 오는 경우(Stop이 마지막 응답 줄보다 먼저)는 늦게 온 줄을 직전 턴에 붙인다.

#### Esc 중단은 흔적을 남긴다 — FOREMAN이 다루는 법

CC에서 Esc로 중단하면 **Stop hook이 불리지 않는다**(4단계 실측). 이건 CC의 동작이라 FOREMAN이 바꿀 수 없다. 그래서 FOREMAN은 남는 흔적으로 판단한다.

| 언제 눌렀나 | 트랜스크립트에 남는 것 | FOREMAN |
|---|---|---|
| 응답이 오는 도중 · 도구 실행 중 | `[Request interrupted by user]` 줄 | 그 줄로 바로 `interrupted`(텔레그램 `⏹ 중단됨`) |
| **첫 응답이 오기 전**(프롬프트를 보내자마자) | 프롬프트 줄과 API 요청 줄뿐 — **중단 표시 줄도 없다** | 턴이 열린 채 남는다 → 아래 |

실제로 있었던 일(2026-11-02): 펫퍼민트 창에 잘못 붙여넣고 바로 Esc. 턴이 10시간 열려 있었고, 대시보드에는 그 세션이 "작업 중"으로 보였다.

열린 채 남은 턴은 이렇게 다룬다.
1. **화면**: 세션의 상태는 CC가 직접 적는 상태(busy · idle)로 정한다. 열린 턴이 있어도 CC가 일하지 않으면 "작업 중"이 아니라 "대기"이고, 카드에 **"⚠ 끝 신호 없는 턴"**을 따로 표시한다
2. **1시간 뒤 정리**: 프로세스는 살아 있는데 CC가 일하지 않고 그 턴이 1시간 넘게 조용하면 `abandoned`로 닫는다(정리 작업, 종료 시각은 마지막 활동 시각)
3. **다음 입력이 오면**: 응답 없이 열려 있던 앞 턴은 다음 입력까지 1시간 안이면 `merged`(다음 입력과 함께 처리됨), 1시간 넘으면 `abandoned`(버려짐)
4. **1시간인 이유**: 실측에서 진짜로 다음 입력과 합쳐진 턴은 66개 모두 56분 안이었다 — 1시간이면 그것을 잘못 닫지 않는다. 설정 `turn_abandon_s`

턴이 닫히는 순간 브리지가 한 번에 처리한다:

```
트랜스크립트 읽기 → DB 적재 → 텔레그램 발송 → WebSocket push → 캐릭터 상태 전환
```

텔레그램 알림 시점 = 캐릭터 상태 전환 시점이므로 하나를 구현하면 둘 다 된다.

**hook 설치 위치**: 사용자 설정 `~/.claude/settings.json`(2026-11-02, 모든 세션 — FOREMAN이 보려는 것이 런슈즈 · 펫퍼민트 세션이다). 설정 원본은 `deploy/hooks/foreman-hooks.json`, 스크립트는 `scripts/foreman-hook.sh`(2초 타임아웃 · 출력 없음 · 항상 exit 0 — 브리지가 꺼져 있어도 CC를 막지 않는다). 설치 전 백업은 `~/.claude/backups/settings.json.before-foreman-hooks`. **실행 중인 CC는 설정 파일 변경을 다음 프롬프트부터 반영한다**(3단계 실측 — 사용자 설정 · 프로젝트 설정 모두) — 이미 떠 있던 세션도 재시작 없이 hook을 보낸다.

**알림은 브리지가 보낸다(4단계, [결과](log/stage4_notify_result.md)).** 예전에는 CLAUDE.md 지시로 모델이 스크립트를 실행해 모델이 턴 종료를 판정했고 누락이 생겼다. 이제 턴이 닫히는 순간(먼저 온 신호) 브리지가 `config/notify.toml` 규칙으로 판정해 보낸다 — 종료 이유마다 제목이 다르고(끝남 · ⚠ API 오류 · ⏹ 중단 · 세션 종료 · ⚠ 프로세스 사라짐), 프로젝트 접두어를 붙인다. 사람이 연 턴만 보내고, 완료 알림 · 서브에이전트 결과 전달로 열린 턴은 보내지 않는다 — 백그라운드 서브에이전트는 세션의 것이 모두 끝났을 때 한 번 묶어 보낸다. 보낸 것 · 안 보낸 것(+규칙)은 `notification`에 남는다. 서브에이전트 결과 전달은 `<agent-message from=X>`의 X가 그 세션의 서브에이전트인지로 가른다(문장 모양으로는 못 가른다).

### 3.3 승인 정책

원래 불편 중 마지막 항목(5단계, [결과](log/stage5_approval_result.md)). PreToolUse hook마다 브리지가 판정한다 — 규칙은 `config/approval.toml`.

**원칙(11-05 다시 좁힘): 사용자가 실제로 거부할 만한 것만 묻는다** — 이론적 위험이 아니라. 목적은 auto mode에서 흐름이 안 끊기는 것. 그 전 승인 이력 65건 중 실제 작업에서 거부는 0건이었다(유일한 거부는 승인 창 시험). 경위 · 근거는 [결과 — 11-05 다시 좁히기](log/stage5_approval_result.md).

| 판정 | 대상 | CC에서 |
|---|---|---|
| `ask` | **통째로 지우기**(`/` · 시스템 최상위 · 홈 · `~/AI_programming`의 프로젝트 하나 · `~/volumes`의 볼륨 하나 …, `X/*`, 비면 `/`가 되는 `$X/`), **운영 DB 날리기**(foreman-mysql · 클러스터 쪽 `DROP` · `TRUNCATE` · WHERE 없는 `DELETE`), **재부팅 · 종료 · VM 파괴**, **작업 이력 날리기**(`push --force` · `reset --hard` · `clean -f` · `filter-branch`), **비밀 파일을 밖으로 보내기**, **데이터 볼륨 · PVC · 네임스페이스 · helm 릴리스 삭제**, CC · tmux 한꺼번에 끄기, `curl … \| sh`, `crontab -r` | 승인 창 — auto mode의 자동 통과보다 앞선다 |
| `allow` | **되돌릴 수 있는 것 · 읽기** — `kubectl apply` · `rollout`, `git push`, `docker stop` · `restart`, `systemctl restart`, 파일 편집 · 쓰기(작업 트리 밖 포함), Read · Grep · Glob, `git status · log · diff`. 명령의 모든 조각이 이래야 한다. 규칙 · 설정 파일 편집도 통과 + 텔레그램 🛡 | 승인 창 없이 통과 |
| `pass` | 그 밖 — `/tmp` · mktemp · 작업 트리 밖의 평범한 삭제, 비밀 파일 읽기 · 복사, 로컬 개발 DB, `kubectl delete pod`, `docker rm`, 해석기 heredoc 안의 글자 … | 브리지는 정하지 않는다 — CC(auto mode 분류기 · 사용자 설정)가 지금처럼 |

21일 다시 돌려 보기(11-05, 도구 호출 18,076개): 하루 승인 창 런슈즈 10.7 → **0.1**, 펫퍼민트 6.8 → **0.2**, 포먼 26.3 → **1.3**. 남은 9건은 모두 거부할 만한 것(운영 DB 비우기 4 · 이력 재작성 2 · PVC · 네임스페이스 삭제 3).

아래 "실행과 글자"부터 "늘 Yes 좁히기"까지는 11-05 전 **엄격한 규칙**에서 오탐을 하나씩 고친 기록이다. 그 장치는 코드에 남아 있고 설정으로 다시 켠다(`[sensitive] mode = "read"` · `protect_mode = "ask"`, `[ask] delete_outside_worktree = true` · `scan_interpreter_heredocs = true`). 시험은 `tests/test_approval.py`(엄격 규칙 = `tests/fixtures/approval_strict.toml`)와 `tests/test_approval_now.py`(지금 기준).

**승인 규칙을 시험할 때**: 판정 함수(`load_policy(...).decide(...)`)를 부르는 코드를 파일로 쓰고 `.venv/bin/python <파일>`로 돌린다 — 위험 명령 글자가 든 코드를 heredoc으로 넘기면 그 명령 자체가 hook에 걸린다. 과거 데이터 다시 돌려 보기는 `scripts/approval-replay.py`.

#### 실행과 글자는 다르다

같은 `rm -rf`라도 두 가지다.

- **실제로 지우는 명령** → 승인 요청
- **글자로 적어 두는 것** — 설정 파일에 규칙으로 적거나, 커밋 메시지에 쓰거나, 주석에 남기는 것 → 그냥 통과

**왜 필요했나.** 이 승인 시스템을 만드는 도중에 승인 시스템이 자기 자신을 막았다. 규칙 파일(`approval.toml`)에 위험한 명령의 모양을 적어 넣는 것만으로 승인 창이 떴고, 커밋 메시지에 "kubectl apply"라고 쓰는 것도 걸렸다. 세 번 연속 걸렸고, 그게 고친 계기다. 처음 규칙은 "명령에 이 글자가 있으면 묻는다"였는데, 그러면 위험한 명령에 대해 *쓰는* 일까지 막힌다.

**어떻게 가르나 — 그 글자가 어디로 들어가는지를 본다.**

| 예 | 무슨 일이 일어나나 | 판정 |
|---|---|---|
| `rm -rf build/` | 지운다 | 묻는다 |
| `cat > notes.md <<'EOF'` … `rm -rf` 설명 … `EOF` | 파일에 글자가 저장될 뿐 | 통과 |
| `git commit -F - <<'EOF'` … "rm -rf를 막는다" … `EOF` | 커밋 메시지로 저장될 뿐 (`git tag -F -`, `git notes`, `gh … --body-file -`도 같다) | 통과 |
| `bash <<'EOF'` … `rm -rf ~/data` … `EOF` | 셸이 그 줄을 **실행한다** | 묻는다 |
| `python3 - <<'EOF'` … `os.system("rm -rf /x")` … `EOF` | 파이썬이 **실행한다** | 묻는다 |
| `bash cleanup.sh` (안에 `rm -rf`가 들어 있다) | 파일 안의 명령이 **실행된다** — 실행하는 순간 파일 내용을 읽어 본다 | 묻는다 |
| `git commit -F - <<EOF` … `$(rm -rf x)` … `EOF` (EOF에 따옴표가 없다) | 따옴표 없는 본문 속 `$( )`는 셸이 **먼저 실행한다** — 받는 쪽이 커밋이어도 | 묻는다 |
| `grep -nE "rm -rf\|docker rm" log/*.md` | 그 글자를 **찾을** 뿐 (rg · sed · awk의 패턴 인자도 같다) | 통과 |
| `grep -o "rm -rf /x" f \| sh` | 찾은 글자를 셸이 **실행한다** — 뒤에 셸 · 해석기 · xargs가 오면 | 묻는다 |
| `grep "$(rm -rf x)" f` · `sed 's/a/b/e'` · `awk '{system($0)}'` | 패턴 자리에서 **실행된다**(명령 치환 · sed `e` · awk `system`) | 묻는다 |
| `bash -n deploy.sh` · `shellcheck` · `python -m py_compile` | 문법만 본다 — **실행하지 않는다** | 통과 |
| `sed -n 's/=.*//p' .env` · `cut -d= -f1 .env` | 비밀 파일을 읽지만 **키 이름만** 나온다 | 통과 |
| `sed -n 's/^TOKEN=//p' .env` · `cut -d= -f2 .env` | **값이 화면에** 찍힌다 — 한번 찍히면 되돌릴 수 없다 | 묻는다 |
| `curl -H @<(printf 'Authorization: Bearer %s' "$(sed -n 's/^TOKEN=//p' .env)") http://127.0.0.1:8000/…` | 값이 **이 서버로 가는 요청 헤더로만** 간다 | 통과 |
| 위와 같은데 `-v` · `--trace` · `--libcurl`, 또는 보내는 곳이 밖 · 변수 | 헤더가 화면 · 파일에 찍히거나 **값이 서버를 떠난다** | 묻는다 |
| `D=$(mktemp -d) … rm -rf "${D:?}"` (같은 명령 안) | **방금 만든 빈 임시 디렉토리**를 지운다 | 통과 |
| `D=/tmp/old; rm -rf "${D:?}"` · `D=$(mktemp -d); D=/home; rm -rf "${D:?}"` | 무엇을 지울지 이 명령 안에서 **확인할 수 없다** | 묻는다 |
| `python3 - <<'EOF'` … `open('.env.db', 'w')` … `EOF` | 스크립트가 **비밀 파일을 쓴다**(읽기만 — 앱이 설정을 읽는 것 — 은 통과) | 묻는다 |
| `git -C $d log` · `git -c x=1 -C "$d" status` (11-03) | `-C` · `-c` · `--git-dir` · `--work-tree` 다음은 **값**(경로 · 설정), 동사는 `log`로 고정 | 통과 |
| `git -C "$d" $VERB` · `git -C $x`(끝) | 동사가 변수 · 따옴표 없는 `$x`가 "경로 push --force"로 **쪼개질 수 있다** | 묻는다 |
| `echo "== cm/secret metadata"` · `printf '%s\n' '…'` (11-03) | 따옴표 친 글자를 **찍을 뿐** — echo는 파일을 읽지 않는다(안쪽 `vagrant ssh -c '…'` 스크립트 안에서도) | 통과 |
| `git commit -m "…rm -rf · .env…"` · `git tag -m` · `curl --data '{"…"}'` (11-03) | **메시지 · 요청 본문**으로 저장 · 전송될 뿐 | 통과 |
| `echo "…" \| docker exec -i db mysql` · `echo "…" \| sh` | 출력을 **받는 프로그램이 실행한다** — 파이프로 어디든 넘어가면 | 묻는다 |
| `$(echo "rm -rf x")` · `bash <(echo …)` · `echo … > run.sh` | 결과가 **명령으로 실행된다** · 스크립트로 쓴다 | 묻는다 |
| `echo rm -rf /x`(따옴표 없음) · `curl -d @.env …` · `git commit -m "$(cat .env)"` | 따옴표 없는 인자는 글자로 보지 않는다 · `@파일`은 **파일을 읽어 보낸다** · 따옴표 안 `$( )`도 **명령이다** | 묻는다 |

정리하면,

1. **텍스트로 저장만 되는 곳**(`cat > 파일`, `tee 파일`, `git commit -F -`, `git tag -F -`)에 들어가는 본문은 검사하지 않는다.
2. **실행기**(`bash`, `sh`, `python` 등)로 들어가는 본문은 검사한다.
3. **나중에 그 파일을 실행할 때**(`bash x.sh`, `source x`, `./x.sh`) 파일 내용을 검사한다 — 위험한 명령을 파일에 숨겨 두어도 실행하는 순간 잡힌다. 그래서 1번은 구멍이 아니다. 파일을 쓰는 다른 길(Write 도구)도 내용은 원래 검사하지 않았고, 똑같이 실행 순간에 잡힌다.
4. 따옴표 없는 본문 속 `$( )` · 백틱은 셸이 실제로 실행하므로, 받는 쪽이 커밋이어도 검사한다.
5. **넓힌 것(11-02)** — 같은 생각을 명령 한 줄 안으로 넓혔다: 검색어(grep · rg · sed · awk의 패턴 인자), 문법 검사만 하는 것(`bash -n` 등), 키 이름만 뽑는 것, 값이 로컬 요청 헤더로만 가는 것, 같은 명령 안에서 `mktemp -d`로 만든 디렉토리를 `${V:?}`로 지우는 것. 조건이 하나라도 어긋나면 예전처럼 검사한다. 이 예외는 "검사 전에 무해한 자리표시로 바꾸기"라 **새로 allow를 만들지 않는다**(allow 판정은 바꾸기 전 원문으로 한다).
   - `mktemp -d` 예외는 흉내 낸 우회를 막으려 좁게 잡았다: 변수가 같은 명령 안에서 `$(mktemp -d …)`로 **딱 한 번** 정해지고, 다시 정하기 · `for` · `read` · `eval` · `source` · `${V:=…}` · `export` · `unset`이 없고, 지우는 대상이 정확히 `"${V:?}"`일 때만(`..` · 덧붙인 경로 · 글롭 없음). 앞 명령에서 만든 디렉토리를 경로로 지우는 것은 이 명령 안에서 확인할 수 없어 여전히 묻는다 — 만들고 지우기를 한 명령에 둔다
   - 다시 돌려 보다 찾은 빈틈도 막았다: 해석기 heredoc(`python3 - <<EOF`)이 비밀 파일을 **쓰거나 바로 찍는** 것은 어느 규칙에도 안 걸렸다 → 묻는다
6. **넓힌 것(11-03) — 출력 · 메시지 리터럴**: `echo` · `printf`의 따옴표 인자, `git commit` · `tag`의 `-m`, `curl --data` 본문. 원칙은 PolicyApprovalGate의 것과 같다 — "명령어 자리만 실행이고 따옴표 친 인자는 글자다(`echo 'sudo rm -rf /'`는 아무것도 지우지 않는다)". 다만 출력이 **파이프로 어디든** 넘어가거나(`| mysql`도 실행한다 — 다시 돌려 보다 처음 안(셸만 막은) 판이 `echo "DROP DATABASE …" | docker exec -i … mysql`을 놓쳐서 넓혔다), 명령 · 프로세스 치환 안이거나, `.sh` · `.py`로 쓰면 예전처럼 검사한다. `git -C`의 값 자리도 이때 고쳤다

**오탐 패턴 정리(11-02 ~ 11-03)** — 모두 "검사 전에 자리표시로 바꾸기"라 allow를 새로 만들지 않는다:

| # | 모양 | 조건(하나라도 어긋나면 그대로 검사) |
|---|---|---|
| 1 | 파일로 저장하는 heredoc 본문 | 받는 쪽이 `cat >` · `tee` · `git commit -F -` · `git tag -F -`, 따옴표 친 EOF, `.sh` 등으로 쓰지 않음 |
| 2 | 검색 패턴(grep · rg · sed · awk) | 뒤에 셸 · 해석기 · xargs 없음, `$( )` 없음, sed `e` · awk `system` 없음 |
| 3 | 문법 검사(`bash -n` · shellcheck · py_compile) | 실행 옵션 없음 |
| 4 | `.env` 키 이름만 | 마지막 단계가 `sed 's/=.*//'` · `cut -d= -f1` · `awk -F= '{print $1}'`, 리다이렉트 · 치환 없음 |
| 5 | `mktemp -d` 디렉토리를 `"${V:?}"`로 지우기 | 같은 명령에서 딱 한 번 정해짐, 바꾸는 길 없음 |
| 6 | 비밀 값을 curl 헤더로만 | `-H @<(printf … "$(sed …)")` 모양, `-v` · `--trace` 없음, 보내는 곳이 이 서버 · VM 망 |
| 7 | `git -C` · `-c` 값 | 값 뒤 동사가 고정 |
| 8 | echo · printf · `-m` 메시지 · `--data` 본문 | 따옴표 안, `$( )` · 백틱 없음, 파이프 · 치환 · 스크립트 쓰기 없음 |

미리 훑어보고 **넣지 않은 것**: 변수 대입 리터럴(`MSG="rm -rf …"` — `$MSG`로 그대로 실행될 수 있다), 해석기 코드(`python3 -c "print('cat .env')"` — 글자인지 실행인지 가를 수 없다).

#### 다른 구현과 비교 (11-03)

바퀴를 다시 만들지 않으려고 공개된 PreToolUse 게이트 다섯을 읽었다(코드는 실행하지 않음). 통째로 바꾸지 않았다 — 우리 것은 이미 동작하고 실데이터로 검증했다. **오탐 처리 방식과 놓친 위험 패턴만** 가져왔다.

| 저장소 | 라이선스 | 매칭 | 우리 오탐 1~8 처리 | 가져온 것 |
|---|---|---|---|---|
| [nobuo-miura/PolicyApprovalGate](https://github.com/nobuo-miura/PolicyApprovalGate) | MIT | Go, 셸 AST(mvdan.cc/sh) — `sudo` · `timeout` · `env` 벗기기, `sh -c` · `eval` 다시 파싱 | 1 · 2 · 7(push만) · 8을 구조로 처리, 4 · 5 · 6은 우리보다 거칠다(`${V:?}` 삭제는 deny) | 8의 원칙("따옴표 친 인자는 글자"), 게이트 자기 보호(hook 스크립트 쓰기), `find -delete`, 재부팅, 비밀 경로 |
| [seelig-ai/claude-code-command-guard](https://github.com/seelig-ai/claude-code-command-guard)(Yodaisgaming에서 옮김) | MIT | JS 정규식, `sh -c` · heredoc · `$( )` 안을 한 번 더 훑는다. 파싱 실패 · 100KB 초과 → **deny**(fail-closed) | 없음(heredoc 본문까지 훑어 1은 더 막힌다) | `DELETE` WHERE 없음 · `FLUSHALL` · `dropdb`, `git filter-branch` · `reflog expire` · `gc --prune`, `truncate -s 0` · `> /dev/sd*` |
| [karanb192/claude-code-hooks](https://github.com/karanb192/claude-code-hooks) | MIT | JS 정규식, 3단계(critical · high · strict) | 없음(grep · echo는 오히려 더 막는다) | `printenv` · `/proc/*/environ`, `chmod 777`, 비밀 파일 목록(`.netrc` · `.npmrc` · `.docker/config.json` …) |
| [disler/claude-code-damage-control](https://github.com/disler/claude-code-damage-control) | README에 "MIT"만(LICENSE 파일 없음 — 코드는 가져오지 않았다) | Python 정규식 + 경로 목록(zero-access · read-only · no-delete) | 없음. `git\s+reset` 식이라 `git -C d reset --hard`는 **놓친다** | `pkill` · `killall`, 비밀 경로(`.gnupg` · `.aws` · `*.tfstate`) |
| TribeAI/claude-code-alignment-checks | — | **저장소 없음**(404, 소유자는 있음) | — | — |

- 가져오지 않은 것: 클라우드 CLI(`aws` · `terraform` · `gcloud` …)와 Windows 규칙 — 이 서버에 없다. AST 파서 — 파이썬에는 같은 수준의 셸 파서가 마땅치 않다(bashlex는 GPL). fail-closed — 파싱 실패를 막으면 우리 실데이터에서 heredoc · 긴 명령이 다 막힌다(우리는 파싱 실패 + `rm`이면 "애매한-삭제"로 묻는다)
- 다른 구현들은 우리 오탐 1~8을 대부분 다루지 않는다 — "글자를 지운 뒤 검사"는 우리 실데이터에서 나온 것이다
- **우리가 놓친 위험 중 실데이터에 있던 것**: 펫퍼민트 세션이 파일을 이력에서 지우려고 `git filter-branch` → `git reflog expire --expire=now --all` → `git gc --prune`을 실행했다(어느 규칙에도 안 걸렸다 — observe라 기록만). 이제 `git-기록파괴`로 묻는다
- 새 규칙(`ask.bash`): `git-기록파괴` · `find-삭제` · `권한-대량변경` · `재부팅-종료`(CLAUDE.md "재부팅은 사용자가 시킬 때만") · `프로세스-대량종료`(대상이 CC · tmux · 브리지 · 인프라일 때만 — 21일 실데이터 `pkill` 17건은 모두 자기가 띄운 스크립트를 끈 것) · `디스크-덮어쓰기` · `환경-덤프`, `DB-파괴`에 `DELETE`(WHERE 없음) · `FLUSHALL` · `dropdb` · `mysqladmin drop`, `git-강제push`에 `:브랜치` · 붙여 쓴 `-f` · `--prune`. 비밀 경로 7줄, 보호 파일 3줄(hook 스크립트 · `~/.claude.json` · `.mcp.json`)
- 따옴표 안 `$( )` · `<( )` · 백틱도 제 명령으로 본다 — `git commit -m "$(cat .env)"`가 통과하던 빈틈(전부터 있었다)

**다시 돌려 본 결과(11-03, 21일 · 도구 호출 18,014개)** — 하루 승인 창(활동한 날로 나눔):

| 프로젝트 | 전 | 후 | 바뀐 것 |
|---|---|---|---|
| 런슈즈 | 13.1 | 13.1 | — |
| 펫퍼민트 | 6.5 | 6.8 | 새로 잡음: `/proc/<pid>/environ` 읽기 4, 이력 재작성 2 |
| 포먼 | 34.5 | 39.5 | 새로 잡음: 시험 DB를 비우는 `DELETE FROM …` 7, hook 스크립트 쓰기 2, 토큰을 셸 변수로 읽기 1, environ 1. 빠짐: `echo "== cm/secret"` 1(이 일의 계기) |
| 미분류 | 5.3 | 6.3 | 새로 잡음: environ 3 |

새로 생긴 ask 21건을 하나씩 봤고 모두 실제로 위험하거나(비밀 · 이력 · 삭제) 의도한 자기 보호다. 도중에 찾은 오탐 3개(경로 속 `/tmp/claude-1000`의 claude, 파이썬 코드 `print(env)` · 마크다운 `| env |`)는 고쳤다. 포먼 수치는 활동한 날이 이틀뿐이고 그 이틀이 이 시스템을 만드는 날이라 높다.

그리고 **규칙 파일 자체**(`config/approval.toml`, `notify.toml`)는 쓰는 것 자체를 묻는다 — 위험한 글자가 들어 있어서가 아니라, 안전 규칙을 바꾸는 일이라서다.

**"늘 Yes" 두 규칙 좁히기(11-03, 승인 이력에서 나온 것)**:
- `보호-설정파일` 7일 10번 — **모두 Edit 도구로 `approval.toml`을 고친 것**(Bash로 덮어쓴 것 0). 그래서 `approval.toml` · `notify.toml`은 **Edit · Write 도구 편집은 통과**(바뀐 내용이 터미널 · 기록에 그대로 보인다) + 텔레그램 `🛡 안전 규칙 파일 수정`(같은 파일 10분에 한 번). **Bash로 쓰는 것은 계속 묻는다.** 게이트를 통째로 끌 수 있는 `~/.claude/settings.json` · hook 스크립트 · `~/.claude.json`은 도구 편집도 묻는다
  - 이걸 하다 찾은 빈틈: Bash 쓰기 중 `>` · heredoc만 보고 **`sed -i` · `cp` · `mv` · `tee` · `install` · `dd of=` · `truncate`로 보호 파일을 고치는 것은 안 걸렸다** → 묻는다. `cp`류는 목적지만 본다(`cp ~/.claude/settings.json 백업/`은 읽기)
- `민감한-경로` 7일 8번(14건 전체를 봤다) — 값을 다른 프로그램 표준 입력으로 넘기기 5(받는 쪽이 찍는지 확인할 수 없다) · 비밀 사본 만들기 2는 **계속 묻는다**. 값이 화면에 안 나오는 모양만 통과: `grep -q` · `-c`, 끝이 `wc` · `sha256sum`(뒤에 `cut` · `head` 가공 가능), `test -n "$(…)"`, 명령 치환 안에서도. `printf --`의 `--`를 옵션으로 못 알아본 오탐도 고쳤다
- 21일 다시 돌려 보기: 포먼 하루 43.5 → 35.5(보호-설정파일 15건 빠짐), 새로 생긴 ask 0

#### 근거 — hook의 `ask`는 auto mode에서도 승인 창을 띄운다

우리 설계는 이 한 가지에 기대어 돈다: **세 프로젝트 모두 auto mode인데, 되돌릴 수 없는 것만은 사람이 본다.** 공식 문서(11-03 확인):

- [permission-modes](https://code.claude.com/docs/en/permission-modes): "In auto mode, a PreToolUse hook's "ask" normally sends the tool call to the permission prompt, and the classifier doesn't decide it." — 그리고 "auto mode still shows you those prompts"(hook이 강제한 창)
- [hooks](https://code.claude.com/docs/en/hooks): `"ask"` prompts the user to confirm. 판정 없이 끝나면(exit 0, 출력 없음) "the tool call continues through the normal permission flow" — 브리지가 꺼졌을 때 우리 hook이 아무것도 내지 않는 이유. 여러 hook이 다르면 "deny > defer > ask > allow"
- [permissions](https://code.claude.com/docs/en/permissions): "PreToolUse hook decisions don't bypass permission rules … a matching ask rule still prompts even when the hook returned "allow"" — 우리 `allow`는 사용자 설정의 deny · ask 규칙을 넘지 못한다

**실측**: 이 세션(FOREMAN 작업, 트랜스크립트의 `permissionMode`가 461줄 모두 `auto`)에서 우리 `ask` 26건이 모두 승인 창으로 떴고 터미널에서 답했다(`approval`: terminal 24, 중단 1, 시간 초과 1).

**문서에 없는 것**(기대지 않는다): bypassPermissions · acceptEdits에서 hook `ask`, hook `allow`가 auto mode 분류기를 건너뛰는지(11-02 `kubectl patch`를 분류기가 막았을 때 우리 판정은 `pass`였다 — 이 질문의 실측은 아직 없다), `claude -p`에서 hook `ask`.

참고: PolicyApprovalGate 문서에 이 근거가 있다고 들었지만, 확인해 보니 그 저장소는 auto mode를 말하지 않고 공식 문서 링크도 없다. auto mode에서도 ask가 확인을 강제한다고 쓴 것은 command-guard README이고(출처 링크 없음), 위 공식 문서가 근거다.

#### 그 밖

**규칙에 없는 것을 `ask`로 하지 않는 이유**: 세 프로젝트 모두 auto mode로 돌고, 20일 동안 도구 호출 약 9,700건 중 사람이 승인을 누른 것은 18건뿐이었다. 규칙에 없는 모든 것을 묻게 하면 승인 창이 수천 건이 된다. `unmatched = "ask"`로 바꿀 수 있다.

**승인 창이 뜨면**(우리 ask든 CC 자체 판단이든) PermissionRequest hook이 브리지에 와서 승인 대기가 생기고 텔레그램 `🔐 승인 대기`가 간다. **브라우저(확인 페이지) · 터미널 · 시간 초과(10분) 중 먼저 온 것이 정한다** — hook이 기다리는 동안에도 터미널 승인 창은 떠 있고, 터미널에서 먼저 답하면 바로 진행된다(실측). 브리지가 꺼져 있으면 hook은 아무것도 돌려주지 않는다 — CC가 지금처럼 정한다(허용 쪽으로 새지 않는다).

**질문(AskUserQuestion)은 승인이 아니지만 같은 길로 받는다(11-09)**: CC가 질문 창을 띄울 때도 PermissionRequest hook이 불린다. 정책(`approval.toml`)에서 빼지 **않는다** — 빼면 질문이 터미널에만 떠 텔레그램 · 화면 알림이 없고 턴도 안 끝나 턴 끝 알림도 없다(세션이 조용히 멈춘다). 대신 모양 · 답하는 길을 따로 둔다: 규칙 이름 "질문", 카드 "❓ 세션이 묻습니다"에 선택지 버튼, 텔레그램 "❓ 세션이 묻습니다 — 답을 기다립니다", 머리말 · 현장 버튼 · 방 카드 · 패널 머리에서 승인 대기와 따로 센다. 패널에서 고르면 `decision.behavior = "allow"` + `updatedInput` = 원래 입력 전체 + `answers`(질문 글 → 선택지 이름, 여러 개는 `", "`로 이음)로 돌려준다(`bridge/approvals.py` `answer()`). 문서는 "Multi-select answers join labels with commas"까지만 말한다 — `", "`로 이은 답이 세션에 그대로 들어가는 것은 실측(11-09 #70, 하나 고름 · 여러 개 고름). 브리지가 다시 뜨면 선택지를 잃어 "터미널에서 답합니다"로 바뀐다. 경위는 `log/pixel_bigger_question_card_20261109.md`

**승인 창 한 줄 요약(11-03)**: 명령 통째로는 읽기 힘들다 — 판단에 필요한 건 "무엇을 대상으로"다. `bridge/approval_summary.py`가 규칙이 아니라 명령을 보고 대상을 뽑는다: `rm -rf → /home/kopo17/volumes (기존 디렉토리, 파일 418개)` · `rm -rf → $D (이 명령에서 mktemp로 만든 것)` · `kubectl delete → pod/jenkins-0 (jenkins 네임스페이스)` · `DROP DATABASE x (컨테이너 runshoes-mysql-dev)` · `읽기(cat) → …/.env.bridge (비밀 파일)`. CC 승인 창(`permissionDecisionReason` 맨 앞) · 텔레그램 둘째 줄 · 대시보드 승인 카드(명령 전체는 접어 둠) · `approval.summary`에 같은 줄. CC 자체가 묻는 것(rule `cc`)에도 붙는다. 디렉토리 파일 수는 0.3초 안에서만 센다(PreToolUse는 4초 안에 답해야 한다).

**승인 이력(11-03)**: 대시보드 "승인 이력"(`/api/approvals/history?days=1|7|30`) — 규칙별로 걸린 수 · 승인 · 거부 · 모름, 최근 목록(요약 줄), 관찰 모드 프로젝트에서 "걸렸을 것". **3번 넘게 걸렸는데 한 번도 거부하지 않은 규칙은 "늘 Yes — 규칙 손볼 후보"**로 표시한다(묻는 의미가 없으면 규칙을 고친다). 시간 초과 · 재시작 뒤 터미널에서 답한 것은 그 도구가 실행됐는지(`tool_result`)로 거꾸로 안다. 처음 본 7일: 45건 중 승인 44 · 거부 1, 늘 Yes = 보호-설정파일 10 · 민감한-경로 8.

**모든 판정을 남긴다**: 자동 승인 · pass까지 `event(type=approval_req)`(규칙 · 이유 · 강제 여부), 승인 대기와 결과는 `approval` 테이블과 `event(approval_res)`. ask와 결정은 로그에도 이유와 함께.

**프로젝트별 mode**: `enforce`(판정을 돌려준다) / `observe`(기록만). 실행 중인 세션에 곧바로 걸리므로 런슈즈 · 펫퍼민트는 observe로 시작했다 — 쌓인 판정을 보고 enforce로 바꾼다.

### 3.4 병렬 작업과 충돌

한 프로젝트에 캐릭터를 둘 이상 붙이면 같은 파일을 덮어쓴다. **git worktree**로 세션마다 별도 워킹트리와 브랜치를 준다.

```
캐릭터 생성 = git worktree add + tmux 세션 생성 + claude 실행 (pane 하나에 claude 하나)
```

UI에서도 "이 캐릭터는 이 브랜치"가 자연스럽게 보인다. 머지는 포먼이 한다.

### 3.5 자동 기상

캐릭터가 스스로 세션을 붙일 수 있다. 단, 상한을 건다.

| 항목 | 제한 |
|---|---|
| 동시 ACTIVE | 최대 3 (초과 시 대기열) |
| 자동 기상 조건 | 실패 이벤트만 (성공은 무시) |
| 자동 세션 수명 | 30분 후 강제 IDLE |
| 일일 자동 기상 | N회 제한 |
| 야간 자동 기상 | 끔 |

자동으로 깬 세션은 **읽기 전용**으로 시작한다. 원인 분석까지만 하고 보고한다. 고치는 것은 사람의 승인을 받는다. 자는 사이에 커밋이 쌓이면 안 된다.

### 3.6 CI/CD 인과 체인

이 프로젝트의 **차별점**. 기존 도구들은 각자 자기 구간만 안다.

```
캐릭터가 파일을 고쳤다
  → 이 커밋이 됐다          (commit_sha)
    → 이 빌드가 돌았다       (Jenkins)
      → 이 태그가 올라갔다   (Harbor)
        → 이 리비전이 동기화됐다 (ArgoCD)
          → 실패했다, 여기서
```

연결고리는 **커밋 SHA**다. 캐릭터 이벤트에 SHA를 심고, 각 웹훅에서 같은 SHA를 받으면 자동으로 묶인다.

시각적으로도 이어진다. 캐릭터가 작업을 마치고 파이프라인 구역으로 걸어가고, 거기서 실패하면 그 지점이 붉게 표시된다.

**실제 흐름(8단계 조사, 2026-11-02 — 적용은 보류)** — 런슈즈 · 펫퍼민트는 같은 구조이고, **전 구간이 폴링**이다(웹훅 없음 — 운영 도구는 Cloudflare Access 뒤라 GitHub 웹훅이 닿지 않는다):

```
로컬 커밋 → GitHub push ─(최대 2분, Jenkins SCM 폴링)→ Jenkins 빌드 → Harbor push(태그 = 커밋 12자리)
  → ronanlab-infra apps/<앱> newTag 커밋 ─(최대 3분, ArgoCD 폴링)→ 런슈즈 자동 Sync / 펫퍼민트 수동 Sync
```

**FOREMAN이 끼어드는 법(정한 방향)** — 기존 흐름에 아무것도 더하지 않고 **읽기 조회**로 본다:
- **Jenkins**: 읽기 API(빌드 결과 · 머리 SHA · 묶인 커밋 · 스테이지별 상태). 2분 폴링 사이에 push된 커밋 여럿이 빌드 하나가 되는 것도 Jenkins가 알려 준다. 필요한 것은 읽기 토큰 하나
- **Harbor**: 따로 받지 않는다 — push는 Jenkins "빌드·push" 스테이지 안이고 태그가 곧 커밋. 생존 확인만
- **ArgoCD**: notifications 웹훅이 후보(동기화 동작은 그대로) — **App of Apps 구조를 본 뒤** 정한다
- **커밋 → 세션**: Jenkins가 알려 준 커밋의 제목 · 시각으로 그 세션의 `git commit` 도구 호출을 찾는다(**명령에 커밋 제목이 있어야** 귀속 — 실데이터 66개 모두 일치). 로컬 저장소를 따로 폴링하지 않는다
- 인프라 캐릭터는 첫 관찰에 등장하고 ingress VIP 폴링으로 생존을 본다. 실패는 실패로 바뀔 때 텔레그램 한 번
- **문서만 바뀐 빌드는 건너뜀이 정상(11-09, 런슈즈 요청 4절):** 바뀐 파일이 모두 `docs/` · `portfolio/` · `config/portfolio.toml` · `*.md`면 Jenkinsfile이 이미지 빌드 · 태그 커밋을 건너뛰고 SUCCESS로 끝내며, `foremanNotify` 본문에 **`"skipped": true`**를 더한다(칸 이름은 FOREMAN이 정함). 브리지는 그 빌드에 이미지 태그를 붙이지 않고(시작 알림 때 붙은 것도 지운다) 단계 글을 "건너뜀 — 문서만"으로 둔다 → Harbor · ArgoCD를 기다리지 않고(배포 대기 빌드로 고르지 않는다), 화면은 빌드에서 끝나며 이미지 · 배포 칸은 "–"(정상). push ↔ 빌드 대응은 그대로 — 건너뛴 빌드도 알림은 온다

- **ArgoCD 수동 Sync 대기 알림(11-09):** 배포 안 된 이미지가 Sync를 기다리면(가장 오래된 빌드의 Jenkins 끝 시각 기준) **처음 1시간 뒤 한 번, 풀릴 때까지 24시간마다** 텔레그램 "⏸ 배포 대기 N일 N시간째 — ArgoCD에서 Sync를 눌러야 올라갑니다". 같은 회차는 `notification.rule` 키로 한 번. 근거: 배포는 약 5분이고 수동 Sync는 보통 빌드 직후 누른다 — 1시간이면 잊은 것, 한 통만 보내면 그걸 놓쳤을 때 11-02 → 11-09처럼 일주일이 간다 [log:screen_mismatch_waits_20261109.md]
- **끝 알림 없이 "진행 중"에 남는 배포(11-09):** ArgoCD가 Healthy 알림을 보내지 않아 running이 남던 것 — running이 10분 넘으면 ArgoCD를 **직접 읽고**(`vagrant ssh m-k8s` kubectl get application, 읽기 전용 — API 토큰은 두지 않는다) 그 리비전 작업이 끝났으면 닫는다. Sync 작업 시작 뒤 30분이 지나도 안 끝났거나 못 읽으면 행마다 텔레그램 "⏳ 배포가 끝나지 않습니다"(`config/pipeline.toml [argocd_read]`) [log:screen_argocd_read_20261109.md]

처음엔 실제 설정을 읽기 전에 웹훅을 새로 붙이는 쪽(Jenkinsfile 수정 · Harbor 정책 · 웹훅 포트)으로 설계했다가 되돌렸다 — 경위와 실제 설정 표는 [8단계 기록](log/stage8_cicd_result.md)

### 3.7 LLM 지표

AI 인프라 관점의 핵심 축. 프로젝트마다 호스트에 LLM이 떠 있다.

| 지표 | 수집 | 시각화 |
|---|---|---|
| 큐 대기 수 | 요청 추적 | 캐릭터 앞에 줄이 선다 |
| TTFT | 응답 측정 | 반응 지연 |
| tok/s | 응답 측정 | 움직임 속도 |
| VRAM 사용률 | nvidia-smi / DCGM | 캐릭터가 땀을 흘린다 |
| 동시 요청 수 | 요청 추적 | — |
| GPU 점유율 | nvidia-smi / DCGM | — |

프로메테우스가 긁고 브리지가 쿼리한다. 프로메테우스 캐릭터는 "다른 캐릭터들의 지표를 공급하는 역할"이 된다.

### 3.8 테마

이벤트 → 애니메이션 매핑 테이블을 JSON으로 분리한다. 렌더러는 `status`와 `tool`만 보고 그리므로, 테마 교체가 매핑 파일 교체로 끝난다.

| 이벤트 | 오피스 | 도서관 |
|---|---|---|
| `tool_use/Read` | 책상에서 타이핑 | 서가에서 책을 꺼냄 |
| `tool_use/Bash` | 서버랙으로 걸어감 | 지하 서고로 내려감 |
| `IDLE` | 의자에 앉음 | 열람석에 앉음 |

**3D는 쓰지 않는다.** 에셋과 카메라·조명 비용이 2D의 몇 배인데 전달되는 정보량은 같다. 2D로 테마 세 개가 3D 하나보다 낫다.

**크기(11-09)**: 방은 이미 무대에 꽉 차 있어(1920은 높이, 1366 · 1024는 폭이 한계) 방을 다 보이게 둔 채로는 방 안의 그림만 키울 수 있다. **캐릭터만 1.5배**(테마 `sprites.char_scale`, `sprites.js charFrame`이 키운 크기를 돌려줘 얼굴 칸 · 소품 · 이름표 · 점검이 같이 따른다) — **가구는 키우지 않는다**(칸 배치 · 길찾기 · 앉기와 묶여 있다, 사용자 결정). 화면 좌표 글씨는 원래 px × 글씨 배율(가+/가−) × 1.2. 경위는 `log/pixel_bigger_question_card_20261109.md` 「3.」

#### 서브에이전트 렌더링

데이터 모델과 렌더링을 분리한다. 서브에이전트는 캐릭터가 아니라 `subagent_run` 행이지만(3.11), **렌더러는 이것을 실제 일꾼으로 그린다.** "에이전트들이 돌아다니면서 일하는" 장면이 이 화면의 목표이고, 서브에이전트 10개가 동시에 도는 것이 그 장면의 핵심이다.

- **외형은 부모 캐릭터의 축소판이다.** 부모 스프라이트를 작게 줄이고 색조만 살짝 바꾼다. 별도 에셋이 필요 없고, 누가 띄웠는지 선이나 색으로 설명하지 않아도 생김새로 보인다. 한 방에서 코더와 CI/CD 캐릭터가 각각 서브에이전트를 띄워도 구분되고, 역할별 외형도 그대로 상속된다 — CI/CD 캐릭터가 띄우면 작은 CI/CD 일꾼이 나온다.
- **위치는 부모 옆이다.** 그러므로 자동으로 부모와 같은 방 안이다(2.5).
- **움직임은 부모와 같은 매핑 테이블을 쓴다.** 서브에이전트 안의 도구 사용도 `status`·`tool` 이벤트이므로 테마 매핑을 그대로 탄다.
- **부모가 IDLE이어도 일꾼은 돈다.** 부모는 자리에 앉아 있고 작은 일꾼들이 돌아다니며, 부모 위에 "백그라운드 n개" 배지가 붙는다(3.11).
  - 11-06 반영: 서브에이전트나 백그라운드 Bash · Monitor가 돌면 IDLE 부모를 **기다림(WAITING)** 으로 그린다. 자는 모습 대신 책상에 서서 "…"를 띄우고, 이름 아래 "백그라운드 n · 설명"을 붙이며, 현장 집계는 작업으로 센다. 서버 상태 값은 그대로 IDLE이고 화면만 바꾼다(`theme.js` `viewState`, 테마 `states.WAITING`)
- **복잡도:** 같은 작업을 여러 개로 나눠 띄우는 경우가 흔하므로(예: "Wide yes/no search wn1"…) `description`의 공통 앞부분으로 묶어 묶음 이름을 단다. **접는 것은 한 부모의 일꾼이 10개를 넘을 때만** — 넘는 만큼 "+N"으로 접는다.

### 3.9 터미널 패널

CC에게 시킬 수 없는 일이 있다. sudo 암호, SSH 패스프레이즈, 레지스트리 로그인.

```
┌─────────────────────────────┬──────────┐
│                             │  패널     │
│      캐릭터 화면             │  (대화)   │
├─────────────────────────────┴──────────┤
│  터미널  (접이식)                        │
└────────────────────────────────────────┘
```

CC가 "이 명령을 실행해주세요"라고 하면 브리지가 감지해 터미널 패널을 올리고 명령어를 미리 채운다. 비밀번호 부분만 비워둔다. 실행 결과는 해당 캐릭터에게 전달된다.

비밀번호가 CC 컨텍스트에 들어가지 않는다. 사람이 직접 치고, CC는 결과만 받는다. 사람의 수동 개입은 이벤트로 기록하되, 민감 값은 마스킹한다.

**만든 모양(7단계)** — ttyd와 tmux를 그대로 쓰고, 브리지는 길만 낸다.

```
브라우저 iframe /terminal/ ──(쿠키)── 브리지 127.0.0.1:8000 ──── ttyd (.run/ttyd.sock, TCP 포트 없음)
                                                                    └─ tmux foreman-shell ─ bash --rcfile deploy/shell/foreman-bashrc
                                                                         └─ 탭마다 그룹 세션 foreman-shell-v-<탭>(deploy/shell/foreman-term-view — 셸은 함께, 보이는 창만 탭마다. 탭을 닫으면 사라짐, 11-10)
셸 PROMPT_COMMAND ── /hooks/shell(hook 토큰) ──> event(source=shell, type=shell_cmd, 마스킹)
CC 턴 끝 ── 부탁 감지 ──> 셸 입력 줄에 미리 채움(send-keys, Enter 없음) + WS terminal_request(패널을 올린다)
사람이 그 명령을 침 ──> 출력(capture-pane, 마스킹) ──> 부탁한 세션에 주입(3단계 방법 C) · 안 되면 화면에만
```

- **밖에 열리지 않는다.** ttyd는 TCP 포트를 열지 않고 UNIX 소켓에만 묶는다(디렉토리 0700 — 다른 사용자도 못 붙는다). 127.0.0.1 포트보다 한 단계 좁다. 브라우저는 브리지를 거쳐서만 닿는다: API 토큰으로 쿠키(HttpOnly · SameSite=Strict · Path=/terminal, 브리지 메모리에만 — 브리지를 다시 띄우면 새로 받는다)를 받고, WS는 Origin이 Host와 같아야 한다(다른 사이트가 브라우저 쿠키로 셸을 여는 것을 막는다). 화면은 같은 출처의 틀 안에서만(`X-Frame-Options: SAMEORIGIN`)
- **승인 정책은 걸리지 않는다, 기록은 남는다.** 명령마다 `shell_cmd` 이벤트(명령 · 종료 코드 · 위치). 마스킹은 기존 규칙(정확한 값 · 토큰 모양 · `KEY=값`)에 명령줄 자리를 더했다: `--password 값`, `docker/podman/helm registry login -p 값`, `mysql -p값`, `sshpass -p`, `echo 값 | sudo -S`, `| … --password-stdin`, URL의 `user:암호@`, `curl -u user:암호`. 셸 기록 파일은 디스크에 남기지 않고(`HISTFILE=`), 공백으로 시작하는 명령도 기록한다(`HISTCONTROL=`)
- **셸은 캐릭터가 아니다.** `character_session.type='shell'`(포먼 프로젝트의 포먼에 붙인 행 하나). 대시보드 · 세션 목록은 `type='agent'`만 본다
- **부탁 찾기** — 턴이 `stop`으로 끝나면 그 턴의 assistant 글에서: ① 셸 코드 블록 · 인라인 코드 · `! 명령` 안에 ② 사람이 쳐야 하는 명령(`sudo` · `su` · `ssh-add` · `ssh-keygen` · `ssh-copy-id` · `passwd` · `kinit` · `docker/podman/… login` · `gh/glab/gcloud auth login` …)이 있고 ③ 부탁하는 말("실행해 주세요" · "쳐 주세요" · "직접 실행" · "please run" …)이 있을 때. 설명 · 기록에 나온 `sudo`는 ③이 없어 걸리지 않는다. `! 명령` 꼴은 그 자체가 부탁이다. 여럿이면 첫 번째를 채우고 나머지는 배너에 보인다
- **미리 채우기** — 셸 입력 줄을 비우고(C-e C-u) 글자로 넣는다(`send-keys -l`, Enter 없음). 비밀번호 자리(`<password>` · `«masked…»` · `YOUR_…` · `-p 값` 등)는 비우고 커서를 거기로 옮긴다. 셸이 다른 일을 하는 중이면(암호 입력 중 · 다른 명령 실행 중) 건드리지 않고 배너에 "다시 채우기"를 둔다
- **결과 전달** — 사람이 친 명령이 부탁과 같으면(비운 자리 앞까지, 아니면 앞 단어 세 개) 화면에서 그 명령의 출력(명령을 친 프롬프트 줄 다음부터 새 프롬프트 앞까지, 마지막 60줄)을 마스킹해 `[터미널 패널] …`로 부탁한 세션에 넣는다. 주입이 안 되는 세션(tmux 밖 · 정지)은 배너에만 보인다. 부탁은 30분 기다리고, 세션마다 최신 하나만 둔다

### 3.10 서버 연결 상태

브리지가 서버 PC에서 돌므로, 서버가 죽으면 브리지도 죽는다. 따라서 "서버 다운"은 브리지가 알려주는 것이 아니라 **브라우저가 WebSocket 끊김으로 판단**한다.

끊기면 화면 전체를 덮고 재연결을 시도한다. 침묵으로 아는 것이다. 확인 페이지에 붙였다(4단계): 한 번 연결된 뒤 끊기면(1006 · 서버 종료 · 하트비트 두 번 놓침) 덮개에 언제부터 끊겼는지와 다음 시도까지 남은 초를 보이고 1→2→4→8→15초로 다시 붙는다. 토큰이 틀려 끊긴 것(1008)은 덮지 않고 멈춘다.

---

### 3.11 서브에이전트 (CC 세션 안의 병렬)

CC 세션 하나가 `Agent` 도구(이 버전에서는 `Task`가 아니라 `Agent`)로 서브에이전트를 띄운다. 실측(2026-11-02): 런슈즈 132회, 동시 최대 10개 / 펫퍼민트 47회, 동시 최대 6개. 179회 전부 `async_launched` — 결과는 tool_result가 아니라 **나중에 부모의 새 입력으로** 돌아온다.

**캐릭터가 아니다.** 부모 프로세스 안에서 몇 분 살다 끝나고 한 세션에서 10개까지 동시에 뜨므로 `character` 테이블에 넣지 않는다(영속 캐릭터, 포먼만 채용). FOREMAN이 띄우는 일꾼(자기 tmux·worktree·CC 세션)은 캐릭터이고, CC 내부 서브에이전트는 `subagent_run` 행이다. 화면에서는 일꾼으로 그린다(3.8 서브에이전트 렌더링).

#### 트랜스크립트 구조 (실측)

- 위치: `~/.claude/projects/<proj>/<sessionId>/subagents/agent-<agentId>.jsonl` + `agent-<agentId>.meta.json`(`agentType`, `description`, `toolUseId`, `spawnDepth`, `requestShape`, `finished`). 런슈즈 132쌍 160.7MB, 펫퍼민트 47쌍 48.4MB
- 기록 종류와 필드는 부모와 같다 — 같은 파서를 쓴다. 다른 점:
  - 모든 줄에 `agentId`, `isSidechain: true`
  - **`sessionId`가 부모와 같다.** 부모·자식 구별은 `agentId`·파일 경로로 한다
  - 첫 줄 `parentUuid`가 null — 부모의 uuid 체인과 이어지지 않는다
  - **system 기록이 없다**(`turn_duration` 없음). 소요 시간은 첫·마지막 줄 timestamp로 잰다
- 부모와 잇는 필드:

```
부모 assistant  tool_use(name=Agent).id ─┬─ meta.json toolUseId
                                         └─ 나중의 <task-notification> <tool-use-id>
부모 user       tool_result.toolUseResult = {agentId, status: async_launched, description, outputFile, …}
                agentId ─┬─ 파일 이름 agent-<agentId>.jsonl, 자식의 모든 줄 agentId
                         └─ <task-notification> <task-id>
결과 전달       부모 queue-operation enqueue
                → user "<agent-message from=agentId> [Subagent hand-back] …" + "<task-notification> … <status> <summary>"
```

#### 처리 규칙

- **와처**: 세션 폴더의 `subagents/`도 inotify로 감시한다. 종료는 `meta.json`의 `finished`와 SubagentStop hook, `<task-notification>`의 status로 판정한다. 부모 세션의 프로세스가 사라지면 남은 running은 stopped. `api-request` 선필터도 같게 적용한다.
- **행을 만드는 곳**: 부모의 `Agent` tool_result(`toolUseResult.agentId`, `async_launched`)에서 만들고 그 턴을 `spawn_turn`으로 한다(2단계). 자식 파일이 먼저 오면 meta.json으로 만들고 연결 작업이 나중에 채운다.
- **귀속**: 백그라운드는 띄운 턴과 결과를 받는 턴이 다르다. 토큰·이벤트는 **띄운 턴**(`toolUseId`로 연결)에 귀속하고, 결과를 받은 턴은 `result_turn_id`로 따로 남긴다.
- **상태**: 부모 턴이 Stop으로 끝나도 자식은 돌 수 있다(토큰은 계속 나간다). 상태 값을 늘리지 않고 **"IDLE + 백그라운드 n개"** 배지로 보인다.
  - 백그라운드 Bash · Monitor도 같이 센다(11-06, 서브에이전트가 아니라 `subagent_run`에는 넣지 않는다)
    - 시작: 도구 결과의 `backgroundTaskId` · `taskId` → 이벤트 `bg_start`
    - 끝: `<task-notification>`의 status → `bg_end`. 큐(enqueue) · 첨부(queued_command) · 사람 줄 어디로 와도 한 번만 남는다
    - 대시보드 `background`에는 끝 없는 시작만 들어간다(살아 있는 세션, 지금 CC 프로세스가 뜬 뒤 시작한 것)
- **알림**: 서브에이전트마다 보내지 않는다. 부모 턴이 끝날 때 한 번, 또는 백그라운드 묶음이 모두 끝났을 때 한 번 묶어서 보낸다.
- **토큰**: 서브에이전트 단위로 따로 저장하고, 화면에서는 부모 턴에 "본인 + 서브에이전트"로 나눠 합산해 보인다.

#### 출력 토큰 문제 (미해결)

- 서브에이전트 줄의 usage는 **응답을 받기 시작한 시점의 값**으로 보인다 — `stop_reason`이 null이고 output_tokens가 글자당 0.002(부모는 0.77, 예: 10,603자 블록에 8). 입력 쪽(cache_read·cache_creation)은 그럴듯하지만 검증 안 함
- **SubagentStop hook 입력에 usage가 없다**(2.1.316 바이너리). 필드는 공통(session_id, transcript_path, cwd, permission_mode, agent_id, agent_type, effort) + `stop_hook_active`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`, `session_crons`
- 완료 알림(`<task-notification>`)의 **일부**에 합계가 있다 — `<usage><subagent_tokens>N</subagent_tokens><tool_uses>N</tool_uses><duration_ms>N</duration_ms></usage>`. 런슈즈 서브에이전트 140개 중 34개, 펫퍼민트 `cddadc68` 18개 중 11개(completed 알림인데도 없는 경우가 많다). 종류 구분 없는 합계 하나이고 입력 포함 여부는 미확인. **소수에만 있으므로 주 경로로 쓰지 않는다** — 있으면 `subagent_run`에 합계로 남겨 다른 경로의 값과 대조하는 **보조 검증용**으로만 쓴다
- **주 경로 후보: OpenTelemetry 메트릭 `claude_code.token.usage`** — 위 합계로 대신할 수 없으므로 **OTel 실측은 여전히 필요하다**. — 응답이 끝난 뒤의 최종 usage로 type(input·output·cacheRead·cacheCreation)별로 더하고, 속성에 `model`·`query_source`·`effort`가 붙는다. `query_source`로 본체와 서브에이전트가 구분되는지는 실측이 필요하다
- 실측 방법: 버리는 디렉토리에서 `CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=console OTEL_METRIC_EXPORT_INTERVAL=5000`으로 CC를 띄워, 서브에이전트 없는 프롬프트 하나와 서브에이전트 하나를 띄우는 프롬프트 하나를 보낸다. 콘솔 메트릭의 `query_source` 값과 output 합계를, 같은 세션 트랜스크립트 부모 줄의 output 합계와 비교한다
- 그 전까지 서브에이전트 output은 `output_tokens_reliable = false`로 저장하고 화면에 "추정"으로 표시한다

**미정**: 동시 서브에이전트 수에 상한·경고를 둘지. 자동 기상의 "동시 ACTIVE 최대 3"(3.5)은 캐릭터 세션 수이고 서브에이전트는 세지 않는다.

### 3.12 배치 — 브리지와 DB는 클러스터 밖, 호스트에 둔다

**결정 (2026-11-02)**: 브리지는 호스트 프로세스, DB는 호스트 도커의 **FOREMAN 전용 MySQL**(`127.0.0.1:3308`)이다. 클러스터(k8s)에 올리지 않는다.

**결정적 이유 — 감시하는 쪽과 감시받는 쪽의 장애 범위를 나눈다.** FOREMAN은 클러스터와 호스트 서비스가 망가지는 순간을 기록하려고 만든다. DB가 클러스터 안에 있으면 클러스터가 흔들리는 바로 그 순간에 적재가 멈추고 화면이 꺼진다. 2026-11-02의 두 사고가 정확히 그런 상황이었다 — `milvus-port-forward.service`가 한 달 넘게 567,740회 재시작했고, milvus 컨테이너가 17분 크래시 루프를 돌았다(2.2). 감시 장비가 감시 대상과 같이 죽으면 그 기록이 남지 않는다.

그 밖의 근거:

- 브리지가 다루는 것(tmux, `~/.claude/projects/` 트랜스크립트, hook, `/proc` 폴링, systemd·docker 폴링)이 전부 호스트에 있다. DB도 같은 곳에 둔다
- 재부팅 때 docker 데몬과 함께 바로 뜬다. VM 4대와 클러스터가 다 올라오기를 기다리지 않는다
- **기존 MySQL에 얹지 않는다.** 클러스터의 `petmint/mysql-0` · `runshoes/runshoes-mysql-0`는 운영 DB이고 headless라 호스트에서 바로 붙을 수 없다. 호스트 3306(`mysql`)은 펫퍼민트 로컬 개발·측정용이다 — 펫퍼민트 `db/bootstrap.py`가 관리하고, 초기화할 때(`~/mysql-data`를 비우는 경우 등) FOREMAN 기록이 같이 사라지며, FOREMAN이 계속 쓰면 측정값이 오염된다
- 검토하고 버린 선택지: m-k8s에서 `kubectl port-forward`(파드가 재시작되면 끊기고 감독 프로세스가 따로 필요하다 — `milvus-port-forward`와 같은 모양), NodePort·MetalLB 신설(연결은 되지만 위의 장애 범위 문제가 그대로이고, 데이터가 노드 하나의 `local-path`에 묶인다)

**브리지를 파드로 띄울 수 없는 이유**: 여기서 k8s 노드는 libvirt VM이다. `hostPID`·`hostPath`가 가리키는 "호스트"는 서버 PC가 아니라 VM이므로, 서버 PC의 claude 프로세스(`/proc`)도 `~/.claude/`도 보이지 않는다. tmux 유닉스 소켓은 VM 경계를 넘지 못한다. 우회하려면 파드에서 호스트로 ssh해야 하는데, 그러면 사용자 계정의 ssh 키가 클러스터 Secret에 들어간다 — 파드 하나가 털리면 서버 PC 셸이 털린다. 트랜스크립트를 NFS로 내보내면 클라이언트 쪽에서 inotify가 오지 않아 폴링으로 돌아간다.

**수집부(호스트) · API/UI(파드)로 나누지 않는다 — 배포는 systemd, 테스트는 GitHub Actions(2026-11-03 결정).** 처음에는 "8단계(CI/CD)에서 다시 본다"로 미뤘던 것이다. 다시 보니 나눌 이유가 오히려 줄었다.

- **떼어낼 수 있는 UI가 사실상 없다.** 실시간 상태(WS 버스 · 조립된 턴), 승인 대기(PreToolUse hook이 응답을 기다린다), 터미널(ttyd UNIX 소켓, 3.9)이 모두 브리지 프로세스 안이나 호스트에 묶여 있다. 파드로 옮길 수 있는 것은 정적 HTML · JS(약 1,260줄)뿐이고, 그 파드는 호스트 브리지 앞의 프록시가 될 뿐이다
- **UI는 빌드할 것이 없다.** 번들러 없는 순수 JS이고, 저장소 파일을 그대로 낸다(no-cache). "빌드 · 이미지 · Harbor · ArgoCD"를 태우면 단계만 늘고 얻는 것이 없다
- **런슈즈 UI와 닮은 점은 "브라우저로 본다"뿐이다.** 런슈즈는 밖의 사용자에게 여는 서비스이고, FOREMAN UI는 호스트 셸(터미널 패널) · 승인 권한을 가진 관제실이다. 클러스터 · 터널 쪽으로 옮기면 노출 면만 커진다
- 처음의 이유도 그대로다 — 배포 단위가 둘이면 그 사이 프로토콜과 한쪽만 죽는 상태를 다뤄야 하고, 클러스터가 죽으면 정작 그때 화면이 꺼지며, 물리 서버가 하나라 가용성도 늘지 않는다

대신 실제로 도움이 되는 두 가지만 한다:

| 무엇 | 왜 | 하지 않는 것 |
|---|---|---|
| **systemd 유닛**(브리지) | 지금 가장 큰 운영 공백 — tmux에 손으로 띄워 재부팅하면 안 뜨고, 죽어도 다시 안 뜬다. 재시작은 유닛 + 사람이 부르는 스크립트 하나(시험 → import 확인 → 대기 중인 승인이 없을 때만 재시작) | **push마다 자동 재시작은 하지 않는다.** 작업 폴더가 곧 실행 폴더이고 커밋하는 CC 세션도 같은 호스트라 받아올(pull) 코드가 없다 — 배포는 사실상 재시작인데, 재시작은 승인 대기와 화면 연결을 끊는다. 커밋한 그 세션의 hook이 끊길 수도 있다 |
| **GitHub Actions에서 시험 자동 실행** | 승인 정책(`approval.py`)은 보안 규칙이라 퇴행을 막을 가치가 크다(순수 함수 시험). DB 시험은 MySQL 서비스 컨테이너로. tmux를 쓰는 시험은 설치하거나 건너뛴다 | **우리 Jenkins에 태우지 않는다.** 그쪽은 이미지를 만들어 Harbor로 보내는 서비스용이고 FOREMAN에는 이미지가 없다 — Jenkinsfile · 시험 DB · 인프라 저장소 수정이 생겨 통일을 위한 통일이 된다 |

다시 볼 조건은 하나 — **VNC 없이 밖에서 FOREMAN을 봐야 할 때.** 그때도 답은 파드가 아니라 호스트 브리지에 바로 붙이는 것이다 — 다만 지금은 밖에 열지 않기로 했다(3.13).

### 3.13 외부 노출 — 터널을 열지 않는다 (2026-11-03 결정)

처음 설계는 6단계 뒤에 `foreman.ronanlab.dev` 터널 + Cloudflare Access로 밖에서 보는 것이었다([브리프 02](docs/02_cloudflare_tunnel.md)). **열지 않기로 했다.** 브리프는 지우지 않고 "⏸ 보류 — 필요해지면"으로 둔다.

- **FOREMAN은 뚫리면 서버 셸이 열리는 물건이다.** 대시보드에는 터미널 패널(ttyd — 호스트 셸, 3.9), 실행 중인 CC 세션에 입력 주입(3.1 — tmux send-keys), 승인 · 거부(되돌릴 수 없는 명령을 통과시키는 버튼)가 있다. 앞단 인증 하나가 깨지면 보는 화면이 아니라 서버를 내주는 셈이다
- **공유 서버다.** 이 서버는 kopo17 · kopo02가 같이 쓴다 — 여기서 셸이 열리면 피해가 이 프로젝트에서 끝나지 않고 다른 계정까지 간다
- **밖에서 필요한 정보는 이미 텔레그램으로 받는다.** 턴 종료 알림(4단계), 승인 대기와 그 요약(5단계 · 11-03), 파이프라인 실패 · 빠진 알림 · 웹훅 끊김(8단계), 적재 막힘(11-03). 보기만 할 거면 이걸로 된다 — **그거 하나 보려고 터널을 유지할 값어치가 없다**
- **못 해서가 아니라 안 한 것이다.** 런슈즈 · 펫퍼민트는 같은 서버에서 이미 터널(클러스터 `cloudflared`, `runshoes.ronanlab.dev` · `petmint.ronanlab.dev`)로 공개했고, Jenkins · ArgoCD · Harbor도 Access 뒤에 열어 두었다. 열 줄 알고, 열 길도 있다. FOREMAN은 열었을 때 잃을 것과 얻을 것을 따져 열지 않았다
- **필요해지면 여는 길**: 지금 화면을 그대로 여는 게 아니라 **읽기 전용 화면**(터미널 패널 · 입력 · 승인 버튼 없이 세션 상태 · 파이프라인만)을 따로 두고, 사람 인증을 **패스키나 mTLS**(클라이언트 인증서 — 기기에 묶인다)로 강하게 해서 연다. 승인은 그때도 텔레그램 · 서버 앞에서. 브리프 02는 이 조건으로 고쳐 쓴다

## 4. 만들 것과 가져다 쓸 것

이미 잘 만들어진 것을 조합하고, 비어 있는 구간만 직접 채운다.

| 구간 | 방식 | 근거 |
|---|---|---|
| 터미널 웹화 | ttyd | 성숙한 도구. 재발명 금지 |
| 프론트 터미널 | xterm.js | 표준 |
| 세션 목록·제어 | 기존 구현 참고 | tmux 다루는 로직만 차용 |
| 상태 수집 | CC hooks | 공식 기능 |
| 캐릭터 스프라이트 | MIT / CC0 에셋 | pixel-agents 계열 |
| 지표 수집 | 프로메테우스 | 어차피 설치 예정 |
| **CI/CD 인과 체인** | 직접 | 기존 구현에 없음 |
| **캐릭터↔인프라 매핑** | 직접 | 기존 구현에 없음 |
| **승인 정책 엔진** | 직접 | 기존 구현에 없음 |
| **LLM 병목 시각화** | 직접 | 기존 구현에 없음 |

### 참고할 기존 프로젝트

| 프로젝트 | 볼 것 |
|---|---|
| Ramillax/claude-code-control-room | ttyd + tmux + hook 상태. 프레임워크 없이 bash·Python 표준 라이브러리. 구조가 가장 가깝다 |
| mxinO/Claude-Web-UI | send-keys 입력 릴레이, 브라우저 툴 승인, 재접속 시 놓친 이벤트 요약 |
| wolfpeter/claude-session-manager | xterm.js ↔ node-pty ↔ tmux attach, 세션 디스커버리 |
| nielsgroen/claude-tmux | git worktree 연계, 세션 상태(idle/working/waiting) 감지 |
| pablodelucca/pixel-agents | 캐릭터 렌더링, 레이아웃 (MIT) |

CC에는 `/remote-control` 모드가 이미 존재한다. 세션 뷰어 구간은 레드오션이므로 여기서 차별화를 시도하지 않는다.

---

## 5. 데이터 모델

> 실제 DDL의 기준은 [`migrations/0001_init.sql`](migrations/0001_init.sql)이다. 1단계에서 승인된 차이(`transcript_file` 분리, event FK 없음, `target_truncated`, `build` · `summary` 보류 등)는 그 파일 머리말과 [1단계 결과](log/stage1_bridge_db_result.md)에 있다. 아래 표는 개념 설명이다.

### project

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| name | varchar | runshoes, petmint-rag-chatbot |
| repo_path | varchar | 메인 리포 경로 |
| repo_url | varchar | GitLab |
| namespace | varchar | K8s 네임스페이스 |
| created_at | datetime | |

### character

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| project_id | FK nullable | null이면 떠돌이 ('미분류' 등) |
| parent_id | FK nullable | 누가 낳았나. null이면 포먼이거나 독립 |
| name | varchar | 표시 이름 |
| sprite | varchar | 외형 키 |
| current_role | enum | foreman coder cicd inspector helper infra |
| status | enum | ACTIVE IDLE DORMANT SUSPENDED STALE |
| kind | enum | agent 세션 가능 / infra 실체 대응 |
| infra_type | varchar nullable | jenkins harbor argocd prometheus llm |
| infra_source | enum nullable | k8s host external |
| infra_endpoint | varchar nullable | 헬스체크·조회 대상 |
| home_position | json | 화면상 자기 자리 |
| watch_targets | json nullable | 상태를 이 캐릭터에 반영할 systemd 유닛·docker 컨테이너 이름(2.2). 어디에도 없는 유닛은 포먼 경고 목록 |
| spawned_by | enum | user foreman cicd auto |
| created_at / retired_at | datetime | |

### character_session

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| character_id | FK | |
| type | enum | agent / shell |
| role | enum | 이 세션에서의 역할 (캐릭터 역할과 별개로 이력 보존) |
| tmux_pane | varchar | tmux pane ID (`%N`). 세션 이름보다 정확한 주입 대상 |
| pid | int nullable | claude 프로세스. 상태 폴링(SUSPENDED 판정·소멸 감지)용 |
| cc_session_id | varchar nullable | CC가 발급한 세션 ID. `--resume`은 같은 ID를 이어 쓰므로 여러 행에 걸칠 수 있다 |
| transcript_path | varchar nullable | JSONL 경로 |
| transcript_inode | bigint nullable | 재시작 시 같은 파일인지 확인 |
| transcript_offset | bigint nullable | 어디까지 읽었나 (바이트) |
| last_uuid | varchar nullable | 마지막으로 적재한 줄의 uuid |
| worktree_path | varchar nullable | |
| branch | varchar nullable | |
| attached_at / detached_at | datetime | |
| token_usage | int | 캐릭터별 누적 비용 산출용 (`message`에서 집계한 캐시) |
| wake_reason | enum | user auto_failure foreman |

### turn

프롬프트 하나부터 턴이 닫힐 때까지가 한 행이다. 메시지 내용은 `message`와 `event`에 있다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| session_id | FK | |
| seq | int | |
| prompt_uuid | varchar | 프롬프트 줄의 uuid |
| prompt_text | text | 사용자 입력 (compact 요약 줄은 제외) |
| started_at / ended_at | datetime | |
| end_reason | enum | stop stop_failure interrupted session_end process_lost merged no_signal abandoned (3.2) |
| duration_ms | int nullable | `system/turn_duration`의 `durationMs` |
| compacted | bool | 턴 도중 compact가 일어났나 |

### message

API 응답 하나(`message.id`)가 한 행이다. 트랜스크립트에서는 content 블록마다 줄이 쪼개지지만 usage는 줄마다 같으므로 여기서 한 번만 센다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK varchar | `msg_…` |
| turn_id | FK | 서브에이전트 메시지는 띄운 턴 |
| subagent_id | FK nullable | 서브에이전트의 API 응답이면 그 `subagent_run` |
| model | varchar | |
| stop_reason | varchar | end_turn tool_use stop_sequence … |
| request_id | varchar | `req_…` |
| token_input | int | |
| token_output | int | |
| token_cache_read | int | 실제 입력의 대부분 |
| token_cache_creation | int | |

### subagent_run

CC 세션 안에서 `Agent` 도구로 띄운 서브에이전트 하나가 한 행이다(3.11). 캐릭터가 아니다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| session_id | FK | 부모 `character_session` |
| agent_id | varchar UNIQUE | 트랜스크립트·파일 이름의 `agentId` |
| tool_use_id | varchar | 부모의 `Agent` tool_use id = meta.json `toolUseId` |
| spawn_turn_id | FK | 띄운 턴. 토큰·이벤트는 여기에 귀속 |
| result_turn_id | FK nullable | hand-back을 받은 턴(백그라운드는 다를 수 있다) |
| agent_type | varchar | general-purpose, fork … |
| mode | enum | foreground background fork |
| spawn_depth | int | meta.json `spawnDepth` |
| description | varchar | 묶음 표시에 쓴다(3.8) |
| transcript_path | varchar | `subagents/agent-<agentId>.jsonl` |
| transcript_inode / transcript_offset | bigint nullable | 부모 세션과 같은 방식으로 이어 읽기 |
| started_at / ended_at | datetime | 첫·마지막 줄 timestamp(system 기록이 없다) |
| status | enum | running done failed stopped |
| token_input / token_output / token_cache_read / token_cache_creation | int | `message.id` 단위로 한 번씩 |
| output_tokens_reliable | bool | 서브에이전트 줄의 output은 응답 시작 시점 값이라 false(3.11) |

### event

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| uuid | varchar UNIQUE nullable | 트랜스크립트 줄 uuid. 재적재·hook 중복 방지 |
| parent_uuid | varchar nullable | 순서의 기준 (timestamp 아님) |
| session_id | FK nullable | 호스트 감시 이벤트(`restart_loop`)는 세션이 없다 |
| character_id | FK nullable | 세션 없는 이벤트를 붙일 캐릭터(`watch_targets`로 찾음). 둘 다 없으면 포먼 경고 목록 |
| turn_id | FK nullable | |
| message_id | FK nullable | 어느 API 응답의 블록인가 |
| subagent_id | FK nullable | 서브에이전트 안에서 일어난 이벤트 |
| tool_use_id | varchar nullable | tool_use와 tool_result 짝짓기 |
| source | enum | hook transcript poll bridge shell(7단계 터미널 패널) |
| ts | datetime | 표시용. 정렬에 쓰지 않는다 |
| type | enum | start tool_use tool_result assistant_msg stop error approval_req approval_res interrupted compact queued session_end subagent_start subagent_stop restart_loop input shell_cmd term_request term_result |
| tool | varchar nullable | Read, Edit, Bash … |
| target | varchar nullable | 파일 경로, 명령어 (마스킹 적용) |
| status | enum | working idle waiting done error |
| commit_sha | varchar nullable | 인과 체인 연결고리 |
| payload | json | 툴마다 다른 필드 |

### build

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| project_id | FK | |
| character_id | FK nullable | 이 변경을 만든 캐릭터 |
| commit_sha | varchar | 체인 연결(그 단계가 다룬 머리 커밋) |
| stage | enum | jenkins harbor argocd — 커밋 단계는 `git_commit`(로컬 저장소 폴링, 세션 귀속)이 맡는다(8단계, GitLab 없음) |
| status | enum | running success failed |
| started_at / ended_at | datetime | |
| log_url | varchar | |
| message | text | 실패 사유 |

실제 DDL은 [`migrations/0012_pipeline.sql`](migrations/0012_pipeline.sql) — `build`에 `external_id`(Jenkins `job#번호` · Harbor `repo@digest` · ArgoCD `app@리비전`, 프로젝트 · 단계와 함께 UNIQUE) · `tag` · `step`(깨진 스테이지) · `infra_character_id`를 더했고, `git_commit`(커밋 · 세션 귀속 · push 시각)과 `build_commit`(빌드 하나에 묶인 커밋들)을 따로 둔다.

### summary

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| character_id | FK | |
| session_id | FK | 어느 세션의 요약인가 |
| period_start / period_end | datetime | |
| done | text | 한 일 |
| pending | text | 미완 |
| next_actions | text | 다음 할 일 |
| injected_to | FK nullable | 어느 세션에 주입됐나 (인계 사슬) |

### 보관 정책

`event`는 양이 빠르게 늘어난다. 보관 기간을 정하고, 기간이 지나면 요약만 남기고 원본을 지운다. 스키마 설계 시점에 함께 결정한다.

**적재 제외**: `api-request`, `api-request-blob` 줄은 적재하지 않는다(트랜스크립트 용량의 80% 이상, 대화 복원에 불필요).

**hook 설치 후에는 재적재하지 않는다**(원칙, 2026-11-02 사용자 결정). turn · message · event는 트랜스크립트에서 다시 만들 수 있지만 **hook 이벤트(`event.source = 'hook'`)와 hook이 정한 턴 필드(`closed_by = 'hook'`인 턴의 종료 시각 · 이유)는 트랜스크립트에 없다** — 다시 만들면 사라진다(2단계에서 실제로 확인). 트랜스크립트 쪽 오류는 다시 읽기(offset 0, 멱등)나 새 마이그레이션으로 고치고, 파생 테이블을 비우는 전체 재구성은 하지 않는다. 꼭 해야 할 상황이면 hook 이벤트와 hook이 닫은 턴을 따로 백업한 뒤 하고, 재구성 뒤 되살린다.

**조회 화면에서 도구 결과 본문이 필요하면** DB가 아니라 트랜스크립트에서 직접 읽는다(`event.tool_use_id` → 트랜스크립트 줄). DB에는 길이 · 오류 여부만 둔다 — 형식을 모르는 비밀은 마스킹으로 못 잡는다(2단계, 사용자 확인).

CC의 `cleanupPeriodDays`(기본 30일)가 트랜스크립트 원본을 지우므로 서버 PC 설정에서 120일로 올려 두었다. 서버를 쓸 수 있는 기간에 맞춘 값이다(하루 약 64MB × 120일 ≈ 7.7GB, 결정 당시 디스크 84%). 브리지 적재가 안정되면 이 값과 `event` 보관 기간을 함께 다시 정한다.

### 인덱스

| 테이블 | 인덱스 | 용도 |
|---|---|---|
| event | `(session_id, ts)` | 세션 타임라인 |
| event | `(commit_sha)` | 인과 체인 |
| event | `uuid` UNIQUE | 중복 방지 |
| message | `(turn_id)` | 턴별 토큰 집계 |
| message | `(subagent_id)` | 서브에이전트별 토큰 집계 |
| event | `(subagent_id)` | 서브에이전트 타임라인 |
| event | `(character_id, type, ts)` | 캐릭터별 재시작 루프 조회 |
| subagent_run | `agent_id` UNIQUE | 트랜스크립트·hook·알림에서 찾기 |
| subagent_run | `(session_id, status)` | 지금 도는 서브에이전트(배지·렌더링) |
| subagent_run | `(spawn_turn_id)` | 턴별 합산 |
| build | `(commit_sha)` | 인과 체인 |
| character_session | `(cc_session_id)` | hook 수신 시 세션 찾기 |
| character_session | `(character_id, detached_at)` | 현재 붙어 있는 세션 조회 |

---

## 6. 로드맵

| 단계 | 내용 | 비고 |
|---|---|---|
| 0 | `cleanupPeriodDays` 상향 (완료: 120일) + CC를 tmux로 이전 | ✅ **완료**(2026-11-08, 세 프로젝트 모두 tmux) — SSH + tmux attach만으로 VNC 우회. pane 하나에 claude 하나. **tmux 이전은 FOREMAN 세션(`cc-foreman`)만 했다.** 런슈즈 · 펫퍼민트 세션(14일 · 17일째)은 옮기다 컨텍스트를 날릴 위험이 커서 FOREMAN이 실제로 동작하는 것을 확인한 뒤에 옮긴다(2026-11-02 결정). **런슈즈는 11-05에 옮겼다**(`/exit` → tmux `cc-runshoes`에서 `claude --resume`, 대화 · 세션 행 이어짐, [결과](log/stage0_tmux_result.md)). **펫퍼민트는 11-08에 옮겼다**(정전 뒤 프로세스가 없어 tmux `cc-petmint`에서 `claude --resume`, 같은 세션 행 이어짐 — 같은 결과 문서 「펫퍼민트」) |
| 1 | 브리지 + 스키마 + MySQL + WebSocket | ✅ **완료**(2026-11-02, [결과](log/stage1_bridge_db_result.md)) — 집 PC 브라우저 왕복까지 확인. 토대. MySQL은 호스트 도커 전용 인스턴스(3.12) |
| 2 | hook 수신 + inotify 기반 JSONL 와처 (offset tail, `subagents/` 포함) + 턴 판정 (`end_reason`) | ✅ **완료**(2026-11-02, [결과](log/stage2_transcript_result.md)) — 1.4GB 백필 18초, 다시 읽어도 행 · 턴 상태 동일. hook은 사용자 설정에 설치(3단계 때) |
| 3 | send-keys 실측 선행 → 입력 → 왕복 완성 | ✅ **완료**(2026-11-02, [결과](log/stage3_inject_result.md)) — 방법 C 성립. `/` · `!`는 앞 공백으로 막음, 제출 확인, 바쁨은 대기열. 주입 대상은 tmux 안의 CC뿐(런슈즈 · 펫퍼민트는 0단계 이전 뒤) |
| 4 | 텔레그램 이관 + 연결 끊김 표시 | ✅ **완료**(2026-11-02, [결과](log/stage4_notify_result.md)) — 런슈즈 · 펫퍼민트 · 포먼 실제 턴으로 확인 후 세 저장소의 CLAUDE.md 알림 절 · `scripts/notify-telegram.sh`를 정리. 턴 종료 → 전송 평균 3.3초 |
| 5 | 승인 정책 엔진 | ✅ **완료**(2026-11-02, [결과](log/stage5_approval_result.md)) — 위험한 것은 ask · 확실한 것만 allow · 나머지는 CC에, 브라우저 · 텔레그램 · 터미널 승인, 모든 판정 기록. 런슈즈 · 펫퍼민트는 observe로 시작. **이어서 — 다른 저장소 막음**(11-09 1단계, [기록](log/repo_scope_readonly_20261109.md)): 11-10 인프라 세션도 읽기만, 예외로 런슈즈 · 펫퍼민트 원본 `docs/`만 고치기 · 경로 적은 `git add` · `commit`(push 막음, [결과](log/coder_infra_project_20261110.md) 「더한 것」) · 관리자 세션만 docs 전용 push(`[repo_scope.manager_push]`, [결과](log/coder_manager_docs_push_20261110.md)) |
| 6 | 대시보드 (못생겨도 되는 실사용 UI) | ✅ **완료**(2026-11-02, [결과](log/stage6_dashboard_result.md)) — 프로젝트별 세션 상태 · 하는 일 · 대화 · 서브에이전트 · 승인 · 토큰, 입력 · 승인 · 끊김. 데이터(`static/js/store.js`)와 그리기(`render.js`)를 나눠 10단계에서 그리기만 바꾼다. 여기까지가 매일 쓸 수 있는 물건 |
| 7 | 터미널 패널 (ttyd) + 명령 자동 채우기 | ✅ **완료**(2026-11-02, [결과](log/stage7_terminal_result.md)) — ttyd(UNIX 소켓) + tmux `foreman-shell`, 대시보드 아래 접이식, 친 명령 기록(마스킹), CC 부탁 감지 → 미리 채움 → 결과를 그 세션에(3.9). 사용자가 패널 · 새 텔레그램 토큰 동작 확인 |
| 8 | CI/CD 웹훅 + 인과 체인 + 파이프라인 구역 | ✅ **적용**(2026-11-03, [결과](log/stage8_cicd_result.md)) — Jenkinsfile `foremanNotify`(시작 · 끝, 실패해도 빌드 영향 없음) → 브리지 8001, 빠진 알림 찾기 · 웹훅 끊김 감지, 검증 빌드 2개(런슈즈 웹훅 첫 검증). ArgoCD 알림 웹훅(기본 구독 + `instance=root` — 자식 앱만, 루트 제외 실측), 수동 Sync는 "⏸ Sync 대기"(실패와 구분). 시험 중 웹훅 토큰이 도구 출력에 노출 → 피해 범위를 따진 뒤 교체(log). 이전 기록: ⏸ 조사 완료, 적용 보류(2026-11-02) — 실제 파이프라인은 폴링(Jenkins 2분 · ArgoCD 3분, 웹훅 없음)이었다. 기존 흐름은 건드리지 않고 **읽기 조회**로 끼어든다(Jenkins 읽기 API, Harbor는 Jenkins 스테이지로, ArgoCD는 알림 웹훅 후보). **ArgoCD App of Apps를 먼저** 하고 그 구조에 맞춰 적용한다. 지금 브리지의 파이프라인 기능은 꺼 둠. 차별점. **11-03 재조사**: App of Apps(`root` → `runshoes` · `petmint` · `cloudflared`) · 웹훅이 들어왔다(Jenkins 웹훅 + 폴링 15분 안전망, ArgoCD 웹훅 + 폴링 3분). 재개 범위 — Jenkins는 **Jenkinsfile 알림 + 토큰 없는 보정**(API 조회용 토큰이 실은 Jenkins 관리자 = 배포 경로 전체의 열쇠라 "새도 되는 비밀의 무게"로 뒤집음, 설계안 log) · ArgoCD 알림 웹훅(기본 구독 + `instance=root`) · 웹훅 끊김 감지 · 파이프라인 표시(펫퍼민트는 "Sync 대기 중") · 인프라 캐릭터. **FOREMAN 자신: 분리하지 않는다, 배포는 systemd, 테스트는 Actions**(3.12). **9단계와 순서를 바꿨다**(아래) |
| 9 | LLM 지표 + 병목 시각화 | ⏸ **보류**(2026-11-03) — 프로메테우스는 펫퍼민트 쪽과 상의가 끝나지 않았다. 10단계를 먼저 한다. AI 인프라 축. 프로메테우스는 펫퍼민트 설계가 정해진 뒤에 설치한다(아래) |

**8 · 9단계 순서를 바꾼 이유**(2026-11-02 사용자 결정) — 원래는 LLM 지표가 8, CI/CD가 9였다.
- **LLM 지표는 프로메테우스가 있어야 하는데, 프로메테우스는 펫퍼민트 설계와 맞물려 있다.** 펫퍼민트(RAG 챗봇)의 LLM · 검색 서비스가 어떤 지표를 어디로 내보낼지가 정해진 뒤에 설치해야 두 번 손대지 않는다. 지금 깔면 펫퍼민트 쪽 결정에 끌려 다시 바꾸게 된다. 설치 자체는 데모 시나리오(7장)로 아껴 둔 것이기도 하다
- **CI/CD는 새로 설치할 것이 없다.** GitLab · Jenkins · Harbor · ArgoCD가 이미 런슈즈 · 펫퍼민트 파이프라인으로 돌고 있다. FOREMAN은 웹훅을 받고 생존을 폴링하기만 하면 된다 — 바로 시작할 수 있고, 인과 체인은 이 프로젝트의 차별점이다
| 10 | 테마 렌더러 — 픽셀 오피스 | 🔧 **10a 끝**(2026-11-03, 사용자 확인 대기) — `/office`: 지도(방 셋 + 라운지) ↔ 방 줌, 도형 캐릭터, 상태별 모습(ACTIVE 움직임 · IDLE 앉음 · SUSPENDED 얼음 · DORMANT 서 있음), 포먼 구석 사무실, 인프라 구역, 방 배지(작업 · 승인 · 파이프라인 · **토큰 오늘 · 최근 10분**). 매핑은 `static/themes/office/theme.json`(판정 `js/theme.js`, `node --test`). 줌 방식으로 결정(2.5). **10d 첫 시트 테마 — 마법학교**(2026-11-05, [결과](log/stage10_office_result.md)): `/office?theme=magic`. 구역 9개(서고 · 작업대 · 물약실 · 시약대 · 원탁방 · 대강당 · 아치 창 · 봉인대 · 출하 라인) + 교장실, Ninja Adventure 캐릭터 4방향 걷기, 앉기 · 엎드려 자기 · 들기 · 석화 · 유령은 엔진 흉내, Bash는 명령으로 구역을 가른다(test → 시약대, git → 봉인대). 에셋은 원본 그대로 + 렌더러가 외곽선 · 색조([LICENSES.md](LICENSES.md) — Calciumtrice CC-BY 3.0, 0x72 · Ninja Adventure CC0). 이어서(같은 날): **감독실(1단)** — 테마마다 현황판(지도+촛불 · 모니터 월 · 공정표+자석), 현장 카드, 누르면 현장 · Esc로 복귀 / **서브에이전트(10c)** — 마법진에서 소환 · 부모 둘레 · 연기 퇴장, 10명 + N / **역할 색 구조**(로브 · 사원증 끈 · 안전모, `?roles=demo`) / **오피스**(2dPig + 직접 그림) · **현장**(Ninja + 직접 그림 19개) 시트 테마. 테마 넷: 오피스 · 마법학교 · 현장 · 도형(plain). 구역 이름표(테마마다 양피지 · 사인판 · 안전 노랑) · 출하 라인 세 단계 이름 + 상태. **10b**(같은 날): 옆 패널 — 캐릭터를 누르면 최근 대화 · 입력(Ctrl+Enter) · 승인 · 거부, 인프라는 파이프라인 체인, 승인 이력, 터미널(아래 접이식), 연결 끊김 띠. 패널은 캔버스를 덮지 않고 옆에 선다(접기 · [좁게] / [넓게] 두 값 — 11-10 모눈 작업에서 끌기 · 너비 기억을 없앰). **모눈**(11-10, [결과](log/designer_grid_20261110.md)): 방 열한 개 · 복도를 칸 한 벌(`themes/_shared/grid.json`)로 다시 짜 세 테마가 같은 자리, 방 이름표는 방 왼쪽 위 칸에 고정, 방 배율은 0.25 계단이라 글씨 배율에 흔들리지 않음, 캐릭터 한 칸, 점검 `gridAudit`. **인프라 방**(11-10, [결과](log/coder_infra_project_20261110.md) · [띄움 · 합침](log/infra_bundle1_launch_20261110.md)): `ronanlab-infra`를 넷째 현장 「인프라」로(0029 시드), 같은 모눈에 출하장은 「출하장 없음」, 터미널 · 알림 `[인프라]`, Notion 게시는 아직 꺼 둠(인프라 `docs/`가 생긴 뒤). **`/` = 픽셀 화면, 예전 화면은 `/classic`**, 테마는 마지막에 본 것을 기억 |
| 11 | 캐릭터 수명 관리 + 포먼 + 세션 인계 | ✅ **완료**(2026-11-05 — 남은 것: 디스패처 자동 기상 3단계는 2단계를 써 본 뒤(2단계는 14에서 함), 런슈즈 실제 인계는 발볼 검증 뒤). **이어서(11-06)**: 인계 검증 — 넣을 때 「인계 뒤 바뀐 것」을 기계로 붙임([결과](log/handoff_verify_20261106.md)) · 겹침 알림 — 살아 있는 세션의 입력도 다른 세션과 맞대 🔁([결과](log/overlap_alert_20261106.md)). **세션 인계 · 세션 조작은 앞당겨 했다**(2026-11-05, [설계](docs/11_handoff.md) · [결과](log/stage11_handoff_result.md) — 세션이 스스로 요약 → 확인 → 새 세션에 주입, 끝내기 · 멈춤 · 되살리기 · 작업 중단. 버리는 세션으로 한 바퀴 확인, 런슈즈는 아직). **포먼 디스패처 1단계**(같은 날, [설계](docs/11_foreman_dispatch.md) · [결과](log/stage11_foreman_dispatch_result.md) — [+ 세션]에서 포먼에게 말하면 `claude -p`가 상황 묶음을 보고 계획(프로젝트 · 방식 new/handoff/attach/ask · 요약 · 역할 · 첫 글) → 사람이 고쳐 시작. 자동 기상 2 · 3단계는 써 본 뒤). **따로 작업(worktree) · 스키마 잠금 · 미리보기 브리지**(같은 날, [설계](docs/11_worktree.md) · [결과](log/stage11_worktree_result.md) — 살아 있는 세션이 있는 프로젝트에 둘째를 띄우면 `.worktrees/<이름>` · `cc/<이름>`, 끝낸 뒤 [합치기], 스키마는 한 세션만, [미리보기 열기]). **세션 재배치 · 역할 통일 · 역할 색**(같은 날, [결과](log/stage11_roles_result.md) — 0017로 포먼에 묶인 세션 38개를 역할 캐릭터 "코더" · "점검"(부모 = 포먼)으로, 터미널 셸은 미분류로. 새 세션은 역할 캐릭터, worktree는 그 자리 일꾼("코더 foreman-2", 합치기 · 버리기 때 퇴장). 테마 역할 이름을 DB와 같게(foreman coder inspector cicd helper) — 전에는 이름이 달라 색이 한 번도 안 맞았다. 점검 역할은 읽기 전용이 기본). **미분류 정리**(0018 — 시험 세션 12개는 지우지 않고 숨김 `hidden_at`, 킥오프 세션 154는 포먼 코더로, 터미널 셸은 미분류에). **교장 계획 바로 시작 · 계획 받기 실패 다루기**(11-10, [결과](log/coder_plan_nowait_fail_20261110.md) · [합침](log/merge_plan_nowait_20261111.md) — 지시서 · 교장 경로 인계 글에서 「확인을 기다려라」 뺌, 실패 원인을 다섯 가지로 갈라 화면 · 기록에, 실패 뒤 [버리기] 고침. 실제 세션 첫 응답은 다음 교장 띄우기 때 확인) |
| 12 | 서기 — 문서화 캐릭터 (Notion MCP) | **먼저 한 것 — 세션 모델 고르기**(2026-11-05, [결과](log/stage12_model_choice_result.md) — [+ 세션] · 포먼 카드에 모델 칸, 역할별 기본값 `config/models.toml`, 패널에 지금 모델 · 모델별 토큰, 방 배지에 Opus 비율 · 머리줄 모델 표시로 `/model` 바꾸기). 📝 **인계 2판 · 압축 알림 설계**(같은 날, [설계](docs/11_handoff_v2.md) — 문서로 옮기기 → 짧은 인계 + 읽을 곳 → 새 세션의 Read 확인, 2번째 압축 직후 알림 + [잃은 것 보기] · [문서로 옮기고 새로 시작]). 📝 **서기 설계**(2026-11-05, [설계](docs/12_scribe.md) — 이름 · 색 · 첫 일감 확정, Notion 부모 페이지 대기) — 떠돌이 포트폴리오 캐릭터 대신 프로젝트마다 서기(`scribe`) 하나. README · docs 맞추기 · 회고 · 포트폴리오 · CLAUDE.md 정리 · 압축 손실 반영 · 인계 요약 다듬기. 사람이 시키고 브리지는 할 일만 센다, worktree [합치기]가 검토 관문, 문장마다 근거 표시를 기계로 확인, 원본은 git · Notion은 게시판. ✅ **12a**(2026-11-06, [결과](log/stage12_scribe_result.md) — 역할 · 화면 · `docs/style_guide.md` · 재료 묶음, 첫 회고 [log/retro_20261105_foreman.md](log/retro_20261105_foreman.md) 합침). **서기실**(같은 날 — 작업 책상 8 → 5 + 필사실 · 문서팀 · 서류실 3자리, 서기 상주 · 누르면 시킬 일 여섯 · 머리 위 "할 일 N"). **12c Notion 게시**(같은 날 — 내부 통합은 FOREMAN 페이지에만 연결해 범위를 Notion 권한이 막음, 변환 · 덮어쓰기 · 옮기기 · 휴지통 실제 확인, 회고 첫 게시). ✅ **12b 근거 확인기 · 고친 양 기록**(11-06, 같은 결과 문서 「12b」). ✅ **12c 포트폴리오 판**(11-06 — `portfolio/` 10편, Notion 루트 아래 번호순 게시, 같은 결과 문서 「12c 포트폴리오」 · [합치기 · 게시](log/portfolio_publish_20261106.md)). **남은 것**: 12b 점검 역할 검토 · 숫자 대조, 12c 작업 기록 DB, 12d 하루 끝 자동 초안([지금 상태](log/stage12_scribe_result.md)) |
| 13 | 시연 사진 · 녹화 — 포트폴리오에 움직이는 화면 | ✅ **완료**(2026-11-06, [설계](docs/13_demo_capture.md) · [결과](log/stage13_demo_capture_result.md)) — 시연 모드(`?demo=`) · `screen.py --record` → GIF, 실제 기록 재생 대본, 포트폴리오 10편에 GIF · 사진, 실제 CI/CD 빌드 녹화. 남은 것: 사진 둘(08 터미널 · 06 Notion 게시 목록)은 넣지 않음, 시연 모드 · 녹화기 자동 시험 없음 |
| 14 | 디스패처 이름 · 노트 · 자동 기상 2단계 · 감독실 캐릭터 | ✅ **완료**(2026-11-08, [설계](docs/14_dispatcher_note_wake.md) · [결과](log/stage14_dispatcher_note_wake_result.md)) — 프로젝트는 FOREMAN · 기능은 디스패처, 노트(0025), 실패 → 계획 → 사람이 [시작]. systemd PATH 때문에 11-06부터 디스패처가 죽어 있던 것을 찾아 고침. 남은 것: 노트가 실제로 쌓이는 것 · 2단계 실제 실패로 돌기 · 3단계 |
| 15 | 사용량 화면 · 한도 역산 | 🔧 **1 끝**(2026-11-08, [설계](docs/15_usage.md) · [결과](log/stage15_usage_result.md)) — `claude -p` 사용량을 `usage_extra`(0026)에. 2~4는 차례로 |

3번을 일찍 치는 이유는 리스크가 가장 크기 때문이다. 막히면 설계를 바꿔야 하므로 늦게 알수록 손해다.

### 나중에 할 일 (정해 두고 미룬 것)

| 무엇 | 언제 · 조건 | 근거 |
|---|---|---|
| 런슈즈 · 펫퍼민트 승인을 관찰(observe) → 차단(enforce)으로 바꿀지 정하기 | 판정 수치가 볼 만큼 쌓이면(11-05 사용자: 아직 아님). 인프라도 묶음 1 동안 observe — 끝나면 enforce로(사용자 확인) | README 3.3, `config/approval.toml`, `log/infra_bundle1_launch_20261110.md` |
| 시험 GitHub Actions(브리지 systemd 유닛은 11-06에 만듦 — 부팅으로 뜨는지는 재부팅 검증 때 확인) | 정해 두고 아직 안 만듦(11-03 결정) | README 3.12, `log/infra_20261106_systemd-bridge.md` |
| 디스패처 자동 기상 3단계(묻지 않고 띄우기) | 2단계를 써 본 뒤(사용자) | `docs/14_dispatcher_note_wake.md` |
| 런슈즈 실제 인계 | 발볼 검증이 끝난 뒤. 맥락이 큰 런슈즈 세션도 지금 작업이 끝나면 사용자가 인계한다(11-08 사용자: "런슈즈는 지금 작업 중이라 나중에. 끝나면 인계할게") | `log/stage11_handoff_result.md`, `log/stage15_usage_result.md` 「6.」 |
| 런슈즈 README 갱신(런슈즈 서기 일감 — 11-06에 "커밋 22개"가 떠 있었다. 11-10 `7cc1f6e` 문서 점검이 README를 고쳤지만 이 갱신까지 됐는지는 확인 안 함). **더할 것(11-10)**: 런슈즈 `README.md` 「다음에 할 일」 줄의 링크 `[overview](docs/overview.md#다음에-할-일)` → `[TODO](docs/TODO.md)`. 지금도 overview를 거쳐 TODO로 가 링크는 안 깨진다. 루트 README는 원본 폴더에서만 고치기로 돼 있어 worktree 코더가 안 건드렸다 — **원본 README를 누가 고치나**(사용자 물음 "근데 원본은 그럼? 누가 고칠 수 있어?")도 같이 정한다 | 포먼 쪽 정리를 먼저 한 뒤(11-06 사용자: "런슈즈 README 갱신은 나중에. 포먼 쪽 먼저 정리하고"). 링크는 "급한 건 아니고 … 나중에 다른 세션 돌 때 같이 시켜도 되고"(11-10 사용자). 런슈즈 저장소 세션의 일 | `log/stage12_scribe_result.md`, t:6507 |
| 펫퍼민트 압축 손실 점검 **결과 보기** — 점검 #2(세션 155)는 11-09에 끝났다(사라짐 93 · 약해짐 38 · 뒤집힘 16 · 살아 있음 42 · 끝남 81, $3.61). 사람이 결과를 보고 펫퍼민트에 되살릴 것을 정한다 | 펫퍼민트를 다시 만질 때(11-09 사용자: "펫퍼민트 손실 결과는 나중에 볼게. 지금 그 프로젝트 안 건드리니까") | `log/cross_paste_20261109.md` 「3.」 |
| 런슈즈 미리보기(vite) | FOREMAN 미리보기가 쓸모 있는지 본 뒤 | `docs/11_worktree.md` |
| Claude Code와 Codex 같이 쓰기 — 일감 떠넘기기(양 많은 반복, Opus 토큰 아끼기) · 다른 모델의 의견(설계 리뷰 · 교차 검증, 같은 모델끼리는 같은 것을 놓친다) | **먼저 같은 일을 Sonnet으로 시켜 비용 · 품질을 본 뒤**, 충분하면 붙이지 않는다(11-06 사용자) | `log/later_codex_bridge.md` |
| 9단계 LLM 지표 | 프로메테우스는 펫퍼민트 설계와 상의 뒤 | 로드맵 9 |
| **Fable 5.2로 해 볼 것**: 픽셀 캐릭터 동작 더하기(책 꺼내 읽기 · 타이핑 · 걸어다니기) · 포트폴리오용 영상이나 다이어그램 | 쌓인 할 일을 줄인 뒤(11-10 사용자: "지금은 하지 않는다. 할 일이 쌓여 있다") | 받은 할 일 #16 |
| **세션이 끝나지 않고 CC 끝내기 확인 창에 걸린 것 알리기** — CC는 뒤에서 도는 일(백그라운드 Bash · Monitor)이 남은 채 끝내려 하면 "Background work is running … 1. Exit and stop tasks / 2. Move to background and exit / 3. Stay" 창을 띄우고 답을 기다린다. 패널에는 "뒤에서 도는 일 1"만 보여 **세션이 그 창에서 멈춰 있다는 것을 모른다**(조용한 고장). 할 것: 그 창이 떠 있음(tmux 화면 · 끝내기 요청 뒤 프로세스가 남음)을 감지해 카드 · 패널에 "끝내기 확인 창 — 뒤에서 도는 일 N이 멈춥니다" + 무엇을 고를지, 오래 걸리면 알림. [끝내기] 전에 뒤에서 도는 일을 보여 주고 멈출지 묻기도 검토. **된 것**: [쉬게 하기]는 뒤에서 도는 일이 있으면 먼저 막고, 안 꺼지면 tmux 화면에서 그 창을 찾아 알린다(`00becd2`) — 새 세션으로 옮기기 ④ · [끝내기]는 아직. **더할 것(받은 할 일 #6 · #7 — 같은 글 두 번)**: ① 뒤에서 도는 일이 끝나면 사람을 기다리지 않고 세션도 끝낸다 ② 옮길 때 뒤에서 도는 일을 새 세션에 넘긴다(11-09 런슈즈 감시 — 앞 세션 것이 멈춰 새 세션이 같은 것을 다시 걸었다). 정할 것: 넘길 수 있는 일 · 못 넘기는 일을 가르는 기준, 넘긴 일을 인계문에 적는 모양, 자동으로 끝낼 때 사람에게 알리는지 | 화면 worktree가 끝난 뒤(11-09 사용자: "할 일에 넣어라") | [기록](log/old_session_exit_bg_20261109.md), `log/coder_resident_20261109.md`, 받은 할 일 #6 · #7 |
| **구조 2단계 — docs 뒤처짐 신호**: "코드 커밋은 있는데 docs 커밋이 없음"을 서기 할 일로 센다(지금 Notion 뒤처짐을 세는 자리에 같이). 1단계(다른 저장소는 읽기만)는 11-09 만듦 | 화면 worktree가 끝나고 문서 세션까지 돈 뒤(11-09 사용자: "지금 셋이 돌고 있어서 더 늘리면 꼬인다") | [기록](log/repo_scope_readonly_20261109.md) |
| **구조 3단계 — 역할 나누기**: 관리자는 docs · README를 고치지 않고 log만. FOREMAN 코드는 worktree 코더, FOREMAN 문서는 FOREMAN 서기. 프로젝트마다 코더와 서기(서기는 띄울 때만 만든다 — 늘 두면 안 쓰는 세션이 쌓인다). CLAUDE.md 작업 규칙 고치기. Bash 샌드박스(작업 폴더 밖 쓰기)는 일상 명령을 막는지 시험한 뒤 | 2단계 뒤(같은 사용자 지시) | 같은 기록 |
| **서기 화면 — Notion 게시가 한 칸에 섞임**: 기술문서 게시와 포트폴리오 게시가 "Notion 게시" 한 칸이라 FOREMAN(portfolio/만) · 펫퍼민트(기술문서만)가 화면에서 구분 안 됨 → 포트폴리오 쓰기 / 기술문서 게시 / 포트폴리오 게시로 나누기 | 구조 3단계와 함께 볼 것(11-09 사용자: "지금 하지 마라") | 같은 기록 |
| **서기 화면 — "문서 할 일"(브리지가 센 것)과 "시킬 일"(늘 떠 있는 메뉴)이 섞여 보임**: 언제 눌러야 할지 몰라 거의 안 눌렀다. 핵심인 문서 점검이 메뉴에 묻힘 → 자동으로 떠야 한다. docs를 커밋마다 고치면 일이 끊기니 **묶는 기준**(커밋 몇 개 · 쉼 · 하루 끝 등)도 정하기. **[시키기] 메뉴 점검(받은 할 일 #15 — 이 줄과 같이 고친다)**: ① 물어보기로 찾은 것(11-10 서기가 "docs에 안 들어간 것 둘"을 찾았는데 시킬 버튼이 없었다)을 바로 시키기 ② 「문서 점검」은 찾기만 하고 고치지 않는다 → 그 결과로 바로 고치기 ③ 포트폴리오 쓰기에 갱신 버튼("10/10 썼다"고만 나온다 — 위 Notion 게시 줄과 겹침) ④ 메뉴 다섯 개가 실제로 쓸모 있는지 다시 보고 안 쓰는 것은 빼기 | 같은 때(2단계 신호와 묶어서) | 같은 기록, 받은 할 일 #15 |
| **서기와 대화 — 이어 묻기**: **된 것**: 물어보기(세션 없이 읽기 전용 `claude -p` 한 번, `/api/scribe/ask`, 11-10 `22e1828`). 남은 것: 한 번 묻고 끝나 이어 묻지 못한다 — 서기가 무엇을 어떻게 하는지 알려고 관리자를 거치는 구조가 맞는지 생각하기. 찾은 것을 시키기로 잇는 것은 위 줄(#15) | 같은 때 | 같은 기록, [물어보기 기록](log/scribe_ask_20261110.md) |
| **later.md가 낱말로만 고른다 — 낱말 없이 미룬 말은 안 들어온다**: 「나중에 할 일 정리」 재료(`later.md`)는 「나중 · 미루」 낱말이 든 턴만 고른다(`bridge/scribe_room.py` `later_prompts`). 「지금은 말고」 「그건 두자」 「~뒤에」처럼 낱말 없이 미룬 말은 처음부터 빠진다. 뜻으로 고르게 하거나, 이 재료를 쓰지 않고 회고 재료 8절(사람 말 전체)을 읽기로 정한다. **된 것**: 재료가 사람 말을 자르던 것(받은 할 일 #14) — 회고 8절 · later.md 모두 자르지 않음, 1500자마다 줄만 나눔, 상한 없음(`2831c8f`, 11-10 합침 — `materials.md` 39만 자에 t:6360 · t:6383 통째로 확인) | 서기 화면 줄들과 함께, 또는 따로 작게(코더). 그때까지 서기는 8절을 읽는다 | [기록](log/scribe_material_noclip_20261110.md) 「설계와 달랐던 점」, [합침](log/merge_scribe_noclip_20261110.md), 받은 할 일 #14 |
| **계획 「다시 받기」가 앞 계획을 끊지 않는다**(받은 할 일 #18, 11-10): 누르면 앞서 돌던 계획이 안 죽고 둘이 같이 돌아 남은 시간이 40초 ↔ 11초로 번갈아 뜨고, 결과도 둘이 와서 섞일 수 있다. 할 것: 다시 받기 때 앞 계획(`claude -p`)을 끊고 새로 받는다 | 교장 ① ~ ④ 줄과 같은 때, 또는 따로 작게(코더) | 받은 할 일 #18 |
| **밖에서 git merge로 합치면 「합치기 기다림」으로 남는다**(받은 할 일 #17, 11-10): 합치기 API가 거부해 `git merge --ff-only`로 직접 합치면 FOREMAN이 몰라 코더 캐릭터에 "맡은 일 1 — 합치기 기다림"이 계속 뜬다. 할 것: 브랜치가 main에 이미 들어간 것을 알아채 지우거나, [쉬게 하기]에서 건너뛸 수 있게 | 따로 작게(코더) | 받은 할 일 #17, 사용자가 말한 UI 불만 셋 (다), `log/coder_resident_20261109.md` |
| **패널이 낮은 창 · 큰 글씨에서 대화 칸 30px**: 1366 · 125%와 1024에서 띠 둘(쌓인 대화 · 같은 파일)과 머리줄 두 줄(▶ 버튼이 줄을 넘김)이 패널을 먹어 대화 칸이 30px다(main도 같다). 1024 × 700 · 150%는 머리말만 창의 62%를 먹는다(`layoutAudit` 25). 할 것: 띠를 한 줄로 합치기 · 머리줄 버튼 줄이기 · 머리말 접기. 11-10 화면 묶음(질문 카드 접기 · 카드 자리 · 터미널 겹침 · 프로젝트 터미널 · 캐릭터 아래 글 · 「서기」 이름표 — 재현 안 됨)은 끝났다 | 따로 볼 때 | [기록](log/designer_screen_six_20261110.md) 「남은 것」 |
| **"답 기다림"이 답할 필요 없는 끝맺음까지 잡는다**(받은 할 일 #13, 11-10): 펫퍼민트가 "시작하라는 말씀을 기다리겠습니다"로 끝나 답 기다림이 됐다 — 다음에 할 일을 말한 것이지 지금 답을 요구한 게 아닌데 칩 · 배너가 계속 떠 거슬린다. 지금 판정은 응답 끝 600자의 문장 끝 모양만 본다(`?` · "~까요" · "말씀해/확인해 … 주세요" 등, `log/screen_mismatch_waits_20261109.md` 「3.」). 할 것: ① "지금 막혀서 답이 필요한 것"과 "다음에 뭘 할지 물은 것"을 나눌 수 있는지 보기 ② 못 나누면 사람이 그 세션의 답 기다림을 끌 수 있게("이건 답 안 해도 됩니다" — 다음 응답이 오면 다시 판정). 11-10 더: 묻는 말이 전혀 없는 보고(관리자 합치기 결과)에도 답 기다림이 떠 있었다 — 앞 응답에서 켜진 것이 새 응답이 와도 꺼지지 않는 것으로 보인다. 판정이 과한 것과 별개로, 새 응답마다 다시 판정해 꺼지는지 확인할 것 | 따로 볼 때 | 받은 할 일 #13, `log/screen_mismatch_waits_20261109.md` |
| **스키마 잠금 단위 — 원본 폴더 세션이 끝나야 풀린다**(받은 할 일 #4 — 11-09 메인이 쥔 잠금에 코더 세션 233이 0028을 못 쓰고 멈췄다). **된 것**(`00becd2`): 방 배너 · [풀기] · 막힘 텔레그램 한 번 · 원본 폴더 세션이 쥔 FOREMAN 잠금은 마이그레이션 적용 · 커밋이 끝나면 1분 안에 일찍 풂 · 잠금 명령은 마이그레이션을 돌리는 것만. **남은 것**: 잠금이 왜 세션 단위인지, 다른 단위(마이그레이션 하나 · 적용 · 커밋까지)로 할 수 있는지 보기. worktree 세션이 쥔 것은 합치기 전까지 그대로이고, 런슈즈(flyway)는 일찍 풀기가 안 된다(적용 기록이 다른 DB) | 따로 볼 때 | `log/coder_resident_20261109.md`, 받은 할 일 #4 |
| **할 일 목록에서 바로 일을 시작**: 지금은 받은 할 일을 서기가 README로 옮기면 끝이고, 고르고 세션 띄우기는 사람이 매번 한다(코더 "맡길 일" → [계획으로]는 하나씩만 — `00becd2`). 원하는 것: 목록을 보면서 바로 고치기 · 지우기, 몇 개를 골라 "이거 해라" 하면 교장이 묶어 계획을 세움, 겹치는 것 · 이미 된 것은 정리하며 걸러짐. 누가 맡을지(서기 · 교장)는 만드는 세션이 정한다(사용자: "누가 하는 게 맞는지는 네가 정해라"). 교장 ①(한 번에 여러 세션 계획)과 이어진다 | 교장 ① 뒤 | 받은 할 일 #8, [기록](log/dispatch_flow_decision_20261109.md) |
| **런슈즈 Jenkinsfile `core.quotePath` 버그 가능** — 한글 경로가 따옴표로 감싸져 문서만 건너뛰기의 `^docs/`에 안 걸린다(지금 런슈즈엔 한글 이름 파일 0, 생기면 문서만 커밋도 빌드). 런슈즈 세션에 `git -c core.quotePath=false diff`로 고치게 한다. 펫퍼민트 문서만 건너뛰기는 11-09 끝(`16727bc`, 확인 `5af21d5` → #57 건너뜀 · 배포 대기 없음) | 사용자가 시킬 때. 런슈즈 저장소 세션의 일 | [기록 · 보낼 글](log/petmint_jenkins_docskip_todo_20261109.md) |
| **교장 ① 한 번에 여러 세션 계획** — 오늘 "둘 띄워줘"가 하나만 됐다(dispatch 132 · 133 → 세션 231만). 한 계획에 담아야 파일 나누기 · 합칠 순서 · 겹침을 한 장에서 정한다. **교장 ②~④보다 먼저**(어느 쪽으로 가든 필요) | 사용자가 시킬 때(11-09 사용자: "교장을 키우는 쪽으로 간다 … 지금 고치지 마라") | [기록](log/dispatch_flow_decision_20261109.md) |
| **교장 ② 읽기 전용 확인 도구** — git log/status, 상태 API, 승인 대기 수. 쓰기는 막는다(다른 저장소 막음 `bridge/reposcope.py`와 같은 방식). 지금 못 보는 것: 프로세스 · tmux 화면, worktree 브랜치 · 커밋 안 한 변경, 브리지를 언제 다시 띄웠는지, 시험 결과 | ① 뒤 | 같은 기록 |
| **교장 ③ 발견을 경고 · 질문 칸에** — 오늘 "알림 셋은 이미 있다"를 교장도 알았지만 이유 칸에 있어(`warnings` · `questions` 빔) 계획 카드에서 안 보였다 | ① 뒤 | 같은 기록 |
| **교장 ④ 모든 띄우기가 계획 기록(dispatch)을 남김** — 오늘 둘째 세션(232)은 관리자가 `POST /api/spawn`으로 직접 띄워 기록이 없다. 관리자가 띄우더라도 같은 경로로. 관리자는 상주로 두지 않고 필요할 때만(11-09 결정) | ① 뒤 | 같은 기록 |
| **들어오는 일을 종류대로 — 세션 띄우기 → 교장에게 바로 말 걸기**: 간단한 기준 안(세션 하나 · 경고 · 질문 없음 · 확신도 높음 · 새로/붙이기)이면 계획 카드 없이 바로 띄우고 "띄웠습니다 · [멈추기]" 띠, 넘으면 지금처럼 카드. 모든 띄우기는 dispatch 기록(교장 ④) | 할 일 받는 칸 뒤(11-09 사용자) | [기록](log/dispatch_flow_decision_20261109.md) |
| **질문 · 분석 → 그때 띄우는 읽기 전용 점검 세션** — 답하고 끝나 맥락이 쌓이지 않는다. 같은 주제를 이어 물을 때만 그 세션을 이어 쓴다 | 같은 때 | 같은 기록 |
| **운영(합치기 뒤 절차) → 브리지** — 시험 → push → 승인 대기 0 → 브리지 다시 띄우기 → 합친 뒤 확인 목록(API 키 · screen.py 점검). 오늘 메인이 손으로 한 일. 11-10 사용자: "그게 되면 관리자 일 대부분이 세션 없이 된다 — 프로젝트별 관리자보다 이게 먼저일 수도 있다"(t:6391, 의견만 물음) | 같은 때 — 아래 프로젝트별 관리자 줄과 순서를 정할 것 | 같은 기록, `log/merge_foreman2_check_20261109.md`, t:6391 |
| **기술문서 게시 상태 읽기 API + 화면**: 서기 패널 "Notion 게시" 목록은 `portfolio/`만이라 docs가 Notion에 제대로 갔는지 볼 데가 없다(11-10 런슈즈 docs 16개를 고친 뒤 확인할 곳이 없었다). API(코더 먼저): `status()` · 마지막 게시 결과 · push 대기 커밋 수. 화면(디자이너): 프로젝트 방 패널의 「기술문서 게시」 목록. 위 「서기 화면 — Notion 게시가 한 칸에 섞임」과 같이 볼 것 | 251(화면 묶음) 끝난 뒤(11-10 사용자 — 251은 합쳐졌다, 아직 시작 안 함) | t:6389 · t:6391 |
| **프로젝트별 관리자**: 런슈즈 문서가 Notion에 갔는지를 FOREMAN 방에 가서 묻는 건 이상하다 — 그 방에서 그 프로젝트 일이 끝나야 한다. 순서: **토큰 범위 묶기**(지금 토큰 하나로 모든 API가 열려, 런슈즈 세션에 주면 FOREMAN 방도 띄우고 끝낼 수 있다) → 관리자 역할 → 그 저장소 CLAUDE.md 규칙. 상주는 시키지 않는다 | 토큰 범위를 먼저 묶은 뒤(11-10 사용자: "지금 바꾸지 마라") | t:6389 · t:6391 |
| **겹침 감지 "같은 파일" 헛경보 — 이미 커밋돼 상대 바탕에 든 변경도 센다**: 11-09 첫 실제 알림(19:57 ~ 20:09, 세션 230 ~ 233, scribe.py · main.py · approvals.py 등 8개)이 헛경보였다 — 230이 고친 것은 커밋(`3ec3294` · `5e2692a`)돼 233의 바탕(`5e2692a`)에 이미 들어 있었다. 고칠 것: A가 고친 파일 중 **커밋돼 B의 바탕(merge-base)에 든 것은 빼고**, 커밋 안 한 변경 · B 바탕 뒤 커밋끼리만 맞댄다(`bridge/overlap.py`). 같은 묶음이 3분마다 다시 로그에 찍히는 것도 본다. 함께 정한 것(11-09 사용자, t:6260): 꺼 둔 낱말 겹침 텔레그램은 "놓쳐서 문제가 생기면 그때 되돌리자", README.md 같은 파일 헛경보는 "실제로 나면 그때 빼고 어떤 파일이었는지 기록" — 지금 빼면 진짜 겹침도 놓친다 | 따로 볼 때 | [기록](log/overlap_false_same_file_20261109.md), t:6260 |
| **상주 세션과 임시 일꾼이 화면에서 안 갈린다**: 관리자 · 코더 상주 세션과 둘째부터 뜨는 임시 일꾼이 화면에서 구별되지 않는다(임시 일꾼은 반투명 · "임시" 점선 이름표로 정했지만 — `00becd2` — 사용자 불만으로 남음) | 정하지 않음 | 사용자가 말한 UI 불만 셋 (가) — [기록](log/scribe_material_noclip_20261110.md) 「다음 세션에 넘길 것」 |
| **끝난 세션의 옛 보고가 새 것처럼 올라온다** | 정하지 않음 | 같은 불만 셋 (나) — 같은 기록 |
| **다른 프로젝트 포트폴리오**: 런슈즈 포트폴리오와 그 Notion 페이지는 런슈즈 서기에게 따로 시킨다(11-06 · 11-09 — 기술 문서 자동 연결만 먼저 함), 펫퍼민트 포트폴리오는 "나중에 한꺼번에" | 사용자가 시킬 때 | t:5941 · t:6084 · t:6256 |
| **GitHub 저장소(`Gabriel-Joo/foreman`) 공개로 돌리기** | 에셋 라이선스와 토큰 흔적을 확인한 뒤(11-06 사용자: "지금은 안 할래") | t:5890 |
| **일어날 때 확인할 것**(일부러 재현하지 않음): ① 적재가 막혔을 때 알림이 실제로 가는지 — "다음에 막힐 때 확인하자. 일부러 DB 건드리진 말고"(11-03) ② 펫퍼민트 Notion `heading_4`가 실제로 만들어지는지 — 다음에 `####`가 든 문서를 push할 때(11-09) | 그 일이 생길 때 | t:5618, t:6243 |
| **`pgrep -f`가 자기 셸에 걸리는 함정 막기**: CC는 Bash 명령 전체를 `bash -c '…'`로 돌려 그 셸 명령 글에 패턴이 들어 있다 → `pgrep -f "<패턴>"`이 자기 자신에 걸린다. 11-09 메인은 "다른 pytest 있음"을 세 번 헛보고, 코더 세션 233은 `until ! pgrep -f "tools/screen.py"` 셸이 영원히 안 끝나 합치기 직전에 걸렸다(끝내기 확인 창 위험). 고칠 것(권장 순): ① PreToolUse에서 Bash 명령에 `pgrep -f`/`pkill -f`가 있고 그 패턴이 대괄호 트릭(`[p]ython`)이 아니면 **거부 + 까닭과 고친 예**(11-10 메인: 대괄호 트릭도 **같은 명령 안에서 그 프로그램을 돌리면** 뒤쪽 글자에 또 걸렸다 — 판정은 "패턴이 같은 명령 글 다른 곳에 나오는가"로, 고친 예는 "확인과 실행을 따로"까지; 승인 모드와 상관없이 — 스키마 잠금 · 다른 저장소 막음과 같은 자리, `bridge/approvals.py`) ② CLAUDE.md 작업 규칙 한 줄 ③ 서기 · 코더 지시문 공통 줄(`bridge/scribe_room.py` COMMON 등). 메인 기억에는 넣었다 | 따로 볼 때(11-09 사용자: "같은 함정에 두 번 빠졌으니 고칠 만하다") | `log/merge_coder_resident_20261109.md` 「합치기 전」 |
| **웹훅이 한 번 빠져 폴링으로 돈 빌드를 표시 없이 넘김**: 11-09 펫퍼민트 `5af21d5` push(20:18)의 GitHub 웹훅이 Jenkins에 오지 않아 #57이 15분 뒤 폴링(cause `poll`)으로 돌았는데 FOREMAN은 `webhook_broken: false`, 화면 표시 없음. 고칠 것: push 뒤 빌드가 `poll`로 시작하면 "웹훅이 오지 않아 폴링으로 돌았습니다(N분 늦음)"를 빌드 호버 · 파이프라인 줄에, 같은 저장소에서 이어지면 지금 끊김 판정으로. GitHub 웹훅 전달 기록은 이 PC에 gh가 없어 못 봄. **같이 볼 것(받은 할 일 #10)**: "push했는데 빌드 없음" 장치(`no_build`)가 이번에 작동했는가 — 작동했으면 알림이 왔어야 하고, 안 왔으면 왜인지(폴링 빌드가 판정 전에 들어왔는지 등). 웹훅이 가끔 빠지는지 이번만인지(Jenkins 웹훅 수신 기록을 거슬러 센다). 폴링 15분 사이는 빈다 | 따로 볼 때 | `log/petmint_jenkins_docskip_todo_20261109.md` 「실제 확인」, 받은 할 일 #10 |
| **"API 오류"만 뜨고 까닭이 안 보인다 · 브리지 로그에도 안 남는다**(11-10 사용자): 서기 세션 245(sonnet)의 응답이 모델 안전 분류기에 두 번 막혔다(09:34 · 09:46, `[reasoning_extraction]`, `req_011CgtKkMaLMkhEyDRTbEGka`). CC 화면에는 "Sonnet 5.5's safeguards flagged this message … try a different model with /model"이 떴지만, 패널에는 끝 이유 `stop_failure` "API 오류"만 보였다(`render.js` `END_LABEL`). 브리지 journal에는 245 요청 200 · 202뿐이었다 — 관리자가 tmux 화면과 대화 기록을 열어 보고서야 알았다(조용한 고장). 할 것: 적재기가 `isApiErrorMessage` 글(`assembler.py`)에서 오류 종류(분류기 거부 · 한도 · 과부하 등)와 request id를 받아 패널 · 호버에 까닭과 할 일("/model로 바꾸기" 등)을 보이고, 브리지 로그에 WARNING 한 줄(세션 · 종류 · request id)을 남긴다. 같은 세션에서 거부가 이어지면 알림. 짐작한 원인(한국어 훅이 모델 글을 따옴표로 되돌림)은 11-10에 고침(`2d3bb1d`) | 따로 볼 때 | 이 줄, `log/korean_hook_sonnet_check_20261110.md` |
| **[⌂] 감독실 현황판의 「FOREMAN」이 끊긴다** — 글씨 110% · 1024 · 패널 넓게에서 세 테마 각 1건. 감독실은 모눈 밖이라 11-10 모눈 작업에서 고치지 않았다. 모눈 전 main에서도 같다. 11-10 인프라 방으로 판이 다섯 칸이 되자 1024 넓게에서도 끊겨, 한 낱말 이름을 8px까지 줄이게 했다(끊김 0, 다만 작다 — 현장이 더 늘면 판 두 줄 등 디자이너 몫). 1024 넓게 · 110% [전체]에서 현장 카드 겹침 4건도 같이 난다. 화면 폭 464px이 그대로라 11-11 화면 다듬기 전후가 같다 | 따로 볼 때(11-10 사용자) | [기록](log/designer_grid_20261110.md), `log/coder_infra_project_20261110.md` 「남은 것」, [화면 다듬기](log/designer_polish_seven_20261111.md) |
| **캐릭터가 한 칸으로 작아져 역할 색이 잘 안 보인다** — 1366 · 패널 넓게(한 칸 24px)부터 안전모 · 끈 · 로브 색이 작다(11-10 모눈 작업에서 2/3로 줄임). 세션 번호는 호버 · 패널에 있어 그대로 | 따로 볼 때(같은 사용자 지시) | 같은 기록 「합친 뒤 관리자가 할 일 · 볼 것」 |
| 서버 재부팅 검증 → `-old` 컨테이너 3개(`milvus-standalone-old` · `openwebui-old` · `mysql-old`)와 백업 정리 | 사용자가 재부팅을 시킬 때(복구할 시간이 있을 때). 정리도 사용자가 시킬 때 | `log/infra_20261102_host-changes.md` 「남겨 둔 것 (되돌리기용) — 재부팅 검증 뒤 정리」 |
| `cleanupPeriodDays`(지금 120일)와 `event` 보관 기간을 함께 다시 정하기 — 기간이 지나면 요약만 남기고 원본을 지운다 | 브리지 적재가 안정되면(11-02 사용자). 보관 정리 코드는 아직 없다 | README 5장 「보관 정책」 |
| Jenkins 실패 상세(스테이지별 로그)를 읽는 보정 — matrix-auth로 진짜 읽기 전용 토큰을 만들어 더하기 | 실패 상세가 필요해지면(11-03 사용자: "지금은 안 만들어"). 플러그인 · JCasC는 인프라 저장소 세션의 일 | `log/stage8_cicd_result.md` |
| Jenkins 차트 init의 `yes n \| cp -i …`(`set -e`)가 같은 파드 재기동 때 실패하는 것 막기 — values에서 init 스크립트를 덮어 `\|\| true`, 또는 `plugin-dir`를 비우게, 또는 고친 차트 버전으로. **정전 · 노드 재부팅마다 반복된다**(그때마다 `kubectl delete pod -n jenkins jenkins-0`로 되살림) | 따로 볼 때(11-06 사용자: 급하지 않음). ronanlab-infra 저장소 세션의 일 | `log/infra_20261106_jenkins-harbor-after-outage.md` |
| 클러스터 파드 감시 — 인프라 웹(Jenkins `/login` 등)은 살아 있는데 **다른 파드가 죽은 것**(11-06 harbor-jobservice CrashLoopBackOff — 이번엔 저절로 풀림)을 알리기. 지금 생존 폴링은 ingress로 웹 주소만 본다. **먼저 호스트에서 클러스터를 조회하는 길이 필요하다** — 호스트에 kubectl이 없고(`vagrant ssh m-k8s`만) 브리지는 그걸 부를 수 없다. 후보: 읽기 전용 ServiceAccount 토큰 + API 서버 직접 조회(토큰 무게를 따질 것 — 웹훅 토큰 · Jenkins 토큰 때처럼) | 따로 볼 때(11-06 사용자) | `log/infra_20261106_jenkins-harbor-after-outage.md` 「판단 · 한계」 |
| FOREMAN 외부 노출(터널) 다시 열기 | 필요해지면 — 열 때는 읽기 전용 + 강한 인증(패스키 · mTLS)으로(11-03 결정) | README 3.13, `docs/02_cloudflare_tunnel.md` |
| **역할 규칙을 글이 아니라 권한으로 막기**: 「worktree는 커밋만 · push는 관리자」가 CLAUDE.md 글로만 있어, 세션이 안 읽거나 사람이 잘못 보내면 깨진다(11-10에 worktree 코더에게 push 지시서가 갔다). 할 것: 역할(관리자 · 코더 · 서기 · 디자이너)마다 allow/deny 도구 목록을 두고 세션을 띄울 때 함께 넘기는 쪽을 보기. 참고: Orchestra는 역할별 권한 프로파일을 JSON으로 두고 `--permission-mode dontAsk`로 돌린다 | 따로 작게(코더). 지금 하지 않음 | 11-10 바깥 도구 참고(Claude Orchestra) |
| **세션이 살아 있는지 · 멈췄는지 알기**: 지금은 `pgrep -f` 함정(위 줄)이 있고, 세션이 멈춰도 모른다(조용한 고장). 할 것: 심장박동을 주기로 받아 끊기면 알리고, 같은 자리에서 오래 도는 것(삽질)도 재는 쪽을 보기. 참고: Orchestra는 heartbeat 폴링 · stall 점수 · rabbit-hole 감지를 둔다 | 따로 작게(코더). 지금 하지 않음 | 11-10 바깥 도구 참고(Claude Orchestra) |
| **끝난 뒤 어긋난 것 훑기(reconcile)**: 합치고 끝낸 뒤 고아 worktree · 커밋 안 된 변경 · 「합치기 기다림」처럼 실제와 다른 상태가 남는다(위 받은 할 일 #17과 같은 뿌리 — 11-10에 262 작업 폴더와 257 합치기 기다림을 사람이 손으로 정리했다). 할 것: 세션이 끝날 때 한 번 훑어 실제와 다른 것을 알리기 | 따로 작게(코더). 지금 하지 않음 | 11-10 바깥 도구 참고(Claude Orchestra) |
| **합치기를 순서대로**: 어느 브랜치를 먼저 합칠지 사람이 머리로 정한다(11-10에 README가 두 브랜치에 있어 순서를 바꿨다). 할 것: 브랜치 사이 의존을 보고 순서를 정하거나, 적어도 같은 파일을 건드리는 브랜치를 합치기 전에 미리 알리기 | 따로 작게(코더). 지금 하지 않음 | 11-10 바깥 도구 참고(Claude Orchestra) |
| **같은 파일을 두 세션이 건드리는 것 미리 막기**: 11-10에 서기 둘이 README를 각자 고쳐 합칠 때 겹칠 뻔했다. 지금 겹침 감지(위 「같은 파일」 헛경보 줄)는 고친 뒤에야 센다. 할 것: 어느 세션이 어느 파일을 맡았는지 적어 두고, 겹치면 세션을 띄울 때 알리기(교장 ① 「파일 나누기」와 이어짐) | 따로 작게(코더). 지금 하지 않음 | 11-10 바깥 도구 참고(Claude Orchestra) |
| **터미널 화면에 스크롤이 없다**(받은 할 일 #19, 11-11): 긴 출력을 내면 앞부분을 볼 수 없다 — 11-11에 README를 `cat`으로 열다 확인했다. 할 것: tmux 복사 모드로 들어가는 길(단추 · 휠)을 붙이거나 화면에 스크롤을 붙이는 쪽을 보기. 탭 그룹 세션 · [새 셸](`log/foreman_term_office_three_20261110.md`)과 맞물리는지 같이 본다 | 따로 볼 때 | 받은 할 일 #19 |
| **인프라 Notion 기술문서 자동 게시 켜기**: 11-10 인프라 프로젝트 등록 때 `config/notion.toml` `[ronanlab-infra]`는 칸만 만들었다(`root = ""` · `docs = "off"` — 그때 인프라 저장소에 `docs/`가 없었다). 지금은 `docs/`가 있다(01_cluster · 02_availability · TODO · runbooks, 11-11 확인). 할 것: root 페이지(사람이 쓴 「인프라」 페이지를 쓸지, 새 프로젝트 페이지를 만들지)를 사용자에게 묻고 `docs = "auto"`, 브리지 다시 띄우기 | 사용자가 root 페이지를 정할 때(설정 값이라 묻고 바꾼다) | `log/coder_infra_project_20261110.md` 「남은 것」 |

---

## 7. 데모 시나리오

프로메테우스는 아직 설치하지 않았다. **수동으로 설치하지 말고 아껴둔다.** 이 시스템의 첫 실사용 사례가 된다.

```
현재        런슈즈에 Jenkins · Harbor · ArgoCD 캐릭터가 서 있다
  ↓ 포먼에게 "프로메테우스 붙여줘"
포먼 기상 → 상황 파악 → 코더 생성
코더      → worktree 생성 → manifest 작성 → 커밋
  ↓ 파이프라인 통과
배포 완료 → 엔드포인트 감지
  ↓
프로메테우스 캐릭터 등장 (세션 없이, 서 있는 상태로)
  ↓ 이후 LLM 지표가 이 캐릭터를 통해 공급된다
```

말로 지시했더니 캐릭터가 생기고 인프라가 실제로 설치되는 과정. 연출이 아니라 실제로 일어나는 일이다.

---

## 문서

브리프 번호는 작성 순서이며 실행 순서가 아니다. 실행 결과는 `log/NN_<이름>_result.md`로 남긴다.
결과 파일에는 실제로 한 일, 조사 결과, 설계와 달랐던 점, 판단 근거만 적고 브리프 내용은 재서술하지 않는다.

**기준 문서**(브리프가 아니라 늘 맞춰 두는 것)
- [operations](docs/operations.md) — 경로 · 저장소 구조 · 돌리기 명령 · CLAUDE.md 규칙의 상세(11-06 서기가 CLAUDE.md를 정리하며 옮김 — `log/trim_20261106.md`)
- [style_guide](docs/style_guide.md) — 문서 종류 · 이름 · 구성 · 문체 · 근거 표시(12a, 서기와 모든 세션 공통)

| # | 브리프 | 내용 | 실행 시점 |
|---|---|---|---|
| 01 | [kickoff](docs/01_kickoff.md) | 설계 검토: README 파악, 환경 조사, 설계 리스크, 기존 구현 조사, 단계 0 계획 | 지금 — 1~3 끝(3은 범위 축소, [결과](log/01_kickoff_result.md)), 4 남음, 5(로드맵 0단계 tmux 이전)는 11-08 끝 |
| 02 | [cloudflare tunnel](docs/02_cloudflare_tunnel.md) | 외부 노출: foreman.ronanlab.dev 터널 + Access 사람 인증, 브리지 자체 토큰 | ⏸ **보류 — 필요해지면**(2026-11-03 결정, 근거 3.13). 다시 열면 읽기 전용 + 패스키 · mTLS로 고쳐서 |
| 10 | [office_design](docs/10_office_design.md) | 픽셀 오피스의 이상적인 그림(사용자 구상) — 에셋 조사 뒤 「실제로 가능한 범위」로 깎음 | 로드맵 10, [결과](log/stage10_office_result.md) |
| 11 | [handoff](docs/11_handoff.md) | 세션 인계 1판 · 세션 조작(끝내기 · 멈춤 · 되살리기) | ✅ 11-05, [결과](log/stage11_handoff_result.md) |
| 11 | [foreman_dispatch](docs/11_foreman_dispatch.md) | 디스패처 1단계 — 사람은 "뭘 하려는지"만, 디스패처가 프로젝트 · 방식 · 역할을 계획 | ✅ 11-05, [결과](log/stage11_foreman_dispatch_result.md) |
| 11 | [worktree](docs/11_worktree.md) | 세션마다 따로 작업(worktree) · 스키마 잠금 · 미리보기 브리지 | ✅ 11-05, [결과](log/stage11_worktree_result.md) |
| 11 | [handoff_v2](docs/11_handoff_v2.md) | 인계 2판 — 문서로 옮기고 읽을 곳을 넘긴다 · 압축 알림 · 인계 검증 | a ~ d, [결과](log/handoff_v2_result.md) · [d](log/handoff_v2_d_result.md) · [검증](log/handoff_verify_20261106.md) |
| 12 | [scribe](docs/12_scribe.md) | 서기 — 프로젝트마다 문서 담당, 근거 표시 · Notion 게시 · 포트폴리오 | 일부, [지금 상태](log/stage12_scribe_result.md) |
| 13 | [demo_capture](docs/13_demo_capture.md) | 시연 사진 · 녹화 — 시연 모드 · GIF 녹화기 · 실제 기록 재생 | ✅ 11-06, [결과](log/stage13_demo_capture_result.md) |
| 14 | [dispatcher_note_wake](docs/14_dispatcher_note_wake.md) | 감독실 캐릭터 · 디스패처 노트 · 자동 기상 2단계 | ✅ 11-08, [결과](log/stage14_dispatcher_note_wake_result.md) |
| 15 | [usage](docs/15_usage.md) | 사용량 화면 · 한도 역산(하한) | 1만 끝(11-08), [결과](log/stage15_usage_result.md) |

### 기록 (`log/`)

| 파일 | 내용 |
|---|---|
| [01_kickoff_result.md](log/01_kickoff_result.md) | 브리프 01 실행 결과 |
| [later_codex_bridge.md](log/later_codex_bridge.md) | **나중에 할 일** — Claude Code와 Codex 같이 쓰기: 후보 5개 조사, `codex mcp-server`는 0.154에서 제거돼 `codex exec -s read-only` + `/etc/codex/requirements.toml` 잠금으로 방향 수정, 설치는 나중 |
| [infra_20261102_host-changes.md](log/infra_20261102_host-changes.md) | 11-02 서버 PC 변경(포트 노출 닫기, milvus 외부 etcd, search-service 유닛, VM 자동 시작), 되돌리기용 자원, 작업 시 주의 |
| [infra_20261102_milvus-port-forward.md](log/infra_20261102_milvus-port-forward.md) | 567,740회 재시작하던 유닛 정지 — 호스트 서비스 감시(2.2)의 근거 |
| [stage1_bridge_db_result.md](log/stage1_bridge_db_result.md) | 로드맵 1단계(브리지 · 스키마 · MySQL · WebSocket) 결과 — 설계 확인 5가지, 시험에서 찾은 것(cryptography), 남은 것 |
| [stage2_transcript_result.md](log/stage2_transcript_result.md) | 로드맵 2단계(와처 · 조립 · 턴 판정 · hook 수신) 결과 — promptId 실측, 백필 · 다시 읽기 · 실시간 · hook 검증, 시험에서 찾은 것 |
| [stage3_inject_result.md](log/stage3_inject_result.md) | hook 설치(실행 중 세션도 다시 읽음 — 실측) + 로드맵 3단계(입력 주입) 결과 — 방법 C 실측표, 첫 글자 · 제출 확인 · 대기열, 거부 경로 |
| [stage4_notify_result.md](log/stage4_notify_result.md) | 로드맵 4단계(텔레그램 브리지 이관 + 연결 끊김 표시) 결과 — 규칙 · 묶음, 실세션 검증, 서브에이전트 결과 전달 판별, 옛 경로 정리 |
| [stage5_approval_result.md](log/stage5_approval_result.md) | 로드맵 5단계(승인 정책 엔진) 결과 — auto mode 실측(hook 판정 · 승인 창 · 터미널과 경주), 과거 데이터 모의 실험, 규칙 조정 |
| [stage6_dashboard_result.md](log/stage6_dashboard_result.md) | 승인 규칙 좁히기(되돌릴 수 없는 것만, 실행과 글자) + 로드맵 6단계(대시보드) 결과 |
| [stage7_terminal_result.md](log/stage7_terminal_result.md) | 로드맵 7단계(터미널 패널) 결과 — ttyd를 UNIX 소켓에, 쿠키 · Origin, 기록 · 마스킹, 부탁 감지 · 미리 채우기 · 결과 전달 |
| [stage8_cicd_result.md](log/stage8_cicd_result.md) | 로드맵 8단계(CI/CD 인과 체인) 결과 — GitLab 없음 · 로컬 git 커밋 귀속, 웹훅 전용 포트, 보내는 쪽 설정(사람 실행), 승인 규칙 "실행과 글자" 넓히기 |
| [handoff_v2_result.md](log/handoff_v2_result.md) | 인계 2판 · 압축 알림 결과 — 단계 a(압축 알림) ~ d를 이어 씀 |
| [handoff_v2_d_result.md](log/handoff_v2_d_result.md) | 인계 2판 d [잃은 것 보기] 1부 — 추출 · 판정 · 손 점검 142항목과 맞대기 |
| [foreman_compaction_loss_20261105.md](log/foreman_compaction_loss_20261105.md) | FOREMAN 세션 압축 손실 점검(auto-compact 7번) — 잃은 것 63 ~ 64% |
| [runshoes_compaction_loss_20261105.md](log/runshoes_compaction_loss_20261105.md) | 런슈즈 세션 압축 손실 점검(auto-compact 17번, 730MB) — 282항목 |
| [runshoes_claude_md_draft_20261105.md](log/runshoes_claude_md_draft_20261105.md) | 런슈즈 CLAUDE.md 초안 — 위 점검에서 사라지거나 약해진 금지 · 결정만 |
| [infra_20261106_systemd-bridge.md](log/infra_20261106_systemd-bridge.md) | 11-06 서버 정전 뒤 복구 · 브리지 systemd 사용자 유닛 · linger(재부팅 검증 전) |
| [stage10_background_waiting_result.md](log/stage10_background_waiting_result.md) | 백그라운드가 도는데 캐릭터가 자던 것 — 기다림 표시 |
| [stage11_session_tab_result.md](log/stage11_session_tab_result.md) | 패널 [세션] 탭 정리 — 버튼이 너무 많고 뭔지 모르던 것 |
| [handoff_verify_20261106.md](log/handoff_verify_20261106.md) | 인계 검증 — 인계 뒤 바뀐 것(worktree · 합침 · 새 커밋 · 잠금)을 기계로 붙인다 |
| [overlap_alert_20261106.md](log/overlap_alert_20261106.md) | 겹침 알림 — 살아 있는 세션에 들어간 입력도 다른 세션과 맞대 본다 |
| [ui_font_title_20261106.md](log/ui_font_title_20261106.md) | 글씨 키우기 · 사람이 붙인 세션 이름이 항상 이기게 |
| [portfolio_publish_20261106.md](log/portfolio_publish_20261106.md) | 포트폴리오 합치기 · Notion 게시, 끝난 서기 세션의 [합치기]가 안 보이던 것 |
| [stage13_demo_capture_result.md](log/stage13_demo_capture_result.md) | 로드맵 13(시연 사진 · 녹화) 결과 |
| [stage14_dispatcher_note_wake_result.md](log/stage14_dispatcher_note_wake_result.md) | 로드맵 14(디스패처 이름 · 노트 · 자동 기상 2단계) 결과 |
| [stage15_usage_result.md](log/stage15_usage_result.md) | 로드맵 15(사용량) 결과 |
| [ui_input_overlay_20261108.md](log/ui_input_overlay_20261108.md) | 패널 입력이 "확인하지 못했습니다"로만 떨어진 건 — CC가 설정 · 사용량 화면을 띄워 둔 것 |
