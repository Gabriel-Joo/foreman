# 머리 칩 「한도」 호버 비중 줄 묶기 (foreman-3, 11-14, 관리자 362 일감)

## 한 일
- `bridge/static/js/office.js`: 비중 줄 말투를 「서브에이전트(general-purpose)가 약 12%를 썼습니다」로 바꾸고, 같은 기간은 머리 한 줄 「지난 7일 동안 쓴 양 가운데」 아래에 항목을 나란히 적었다
- 들여쓰기: 항목 줄 앞에 빈칸 둘을 달아 보내면 `bridge/static/js/tip.js`의 `textTip`이 그 줄에 `.sub`를 붙이고, `bridge/static/css/panel.css`가 한 칸 더 들여 쓴다. 기호는 쓰지 않았고 가운뎃점도 없다
- `docs/15_usage.md` 6절 호버 설명을 같은 브랜치에서 고쳤다

## 새 글(미리보기 실제 값)
```
지난 24시간 동안 쓴 양 가운데
  서브에이전트(general-purpose)가 약 17%를 썼습니다
지난 7일 동안 쓴 양 가운데
  서브에이전트(general-purpose)가 약 12%를 썼습니다
  MCP 서버(claude.ai Notion)가 약 1%를 썼습니다
```
사진: `log/img/usage_hover_group_20261114.png`(office 테마 1366x768)

## 설계와 달랐던 점
- 일감은 `office.js` 둘레만 맡겼지만, 들여쓰기를 보이게 하려면 `tip.js`와 `panel.css`에 몇 줄이 필요했다. 툴팁 숫자 줄은 앞 공백을 `trim`으로 지우고 이어지는 줄만 들여 쓰는 구조였기 때문이다. 다른 툴팁은 앞 빈칸 둘로 시작하는 줄이 없어 영향이 없다
- 감독실 경고등 호버는 같은 `lines`를 써서 함께 바뀐다(`usageTipRows`는 손대지 않음)
- 줄이 길어 이어지는 줄은 원래의 걸어 둔 들여쓰기(1칸)로 이어져, 항목 줄(2칸)과는 구분된다

## 확인
- 미리보기(`bridge.preview` 포트 8278, 끝난 뒤 PID로 끔)에서 `tools/screen.py --no-term --views hq,foreman` 세 테마 × 여섯 크기 × 패널 둘: 문제 0건(`tipAudit` 0 포함)
- `node --test tests/js/`: 172개 통과(이 글을 맞대는 시험은 없음)

## 규칙 위반
규칙 위반 없음. (`pgrep -f`는 쓰지 않았고 파일은 Edit · Write로만 고쳤다. 사진용 임시 스크립트는 Write로 scratchpad에 두었다)
