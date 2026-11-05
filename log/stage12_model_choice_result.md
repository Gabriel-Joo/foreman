# 12 준비 — 세션 모델 고르기 · 모델별 토큰 결과 (2026-11-05)

서기(12단계)를 만들기 전에 넣었다(사용자 결정). 서기가 일감마다 모델을 고르려면 어차피 필요하고, Opus를 어디서 쓰는지 보여야 한다는 요청.

## 한 일

- **설정** `config/models.toml`
  - 고를 수 있는 모델: opus · sonnet · haiku. `claude --model` 별칭이라 CC가 그때의 최신으로 푼다
  - 역할별 기본값: coder opus · inspector sonnet · cicd sonnet · scribe opus
  - 읽는 코드 `bridge/model_choice.py`
    - 목록에 없는 id · 셸에 못 넣는 id는 버린다
    - 고른 값이 목록에 없으면 역할 기본값, 그것도 없으면 `--model` 없이 띄운다(CC 설정)
- **띄우기** `handoff.spawn_new(model=…)`
  - `claude --model <id>`로 띄운다. 고른 값은 새 칸 `character_session.model`에 남긴다(0019)
  - 목록에 없는 모델을 API로 보내면 거부한다
  - 세션 패널의 [새로 띄우기]는 원래 세션의 역할 · 모델을 이어받는다
- **화면**
  - [+ 세션] 직접 고르기에 역할 · 모델 칸을 더했다
  - 포먼 계획 카드에 모델 칸을 더했다. 포먼(LLM)은 모델을 고르지 않고, 브리지가 `check()`에서 역할 기본값을 채운다
  - 두 곳 다 역할을 바꾸면 모델이 그 역할의 기본값으로 따라간다. 사람이 모델을 직접 고른 뒤에는 따라가지 않는다(`js/modelpick.js`)
- **지금 모델 표시**
  - 대시보드 API: 세션마다 `model`(본 대화의 마지막 응답 — `/model`로 바꾸면 따라간다) · `model_req`(띄울 때 고른 것) · `tokens.by_model`
  - 패널 머리줄에 모델 표시. Opus는 금색, Sonnet은 파랑, Haiku는 초록
  - [세션] 탭: "모델" 줄과 "모델별" 표(출력 · 입력 · 오늘 출력)
  - 방 배지: "Opus 출력 N (서브에이전트 포함 M%)", 전부 Opus면 "오늘은 전부 Opus"

## 조사 결과

- 실제로 쓴 모델은 이미 응답마다 `message.model`에 있었다
  - DB 전체: opus-5-5 18,383 · opus-4-8 178 · haiku-5-5 104 · `<synthetic>` 5
  - Haiku는 CC 내부 호출(제목 붙이기 등)로 보인다. 띄울 때 고른 적은 없다
  - `<synthetic>`(CC가 만든 가짜 응답)은 모델별 집계에서 뺐다
- 서브에이전트 토큰은 `subagent_run`의 합이 `message`에서 나온다(조립기가 다시 더한다). 모델별은 `message`만 묶어 두 번 세지 않는다
  - 방 배지의 "오늘 출력"은 본 대화만 센다. 그래서 Opus 비율은 모델별 합끼리 낸다(서브에이전트 포함이라고 적었다)
- 지금 세션은 모두 Opus 5.5다. 이 세션(158)은 Opus 출력 300만 · Haiku 1.2만이다

## 확인

- 시험: Python 376(모델 고르기 4개 추가), JS 32
- 헤드리스
  - 패널 머리줄에 "Opus 5.5"가 보이고, [세션] 탭에 모델별 표가 나온다
  - [+ 세션]에서 역할을 점검으로 바꾸면 Sonnet으로 따라간다. Haiku를 직접 고른 뒤 역할을 바꾸면 Haiku가 남는다
- 실제로 띄우기
  - 스크래치패드 폴더에서 점검 역할로 띄웠다 → `claude --model sonnet`, 화면 "Sonnet 5.5 · Claude Max", DB 행 role inspector · model sonnet
  - 끝내기 API로 닫고 그 행(183)은 숨김(test)으로 표시했다

## 설계와 달랐던 점 · 판단 근거

- 역할 기본값 중 점검 · CI/CD를 Sonnet으로 정한 것은 이번에 처음 정한 값이다. 지금까지는 모든 세션이 CC 설정(Opus)으로 떴다. `config/models.toml`에서 바꾼다
- 살아 있는 세션의 모델을 화면에서 바꾸는 칸은 만들지 않았다(요청은 "보이게"까지). 필요하면 입력 주입으로 `/model`을 보내면 된다
- 이 과정에서 실수가 있었다
  - 처음에 새 모듈을 `bridge/models.py`로 썼는데, 같은 이름의 기존 파일(DB 값 목록)을 덮었다
  - 바로 `git restore`로 되돌렸다. 커밋 전이라 잃은 것은 없다
  - 새 모듈은 `bridge/model_choice.py`로 옮겼다
