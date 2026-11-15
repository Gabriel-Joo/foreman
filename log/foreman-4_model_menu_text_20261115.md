# 모델 고르기 창 글 고침 (11-15, cc/foreman-4, 관리자 410 일감)

## 한 일

패널 머리줄 모델 칩을 누르면 뜨는 창(`bridge/static/js/modelpick.js` `modelMenuHtml`)의 마지막 글을 사용자 글 그대로 두 문단으로 바꿨다. 기능은 그대로다.

- 문단 1: 다른 세션은 바뀌지 않습니다. 이 세션이 이어지는 동안에는 바꾼 모델을 씁니다. 브리지가 다시 뜰 때, 새 세션으로 옮기거나 이어서 띄우면 바뀐 모델이 적용됩니다.
- 문단 2: [+ 세션]으로 따로 띄우는 세션은 이 값을 따르지 않습니다.
- 두 문단 모두 창의 기존 글 꼴(`small muted`) 한 줄씩이다. 글에 em dash와 가운뎃점은 없다.
- 같은 글이 다른 곳(호버, 다른 창, 서버 거부 사유)에는 없었다. 코드에서 옛 글은 이 한 곳뿐이었다.

## 같이 고친 것

- `tests/js/modelmenu.test.mjs`: 옛 글을 찾던 검사를 새 글(두 문단, 둘 사이 나눔)로 바꾸고 옛 글이 없음을 확인
- `docs/10_office_design.md` 「패널 모델 창」 글 목록의 해당 줄: 새 두 문단으로 맞춤(옛 한 줄 글은 이력으로 남김)
- `tests/data/screen_words.toml`: 바꾼 이름 한 줄 추가

## 설계와 달랐던 점

`screen_words.toml`의 새 줄은 `scope = "화면"`(코드만 봄)으로 두었다. 「화면과 문서 인용」으로 하면 아직 옛 글을 인용 중인 `docs/style_guide.md` 4-1이 걸려 시험이 실패한다. 일감이 그 파일을 관리자 몫으로 남겼기 때문이다.

## 관리자가 할 것

- `docs/style_guide.md` 89줄(4-1) 「이 세션만 바뀝니다. 브리지가 다시 떠도, …바꾼 모델을 그대로 씁니다.」 인용을 새 글에 맞춘다
- 맞춘 뒤 `tests/data/screen_words.toml`의 새 줄(`old = "이 세션만 바뀝니다. 브리지가 다시 떠도"`) `scope`를 「화면과 문서 인용」으로 올린다
- `log/foreman-3_model_menu_20261114.md` 41줄은 11-14 기록이라 그대로 두었다

## 확인

- `node --test tests/js/`: 200개 통과, 실패 0
- `.venv/bin/python -m pytest -q tests/test_screen_words.py`: 16개 통과
- 미리보기(포트 8200, 세션 433)에서 모델 창을 연 사진: 창 너비 안에서 문단 둘이 줄바꿈되고 넘치거나 낱말이 끊기지 않았다. 사진 `/tmp/claude-1000/-home-kopo17-AI-programming-foreman--worktrees-foreman-4/77460084-fe9f-4d2c-a0d0-f019f7d58f57/scratchpad/shots/office_1440x900w_hq.png`
- `tools/screen.py --no-term` 세 테마(office · site · magic) 크기 여섯 × 패널 둘: 문제 0건(`scratchpad/shots3/report.json`)
- 미리보기는 `DELETE /api/sessions/433/preview`로 껐다. 서브에이전트 · 예약은 쓰지 않았다

## 규칙 위반

한 번 있었다. 11-15 미리보기를 띄우기 직전에 도구 호출 사이의 진행 글 한 번이 영어로 나갔다(「Next is the preview and the screen check…」). 이어서 훅이 알려 준 뒤로는 모두 한국어로 썼다. 그 밖의 위반은 없다(파일은 Edit · Write로만 고쳤고 `pgrep -f`와 heredoc도 쓰지 않았다).
