# 서기 두 길 합치기, 서기 동시 상한 없애기 (FOREMAN, 2026-11-15)

관리자 410의 일감(사용자 지시, 서기 구조 다시 짜기 6번). 바탕 설계는 `log/foreman-7_scribe_design_20261115.md` 6-2 안 1. 브랜치 `cc/foreman-4`, 커밋만 했다(push, 브리지 다시 띄우기 안 함). 마이그레이션 없음(`dispatch.origin`은 VARCHAR(10)이라 `scribe`가 들어간다).

## 한 일

- **일 종류 기록을 한 곳으로**: `HandoffManager.spawn_new`에 `scribe_task`를 더했다. 세션 행이 생기는 `_finish_spawn`에서 역할 scribe면 `session_action scribe-task`를 남긴다(신뢰 창을 기다리는 길도 같은 곳을 지난다). 없으면 옮기기는 옛 세션의 일을 잇고, 아니면 `plan`
  - 서기실 [시키기](`scribe_room.start`)는 스스로 `_act`를 부르지 않고 `scribe_task`를 넘긴다
  - 계획 [시작]은 세션 칸 `task`를 넘긴다. `sessions_of`가 `task`를 받고(꼴 `[a-z][a-z0-9_-]{0,19}`, 아니면 버림), 교장 지시문에 `task` 한 줄을 더했다. 계획 카드는 세션 칸을 펼쳐 담아 보내므로 `task`가 남는다(화면에 칸은 없다)
  - `POST /api/spawn`이 `task`를 받는다(역할 scribe일 때만 넘김)
- **맡을 파일 기록도 같은 곳에**: 서기실 [시키기]가 `record_spawn`으로 `dispatch`(origin `scribe`)와 `dispatch_session`(맡을 파일 = 그 일의 `TOUCHES`)을 남긴다(`scribe_room._record`). 실패해도 띄우기는 되돌리지 않는다
- **「열려 있다」 한 판단**: `foreman.py`에 `UNMERGED_SQL`(합치기, 버리기 기록 없음)과 `still_open`(worktree는 폴더가 남아 있는 동안, 원본 폴더 세션은 끝나기 전)을 두고 두 곳이 같이 쓴다
  - `scribe_room.open_tasks`: 역할 scribe이고 `scribe-task` 또는 `dispatch_session started`가 있는 세션. 일 종류는 `scribe-task`, 없으면 `plan`. 맡을 파일은 `dispatch_session.files`, 없으면 `TOUCHES`
  - `foreman.file_conflicts`: 「살아 있는 세션(14일)」에 「합치지 않은 worktree(날짜 없음)」를 더하고, `open_tasks`의 서기 세션(11-15 전 서기실 것처럼 dispatch 기록이 없는 것)도 넣는다. 겹침 글은 「살아 있는 세션 N」, 「합치지 않은 세션 N」, 「열려 있는 서기 세션 N」으로 가른다
- **겹침 판단 한 벌**: `TOUCHES`를 `files_overlap` 꼴(목록, 폴더 `/`, 글롭 `*`)로 바꿨다(`log/doccheck_*`, 포트폴리오 `portfolio/<slug>*`). `blocked`가 집합 교집합 대신 `files_overlap`을 쓴다. 그래서 `docs/`를 고치는 일과 `docs/operations.md`를 맡은 계획 서기가 서로 걸린다. `plan`끼리는 같은 일로 보지 않고 맡을 파일로만 본다. 막힘 글의 이름은 서기실 일이면 일 이름, `plan`이면 세션 이름
- **동시 상한을 뺐다**: `MAX_OPEN = 2`와 `blocked`의 「서기 일이 이미 N개 열려 있습니다(동시에 N개까지)」 거절, 주석의 「프로젝트당 둘 넘게」 「둘까지인 이유」, 화면 `scribe.js` 「열려 있는 일」 글의 「동시에 2개까지」. 같은 일, 같은 파일 막기는 남겼다(상한이 아니라 겹침이다)
- 화면: 「열려 있는 일」 글을 「합치거나 버리기 전까지(같은 일, 같은 파일을 고치는 일은 하나씩. 계획으로 띄운 서기 세션도 셉니다)」로, `plan` 세션은 세션 이름으로 보인다. `tests/data/screen_words.toml`에 「동시에 2개까지」 rename 한 줄
- 시험: `tests/test_scribe_room.py`(상한 시험을 「상한 없음」으로, 계획 서기를 맡을 파일로 막기), 새 `tests/test_scribe_two_paths.py`(기록 한 곳, 계획 [시작]이 task를 넘김, DB 셋: 계획 길 서기가 서기실 열린 일과 막기에 잡힘 / 서기실 서기가 계획 겹침에 잡힘 / 다섯 개 열어도 안 막힘)
- docs: `docs/12_scribe.md` 1절 끝 「띄우는 길은 셋, 기록은 하나」, 2절 「동시에 시키기」. `docs/11_foreman_dispatch.md` 11절 맡을 파일 겹침 아래 두 줄과 「서기 일 종류」

## 숫자 전과 뒤(운영 DB, SELECT만, 11-15)

| 프로젝트 | 열린 서기 일 전(scribe-task만, 합치기 전) | 뒤(새 `open_tasks`) | 서기실이 몰랐던 계획 길 서기(전체) |
|---|---|---|---|
| foreman | 0 | 0 | 15 |
| petmint-rag-chatbot | 1 (260 doccheck) | 0 | 1 |
| runshoes | 0 | 0 | 0 |
| ronanlab-infra | 0 | 0 | 0 |

- 펫퍼민트 260은 11-10에 띄운 문서 점검이다. worktree 폴더(`petmint-rag-chatbot/.worktrees/petmint-rag-chatbot`)가 없는데 합치기 기록이 없어 닷새째 「열려 있음」이었고, 그동안 펫퍼민트 「문서 점검」을 조용히 막고 있었다. 새 판단에서 닫힌다
- 439가 열려 있다고 본 437은 그 뒤 합쳐져 지금은 0이다
- 계획 겹침 쪽: 14일 안 started인데 합치기 기록이 없는 worktree 세션은 코더 5개(296, 311, 441, 442, 443). 296, 311은 끝났고 폴더(foreman-2, foreman)도 없어 새 판단에서 빠진다. 441~443은 지금 살아 있는 세션이라 전에도 잡혔다. 그래서 넓혀서 늘어나는 겹침 글은 지금은 0이다

## 확인

- `.venv/bin/python -m pytest -q` 985 통과(DB 시험 포함), `node --test tests/js/` 200 통과
- 화면 말 시험: 서기 몫 0줄

## 판단 근거

- 기록을 `_finish_spawn`에 둔 까닭: `spawn_new`는 신뢰 창이 뜨면 세션 행 없이 돌아오고 뒷일을 `_finish_spawn`이 한다. 세션 id가 생기는 곳이 여기 하나라 세 길과 신뢰 창 길이 모두 지난다
- 맡을 파일 기록은 `spawn_new` 안에 넣지 않았다. 계획 [시작]은 계획 번호에 세션 여럿을 한 줄씩(`save_sessions`), 직접 띄우기는 실패도 기록(`record_direct`)하는 등 길마다 다르다. 넣으면 계획 길이 두 번 적는다. 대신 서기실만 빠져 있던 것을 `record_spawn`으로 채워 셋이 같은 표에 있게 했다
- 계획 겹침의 「열려 있다」를 서기만이 아니라 모든 worktree 세션에 넓혔다: 사용자 정의(합치거나 버리기 전)가 역할을 가르지 않고, 합치지 않은 worktree끼리 같은 파일이면 뒤의 합치기가 실제로 충돌한다. 439가 걱정한 코더 겹침 글 늘어남은 폴더 확인으로 유령을 빼서 지금 숫자 0
- 폴더 확인을 넣은 까닭: 「합치기 기록 없음」만 보면 손으로 지운 worktree가 영영 열린다(260, 296, 311이 실제로 그랬다). 조용한 고장을 하나 더 만드는 셈이다
- 같은 일, 같은 파일 막기는 남겼다. 사용자 말이 「상한」이었고 이 둘은 개수가 아니라 겹침이다. 겹침 막기도 빼야 하는지 판단이 서지 않아 남겼다(정할 것 아래)

## 남은 것, 정할 것

- 「나중에 할 일 정리」 기준점(`later_since`, `LATER_ACT`)과 「바로 고치기」를 합친 결과(`fixed_reports`)는 서기실 길에서만 쌓인다. 계획 길로 `task: later`를 띄우면 열린 일과 막기에는 잡히지만 기준점은 옮겨 가지 않는다. later, inbox 둘레는 같은 시각 포스트잇 코더 몫이라 건드리지 않았다
- 계획 카드에 `task` 칸은 없다. 교장이 넣은 값이 그대로 가고, 사람이 고칠 수는 없다
- 서기실 [시키기]는 띄운 뒤 계획 겹침(코더 쪽 맡을 파일)을 보이지 않는다. 서기끼리는 `blocked`가 막는다
- 정할 것: 같은 일, 같은 파일 막기도 뺄지(지금은 남김)

## 서기 몫(CLAUDE.md, operations, style_guide)

- 상한(`MAX_OPEN`, 「둘까지」, 「동시에 2개」)은 세 파일 어디에도 없었다. 고칠 것 없음
- `docs/operations.md` 111줄 「`record_spawn`은 띄워진 새 세션만 적는다」는 그대로 맞다. `dispatch.origin` 값에 `scribe`가 늘었는데 세 파일에 origin 값 목록은 없다

## 규칙 위반

규칙 위반 없음. 스크래치 스크립트(SELECT만)는 Write로 쓰고 돌렸다. 처음 한 번은 스크래치 폴더에서 돌려 원본 폴더의 `bridge`를 읽었다(`KeyError`, 쓰기 없음). `PYTHONPATH`를 작업 폴더로 두고 다시 셌다.
