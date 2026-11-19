# 한계 편 정리 뒷손질: FP13, FP5, 경계 여섯 곳, 출처 글, 낡은 줄 둘 (서기)

> 2026-11-19 서기 세션(foreman-4, 브랜치 `cc/foreman-4`, main `c061fd3` 위). 관리자 410 일감(사용자 결정 11-19). `log/foreman-5_limits_four_way_sync_20261119.md`(566) 7절 「사람이 정할 것」에 사용자가 답한 것을 원고에 옮겼다.

## 1. FP13과 FP5

| 곳 | 고친 것 |
|---|---|
| `portfolio/09_new_session.md` 18 | 「이 범위로 정한 까닭은 기록에 없습니다.」를 뺐다. 폴더 범위(집 폴더와 `/tmp` 아래)는 화면 약속으로 본문에 그대로 둔다(설계) |
| `notion/17_limits.md` 62 | FP5의 여러 줄 부분을 뺐다. 「`!`로 `sudo`는 보내지 않는다. `sudo`는 암호를 물어 입력이 멈추기 때문이다」만 남김 |
| `portfolio/16_limits.md` 39 | 같은 줄을 「`!`로는 암호를 물어 멈추는 `sudo`를 보내지 않습니다」로 |
| `docs/TODO.md` 2절 | **foreman-143** 「`!` 여러 줄을 막는 까닭 찾기, 없으면 풀지 정하기」. 올린 날은 거부 글이 들어온 커밋 `0edca8c`(11-09) |

## 2. 경계 여섯 곳(566 4절 판정대로)

| 곳 | 판정 | 고친 것 |
|---|---|---|
| `notion/01_structure/02_startup.md` 115 | 할 일 | 「재부팅 검증을 아직 하지 않아 확인하지 못했다」를 「재부팅으로 확인하는 일은 저장소 할 일 목록에 있다 [docs:TODO.md]」로(foreman-3) |
| `notion/07_merge/01_card.md` 280 | 할 일 | 「처음 켰을 때 브리지 로그로 확인하지 못했다」를 「브리지 로그로 확인하는 일은 저장소 할 일 목록에 있다 [docs:TODO.md]」로(foreman-130). 「다만」도 뺐다 |
| `notion/10_scribe/04_notion.md` 112 | 한계와 할 일로 나눔 | 한계: 「사람이 실제로 Notion에서 고친 블록으로 멈추는지는 가짜 Notion으로만 시험한다. 통합 토큰은 봇이라 사람 수정을 만들 수 없기 때문이다」. 할 일: 부모 블록 수정자는 「알아보는 일은 저장소 할 일 목록에 있다 [docs:TODO.md]」로, TODO **foreman-144** 새로(올린 날은 그 줄이 들어온 `e285e57` 11-15) |
| `notion/13_usage.md` 313 | 그대로 둘 사실 | 고치지 않음 |
| `notion/02_ingest/01_transcript.md` 121 | 그대로 둘 사실 | 고치지 않음 |
| `notion/04_approval/02_flow.md` 126 | 설계 | 고치지 않음(본문 약속) |

줄이며 옮기지 않은 말(기준 2절 「줄일 때 뺀 말」):

- 04_notion 112 「실제 첫 시도에서는 맞추기 전에 사람 수정이 페이지에 없어 시험이 되지 않았다」: 지난 경위라 지금 상태 규칙에 걸려 뺐다. 원문은 `log/notion_docsync_checks_20261109.md`에 있다
- 01_card 280 「처음 켰을 때」, 02_startup 115 「재부팅 검증을 아직 하지 않아」: 글쓴이 사정과 지난 경위. 내용은 TODO foreman-130, foreman-3에 있다

## 3. 출처 글 「사용자 결정(날짜)」 꼴

`notion/`과 `portfolio/`에서 「사용자 결정, 판단, 지시, 요청, 승인, 말」과 「사용자가 … 정했다, 골랐다」 꼴을 찾아 갈랐다. `docs/`와 `log/`는 건드리지 않았다.

### 3-1. 고친 줄

| 곳 | 전 | 후 |
|---|---|---|
| `portfolio/16_limits.md` 29 | 사람이 화면을 계속 보지 않는다는 사용자 판단(2026-11-06)으로 정한 길이이고 | 사람이 화면을 계속 보지 않아서 정한 길이이고 [code:config/approval.toml] 그대로 |
| `notion/14_screen/05_check.md` 282 FN150 | ffmpeg를 새로 깔지 않기로 한 것은 사용자 결정(2026-11-06)이다 | ffmpeg를 새로 깔지 않기로 했다 [docs:13_demo_capture.md] 그대로 |
| `notion/08_handoff.md` 19 | 뒤쪽 단계였지만 사용자 판단으로 앞당겼다. | 뒤쪽 단계였지만, 이 세션 때문에 앞당겼다 [docs:11_handoff.md](근거 표시를 새로 담) |
| `notion/14_screen/04_shell.md` 262 | 늘 80×24로 되돌리는 것은 사용자 지시다 | 늘 80×24로 되돌린다(근거 `bridge/terminal.py` 그대로. 까닭은 기록에서 못 찾아 쓰지 않았다) |
| `notion/14_screen/04_shell.md` 273 | 따라 바뀌면 헷갈린다는 것이 사용자 결정이다 | 따라 바뀌면 헷갈리기 때문이다 |
| `notion/07_merge.md` 140 | 사용자의 말이 그대로 문제였다. 「…」 | 사람이 겪은 불편은 이랬다. 「…」(인용은 그대로) |
| `notion/11_notify.md` 260 | 쓰는 곳이 없어졌고, 사용자 지시로 지웠다 | 쓰는 곳이 없어져 지웠다 |
| `notion/12_pipeline.md` 287 | 사용자 요청으로 배송 담당 한 명이 … 바꿨다. | 배송 담당 한 명이 … 바꿨다 [log:stage11_handoff_result.md](근거 표시를 새로 담) |
| `notion/14_screen/02_office.md` 176 | 사용자 지시로 소품은 들지 않고 | 그래서 소품은 들지 않고(까닭은 앞 문장, 얼굴을 가림) |
| `notion/14_screen/02_office.md` 265 | 사용자 말은 이랬다. 「…」 | 화면을 보는 사람의 말은 이랬다. 「…」(인용은 그대로) |
| `notion/09_dispatcher/04_managers.md` 295 | 그래서 사용자는 규칙을 정했다. | 그래서 규칙을 하나 세웠다. |
| `notion/10_scribe/02_postit.md` 60 | 사용자가 커밋만 보고 할 일을 자동으로 지우지 말라고 정했기 때문이다 | 커밋만 보고 할 일을 자동으로 지우지 않기로 했기 때문이다(까닭은 뒤 문장) |
| `notion/10_scribe/02_postit.md` 238 | 사용자가 조사 세션 길을 골랐다. | 조사 세션 길을 골랐다. … 들여다볼 수 있다 [log:foreman-5_postit_20261115.md](근거 표시를 새로 담) |
| `notion/13_usage.md` 279 | 3차 결과를 보고 사용자가 Sonnet으로 정했다. | 3차 결과를 보고 Sonnet으로 정했다.(까닭 문단은 그대로) |
| `notion/10_scribe/04_notion.md` 22 | 사용자의 말로는 "…" | 한 줄로 줄이면 "…"(인용은 그대로) |
| `notion/16_tests.md` 87 | 낡으므로, 깨지게 만드는 것은 시험뿐이라는 사용자 결정이다. | 낡는다. 깨지게 만드는 것은 시험뿐이어서 시험에 걸었다. |
| `notion/00_foreman.md` 145 | 사용자가 승인 카드를 풀어 | 승인 카드를 풀어 |

### 3-2. 남긴 줄

출처 글이 아니라 본문의 내용이다(규칙의 내용, 다루는 자료의 갈래, 화면 글, 원문 인용).

- 규칙의 내용에 「사용자」가 든 줄: `notion/00_foreman.md` 145 앞 문장(다른 저장소는 사용자가 시킬 때만), `notion/07_merge/02_reconcile.md` 83, `notion/05_roles/02_guards.md` 8, `notion/05_roles/01_roles.md` 151, `notion/09_dispatcher/04_managers.md` 295 뒤 문장(「사용자가 허락했습니다」 규칙), `notion/09_dispatcher.md` 55
- 다루는 자료의 갈래로 「사용자 지시, 결정」을 말하는 줄: `notion/09_dispatcher.md` 23, `notion/08_handoff.md` 77, 79, 83, `notion/08_handoff/01_loss.md` 28, 42, `notion/08_handoff/02_summary.md` 66, `notion/08_handoff/03_promote.md` 51, `notion/09_dispatcher/02_note_wake.md` 70, 72, `notion/14_screen/05_check.md` 226
- 화면 글, 거부 글 인용: `notion/05_roles/02_guards.md` 225, 298, 299, 포트폴리오의 「사용자 답 기다림」, 「사용자에게 보고함」 등
- `notion/14_screen/05_check.md` 212 「사용자 승인을 받아 런슈즈에 빈 커밋 하나를 올리고」: 결정의 출처가 아니라 다른 저장소를 고칠 때 허락을 받은 일이라 두었다(4절 사람이 정할 것 2)

## 4. 남은 낡은 줄 둘

| 곳 | 고친 것 |
|---|---|
| `notion/10_scribe/02_postit.md` 210 | 「알려진 한계 쓰기: 쓸 줄 N, 뺄 줄 M」을 「알려진 한계 쓰기: 쓸 줄 N」으로. 지금 `bridge/scribe_room.py` 200 할 일 제목과 같다 |
| `notion/10_scribe.md` 7 | 서기가 맡는 문서 목록의 「README의 알려진 한계」를 「할 일 목록 `docs/TODO.md`」로. 「알려진 한계 쓰기」는 TODO 항목을 지우고 고른 편에 쓴다(`bridge/scribe_room.py` 31~33 주석) |

## 5. 읽은 커밋

다루는 코드가 옛 읽은 커밋 뒤로 바뀌지 않은 네 편만 `c061fd3`으로 올렸다: `notion/13_usage.md`(`fb7121b`), `notion/17_limits.md`, `portfolio/09_new_session.md`, `portfolio/16_limits.md`(셋 다 `6cc0e36`). 나머지 15편은 다루는 코드가 그 뒤 바뀌었는데(`git diff --name-only <읽은 커밋> c061fd3 -- <다루는 곳>`로 1~21개) 이번에는 출처 글 몇 줄만 고치고 그 코드 변경은 읽지 않았다. 올리면 「코드가 바뀐 편」 신호가 조용히 사라지므로 그대로 두었다. 566은 고친 편을 모두 올렸는데 이번에는 다르게 했다(6절 사람이 정할 것 3).

## 6. 시험

- `.venv/bin/python -m pytest -q`: 1461 passed, 1 warning(202초)
- `tools/docs.py check`: 틀린 것 0, 의심 242, 기준 커밋 뒤 새 줄 줄표와 가운뎃점 0건
- `tools/docs.py readme`: 「README.md가 이미 같습니다」

## 7. 규칙

**규칙 위반 하나.** 진행 글 하나를 영어로 썼다. 언제: 출처 글 줄을 고치기 직전 진행 글 「Now edit the source-text lines.」. 왜: 쓰기 전에 첫 낱말을 보지 않았다. 바로잡음: Edit 뒤 PostToolUse 알림으로 알았고, 그 뒤 진행 글은 모두 한국어로 썼다.

그 밖에는 지켰다. 파일은 Edit, Write로만 고쳤고 sed, heredoc, `python -c`로 파일을 고치지 않았다(`>`는 pytest 출력을 스크래치 폴더에 받는 데만 썼다). `pgrep -f`를 쓰지 않았다. push와 브리지 다시 띄우기는 하지 않았다. `docs/`, `log/`의 날짜와 사람 표시는 건드리지 않았다(TODO 새 항목 둘만 더함).

## 8. 사람이 정할 것

1. **TODO foreman-64**(「실제 Notion에서 사람이 고친 블록」, 가짜 Notion으로만 봤다): 이번 판정으로 「실제 사람 수정으로 멈추는지」는 까닭(봇 토큰) 있는 한계가 되었다. foreman-64의 앞 절반은 할 일에서 빼고 「[기술문서] 아래 사람 글이 섞였을 때」만 남길지. 일감에 없어 고치지 않았다
2. **`notion/14_screen/05_check.md` 212 「사용자 승인을 받아」**: 다른 저장소에 빈 커밋을 올린 일의 허락이라 두었다. 이것도 빼거나 「허락을 받아」로 줄일지
3. **읽은 커밋**: 출처 글 몇 줄만 고친 편의 읽은 커밋을 올리지 않았다(5절). 566처럼 고친 편은 모두 올리는 것이 맞으면 15편을 한 줄씩 올린다
4. **까닭을 못 찾은 줄 하나**: `notion/14_screen/04_shell.md` 262 「원래 크기가 아니라 늘 80×24로 되돌린다」. 출처 글(사용자 지시)을 빼니 까닭이 기록에 없다(`docs/10_office_design.md` 317은 창 크기에 맞추는 까닭만 적는다). 설계로 본문에 두었는데, 할 일로 옮길지
