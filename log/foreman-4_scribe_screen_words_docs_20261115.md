# 서기 · 화면 말 시험 문서에 적기 (11-15, 관리자 410 일감)

## 한 일

- `docs/operations.md` 「3. 돌리기 · 확인」: 「브리지 주소」 줄 아래에 한 줄. pytest 끝 요약의 「화면 말 시험: 서기 몫 N줄 남음 …」이 무엇인지, 0이 아니면 서기가 두 문서를 맞추고 `[[scribe]]` 줄을 지운다, 상세 `docs/11_worktree.md` 「8.」
- `docs/style_guide.md` 「4-1. 화면 글」: 화면 말 표 아래에 한 줄. 화면 말을 바꾸면 같은 브랜치에서 `tests/data/screen_words.toml` `[[rename]]`에 한 줄
- `docs/style_guide.md` 「세션 화면」 줄: 「사용자가 정한다」를 지금 모습으로 고침. 코드(`bridge/static/js/ccscreen.js` `showSize`)의 머리줄 크기 글은 `Claude Code 창 ${…}`(예: 「Claude Code 창 109×37」)이라, 전에는 「세션 창 109×37」이었고 `1f08ac5`에서 바뀌었다고 적음

## 확인

- `.venv/bin/python -m pytest -q tests/test_screen_words.py` 16 passed, 요약 「서기 몫 0줄 남음」

## 설계와 달랐던 점

- 시험 줄(`operations.md` 28줄 「시험」 표 칸)은 한 칸이 이미 아주 길어, 새 줄은 「3.」 아래 시험 DB 묶음 바로 위의 독립 글머리로 두었다

## 규칙 위반

규칙 위반 없음.
