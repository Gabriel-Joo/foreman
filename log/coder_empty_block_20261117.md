# 빈 블록을 사람 고침으로 세지 않기 (11-17, 코더, 관리자 410 일감)

## 바꾼 자리
- `bridge/notion.py` `Publisher.human_edits` 한 곳. 다른 함수는 건드리지 않았다(코더 528의 근거 떼기, 편 사이 참조 부분과 겹치지 않음)
- 판정 추가: 블록 종류의 칸에 `rich_text`가 있고 그 글이 비었거나 공백뿐이면 건너뛴다

## 빈 블록 판정 기준
- 글 칸이 있는 종류(문단, 목록, 제목, 인용, 할 일 등)의 `rich_text`가 비었거나 공백, 줄바꿈뿐인 것
- 그림, 표, 구분선, 영상처럼 글 칸이 없는 종류는 지금처럼 센다. 글이 없는 것이 본디라 빈 것과 구분할 수 없기 때문이다
- 글자가 있는 블록이 하나라도 바뀌면 지금처럼 멈춘다. 빈 블록이 섞여도 같다. 느슨하게 하지 않았다

## 시험
- `tests/test_docsync.py` `test_human_edits_ignores_empty_blocks_only`: 빈 블록만(멈추지 않음, 빈 문단, 공백 문단, 빈 목록 항목), 글 블록 바뀜(멈춤), 섞임(멈춤), 구분선(여전히 셈)
- `test_trailing_empty_block_does_not_hold_and_is_removed_on_overwrite`: 04_approval 꼴, 곧 맨 끝에 사람이 만든 빈 문단 하나를 가짜 Notion으로 만들어 멈추지 않는 것을 확인. 실제 Notion은 건드리지 않았다

## 빈 블록이 덮어쓰면 지워지는가
지워진다. `sync_children`이 git 판에 없는 끝 블록을 지운다(위 시험에서 `sync_children` 뒤 빈 문단이 사라지는 것을 확인).

## 함께 고친 문서
- `docs/12_scribe.md` 5절 사람 수정 항목에 11-17 줄
- `notion/10_scribe/04_notion.md` 사람이 고친 곳 판정 문단에 빈 블록 설명(평서체, 근거 표시, 머리 「읽은 커밋」은 그대로)

규칙 위반 없음
