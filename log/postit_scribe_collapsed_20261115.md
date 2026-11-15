# 서기실 포스트잇 늘 접힌 채로 (11-15, foreman-4)

사용자 지시: 「서기 화면 갔을때 포스트잇 기본값 접혀있느걸로 해줘」

## 한 일
- `bridge/static/js/scribe.js`: 포스트잇 칸을 `pick === 'postit'`이면 펼치던 길을 없앴다. 이제 `keep`이 기억한 것만 따른다(기본 접힘, 사람이 펼친 것은 그대로 기억).
- `bridge/static/js/office.js`: 서기 캐릭터를 누를 때 `pick: 'postit'`을 넘기던 것을 `pick: null`로 바꿨다. `'postit'` pick은 이곳에서만 만들어졌고, 이제 어디에도 없다(grep 확인).
- 호버 글 두 곳의 끝 「누르면 서기실 포스트잇이 열립니다.」를 「누르면 서기실이 열립니다.」로 고쳤다. 쌓임 표시(머리줄 `warn` 색, 말풍선, 호버 앞부분)는 그대로다.
- `tests/js/scribe.test.mjs`: pick `'postit'`을 넘겨도 포스트잇이 접혀 있음을 보는 줄을 더했다.

## 동작이 바뀌는 곳
- 「할 일」 칸(`pick && pick !== 'postit'`을 `pick`으로): `'postit'` pick은 이제 없으므로 조건이 줄었을 뿐 동작은 같다. 포스트잇 pick일 때도 「할 일」은 전에 `keep` 기본(펼침)이었고 지금도 같다. `later` pick은 전처럼 「할 일」을 펼친다.
- 바뀌는 것은 포스트잇이 쌓여 캐릭터를 눌렀을 때 포스트잇이 더는 저절로 펼쳐지지 않는 것 하나다.

## 확인
- `node --test tests/js/` 207개 통과, `pytest -q` 1039개 통과(화면 말 시험 포함).
- 미리보기로 눈 확인은 하지 않았다(JS 시험으로 갈음). 합친 뒤 화면에서 봐 주기 바란다.

## 서기 몫
- `docs/12_scribe.md` · `docs/10_office_design.md`에 이 동작(쌓였을 때 편 채로 열림)을 적은 줄은 없었다(grep). `docs/operations.md` · `style_guide.md`도 해당 없음.

## 규칙 위반 없음
