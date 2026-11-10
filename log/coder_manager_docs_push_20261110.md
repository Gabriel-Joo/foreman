# 관리자 세션의 docs 전용 push 허용 (코더, 2026-11-10)

관리자 세션 244 요청(사용자 11-10 지시). 브랜치 `cc/foreman`, 커밋만.

## 한 일

- `bridge/reposcope.py` — 예외 2 `[repo_scope.manager_push]`: 관리자 세션이 적힌 저장소 원본에서 `git push`를 하면
  push 모양 · 원격 머리 · 앞선 커밋을 보고 허용 또는 거부. 리디렉션 빼기는 `_strip_redir`로 꺼내 add · commit과 같이 쓴다
- `bridge/approvals.py` — `session_role(p)`(비동기): 판정이 역할을 쓸 때(`wants_role` — Bash에 `push`가 보일 때)만
  DB `character_session`(그 cc_session_id의 마지막 행)의 `role`을 읽는다. `worktree_path`가 있으면 None. `pre_tool_use(p, role=)`
- `bridge/api/hooks.py` — `/hooks/pre`가 역할을 읽어 넘긴다(push가 아니면 DB를 읽지 않는다)
- `config/approval.toml` — `[repo_scope.manager_push] foreman = ["runshoes/docs/", "petmint-rag-chatbot/docs/"]`
  (`[repo_scope.writable]`과 같은 "<프로젝트>/<경로>/" 모양, 키는 세션 프로젝트)
- `tests/test_reposcope.py` 6개 더함(실제 `git init` + 로컬 bare 원격). 전체 569 통과 · 1 건너뜀

## 관리자 가르는 법

셋 다 맞아야 한다:
1. 세션 프로젝트가 `[repo_scope.manager_push]`의 키(foreman)
2. DB 역할 `manager`, 그 행의 `worktree_path`가 비어 있음
3. 훅의 cwd가 그 프로젝트 원본 폴더 안(`_top(realpath(cwd)) == realpath(repo_path)` — `.worktrees/x`는 자기 `.git`이 있어 다르다)

대상 저장소는 DB `project.repo_path`(realpath)와 같은 맨 위 폴더만 — 그 저장소의 worktree · 비슷한 이름은 아니다.

## 허용 모양

`git -C <저장소> push [origin] [main]` 또는 `cd <저장소> && git push …`. 옵션은 `-q` · `-v`만. 리디렉션(`2>&1`)은 괜찮다.
- 브랜치를 안 적으면: 지금 브랜치가 main, `push.default`가 matching이 아님, 원격도 안 적으면 `@{push}`가 origin/main
- 원격 머리: `git ls-remote origin refs/heads/main`(10초, `GIT_TERMINAL_PROMPT=0`)
- 로컬이 원격 머리를 갖고 있고 그 자손, `rev-list <원격>..main`에 머지 커밋 없음, 각 커밋의 `diff-tree --name-only -r`이 전부 `docs/` 아래
- 앞선 커밋 0개면 통과(push할 것 없음)

## 거부 경우(거부 글)

| 경우 | 글 |
|---|---|
| docs 밖 하나라도 | 「앞선 커밋 N개 중 docs/ 밖을 건드린 것이 있어 막았습니다: <커밋 8자> <파일>, …」(5개까지 + 「외 N개」) |
| 뒤처짐(원격 머리 없음) · 갈라짐 · 머지 커밋 | 각각 까닭을 적는다 |
| 원격 못 읽음 | 「원격(origin)의 main을 읽지 못해 막았습니다(네트워크 · 인증 · 10초 넘김)…」 |
| `--force` · `-f` · `--force-with-lease` · `--delete` · `--mirror` · `--tags` · `--all` · `-u` | 「…는 쓸 수 없습니다…」 |
| `+main` · `main:main` · `HEAD` · 다른 브랜치 · 다른 원격 | 「…다른 원격 · 브랜치 · refspec 막음」 |
| `remote.origin.mirror` · `remote.origin.push` 설정 | 설정 이름을 적어 거부 |
| 관리자가 아님(coder · 서기 · 역할 못 읽음) · worktree 관리자 · 적히지 않은 저장소 | 기존 「다른 저장소 쓰기 막힘 … 읽기만 합니다(git push)」 |

인프라 세션(265)의 push 막음은 그대로(`[repo_scope.writable]` 쪽은 손대지 않았다).

## 판단 근거 · 설계와 달랐던 점

- PreToolUse는 동기 함수라 역할을 그 안에서 DB로 읽을 수 없다 → 훅 라우트(비동기)가 push일 때만 읽어 넘긴다. 역할을 메모리에 캐시하지 않은 것은
  역할 API로 바뀐 값을 바로 따르기 위해서다
- `ls-remote`는 판정 안에서 동기로 돈다(최대 10초 동안 브리지 이벤트 루프가 멈출 수 있다). 관리자가 그 두 저장소에 push할 때만이라 받아들였다.
  실제 GitHub 원격으로 판정 전체가 약 2초였다
- 앞선 커밋은 로컬 `origin/main` 추적 브랜치가 아니라 `ls-remote`로 읽은 실제 원격 머리 기준이다(fetch 안 한 상태에서도 맞게)

## 실제 경로로 확인(push는 하지 않음)

실제 `config/approval.toml` + 원본 폴더 경로로 `check`만 불렀다: runshoes · petmint 모두 관리자 `push origin main` · `cd 뒤 push` 허용
(지금 앞선 커밋 0개), `--force` 거부, 코더 · worktree 관리자 거부. 세션 244는 캐릭터 「관리자」, cwd 원본 폴더.

## 합친 뒤 관리자가 할 일

1. 합친 뒤 `pytest` 확인
2. 승인 대기가 없는지 보고 브리지(tmux `foreman-bridge`) 다시 띄우기 — reposcope · approvals · hooks · approval.toml이 바뀌었다
3. 확인: 인프라 세션의 docs 커밋이 있을 때 `git -C ~/AI_programming/runshoes push origin main`(관리자 세션에서).
   먼저 `git -C ~/AI_programming/runshoes log --stat origin/main..main`으로 내용을 본다. 막히면 거부 글이 까닭(파일 이름)을 말한다
4. 세션 244의 DB 역할이 `manager`가 아니면(캐릭터만 관리자인 경우) 패널 역할 바꾸기로 manager로 둔다 — 아니면 기존 「읽기만」 글로 막힌다
