# 역할 「점검」을 「조사」로, 조사가 결과 log를 쓰게, 역할 기준을 CLAUDE.md에 (2026-11-15, cc/foreman-6)

관리자 410의 일감(사용자 지시). 일감 중간에 사용자가 4번(역할 기본 모델을 일마다 고르는 길 확인과 CLAUDE.md 모델 한 줄)을 뺐다. `config/models.toml`은 건드리지 않았다.

## 한 일

### 1. 화면 이름 「점검」을 「조사」로

- 화면 이름표: `bridge/handoff.py` `ROLE_KO`, `bridge/foreman.py` `ROLE_KO`, `bridge/wake.py` `ROLE_KO`, `bridge/static/js/modelpick.js` `ROLE_PICK`(「조사 — 읽고 알아보기, 결과 log만 쓰기」, 앞의 ` — `는 `foremanchat.js`가 자르는 기호라 그대로), `render.js` `ROLE_LABEL`, `coder.js` 주석
- 교장 지시문(`bridge/foreman.py` INSTRUCTIONS): inspector 설명을 사용자 기준 글로(「읽고 알아본다. 고치지 않는다. 조사와 제안은 모두 여기」), 조사 줄 하나 더(결과 log는 쓰고 커밋, 고칠 것은 log에 적고 끝냄). read_only 설명과 자동 기상 힌트(WAKE_HINT)의 「read_only true」를 새 꼴로
- 코드 값 `inspector`(DB `character_session.role`, 설정 키, 테마 색 키, 함수 이름)는 그대로. 마이그레이션 없음
- 캐릭터 이름(DB `character.name`)은 `ROLE_KO`에서 온다. 이름만 바꾸면 다음 조사 세션 때 「조사」 캐릭터가 새로 생기고 「점검」 캐릭터가 남는다. 그래서 `_character_for`가 새 이름이 없으면 옛 이름(`ROLE_OLD_KO`, 「점검」 또는 「점검 <worktree>」)을 찾아 이름을 바꿔 이어 쓴다. DB 시험(`test_reassign_role_and_worktree_characters`)에 한 단계 더함
- 문서: `docs/11_foreman_dispatch.md`(새 「10-2. 역할 조사」 절, 역할 권한 표 줄, 9-2), `docs/12_scribe.md` 역할 이름 다섯 곳, `docs/10_office_design.md` 역할 고르기 칸, `docs/14_dispatcher_note_wake.md` 그림과 시험 줄, `README.md` 한 줄(489 서브에이전트 외형. 911 질문 분석 줄도 고쳤지만 main이 README 정리(445, `74e722d`)로 「나중에 할 일」 표를 없애 rebase 때 main 쪽을 따랐다), `portfolio/09_models_cost.md` 한 줄(당시 이름 표시), `docs/style_guide.md` 「4-1」 화면 말 표에 「조사 ↔ inspector」 한 줄(사람 승인 카드), `docs/11_worktree.md` 「8.」에 `whole` 한 줄
- 다른 뜻의 「점검」(화면 점검, 문서 점검 = 서기 일, 압축 손실 점검, 잃은 것 점검, 점검 페이지)은 그대로 두었다

### 2. 조사가 결과 log를 승인 없이 쓰고 커밋

- `bridge/roleguard.py`에 규칙 `inspector-write` 하나. 조사 세션(역할 inspector)만 본다
  - Edit, Write, NotebookEdit: `inspector_allow`(`log/*`) 안에서 새 파일, 이 세션이 Write로 만든 파일(브리지 메모리), git이 아직 모르는 파일(브리지가 다시 떠 메모리를 잃은 경우)만 허용. 다른 세션이 커밋한 log, log 밖은 거부
  - Bash: 저장소 파일 쓰기(리디렉션, `sed -i`, `tee`, `rm`, `mv`, `cp`와 `ln`과 `install`의 대상, `touch`, `mkdir`, `chmod` 등), `git push`, 저장소를 바꾸는 git(checkout, reset, rebase, merge, stash, worktree add, 브랜치·태그 만들기 등), log 밖 `git add`(`-A`, `-u`, `.` 포함), `git commit -a`, 경로를 준 커밋에 log 밖 경로, 스테이지(`git diff --cached`)에 log 밖 파일이 있는 커밋을 거부. `git add log/<파일>`, 스테이지가 log뿐인 `git commit`, `git restore --staged`, 읽기 git은 허용. `git -C`를 따라간다. 저장소 밖(스크래치, /tmp, 그 안에 만든 시험 저장소)은 자유
  - 거부 글: 「조사 세션은 log 파일만 쓸 수 있습니다. <무엇>. 조사는 읽고 알아보는 일이라 … 결과는 log/ 아래 새 파일에 Write로 쓰고 `git add log/<파일>` 뒤 `git commit -m`으로 커밋합니다. 고칠 것은 그 log와 보고에 적어 관리자에게 올립니다」
- **이 규칙만 막는다**: `RolesConfig.enforce`(설정 `[roles] enforce = ["inspector-write"]`)에 든 규칙은 `mode = "observe"`여도 막는다. `Hit.enforce`를 check가 채우고 `approvals.py`가 그것을 본다. 다른 네 규칙은 관찰 그대로(11-12 사용자 「켜지 마라」를 바꾸지 않음). 모르는 규칙 이름을 적으면 설정을 읽지 않고 꺼진 채 알린다(기존 방식)
- 막힌 것은 기존 거부 길로 기록된다(`_record_pre` approval_req 이벤트 rule 「역할-조사쓰기」, 브리지 로그 warning). 조용히 묻히지 않는다
- 교장 계획(`ForemanDispatcher.check`): main.py가 역할 권한을 켠 뒤 `inspector_log_only = lambda p: guard.enforces("inspector-write", p)`를 넣는다
  - 막는 프로젝트(지금 foreman만): 조사 세션의 read_only를 끈다(교장이 켜 보내도). 계획에 `log_only`
  - 막지 않는 프로젝트(런슈즈, 펫퍼민트, 인프라) 또는 역할 권한이 꺼짐: 예전처럼 읽기 전용 + 경고 「역할이 조사라 읽기 전용으로 시작합니다」
  - 자동 기상 계획(`plan["wake"]`, `_plan`이 `_origin`으로 붙임): 막는 프로젝트여도 읽기 전용. README 「자는 사이에 커밋이 쌓이면 안 된다」(사용자 결정)와 맞추려고
  - 사람이 카드에서 바꾼 값(`read_only_set`)은 그대로
- 계획 카드(`foremanchat.js`): 읽기 전용 칸 아래에 `log_only`면 「조사 세션은 읽기 전용이 아니어도 log 파일만 쓰고 커밋할 수 있습니다. 다른 파일은 브리지가 막습니다.」(첫 세션 칸, 둘째부터의 세션 칸 둘 다)
- [+ 세션] 창으로 바로 띄운 조사도 같은 규칙에 걸린다(PreToolUse가 DB 역할을 읽는다). 전에도 그 길은 plan 모드가 아니었다

### 3. CLAUDE.md 「작업 규칙」에 역할 다섯 줄

- 관리자 줄(과 그 하위 줄) 바로 아래에 「역할을 가르는 기준」 다섯 줄, 사용자 글 그대로. 관리자 줄은 그대로. 모델 줄은 사용자 지시로 넣지 않음. 사람 승인 카드로 간다

### 화면 말 시험

- `tests/data/screen_words.toml`에 rename 셋: 「점검」(`whole = true`, 문자열 전체가 「점검」일 때만 = 역할 이름표 값), 「역할이 점검」, 「점검 — 살펴보기」. 예외 하나(`ROLE_OLD_KO`)
- 「점검」 하나를 부분 맞추기로 넣으니 31곳이 걸렸고 그중 역할 뜻은 1곳뿐이었다(나머지는 화면 점검, 문서 점검, 잃은 것 점검 등). 예외 30줄은 앞으로 「문서 점검」 글을 새로 쓸 때마다 시험을 깨뜨린다. 그래서 `tests/screen_words.py`에 `whole` 칸 한 줄을 더했다

## 확인

- `.venv/bin/python -m pytest -q`: 994 통과(처음 돌렸을 때 1 실패, `_plan`에 없는 변수 `wake`를 썼다. `self._origin.get(did)`로 고친 뒤 통과)
- `node --test tests/js/`: 200 통과
- 새 시험 `tests/test_roleguard_inspector.py`: 진짜 git 저장소(임시)로 Edit 허용과 거부, Bash 허용 19가지, 거부 28가지, 스테이지 검사 커밋, 다른 역할과 관찰 모드, 실제 `config/roles.toml` 모양, 모르는 enforce 이름, `ApprovalManager.pre_tool_use`가 관찰 모드에서도 조사를 거부하고 기록에 남기는지
- `tests/test_foreman_multi.py`: 막는 프로젝트면 read_only 끔, 사람이 켠 값 유지, 자동 기상은 읽기 전용
- 실제 조사 세션은 띄우지 않았다. 도는 브리지는 원본 폴더 코드라 이 브랜치의 판정이 실린 브리지가 없다(worktree는 브리지를 다시 띄우지 않는다). 대신 가짜 PreToolUse 입력으로 확인했다. **합친 뒤 브리지를 다시 띄운 다음 조사 세션 하나로 log 쓰기와 커밋 허용, 그리고 다른 파일 Edit 거부를 실제로 보면 좋다**(띄운 세션은 `hidden_reason='test'`)

## 설계와 달랐던 점, 판단 근거

- 브리프는 「그 세션이 만든 log 파일」을 허용하라고 했다. 브리지 메모리로 기억하되, 브리지가 다시 뜨면 잃으므로 「git이 아직 모르는 파일」도 허용했다. 커밋한 뒤 다시 고치려면 새 파일에 써야 한다(커밋된 log는 다른 세션 것과 가를 수 없다)
- `git restore --staged`는 허용했다(스테이지에서 내리기만 하고 작업 트리는 그대로). 스테이지에 남이 올린 파일이 있을 때 스스로 풀 길이 있어야 해서
- 자동 기상 계획의 조사는 읽기 전용을 남겼다. 브리프에는 없지만 README의 사용자 결정(「자는 사이에 커밋이 쌓이면 안 된다」)과 부딪치지 않게
- 캐릭터 이름은 마이그레이션 없이 쓸 때 바꾼다. 그래서 **조사 세션이 다시 뜨기 전까지는 각 프로젝트의 쉬는 「점검」 캐릭터가 화면에 옛 이름으로 남을 수 있다**. 바로 바꾸려면 데이터 마이그레이션 한 줄(`UPDATE character SET name = REPLACE(name, '점검', '조사') WHERE current_role = 'inspector' AND (name = '점검' OR name LIKE '점검 %')`)이 필요하다. 스키마 잠금과 「마이그레이션 없이」 지시 때문에 하지 않았다. 필요하면 관리자가 정한다

## 남은 것, 겹칠 수 있는 것

- 445(README 정리)와 README 두 줄, 443(포스트잇)과 CLAUDE.md가 겹칠 수 있다(내 자리는 관리자 줄 아래, 443은 포스트잇 규칙 한 줄). 나중에 합치는 쪽이 rebase
- 못 막는 것: 해석기 안 쓰기(`python -c "open(…,'w')"`), `cd $X` 뒤 폴더를 모르는 명령. 다른 역할 규칙과 같은 한계

## 규칙 위반

- 지시서의 「새 글에 em dash와 가운뎃점을 쓰지 않는다」: 처음 쓴 docs 10-2 절, `config/roles.toml` 주석 두 줄, 교장 지시문 새 줄 둘에 가운뎃점과 em dash를 썼다(11-15 작업 중). 커밋 전에 diff를 세다 알아채고 쉼표와 마침표로 고쳤다. 화면 거부 글의 em dash도 같은 때 뺐다. **코드 주석과 docstring의 새 줄에는 그대로 남겼다**(이 저장소 코드 주석의 꼴을 따랐다, 「코드와 문서 자체 문장은 그대로」 style_guide 4-1). 기존 문장에서 낱말만 바꾼 줄도 그대로다
- 그 밖에 규칙 위반 없음(파일은 Edit, Write로만 고침, `pgrep -f` 안 씀, push와 브리지 다시 띄우기 안 함). 한 번 쓸모없는 명령(`git show … > "$TMPDIR/x"`, TMPDIR이 비어 `/x`에 쓰려다 권한 거부로 실패)을 쳤다. 저장소 파일을 건드리지 않았다
