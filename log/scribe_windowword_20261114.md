# 서기: 「세션 창」 · 「CC 창」 말 겹침 문서 맞춤 (11-14)

관리자 362의 서기 일감(사용자 지시 11-14). 문서만 고쳤다. 코드와 시험과 설정은 그대로다.

## 문제
「CC 화면」을 「세션 화면」으로 바꾸면서(`fcd4b68`, `82faf1f`) 「CC 창」(그 세션의 Claude Code 터미널, tmux 창)까지 「세션 창」으로 바뀐 곳이 있다. 「세션 화면」이 사람이 띄우는 창이고 「세션 창」이 그 안에 보이는 터미널인데 둘 다 「세션」이 들어가 어느 쪽인지 헷갈린다.

## 말 정리
- 그 세션의 Claude Code 터미널(tmux 창, 닫으면 80×24로 돌아가는 것): 「Claude Code 창」
- 사람이 패널 위에 띄우는 창: 「세션 화면」(또는 문맥상 「띄운 창」)

## 고친 것(줄마다 근거: 모두 앞의 말 정리에 따라 뜻이 (b) Claude Code 터미널인 곳)
- `docs/style_guide.md` 화면 말 표 「세션 화면」 줄(117): 「그 세션의 세션 창을 그대로 보고」 → 「Claude Code 창」(사용자가 지목한 줄). 같은 줄 오른쪽 칸 「세션 창의 tmux 그룹 세션」 → 「그 세션의 Claude Code 창(tmux)에 붙는 그룹 세션」
- 같은 줄의 머리줄 글 「세션 창 109×37」은 코드가 지금 그렇게 보여 주므로 인용은 두고, 이 크기가 Claude Code 창 크기라는 것과 글을 바꿀지 사용자가 정한다는 것을 적었다(아래 코드 표)
- `docs/style_guide.md` 4-1(119): 「CC 창이 대화창을 가려」 → 「Claude Code 창이」, 「그중 세션 창의 결정 창」 → 「그 세션의 Claude Code 창에 뜨는 결정 창」. 「대화창」 약속은 그대로
- `docs/operations.md` 73: 「세션의 세션 창(권한 …」 → 「Claude Code 창」. 74: 머리줄 글 「(세션 창 크기)」 → 그 세션의 Claude Code 창 크기이고 띄우는 창 크기가 아니라고 풀었다. 76 「세션 창(tmux)을 띄운 창 크기에」 → 「그 세션의 Claude Code 창(tmux)을 띄운 창(세션 화면) 크기에」
- `docs/10_office_design.md` 261: 「세션이 도는 tmux 창은 『세션 창』이라 쓴다」가 이번 겹침의 뿌리라 「Claude Code 창」 · 「세션 화면」으로 갈라 쓰고 「세션 창」은 쓰지 않는다고 바꿨다. 263 · 266 · 271(둘) · 273 · 275: 같은 뜻의 「세션 창」 · 「CC 창」을 「Claude Code 창」으로, 271은 「띄운 창(세션 화면) 크기」로. 267 머리줄 인용 「세션 창 109×37」은 두고 「(그 세션의 Claude Code 창 크기)」를 붙였다
- `README.md` 896: 「쉬는 세션 창 판정」 → 「쉬는 세션의 Claude Code 창 판정」(`judge_dialog`는 쉬는 세션의 tmux 화면을 본다)
- 남긴 것: README 896의 「CC 끝내기 확인 창」은 Claude Code가 띄우는 결정 창 이름이라 겹침이 아니다. 전 이름을 적은 「CC 화면」 · 「CC 창」(261, operations 73, style_guide 117)도 그대로

## 코드 글 — 사용자가 정할 것(코드는 고치지 않았다)
아래는 모두 뜻이 그 세션의 Claude Code 창(tmux)이다. 제안은 「Claude Code 창」.

| 파일 · 줄 | 지금 글 | 고칠 글 제안 |
|---|---|---|
| `bridge/static/js/ccscreen.js:135` | 머리줄 `세션 창 109×37` | `Claude Code 창 109×37` |
| `bridge/static/js/ccscreen.js:136` | 툴팁 `세션 창 크기 — 이 창 크기에 맞춥니다. …` | `Claude Code 창 크기 — 이 창(세션 화면) 크기에 맞춥니다. …` |
| `bridge/static/js/ccscreen.js:32` | 크기 툴팁 `놓을 때 세션 창도 이 크기로 맞추고` | `놓을 때 Claude Code 창도 이 크기로 맞추고` |
| `bridge/static/js/ccscreen.js:38` | 닫기 툴팁 `세션 화면을 닫습니다. 세션 창은 80×24로 돌아갑니다.` | `… Claude Code 창은 80×24로 돌아갑니다.` |
| `bridge/static/js/opanel.js:37` | `세션 화면 — 이 세션의 세션 창을 띄우는 창으로 봅니다.` | `… 이 세션의 Claude Code 창을 띄우는 창으로 봅니다.` |
| `bridge/api/terminal.py:160` | 거부 사유 `세션 창을 확인하지 못했습니다 — …` | `Claude Code 창을 확인하지 못했습니다 — …` |
| `deploy/shell/foreman-cc-view:29` | `세션 창 대상이 올바르지 않습니다.` | `Claude Code 창 대상이 …` |
| `deploy/shell/foreman-cc-view:32` | `세션 창을 찾지 못했습니다 — 세션이 끝났을 수 있습니다.` | `Claude Code 창을 찾지 못했습니다 — …` |
| `deploy/shell/foreman-cc-view:34` | `세션 창을 찾지 못했습니다.` | `Claude Code 창을 찾지 못했습니다.` |
| `deploy/shell/foreman-cc-view:71` | `세션 창에 붙지 못했습니다.` | `Claude Code 창에 붙지 못했습니다.` |

- 주석(`ccscreen.js:98` 「세션 창도 한 번」)은 화면 글이 아니라 목록에서 뺄 수 있다
- 일감이 말한 `terminal.py`는 「세션 창」이 들어간 줄이 없었다(375가 「세션 화면」으로만 바꿨다). `inject.py`도 「대화창(세션 화면)」이라 겹침이 없다
- 비슷한 말이지만 다른 뜻이라 뺀 것: `bridge/foreman.py:954` · `bridge/api/handoff.py:304` · `bridge/static/js/uiscale.js:8` · `bridge/static/css/panel.css:220`의 「새 세션 창」(+ 새 세션 만드는 창)
- 문서 쪽 인용(위 `머리줄 글`)은 코드를 바꾸면 같이 고친다: `docs/style_guide.md` 117, `docs/operations.md` 74, `docs/10_office_design.md` 267

## 설계와 달랐던 점
- 일감은 문서의 「세션 창」을 (a) 띄우는 창으로 읽히는 곳도 찾으라 했으나, `docs/` · README에는 (a) 뜻으로 쓴 「세션 창」이 없었다. 전부 (b)였다

## 규칙 위반
규칙 위반 없음
