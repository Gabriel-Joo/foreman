# 「다루는 곳」 기준을 적고 원고 머리를 맞춤 (서기, 관리자 410 일감)

- 시작한 main 커밋: a511e6f
- 규칙 위반: 없음

## 한 일

1. `docs/manuscript_rules.md`에 사용자 기준 넷을 적었다. 1~5절은 한 줄에 기준 하나라 모두 한 줄 글머리로 썼고 까닭은 같은 줄에 붙였다.
   - 1절(편 사이 참조 줄 옆): 표 칸에서도 `→ 「제목」` 꼴
   - 4절: 본문이 그 파일의 동작을 설명하면 다루는 곳에 넣고, 근거로 한 번 걸었을 뿐이면 넣지 않는다. 입구 편처럼 특정 코드를 설명하지 않는 편도 넣지 않는다
   - 4절: 「자주 걸린다」는 넣지 않을 까닭이 아니라는 문장과 까닭(자주 바뀌는 파일을 설명하는 편은 자주 고쳐야 하고, 안 넣으면 낡아도 모른다. 서기들이 열 번 물었다)
   - 4절: 원고에 바깥으로 나가는 링크를 넣지 않는다. 까닭은 `bridge/notion.py`가 글자만 남기는 동작과 정해질 때 저장소가 비공개라 404가 났던 일. 공개된 뒤에도 그대로 둔 까닭은 기록에 없다고 적었다
2. 다루는 곳을 고쳤다.
   - `notion/09_dispatcher/02_note_wake.md`: `bridge/foreman.py` 더함
   - `notion/10_scribe/01_room.md`: `bridge/mergeprep.py`, `bridge/manuscript.py` 더함
   - `notion/12_pipeline.md`: `render.js`, `office.js`, `bridge/main.py`, `bridge/foreman.py` 더함
   - `notion/00_foreman.md`: 기준대로 넣지 않음
   - `notion/14_screen/05_check.md`: 시험 여섯 파일을 뺐다(`merge_wait.test.mjs`는 본문 220줄이 설명해 남김). 합치기 기다림 시험 넷(`test_merge_wait.py`, `test_merge_wait_manager.py`, `test_merge_wait_off_remind.py`, `merge_wait_manager.test.mjs`)은 `notion/07_merge/01_card.md`로, 머리 위 표시 시험 둘(`test_overhead_marks.py`, `overhead_marks.test.mjs`)은 `notion/14_screen/02_office.md`로 옮겼다
   - 덮기 검사: 옮긴 뒤 「덮기 대상 파일 511 가운데 511 덮음」으로 빠진 것 없음(옮기기 전 수는 재지 않았다)
3. 낡은 줄 둘을 고쳤다.
   - `notion/12_pipeline.md` 11절: 설계 문서가 이제 웹훅을 Jenkins, Harbor, ArgoCD 셋으로 적고 GitLab 길이 없다고 밝히며, 파이프라인 구역으로 걷지 않고 출하 라인에서 배송 담당이 걷는다고 적는다. 그에 맞게 인용을 고쳤다
   - `notion/01_structure.md`: no-cache 목록에 `/usage` 더함
4. 맞대어 올린 「읽은 커밋」(a511e6f): `02_note_wake.md`, `01_room.md`, `12_pipeline.md`
   - `02_note_wake.md`: `foreman.py`의 인용 11곳 가운데 5건 상한, 8건 패널, 30분 훑기, 24시간 안 계획, 읽기 전용 규칙, 빈 노트 안내를 코드와 맞대 같았다. 나머지 인용은 줄마다 읽지 않았다(읽은 커밋 뒤 `foreman.py`에는 커밋이 없었다)
   - `01_room.md`: `manuscript.py`의 feat, fix 병합 제외 셈과 `mergeprep.py`의 줄 카드 가르기(`_queue_verdict`)를 맞대 같았다
   - `12_pipeline.md`: 패널 체인 4건, 17분 빨강, 25초와 30분 머묾, 웹훅 포트 `/webhooks/*`만 받음, `foreman.py` 체인 하나를 맞대 같았다. 읽은 커밋 뒤 네 파일의 변경은 `2203c57`의 한 줄뿐(`/usage` no-cache)
5. 올리지 않은 것: `07_merge/01_card.md`, `14_screen/02_office.md`, `14_screen/05_check.md`, `01_structure.md`는 머리 시험 파일만 옮겼거나 한 줄만 고쳤고 본문과 맞대지 않아 읽은 커밋을 그대로 둔다

## 기준에 걸릴 수 있는 다른 편

고치지 않고 목록만 적는다. 전체 38편을 하나씩 읽지는 않았다. 눈에 띈 것만이다.

- `notion/14_screen/05_check.md`: 본문이 `tests/js/merge_wait.test.mjs` 외에 화면 말 시험은 설명하나, `bridge/static/js/render.js`의 `mergeWaits` 같은 동작을 직접 말하지는 않아 넣지 않았다
- 그 밖에 근거 표시로 한 번만 건 파일이 다루는 곳에 들어 있는지는 편마다 다시 봐야 한다. 이번 일감에서는 따로 찾아 내지 못했다

## 하지 않은 것

- 코드, 시험, 설정은 고치지 않았다
- 근거 표시 점검 코더가 맡은 `[code:CLAUDE.md]` 줄과 `docs/manuscript_rules.md`의 근거 표시 꼴 줄은 건드리지 않았다
- 시험: `tools/docs.py check` 틀린 것 0(의심 209), pytest 1522 passed(213초)

## 사람이 정할 것

- `docs/manuscript_rules.md`는 사람 승인 문서라 합치기 카드가 사람에게 간다. 4절 세 줄은 코더 규칙 절에는 첫 줄만 들어가고 서기 지시문(기술문서 서기)에는 모두 들어간다
- 바깥 링크 줄에 `[code:bridge/notion.py]`와 `(11-20 사용자)`를 붙였다. 줄 꼴이 마음에 안 들면 알려 주기를 바란다

## 11-20 사용자 답으로 고침

- 바깥 링크 줄의 까닭을 「노션 글은 저장소 없이 혼자 읽혀야 하고, 포트폴리오를 보는 사람은 저장소를 함께 보지 않는다」로 바꾸고, 비공개 시절 404 이야기와 「까닭은 기록에 없다」를 뺐다(위 1절 넷째 항목과 「사람이 정할 것」의 줄 꼴 물음은 이 답으로 풀림)
