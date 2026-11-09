# 구조 1단계 — FOREMAN 세션은 다른 저장소를 읽기만 (2026-11-09 저녁, 원본 폴더)

앞 기록: [old_session_exit_bg_20261109.md](old_session_exit_bg_20261109.md)

## 정한 것(사용자 11-09, 구조 질문 답 뒤)

- 1단계 관리자(FOREMAN 세션)는 다른 저장소를 읽기만 — 훅으로 막는다. 읽기는 그대로. 상태 보기는 `git ls-remote` · 스크래치 복제본으로
- 2단계 docs 뒤처짐 신호 · 3단계 역할 나누기는 화면 worktree · 문서 세션이 끝난 뒤. 서기는 띄울 때만 만든다
- Bash 샌드박스는 일상 명령을 시험한 뒤
- 서기 화면 세 가지(Notion 게시 나누기 · 할 일과 시킬 일 분리 + 묶는 기준 · 서기와 대화)는 할 일로만 — README 「나중에 할 일」

## 한 일

- 새 `bridge/reposcope.py` + `config/approval.toml [repo_scope]`(`read_only_elsewhere = ["foreman"]`, 읽기 명령 목록). PreToolUse에서 스키마 잠금 바로 뒤, **승인 모드와 상관없이** 거부(규칙 이름 `다른저장소-쓰기`)
  - Edit · Write · MultiEdit · NotebookEdit: 대상이 자기 저장소(+ `.worktrees/*`) 밖의 git 저장소 안이면
  - git: `-C` · `cd`(줄을 넘어 이어짐) · `--git-dir` · `--work-tree` · `GIT_DIR=`로 다른 저장소를 가리키며 읽기가 아닌 것. fetch · pull도 막는다(그 저장소 .git에 쓴다)
  - 막지 않는 것: `/tmp` · 스크래치 아래(복제본), git 저장소가 아닌 곳(`~/.claude` · 메모리 — 홈은 저장소가 아님을 확인), heredoc 본문(커밋 메시지 안 글자)
  - 거부 사유: "다른 저장소 쓰기 막힘 — 이 세션은 다른 저장소(runshoes)를 읽기만 합니다(git push). 고칠 것은 그 저장소의 세션에 맡기거나(세션 간 메시지) 사용자에게 요청하세요. 상태만 볼 때는 git ls-remote, 손볼 시험은 /tmp · 스크래치 복제본에서 합니다."
- 저장소 경로는 DB `project.repo_path`(assembler가 이미 올려 둔 것). ronanlab-infra · k8s-cluster는 프로젝트가 아니어도 git 저장소라 막힌다

## 다시 돌려 봄 — 지난 7일 FOREMAN 세션 호출(Bash 4,505 · Edit 3,093 · Write 290)

- 첫 판 24건 중 헛거부 4: `git reflog show` · `git remote get-url origin`(`$(…)` 안) · `git apply --check` · `git fetch --dry-run` → 명령마다 "읽기로 치는 인자"(`_is_read`)로 고침. `fetch -n`은 `--no-tags`라 읽기 아님
- 고친 뒤 20건, 모두 막으려던 것: 다른 저장소 Edit · Write 13(11-02 Jenkinsfile 둘 · ronanlab-infra values.yaml, 11-09 런슈즈 settings.json · CLAUDE.md), commit · add · pull · fetch 7(11-09 펫퍼민트 fetch 포함)
- 이 일들은 이제 그 저장소 세션에 맡겨야 한다(왕복이 하나 는다 — 구조 답에서 말한 대로)

## 한계

- Bash의 그 밖 쓰기(`sed -i` · `>` · `cp`)는 보지 않는다 — 샌드박스 단계에서
- `cd $X` 처럼 변수 경로 cd는 따라가지 않는다. `git -C $X` 쓰기는 판정할 수 없어 막는다
- 같은 시험 DB(`foreman_test`)를 두 세션이 동시에 쓰면 서로 표를 지워 시험이 깨진다(이번에 worktree 세션 pytest와 겹쳐 31건 실패 → 혼자 돌려 통과). 남은 일 후보

## 확인

- 파이썬 523 + `tests/test_reposcope.py` 3(헛거부 사례 포함)
- 브리지 17:32:37 다시 띄움(승인 대기 0 뒤). 실제: 이 세션에서 `git -C ~/AI_programming/runshoes tag -d <없는 태그>` → PreToolUse 거부(위 사유 그대로). 같은 저장소 `git log` · `git ls-remote`는 그대로 됨
