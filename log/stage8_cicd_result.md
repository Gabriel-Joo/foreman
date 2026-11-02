# 로드맵 8단계 — CI/CD 인과 체인 (+ 승인 규칙 "실행과 글자" 넓히기)

- **실행일**: 2026-11-02 (8 · 9단계 순서를 바꾼 뒤 — README 로드맵)
- **11-03**: App of Apps · 웹훅 뒤 재조사 완료(아래 "11-03 재조사"). 그 뒤 Jenkins 연동을 API 조회에서 **Jenkinsfile 알림 + 토큰 없는 보정**으로 바꿨다 — "새도 되는 비밀의 무게"(아래). **Jenkins 부분 적용 완료**(아래 "11-03 적용 결과"). 남은 것: ArgoCD 알림 웹훅, 펫퍼민트 "Sync 대기" 표시
- **상태(11-02)**: **조사 완료, 적용 보류.** 실제 파이프라인은 웹훅이 아니라 폴링이었다. FOREMAN은 "읽기 조회"로 끼어드는 방향으로 정했고(사용자 결정), **ArgoCD App of Apps를 먼저 한 뒤** 그 구조에 맞춰 만든다 — Application 구조가 바뀌면 FOREMAN이 보는 방식도 바뀌므로 지금 맞추면 두 번 일한다
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

## 정한 방향 (적용은 App of Apps 뒤)

| 단계 | 끼어드는 법 | 기존 흐름에 닿는 것 |
|---|---|---|
| Jenkins | **(11-03 바뀜 → Jenkinsfile 알림 + 토큰 없는 보정, 아래 "Jenkins 연동 방식")** ~~FOREMAN이 읽기 API를 조회(30초 남짓)~~ — 빌드마다 결과 · 머리 SHA · 묶인 커밋(changeSets) · 스테이지별 상태(wfapi) | 없음. **읽기 토큰 하나**(사용자 › Security › API Token — App of Apps 뒤에 사용자가 만든다) |
| Harbor | 따로 받지 않는다 — push는 Jenkins "빌드·push" 스테이지 안이고 태그는 커밋 12자리. 생존만 `/api/v2.0/ping` | 없음 |
| ArgoCD | **① notifications 웹훅**으로 생각 중(동기화 동작은 그대로, FOREMAN이 ArgoCD 비밀을 갖지 않는다). App of Apps 구조를 보고 최종 결정 — 구독 범위 · 받는 주소가 그 구조에 달렸다 | 알림 설정 추가뿐 |

- **로컬 저장소 폴링은 뺀다** — 커밋 목록 · 묶인 커밋 · SHA는 Jenkins가 준다. "어느 세션이 만든 커밋인가"는 Jenkins가 알려 준 커밋의 제목 · 시각으로 그때 세션의 `git commit` 기록을 찾으면 된다. 잃는 것은 "push 전 · 빌드 대기 커밋" 표시 하나
- 그대로 쓸 것: 커밋 귀속 규칙(명령에 커밋 제목이 있어야 — 아래), `build` · `build_commit` 표, 대시보드 파이프라인 칸, 인프라 캐릭터 등장 · 생존 규칙, 실패 알림
- App of Apps 때 FOREMAN이 기대는 것: Application 이름(`runshoes` · `petmint`)과 앱 ↔ Jenkins job ↔ Harbor 프로젝트 대응(`config/pipeline.toml`), 펫퍼민트 수동 Sync(실패 판정이 "Sync 안 함"과 섞이지 않게), notifications 구독을 어디에 둘지(루트 앱 · 라벨 · 앱 주석)

## 11-03 재조사 — App of Apps · 웹훅 뒤 (위 11-02 표보다 이것이 지금 값)

런슈즈 · 펫퍼민트 세션이 App of Apps로 바꾸고 웹훅을 건 뒤(사용자: "폴링은 안전장치로 15분만"), 아래 "재개할 때 다시 조사할 것" 네 가지 + 빌드 원인 구분을 live 설정으로 읽었다(읽기 전용 — `kubectl get` · `logs`, Jenkins 홈 `config.xml` · `build.xml`, `~/ronanlab-infra` = 클러스터 리비전 `79e5679`). 바꾼 것 없음. 조사 시각 2026-11-03 07:00 무렵(KST).

| 볼 것 | 지금 | 근거 |
|---|---|---|
| Application 구조 | **루트 `root`**(`bootstrap/root-app.yaml`, 사람이 한 번 apply) → `apps/` 아래 `*/app.yaml`만 읽어 자식 Application을 만든다(directory recurse + include, `monitoring/app.yaml`은 exclude — 클러스터에 없음). 자식: **`runshoes` · `petmint` · `cloudflared` — 이름 그대로**. 자식에는 라벨 `app.kubernetes.io/instance=root`, 루트에는 없음. AppProject는 `default` 하나. 루트: 자동 Sync(prune · selfHeal 끔), finalizer 없음, `ignoreDifferences /spec/syncPolicy` + `RespectIgnoreDifferences` — **자식의 Sync 방식은 루트가 덮지 않고 클러스터의 값이 진짜 스위치**(`app.yaml`은 기록). `platform/`(Jenkins · Harbor · ingress · argocd ingress …)은 ArgoCD 밖 | `kubectl -n argocd get applications,appprojects`, 인프라 저장소 `740f9dd` · 루트 머리말 |
| Jenkins 감지 | **웹훅 + 폴링 15분(안전망).** job `config.xml` 트리거 = `com.cloudbees.jenkins.GitHubPushTrigger` + `hudson.triggers.SCMTrigger H/15`. github 플러그인 1.47.0, 서명 검증 SHA-256(Secret `jenkins/github-webhook-secret`, 두 앱 저장소가 같이 씀). Cloudflare Access는 `/github-webhook/`만 Bypass — 밖에서 GET 405(Jenkins까지 닿음), `/login`은 그대로 302 | live `config.xml`, 인프라 `734319f`, 밖에서 curl. Jenkins 로그 06:55:30 `Received PushEvent … petmint-rag-chatbot` → `Poked petmint-app` → `Triggering #48` |
| 웹훅 검증 상태 | **펫퍼민트 ✅**(#46 · #47 · #48이 웹훅 원인). **런슈즈 ⚠ 아직 검증 안 됨** — 웹훅을 건 뒤 빌드가 없다(마지막 #51은 11-02 21:04, 폴링 원인). 다음 런슈즈 push 때 원인이 `GitHubPushCause`인지 본다 | `build.xml` causeBag |
| ArgoCD 감지 | **웹훅 + 폴링 3분(기본 그대로).** `argocd-secret`에 `webhook.github.secret` 키가 생겼다. `argocd-cm` · `argocd-cmd-params-cm`은 비어 있어 `timeout.reconciliation` 기본 180초 — 컨트롤러 로그에 3분마다 `comparison expired` 새로 고침이 계속 있다. 웹훅은 06:43부터 `Received push event repo: …/ronanlab-infra` → `normal refresh requested`(그 전 06:23~06:37에 서명 실패 · 헤더 없음 몇 번 — 설정 중). 밖에서 `/api/webhook` GET 400(ArgoCD까지 닿음). **"15분 안전망"은 Jenkins만이다** — ArgoCD는 그대로 3분(부담이 작아 그대로 둬도 된다, 사용자에게 알림) | 키 이름만 봄, `argocd-server` · 컨트롤러 로그 |
| ① 붙일 자리 | `argocd-notifications-cm` · `-secret` **여전히 비어 있음, git으로 관리하지 않는다**(ArgoCD 설치물은 ArgoCD 밖) — 손으로 넣어도 되돌려지지 않는다. **기본 구독(`subscriptions`)에 셀렉터 `app.kubernetes.io/instance=root`** 로 건다(사용자 결정) — 자식 전부 · 앞으로 더할 앱이 자동으로 들어오고 루트는 빠진다. 앱 주석 방식은 루트가 `app.yaml`을 관리해 인프라 저장소를 고쳐야 해서 버림. 받는 주소 `192.168.122.1:8001` — 알림 컨트롤러 **파드**에서 닿는지는 적용 때 확인(11-02엔 노드에서만 봤다) | 키 이름 · 데이터 비어 있음 확인 |
| 펫퍼민트 Sync | **수동 유지**(`syncPolicy`에 `automated` 없음). 런슈즈 자동(`automated: {}`), cloudflared 수동. 루트가 자식 syncPolicy를 덮지 않으니 바뀌지 않는다 → FOREMAN은 펫퍼민트 OutOfSync를 **"Sync 대기 중"** 으로, 실패와 따로 보여 준다 | live `spec.syncPolicy` |
| 그 밖 | ArgoCD v2.13.2 그대로. 앱 ↔ Jenkins job ↔ Harbor 대응(`config/pipeline.toml`) · `apps/<앱>/kustomization.yaml` newTag 자리 그대로 — 바꿀 것 없음 | — |

### 빌드가 웹훅으로 시작됐는지 폴링으로 시작됐는지 — 구분된다

빌드마다 원인(cause) 클래스가 남는다: 웹훅 `com.cloudbees.jenkins.GitHubPushCause`(펫퍼민트 #46~48), 폴링 `hudson.triggers.SCMTrigger$SCMTriggerCause`(그 전 전부 — XML에는 `SCMTrigger_-SCMTriggerCause`), 손으로 누름 `hudson.model.Cause$UserIdCause`. API 한 번이면 읽힌다: `/job/<job>/api/json?tree=builds[number,timestamp,result,actions[causes[_class]]]`. **익명 읽기는 403** → 읽기 토큰이 필요하다.

웹훅 끊김 규칙(재개 범위): SCM 폴링은 바뀐 것이 있을 때만 빌드를 시작하므로 웹훅이 살아 있으면 폴링 원인 빌드는 거의 생기지 않는다 → **"웹훅 원인 빌드가 있던 job에서 폴링 원인 빌드가 연달아 2번"이면 끊김으로 알린다.** 보조 신호로 push → 빌드 시작 지연(웹훅 수 초, 폴링 최대 15분). ArgoCD 웹훅 끊김은 FOREMAN이 직접 보기 어렵다 — 인프라 커밋 → 반영이 3분 가까이로 늘어나는 것이 간접 신호.

### Jenkins 인증 구조 (토큰 계정 판단 근거)

`authorizationStrategy` = `FullControlOnceLoggedInAuthorizationStrategy`(익명 읽기 거부), 보안 영역은 Jenkins 자체 사용자 DB(가입 막힘). matrix-auth · role-strategy 플러그인 없음 → **로그인한 사용자는 누구나 전체 권한이다. 지금 구조로는 "읽기 전용 계정"을 만들 수 없다.** 사용자는 `admin`(JCasC가 기동 때마다 Secret `jenkins/jenkins-admin`으로 비밀번호를 다시 넣는다)과 `cjswoduf` 둘. 결정: 전용 계정 `foreman`을 만들어 그 계정의 API 토큰을 쓴다(권한은 같지만 토큰을 따로 끊을 수 있고, Jenkins 기록에 `foreman`으로 남고, admin 비밀번호 교체에 안 엮인다). FOREMAN 쪽은 GET만 하도록 코드에서 막는다. 진짜 읽기 전용이 필요하면 인프라 저장소에서 matrix-auth(플러그인 목록 + JCasC `authorizationStrategy`)로 — 잘못 넣으면 잠기므로 그쪽 세션의 일.

### 재개 범위 (11-03 사용자 확정 — Jenkins 부분은 아래 "Jenkins 연동 방식"에서 알림으로 바뀜)

~~Jenkins 읽기 조회~~ → Jenkinsfile 알림 + 토큰 없는 보정 · ArgoCD 알림 웹훅(기본 구독 + `instance=root`) · 웹훅 끊김 감지(폴링 원인 연속 2번) · 대시보드 파이프라인 표시(펫퍼민트 "Sync 대기 중"은 실패와 구분) · 인프라 캐릭터 등장. 런슈즈 웹훅은 다음 push 때 확인.

## Jenkins 연동 방식 — "새도 되는 비밀의 무게"로 골랐다 (11-03 사용자 결정)

### 두 방식

| | 기존 흐름에 닿는 것 | 필요한 비밀 |
|---|---|---|
| **API 조회** — FOREMAN이 Jenkins 읽기 API를 주기적으로 부른다 | 없음(Jenkins 설정 · Jenkinsfile 그대로) | **Jenkins API 토큰**(FOREMAN 호스트에 둔다) |
| **Jenkinsfile 알림** — 빌드가 FOREMAN에 알린다 | Jenkinsfile에 몇 줄(두 앱 저장소) + Jenkins 자격 증명 하나 | **FOREMAN이 받는 쪽 토큰**(Jenkins가 보낼 때 쓴다) |

처음에는 "기존 파이프라인을 건드리지 않는다"를 우선해 API 조회로 정했다. 토큰을 만들기 직전에 그 토큰이 무엇을 열 수 있는지 다시 따졌고, 선택이 뒤집혔다.

### 토큰의 무게 — live 설정으로 확인한 것

1. **"읽기 전용 토큰"을 만들 방법이 없다.** Jenkins 권한 방식이 `FullControlOnceLoggedInAuthorizationStrategy`(로그인하면 전체 권한)이고 matrix-auth · role-strategy 같은 권한 플러그인이 없다(Jenkins 홈 `config.xml`, 플러그인 목록). 전용 계정 `foreman`을 만들어도 admin과 권한이 같다
2. **그 토큰은 Jenkins 관리자 권한이다.** API 토큰으로 Script Console(`/script`)에 Groovy를 보내면 컨트롤러 안에서 임의 코드가 돈다. 저장된 자격 증명도 복호화해 꺼낼 수 있다 — Harbor push robot 두 개(`harbor-robot-petmint-jenkins` · `harbor-robot-runshoes-jenkins`)와 **ronanlab-infra 쓰기 deploy key**(`ronanlab-infra-deploy-key`, JCasC `values.yaml`)
3. **infra 쓰기 = 배포.** 런슈즈는 자동 Sync라 `apps/runshoes/kustomization.yaml`의 이미지를 바꿔 push하면 그대로 배포된다. 그리고 **App of Apps 뒤로는 런슈즈에 그치지 않는다** — 루트 `root`가 자동 Sync이고 `apps/*/app.yaml`을 읽어 Application을 만들므로, `apps/<아무거나>/app.yaml`에 자동 Sync Application을 하나 더하면 루트가 만들고 그 Application이 매니페스트를 깐다. AppProject는 제한 없는 `default`라 대상 네임스페이스도 정하기 나름이다. 펫퍼민트의 수동 Sync도 이 길을 막지 못한다
4. 즉 **"읽기용"으로 생각한 토큰이 실은 빌드 → 레지스트리 → 매니페스트 → 클러스터 배포 경로 전체의 열쇠**였다
5. FOREMAN 코드에서 GET만 보내도록 막는 것은 FOREMAN 자신의 버그를 막는 장치이지 보안 경계가 아니다 — 토큰이 새면 그 제한은 같이 새지 않는다
6. 서버는 여러 계정이 쓴다(kopo17 · kopo02). 파일 권한 600은 다른 일반 계정을 막지만, 이 계정에서 도는 CC 세션 · 로그 · 트랜스크립트로 새는 길은 남는다 — 이 프로젝트에서도 httpx 로그에 텔레그램 봇 토큰이 찍혀 재발급한 적이 있다(7단계). 그만한 비밀을 호스트에 두는 것 자체가 부담이다

### 알림 방식의 토큰

새도 할 수 있는 것은 **FOREMAN에 가짜 빌드 이벤트를 넣는 것**이다 — 대시보드에 거짓 상태, 거짓 실패 알림(텔레그램), DB 행. 배포 · 레지스트리 · 클러스터에는 닿지 않는다. 그나마도 받는 쪽이 VM 망 IP만 받으므로(`webhook_allow_cidrs`, 리스너는 virbr0 `192.168.122.1:8001`) 클러스터 · VM 망 안에 있어야 쓸 수 있다. 받는 쪽은 이미 있다 — `POST /webhooks/jenkins`, 토큰 비교 `hmac.compare_digest`, VM 망 IP 제한(지금 꺼 둠).

**같은 유출이라도 피해 범위가 다르다. 그래서 "새도 되는 비밀의 무게"를 기준으로 알림 방식을 골랐다.**

대신 처음에 API 조회를 고른 이유("기존 파이프라인을 건드리지 않는다")를 조건으로 바꿔 지킨다 — **알림은 빌드 결과에 영향을 주지 않는다**: curl 실패는 `|| true`, 짧은 timeout(연결 3초 · 전체 5초), post 중 맨 마지막(`cleanup`)에 둔다. 그리고 단계 자체가 예외를 던지는 경우(에이전트 연결 끊김 등)까지 `try/catch`로 삼킨다 — `|| true`는 셸 종료 코드만 막는다.

알림만으로는 "알림이 안 왔다 = 빌드가 없었다"를 믿을 수 없다(Jenkinsfile 문법 오류 · 에이전트 파드가 안 뜸 · 빌드 중 컨트롤러 재시작 · 웹훅 유실 · 알림 자체 실패). 그래서 **보정은 토큰 없이** 한다 — 로컬 저장소 push를 보고(브리지 `scan_git`, 20초), push 뒤 정해진 시간 안에 빌드 알림이 없으면 "빌드 알림 없음 — Jenkins 확인"으로 알린다. 내용을 되살리지는 못해도, 놓친 것을 놓친 채로 두지 않는다 — milvus-port-forward가 567,740번 재시작하는 것을 한 달 넘게 몰랐던 것 같은 조용한 고장을 잡는 것이 이 프로젝트를 만든 이유다. 실패 상세(스테이지별 로그)가 필요해지면 그때 matrix-auth로 진짜 읽기 전용 토큰을 만들어 보정용으로 더한다 — 지금은 만들지 않는다.

## Jenkins 알림 설계안 (11-03 — 적용 전, 사용자 검토용)

### 1. Jenkinsfile (런슈즈 · 펫퍼민트 같은 모양)

각 stage 첫 줄에서 지금 스테이지 이름을 전역 `env.STAGE`에 옮긴다. stage 안에는 Jenkins가 주는 `env.STAGE_NAME`이 있지만 pipeline 단계 `post`에서는 실패한 스테이지 이름이 남지 않고, 샌드박스에서 쓸 수 있는 스테이지 조회 API도 없어서다. 이름을 두 번 쓰지 않으려고 `STAGE_NAME`을 복사한다.

```groovy
    stage('태그') {
      steps {
        script {
          env.STAGE = env.STAGE_NAME
          env.TAG = env.GIT_COMMIT.take(12)
          currentBuild.description = …                 // 그대로
        }
        foremanNotify('started')                       // 시작 알림 — "push 뒤 빌드가 시작됐나" 판정에 쓴다
      }
    }
    stage('빌드·push') {
      steps {
        script { env.STAGE = env.STAGE_NAME }
        container('buildkit') { … }                    // 그대로
      }
    }
    stage('매니페스트 태그') {
      steps {
        script { env.STAGE = env.STAGE_NAME }
        withCredentials(…) { … }                       // 그대로
      }
    }
  }

  post {
    always { sh 'rm -rf …' }                           // 그대로
    cleanup { foremanNotify('completed') }             // post 블록 중 맨 마지막에 돈다
  }
}

// FOREMAN 빌드 알림(foreman log/stage8_cicd_result.md). 실패해도 빌드 결과에 영향 없다:
// 단계 예외는 try/catch, curl 실패는 || true, 연결 3초 · 전체 5초. 토큰은 셸 환경변수로만(Groovy 문자열에 넣지 않는다),
// curl 인자가 아니라 표준 입력 설정(-K -)으로 넘겨 프로세스 목록 · 로그에 안 남는다.
def foremanNotify(String phase) {
  try {
    def causes = currentBuild.getBuildCauses().collect { it._class as String }
    String cause = causes.any { it.endsWith('GitHubPushCause') } ? 'webhook'
                 : causes.any { it.contains('SCMTrigger') }      ? 'poll'
                 : causes.any { it.contains('UserIdCause') }     ? 'manual' : 'other'
    withEnv(["F_PHASE=${phase}", "F_CAUSE=${cause}", "F_STAGE=${env.STAGE ?: ''}",
             "F_RESULT=${phase == 'completed' ? currentBuild.currentResult : ''}",
             "F_DURATION=${currentBuild.duration}"]) {
      withCredentials([string(credentialsId: 'foreman-webhook-token', variable: 'F_TOKEN')]) {
        sh '''
          set +x
          body=$(printf '{"job":"%s","number":%s,"phase":"%s","result":"%s","commit":"%s","stage":"%s","cause":"%s","url":"%s","timestamp":%s000,"duration":%s}' \
            "$JOB_NAME" "$BUILD_NUMBER" "$F_PHASE" "$F_RESULT" "${GIT_COMMIT:-}" "$F_STAGE" "$F_CAUSE" "$BUILD_URL" "$(date +%s)" "$F_DURATION")
          printf 'header = "Authorization: Bearer %s"\n' "$F_TOKEN" |
            curl -sS -o /dev/null --connect-timeout 3 --max-time 5 -K - \
              -H 'Content-Type: application/json' --data "$body" \
              http://192.168.122.1:8001/webhooks/jenkins || true
        '''
      }
    }
  } catch (e) {
    echo "FOREMAN 알림 실패(빌드 결과와 무관): ${e}"
  }
}
```

- 보내는 값은 모두 Jenkins가 정한 것(job · 번호 · SHA · 결과 enum · 스테이지 이름 · URL) — 따옴표가 들어갈 자리가 없어 printf로 JSON을 만든다. 받는 쪽 형식은 지금 `jenkins_status`가 받는 `{job, number, phase, result, commit, stage, url}` + `cause` · `duration`
- `cause`가 들어가므로 **웹훅 끊김 감지도 토큰 없이 된다**(아래 3)
- 차이: 런슈즈는 스테이지가 같고 이미지 둘, 펫퍼민트는 이미지 하나 — 알림 부분은 글자까지 같다

### 2. JCasC 자격 증명 (`ronanlab-infra platform/jenkins/values.yaml`, 웹훅 시크릿과 같은 방식)

```yaml
  additionalExistingSecrets:
    …
    # FOREMAN 빌드 알림 토큰 — 사람이 넣은 Secret jenkins/foreman-webhook-token(키 token). 값은 foreman .env.bridge FOREMAN_WEBHOOK_TOKEN.
    # 새도 FOREMAN에 가짜 빌드 이벤트를 넣는 정도(foreman log/stage8_cicd_result.md "새도 되는 비밀의 무게")
    - name: foreman-webhook-token
      keyName: token

  JCasC:
    configScripts:
      foreman: |                    # 따로 둔다 — 지울 때 이 블록만. configScripts는 합쳐진다(credentials 목록이 이어 붙는다)
        credentials:
          system:
            domainCredentials:
              - credentials:
                  - string:
                      scope: GLOBAL
                      id: foreman-webhook-token
                      description: "FOREMAN 빌드 알림 토큰 — POST 192.168.122.1:8001/webhooks/jenkins"
                      secret: "${foreman-webhook-token-token}"
```

Secret은 사람이 넣는다(값을 화면에 내지 않고 `.env.bridge`에서 바로):
`sed -n 's/^FOREMAN_WEBHOOK_TOKEN=//p' .env.bridge | tr -d '\n' | (cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl -n jenkins create secret generic foreman-webhook-token --from-file=token=/dev/stdin')`

`additionalExistingSecrets`가 바뀌면 컨트롤러 파드의 볼륨이 바뀌므로 `helm upgrade` 때 **Jenkins 컨트롤러가 재시작된다** — 빌드가 없을 때.

### 3. 확인한 것 두 가지 (11-03, 읽기 전용)

| 확인 | 결과 | 근거 |
|---|---|---|
| post가 도는 컨테이너(jnlp)에 curl이 있나 | **있다** | 실제 에이전트 이미지는 `jenkins/inbound-agent:3391.va_37fa_a_305d6d-1-jdk25`(런슈즈 #51 빌드 로그 — 클라우드 설정의 3385가 아니라 플러그인 기본값). 공식 `jenkinsci/docker-agent` `debian/Dockerfile`의 agent 단계가 `curl`을 설치하고 inbound-agent가 그 위에 선다. 같은 계열(Debian 13) 컨트롤러에도 `/usr/bin/curl`. 적용 첫 빌드 로그로 최종 확인 — 없더라도 `try` · `\|\| true`라 빌드는 그대로, 알림이 안 와서 보정 규칙이 잡는다 |
| 파드 → 호스트가 FOREMAN의 VM 망 IP 제한을 통과하나 | **통과한다(경로 확인, 출발 IP는 설정으로 판단)** — 적용 때 실측: `192.168.122.13`(노드의 122망 주소, 아래 "적용 결과") | 파드(`jenkins-0`, 10.244.x)에서 `192.168.122.1:11434`(ollama) 200 — 경로 있음. Calico IP 풀 `10.244.0.0/16` `natOutgoing: true` → 풀 밖으로 나가는 패킷은 노드 IP로 SNAT된다. 노드 IP는 `192.168.121.{64,179,95,158}` → 허용 목록 `192.168.121.0/24` 안. 출발 IP를 직접 보지는 못했다(ollama는 docker 프록시를 거쳐 172.17.0.1로 보인다) — 적용 때 브리지 로그(거절하면 출발 IP를 남긴다)로 확인. 11-02에 노드에서 8001로 보내 401 · 404를 받은 것도 같은 출발 IP다 |

### 4. "빠진 알림 찾기" 규칙

기준은 로컬 저장소 push(브리지 `scan_git` — 20초마다 `origin/main`이 움직였는지. 11-02에 꺼 둔 것을 다시 켠다). 빌드 하나가 커밋 여럿을 묶으므로(`disableConcurrentBuilds`), push 머리 H는 **H와 같거나 H를 조상으로 가진 커밋의 빌드 알림**이 오면 채워진 것으로 본다.

| 상황 | 기다리는 시간 | 하는 것 |
|---|---|---|
| push 뒤 시작 알림 없음 | **3분** | 대시보드에 "빌드 시작 알림 없음 — 폴링 안전망 대기" 노란색(텔레그램 안 보냄). 웹훅이면 몇 초 안에 시작한다(펫퍼민트 #48: push → 시작 3초) |
| 〃 | **17분**(폴링 15분 + 2분) | 텔레그램 `[런슈즈] 빌드 알림 없음 — push abc1234 "제목" 뒤 17분째 Jenkins 시작 알림이 없다. Jenkins 확인: <job URL>`, 대시보드 빨간색 |
| 시작은 왔는데 끝 알림 없음 | **35분**(Jenkins `timeout` 30분 + 5분) | 텔레그램 "빌드 끝 알림 없음 — #N" |
| 같은 job 앞 빌드가 아직 도는 중 | 그 빌드가 끝날 때부터 잰다 | `disableConcurrentBuilds`라 줄 서 있는 것 |
| 늦게 도착 | — | "늦게 도착함(N분)"을 한 번 보내고 상태를 정상으로 |
| 웹훅 끊김 | 웹훅 원인 빌드가 있던 job에서 **`cause: poll` 빌드가 연달아 2번** | 텔레그램 "웹훅 끊김 의심 — 최근 두 빌드가 폴링으로 시작". 원인이 `webhook`으로 돌아오면 해제 |

- 알림은 (job, push 머리)마다 한 번. 실제 빌드 시간: 런슈즈 약 4~5분, 펫퍼민트 약 1분(최근 6개)
- main 밖 브랜치 push는 보지 않는다
- 첫 런슈즈 빌드가 런슈즈 웹훅 검증을 겸한다(원인 `webhook`이면 확인 끝)

### 5. 적용 순서와 부작용

1. Secret(사람) → `values.yaml` + `helm upgrade`(컨트롤러 재시작, 빌드 없을 때)
2. FOREMAN 브리지 파이프라인 켜기(리스너 8001, `scan_git`) — 알림 받는 쪽부터
3. 두 앱 저장소 Jenkinsfile 커밋 · push — **이 push가 빌드를 한 번 부른다.** 코드가 같아도 커밋이 새로 생겨 태그가 바뀌므로 런슈즈는 자동 Sync로 다시 배포된다(롤링, 같은 코드). 펫퍼민트는 OutOfSync로 "Sync 대기". 피하려면 다음 실제 변경과 같이 넣는다. 이 빌드가 런슈즈 웹훅 검증 · curl · 출발 IP 확인을 겸한다

순서가 바뀌어도 위험은 없다 — 자격 증명이 없으면 `withCredentials`가 예외를 던지고 `try`가 삼킨다. 세 저장소(runshoes · petmint-rag-chatbot · ronanlab-infra) 수정은 사용자 지시로, 각 저장소 CLAUDE.md를 따른다.

### 6. 되돌리기

| 범위 | 방법 | 빌드 영향 |
|---|---|---|
| 즉시 · Jenkins를 안 건드림 | FOREMAN `pipeline_enabled = False` → 8001이 닫혀 curl이 바로 연결 거부, `\|\| true` | 없음 |
| 알림 단계 제거 | 두 앱 저장소에서 Jenkinsfile 커밋 `git revert` + push | 이 push도 빌드 한 번(런슈즈 재배포) |
| 자격 증명 제거 | `values.yaml`에서 `foreman` configScript · `additionalExistingSecrets` 항목 지우고 `helm upgrade`(컨트롤러 재시작), `kubectl -n jenkins delete secret foreman-webhook-token` | 없음(Jenkinsfile에 남아 있어도 `try`가 삼킨다) |
| 토큰이 샜을 때 | `.env.bridge`의 `FOREMAN_WEBHOOK_TOKEN` 바꾸고 브리지 재시작 + Secret 갱신 → JCasC 다시 읽기 | 없음 |

### 재개할 때 다시 조사할 것 (11-03 아침 기록 — 위에서 다 봤다)

11-03에 펫퍼민트 세션에서 App of Apps 작업이 끝났고 웹훅을 거는 중이라고 사용자가 알려 왔다. 그 작업이 끝날 때까지 FOREMAN은 아무것도 하지 않았고, 끝난 뒤 위처럼 읽었다.

| 볼 것 | 11-02 값(비교 기준) | 확인할 곳 |
|---|---|---|
| **App of Apps에서 Application이 어떻게 나뉘는지**: 루트 앱 이름 · 자식 앱 목록 · 앱 이름이 `runshoes` · `petmint` 그대로인지 · 앱 하나에 무엇이 묶였는지(앱/플랫폼 분리 등) · `project`(AppProject) | 손으로 `kubectl apply`한 Application 4개(`cloudflared` · `monitoring` · `petmint` · `runshoes`), ArgoCD가 자기 Application을 관리하지 않음 | `kubectl -n argocd get applications`(+ `-o yaml`의 `ownerReferences` · `app.kubernetes.io/instance` 라벨), `appprojects`, `ronanlab-infra` 새 디렉토리 구조(`platform/argocd/…`), 루트 앱의 `source.path` |
| **웹훅이 걸리면 폴링이 없어지는지** — Jenkins 2분 | `SCMTrigger H/2`, GitHub 웹훅은 Cloudflare Access(302)에 막혀 닿을 수 없음 | job live `config.xml`의 트리거(`GitHubPushTrigger`? `SCMTrigger`가 남았나 · spec), 최근 `build.xml`의 원인(`GitHubPushCause` vs `SCMTriggerCause`), `scm-polling.log`가 계속 2분마다 도는지, 터널 · Access에 웹훅 경로 예외(bypass)가 생겼는지(`cloudflared-config`, 밖에서 `/github-webhook/` 응답 코드), 플러그인 목록 |
| **웹훅이 걸리면 폴링이 없어지는지** — ArgoCD 3분 | 기본 3분, `argocd-secret`에 `webhook.github.secret` 없음 | `argocd-secret` **키 이름만**(`webhook.github.secret` 생겼나), `argocd-cm`의 `timeout.reconciliation`, 밖에서 `argocd.ronanlab.dev/api/webhook` 응답 코드, 인프라 저장소 push → Application `status.reconciledAt`까지 걸린 시간. 웹훅을 걸어도 ArgoCD 폴링은 보통 꺼지지 않고(기본값 그대로 같이 돈다) 감지만 빨라진다 — 실제 값을 확인 |
| **FOREMAN이 ArgoCD 알림 웹훅(①안)을 붙일 자리** | `argocd-notifications-cm` · `-secret` 비어 있음. 초안 `deploy/cicd/argocd-notifications-foreman.yaml`(기본 구독 = 모든 앱) | ① 펫퍼민트 쪽이 notifications를 이미 쓰기 시작했나(cm · secret이 비었나, 누가 관리하나 — 인프라 저장소에 있으면 거기 더해야 한다. 손으로 `apply`하면 ArgoCD self-heal과 충돌할 수 있다) ② 구독을 어디에 둘지: cm의 기본 구독(`subscriptions`) · 자식 Application 주석(`notifications.argoproj.io/subscribe.<trigger>.foreman`) · AppProject 주석 중 무엇이 새 구조에 맞나 ③ 루트 앱이 자식 앱 정의를 관리하면 주석도 인프라 저장소에 넣어야 한다(손으로 붙이면 되돌려진다) ④ 받는 주소 `192.168.122.1:8001`(virbr0) — 노드에서 닿는지 다시 확인 |
| **펫퍼민트 수동 Sync가 유지되는지** | 런슈즈 `automated: {}`(prune · selfHeal 끔), 펫퍼민트 `automated` 없음 | 새 Application `spec.syncPolicy` 둘 다. 루트 앱 자신의 syncPolicy도. 수동이면 FOREMAN은 "OutOfSync로 기다림"을 실패가 아닌 별도 상태로 보여 준다 |

같이 볼 것: 앱 ↔ Jenkins job ↔ Harbor 프로젝트 대응(`config/pipeline.toml`)이 바뀌었나, `kustomization.yaml` newTag 자리(경로)가 그대로인가 — Jenkinsfile 마지막 스테이지가 거기를 고친다. 바뀐 것이 있으면 위 "정한 방향"(Jenkins 읽기 조회 · ArgoCD ①)을 다시 판단하고 사용자에게 먼저 보인다.

## 11-03 적용 결과 — Jenkins 알림 (사용자 순서: 자격 증명 → FOREMAN → Jenkinsfile)

되돌리기 · 진행 기록: 호스트 `~/k8s-cluster/backup/2026-11-03-foreman-notify/ROLLBACK.md`(바꾸기 전 `values-rev7.yaml`).

| 단계 | 한 것 | 확인 |
|---|---|---|
| 1. 자격 증명 | Secret `jenkins/foreman-webhook-token`(값은 `.env.bridge`에서 바로, 43바이트 — 화면에 안 냄) → `values.yaml`(`additionalExistingSecrets` + `configScripts.foreman`) → `helm upgrade`(revision 7 → 8, 22:49:53~22:50:35 UTC, 재시작 42초). 빌드 없을 때(에이전트 파드 0). 배포된 rev7 값 = 저장소 값 확인 뒤. infra `8277b64` | 자격 증명 id 5개(새로 `foreman-webhook-token`), job 2개 · `githubPush` 그대로, 플러그인 73개 그대로, `/login` 200 |
| 2. FOREMAN | `pipeline_enabled = True` — 8001 리스너, 로컬 git 폴링, 인프라 생존 폴링, **빠진 알림 찾기**(새 — `track_origin` · `check_watch`, `[watch]` 설정), **웹훅 끊김 감지**(새 — 빌드 원인 `cause`) | `jenkins-0`(w3)에서 토큰 없이 POST → **401**(출발 IP 허용, 토큰만 없음), 다른 경로 404. **출발 IP는 `192.168.122.13`** — 설계 때 생각한 `192.168.121.x`가 아니라 노드의 122망 주소로 SNAT된다(둘 다 허용 대역) |
| 3. Jenkinsfile | 펫퍼민트 먼저(빌드 1분 · 수동 Sync라 배포 없음) `d336871`, 확인 뒤 런슈즈 `385c750`. 알림 부분은 두 파일이 글자까지 같다. push 전에 셸 부분을 임시 수신기로 시험(헤더 인증 · JSON · 한글 스테이지 이름 · 받는 쪽이 꺼져도 종료 코드 0) | 아래 |

검증 빌드 두 개(사용자: "3번 push 빌드를 검증에 쓰자"):

| | 펫퍼민트 #49 | 런슈즈 #52 |
|---|---|---|
| push → FOREMAN push 감지 | 9초 | 4초 |
| push → 시작 알림 | 25초 | 23초 |
| 빌드 원인 | `webhook` | **`GitHubPushCause` — 런슈즈 웹훅 첫 검증** |
| 결과 · 끝 알림 | SUCCESS 58초, `stage` 매니페스트 태그 | SUCCESS 295초 |
| jnlp curl | 있음(빌드 로그에 `curl: not found` · 알림 실패 0) | 같음 |
| 출발 IP | 192.168.122.13 | 192.168.122.13 |
| 토큰이 빌드 로그에 | 0번 | 0번 |
| 샌드박스 거부(`Scripts not permitted`) | 0 | 0 |
| 그 뒤 | infra `b88ef7c` → ArgoCD OutOfSync(수동 Sync 대기) | infra `ce51759` → 자동 Sync, `runshoes:385c75027699` Healthy(재배포 — 사용자 감수) |

인프라 캐릭터 Jenkins가 두 프로젝트에 첫 알림으로 등장했다. 빠진 알림 찾기는 두 push 모두 시작 알림이 와서 대기 → 해제(경고 없음).

## 지금 상태

- **브리지**: 파이프라인 **켜짐**(11-03) — 8001(virbr0, `/webhooks/*`만, VM 망 IP만, 토큰), 로컬 git 폴링 20초, 인프라 생존 폴링, 빠진 알림 찾기 30초
- ~~11-02 보류 때~~: 파이프라인을 껐었다(`pipeline_enabled = False`)
- **코드**: `bridge/pipeline.py`(+ `build_cause` · `watch_state` · `webhook_broken`, `track_origin` · `check_watch` · `_check_hook`), `bridge/api/webhooks.py`, `config/pipeline.toml`(`[watch]`), 대시보드 `render.js`(빌드 기다림 · 알림 없음 · 웹훅 끊김 줄). 시험 193개
- **ArgoCD**: 아직 — notifications 매니페스트 초안(`deploy/cicd/argocd-notifications-foreman.yaml`)을 기본 구독 + `instance=root`로 고쳐 적용할 차례. 펫퍼민트 "Sync 대기"는 이것과 같이(지금 대시보드는 Jenkins 단계까지만)
- **DB**: `build`에 검증 빌드 2행(`petmint-app#49` · `runshoes-app#52`), 인프라 캐릭터 Jenkins 2(프로젝트마다)
- **`FOREMAN_WEBHOOK_TOKEN`**: `.env.bridge`(브리지가 받을 때) + Secret `jenkins/foreman-webhook-token`(Jenkins가 보낼 때). 바꿀 때 둘 다
- **빠진 알림 찾기의 한계**: 상태가 메모리에 있다 — 브리지를 다시 띄우면 그때의 origin 머리부터 다시 잰다(재시작 직전 push는 놓친다). 이 서버에서 push · fetch해 `origin/main`이 움직여야 보인다(다른 PC에서 GitHub에 직접 push하면 못 본다 — 지금은 모두 이 서버의 세션이 push한다)

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
- ~~고치지 않은 오탐~~ **11-03 고침**: `git -C $d status`가 "git 동사 자리가 변수"(애매한-운영명령)로 걸렸다 — `-C`가 값을 받는 옵션인 것을 `verb_re`가 몰랐다. 이제 git의 `-C` · `-c` · `--git-dir` · `--work-tree` · `--namespace`는 다음 토큰을 값으로 넘기고 그 뒤를 동사 자리로 본다. 동사가 변수면 그대로 묻고(`git -C "$d" $VERB`), 값만 있고 끝나는 `git -C $x`도 묻는다(따옴표 없는 `$x`가 "경로 push --force"로 쪼개질 수 있다). 21일 재생: 빠진 ask 7건(포먼 6 · 런슈즈 1, 모두 `git -C $d <고정 동사>`), 새로 생긴 ask 0. 시험 104개 통과. 사용자가 보호 파일 쓰기를 승인
- 6단계 표(런슈즈 7.2)는 20일로 나눴고 지금은 활동한 날로 나눈다(같은 총량 약 145건)
