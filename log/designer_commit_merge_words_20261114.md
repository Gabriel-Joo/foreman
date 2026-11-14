# 화면 글 「저장」 · 「붙이기」를 커밋 · 합치기로 되돌림 (2026-11-14, `cc/foreman-2`)

관리자 362 일감(사용자 결정 11-14: 「커밋, 합치기, 브랜치는 화면에도 그대로 쓴다. worktree만 작업방으로 한다」). 보이는 글만 고쳤고 기능은 건드리지 않았다.

## 바뀐 곳

| 파일 | 전 | 뒤 |
|---|---|---|
| `bridge/static/js/handoff.js` `END_ITEMS` | 고친 것을 main에 붙이고 끝냅니다 | 고친 것을 main에 합치고 끝냅니다 |
| 같은 곳 | 작업방에 저장만 해두고 끝냅니다 | 작업방에 커밋만 해두고 끝냅니다 |
| `handoff.js` 쉬는 중 호버 | 지금까지를 작업방에 저장하고 세션만 끝냈습니다 | 지금까지를 작업방에 커밋하고 세션만 끝냈습니다 |
| `handoff.js` 이미 원본에 들어 있음 호버 | [합치기]는 worktree와 브랜치만 지웁니다 | [합치기]는 작업방과 브랜치만 지웁니다 |
| `handoff.js` [이어서] 호버 | 같은 worktree에서 | 같은 작업방에서 |
| `handoff.js` [합치기] 호버 | 합치고 worktree를 지웁니다 | 합치고 작업방을 지웁니다 |
| `handoff.js` [버리기] 호버 | worktree와 브랜치를 지웁니다 | 작업방과 브랜치를 지웁니다 |
| `tests/js/handoff_flow.test.mjs` | 저장만 해두고 맞대기 | 커밋만 해두고 맞대기 |
| `docs/11_worktree.md` 메뉴 표 두 줄 | 붙이고 / 저장만 | 합치고 / 커밋만 |

- `grep '저장\|붙이' bridge/static/`로 다시 훑었다. 남은 것은 모두 원래 다른 뜻이다(토큰 저장 · 설정 저장 · 「제목 붙이기」 · 「위에 붙이기」 같은 배치 말 · 「git 저장소」). 커밋 뜻으로 쓴 곳은 위가 전부다
- `docs/10_office_design.md`에는 인용한 곳이 없었다. `docs/operations.md` · `docs/style_guide.md`는 건드리지 않았다
- 403 log 본문(`designer_sesstab_end_20261114.md`)은 그날의 기록이라 고치지 않았다. 거기 적힌 「저장 · 붙이기」 표는 이 일로 뒤집힌 것이다
- 메뉴 이름 · 버튼 · 확인 창 글은 그대로다. 확인 창과 화면 글의 worktree 낱말 중 이 탭 밖(포먼 채팅 [따로 작업(worktree)] · 코더 칸 · 서기 · 사무실 잠금 안내 · 확인 창)은 일감 범위 밖이라 남겼다. 바꿀지는 관리자가 정한다

## 확인

- `node --test tests/js/` 189 통과
- `tools/screen.py` 세 테마 점검은 못 했다. 미리보기(:8200)가 떠 있지 않았고, 이 일은 글자 몇 개만 바꿔 레이아웃 변화가 없다. 필요하면 미리보기를 열어 달라고 하면 돌린다

## 화면 점검(미리보기 8200, 첫 일)

`POST /api/sessions/404/preview`로 띄우고(토큰은 셸 변수로만) `tools/screen.py --base http://127.0.0.1:8200/ --no-term --session 404`: 세 테마 × 여섯 크기 18판 모두 문제 0건(tipAudit 0/285~299, 페이지 오류 0, 방 자리 같음).

## 이어서: 화면의 worktree를 모두 「작업방」으로 (사용자 답 11-14)

「화면에 보이는 worktree는 전부 작업방으로. 코드 · 문서는 worktree 그대로.」 따로 작업(worktree)이던 칸 이름은 「작업방」으로 줄였다.

| 파일 | 전 | 뒤 |
|---|---|---|
| `foremanchat.js` | 따로 작업(worktree) 체크 · 요약 · 자세히 호버 · 두 번째 체크, 호버 「따로 작업 —」, 띄운 뒤 결과 「따로 작업 …에서 합니다」 | 작업방 · 「작업방 —」 · 「작업방 …에서 합니다」 |
| `handoff.js` | 관리자 호버 「따로 작업(worktree)이 아니라」, 「따로 작업에서 뜹니다」 · 「…따로 작업(worktree)에서 뜹니다」, 확인 창 「worktree는 남습니다」 · 「worktree와 브랜치」 | 작업방 |
| `scribe.js` | 따로 작업(worktree) 세 곳(버튼 호버 · 설명 줄 · 확인 창) | 작업방 |
| `coder.js` | 빈 worktree 여섯 곳(안내 · 머리 · 호버 · 버리기 호버 · 확인 창 · 결과) | 빈 작업방 |
| `office.js` | 잠금 안내 · 풀기 확인 창의 「worktree 이름」 | 작업방 |
| `render.js` `worktreeTip` | 「따로 작업 — foreman-2(…)」 | 「작업방 — …」(시험 `now_doing.test.mjs`도) |
| `approvals.py` · `schemalock.py` | 알림(텔레그램) 「worktree 이름」 | 작업방 |
| `coder_room.py` | 어긋난 까닭 세 곳 | 작업방 |
| `reconcile.py` | 어긋남 글 일곱 곳 | 작업방 |
| `handoff.py` | 거부 사유 · 결과 글 아홉 곳(관리자 · 맨 위 폴더 · 끝내기 · 버리기 · 쉬게 하기 결과 · 없음 등) · 포인터 글 두 곳 | 작업방 |
| `api/handoff.py` · `mergeprep.py` · `worktree.py` · `previews.py` · `foreman.py` | 거부 사유 · 결과 글 · 계획 요약 「· 따로 작업」 | 작업방 |
| `handover.py` | 인계 줄 「· 따로 작업」 | 작업방 |

- **그대로 둔 것**: 주석 · 변수 · API 경로 · CSS · 데이터 이름(`worktree` 필드), docs · log. `demo/*.json` 견본 글. 그리고 **모델에게 가는 글**: 역할 막음 `roleguard.py`(「worktree 세션은 커밋만…」), 인계 · 서기 안내문(`handoff.py` 「따로 작업(worktree) …」, `handoff_state.py`, `scribe_room.py`, `foreman.py` 계획 안내). 세션이 읽는 글이라 CC가 아는 말로 둔 것이고, 사람 화면 글이 아니다. 바꿀지는 정해 주세요
- 시험이 화면 글을 맞대는 곳은 `now_doing.test.mjs` 하나뿐이었다(고침). pytest는 맞대는 곳이 없었다

## 확인(이어서)

- `node --test tests/js/` 189 통과. `pytest -q tests` 958 통과(157초)
- 미리보기에서 `tools/screen.py --no-term --session 404` 세 테마 18판 문제 0건

## 규칙 위반

규칙 위반 없음.
