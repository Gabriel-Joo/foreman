# 조사 B: 묻지 않고 통과하는 삭제 (foreman-6, 2026-11-15)

관리자 410의 조사 일감. 훅 · 판정 코드는 고치지 않았다. 재현은 판정 함수(`load_policy(원본 config/approval.toml).decide(...)`)에 명령 글만 넣는 방식으로 했고, 아무것도 지우지 않았다. 재현 스크립트는 세션 스크래치패드(`repro.py`, `replay_b.py`)에 두었다.

## PreToolUse 훅이 명령을 보는 꼴

1. CC → `scripts/foreman-decide.sh pre` → 브리지 `/hooks/pre` → `bridge/approvals.py` `pre_tool_use`. 역할 · 스키마 잠금 · 다른 저장소 · pgrep 거부를 먼저 보고, 그다음 `Policy.decide(도구, 입력, cwd, scratchpad, 프로젝트)`(`bridge/approval.py`)
2. 훅이 받는 것은 **명령 글 한 덩어리와 cwd뿐**이다. 실행 시점의 변수 값, 명령 치환 결과, 파일 내용(아래 스크립트 하나만 예외)은 모른다
3. Bash 판정 차례(`_bash`)
   - 파일에 쓰기만 하는 heredoc(`cat > f`, `tee f`, 커밋 본문)은 본문을 지운다
   - `_neutralize`로 검색어, 메시지 같은 실행되지 않는 글자를 지운다. 해석기(python 등) heredoc 본문도 지운다(`scan_interpreter_heredocs = false`)
   - **ask 정규식**(`[ask.bash]` 열 개)을 남은 글 전체에 돌린다. heredoc 본문도 여기서는 보인다
   - `_segments`로 조각을 나눈다. **이때 모든 heredoc 본문을 뺀다**(`HEREDOC.sub(... line + "<<" + tag)`)
   - 조각마다 `_segments_ask`: 보호 파일 쓰기, `bash -c` 안쪽 다시 판정, **스크립트 실행이면 파일을 읽어 ask 정규식만 돌림**, `rm`이면 `_protected_delete`(통째로-삭제)
4. 「통째로-삭제」는 정규식이 아니라 조각 판정(`delete_whole`)이다. 그래서 조각으로 보이는 곳(최상위 명령, `bash -c '…'` 안쪽)에서만 돈다

## 네 경우: 모두 통과(재현)

| 경우 | 재현한 명령(cwd) | 판정 | 왜 안 걸리나 |
|---|---|---|---|
| heredoc 안 `rm -rf` | `bash <<'EOF'` / `sh <<EOF` / `bash -s <<'EOF'` / `ssh host bash <<'EOF'` 본문 `rm -rf ~/AI_programming/runshoes` | pass ×4 | 본문은 ask 정규식에는 보이지만 `rm`은 정규식 목록에 없다. 통째로-삭제를 보는 조각 판정은 `_segments`가 heredoc 본문을 뺀 뒤에 돈다 |
| 같은 쪽, 해석기 | `python3 - <<'EOF'` `shutil.rmtree(...)` / `os.system('rm -rf …')` | pass ×2 | 해석기 본문은 11-05 결정으로 아예 보지 않는다(`scan_interpreter_heredocs = false`) |
| `.sh` 안 `rm -rf` | `bash whole.sh`, `/경로/whole.sh`, `source whole.sh`(본문 `rm -rf ~/AI_programming/runshoes`) | pass ×3 | `_segments_ask`가 스크립트 본문에 `_ask_patterns`(정규식)만 돌리고 조각 판정은 하지 않는다. 대조군 `git push --force`가 든 스크립트는 ask |
| 같은 쪽, 즉석 스크립트 | `cat > new.sh <<'EOF' … EOF` 다음 줄 `bash new.sh` | pass | 판정 순간 파일이 없어 `_read_script`가 None. `.sh`로 쓰는 heredoc 본문은 남기지만 역시 정규식만 본다 |
| `rm -rf "$(pwd)"` | cwd = `~/AI_programming/runshoes`에서 `"$(pwd)"`, `` `pwd` ``, `"$PWD"`, `"$(git rev-parse --show-toplevel)"`, `d=$(pwd) && rm -rf "$d"`, `"$(dirname "$PWD")"` | pass ×6 | `_protected_delete`가 `$` 앞 고정 부분(prefix)이 비면 None을 돌려준다. 「비면 /」 검사는 `$(`면 건너뛰고, `$PWD`는 비우면 빈 글이라 `/`로 시작하지 않는다. `_literal_env`는 글자 그대로 정한 값만 푼다. 대조군 `rm -rf .`, `rm -rf "$HOME"`은 ask |
| 작업방 `config/approval.toml` 편집 | Edit `…/.worktrees/foreman-6/config/approval.toml`, Write `…/scripts/foreman-decide.sh`, cwd 작업방에서 `sed -i … config/approval.toml` | allow(편집) ×2, pass(unmatched) | `protect` 정규식이 `(^\|/)AI_programming/foreman/config/(approval\|notify)\.toml$`로 원본 경로만 맞는다. 작업방 경로는 `foreman/.worktrees/<이름>/config/…`라 안 맞아 「규칙파일-편집」(🛡 알림)이 아니라 평범한 편집이 된다. 원본 경로 Edit은 allow + 🛡, 원본 `sed -i`는 pass + 🛡 |

넷 밖에서 같이 확인한 것(같은 까닭으로 통과): `find ~/AI_programming/runshoes -delete`, `echo … | xargs rm -rf`, `mv ~/AI_programming/runshoes /tmp/x` 모두 pass. 통째로-삭제는 `rm`이라는 동사에만 붙어 있다.

### 「통과」가 뜻하는 것

여기서 통과는 **브리지가 묻지 않는다(pass)** 는 뜻이다. pass면 CC 자동 모드 분류기가 정한다. 분류기가 이것들을 막는지는 **확인하지 않았다** — 프로젝트 폴더를 지우는 명령을 실제로 내야 해서 브리프의 안전 기준(빈 임시 폴더 안만)으로는 재현할 수 없다. 임시 폴더 안 대상으로는 통째로-삭제 규칙 자체가 걸리지 않으므로 실제 실행 재현은 보호 경로 우회를 보여 주지 못한다. 그래서 판정 함수 재현만 했다.

작업방 편집의 위험은 편집 순간이 아니다. 도는 브리지는 원본 폴더의 설정을 읽으므로 작업방 편집은 그 자리에서는 효과가 없다. 효과가 나는 때는 **합칠 때**인데, 합치기(`POST /api/sessions/{sid}/worktree`, git merge)는 Edit 도구를 거치지 않아 🛡 알림이 없고, `bridge/worktree.py` · `bridge/mergeprep.py`에도 규칙 파일 변경을 보는 곳이 없다(grep으로 확인). 그 뒤 브리지를 다시 띄우면 바뀐 규칙이 조용히 살아난다.

곁에서 본 것(일감 밖, 고치지 않음): 판정 코드 자체(`bridge/approval.py`, `bridge/approvals.py`, `bridge/roleguard.py`)와 `deploy/hooks/foreman-hooks.json`은 원본 경로여도 `protect`에 없어 평범한 편집(allow)이다.

## 막는 자리 안과 평소 작업 영향

지난 21일(실제 기록 17일) 도구 호출 50,597개, Bash 27,677개에 후보 검사를 흉내 내 돌렸다(`replay_b.py`, DB 읽기만). 「새로 묻게 되는 수」는 지금 이미 ask인 것을 뺀 수다.

| 안 | 자리 | 새로 묻는 수(17일) | 막는 것 |
|---|---|---|---|
| A1 셸 heredoc 본문을 `bash -c` 안쪽처럼 다시 판정(받는 쪽이 bash · sh · zsh · ssh) | `_segments_ask`: heredoc을 받는 조각이면 그 본문으로 `self._bash(body, here, …, depth+1)` | **0** (셸 heredoc 명령 47개 중 본문에 `rm`이 든 것 0) | heredoc 안 통째로-삭제 |
| A1s 실행 스크립트 본문도 정규식만이 아니라 `_bash`로 다시 판정 | `_segments_ask` 스크립트 분기(지금 `_ask_patterns(body)` 자리) | **0** | `.sh` 안 통째로-삭제 |
| A2 넓게: heredoc · 스크립트 안의 `rm -r` 아무거나 ask | 같은 자리 | heredoc 0, 스크립트 **9**(전부 런슈즈 `contract/run-spring-local.sh` 계약 시험) | 위와 같고 넓다 |
| B1 `$(pwd)`, `` `pwd` ``, `$PWD`, `$(git rev-parse --show-toplevel)`을 cwd · 저장소 뿌리로 풀어 통째로-삭제 판정 | `_protected_delete`의 `$` 분기 앞 | **0** (`${PWD:?}/tmp.X` 꼴 3건은 풀어도 통째로가 아니라 안 걸림) | `rm -rf "$(pwd)"` 꼴 |
| B2 넓게: `rm` 대상이 명령 치환으로 시작(고정 부분 없음)이면 ask | 같은 자리, `if not prefix: return None` 대신 | **1**(파이썬 heredoc 안 글자, 실제 삭제 아님. 해석기 본문을 빼고 보면 0으로 줄 것으로 본다, 미검증) | `$(dirname "$PWD")` 등 임의 치환 |
| C 해석기 본문에서 `shutil.rmtree('글자')`, `os.system('rm …')`의 글자 경로만 통째로 판정 | `_bash`의 해석기 본문 지우기 전 | **0**(넓게 rmtree · rm 아무거나도 0) | 글자 경로만. 변수 경로는 못 잡는다 |
| D1 `protect` · `protect_tool_edit_ok`에 작업방 꼴 추가 `AI_programming/foreman/(\.worktrees/[^/]+/)?config/…`, `scripts/foreman-…` | `config/approval.toml`(정규식만) | 묻는 것 0. 🛡 알림 **9**건(10분 묶음이라 실제로 더 적음) | 작업방 편집을 알림으로 보임 |
| D2 합칠 때 규칙 · 게이트 파일이 바뀌었으면 🛡 알림 · 합치기 결과에 표시 | `bridge/worktree.py` 합치기 경로(`git diff --name-only` 결과를 `protect`에 대조) | 묻는 것 0 | 실제로 효과가 나는 순간을 잡는다 |
| E 실행 순간에 막기: CC 샌드박스 파일 쓰기 거부 또는 `rm` 래퍼로 `~/AI_programming/*` 등 뿌리를 막음 | 훅 밖(CC 설정 · OS) | 재지 않음 | 위 모두 + `find -delete` · `xargs rm` · 계산된 경로. 일상 명령을 깨뜨릴 위험이 가장 크고 시험 전이다(`config/approval.toml` `[repo_scope]` 주석에도 「샌드박스는 일상 명령을 시험한 뒤」) |

### 추천

- **A1 + A1s + B1 + B2(해석기 본문 뺀 뒤) + D1 + D2.** A1 · A1s는 이미 있는 `bash -c` 안쪽 다시 판정을 heredoc · 스크립트 본문에 그대로 쓰는 것이라 새 규칙이 아니고, 지난 17일 새 ask 0이다. B는 B1만으로 브리프의 꼴은 막히고 B2를 더해도 ask가 사실상 늘지 않는다. D는 묻지 않고 알림만이라 흐름을 끊지 않으며, 효과가 나는 자리인 합치기(D2)가 핵심이다
- **A2(넓게)는 권하지 않는다** — 런슈즈 계약 시험이 매번 묻게 된다(17일 9번, 실제 거부할 만한 것 0)
- **C는 하더라도 글자 경로만** 잡힌다는 것을 알고 넣는다. 해석기 본문을 다시 넓게 보면 11-05에 빼 둔 「승인 정책을 시험하는 코드의 문자열」 오탐(9번 다 Yes)이 돌아온다
- 훅은 글만 보므로 `find -delete`, `xargs rm`, 실행 시점에 정해지는 경로는 어느 안으로도 다 막히지 않는다. 다 막아야 하면 E(실행 순간)뿐이고, 그건 별도 시험이 필요하다

### 과하게 막을 위험(어림)

- 추천안 묶음의 새 승인 창: 지난 17일 **0~1번**(B2가 해석기 본문까지 보면 1번). 지금 FOREMAN 하루 승인 창 1.3번(README 3.3)에 거의 더하지 않는다
- 새 🛡 알림: 17일 9건 이하(작업방 규칙 파일 편집). 10분 묶음이라 더 적다
- 남은 위험: A1s가 스크립트 본문에 `_bash` 전체를 돌리면 정규식 말고 다른 조각 규칙(보호 파일 쓰기 알림 등)도 스크립트에서 돌기 시작한다. 이번 셈은 통째로-삭제만 셌으므로, 넣을 때는 `scripts/approval-replay.py`로 전체 판정을 다시 돌려 봐야 한다(미검증)
- 실행 스크립트를 판정 순간 못 읽는 경우가 17일 271건이었다(대부분 `. ./.env`처럼 경로 해석이 엇갈리거나 지워진 스크래치 파일). 이 경우는 어느 안이든 그대로 통과한다 — 「같은 명령에서 `.sh`를 쓰고 바로 실행」은 2건

## 확인 체크리스트

- [x] 네 경우 각각 실제로 통과하는지 확인 — 판정 함수에 명령 글을 넣어 넷 모두(변형 포함 16꼴) pass 또는 알림 없는 allow를 확인했다. 대조군(직접 `rm -rf` 프로젝트, `bash -c` 안쪽, `rm -rf .`, `"$HOME"`, 스크립트 안 `push --force`, 원본 경로 Edit)은 예상대로 ask · 🛡. 실제 삭제 실행 재현은 하지 않았다(위 「통과가 뜻하는 것」) — 그래서 CC 자동 모드 분류기가 막는지는 모른다
- [x] 막는 안이 기존 작업을 깨지 않는지 검토 — 지난 17일 기록에 흉내 내 돌려 위 표의 수를 얻었다. 후보 검사는 스크래치 스크립트 안의 흉내라 실제 구현과 다를 수 있다
- [x] 훅 코드를 고치지 않았다 — 바꾼 파일은 이 log 하나다

## 규칙 위반

규칙 위반 없음.
