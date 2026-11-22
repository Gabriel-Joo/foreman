# 포트폴리오 「합치기 카드와 코더 창」 맞추기 (2026-11-22, 서기 foreman-4)

맞대 본 main 커밋: 34a9cd5

## 축

화면 축이다. 근거: `bridge/static/js/handoff.js`(합치기 카드), `bridge/static/js/coder.js`(코더 창), `bridge/static/js/render.js`(머리 위 표시)가 화면 파일이고, `tools/screen.py`로 찍은 사진이 `portfolio/img/07_merge_*`에 있다.

## 한 일

- 읽은 커밋 33839db 뒤 다루는 곳을 바꾼 커밋 셋을 읽었다
  - 92eae54: `bridge/mergeprep.py`가 세션에 글을 넣었는지 `inject.submitted`로 가린다. 입력 칸이 비었는데 기록이 늦으면 넣은 것으로 보고, 끝내 기록에 없으면 텔레그램으로 바로 알린다. 본문 「누가 승인하나」에 이 판정을 더하고 「세션 패널: 대화와 활동」을 가리켰다
  - 725f781: `render.js`의 빈 대화 표시. 대화 탭 일이라 이 편에는 넣지 않았다(04편이 이미 적음)
  - 3354d11: `handoff.js` 근거 확인 줄의 툴팁 글. 이 편 사진과 본문에 나오지 않는 줄이라 고치지 않았다
- 머리 주석 읽은 커밋을 34a9cd5로 바꿨다
- 첫 사진 캡션의 인용 밖 줄표 하나를 마침표로 바꿨다
- 사진 셋(`07_merge_wait.png`, `07_merge_card.png`, `07_merge_coder.png`)을 열어 봤다. 바뀐 화면 코드가 이 화면에 닿지 않아 다시 쓴다. 비밀값, 토큰, 다른 프로젝트의 민감한 글은 없었다

## 확인

- `tools/docs.py check`: 틀린 것 0, 의심 207(전체 저장소 수)

## 규칙 위반

규칙 위반 없음
