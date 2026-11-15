# 노션 기술문서 목차안, 포트폴리오 편 목록안 (조사, FOREMAN, 2026-11-15)

관리자 410의 조사 일감(사용자 지시). 글은 쓰지 않았다. 안만 낸다. 사용자가 정한 뒤 서기가 쓴다.

읽은 것: CLAUDE.md, `docs/12_scribe.md` 0절, `log/foreman-7_scribe_design_20261115.md` 4-1, 4-2, 5-3, README 3절(아키텍처)과 5, 6절, docs 절 머리 전부, `bridge/` 모듈 docstring 전부(api, db, transcript 포함), `bridge/static/js` 머리 주석 전부, `bridge/main.py` 앱 조립과 페이지 경로, `migrations/` 표 이름, `config/*.toml` 머리, `scripts/`, `deploy/`, `tools/`, `portfolio/` 10편 절 머리. 서브에이전트는 쓰지 않았다.

---

## 사용자가 정할 것

1. **「브리지」를 한 편으로 둘까, 하는 일별로 맨 위에 펼칠까.** 사용자 예는 「02 브리지」 하나였다. 코드를 보면 화면(`bridge/static`)과 DB 스키마(`migrations/`) 말고는 모두 `bridge/` 파이썬이다(86파일, 약 26,000줄). 「02 브리지」 한 편 아래에 모두 넣으면 하위가 열다섯 개가 넘는다. **추천: 펼친다.** 「01 전체 구조」가 브리지의 지도 노릇을 하고, 맨 위는 브리지가 하는 일(모으기, 지켜보기, 넣기, 막기, 띄우기, 합치기 …)로 나눈다. 아래 안은 이 추천을 따른다
2. **편 수.** 아래 안은 맨 위 18편, 하위 31편, 모두 49쪽이다. 줄이려면 「줄인 안」(아래 2절 끝, 맨 위 14편 하위 14편, 28쪽)을 쓴다. 노션은 하위 페이지가 접혀 있어 많아도 읽기 길은 맨 위 18줄이다
3. **합칠 후보.**
   - 「03 세션 지켜보기」와 「04 세션에 글 넣기」: 둘 다 「세션 하나를 다루는 법」이다. 합치면 김
   - 「12 알림」을 따로 둘까, 각 편에 흩을까. 알림 규칙(`config/notify.toml`, `bridge/notify.py`)은 한 곳이라 따로 두기를 권한다
   - 「14 사용량과 모델」과 「07 세션 띄우기」의 모델 고르기: 모델 고르기는 띄울 때 정해지지만 까닭(정답과 맞댄 모델 정하기, 비용)은 사용량 편이 맞다. 추천은 14에 둔다
4. **포트폴리오와 노션의 경계.** 추천: 포트폴리오는 「이 화면이 무엇을 해 주나」까지만, 「왜 이렇게 만들었나, 무엇을 버렸나, 무엇에 막혔나」는 노션. 포트폴리오 편 끝에 노션 편 링크 한 줄. 지금 `portfolio/` 10편에는 판단, 겪은 문제, 숫자가 깊게 들어 있다. 새 기준이면 그 대부분이 노션 재료로 간다(4절 표)
5. **화면이 없는 이야기를 포트폴리오에 둘까.** 배치와 보안(지금 `portfolio/08`), 압축 손실 재기(지금 `03`의 앞 절), 관찰 파이프라인의 적재(지금 `07`)는 화면이 없다. 화면 축이면 빠진다. 추천: 포트폴리오 첫 편 「한눈에」에 두세 줄로만 두고 깊이는 노션에
6. **포트폴리오 편 수.** 아래 안은 16편. 합칠 후보 셋을 합치면 13편(4절 끝)
7. **「17 시험과 배포」를 둘까.** `tests/` 125파일이 어느 편에도 안 든다(3절). 편마다 「어떻게 시험하나」 한 단락으로 흩을 수도 있다. 추천: 짧은 편 하나 + 편마다 한 줄

---

## 1. 나무 맨 윗줄

```
notion/00_foreman.md         00 FOREMAN이란
notion/01_structure.md       01 전체 구조              (하위 2)
notion/02_ingest.md          02 기록 모으기             (하위 4)
notion/03_watch.md           03 세션 지켜보기
notion/04_input.md           04 세션에 글 넣기
notion/05_approval.md        05 승인                   (하위 3)
notion/06_roles.md           06 역할과 권한             (하위 3)
notion/07_sessions.md        07 세션 띄우기와 따로 작업
notion/08_merge.md           08 합치기                 (하위 2)
notion/09_handoff.md         09 인계와 압축 손실        (하위 4)
notion/10_dispatcher.md      10 교장과 관리자           (하위 4)
notion/11_scribe.md          11 서기와 문서             (하위 4)
notion/12_notify.md          12 알림
notion/13_pipeline.md        13 CI/CD 인과 체인
notion/14_usage.md           14 사용량과 모델
notion/15_screen.md          15 화면                   (하위 5)
notion/16_db.md              16 DB                     (하위 2)
notion/17_tests.md           17 시험과 배포
```

차례의 뜻: 00, 01은 전체. 02 ~ 04는 「세션 하나를 보고 다루기」(관찰과 입력). 05, 06은 「막기」. 07 ~ 09는 「세션의 한살이」(띄우기, 합치기, 넘기기). 10, 11은 「사람 대신 시키는 캐릭터」(교장, 서기). 12 ~ 14는 「바깥과 잇기」(알림, CI/CD, 사용량). 15, 16은 바탕(화면, DB). 17은 돌리기.

크기 어림: 짧음 = 노션 한 화면 남짓, 보통 = 두세 화면, 김 = 그 이상. 「김」으로 어림한 편은 모두 하위로 나눴다.

---

## 2. 편마다

### 00 FOREMAN이란 — `notion/00_foreman.md`
- 다루는 것: 여러 Claude Code(CC) 세션을 한 화면에서 보고 다루는 관제실이다. 만든 까닭은 「조용한 고장」을 잡는 것이다(milvus-port-forward 56만 번 재시작을 한 달 넘게 몰랐다). 캐릭터와 세션은 다르다, 캐릭터는 인프라의 거울이다, 역할은 바뀐다는 세 생각. 다루는 프로젝트 넷(FOREMAN, 런슈즈, 펫퍼민트, 인프라)
- 포기한 것: 별도 headless 세션으로 돌리기(「내가 보는 것과 실제가 같아야 한다」가 전제라서 버렸다)
- 다루는 곳: README 1, 2절, CLAUDE.md 맨 위 절, `docs/01_kickoff.md`
- 크기: 짧음 ~ 보통. 나누지 않는다

### 01 전체 구조 — `notion/01_structure.md`
- 다루는 것: 브리지(FastAPI 프로세스 하나)가 입력(tmux), 출력(트랜스크립트), 상태(hook, /proc), 승인, 수명(tmux, worktree), 적재(MySQL), 알림(텔레그램), 웹훅을 한 곳에서 맡는 그림. 입력과 출력의 길이 다른 까닭(CC는 TUI라 화면을 긁으면 깨진다). 브리지가 뜰 때 붙는 뒤 작업 스무 개 남짓(`bridge/main.py` lifespan)의 지도. 아래 편들로 가는 길잡이
- 다루는 곳: `bridge/main.py`, `bridge/__main__.py`, `bridge/config.py`, README 3절 그림과 3.1 머리
- 크기: 보통. 하위 둘

#### 01-1 어디에 두었나 — `notion/01_structure/01_placement.md`
- 다루는 것: 브리지와 DB를 클러스터 밖 호스트에 둔 까닭(감시하는 쪽과 감시받는 쪽의 장애 범위를 나눈다). 기존 MySQL에 얹지 않은 까닭. 브리지를 파드로 못 띄우는 까닭(k8s 노드가 libvirt VM이라 호스트 /proc, tmux 소켓이 안 보인다). 수집부와 UI를 나누지 않은 까닭. 밖에 열지 않은 결정(뚫리면 서버 셸이 열린다, 공유 서버다, 필요한 것은 텔레그램으로 이미 온다). 열 때의 조건(읽기 전용 화면, 패스키나 mTLS)
- 포기한 것: Cloudflare 터널 공개(브리프를 다 써 놓고 열지 않았다)
- 다루는 곳: `deploy/systemd/foreman-bridge.service`, `deploy/mysql/compose.yml`, `deploy/mysql/my.cnf`, `deploy/mysql/backup.sh`, README 3.12, 3.13, `docs/02_cloudflare_tunnel.md`
- 크기: 보통

#### 01-2 브리지가 뜨는 차례 — `notion/01_structure/02_startup.md`
- 다루는 것: 설정을 읽는 차례(`.env.*` 비밀값과 기본값, 같은 이름 환경 변수로 덮기), 뒤 작업을 켜는 차례와 꺼질 때 거두기, 한 작업이 실패해도 나머지는 뜨게 한 것, 다시 띄우기 전에 승인 대기 0을 보는 까닭(승인 대기가 끊긴다), 화면 파일을 매번 다시 확인하게 한 까닭(옛 store.js 캐시로 연결이 안 됐다)
- 다루는 곳: `bridge/main.py`, `bridge/config.py`, `bridge/api/health.py`, `bridge/uiver.py`
- 크기: 짧음. 01에 합쳐도 된다

### 02 기록 모으기 — `notion/02_ingest.md`
- 다루는 것: CC가 남기는 흔적 둘(트랜스크립트 JSONL, hook)이 어떻게 한 줄의 DB 기록(turn, message, subagent_run, event)이 되는가의 전체 흐름. 생산자 → 대기열 → 적재(쓰는 쪽 하나) → WS
- 다루는 곳: `bridge/transcript/`, `bridge/assembler.py`, `bridge/bus.py`, `bridge/store.py`, `bridge/api/hooks.py`
- 크기: 보통(개요). 하위 넷

#### 02-1 트랜스크립트 읽기 — `notion/02_ingest/01_transcript.md`
- 다루는 것: 경로 규칙, 서브에이전트 파일, inotify를 파일이 아니라 디렉토리에 건 까닭, offset과 inode로 이어 읽기, `api-request` 줄 미리 거르기(561MB 중 76%), 개행 없는 마지막 줄 보류, 순서를 timestamp가 아니라 파일 순서와 parentUuid로 잡은 까닭(49,454줄 중 4,975줄이 거꾸로, 최대 521초). 도구 결과 본문은 DB에 넣지 않고 누를 때 파일 끝에서 거꾸로 찾는다(730MB 파일)
- 다루는 곳: `bridge/transcript/watcher.py`, `reader.py`, `lookup.py`, `bridge/ingest.py`(백필 측정 도구), README 3.1 「트랜스크립트 읽기」, 3.11
- 크기: 김

#### 02-2 CC hook 받기 — `notion/02_ingest/02_hooks.md`
- 다루는 것: hook 여덟 종류, hook 스크립트가 CC를 절대 막지 않게 한 약속(2초, 출력 없음, 늘 exit 0, UserPromptSubmit의 stdout은 모델 맥락에 들어간다), 바로 202를 돌리고 뒤에서 적재하는 까닭, hook 토큰을 API 토큰과 가른 까닭
- 다루는 곳: `scripts/foreman-hook.sh`, `deploy/hooks/foreman-hooks.json`, `bridge/api/hooks.py`
- 크기: 보통

#### 02-3 턴 조립 — `notion/02_ingest/03_turns.md`
- 다루는 것: 턴 경계를 신호 하나로 판정하지 않는 까닭(정상, Esc, API 오류, 세션 종료, 압축 도중마다 잡는 신호가 다르다, 실측 표). 먼저 온 신호가 닫는다(closed_by). 턴 경계는 promptId. Esc를 첫 응답 전에 누르면 흔적이 없다. merged 턴, 다른 세션 메시지가 연 턴(origin). 토큰을 message.id로 한 번만 센다. 덩어리 하나가 트랜잭션 하나라 다시 읽어도 행이 늘지 않는다
- 막혔던 것: 시험은 통과했는데 행 수만 비교해 틀렸던 일(지금 `portfolio/07` 4-2)
- 다루는 곳: `bridge/assembler.py`, `bridge/store.py`, `bridge/models.py`, README 3.2
- 크기: 김

#### 02-4 적재와 내보내기 — `notion/02_ingest/04_bus.md`
- 다루는 것: 쓰는 쪽을 하나로 둔 까닭(event.id 순서 = 들어온 순서), 적재 뒤에 내보내기(화면에 보인 것은 DB에도 있다), DB가 죽으면 붙들고 재시도, 대기열이 차면 와처가 offset을 멈춘다. DB에 넣기 전 비밀 가리기(정확한 값, 형식, 키=값). 적재가 스스로 막힌 것을 알리기(11-03 한 파일이 몇 시간 같은 덩어리에서 실패를 되풀이했고 로그에만 남았다)
- 다루는 곳: `bridge/bus.py`, `bridge/mask.py`, `bridge/ingest_health.py`, `bridge/api/ws.py`, `bridge/api/debug.py`, `bridge/static/debug.html`
- 크기: 보통

### 03 세션 지켜보기 — `notion/03_watch.md`
- 다루는 것: 세션이 살아 있나(`~/.claude/sessions/<pid>.json`과 /proc starttime으로 PID 재사용 거르기, .key 파일은 열지 않는다), 정지(T)와 사라짐, CC가 심장박동을 보내지 않아 브리지가 1분마다 재는 멈춤의 종류(작업 중 끊김, 응답 없음, 맴돎, 끝내기 확인 창). 사람이 필요한데 조용한 때들: 권한 거부가 30분 안 풀림, API 오류(분류기에 막힌 것이 패널에 「API 오류」로만 보였다), `!` 명령이 글로 들어감(11-07 ~ 09에 7번, 아무도 몰랐다), 세션 간 메시지를 받는 쪽이 읽었는지
- 다루는 곳: `bridge/liveness.py`, `bridge/session_state.py`, `bridge/stallwatch.py`, `bridge/human_wait.py`, `bridge/api_error.py`, `bridge/bang_watch.py`, `bridge/xmsg.py`
- 크기: 보통 ~ 김. 길어지면 「03-1 살아 있나 멈췄나」, 「03-2 사람이 필요할 때」로 나눈다

### 04 세션에 글 넣기 — `notion/04_input.md`
- 다루는 것: 방법 C(load-buffer, 괄호 붙여넣기, 잠깐 쉬고 Enter)를 고른 까닭(`send-keys -l`은 줄바꿈에서 제출된다). 넣기 전에 앞 프로세스가 claude인지 본다(정지된 CC에 넣으면 셸 명령으로 실행된다). 첫 글자 `/`, `!` 다루기와 11-09에 바꾼 것. 창이 떠 있으면 종류로 갈라 Esc로 닫거나 거부한다(11-13 자동 압축 권유 창에 끝내기 명령이 들어갔다). 들어갔는지 트랜스크립트로 확인하고, 실패해도 입력 칸을 비우지 않는다
- 다루는 곳: `bridge/inject.py`, `bridge/api/sessions.py`, `bridge/static/js/slash.js`, README 3.1 「입력 주입」, `log/stage3_inject_result.md`
- 크기: 보통 ~ 김

### 05 승인 — `notion/05_approval.md`
- 다루는 것: 원칙 「되돌릴 수 없는 것만 묻고, 되돌릴 수 있는 것은 통과, 애매하면 묻는다」. 평범한 작업은 CC 자동 모드에 맡긴다. 프로젝트마다 observe, enforce. 텔레그램과 브라우저와 터미널 가운데 먼저 온 결정
- 다루는 곳: `bridge/approval.py`, `bridge/approvals.py`, `bridge/approval_summary.py`, `bridge/api/approvals.py`, `scripts/foreman-decide.sh`, `scripts/approval-replay.py`, `config/approval.toml`, README 3.3
- 크기: 김. 하위 셋

#### 05-1 규칙: 실행과 글자 — `notion/05_approval/01_rules.md`
- 다루는 것: 「위험한 명령을 실행하는 것」과 「위험한 명령을 글자로 쓰는 것」을 가르는 법(커밋 메시지, heredoc 속 `rm -rf`). 동사가 변수거나 지울 경로에 변수가 있으면 묻는다. 다른 구현과 비교(README 3.3 「다른 구현과 비교」). 규칙을 바꿀 때 지난 도구 호출에 옛 규칙과 새 규칙을 다시 돌려 하루 ask 수를 센다
- 다루는 곳: `bridge/approval.py`, `config/approval.toml`, `scripts/approval-replay.py`
- 크기: 김

#### 05-2 기다리는 길: hook 두 개 — `notion/05_approval/02_flow.md`
- 다루는 것: PreToolUse의 ask가 자동 모드에서도 승인 창을 띄운다는 실측, PermissionRequest hook이 기다리는 동안 터미널 창도 이미 떠 있다, 4초 판정 시간, 먼저 온 결정이 이기고 나머지는 거둔다, 시간 초과
- 다루는 곳: `bridge/approvals.py`, `scripts/foreman-decide.sh`, `bridge/api/approvals.py`
- 크기: 보통

#### 05-3 승인 요약 — `notion/05_approval/03_summary.md`
- 다루는 것: 명령을 통째로 보이지 않고 「무엇을 대상으로」 한 줄로(mktemp로 만든 것인지, 기존 디렉토리 파일 수, 네임스페이스, 컨테이너)
- 다루는 곳: `bridge/approval_summary.py`
- 크기: 짧음. 05-1에 합쳐도 된다

### 06 역할과 권한 — `notion/06_roles.md`
- 다루는 것: 코더, 디자이너, 서기, 조사, 관리자 다섯 역할과 그 기준. CLAUDE.md 글로만 있던 규칙이 계속 새서(11-10 worktree 코더에게 push 지시, 11-11 sed와 heredoc으로 파일 고침) PreToolUse 권한으로 옮긴 흐름
- 다루는 곳: `config/roles.toml`, `bridge/roleguard.py`, `bridge/static/js/modelpick.js`(`ROLE_PICK`), CLAUDE.md 「역할을 가르는 기준」, `docs/11_foreman_dispatch.md` 10절, `.claude/agents/Explore.md`
- 크기: 김. 하위 셋

#### 06-1 역할 다섯 — `notion/06_roles/01_roles.md`
- 다루는 것: 역할마다 하는 일, 기본 모델, 띄울 때 받는 지시. 관리자는 코드를 고치지 않는다는 선과 그 예외 셋. 조사는 끝나면 스스로 끝난다. 점검이 조사로, cicd가 빠진 것처럼 역할이 바뀐 까닭
- 다루는 곳: `config/roles.toml`, `config/models.toml`, `bridge/foreman.py`(역할 지시문), `bridge/inspector_close.py`, `docs/11_foreman_dispatch.md` 10절
- 크기: 보통

#### 06-2 글이 아니라 권한으로 — `notion/06_roles/02_guards.md`
- 다루는 것: PreToolUse에서 막는 것 다섯: 역할 규칙(`roleguard`), 다른 저장소는 읽기만(`reposcope`), 스키마는 한 세션만(`schemalock`, 잠금이 풀리는 때), `pgrep -f`가 자기 셸에 걸리는 함정(`pgrep_guard`), 진행 글이 영어면 알리기(`korean-check`). 승인 모드와 상관없이 도는 것과 observe부터 켜는 것의 차이
- 다루는 곳: `bridge/roleguard.py`, `bridge/reposcope.py`, `bridge/schemalock.py`, `bridge/pgrep_guard.py`, `scripts/korean-check.py`, `.claude/settings.json`, `docs/11_worktree.md` 5, 7절
- 크기: 김

#### 06-3 열쇠와 비밀 — `notion/06_roles/03_keys.md`
- 다루는 것: 토큰 넷(관리, 프로젝트, hook, 웹훅)을 가른 까닭(토큰 하나로 다른 방 세션까지 끝낼 수 있었다). WS는 쿼리스트링이 아니라 첫 메시지로 인증(로그에 남아서). 비밀 파일을 Edit, Write로 고치지 않는 까닭. 비밀값이 세 번 찍힌 일
- 다루는 곳: `bridge/api/auth.py`, `bridge/scopetoken.py`, `config/tokens.toml`, `bridge/mask.py`, `.env.*.example`, `bridge/api/webhooks.py`(토큰 부분)
- 크기: 보통

### 07 세션 띄우기와 따로 작업 — `notion/07_sessions.md`
- 다루는 것: 띄우는 길 셋(서기실, 계획 [시작], 직접 띄우기)을 `spawn_new` 한 곳으로 모은 까닭(계획 길 서기 15개를 서기실이 몰랐다). 이미 세션이 있으면 worktree(`.worktrees/<이름>`, 브랜치 `cc/<이름>`)로 띄운다. 링크로 잇는 것(.venv, .tools, .env*). 미리보기 브리지(worktree 화면 파일 + 지금 브리지 데이터, 8200 ~ 8299). 모델 고르기와 실제로 쓴 모델을 보이는 까닭. 시험 세션은 지우지 않고 숨긴다
- 다루는 곳: `bridge/handoff.py`(spawn_new, 세션 조작), `bridge/worktree.py`, `bridge/preview.py`, `bridge/previews.py`, `bridge/model_choice.py`, `bridge/api/handoff.py`, `config/worktree.toml`, `config/handoff.toml`, `docs/11_worktree.md` 1 ~ 3절
- 크기: 보통 ~ 김. 나누면 「07-1 띄우는 길」, 「07-2 worktree와 미리보기」

### 08 합치기 — `notion/08_merge.md`
- 다루는 것: main 위로 rebase하고 fast-forward로 합친다, 충돌이면 되돌리고 멈춘다. 누가 합치나(관리자가 API로, 사람이 패널로). merge-tree 확인과 합치기를 한 명령에 묶지 않는 까닭(11-10 실수). 합치는 차례
- 막혔던 것: 끝난 세션의 [합치기]가 화면에서 사라져 브랜치가 조용히 남았다
- 다루는 곳: `bridge/worktree.py`, `bridge/mergeprep.py`, `bridge/api/handoff.py`(worktree, merge-prep, merge-order), `docs/11_worktree.md` 6절
- 크기: 김. 하위 둘

#### 08-1 합치기 카드 — `notion/08_merge/01_card.md`
- 다루는 것: worktree 세션이 「일을 마침」이 되는 판정(살아 있음, 일하지 않음, 권한 거부 없음 …), 턴 끝에 바로 보고 1분 훑기는 그물, merge-tree로 카드를 만든다, 사람 화면에는 승인만. log만 바뀐 조사 작업방은 승인 없이 합친다. 쉬게 하기(세션만 끝내고 worktree를 남김)와 이어서
- 다루는 곳: `bridge/mergeprep.py`, `bridge/inspector_close.py`, `bridge/coder_room.py`, `bridge/api/coder.py`, `migrations/0032_merge_card.sql`, `docs/11_worktree.md` 4, 6-1, 6-2절
- 크기: 김

#### 08-2 끝난 뒤 맞추기 — `notion/08_merge/02_reconcile.md`
- 다루는 것: 합치고 끝낸 뒤 실제와 다른 것(남은 작업 폴더, 남은 「합치기 기다림」)을 훑어 알리기만 한다. 지우기는 사람이
- 다루는 곳: `bridge/reconcile.py`
- 크기: 짧음

### 09 인계와 압축 손실 — `notion/09_handoff.md`
- 다루는 것: 압축이 사용자 지시와 결정의 약 63%를 지우거나 약하게 했다는 실측, 그래서 요약을 통째로 넘기던 인계 1판을 버리고 「문서로 옮기고, 읽을 곳을 넘긴다」(2판)로 간 흐름
- 다루는 곳: `docs/11_handoff.md`, `docs/11_handoff_v2.md`, `log/runshoes_compaction_loss_20261105.md`, `log/foreman_compaction_loss_20261105.md`
- 크기: 김. 하위 넷

#### 09-1 압축 손실 재기 — `notion/09_handoff/01_loss.md`
- 다루는 것: 손 점검 두 번, 그 방법을 기계로 옮긴 [잃은 것 찾기](추출은 LLM 없이, 판정은 `claude -p`). 압축 알림을 파일 크기가 아니라 압축 횟수로 정한 까닭(가장 많이 빠지는 때가 두 번째 압축). 기계 판정이 뒤집힌 결정을 되살릴 수 있어 사람이 마지막 관문
- 다루는 곳: `bridge/losscheck.py`, `bridge/compactwatch.py`, `bridge/static/js/losscheck.js`, `migrations/0021_loss_check.sql`
- 크기: 보통 ~ 김

#### 09-2 인계 요약과 읽을 곳 — `notion/09_handoff/02_summary.md`
- 다루는 것: 요약은 그 세션 자신이 쓰고 브리지는 표지(`<<<FOREMAN-HANDOFF r=X>>>`)로 꺼낸다. 응답 못 하는 상태. 읽을 곳 한 줄 꼴과 새 세션이 실제로 읽었나 확인. 인계 뒤 바뀐 것(git, 잠금)을 붙이는 까닭(받은 세션이 「아직 안 합쳤다」를 읽었는데 이미 합쳐져 있었다)
- 다루는 곳: `bridge/handoff.py`, `bridge/pointers.py`, `bridge/handoff_state.py`, `migrations/0014_handoff.sql`, `0024_summary_state.sql`
- 크기: 김

#### 09-3 문서로 옮기기 — `notion/09_handoff/03_promote.md`
- 다루는 것: 넘기기 전에 대화에서 정했지만 문서에 없는 것을 세션이 목록으로 내고, 사람이 고르고, 세션이 쓰고 커밋하고, 브리지가 그 커밋을 git으로 확인한다
- 다루는 곳: `bridge/promote.py`, `bridge/static/js/promote.js`, `migrations/0020_promotion.sql`
- 크기: 보통

#### 09-4 새 세션으로 옮기기 — `notion/09_handoff/04_move.md`
- 다루는 것: 사람이 일곱 번 끼어들던 옛 흐름을 「무엇을 문서에 넣을지 고르기」 한 번만 멈추는 한 흐름으로. 옮길 때를 권하는 판단(쌓인 대화 40%, 전환 말투, 커밋이나 긴 쉼 셋이 겹칠 때). 알려진 한계(worktree 세션을 옮기면 새 세션이 원본 폴더에 뜬다)
- 다루는 곳: `bridge/static/js/moveflow.js`, `bridge/switchwatch.py`, `bridge/handoff.py`(spawn), `config/handoff.toml [move]`, README 6절
- 크기: 보통

### 10 교장과 관리자 — `notion/10_dispatcher.md`
- 다루는 것: 디스패처(화면 얼굴은 교장, 팀장, 소장)는 상주 세션이 아니라 부를 때만 `claude -p` 한 번. 관리자는 원본 폴더의 manager 세션. 관리자를 상주로 두지 않은 결정과 그 뒤 프로젝트별 관리자를 둔 흐름
- 다루는 곳: `bridge/foreman.py`, `bridge/api/foreman.py`, `docs/11_foreman_dispatch.md`, `docs/14_dispatcher_note_wake.md`
- 크기: 김. 하위 넷

#### 10-1 계획 한 번 — `notion/10_dispatcher/01_plan.md`
- 다루는 것: 브리지가 LLM 없이 만드는 상황 묶음(CLAUDE.md, 메모리 색인, docs 색인, 진행 중인 일, 지난 디스패치, 세션, 인계 요약, 파이프라인). 계획의 칸(프로젝트, 방식, 역할, 이름, 첫 글). 사람이 고쳐 [시작]. 여러 세션 계획과 맡을 파일 겹침(`file_conflicts`). 디스패처가 틀릴 때(직접 고르기 창을 남긴 까닭). 디스패처가 이틀 동안 조용히 죽어 있었던 일
- 다루는 곳: `bridge/foreman.py`, `bridge/api/foreman.py`, `migrations/0016_foreman_dispatch.sql`, `0030_dispatch_session.sql`
- 크기: 김

#### 10-2 진행 중인 일과 자동 기상 — `notion/10_dispatcher/02_note_wake.md`
- 다루는 것: 노트 = 「무엇이 남을지 사람이 고르는 압축 요약」. 쌓는 것은 진행 중인 일 하나뿐. 자동 기상 1, 2, 3단계 가운데 2단계(실패가 부르고 사람이 누른다)에서 멈춘 까닭, 하루 상한과 같은 실패 거르기
- 다루는 곳: `bridge/foreman_note.py`, `bridge/wake.py`, `config/wake.toml`, `migrations/0025_foreman_note.sql`
- 크기: 보통

#### 10-3 겹침 알림 — `notion/10_dispatcher/03_overlap.md`
- 다루는 것: 「이미 같은 일을 하는 세션을 알아챈다」(포먼이 있어야 하는 까닭). 디스패처는 띄울 때만 돌아서, 먼저 띄운 세션의 일을 다른 세션에 다시 시키는 것은 아무도 안 봤다(세션 198, 197이 같은 조사). 드문 낱말로 맞대기. 제목만으로 모자랐던 것
- 다루는 곳: `bridge/overlap.py`
- 크기: 보통

#### 10-4 관리자에게 넘기기와 보고 — `notion/10_dispatcher/04_managers.md`
- 다루는 것: 계획 카드를 사람이 복사해 옮기던 것을 [관리자에게 보내기]로. 관리자 주소와 관리자끼리 부탁. 작업 세션 보고는 관리자에게만, 관리자가 사람에게 올리는 escalate(물음은 바로, 보고는 21:00 묶음)
- 다루는 곳: `bridge/handover.py`, `bridge/managers.py`, `bridge/api/managers.py`, `bridge/api/handoff.py`(escalate), `config/managers.toml`, `migrations/0031_handover_todo_edit.sql`
- 크기: 보통

### 11 서기와 문서 — `notion/11_scribe.md`
- 다루는 것: 네 문서(깃헙, docs, 노션, 포트폴리오)의 깊이, 쉬움, 압축 축. 떠돌이 포트폴리오 캐릭터를 프로젝트마다 하나 두는 문서 담당으로 바꾼 결정. 회고와 README 갱신을 없앤 까닭(사람이 읽지 않는다, 로드맵 표가 멈춰 틀리게 알렸다). 커밋 수로 자동 실행하지 않는 까닭(검토 빚)
- 다루는 곳: `docs/12_scribe.md`, `log/foreman-7_scribe_design_20261115.md`
- 크기: 김. 하위 넷

#### 11-1 서기실과 일감 — `notion/11_scribe/01_room.md`
- 다루는 것: 시킬 일 종류와 할 일 세기(LLM 없음), 같은 일과 같은 파일만 막고 개수 상한은 없앤 것, 열려 있다의 판정(펫퍼민트 260이 폴더가 없는데 계속 막았다). 재료는 저장소 밖에 쓴다(사람 프롬프트 원문)
- 다루는 곳: `bridge/scribe_room.py`, `bridge/scribe.py`, `bridge/api/scribe.py`, `config/scribe.toml`, `migrations/0023_scribe_review.sql`
- 크기: 보통 ~ 김

#### 11-2 포스트잇 — `notion/11_scribe/02_postit.md`
- 다루는 것: 받는 함이 곧 포스트잇. 들어오는 길 셋, 대화에서 미룬 것을 거르는 그물(「확인 전」), [갱신] 판정은 제안이고 닫기는 사람, [→]로 알려진 한계에 보내기, 못 읽으면 0이 아니라 「읽지 못했습니다」
- 다루는 곳: `bridge/postit.py`, `bridge/api/postit.py`, `bridge/api/todo.py`, `migrations/0027`, `0028`, `0031`, `0033`, `docs/12_scribe.md` 11절
- 크기: 보통 ~ 김

#### 11-3 근거 확인과 물어보기 — `notion/11_scribe/03_evidence.md`
- 다루는 것: AI가 「됐다」고 쓴 것이 실제로 아니었던 일. 근거 표시(`[c:]`, `[log:]`, `[docs:]`, `[t:]`)를 LLM 없이 확인하고, 숫자나 인용이 있는데 근거 없는 줄을 의심으로 띄운다. 서기에게 물어보기는 세션 없이 읽기 전용 `claude -p` 한 번
- 다루는 곳: `bridge/evidence.py`, `bridge/scribe_ask.py`
- 크기: 보통

#### 11-4 노션 게시 — `notion/11_scribe/04_notion.md`
- 다루는 것: 원본은 git, 노션은 사본. 브리지가 API를 직접 부르고 LLM이 글을 옮겨 적지 않는다. 통합이 FOREMAN 페이지에만 연결돼 그 밖은 노션 권한이 막고, 코드에서도 한 번 더 막는다(`Scope`). 기준은 push된 것. 설정을 각 저장소 `.foreman/notion.toml`로 옮긴 까닭. docs 자동 맞추기. 막혔던 것: 게시할 때마다 mermaid 그림이 풀렸다. 이 기술문서 원고(`notion/`)를 올리는 길도 여기
- 다루는 곳: `bridge/notion.py`, `bridge/docsync.py`, `bridge/notioncfg.py`, `bridge/api/publish.py`, `config/notion.toml`, `migrations/0022_doc_publish.sql`, `docs/12_scribe.md` 5절
- 크기: 김

### 12 알림 — `notion/12_notify.md`
- 다루는 것: 모델이 CLAUDE.md를 보고 스크립트를 부르던 방식은 턴 끝 판정을 모델이 해서 빠졌다. 그래서 조립기가 턴을 닫을 때 기계로 보낸다. 끝 이유마다 제목, 서브에이전트는 따로 보내지 않는다, 21:00 묶음, 브리지 밖 알림(백업 실패). 토큰 파일은 하나. 알림이 조용히 안 나가던 길 셋
- 다루는 곳: `bridge/notify.py`, `bridge/telegram.py`, `config/notify.toml`, `migrations/0005_notification.sql`, `docs/operations.md` 5절
- 크기: 보통

### 13 CI/CD 인과 체인 — `notion/13_pipeline.md`
- 다루는 것: 커밋 SHA를 축으로 「이 세션이 고친 것 → 이 커밋 → 이 빌드(Jenkins) → 이 태그(Harbor) → 이 동기화(ArgoCD) → 여기서 실패」를 한 줄로 꿴다. 웹훅 전용 포트(루프백에만 있는 브리지가 클러스터 웹훅을 받는 법). 빌드 알림이 없으면 「Jenkins 확인」. FOREMAN 자신은 CI에 태우지 않는 까닭. 막혔던 것: 정전 뒤 Jenkins가 죽었는데 세 경로가 모두 조용했다, 「배포 진행 중」이 이틀 남았다
- 다루는 곳: `bridge/pipeline.py`, `bridge/api/webhooks.py`, `config/pipeline.toml`, `deploy/cicd/argocd-notifications-foreman.yaml`, `migrations/0012_pipeline.sql`, README 3.6
- 크기: 보통 ~ 김

### 14 사용량과 모델 — `notion/14_usage.md`
- 다루는 것: 트랜스크립트에 남지 않는 `claude -p` 사용량(디스패처, 손실 점검)을 따로 남기는 까닭. 한도별 측정 %와 리셋, API 정가 비율로 환산. 역할별 기본 모델과 정답과 맞대 모델을 정하는 방법. 막혔던 것: `/model`이 새 세션 기본값까지 바꿨다, 대화가 쌓인 세션에서 모델을 바꾸면 전체를 다시 읽는다
- 다루는 곳: `bridge/usage.py`, `bridge/api/usage.py`, `bridge/model_choice.py`, `bridge/static/usage.html`, `config/usage.toml`, `config/models.toml`, `migrations/0019`, `0026`, `docs/15_usage.md`
- 크기: 보통

### 15 화면 — `notion/15_screen.md`
- 다루는 것: 빌드 없는 순수 JS(번들러 없음, 저장소 파일을 그대로 낸다). 데이터 계층과 그리는 쪽을 가른 계약(테마 렌더러는 같은 state를 받아 그리기만). 페이지 넷(`/` 픽셀 화면, `/usage`, `/classic` 카드 대시보드, `/debug`). 화면 글 약속
- 다루는 곳: `bridge/static/*.html`, `bridge/static/css/panel.css`, `docs/10_office_design.md`, `docs/style_guide.md` 4-1
- 크기: 보통(개요). 하위 다섯

#### 15-1 데이터 계층 — `notion/15_screen/01_store.md`
- 다루는 것: 스냅샷 한 번 + WS로 고치기 + 몇 초마다 스냅샷으로 맞추기, 알림은 초당 4번까지. 화면 코드 지문(브리지를 다시 띄워도 열린 탭은 옛 코드라 버튼이 안 나왔다). 다시 그리기가 사람이 고치던 글을 지운 일
- 다루는 곳: `bridge/static/js/store.js`, `bridge/api/dashboard.py`, `bridge/api/ws.py`, `bridge/uiver.py`
- 크기: 보통

#### 15-2 픽셀 오피스와 테마 — `notion/15_screen/02_office.md`
- 다루는 것: 세 테마(현장, 마법학교, 오피스)와 plain이 한 모눈을 쓰고 이름, 그림, 색만 갈아 끼운다. 상태, 도구, 플래그 → 동작 판정. 시트 그림을 브라우저에서 자르고 칠하기, 에셋은 CC0와 MIT만, 없는 소품은 직접 그렸다. A* 길찾기와 복도. 발밑 역할 색, 머리 위 표시 쌓기. 막혔던 것: 가려짐을 하나씩 땜질하다 점검기와 자동 재배치로
- 다루는 곳: `bridge/static/js/office.js`, `theme.js`, `grid.js`, `sprites.js`, `walk.js`, `aura.js`, `overhead.js`, `wrap.js`, `bridge/static/themes/`, `scripts/draw_props.py`, `LICENSES.md`, `docs/10_office_design.md`
- 크기: 김. `office.js`가 3,913줄이라 더 나눌 수 있다(「테마와 모눈」, 「캐릭터와 움직임」, 「머리 위 표시」)

#### 15-3 옆 패널 — `notion/15_screen/03_panel.md`
- 다루는 것: 대화가 주인공(제목 줄 아래부터 입력 칸 위까지). 탭 [대화], [활동], [세션 정리]. 읽던 자리를 지키는 다시 그리기. 작은 마크다운(원문 HTML을 통과시키지 않는다). 툴팁 하나, 글씨 배율, 입력 칸 손잡이. 「끝남」이 「멈춤」처럼 보였던 일, 사람 이름이 이긴다
- 다루는 곳: `bridge/static/js/opanel.js`, `render.js`, `handoff.js`, `md.js`, `tip.js`, `uiscale.js`, `grip.js`, `modelpick.js`, `newsession.js`, `foremanchat.js`, `fmpanel.js`, `scribe.js`, `postit.js`, `coder.js`
- 크기: 김. 각 창의 동작은 기능 편(09, 10, 11)이 맡고, 여기는 패널의 뼈대만

#### 15-4 셸 패널과 CC 화면 — `notion/15_screen/04_shell.md`
- 다루는 것: CC에게 시킬 수 없는 일(sudo 암호, SSH 패스프레이즈)을 화면에서 끝내는 셸 패널(ttyd, xterm.js, 파싱하지 않는다). CC가 「이 명령을 실행해 주세요」 하면 입력 줄에 미리 채운다. 쿠키 범위를 좁힌 까닭. CC 화면 창(권한 창, 계획 승인 창을 FOREMAN에서 못 봐 VNC로 들어가 Esc로 닫았다)
- 다루는 곳: `bridge/terminal.py`, `bridge/api/terminal.py`, `bridge/static/js/terminal.js`, `ccscreen.js`, `deploy/shell/`, `scripts/foreman-shell-hook.sh`, README 3.9
- 크기: 보통 ~ 김

#### 15-5 화면 점검과 시연 — `notion/15_screen/05_check.md`
- 다루는 것: 사람에게 콘솔을 부탁하지 않는다(헤드리스 크로미움으로 세 테마 × 세 크기 점검). 시연 재생은 실제 기록 재생과 대본을 가르고 화면에 밝힌다. GIF와 WebM 가르기. 화면 말 시험(옛 이름 찾기)
- 다루는 곳: `tools/screen.py`, `tools/demo_from_db.py`, `tools/frames_to_gif.py`, `bridge/static/js/demo.js`, `bridge/static/demo/`, `tests/test_screen_words.py`, `tests/data/screen_words.toml`, `docs/13_demo_capture.md`
- 크기: 보통

### 16 DB — `notion/16_db.md`
- 다루는 것: MySQL을 고른 까닭과 전용 인스턴스. ENUM을 쓰지 않고 코드에서 검사, event에 FK를 두지 않고 쓰는 곳을 하나로. 보관 정책과 인덱스. 백업
- 다루는 곳: `bridge/db/`, `bridge/models.py`, `bridge/store.py`, `migrations/`, `deploy/mysql/`, README 5절
- 크기: 김. 하위 둘

#### 16-1 표 지도 — `notion/16_db/01_tables.md`
- 다루는 것: 표 스물아홉을 덩어리로(기록: project, character, character_session, transcript_file, turn, message, subagent_run, event / 세션 한살이: session_action, summary, character_session_move_*, promotion, loss_check, merge_card / 시키기: dispatch, dispatch_session, foreman_note / 문서: doc_publish, scribe_review, todo_inbox, postit_check / 바깥: notification, approval, git_commit, build, build_commit, usage_extra, usage_observation). 각 표가 어느 편의 것인지
- 다루는 곳: `migrations/0001` ~ `0033`
- 크기: 김

#### 16-2 마이그레이션 — `notion/16_db/02_migrate.md`
- 다루는 것: 번호 순으로 한 번씩, 적용 기록. 한 세션만 스키마를 바꾸는 잠금(06-2와 잇는다). 시험 DB
- 다루는 곳: `bridge/db/migrate.py`, `bridge/schemalock.py`, `tests/test_testdb.py`
- 크기: 짧음

### 17 시험과 배포 — `notion/17_tests.md`
- 다루는 것: CI가 없다(GitHub Actions는 정하고 아직 안 만듦). 관리자가 합친 뒤 pytest와 node를 손으로. 배포는 systemd 유닛 재시작, 승인 대기 0 뒤에 사람이. GitLab, Jenkins에 태우지 않는 까닭(이미지가 없다). 시험 묶음(파이썬 약 80파일, js `node --test`), 실제 설정 모양 시험
- 다루는 곳: `tests/`, `pyproject.toml`, `requirements.lock`, `deploy/systemd/`, CLAUDE.md 「돌리기, 확인」
- 크기: 짧음 ~ 보통

### 줄인 안(사용자가 편 수를 줄이고 싶으면)

| 줄인 안 | 합치는 것 |
|---|---|
| 01 전체 구조 | 01-2를 본문에, 01-1만 하위 |
| 02 기록 모으기 | 하위 넷 → 「02-1 트랜스크립트와 hook」, 「02-2 턴 조립과 적재」 |
| 03 세션 지켜보고 넣기 | 03 + 04 |
| 05 승인 | 05-3을 05-1에, 하위 둘 |
| 06 역할과 권한 | 하위 셋 그대로 |
| 07 띄우기와 합치기 | 07 + 08, 하위 「07-1 합치기 카드」 |
| 09 인계와 압축 손실 | 09-2, 09-3 합침, 하위 셋 |
| 10 교장과 관리자 | 10-2, 10-3 합침, 하위 셋 |
| 11 서기와 문서 | 11-3을 11-1에, 하위 셋 |
| 12 알림 + 13 CI/CD | 「12 알림과 CI/CD」 |
| 14 사용량과 모델 | 그대로 |
| 15 화면 | 15-1을 본문에, 15-5를 17에, 하위 셋 |
| 16 DB | 하위 없이 |
| 17 시험과 배포 | 15-5를 받음 |

---

## 3. 덮지 못한 코드

위 안의 「다루는 곳」에 한 번도 나오지 않는 것.

| 코드 | 무엇 | 판단 |
|---|---|---|
| `tests/` 대부분(약 120파일) | 기능마다의 시험 | 17에 묶음으로만 넣는다. 파일 하나하나를 편에 넣지 않는다(정할 것 7) |
| `bridge/static/demo/*.json`(18개) | 시연 대본 | 15-5에서 폴더로만 가리킨다. 넣는다 |
| `portfolio/`, `log/` | 글과 기록 | 코드가 아니다. 뺀다 |
| `config/portfolio.toml` | 포트폴리오 고정 주제 10개 | 사용자 지시로 없앨 것. 뺀다. 남아 있으면 「덮지 못한 코드」 세기가 매번 이것을 센다 |
| `bridge/__init__.py`, `api/__init__.py` 등 빈 파일 | 패키지 표시 | 뺀다(세기에서도 빈 파일은 빼자고 제안) |
| `.gitignore`, `.env.*.example` | 비밀 파일 이름 | 06-3에 `.env.*.example`만 넣었다. `.gitignore`는 뺀다 |
| `docs/01_kickoff.md` | 킥오프 브리프 | 00에서 가리킨다. 넣는다(00 「다루는 곳」에 있음) |

브리지 파이썬 86파일, 화면 js 29파일, 마이그레이션 33개, 설정 13개(`portfolio.toml`은 위 표), `scripts/` 6개, `tools/` 3개, `deploy/` 9개는 모두 어느 편에 들었다.

---

## 4. 포트폴리오 편 목록안(화면 축)

편마다: 제목 / 그 화면이 하는 일 한 줄 / 기능 단위로 내려갈 거리 / 다루는 곳 / 지금 `portfolio/`에서 옮겨 쓸 재료(이하 「재료」). 그림은 지금 `portfolio/img/` 32장 가운데 맞는 것을 적었다.

| 편 | 제목 | 그 화면이 하는 일 | 내려갈 거리 | 다루는 곳 | 재료 |
|---|---|---|---|---|---|
| 00 | 한눈에 보는 FOREMAN | 한 화면에서 여러 AI 작업 세션을 보고 다룹니다 | 왼쪽 지도, 오른쪽 패널, 아래 셸. 화면 없는 이야기(어디에 두었나, 왜 밖에 열지 않았나) 두세 줄 | `office.html`, `office.js`, `opanel.js` | `00_overview` 1, 3절, `08_placement` 2절 요지. 그림 `00_overview_*` |
| 01 | 픽셀 지도와 방 | 세션마다 캐릭터가 서고, 하는 일에 따라 움직입니다 | 테마 셋, 방과 복도, 상태별 모습, 서브에이전트, 이름표, 툴팁 | `office.js`, `theme.js`, `grid.js`, `walk.js`, `sprites.js`, `themes/` | `01_pixel_office` 거의 전부. 그림 `01_*` |
| 02 | 머리 위 표시와 띠 | 사람이 볼 것이 생기면 캐릭터 머리 위와 방 배너에 뜹니다 | 보고 옴, 답 기다림, 문서 할 일, 맡길 일, 권한 거부 배너, 새로 고침 띠, 적재 막힘 띠 | `overhead.js`, `aura.js`, `office.js`, `bridge/uiver.py`, `bridge/ingest_health.py` | `02_ui` 3-4, `07_observability` 4-1. 그림 `02_ui_bands.png` |
| 03 | 출하 라인 | 커밋 하나가 빌드, 이미지, 배포까지 어디에 와 있는지 보입니다 | 단계 셋, 실패 표시, 빌드 알림 없음 | `office.js`(INFRA_STAGES), `grid.js`, `/api/pipeline`, `bridge/pipeline.py` | `07_observability` 3-3, 4-7, 4-8. 그림 `07_observability_pipeline.gif`, `07_observability_real_build.gif` |
| 04 | 세션 패널: 대화와 활동 | 캐릭터를 누르면 그 세션과 나눈 대화와 한 일이 보입니다 | 대화 탭, 활동 탭(누르면 입력과 결과 본문), 새 답 따라가기, 입력 칸과 `/`, `!` | `opanel.js`, `render.js`, `md.js`, `slash.js`, `/api/dashboard`, `/api/sessions`, `bridge/transcript/lookup.py`, `bridge/inject.py` | `02_ui` 3-1, `04_agent_control` 3-3. 그림 `02_ui_convo.png`, `04_agent_control_input.png` |
| 05 | 승인 카드 | 되돌릴 수 없는 명령만 사람에게 묻고, 무엇을 대상으로 하는지 한 줄로 보입니다 | 카드 꼴, 요약 한 줄, 텔레그램과 화면 가운데 먼저 누른 것 | `render.js`(승인 카드), `/api/approvals`, `bridge/approvals.py`, `bridge/approval_summary.py` | `04_agent_control` 3-2, `08_placement` 그림. 그림 `04_agent_control_approval.gif`, `08_placement_approval_card.png`, `02_ui_approval_done.png` |
| 06 | 세션 정리: 인계와 옮기기 | 대화가 무거워진 세션을 잃는 것 없이 새 세션으로 넘깁니다 | 잃은 것 찾기, 문서에 남기기, 요약과 읽을 곳, 옮기기 한 흐름 | `handoff.js`, `moveflow.js`, `losscheck.js`, `promote.js`, `/api/sessions/{sid}/handoff`, `bridge/handoff.py` | `03_context_loss` 3, 4절, `02_ui` 3-2. 그림 `03_context_loss_*`, `02_ui_session_tab.png` |
| 07 | 합치기 카드와 코더 창 | 따로 일한 세션이 끝나면 합칠지 묻는 카드가 뜹니다 | 일을 마침 판정, 합치기 카드, 쉬게 하기, 코더의 맡길 일 | `coder.js`, `render.js`, `/api/coder`, `/api/sessions/{sid}/merge-prep`, `bridge/mergeprep.py`, `bridge/coder_room.py` | `02_ui` 4-1, `05_dispatcher` 4-5. 새 그림 필요 |
| 08 | 교장 계획 창과 감독실 | 하려는 일을 말하면 교장이 계획을 내고, 이미 하는 세션이 있으면 알려 줍니다 | 계획 카드, 진행 중인 일, 자동 제안([시작]?), 겹침 알림, 관리자에게 보내기 | `foremanchat.js`, `fmpanel.js`, `/api/foreman`, `bridge/foreman.py`, `bridge/overlap.py`, `bridge/handover.py` | `05_dispatcher` 3절, 4-1. 그림 `05_dispatcher_*` |
| 09 | 새 세션 창 | 프로젝트, 역할, 모델을 골라 화면에서 바로 세션을 띄웁니다 | 어디서, 역할과 기본 모델, 따로 작업(worktree) 여부, 인계 넣기 | `newsession.js`, `modelpick.js`, `/api/spawn`, `/api/spawn/options`, `bridge/worktree.py`, `bridge/model_choice.py` | `09_models_cost` 3-2. 그림 `09_models_cost_model_menu.png` |
| 10 | 서기실 | 문서 담당 서기에게 문서 일을 시키고, 문서에 대해 묻습니다 | 할 일 목록, 시키기, 물어보기, 포트폴리오와 기술문서 게시 | `scribe.js`, `/api/scribe`, `/api/publish`, `bridge/scribe_room.py`, `bridge/scribe_ask.py`, `bridge/notion.py` | `06_scribe` 3절. 그림 `06_scribe_room.png`, `06_scribe_review.png` |
| 11 | 포스트잇 | 미뤄 둔 할 일이 한 장에 모이고, 끝났는지 코드를 보고 알려 줍니다 | 적기, 대화에서 미룬 것 줍기, [갱신] 판정, 알려진 한계로 보내기, 코더에게 띄우기 | `postit.js`, `/api/postit`, `bridge/postit.py` | 없음(새 편). 새 그림 필요 |
| 12 | CC 화면 창 | 세션의 실제 CC 창을 그대로 보고, 떠 있는 창에 키를 보냅니다 | 창 옮기기와 크기, 보낼 수 있는 키 | `ccscreen.js`, `/api/ccscreen`, `bridge/api/terminal.py` | 없음(새 편). 새 그림 필요 |
| 13 | 셸 패널 | AI에게 시킬 수 없는 암호 입력을 화면 아래 셸에서 끝냅니다 | AI가 부탁한 명령이 미리 채워짐, 결과가 그 세션에 돌아감 | `terminal.js`, `/api/terminal`, `bridge/terminal.py`, `deploy/shell/` | `08_placement` 4-2, `02_ui` 3-5 |
| 14 | 사용량 화면 | 한도를 얼마나 썼고 이 속도면 언제 다 쓰는지 보입니다 | 한도별 %, 리셋, 환산액, 모델별, 추가 요금 배지 | `usage.html`, `/api/usage`, `bridge/usage.py` | `09_models_cost` 3-1, 5절. 그림 `09_models_cost_tokens.png` |
| 15 | 텔레그램 알림 | 화면을 보고 있지 않아도 휴대폰으로 알려 줍니다 | 턴 끝, 승인 대기, 파이프라인 실패, 적재 막힘, 21:00 묶음, [시작] 링크 | `bridge/notify.py`, `config/notify.toml`, `bridge/wake.py` | `07_observability` 4-4, `07_observability_card.png` |

합칠 후보(합치면 13편): 12 + 13 → 「세션 화면과 셸」, 07을 06 또는 09로(합치기는 따로 작업의 끝이라 09 「새 세션 창」과 이어진다), 02를 01로(머리 위 표시는 지도 위에 뜬다).

포트폴리오에 화면이 없어 들지 않는 지금 재료: `03_context_loss` 2절(손 점검 방법과 결과), `07_observability` 3-1, 3-2(적재, 턴 판정), `08_placement` 거의 전부, `09_models_cost` 3-3(정답과 맞대 모델 정하기). 모두 노션 재료로 간다(02, 09-1, 01-1, 14).

---

## 확인한 방법

- `bridge/` 파이썬은 `ast.get_docstring`으로 모듈 머리를 뽑아 모두 읽었다. 함수 본문은 읽지 않았다
- API 경로는 `@router.<동사>("…")`를 grep으로 뽑았다
- 화면 js는 머리 주석 여섯 줄씩, 페이지 경로는 `bridge/main.py` 556 ~ 592
- 표 이름은 마이그레이션의 `CREATE TABLE`을 grep으로(29개)
- 「덮지 못한 코드」는 손으로 맞댔다. 기계 세기(설계 4-2)는 아직 없다

## 확인하지 못한 것

- 각 편의 「막혔던 것」은 docs, README, 포트폴리오 절 머리에서 골랐다. log 300파일을 다 읽지 않았다. 서기가 쓸 때 log에서 더 큰 것이 나올 수 있다
- 크기 어림은 코드 줄 수와 docs 절 수로 했다. 실제 글 길이는 다를 수 있다
- `config/wake.toml`의 `public_url = "https://foreman.ronanlab.dev"`가 텔레그램 [시작] 링크에 쓰이는데(`bridge/wake.py:110`), README 3.13은 그 터널을 열지 않기로 했다. 링크가 실제로 열리는지 보지 않았다. 열리지 않으면 링크가 조용히 죽어 있는 것이라 관리자에게 알린다(조사 역할이라 고치지 않았다)
- 노션 변환기가 HTML 주석을 빼지 않는다는 점(설계 4-1)은 이 안의 머리 주석에도 걸린다. 그대로다

## 규칙 위반

규칙 위반 없음.
