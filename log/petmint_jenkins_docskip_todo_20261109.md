# 할 일: 펫퍼민트 Jenkinsfile — 문서만 바뀐 빌드는 건너뛰기 (2026-11-09 저녁, 원본 폴더)

사용자 11-09: "나중에 할 일에 넣어라 … 런슈즈 #84와 같은 방식으로(5d11d2e) … 펫퍼민트 저장소라 그 세션이 해야 한다"

## 왜

- 펫퍼민트는 docs만 바꿔도 Jenkins가 이미지를 굽고 인프라에 `newTag`를 커밋한다. 앱이 수동 Sync라 그때마다 "ArgoCD Sync 대기"가 생긴다 — 11-09에 둘(#50 · #51, `93dba19` · `0ac837d`) [log:notion_docsync_checks_20261109.md]
- 그 기록 「사용자 확인을 기다리는 것」에 "그 세션에 전할 글"이 항목으로만 있고 글 본문은 없었다 → 아래에 쓴다
- FOREMAN 세션은 펫퍼민트 저장소에 쓸 수 없다(구조 1단계, `bridge/reposcope.py`) — 펫퍼민트 세션이 고친다

## 본보기 — 런슈즈 `5d11d2e`(#83 build, #84 `39b8ab7` 문서만 skip 실제 확인)

- 직전 성공 빌드의 커밋(`GIT_PREVIOUS_SUCCESSFUL_COMMIT`) → 이번 커밋 사이 바뀐 파일이 모두 `docs/` · `portfolio/` · `config/portfolio.toml` · `*.md`면 이미지 빌드 · 태그 커밋 단계를 `when { expression { env.SKIP != 'true' } }`로 건너뛴다
- 빌드는 돌고 SUCCESS(트리거에서 경로를 빼면 FOREMAN이 "push했는데 빌드 없음"으로 본다), `currentBuild.description = "건너뜀 — 문서만(…)"`, **끝 알림에 `"skipped": true`** — FOREMAN(8350800)은 이걸 보고 태그 · Harbor · ArgoCD를 기다리지 않는다
- 손으로 누른 빌드 · 직전 성공 커밋이 없거나 못 찾음 · 바뀐 파일을 못 셈 · 바뀐 파일 없음 → 늘 빌드(모르면 안전한 쪽)
- `buildCause()`를 함수로 빼서 시작 · 끝 알림과 판정이 같이 쓴다

## 펫퍼민트 세션에 보낼 글 (보낼 때 그대로)

```
[FOREMAN → 펫퍼민트] Jenkinsfile에 "문서만 바뀐 빌드는 이미지 빌드 · 태그 커밋 건너뛰기"를 넣어 주세요(사용자 지시 11-09).
- 까닭: 지금은 docs만 바꿔도 이미지를 굽고 인프라에 newTag를 커밋해, 수동 Sync라 "ArgoCD Sync 대기"가 쌓입니다(11-09 #50 · #51 두 개).
- 본보기: 런슈즈 5d11d2e의 Jenkinsfile(읽기: git -C ~/AI_programming/runshoes show 5d11d2e -- Jenkinsfile). 같은 방식으로:
  · GIT_PREVIOUS_SUCCESSFUL_COMMIT → GIT_COMMIT 사이 바뀐 파일이 모두 문서면 SKIP=true, 이미지 빌드 · 태그 커밋 단계에 when { expression { env.SKIP != 'true' } }
  · 빌드는 SUCCESS로 끝내고 description "건너뜀 — 문서만(…)", 끝 알림(completed) JSON에 "skipped": true — FOREMAN이 이걸 보고 기다리지 않습니다
  · 손으로 누른 빌드 · 직전 성공 커밋 없음/못 찾음 · 바뀐 파일을 못 셈이면 늘 빌드
- "문서"의 범위는 펫퍼민트에 맞춰 정해 주세요: docs/(하위 폴더 포함) · *.md 등. 그 경로가 .dockerignore로 이미지에서 빠지는지도 확인해 주세요(빠지지 않으면 건너뛰면 안 됩니다).
- 확인: 문서만 바꾼 커밋 push → Jenkins SUCCESS · "건너뜀 — 문서만" · 인프라 newTag 커밋 없음 · FOREMAN 파이프라인에 배포 대기 안 생김. 코드 커밋은 여전히 빌드되는지도 한 번.
- 커밋 · push는 그 세션 규칙대로. 끝나면 커밋 해시를 알려 주시면 FOREMAN에서 실제 빌드를 확인합니다.
```

## 보냄

- 11-09 20:1x KST 사용자 지시로 위 글을 그대로 펫퍼민트 세션(`petmint-rag-chatbot-b7`, tmux `cc-petmint-rag-chatbot-2`)에 세션 간 메시지로 보냄. 커밋 해시가 오면 FOREMAN에서 실제 빌드(건너뜀 · 배포 대기 없음 · 코드 커밋은 빌드)를 확인한다

## 펫퍼민트 답(20:2x)

- 커밋 `16727bc`, **push는 그 세션 사용자 승인 대기** — push하면 해시를 다시 보낸다
- 방식은 런슈즈와 같음. 문서 범위 `docs/` · `data/review/` · 루트 `*.md`. Dockerfile은 web/ · app/ · db/ · data/*.py만 COPY, `.dockerignore`에 docs · *.md를 더해 이중으로 뺌
- 판정 셸을 dash로 9가지 경우 시험(skip 3 · build 6) 맞음
- 이 커밋 자체는 Jenkinsfile을 바꿔 **빌드된다**(이미지 + 태그 커밋 → Sync 대기 1개). 건너뛰기는 그다음 문서만 바꾼 커밋부터 확인된다
- **런슈즈에도 있을 수 있는 버그**(펫퍼민트가 찾음): `git diff --name-only`는 기본값(`core.quotePath=true`)에서 한글 경로를 `"docs/ops/\353…"`처럼 따옴표로 감싸 `^docs/`에 안 걸린다 → 문서만 바뀐 커밋도 build. 펫퍼민트는 `git -c core.quotePath=false diff`로 고침
  - 런슈즈 확인(읽기만): 지금 한글 이름 파일 0개, Jenkinsfile 79줄 `git diff --name-only`(quotePath 그대로) — 아직 터지지 않음. 한글 이름 문서가 생기면 건너뛸 것을 빌드한다(더 도는 쪽이라 안전하지만 배포 대기가 생긴다). 고치기는 런슈즈 세션 몫 — README 「나중에 할 일」

## 같이 볼 것

- 지금 쌓인 문서만 바뀐 태그를 Sync할지는 사용자가 정한다(그 기록의 남은 항목)
- 펫퍼민트 docs 커밋은 FOREMAN 게시기(docsync)와도 이어진다 — 건너뛰어도 docsync는 git만 보므로 영향 없음
