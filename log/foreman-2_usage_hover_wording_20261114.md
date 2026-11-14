# 머리 칩 「한도」 호버 글 다시 쓰기 (foreman-2, 11-14, 관리자 362 일감)

## 한 일
- `bridge/static/js/office.js`의 「What's contributing」 호버 줄을 고쳤다
  - 「CC 제안」 줄(24시간 구간 다섯)을 뺐다
  - 「CC가 본 비중 — 대략 · 이 기기 세션만 · 비중끼리 겹침」과 「지난 24시간 — 서브에이전트 general-purpose 24%」 꼴을 한국말 문장으로 바꿨다. 가운뎃점은 이 글 안에서 쓰지 않는다
- `docs/15_usage.md` 6절 호버 설명을 같은 브랜치에서 고쳤다

## 새 글(실제 값으로 본 것)
```
Claude Code가 어림한 값이고 이 컴퓨터의 세션만 셉니다. 한 요청이 서브에이전트이면서 MCP 서버를 쓰는 것처럼 여러 갈래에 함께 들어가므로 합이 100%가 되지 않습니다
지난 24시간 동안 쓴 양 가운데 약 21%에 서브에이전트(general-purpose)가 들어 있습니다
지난 7일 동안 쓴 양 가운데 약 12%에 서브에이전트(general-purpose)가 들어 있습니다
지난 7일 동안 쓴 양 가운데 약 1%에 MCP 서버(claude.ai Notion)가 들어 있습니다
```
사진: `log/img/usage_hover_20261114.png`(미리보기, office 테마 1366x768)

## 조사 결과: 그 %가 무엇의 비율인가
`claude -p "/usage"` 원문(14일 실행):
```
What's contributing to your usage?
Approximate · sessions on this machine only · shares overlap
Last 24h · 3288 requests · 42 sessions
  ...
  Top subagents: general-purpose 21%
Last 7d · 18843 requests · 168 sessions
  Top subagents: general-purpose 12%
  Top MCP servers: claude.ai Notion 1%
```
- 확인된 것: 대략값, 이 기기 세션만, 비중끼리 겹침(shares overlap). 구간 머리에 요청 수 · 세션 수가 함께 적힌다
- **확인 안 된 것**: 분모가 요청 수인지 토큰인지 사용량 환산인지는 원문에 없다. 그래서 「쓴 양 가운데 약 N%에 … 들어 있습니다」까지만 썼다("서브에이전트에서 나온 몫"처럼 단정하지 않았다)
- 겹침의 까닭 예(한 요청이 서브에이전트이면서 MCP를 씀)는 일감이 준 설명이고 원문에 적힌 것은 아니다. 머리 줄에 「~처럼」 예로만 넣었다

## 설계와 달랐던 점
- 일감은 제안 줄이 `usage.html`에도 있으면 뺀다고 했으나 `usage.html`에는 제안 줄이 없다(`contributing`을 쓰는 곳은 `office.js` 하나). 서버 `parse_contrib`와 그 시험은 그대로 둔다
- 감독실 경고등 호버(`usageTipRows`)는 같은 `lines`를 쓰므로 함께 바뀐다. 5시간 · 주간 · 리셋 줄은 손대지 않았다
- 이름이 둘 이상이면(`a 12%, b 3%`) 한 줄씩 나눈다. 모양을 못 읽으면 원문 그대로 「지난 7일 동안 서브에이전트: …」로 보인다

## 확인
- 미리보기(`bridge.preview` 포트 8277, 시험 뒤 끔)에서 `tools/screen.py --no-term --views hq,foreman` 세 테마 × 여섯 크기: 문제 1건 — site 1024x700w의 `tipAudit` 「낱말 끊김 캐릭터 FOREMAN admin」(`inspector|cicd|designer…`). 캐릭터 툴팁이고 이번에 바꾼 글과 무관해 손대지 않았다. 「한도」 호버는 모든 크기에서 문제 없음
- `node --test tests/js/` 172개 통과. 이 글을 맞대는 시험은 없었다(`parse_contrib` 파이썬 시험은 서버 읽기라 그대로)

## 규칙 위반
규칙 위반 없음. (미리보기 서버는 패널 버튼 대신 같은 `bridge.preview`를 직접 띄웠다가 PID로 끝냈다. `pgrep -f`는 쓰지 않았다)
