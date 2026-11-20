# 포트폴리오 「출하 라인」 고쳐 쓰기 (2026-11-20, foreman-4 서기)

규칙 위반 없음

맞대 본 main 커밋: `0e40185`

## 축

화면 축. 근거: `bridge/static/js/office.js`, `bridge/static/js/grid.js`가 출하 라인을 그리고, `portfolio/img/03_pipeline_*` 다섯 장을 `tools/screen.py`로 찍은 화면이 있다. 묶음의 다른 편도 화면 축이다.

## 한 일

- 읽은 커밋(`5e0f7c5`) 뒤 다루는 곳을 바꾼 커밋 둘(`b6aebf9`, `2203c57`)은 둘 다 주석만 바꿨다(README 가리킴을 `docs/00_design.md`로, 서기실 주석). 동작이 바뀐 곳은 없다
- 원고의 숫자(20초, 3분, 17분, 35분, 1분, 3번, 5번, 10분, 30분, 2시간, 30분 머무름)와 화면 글(「🔥 파이프라인 실패 · …」, 「⏸ 배포 대기: …」, 「⚠ 빌드 알림 늦음/없음/끊김 의심」, NO_SHIP 두 줄, 테마 이름)을 `config/pipeline.toml`, `bridge/static/js/office.js`, 테마 `theme.json`과 맞대 봤다. 모두 맞았다
- 틀린 곳 하나: 원고가 「세 곳(Jenkins, Harbor, ArgoCD)이 보내는 알림을 꿴다」고 썼는데, Harbor는 FOREMAN으로 알림을 보내지 않고 ② 이미지 칸은 Jenkins의 「빌드·push」 단계에서 미루어 그린다(`bridge/static/js/shipstate.js`, `notion/12_pipeline.md` 5-2). 머리 문단과 「커밋 하나로 잇는다」 절을 고치고, 이미지 칸을 그리는 기준을 한 문단 더했다. 「문서만 바뀐 빌드」는 런슈즈 Jenkinsfile 규칙이라 런슈즈로 범위를 좁혔다
- 다루는 곳에 `bridge/static/js/shipstate.js`를 더했다(이 편이 이제 그 판정을 설명한다)
- 빌드 알림 없음 사진 캡션의 em dash를 문장으로 바꿨다
- 사진 다섯 장은 오늘 다시 찍힌 것(`0ba3538`)이고 열어 보니 지금 화면과 맞아 그대로 썼다. 새로 찍지 않았다

## 확인

- `tools/docs.py check`: 틀린 것 0, 이 편에 걸린 의심 없음
- 원고에서 뺀 말 없음(줄이거나 옮긴 문장 없음)
