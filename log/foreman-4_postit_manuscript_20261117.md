# 포스트잇 원고를 554 동작에 맞춤 (서기 일감, cc/foreman-4, 2026-11-17)

관리자 410 일감. 사용자는 자리를 비웠고, 판단이 필요한 것은 고치지 않고 맨 끝 「아침에 사람이 정할 것」에 모았다.

## 1. 한 일

554(`da5ceba`)가 포스트잇을 받은 편지함과 TODO 창으로 바꾸고 `notion/10_scribe/02_postit.md`만 고쳤다. 같은 동작을 서술하는데 안 고친 원고를 지금 코드(`bridge/postit.py`, `bridge/scribe_room.py`, `bridge/static/js/postit.js`)에 맞췄다.

| 파일 | 고친 곳 |
|---|---|
| `notion/10_scribe.md` | 14줄 편 표(옛 [→]를 받은 편지함, TODO 창, [TODO로], [한계로]로), 49줄 「알려진 한계 쓰기」 행(고른 편에 까닭과 함께 씀, TODO 항목은 같은 커밋에서 지움, README 생성물 거부 문장 삭제, 맡을 파일 `README.md`, `docs/TODO.md`, 띄울 때 고른 편), 105줄 그림(「[한계로] 보냄」), 115줄 문단. 머리 읽은 커밋 `da5ceba` |
| `notion/10_scribe/01_room.md` | 11줄, 34줄 표(`later` 줄과 맡을 파일), 67줄, 157줄(재료 「쓸 줄」은 [한계로]로 보낸 것, 편과 까닭이 들어감, 편 없는 옛 줄은 쓰지 않음), 155줄 한 낱말, 218줄(세 묶음 한 줄). 머리 읽은 커밋 `da5ceba` |
| `notion/14_screen.md` | 76줄 「할 일 목록인 포스트잇」을 받아 두고 `docs/TODO.md`를 보는 포스트잇으로 |
| `notion/15_db/01_tables.md` | 368줄 `source`에 `todomd`, `closed_reason`에 `todo`를 더하고 `limit`의 뜻을 「고른 편」으로 |
| `portfolio/10_scribe_room.md` | 31줄 표 행 |

## 2. 조사 결과, 고치지 않은 것과 까닭

- 01_room 218줄의 머리줄 「N장, 확인 전 K, 끝난 것 같음 M」은 지금 코드에서도 맞다. `bridge/static/js/scribe.js`는 554에서 바뀌지 않았고 `postit.summary`가 `unconfirmed`와 `likely_done`을 그대로 낸다. 그래서 문구는 두고 세 묶음 한 줄만 더했다
- 01_room 75, 255줄은 지금도 맞아 그대로 뒀다(75는 [갱신] 실패 줄, 255는 옛 받는 함 API)
- 「확인 전」 칩은 브리지 그물(`chat` 출처)에 아직 있어서 `portfolio/11_postit.md` 30줄과 `notion/10_scribe/02_postit.md`는 그대로 맞다
- `tools/docs.py refs --range 82f0c90..da5ceba --unfixed`가 건 나머지 원고(`06_sessions`, `01_structure`, `08_handoff/03_promote`, `14_screen/*`, `16_tests`, `03_evidence` 등)와 docs의 줄은 읽어 보니 옛 [→], README 「알려진 한계」 쓰기, 「확인 전」을 서술한 곳이 없어 건드리지 않았다. 목록의 줄은 포스트잇이나 `scribe_room.py`를 가리키기만 하는 근거 표시다
- 포트폴리오 사진 `portfolio/img/11_postit*.png`은 옛 화면([→] 단추)이다. 일감대로 다시 찍지 않았다. `portfolio/11_postit.md` 12줄의 사진 설명도 사진 속 [→]를 말하므로 사진을 바꿀 때 함께 고쳐야 한다(고치지 않음)
- `notion/14_screen.md`, `15_db/01_tables.md`, `portfolio/10_scribe_room.md`의 머리 「읽은 커밋」은 한 줄만 고쳤으므로 올리지 않았다. 파일 전체를 다시 읽은 것이 아니라서다

## 3. 시험

- `tools/docs.py check`: 틀린 것 0, 새 줄 줄표와 가운뎃점 0건
- `tools/docs.py readme`: README.md가 이미 같음
- `pytest -q`: 1427 통과

## 4. 규칙 위반

규칙 위반 없음

## 5. 아침에 사람이 정할 것

1. 포트폴리오 사진 `11_postit*.png`과 `11_postit.md` 12줄 사진 설명을 언제 다시 찍고 고칠지(브리지를 다시 띄운 뒤여야 새 화면이 나온다)
2. 위 「읽은 커밋」을 올리지 않은 세 파일은 서기가 다음 기술문서 쓰기 때 전체를 다시 읽고 올린다는 것으로 둬도 되는지
