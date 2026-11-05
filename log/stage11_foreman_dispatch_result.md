# 11단계 — 포먼 디스패처 1단계(부를 때만) 결과 (2026-11-05)

설계: `docs/11_foreman_dispatch.md`. 이번에 만든 것은 1단계(사람이 [+ 세션]에서 부를 때만)까지다. 자동 기상 2 · 3단계는 1단계를 써 본 뒤 정한다.

## 한 일

- `bridge/foreman.py` — `ForemanDispatcher`
  - `context(request)`: LLM 없이 상황 묶음을 만든다. 파일은 mtime 캐시로 바뀌었을 때만 다시 읽는다.
    - 요청에 이름이 나온 프로젝트만 자세히 넣는다: CLAUDE.md, MEMORY.md, docs 목록, 압축 손실 점검 파일, 세션(살아 있거나 48시간 안), 최근 인계 요약 머리, 파이프라인
    - 세션마다 최근 사람 요청 3개와 각 답의 첫머리도 넣는다
  - `plan()`: `claude -p --model sonnet`으로 계획을 받는다.
    - 읽기 도구만 쓰고 hook을 끄며, 세션 기록을 남기지 않는다
    - 프롬프트는 stdin으로 보낸다
  - `check()`: 계획을 사실과 맞춘다.
    - 없는 프로젝트를 고르면 ask로 바꾼다
    - 다른 프로젝트의 요약은 비운다
    - 끝났거나 tmux 밖인 세션에 붙이려 하면 new 또는 handoff로 바꾼다
    - 바꾼 것마다 경고를 붙인다
  - `start()`: 방식에 따라 시작한다.
    - attach는 `deliver`로 보낸다
    - 그 밖에는 `handoff.spawn_new`로 띄운다(첫 글, 읽기 전용, 역할)
- `bridge/handoff.py` `spawn_new` / `_finish_spawn` 확장
  - `first_prompt`가 있으면 첫 글로 넣고, 인계 요약을 고른 경우 그 뒤에 붙인다
  - `read_only`면 `claude --permission-mode plan`으로 띄운다
  - `role`을 세션 행에 적는다
- API `bridge/api/foreman.py`
  - `POST /api/foreman/plan`
  - `POST /api/foreman/start`
  - `GET /api/foreman/context`: 무엇을 보고 판단했는지 확인하는 용도
- `migrations/0016_foreman_dispatch.sql`: `dispatch` 표
  - 요청, 포먼의 계획, 사람이 고친 계획, 결과를 남긴다
  - 포먼이 자주 틀리는 유형을 찾는 데 쓴다
- 화면 `bridge/static/js/foremanchat.js`(office.html에서 실음)
  - [+ 세션] 창 맨 위에 "포먼에게 말하기"를 둔다
  - [계획 받기]를 누르면 고칠 수 있는 계획 카드가 나온다
    - 칸: 프로젝트, 방식, 인계 요약, 보낼 세션, 역할, 이름, 읽기 전용, 첫 글
    - 판단 근거와 확신도를 함께 보여 준다. 확신도가 0.7보다 낮으면 근거를 펼쳐 둔다
  - 카드 아래 [이대로 시작] / [다시 물어보기]
  - 원래 창은 "직접 고르기"로 접어 둔다. [띄우기]는 그것을 펼쳤을 때만 보인다
  - newsession.js는 고치지 않고 창이 생기면 위에 붙인다
- 시험 `tests/test_foreman.py`: `parse_plan`, docs 목록, 캐시

## 확인

- "런슈즈 발볼 검증 이어서"
  - 1차(상황 6.2k자, 20초): new를 골랐다. 세션 156이 이미 같은 일을 하는 줄 몰랐다
  - 세션별 최근 요청과 답 첫머리를 넣은 뒤(11.4k자, 19초): attach 156, 확신도 0.85
    - 타이머 33ddc2c4와 남은 43켤레를 근거로 들었다
    - 메모리와 압축 손실 목록에서 지켜야 할 것을 첫 글에 옮겼다
  - 런슈즈 세션에는 실제로 보내지 않았다
- 시작 경로는 무해한 시험으로 확인했다
  - 요청: "포먼 저장소에서 읽기 전용으로 README 첫 줄만 확인"
  - 포먼의 판단: foreman, new, 읽기 전용
  - 세션 178이 tmux `cc-foreman-3`에 plan 모드로 떴고, 첫 글을 넣었다(제출 확인됨)
  - 세션이 바르게 답했다. 그 뒤 끝내기로 정리했다(tmux 닫힘)
- 화면: 헤드리스 캡처로 계획 카드와 접힌 "직접 고르기"를 봤다
- 시험: Python 364, JS 31 통과

## 설계와 달랐던 점 · 판단 근거

- `--add-dir` 뒤에 프롬프트를 인자로 주면 디렉터리로 먹혔다("Input must be provided…"). 그래서 stdin으로 보낸다
- 요청 속 프로젝트 이름을 영문 이름으로만 찾아서 "런슈즈"가 걸리지 않았다. 대시보드의 LABEL 대응표로 한국어 이름도 찾는다
- 이어 하기와 새로 하기를 가르려면 세션 제목만으로는 모자랐다. 최근 사람 요청과 답 첫머리가 결정적이었다
- CSS는 다른 세션이 고치고 있는 panel.css 대신 office.html의 `<style>`에 넣었다
  - 세션 177의 작업을 커밋(`8b24a75`)하고 177을 끝낸 뒤 panel.css로 옮겼다
  - 옮긴 뒤 계산된 스타일이 같은지 헤드리스로 확인했다

## 세션 정리(11-05)

- 177의 작업(소품 놓기, 이름표 자리, 인계 요약 고르기, 한국어 hook)을 커밋하기 전에 확인한 것
  - JS 시험 31개, 문법, 테마 JSON
  - `layoutAudit` · `propAudit`: 세 테마 모두 0건
- 177의 입력 칸에 "커밋하고 push해"가 보였다. 흐린 글자(`ESC[2m`)라 CC의 제안 글이었고, 제출하지 않았다
- 177은 끝내기로 정리했다(tmux도 닫힘)
- 런슈즈 CLAUDE.md 초안: `log/runshoes_claude_md_draft_20261105.md`. 런슈즈 저장소는 고치지 않았다
