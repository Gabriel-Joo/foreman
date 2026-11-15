# 잊은 것 찾기 비용 글 한 곳으로 (2026-11-15, `cc/foreman-7`, 포스트잇 #49)

## 한 일

`bridge/static/js/losscheck.js`에 다음 셋을 두었다.

- `LOSS_COST = { prompts: 20, usd: 0.4, min: 1.5 }`: 숫자
- `lossCost(sep = ', ')`: 「내가 보낸 말 20개당 약 0.4달러, 1.5분」을 만든다
- `LOSS_CONFIRM`: 확인 창 글. handoff.js와 opanel.js에 같은 글이 둘 있던 것을 하나로 합쳤다

다섯 곳은 아래처럼 이것을 읽는다.

| 곳 | 읽는 것 |
|---|---|
| `losscheck.js` 버튼 호버 | `lossCost()` |
| `handoff.js` 잊은 것 찾기 확인 창 | `LOSS_CONFIRM` |
| `handoff.js` `startMove` 확인 창 | `찾는 데 ${lossCost()} 걸립니다.` |
| `opanel.js` 압축 띠 호버 | `lossCost(' · ')`. 이 호버만 가운뎃점이라 글을 그대로 두려고 구분자를 받게 했다 |
| `opanel.js` 잊은 것 찾기 확인 창 | `LOSS_CONFIRM` |

- 자리를 고른 까닭: 이 기능의 모듈이고, `handoff.js`가 이미 `losscheck.js`를 읽는다. `opanel.js`는 import 한 줄을 더했다. 새 파일은 만들지 않았다
- 화면 글은 바뀌지 않았다. 다섯 곳 모두 node로 옛 글과 맞대어 보니 같았다

## 실측 계산은 하지 않음 (남은 일)

서버(`bridge/losscheck.py`)는 점검마다 `cost_usd`, `prompts`, 묶음별 `ms`를 저장한다. 하지만 이것으로 계산하기는 몇 줄로 되지 않는다.

- 화면이 받는 것은 마지막 점검 하나(`lc`)뿐이다. `opanel.js` 압축 띠와 확인 창에는 그것조차 없다
- 「20개당」 어림값을 내려면 지난 점검들을 모아 계산하는 서버 쪽 집계와 그것을 내려 주는 길이 새로 필요하다
- 계산값을 쓰면 화면 숫자가 바뀐다. 이번 일감은 화면 글을 바꾸지 않는 것이었다

남은 일: `loss_check` 표에서 끝난 점검의 `sum(cost_usd)/sum(prompts)*20`과 걸린 시간을 집계해 `LOSS_COST`의 기본값을 바꾸는 길. 하게 되면 숫자를 바꿀 곳은 `LOSS_COST` 하나다.

## 시험

- `node --test tests/js/`: 206개 통과. `tests/js/losscheck.test.mjs`에 「잊은 것 찾기 비용, 한 곳에서 만든 글」 시험 하나를 더했다
- `tests/test_screen_words.py`: 16개 통과. 화면 말을 바꾸지 않아 `tests/data/screen_words.toml`은 그대로다
- docs와 시험에 이 문구가 박힌 곳은 없었다(grep). 그래서 docs는 고치지 않았다

## 규칙 위반

규칙 위반 없음.
