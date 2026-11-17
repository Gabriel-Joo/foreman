# 설계 문서에서 옮긴 진행 기록과 지난 경위 (11-17, 코더 foreman-4, 관리자 410 일감 커밋 2)

`docs/00_design.md`(11-17까지 맨 위 README.md)를 docs 기준에 맞춰 줄이면서 뺀 글을 **고치지 않고 그대로** 모았다. 사용자 결정(11-17): 진행 기록은 docs가 아니라 기록 폴더 몫이고, 옛 기록 파일에 덧붙이지 않고 이 파일 하나에 모은다. 절마다 원래 기록이 있으면 그 파일을 적었다.

- 원문 판: `527d841:docs/00_design.md`(옮긴 그대로, 941줄). 아래 「줄」은 그 판의 줄 번호다. 이 파일에 없는 옛 글(데이터 모델 칸 표, 인덱스 표 등)도 그 판에서 볼 수 있다
- 원고 근거가 이 파일을 가리키게 옮긴 것: `notion/04_approval.md`(다른 구현 비교), `notion/04_approval/01_rules.md`(넣지 않은 것, 다른 구현 비교와 그 뒤 수치). 근거 지도는 `log/foreman-4_design_evidence_map_20261117.md`
- 날짜 꼬리표만 뗀 줄(결정은 그대로 남김)은 여기 옮기지 않았다. 그 줄의 옛 꼴은 위 판에서 본다

## 1. 머리말 (줄 5)

🔧 **매일 쓰는 중** — 런슈즈 · 펫퍼민트 · FOREMAN · 인프라 세션이 모두 tmux에서 돌고, 브리지는 systemd 사용자 유닛이 돌린다(11-06). 만든 순서는 깃헙 커밋이, 기능마다 지금 상태는 아래 「문서」의 docs가 맡는다(로드맵 표는 11-11에 멈춰 지금을 틀리게 알려 11-15에 뺐다). 아직 안 되는 것은 「6. 알려진 한계」, 서버 PC 변경 기록은 [`log/`](log/). 킥오프(2026-11-02) 설계 검토는 [`log/01_kickoff_result.md`](log/01_kickoff_result.md) — 브리프 01의 4는 남음

원래 기록: `log/infra_20261106_systemd-bridge.md`, `log/foreman-4_readme_cleanup_20261115.md`

## 2. 2.2 캐릭터는 인프라의 거울이다 (줄 61~80)

처음 설계의 등장 흐름 그림과 호스트 감시 계획이다. 등장, STALE, 퇴장은 코드에 있고(`bridge/pipeline.py`), 호스트 감시는 아직 없다(`docs/TODO.md` foreman-1).

```
새 프로젝트          포먼만 있음
  ↓ "파이프라인 깔아줘"
포먼이 코더를 띄움    코더 등장
  ↓ Jenkinsfile 작성, 커밋, 첫 빌드
웹훅 최초 수신       Jenkins 캐릭터 등장
  ↓ 첫 이미지 push
                    Harbor 캐릭터 등장
```

**호스트의 systemd 유닛과 docker 컨테이너도 감시한다.** 웹훅과 엔드포인트 응답만으로는 "죽지 않고 계속 다시 뜨는" 상태가 잡히지 않는다. 2026-11-02에 이런 것이 둘 나왔고 둘 다 어느 경로에도 걸리지 않았다 — `milvus-port-forward.service`는 10-01부터 567,740회 재시작했고(실행 파일 없음), milvus 컨테이너는 재시작 크래시 루프를 17분 돌았다(재시작 중에도 잠깐씩 응답).

- **신호는 상태보다 재시작 추세다.** systemd `NRestarts` · `ActiveState`/`SubState` · `ExecMainStatus`, docker `RestartCount` · `State`를 폴링하고, 시간 창 안에서 재시작 횟수가 계속 늘면 `restart_loop` 이벤트를 낸다. 한 번의 실패는 잡음일 수 있다.
- **유닛·컨테이너는 캐릭터로 만들지 않는다.** 서버의 유닛 전부를 캐릭터로 만들 수는 없다.
  - 프로젝트에 연결된 것(예: `petmint-search`, `cloudflared-ollama`, milvus, ollama 컨테이너)은 대응하는 인프라 캐릭터의 상태에 반영한다 — 재시작 루프면 그 캐릭터가 `STALE`·경고가 된다. 연결은 `character.watch_targets`에 둔다.
  - 어느 캐릭터에도 속하지 않는 것(이번의 `milvus-port-forward` 같은 것)은 포먼의 경고 목록에 띄운다.

원래 기록: `log/infra_20261102_milvus-port-forward.md`

## 3. 2.3, 2.4 (줄 86, 99)

11-14 cicd 역할을 뺐다(한 번도 쓰지 않음, 빌드 · 배포는 브리지 파이프라인 구역). 세션 역할은 coder · inspector · scribe · manager · designer이다.

> **⚠ (11-05 해소 — 0017 재배치, log/stage11_roles_result.md) 아래는 그때까지의 임시 상태다(2026-11-02).** FOREMAN이 생기기 전부터 돌던 세션(런슈즈 · 펫퍼민트 · 포먼의 기존 CC 세션)은 2단계에서 **모두 그 프로젝트의 포먼 캐릭터 하나에 `role = coder`로 묶어 두었다**(입양만 — 캐릭터는 포먼만 채용하므로 브리지가 캐릭터를 만들지 않았다). 프로젝트 밖 cwd의 세션은 떠돌이 '미분류'에 묶였다. 그래서 대시보드는 캐릭터 이름 대신 **세션 제목**(CC가 붙이는 `ai-title`, `character_session.title`)으로 세션을 구분한다(6단계). **11단계에서 포먼이 캐릭터를 제대로 만들 때 이 세션들을 각각 올바른 캐릭터로 재배치해야 한다**(로드맵 11 할 일).

원래 기록: `log/cicd_role_removal_20261114.md`, `log/stage11_roles_result.md`

## 4. 3.1 입력 주입의 바뀐 내력 (줄 176~181)

- **첫 글자**: `/`는 슬래시 명령으로, **`!`는 셸 명령으로 실행된다** → `/`는 앞에 공백 한 칸을 붙인다(일부러 명령을 보낼 때만 그대로). `@`는 새지 않는다. 폭 없는 공백 보호는 Enter가 안 먹혀 입력 칸에 남았다 — 쓰지 않는다
  - `!`(11-09 바뀜): ~~언제나 공백을 붙여 막는다~~ — 그래서 사람이 실행하려던 명령 7건이 글로 갔고 아무도 몰랐다. 이제 입력 API가 앞뒤 공백을 떼고, 같은 명령을 Bash 도구 호출처럼 승인 규칙에 넣어 **묻는 규칙(ask) · sudo · 여러 줄 · 빈 명령만 막고**(이유 · 할 일을 글로) 그 밖은 bash 모드로 실행한다(`inject.bang_check`). bash 모드는 승인 훅을 거치지 않는다. 그래도 `!`가 글로 들어가면 텔레그램으로 알린다(`bridge/bang_watch.py`) [log:petmint_docs_move_20261109.md] [log:alerts_denied_xmsg_bang_20261109.md]
- **창이 떠 있으면 종류로 갈라 닫거나 거부한다(11-09, 11-13 바뀜)**: 붙여넣기 전에 화면을 가른다(`inject.screen_state` — `deliver`가 부르므로 패널 입력 · 옮기기 넣기 · 감독실 [보내기] · 끝내기 모두 같은 길)
  - 입력 칸 = 0칸에서 시작하는 가로줄(`────`) 바로 아래의 0칸 `❯` 줄 … 다음 가로줄. ~~`❯`로 시작하는 줄이 하나라도 있으면 입력 줄~~ — 지난 사용자 글도 0칸 `❯`로 남고 고르기 줄도 `❯`라, 대화가 있는 세션에선 창이 떠 있어도 늘 입력 줄로 보고 그 창에 붙여 넣었다(11-13 서기의 자동 압축 권유 창에 끝내기 명령이 들어감). 입력 칸 위에 `▔▔▔` 테두리나 Esc 안내 줄(「… · Esc to cancel」)이 있으면 창으로 본다
  - Esc가 「그대로 둠 · 지금은 아님」인 창(자동 압축 권유 · `/model` · `/config` · `/usage` · `/autocompact`): Esc를 보내고 0.6초 뒤 다시 본다, 최대 3번. 결과 글 "떠 있던 ○○ 창을 Esc N번으로 닫고 보냈습니다."(입력 이벤트에 `esc` 수 · `dialog` 이름)
  - Esc가 결정이 되는 창(폴더 신뢰 · 도구 권한 · 보류된 세션 메시지 승인 · 끝내기 확인 · 계획 승인)과 모르는 창: Esc도 글도 보내지 않고 거부 "○○ 창이 떠 있어 넣지 못했습니다 … 그 세션 대화창에서 확인해 주세요"
  - **작업 중(busy)이면 Esc를 보내지 않는다** — Esc는 작업을 끊는다. 권한 창이 떠 있을 때 상태 파일 status는 `busy`가 아니라 `waiting`이다(11-13 실측) — 그래서 창 종류로 거른다 [log:plan_dialog_escape_retry_20261109.md] [log:prompt_vs_dialog_20261113.md]

## 5. 3.3 승인 정책 (줄 245~393)

원래 기록: `log/stage5_approval_result.md`(5단계와 11-05 다시 좁히기), `log/stage6_dashboard_result.md`(실행과 글자), `log/stage8_cicd_result.md`(11-03 넓히기). 11-03 다른 구현 비교와 승인 창 한 줄 요약을 따로 적은 기록은 없어 이 절이 그 기록이다.

원래 불편 중 마지막 항목(5단계, [결과](log/stage5_approval_result.md)). PreToolUse hook마다 브리지가 판정한다 — 규칙은 `config/approval.toml`.

**원칙(11-05 다시 좁힘): 사용자가 실제로 거부할 만한 것만 묻는다** — 이론적 위험이 아니라. 목적은 auto mode에서 흐름이 안 끊기는 것. 그 전 승인 이력 65건 중 실제 작업에서 거부는 0건이었다(유일한 거부는 승인 창 시험). 경위 · 근거는 [결과 — 11-05 다시 좁히기](log/stage5_approval_result.md).

21일 다시 돌려 보기(11-05, 도구 호출 18,076개): 하루 승인 창 런슈즈 10.7 → **0.1**, 펫퍼민트 6.8 → **0.2**, 포먼 26.3 → **1.3**. 남은 9건은 모두 거부할 만한 것(운영 DB 비우기 4 · 이력 재작성 2 · PVC · 네임스페이스 삭제 3).

아래 "실행과 글자"부터 "늘 Yes 좁히기"까지는 11-05 전 **엄격한 규칙**에서 오탐을 하나씩 고친 기록이다. 그 장치는 코드에 남아 있고 설정으로 다시 켠다(`[sensitive] mode = "read"` · `protect_mode = "ask"`, `[ask] delete_outside_worktree = true` · `scan_interpreter_heredocs = true`). 시험은 `tests/test_approval.py`(엄격 규칙 = `tests/fixtures/approval_strict.toml`)와 `tests/test_approval_now.py`(지금 기준).

### 실행과 글자는 다르다

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

### 다른 구현과 비교 (11-03)

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

### 근거 절에서 뺀 두 줄 (줄 373, 375)

**문서에 없는 것**(기대지 않는다): bypassPermissions · acceptEdits에서 hook `ask`, hook `allow`가 auto mode 분류기를 건너뛰는지(11-02 `kubectl patch`를 분류기가 막았을 때 우리 판정은 `pass`였다 — 이 질문의 실측은 아직 없다), `claude -p`에서 hook `ask`.

참고: PolicyApprovalGate 문서에 이 근거가 있다고 들었지만, 확인해 보니 그 저장소는 auto mode를 말하지 않고 공식 문서 링크도 없다. auto mode에서도 ask가 확인을 강제한다고 쓴 것은 command-guard README이고(출처 링크 없음), 위 공식 문서가 근거다.

### 그 밖 (줄 383~389)

**질문(AskUserQuestion)은 승인이 아니지만 같은 길로 받는다(11-09)**: CC가 질문 창을 띄울 때도 PermissionRequest hook이 불린다. 정책(`approval.toml`)에서 빼지 **않는다** — 빼면 질문이 터미널에만 떠 텔레그램 · 화면 알림이 없고 턴도 안 끝나 턴 끝 알림도 없다(세션이 조용히 멈춘다). 대신 모양 · 답하는 길을 따로 둔다: 규칙 이름 "질문", 카드 "❓ 세션이 묻습니다"에 선택지 버튼, 텔레그램 "❓ 세션이 묻습니다 — 답을 기다립니다", 머리말 · 현장 버튼 · 방 카드 · 패널 머리에서 승인 대기와 따로 센다. 패널에서 고르면 `decision.behavior = "allow"` + `updatedInput` = 원래 입력 전체 + `answers`(질문 글 → 선택지 이름, 여러 개는 `", "`로 이음)로 돌려준다(`bridge/approvals.py` `answer()`). 문서는 "Multi-select answers join labels with commas"까지만 말한다 — `", "`로 이은 답이 세션에 그대로 들어가는 것은 실측(11-09 #70, 하나 고름 · 여러 개 고름). 브리지가 다시 뜨면 선택지를 잃어 "터미널에서 답합니다"로 바뀐다. 경위는 `log/pixel_bigger_question_card_20261109.md`

**계획 승인(ExitPlanMode)도 updatedInput을 붙여 돌려준다(11-14)**: CC는 사람 창을 띄우는 도구에서 `updatedInput` 없는 hook `allow`를 결정으로 받지 않는다 — 패널이 허용해도 터미널 계획 승인 창이 그대로 남아, 브리지는 「허용됨」으로 카드를 닫고 세션은 조용히 멈췄다(11-09~13 패널 허용 세 건이 모두 2~3분씩 멈춤, `log/silent_finish_20261114.md` 1절). 그래서 패널 허용은 `updatedInput` = 원래 입력 + `updatedPermissions = [{type: "setMode", mode: "auto", destination: "session"}]`로 돌려준다(`bridge/approvals.py` `allow_decision`) — 터미널 기본 선택 「1. Yes, and use auto mode」와 같은 결과다. `updatedInput`만 주면 CC는 「계획 전 모드」로 돌아가는데, `--permission-mode plan`으로 띄운 세션(읽기 전용)은 그것이 manual이라 그 뒤 편집 · Bash마다 다시 묻는다(실측 CC 2.1.325, `log/plan_approve_mode_20261114.md`). 그래도 창이 남으면 멈춤 감시가 잡는다 — 쉬는 세션 화면에 결정 창이 떠 있는데 브리지가 기다리는 승인이 없으면 2분 뒤 패널 「⏸ 창에서 답을 기다림」 + 텔레그램 한 번(`bridge/stallwatch.py` `dialog`, 머리글에 종류 설명).

**승인 창 한 줄 요약(11-03)**: 명령 통째로는 읽기 힘들다 — 판단에 필요한 건 "무엇을 대상으로"다. `bridge/approval_summary.py`가 규칙이 아니라 명령을 보고 대상을 뽑는다: `rm -rf → /home/kopo17/volumes (기존 디렉토리, 파일 418개)` · `rm -rf → $D (이 명령에서 mktemp로 만든 것)` · `kubectl delete → pod/jenkins-0 (jenkins 네임스페이스)` · `DROP DATABASE x (컨테이너 runshoes-mysql-dev)` · `읽기(cat) → …/.env.bridge (비밀 파일)`. CC 승인 창(`permissionDecisionReason` 맨 앞) · 텔레그램 둘째 줄 · 대시보드 승인 카드(명령 전체는 접어 둠) · `approval.summary`에 같은 줄. CC 자체가 묻는 것(rule `cc`)에도 붙는다. 디렉토리 파일 수는 0.3초 안에서만 센다(PreToolUse는 4초 안에 답해야 한다).

## 6. 3.5 자동 기상 처음 설계 표 (줄 409~415)

| 항목 | 제한 |
|---|---|
| 동시 ACTIVE | 최대 3 (초과 시 대기열) |
| 자동 기상 조건 | 실패 이벤트만 (성공은 무시) |
| 자동 세션 수명 | 30분 후 강제 IDLE |
| 일일 자동 기상 | N회 제한 |
| 야간 자동 기상 | 끔 |

지금 코드에 있는 것은 실패 이벤트만, 하루 상한, 같은 실패 다시 안 함, 읽기 전용, 사람이 [시작]을 누름이다(`config/wake.toml`, `bridge/wake.py`). 나머지는 `docs/TODO.md` foreman-118. 원래 기록: `log/stage14_dispatcher_note_wake_result.md`

## 7. 3.6 CI/CD 인과 체인의 옛 흐름과 11-09 줄들 (줄 436~454)

11-02 조사 때 서술이다. 11-03부터 Jenkins와 ArgoCD의 GitHub 웹훅 경로 하나씩이 Access 밖(Bypass)이라 아래 「웹훅 없음」은 지금과 다르다(`log/stage8_cicd_result.md` 「재개 조사」, `log/foreman-6_access_policy_20261117.md`).

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

## 8. 3.7 LLM 지표 (줄 456~469)와 7. 데모 시나리오 (줄 867~883)

코드가 없다(bridge, config에 TTFT, VRAM, 프로메테우스 쿼리 0건). `docs/TODO.md` foreman-117로 옮겼다.

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

### 7. 데모 시나리오

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

(11-17 덧붙임: 인프라 저장소에는 11-11부터 Prometheus와 Grafana가 있다(`log/foreman-6_access_policy_20261117.md` 「운영 도구 다섯」). 「아직 설치하지 않았다」는 이 글이 쓰인 때의 것이다.)

## 9. 3.8 테마 매핑 예시 표와 크기 (줄 475~483, 493)

표의 테마 이름(오피스, 도서관)은 지금 테마(office, site, magic, plain)와 다르다.

| 이벤트 | 오피스 | 도서관 |
|---|---|---|
| `tool_use/Read` | 책상에서 타이핑 | 서가에서 책을 꺼냄 |
| `tool_use/Bash` | 서버랙으로 걸어감 | 지하 서고로 내려감 |
| `IDLE` | 의자에 앉음 | 열람석에 앉음 |

**크기(11-09)**: 방은 이미 무대에 꽉 차 있어(1920은 높이, 1366 · 1024는 폭이 한계) 방을 다 보이게 둔 채로는 방 안의 그림만 키울 수 있다. **캐릭터만 1.5배**(테마 `sprites.char_scale`, `sprites.js charFrame`이 키운 크기를 돌려줘 얼굴 칸 · 소품 · 이름표 · 점검이 같이 따른다) — **가구는 키우지 않는다**(칸 배치 · 길찾기 · 앉기와 묶여 있다, 사용자 결정). 화면 좌표 글씨는 원래 px × 글씨 배율(가+/가−) × 1.2. 경위는 `log/pixel_bigger_question_card_20261109.md` 「3.」

  - 11-06 반영: 서브에이전트나 백그라운드 Bash · Monitor가 돌면 IDLE 부모를 **기다림(WAITING)** 으로 그린다. 자는 모습 대신 책상에 서서 "…"를 띄우고, 이름 아래 "백그라운드 n · 설명"을 붙이며, 현장 집계는 작업으로 센다. 서버 상태 값은 그대로 IDLE이고 화면만 바꾼다(`theme.js` `viewState`, 테마 `states.WAITING`)

## 10. 3.12, 3.13 (줄 605, 617, 625~626)

**수집부(호스트) · API/UI(파드)로 나누지 않는다 — 배포는 systemd, 테스트는 GitHub Actions(2026-11-03 결정).** **GitHub Actions는 결정만 했고 아직 만들지 않았다**(워크플로 파일 `.github/workflows` 없음, 11-11 확인). 지금은 관리자가 합친 뒤 pytest · node를 손으로 돌린다. 처음에는 "8단계(CI/CD)에서 다시 본다"로 미뤘던 것이다. 다시 보니 나눌 이유가 오히려 줄었다.

| **GitHub Actions에서 시험 자동 실행**(아직 안 만듦 — 지금은 관리자가 합친 뒤 손으로) | 승인 정책(`approval.py`)은 보안 규칙이라 퇴행을 막을 가치가 크다(순수 함수 시험). DB 시험은 MySQL 서비스 컨테이너로. tmux를 쓰는 시험은 설치하거나 건너뛴다 | **우리 Jenkins에 태우지 않는다.** 그쪽은 이미지를 만들어 Harbor로 보내는 서비스용이고 FOREMAN에는 이미지가 없다 — Jenkinsfile · 시험 DB · 인프라 저장소 수정이 생겨 통일을 위한 통일이 된다 |

11-17 사용자 결정으로 GitHub Actions는 쓰지 않는다(`log/foreman-5_todo_collect_20261117.md` 4-1절).

- **FOREMAN은 뚫리면 서버 셸이 열리는 물건이다.** 대시보드에는 터미널 패널(ttyd — 호스트 셸, 3.9), 실행 중인 CC 세션에 입력 주입(3.1 — tmux send-keys), 승인 · 거부(되돌릴 수 없는 명령을 통과시키는 버튼)가 있다. 앞단 인증 하나가 깨지면 보는 화면이 아니라 서버를 내주는 셈이다

11-17 사용자 문장으로 까닭을 바꿨다(`docs/00_design.md` 「3.13」).

## 11. 「문서」 절 (줄 887~941)

README가 편 목록을 만들어 두 벌이 되므로 지웠다(사용자 11-17). 그 표에만 있던 것은 `log/foreman-4_readme_split_20261117.md` 「10.」에 적었다.

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
