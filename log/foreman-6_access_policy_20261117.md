# 접근 정책 표, FOREMAN 화면과 터널, 인프라 MySQL 「노드가 3대라 감수」 조사 (2026-11-17, foreman-6)

관리자 410의 조사 일감(사용자 물음 11-17). 읽기만 했고 고친 것은 없다.

읽은 판:

- 인프라 저장소: `origin/main` `1172481`(fetch 하지 않은 판)
- 펫퍼민트 저장소: `HEAD` `aea5a6f`
- 런슈즈 저장소: `HEAD` `606b730`
- FOREMAN: 이 브랜치(`cc/foreman-6`, `8356bcd` 위)

주소는 쓰지 않고 이름으로 적는다(「런슈즈 앱 주소」처럼). Cloudflare Access 정책과 DNS 기록은 Cloudflare 대시보드에 있고 저장소에는 없다(인프라 `docs/history/build_log/03_cloudflare_tunnel.md:699`). 그래서 아래 「Access 걸림 여부」는 모두 **저장소 기록에 적힌 것**이고, 대시보드를 직접 본 것이 아니다.

## 1. 접근 정책 표

바깥에서 열리는 길은 둘이다. 클러스터 공용 터널 `ronanlab-tunnel`(호스트 일곱, 인프라 `apps/cloudflared/configmap.yaml:13-44`)과 호스트에 따로 도는 `ollama-tunnel`(호스트 systemd `cloudflared-ollama`, 설정은 저장소 밖). 운영 도구 다섯은 터널 설정의 호스트 일곱 가운데 프로젝트 앱 둘을 뺀 것이다: ArgoCD, Harbor, Jenkins, Grafana, Prometheus.

### 네 프로젝트

| 무엇 | Access 걸림 여부 | 까닭이 적힌 곳 |
| --- | --- | --- |
| FOREMAN 관제 화면 | 바깥에 안 열림. 화면은 루프백에서만 듣는다 | FOREMAN `README.md:621-629` 「3.13 외부 노출, 터널을 열지 않는다(2026-11-03 결정)」(`0e348e13`). 까닭: 화면이 호스트 셸과 승인 권한을 가진 관제실이라 열면 노출 면만 커지고(`README.md:609`), 밖에서 필요한 것은 텔레그램으로 받는다(`README.md:627`). 듣는 주소 기본값 `bridge/config.py:57`(`cc6af55a`) |
| FOREMAN 웹훅 포트(참고) | 바깥에 안 열림. VM 사설망 주소에서 듣고 `/webhooks/*`만 받는다 | `bridge/config.py:122-127`, `bridge/main.py:542-545`. ArgoCD와 Jenkins가 빌드, 배포 알림을 보내는 곳(인프라 `docs/06_gitops.md:46`, `docs/08_build.md:30`) |
| 런슈즈 앱 | 걸리지 않음(공개) | 인프라 `apps/cloudflared/configmap.yaml:30` 「Access 없음(공개 사이트)」(`063c513a`, 2026-10-18), 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:54`(`6f49878a`), 런슈즈 `docs/06_deployment.md:38`(`6bef5730`). 적힌 까닭은 「공개 사이트」 한 마디뿐이고 그보다 자세한 까닭 기록 없음 |
| 펫퍼민트 앱 | 걸리지 않음. 앱 자체 로그인(`PETMINT_AUTH=app`)이 받는다 | 펫퍼민트 `docs/02_pipeline/13_access_and_tunnel.md:1`(`173f441a`), `:47`(`d84958cf`) 「데모 공개를 위해 의도적으로 제거(사용자, 2026-11-09 확인)」, 전환 까닭 `:91-94`(데모를 보는 사람은 사내 계정이 없다). 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:50`(`6f49878a`)이 같은 내용을 옮겼다 |
| 인프라 | 인프라 자체의 화면은 없다(저장소는 클러스터 GitOps 설정). 바깥에 여는 것은 아래 운영 도구 다섯 | 인프라 `README.md:3` |

### 운영 도구 다섯

| 무엇 | Access 걸림 여부 | 까닭이 적힌 곳 |
| --- | --- | --- |
| ArgoCD | 걸림. Access 앱 「운영도구」(운영자만) | 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:51`(`6f49878a`) 「운영자만」, 까닭 `:175`(`6f49878a`) 「터널만 뚫으면 도메인 주소를 아는 누구나 부를 수 있다. 그래서 Access를 앞에 둔다」. 펫퍼민트 `13_access_and_tunnel.md:49`(`82aab5ea`) 「운영자만. Application 하나로 묶어 세션을 공유」 |
| ArgoCD GitHub 웹훅 경로 하나 | 그 경로만 Access 밖(Bypass), 서버의 HMAC 서명 검사가 지킨다 | 인프라 `docs/history/build_log/04_argocd.md:45`, 펫퍼민트 `13_access_and_tunnel.md:50`(`acd73900`, 2026-11-03). 까닭: GitHub 웹훅이 들어와야 한다 |
| Harbor | 걸림. 「운영도구」 | 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:52`, 까닭은 ArgoCD와 같은 `:175` |
| Jenkins | 걸림. 「운영도구」 | 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:53`, 까닭 `:175` |
| Jenkins GitHub 웹훅 경로 하나 | 그 경로만 Access 밖(Bypass), HMAC SHA-256 서명이 지킨다 | 인프라 `platform/jenkins/values.yaml:92-93`(`a1d0238f`, 2026-11-03), `docs/08_build.md:28` |
| Grafana | 걸림. 「운영도구」(Grafana 자체 로그인과 두 겹) | 인프라 `apps/monitoring/ingress.yaml:3-7`(`f71de87d`, 2026-11-11), `apps/cloudflared/configmap.yaml:35`(`f71de87d`) |
| Prometheus | 걸림. 「운영도구」. 자체 로그인이 없어 바깥에서는 Access가 유일한 문 | 인프라 `apps/monitoring/ingress.yaml:5`(`f71de87d`) 「Access 를 건 뒤에 DNS(CNAME)를 연다」, `apps/monitoring/README.md:51` |

### 참고: 다섯 밖의 바깥 길

| 무엇 | Access 걸림 여부 | 까닭이 적힌 곳 |
| --- | --- | --- |
| Ollama API(학교 PC용, 호스트 터널) | 걸림. Service Auth와 서비스 토큰(사람 로그인이 아니라 프로그램 인증) | 인프라 `docs/history/build_log/03_cloudflare_tunnel.md:688-690`(2026-11-09 정책이 빠져 열려 있던 것을 다시 걸었다), `:701` 「GPU가 한 장이다. 이 호스트는 늘 Access 뒤에 둔다」. 펫퍼민트 `13_access_and_tunnel.md:52-58` |

### 표를 모으며 본 어긋남(고치지 않음)

- 인프라 `apps/cloudflared/README.md:4`는 일곱 호스트 모두 「앞단은 Cloudflare Access」라고 적는데 런슈즈, 펫퍼민트는 Access가 없다. 인프라 `docs/05_public.md:145`가 이미 한계로 적어 두었다(그 줄은 「petmint의 Access 여부는 저장소에 적혀 있지 않다」고도 하지만 인프라 `03_cloudflare_tunnel.md:50`에는 적혀 있다)
- 펫퍼민트 `13_access_and_tunnel.md:49`의 운영 도구 줄은 argocd, harbor, jenkins 셋만 적고, 11-11에 더한 grafana, prometheus가 없다
- FOREMAN `README.md:436` 「운영 도구는 Cloudflare Access 뒤라 GitHub 웹훅이 닿지 않는다」는 11-02 조사 시점 서술이다. 11-03부터 두 웹훅 경로가 Bypass라 지금과 다르다(런슈즈 `docs/06_deployment.md:150`은 웹훅이 주력이라고 적는다)
- 「왜 이 도구는 막고 저 앱은 안 막았나」를 한 곳에 적은 문서는 없다. 가장 가까운 것은 인프라 `docs/05_public.md:24-28` 「경로와 Access」 표(까닭 칸 없음)와 펫퍼민트 `13_access_and_tunnel.md:41-50`(「Access 정책은 호스트별로 건다. 프로젝트마다 접근 정책이 다를 수 있기 때문」, `:43`)

## 2. FOREMAN 화면이 터널 설정에 있는가: 없다

| 본 곳 | 결과 |
| --- | --- |
| 인프라 클러스터 터널 설정 `apps/cloudflared/configmap.yaml` | 호스트 일곱의 첫 이름은 petmint, argocd, harbor, jenkins, runshoes, grafana, prometheus. FOREMAN 없음. 마지막 규칙은 404 |
| 인프라 Ingress 전체(`apps/*/ingress.yaml`, `platform/argocd/ingress.yaml`, Harbor, Jenkins Helm 값의 hosts) | FOREMAN 호스트 없음 |
| 인프라 저장소 전체 `git grep -i foreman`(origin/main) | 터널, Ingress, DNS에 걸린 줄 없음. 걸린 것은 문서 도구 설정(`.foreman/*.toml`), CLAUDE.md의 세션 규칙, ArgoCD와 Jenkins가 FOREMAN 웹훅 포트(사설망)로 알림을 보내는 설정뿐 |
| 호스트 터널 `ollama-tunnel` 설정 파일 | 호스트 하나(ollama), foreman 0건 |
| 호스트의 cloudflared 유닛 | `cloudflared-ollama` 하나(active). FOREMAN용 유닛 없음 |
| FOREMAN 듣는 주소 | 화면 포트는 루프백만(기본값 `bridge/config.py:57`, `.env.bridge`에 듣는 주소를 덮는 키 0개, 지금 실제로 루프백에서 듣는다). 웹훅 포트는 VM 사설망 주소 |
| DNS 기록 | Cloudflare 대시보드에 있어 저장소에 없다. 코드로는 확인할 수 없다(조회하지 않음) |

결론: 터널, Ingress, 호스트 터널, 듣는 주소 어디에도 FOREMAN 화면을 바깥으로 내는 설정은 없다. 화면 포트가 루프백에서만 들으므로 DNS 기록이 있더라도 닿을 원점이 없다. FOREMAN `docs/14_dispatcher_note_wake.md:76` 「화면은 Cloudflare 로그인 뒤라」(`89076652`)는 설계(`README.md:621-629`)와 지금 상태 모두와 맞지 않는다.

같은 문장이 남은 곳:

- `log/stage14_dispatcher_note_wake_result.md:23`(기록이라 고치는 대상인지는 관리자 판단)
- `docs/02_cloudflare_tunnel.md:113`은 보류된 브리프(`README.md:899` 「⏸ 보류」)의 검증 항목이라 그대로 맞다

## 3. 인프라 MySQL 「노드가 3대라 감수」

### 무엇을 감수했나

인프라 `apps/runshoes/mysql/statefulset.yaml:6-7`(`07bc3b2c`, 2026-10-18): 런슈즈 MySQL은 local-path라 처음 뜬 노드에 PV가 묶이고, w1을 고른다(그때 limits 여유가 가장 큰 노드). 펫퍼민트 MySQL의 PV도 w1에 있어 **w1이 멈추면 두 앱의 DB가 같이 멈춘다.** 그것을 「노드가 3대라」 감수했다. 그때는 Replica가 없어서 w1이 돌아올 때까지 두 DB가 모두 멈추는 것이었다.

### 그 뒤 바뀐 것(2026-11-10~11-12 가용성 작업, 인프라 `docs/history/build_log/08_scale_out.md`)

- 워커가 넷이 되었다(w4 추가, 메모리 8GB씩). 인프라 `README.md:3`, `docs/02_nodes.md:14-25`
- 노드에 역할을 고정했다(`cluster/label-nodes.sh:6-8`, `d63639f2`): app은 w1, w2 / infra(Harbor, Jenkins, ArgoCD)는 w3 / platform(모니터링)은 w4. 그래서 **DB가 뜰 수 있는 app 노드는 지금도 둘**이다. 노드가 넷이 된 것이 DB 쪽 노드 수를 늘리지는 않았다
- 배치는 사용자 2026-11-10 목표로 「w1 MySQL Primary ×2, w2 Replica ×2」라고 정해졌다(`08_scale_out.md:14-19`)
- 두 DB 모두 Replica를 w2에 두었다(`apps/runshoes/mysql/replica.yaml:1-6`, `apps/petmint/mysql/replica.yaml:1-8`, `bda8638`). 자동 전환은 없고 사람이 승격한다(`08_scale_out.md:132-137`, 까닭: Operator는 부품이 늘고 메모리를 더 먹는다)

### 그 판단이 지금도 맞는가

- **위험 자체는 그대로다.** w1이 멈추면 두 앱의 DB 쓰기가 같이 실패한다. 달라진 것은 「w1이 돌아올 때까지」가 「사람이 Replica를 승격할 때까지」로 줄었다는 점이다(`08_scale_out.md:28`, 인프라 `docs/10_database.md:148-149`가 한계로 적어 둠)
- **「노드가 3대라」는 까닭은 더는 맞지 않는다.** 지금 두 Primary가 w1에 함께 있는 것은 노드 수 때문이 아니라 위 역할별 배치(사용자 11-10 목표)의 결과다. 인프라 `docs/10_database.md:156`도 이 주석이 낡았다고 이미 적었다
- **두 Primary를 w1, w2로 나누지 않은 까닭은 기록에 없다.** `08_scale_out.md`는 배치를 목표로 적었을 뿐 나누는 길과 견주지 않았다. 나누기에 걸릴 조건은 따로 적혀 있다(local-path PVC는 다른 노드로 옮길 수 없다 `08_scale_out.md:145`, Primary를 다시 시작하지 않는다는 조건 `:139`). 이것이 나누지 않은 까닭인지는 적혀 있지 않아 짐작하지 않는다
- **승격은 「사람이 알아채야」 시작된다.** 런북 `docs/runbooks/mysql-replica.md:105`는 「장애를 알아채고(알림)」라고 적지만, Prometheus 설정(`apps/monitoring/prometheus/configmap.yaml`)에 알림 규칙과 Alertmanager가 없고 인프라 `docs/TODO.md:10`에 「알림(Alertmanager)」이 할 일로 남아 있다. FOREMAN 설정에도 이 Pod나 노드를 보는 항목은 찾지 못했다. w1이 멈추면 무엇이 사람에게 알리는지는 기록에서 확인하지 못했다

### 한계인가 할 일인가

FOREMAN `docs/manuscript_rules.md:32` 기준(한계 줄에는 안 하는 까닭이나 조건을 적고, 쓸 수 없으면 `docs/TODO.md`로)에 대 보면 둘로 갈린다.

- 「자동 전환이 없어 w1이 멈추면 승격 전까지 쓰기 실패」는 수동 승격 결정의 치른 값이라 까닭이 있다(`08_scale_out.md:132-137`). 한계로 남을 수 있다
- 「두 Primary가 한 노드(w1)에 있다」는 적힌 까닭(노드가 3대)이 사라졌고 대신할 까닭이 기록에 없다. 이 기준으로는 **까닭을 새로 적을 수 있으면 한계, 없으면 TODO 쪽**이다. 까닭이 있는지(예를 들어 역할별 배치에서 일부러 고른 것인지)는 사용자와 인프라 세션이 정할 일이다

## 결과 요약

- 물음 1: 네 프로젝트 중 바깥에 열린 것은 런슈즈, 펫퍼민트 앱이고 둘 다 Access가 없다(런슈즈는 「공개 사이트」 한 마디, 펫퍼민트는 데모 공개로 사용자가 제거하고 앱 로그인). FOREMAN은 바깥에 안 열림(11-03 결정). 운영 도구 다섯은 모두 Access 「운영도구」 뒤이고, ArgoCD와 Jenkins의 웹훅 경로 하나씩만 Bypass다. Access 여부는 모두 저장소 기록이고 대시보드는 보지 않았다
- 물음 2: 터널, Ingress, 호스트 터널, 듣는 주소 어디에도 FOREMAN 화면은 없다. DNS 기록은 저장소 밖이라 확인하지 못했지만 화면이 루프백에서만 들어 닿을 원점이 없다. `docs/14_dispatcher_note_wake.md:76`은 틀린 서술이다
- 물음 3: 감수한 위험(w1이 멈추면 두 DB가 같이 멈춤)은 그대로이고, 까닭 「노드가 3대」만 낡았다. 노드가 넷이어도 DB용 app 노드는 둘이다. 두 Primary를 나누지 않은 까닭은 기록에 없어 기준상 TODO 후보다. w1이 멈췄을 때 알리는 길도 기록에서 찾지 못했다

규칙 위반 없음.
