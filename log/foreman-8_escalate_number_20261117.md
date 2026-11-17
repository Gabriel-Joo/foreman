# 관리자 물음에 번호, 번호 없이 넘어간 물음은 「아직 안 본 물음」 (2026-11-17, worktree foreman-8, 코더)

관리자 410의 코더 일감(사용자 지시 11-17, #3123 답 (다), 인프라 관리자가 사람 지시로 전한 #3058 건).
관리자가 escalate로 올린 물음이 사람이 그 관리자에게 무엇이든 입력하면 내용과 상관없이 사라지던 것을 고쳤다.

## 1. 판정 규칙 (`bridge/api/dashboard.py`)

- `human_needs`가 합치기 카드 물음이 아닌 escalate 물음(끄거나 봤다로 지운 것은 뺀다)을 `esc_question_states`로 넘긴다
- 그 물음 뒤에 시작한 사람 턴(origin human)의 글(`turn.prompt_text`, 마스킹을 거친 글)에서 `#숫자`를 찾는다(`esc_numbers`, 정규식 `#(\d+)(?!\d)`. `#30581`은 3058이 아니다)

| 그 물음 뒤 사람 입력 | 결과 | 화면 |
|---|---|---|
| 없음 | pending | 지금처럼 `escalate.question`(가장 최근 하나) |
| 있고, 어느 글에든 `#id` | answered(끝남) | 띄우지 않는다 |
| 있지만 번호 없음 | unseen | `escalate.unseen` 목록 |

- 여러 물음이면 번호가 든 것만 끝나고 나머지는 unseen. 나중에 번호로 답하면 그때 끝난다(입력 차례와 상관없이 그 물음 뒤 사람 턴 어디든)
- 끝난 물음의 기록: 새 행을 쓰지 않는다. 번호가 든 사람 턴 글과 escalate 행이 이미 DB에 있어 둘로 되짚을 수 있다. `human_needs`는 화면 스냅샷마다 도는 읽기 함수라 거기서 쓰기를 하지 않으려고 이렇게 정했다
- 보고(`report`)는 바꾸지 않았다(읽거나 사람이 입력하면 사라짐). 합치기 카드 물음(`_MERGE_TAG`)도 바꾸지 않았다(카드가 남는 동안 남음, unseen으로 가지 않음)
- 곁가지로 바뀐 것: 전에는 물음을 종류마다 마지막 하나로 덮어써서, 마지막 물음이 꺼지면(esc-off) 앞의 안 끈 물음까지 같이 안 보였다. 이제 아직 떠 있는 물음 중 가장 최근 것이 보인다. 앞의 물음은 사람이 입력하면 unseen으로 드러난다

## 2. API

- `POST /api/sessions/{sid}/escalate-seen?id=N`: unseen 목록에 있는 물음만 `session_action` `esc-seen`(detail = escalate id)으로 지운다. 목록에 없으면 `{"ok": false}`. 점검 화면(`x-foreman-probe`)은 세지 않는다. 브리지 로그에 한 줄
- `esc-seen`은 `esc-read`, `esc-off`와 같은 「끝난 것」 집합에 들어간다
- `POST /api/sessions/{sid}/escalate` 물음의 응답 `note`에 「물음 번호는 #N입니다. 사람이 그 번호를 넣어 답하면 끝나고, 번호 없이 다른 얘기를 하면 「아직 안 본 물음」으로 남습니다」

## 3. 화면

- 머리 위(`render.js` `needMark`): 「아직 안 본 물음 N」, 노랑. 순서는 사용자 답 기다림 다음, 합치기 기다림 위. 호버에 번호와 글
- 「사용자 답 기다림」 호버에 물음 번호와 「#N을 넣어 답하면 끝납니다」
- 관리자 패널(`opanel.js` `drawEscUnseen`, `#pEsc`): 머리줄 아래 띠 「❔ 아직 안 본 물음 N: …」, 물음마다 `#번호`, 글 한 줄, [봤다]. [나중에]는 두지 않았다(숨기는 길을 두면 다시 쌓여도 안 보인다). 패널을 연 것만으로는 지우지 않는다
- `store.js` `escalateSeen`, `panel.css` `.esc-unseen .esc-row`
- 배지(`humanNeed`)와 방 카드 숫자(`office.js` `userAsks`)에는 넣지 않았다. 세션을 막는 대기가 아니어서다
- 이름을 바꾼 화면 말이 없어 `tests/data/screen_words.toml`에는 줄을 더하지 않았다

## 4. 알림(텔레그램) 판단

- 물음 알림 첫 줄에 `#N`, 끝에 「답할 때 물음 번호 #N도 함께 넣으면 이 물음이 끝납니다」(합치기 카드 물음에는 끝줄을 붙이지 않는다)
- unseen으로 바뀔 때 따로 알리지 않는다. 물음이 올라올 때 이미 바로 알렸고, unseen이 되는 순간은 사람이 그 관리자 대화에 입력하던 때라 화면 앞에 있다. 더 보내면 같은 물음으로 두 번 울린다

## 5. 지시문 줄

- `bridge/managers.py` `escalate_hint`(관리자가 받는 중계 글 끝 「사람에게 올릴 때」 한 줄) 끝에 「물음에는 번호(#id, 응답의 id)가 붙고, 사람이 그 번호를 넣어 답하면 끝납니다(번호 없이 넘어가면 사람 화면에 「아직 안 본 물음」으로 남습니다)」
- CLAUDE.md 「작업 규칙」 escalate 줄 끝에 같은 뜻 한 문장(사람 승인 카드가 된다)
- 네 프로젝트 관리자 모두 같다. 다른 저장소 CLAUDE.md는 고치지 않았다. 그쪽 관리자는 escalate 응답 `note`와 중계 글 끝 한 줄로 번호를 받는다

## 6. 시험

- `tests/test_escalate_number.py`(새): 번호 뽑기, 지시문 줄, 번호를 넣은 입력(그 물음만 끝나고 다른 물음은 unseen, 나중에 번호로 답하면 빠짐), 번호 없는 입력과 [봤다]로 지우기(하나씩 줄어 빔, 이미 지운 것과 아직 떠 있는 물음은 거부), 합치기 카드 물음은 그대로
- `tests/js/escalate_unseen.test.mjs`(새): 머리 위 글과 색, 호버, 순서, 배지에 안 듦
- 기대를 바꾼 옛 시험 둘: `tests/test_overhead_marks.py`(번호 없는 입력 뒤 「escalate 없음」 → unseen), `tests/test_merge_wait_manager.py`(카드 물음과 같이 있던 다른 물음이 unseen으로)
- 전체: pytest 1246 passed(경고 1은 이번 파일과 무관), `node --test tests/js/` 225 pass 0 fail. 문서까지 고친 뒤 다시 돌린 결과는 7절

## 7. 함께 고친 문서

- `docs/10_office_design.md` 「머리 위 표시」: 3행 고침, 3-2행 「아직 안 본 물음 N」 더함, 겹침 순서
- `docs/operations.md`: escalate 줄 아래에 번호와 아직 안 본 물음, 알림 표 escalate 행
- `notion/09_dispatcher/04_managers.md`: 안내 한 줄, 알림 표, 「언제 사라지나」(#3058 까닭, 세 갈래 표, 쌓이지 않게 한 까닭), 머리 위 표, 겹침 순서
- `notion/11_notify.md`: 물음 알림의 번호와 다시 알리지 않는 까닭
- `notion/14_screen/03_panel.md`: 띠 셋 → 넷, 넷째 띠 문단
- `portfolio/02_overhead.md`: 물음 번호와 아직 안 본 물음(경어체)
- `notion/16_tests.md`: 시험 개수(파이썬 파일 97 → 98, 시험 1,241 → 1,246, js 39 → 40 파일, 222 → 225)
- 거꾸로 찾는 도구(`--range main...HEAD --unfixed`)는 원고 서른 곳 남짓을 더 짚었지만, `dashboard.py`, `render.js`, `opanel.js`, `store.js`, `panel.css` 같은 큰 파일을 통째로 가리키는 근거 표시라서 걸렸다. escalate, 머리 위 표시, 패널 띠, 시험 개수를 다루는 문단은 위에서 고쳤고, 나머지 걸린 문단은 지금 코드와 맞아 그대로 두었다(예: `portfolio/15_telegram.md` 56, `notion/14_screen/01_store.md` 73과 83, `notion/14_screen/05_check.md` 76)
- 머리 「읽은 커밋」은 바꾸지 않았다. 「다루는 곳」은 범위가 바뀌지 않아 그대로
- 건드리지 않은 파일: `bridge/evidence.py`, `bridge/manuscript.py`, `bridge/notion.py`, `bridge/scribe_room.py`(같은 시각 다른 코더 몫). 서기 526의 원고 세 곳과 겹치는지는 알 수 없다. 합칠 때 `git merge-tree`로 확인이 필요하다

## 8. 규칙 위반

- **있음, 한 번.** 처음 고칠 때 `bridge/api/dashboard.py` 새 주석과 docstring 몇 줄, `bridge/static/js/render.js` 새 주석 두 줄에 em dash(—)와 가운뎃점(·)을 썼다(일감 「지킬 것」: 새 주석에 쓰지 않는다). 쓰고 바로 알아채 커밋 전에 쉼표, 마침표, 「와」로 바꿨다. 화면 툴팁 첫 줄의 「제목 — 설명」은 `docs/style_guide.md` 4-1이 허락한 나눔(tip.js가 그 기호로 자름)이라 그대로 썼다
- 그 밖에는 위반 없음(파일은 Edit, Write로만, push와 브리지 다시 띄우기 안 함)
