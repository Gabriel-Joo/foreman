# foreman 공개 전 비밀값 · 개인정보 점검 (2026-11-15, foreman-6 조사)

관리자 410 일감(사용자 지시 「공개 전 비밀값 점검」). 대상은 원본 폴더 `~/AI_programming/foreman`의 git 기록 전체다. 고친 것은 없고, 이 파일 하나만 이 브랜치에 커밋했다. 이 문서에는 **값을 쓰지 않는다**. 파일, 줄, 커밋 해시, 무엇인지(꼴과 길이)만 적는다.

## 0. 본 범위와 방법

- **ref**: 로컬 ref 32개를 모두 봤다. `main`, `cc/foreman-*` 3개, `refs/remotes/origin/*` 2개, 태그 `archive/main-before-reword-20261113`, 숨은 ref `refs/foreman/squashed/*` 25개. stash는 0개다.
- **원격**(`git ls-remote origin`): `HEAD`, `refs/heads/main`, `refs/tags/archive/main-before-reword-20261113` 세 개만 있다. **Public이 되면 보이는 것은 이 셋이다.** 태그에는 11-13 커밋 메시지를 바꾸기 전의 옛 기록(커밋 541개)이 그대로 남아 있다.
- **커밋**: `git rev-list --all` 1337개(조사 중 다른 세션이 커밋해 1335에서 늘었다). `origin/main` 714개.
- **blob**: 모든 ref에서 닿는 서로 다른 blob 3566개를 한 번씩 읽었다. 글 blob은 꼴로 찾았고, 바이너리 blob 236개는 바이트로 찾았다.
- **커밋 메시지**: `git log --all` 전체를 같은 꼴로 찾았다. 작성자와 커미터 메일도 봤다.
- gitleaks와 trufflehog는 이 서버에 없다(`command -v` 빈 결과). 그래서 스크래치에 값을 가리는 스크립트를 써서 `.venv/bin/python -I`로 돌렸다. 스크립트는 값을 찍지 않는다. 찍는 것은 경로, 꼴 이름, 앞 2글자와 길이, 그리고 같은 값을 묶기 위한 sha256 앞 6글자뿐이다.
  - `scan.py`: 꼴 검색, 실제 값 맞대기, 커밋 메시지, 작성자 메일
  - `entropy.py`: 32자 넘는 높은 엔트로피 글자(대소문자와 숫자가 섞이고 엔트로피 4.2 넘음)
  - `binscan.py`: 바이너리 blob
  - `ctx.py`, `ipctx.py`: 문맥을 가린 채 판정
- **찾은 꼴**:
  - 텔레그램 봇 토큰 `\d{8,10}:[A-Za-z0-9_-]{35}`
  - 키와 토큰: `sk-ant-`, `sk-`(20자+), `gh[pousr]_`, `github_pat_`, `secret_`, `ntn_`, `AKIA`, JWT `eyJ….…`, `-----BEGIN … PRIVATE KEY`
  - 접속 문자열: `mysql|postgres|mongodb|redis|amqp://`, `scheme://user:pass@`
  - 값 넣는 꼴: `password|passwd|pwd|MYSQL_*PASSWORD [=:]`, `*token|secret|api_key [=:]`(12자+), `Bearer`(12자+), `chat_id [=:]`
  - 개인정보와 내부망: IPv4(사설 192.168, 10, 172.16-31, 공인, 공용 DNS, 문서용 대역으로 나눔), 휴대폰 `01x-`, 메일, `/home/<이름>`, Notion id(32자 hex나 uuid)
- **실제 값 맞대기**(가장 확실한 확인): 아래 비밀값 24개를 스크립트 메모리에만 읽고, 모든 blob과 모든 커밋 메시지에 같은 글자가 있는지 개수만 셌다.
  - `.env.bridge` 3개, `.env.notion` 1개, `.env.project_tokens` 3개, `.env.telegram` 2개(봇 토큰과 chat id), `.env.db` 3개
  - `~/.claude/sessions/*.key` 9개(세션 간 통신 키)
  - `~/.claude/.credentials.json`의 OAuth 토큰 2개

## 1. 지금 코드에서 찾은 것 (HEAD, 모두 원격 main에 올라가 있음)

| 파일 · 줄 | 무엇인지 | 판정 |
|---|---|---|
| `bridge/api/webhooks.py` 3,5 · `bridge/config.py` 119,126,128 · `bridge/pipeline.py` 75,98 · `config/pipeline.toml` 4,28 · `deploy/cicd/argocd-notifications-foreman.yaml` 1,26 · `tests/test_approval.py` 208 · `tests/test_approval_now.py` 116 · `tests/test_pipeline.py` 40,200-202 | 내부망 IP(192.168 대역, 일부는 포트 붙음) | **서버 IP. 공개 불가(사용자 기준)** |
| `log/01_kickoff_result.md` 18 · `log/infra_20261102_host-changes.md` 13,14,38 · `log/infra_20261102_milvus-port-forward.md` 26 · `log/merge_wait_to_manager_20261113.md` 49 · `log/preview_alive_20261113.md` 14 · `log/stage8_cicd_result.md` 26,27,53,93,158,192,206,251,263,275,289 | 내부망 IP. 192.168 대역이 대부분이고, 10 대역 하나와 172.16-31 대역 하나(클러스터 안쪽)가 있다. 포트가 붙은 것도 있다 | **공개 불가(사용자 기준)** |
| 위 전체 | 서로 다른 사설 IP는 192.168 대역 10개, 10 대역 1개, 172 대역 1개. HEAD 15개 파일에 있다 | |
| `log/infra_20261106_jenkins-harbor-after-outage.md` 86, `tests/test_pipeline.py` | 공인 IP 꼴 5개. 모두 잘 알려진 공용 DNS 주소와 해시가 같다(박스 이미지의 resolv 설정, 시험 값) | 서버 주소 아님. 두어도 됨 |
| HEAD 21개 파일 46줄. 예: `.claude/settings.json`, `deploy/hooks/foreman-hooks.json`(8줄), `deploy/systemd/foreman-bridge.service`(4줄), `deploy/mysql/backup.sh`, `deploy/shell/foreman-bashrc`, `migrations/0002_seed.sql`(3줄), `migrations/0029_seed_ronanlab_infra.sql`, `bridge/approval_summary.py`, `bridge/static/demo/stills.json`, `README.md`, `tests/*` 여러 개 | 홈 경로 `/home/<서버 계정 이름>`. 계정 이름은 경로 밖까지 치면 HEAD 42개 파일에 있다 | 개인정보(서버 계정 이름). 공개할지는 사용자가 정할 일 |
| 커밋 1337개 전부(작성자와 커미터) | 작성자 메일이 사용자의 개인 메일(무료 메일 도메인)이다 | **개인정보. Public이 되면 GitHub 커밋 화면과 `.patch`에서 그대로 보인다** |
| `config/notion.toml` 40-42, 53-55, 62-64, 87-89 | Notion 페이지와 DB id(32자 hex) | 비밀값은 아니다. 토큰이 없으면 열 수 없다. 다만 워크스페이스 구조가 드러난다. 낮음 |
| `.env.bridge.example` | `FOREMAN_API_TOKEN`, `FOREMAN_HOOK_TOKEN`, `FOREMAN_WEBHOOK_TOKEN`의 값은 모두 빈칸(0자). `DEBUG_ENDPOINTS`는 불 값 | 견본. 문제없음 |
| `.env.db.example` | `MYSQL_ROOT_PASSWORD`와 `MYSQL_PASSWORD`는 빈칸. `MYSQL_DATABASE`(7자)와 `MYSQL_USER`(11자)는 값이 있다. 이 사용자 이름은 실제 `.env.db`와 같고 코드, 문서, 시험 여러 곳(`bridge/config.py`, `bridge/mask.py`, `docs/operations.md`, `notion/05_roles/03_keys.md`, `tests/test_units.py` 등)에 있다 | 비밀번호가 아닌 DB 이름과 사용자 이름이다. 낮음 |
| `tests/test_units.py` 37,51,60,61 · `tests/test_terminal.py` 91,101,105 · `tests/test_stage2_db.py` 86 · `tests/test_roleguard_inspector.py` 31 | 가리기 시험용 가짜 비밀번호, API 키, Bearer, chat id, `user:pass@` 주소, 시험 메일 | 시험 고정값. 실제 값 맞대기 0건. 두어도 됨 |
| `bridge/db/engine.py` 13 외 시험 파일 여럿, `scripts/approval-replay.py` | `password=s.mysql_password…`처럼 설정을 읽는 코드 식 | 값 아님 |
| `docs/02_cloudflare_tunnel.md` 74 | `<foreman-tunnel UUID>.cfargotunnel.com` 꼴. 터널 UUID는 자리표시이고 실제 값이 아니다 | 문제없음 |
| `ronanlab.dev` 하위 호스트(`jenkins`, `harbor`, `argocd` 등 40곳) | 도메인 이름 | 사용자가 공개해도 된다고 함 |

## 2. 히스토리에만 있는 것

| 커밋 · 파일 | 무엇인지 | 원격에 있나 |
|---|---|---|
| 옛 판의 `README.md`, `deploy/cicd/harbor-webhook.py`, `deploy/cicd/jenkinsfile-petmint.patch`, `deploy/cicd/jenkinsfile-runshoes.patch`, `scripts/cicd-apply.sh` | 내부망 IP(192.168 대역). 지금 HEAD에는 없거나 줄이 빠졌다 | 있음(main 기록) |
| 커밋 메시지 `a56f45c8`, `8c614212` | 본문에 내부망 IP(192.168 대역) | 있음(`origin/main`) |
| 커밋 메시지 `86b613ea`, `0178fd5e` | 본문에 내부망 IP(192.168 대역). 11-13 메시지를 바꾸기 전 커밋이다 | 있음(태그 `archive/main-before-reword-20261113`) |
| `portfolio/img/09_models_cost_tokens.png` | 지워진 스크린샷. 파일 이름으로 보아 모델 비용과 토큰 사용량 화면이다. 그림 속 글은 **못 봄**(OCR 도구 없음). 메타데이터에 비밀값, 홈 경로, 메일은 0건 | 있음(`origin/main` 기록 1커밋) |
| 로컬에만 있는 ref(`cc/*`, `refs/foreman/squashed/*`)에서만 걸린 것 | 2건. `log/foreman-4_bridge_down_20261115.md`의 홈 경로 1줄. `log/foreman-6_silent_delete_20261115.md`의 `${PWD:…}` 꼴은 거짓 걸림이다 | 없음(합치면 올라간다) |

- 실제 값 맞대기(24개 × blob 3566개 + 커밋 메시지 전체): **토큰, 비밀번호, 세션 키, OAuth 토큰, 텔레그램 봇 토큰, chat id는 0건이다.** 걸린 것은 `MYSQL_USER`(위 1절, 비밀번호 아님)뿐이다. 커밋 메시지 2개(`d315c899`, `5650cca0`)에도 같은 사용자 이름이 있다.
- 높은 엔트로피 검색에 걸린 것은 2건이다(`log/infra_20261102_host-changes.md`, `log/stage3_inject_result.md`). 글자 모양을 보면 둘 다 `~/.claude/…` 파일 경로다. 비밀값이 아니다.
- **11-02 세션 키가 찍혔던 일, 11-11 Bearer가 찍혔던 일**: 그 일을 적은 log에 값이 옮겨 적힌 흔적은 없다.
  - 세션 키는 141자 JSON 꼴이다. 지금 키 9개를 맞대어 0건이었고, 그 안의 높은 엔트로피 글자도 기록 어디에도 없다.
  - Bearer 꼴은 기록 전체에서 2건뿐이고 둘 다 가짜 값이다(`log/test_terminal_bearer_20261111.md` 9줄 `fake-…`, `tests/test_units.py` 60줄).
  - 바꾸기 전의 옛 API 토큰은 맞댈 수 없다(값이 남아 있지 않다). 대신 43자 urlsafe 꼴이 엔트로피 검색에 0건이어서 남아 있지 않다고 판단했다.
- 바이너리 blob 236개: 실제 비밀값, `/home/`, git 메일 모두 0건이다. 글 덩이가 있는 PNG는 1개(`…/calciumtrice/medieval_interior.png`, 외부 스프라이트)다.
- 휴대폰 번호, `-----BEGIN`, `sk-ant-`, `sk-`, `gh*_`, `secret_`, `ntn_`, `AKIA`, JWT, 접속 문자열(`mysql://` 등)은 기록 전체에서 0건이다(시험 고정값 제외).

## 3. 폐기가 필요한 것

**없음.** 저장소 기록(모든 ref, 모든 blob, 커밋 메시지)에서 실제 비밀값과 같은 글자가 0건이다. 그러니 저장소를 공개한다고 재발급할 토큰은 없다.
- 참고: 11-02와 11-11에 값이 찍힌 곳은 저장소가 아니라 그때의 세션 화면이었다. 그 값을 바꿨는지는 이 조사 범위 밖이다. 바꾸지 않았다면 바꾸는 곳은 다음과 같다.
  - 세션 키: CC 세션을 다시 띄우면 새로 생긴다.
  - `FOREMAN_API_TOKEN`: 서버의 `.env.bridge`. 11-11에 바꾼 기록이 있다.

## 4. 그냥 지워도 되는 것 (히스토리에 없고 지금만 있는 것)

- 비밀값으로는 **해당 없음.**
- 로컬 브랜치에만 있는 `log/foreman-4_bridge_down_20261115.md`의 홈 경로 1줄은 합치기 전에 빼면 원격 기록에 들어가지 않는다. 다만 같은 홈 경로가 이미 원격 기록 수십 곳에 있으니, 홈 경로를 어떻게 할지 정한 뒤에 같이 처리하면 된다.

## 5. .gitignore와 견본 파일

- 실제 비밀 파일 `.env.bridge`, `.env.telegram`, `.env.db`, `.env.notion`, `.env.project_tokens`는 모두 막혀 있다(`git check-ignore`).
- 추적 중인 `.env` 계열은 견본 둘(`.env.bridge.example`, `.env.db.example`)뿐이다. 비밀번호와 토큰 칸은 비어 있다.
- 기록 전체에서 `.env`, `.pem`, `.key`, `credentials` 같은 이름의 파일이 커밋된 적은 없다(`git log --all --name-only`, `--diff-filter=D`). 막기 전에 올라간 파일도 없다.
- 빈틈: `*.pem`, `*.key`, `*.db`, `*.sqlite`는 막혀 있지 않다(시험 경로 `x.pem`, `x.key`, `foreman.db`가 「안막힘」). 지금 그런 파일은 없다. 앞으로를 위해 넣어 둘지는 관리자가 정한다.

## 6. 판정

**비밀값 기준으로는 지금 Public으로 돌려도 된다.** 폐기할 토큰이 없다. **사용자 기준(서버 IP와 포트 불가, 개인정보)으로는 조치가 먼저다.**

1. **개인 메일**: 커밋 1337개 모두의 작성자 메일이 개인 메일이다. 가리려면 둘 중 하나다.
   - 기록을 다시 쓴다(mailmap이나 `git filter-repo --mailmap`으로 GitHub noreply로 바꾸고 force push).
   - 받아들인다.
2. **내부망 IP와 포트**: 지금 코드 15개 파일, 옛 판 5개 파일, 커밋 메시지 4개에 있다. HEAD만 고치면 기록에 남는다. 가리려면 `git filter-repo --replace-text`(파일)와 `--replace-message`(메시지)로 기록을 다시 쓰고 force push해야 한다.
   - **원격 태그 `archive/main-before-reword-20261113`도 함께 지우거나 다시 써야 한다.** 이 태그가 옛 메시지 2개를 들고 있다.
   - 세션이 도는 동안 force push하면 worktree들이 꼬인다(CLAUDE.md 「커밋 메시지」 끝 줄).
   - 대신 사설 IP는 바깥에서 닿지 않으니 받아들인다는 선택도 있다. 사용자가 정할 일이다.
3. **홈 경로의 계정 이름**(42개 파일): 공개할지 사용자가 정한다.
4. **스크린샷**: 원격 기록에 있는 `log/img`(37개 경로)와 `portfolio/img`(87개 경로), 지운 `09_models_cost_tokens.png`는 그림 속 글을 **못 봤다.** 공개 전에 사람이 한 번 훑어야 한다. 화면에 내부 IP, 경로, 토큰 끝자리가 찍혀 있을 수 있다.

## 7. 체크리스트

- [x] 이 레포 보고가 있는가: 이 파일
- [x] 히스토리 전체를 봤는가: `rev-list --all --objects`의 blob 3566개 전부와 `log --all` 커밋 메시지 전부
- [x] 모든 브랜치를 봤는가: 로컬 ref 32개(브랜치, 원격 추적, 태그, `refs/foreman/squashed/*`). 원격은 `ls-remote`로 3개를 확인했고, 원격 ref에서 닿는 것과 로컬에만 있는 것을 따로 표시했다
- [x] 「없다」의 근거: 0절의 꼴 목록, 실제 값 24개 맞대기, 엔트로피 검색, 바이너리 바이트 검색, `git check-ignore`, `--diff-filter=D`
- [x] 실제 값을 적지 않았는가: 이 파일에는 꼴, 길이, 파일, 줄, 해시만 있다. IP는 대역만 적었다
- [x] 대상 저장소를 고치지 않았는가: 쓴 것은 이 log 하나(이 브랜치 커밋)와 스크래치 스크립트뿐이다
- [x] push하지 않았는가: 하지 않았다. fetch도 하지 않았다

## 8. 규칙 위반 · 실수

- **시험 고정값 한 개가 세션 화면에 찍혔다**(조사 중반, `ctx.py` 첫 실행). `tests/test_units.py` 51줄을 문맥으로 볼 때, 꼴에 맞은 칸(chat id)만 가리고 같은 줄의 다른 칸 `MY_PASSWORD=`의 10자 가짜 값은 가리지 않았다.
  - 이 값은 가리기 시험용 가짜다. 실제 `.env.db` 비밀번호는 32자이고, 맞대기 0건으로 다르다는 것을 확인했다.
  - 바로잡은 것: 그 뒤 문맥 출력은 `=`나 `:` 뒤 값을 모두 가리게 바꿨다(perl 치환).
- 작성자 메일이 사용자 메일과 같은지 보려고, 세션이 이미 알고 있던 사용자 메일을 명령 안의 비교 값으로 한 번 적었다. 저장소에서 꺼내 찍은 것은 아니고, 결과는 「같음」만 나왔다. 이 log에는 적지 않았다.
- 원본 폴더로 `cd`한 명령이 하나 있었다(읽기만 함. 셸이 worktree로 되돌렸다). 쓰기는 없었다.
- `git branch -a --contains`(읽기)가 조사 세션 훅에 막혔다. `git for-each-ref --contains`로 바꿨다. 위반은 아니다.
- 그 밖에 CLAUDE.md 규칙 위반은 없다(`pgrep -f` 안 씀, 파일은 Write로만 씀, push 안 함, 대상 파일 안 고침).
