# 로드맵 8단계 — CI/CD 인과 체인: 조사 완료, 적용 보류 (+ 승인 규칙 "실행과 글자" 넓히기)

- **실행일**: 2026-11-02 (8 · 9단계 순서를 바꾼 뒤 — README 로드맵)
- **상태**: **조사 완료, 적용 보류.** 실제 파이프라인은 웹훅이 아니라 폴링이었다. FOREMAN은 "읽기 조회"로 끼어드는 방향으로 정했고(사용자 결정), **ArgoCD App of Apps를 먼저 한 뒤** 그 구조에 맞춰 만든다 — Application 구조가 바뀌면 FOREMAN이 보는 방식도 바뀌므로 지금 맞추면 두 번 일한다
- 커밋: `0178fd5`(웹훅 수신 · 로컬 git 폴링 — 지금은 꺼 둠), 이 문서 · 정리는 다음 커밋

## 지금 실제 설정 (11-02 조사 — App of Apps 작업 때 참고)

리포 파일이 아니라 **떠 있는 설정**을 읽었다(Jenkins 홈의 job `config.xml` · `build.xml` · `scm-polling.log`, 클러스터 ConfigMap · Secret 키 이름 · Application, Harbor DB). 아무것도 바꾸지 않았다.

| 구간 | 실제 | 근거 |
|---|---|---|
| GitHub → Jenkins | **SCM 폴링 2분**(`hudson.triggers.SCMTrigger`, spec `H/2 * * * *`, `ignorePostCommitHooks=false`). 웹훅 아님 | job `runshoes-app` · `petmint-app`의 live `config.xml`. 최근 빌드 원인이 모두 `SCMTrigger`. `scm-polling.log`에 2분마다 `git ls-remote https://github.com/Gabriel-Joo/<repo>.git`. 빌드 시작 시각이 늘 짝수 분 + 6~12초(08:20:06 · 09:34:12 · 21:04:08 — push 08:19:27 · 09:33:39 · 21:03:57). GitHub · webhook 플러그인 없음 |
| Jenkins job 정의 | JCasC job-dsl(`ronanlab-infra platform/jenkins/values.yaml`) — `pollSCM { scmpoll_spec('H/2 * * * *') }`, 파이프라인 본문은 앱 저장소 `Jenkinsfile`(lightweight) | 주석: "GitHub webhook 은 Access 에 막히므로(운영 도구는 인터넷에 열지 않는다, docs/13) 2분마다 폴링한다" |
| 터널(cloudflared, 클러스터 `cloudflared` ns) | tunnel `02ad6a13-…` 하나. `petmint` · `argocd` · `harbor` · `jenkins` · `runshoes` `.ronanlab.dev` → 모두 `ingress-nginx-controller.ingress-nginx.svc:443`(noTLSVerify), 나머지 404. 운영 도구(jenkins · argocd · harbor)는 Cloudflare Access 뒤 | ConfigMap `cloudflared-config`. 밖에서 `jenkins.ronanlab.dev/github-webhook/` · `/git/notifyCommit` · `/login` 모두 302(Access 로그인) — **GitHub 웹훅이 있어도 Jenkins에 닿지 못한다** |
| GitHub 웹훅 설정 | **읽지 못함** — 이 서버에 `gh` · GitHub 토큰이 없다. 등록돼 있다면 위 이유로 전달이 실패하고 있을 것(저장소 Settings › Webhooks › Recent Deliveries로 확인) | — |
| Jenkins → Harbor | Jenkinsfile 안에서 BuildKit이 push(robot `runshoes+jenkins` · `petmint+jenkins`). 태그 = `GIT_COMMIT` 앞 12자리, OCI 라벨 revision = 전체 SHA. 런슈즈는 이미지 둘(`runshoes` · `runshoes-chatbot`, 같은 태그) | 두 저장소 `Jenkinsfile` |
| Harbor 웹훅 정책 | **없음** | Harbor DB `registry.notification_policy` 0행 |
| Jenkins → 매니페스트 | Jenkinsfile 마지막 스테이지가 `ronanlab-infra apps/<앱>/kustomization.yaml` `newTag`를 12자리로 바꿔 커밋 · push(deploy key, 3번 재시도). 커밋 메시지에 앱 커밋 SHA · Jenkins 번호 | 두 저장소 `Jenkinsfile` |
| ArgoCD 감지 | **폴링 3분**(기본 — `argocd-cm`에 `timeout.reconciliation` 없음). 웹훅 아님 | `argocd-secret` 키에 `webhook.github.secret` 없음(키: admin.password · admin.passwordMtime · server.secretkey · tls.crt · tls.key). argocd.ronanlab.dev도 Access 뒤 |
| ArgoCD Sync | **런슈즈 자동**(`automated: {}` — prune · selfHeal 끔), **펫퍼민트 수동**(`automated` 없음) | Application `runshoes` · `petmint`의 live spec. 둘 다 `kubectl apply`로 넣은 것(`last-applied-configuration` 주석) — ArgoCD가 자기 Application을 관리하지 않는다 |
| ArgoCD 설치 | v2.13.2. `argocd-notifications-controller`가 떠 있지만 `argocd-notifications-cm` · `-secret`은 비어 있다 | — |
| 클러스터 Application | `cloudflared` · `monitoring` · `petmint` · `runshoes`(`ronanlab-infra platform/argocd/applications/`) | — |
| 배포된 태그 | 둘 다 앱 HEAD와 같다(runshoes `0f349e101774`, petmint `5f31a6e6649b`) | `kustomization.yaml` newTag |
| 호스트에서 닿는 길 | `*.ronanlab.dev` 이름은 Cloudflare(Access)로 간다. ingress VIP `192.168.122.240`(MetalLB, virbr0)에 Host 헤더로 닿는다 — http(80)도 열려 있다(ssl-redirect false). Jenkins `/login` · Harbor `/api/v2.0/ping` · ArgoCD `/api/version`은 인증 없이 200. 데이터 API는 401 · 403 | 호스트 curl |
| 클러스터에서 호스트 | 노드에서 `192.168.122.1`(virbr0) 닿음 | m-k8s에서 확인 |

즉 흐름은: **로컬 커밋 → GitHub push → (최대 2분) Jenkins 폴링 → 빌드 · Harbor push → 인프라 저장소 newTag 커밋 → (최대 3분) ArgoCD 폴링 → 런슈즈는 자동 Sync / 펫퍼민트는 사람이 Sync.**

## 처음 접근이 틀린 이유

처음에는 리포 파일(Jenkinsfile 머리말 · values.yaml)만 읽고 바로 설계해 웹훅을 "새로 붙이는" 쪽으로 갔다 — Jenkinsfile에 알림 단계 추가(push하면 두 앱이 다시 빌드 · 배포된다), Harbor 웹훅 정책 추가, ArgoCD notifications, 호스트에 웹훅 전용 포트. **이미 동작하는 흐름을 먼저 읽고 거기 맞췄어야 했다**(사용자 지적). 실제 설정을 읽어 보니 전 구간이 폴링이라, 관찰도 읽기 조회로 하면 기존 흐름에 아무것도 더할 필요가 없다. (클러스터 쪽 적용은 CC 자동 모드가 막아 실제로 바뀐 것은 없다.)

## 정한 방향 (적용은 App of Apps 뒤)

| 단계 | 끼어드는 법 | 기존 흐름에 닿는 것 |
|---|---|---|
| Jenkins | FOREMAN이 읽기 API를 조회(30초 남짓) — 빌드마다 결과 · 머리 SHA · 묶인 커밋(changeSets) · 스테이지별 상태(wfapi) | 없음. **읽기 토큰 하나**(사용자 › Security › API Token — App of Apps 뒤에 사용자가 만든다) |
| Harbor | 따로 받지 않는다 — push는 Jenkins "빌드·push" 스테이지 안이고 태그는 커밋 12자리. 생존만 `/api/v2.0/ping` | 없음 |
| ArgoCD | **① notifications 웹훅**으로 생각 중(동기화 동작은 그대로, FOREMAN이 ArgoCD 비밀을 갖지 않는다). App of Apps 구조를 보고 최종 결정 — 구독 범위 · 받는 주소가 그 구조에 달렸다 | 알림 설정 추가뿐 |

- **로컬 저장소 폴링은 뺀다** — 커밋 목록 · 묶인 커밋 · SHA는 Jenkins가 준다. "어느 세션이 만든 커밋인가"는 Jenkins가 알려 준 커밋의 제목 · 시각으로 그때 세션의 `git commit` 기록을 찾으면 된다. 잃는 것은 "push 전 · 빌드 대기 커밋" 표시 하나
- 그대로 쓸 것: 커밋 귀속 규칙(명령에 커밋 제목이 있어야 — 아래), `build` · `build_commit` 표, 대시보드 파이프라인 칸, 인프라 캐릭터 등장 · 생존 규칙, 실패 알림
- App of Apps 때 FOREMAN이 기대는 것: Application 이름(`runshoes` · `petmint`)과 앱 ↔ Jenkins job ↔ Harbor 프로젝트 대응(`config/pipeline.toml`), 펫퍼민트 수동 Sync(실패 판정이 "Sync 안 함"과 섞이지 않게), notifications 구독을 어디에 둘지(루트 앱 · 라벨 · 앱 주석)

## 재개할 때 다시 조사할 것 (11-03 기록 — 아직 아무것도 안 봄)

11-03에 펫퍼민트 세션에서 App of Apps 작업이 끝났고 웹훅을 거는 중이라고 사용자가 알려 왔다. **그 작업이 끝날 때까지 FOREMAN은 아무것도 하지 않는다**(조사도 하지 않음). 끝나면 위 "지금 실제 설정" 표를 다시 채우는 것부터 한다. 이 표의 11-02 값은 그때 낡은 것으로 본다. 보는 방법은 똑같이 live 설정을 읽기 전용으로 본다.

| 볼 것 | 11-02 값(비교 기준) | 확인할 곳 |
|---|---|---|
| **App of Apps에서 Application이 어떻게 나뉘는지**: 루트 앱 이름 · 자식 앱 목록 · 앱 이름이 `runshoes` · `petmint` 그대로인지 · 앱 하나에 무엇이 묶였는지(앱/플랫폼 분리 등) · `project`(AppProject) | 손으로 `kubectl apply`한 Application 4개(`cloudflared` · `monitoring` · `petmint` · `runshoes`), ArgoCD가 자기 Application을 관리하지 않음 | `kubectl -n argocd get applications`(+ `-o yaml`의 `ownerReferences` · `app.kubernetes.io/instance` 라벨), `appprojects`, `ronanlab-infra` 새 디렉토리 구조(`platform/argocd/…`), 루트 앱의 `source.path` |
| **웹훅이 걸리면 폴링이 없어지는지** — Jenkins 2분 | `SCMTrigger H/2`, GitHub 웹훅은 Cloudflare Access(302)에 막혀 닿을 수 없음 | job live `config.xml`의 트리거(`GitHubPushTrigger`? `SCMTrigger`가 남았나 · spec), 최근 `build.xml`의 원인(`GitHubPushCause` vs `SCMTriggerCause`), `scm-polling.log`가 계속 2분마다 도는지, 터널 · Access에 웹훅 경로 예외(bypass)가 생겼는지(`cloudflared-config`, 밖에서 `/github-webhook/` 응답 코드), 플러그인 목록 |
| **웹훅이 걸리면 폴링이 없어지는지** — ArgoCD 3분 | 기본 3분, `argocd-secret`에 `webhook.github.secret` 없음 | `argocd-secret` **키 이름만**(`webhook.github.secret` 생겼나), `argocd-cm`의 `timeout.reconciliation`, 밖에서 `argocd.ronanlab.dev/api/webhook` 응답 코드, 인프라 저장소 push → Application `status.reconciledAt`까지 걸린 시간. 웹훅을 걸어도 ArgoCD 폴링은 보통 꺼지지 않고(기본값 그대로 같이 돈다) 감지만 빨라진다 — 실제 값을 확인 |
| **FOREMAN이 ArgoCD 알림 웹훅(①안)을 붙일 자리** | `argocd-notifications-cm` · `-secret` 비어 있음. 초안 `deploy/cicd/argocd-notifications-foreman.yaml`(기본 구독 = 모든 앱) | ① 펫퍼민트 쪽이 notifications를 이미 쓰기 시작했나(cm · secret이 비었나, 누가 관리하나 — 인프라 저장소에 있으면 거기 더해야 한다. 손으로 `apply`하면 ArgoCD self-heal과 충돌할 수 있다) ② 구독을 어디에 둘지: cm의 기본 구독(`subscriptions`) · 자식 Application 주석(`notifications.argoproj.io/subscribe.<trigger>.foreman`) · AppProject 주석 중 무엇이 새 구조에 맞나 ③ 루트 앱이 자식 앱 정의를 관리하면 주석도 인프라 저장소에 넣어야 한다(손으로 붙이면 되돌려진다) ④ 받는 주소 `192.168.122.1:8001`(virbr0) — 노드에서 닿는지 다시 확인 |
| **펫퍼민트 수동 Sync가 유지되는지** | 런슈즈 `automated: {}`(prune · selfHeal 끔), 펫퍼민트 `automated` 없음 | 새 Application `spec.syncPolicy` 둘 다. 루트 앱 자신의 syncPolicy도. 수동이면 FOREMAN은 "OutOfSync로 기다림"을 실패가 아닌 별도 상태로 보여 준다 |

같이 볼 것: 앱 ↔ Jenkins job ↔ Harbor 프로젝트 대응(`config/pipeline.toml`)이 바뀌었나, `kustomization.yaml` newTag 자리(경로)가 그대로인가 — Jenkinsfile 마지막 스테이지가 거기를 고친다. 바뀐 것이 있으면 위 "정한 방향"(Jenkins 읽기 조회 · ArgoCD ①)을 다시 판단하고 사용자에게 먼저 보인다.

## 지금 상태 (보류 중)

- **브리지**: 파이프라인(로컬 git 폴링 · 웹훅 포트 8001 · 인프라 생존 폴링)을 **껐다**(`pipeline_enabled = False`). `/api/pipeline`은 `enabled: false`, 대시보드 파이프라인 칸은 안 보인다
- **남긴 코드**: `bridge/pipeline.py` · `bridge/api/webhooks.py` · `config/pipeline.toml` · `tests/test_pipeline.py`(시험은 그대로 통과) — 읽기 조회로 다시 만들 때 판정 · 연결 · 화면 · 알림 부분을 쓴다
- **지운 것**: Jenkinsfile 패치 2개, Harbor 웹훅 정책 스크립트, 클러스터 설정 스크립트(`scripts/cicd-apply.sh`). ArgoCD notifications 매니페스트(`deploy/cicd/argocd-notifications-foreman.yaml`)는 ① 후보라 **초안으로 남겼다**(적용 안 함, 머리말에 표시)
- **DB**: 마이그레이션 0012 적용됨(`git_commit` · `build` · `build_commit` · `character.last_seen_at`). `git_commit`에 최근 7일 커밋 83행(런슈즈 54 · 펫퍼민트 29)이 남아 있다 — 다시 만들 때 쓰거나 비운다. `build`는 비어 있다. 인프라 캐릭터는 만들어지지 않았다
- **`.env.bridge`의 `FOREMAN_WEBHOOK_TOKEN`**: 쓰는 곳 없음(ArgoCD ①로 가면 쓴다)

## 만들면서 확인한 것 (다시 만들 때 쓴다)

- **커밋 귀속은 "명령에 커밋 제목이 있어야"** — 처음엔 "커밋 시각 직전의 가장 가까운 `git commit` 호출"이었는데 실데이터에서 둘이 틀렸다: ① 런슈즈 세션이 `cd ~/ronanlab-infra && git commit`으로 인프라 저장소에 한 커밋이 런슈즈 커밋으로 잡혔다 ② 5분 안에 커밋이 여럿이면 가장 가까운 명령이 다른 커밋의 것이었다. 고친 규칙: 명령(1,024자 넘으면 원문)에 그 커밋 제목이 있으면 그것, 다른 제목을 줬거나 다른 저장소로 들어간 명령은 아니다, 메시지를 알 수 없는 명령(`git revert --no-edit`)만 가까운 것으로. 다른 프로젝트 세션(포먼 · '미분류')이 `cd <저장소> && git commit`한 것도 제목이 맞으면 귀속. 최근 7일: 런슈즈 52/54, 펫퍼민트 14/29 — **귀속된 66개 모두 제목 일치**(어림짐작 0)
- **실패 알림은 "실패로 바뀔 때 한 번"**, 늦게 온 running이 끝난 상태를 덮지 않는다(시험)
- **웹훅을 받게 되면**(ArgoCD ①): 브리지는 127.0.0.1에만 있어 VM에서 닿지 않는다. 같은 프로세스에 virbr0 전용 리스너를 두고, 웹훅 경로만 · VM 망 IP만(리눅스는 다른 인터페이스로 들어온 패킷도 받는다 — weak host) · 별도 토큰. 클러스터 노드에서 401 · 404 · 8000 차단을 확인했다

## 승인 규칙 — "실행과 글자" 넓히기 (사용자 요청, 이 단계 도중 — 적용됨)

승인 창이 자주 떠 흐름이 끊겼다. 걸린 것은 모두 오탐: grep 검색어 속 `rm -rf`, `mktemp -d` 디렉토리를 `${V:?}`로 지우기, `.env`에서 키 이름만 뽑기, `bash -n`으로 검사만 하는 스크립트 안의 `kubectl delete`, `.env` 토큰을 curl 헤더로만 넘기기. README 3.3 표에 넣었다.

- 방식: 검사 전에 "실행되지 않는 글자 · 값이 새지 않는 것이 명백한 모양"을 무해한 자리표시로 바꾼다(`bridge/approval.py` `_neutralize`). 조건이 하나라도 어긋나면 예전처럼 검사한다. allow 판정은 바꾸기 전 원문으로 하므로 **이 예외가 allow를 새로 만들지 않는다**
- `mktemp -d` + `${V:?}`는 허용 — 같은 명령에서 방금 만든 디렉토리만 지울 수 있게 좁혔다(한 번만 정해짐, 다시 정하기 · for · read · eval · source · `${V:=}` · export · unset 없음, 대상이 정확히 `"${V:?}"`). 앞 명령에서 만든 디렉토리를 경로로 지우는 것은 확인할 수 없어 여전히 묻는다
- 헤더 토큰은 "화면에 안 찍힌다"에 더해 "**밖으로 안 간다**" — `-v` · `--trace` · `--libcurl`이 없고, 보내는 곳이 127.0.0.1 · VM 망이며 변수가 아닐 때만
- 다시 돌려 보다 찾은 **빈틈**: python heredoc으로 `.env.db`를 쓰는 명령이 어느 규칙에도 안 걸렸다(옛 규칙은 같은 명령 끝의 `cut -d= -f1 .env.db` 때문에 우연히 물었다) → 해석기 heredoc이 비밀 파일을 쓰거나 바로 찍으면 묻는다. 읽기만(앱이 설정을 읽는 것)은 5단계 결정대로 묻지 않는다
- 다시 돌려 보기 도구: `scripts/approval-replay.py`(DB의 과거 도구 호출에 옛 규칙(git REV)과 지금 규칙)

| 프로젝트 | 활동한 날 | 옛 규칙 ask/일 | 새 규칙 ask/일 |
|---|---|---|---|
| 런슈즈 | 10 | 14.5 | 14.4 |
| 펫퍼민트 | 16 | 6.6 | 6.6 |
| 포먼 | 1(오늘) | 59 | 49 |
| 미분류 | 2 | 6.0 | 7.0(위 빈틈 — python으로 비밀 파일 쓰기) |

- **이 세션의 7 · 8단계 작업(20:30 이후, 도구 호출 304개): 10 → 3.** 남은 3개는 묻는 게 맞다 — `.env.bridge`에 토큰 쓰기, 토큰 값을 임시 파일로 옮기기, 테스트 문자열에 `rm -rf`가 든 python heredoc
- 포먼 하루 49는 대부분 이전 단계의 것 — 앞 명령에서 만든 임시 디렉토리를 경로로 지우기, 글롭 루프 삭제. 만들기와 지우기를 한 명령에 두면 묻지 않는다
- **고치지 않은 오탐**: `git -C $d status`가 "git 동사 자리가 변수"(애매한-운영명령)로 걸린다 — `-C`가 값을 받는 옵션인 것을 `verb_re`가 모른다. `config/approval.toml` 정규식이라 보호 파일 쓰기 승인이 필요하다 — 다음 후보
- 6단계 표(런슈즈 7.2)는 20일로 나눴고 지금은 활동한 날로 나눈다(같은 총량 약 145건)
