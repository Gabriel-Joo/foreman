# 묶음 B 판정: 문서 도구 합치기 커밋이 건 원고와 포트폴리오 (2026-11-19)

> 관리자 410의 조사 일감(사용자 지시 11-19). 읽고 판정만 했다. 원고, 포트폴리오, 코드는 고치지 않았다. 판정은 main HEAD `6e9d002` 판의 글과 코드로 했다.

## 1. 맨 위 수

- 고칠 것 있음인 편: **기술문서 3편, 포트폴리오 0편**
- 짝 60개: **있음 3, 없음 57, 모름 0**
- 고칠 것 있음인 편
  - `notion/10_scribe/03_evidence.md` 87줄(근거 표시 고침과 문장 고침)
  - `notion/10_scribe/04_notion.md` 279줄, 283줄
  - `notion/07_merge/01_card.md` 103줄 끝 두 문장

이 묶음의 커밋 여덟은 거의 모두 「고친 코드를 가리키는 문서도 같은 브랜치에서 고친다」(사용자 지시 21) 뒤에 나왔다. 그래서 대부분 커밋이 그 편의 해당 문장을 같은 커밋에서 이미 고쳤다. 머리 주석 「읽은 커밋」만 올리지 않았다. 없음 57개 가운데 많은 수가 「읽은 커밋만」이다.

## 2. 편마다

| 편 | 판정 | 줄과 원문 앞부분 | 까닭 |
|---|---|---|---|
| notion/10_scribe/03_evidence.md | 고칠 것 있음 | 87: 「…머리 주석을 읽는 함수는 근거 확인기가 따로 만들지 않고 게시기와 서기실이 쓰는 원고 모듈의 것을 그대로 가져다 쓴다. … [code:bridge/manuscript.py]」 | 52228df에서 머리 주석 읽기(`parse_head`, `COVERS`, `READ`)가 `bridge/doctext/head.py`로 옮겨 갔다. `bridge/evidence.py`는 이제 `bridge.doctext.head`에서 가져온다. 「원고 모듈」이라는 말과 근거 표시 `[code:bridge/manuscript.py]`가 옛 자리다(같은 편 81줄은 이미 `[code:bridge/doctext/head.py]`로 맞게 쓴다). 근거 표시 고침과 문장 고침 |
| notion/10_scribe/04_notion.md | 고칠 것 있음 | 279: 「인프라 저장소는 이 꼴을 자기 점검 스크립트로 따로 검사한다. 원고를 고치면 저장소마다 원고와 점검을 함께 고쳐야 한다」 / 283: 「번호를 떼는 규칙은 인프라 저장소의 점검 스크립트가 같은 꼴을 검사할 때 쓰는 규칙과 같고…」 | d5ed80d(문서 점검 명령 check를 묶음 위로)부터 인프라 `scripts/docs-check.py`는 FOREMAN `tools/docs.py check`를 부르는 껍데기다(인프라 저장소 파일 머리 글로 확인함). 편 사이 참조 검사도 `bridge/doctext/check.py` 5번이 한다. 「따로 검사한다」는 지금과 어긋나고, 283줄은 따로 된 스크립트가 있는 것처럼 읽힌다. 같은 편 03_evidence 132줄은 「FOREMAN 명령으로 옮겨 왔다」고 맞게 쓴다 |
| notion/07_merge/01_card.md | 고칠 것 있음 | 103 끝: 「카드는 보이게만 할 뿐이라, 아무도 안 보면 조용히 낡는다. 깨지게 만드는 것은 시험뿐이어서 지금 못 푸는 참조가 풀린 뒤에는 pytest에 점검을 건다」 | 550ca00 바로 뒤 `648ac08 test: 문서 점검을 pytest가 돌게 걸기`가 이미 걸었다(`tests/test_docs_selfcheck.py`, 틀린 것 하나라도 있으면 깨짐). 앞날로 쓴 일이 지금은 된 일이다. 648ac08은 test 커밋이라 서기실 셈이 세지 않으므로 이 짝에서 센다 |
| notion/00_foreman.md | 고칠 것 없음 | | CLAUDE.md는 도구 이름(`tools/docrefs.py`가 `tools/docs.py refs`로)만 바뀌었고 편은 그 줄을 말하지 않음. 읽은 커밋만 |
| notion/05_roles/01_roles.md | 고칠 것 없음 | 54 | 코더 절이 「찾는 명령과 원고 쓰는 기준을 함께 적는다」로 이미 맞음(3c75080이 같이 고침). 읽은 커밋만 |
| notion/06_sessions.md | 고칠 것 없음 | 74 | 명령 `tools/docs.py refs --range main...HEAD --unfixed`, 원고 쓰는 기준 절, 다른 저장소 코더 줄 모두 지금 `prompt_block`과 맞음(d5ed80d, 3c75080이 같이 고침). 읽은 커밋만 |
| notion/07_merge.md | 고칠 것 없음 | 136 | 합친 뒤 글의 「코드로 걸린 것과 문서로만 걸린 것을 나눠서」, `tools/docs.py refs --range`가 지금 `mergeprep.py`와 맞음. 문서 점검 줄은 합친 뒤 글에 들지 않고 편도 말하지 않음. 읽은 커밋만 |
| notion/08_handoff/04_move.md | 고칠 것 없음 | | `handoff.js` 변경은 합치기 카드의 걸리는 문서 줄과 문서 점검 줄(`docsNote`, `checkNote`)뿐. 편은 옮기기 흐름만 말함 |
| notion/09_dispatcher.md | 고칠 것 없음 | | `foreman.py` 변경은 지시문의 도구 이름 하나. 편이 말하지 않음 |
| notion/09_dispatcher/01_plan.md | 고칠 것 없음 | 139, 157 | 157줄 코더 절이 지금과 맞음(3c75080이 같이 고침). `scribe_room.py` 변경(머리 주석 가져오는 곳, 원고 쓰는 기준 절)은 139줄의 일 종류 목록과 무관. 읽은 커밋만 |
| notion/10_scribe/03_evidence.md 외 짝 | (위) | | 87줄 말고는 묶음 B가 바꾼 것(점검 명령, 저장소 읽기, `not_code` 경로와 글롭, 줄표 검사, 옮긴 줄 가리기, 덮기에서 `not_code` 빼기)을 41, 69, 83, 85, 132, 134줄이 이미 맞게 씀 |
| notion/11_notify.md | 고칠 것 없음 | 198~205 | 카드 글에 더해진 ⚠ 줄(설정 바뀜, 점검 새 틀림)은 표의 「묶음 종류여도 글에 ⚠가 있는 것」 규칙으로 바로 가고, 편이 그 규칙을 맞게 씀. 걸리는 문서 줄 꼴은 말하지 않음 |
| notion/14_screen.md | 고칠 것 없음 | | `docs/10_office_design.md` 변경은 합치기 카드의 걸리는 문서 줄 하나. 편은 그 줄을 말하지 않음 |
| notion/14_screen/05_check.md | 고칠 것 없음 | 274 | `MARK`가 문서 문법 묶음에 있다고 이미 맞게 씀(52228df가 같이 고침). `tools/docrefs.py`는 말하지 않음. 읽은 커밋만 |
| notion/16_tests.md | 고칠 것 없음(짝 안) | 57, 83, 89 | 걸린 세 파일(`test_coder_docs_rule.py`, `test_docrefs.py`, `screen_words.py`)을 말하는 줄이 지금과 어긋나지 않음. 89줄은 지난 일로 맞게 씀. 다만 짝 밖 43줄 시험 수가 다름(5절) |
| portfolio/06_handoff.md | 고칠 것 없음 | | `handoff.js` 변경은 합치기 카드 줄뿐. 편은 옮기기만 말함 |
| portfolio/07_merge.md | 고칠 것 없음 | 24 | 「코드로 걸린 문서」, 「문서로만 걸린 문서」, 문서 점검 줄을 이미 맞게 씀(d5ed80d, 550ca00이 같이 고침). 읽은 커밋만 |
| portfolio/08_foreman_plan.md | 고칠 것 없음 | 49 | 도구 이름을 말하지 않음 |
| portfolio/10_scribe_room.md | 고칠 것 없음(짝 안) | 44 | 셈은 지금도 `bridge/manuscript.py`(`code_commits`). 묶음 B 변경(문법 옮기기, 원고 기준 절)은 편이 말하지 않음. 다만 짝 밖 44줄 편 수가 다름(5절) |

## 3. 짝마다

### d5ed80d feat: 문서 도구 합치기 3단계
- 00_foreman: 없음. CLAUDE.md는 도구 이름만 바뀜, 편이 말하지 않음
- 05_roles/01_roles: 없음. 지시문 도구 이름과 거꾸로 찾기 머리 주석 읽기 빼기, 편은 도구 이름을 말하지 않음
- 06_sessions: 없음. 74줄 명령이 이미 `tools/docs.py refs`(같은 커밋이 고침). 읽은 커밋만
- 07_merge: 없음. 136줄 합친 뒤 글을 이미 맞게 씀. 읽은 커밋만
- 07_merge/01_card: 없음. 95~101줄(옛 이름 지움, 다루는 곳 안 읽음, 두 줄로 나눈 수, 설정 바뀜 줄)을 같은 커밋이 고침. 읽은 커밋만
- 08_handoff/04_move: 없음. 카드 줄 변경, 편이 말하지 않음
- 09_dispatcher: 없음. 지시문 도구 이름, 편이 말하지 않음
- 09_dispatcher/01_plan: 없음. 157줄 맞음
- 10_scribe/03_evidence: 없음. 점검 명령(check.py), 함수 같이 쓰기를 41, 69, 83, 85, 132줄이 맞게 씀
- 10_scribe/04_notion: **있음**. 279, 283줄 인프라 점검 스크립트가 따로 검사한다는 말, 지금은 FOREMAN check를 부르는 껍데기
- 11_notify: 없음. 카드 글 수 줄 꼴을 말하지 않음, ⚠ 규칙은 맞음
- 14_screen: 없음. 설계 문서의 카드 줄, 편이 말하지 않음
- 14_screen/05_check: 없음. `tools/docrefs.py` 지움, 편이 말하지 않음
- 16_tests: 없음. 두 시험 파일의 고침(도구 이름, 다루는 곳 안 읽음)이 57줄 설명과 어긋나지 않음
- portfolio/06_handoff: 없음. 카드 줄, 편이 말하지 않음
- portfolio/07_merge: 없음. 24줄 이미 맞음(같은 커밋이 고침). 읽은 커밋만
- portfolio/08_foreman_plan: 없음. 도구 이름, 편이 말하지 않음

### 52228df feat: 문서 도구 합치기 1단계
- 05_roles/01_roles: 없음. docrefs 안 문법 옮기기(리팩터), 편이 말하지 않음
- 06_sessions: 없음. 같은 까닭
- 07_merge/01_card: 없음. 95줄 `.foreman/docs.toml`과 `bridge/doctext/config.py`를 맞게 씀. 읽은 커밋만
- 09_dispatcher/01_plan: 없음. `scribe_room.py`는 머리 주석 가져오는 곳만 바뀜, 편이 말하지 않음
- 10_scribe/03_evidence: **있음**. 87줄 「원고 모듈」, `[code:bridge/manuscript.py]`가 옛 자리(지금 `bridge/doctext/head.py`)
- 10_scribe/04_notion: 없음. 58, 253, 283줄이 `bridge/doctext/titles.py`, `head.py`를 맞게 씀(같은 커밋이 고침). 232, 234줄 `tree_parent`, `tree_order`는 지금도 `manuscript.py`에 있음. 읽은 커밋만
- 14_screen/05_check: 없음. 274줄 이미 맞음(같은 커밋이 고침). 읽은 커밋만
- 16_tests: 없음. `screen_words.py`의 MARK 가져오는 곳만 바뀜, 89줄은 지난 일로 맞음
- portfolio/10_scribe_room: 없음. 리팩터, 편이 말하지 않음

### 79b0023 feat: 문서 도구 합치기 2단계, 거꾸로 찾기를 묶음 위로
- 05_roles/01_roles: 없음. 거꾸로 찾기가 설정을 읽게 됨, 편이 말하지 않음
- 06_sessions: 없음. 같은 까닭
- 07_merge/01_card: 없음. 95줄이 문서 트리거(docs와 묶음 밖 .md), 설정 파일을 맞게 씀(같은 커밋이 고침). 읽은 커밋만
- 09_dispatcher/01_plan: 없음. 편이 말하지 않음
- 10_scribe/03_evidence: 없음. 132줄이 저장소 읽기(`repo.py`)를 맞게 씀
- 10_scribe/04_notion: 없음. marks, repo 변경을 편이 말하지 않음
- 14_screen/05_check: 없음. `tools/docrefs.py` 껍데기화, 편이 말하지 않음
- 16_tests: 없음. `test_docrefs.py`의 겹치지 않는 줄 번호 판정 변경, 57줄 설명과 어긋나지 않음

### 3c75080 feat: 문서 도구 합치기 4단계
- 05_roles/01_roles: 없음. 54줄 원고 쓰는 기준을 이미 말함(같은 커밋이 고침). 읽은 커밋만
- 06_sessions: 없음. 74줄 이미 맞음. 읽은 커밋만
- 07_merge/01_card: 없음. 말투 줄 변경, 편이 말하지 않음
- 09_dispatcher/01_plan: 없음. 157줄 이미 맞음. 읽은 커밋만
- 10_scribe/03_evidence: 없음. 134줄이 줄표 검사(dashdot)를 맞게 씀
- 10_scribe/04_notion: 없음. dashdot을 편이 말하지 않음(259줄 갱신 줄의 줄표 약속은 `notion.py` 몫)
- 16_tests: 없음. `test_coder_docs_rule.py`에 기준 문서 확인이 더해졌을 뿐, 57줄과 어긋나지 않음
- portfolio/10_scribe_room: 없음. 지시문에 원고 기준 절, 31줄 「원고 쓰는 기준이 정하고」와 맞음

### 550ca00 feat: 합치기 카드에 문서 점검 줄, 근거 없는 파일 셈 정리
- 05_roles/01_roles: 없음. `not_code` 경로 받기, 편이 말하지 않음
- 06_sessions: 없음. 같은 까닭
- 07_merge: 없음. 문서 점검 줄은 합친 뒤 글에 들지 않음, 편이 말하지 않음
- 07_merge/01_card: **있음**. 103줄 끝 「풀린 뒤에는 pytest에 점검을 건다」, 이미 648ac08에서 걸림. 나머지 83, 103, 129, 274줄은 맞음
- 08_handoff/04_move: 없음. `checkNote`, 편이 말하지 않음
- 09_dispatcher/01_plan: 없음. 편이 말하지 않음
- 10_scribe/03_evidence: 없음. 132줄 `not_code`(빈 패키지 표시 파일 넷과 `.gitignore`)가 지금 `.foreman/docs.toml`과 같음
- 10_scribe/04_notion: 없음. config 변경, 편이 말하지 않음
- 11_notify: 없음. 점검 줄 ⚠는 「글에 ⚠가 있으면 바로」 규칙(205줄 위 표)으로 맞음
- portfolio/06_handoff: 없음. 편이 말하지 않음
- portfolio/07_merge: 없음. 24줄 문서 점검 줄 이미 맞음. 읽은 커밋만

### 3bd1eee feat: 줄표와 가운뎃점 검사를 저장소마다 문서 점검에 넣음
- 07_merge/01_card: 없음. 103줄 「문서 점검에는 새 줄의 em dash와 가운뎃점 검사도 들어 있어서」 맞음
- 10_scribe/03_evidence: 없음. 134줄 기준 커밋을 저장소마다 `.foreman/docs.toml`, README와 CLAUDE.md도 봄, 기준 없으면 알림, 조상 아니면 틀림 하나, 모두 맞음
- 10_scribe/04_notion: 없음. 편이 말하지 않음

### c135449 fix: 줄표 검사 옮긴 줄 가리기
- 10_scribe/03_evidence: 없음. 134줄 옮긴 줄 풀이(근거 표시 떼고 맞대기, 하나가 하나만 풂)를 맞게 씀
- 10_scribe/04_notion: 없음. 편이 말하지 않음

### f305179 fix: 덮기 검사가 not_code에 드는 파일을 뺌
- 10_scribe/03_evidence: 없음. 132줄 덮기에서 `not_code` 빼기, `.md`만 남김을 맞게 씀
- 10_scribe/04_notion: 없음. 편이 말하지 않음

## 4. 사람이 정할 것

- 01_card 103줄은 탓한 커밋(550ca00)이 아니라 그 바로 뒤 test 커밋(648ac08)이 낡게 했다. test 커밋은 서기실 셈이 세지 않으므로, 이 짝으로 넘겨 서기에게 맡길지 정해 주십시오.
- 04_notion 279줄은 「원고 쪽을 마크다운 링크로 바꾸지 않은 까닭」의 한 근거다. 인프라 점검이 FOREMAN으로 옮겨 온 지금도 「원고는 저장소마다 있다」는 까닭은 남는다. 그래서 줄을 지울지, 까닭을 고쳐 쓸지는 서기가 판단할 몫으로 보았다.

## 5. 짝 밖에서 본 것(이 묶음 판정 수에 넣지 않음)

다른 세션이 다른 커밋으로 같은 편을 볼 수 있어 수에 넣지 않았다. 겹치는지 관리자가 맞대 주십시오.

- `notion/16_tests.md` 43줄 「파이썬 시험 파일 107개, 모으는 시험 1,369개, js 40개 파일, 227개」: 지금은 `tests/test_*.py` 111개, `pytest --collect-only` 1,461개, `tests/js/*.test.mjs` 42개다(js 시험 수는 세지 않았다)
- `portfolio/10_scribe_room.md` 44줄 「지금은 16편입니다」: 지금 `portfolio/*.md`는 17편이다(`16_limits.md`가 뒤에 더해짐)
- 코드 주석 `bridge/evidence.py` 6줄 머리 글이 아직 「bridge/manuscript.py」를 머리 주석 자리로 적는다. 원고가 아니라 코드 주석이라 이 일감 밖이다

## 6. 규칙 위반

규칙 위반 없음.
