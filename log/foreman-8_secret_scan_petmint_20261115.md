# petmint-rag-chatbot 공개 전 비밀값 · 개인정보 점검 (2026-11-15, worktree foreman-8)

관리자 410 조사 일감(사용자 지시 「공개 전 비밀값 점검」). 대상 저장소는 읽기만 했다. 이 기록에는 찾은 값을 쓰지 않는다(파일 · 줄 · 커밋 해시 · 종류 · 길이만).

## 1. 본 범위

- ref: 로컬 `refs/heads/main`, `refs/remotes/origin/main`, 태그 `archive/main-before-reword-20261113`(annotated). 그 밖의 ref 없음(`git for-each-ref`), stash 0, worktree는 원본 하나
- 원격(`git ls-remote origin`): `HEAD`, `refs/heads/main`, `refs/tags/archive/main-before-reword-20261113` — **태그도 GitHub에 올라가 있다.** 로컬 main과 원격 main은 같은 커밋
- 커밋 425개 = main 213 + 태그로만 닿는 옛 이력 212(태그 설명: 커밋 메시지만 다시 쓰기 전 이력, 내용은 같음). **로컬에만 있고 원격에 없는 커밋 0** — 즉 본 것 전부가 Public이 되면 보인다
- 객체: 모든 ref에서 닿는 blob 1,255개(바이너리 35개 제외, 20MB 넘는 것 0) 전부 + 커밋 메시지 425개 + 태그 객체 1개 + 작성자/커미터 메일
- 히스토리 전체 파일 이름 503개(한글 이름 포함, `core.quotePath=false`)
- 원본 폴더의 추적 안 하는 파일 59개, 무시된 파일(`.env`, `app/fixtures/customers.json`)

## 2. 방법(값을 찍지 않게)

- `gitleaks` · `trufflehog` · `detect-secrets`는 이 서버에 없다(`command -v`)
- 스크래치에 가리는 스캐너를 써서 `.venv/bin/python`으로 돌렸다. 값은 앞 2글자 + 길이로만, IP는 대역 분류(공용 DNS / 기타 공인 / 사설 192.168 / 사설 기타 / loopback)로만, 메일은 도메인 분류로만, 줄 맥락은 모든 꼴을 `[가림:종류#번호 N자]`로 바꿔서 봤다
- 꼴 목록: 텔레그램 봇 토큰, `sk-ant-`, `sk-`(OpenAI), `gh[pousr]_`, `github_pat_`, `secret_` · `ntn_`(Notion), `AKIA`/`ASIA`, `AIza`, `hf_`, `xox?-`, JWT(`eyJ…`), `-----BEGIN … PRIVATE KEY`/`CERTIFICATE`, 접속 문자열(`mysql://` · `postgres://` · `mongodb` · `redis://` · `amqp://`), URL 안 `사용자:비밀번호@`, `password|passwd|pwd|…_PASSWORD = / :`, `…token|secret|api_key|access_key = / :`, 키 이름 끝말 확장판(`*_PASSWORD`, `*_SECRET`, `*_TOKEN`, `*ACCESS_KEY`, `*credential*`, `*auth*` 대입), `Bearer`, IPv4, `호스트:포트`, 휴대전화 `01x-`, 지역번호 전화, 주민등록번호 꼴, 카드번호 꼴, 메일, 한국 주소 꼴(시/도 구/군 로/길/동 번지), UUID, Cloudflare(`cfargotunnel` · `TUNNEL_TOKEN` · `CLOUDFLARE_API`)
- 비밀값 파일 이름 꼴: `.env*`, `.pem`, `.key`, `.p12`, `.crt`, `id_rsa`, `credential`, `secret`, `kubeconfig`, `customers`, `.sqlite`, `.db`, `.dump`, `.sql.gz`, `.csv`, `.xls*`, `.pdf`, `backup`
- 값을 판정할 때도 스크립트가 꼴만 봤다(변수 참조 `$…` / 견본 낱말 / 빈 값 / 숫자 / 식별자)

## 3. 결과

### 3-1. 지금 코드에서 찾은 것

비밀값(토큰 · 키 · 비밀번호 · 접속 문자열 · 개인 키 · 인증서): **0건.** 걸린 것은 모두 진짜 비밀값이 아니었다.

| 파일:줄 | 무엇 | 판정 |
| --- | --- | --- |
| `.env.example` | DB 계정 4묶음 · 호스트 · 포트 | 비밀번호 칸 모두 빈 값. 호스트는 loopback, 사용자 이름은 앱 계정 이름. 옛 판 8개(`9029301` `0e0944e` `0c983fa` `dc60334` `1fb8270` `33b1a81` `f4809cd` `2c6ff32`)도 비밀번호 · 토큰 줄이 모두 빈 값 |
| `Jenkinsfile:100`, `:109` 근처 | Harbor 자격 증명 | `withCredentials`로 셸 환경변수만 받음. `credentialsId`는 Jenkins 자격 증명 이름(값 아님) |
| `docs/ops/저녁실행.md:381` | Grafana admin 비밀번호 대입 | 셸 변수 `$P` 참조(값 없음) |
| `CLAUDE.md:122` 근처 | FOREMAN 프로젝트 토큰 | 파일에서 읽는 명령만, 값 없음 |
| `tests/test_auth.py:185~384` | IP 4개, 시험 비밀번호 | 시험용 고정값(사설 기타 대역 · 문서용 대역) |
| `app/services/answer.py:57`, `web/src/pages/ModeSelect.tsx:55`, `data/eval/requirements-ragas.txt:88`, `notebooks/01_데이터_전처리.ipynb:612` | `*token* =` | 글자 수 비율 상수, 카운터, 패키지 버전, 정규식 |
| `data/review/faq_rewrite_rewrite_20261015_1245.md:1249,2012,2355`, `notebooks/01_데이터_전처리.ipynb:1936` | 지역번호 전화 5가지 | 신용정보회사 · 손해보험협회 · 보험사 대표번호(약관 원문). 개인 번호 아님 |
| `app/fixtures/customers.example.json` | 고객 견본 3명(이름, 전화 1개) | 전화는 `01x`로 시작하지 않고 가운데 4자리가 0인 가짜 꼴. 진짜 픽스처 `customers.json`은 `.gitignore`에 있고 히스토리에 한 번도 없음 |
| `db/fixtures/employees.json`, `data/eval/hr_personal.json`, `db/migrations/insurance_core/0004_employee_rename.sql` 등 7개 | 직원 메일 23가지, 이름 11명, 생년월일 11개 | 메일 도메인이 예약 TLD(`.example`)인 가상 직원(저장소 CLAUDE.md 「가상 인사규정」). 이름이 실존 인물과 겹치는지는 확인할 수 없음 |
| 노트북 9개 | 출력 칸 138개, UUID | 토큰 꼴 0. UUID는 셀 ID |

공개 여부를 사람이 정할 것(비밀값은 아니지만 사용자가 「안 된다」고 한 종류):

| 무엇 | 어디 |
| --- | --- |
| **사설 IP 4개(192.168 대역 한 /24 안: GPU 호스트, MetalLB VIP 등)와 그 포트들** | HEAD 23개 파일: `Jenkinsfile`, `README.md`, `data/chunks_v2.py`, `data/model_client.py`, `data/review/verify_modes_20261021.md`, `deploy/README.md`, `deploy/host/milvus/docker-compose.yml`, `deploy/host/petmint-search.service`, `deploy/scripts/host-nfs-backup-setup.sh`, `deploy/scripts/host-nfs-setup.sh`, `docs/02_pipeline/08_ragas_eval.md`, `12_data_storage.md`, `13_access_and_tunnel.md`, `14_deployment.md`, `15_monitoring.md`, `docs/ops/모드검증.md`, `docs/ops/저녁실행.md`, `docs/pipeline.md`, `log/doccheck_20261110.md`, `scripts/rebuild5_chain.sh`, `scripts/rebuild5b_chain.sh`, `scripts/search_parity.py`, `search_service/main.py` |
| 서버 사용자 이름이 든 홈 경로(`/home/<사용자>/…`) | 모든 ref의 blob 64개 |
| Cloudflare 터널 UUID 1개(자격 증명 아님, 터널 식별자) | `docs/02_pipeline/13_access_and_tunnel.md:34` |
| 내부 구성 서술(터널 · Access 정책 · 2026-11-09 Ollama 터널이 열려 있던 사고 기록, 지금은 Service Token으로 막혔다고 적힘) | `docs/02_pipeline/13_access_and_tunnel.md:1,56~59` |

공인 IP: 공용 DNS 리졸버(잘 알려진 것) 120곳과 Vagrant 박스 기본 DNS 1개(7자)뿐. **서버 공인 IP 0.**

### 3-2. 히스토리에만 있는 것

비밀값: **0건.** `.env` · `.env.telegram`이 커밋된 적 0(`git log --all -- .env .env.telegram`). 지운 파일 중 이름이 걸린 것은 `deploy/scripts/create-secrets.sh` 하나(커밋 `033751d` `c742df7` `3afae1b` `8e497a0`, 2026-10-15~16) — 클러스터에서 `openssl rand`로 무작위 값을 만드는 스크립트이고 값은 없다.

| 커밋 / 파일 | 무엇 |
| --- | --- |
| `deploy/app/configmap.yaml`, `deploy/data/nfs.yaml`, `docs/13_access_and_tunnel.md`, `docs/14_deployment.md`, `docs/15_monitoring.md`, `docs/저녁실행.md`(지금은 옮겨지거나 지워진 옛 경로) | 같은 사설 IP · 포트 |
| 커밋 메시지 13개. main 7개: `173f441a0192` `56cb2aae2aeb` `579c0dc1a7d0` `65124fee1c5b` `6d1aeeb2835f` `74397ed847d7` `f0c24b8f610e`. archive 태그 옛 이력에만 6개: `17da4b997778` `2b4d3ce8655e` `636df792b264` `93dba1920b08` `96dcab54123b` `b0f2df6eceac` | 사설 IP(192.168) |
| `docs/09_ui_design.md:272~309`(옛 판) | 휴대전화 꼴 1가지 — 견본 번호 꼴(1234/5678 류) |
| **작성자 · 커미터 메일: 425개 커밋 전부 + 태그 작성자** | 개인 gmail 주소 1개(도메인 gmail.com). Public이면 GitHub에서 커밋마다 보인다 |
| 커밋 메시지 메일 421곳 | 모두 `Co-Authored-By` 줄의 anthropic.com 주소 |

### 3-3. 폐기가 필요한 것

**없다.** 찾은 토큰 · 키 · 비밀번호 값이 0이라 재발급할 것이 없다.

### 3-4. 그냥 지워도 되는 것(히스토리에 없고 지금만 있는 것)

**없다.** 지금 코드에 있는 것은 모두 히스토리에도 있다. 추적하지 않는 파일(`data/review/` 57개, `data/search_experiments.py`, `data/eval/ragas_pilot_set.json`)에서 비밀값 꼴 든 파일 0. 무시된 `.env` · `customers.json`은 올라간 적이 없고 `.gitignore`가 막고 있다.

### 3-5. 판정

- **비밀값 기준으로는 지금 Public으로 돌려도 된다.** 토큰 · 키 · 비밀번호 · 개인 키 · 접속 문자열이 현재 코드에도, 원격에 올라간 두 ref(main, archive 태그)의 히스토리 전체에도 없다
- 다만 돌리기 전에 사람이 정할 것이 둘 있다
  1. **작성자 gmail 공개** — 425개 커밋 전부에 들어 있어 지우려면 모든 이력을 다시 쓰고 force push해야 한다(저장소 CLAUDE.md상 사람 승인, Jenkins 전체 빌드와 자동 Sync가 뒤따름). 받아들일지, 다시 쓸지
  2. **사설 IP · 포트 · 홈 경로 · 터널 UUID** — 사용자가 「서버 IP와 포트는 안 된다」고 했다. 인터넷에서 닿지 않는 사설 주소지만, 지우려면 HEAD를 고치는 것만으로는 히스토리 · 커밋 메시지 · archive 태그에 남는다. 받아들일지, 이력 다시 쓰기(태그 포함)를 할지
- 둘 다 받아들이면 조치 없이 Public 가능. 하나라도 지우기로 하면 **조치 먼저**(이력 다시 쓰기 + archive 태그 처리 + force push)

## 4. .gitignore

- 막는 것: `.env`, `.env.telegram`, `app/fixtures/customers.json`, `models/`, `data/raw_pdf/` 등 원본 데이터, `backups/`, `logs/`, `*.log`, `.claude/*`(`agents/`만 허용)
- 막기 전에 올라간 비밀값 파일: 없음(`.env*`는 `.env.example`만 이력에 있음)
- 막지 않는 것: `*.pem` · `*.key` · `.env.*`(`.env.example` 말고 다른 이름) — 지금 그런 파일은 없지만, 넣어 두면 실수로 올라가는 길이 닫힌다(제안, 고치지 않음)

## 5. 남은 미검증

- 가상 직원 · 고객 이름이 실존 인물과 겹치는지는 확인할 수 없다(꼴로만 봄)
- 한국어 이름 · 주소는 꼴로만 찾았다(주소 꼴 0, 주민번호 꼴 0, 카드번호 꼴 0). 자유 서술 속 실명은 꼴로 못 잡는다
- 바이너리 blob 35개(이미지 등)는 내용을 보지 않았다

## 6. 규칙 위반

- 비밀값(토큰 · 비밀번호 · 키)은 화면에도 이 기록에도 찍히지 않았다
- **다만 화면(이 세션 대화)에 포트 번호가 찍혔다.** 맥락을 보는 스크립트가 IP만 가리고 포트는 남겨, 터널 · 배포 문서 줄을 볼 때 search-service · model-service · Ollama 포트 숫자가 대화에 나왔다(사설 IP는 가려짐). 저장소 CLAUDE.md를 읽을 때 loopback 주소와 포트, 시크릿 스크립트를 볼 때 Harbor robot 계정 이름과 Grafana admin 사용자 이름(비밀번호 아님)도 나왔다. 일감은 「보고서와 log에 포트 값을 쓰지 않는다」이므로 이 기록과 보고에는 쓰지 않았다. 다음 스크립트부터는 `:숫자`도 가렸어야 했다
- 그 밖에 규칙 위반 없음: 대상 저장소에 쓰기 · checkout · stash · fetch · push 없음, 파일은 Write로만, `pgrep -f` 안 씀, 서브에이전트 안 씀
