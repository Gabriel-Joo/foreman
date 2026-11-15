# 서기실 포스트잇 머리줄 줄이기 (11-15, foreman-4)

## 한 일
- `bridge/static/js/scribe.js`: 접기 머리줄 「포스트잇 할 일 N」을 「포스트잇 N장」으로 바꿨다(확인 전, 끝난 것 같음 덧붙임은 그대로). 「포스트잇이 쌓였습니다: …」 줄은 그리지 않는다. 쌓임 판정(`pst.nudge`의 경고색)은 그대로 둔다.
- `bridge/static/js/postit.js`: `listHtml`에 `noHead` 선택 인자를 더하고 `html(room, label, {noHead})`로 넘긴다. 서기실만 `noHead: true`로 부르고 머리 탭 창은 기본값이라 「FOREMAN 할 일 N장」이 그대로다. 읽지 못했을 때의 경고는 서기실에서도 한 줄로 남긴다.
- 시험: `tests/js/scribe.test.mjs`를 새 글에 맞추고, 쌓임 줄과 머리줄이 없음을 확인하는 줄을 더했다.

## 확인
- `node --test tests/js/` 207개 통과, `pytest -q` 1039개 통과(화면 말 시험 포함).
- 패널 [미리보기 열기]로 눈으로 보는 확인은 하지 않았다(JS 시험으로 갈음). 관리자가 합친 뒤 화면에서 봐 주기 바란다.
- 화면 말 시험 자료(`tests/data/screen_words.toml`)는 새 이름을 만들지 않아 고치지 않았다.

## 서기 몫
- `docs/12_scribe.md` · `docs/10_office_design.md`에는 이 글이 인용돼 있지 않아 고칠 것이 없다. `docs/operations.md` · `style_guide.md`도 해당 없음.

## 규칙 위반 없음
