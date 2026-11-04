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

---

## 11-05 다시 좁히기 — "실제로 거부할 만한 것만"

### 경위 — 방향이 두 번 바뀌었다

1. **처음(11-02 설계)**: 목적은 **귀찮음 없애기**였다 — "승인을 매번 누른다", 승인을 브라우저 · 텔레그램으로
2. **조사해 보니(11-02)**: 세 프로젝트 모두 auto mode라 20일에 사람이 누른 승인은 19번뿐이었다. 귀찮음은 이미 없었고, 대신 분류기가 운영 명령(git push 79 · kubectl 변경 132 · rm -r 60 …)을 그냥 통과시켜 왔다 → **위험 차단으로 방향을 틀었다**("되돌릴 수 없는 것만 ask, 애매하면 ask")
3. **실제로 써 보니(11-02 ~ 11-05)**: 흐름이 계속 끊겼다. 오탐을 패턴 하나씩 고쳐 나갔지만(실행과 글자 · 리터럴 · mktemp · 스크래치패드 · 늘 Yes 좁히기 …) 끊김은 줄지 않았다. 승인 정책을 고치려고 **시험하는 코드가 그 정책에 걸리는** 일까지 반복됐다
4. **사용자 결정(11-05)**: 처음 목적(auto mode에서 흐름이 안 끊기는 것)으로 되돌린다. 기준은 **"사용자가 실제로 거부할 만한 것"**, 이론적 위험이 아니라

### 근거 — 승인 이력 전체(65건)

**거부는 1건, 그것도 승인 창 시험**이었다 — 11-02 5단계 검증에서 일부러 거부한 `rm -r junk-b`(`.probe-appr` 시험 폴더). **실제 작업 중 거부 0건.**

같은 성격으로 반복된 것(전부 Yes):

| 성격 | 건수 | 걸린 규칙 | 지금 규칙 |
|---|---|---|---|
| `/tmp/claude-1000` 아래 지우기(서브에이전트 · 다른 세션 스크래치패드, 임시 폴더) | 16 | rm-재귀 10 · 애매한-삭제 6 | 0 |
| 토큰(`.env.bridge`) 다루기 — 교체 · 시험 | 13 | 민감한-경로 | 0 |
| 규칙 파일을 Edit 도구로 고치기 | 11 | 보호-설정파일 | 0(🛡 알림만) |
| 승인 정책을 시험하는 코드의 문자열(`python - <<EOF` 안 `"rm -rf …"`) | 9 | rm-재귀 7 · kubectl-변경 2 | 0 |
| 클러스터 조회 · 그 밖 heredoc 글자 | 5 | 디스크-전원 · kubectl-* · 민감한-경로 | 0 |
| mktemp로 만든 것 지우기(`jar=$(mktemp); trap 'rm -f "$jar"'`) | 4 | rm-재귀 | 0 |
| 그 밖의 지우기(승인 창 시험 3 · `__pycache__` 1) | 4 | rm-재귀 | 0 |
| 그 밖 | 3 | — | 0 |

"같은 규칙이 계속 걸리면 규칙이 잘못된 것"이라는 사용자 판단이 이 표로 맞았다 — 상위 네 줄(49건)이 모두 **무엇을 지우는지 · 어디에 쓰는지 보면 위험하지 않은 것**이었다.

### 새 목록

**남긴 것**(사용자 후보 + 내 판단):

| 규칙 | 무엇 |
|---|---|
| `통째로-삭제` | `/` · 시스템 최상위 폴더(`/etc` …) · 홈과 그 조상, 지정 폴더(`~/AI_programming` · `~/volumes` · `~/backups` · `~/mysql-data` · `~/k8s-cluster` · `~/ronanlab-infra` · `~/.claude` · `~/.claude/projects` · `~/.ssh` · `~/.kube`) 자체와 **바로 아래의 폴더**(프로젝트 하나 · 볼륨 하나), `X/*`(내용 전부). 변수 경로는 변수 앞의 고정 부분으로(`~/AI_programming/$p`), 변수가 비면 `/`가 되는 것(`rm -rf $X/`) — `${X:?}`로 막았으면 통과. 같은 명령에서 문자 그대로 정한 변수는 값을 풀어 본다 |
| `DB-파괴` | **운영 쪽**(FOREMAN `foreman-mysql` · 3308, 클러스터: kubectl · vagrant ssh · 런슈즈 `mk` 래퍼)과 **같은 줄**(또는 그 줄의 heredoc)에서 `DROP DATABASE/SCHEMA/TABLE` · `TRUNCATE` · WHERE 없는 `DELETE FROM` · `dropdb` · `FLUSHALL` |
| `재부팅-종료` · `디스크·VM-파괴` | reboot · shutdown · `systemctl poweroff`, `mkfs` · `dd of=/dev/…` · `vagrant destroy` · `virsh undefine` |
| `git-이력파괴` · `git-강제push` | `reset --hard` · `clean -f` · `filter-branch` · `filter-repo` · `reflog expire` · `gc --prune=now`, `push --force` · `+ref` · `--delete` · `--mirror` |
| `비밀-외부전송` | 비밀 파일이 **밖으로 보내는 명령의 인자**(`curl -F f=@.env` · `scp .env host:` · `"$(cat .env)"`)이거나 같은 파이프라인 앞 단계에서 읽혀 넘어갈 때. 밖 = curl · wget의 URL이 이 PC · VM 망(127.* · localhost · 192.168.121/122.*)이 아닌 것, scp · rsync `host:`, ssh(vagrant ssh 아님) · nc · socat · gh 등 |
| `데이터-삭제` | `docker volume rm/prune` · `system prune --volumes`, `compose down -v`(런슈즈 개발 스택 빼고), kubectl `delete ns/pvc/pv` · `delete --all`, `helm uninstall`, `argocd app delete` |
| `프로세스-대량종료` · `권한-대량변경` · `원격스크립트-실행` · `크론-삭제` | CC · tmux · 인프라 한꺼번에 끄기(`tmux kill-server` 추가), `chmod/chown -R /`·`~`, `curl … \| sh`, `crontab -r` — 실데이터 0건이지만 거부할 만하고 비용이 없다 |

**뺀 것**: `/tmp` 아래 · mktemp로 만든 것 · 작업 트리 밖의 평범한 삭제 · 변수 경로 삭제 · 해석기(python · node …) heredoc 본문의 글자 · 비밀 파일 읽기 · 쓰기 · 복사 · 로컬 서비스로 넘기기 · 규칙 · 설정 파일 쓰기(묻지 않고 🛡 텔레그램 — Bash로 고쳐도) · 로컬 개발 · 시험 DB · kubectl `delete pod/deploy/-f` 등 다시 생기는 것 · `docker rm/rmi` · `git checkout --`/`restore`/`stash drop`/`branch -D` · `find -delete` · `chmod 777` · `printenv`/`env` · 동사가 변수인 운영 명령 · `truncate -s 0`

### 내 판단이 들어간 것

- **`/tmp/claude-1000` 아래**: 안전하다 — 디렉토리가 kopo17 소유 · 700이라 다른 계정이 링크를 심을 수 없다. 판정할 때마다 확인하고(진짜 디렉토리 · 내 것 · 그룹/남 권한 0), 아니면 예외를 쓰지 않는다. `/tmp/claude-1000` 자체를 지우는 것은 묻는다. 대상의 부모를 realpath로 풀고, `link/`처럼 끝이 /면 대상도 푼다(`rm -r link/`는 링크를 따라간다) — 지금 기준(통째로만 묻는다)에서는 `/tmp` 전체가 어차피 통과지만, 예외 자체는 남겨 뒀다(엄격 규칙으로 돌릴 때를 위해)
- **테스트 코드의 문자열**: `tests/` 파일이나 `bridge.approval`을 import하는 스크립트를 본문 검사에서 빼는 안은 **위험하다** — `import bridge.approval` 한 줄을 붙이면 아무 heredoc이나 검사를 피한다(우회 문구가 된다). 대신 **해석기 heredoc 본문을 셸 규칙으로 읽지 않는다**(셸 · SQL heredoc과 실행하는 `.sh` 파일은 그대로). 해석기 코드의 `os.system("rm -rf …")`을 놓치는 것은 받아들인다 — 실데이터에 그런 모양이 없었고, 파일로 쓴 스크립트를 `python x.py`로 돌리는 것은 전에도 검사하지 않았다
- **승인 규칙 시험 방법**: 앞으로는 판정 함수(`load_policy(...).decide(...)`)를 직접 부르는 시험 코드를 **파일로 쓰고**(Write 도구) `.venv/bin/python <파일>`로 돌린다 — hook에 걸리는 것은 그 한 줄뿐이다. 다시 돌려 보기는 `scripts/approval-replay.py`(DB 읽기만)
- **비밀 파일 읽기를 뺀 것**: 비밀을 화면에 내지 않는 것은 승인 창이 아니라 작업 규칙(CLAUDE.md · 메모리 "출력에 섞이는 시험 명령은 출력 버리기")으로 지킨다. 13건 모두 토큰 교체 날의 정상 작업이었다. 되돌리려면 `[sensitive] mode = "read"` · `tool_ask = true`
- **`compose down -v`**: 런슈즈 개발 DB(이름 있는 볼륨)를 비우는 일상 작업이라 뺐지만, `openwebui_data` · `ollama_data`도 이름 있는 볼륨이라 그 밖은 묻는다. FOREMAN · 밀버스 · mysql은 bind mount(`~/volumes` · `~/mysql-data`)라 `-v`로 안 지워진다(`docker inspect`로 확인)
- **런슈즈 · 펫퍼민트는 여전히 observe** — 이 판정은 기록만 된다. enforce 전환은 사용자 결정

### 다시 돌려 본 결과(21일, 도구 호출 18,076개, 판정 함수 직접 — hook 안 탐)

| 프로젝트 | 활동한 날 | 전 ask/일 | 후 ask/일 |
|---|---|---|---|
| 런슈즈 | 12 | 10.7 | 0.1 |
| 펫퍼민트 | 16 | 6.8 | 0.2 |
| 포먼 | 3 | 26.3 | 1.3 |
| 미분류 | 2 | 8.5 | 0.0 |

남은 9건을 하나씩 봤다 — 전부 거부할 만하다: FOREMAN 운영 DB 전체 비우기(`DELETE FROM event; …` → foreman-mysql) 4, 펫퍼민트 `git filter-branch` · `reflog expire` 2, 런슈즈 · 펫퍼민트 `kubectl delete pvc` · `delete ns` 3. 하루 2~3건 목표보다 적다 — 남은 것이 모두 진짜라 더 넣을 이유가 없었다.

도중에 고친 것: 홈 바로 아래 **파일** 하나(`~/embedEtcd.yaml.bak`)가 통째로 걸림 → 바로 아래는 폴더만. `$T/cfg`(T가 비면 `/cfg` 하나)가 "비면 /"로 걸림 → 변수를 빈 값으로 놓고 남는 경로를 판정. 운영 덤프를 받아 개발 DB에 넣는 명령이 `DB-파괴`로 걸림(운영 표시와 `DROP`이 다른 줄) → 같은 줄만. 따옴표가 꼬인 조각(`import json; …`)이 `/`로 풀림 → 경로가 아닌 글자는 건너뜀.

### 장치는 남겼다

엄격한 규칙의 장치(실행과 글자, 리터럴 · 키 이름 · 헤더 · mktemp · 스크래치패드 처리, 비밀 읽기 · 보호 파일 ask)는 코드에 그대로 있고 설정으로 켠다. `tests/test_approval.py`는 11-05 직전 config(`tests/fixtures/approval_strict.toml`)로 그 장치를 시험하고, `tests/test_approval_now.py`가 지금 기준(남긴 것은 묻고 뺀 것은 안 묻는다)을 시험한다.

### 설계 판단 사례로

- 안전장치는 **"거부한 기록"으로 검증**해야 한다. 65번 물어 0번 거부했다면 그 65번은 안전이 아니라 소음이었다 — 소음은 진짜 경고도 Yes로 누르게 만든다
- 오탐을 하나씩 고치는 방식은 끝이 없었다. 기준(무엇을 막고 싶은가)을 다시 정하자 묻는 규칙이 22개에서 12개로 줄었고 오탐 패치가 대부분 필요 없어졌다
- 이론적 위험(변수 경로 · 해석기 코드 · 비밀 읽기)은 승인 창 대신 다른 층(작업 규칙 · 기록 · 알림)이 맡는다
