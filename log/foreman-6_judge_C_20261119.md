# 원고 걸림 판정, 묶음 C (foreman-6, 2026-11-19)

관리자 410 조사 일감. 커밋 묶음 C(12커밋, 짝 51)의 걸린 편을 main HEAD(`6e9d002`) 판으로 읽고 판정했다. 원고와 포트폴리오, 코드는 고치지 않았다.

## 1. 맨 위 수

- 고칠 것 있음인 편: 기술문서 3편, 포트폴리오 2편
- 짝 51: 있음 8, 없음 43, 모름 0
- 이 묶음이 건 편: 기술문서 12편, 포트폴리오 6편

고칠 것 있음인 편:
- `notion/10_scribe.md` 93줄
- `notion/10_scribe/01_room.md` 182줄
- `notion/14_screen/05_check.md` 240줄
- `portfolio/10_scribe_room.md` 34줄, 44줄
- `portfolio/11_postit.md` 12줄(사진과 그 설명)

## 2. 편마다

| 편 | 판정 | 줄과 원문 앞부분 | 까닭 |
|---|---|---|---|
| notion/10_scribe.md | 고칠 것 있음 | 93 「README에는 대신 「지금은 ~이다」 말투로 쓰는 알려진 한계 절이 남았고, 이것을 맞추는 일이 위의 알려진 한계 쓰기다」 | 798ff7a로 README 한계 절 길이 다 빠졌다(README는 생성물이라 그 절이 없고, 한계는 원고 편의 「알려진 한계」에 쓴다). 같은 편 49줄 표와 115줄은 이미 맞다 |
| notion/10_scribe/01_room.md | 고칠 것 있음 | 182 「알려진 한계 쓰기 \| 재료 파일 경로, 쓸 줄은 할 일 말투를 「지금은 ~이다. ~하면 다시 연다」 말투로, …」 | 지금 지시문(`bridge/scribe_room.py` `task_prompt` later)은 「할 일 말투가 아니라 그 편을 읽는 사람에게 알리는 말투로」이고, 「지금은 ~이다. ~하면 다시 연다」는 코드에도 `docs/manuscript_rules.md`에도 없다(옛 README 지시문 말). 798ff7a가 이 줄 뒷부분은 고쳤지만 인용은 남겼다 |
| notion/14_screen/05_check.md | 고칠 것 있음 | 240 「지금(fb7121b) 목록에는 바꾼 이름 35줄, 호버 약속 7줄과 건너뛰기 4줄, 코드 예외 8줄, 버튼 예외 5줄이 있고, 서기 몫은 0줄이다」 | 지금 `tests/data/screen_words.toml`은 바꾼 이름 41줄, 코드 예외 7줄(호버 약속 7, 건너뛰기 4, 버튼 예외 5, 서기 몫 0은 그대로). 묶음 C의 넷이 바꿨다: 3bda826 이름 +1, 5a5031e 이름 +1, da5ceba 이름 +2와 코드 예외 -1, 798ff7a 이름 +2로, 합하면 35→41, 8→7이 맞는다. 수와 「지금(…)」 커밋을 함께 고친다 |
| portfolio/10_scribe_room.md | 고칠 것 있음 | 34 「포트폴리오 쓰기 \| 화면을 보고 편 목록을 정해 비개발자도 읽을 글을 씁니다(아래)」, 44 「편 없이 [시키기]를 누르면 서기가 화면을 보고 편 목록부터 정합니다」 | 6bfbd0c로 일 설명과 호버가 「보여줄 화면이 있으면 화면마다, 없으면 결정마다 편 목록을 정해」로 바뀌었다. 지시문도 축 고르기(화면 축, 결정 중심)를 먼저 한다 |
| portfolio/11_postit.md | 고칠 것 있음 | 12 사진 설명 「…[갱신] 판정(남음)과 [x] [→] 단추…」 | da5ceba로 [→]가 없어지고 줄 단추가 [TODO로] [한계로] [x]가 되었고 세 묶음이 생겼다. 사진(`img/11_postit.png`, 11-15 찍음)과 설명이 옛 화면이다. 본문(10~50줄)은 이미 맞다. 사진을 다시 찍고 설명을 고쳐야 한다(사진 다시 찍기는 사람이 정할 것 1) |
| notion/02_ingest/03_turns.md | 고칠 것 없음 | | 바뀐 시험은 포스트잇과 노션 게시 시험이고, 편은 턴과 메시지 다시 읽기 시험만 말한다. 읽은 커밋만 |
| notion/09_dispatcher/01_plan.md | 고칠 것 없음 | | 편은 `TASKS`에서 일 이름을 가져오고 publish만 뺀다는 것만 말한다(139줄). 묶음의 변경은 일 설명, 맡을 파일, 덮기 줄로 이름 목록은 그대로. 읽은 커밋만 |
| notion/10_scribe/02_postit.md | 고칠 것 없음 | | 798ff7a가 236줄을 함께 고쳤다(재료에 README 줄 없음, 열린 포스트잇 없으면 안 띄움). 읽은 커밋만 |
| notion/14_screen.md | 고칠 것 없음 | | 바뀐 것은 포스트잇 칸 css와 office_design 「끝난 것 같음」 줄 한 줄. 편은 그 수준을 말하지 않는다. 읽은 커밋만 |
| notion/14_screen/03_panel.md | 고칠 것 없음 | | 5a5031e가 160줄을 함께 고쳤다(접은 칸 기억이 새로고침 뒤에도 남음, 최근 200칸, 처음값 신호는 적지 않음). 읽은 커밋만 |
| notion/05_roles/03_keys.md | 고칠 것 없음 | | 시험에 가짜 메서드 둘만 더함. 편 본문은 이 시험을 말하지 않는다. 읽은 커밋만 |
| notion/10_scribe/04_notion.md | 고칠 것 없음 | | 102(빈 블록), 106~108(덮기 줄 자리, 멈춘 편 행, 목록 모름 글), 130(마지막으로 올림, 10분, 「Notion에 올린 기록이 없습니다」), 259~261(갱신 줄 꼴), 277~289(편 사이 링크)가 모두 지금 코드와 맞다. 커밋들이 함께 고쳤다. 읽은 커밋만 |
| notion/15_db/01_tables.md | 고칠 것 없음 | | fb6b07e가 표 수(서른, 스물아홉), 마이그레이션 수(서른셋), `postit_repo_log` 절을 함께 고쳤다. 마이그레이션 표 이름을 세어 29로 맞음을 확인했다. 읽은 커밋만 |
| notion/10_scribe/03_evidence.md | 고칠 것 없음 | | `tests/test_techdoc.py`는 갱신 줄 단언 한 줄만 바뀌었고 편 본문은 이 시험을 말하지 않는다. 읽은 커밋만 |
| portfolio/00_overview.md | 고칠 것 없음 | | opanel.js는 「종료된 세션」 칸 접힘 기억만 바뀜. 편은 접기를 말하지 않는다. 읽은 커밋만 |
| portfolio/02_overhead.md | 고칠 것 없음 | | render.js 변경은 접은 칸 기억뿐. 편은 머리 위 표시만 말한다. 읽은 커밋만 |
| portfolio/05_approval.md | 고칠 것 없음 | | 답한 카드가 한 줄로 접히는 동작(44, 48줄)은 그대로. 접힘 기억 저장은 편이 말하지 않는다. 읽은 커밋만 |
| portfolio/07_merge.md | 고칠 것 없음 | | 「자세히」 접는 칸(24줄)은 handoff.js 몫이고 그대로. 읽은 커밋만 |

## 3. 짝마다

| 커밋 | 편 | 판정 | 까닭 |
|---|---|---|---|
| 798ff7a | notion/02_ingest/03_turns.md | 없음 | 시험 단언 글(「쓸 줄 1」)만, 편은 포스트잇 시험을 말하지 않음 |
| 798ff7a | notion/09_dispatcher/01_plan.md | 없음 | later 설명과 TOUCHES만 바뀜, 편은 일 이름 목록만 말함 |
| 798ff7a | notion/10_scribe.md | 있음 | 93줄 「README에는 … 알려진 한계 절이 남았고」가 README 한계 길을 뺀 것과 어긋남 |
| 798ff7a | notion/10_scribe/01_room.md | 있음 | 182줄 「지금은 ~이다. ~하면 다시 연다」 말투 인용이 지금 지시문과 다름 |
| 798ff7a | notion/10_scribe/02_postit.md | 없음 | 같은 커밋이 236줄을 맞게 고침 |
| 798ff7a | notion/14_screen.md | 없음 | office_design 한 줄(끝난 것 같음의 README 줄)을 편이 말하지 않음 |
| 798ff7a | notion/14_screen/05_check.md | 있음 | 바꾼 이름 2줄 더함, 240줄 수가 낡음 |
| 798ff7a | portfolio/10_scribe_room.md | 없음 | 같은 커밋이 31줄을 맞게 고침 |
| 798ff7a | portfolio/11_postit.md | 없음 | 같은 커밋이 46줄을 맞게 고침 |
| 5a5031e | notion/14_screen/03_panel.md | 없음 | 같은 커밋이 160줄을 맞게 고침 |
| 5a5031e | notion/14_screen/05_check.md | 있음 | 바꾼 이름 1줄 더함, 240줄 수가 낡음 |
| 5a5031e | portfolio/00_overview.md | 없음 | 접힘 기억, 편이 말하지 않음 |
| 5a5031e | portfolio/02_overhead.md | 없음 | 접힘 기억, 편이 말하지 않음 |
| 5a5031e | portfolio/05_approval.md | 없음 | 접힘 기억, 카드 접힘 동작은 그대로 |
| 5a5031e | portfolio/07_merge.md | 없음 | 접힘 기억, 편이 말하지 않음 |
| 5a5031e | portfolio/10_scribe_room.md | 없음 | 답 닫기, 접힘 기억, 기술문서 줄 중복 표시 정리. 편 40줄은 어긋나지 않음 |
| da5ceba | notion/02_ingest/03_turns.md | 없음 | 포스트잇 시험만 바뀜 |
| da5ceba | notion/09_dispatcher/01_plan.md | 없음 | later 설명, TOUCHES, blocked의 extra. 편은 말하지 않음 |
| da5ceba | notion/14_screen.md | 없음 | 포스트잇 칸 css 클래스 더함, 편은 말하지 않음 |
| da5ceba | notion/14_screen/05_check.md | 있음 | 바꾼 이름 2줄 더하고 코드 예외 1줄 뺌, 240줄 수가 낡음 |
| da5ceba | portfolio/10_scribe_room.md | 없음 | later 설명은 31줄이 이미 맞음(798ff7a가 다시 고침) |
| da5ceba | portfolio/11_postit.md | 있음 | 12줄 사진과 설명이 옛 [→] 단추 화면 |
| 054783b | notion/05_roles/03_keys.md | 없음 | 시험에 가짜 메서드만 더함 |
| 054783b | notion/09_dispatcher/01_plan.md | 없음 | 덮기 줄 되살리기, 편은 말하지 않음 |
| 054783b | notion/10_scribe.md | 없음 | 편은 덮기 단추 자리를 말하지 않음 |
| 054783b | notion/10_scribe/01_room.md | 없음 | 같은 커밋이 220, 226줄을 맞게 고침 |
| 054783b | notion/10_scribe/04_notion.md | 없음 | 같은 커밋이 106, 108줄을 맞게 고침 |
| 054783b | portfolio/10_scribe_room.md | 없음 | 54줄 [Notion 수정 버리고 덮기]는 이름 그대로, 자리는 편이 말하지 않음 |
| 7b14b58 | notion/09_dispatcher/01_plan.md | 없음 | `held_list_missing` 한 줄, 편은 말하지 않음 |
| 7b14b58 | notion/10_scribe.md | 없음 | 편은 멈춘 목록 글을 말하지 않음 |
| 7b14b58 | notion/10_scribe/01_room.md | 없음 | 226줄 「멈춘 N편의 목록이 아직 없습니다…」가 코드 글과 같음 |
| 7b14b58 | notion/10_scribe/04_notion.md | 없음 | 108줄이 코드 글과 같음 |
| 7b14b58 | portfolio/10_scribe_room.md | 없음 | 편은 말하지 않음 |
| fb6b07e | notion/02_ingest/03_turns.md | 없음 | 포스트잇 시험만 바뀜 |
| fb6b07e | notion/10_scribe.md | 없음 | [TODO로]가 docs/TODO.md에 올린다는 115줄은 그대로 맞음 |
| fb6b07e | notion/15_db/01_tables.md | 없음 | 같은 커밋이 표 수와 0034 절을 고침, 읽은 커밋만 |
| fb6b07e | portfolio/11_postit.md | 없음 | 같은 커밋이 44줄(저장소에 넣은 기록, 거부 까닭)을 고침 |
| dece9bb | notion/10_scribe.md | 없음 | 편은 갱신 줄 꼴을 말하지 않음 |
| dece9bb | notion/10_scribe/03_evidence.md | 없음 | 시험 단언 한 줄, 편은 말하지 않음 |
| dece9bb | notion/10_scribe/04_notion.md | 없음 | 같은 커밋이 259, 261줄을 맞게 고침 |
| dece9bb | portfolio/10_scribe_room.md | 없음 | 편은 갱신 줄을 말하지 않음 |
| 3bda826 | notion/10_scribe/04_notion.md | 없음 | 130줄이 지금 코드(10분, DB 기록, 글)와 맞음 |
| 3bda826 | notion/14_screen/05_check.md | 있음 | 바꾼 이름 1줄 더함, 240줄 수가 낡음 |
| 3bda826 | portfolio/10_scribe_room.md | 없음 | 편은 마지막으로 올림 글을 말하지 않음 |
| 95cbb74 | notion/10_scribe/04_notion.md | 없음 | 같은 커밋이 102줄을 더함 |
| 95cbb74 | portfolio/10_scribe_room.md | 없음 | 편은 빈 블록 판정을 말하지 않음 |
| 3911aa9 | notion/10_scribe/04_notion.md | 없음 | 같은 커밋이 277~289줄을 더함 |
| 3911aa9 | portfolio/10_scribe_room.md | 없음 | 같은 커밋이 50줄을 고침 |
| 6bfbd0c | notion/09_dispatcher/01_plan.md | 없음 | 포트폴리오 설명과 지시문만, 편은 말하지 않음 |
| 6bfbd0c | portfolio/10_scribe_room.md | 있음 | 34, 44줄 「화면을 보고 편 목록을」이 축 고르기와 어긋남 |
| 5adb03a | notion/02_ingest/03_turns.md | 없음 | 노션 게시 시험 두 줄만 바뀜 |

## 4. 사람이 정할 것

- `portfolio/11_postit.md`의 사진 `img/11_postit.png`(11-15 찍음)는 [→] 단추가 있던 옛 화면이다. 서기가 다시 찍을지, 설명에 찍은 때만 적을지(서기실 편 12줄처럼) 정할 것
- 묶음 밖에서 본 것: `notion/10_scribe.md` 49줄 표의 「포트폴리오 쓰기 \| 화면 하나를 한 편으로」도 6bfbd0c의 축 고르기와 어긋난다. 6bfbd0c가 이 편의 읽은 커밋(ce65082) 안에 있어 걸림 목록에는 안 나왔다. 서기를 돌릴 때 함께 고칠지 정할 것
- `notion/10_scribe/01_room.md` 182줄 인용은 da5ceba(이 편의 읽은 커밋) 때 이미 코드에서 빠진 말이라, 쓸 때부터 틀렸던 것으로 보인다. 798ff7a 짝으로 셌다

## 5. 규칙 위반

규칙 위반 없음.
