# FOREMAN

> 문서 틀(11-17 사용자): 이 문서는 설계 전체이고 세션과 개발자가 읽는다. 세션이 지킬 규칙은 `CLAUDE.md`, 처음 온 사람의 길 안내는 맨 위 `README.md`(생성물, `tools/docs.py readme`)다. README에 설계를 다시 쓰지 않는다. 이 문서는 11-17까지 맨 위 README.md였다

> AI 코딩 에이전트가 만든 변경이 배포까지 가는 전 과정을, 브라우저 한 화면에서 보고 지시하는 관제실.

**매일 쓰는 중이다.** 런슈즈, 펫퍼민트, FOREMAN, 인프라 세션이 모두 tmux에서 돌고 브리지는 systemd 사용자 유닛이 돌린다. 만든 순서는 깃헙 커밋, 기능마다 지금 상태는 `docs/`의 각 문서, 아직 할 일은 `docs/TODO.md`, 안 하기로 한 것은 「6. 알려진 한계」, 서버 PC 변경과 지난 경위는 [`log/`](log/)가 맡는다. 이 문서에서 뺀 진행 기록은 [`log/design_history_20261117.md`](log/design_history_20261117.md)에 있다. 킥오프 설계 검토는 [`log/01_kickoff_result.md`](log/01_kickoff_result.md).

**접속**: 서버 PC(VNC) 브라우저나 `ssh -L 8000:localhost:8000`으로 붙는다. **터널로 밖에 열지 않는다**(3.13). 밖에서는 텔레그램으로 받는다. 화면은 `http://localhost:8000/`(픽셀 화면. 승인, 대화, 입력, 터미널이 다 여기 있고 테마는 마지막에 본 것), 카드 목록은 `/classic`, 확인과 디버그 페이지는 `/debug`.

---

## 1. 왜 만드는가

Claude Code 세션 두 개를 터미널 두 개로 띄워놓고 쓰다가 생긴 불편에서 출발했다.

| 불편 | 임시 대응 | FOREMAN의 해결 |
|---|---|---|
| 언제 끝날지 모름 | 텔레그램 봇 직접 연동 | 턴 종료를 hook으로 기계 판정, 브리지가 발송 |
| 뭘 하고 있는지 안 보임 | 창 전환해서 확인 | 세션 상태를 실시간 시각화 |
| 서버 PC 다운을 모름 | 없음 | WebSocket 끊김으로 감지, 화면 전체 표시 |
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
| `SUSPENDED` | 프로세스 정지(Ctrl+Z, `T` 상태). 컨텍스트는 메모리에 있으나 입력과 hook 불가 | 안 쓴다 | 자리에서 얼어붙음 (회색) |

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

캐릭터는 버튼으로 만드는 것이 아니라, 대응하는 실체가 생기면 등장한다. 파이프라인의 첫 알림을 받으면 그 프로젝트에 Jenkins, Harbor, ArgoCD 캐릭터가 등장한다(`bridge/pipeline.py`, `config/pipeline.toml`).

따라서 **캐릭터 구성이 곧 프로젝트 성숙도**다. 포먼만 있으면 맨땅, 코더가 붙으면 개발 중, 인프라 캐릭터가 서 있으면 파이프라인 가동 중.

등장은 이벤트 기반이지만 **생존은 폴링 기반**이다. 웹훅은 「사라졌다」는 신호를 보내지 않으므로, 주기적으로 엔드포인트를 확인해 응답이 없으면 `STALE`로 바꾸고 오래 그러면 퇴장시킨다. 덤으로 인프라 헬스체크가 생긴다.

**호스트의 systemd 유닛과 docker 컨테이너 감시는 아직 없다**(`docs/TODO.md` foreman-1). 웹훅과 엔드포인트 응답만으로는 죽지 않고 계속 다시 뜨는 상태가 잡히지 않는다. 킥오프 무렵 `milvus-port-forward.service`가 한 달 넘게 567,740회 재시작했고 milvus 컨테이너가 재시작 크래시 루프를 17분 돌았는데, 둘 다 어느 경로에도 걸리지 않았다([기록](log/infra_20261102_milvus-port-forward.md)). 계획은 유닛과 컨테이너를 캐릭터로 만들지 않고, 재시작 추세를 폴링해 프로젝트에 연결된 것은 그 인프라 캐릭터 상태에, 어디에도 속하지 않는 것은 포먼 경고 목록에 띄우는 것이다. `character.watch_targets` 칸과 `restart_loop` 이벤트 종류는 이 감시를 위해 두었고, 쓰는 코드는 없다.

### 2.3 역할은 바뀐다

Jenkins 캐릭터에게 "왜 터졌어?"라고 물으면 inspector 세션이 붙고, "고쳐줘"라고 하면 같은 캐릭터에 coder 세션이 붙는다. 캐릭터는 그대로이고 세션 이력이 쌓인다.

cicd 역할은 뺐다. 한 번도 쓰지 않았고 빌드와 배포는 브리지 파이프라인 구역이 본다([기록](log/cicd_role_removal_20261114.md)). 세션 역할은 coder, inspector, scribe, manager, designer다(`docs/roles.md`).

### 2.4 포먼만이 채용한다

새 캐릭터를 만들 수 있는 것은 포먼뿐이다. 프로젝트마다 하나씩 상주한다.

- 프로젝트 컨텍스트 보유
- 작업 분배: 누구를 띄울지, 무엇을 시킬지
- 세션 요약과 인계 작성
- CI/CD 결과 수신 후 후속 조치 판단

포먼도 평소에는 세션 없이 서 있다가, 말을 걸면 붙는다.

UI에서는 부모-자식 관계를 트리로 그리지 않는다. **공간으로 표현한다.** 포먼에게는 프로젝트 방 안에 별도의 자리(구석 사무실 / 사서 데스크)를 주고, 일꾼은 공용 작업장에 둔다(2.5).

### 2.5 공간 구성

- **프로젝트마다 별도의 방이다.** 런슈즈와 펫퍼민트는 다른 방에 있다. 방 안에 포먼의 자리, 일꾼의 공용 작업장, 파이프라인 구역(3.6), 인프라 캐릭터의 자리가 있다.
- **서브에이전트는 부모 옆에서 돈다**(3.11). 그러므로 자동으로 부모와 같은 방 안이다.
- **떠돌이 캐릭터**(`project_id`가 null, 예: '미분류'. 프로젝트 밖 폴더의 세션이다. 포트폴리오는 프로젝트마다 두는 서기가 쓴다, `docs/12_scribe.md`)는 어느 방에도 속하지 않으므로 방 밖의 별도 공간이 필요하다(예: 복도, 라운지).
- **방이 여러 개일 때 화면을 어떻게 보여줄지는 10단계(테마 렌더러)에서 정한다.** 선택지와 지금의 의견만 적어 둔다.

| 선택지 | 좋은 점 | 문제 |
|---|---|---|
| 나란히 | 모든 방이 한 번에 보인다 | 방이 3개를 넘으면 각 방이 작아져, 서브에이전트 10개가 도는 장면이 안 보인다 |
| 탭 | 한 방을 크게 본다 | 다른 방에서 생긴 사고가 안 보인다. "모르고 있던 것을 보이게 한다"는 목적과 부딪힌다 |
| 줌 (전체 지도 → 방 확대) | 축소 상태에서도 방마다 경고, ACTIVE, 재시작 루프가 보이고, 알림이 온 방으로 들어가기 자연스럽다 | 지도와 확대 사이 전환을 만들어야 한다 |

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
    ├─ 상태        CC hooks (UserPromptSubmit / PreToolUse / PermissionRequest / Stop / StopFailure / SessionEnd
    │                        / SubagentStart / SubagentStop, 견본 deploy/hooks/foreman-hooks.json)
    │              + 프로세스 상태 폴링 (/proc/<pid>/stat)
    ├─ 승인 정책   PreToolUse에서 allow / ask 판정
    ├─ 수명 관리   tmux 생성·종료, git worktree add·remove
    ├─ 적재        MySQL — 호스트 도커의 FOREMAN 전용 인스턴스 (127.0.0.1:3308, 3.12)
    ├─ 발신        텔레그램
    ├─ 수신        웹훅 (GitLab · Jenkins · Harbor · ArgoCD)
    └─ 폴링        인프라 생존 확인 (2.2), 사용량
                   (LLM 지표, 재시작 추세는 아직 없음, docs/TODO.md)
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

`send-keys -l`로 직접 치면 LF가 그대로 들어가 CC가 중간에 제출할 수 있다. `paste-buffer -p`는 앱이 괄호 붙여넣기를 켰을 때만 괄호를 씌우고, `-r`이 없으면 LF를 CR로 바꾼다. CC 바이너리는 `[200~`/`[201~`를 paste-start/end로 해석하고, CC 자신도 pty에 `\x1B[200~…\x1B[201~`를 쓴 뒤 10ms 후 `\r`을 보내는 같은 패턴을 쓴다. tmux는 셸 문자열이 아니라 인자 목록(subprocess argv)으로 호출한다. 따옴표, `$`, 백틱, 백슬래시, 한글은 tmux 계층에서 그대로 통과한다(실측).

- **pane 하나에 claude 하나.** job control(Ctrl+Z, `&`, `fg`)을 쓰지 않는다. send-keys는 pane의 포그라운드 프로세스로 가므로, bash 하나에 claude 여럿이 얹히면 대상이 모호해진다.
- **주입 전 `#{pane_current_command}` 확인.** claude가 아니면 주입하지 않는다. CC가 정지되면 포그라운드는 bash가 되고, 보낸 프롬프트가 **셸 명령으로 실행된다.** 따라서 SUSPENDED 캐릭터에는 주입을 차단한다.
- **ACTIVE 중 입력은 새 턴이 아니라 대기열로 들어간다**(트랜스크립트 `queue-operation` enqueue/dequeue/remove). UI는 캐릭터별 대기열을 표시한다.
- **실측 결과(3단계, [기록](log/stage3_inject_result.md))**: 따옴표, `$`, 백틱, 백슬래시, 한글, 들여쓰기는 그대로, 긴 붙여넣기(3천 자)도 원문이 트랜스크립트에 남는다. 다만 **여러 줄은 `<pasted_content id="…">` 태그로 감싸여 모델에 "붙여넣은 글"로 가고, 탭은 공백 4칸이 된다.**
- **첫 글자**: `/`는 슬래시 명령으로, **`!`는 셸 명령으로 실행된다** → `/`는 앞에 공백 한 칸을 붙인다(일부러 명령을 보낼 때만 그대로). `@`는 새지 않는다. 폭 없는 공백 보호는 Enter가 안 먹혀 입력 칸에 남았다. 쓰지 않는다
  - `!` 명령: 입력 API가 앞뒤 공백을 떼고, 같은 명령을 Bash 도구 호출처럼 승인 규칙에 넣어 **묻는 규칙(ask), sudo, 여러 줄, 빈 명령만 막고**(이유와 할 일을 글로) 그 밖은 bash 모드로 실행한다(`inject.bang_check`). bash 모드는 승인 훅을 거치지 않는다. 그래도 `!`가 글로 들어가면 텔레그램으로 알린다(`bridge/bang_watch.py`). 언제나 공백을 붙여 막던 옛 방식은 사람이 실행하려던 명령 7건을 글로 보냈다 [log:petmint_docs_move_20261109.md] [log:alerts_denied_xmsg_bang_20261109.md]
- **창이 떠 있으면 종류로 갈라 닫거나 거부한다**: 붙여넣기 전에 화면을 가른다(`inject.screen_state`. `deliver`가 부르므로 패널 입력, 옮기기 넣기, 감독실 [보내기], 끝내기가 모두 같은 길이다)
  - 입력 칸은 0칸에서 시작하는 가로줄(`────`) 바로 아래의 0칸 `❯` 줄부터 다음 가로줄까지다. 입력 칸 위에 `▔▔▔` 테두리나 Esc 안내 줄(「… · Esc to cancel」)이 있으면 창으로 본다
  - Esc가 「그대로 둠, 지금은 아님」인 창(자동 압축 권유, `/model`, `/config`, `/usage`, `/autocompact`): Esc를 보내고 0.6초 뒤 다시 본다, 최대 3번. 결과 글 "떠 있던 ○○ 창을 Esc N번으로 닫고 보냈습니다."(입력 이벤트에 `esc` 수와 `dialog` 이름)
  - Esc가 결정이 되는 창(폴더 신뢰, 도구 권한, 보류된 세션 메시지 승인, 끝내기 확인, 계획 승인)과 모르는 창: Esc도 글도 보내지 않고 거부한다. "○○ 창이 떠 있어 넣지 못했습니다 … 그 세션 대화창에서 확인해 주세요"
  - **작업 중(busy)이면 Esc를 보내지 않는다.** Esc는 작업을 끊는다. 권한 창이 떠 있을 때 상태 파일 status는 `busy`가 아니라 `waiting`이라 창 종류로 거른다. 바뀐 내력은 [옮긴 기록](log/design_history_20261117.md) 4절 [log:plan_dialog_escape_retry_20261109.md] [log:prompt_vs_dialog_20261113.md]
- **제출 확인**: 보낸 글이 트랜스크립트에 프롬프트나 대기열(`queue-operation enqueue`)로 기록됐는지 본다. 안 되면 실패로 알리되 입력 칸은 자동으로 비우지 않는다(사람의 초안을 지울 수 있다)
- **바쁨 판정은 CC가 `~/.claude/sessions/<pid>.json`에 적는 `status`(busy, idle, shell)**. 바쁠 때 보낸 입력에도 UserPromptSubmit hook이 불린다. 열린 턴이 있으면 새 턴을 열지 않는다

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
| 정상 종료 | 625/625 | Stop | 없음 |
| 사용자 중단(Esc) | 29건 중 15건만 | Stop 미발동 (4단계 실측) | 트랜스크립트 `[Request interrupted by user]` 줄. **첫 응답 전에 누르면 이 줄도 없다**(아래) |
| API 에러 | 2/2 | StopFailure (error, error_details) | 없음 |
| 세션 종료 (창 닫힘, exit) | 0/5 | SessionEnd (reason) | 프로세스 소멸 폴링 |
| 턴 도중 auto-compact | 턴이 `compact_boundary`를 넘어 이어짐 | 없음 | 없음 |

그래서 턴에 `end_reason`을 두고, **먼저 도착한 신호가 턴을 닫는다**(`closed_by`에 출처: transcript, hook, sweep). 시작은 UserPromptSubmit hook, 실시간 종료 트리거는 Stop / StopFailure / SessionEnd hook, 중단은 interrupt 마커, 비정상 소멸은 폴링이 맡는다. `turn_duration`은 소요시간(`durationMs`)과 사후 대조에 쓴다.

**턴의 경계는 CC의 `promptId`다**(2단계 실측). 한 턴의 user 줄(프롬프트, tool_result, 중단 표시, compact 요약)이 모두 같은 `promptId`를 갖는다. 새 `promptId`를 가진 user 줄이 턴을 연다. 사람 프롬프트만이 아니라 task-notification과 다른 세션의 메시지도 연다(`turn.origin`). 앞 턴이 안 닫힌 채 다음 턴이 열리면, 앞 턴에 모델 활동이 없었으면 `merged`(응답 없이 다음 입력과 함께 처리, 실측 54건 전부), 있었으면 `no_signal`. 프로세스가 사라진 세션은 hook을 받던 세션이면 `process_lost`, 아니면 `session_end`. hook이 트랜스크립트보다 먼저 오는 경우(Stop이 마지막 응답 줄보다 먼저)는 늦게 온 줄을 직전 턴에 붙인다.

#### Esc 중단은 흔적을 남긴다: FOREMAN이 다루는 법

CC에서 Esc로 중단하면 **Stop hook이 불리지 않는다**(4단계 실측). 이건 CC의 동작이라 FOREMAN이 바꿀 수 없다. 그래서 FOREMAN은 남는 흔적으로 판단한다.

| 언제 눌렀나 | 트랜스크립트에 남는 것 | FOREMAN |
|---|---|---|
| 응답이 오는 도중, 도구 실행 중 | `[Request interrupted by user]` 줄 | 그 줄로 바로 `interrupted`(텔레그램 `⏹ 중단됨`) |
| **첫 응답이 오기 전**(프롬프트를 보내자마자) | 프롬프트 줄과 API 요청 줄뿐이다. **중단 표시 줄도 없다** | 턴이 열린 채 남는다 → 아래 |

실제로 있었던 일: 펫퍼민트 창에 잘못 붙여넣고 바로 Esc. 턴이 10시간 열려 있었고, 대시보드에는 그 세션이 "작업 중"으로 보였다.

열린 채 남은 턴은 이렇게 다룬다.
1. **화면**: 세션의 상태는 CC가 직접 적는 상태(busy, idle)로 정한다. 열린 턴이 있어도 CC가 일하지 않으면 "작업 중"이 아니라 "대기"이고, 카드에 **"⚠ 끝 신호 없는 턴"**을 따로 표시한다
2. **1시간 뒤 정리**: 프로세스는 살아 있는데 CC가 일하지 않고 그 턴이 1시간 넘게 조용하면 `abandoned`로 닫는다(정리 작업, 종료 시각은 마지막 활동 시각)
3. **다음 입력이 오면**: 응답 없이 열려 있던 앞 턴은 다음 입력까지 1시간 안이면 `merged`(다음 입력과 함께 처리됨), 1시간 넘으면 `abandoned`(버려짐)
4. **1시간인 이유**: 실측에서 진짜로 다음 입력과 합쳐진 턴은 66개 모두 56분 안이었다. 1시간이면 그것을 잘못 닫지 않는다. 설정 `turn_abandon_s`

턴이 닫히는 순간 브리지가 한 번에 처리한다:

```
트랜스크립트 읽기 → DB 적재 → 텔레그램 발송 → WebSocket push → 캐릭터 상태 전환
```

텔레그램 알림 시점 = 캐릭터 상태 전환 시점이므로 하나를 구현하면 둘 다 된다.

**hook 설치 위치**: 사용자 설정 `~/.claude/settings.json`(모든 세션. FOREMAN이 보려는 것이 런슈즈, 펫퍼민트 세션이다). 설정 원본은 `deploy/hooks/foreman-hooks.json`, 스크립트는 `scripts/foreman-hook.sh`(2초 타임아웃, 출력 없음, 항상 exit 0. 브리지가 꺼져 있어도 CC를 막지 않는다). 설치 전 백업은 `~/.claude/backups/settings.json.before-foreman-hooks`. **실행 중인 CC는 설정 파일 변경을 다음 프롬프트부터 반영한다**(3단계 실측, 사용자 설정과 프로젝트 설정 모두). 이미 떠 있던 세션도 재시작 없이 hook을 보낸다.

**알림은 브리지가 보낸다(4단계, [결과](log/stage4_notify_result.md)).** 예전에는 CLAUDE.md 지시로 모델이 스크립트를 실행해 모델이 턴 종료를 판정했고 누락이 생겼다. 이제 턴이 닫히는 순간(먼저 온 신호) 브리지가 `config/notify.toml` 규칙으로 판정해 보낸다. 종료 이유마다 제목이 다르고(끝남, ⚠ API 오류, ⏹ 중단, 세션 종료, ⚠ 프로세스 사라짐), 프로젝트 접두어를 붙인다. 사람이 연 턴만 보내고, 완료 알림이나 서브에이전트 결과 전달로 열린 턴은 보내지 않는다. 백그라운드 서브에이전트는 세션의 것이 모두 끝났을 때 한 번 묶어 보낸다. 보낸 것과 안 보낸 것(+규칙)은 `notification`에 남는다. 서브에이전트 결과 전달은 `<agent-message from=X>`의 X가 그 세션의 서브에이전트인지로 가른다(문장 모양으로는 못 가른다).

### 3.3 승인 정책

원래 불편 중 마지막 항목이다(5단계, [결과](log/stage5_approval_result.md)). PreToolUse hook마다 브리지가 판정한다. 규칙은 `config/approval.toml`, 판정은 `bridge/approval.py`다. 규칙 하나하나, 오탐을 고친 내력, 승인 창이 뜬 뒤의 흐름은 기술문서 원고 `notion/04_approval.md`와 그 아래 `01_rules`, `02_flow`가 다룬다. 이 절은 원칙과 그 원칙이 기대는 근거만 둔다.

**원칙: 사용자가 실제로 거부할 만한 것만 묻는다.** 이론적 위험이 아니라 실제 거부가 기준이다. 목적은 auto mode에서 흐름이 안 끊기는 것이다. 좁히기 전 승인 이력 65건 가운데 실제 작업에서 거부는 0건이었다(유일한 거부는 승인 창 시험). 경위와 근거는 [결과](log/stage5_approval_result.md) 「11-05 다시 좁히기」.

| 판정 | 대상 | CC에서 |
|---|---|---|
| `ask` | **통째로 지우기**(`/`, 시스템 최상위, 홈, `~/AI_programming`의 프로젝트 하나, `~/volumes`의 볼륨 하나 …, `X/*`, 비면 `/`가 되는 `$X/`), **운영 DB 날리기**(foreman-mysql, 클러스터 쪽 `DROP`, `TRUNCATE`, WHERE 없는 `DELETE`), **재부팅, 종료, VM 파괴**, **작업 이력 날리기**(`push --force`, `reset --hard`, `clean -f`, `filter-branch`), **비밀 파일을 밖으로 보내기**, **데이터 볼륨, PVC, 네임스페이스, helm 릴리스 삭제**, CC와 tmux 한꺼번에 끄기, `curl … \| sh`, `crontab -r` | 승인 창. auto mode의 자동 통과보다 앞선다 |
| `allow` | **되돌릴 수 있는 것과 읽기**: `kubectl apply`, `rollout`, `git push`, `docker stop`, `restart`, `systemctl restart`, 파일 편집과 쓰기(작업 트리 밖 포함), Read, Grep, Glob, `git status`, `log`, `diff`. 명령의 모든 조각이 이래야 한다. 규칙과 설정 파일 편집도 통과하고 텔레그램 🛡을 보낸다 | 승인 창 없이 통과 |
| `pass` | 그 밖: `/tmp`, mktemp, 작업 트리 밖의 평범한 삭제, 비밀 파일 읽기와 복사, 로컬 개발 DB, `kubectl delete pod`, `docker rm`, 해석기 heredoc 안의 글자 … | 브리지는 정하지 않는다. CC(auto mode 분류기와 사용자 설정)가 지금처럼 정한다 |

21일 다시 돌려 보기(도구 호출 18,076개): 하루 승인 창이 런슈즈 10.7에서 **0.1**, 펫퍼민트 6.8에서 **0.2**, 포먼 26.3에서 **1.3**이 되었다. 남은 9건은 모두 거부할 만한 것이었다(운영 DB 비우기 4, 이력 재작성 2, PVC와 네임스페이스 삭제 3).

좁히기 전의 **엄격한 규칙**은 코드에 남아 있고 설정으로 다시 켠다(`[sensitive] mode = "read"`, `protect_mode = "ask"`, `[ask] delete_outside_worktree = true`, `scan_interpreter_heredocs = true`). 시험은 `tests/test_approval.py`(엄격 규칙은 `tests/fixtures/approval_strict.toml`)와 `tests/test_approval_now.py`(지금 기준).

**승인 규칙을 시험할 때**: 판정 함수(`load_policy(...).decide(...)`)를 부르는 코드를 파일로 쓰고 `.venv/bin/python <파일>`로 돌린다. 위험 명령 글자가 든 코드를 heredoc으로 넘기면 그 명령 자체가 hook에 걸린다. 과거 데이터 다시 돌려 보기는 `scripts/approval-replay.py`.

#### 실행과 글자는 다르다

같은 `rm -rf`라도 실제로 지우는 명령은 묻고, 글자로 적어 두는 것(설정 파일의 규칙, 커밋 메시지, 주석)은 통과한다.

**왜 필요했나.** 이 승인 시스템을 만드는 도중에 승인 시스템이 자기 자신을 막았다. 규칙 파일(`approval.toml`)에 위험한 명령의 모양을 적어 넣는 것만으로 승인 창이 떴고, 커밋 메시지에 "kubectl apply"라고 쓰는 것도 걸렸다. 세 번 연속 걸렸고, 그게 고친 계기다. 처음 규칙은 "명령에 이 글자가 있으면 묻는다"였는데, 그러면 위험한 명령에 대해 *쓰는* 일까지 막힌다.

**어떻게 가르나: 그 글자가 어디로 들어가는지를 본다.**

1. **텍스트로 저장만 되는 곳**(`cat > 파일`, `tee 파일`, `git commit -F -`, `git tag -F -`)에 들어가는 본문은 검사하지 않는다.
2. **실행기**(`bash`, `sh`, `python` 등)로 들어가는 본문은 검사한다.
3. **나중에 그 파일을 실행할 때**(`bash x.sh`, `source x`, `./x.sh`) 파일 내용을 검사한다. 위험한 명령을 파일에 숨겨 두어도 실행하는 순간 잡히므로 1번은 구멍이 아니다. 파일을 쓰는 다른 길(Write 도구)도 내용은 원래 검사하지 않았고, 똑같이 실행 순간에 잡힌다.
4. 따옴표 없는 본문 속 `$( )`와 백틱은 셸이 실제로 실행하므로, 받는 쪽이 커밋이어도 검사한다.
5. 같은 생각을 명령 한 줄 안으로 넓혔다: 검색 패턴(grep, rg, sed, awk의 패턴 인자), 문법 검사만 하는 것(`bash -n` 등), 키 이름만 뽑는 것, 값이 로컬 요청 헤더로만 가는 것, 같은 명령 안에서 `mktemp -d`로 만든 디렉토리를 `"${V:?}"`로 지우는 것, `echo`와 `printf`의 따옴표 인자, `git commit -m` 메시지, `curl --data` 본문. 모두 「검사 전에 무해한 자리표시로 바꾸기」라 **새로 allow를 만들지 않는다**(allow 판정은 바꾸기 전 원문으로 한다). 조건이 하나라도 어긋나면(파이프로 넘김, 명령 치환 안, 스크립트로 씀 등) 그대로 검사한다.

예시 표, 오탐 패턴 여덟 가지와 그 조건, 넣지 않은 것은 `notion/04_approval/01_rules.md`에, 고친 차례는 [옮긴 기록](log/design_history_20261117.md) 5절에 있다.

공개된 PreToolUse 게이트 다섯과 견주어 놓친 위험 패턴(이력 지우기 `git filter-branch`, 환경 덤프 등)을 더했고, 통째로 바꾸지는 않았다. 견준 표와 그때 다시 돌려 본 수치는 [옮긴 기록](log/design_history_20261117.md) 5절에 있다.

**규칙 파일 자체**(`config/approval.toml`, `notify.toml`)는 안전 규칙을 바꾸는 일이라 따로 다룬다. Edit, Write 도구 편집은 바뀐 내용이 터미널과 기록에 그대로 보이므로 통과하고 텔레그램 `🛡 안전 규칙 파일 수정`(같은 파일 10분에 한 번)을 보낸다. Bash로 쓰는 것(`>`, heredoc, `sed -i`, `cp`, `mv`, `tee`, `install`, `dd of=`, `truncate`)은 묻는다. 게이트를 통째로 끌 수 있는 `~/.claude/settings.json`, hook 스크립트, `~/.claude.json`은 도구 편집도 묻는다. 비밀 경로는 값이 화면에 안 나오는 모양(`grep -q`, `-c`, 끝이 `wc`나 `sha256sum`, `test -n "$(…)"`)만 통과한다.

#### 근거: hook의 `ask`는 auto mode에서도 승인 창을 띄운다

우리 설계는 이 한 가지에 기대어 돈다: **세 프로젝트 모두 auto mode인데, 되돌릴 수 없는 것만은 사람이 본다.** 공식 문서:

- [permission-modes](https://code.claude.com/docs/en/permission-modes): "In auto mode, a PreToolUse hook's "ask" normally sends the tool call to the permission prompt, and the classifier doesn't decide it." 그리고 "auto mode still shows you those prompts"(hook이 강제한 창)
- [hooks](https://code.claude.com/docs/en/hooks): `"ask"` prompts the user to confirm. 판정 없이 끝나면(exit 0, 출력 없음) "the tool call continues through the normal permission flow". 브리지가 꺼졌을 때 우리 hook이 아무것도 내지 않는 이유다. 여러 hook이 다르면 "deny > defer > ask > allow"
- [permissions](https://code.claude.com/docs/en/permissions): "PreToolUse hook decisions don't bypass permission rules … a matching ask rule still prompts even when the hook returned "allow"". 우리 `allow`는 사용자 설정의 deny와 ask 규칙을 넘지 못한다

**실측**: 이 세션(FOREMAN 작업, 트랜스크립트의 `permissionMode`가 461줄 모두 `auto`)에서 우리 `ask` 26건이 모두 승인 창으로 떴고 터미널에서 답했다(`approval`: terminal 24, 중단 1, 시간 초과 1).

**문서에 없는 것**(기대지 않는다): bypassPermissions와 acceptEdits에서 hook `ask`, hook `allow`가 auto mode 분류기를 건너뛰는지(실측 없음), `claude -p`에서 hook `ask`.

#### 그 밖

**규칙에 없는 것을 `ask`로 하지 않는 이유**: 세 프로젝트 모두 auto mode로 돌고, 20일 동안 도구 호출 약 9,700건 중 사람이 승인을 누른 것은 18건뿐이었다. 규칙에 없는 모든 것을 묻게 하면 승인 창이 수천 건이 된다. `unmatched = "ask"`로 바꿀 수 있다.

**승인 창이 뜨면**(우리 ask든 CC 자체 판단이든) PermissionRequest hook이 브리지에 와서 승인 대기가 생기고 텔레그램 `🔐 승인 대기`가 간다. **브라우저(확인 페이지), 터미널, 시간 초과(10분) 가운데 먼저 온 것이 정한다.** hook이 기다리는 동안에도 터미널 승인 창은 떠 있고, 터미널에서 먼저 답하면 바로 진행된다(실측). 브리지가 꺼져 있으면 hook은 아무것도 돌려주지 않고 CC가 지금처럼 정한다(허용 쪽으로 새지 않는다).

**질문(AskUserQuestion)은 승인이 아니지만 같은 길로 받는다.** CC가 질문 창을 띄울 때도 PermissionRequest hook이 불린다. 정책(`approval.toml`)에서 빼지 **않는다.** 빼면 질문이 터미널에만 떠 텔레그램과 화면 알림이 없고 턴도 안 끝나 턴 끝 알림도 없다(세션이 조용히 멈춘다). 대신 카드와 답하는 길을 따로 두고, 패널에서 고른 답은 `updatedInput`에 `answers`를 실어 돌려준다(`bridge/approvals.py` `answer()`). 자세한 것은 `notion/04_approval/02_flow.md` [log:pixel_bigger_question_card_20261109.md]

**계획 승인(ExitPlanMode)도 `updatedInput`을 붙여 돌려준다.** CC는 사람 창을 띄우는 도구에서 `updatedInput` 없는 hook `allow`를 결정으로 받지 않는다. 패널이 허용해도 터미널 계획 승인 창이 남아 세션이 조용히 멈췄다. 그래서 패널 허용은 원래 입력에 `updatedPermissions = [{type: "setMode", mode: "auto", destination: "session"}]`을 붙여 돌려준다(`bridge/approvals.py` `allow_decision`, 터미널 기본 선택 「1. Yes, and use auto mode」와 같은 결과). 그래도 창이 남으면 멈춤 감시(`bridge/stallwatch.py` `dialog`)가 2분 뒤 패널과 텔레그램으로 알린다 [log:silent_finish_20261114.md] [log:plan_approve_mode_20261114.md]

**승인 창 한 줄 요약**: 판단에 필요한 건 「무엇을 대상으로」다. `bridge/approval_summary.py`가 명령을 보고 대상을 뽑아(`rm -rf → … (기존 디렉토리, 파일 418개)`처럼) CC 승인 창, 텔레그램, 대시보드 승인 카드, `approval.summary`에 같은 줄을 붙인다. 디렉토리 파일 수는 0.3초 안에서만 센다(PreToolUse는 4초 안에 답해야 한다).

**승인 이력**: 대시보드 "승인 이력"(`/api/approvals/history?days=1|7|30`)이 규칙별로 걸린 수, 승인, 거부, 모름과 최근 목록(요약 줄), 관찰 모드 프로젝트에서 "걸렸을 것"을 보인다. **3번 넘게 걸렸는데 한 번도 거부하지 않은 규칙은 "늘 Yes — 규칙 손볼 후보"**로 표시한다(묻는 의미가 없으면 규칙을 고친다). 시간 초과나 재시작 뒤 터미널에서 답한 것은 그 도구가 실행됐는지(`tool_result`)로 거꾸로 안다. 처음 본 7일은 45건 가운데 승인 44, 거부 1이었고 늘 Yes는 보호-설정파일 10, 민감한-경로 8이었다.

**모든 판정을 남긴다**: 자동 승인과 pass까지 `event(type=approval_req)`(규칙, 이유, 강제 여부)에, 승인 대기와 결과는 `approval` 테이블과 `event(approval_res)`에 남는다. ask와 결정은 로그에도 이유와 함께 남는다.

**프로젝트별 mode**: `enforce`(판정을 돌려준다)와 `observe`(기록만). 실행 중인 세션에 곧바로 걸리므로 런슈즈, 펫퍼민트는 observe로 시작했다. 쌓인 판정을 보고 enforce로 바꾼다. 지금 값은 `config/approval.toml`.

### 3.4 병렬 작업과 충돌

한 프로젝트에 캐릭터를 둘 이상 붙이면 같은 파일을 덮어쓴다. **git worktree**로 세션마다 별도 워킹트리와 브랜치를 준다.

```
캐릭터 생성 = git worktree add + tmux 세션 생성 + claude 실행 (pane 하나에 claude 하나)
```

UI에서도 "이 캐릭터는 이 브랜치"가 자연스럽게 보인다. 머지는 포먼이 한다.

### 3.5 자동 기상

실패 이벤트(빌드 실패, 빌드 없음, 웹훅 끊김, 인프라 다운, 적재 막힘)가 오면 디스패처가 「살펴볼 세션」 계획을 만들고, 텔레그램과 화면으로 [시작]을 묻는다. **사람이 눌러야 뜬다.** 상한은 `config/wake.toml`이다: 하루 계획 수(`daily_max`), 같은 실패는 `dedupe_hours` 안에 다시 계획하지 않음. 상세는 `docs/14_dispatcher_note_wake.md`, 코드는 `bridge/wake.py`.

자동으로 깬 세션은 **읽기 전용**으로 시작한다. 원인 분석까지만 하고 보고한다. 고치는 것은 사람의 승인을 받는다. 자는 사이에 커밋이 쌓이면 안 된다.

처음 설계에 있던 동시 ACTIVE 최대 3, 자동 세션 30분 뒤 강제 IDLE, 야간 끔은 코드에 없다(`docs/TODO.md` foreman-118). 묻지 않고 띄우는 3단계도 아직이다(foreman-49). 처음 설계 표는 [옮긴 기록](log/design_history_20261117.md) 6절.

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

**실제 흐름**: 런슈즈와 펫퍼민트는 같은 구조다. GitHub push가 GitHub 웹훅으로 Jenkins 빌드를 시작하고(15분 SCM 폴링이 안전망), ArgoCD도 GitHub 웹훅과 3분 폴링으로 인프라 저장소 변경을 본다. Jenkins, ArgoCD 같은 운영 도구는 Cloudflare Access 뒤에 있고, 두 도구의 GitHub 웹훅 경로 하나씩만 Access 밖(Bypass)에 두어 HMAC 서명 검사가 지킨다 [log:stage8_cicd_result.md] [log:foreman-6_access_policy_20261117.md].

```
로컬 커밋 → GitHub push ─(GitHub 웹훅, 안전망 15분 폴링)→ Jenkins 빌드 → Harbor push(태그 = 커밋 12자리)
  → ronanlab-infra apps/<앱> newTag 커밋 ─(GitHub 웹훅, 3분 폴링)→ 런슈즈 자동 Sync / 펫퍼민트 수동 Sync
```

**FOREMAN이 받는 길**: 앱 저장소 Jenkinsfile의 `foremanNotify`가 빌드 시작과 끝을, ArgoCD notifications가 동기화를 FOREMAN 웹훅 포트로 보낸다. 웹훅 포트는 VM 사설망 주소에서 `/webhooks/*`만 받는다(`bridge/main.py`). 커밋은 같은 서버의 프로젝트 저장소를 폴링해 그 시각 직전에 `git commit`을 부른 세션에 귀속한다(`bridge/pipeline.py` 머리). 인프라 캐릭터는 첫 알림에 등장하고(2.2), 실패는 실패로 바뀔 때 텔레그램 한 번이다.

- **문서만 바뀐 빌드는 건너뜀이 정상이다.** 바뀐 파일이 모두 문서면 Jenkinsfile이 이미지 빌드와 태그 커밋을 건너뛰고 SUCCESS로 끝내며 `foremanNotify` 본문에 **`"skipped": true`**를 더한다. 브리지는 그 빌드에 이미지 태그를 붙이지 않고 Harbor, ArgoCD를 기다리지 않는다
- **ArgoCD 수동 Sync 대기 알림**: 배포 안 된 이미지가 Sync를 기다리면 처음 1시간 뒤 한 번, 풀릴 때까지 24시간마다 텔레그램을 보낸다. 한 통만 보내면 그걸 놓쳤을 때 일주일이 간 일이 있었다 [log:screen_mismatch_waits_20261109.md]
- **끝 알림 없이 「진행 중」에 남는 배포**: running이 10분 넘으면 ArgoCD를 읽기 전용으로 직접 읽어 끝났으면 닫고, Sync 시작 뒤 30분이 지나도 안 끝났거나 못 읽으면 텔레그램으로 알린다(`config/pipeline.toml [argocd_read]`) [log:screen_argocd_read_20261109.md]

처음 조사(웹훅 없이 전 구간 폴링이던 때)와 처음 정한 「읽기 조회」 방향, 위 세 줄의 자세한 동작은 [옮긴 기록](log/design_history_20261117.md) 7절과 [8단계 기록](log/stage8_cicd_result.md)에 있다.

### 3.7 LLM 지표

없앴다. 프로메테우스로 LLM 지표(큐 대기, TTFT, tok/s, VRAM)를 긁어 캐릭터로 보이는 계획이었고 코드는 없다(`docs/TODO.md` foreman-117, 처음 계획은 [옮긴 기록](log/design_history_20261117.md) 8절). 절 번호는 다른 문서가 「3.8」 이하를 가리키고 있어 비워 둔다.

### 3.8 테마

이벤트를 애니메이션으로 잇는 매핑을 테마마다 JSON 하나로 분리한다(`bridge/static/themes/<테마>/theme.json`의 `match`, `go`, `anim`). 렌더러는 상태, 도구, 플래그만 보고 그리므로 테마 교체가 매핑 파일 교체로 끝난다.

**3D는 쓰지 않는다.** 에셋과 카메라, 조명 비용이 2D의 몇 배인데 전달되는 정보량은 같다. 2D로 테마 세 개가 3D 하나보다 낫다.

**크기**: 방은 이미 무대에 꽉 차 있어 방을 다 보이게 둔 채로는 방 안의 그림만 키울 수 있다. **캐릭터만 1.5배**(테마 `sprites.char_scale`)이고 **가구는 키우지 않는다**(칸 배치, 길찾기, 앉기와 묶여 있다, 사용자 결정). 경위는 `log/pixel_bigger_question_card_20261109.md` 「3.」

#### 서브에이전트 렌더링

데이터 모델과 렌더링을 분리한다. 서브에이전트는 캐릭터가 아니라 `subagent_run` 행이지만(3.11), **렌더러는 이것을 실제 일꾼으로 그린다.** "에이전트들이 돌아다니면서 일하는" 장면이 이 화면의 목표이고, 서브에이전트 10개가 동시에 도는 것이 그 장면의 핵심이다.

- **외형은 부모 캐릭터의 축소판이다.** 부모 스프라이트를 작게 줄이고 색조만 살짝 바꾼다. 별도 에셋이 필요 없고, 누가 띄웠는지 선이나 색으로 설명하지 않아도 생김새로 보인다. 한 방에서 코더와 조사 캐릭터가 각각 서브에이전트를 띄워도 구분되고, 역할별 외형도 그대로 상속된다. 조사 캐릭터가 띄우면 작은 조사 일꾼이 나온다.
- **위치는 부모 옆이다.** 그러므로 자동으로 부모와 같은 방 안이다(2.5).
- **움직임은 부모와 같은 매핑 테이블을 쓴다.** 서브에이전트 안의 도구 사용도 `status`, `tool` 이벤트이므로 테마 매핑을 그대로 탄다.
- **부모가 IDLE이어도 일꾼은 돈다.** 부모는 자리에 앉아 있고 작은 일꾼들이 돌아다니며, 부모 위에 "백그라운드 n개" 배지가 붙는다(3.11).
  - 서브에이전트나 백그라운드 Bash, Monitor가 돌면 IDLE 부모를 **기다림(WAITING)** 으로 그린다. 자는 모습 대신 책상에 서서 "…"를 띄우고, 이름 아래 "백그라운드 n · 설명"을 붙이며, 현장 집계는 작업으로 센다. 서버 상태 값은 그대로 IDLE이고 화면만 바꾼다(`theme.js` `viewState`, 테마 `states.WAITING`)
- **복잡도:** 같은 작업을 여러 개로 나눠 띄우는 경우가 흔하므로(예: "Wide yes/no search wn1"…) `description`의 공통 앞부분으로 묶어 묶음 이름을 단다. **접는 것은 한 부모의 일꾼이 10개를 넘을 때만이다.** 넘는 만큼 "+N"으로 접는다.

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

**만든 모양(7단계)**: ttyd와 tmux를 그대로 쓰고, 브리지는 길만 낸다.

```
브라우저 iframe /terminal/ ──(쿠키)── 브리지 127.0.0.1:8000 ──── ttyd (.run/ttyd.sock, TCP 포트 없음)
                                                                    └─ tmux foreman-shell ─ bash --rcfile deploy/shell/foreman-bashrc
                                                                         └─ 탭마다 그룹 세션 foreman-shell-v-<탭>(deploy/shell/foreman-term-view — 셸은 함께, 보이는 창만 탭마다. 탭을 닫으면 사라짐)
셸 PROMPT_COMMAND ── /hooks/shell(hook 토큰) ──> event(source=shell, type=shell_cmd, 마스킹)
CC 턴 끝 ── 부탁 감지 ──> 셸 입력 줄에 미리 채움(send-keys, Enter 없음) + WS terminal_request(패널을 올린다)
사람이 그 명령을 침 ──> 출력(capture-pane, 마스킹) ──> 부탁한 세션에 주입(3단계 방법 C) · 안 되면 화면에만
```

- **밖에 열리지 않는다.** ttyd는 TCP 포트를 열지 않고 UNIX 소켓에만 묶는다(디렉토리 0700, 다른 사용자도 못 붙는다). 127.0.0.1 포트보다 한 단계 좁다. 브라우저는 브리지를 거쳐서만 닿는다: API 토큰으로 쿠키(HttpOnly, SameSite=Strict, Path=/terminal. 브리지 메모리에만 있어 브리지를 다시 띄우면 새로 받는다)를 받고, WS는 Origin이 Host와 같아야 한다(다른 사이트가 브라우저 쿠키로 셸을 여는 것을 막는다). 화면은 같은 출처의 틀 안에서만(`X-Frame-Options: SAMEORIGIN`)
- **승인 정책은 걸리지 않는다, 기록은 남는다.** 명령마다 `shell_cmd` 이벤트(명령, 종료 코드, 위치). 마스킹은 기존 규칙(정확한 값, 토큰 모양, `KEY=값`)에 명령줄 자리를 더했다: `--password 값`, `docker/podman/helm registry login -p 값`, `mysql -p값`, `sshpass -p`, `echo 값 | sudo -S`, `| … --password-stdin`, URL의 `user:암호@`, `curl -u user:암호`. 셸 기록 파일은 디스크에 남기지 않고(`HISTFILE=`), 공백으로 시작하는 명령도 기록한다(`HISTCONTROL=`)
- **방을 따라간다**(사용자 결정, [기록](log/foreman_term_office_three_20261110.md)). 방(현장)을 옮기면 터미널도 그 방 프로젝트의 창으로 바뀐다. 연 채 옮겨도 바뀌고, 막대의 창 이름도 같이 바뀐다. tmux는 보이는 창이 하나라서 브라우저 탭마다 그룹 세션 `foreman-shell-v-<탭>`으로 자기 창을 본다
- **셸은 캐릭터가 아니다.** `character_session.type='shell'`(포먼 프로젝트의 포먼에 붙인 행 하나). 대시보드와 세션 목록은 `type='agent'`만 본다
- **부탁 찾기**: 턴이 `stop`으로 끝나면 그 턴의 assistant 글에서: ① 셸 코드 블록, 인라인 코드, `! 명령` 안에 ② 사람이 쳐야 하는 명령(`sudo`, `su`, `ssh-add`, `ssh-keygen`, `ssh-copy-id`, `passwd`, `kinit`, `docker/podman/… login`, `gh/glab/gcloud auth login` …)이 있고 ③ 부탁하는 말("실행해 주세요", "쳐 주세요", "직접 실행", "please run" …)이 있을 때. 설명이나 기록에 나온 `sudo`는 ③이 없어 걸리지 않는다. `! 명령` 꼴은 그 자체가 부탁이다. 여럿이면 첫 번째를 채우고 나머지는 배너에 보인다
- **미리 채우기**: 셸 입력 줄을 비우고(C-e C-u) 글자로 넣는다(`send-keys -l`, Enter 없음). 비밀번호 자리(`<password>`, `«masked…»`, `YOUR_…`, `-p 값` 등)는 비우고 커서를 거기로 옮긴다. 셸이 다른 일을 하는 중이면(암호 입력 중, 다른 명령 실행 중) 건드리지 않고 배너에 "다시 채우기"를 둔다
- **결과 전달**: 사람이 친 명령이 부탁과 같으면(비운 자리 앞까지, 아니면 앞 단어 세 개) 화면에서 그 명령의 출력(명령을 친 프롬프트 줄 다음부터 새 프롬프트 앞까지, 마지막 60줄)을 마스킹해 `[터미널 패널] …`로 부탁한 세션에 넣는다. 주입이 안 되는 세션(tmux 밖, 정지)은 배너에만 보인다. 부탁은 30분 기다리고, 세션마다 최신 하나만 둔다

### 3.10 서버 연결 상태

브리지가 서버 PC에서 돌므로, 서버가 죽으면 브리지도 죽는다. 따라서 "서버 다운"은 브리지가 알려주는 것이 아니라 **브라우저가 WebSocket 끊김으로 판단**한다.

끊기면 화면 전체를 덮고 재연결을 시도한다. 침묵으로 아는 것이다. 확인 페이지에 붙였다(4단계): 한 번 연결된 뒤 끊기면(1006, 서버 종료, 하트비트 두 번 놓침) 덮개에 언제부터 끊겼는지와 다음 시도까지 남은 초를 보이고 1→2→4→8→15초로 다시 붙는다. 토큰이 틀려 끊긴 것(1008)은 덮지 않고 멈춘다.

---

### 3.11 서브에이전트 (CC 세션 안의 병렬)

CC 세션 하나가 `Agent` 도구(이 버전에서는 `Task`가 아니라 `Agent`)로 서브에이전트를 띄운다. 킥오프 실측([기록](log/01_kickoff_result.md)): 런슈즈 132회, 동시 최대 10개 / 펫퍼민트 47회, 동시 최대 6개. 179회 전부 `async_launched`이다. 결과는 tool_result가 아니라 **나중에 부모의 새 입력으로** 돌아온다.

**캐릭터가 아니다.** 부모 프로세스 안에서 몇 분 살다 끝나고 한 세션에서 10개까지 동시에 뜨므로 `character` 테이블에 넣지 않는다(영속 캐릭터, 포먼만 채용). FOREMAN이 띄우는 일꾼(자기 tmux, worktree, CC 세션)은 캐릭터이고, CC 내부 서브에이전트는 `subagent_run` 행이다. 화면에서는 일꾼으로 그린다(3.8 서브에이전트 렌더링).

#### 트랜스크립트 구조 (실측)

- 위치: `~/.claude/projects/<proj>/<sessionId>/subagents/agent-<agentId>.jsonl` + `agent-<agentId>.meta.json`(`agentType`, `description`, `toolUseId`, `spawnDepth`, `requestShape`, `finished`). 런슈즈 132쌍 160.7MB, 펫퍼민트 47쌍 48.4MB
- 기록 종류와 필드는 부모와 같다. 같은 파서를 쓴다. 다른 점:
  - 모든 줄에 `agentId`, `isSidechain: true`
  - **`sessionId`가 부모와 같다.** 부모와 자식 구별은 `agentId`와 파일 경로로 한다
  - 첫 줄 `parentUuid`가 null이다. 부모의 uuid 체인과 이어지지 않는다
  - **system 기록이 없다**(`turn_duration` 없음). 소요 시간은 첫 줄과 마지막 줄 timestamp로 잰다
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
- **귀속**: 백그라운드는 띄운 턴과 결과를 받는 턴이 다르다. 토큰과 이벤트는 **띄운 턴**(`toolUseId`로 연결)에 귀속하고, 결과를 받은 턴은 `result_turn_id`로 따로 남긴다.
- **상태**: 부모 턴이 Stop으로 끝나도 자식은 돌 수 있다(토큰은 계속 나간다). 상태 값을 늘리지 않고 **"IDLE + 백그라운드 n개"** 배지로 보인다.
  - 백그라운드 Bash와 Monitor도 같이 센다(서브에이전트가 아니라 `subagent_run`에는 넣지 않는다, [기록](log/stage10_background_waiting_result.md))
    - 시작: 도구 결과의 `backgroundTaskId`, `taskId` → 이벤트 `bg_start`
    - 끝: `<task-notification>`의 status → `bg_end`. 큐(enqueue), 첨부(queued_command), 사람 줄 어디로 와도 한 번만 남는다
    - 대시보드 `background`에는 끝 없는 시작만 들어간다(살아 있는 세션, 지금 CC 프로세스가 뜬 뒤 시작한 것)
- **알림**: 서브에이전트마다 보내지 않는다. 부모 턴이 끝날 때 한 번, 또는 백그라운드 묶음이 모두 끝났을 때 한 번 묶어서 보낸다.
- **토큰**: 서브에이전트 단위로 따로 저장하고, 화면에서는 부모 턴에 "본인 + 서브에이전트"로 나눠 합산해 보인다.

#### 출력 토큰 문제 (미해결)

- 서브에이전트 줄의 usage는 **응답을 받기 시작한 시점의 값**으로 보인다. `stop_reason`이 null이고 output_tokens가 글자당 0.002(부모는 0.77, 예: 10,603자 블록에 8). 입력 쪽(cache_read, cache_creation)은 그럴듯하지만 검증 안 함
- **SubagentStop hook 입력에 usage가 없다**(2.1.316 바이너리). 필드는 공통(session_id, transcript_path, cwd, permission_mode, agent_id, agent_type, effort) + `stop_hook_active`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`, `session_crons`
- 완료 알림(`<task-notification>`)의 **일부**에 합계가 있다: `<usage><subagent_tokens>N</subagent_tokens><tool_uses>N</tool_uses><duration_ms>N</duration_ms></usage>`. 런슈즈 서브에이전트 140개 중 34개, 펫퍼민트 `cddadc68` 18개 중 11개(completed 알림인데도 없는 경우가 많다). 종류 구분 없는 합계 하나이고 입력 포함 여부는 미확인. **소수에만 있으므로 주 경로로 쓰지 않는다.** 있으면 `subagent_run`에 합계로 남겨 다른 경로의 값과 대조하는 **보조 검증용**으로만 쓴다
- **주 경로 후보: OpenTelemetry 메트릭 `claude_code.token.usage`**: 위 합계로 대신할 수 없으므로 **OTel 실측은 여전히 필요하다**. 응답이 끝난 뒤의 최종 usage로 type(input, output, cacheRead, cacheCreation)별로 더하고, 속성에 `model`, `query_source`, `effort`가 붙는다. `query_source`로 본체와 서브에이전트가 구분되는지는 실측이 필요하다
- 실측 방법: 버리는 디렉토리에서 `CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=console OTEL_METRIC_EXPORT_INTERVAL=5000`으로 CC를 띄워, 서브에이전트 없는 프롬프트 하나와 서브에이전트 하나를 띄우는 프롬프트 하나를 보낸다. 콘솔 메트릭의 `query_source` 값과 output 합계를, 같은 세션 트랜스크립트 부모 줄의 output 합계와 비교한다
- 그 전까지 서브에이전트 output은 `output_tokens_reliable = false`로 저장하고 화면에 "추정"으로 표시한다

**미정**: 동시 서브에이전트 수에 상한이나 경고를 둘지. 처음 설계의 자동 기상 「동시 ACTIVE 최대 3」(3.5, 아직 없음)도 캐릭터 세션 수이고 서브에이전트는 세지 않는다.

### 3.12 배치: 브리지와 DB는 클러스터 밖, 호스트에 둔다

**결정**: 브리지는 호스트 프로세스, DB는 호스트 도커의 **FOREMAN 전용 MySQL**(`127.0.0.1:3308`)이다. 클러스터(k8s)에 올리지 않는다.

**결정적 이유: 감시하는 쪽과 감시받는 쪽의 장애 범위를 나눈다.** FOREMAN은 클러스터와 호스트 서비스가 망가지는 순간을 기록하려고 만든다. DB가 클러스터 안에 있으면 클러스터가 흔들리는 바로 그 순간에 적재가 멈추고 화면이 꺼진다. 킥오프 무렵의 두 사고가 정확히 그런 상황이었다. `milvus-port-forward.service`가 한 달 넘게 567,740회 재시작했고, milvus 컨테이너가 17분 크래시 루프를 돌았다(2.2). 감시 장비가 감시 대상과 같이 죽으면 그 기록이 남지 않는다.

그 밖의 근거:

- 브리지가 다루는 것(tmux, `~/.claude/projects/` 트랜스크립트, hook, `/proc` 폴링, systemd와 docker 폴링)이 전부 호스트에 있다. DB도 같은 곳에 둔다
- 재부팅 때 docker 데몬과 함께 바로 뜬다. VM 4대와 클러스터가 다 올라오기를 기다리지 않는다
- **기존 MySQL에 얹지 않는다.** 클러스터의 `petmint/mysql-0`과 `runshoes/runshoes-mysql-0`는 운영 DB이고 headless라 호스트에서 바로 붙을 수 없다. 호스트 3306(`mysql`)은 펫퍼민트 로컬 개발과 측정용이다. 펫퍼민트 `db/bootstrap.py`가 관리하고, 초기화할 때(`~/mysql-data`를 비우는 경우 등) FOREMAN 기록이 같이 사라지며, FOREMAN이 계속 쓰면 측정값이 오염된다
- 검토하고 버린 선택지: m-k8s에서 `kubectl port-forward`(파드가 재시작되면 끊기고 감독 프로세스가 따로 필요하다. `milvus-port-forward`와 같은 모양이다), NodePort나 MetalLB 신설(연결은 되지만 위의 장애 범위 문제가 그대로이고, 데이터가 노드 하나의 `local-path`에 묶인다)

**브리지를 파드로 띄울 수 없는 이유**: 여기서 k8s 노드는 libvirt VM이다. `hostPID`와 `hostPath`가 가리키는 "호스트"는 서버 PC가 아니라 VM이므로, 서버 PC의 claude 프로세스(`/proc`)도 `~/.claude/`도 보이지 않는다. tmux 유닉스 소켓은 VM 경계를 넘지 못한다. 우회하려면 파드에서 호스트로 ssh해야 하는데, 그러면 사용자 계정의 ssh 키가 클러스터 Secret에 들어간다. 파드 하나가 털리면 서버 PC 셸이 털린다. 트랜스크립트를 NFS로 내보내면 클라이언트 쪽에서 inotify가 오지 않아 폴링으로 돌아간다.

**수집부(호스트)와 API/UI(파드)로 나누지 않는다. 배포는 systemd 유닛 재시작이고, 시험은 관리자가 합친 뒤 손으로 돌린다.** 처음에는 「8단계(CI/CD)에서 다시 본다」로 미뤘는데, 다시 보니 나눌 이유가 오히려 줄었다.

**GitHub Actions는 쓰지 않는다.** Jenkins, Harbor, ArgoCD를 익히려고 그 묶음을 골랐고, 채용 공고에서도 이 도구들이 자주 보였다. 그리고 GitHub Actions는 깃허브 쪽 러너에서 돌아 사설망 안의 Harbor에 닿지 않는다. 닿게 하려면 러너를 따로 세워야 하는데, 그러면 Jenkins를 세우는 것과 다르지 않다(사용자) [log:foreman-5_todo_collect_20261117.md].

- **떼어낼 수 있는 UI가 사실상 없다.** 실시간 상태(WS 버스, 조립된 턴), 승인 대기(PreToolUse hook이 응답을 기다린다), 터미널(ttyd UNIX 소켓, 3.9)이 모두 브리지 프로세스 안이나 호스트에 묶여 있다. 파드로 옮길 수 있는 것은 정적 HTML과 JS(약 1,260줄)뿐이고, 그 파드는 호스트 브리지 앞의 프록시가 될 뿐이다
- **UI는 빌드할 것이 없다.** 번들러 없는 순수 JS이고, 저장소 파일을 그대로 낸다(no-cache). "빌드, 이미지, Harbor, ArgoCD"를 태우면 단계만 늘고 얻는 것이 없다
- **런슈즈 UI와 닮은 점은 "브라우저로 본다"뿐이다.** 런슈즈는 밖의 사용자에게 여는 서비스이고, FOREMAN UI는 호스트 셸(터미널 패널)과 승인 권한을 가진 관제실이다. 클러스터나 터널 쪽으로 옮기면 노출 면만 커진다
- 처음의 이유도 그대로다. 배포 단위가 둘이면 그 사이 프로토콜과 한쪽만 죽는 상태를 다뤄야 하고, 클러스터가 죽으면 정작 그때 화면이 꺼지며, 물리 서버가 하나라 가용성도 늘지 않는다

대신 실제로 도움이 되는 두 가지만 한다:

| 무엇 | 왜 | 하지 않는 것 |
|---|---|---|
| **systemd 유닛**(브리지) | 지금 가장 큰 운영 공백이다. tmux에 손으로 띄워 재부팅하면 안 뜨고, 죽어도 다시 안 뜬다. 재시작은 유닛 + 사람이 부르는 스크립트 하나(시험 → import 확인 → 대기 중인 승인이 없을 때만 재시작) | **push마다 자동 재시작은 하지 않는다.** 작업 폴더가 곧 실행 폴더이고 커밋하는 CC 세션도 같은 호스트라 받아올(pull) 코드가 없다. 배포는 사실상 재시작인데, 재시작은 승인 대기와 화면 연결을 끊는다. 커밋한 그 세션의 hook이 끊길 수도 있다 |
| **시험은 관리자가 합친 뒤 손으로**(pytest, node) | 사람이 잊으면 돌지 않는 빈틈은 아는 채로 둔다. 승인 정책(`approval.py`)처럼 퇴행을 막아야 하는 규칙도 이 길로만 지켜진다 | **우리 Jenkins에 태우지 않는다.** 그쪽은 이미지를 만들어 Harbor로 보내는 서비스용이고 FOREMAN에는 이미지가 없다. Jenkinsfile, 시험 DB, 인프라 저장소 수정이 생겨 통일을 위한 통일이 된다 |

다시 볼 조건은 하나다. **VNC 없이 밖에서 FOREMAN을 봐야 할 때.** 그때도 답은 파드가 아니라 호스트 브리지에 바로 붙이는 것이다. 다만 지금은 밖에 열지 않기로 했다(3.13).

### 3.13 외부 노출: 터널을 열지 않는다

처음 설계는 6단계 뒤에 `foreman.ronanlab.dev` 터널과 Cloudflare Access로 밖에서 보는 것이었다([브리프 02](docs/history/02_cloudflare_tunnel.md)). **열지 않기로 했다.** 브리프는 지우지 않고 "⏸ 보류 — 필요해지면"으로 둔다.

**까닭(사용자)**: 관제실은 호스트 셸과 승인 권한을 쥐고 있다. 여기가 한 번 뚫리면 네 저장소 전부에 push할 수 있고, 위험 작업을 통과시킬 수 있고, 비밀값이 든 설정도 만질 수 있다. 다른 서비스는 뚫려도 그 서비스 하나지만 여기는 나머지 전부로 번진다. 그래서 Access를 앞에 두는 것으로 그치지 않고 아예 열지 않았다. 밖에서 필요한 것은 텔레그램으로 받는다 [log:foreman-5_todo_collect_20261117.md].

- **화면에 그 권한이 다 있다.** 터미널 패널(ttyd, 호스트 셸, 3.9), 실행 중인 CC 세션에 입력 주입(3.1, tmux send-keys), 승인과 거부(되돌릴 수 없는 명령을 통과시키는 버튼)가 대시보드에 있다. 앞단 인증 하나가 깨지면 보는 화면이 아니라 서버를 내주는 셈이다
- **공유 서버다.** 이 서버는 kopo17과 kopo02가 같이 쓴다. 여기서 셸이 열리면 피해가 이 프로젝트에서 끝나지 않고 다른 계정까지 간다
- **밖에서 필요한 정보는 이미 텔레그램으로 받는다.** 턴 종료 알림(4단계), 승인 대기와 그 요약(5단계), 파이프라인 실패, 빠진 알림, 웹훅 끊김(8단계), 적재 막힘. 보기만 할 거면 이걸로 된다. **그거 하나 보려고 터널을 유지할 값어치가 없다**
- **못 해서가 아니라 안 한 것이다.** 런슈즈와 펫퍼민트는 같은 서버에서 이미 터널(클러스터 `cloudflared`, `runshoes.ronanlab.dev`, `petmint.ronanlab.dev`)로 공개했고, Jenkins, ArgoCD, Harbor도 Access 뒤에 열어 두었다. 열 줄 알고, 열 길도 있다. FOREMAN은 열었을 때 잃을 것과 얻을 것을 따져 열지 않았다
- **필요해지면 여는 길**: 지금 화면을 그대로 여는 게 아니라 **읽기 전용 화면**(터미널 패널, 입력, 승인 버튼 없이 세션 상태와 파이프라인만)을 따로 두고, 사람 인증을 **패스키나 mTLS**(클라이언트 인증서, 기기에 묶인다)로 강하게 해서 연다. 승인은 그때도 텔레그램이나 서버 앞에서. 브리프 02는 이 조건으로 고쳐 쓴다

## 4. 만들 것과 가져다 쓸 것

이미 잘 만들어진 것을 조합하고, 비어 있는 구간만 직접 채운다.

| 구간 | 방식 | 근거 |
|---|---|---|
| 터미널 웹화 | ttyd | 성숙한 도구. 재발명 금지 |
| 프론트 터미널 | xterm.js | 표준 |
| 세션 목록과 제어 | 기존 구현 참고 | tmux 다루는 로직만 차용 |
| 상태 수집 | CC hooks | 공식 기능 |
| 캐릭터 스프라이트 | MIT / CC0 에셋 | pixel-agents 계열 |
| 지표 수집 | 프로메테우스 | 아직 없음(`docs/TODO.md` foreman-117) |
| **CI/CD 인과 체인** | 직접 | 기존 구현에 없음 |
| **캐릭터↔인프라 매핑** | 직접 | 기존 구현에 없음 |
| **승인 정책 엔진** | 직접 | 기존 구현에 없음 |
| **LLM 병목 시각화** | 직접 | 기존 구현에 없음. 아직 없음(foreman-117) |

### 참고할 기존 프로젝트

| 프로젝트 | 볼 것 |
|---|---|
| Ramillax/claude-code-control-room | ttyd + tmux + hook 상태. 프레임워크 없이 bash와 Python 표준 라이브러리. 구조가 가장 가깝다 |
| mxinO/Claude-Web-UI | send-keys 입력 릴레이, 브라우저 툴 승인, 재접속 시 놓친 이벤트 요약 |
| wolfpeter/claude-session-manager | xterm.js ↔ node-pty ↔ tmux attach, 세션 디스커버리 |
| nielsgroen/claude-tmux | git worktree 연계, 세션 상태(idle/working/waiting) 감지 |
| pablodelucca/pixel-agents | 캐릭터 렌더링, 레이아웃 (MIT) |

CC에는 `/remote-control` 모드가 이미 존재한다. 세션 뷰어 구간은 레드오션이므로 여기서 차별화를 시도하지 않는다.

---

## 5. 데이터 모델

테이블과 칸의 기준은 마이그레이션(`migrations/NNNN_*.sql`, 적용은 `bridge.db.migrate`)이다. 칸 하나하나와 칸마다의 설명은 그 파일 주석과 기술문서 원고 `notion/15_db.md`, `notion/15_db/`에 있다. 처음 스키마는 [`migrations/0001_init.sql`](migrations/0001_init.sql)이고, 처음 설계와 달라진 점(`transcript_file` 분리, event FK 없음, enum을 VARCHAR와 애플리케이션 검사로, `target_truncated` 등)은 그 파일 머리말과 [1단계 결과](log/stage1_bridge_db_result.md)에 있다. 이 절은 테이블마다 무엇을 담는지만 둔다.

| 테이블 | 담는 것 | 만든 마이그레이션 |
|---|---|---|
| `project` | 프로젝트 하나(이름, 저장소 경로, 네임스페이스) | 0001 |
| `character` | 영속 캐릭터(역할, 상태, 화면 자리, 인프라 캐릭터면 종류와 확인 대상). 세션과 다르다(2.1) | 0001 |
| `transcript_file` | 트랜스크립트 파일마다 어디까지 읽었나(inode, offset, 마지막 uuid) | 0001 |
| `character_session` | 캐릭터에 붙은 CC 세션이나 셸 하나(tmux pane, pid, CC 세션 id, worktree, 역할) | 0001 |
| `turn` | 프롬프트 하나부터 턴이 닫힐 때까지(종료 이유와 닫은 신호, 3.2) | 0001 |
| `message` | API 응답 하나(`message.id`)와 그 토큰. 블록마다 줄이 쪼개져도 한 번만 센다 | 0001 |
| `subagent_run` | CC 세션 안의 서브에이전트 하나(3.11). 캐릭터가 아니다 | 0001 |
| `event` | 도구 호출, 승인, 셸 명령 같은 사건 한 줄. FK가 없다(0001 주석) | 0001 |
| `notification` | 보낸 알림과 안 보낸 알림, 그 규칙 | 0005 |
| `approval` | 승인 대기와 그 결과(3.3) | 0010 |
| `git_commit`, `build`, `build_commit` | 커밋과 세션 귀속, 파이프라인 단계, 빌드 하나에 묶인 커밋들(3.6) | 0012 |
| `summary`, `session_action` | 인계 요약과 세션 조작 기록 | 0014 |
| `dispatch`, `dispatch_session` | 교장 계획과 그 계획으로 띄운 세션, 맡을 파일 | 0016, 0030 |
| `promotion`, `loss_check` | 문서로 옮기기와 압축 손실 점검 | 0020, 0021 |
| `doc_publish`, `scribe_review` | 노션 게시 기록과 서기 검토 | 0022, 0023 |
| `foreman_note` | 교장 노트 | 0025 |
| `usage_observation`, `usage_extra` | 사용량 관찰과, 트랜스크립트에 남지 않는 `claude -p`(디스패처, 압축 손실 점검)의 사용량 | 0026 |
| `todo_inbox`, `postit_check` | 포스트잇과 [갱신] 판정 | 0027, 0033 |
| `merge_card` | 합치기 카드 | 0032 |

`character_session_move_0017`은 0017 재배치 때 남긴 되돌리기용 표다. 위 표에 없는 테이블이나 칸이 생기면 마이그레이션이 기준이다.

### 보관 정책

`event`는 양이 빠르게 늘어난다. 보관 기간을 정하고, 기간이 지나면 요약만 남기고 원본을 지운다. 스키마 설계 시점에 함께 결정한다.

**적재 제외**: `api-request`, `api-request-blob` 줄은 적재하지 않는다(트랜스크립트 용량의 80% 이상, 대화 복원에 불필요).

**hook 설치 후에는 재적재하지 않는다**(원칙, 사용자 결정). turn, message, event는 트랜스크립트에서 다시 만들 수 있지만 **hook 이벤트(`event.source = 'hook'`)와 hook이 정한 턴 필드(`closed_by = 'hook'`인 턴의 종료 시각과 이유)는 트랜스크립트에 없다.** 다시 만들면 사라진다(2단계에서 실제로 확인). 트랜스크립트 쪽 오류는 다시 읽기(offset 0, 멱등)나 새 마이그레이션으로 고치고, 파생 테이블을 비우는 전체 재구성은 하지 않는다. 꼭 해야 할 상황이면 hook 이벤트와 hook이 닫은 턴을 따로 백업한 뒤 하고, 재구성 뒤 되살린다.

**조회 화면에서 도구 결과 본문이 필요하면** DB가 아니라 트랜스크립트에서 직접 읽는다(`event.tool_use_id` → 트랜스크립트 줄). DB에는 길이와 오류 여부만 둔다. 형식을 모르는 비밀은 마스킹으로 못 잡는다(2단계, 사용자 확인).

CC의 `cleanupPeriodDays`(기본 30일)가 트랜스크립트 원본을 지우므로 서버 PC 설정에서 120일로 올려 두었다. 서버를 쓸 수 있는 기간에 맞춘 값이다(하루 약 64MB × 120일 ≈ 7.7GB, 결정 당시 디스크 84%). 브리지 적재가 안정되면 이 값과 `event` 보관 기간을 함께 다시 정한다.

인덱스는 마이그레이션 파일에 있다(`migrations/0001_init.sql` 등).

---

## 6. 알려진 한계

- 한계(하려 했는데 안 한 것)와 조건(우리가 고르지 않은 것)은 까닭과 함께 원고 `notion/17_limits.md` 한 곳에 모았다(11-19). 여러 편에 되풀이되는 것만 거기 두고, 한 편에만 걸리는 것은 그 편 한계 절에 있다(`docs/manuscript_rules.md` 2절)
- 이 설계에 걸리는 큰 한계 줄기: 서버 한 대(조건), 밖에 열지 않음(3.13), 브리지가 답하지 못하면 판정 없이 통과, 해석기 안 쓰기와 샌드박스, 관리자 규칙은 기록만, 도구 결과 본문과 binlog를 남기지 않음, CI 없음과 손 재시작
- 설계(하기로 한 것)는 각 절 본문에 약속으로 쓴다. 할 일(까닭이 없는 것)은 `docs/TODO.md` 한 곳이다(`docs/manuscript_rules.md` 1절). 이 절에 있던 「작업방 세션을 옮기면 새 세션이 원본 폴더에 뜬다」는 할 일이라 foreman-44로 갔다

---

## 7. 데모 시나리오

없앴다. 「포먼에게 프로메테우스를 붙여 달라고 하면 코더가 manifest를 쓰고 파이프라인을 지나 프로메테우스 캐릭터가 등장한다」는 시연 계획이었고 그 길을 만드는 코드는 없다(`docs/TODO.md` foreman-117, 처음 계획은 [옮긴 기록](log/design_history_20261117.md) 8절).
