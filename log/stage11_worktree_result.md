# 11 — 따로 작업(worktree) · 스키마 잠금 결과 (2026-11-05)

설계와 미리보기 브리지 제안은 `docs/11_worktree.md`에 있다. 이번에는 미리보기 브리지를 빼고 만들었다.

## 한 일

- `bridge/worktree.py`
  - 만들기: `.git/info/exclude`, 링크(.venv · .env* · */node_modules), CC 메모리 링크
  - 상태 보기: 앞선 커밋 · 원본이 앞선 커밋 · 커밋 안 된 변경 · 바뀐 파일
  - 합치기: rebase → ff. 충돌이면 abort하고 충돌 파일을 돌려준다
  - 버리기
- `bridge/schemalock.py` + `config/worktree.toml`
  - 프로젝트별 마이그레이션 경로 · 명령
  - 상태 파일 `~/.foreman/schema_lock.json`
  - `approvals.pre_tool_use`에서 승인 모드보다 먼저 보고 deny한다
- `handoff.spawn_new(worktree=None|True|False)`
  - None이면 살아 있는 세션이 같은 프로젝트에 있을 때 worktree로 띄운다
  - `character_session.worktree_path`를 채운다(0001부터 있던 칸)
  - worktree 세션의 [새로 띄우기]는 원본 저장소 기준으로 한다(같은 worktree에 둘이 붙지 않게)
- `handoff.worktree_act`: 세션이 끝난 뒤에만 한다. 잠금을 풀고 `session_action`에 `wt-merge` · `wt-discard`를 남긴다
- API
  - `POST /api/spawn`의 `worktree`
  - `POST /api/sessions/{id}/worktree`: 버리기는 이름을 그대로 적어야 한다
  - `GET` · `DELETE /api/schema-lock`
- 화면
  - 패널 "따로 작업" 칸: 브랜치, 앞선 커밋, 커밋 안 됨, 잠금 보유, [합치기] · [버리기]
  - 끝내기 확인 창: 커밋 안 된 변경이 있으면 경고한다
  - 포먼 계획 카드: "따로 작업(worktree)" 칸. 살아 있는 세션이 있으면 켜진 채로 나온다
- 끝내기의 tmux 정리 경쟁 상황을 고쳤다. 세션 파일이 사라진 직후 pane에 `claude`가 남아 있어 정리를 건너뛰었다 → 5초까지 기다린다
- 화면 크기(같은 날 사용자 요청: 브라우저 가로 · 세로 스크롤바)
  - `html, body { overflow:hidden }`
  - `#app` 높이를 `100dvh - --term-h(기본 0)`으로
  - 패널 폭 상한 `100vw - 160px`
  - 터미널 높이 `45dvh`(최소 `min(260px, 40dvh)`, 최대 `55dvh`). 760px 이하 휴대폰 폭은 원래대로 거의 전체

## 확인

- 시험 `tests/test_worktree.py` 5개: 만들기 · 링크 · 메모리, rebase 합치기와 정리, 충돌 때 멈추고 되돌림, 버리기, 스키마 잠금 흐름
- 전체 Python 369, JS 31 통과
- 실제 시험(세션 179)
  - 이 세션이 살아 있는 상태에서 `/api/spawn` → `.worktrees/foreman-2`, `cc/foreman-2`, 링크 4개, 메모리 링크
  - 신뢰 창이 뜨지 않았다
  - 시험 세션이 원본 MEMORY.md 첫 줄을 말했다
  - 이 세션이 잠금을 잡은 뒤 시험 세션의 `Write migrations/9999_lock_test.sql`이 "FOREMAN 스키마 잠금 — …"으로 거부됐다. 파일은 생기지 않았다
  - 끝낸 뒤 패널 정보가 맞았다. 버리기는 틀린 이름이면 거부, 맞는 이름이면 worktree · 브랜치가 지워졌다
  - 시험 잠금은 API로 풀었다
- 화면 크기: 헤드리스로 1600×900 · 1366×697(배율 0.9 · 1.25 · 1.5) · 1100×700 · 900×500 · 761×460에서 확인했다
  - 세션 선택, 넓게 모드, 터미널 열기 상태
  - 문서 크기가 창 크기와 같았다. 픽셀 화면 높이는 0보다 컸다

## 미리보기 브리지(같은 날, 사용자 결정: A · 버튼 때만 · 런슈즈는 나중)

- `bridge/preview.py` 미리보기 서버
  - `/` · `/office` · `/classic` · `/static/*`는 worktree의 파일로 준다. 머리에 토큰 받기(`#t=`, 받고 주소에서 지움)와 "미리보기 · cc/<이름>" 띠를 끼운다
  - 그 밖의 HTTP와 웹소켓은 지금 브리지로 넘긴다
  - 웹소켓은 같은 출처일 때만 넘긴다. 넘길 때 Origin을 지금 브리지 것으로 바꾼다(터미널 WS의 Origin 검사 통과)
- `bridge/previews.py` 관리
  - 8200~8299에서 빈 포트를 고르고 tmux `fm-pv-<이름>`에서 띄운다. 10초 안에 뜨는지 본다
  - 상태는 `~/.foreman/previews.json`. 브리지가 뜰 때 맞춰 본다(sweep)
  - 명령은 `config/worktree.toml [preview.foreman]`. 서버 코드는 원본 저장소 것을 쓴다(worktree가 이 기능보다 먼저 갈라졌을 수 있다)
- 정리: 세션을 끝내거나 합치기 · 버리기 때 끈다
- 화면: 패널 "따로 작업" 칸에 [미리보기 열기] · [미리보기 닫기]
  - 팝업 차단을 피하려고 누른 순간 빈 창을 먼저 연다
  - 실패하면 그 창을 닫는다
- 시험 `tests/test_preview.py`
  - 페이지에 끼운 것이 맞는지, 토큰 받기가 모듈보다 앞서는지
  - worktree의 정적 파일을 주는지
  - 넘기기: 인증 헤더 · 쿼리 · 본문 · Host · Set-Cookie 여러 개
  - 빈 포트 고르기
- 실제 시험(세션 180, worktree `foreman-2`)
  - worktree의 office.html에만 표시를 넣고 [미리보기]를 열었다 → :8200. 다시 열면 같은 것을 다시 썼다
  - 헤드리스로 확인한 것
    - 표시와 띠가 있었다
    - 실시간 연결("연결됨")과 캐릭터 14명이 보였다
    - 터미널 창이 미리보기를 거쳐 붙었다
    - `#t=`(시험 값)를 저장하고 주소에서 지웠다
  - 세션을 끝내니 미리보기 tmux도 꺼졌다. 버리기로 정리했다

## 설계와 달랐던 점 · 판단 근거

- 스키마 잠금이 저장소 맨 위를 잘못 잡았다. worktree가 아닌 경로에서 `split()`이 파일 경로 자체를 돌려줬다 → 위로 올라가며 `.git`(원본은 폴더, worktree는 파일)을 찾는다
- `.gitignore`의 `.venv/`는 끝에 `/`가 있어 링크(파일)에 걸리지 않는다. 그래서 저장소 파일을 고치지 않고 `info/exclude`에 넣었다. 다른 저장소(런슈즈 등)에도 저장소 파일 변경 없이 쓸 수 있다
- worktree는 원본의 **커밋된** 상태에서 갈라진다. 원본에 커밋 안 된 변경이 있으면 새 세션에는 그것이 없다
- 스크롤바는 헤드리스에서 재현되지 않았다. 바깥 틀이 넘칠 수 없게 막는 쪽으로 고쳤다. 사용자 브라우저에서 확인이 필요하다
