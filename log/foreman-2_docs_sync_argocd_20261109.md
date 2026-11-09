# 11-09 동작을 문서에 맞춤 · ArgoCD Healthy 알림이 안 오는 원인 (2026-11-09 저녁, worktree foreman-2)

코드는 고치지 않았다. 문서는 지금 코드를 기준으로 맞췄다(log와 코드가 다르면 코드 — 아래 「log와 다르게 쓴 것」).

## 1. 문서에 넣은 것

| 문서 | 넣은 것 |
|---|---|
| `docs/style_guide.md` 「4-1. 화면 글」 | 툴팁 보이는 모양: 문장마다 줄(`splitSentences`), 숫자 줄은 넘치면 줄바꿈 + 들여쓰기, 긴 경로 · 명령은 `/ _ - . = , : ?` 뒤에서만(`softEsc`, 16자 넘는 낱말), 폭 `min(440px × 배율, 화면 − 16px)`, 높이 넘치면 폭을 화면까지(`fit`), 점검 `tipAudit()`. 옛 줄("설명 안에서 줄을 바꾸지 않는다" · nowrap 자름)은 지운 줄로 |
| 같은 절 | 화면 말 표에 "쌓인 대화 N%" ↔ "한도" 두 줄 + 이름을 나눈 까닭, 겹침 띠 세 갈래(📝 빨강 · 🔁 겹침 노랑 · 🔁 겹칠 수도 옅게) 표, 옮기기 ② 확인의 [이대로 보내기] / [덧붙여서 보내기] · [덧붙이지 않기] |
| `docs/12_scribe.md` 「5. Notion 연동」 | 펫퍼민트 `create = true`(11-09 16:51:18) · `new_parent = "folder"` · `new_title = "numbered"` · 중간 번호는 실패(`file_order`, 지운 문서 번호도 셈) · `order = "keep"`의 까닭 · `archive = false` · `headings = "md"` · 목록 줄은 꼬리 줄만 · heading_4 미확인. 구조 그림의 "새 페이지 안 만듦" → "맨 뒤 번호 새 페이지만", 휴지통 조건에 `archive = false` |
| `docs/15_usage.md` | 「6. 화면」 머리 칩 이름 "한도:" · 소진 예상 · 호버 리셋 줄 · What's contributing(`parse_contrib`), 막혔을 때 90% 알림 · rule 키. 새 「6-2. 추가 사용(크레딧)」: CC 한도 글로 막힘 · 이어 씀 · 모름, StopFailure 훅 행 빼기, `[credits]`는 참고용 · 3일/달 바뀜에 감춤. 머리 상태 줄 |
| `docs/11_handoff_v2.md` | 「③」에 덧붙이기(`## 사람이 덧붙인 말 (넣기 직전)`) · 새 세션이 뜨는 자리(replace → 원본 폴더, 「이 세션이 뜬 자리」). 「3. 압축 알림」 아래 새 절 「쌓인 대화 비율 · 작업 전환 권유 (11-09)」 — `[windows]`, `context_pct` · `switch_min_pct`, 먼저 닿는 쪽, rule `ctx:` · `pct:` · `over:` · `switch:`, 전환 권유 세 조건, 패널 띠(`/api/dashboard` `switch`) |
| `docs/operations.md` 「3.」 | systemctl 줄에 실제 명령 한 줄, 다시 띄울 것은 파이썬뿐 · 화면 코드 지문 띠, screen.py가 nameAudit · cardAudit · tipAudit를 기본으로 셈 · `--ui-scale` · 통과의 한계 |
| 같은 문서 「2.」 「4.」 | 시험: 두 세션 동시 실행 금지 · `losscheck_recover`. worktree에서 `PYTHONPATH=.` |
| 같은 문서 「5. 알림」 | rule 키로 한 번만, 겹침 알림을 지금 동작으로(낱말은 띠만, 텔레그램은 같은 파일 · 📋 다른 프로젝트 같은 글, `edit_scan_sec` 60), 알림 표(권한 거부 30분 · '!' · Sync 대기 · 끝나지 않는 배포 · 쌓인 대화 · 한도 — 코드 · kind · 조건 · rule 키), 세션 간 메시지 읽음(텔레그램이 아니라 활동 탭 표시) |
| `README.md` 3.1 | 입력 줄이 가려지면 Esc로 닫고 보내기(`inject.clear_screen`, 최대 3번, busy면 안 보냄) |

## 2. 7번 — 오늘 log에 있었는데 README · docs에 없던 것(찾아서 넣음)

- 입력 줄이 가려지면 Esc 최대 3번(`plan_dialog_escape_retry`) → README 3.1
- 화면 코드 지문 · [새로 고침] 띠, js · css는 재시작 없이 나감(`pixel_bigger_question_card` · `screen_mismatch_waits`) → operations 3
- screen.py `--ui-scale`, 통과는 "고른 화면"뿐(`pixel_bigger_question_card` · `screen_mismatch_waits`) → operations 3
- 📋 다른 프로젝트 같은 글(`cross_paste`) → operations 5
- 시험이 운영 점검을 failed로 바꾸던 것 · `losscheck_recover`(`cross_paste`), 시험 DB 동시 사용(`repo_scope_readonly`) → operations 2
- worktree에서 `PYTHONPATH=.`(`foreman_context_pct`) → operations 4
- 옮기기는 옛 세션을 빼고 판단해 원본 폴더에서 뜸 · 「이 세션이 뜬 자리」(`handoff_replace_main` · `handoff_flow_check`) → 11_handoff_v2 ③(README에는 「나중에 할 일」 줄에만 있었다)
- 세션 간 메시지 읽음(`alerts_denied_xmsg_bang`) → operations 5. README에는 기록 파일 이름으로만 걸려 있었다
- 권한 거부 30분 알림 → operations 5(어디에도 없었다). '!' 알림은 README 3.1에 한 줄 있어 표에서 그쪽을 가리킴

넣지 않은 것: README 로드맵 · 「나중에 할 일」 표(원본 세션 몫 — 887줄 worktree 덧붙이기 줄은 이미 ✅로 적혀 있다), [⌂] 빨간 표시 종류 표(`screen_argocd_read` 2절 — 화면 설명이라 log로 충분하다고 봤다), 런슈즈 서브에이전트 모델(다른 저장소).

## 3. log와 다르게 쓴 것 (코드가 기준)

- 크레딧: `credits_and_middle_number`는 `[credits]` 값으로 막힘 · "갱신 필요"를 판정한다고 썼으나 뒤 기록(`tips_and_credit_signal`)에서 바뀌었다. 코드(`usage.credit_view`)는 **CC 한도 글이 이번 달 없을 때(모름)만** 넣은 값의 막힘을 쓴다 — 브리프의 "판정에 안 쓰고"보다 한 칸 넓다. 문서에 그대로 적었다(칩 "⛔ 추가 사용 막힘(넣은 값)")
- `softEsc`가 끊는 자리는 브리프의 `/ _ - .`보다 많다(`= , : ?`도), 그리고 16자 넘는 낱말에만
- 같은 파일 알림의 "새로 겹친 파일이 생길 때만"은 브리지 메모리(`_files_sent`)라 다시 띄우면 다시 알릴 수 있다 — rule 키가 아니다
- 세션 간 메시지 읽음은 텔레그램 알림이 아니다(패널 표시)

## 4. ArgoCD Healthy 알림이 안 오는 원인 — 조사만(인프라 · 클러스터 고치지 않음)

조사는 이 세션이 띄운 에이전트가 읽기 명령으로 했고, 핵심 근거(트리거 정의 · 펫퍼민트 `notified` 기록)는 직접 다시 봤다.

### 원인

**`foreman-deployed` 알림이 Sync 전에 이미 나가 그 리비전의 "한 번"을 써 버렸다.**

- 트리거(클러스터 `argocd-notifications-cm`, 사본 `deploy/cicd/argocd-notifications-foreman.yaml:56-59`):
  `when: operationState != nil and operationState.phase in ['Succeeded'] and health.status == 'Healthy'`, `oncePer: app.status.sync.revision`
- 수동 Sync 앱(펫퍼민트)에 새 커밋이 오면 `sync.revision`은 곧바로 새 목표(9efe67d4)로 바뀌는데 `operationState`는 지난 작업(Succeeded) 그대로, 옛 파드는 Healthy → **OutOfSync인 채로 조건이 참** → 그 자리에서 deployed 전송, oncePer 키 소진
- 앱 주석 `notified.notifications.argoproj.io`: `9efe67d4:foreman-deployed` 와 `9efe67d4:foreman-out-of-sync` 가 **같은 06:02:44Z(15:02:44 KST)**. 사용자 Sync는 15:39:22, 끝 15:39:34, Healthy 15:39:57
- 컨트롤러 로그: 06:39:57Z 이후 deployed 조건은 매분 참인데 전송 줄이 없음(이미 보냄). sync-succeeded는 15:39:36 Progressing 때 이미 한 번 보냄 → Healthy로는 다시 안 감
- 같은 초에 deployed · out-of-sync가 찍힌 리비전이 오늘 여럿(4c6e451d · 7b154165 · cd50cec9 · 2df28b0a · 3b8d06dd) — 수동 Sync 회차마다 같은 일이었을 것(이 행들이 stale로 닫힌 것과 맞다)
- FOREMAN 쪽(`bridge/pipeline.py` `argocd_status`)은 맞게 읽었다: 15:02 deployed 본문은 OutOfSync · 수동 → `waiting`, 15:39:36 sync-succeeded는 Progressing → `running`, 그 뒤 끝 알림이 없어 `check_argo_running`이 읽어서 닫음
- 템플릿 본문에 트리거 이름 칸이 없어 FOREMAN은 이 "deployed"가 OutOfSync 때 온 것인지 알 수 없다

| | 런슈즈 | 펫퍼민트 |
|---|---|---|
| 구독 | 기본 구독(`instance=root`) | 같음 |
| syncPolicy | `automated` | 수동 |
| 새 리비전 때 | 몇 초 안에 자동 Sync → deployed 조건이 잠깐 거짓 → 약 13초 뒤 Healthy에서 전송(09:27:01 out-of-sync → 09:27:14 deployed) | OutOfSync인 채 조건 참 → 즉시 전송 · 소진 |
| Sync 뒤 Healthy 알림 | 온다 | 안 온다 |

런슈즈가 되는 것은 자동 Sync가 빨라 이기는 경합 덕이다 — 자동 Sync가 늦으면 런슈즈도 같은 일을 겪는다.

### 바꿀 곳

- 파일 · 키: 클러스터 `argocd/argocd-notifications-cm`의 `trigger.foreman-deployed`. 원본 사본은 **FOREMAN 저장소** `deploy/cicd/argocd-notifications-foreman.yaml`(ronanlab-infra에는 없다)
- **안 A(권함)** — when에 Synced를 더한다. oncePer는 그대로
  - 앞: `app.status.operationState != nil and app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'`
  - 뒤: `app.status.operationState != nil and app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy' and app.status.sync.status == 'Synced'`
  - OutOfSync 동안은 거짓이라 키가 남고, Sync 뒤 Synced · Healthy가 되는 순간 보낸다
- 안 B — `oncePer: app.status.operationState.syncResult.revision`. 같은 리비전 다시 Sync · 앱 경로를 안 건드린 커밋에 deployed가 안 나가게 되어 동작 변화가 크다

### 적용 방법

- 이 cm은 ArgoCD가 관리하지 않는다(루트 앱은 Application만, cm managedFields는 kubectl apply · patch뿐, `log/stage8_cicd_result.md`) → **ArgoCD가 되돌리지 않고 ronanlab-infra 커밋도 필요 없다. ArgoCD 앱 재적용도 아니다**
- 순서: ① FOREMAN 세션이 yaml의 when을 고쳐 커밋 ② 사용자 승인 뒤 m-k8s에서 `kubectl -n argocd patch cm argocd-notifications-cm --type merge --patch-file argocd-notifications-foreman.yaml`(파일 머리말 방식 — 토큰은 secret 키 `foreman-webhook-token` 참조만, cm에 값 없음). 키 하나만이면 `-p`로 `trigger.foreman-deployed`만
- 컨트롤러는 보통 cm 변경을 다시 읽어 재시작이 필요 없다 — 이 클러스터에서 실측은 안 함. 적용 뒤 로그의 deployed 평가 조건 해시가 바뀌는지 본다

### 위험

- 조건 글이 바뀌면 해시(`[0].Yv81…`)가 바뀌어 oncePer 기록이 새로 시작된다 → 적용 직후 지금 Synced · Healthy인 앱마다(런슈즈 · 펫퍼민트 · cloudflared) 현재 리비전으로 deployed가 **한 번씩 다시** 갈 수 있다. FOREMAN에는 같은 외부 id 성공 행이 있어 덮어쓸 뿐이고 cloudflared는 모르는 앱이라 무시. 다만 "나중 결과가 대신함"이 그 시각 이전 진행 중 행을 stale로 닫을 수 있으니 **진행 중 배포가 없을 때** 적용한다
- 안 A에서도 앱 경로를 안 건드린 커밋(Synced 유지)엔 지금처럼 바로 deployed가 나간다(지금과 같음)
- 구독자 · 서비스는 foreman 하나라 다른 곳 영향 없음
- 고치면 FOREMAN의 10분 뒤 직접 읽기(`check_argo_running`)는 안전망으로 남긴다

### 확인 못 한 것

- 컨트롤러가 재시작 없이 cm을 다시 읽는지
- FOREMAN이 15:02:44 · 15:39:22 · 15:39:36에 받은 웹훅 원문(행 payload가 읽기 결과로 덮였다)
- **브리프의 "109번 행"은 DB `build.id` 116(`petmint@9efe67d4`)이다** — `build.id` 109는 4c6e451d로 stale로 닫힌 행. 화면 번호와 DB id가 다를 수 있다
- 행 116의 `started_at`이 대기 시작 13:53으로 남은 것 — sync-running 때 바뀌어야 하는데 그대로(`screen_argocd_read` 4절에 "고치기 전 코드로 닫힘"이라 적혀 있어 같은 일로 보인다, 다시 보지 않았다)

쓴 명령(모두 읽기): `kubectl get applications` · `get cm argocd-notifications-cm -o yaml`(주소 가림) · `get applications.argoproj.io {runshoes,petmint} -o json` · `logs deploy/argocd-notifications-controller`, ronanlab-infra grep, `build` 표 SELECT.

## 5. 이어서(11-09, 32f4b60) — 안 A 고침 · 클러스터 적용

사용자: "권한 안 그대로 간다. 조건 끝에 and app.status.sync.status == 'Synced' 추가. oncePer는 그대로 … kubectl patch는 내 승인을 받고 한다"

- **고친 파일은 FOREMAN 저장소의 `deploy/cicd/argocd-notifications-foreman.yaml`이다**(ronanlab-infra · k8s-cluster가 아님 — 이 cm의 원본 사본은 FOREMAN에만 있다). 글로 쓴 제안이 아니라 사용자 지시로 **실제로 고쳐 커밋했다**(`32f4b60`, 이 브랜치). 키 `trigger.foreman-deployed`의 when 끝에 `and app.status.sync.status == 'Synced'`, oncePer 그대로, 위에 까닭 주석
- 적용 전 확인
  - ArgoCD 앱 넷 Synced · Healthy · Succeeded, FOREMAN `/api/pipeline`에 진행 중 배포 없음(펫퍼민트 "대기" 4는 push 안 한 커밋)
  - 클러스터 cm과 파일을 키마다 맞댐(값은 출력 안 함): `trigger.foreman-deployed`만 다르고 서비스 · 템플릿 · 구독 · 다른 트리거는 같음 → 그 키 하나만 patch
- **18:43:42 KST 적용**(사용자 승인): 그 키만 담은 JSON을 표준 입력으로 `kubectl -n argocd patch cm argocd-notifications-cm --type merge --patch-file /dev/stdin` → `patched`. 클러스터 값이 파일과 같음을 다시 읽어 확인
- **컨트롤러는 재시작 없이 다시 읽었다** — 다음 평가(09:43:57Z)부터 조건 해시가 `[0].Yv81…` → `[0].v_xI9i8…`로 바뀜. 예상대로 Synced · Healthy인 앱 셋(runshoes · petmint · cloudflared)에 지금 리비전 efb9bf33으로 deployed가 **한 번씩 다시 갔고**, 같은 분의 두 번째 평가부터 "already sent"
  - FOREMAN: 18:43:57 petmint · runshoes `argocd …@efb9bf33 → success`(있던 성공 행에 덮어씀, 상태 변화 없음), cloudflared "모르는 ArgoCD 앱" 건너뜀
- 실제 배포 확인 — 펫퍼민트 세션에 docs 한 줄 커밋 · push를 부탁함(사용자 결정 — FOREMAN 세션은 다른 저장소에 쓸 수 없다). 펫퍼민트는 docs만 바뀐 커밋도 Jenkins → ArgoCD로 간다(런슈즈와 달리 "건너뜀 — 문서만" 없음, `/api/pipeline` 체인 2e287cbc · 3eb664f3). push 안 한 커밋 4개가 같이 올라가는지는 그 세션이 판단. Sync는 사용자가 누른다

## 6. 같은 파일 알림(README.md) — 메인과 확인

- 사용자: 230(메인)도 README.md를 고쳤다는 알림은 헛경보가 아니다, 합칠 때 충돌 날 수 있다
- 확인: 230의 README 수정은 `c4a08ce`(18:25)로 **이 브랜치의 바탕에 이미 들어 있다**. main은 그 뒤 README 새 커밋 · 커밋 안 한 변경 없음 → 지금 합치면 부딪치지 않는다. 이 브랜치의 README 변경은 3.1 「제출 확인」 줄 위 한 줄뿐
- 메인(foreman-59)에 알림 → 답: 지금 그 파일들을 고치지 않는다, README를 고치게 되면 3.1 「제출 확인」 앞뒤를 피하고 커밋을 알려 준다, 합치기는 메인이 한다
- 같은 파일 알림은 "최근 3시간 안에 둘 다 고쳤다"로 판정해, 이미 합쳐진 바탕 위에서 고친 경우도 잡는다 — 이번이 그렇다(실제 충돌 위험은 그 뒤 main이 다시 고칠 때)

## 7. 이어서(11-09) — 실제 배포로 확인: Sync 뒤 Healthy 알림이 온다

- 펫퍼민트 세션이 그 세션 사용자 승인으로 push(`2e287cb..a498cb5`, 시험 커밋 a498cb5 = `docs/ops/배포기록.md` · `docs/README.md` 한 줄 + 사용자가 지시했던 안 올린 커밋 3개). 사용자가 ArgoCD에서 Sync
- 흐름(KST, ArgoCD 앱 상태 · 컨트롤러 전송 · FOREMAN 행 `petmint@1998617f`):

| 시각 | ArgoCD | 컨트롤러가 보낸 것 | FOREMAN |
|---|---|---|---|
| 18:49:20 | — | — | jenkins `petmint-app#55` → success |
| 18:49:25 ~ 27 | OutOfSync · Healthy · (지난 작업) Succeeded | **out-of-sync만** — deployed 없음(고치기 전엔 여기서 같이 나갔다) | → waiting(Sync 대기) |
| 18:49:53 | Sync 누름 | sync-running | → running |
| 18:50:11 | Synced · Progressing | sync-succeeded | → running |
| 18:50:30 | Synced · Healthy | **foreman-deployed** | → **success**(끝 알림으로 닫힘 — 직접 읽기 `[끝 알림이 없어 ArgoCD를 읽어 확인]` 아님) |

- **결론: 고친 조건이 맞게 동작한다. 컨트롤러 재시작은 필요 없었다**
- 런슈즈는 같은 인프라 커밋(1998617f)에서 앱이 바뀌지 않아 Synced 그대로 → 18:49:25 바로 deployed → success. 안 A에서도 그대로인 동작(「위험」 둘째 줄)
- 감시 스크립트 실수 한 번: 컨트롤러 "Sending" 줄에 리비전이 없는데 옛 리비전 이름으로 거르려 해서, 옛 deployed 줄을 새것으로 읽고 18:49:29에 일찍 끝났다 → 시각(`--since-time`)으로 걸러 다시 돌림. 결과 판단에는 영향 없음(위 표는 다시 돌린 것)

## 남은 것

- 이 브랜치는 커밋만 했다(push 안 함, 브리지 안 띄움 — 문서 · yaml만 바꿔 브리지 동작 같음)
