# 로드맵 8단계 — CI/CD 인과 체인 결과 (+ 승인 규칙 "실행과 글자" 넓히기)

- **실행일**: 2026-11-02 (8 · 9단계 순서를 바꾼 뒤 — README 로드맵)
- **상태**: FOREMAN 쪽(수신 · 연결 · 화면 · 알림 · 인프라 캐릭터) 구현 · 시험 끝, 실서버 가동. **보내는 쪽(클러스터) 설정은 사람이 적용할 차례** — CC 자동 모드가 공유 클러스터 변경을 막았다(아래)
- 설계는 README 3.6 "만든 모양". 여기는 조사 · 설계와 달랐던 점 · 판단 근거 · 실측

## 조사 결과

| 무엇 | 실제 |
|---|---|
| 런슈즈 · 펫퍼민트 파이프라인 | 같은 구조. GitHub push → Jenkins `pollSCM H/2`(JCasC, `ronanlab-infra platform/jenkins/values.yaml`) → BuildKit rootless → Harbor push(태그 = `GIT_COMMIT` 12자리, OCI 라벨 revision = 전체 SHA) → `ronanlab-infra apps/<앱>/kustomization.yaml` newTag 커밋(메시지에 앱 커밋 · Jenkins 번호) → ArgoCD 자동 Sync(prune · selfHeal 끔) |
| GitLab | **돌고 있지 않다** — 호스트 컨테이너 · 클러스터 네임스페이스 어디에도 없다. 10-18 학교 환경(std-gitlab)에서 GitHub로 옮겼다(Jenkinsfile 머리말). GitHub 웹훅은 Cloudflare Access에 막혀 이 서버에 오지 않는다(그래서 Jenkins도 폴링) |
| 닿는 길 | 호스트 → 클러스터: `*.ronanlab.dev`는 Cloudflare(Access 302)로 간다. ingress VIP `192.168.122.240`(MetalLB, virbr0)에 Host 헤더로 닿는다(노드 IP 192.168.121.x는 거절). 클러스터 → 호스트: 노드에서 `192.168.122.1` 닿음 |
| ArgoCD | v2.13.2. `argocd-notifications-controller`가 이미 떠 있고 cm · secret은 비어 있었다 |
| Jenkins | 익명 API 403. 나가는 웹훅 기능 없음(플러그인 없음). 차트 JCasC가 credentials를 덮어쓰므로 UI에서 자격 증명을 더하면 재시작 때 사라진다 |
| 배포된 태그 | 둘 다 HEAD와 같다(runshoes `0f349e101774`, petmint `5f31a6e6649b`) — Jenkinsfile 변경은 같은 코드를 다시 빌드 · 배포한다 |

## 설계와 달랐던 점

| 설계 · 지시 | 한 것 | 이유 |
|---|---|---|
| 웹훅: GitLab | **로컬 git 폴링**(`git_commit`) | GitLab이 없다. GitHub 웹훅은 못 온다. 같은 서버의 저장소를 보면 "어느 세션이 만든 커밋인가"까지 알 수 있어 오히려 체인 첫 고리가 단단하다 |
| build.stage = gitlab jenkins harbor argocd | jenkins harbor argocd + `git_commit` · `build_commit` 표 | 커밋은 단계가 아니라 축이다. 여러 커밋 → 빌드 하나를 표현하려면 연결 표가 필요하다 |
| Jenkins 웹훅 | Jenkinsfile에 `foreman()` 몇 줄(시작 · 끝 · 깨진 스테이지) + optional Secret 파일 | Jenkins 설정 · 플러그인 · 재시작이 없다. 알림 실패가 빌드를 깨지 않는다(`try/catch`, `curl -m 5 … || true`, Secret 없으면 보내지 않음). Groovy 샌드박스 승인이 필요한 호출(changeSets 순회)은 피하고 커밋 범위는 FOREMAN이 로컬 저장소로 계산한다 |
| 브리지 127.0.0.1만 | 같은 프로세스에 virbr0 웹훅 전용 리스너(`192.168.122.1:8001`) | VM에서 127.0.0.1에 닿을 수 없다. 대시보드 · API · 터미널은 그 포트에서 404 |
| 클러스터 설정을 적용하고 진행 | **적용하지 못했다** — 스크립트 · 패치로 준비 | CC 자동 모드 분류기가 `kubectl patch`(공유 클러스터 변경)를 막았다. 우회하지 않고 사람이 검토 · 실행하도록 `scripts/cicd-apply.sh`와 `deploy/cicd/jenkinsfile-*.patch`(두 저장소에 `git apply --check` 통과)를 남겼다 |

## 판단 근거

- **커밋 귀속은 "제목이 명령에 있어야"** — 처음엔 "커밋 시각 직전의 가장 가까운 `git commit` 호출"이었다. 실데이터에서 두 가지가 틀렸다: ① 런슈즈 세션이 `cd ~/ronanlab-infra && git commit`으로 인프라 저장소에 한 커밋이 런슈즈 커밋으로 잡혔다 ② 5분 안에 커밋이 여럿이면 가장 가까운 명령이 다른 커밋의 것이었다. 지금 규칙: 명령(1,024자 넘으면 원문)에 그 커밋 제목이 있으면 그것, 다른 제목을 줬거나 다른 저장소로 들어간 명령은 아니다, 메시지를 알 수 없는 명령(`git revert --no-edit`)만 가까운 것으로. 다른 프로젝트 세션(포먼 · '미분류')의 커밋도 제목이 맞으면 귀속. 결과(최근 7일): 런슈즈 52/54, 펫퍼민트 14/29 — **귀속된 66개 모두 제목이 일치**(어림짐작 0). 나머지는 세션 밖(사람) 커밋이거나 트랜스크립트가 없는 때
- **여러 커밋 → 빌드 하나** — 머리(GIT_COMMIT)와 직전 Jenkins 빌드 머리 사이를 `git rev-list`로. Jenkinsfile에서 Groovy로 changeSets를 꺼내면 샌드박스 승인이 필요할 수 있다(승인 대기 = 빌드가 멈춘다)
- **실패 알림은 "실패로 바뀔 때 한 번"** — ArgoCD는 같은 상태로 여러 번 알릴 수 있고, 늦게 온 running이 끝난 상태를 덮지 않게 했다
- **웹훅 포트를 virbr0에만, 그리고 IP로도** — 리눅스는 다른 인터페이스로 들어온 패킷도 호스트 주소면 받는다(weak host). LAN에서 경로를 잡아 192.168.122.1로 보내는 것을 보낸 곳 IP(VM 망만)로 한 번 더 거른다. 토큰은 hook · API와 별개
- **인프라 캐릭터 생존** — ingress VIP에 Host 헤더로 Jenkins `/login` · Harbor `/api/v2.0/ping` · ArgoCD `/api/version`(셋 다 200 확인). 3번 무응답 STALE, 24시간 STALE면 퇴장(`retired_at`), 응답 · 웹훅이 오면 돌아온다

## 시험

- `tests/test_pipeline.py` 8개 — 판정(Jenkins · Harbor · ArgoCD), 보낸 곳 허용, 커밋 귀속(제목 · 다른 저장소), 그리고 `foreman_test` + 임시 git 저장소로 전 과정: 세션 귀속 → push 표시 → Jenkins 두 빌드(2분 사이 두 커밋이 한 빌드) → Harbor 12자리 → 전체 SHA → ArgoCD Degraded(늦은 running이 덮지 않음, 알림 한 번) → 인프라 캐릭터 셋 → 화면 스냅숏에 깨진 곳 · 커밋 · 세션 제목 → Jenkins 실패 스테이지
- 실서버: 마이그레이션 0012 적용, 웹훅 포트 열림. 클러스터 노드에서 `/webhooks/jenkins` 토큰 없이 401 · 다른 경로 404 · 8000번은 닿지 않음. Jenkinsfile의 curl 부분을 그대로 돌려 브리지가 받는 것 확인(모르는 job이라 건너뜀 — DB에 안 씀)
- 전체 182개 통과

## 승인 규칙 — "실행과 글자" 넓히기 (사용자 요청, 이 단계 도중)

승인 창이 자주 떠 흐름이 끊겼다. 걸린 것은 모두 오탐: grep 검색어 속 `rm -rf`, `mktemp -d` 디렉토리를 `${V:?}`로 지우기, `.env`에서 키 이름만 뽑기, `bash -n`으로 검사만 하는 스크립트 안의 `kubectl delete`, `.env` 토큰을 curl 헤더로만 넘기기. README 3.3 표에 넣었다.

- 방식: 검사 전에 "실행되지 않는 글자 · 값이 새지 않는 것이 명백한 모양"을 무해한 자리표시로 바꾼다(`bridge/approval.py` `_neutralize`). 조건이 하나라도 어긋나면 예전처럼 검사한다. allow 판정은 바꾸기 전 원문으로 하므로 **이 예외가 allow를 새로 만들지 않는다**
- 4번(`mktemp -d` + `${V:?}`)은 허용했다 — 같은 명령에서 방금 만든 빈 디렉토리만 지울 수 있게 조건을 좁혔다(한 번만 정해짐, 다시 정하기 · for · read · eval · source · `${V:=}` · export · unset 없음, 대상이 정확히 `"${V:?}"`). 앞 명령에서 만든 디렉토리를 경로로 지우는 것은 확인할 수 없어 여전히 묻는다
- 헤더 토큰은 "화면에 안 찍힌다"에 더해 "**밖으로 안 간다**"를 조건으로 했다 — `-v` · `--trace` · `--libcurl`이 없고, 보내는 곳이 127.0.0.1 · VM 망이며 변수가 아닐 때만. 밖으로 보내면 그 자체가 유출이다
- 다시 돌려 보다 **빈틈**을 찾았다: python heredoc으로 `.env.db`를 **쓰는** 명령이 어느 규칙에도 안 걸렸다(옛 규칙은 같은 명령 끝의 `cut -d= -f1 .env.db` 때문에 우연히 물었다). 해석기 heredoc이 비밀 파일을 쓰거나 바로 찍으면 묻게 했다. 읽기만(앱이 설정을 읽는 것)은 5단계 결정대로 묻지 않는다
- 다시 돌려 보기 도구: `scripts/approval-replay.py`(DB의 과거 도구 호출에 옛 규칙(git HEAD)과 지금 규칙을 돌린다 — 6단계 때는 일회성이라 남기지 않았다)

| 프로젝트 | 활동한 날 | 옛 규칙 ask/일 | 새 규칙 ask/일 |
|---|---|---|---|
| 런슈즈 | 10 | 14.5 | 14.4 |
| 펫퍼민트 | 16 | 6.6 | 6.6 |
| 포먼 | 1(오늘) | 59 | 49 |
| 미분류 | 2 | 6.0 | 7.0(위 빈틈 — python으로 비밀 파일 쓰기) |

- **이 세션의 7 · 8단계 작업(20:30 이후, 도구 호출 304개): 10 → 3.** 남은 3개는 묻는 게 맞다 — `.env.bridge`에 토큰 쓰기, 토큰 값을 임시 파일로 옮기기, 테스트 문자열에 `rm -rf`가 든 python heredoc(실행되는 스크립트라 글자인지 가릴 수 없다)
- 포먼 하루 49는 대부분 이전 단계의 것 — 앞 명령에서 만든 임시 디렉토리를 경로로 지우기(`T=/tmp/foreman-ws.XXXX; rm -rf -- "${T:?}"`), 글롭 루프 삭제. 앞으로는 만들기와 지우기를 한 명령에 두면 묻지 않는다
- 런슈즈 · 펫퍼민트는 거의 그대로 — 남은 것은 실제 rm -r · docker 삭제 · DB DROP과 `git -C $d …`(애매한-운영명령)
- **고치지 않은 오탐 하나**: `git -C $d status`가 "git 동사 자리가 변수"(애매한-운영명령)로 걸린다 — `-C`가 값을 받는 옵션인 것을 `verb_re`가 모른다(포먼 8건 · 펫퍼민트 다수). `config/approval.toml`의 정규식이라 고치려면 보호 파일 쓰기 승인이 필요하다 — 다음에 같이 고칠 후보
- 숫자 기준이 6단계 표와 다르다: 그때는 20일로 나눴고(런슈즈 7.2), 지금은 활동한 날로 나눈다(같은 총량 약 145건)

## 남은 것

- **보내는 쪽 설정(사람)**: `scripts/cicd-apply.sh all` → 두 저장소에 Jenkinsfile 패치 적용 · push(같은 코드가 다시 빌드 · 배포된다 — 그 빌드가 첫 실제 체인이 된다). 그 뒤 첫 웹훅으로 인프라 캐릭터가 등장하는지, 실패 알림이 가는지 본다
- 체인이 실제로 한 바퀴 돈 것을 아직 못 봤다 — 시험 저장소로만 확인
- 대시보드 파이프라인 칸은 지금 "빌드 전 커밋"만 보인다(빌드 기록이 아직 없다)
