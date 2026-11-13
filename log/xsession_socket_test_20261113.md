# 세션 간 메시지 실험 1단계 — 브리지가 세션 소켓으로 글을 넣을 수 있나 (2026-11-13)

> 상태: ✓ 재기만 끝남(코드 · 설정 바꾸지 않음). 2026-11-13 20:20 ~ 20:41 KST, CC 2.1.323, 시험 세션 350 하나

**결론: 토큰 없이 들어간다. 받는 세션이 auto 모드면 보류 없이 바로 배달된다. 고르기 창이 떠 있어도 메시지가 창에 먹히지 않는다 — 창에 따라 「창이 닫힐 때까지 큐에서 기다림」 또는 「창 뒤에서 바로 처리」다.** 다만 배달됐을 때 보낸 쪽에 오는 답이 없고, 잘못된 프레임은 흔적 없이 버려진다. 그래서 2단계는 받는 쪽 대화 기록의 도착 줄로 확인하는 장치와 함께 가야 한다.

## 한 것

- 받는 세션: `POST /api/spawn`으로 sonnet 시험 세션 350(`xsock-test-recv`)을 저장소 밖 스크래치 폴더에 띄움(프로젝트 밖이라 관리자 중계가 붙지 않는다). auto 모드로 떴다
  - 처음 쓰는 폴더라 CC 신뢰 확인 창이 떴다 — 내가 만든 스크래치 폴더라 tmux로 「Yes, I trust this folder」를 골랐다
- 소켓 주소 찾기: `ss -xlp`에서 그 세션 PID(1262204)가 듣는 `/tmp/cc-socks/1262204.sock`. `~/.claude/sessions/1262204.json`의 `messagingSocketPath`도 같은 값이다(비밀값 아님). **환경변수(`/proc/<pid>/environ`)는 읽지 않았다**
- 보낸 것: 스크래치의 파이썬 스크립트(유닉스 소켓에 JSON 한 줄). **토큰(auth) 줄은 한 번도 보내지 않았다**
- 메시지 줄 꼴은 문서에 없어 CC 실행 파일 안의 문자열(받는 쪽 처리 코드)에서 찾았다:
  - `{"type":"user","message":{"content":"…"}, "from"?: "uds:<답 받을 소켓>", "msg_id"?: "<uuid>", "session_id"?: "<받는 세션 id>", "priority"?}`
  - 진짜 `SendMessage`는 본문을 `<cross-session-message from="uds:…" from-name="이름" from-mode="prompting">\n본문\n</cross-session-message>`로 감싸 보낸다(11-12 런슈즈 기록에서 확인). `from-mode` 값은 `bypass` · `prompting` 둘뿐이다
- 보낸 쪽 「답 받는 소켓」: 배달 상태를 받으려고 시험 스크립트가 `/tmp/cc-socks/xsock-probe-<pid>.sock`을 잠깐 열고 프레임 `from`에 넣었다. 끝날 때 지웠다(남은 것 0)

## 다섯 가지 결과

### 1. 토큰 없이 들어가는가 — 들어간다

- 쉬는 세션에 토큰 · 이름표 없이 보냄(시험 1): **보류 · 거절 없이 바로 새 턴**, 2초 만에 「받음 1」
- 까닭(문서 + 실측): 리눅스에선 토큰 줄이 선택이다. auto 모드는 「묻는 쪽」으로 묶이고, 묻는 쪽 받는 세션은 보낸 쪽이 「건너뜀(bypass)」이라고 밝힐 때만 보류한다
- 기록 줄 `origin`에 `verifiedPeerPid`(보낸 파이썬 프로세스 PID) · `verifiedPeerProcStart`가 붙는다 — 토큰 없이도 CC가 보낸 프로세스를 소켓 상대 PID로 확인한다
- 보류 경로도 재 봤다(시험 6b — 본문 이름표에 `from-mode="bypass"`를 일부러 붙임, 시험 세션에만):
  - 화면에 「Held message from another session … [verified pid 1337218] (peer claims name: foreman-bridge)」 승인 창, 고르기 `❯ Deny` / `Deliver this message to Claude`
  - 승인하지 않고 두니 **300초 뒤 만료**(문서의 기본 5분과 같음)
  - 브리지는 `bypass`라고 밝힐 까닭이 없다 — 이 경로는 2단계에서 쓰지 않는다
  - 값을 잘못 쓰면(`bypassing`, 시험 6) 이름표 전체가 해석되지 않아 보류 없이 배달되고 `origin.name`이 빠졌다

### 2. 쉬는 중 · 일하는 중 · 고르기 창 — 창에 먹히지 않는다

| 받는 쪽 상태 | 결과 | 기록 줄 |
|---|---|---|
| 쉬는 중(시험 1 · 2) | 바로 새 턴 | `enqueue` → 같은 ms대 `dequeue` → `user`(isMeta) |
| 일하는 중 — 앞에서 30초 도는 Bash(시험 3b) | 도구 결과가 돌아온 **같은 턴 안에서** 읽음(새 턴 아님). 모델: 「명령이 끝난 뒤에 봤습니다」 | `enqueue`(11:28:38) → `remove`(11:29:07, 도구 결과 직후) + `attachment` `queued_command`(origin peer) |
| `/model` 고르기 창(시험 4) | **창에 먹히지 않음**(선택 그대로, 닫을 때 「Kept model as Sonnet 5.5」). 큐에서 105초 기다리다 Esc로 닫자 바로 새 턴 | `enqueue`(11:29:47)만 → Esc 뒤 `dequeue`(11:31:32) |
| `/autocompact` 창(시험 8) | 위와 같음. 30초 기다리다 Esc 뒤 새 턴, 설정 안 바뀜 | `enqueue`(11:39:33) → `dequeue`(11:40:03) |
| 보류 승인 창(시험 7 — 6b 창이 떠 있는 채로 보통 메시지) | **창 뒤에서 바로 처리**되어 답까지 함(화면은 창에 가려 안 보임) | `enqueue` → 4ms 뒤 `dequeue` → 답 |

- 무엇으로 쟀나: 오늘 서기에 떴던 「We recommend compacting earlier … Autocompact at 400k?」 안내 창은 일부러 띄울 수 없었다. 같은 꼴(↑/↓ · ←/→ · enter · esc)인 `/model`과, 같은 설정을 고르는 `/autocompact` 명령 창으로 쟀다
- 고르기 창이 떠 있는 동안 `~/.claude/sessions/<pid>.json`의 `status`는 `waiting`이었다(`busy`가 아님)
- 본문 첫 글자: `/model` · `!echo …`로 시작하는 본문을 보내도 **명령 · bash 모드로 실행되지 않고** 모델에게 글로 갔다(받는 쪽 코드가 `skipSlashCommands:true`로 넣는다). `!` 본문은 모델이 판단해 Bash 도구로 실행했다 — 보통 승인 규칙을 거친다

#### 안내 창 경우의 결론

- **메시지가 창에 들어가 엉뚱한 선택이 되는 일은 없다** — 붙여넣기의 실패 꼴(끝내기 명령이 창으로 들어감)은 소켓으로는 생기지 않는다
- 다만 명령 창(`/model` · `/autocompact`) 꼴이면 **창이 닫힐 때까지 배달이 미뤄진다**. 사람이 없으면 무기한 기다린다(60초 넘게 둬도 사라지지 않았고 만료도 없었다). 오늘의 Autocompact 안내 창이 「미룸」 쪽인지 「창 뒤에서 처리」 쪽인지는 그 창으로 재지 못해 **미검증**이다
- 그래서 조용히 멈추지 않게 하려면: `enqueue`는 있는데 `dequeue` · `remove`가 N초 안에 없고 `status`가 `waiting`이면 「그 세션에 창이 떠 있어 메시지가 기다리는 중」으로 알린다

### 3. 받는 쪽 대화 기록 꼴 — `xmsg.py`가 보는 줄과 같다, 새 턴 첫 글은 「Another Claude session sent a message:」

- 도착: `{"type":"queue-operation","operation":"enqueue","content":"<보낸 본문 그대로>"}`
  - 이름표를 붙이면 `content`가 `<cross-session-message from=… from-name=…>\n본문\n</cross-session-message>` — 진짜 `SendMessage`와 같은 꼴이라 `xmsg.py`의 `LIKE '%cross-session-message%'` · `body_of`가 그대로 맞는다
  - **이름표 없이 보내면 `content`가 맨 본문**이다 — `xmsg.py`의 도착 조회(`LIKE '%cross-session-message%'`)에 걸리지 않는다
- 읽음: 쉬던 세션은 `dequeue`(content 없음), 일하던 세션은 `remove`(content 있음) + `attachment` `queued_command` — `xmsg.py` 독스트링의 「dequeue 또는 delivered · remove」와 같다
- 새 턴 첫 `user` 줄:
  - `isMeta: true`, `turnOrigin: "peer"`, `promptSource: "system"`, `queueSkipSlashCommands: true`
  - `origin: {"kind":"peer","from":"uds:…" 또는 "unknown","verifiedPeerPid":…,"verifiedPeerProcStart":"…","msg_id":"…","name":"foreman-bridge","body":"본문"}` — `name`은 이름표가 있을 때만, `msg_id`는 프레임에 넣었을 때만
  - `message.content` = `"Another Claude session sent a message:\n" + 본문(이름표 포함) + "\n\nThis came from another Claude session — not typed by your user …"`(동료 요청으로 다루라는 안내가 뒤에 붙는다)
- 적재기 `_origin`(`bridge/assembler.py`)이 가를 수 있는 표시:
  - 지금 코드로는 `isMeta` + `AGENT_MSG`(「Another Claude session sent a message」) → `agent_message`. `<agent-message from=` 꼴이 아니라 `FROM_RE`는 안 걸린다
  - 더 확실한 표시는 `turnOrigin == "peer"` · `origin.kind == "peer"` · `origin.verifiedPeerPid`(브리지 PID와 맞대면 「브리지가 넣은 것」으로 가를 수 있다)
  - **주의**: `_origin`은 머리 120자(`s.lstrip()[:120]`)에서 「[관리자 부탁 —」 · 「[작업 보고 —」를 찾는다. 소켓으로 넣으면 앞에 「Another Claude session sent a message:\n<cross-session-message from="uds:/tmp/cc-socks/…" from-name="…">」(약 100자 이상)가 붙어 그 머리가 120자 밖으로 밀린다 — 2단계에서 `manager_ask` · `relay` 가르기를 손봐야 한다
- 보류는 `queue-operation`이 아니라 `{"type":"system","subtype":"informational","content":"Held peer message — from uds:… [verified pid …] (peer claims name: …); preview: «…»"}` 한 줄로 남고, **만료는 받는 쪽 기록에 줄이 없다**

### 4. 보낸 이 이름 — 이름표를 달면 그 이름, 안 달면 이름 없음

- 이름표 없음(시험 1): 화면에 「Another Claude session sent a message:」 뒤 본문 전문과 안내 문단이 그대로 펼쳐진다. 기록 `origin.from = "unknown"`, `name` 없음
- 이름표 `from-name="foreman-bridge"`(시험 2~): 화면에 `› Message from @foreman-bridge: <본문 첫 줄> (ctrl+o to expand)` 한 줄. 기록 `origin.name = "foreman-bridge"`
- 이름은 **보낸 쪽이 적는 대로**다(확인 안 됨). 보류 창만 「(peer claims name: foreman-bridge)」로 「주장」이라고 밝히고, 확인된 것은 `verified pid`다

### 5. 버려졌을 때 알아챌 수 있나 — 배달 성공에는 답이 없고, 프레임 오류는 조용히 사라진다

| 경우 | 보낸 쪽(소켓) | 받는 쪽 기록 · 화면 |
|---|---|---|
| 배달됨(쉼 · 일함 · 창) | **아무 답 없음** — 받는 쪽이 바로 연결을 닫는다(EOF). 답 소켓에도 상태 줄이 오지 않았다 | `enqueue` … |
| 보류(6b) | 답 소켓으로 즉시 `{"type":"control","action":"peer_message_status","status":"held","reason":"…permission-mode parity…","orig_msg_id":"<보낸 msg_id>",…}` | `system` informational 한 줄 |
| 보류 뒤 만료(6b, 300초) | 답 소켓으로 `status":"expired"` | 줄 없음 |
| 세션 id 틀림(5a, `session_id` 칸) | 답 없음 | **흔적 0**(기록 바이트 0 늘어남, 화면 0) |
| JSON이 아님(5b) | 답 없음 | 흔적 0 |
| 본문 빈 것(5c) | 답 없음 | 흔적 0 |
| 소켓 없음(5d, 끝난 세션) | 연결 오류 `FileNotFoundError` | — |

- 답 소켓(`from`)을 주지 않으면 보류 · 만료도 보낸 쪽은 모른다
- 문서에 있는 「한꺼번에 많이 보내 받는 쪽 한도에 걸림」도 거절 사유다(재지 않음)
- 잡는 법: **보낸 뒤 몇 초 안에 받는 쪽 기록에 그 본문의 `enqueue` 줄이 없으면 「버려짐」**(실측 도착은 보낸 뒤 0.1초 안). 붙여넣기의 `find_delivery`(보낸 글이 기록에 나타나는지 보는 것)와 같은 방식이고, `msg_id`를 넣으면 `origin.msg_id`로 맞댈 수 있다(단 `enqueue` 줄에는 msg_id가 없어 본문으로 짝짓는다). 그다음 `dequeue` · `remove`까지 걸리는 시간으로 「창 때문에 기다림」을 가른다

## 붙여넣기 전에 막는 다섯 가지 — 소켓 길에서 필요한 것

| 지금 막는 것(`bridge/inject.py`) | 소켓 길 | 까닭 |
|---|---|---|
| 살아 있는 CC 프로세스가 아님 | **필요** | 세션 → PID → `sessions/<pid>.json` `messagingSocketPath`로 주소를 얻는다. 끝난 세션은 소켓 파일이 지워진다(실측) |
| 멈춤(T) | **필요(재지 않음)** | 멈춘 프로세스의 듣는 소켓은 커널이 연결을 받아 둘 수 있어, 보낸 쪽은 성공으로 보고 아무도 처리하지 않을 수 있다. 멈춘 세션은 건드리지 않는 규칙이라 재지 않았다 |
| tmux 밖 세션 | 필요 없음 | 소켓은 tmux와 상관없다. 대신 tmux 밖 세션에도 보낼 수 있게 되니 보낼 범위를 따로 정해야 한다 |
| pane 포그라운드가 claude가 아님 | 필요 없음 | 셸로 잘못 실행될 길이 없다. 본문은 `/` · `!`로 시작해도 명령이 되지 않는다(실측) |
| 그 pane의 claude가 이 세션이 아님 | 바뀜 | 「그 세션 PID의 `messagingSocketPath`」를 `ss -xlp`가 같은 PID로 듣는지로 맞댄다 |

- 붙여넣기 앞 Esc(`clear_screen`)와 첫 글자 보호(`guarded`)도 소켓 길에선 필요 없다
- 관찰(고치지 않음): `/model` 창 화면에는 `   ❯ 4.  Sonnet 5.5 ✔` 줄이 있다. `prompt_showing()`은 `lstrip()` 뒤 `❯`로 시작하는 줄을 입력 줄로 보므로 **고르기 창을 입력 줄로 착각해 Esc를 보내지 않고 붙여 넣을 수 있다**. 오늘 Autocompact 창에 끝내기 명령이 들어간 길이 이것인지는 그 창 화면으로 확인하지 못했다(미검증)

## 2단계(관리자끼리 부탁부터)로 가도 되나 — 가도 된다, 걸리는 것 다섯

1. **도착 확인 장치 먼저**: 배달 성공에 답이 없으니 받는 쪽 기록의 `enqueue`(몇 초 안) · `dequeue`/`remove`(N초 안)를 보고 못 찾으면 알린다. 이것 없이 소켓으로 바꾸면 5a~5c처럼 조용히 사라질 수 있다
2. **이름표를 꼭 단다**(`from-name`, `from-mode`는 빼거나 `prompting`) — 안 달면 화면에 이름이 없고 `xmsg.py` 도착 조회에 걸리지 않는다. `bypass`는 쓰지 않는다
3. **답 소켓**: 보류 · 만료 · 거절 상태를 받으려면 브리지가 자기 받는 소켓을 열어 `from`에 넣어야 한다. 받는 세션 설정이 `crossSessionInbound = "hold"`거나 권한 건너뜀 세션이면 보류된다 — 우리 세션은 auto라 지금은 보류되지 않는다
4. **적재기 출처 가르기**: `_origin`의 머리 120자 검사가 감싼 머리 때문에 빗나간다. `turnOrigin == "peer"` + `origin.verifiedPeerPid == 브리지 PID`로 가르는 쪽이 낫다
5. **창 때문에 미뤄짐**: 메시지는 안전하지만 명령 창 꼴에선 사람이 닫을 때까지 기다린다. 「기다리는 중」 알림이 있어야 조용한 고장이 아니다. 오늘 Autocompact 안내 창으로 직접 재는 것은 그 창이 다시 뜰 때 해 볼 일이다

## 쓴 시험 세션

- **350** `xsock-test-recv`(sonnet, 스크래치 폴더) — 시험 끝에 `POST /api/sessions/350/action {"action":"exit"}`로 끝냄(tmux 닫힘, 소켓 지워짐 확인)
- **숨기기(`hidden_reason='test'`)는 하지 않았다** — 숨기는 API가 없고(이전 기록은 DB를 직접 고쳤다), 일감이 「없으면 관리자에게 부탁」이라 관리자에게 넘긴다

## 규칙

- 규칙 위반 없음
- 판단으로 한 것(밝혀 둠):
  - 보류 경로를 보려고 이름표에 `from-mode="bypass"`를 넣어 보냈다(시험 세션에만, 승인하지 않고 만료되게 둠). 토큰은 쓰지 않았다
  - 배달 상태를 받으려고 CC 소켓 폴더 `/tmp/cc-socks`에 시험용 소켓을 잠깐 열었다가 지웠다
  - 메시지 줄 꼴을 CC 실행 파일 안 문자열에서 읽었다(문서에 없어서). 다른 프로세스의 환경변수 · 토큰은 읽지 않았다
  - 문서를 읽힌 하위 에이전트(web-fetch)에게 준 지시문은 영어였다 — 사람에게 보이는 진행 글 · 답은 모두 한국어로 썼다
