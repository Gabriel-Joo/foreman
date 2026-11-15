# 서기 구조 첫 묶음: 네 문서의 역할, 회고 없애기 (FOREMAN, 2026-11-15)

관리자 410의 일감(사용자 지시). 바탕 조사는 `log/foreman-4_scribe_structure_20261115.md`. 브랜치 `cc/foreman-4`, 커밋만 했다(push, 브리지 다시 띄우기 안 함).

## 한 일

- `docs/12_scribe.md` 맨 앞에 0절 「네 문서의 역할」을 넣었다. 사용자가 정한 네 갈래(깃헙, docs, 노션 기술 문서, 포트폴리오)와 세 축(깊이, 쉬움, 압축)을 뜻을 바꾸지 않고 docs 문체로 옮기고, 축을 한눈에 보는 표를 붙였다. 회고를 없앤 결정과 까닭도 이 절에 한 단락으로 적었다
- 회고 기능을 뺐다
  - 서기실 화면: `bridge/static/js/scribe.js` `ORDER`에서 `retro`를 빼 「회고 쓰기」 줄과 [시키기]가 사라졌다. 포트폴리오 게시 빈 목록 안내의 「회고는 git에만 둡니다」도 뺐다
  - 서기 캐릭터 호버: `bridge/static/js/office.js` 「문서 담당: 회고 · …」에서 회고를 뺐다
  - 세션 띄우기: `bridge/scribe_room.py` `TASKS["retro"]`, `TOUCHES["retro"]`, `start()`의 retro 분기를 뺐다
  - 밀림 세기: `RETRO_STALE`, `todo()`의 `behind["retro"]`와 「회고 쓰기: 마지막 회고 뒤 커밋 N개」 줄을 뺐다
  - 재료와 지시문: `bridge/scribe.py`의 `collect`, `render`, `_tok`, `first_heading`, `CORRECTION`, `retro_prompt`, 손으로 만드는 CLI(`python -m bridge.scribe`)와 `parse_kst`를 뺐다
  - 포먼 계획 지시문(`bridge/foreman.py` 서기 일감 목록)의 회고 두 줄을 뺐다
  - 모델 고르기 역할 설명 `서기 — 문서 · 회고` → `서기 — 문서와 포트폴리오`(`modelpick.js`). 「무엇 — 설명」 꼴의 줄표는 이웃 역할과 같은 툴팁 꼴이라 두었다
  - 「Notion 게시」 설명 「회고 · 문서를」 → 「포트폴리오와 기술문서를」
- 포트폴리오 「한눈에」(`config/portfolio.toml` 00_overview) 재료에서 `log/retro_20261105_foreman.md`를 뺐다. README.md와 docs 세 편(10, 11, 12)이 이미 재료라 그대로 쓸 수 있다
- `config/scribe.toml`에는 회고 키가 없었다(nudge 둘뿐)
- 문서: `docs/12_scribe.md` 1, 2, 3, 4, 5, 6, 9, 10절의 회고 부분을 고치고 7, 8절(회고만 다룸)을 지웠다. README 로드맵 12줄, 나중에 할 일 두 줄을 고쳤다. `docs/10_office_design.md` 등 다른 docs에는 회고가 없었다
- 시험: `tests/test_scribe.py`(render, retro_prompt 시험 지움, 회고 함수가 없는지 보는 시험 하나 더함), `tests/test_scribe_room.py`, `tests/js/scribe.test.mjs`(메뉴 넷, 화면에 「회고」 없음). 회고와 상관없이 낱말만 빌려 쓰던 예시 셋(`test_overlap`, `test_stage2_db` 1464줄, `test_evidence`)은 지금 있는 일감 이름, 파일 이름으로 바꿨다
- 화면 말 목록 `tests/data/screen_words.toml`: `[[rename]] old = "회고 쓰기"`(문서 인용까지)를 더하고, `retro_prompt`에만 있던 `bridge/scribe.py` 「따로 작업」 코드 예외를 지웠다
- `bridge/evidence.py` 머리 주석의 「12d 자동을 열지 정하는 숫자」를 지금에 맞췄다

`log/retro_20261105_foreman.md`는 지우지 않았다.

## 숫자 전과 뒤

지금 DB에 대고 잰 값. 전 = 도는 브리지(`GET /api/scribe/todo`), 뒤 = 이 worktree 코드의 `scribe_room.todo()`(SELECT만, 스크래치 스크립트).

| 프로젝트 | 할 일 줄(전 → 뒤) | 화면 「밀린 것 N」(전 → 뒤) | 말풍선 |
|---|---|---|---|
| FOREMAN | 5 → 4(회고 줄 「마지막 회고 뒤 커밋 542~546개」가 빠짐) | 4 → 3(README, 나중에, CLAUDE.md 정리) | 받은 할 일이 쌓여 「정리할까요?」 그대로. 받은 할 일이 줄어 그 말풍선이 없어지면 「문서 할 일 5」 대신 「문서 할 일 4」 |
| 런슈즈, 펫퍼민트, 인프라 | 그대로(원래 `log/retro_*`가 없어 회고 줄이 없었다) | 그대로 | 그대로 |

- 서기 호버의 「문서 할 일 5」 목록에서 「회고 쓰기: 마지막 회고 뒤 커밋 546개」가 빠진다(합친 뒤 브리지를 다시 띄우면)

## 확인

- `.venv/bin/python -m pytest -q`: 975 passed. `node --test tests/js/`: 200 pass
- 미리보기(세션 436, 포트 8200): `tools/screen.py --no-term` 세 테마 × 크기 × 패널 모두 문제 0건. 서기실 창 사진: 할 일 넷, 「밀린 것 3」, 회고 줄 없음. 서기 호버 사진: 「문서 담당: 문서 점검 · README · CLAUDE.md · 나중에 할 일 · Notion 게시」. 호버 아래 「회고 쓰기: … 546개」 줄은 아직 도는 브리지(옛 파이썬)가 준 데이터라 남아 보였다. 합치고 다시 띄우면 사라진다(위 뒤 숫자로 확인). 미리보기는 끝에 껐다(`DELETE`, tmux `fm-pv-foreman-4` 없음 확인)
- 사진: 스크래치(`…/scratchpad/panel/`, `…/scratchpad/hover/`), 저장소에 넣지 않았다

## 판단 근거

- **`docs/12_scribe.md` 절 번호는 바꾸지 않았다.** 다른 문서와 코드가 「4.」, 「5.」, 「11.」, 「11-4.」, 「12.」를 가리킨다(operations, style_guide, 10_office_design, 11_foreman_dispatch, 마이그레이션 0022, 0023 주석, notion.py, scribe_ask.py). 7, 8절 자리에는 지웠다는 한 줄만 둔다
- **`bridge/scribe.py`는 남겼다.** 「나중에 할 일 정리」 재료(`later_material`)가 `kst`, `_full`, `write`, `OUT_ROOT`를, 물어보기(`scribe_ask`)가 `kst`, `_clip`, `git_commits`를 쓴다. 그 여섯만 남겼다. `parse_kst`는 지운 CLI만 썼다
- **12d 「하루 끝 자동 초안」도 뺐다.** 그 초안이 회고였다. 12d 줄은 할 일 세기(이미 됨)만 남겼다
- **README의 지난 기록 링크(`log/retro_20261105_foreman.md`)는 「11-05 기록」으로 남겼다.** 기록은 지우지 말라는 지시이고 링크가 그 기록을 가리킬 뿐이다
- **README 로드맵 줄을 이 브랜치에서 고쳤다.** CLAUDE.md는 로드맵 표를 원본 세션이 고친다고 하지만, 이번 지시가 README의 회고 자리를 지우라고 했다. 고친 것은 회고 낱말과 「서기 구조 다시 짜기」 줄의 상태뿐이다

## 남긴 「회고」, 「retro」(grep `bridge tests config docs README.md`)

| 곳 | 남긴 까닭 |
|---|---|
| `bridge/notion.py` 469(`SECTIONS`의 `log/retro_` → 「회고」), 1087, 1352, 1368 주석 | Notion 게시기의 옛 묶음 페이지 규칙. 회고 게시는 11-06부터 게시 목록에서 빠져 있고 `doc_publish`에 내린 기록이 남아 있다. 회고 기능과 따로 도는 게시 장치라 이번에 손대지 않았다. Notion 게시를 손볼 때 같이 정리할 거리 |
| `tests/test_stage2_db.py` 1189~1269, `tests/test_notion.py` 7, 35, 37, 180 | 위 게시 장치 시험이 회고 파일을 예로 쓴다(만들기, 묶음 페이지, 옮기기, 내리기). 예를 바꾸면 묶음 이름 「회고」 단언을 모두 다시 써야 해 위와 함께 미룬다 |
| `bridge/static/demo/stills.json` 562, 574, 598 | 시연 정지 장면의 옛 가짜 데이터(점검 결과 글). 화면 기능이 아니다 |
| `bridge/scribe_room.py` 3, `bridge/scribe.py` 6, `bridge/evidence.py` 6 | 뺐다는 주석 |
| `tests/test_scribe.py` 36~38, `tests/test_scribe_room.py` 65, `tests/js/scribe.test.mjs` 46, 48 | 회고가 다시 들어오지 않게 지키는 시험 |
| `tests/data/screen_words.toml` 116~119 | 화면 말 목록. 문서에 「회고 쓰기」 인용이 다시 들어오면 시험이 잡는다 |
| `docs/12_scribe.md` 20, 170, 174, 181 | 없앤 결정과 까닭, 지운 절 자리 |
| `README.md` 877, 903, 938 | 지난 기록 링크와 없앴다는 줄 |
| `docs/style_guide.md` 13, 18, 41, 71, 78, 162, 166 | 건드리지 말라는 파일(서기 세션이 사람 승인 카드로 고친다). 아래 「서기에게 넘길 것」 |

grep 범위 밖에서 본 것: `migrations/0023_scribe_review.sql` 4줄 주석(「12d 하루 끝 자동 초안을 열지」)은 스키마 파일이라 두었다. `portfolio/06_scribe.md` 55줄 시킬 일 목록에 회고가 있다. 게시된 포트폴리오 글이라 고치면 「바뀜」이 뜬다. 포트폴리오를 갱신할 때 서기가 고친다. `log/` 아래는 기록이라 그대로다.

## 서기에게 넘길 것(CLAUDE.md, operations, style_guide 몫)

- `docs/style_guide.md` 13줄 문서 종류 표의 「회고」 행, 18줄 「결정의 역사는 … 회고에 있다」, 41줄 「회고(log/retro_*)」 구성 절(가리키는 `docs/12_scribe.md` 「7. 포트폴리오 관점」은 이제 비었다), 71, 78, 162(`retro:` 커밋 꼴), 166줄
- `docs/operations.md`, `CLAUDE.md`에는 회고, `bridge.scribe` CLI 언급이 없었다

## 규칙 위반

규칙 위반 없음.
