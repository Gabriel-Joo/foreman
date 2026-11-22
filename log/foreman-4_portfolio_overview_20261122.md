# 포트폴리오 「한눈에 보는 FOREMAN」 맞대 읽기 (foreman-4, 2026-11-22)

맞대 본 main 커밋: 1402e3d. 규칙 위반 없음.

## 한 일

- `portfolio/00_overview.md` 머리 주석의 읽은 커밋을 9e24a8f에서 1402e3d로 올렸다. 본문과 사진은 바꾸지 않았다.

## 축

화면 축. 근거: `bridge/static/office.html`, `bridge/static/js/office.js`, `bridge/static/js/opanel.js`가 화면 파일이고 `tools/screen.py`로 찍는다. 이 편은 이미 화면 축으로 쓰여 있다.

## 조사 결과

- 읽은 커밋 뒤 다루는 곳을 바꾼 커밋은 725f781, 92eae54 둘이고 둘 다 `bridge/static/js/opanel.js`만 두 줄 바꿨다. 하나는 대화 칸이 비었을 때 「불러오는 중」 대신 `convoHtml`이 빈 상태, 불러오는 중, 실패를 가르게 한 것, 다른 하나는 제출 확인 중(pending)인 입력 결과를 150초 남기는 것이다. 이 편은 패널을 탭과 입력 칸 수준으로만 말하고 그 세부는 「세션 패널: 대화와 활동」 편 몫이라(725f781이 그 편을 이미 고쳤다) 본문에 걸리는 곳이 없다.
- 본문의 화면 글을 코드와 맞대 봤다: 탭 [⌂] [전체] [+ 세션] [포스트잇], 「작업 N」, [가−] [가+], 패널 탭 대화, 활동, 세션 정리(`opanel.js` TABS), [세션 화면 ↗], [▲ 셸](`terminal.js`), 「아직 안 본 물음」, 출하 라인 없는 방의 「<테마 출하 이름> 없음」 이름표(`office.js`), 적재 막힘 300초(`bridge/config.py` `ingest_alert_s`). 모두 지금 코드와 같다.
- 사진 `00_overview_screen.png`, `00_overview_map.png`를 열어 봤다. 머리줄, 방, 패널 모양이 지금 코드와 같아 다시 찍지 않았다. 비밀값, 토큰, 다른 프로젝트의 민감한 글은 없다.
