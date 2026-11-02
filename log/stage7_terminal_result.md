# 로드맵 7단계 — 터미널 패널 결과

- **실행일**: 2026-11-02
- **상태**: 구현 · 시험 끝, 브라우저에서 쓰는 확인은 사용자 차례(아래 "남은 것")
- 설계는 README 3.9 "만든 모양"에 있다. 여기는 한 일 · 설계와 달랐던 점 · 판단 근거 · 시험에서 찾은 것

## 한 일

| 무엇 | 어디 |
|---|---|
| ttyd 1.7.7 설치(sudo 없이) | `.tools/ttyd` — GitHub 릴리스 정적 바이너리, `SHA256SUMS`로 확인(`ttyd.x86_64: OK`). `.gitignore` |
| 셸 | tmux `foreman-shell` ← `bash --rcfile deploy/shell/foreman-bashrc`(`~/.bashrc`를 읽고 기록 훅만 더한다) |
| 기록 훅 | `scripts/foreman-shell-hook.sh` — PROMPT_COMMAND가 명령 · 종료 코드 · 위치를 `/hooks/shell`로(hook 토큰, 2초, 항상 exit 0) |
| ttyd 관리 · 부탁 감지 · 미리 채우기 · 결과 전달 · 마스킹 | `bridge/terminal.py`(TerminalManager) |
| 길 | `bridge/api/terminal.py` — `/api/terminal/*`(쿠키 발급 · 상태 · 부탁 닫기 · 다시 채우기), `/terminal/*` HTTP · WS 넘김, `/hooks/shell` |
| 화면 | `static/js/terminal.js`(아래 접이식 패널, 부탁 배너, iframe), `store.js`(terminal 상태 · `terminal_request` · `terminal_result` · 셸 이벤트는 카드로 안 감) |
| 이벤트 | `source=shell` · `type=shell_cmd`(친 명령), `term_request` · `term_result`(부탁한 세션 쪽) |
| 셸 세션 행 | `character_session` id 169, `type='shell'`, 포먼 프로젝트의 포먼에. 대시보드 · `/api/sessions`는 `type='agent'`만 |
| 시험 | `tests/test_terminal.py` 24개 — 감지 · 채우기 · 마스킹 · 맞춰 보기 · 출력 범위, 시험용 tmux 셸에서 채우기 → 커서 위치에 입력 → 결과, 실제 ttyd를 브리지로 넘겨 쿠키 · Origin · HTTP · WS 왕복. 전체 139개 통과 |

실서버 확인: 브리지를 다시 띄우자 ttyd가 소켓에 붙고(`ss`에 TCP 리슨 없음), 셸에 친 `echo live-check --password …`가 `echo live-check --password «masked»`로 기록됐다. `/terminal/`은 쿠키 없이 401, 쿠키로 200.

## 설계와 달랐던 점

| 설계 · 지시 | 한 것 | 이유 |
|---|---|---|
| ttyd를 127.0.0.1에 묶는다 | **UNIX 소켓**(`.run/ttyd.sock`, 디렉토리 0700)에만 묶는다. TCP 포트 없음 | 127.0.0.1 포트는 이 PC의 다른 사용자 · 다른 프로세스가 붙을 수 있고, ttyd는 자체 인증이 없다(`-c`는 Basic 인증뿐). 소켓 + 0700이면 내 계정만 닿고, 브라우저는 브리지(127.0.0.1)의 쿠키 검사를 거쳐야 한다. "밖에 열지 않는다"는 지시보다 좁다 |
| ttyd 설치에 sudo | apt 대신 릴리스 바이너리 | 버전이 같고(1.7.7) sudo 왕복이 없다. 체크섬으로 확인. 지우기도 디렉토리 하나 |
| 결과는 "해당 캐릭터에게" | **부탁한 세션에** 3단계 주입으로 | 지금은 모든 세션이 포먼 캐릭터에 묶여 있다(임시, 2.4). 부탁한 것은 세션이다. 주입이 안 되는 세션(tmux 밖 — 지금의 런슈즈 · 펫퍼민트)은 배너에 결과(마스킹)만 보이고 `term_result`에 남는다 |
| 브리지가 ttyd를 따로 띄운다(별도 유닛) | 브리지가 자식으로 띄우고 죽으면 다시 띄운다(1→30초) | 유닛이 하나 더 늘지 않는다. 브리지를 다시 띄워도 tmux 셸은 남는다(ttyd만 다시 붙는다) |

## 판단 근거

- **쿠키를 쓰는 이유** — iframe 안의 xterm.js는 Authorization 헤더를 붙일 수 없다. 그래서 API 토큰으로 `POST /api/terminal/session` → 무작위 쿠키(HttpOnly · SameSite=Strict · Path=/terminal, 12시간, 브리지 메모리에만). 쿠키만으로는 다른 사이트의 WS 연결을 막지 못하므로(cross-site WebSocket hijacking) **Origin = Host**를 따로 본다. 화면은 `X-Frame-Options: SAMEORIGIN` — 다른 사이트가 틀에 넣어 클릭을 훔치지 못하게
- **기록은 PROMPT_COMMAND로** — WS를 지나는 키 입력을 읽으면 암호까지 지나간다(sudo 암호 입력도 같은 길). 셸이 "실행한 명령"만 알려 주면 암호 프롬프트에 친 글자는 기록에 들어오지 않는다. `HISTFILE=`(디스크에 남기지 않음), `HISTCONTROL=`(~/.bashrc의 ignoreboth면 공백으로 시작한 명령 · 반복이 빠진다 — 기록을 피하는 길이 된다)
- **명령줄에 들어간 비밀** — 미리 채우기는 비밀번호 자리를 비워 둔다. 거기 치면 명령줄에 남는다(ps · tmux 화면). 기록은 마스킹되지만, `docker login`은 `-p`를 지우고 물을 때 치는 편이 안전하다 — 사용자가 고를 일이라 둘 다 된다
- **부탁 감지는 세 조건을 모두** — 코드 안의 명령 + 사람이 쳐야 하는 명령 + 부탁하는 말. 설명 · 기록 속 `sudo …`(예: "어제 `sudo apt install ttyd`로 깔았다")까지 패널을 올리면 귀찮아서 안 쓰게 된다. `! 명령`은 CC가 사용자에게 권하는 모양이라 그 자체로 부탁
- **승인 정책은 터미널에 안 걸린다** — 정책은 CC의 도구 호출(PreToolUse)에만 걸리고, 이 셸은 CC가 아니다. 사람이 치는 것은 막지 않고 남긴다

## 시험에서 찾은 것

- **gzip 이중 해석** — ttyd는 index를 gzip으로 준다. httpx가 풀어 준 본문에 `Content-Encoding: gzip`을 그대로 붙여 넘겨 브라우저 쪽에서 깨졌다(시험이 잡음). 받은 바이트 그대로(`aiter_raw`) 넘긴다
- **history 번호 떼기** — 처음 쓴 `${cmd#*[0-9]}`는 숫자 한 글자만 뗀다("123  ls" → "23  ls"). 정규식으로
- **작업 알림** — PROMPT_COMMAND에서 `&`로 띄우면 대화형 셸이 `[1] 1234` · `Done`을 찍는다. 괄호 안에서 띄운다
- **시험이 운영 자원을 건드릴 뻔** — 기존 앱 시험(`test_app_db.py`)은 운영 설정으로 앱을 띄운다. 터미널이 켜진 채면 운영 tmux 셸 · ttyd 소켓을 건드린다 → 그 시험에서는 끄고, 터미널 시험은 시험 전용 tmux 세션 · 임시 소켓 · `foreman_test`로

## 남은 것

- **브라우저에서 쓰기** — 집 PC 대시보드에서 패널을 열어 실제로 sudo를 쳐 보는 것(화면 · 초점 · 크기 · 휴대폰). 사용자 차례
- **실제 CC 턴으로 부탁 → 채우기 → 결과** — 조각마다 시험했고(감지는 글, 채우기 · 결과는 시험 tmux 셸), 실서버에서 CC가 진짜로 부탁하는 턴은 아직 없다. 주입이 되는 세션은 지금 tmux 안의 포먼(`cc-foreman`)뿐
- **출력 범위** — 명령을 친 프롬프트 줄을 화면에서 찾는다. `clear` · 전체 화면 프로그램 · 3,000줄 넘는 출력이면 "범위를 못 찾아 마지막 줄들"로 간다(전달문에 그렇게 적힌다)
- **브리지 systemd 유닛** — 아직 손으로 띄운다. 유닛을 만들면 ttyd도 같이 뜬다
