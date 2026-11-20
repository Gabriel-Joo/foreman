# 포트폴리오 「교장 계획 창과 감독실」 맞추기 (2026-11-20, foreman-4 서기)

맞대 본 main 커밋: 21428fd. 규칙 위반 없음.

## 축

화면 축. 근거: 이 편이 다루는 화면 코드 `bridge/static/js/foremanchat.js`(계획 카드), `bridge/static/js/fmpanel.js`(교장 패널), `bridge/static/js/office.js`(감독실 현황판)가 있고 `tools/screen.py`로 찍을 수 있다.

## 한 일

- 읽은 커밋 fb7121b 뒤 다루는 곳을 바꾼 커밋 2개(d5ed80d, b6aebf9)를 읽었다. 둘 다 `bridge/foreman.py`, `bridge/wake.py`의 주석과 교장 지시문 속 문서 경로(README → docs/00_design.md, tools/docrefs.py → tools/docs.py refs)만 바꿨고 동작은 그대로다. 원고 본문에 고칠 사실이 없었다.
- 본문 숫자를 코드와 맞대 봤다: 진행 중인 일 2,000토큰(`TOKEN_CAP`), 낡음 3일과 커밋 150개(`config/wake.toml [note]`), 확신도 70%(foremanchat.js), 자동 제안 12시간과 하루 5번(`config/wake.toml`), 관리자에게 넘긴 뒤 15분(`config/managers.toml [handover]`, 켜져 있음). 모두 같다.
- 사진 여섯 장을 열어 봤다. card, hq(11-15), card_more, panel, overlap, wake(11-19)는 그 뒤 감독실과 계획 카드 화면 코드를 바꾼 커밋이 없어 그대로 쓴다. 비밀값이나 다른 프로젝트의 민감한 글은 보이지 않았다.
- 캡션 셋(card, hq, card_more)이 「~다」로 끝나 다른 캡션과 묶음 말투(경어체)가 달라 「~습니다」로 고쳤다. card_more 캡션의 「단추가 잠겨 있다」는 사진에서 [다시 물어보기]가 살아 있어 「[다시 물어보기]만 빼고 잠겨 있습니다」로 좁혔다(foremanchat.js의 `done` 처리와 같다).
- 머리 주석 읽은 커밋을 21428fd로 바꿨다.
- `tools/docs.py check`: 틀린 것 0.

## 옮기거나 줄인 말

없음.
