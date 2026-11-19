# 묶음 D 판정: 원고와 포트폴리오에 실제로 고칠 것이 있는가 (11-19)

관리자 410의 조사 일감(사용자 지시 11-19). 읽고 판정만 했다. 원고, 포트폴리오, 코드는 고치지 않았다. 판정은 main HEAD 판 글을 기준으로 했다.

## 1. 맨 위 수

- 고칠 것 있음인 편: **기술문서 0편, 포트폴리오 1편** (`portfolio/02_overhead.md`)
- 짝 20개: 고칠 것 있음 1, 고칠 것 없음 19, 모름 0
  - 7febd11: 10짝(있음 1, 없음 9)
  - 4386b3a: 9짝(없음 9)
  - 408e4ed: 1짝(없음 1)
- 「읽은 커밋만」 올리면 되는 편(문장은 맞고 머리만 낡음): 6편. 기술문서 `09_dispatcher/04_managers.md`, `14_screen/03_panel.md`, `07_merge/01_card.md`, `08_handoff/01_loss.md`, `08_handoff/03_promote.md`, `16_tests.md`. 이 여섯은 그 커밋이 같은 묶음 안에서 이미 문장을 고쳤고, 머리의 읽은 커밋만 옛 값이다

## 2. 편마다 표

| 편 | 판정 | 줄과 원문 앞부분 | 까닭 |
|---|---|---|---|
| portfolio/02_overhead.md | **고칠 것 있음** | 35줄 「순서는 권한 거부, API 오류로 멈춤, 답 기다림, 사용자 답 기다림, 합치기 기다림, 사용자에게 보고함, …」 | `render.js` `needMark`에 「아직 안 본 물음 N」이 사용자 답 기다림 다음, 합치기 기다림 앞으로 들어갔는데 이 순서 문장에 없다. 같은 편 19줄은 이미 새 표시를 설명하고 있어 35줄만 어긋난다 |
| notion/00_foreman.md | 고칠 것 없음 | | `CLAUDE.md`에서 바뀐 것은 escalate 줄 하나(물음 번호). 이 편의 `[code:CLAUDE.md]` 문장(43, 49, 59, 145줄)은 조용한 고장 질문, 같은 일을 하는 세션 알아채기, 다른 저장소 규칙이라 그 줄을 말하지 않는다 |
| notion/09_dispatcher/04_managers.md | 고칠 것 없음(읽은 커밋만) | | 7febd11이 이 편의 escalate 절(173, 222, 232, 239~247, 261~273줄)을 이미 새 동작으로 고쳤고, 코드와 맞대어 보니 맞다. 머리 읽은 커밋 `5e0f7c5`만 7febd11 앞이다. 경미한 참고는 3절 |
| notion/14_screen.md | 고칠 것 없음 | | `panel.css`는 새 규칙 세 줄(안 본 물음 띠), `docs/10_office_design.md`는 그 표 갱신. 이 편은 panel.css를 「색 변수만 쓴다」, 「한 파일로 모았다」로만 말하고 띠나 말풍선 순서를 말하지 않는다 |
| notion/14_screen/01_store.md | 고칠 것 없음 | | `store.js`에 `escalateSeen`, `dashboard.py`에 `esc_question_states`, `escalate_seen`이 생겼다. 이 편은 이 둘을 말하지 않는다. 73줄은 칸 이름 `escalate`만 적고 안쪽 모양을 안 풀며, 83줄 「사람이 읽거나 답할 때까지」와 107줄의 캐시 비우기 예시(「등」)와 262줄의 읽음 요청 거절도 새 길과 어긋나지 않는다 |
| notion/14_screen/03_panel.md | 고칠 것 없음(읽은 커밋만) | | 7febd11이 29줄(띠 넷), 142~144줄(넷째 띠, [나중에] 없음)을 이미 고쳤다. `opanel.js` `drawEscUnseen`, `pEsc`, `escUnseen`과 맞다. 머리 읽은 커밋만 낡았다. 경미한 참고는 3절 |
| notion/14_screen/05_check.md | 고칠 것 없음 | | 바뀐 것은 시험 파일 둘의 기대값(unseen 추가)뿐이다. 이 편은 시험 파일을 「다루는 곳」에 나열하기만 하고 그 기대값을 말하지 않는다 |
| portfolio/00_overview.md | 고칠 것 없음 | | `opanel.js`에 띠 하나가 늘었다. 25줄의 패널 설명(머리, 탭 셋, 입력 칸)은 띠를 세지 않아 어긋나지 않는다 |
| portfolio/05_approval.md | 고칠 것 없음 | | `render.js`에서 바뀐 것은 escalate 말풍선 글(ESC_TIP)과 `needMark` 순서뿐이다. 이 편이 `render.js`를 가리키는 문장(36, 44, 48줄)은 승인 대기 머리줄, ❗, 접힌 카드, 질문 카드라 닿지 않는다 |
| portfolio/07_merge.md | 고칠 것 없음 | | 36줄 「권한 거부, 답 기다림, 합치기 기다림, 보고 옴 순」은 작업 세션 캐릭터 이야기이고, 새 표시는 관리자만이라 이 문장에 끼지 않는다. 이 줄이 API 오류를 빼고 있는 것은 이 커밋 전부터이고 이 커밋이 만든 어긋남이 아니다 |
| notion/05_roles/01_roles.md | 고칠 것 없음 | | `docrefs.py`는 `is_code`가 문서 묶음 폴더 아래 파일(사진)을 코드로 세지 않게 바뀌고 주석 한 줄이 바뀌었다. 이 편 54줄은 규칙 글을 코더 첫 글에 붙이는 일을 말해, 코드로 세는 범위와 닿지 않는다 |
| notion/06_sessions.md | 고칠 것 없음 | | 같은 까닭. 74줄은 첫 글에 붙는 절의 내용이다 |
| notion/07_merge/01_card.md | 고칠 것 없음(읽은 커밋만) | | 4386b3a가 95줄에 「docs, 원고, 포트폴리오 폴더 아래 사진 같은 파일도 확장자와 상관없이 뺀다」를 이미 넣었다. 지금 `trigger_kind`도 같은 동작(문서 묶음 폴더 아래는 코드가 아님)이라 맞다 |
| notion/08_handoff/01_loss.md | 고칠 것 없음(읽은 커밋만) | | 4386b3a가 310줄을 「실패 알림은 ⚠를 달고 바로 간다, 판정 묶음 일부가 실패하면 끝남 알림도 바로, 건너뛴 것만 있으면 묶음」으로 이미 고쳤다. `losscheck.py`(`fail=True`, `fail=bool(bad)`)와 맞다 |
| notion/08_handoff/03_promote.md | 고칠 것 없음(읽은 커밋만) | | 4386b3a가 94줄과 172줄을 이미 고쳤다. `promote.py`의 목록 실패 둘, 확인 실패 하나가 `fail=True`인 것과 맞다 |
| notion/08_handoff/04_move.md | 고칠 것 없음 | | 이 편은 `losscheck.py`를 결과 갈래(`outcome`, 95줄)로만 가리키고 점검의 텔레그램 알림은 말하지 않는다. 알림 줄이 있는 곳은 01_loss 쪽이다 |
| notion/09_dispatcher/01_plan.md | 고칠 것 없음 | | `docrefs.py`를 가리키는 157줄은 코더 첫 글에 붙는 절의 내용이다. 코드로 세는 범위는 말하지 않는다 |
| notion/16_tests.md | 고칠 것 없음(읽은 커밋만) | | 4386b3a가 57줄에 `test_docrefs.py`(사진을 코드로 세지 않는지)와 `test_fail_notify_scan.py`(알림 부르는 곳 훑기)를 이미 적었고 시험 파일 머리 설명과 맞다. 수 줄(43줄)이 낡은 것은 3절 |
| portfolio/06_handoff.md | 고칠 것 없음 | | 알림을 말하는 두 곳 중 18줄은 압축 알림(`compactwatch`), 54줄은 인계 요약 실패(`handoff.py`)라서 점검과 문서 옮기기의 실패 알림을 말하는 문장이 없다. 어긋난 문장이 없다 |
| notion/02_ingest/03_turns.md | 고칠 것 없음 | | 408e4ed가 `test_stage2_db.py`에서 뺀 것은 받은 할 일 칸과 서기 말풍선 기준 시험이다. 이 편이 이 파일을 가리키는 세 문장(158, 217, 221줄)은 메시지 중복, 다시 읽어도 같은 결과 시험이라 닿지 않는다 |

## 3. 짝마다 짧은 판정

### 7febd11 feat: 물음 번호로 풀기와 안 본 목록
- 7febd11, notion/00_foreman.md: 고칠 것 없음. 바뀐 CLAUDE.md 줄을 이 편이 말하지 않는다
- 7febd11, notion/09_dispatcher/04_managers.md: 고칠 것 없음(읽은 커밋만). 같은 커밋이 이미 고쳤고 코드와 맞다
- 7febd11, notion/14_screen.md: 고칠 것 없음. panel.css와 10_office_design 변경분을 이 편이 말하지 않는다
- 7febd11, notion/14_screen/01_store.md: 고칠 것 없음. 새 `escalateSeen`, `esc_question_states`를 말하지 않고 기존 문장도 안 틀린다
- 7febd11, notion/14_screen/03_panel.md: 고칠 것 없음(읽은 커밋만). 같은 커밋이 이미 넷째 띠를 적었다
- 7febd11, notion/14_screen/05_check.md: 고칠 것 없음. 시험 기대값만 바뀌고 이 편은 그것을 말하지 않는다
- 7febd11, portfolio/00_overview.md: 고칠 것 없음. 패널 설명이 띠 수를 세지 않는다
- 7febd11, portfolio/02_overhead.md: **고칠 것 있음**. 35줄 겹침 순서에 「아직 안 본 물음」이 빠졌다(사용자 답 기다림 다음, 합치기 기다림 앞)
- 7febd11, portfolio/05_approval.md: 고칠 것 없음. render.js의 바뀐 부분(물음 말풍선)과 닿지 않는다
- 7febd11, portfolio/07_merge.md: 고칠 것 없음. 새 표시는 관리자 몫이고 이 문장은 작업 세션 몫이다

### 4386b3a fix: 놓친 실패 알림을 바로 보내고 사진 헛걸림을 고침
- 4386b3a, notion/05_roles/01_roles.md: 고칠 것 없음. docrefs 변경은 코드로 세는 범위이고 이 문장은 규칙 붙이기
- 4386b3a, notion/06_sessions.md: 고칠 것 없음. 같은 까닭
- 4386b3a, notion/07_merge/01_card.md: 고칠 것 없음(읽은 커밋만). 같은 커밋이 이미 고쳤고 지금 코드와 맞다
- 4386b3a, notion/08_handoff/01_loss.md: 고칠 것 없음(읽은 커밋만). 같은 커밋이 이미 고쳤고 맞다
- 4386b3a, notion/08_handoff/03_promote.md: 고칠 것 없음(읽은 커밋만). 같은 커밋이 이미 고쳤고 맞다
- 4386b3a, notion/08_handoff/04_move.md: 고칠 것 없음. 점검 알림을 말하지 않는다
- 4386b3a, notion/09_dispatcher/01_plan.md: 고칠 것 없음. docrefs 변경과 닿지 않는다
- 4386b3a, notion/16_tests.md: 고칠 것 없음(읽은 커밋만). 새 시험 둘 설명은 이미 있고 맞다. 수 줄은 아래 참고
- 4386b3a, portfolio/06_handoff.md: 고칠 것 없음. 점검과 문서 옮기기의 실패 알림을 말하는 문장이 없다

### 408e4ed fix: nudge 설정과 🛡 알림 고치기
- 408e4ed, notion/02_ingest/03_turns.md: 고칠 것 없음. 뺀 시험은 이 편이 가리키는 시험이 아니다

### 참고(세지 않은 것, 이 묶음 짝의 판정은 바꾸지 않는다)
- `notion/16_tests.md` 43줄 수가 지금 코드와 다르다. 글은 「시험 파일 107개, pytest 1,369개, js 40개 파일 227개」인데 이 worktree 기준 실제는 시험 파일 111개, pytest 수집 1,461개, js 파일 42개다(js 시험 수는 세지 않았다). 4386b3a 때문이 아니라 그 뒤 다른 커밋들이 시험을 더해서 생긴 일이라 다른 묶음 짝에서 걸릴 것이다. 서기가 이 편을 고치게 되면 이 줄은 같이 고쳐야 한다
- `notion/09_dispatcher/04_managers.md` 222줄 표: 물음 알림 글 끝에 「답할 때 물음 번호도 함께 넣으면…」이 붙는다고 일반으로 썼는데, 코드(`dashboard.py` `escalate`)는 합치기 카드 물음(`tag`가 있는 것)에는 이 줄을 붙이지 않는다. 253줄이 합치기 물음을 따로 말하니 큰 어긋남은 아니고, 고칠지는 서기가 정하면 된다
- `notion/14_screen/03_panel.md` 142줄 「띠마다 [나중에]가 있어」와 144줄 「이 띠에는 [나중에]가 없다」가 같은 절에서 부딪힌다. 144줄이 예외를 밝혀 둔 것이라 어긋남으로 세지 않았다

## 4. 사람이 정할 것

- 포트폴리오 `02_overhead.md` 35줄 한 문장은 서기에게 시킬 만한 크기다(순서 문장에 「아직 안 본 물음」을 사용자 답 기다림 뒤에 한 칸 넣으면 끝). 기술문서는 이 묶음에서 고칠 것이 없어, 머리 읽은 커밋만 올리는 일은 서기를 돌리지 않고 도구로 한 번에 올릴지 사용자가 정하면 된다
- 위 참고 셋(16_tests 수 줄, 04_managers 222줄, 03_panel 142줄)을 서기에게 같이 시킬지

## 5. 규칙 위반

규칙 위반 없음. 파일은 Write로 이 log 하나만 만들었다. sed, heredoc, 리디렉션, `pgrep -f`를 쓰지 않았고 원고, 포트폴리오, 코드를 건드리지 않았다.
