# 11-06 정전 뒤 클러스터 — jenkins-0 Unknown · harbor-jobservice CrashLoopBackOff 조사

조사만 했다. 클러스터에는 아무것도 바꾸지 않았다. 배경은 [`infra_20261106_systemd-bridge.md`](infra_20261106_systemd-bridge.md)(09:32 정전, 12:24 부팅).

## 지금 상태 (12:3x KST)

- VM 4대 running, 노드 4대 Ready
- 정상이 아닌 파드는 `jenkins/jenkins-0` 하나

## harbor-jobservice — 기동 순서 경합, 저절로 풀림

- 이전 컨테이너 로그: `GET http://harbor-core:80/api/v2.0/internalconfig` → `connection refused` → `panic: failed to load configuration` (exit 2)
- 부팅 직후 harbor-core가 아직 안 떠 있었다. jobservice는 기동 때 core에서 설정을 받아야 해서 재시작 3번(BackOff) 뒤 **03:33:33 UTC(12:33 KST)부터 Running**, 이후 정상 로그(워커 · 스케줄 동기화)
- 조치 필요 없음. 정전 · 재부팅마다 몇 분 같은 모습이 나올 수 있다

## jenkins-0 — init 컨테이너가 계속 실패 (진짜 문제)

- `Unknown`은 정전 전 부팅의 `jenkins` 컨테이너 상태(11-03 00:50 시작 ~ 11-06 03:31 끝, exit 255)가 남은 것뿐이다
- 실제로 막힌 곳은 init 컨테이너 `init`: exit 1, 재시작 5번 이상, BackOff
- init 스크립트(ConfigMap `jenkins`의 `apply_config.sh`)는 `set -e`이고 마지막에 `yes n | cp -i /usr/share/jenkins/ref/plugins/* /var/jenkins_plugins/` 를 한다
- 로그 끝이 플러그인마다 `cp: overwrite '/var/jenkins_plugins/….jpi'?` 이다 — 대상에 파일이 이미 있다
- `/var/jenkins_plugins`(볼륨 `plugin-dir`)는 **emptyDir**. emptyDir은 같은 파드(UID)인 동안 노드 재부팅 · 샌드박스 재생성에도 남는다. 파드 `53a7a27f…`는 11-03 00:50 생성(Helm revision 8 적용 때)이고 정전 뒤에도 같은 파드가 다시 떴다 → 11-03에 복사한 플러그인이 그대로 있다
- GNU coreutils 9.x의 `cp -i`는 덮어쓰기를 거절하면 **종료 코드 1**. 호스트(coreutils 9.7)에서 재현: 빈 대상 exit 0, 파일이 있는 대상 exit 1. `set -e`라 스크립트가 실패한다
- 그전에 문제가 없던 이유: helm 업그레이드 · 재배포는 매번 새 파드(빈 emptyDir)를 만들었다. **파드를 다시 만들지 않고 컨테이너만 다시 뜬 것은 이번 정전이 처음**

### 미검증

- jenkins 이미지(`2.580.1-jdk25`) 안의 coreutils 버전은 직접 보지 못했다(컨테이너가 안 떠서 exec 불가). 재현은 호스트 cp로 했다. 로그 모양(질문 뒤 바로 실패)은 일치한다
- 차트 새 버전이 이 줄을 고쳤는지 확인하지 않았다

## 고치는 방법 (사용자 승인 대기)

1. **지금 되살리기**: `kubectl delete pod -n jenkins jenkins-0` — StatefulSet이 새 UID로 다시 만들어 emptyDir이 비고 init이 통과한다. `jenkins_home`은 PVC(`jenkins`, local-path)라 유지된다. 어차피 지금 Jenkins는 내려가 있다
2. **다음 정전에 재발 막기**(ronanlab-infra 소관): values에서 init 스크립트를 덮어 `cp -i` 줄이 실패해도 넘어가게(`|| true`) 하거나 `plugin-dir`를 매번 비우게, 또는 이 줄을 고친 차트 버전으로 올리기

## 조용한 고장인가

- Jenkins가 내려가 있는 동안 push해도 빌드 · 알림이 없다. FOREMAN은 빌드 알림을 웹훅으로만 받으므로 "알림이 안 온다"로만 드러난다 — CLAUDE.md의 "push 뒤 빌드 알림이 없으면 Jenkins 확인" 경우다
- 정전 뒤 파드 상태 점검(Ready가 아닌 파드)을 감시 항목에 넣을지는 따로 정할 일
