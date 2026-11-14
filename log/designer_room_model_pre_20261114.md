# 머리줄 「작업방」과 응답 전 모델 표시 (2026-11-14, `cc/foreman-2-2`, 세션 406)

관리자 362 일감(사용자 지시 11-14). 화면 글만 고쳤고 기능 · 서버는 건드리지 않았다.

## 1. 「따로 작업」을 「작업방」으로

머리줄 셋째 줄 글자가 호버만 작업방이고 바깥은 「따로 작업 foreman-2」였다. 같은 말이 남은 화면 글을 `grep -rn '따로 작업' bridge/static/`로 모두 찾아 바꿨다(주석 · 데모 견본 글은 그대로).

| 파일 | 전 | 뒤 |
|---|---|---|
| `render.js` `sessionSub` (머리줄 · 세션 목록 아래 줄) | 따로 작업 foreman-2 | 작업방 foreman-2 |
| `render.js` 「합치기 기다림」 말풍선 호버 | 일을 마친 따로 작업의 합치기 카드가 | 일을 마친 작업방의 합치기 카드가 |
| `handoff.js` 합치기 카드 브랜치 칩 호버 | 합칠 따로 작업 브랜치입니다 | 합칠 작업방 브랜치입니다 |
| `handoff.js` 작업방 칸 오류 줄 이름표 | 따로 작업 | 작업방 |
| `handoff.js` 합치기 확인 창 주의 줄 | 「따로 작업」의 「자세히」 | 「작업방」의 「자세히」 |
| `handoff.js` 끝내기 확인 창 주의 줄 | 따로 작업(브랜치)에 커밋 안 된 변경이 | 작업방(브랜치)에 … |
| `scribe.js` [세션 열기] 호버 | 「따로 작업」에서 diff를 | 「작업방」에서 diff를 |
| `office.js` 상단 [합치기 대기] 호버 | 일을 마친 따로 작업 N건이 | 일을 마친 작업방 N건이 |
| `tests/js/role_label.test.mjs` | 따로 작업 foreman-N 세 곳 | 작업방 foreman-N |

- 일감이 가리킨 곳은 머리줄 · 칩 · 배지 · 이름표(위 표 앞 두 줄과 브랜치 칩)이고, 확인 창 · 호버의 같은 낱말도 한 말로 맞추려고 같이 바꿨다. 범위를 넓게 읽었으니 좁혀야 하면 알려 달라
- 남은 곳: `opanel.js:103` · `handoff.js:456` 주석, `demo/move_choose.json` 견본 글(CLAUDE.md 절 이름 인용)

## 2. 응답 전에는 고른 모델

- 원인: 모델 칸은 마지막 응답의 모델(`s.model`)만 읽어, 응답이 없는 세션(405)은 「모델」만 떴다. 405는 `claude-sonnet-5-5`로 띄웠다(DB `character_session.model`)
- 고친 것(`render.js` `modelChip`): 응답이 없고 대시보드의 `model_req`가 있으면 그 값을 같은 이름 꼴로 보인다(`claude-sonnet-5-5` → 「Sonnet 5.5」, 옛 별칭 `opus` → 「Opus」). 이름 꼴 바꾸기는 서버 `model_choice.label`과 같은 식을 화면에 옮겼다(`pickedLabel` · `pickedFamily`)
- 구분: 칩 테두리 점선(`panel.css` `.mdl-pre`), 호버 「모델 — 띄울 때 고른 모델입니다. 첫 응답이 오면 실제로 쓴 모델로 바뀝니다.」. 응답이 오면 전처럼 실제 모델 · 실선. 「· 고른 것 …」 나란히 보이기는 하지 않았다
- 서버는 안 고쳤다. `model_req`가 이미 `/api/dashboard` 응답에 있었다(405: `claude-sonnet-5-5`, 옛 세션은 `sonnet` · `opus` 별칭)
- 세션 정보 「모델」 줄도 같은 `modelChip`이라 같이 바뀐다
- 시험: `now_doing.test.mjs`에 응답 전 고른 모델(이름 · 점선 · 호버) · 응답 뒤 실제 모델 · 둘 다 없으면 빈 글

## 확인

- `node --test tests/js/` 190 통과
- 미리보기(:8200, `POST /api/sessions/406/preview`)에서 `tools/screen.py --no-term --session 406` 세 테마 × 여섯 크기 18판 문제 0건(tipAudit 0/289). 응답 전 세션 405는 마법학교 1920 두 폭 문제 0건(0/290)
- 사진(`log/img/`):
  - 전(:8000, 옛 코드) `designer_head_room_before_20261114.png`: 머리줄 「따로 작업 …」
  - 뒤(:8200) `designer_head_room_after_20261114.png`: 머리줄 「작업방 foreman-2-2」, 모델 칩 실선
  - 응답 전 세션 405 `designer_model_prereply_405_20261114.png`: 「작업방 foreman-2 · [Sonnet 5.5]」 점선 칩(전에는 「모델」). 405에는 키를 보내지 않았다(보기만)

## 규칙 위반

- **영어 진행 글 한 번**: 모델 칸을 고치기 직전 도구 호출 사이에 영어 한 줄(「Now the handoff.js texts and the model chip.」)을 썼다. 훅이 알려 준 뒤 바로 한국어로 돌아와 다음 글부터 지켰다
- 그 밖에 없음(Edit · Write로만 고침, `pgrep -f` · heredoc 커밋 없음, 405에 키 안 보냄)
