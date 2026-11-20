# 포트폴리오 「알려진 한계」 편 다시 맞춤 (2026-11-20, 서기 foreman-4)

맞대어 본 main 커밋: 2b56124

## 축

한계 편이라 결정으로 묶는다(원고 기준 「한계 편의 꼴」). 묶음 전체 축은 화면 축이다. 근거: `bridge/static/`(화면 html, css, js)과 `tools/screen.py`로 찍을 수 있는 화면이 있다. 이 편에 보일 화면은 없어 사진을 넣지 않았다.

## 한 일

- 읽은 커밋 `c061fd3` 뒤 다루는 곳을 바꾼 커밋은 `2203c57` 하나다. `bridge/inject.py` 주석의 화면 이름(「CC 화면」에서 「세션 화면」으로)만 바꿨다. 동작은 그대로라 본문 사실은 고칠 것이 없었다
- 본문 사실을 코드와 맞대 봤다: 승인 카드 대기 3600초(`config/approval.toml` `wait_s`), 프로젝트별 mode(runshoes, petmint observe, foreman, ronanlab-infra enforce), `!` 명령의 sudo 막음(`bridge/inject.py`), 사용량 하한(`bridge/usage.py`), 텔레그램은 답을 받지 않음(`bridge/`에 받는 코드 없음). 모두 맞다
- 5절 치른 값의 「(기본 120일)」을 고쳤다. Claude Code 기본값은 30일이고 120일은 서버 설정으로 늘린 값이다(`docs/00_design.md`). 근거 표시를 달았다
- 머리 주석 읽은 커밋을 `2b56124`로 바꿨다
- `tools/docs.py check` 틀린 것 0

## 규칙 위반

규칙 위반 없음.
