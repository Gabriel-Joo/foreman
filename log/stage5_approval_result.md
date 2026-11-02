# 로드맵 5단계 — 승인 정책 엔진 결과

- **실행일**: 2026-11-02
- **앞 단계 마무리**: 런슈즈 `393315e` · 펫퍼민트 `5f31a6e` push(작업 중 변경 · 추적 안 된 파일은 그대로), 두 저장소의 `.env.telegram` 삭제(쓰는 곳 없음 확인 — 펫퍼민트 `.gitignore` 항목만, git 이력 0). foreman 것만 남음
- **커밋**: `e187bb1` 판정 엔진 · `c89ea7f` 승인 흐름 · (이 문서는 다음 커밋)
- 시험은 새로 만든 probe에서만(`--settings`로 그 세션에만 hook). 사용자 설정 설치는 이 기록을 push한 뒤에 했다 — 설치하면 이 세션도 enforce라 `git push` · `rm -r`이 승인을 기다린다

## 조사 결과 — 먼저 확인한 것

### 세 프로젝트 모두 auto mode다

트랜스크립트의 tool_result마다 CC가 `permissionDecision`을 남긴다. 20일 전체:

| 결정 | 출처 | 건수 |
|---|---|---|
| accept | config / classifier(auto mode 분류기) | 8,657 |
| accept | config / mode · other · (없음) | 1,065 |
| **accept** | **user_temporary(사람이 승인을 누름)** | **18** |
| reject | config / classifier · safetyCheck | 9 |
| reject | user_reject | 1 |

→ "매번 승인을 누르는" 불편은 지금 auto mode가 거의 없애고 있다(20일에 19번). 대신 **분류기가 운영 명령을 그냥 통과시켜 왔다** — 런슈즈 git push 79 · kubectl 변경 60 · docker 정지 · 삭제 67 · rm -r 41, 펫퍼민트 kubectl 변경 72 · rm -r 19 · sudo 13. 이 단계의 실제 가치는 "위험한 것부터 막기"와 "남은 승인을 브라우저로"다.

### hook 실측 (probe, auto mode, CC 2.1.316)

| 시험 | 결과 |
|---|---|
| PreToolUse `ask` + PermissionRequest `allow` | 승인 창 → PermissionRequest가 불림 → 승인(`permissionDecision.source = hook`) |
| PermissionRequest `deny` + message | 거부(`reject / hook / hook:PermissionRequest`), message가 모델에 감 |
| PreToolUse `allow` | **적용됨**(`accept / hook`). 바이너리의 "auto mode에서는 hook이 승인할 수 없다" 문구는 별칭 매칭 등 특정 조건으로 보인다 |
| PermissionRequest가 8초 기다림 | 3초 시점에 **이미 터미널에 승인 창이 떠 있다**. hook이 빈손으로 끝나면 창은 그대로 |
| 기다리는 중 터미널에서 Yes | **즉시 진행**(`user_temporary`, 20초 기다리던 hook과 무관) — 먼저 온 쪽이 정한다 |

입력 필드: PreToolUse는 `tool_use_id` · `prompt_id` · `permission_mode` · `scratchpad_dir`, PermissionRequest는 `prompt_id`는 있고 **`tool_use_id`가 없다** → 바로 앞 PreToolUse(세션 · 도구 · 입력)로 잇는다. 출력: PreToolUse `hookSpecificOutput.permissionDecision`(allow / ask / deny) + `permissionDecisionReason`, PermissionRequest `hookSpecificOutput.decision.behavior`(allow / deny) + `message`.

## 한 일

| 무엇 | 위치 |
|---|---|
| 규칙 | `config/approval.toml` — ask(운영 명령 · 작업 트리 밖 쓰기 · 비밀 / 설정 파일 · 애매한 운영 명령), allow(읽기 도구 · 작업 트리 안 Edit · git status/log/diff), 규칙에 없으면 pass, 프로젝트별 mode |
| 판정 | `bridge/approval.py` — 메모리 안(약 25ms 왕복). Bash는 조각마다, 위험 규칙은 따옴표 안까지 |
| 승인 흐름 | `bridge/approvals.py` — PreToolUse 판정 · 기록, PermissionRequest 대기, 브라우저 · 터미널 · 시간 초과 |
| hook | `/hooks/pre` · `/hooks/permission`, `scripts/foreman-decide.sh`(브리지가 없으면 아무것도 안 냄) |
| 기록 | `0010` `approval`, `event(approval_req)`(모든 판정) · `event(approval_res)`, 로그(ask · 결정) |
| 화면 | 확인 페이지 "승인 대기" 카드(승인 · 거부, 거부 이유 입력) |
| 알림 | 텔레그램 `[프로젝트] 🔐 승인 대기 · 도구 / 대상 / 이유` |

## 과거 데이터 모의 실험 — 규칙을 켜면 얼마나 묻게 되나

20일 도구 호출(서브에이전트 제외)에 정책을 돌렸다. 첫 규칙 → 조정 뒤(scratchpad 경로까지 넣은 실제 조건):

| 프로젝트 | 도구 호출 | ask(첫 규칙) | ask(조정 뒤) | 하루 | allow |
|---|---|---|---|---|---|
| 런슈즈 | 4,181 | 657 | 356 | 17.8 | 230 |
| 펫퍼민트 | 4,825 | 508 | 228 | 11.4 | 308 |
| 포먼 | 308 | 76 | 27 | 1.4 | 43 |

조정 뒤 남은 ask는 거의 실제 운영 명령이다(런슈즈 kubectl 변경 126 · git push 69 · docker 65 · rm -r 27, 펫퍼민트 kubectl 변경 125).

조정한 오탐:
- **애매한 운영 명령**: 처음엔 "명령 어딘가에 kubectl · docker가 있고 어딘가에 $가 있으면"이었다 — heredoc 스크립트 · `for` 반복이 수백 건 걸렸다. **동사 자리**가 변수 · 명령 치환일 때만(`kubectl $VERB`, `docker $(…)`, `eval`)
- **비밀 파일(Bash)**: heredoc 본문의 `.env` 글자, 파이썬 `x.key`, `kubectl get secret`의 secret, `source ./.env`(펫퍼민트 76건 대부분)가 걸렸다. heredoc 본문을 빼고, 경로처럼 생긴 토큰만, **내용을 찍거나 옮기는 명령의 인자일 때만**(cat · grep · cp · curl -d @ …). `.env.example` 같은 견본은 제외
- **작업 트리 밖 쓰기**: 세션 scratchpad(54건)와 CC 자신의 계획 · 메모리 파일(`~/.claude/plans/`, `~/.claude/projects/*/memory/`)은 안쪽으로
- 설정 파일(`~/.claude/settings.json` 등)은 쓰기만 묻는다(읽기는 괜찮다)

## 검증 (probe, 포먼 저장소 아래, enforce)

| 시험 | 결과 |
|---|---|
| `git status` | hook이 자동 승인(`accept / hook`) |
| `rm -r junk-a` → 브라우저 승인 | 승인 대기 #1 → 0.4초 뒤 승인 → 실행 |
| `rm -r junk-b` → 브라우저 거부 | #2 → 거부 이유가 모델에 → 폴더 그대로 |
| `rm -r junk-c` → 터미널에서 먼저 Yes | #3 → `terminal`(CC 기록 `accept`), 3.2초, 기다리던 hook이 풀림 |
| 텔레그램 | 세 건 모두 `[포먼] 🔐 승인 대기 · Bash / rm -r junk-… / 이유: rm-재귀 — …` |
| 로그 | `ask foreman[enforce] Bash rm -r junk-b — rm-재귀: …`, `승인 #2 → denied (browser): …` |

## 시험에서 찾은 것

- **터미널 응답과 기다리던 쪽이 둘 다 기록하는 경주** — 먼저 쓴 쪽이 터미널 결정 값 없이 행을 닫았다. 결정은 기다리던 쪽 한 곳에서만 쓴다
- **TOML 작은따옴표 문자열 안의 `'`** — 정규식(`["']`)이 문자열을 끊었다. 따옴표 세 개짜리로
- **TOML 표 머리말 앞에 둔 키는 앞 표에 들어간다** — `bash_secret_readers`가 `[ask.ambiguous]`에 들어가 0개로 읽혔고, 비밀 파일 규칙이 조용히 꺼졌다. 테스트가 잡았다
- `.env.db.example` — 바로 뒤의 `.example`만 제외해서 걸렸다. 끝이 견본 접미사인 것은 모두 제외

## 설계와 달랐던 점

- **"승인을 매번 누른다"** → auto mode라 20일에 19번. 이 단계는 귀찮음보다 **위험한 것을 막는** 쪽이 크다
- **"애매하면 ask"** → 규칙에 없는 모든 것을 ask로 하면 수천 건. **위험한 명령의 동사가 애매할 때 ask**, 평범한 작업은 pass(CC가 지금처럼). `unmatched = "ask"`로 바꿀 수 있다
- **"PreToolUse에서 allow / ask"만** → 승인 창이 뜬 뒤의 결정은 PermissionRequest hook이다. 브라우저 승인은 이것으로
- **Write 작업 트리 밖 ask** → Edit · MultiEdit · NotebookEdit도 밖이면 ask. 안쪽 Write는 규칙에 없음(pass)
- **프로젝트별 규칙** → 지금은 mode · unmatched · wait만 프로젝트별. 규칙 목록 자체를 프로젝트별로 더하는 것은 필요해지면

## 판단 근거

- **pass는 지금보다 넓히지 않는다** — 브리지가 정하지 않으면 CC의 원래 판단이 그대로다. 브리지가 꺼져 있을 때도 같다
- **위험 규칙은 따옴표 안까지** — `vagrant ssh m-k8s -c 'kubectl apply …'`처럼 다른 명령 안에 넣어 실행하는 것이 이 환경의 실제 모양이다
- **allow는 조각마다 증명** — 하나라도 확실하지 않으면(리다이렉트 · 명령 치환 · `git -c` · `--output`) allow하지 않는다
- **런슈즈 · 펫퍼민트는 observe로 시작** — hook은 실행 중인 세션에 다음 도구 호출부터 걸린다(3단계 실측). 하루 11~18건의 승인 창이 갑자기 생기므로, 쌓인 판정을 보고 사용자가 enforce로 바꾼다
- **승인 대기 10분** — 그 뒤엔 터미널 창만 남는다. 브라우저 결정을 기다리는 동안에도 터미널은 막히지 않는다(실측)

## 아직 안 한 것

- 런슈즈 · 펫퍼민트 enforce 전환 — observe 판정이 쌓인 뒤 사용자 결정(`event` `approval_req` 중 `payload.decision = 'ask'`)
- 서브에이전트의 도구 호출 — hook은 같은 경로로 오지만(입력에 agent_id), probe로 따로 확인하지 않았다
- 규칙 목록의 프로젝트별 덧붙이기, 자주 묻는 명령을 "이번 세션 동안 허용"하는 기능
