# 실제 확인 · 배포 대기 표시 진위 · 방 배너 · 감독실 카드 (2026-11-09, 원본 폴더)

앞 세션의 남은 확인([notion_projects_docsync_20261109.md](notion_projects_docsync_20261109.md) 「확인」)과, 그 사이 들어온 화면 지시.

## 1. 런슈즈 건너뜀 빌드 — 실제 확인 ✓

런슈즈가 Jenkinsfile을 고쳐 push(#83 `5d11d2e` build, #84 `39b8ab7` 문서만 skip).
- DB `build` #84: Jenkins success, 단계 "건너뜀 — 문서만", 태그 없음, payload `skipped: true`
- `/api/pipeline`: `broke: null`, 배포 대기(waiting) 0. 파이프라인 줄 "Jenkins ✓ → Harbor – → ArgoCD –", 경고 줄 없음, 호버 "건너뜀 — 정상입니다"
- 방(헤드리스): 빌드 모니터 ✓에서 끝, 배포 담당이 걸어가지 않음. 텔레그램 빌드 경고 없음
- 덤: 정상 빌드 #83의 Harbor 칸은 "·"(아직) — Harbor를 따로 받지 않는 설계 그대로라 남김

## 2. docs 한 파일 push → 30분 뒤 그 페이지만 — 실제 확인 ✓

- 런슈즈 `origin/main` docs 변경은 `06_deployment.md` 하나(커밋 10:58:22 KST)
- 11:33:07~18 자동 맞추기: "올림 1 · 사람 수정으로 멈춤 0 · 실패 0"(브리지 로그). `doc_publish` 19행 중 바뀐 것은 06과 `@docs-sync`(`3358d6e5` → `39b8ab79`)뿐
- Notion: 06만 11:33에 바뀜, 나머지 17쪽 마지막 수정 10:44~10:47 그대로. 블록은 바뀐 9개만 고침(callout 머리말 · 코드 · 문단 · 목록 — 버전 기록)

## 3. 사람 수정 보호(`HumanEdited`) — 시험이 되지 않았다

- 06이 멈추지 않고 덮였다. 지시대로 "안 걸렸다"로 결론 내지 않고 검사가 그 블록을 봤는지부터 봤다
- Notion 버전 기록(10:50~11:40 KST, MCP `get-version-changes`): 06을 고친 쪽은 **우리 통합("CC") 하나** — 사람 수정이 맞추기 전에 없었다. 런슈즈 17쪽 모두 페이지 마지막 수정자가 봇 — 다른 페이지에도 없다
- 검사는 돌았다: 06은 지문이 달라 `publish` → `human_edits`(`bridge/notion.py:785`)를 거쳤고, 사람이 마지막으로 고친 블록이 0이라 덮었다
- 남은 것: 다시 할 때는 git에서 곧 바뀔 파일의 페이지를 그 docs 커밋 뒤 30분 안에(맞추기 전에) 본문 문단 · 목록 한 줄 고친다. 표 칸 · 목록 안 줄은 검사가 바로 아래 블록만 봐서 못 볼 수 있다(12_scribe 5절)

## 4. 펫퍼민트 "배포 승인 기다림" — 유령이 아니라 실제 ArgoCD 수동 Sync 대기

**진위**
- CC 승인 큐(`approval` pending) 0건. 이 표시는 CC 승인과 무관하다 — 파이프라인 `build` 행 #98 · #101(`stage=argocd`, `status=waiting`, `sync=OutOfSync`, `automated=false`)
- 클러스터 쪽도 실제다: 인프라 `apps/petmint/kustomization.yaml` `newTag`는 `0ac837d4dec8`, 마지막 Sync는 `d33687127aa3`(11-02) — 배포 안 된 태그 둘

**재현 경로**
1. 펫퍼민트 세션이 **문서만** 고친 커밋 둘을 push — `93dba19`(10:57, docs/13 · 14), `0ac837d`(11:01, docs/09 · 11 · pipeline)
2. 펫퍼민트 Jenkinsfile엔 문서만 건너뜀이 없다 → #50 · #51이 이미지를 굽고 인프라에 `newTag` 커밋(`2df28b0` 10:59 · `3b8d06d` 11:03)
3. ArgoCD 알림: 펫퍼민트 앱 OutOfSync, `automated: false` → `argocd_status`가 `waiting`(`bridge/pipeline.py:214`), `_undeployed_tag`가 #50 · #51에 붙임
4. 방 카드 `r.st_argocd === 'waiting'` → "⏸ 배포 승인 기다림"

**어디서 푸는가 — ArgoCD(확인한 근거)**
- FOREMAN 코드에 ArgoCD로 쓰는 호출이 없다 — `on_argocd`는 알림을 받기만 한다(README 3.6 "읽기 조회"). 화면에 승인 버튼도 없다
- 펫퍼민트 앱은 ArgoCD 쪽에서 수동 Sync다(알림 본문 `automated: false`, `config/pipeline.toml` 9줄). 푸는 길: ArgoCD 화면의 Sync(또는 `argocd app sync petmint` — CC 세션이 치면 `approval.toml` "argocd-동기화"로 승인을 묻는다)
- 치우는 쪽: 같은 리비전의 Synced · Healthy 알림 → `success`, 앞선 #98은 `started_at < at`으로 `stale`. 조건은 만족될 수 있다(갇힌 구조 아님). 다만 FOREMAN 안엔 풀 곳도, 전엔 링크도 없었다

**승인 · 대기 종류(지금 화면)**
| 종류 | 문구 | 어디서 푸나 | 안 풀리면 |
|---|---|---|---|
| CC 도구 승인(FOREMAN 훅) | "❗ 승인 대기 N" · 감독실 "멈춤 — 승인 대기 N" · 승인 카드 | 패널 승인 카드 · 그 세션 터미널 | 화면 답 · 터미널 답(`on_tool_result`) · `wait_s` 시간 초과(텔레그램 ⏰) · 브리지 재시작(`abandoned`) — 승인 없이 재개돼도 치워진다 |
| CC 질문(AskUserQuestion) | "❓ 질문 N — 패널에서 답합니다" · 감독실 "멈춤 — 질문 N" | 패널 질문 카드 · 터미널 | 위와 같은 길 |
| ArgoCD 수동 Sync 대기 | (고친 뒤) "⏸ 배포 대기 — ArgoCD에서 Sync를 눌러야 올라갑니다 ↗" · 칸 "ArgoCD Sync 대기" | ArgoCD 화면 | Sync뿐. **오래 남아도 알리는 장치 없음** |
| 수동 Sync 아닌 OutOfSync | 진행 중(…) | ArgoCD 자동 Sync | — |
| CC 자체 권한 거부(auto mode) | **화면에 없음** | 그 세션 | 아래 5 |

## 5. 작업 중인데 멈춤처럼(또는 그 반대로) 보이는 곳

- **CC 자체 권한 검사에 막힌 것은 FOREMAN에 보이지 않는다.** 펫퍼민트 터미널(11:28 읽기만): 서브에이전트의 Notion 쓰기가 CC auto mode 검사에 막혔고("외부 시스템 쓰기"), 메인은 (가)/(나)/(다) 선택을 묻고 입력 줄에서 기다린다. FOREMAN은 `cc_status: idle` → "대기" · "쉼". 글로 물은 것이라 질문 카드도 아니다 — 사람 답을 기다리는데 "쉼"으로 보인다
- 같은 세션 `open_turn`(서브에이전트 완료 알림으로 열린 턴, 11:22:57)이 닫히지 않아 `stuck_turn: true`
- ArgoCD waiting 칸 호버에 지난 Sync 메시지 "successfully synced"가 같이 떠 반대로 읽혔다 → 고침(아래)

## 6. 고친 것

**배포 대기 문구 · 링크**(사용자 지시 — ArgoCD에서 푸는 것이면 버튼 없이 문구 · 링크)
- "배포 승인 기다림" 다섯 곳 → 배너 "⏸ 배포 대기 — ArgoCD에서 Sync를 눌러야 올라갑니다 ↗", 짧은 칸 "ArgoCD Sync 대기"
- `/api/pipeline` 프로젝트마다 `argocd_url`(`https://<argocd host>/applications/<app>`), ArgoCD 칸 url이 비면 그것으로 — 파이프라인 줄 ArgoCD 칸이 링크가 된다. 배너의 그 줄은 밑줄, 누르면 새 탭, 호버 설명. 주소 형식은 ArgoCD 표준 경로이고 Access 뒤라 여기서 열어 보지는 못했다
- waiting일 때 지난 Sync 메시지를 내지 않는다

**방 배너**(사용자 지시) — 캔버스 맨 위(탭 줄 바로 밑)에 폭 전체, 방은 `aim`이 배너 높이를 뺀 칸에 위로 붙여 맞춘다. 경고가 생기거나 사라지면 프레임마다 다시 맞춘다. 넘치면 `…` 대신 낱말 단위 줄바꿈(`bridge/static/js/wrap.js`)
- 세 테마 × 1920 · 1366 · 1024: 탭과 배너 틈 0, 배너 66px · 방 윗벽 73~80px, 배너 없을 때 방 윗벽 7~15px(원래 0.3칸 여백). 전엔 1024에서 방이 세로 가운데라 위에 47px 빈 띠
- 두 줄 줄바꿈은 화면에서 만들 수 없어(지금 글이 폭 520에서도 한 줄) JS 시험으로

**감독실 카드**(사용자 지시) — 방 아래로 떼고(`aim`이 카드 높이만큼 비움) 두 줄: 이름 · 지금 상태("작업 중 N" / "멈춤 — 승인 대기 N" · "멈춤 — 질문 N" · "멈춤 — 파이프라인 실패(단계)" / "쉼" / "세션 없음"). 토큰 · Opus · 최근 사용량 · 배포 대기는 호버(`textTip`). 캔버스 폭 4등분, 네 칸 같은 높이(가장 긴 카드), 넘치면 줄바꿈(괄호 앞에서 — "라운지" / "(떠돌이)")
- Ctrl+Z로 멈춰 둔 세션(SUSPENDED)은 "쉼"에 넣고 호버에 "멈춰 둠 N" — "멈춤"은 사람이 풀어야 하는 것만

## 확인

- 파이썬 487 · JS 52 통과(새 `tests/js/banner_wrap.test.mjs` 4)
- `tools/screen.py` 세 테마 × 세 크기 × 감독실 · 펫퍼민트 · 런슈즈 · FOREMAN 0건, 페이지 오류 0
- 브리지 다시 띄움(승인 대기 0 뒤) — `argocd_url` 실림, 펫퍼민트 ArgoCD 칸 url · message None 확인

## 사용자 확인을 기다리는 것

- 펫퍼민트 Jenkinsfile 문서만 건너뜀(다른 저장소 — 그 세션에 전할 글)
- 지금 쌓인 펫퍼민트 태그 둘(문서만 바뀐 이미지)을 Sync할지
- ArgoCD Sync 대기가 오래 남으면 알림(지금 없음)
- CC 자체 권한 거부 · 글로 묻고 기다리는 세션을 "쉼"과 구분해 보이기
