# 덮을 편이 없다는 글이 사정과 다르던 것, 원고 기준 F5 줄 (11-19, 코더 foreman-4, 관리자 410 일감)

브랜치 `cc/foreman-4`. 커밋만 했고 push와 브리지 다시 띄우기는 하지 않았다.

## 1. 「덮을 편이 없습니다」 글을 두 사정으로 가름

고장: 멈춤 수는 있는데 덮기 단추가 없을 때 화면은 늘 「지금 덮을 편이 없습니다. 그 뒤 git이 다시 바뀌었거나 이미 맞춰졌습니다」를 썼다. 옛 브리지가 `@docs-held/` 행을 남기지 않아 목록 자체를 모르는 경우에도 같은 글이 떴다(펫퍼민트 멈춤 5).

- 서버: `docsync.held_list_missing(summ, last, held_error)`가 멈춘 수 N을 주거나 None을 준다. 멈춘 수가 있고, 목록을 못 읽은 것이 아니고(`held_error` 없음), `last_for`가 돌려준 결과에 멈춘 편이 하나도 없으면 N이다. `scribe_room.todo`가 이것을 `docs_pub.held_list_missing`으로 내린다.
- 화면: `scribe.js heldRows`가 `held_list_missing`이 있으면 「멈춘 N편의 목록이 아직 없습니다. 다음 맞추기 뒤에 보입니다.」(사용자 문장 그대로). 없으면 지금 글 그대로다.
- (나)의 글이 정말 그 사정에서만 뜨는지: 단추 없음, 목록 못 읽음 아님, 목록 없음 아님이 겹칠 때만 남으므로 「목록은 있는데 덮을 편 0」에서만 뜬다. 시험으로 확인했다.
- 덮기 단추는 한 곳(기술문서 게시 줄 아래)만 둔다. 「할 일」 안에 다시 두지 않았다.
- 가름의 한계: 행이 전부 `released`인데 `@docs-last`가 멈춤 N을 말하는 경우도 「목록 없음」으로 가른다(행 중 `held`만 목록으로 치기 때문). 새 브리지는 행을 풀 때 `@docs-last`도 새로 쓰므로 그 어긋남은 생기기 어렵다고 보지만, 돌려 보지는 않았다.

## 2. 원고 기준 F5 줄

`docs/manuscript_rules.md` 5절 「… 둘을 섞지 않는다」 바로 다음 줄을 「다만 한계 편은 결정으로 묶는다. 화면으로 나눌 수 없기 때문이다(11-19 사용자).」로 바꿨다. 줄 꼴(목록 표시)은 그대로다. 커밋은 따로 했다.

## 시험, 문서

- 새 파이썬 시험 `tests/test_docsync_held_restart.py`의 `test_held_list_missing_tells_two_cases_apart`: 행 없음이면 N, 행 있고 덮을 편 0이면 None, 멈춤 0 · 기록 없음 · 못 읽음이면 None.
- 새 node 시험 `tests/js/scribe_held.test.mjs`: 목록 없음 글, 그때 「덮을 편이 없습니다」가 안 뜸, `held_list_missing`이 null이면 지금 글, 단추가 있으면 단추가 먼저.
- 결과: pytest 1438 통과(문서를 고치기 전에 돌렸고 이 일의 시험은 들어 있다), node 244 통과, `tools/docs.py check` 틀린 것 0(「요약을 찾지 못한 문서 2개」 알림은 전부터 있던 것), `tools/docs.py readme` 같음. 실제 화면은 보지 못했다(시험만 통과했다).
- 고친 문서: `docs/12_scribe.md`(덮기 단추 자리의 까닭 셋), `notion/10_scribe/04_notion.md`(멈춘 뒤 절), `notion/10_scribe/01_room.md`(기술문서 게시 아래 덮기 줄). `refs --range main...HEAD --unfixed`에 남는 것은 `docs/manuscript_rules.md`를 가리키는 다른 문단들이고, 그 문단들은 5절의 한 줄 문구만 바뀌어 지금 내용과 맞아 그대로 뒀다.
- 화면 말을 바꾼 이름은 없어(새 글 하나 추가) `tests/data/screen_words.toml`은 그대로다.

## 옮겨 가는 한 번

이 코드를 합치고 브리지를 다시 띄워도, 그 프로젝트에서 맞추기나 한 쪽 게시를 한 번 돌리기 전까지는 행이 없어 새 글(목록 없음)이 뜬다. 이것이 의도한 글이다.

## 규칙

위반이 하나 있었다. 시험을 덧붙이려고 Bash heredoc(`cat >> 파일`)으로 `tests/test_docsync_held_restart.py`를 고치려 했다. 자동 모드 검사가 막아 실행되지 않았고 파일은 바뀌지 않았다. 곧바로 Edit으로 같은 시험을 넣었다. 그 밖의 위반은 없다.

## 사람이 정할 것

- 없음. (덮기 단추를 「할 일」 안에 다시 두지 않는다는 결정은 따랐다.)
