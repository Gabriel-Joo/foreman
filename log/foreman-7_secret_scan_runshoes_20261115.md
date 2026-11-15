# runshoes 공개 전 비밀값 점검 (2026-11-15, foreman-7)

관리자 410 조사 일감. 대상 `/home/kopo17/AI_programming/runshoes`를 읽기만 했다. 이 문서에는 값을 쓰지 않는다(파일, 줄, 커밋 해시, 꼴, 길이만).

## 본 범위와 방법

- ref: 로컬 `main`, `cc/runshoes-4`, `keep/441-copy-tone`, `refs/foreman/squashed/*` 13개, 태그 `archive/main-before-reword-20261112`, `archive/main-before-reword-20261113`, `origin/main`. 커밋 964개(`git rev-list --all`), stash 0개
- 원격(`git ls-remote origin`)에 있는 것: `main`, 태그 두 개(위 archive). 로컬 `origin/main`과 원격 `main`이 같다. 원격 ref에서 닿는 커밋 362개 + 태그, 로컬에만 있는 커밋 602개(`cc/*`, `keep/*`, `refs/foreman/squashed/*`는 Public에 올라가지 않는다)
- 지금 코드: `git ls-files` 전부를 값 가리는 스크립트로 스캔
- 히스토리: `git rev-list --objects --all`에서 닿는 blob 전부(경로 포함)와 모든 커밋 메시지, 커밋 작성자와 커미터 메일. 원격 ref만으로 한 번 더 돌려 비교
- 스크립트는 찾은 값을 앞 2글자와 길이로만, IP는 대역 종류로만 찍었다. 값이 진짜인지는 견본 낱말 포함 여부, 지금 코드 값과의 같음, 변수 참조 여부로만 판정했다
- 본 꼴: 텔레그램 봇 토큰, Anthropic `sk-ant-`, OpenAI `sk-`, GitHub `gh[pousr]_` `github_pat_`, Notion `secret_` `ntn_`, AWS `AKIA`, Google `AIza`, Slack `xox`, JWT `eyJ…`, 개인 키와 인증서 `-----BEGIN`, bcrypt 해시, 접속 문자열(mysql, postgres, mongodb, redis, amqp), `사용자:암호@` URL, Bearer, `password|secret|token|api_key… =|:` 할당, URL 쿼리 속 key, token, signature, IPv4(공인, 사설), 호스트:포트, 한국 휴대전화, 메일, 한국 도로명 주소, 주민번호 꼴, 카드번호 꼴
- 파일 이름: `.env*`, `*.pem`, `*.key`, `*.p12`, `*.crt`, `*.jks`, `id_rsa*`, `credentials*.json`, `*secret*`, `kubeconfig*`, `.npmrc`, `.netrc`, 지금 `.gitignore`가 막는 경로(`catalog/local/`, `catalog/loads/`, `runshoes_env/`, `contract/run/`, `.claude/settings.local.json`), 덤프와 백업. 히스토리에 한 번이라도 있던 경로 1020개, 지워진 파일 목록(`--diff-filter=D`)까지
- gitleaks, trufflehog는 이 서버에 없다(`command -v` 빈 결과)
- k8s 매니페스트는 이 저장소에 없다(인프라 저장소 몫). 본 배포 파일은 `Jenkinsfile`, `Dockerfile`, `Dockerfile.chatbot`, `docker-compose.yml`, `backend/src/main/resources/application*.yml`

## 1. 지금 코드에서 찾은 것

토큰 꼴(위 목록의 API 키, 봇 토큰, JWT, 개인 키, 인증서, bcrypt)은 0건이다. 비밀류 파일 이름도 0건이다.

| 파일:줄 | 무엇 | 판정 |
|---|---|---|
| `docker-compose.yml:18`, `:21` | 개발 MySQL root 암호(17자), 앱 암호(8자) 글자값 | 로컬 개발용. root 암호는 `-dev`로 끝난다. 앱 암호는 사용자 이름, 저장소 이름과 같은 값 |
| `contract/run-spring-local.sh:43` | 위 두 암호와 같은 값 | 같은 개발용 |
| `backend/src/main/resources/application.yml:12-13` | DB 사용자 이름과 암호의 env 기본값(각 8자, 위 앱 암호와 같은 값) | 운영은 env로 받는다. 다만 운영 env가 빠지면 이 약한 기본값으로 붙으려 한다 |
| `backend/src/main/resources/application.yml:30` | JWT 비밀 | env 참조, 기본값 없음(값 없으면 뜨지 않음). 문제 없음 |
| `backend/src/test/java/com/kopo17/runshoes/auth/JwtTest.java:36` | 시험용 HMAC 키 글자값(40자) | 시험 낱말이 든 견본. 문제 없음 |
| `chatbot/eval/login.py:21-22` | 가짜 체험 토큰 글자값(19자, 16자) | 평가용 가짜 서버 값(주석에 「가짜 /api/me」). 문제 없음 |
| `contract/scenarios.mjs:224-529` | 계약 시험용 암호 글자값 여러 개 | 시험 계정용. 문제 없음 |
| `Jenkinsfile:103` | 자격 증명 변수 이름 | 이름만, 값 아님 |
| 사설 IP 42줄, 서로 다른 주소 5개(192.168 대역 4개, 10. 대역 1개) | `Jenkinsfile:181`, `:205`(FOREMAN 브리지 웹훅 주소와 포트), `SummaryService.java:31`(GPU 호스트 주소와 포트), `catalog/load.mjs:3`, `contract/record.mjs:4`, `scripts/load-prod.sh:10`, `contract/baseline/node/index.json:3`(MetalLB VIP), `chatbot/eval/run.py:41`, `chatbot/search/embed.py:3`(모델 서비스 주소와 포트), `start_server.sh:12`, `backend/README.md:60`, `contract/README.md:31`, `:55`, docs 여러 곳(`05`, `06`, `09`, `HISTORY.md`, `archive/*`) | 내부망 주소와 포트. 밖에서 닿지 않지만 내부 구조가 드러난다. 10. 대역 하나는 `ChatbotMissTest.java:16`의 루프백 판정 견본 |
| 호스트:포트 22건 | 대부분 `log/doccheck_20261110.md`의 문서 점검 기록, `docs/07_database.md:108`, `catalog/decisions.json:12655` | 서비스 이름, ronanlab.dev 이름. 값으로 볼 것 아님 |
| 메일 176건 | 173건은 `runshoes.test` 시험 도메인, 2건 `git@github.com`(SSH 원격 꼴), 1건 `ronanlab.dev`의 jenkins 주소 | 개인 메일 0건 |
| 주민번호 꼴 5건 | `catalog/decisions.json`, `catalog/shoes.jsonl`, `catalog/todo-sources.csv` | 쇼핑몰 URL 속 상품 번호. 오탐 |

전화번호 꼴, 도로명 주소 꼴, 카드번호 꼴, 공인 IP는 지금 코드에 0건이다.

## 2. 히스토리에만 있는 것

토큰 꼴, bcrypt, 비밀류 파일 이름, 지워진 비밀 파일은 히스토리 전체(모든 ref)에서도 0건이다. `.env`, 키, 인증서, `catalog/local/`, `.claude/settings.local.json`이 커밋된 적이 없다.

| 위치 | 무엇 | 판정 |
|---|---|---|
| 옛 `Jenkinsfile`(blob `56c57689cb`, `a066f682f8`, `124746c1f1`, `b6c8e477d3`), 옛 `docs/INFRA.md`(blob `4b8baefacb`, `f0c7e7c224`, `3ebcb2d7d6`, `7b2ab0de37`, `f306ee7df1`) | 학교 GitLab으로 가는 `사용자:암호@` URL 9건 | 사용자 자리는 고정 낱말 6자, 암호 자리는 변수(`GIT_TOKEN`). 값 아님 |
| 옛 `Jenkinsfile:48` 등 10개 blob | `secretName` 할당 | k8s Secret 이름(18자). 값 아님 |
| 사설 IP와 포트 꼴 2개(그중 주소 1개는 지금 코드에 없음) | 옛 문서와 설정 | 내부망 주소. 지금 코드와 같은 성격 |
| 커밋 `4f665cdc93`(원격 태그 `archive/main-before-reword-20261113`에 있음), `39bc1d1b74`(원격 태그 `archive/main-before-reword-20261112`에 있음) 메시지 6번째 줄 | 사설 IP(192.168 대역) | 다시 쓴 지금 `main`에는 없고 원격 archive 태그에만 남았다 |
| 전화번호 꼴 4건, 옛 `yarn.lock` | 무결성 해시 속 숫자 | 오탐 |
| 커밋 작성자와 커미터 메일 3개(모든 ref, 셋 다 원격 ref에 있음) | 개인 gmail 2개(앞부분 8자, 6자), 다른 도메인 1개(10자) | Public이 되면 커밋마다 보이는 개인정보 |
| 커밋 메시지 메일 704건 | 702건 `anthropic.com`(`Co-Authored-By` 줄), 2건 견본 | 문제 없음 |

지금 코드에 없는 암호, 토큰 할당 값은 히스토리 전체에서 위 `secretName` 하나뿐이었다(값을 해시로 지금 코드와 맞대어 봄).

## 3. 폐기가 필요한 것

없다. 진짜 토큰, API 키, 운영 암호가 지금 코드에도 히스토리에도 들어간 적이 없다. 그래서 재발급할 것도 없다.
- 운영 비밀은 저장소 밖에 있다: Jenkins 자격 증명(Harbor 로봇, FOREMAN 웹훅 토큰), 클러스터 Secret `runshoes-mysql`, `runshoes-auth`
- 개발 DB 암호는 runshoes CLAUDE.md가 「운영과 다르다」고 적었다. 이번 조사는 운영 Secret을 보지 않아 같지 않음을 값으로 맞대어 보지는 않았다. 운영이 같은 값을 쓴다면 그때는 운영 DB 암호를 바꿔야 한다(클러스터 Secret `runshoes-mysql`, 인프라 관리자)

## 4. 그냥 지워도 되는 것(히스토리에 없고 지금만 있는 것)

없다. 지금 코드에서 찾은 것(개발 DB 암호, 사설 IP와 포트)은 모두 히스토리에도 있다. 지금 코드에서만 지우면 Public에서는 옛 커밋으로 그대로 보인다.

## 5. 판정

조치 먼저, 다만 가볍다. 폐기할 비밀은 없다. 사람이 정할 것이 셋이다.
1. 커밋 작성자 메일(개인 gmail 2개 등): Public에서 그대로 보인다. 받아들이거나, 히스토리를 다시 써서 GitHub noreply 메일로 바꾼다. 다시 쓰면 force push이고 원격 archive 태그 두 개도 같이 바뀐다(runshoes CLAUDE.md 「이력을 다시 쓰는 force push」의 Jenkins 전체 빌드 위험)
2. 내부망 IP와 포트(5개 주소, 42줄, 히스토리와 원격 archive 태그에도): 밖에서 닿지 않는 사설 대역이라 비밀은 아니다. 공개 기준(「서버 IP와 포트는 안 된다」)을 그대로 적용하면 지금 코드에서 변수나 이름으로 바꾸고, 히스토리까지 지우려면 위 1과 같이 다시 쓰기가 필요하다
3. 권장: `application.yml:12-13` DB env 기본값 지우기(운영 env가 빠지면 약한 값으로 붙으려 한다), `.gitignore`에 `*.pem`, `*.key`, `*.p12`, `kubeconfig*` 추가. 공개를 막는 것은 아니다

## 확인 체크리스트

- [x] 이 레포 보고가 있는가: 이 문서
- [x] 히스토리 전체를 봤는가: `rev-list --objects --all`의 모든 blob, 모든 커밋 메시지, 작성자 메일
- [x] 모든 브랜치를 봤는가: 로컬 브랜치 3개, `refs/foreman/squashed/*` 13개, 태그 2개, `origin/main`. 원격은 `main`과 태그 2개(로컬에만 있는 ref는 위 「본 범위」에 따로 적음)
- [x] 「없다」의 근거: 위 「본 범위와 방법」의 꼴 목록과 스캔 대상. 지워진 파일은 `git log --all --diff-filter=D --name-only`, 경로는 `git log --all --name-only`
- [x] 실제 값을 적지 않았는가: 이 문서에는 없다. 다만 조사 중 대화 화면에 한 번 찍혔다(아래)
- [x] 대상 저장소의 파일을 고치지 않았는가: 읽기 명령만 썼다(`ls-files`, `cat-file`, `log`, `for-each-ref`, `ls-remote`, `merge-base --is-ancestor`). fetch도 하지 않았다
- [x] push하지 않았는가: 하지 않았다

## 규칙 위반

- 2026-11-15 19:5x, 후보 줄 모양을 보는 명령에서 `docker-compose.yml:18`이 따옴표 없는 YAML 값이라 내 가림(따옴표 안만 가림)이 듣지 않아, 개발 MySQL root 암호(17자, 로컬 전용) 한 줄이 이 세션 대화 화면에 그대로 찍혔다. 까닭은 가림 식이 따옴표 글자값만 다룬 것. 그 뒤로는 `:`, `=` 뒤 글자도 길이로 가렸다
- 같은 명령에서 「앱 DB 기본 암호가 저장소 이름과 같은가: True」를 찍어, 개발용 앱 DB 암호가 사실상 화면에 드러났다. 판정 항목을 값과 맞대는 꼴로 만든 것이 까닭
- 두 값 모두 로컬 개발 DB 값이고 이미 저장소에 커밋되어 있는 값이라 새로 샌 비밀은 아니다. 이 문서와 커밋에는 값을 쓰지 않았다
- 그 밖에 규칙 위반 없음
