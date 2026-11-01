# FOREMAN

> AI 코딩 에이전트가 만든 변경이 배포까지 가는 전 과정을, 브라우저 한 화면에서 보고 지시하는 관제실.

🚧 **킥오프** (2026-11-02) — 진행은 [`docs/`](docs/) 브리프 참고

**개발 중 접속**: 로드맵 0~5단계는 `ssh -L 8000:localhost:8000`으로 붙고, 6단계 이후에 Cloudflare Tunnel로 바꾼다. 코드는 바뀌지 않고 앞단만 바뀐다.

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

### 2.3 역할은 바뀐다

Jenkins 캐릭터에게 "왜 터졌어?"라고 물으면 inspector 세션이 붙고, "고쳐줘"라고 하면 같은 캐릭터에 coder 세션이 붙는다. 캐릭터는 그대로이고 세션 이력이 쌓인다.

### 2.4 포먼만이 채용한다

새 캐릭터를 만들 수 있는 것은 포먼뿐이다. 프로젝트마다 하나씩 상주한다.

- 프로젝트 컨텍스트 보유
- 작업 분배 — 누구를 띄울지, 무엇을 시킬지
- 세션 요약·인계 작성
- CI/CD 결과 수신 후 후속 조치 판단

포먼도 평소에는 세션 없이 서 있다가, 말을 걸면 붙는다.

UI에서는 부모-자식 관계를 트리로 그리지 않는다. **공간으로 표현한다.** 포먼에게는 별도의 방(구석 사무실 / 사서 데스크)을 주고, 일꾼은 공용 작업장에 둔다.

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
    ├─ 출력        JSONL 트랜스크립트 와처 (inotify + offset tail)
    ├─ 상태        CC hooks (UserPromptSubmit / PreToolUse / PostToolUse / Stop / StopFailure / SessionEnd)
    │              + 프로세스 상태 폴링 (/proc/<pid>/stat)
    ├─ 승인 정책   PreToolUse에서 allow / ask 판정
    ├─ 수명 관리   tmux 생성·종료, git worktree add·remove
    ├─ 적재        MySQL (클러스터 내 파드)
    ├─ 발신        텔레그램
    ├─ 수신        웹훅 (GitLab · Jenkins · Harbor · ArgoCD)
    └─ 폴링        인프라 생존 확인, LLM 지표, 프로메테우스 쿼리
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

#### 입력 주입

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
- 미검증: 긴 붙여넣기의 `[Pasted text #N +M lines]` 접힘이 트랜스크립트에 원문으로 남는지, 첫 글자 `/` `!`의 모드 전환, `@` 자동완성 중 Enter 동작. 3단계 전에 실측한다.

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
| 사용자 중단(Esc) | 29건 중 15건만 | Stop 미발동 (공식 문서 기준) | 트랜스크립트 `[Request interrupted by user]` 줄 |
| API 에러 | 2/2 | StopFailure (error, error_details) | — |
| 세션 종료 (창 닫힘·exit) | 0/5 | SessionEnd (reason) | 프로세스 소멸 폴링 |
| 턴 도중 auto-compact | 턴이 `compact_boundary`를 넘어 이어짐 | — | — |

그래서 턴에 `end_reason`을 두고, **먼저 도착한 신호가 턴을 닫는다.** 시작은 UserPromptSubmit hook, 실시간 종료 트리거는 Stop / StopFailure / SessionEnd hook, 중단은 interrupt 마커, 비정상 소멸은 폴링이 맡는다. `turn_duration`은 소요시간(`durationMs`)과 사후 대조에 쓴다.

턴이 닫히는 순간 브리지가 한 번에 처리한다:

```
트랜스크립트 읽기 → DB 적재 → 텔레그램 발송 → WebSocket push → 캐릭터 상태 전환
```

텔레그램 알림 시점 = 캐릭터 상태 전환 시점이므로 하나를 구현하면 둘 다 된다.

현재 CC가 직접 봇 API를 호출하는 방식은 CC 자신이 턴 종료를 판정하므로 누락이 생긴다. 브리지로 옮기면 기계적으로 바뀌고, 턴 수·소요시간 통계가 공짜로 따라온다.

### 3.3 승인 정책

원래 불편 중 마지막 항목. PreToolUse hook이 `allow`를 반환하면 사람에게 묻지 않는다.

| 대상 | 판정 |
|---|---|
| Read · Grep · Glob | `allow` |
| Bash (git status · log · diff) | `allow` |
| Edit (worktree 안) | `allow` |
| Bash (kubectl apply, 운영) | `ask` |
| Write (worktree 밖) | `ask` |

브리지로 모으면 승인 대기가 알림으로 오고, 폰에서 눌러도 된다. 터미널에 포커스를 둘 필요가 없어진다.

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

### 3.10 서버 연결 상태

브리지가 서버 PC에서 돌므로, 서버가 죽으면 브리지도 죽는다. 따라서 "서버 다운"은 브리지가 알려주는 것이 아니라 **브라우저가 WebSocket 끊김으로 판단**한다.

끊기면 화면 전체를 덮고 재연결을 시도한다. 침묵으로 아는 것이다.

---

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
| project_id | FK nullable | null이면 떠돌이 (포트폴리오 작성 캐릭터 등) |
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
| end_reason | enum | stop stop_failure interrupted session_end process_lost |
| duration_ms | int nullable | `system/turn_duration`의 `durationMs` |
| compacted | bool | 턴 도중 compact가 일어났나 |

### message

API 응답 하나(`message.id`)가 한 행이다. 트랜스크립트에서는 content 블록마다 줄이 쪼개지지만 usage는 줄마다 같으므로 여기서 한 번만 센다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK varchar | `msg_…` |
| turn_id | FK | |
| model | varchar | |
| stop_reason | varchar | end_turn tool_use stop_sequence … |
| request_id | varchar | `req_…` |
| token_input | int | |
| token_output | int | |
| token_cache_read | int | 실제 입력의 대부분 |
| token_cache_creation | int | |

### event

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | PK | |
| uuid | varchar UNIQUE nullable | 트랜스크립트 줄 uuid. 재적재·hook 중복 방지 |
| parent_uuid | varchar nullable | 순서의 기준 (timestamp 아님) |
| session_id | FK | |
| turn_id | FK nullable | |
| message_id | FK nullable | 어느 API 응답의 블록인가 |
| tool_use_id | varchar nullable | tool_use와 tool_result 짝짓기 |
| source | enum | hook transcript poll |
| ts | datetime | 표시용. 정렬에 쓰지 않는다 |
| type | enum | start tool_use tool_result assistant_msg stop error approval_req approval_res interrupted compact queued session_end |
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
| commit_sha | varchar | 체인 연결 |
| stage | enum | gitlab jenkins harbor argocd |
| status | enum | running success failed |
| started_at / ended_at | datetime | |
| log_url | varchar | |
| message | text | 실패 사유 |

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

CC의 `cleanupPeriodDays`(기본 30일)가 트랜스크립트 원본을 지우므로 서버 PC 설정에서 120일로 올려 두었다. 서버를 쓸 수 있는 기간에 맞춘 값이다(하루 약 64MB × 120일 ≈ 7.7GB, 디스크 84% 사용 중). 브리지 적재가 안정되면 이 값과 `event` 보관 기간을 함께 다시 정한다.

### 인덱스

| 테이블 | 인덱스 | 용도 |
|---|---|---|
| event | `(session_id, ts)` | 세션 타임라인 |
| event | `(commit_sha)` | 인과 체인 |
| event | `uuid` UNIQUE | 중복 방지 |
| message | `(turn_id)` | 턴별 토큰 집계 |
| build | `(commit_sha)` | 인과 체인 |
| character_session | `(cc_session_id)` | hook 수신 시 세션 찾기 |
| character_session | `(character_id, detached_at)` | 현재 붙어 있는 세션 조회 |

---

## 6. 로드맵

| 단계 | 내용 | 비고 |
|---|---|---|
| 0 | `cleanupPeriodDays` 상향 (완료: 120일) + CC를 tmux로 이전 | 즉시 가능. SSH + tmux attach만으로 VNC 우회. pane 하나에 claude 하나 |
| 1 | 브리지 + 스키마 + MySQL + WebSocket | 토대 |
| 2 | hook 수신 + inotify 기반 JSONL 와처 (offset tail) + 턴 판정 (`end_reason`) | 기존 구현 참고 |
| 3 | send-keys 실측 선행 → 입력 → 왕복 완성 | ⚠️ **최대 리스크.** 격리된 tmux에서 CC로 방법 C·멀티라인·`/` `!` `@`·긴 붙여넣기를 먼저 실측. 여기가 막히면 프로젝트가 성립하지 않음 |
| 4 | 텔레그램 이관 + 연결 끊김 표시 | 3번과 같은 신호를 쓴다. 그 전까지는 CLAUDE.md "알림" 절 + `scripts/notify-telegram.sh`(모델 판단 발송)가 임시로 쓰이며, 이 단계에서 지운다 |
| 5 | 승인 정책 엔진 | 원래 불편 중 유일하게 안 풀린 것 |
| 6 | 대시보드 (못생겨도 되는 실사용 UI) | 여기까지가 매일 쓸 수 있는 물건 |
| 7 | 터미널 패널 (ttyd) + 명령 자동 채우기 | |
| 8 | LLM 지표 + 병목 시각화 | AI 인프라 축 |
| 9 | CI/CD 웹훅 + 인과 체인 + 파이프라인 구역 | 차별점 |
| 10 | 테마 렌더러 | 데이터가 어떻게 생겼는지 안 뒤에 설계 |
| 11 | 캐릭터 수명 관리 + 포먼 + 세션 인계 | |
| 12 | 포트폴리오 작성 캐릭터 (Notion MCP) | 로그를 읽어 회고 생성 |

3번을 일찍 치는 이유는 리스크가 가장 크기 때문이다. 막히면 설계를 바꿔야 하므로 늦게 알수록 손해다.

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

| # | 브리프 | 내용 | 실행 시점 |
|---|---|---|---|
| 01 | [kickoff](docs/01_kickoff.md) | 설계 검토: README 파악, 환경 조사, 설계 리스크, 기존 구현 조사, 단계 0 계획 | 지금 |
| 02 | [cloudflare tunnel](docs/02_cloudflare_tunnel.md) | 외부 노출: foreman.ronanlab.dev 터널 + Access 사람 인증, 브리지 자체 토큰 | 로드맵 6단계 완료 후 |
