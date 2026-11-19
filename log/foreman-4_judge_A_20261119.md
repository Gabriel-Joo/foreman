# 원고 걸림 판정 묶음 A (커밋 b6aebf9, 92a4558, 82f0c90)

관리자 410의 조사 일감(사용자 지시 11-19)이다. 읽고 판정만 했고 원고, 포트폴리오, 코드는 고치지 않았다. 판정 기준은 main HEAD(6e9d002) 판의 원고와 코드다.

## 1. 맨 위 수

| 구분 | 고칠 것 있음인 편 |
|---|---|
| 기술문서(`notion/`) | 4편 (28편 가운데) |
| 포트폴리오(`portfolio/`) | 0편 (12편 가운데) |

짝 수: 모두 50짝(b6aebf9 40, 92a4558 4, 82f0c90 6). 고칠 것 있음 5, 고칠 것 없음 45, 모름 0.

고칠 것 있음인 편:
- `notion/02_ingest.md` (30줄)
- `notion/01_structure.md` (247줄)
- `notion/12_pipeline.md` (301줄, 303줄)
- `notion/07_merge/01_card.md` (95줄)

## 2. 읽어 낸 것

- b6aebf9가 코드에서 한 일은 둘이다. 하나는 주석과 docstring의 「README 3.x」를 「docs/00_design.md 3.x」로 바꾼 것(`bridge/` 30여 파일, `config/pipeline.toml`, `deploy/mysql/compose.yml`, 정적 js, theme.json). 동작도 화면 글도 수도 안 바뀐다. 다른 하나는 README 생성물 처리다. `bridge/docrefs.py`(생성물 README는 거꾸로 찾기에서 뺌), `bridge/doctext/*`(docs 차례, 하위 칸, `-C40%` 복사 알아보기), `tests/screen_words.py`(생성 README는 화면 말 시험에서 뺌).
- 그 커밋이 원고도 이미 고쳤다(`notion/00_foreman.md`, `01_structure.md`, `01_placement.md`, `02_ingest/*`, `03_session.md`, `04_approval*`, `10_scribe/*`, `12_pipeline.md`, `14_screen/*`, `16_tests.md` 등). 그래서 근거 표시 `[code:README.md]`는 모두 `[docs:00_design.md]`로 바뀌어 있고, 남은 걸림은 머리 주석의 「읽은 커밋」이 낡은 것뿐인 편이 많다.
- 92a4558과 82f0c90의 코드 변화는 README 생성기(`readme.py`, `check.py`, `config.py`, `tools/docs.py`)와 거꾸로 찾기와 덮기 검사에서 생성물 빼기(`readme.GENERATED`)다.
- 근거 표시에 줄 번호(`:10-20`)를 붙인 것은 notion과 portfolio 어디에도 없다(grep 0건). 그래서 줄 번호가 어긋나 고칠 것은 없다.
- b6aebf9의 `bridge/postit.py`, `bridge/scribe_room.py` 변화(생성물 README에서 「알려진 한계 쓰기」 거부, `LIMIT_GONE`)는 HEAD에 없다(da5ceba 「포스트잇을 받은 편지함과 TODO 창으로 바꿈」이 [한계로] 길로 바꾸며 없앴다). 원고는 지금 [한계로] 길을 맞게 쓴다.

## 3. 편마다 표

「읽은 커밋만」은 문장은 맞고 머리 주석의 읽은 커밋만 낡은 편이다.

### 기술문서

| 편 | 판정 | 줄과 원문 앞부분 | 까닭 |
|---|---|---|---|
| notion/00_foreman.md | 없음(읽은 커밋만) | | 문서 표시가 이미 `[docs:00_design.md]`, 머리 다루는 곳도 `docs/00_design.md` |
| notion/01_structure.md | **있음** | 247줄 「README의 처음 설계 그림은 브리지가 맡을 일로…」 | 설계 그림은 지금 `docs/00_design.md`에 있고 README에는 없다. 「설계 문서의 처음 그림」으로 |
| notion/01_structure/01_placement.md | 없음(읽은 커밋만) | | compose.yml은 주석만, 02_cloudflare_tunnel은 근거 쪽 글만 바뀜. 편은 「README 3.13」을 말하지 않는다 |
| notion/01_structure/02_startup.md | 없음 | | config.py 주석만 |
| notion/02_ingest.md | **있음** | 30줄 「이 표의 수치는 README 3.2와 킥오프 결과의 실측이다」 | 3.2는 `docs/00_design.md` 「3.2 턴 경계는 단일 신호로 판정하지 않는다」다. 「설계 문서 3.2」로 |
| notion/02_ingest/02_hooks.md | 없음 | | hooks.py, hookmiss.py 주석만 |
| notion/02_ingest/03_turns.md | 없음 | | assembler.py 주석만, test_stage2_db는 포스트잇 시험이고 편이 말하지 않음 |
| notion/02_ingest/04_bus.md | 없음 | | ws.py, debug.html 주석만 |
| notion/03_session.md | 없음 | | inject.py, liveness.py 주석만 |
| notion/04_approval.md | 없음 | | approval.py 주석만 |
| notion/05_roles.md | 없음 | | hookmiss.py 주석만 |
| notion/05_roles/01_roles.md | 없음(읽은 커밋만) | | hookmiss, foreman은 주석만. docrefs 변화(생성물 README 빼기)는 이 편이 말하지 않음(54줄은 코더가 문서도 고친다는 것) |
| notion/06_sessions.md | 없음(읽은 커밋만) | | handoff, worktree 주석만, docrefs 변화는 편이 말하지 않음(74줄) |
| notion/07_merge.md | 없음 | | worktree.py 주석만 |
| notion/07_merge/01_card.md | **있음** | 95줄 「그다음은 docs 문서와 README.md, CLAUDE.md처럼 문서 묶음 밖에 있는 `.md` 파일이다」 | 거꾸로 찾기는 `[readme]` 표가 켜진 저장소(FOREMAN)의 맨 위 README.md를 거르는 파일로 보지 않는다(`bridge/docrefs.py` 139~141줄, `readme.GENERATED`). 생성물 README는 뺀다고 덧붙여야 한다 |
| notion/08_handoff.md | 없음 | | handoff.py 주석만 |
| notion/09_dispatcher.md | 없음 | | foreman.py 주석, docs 두 편은 근거 쪽 글만. 편이 말하지 않음 |
| notion/09_dispatcher/01_plan.md | 없음 | | foreman.py 주석, docrefs 변화는 편이 말하지 않음(157줄), scribe_room.py의 거부는 HEAD에 없음 |
| notion/09_dispatcher/02_note_wake.md | 없음 | | wake.py 주석, test_wake_url 주석만 |
| notion/10_scribe/03_evidence.md | 없음(읽은 커밋만) | | 134~138줄이 README 생성, 하위 칸, docs 차례, 상태 칸 없음, docs_summary, docs_skip, docs_numbered_only, 생성물 README 거꾸로 찾기 제외, 소개 문단 굵은 글 벗기기까지 이미 맞게 쓴다. `-C40%`는 편이 말하지 않는다 |
| notion/10_scribe/04_notion.md | 없음 | | `bridge/doctext/` 가운데 README 생성기, dashdot 복사 알아보기는 편이 말하지 않는다(58, 253줄은 titles.py, head.py) |
| notion/11_notify.md | 없음 | | handoff.py, notify.py 주석만 |
| notion/12_pipeline.md | **있음** | 301줄 「README의 구조 그림에는 받는 웹훅이 …」, 303줄 「README 설계 글의 …」 | 두 곳 모두 지금은 `docs/00_design.md`(125줄, 329줄에서 확인). 301줄은 근거 표시만 `[docs:00_design.md]`로 바뀌고 글은 「README」로 남아 표시와 어긋난다 |
| notion/14_screen/01_store.md | 없음 | | dashboard.py, store.js 주석만 |
| notion/14_screen/02_office.md | 없음 | | office.js, theme.js, theme.json 주석만 |
| notion/14_screen/04_shell.md | 없음 | | terminal.py 주석만 |
| notion/14_screen/05_check.md | 없음(읽은 커밋만) | | 242줄이 생성 README는 화면 말 시험에서 뺀다는 것을 이미 쓴다. tools/docs.py의 readme 명령은 편이 말하지 않음 |
| notion/16_tests.md | 없음(읽은 커밋만) | | 83줄은 화면 말 시험을 일반으로 말하고 README 예외는 05_check가 맡음 |

### 포트폴리오

| 편 | 판정 | 까닭 |
|---|---|---|
| portfolio/00_overview.md | 없음 | office.js 주석만 |
| portfolio/01_pixel_office.md | 없음 | office.js, theme.js, theme.json 주석만 |
| portfolio/02_overhead.md | 없음 | dashboard.py, office.js, store.js 주석만 |
| portfolio/03_pipeline.md | 없음 | pipeline.py, office.js, pipeline.toml 주석만 |
| portfolio/05_approval.md | 없음 | approval.py 주석만 |
| portfolio/06_handoff.md | 없음 | handoff.py 주석만 |
| portfolio/07_merge.md | 없음 | worktree.py 주석만 |
| portfolio/08_foreman_plan.md | 없음 | foreman.py, wake.py 주석만 |
| portfolio/10_scribe_room.md | 없음 | scribe_room.py의 「한계 쓰기 거부」는 HEAD에 없다. 31줄 「알려진 한계 쓰기: 포스트잇에서 [한계로] 보낸 것을…」은 지금 길과 맞다 |
| portfolio/13_shell.md | 없음 | terminal.py 주석만 |
| portfolio/14_usage.md | 없음 | office.js 주석만 |
| portfolio/15_telegram.md | 없음 | notify.py, wake.py 주석만 |

## 4. 짝마다 짧은 판정

### b6aebf9 (40짝)

- b6aebf9, 00_foreman: 없음(읽은 커밋만). CLAUDE.md와 설계 문서 표시가 이미 새 자리를 가리킨다
- b6aebf9, 01_structure: **있음** 247줄 「README의 처음 설계 그림」이 옛 자리
- b6aebf9, 01_placement: 없음(읽은 커밋만). 주석과 근거 쪽 글만
- b6aebf9, 02_startup: 없음. config.py 주석만
- b6aebf9, 02_ingest: **있음** 30줄 「README 3.2」가 옛 자리
- b6aebf9, 02_hooks: 없음. 주석만
- b6aebf9, 03_turns: 없음. 주석만, 포스트잇 시험은 편 밖
- b6aebf9, 04_bus: 없음. 주석만
- b6aebf9, 03_session: 없음. 주석만
- b6aebf9, 04_approval: 없음. 주석만
- b6aebf9, 05_roles: 없음. 주석만
- b6aebf9, 05_roles/01_roles: 없음(읽은 커밋만). docrefs 변화를 편이 말하지 않음
- b6aebf9, 06_sessions: 없음(읽은 커밋만). 같은 이유
- b6aebf9, 07_merge: 없음. 주석만
- b6aebf9, 07_merge/01_card: **있음** 95줄에서 README.md가 걸게 하는 문서로 적힘, 지금은 생성물이라 빠진다
- b6aebf9, 08_handoff: 없음. 주석만
- b6aebf9, 09_dispatcher: 없음. 주석과 docs 쪽 근거 글만
- b6aebf9, 09_dispatcher/01_plan: 없음. 편이 말하지 않음, scribe_room 거부는 HEAD에 없음
- b6aebf9, 09_dispatcher/02_note_wake: 없음. 주석만
- b6aebf9, 10_scribe/03_evidence: 없음(읽은 커밋만). 편이 이미 새 동작을 다 쓴다
- b6aebf9, 10_scribe/04_notion: 없음. 편이 말하지 않는 부분
- b6aebf9, 11_notify: 없음. 주석만
- b6aebf9, 12_pipeline: **있음** 301, 303줄의 「README」가 옛 자리
- b6aebf9, 14_screen/01_store: 없음. 주석만
- b6aebf9, 14_screen/02_office: 없음. 주석만
- b6aebf9, 14_screen/04_shell: 없음. 주석만
- b6aebf9, 14_screen/05_check: 없음(읽은 커밋만). 242줄이 이미 맞다
- b6aebf9, 16_tests: 없음(읽은 커밋만). 일반으로만 말함
- b6aebf9, portfolio 00, 01, 02, 03, 05, 06, 07, 08, 13, 14, 15: 모두 없음. 주석만 바뀜(각 11짝)
- b6aebf9, portfolio/10_scribe_room: 없음. 거부는 HEAD에 없고 편은 지금 길과 맞다

### 92a4558 (4짝)

- 92a4558, 07_merge/01_card: 없음. 편이 `[readme]` 표와 tools/docs.py readme를 말하지 않음(위 95줄 문제는 b6aebf9, 82f0c90 쪽에서 센다)
- 92a4558, 10_scribe/03_evidence: 없음(읽은 커밋만). README 생성과 점검 9번이 이미 쓰여 있음
- 92a4558, 10_scribe/04_notion: 없음. 편이 말하지 않음
- 92a4558, 14_screen/05_check: 없음. 편은 tools/screen.py를 다루고 tools/docs.py는 말하지 않음

### 82f0c90 (6짝)

- 82f0c90, 05_roles/01_roles: 없음. docrefs의 생성물 빼기를 편이 말하지 않음
- 82f0c90, 06_sessions: 없음. 같은 이유
- 82f0c90, 07_merge/01_card: **있음** 95줄. 같은 문제(b6aebf9 짝과 한 번 고치면 둘 다 풀린다)
- 82f0c90, 09_dispatcher/01_plan: 없음. 편이 말하지 않음
- 82f0c90, 10_scribe/03_evidence: 없음(읽은 커밋만). 거꾸로 찾기 제외, 소개 문단 굵은 글, `docs_numbered_only`가 이미 쓰여 있음
- 82f0c90, 10_scribe/04_notion: 없음. 편이 말하지 않음

## 5. 사람이 정할 것

고칠 것 있음에는 세지 않았다(문장이 틀리지는 않고 보태거나 손볼 수 있는 것).

1. `notion/10_scribe/03_evidence.md`에 두 줄을 더할지. (a) 덮기 검사가 생성물 README를 대상에서 뺀다(`bridge/doctext/check.py` 362줄, `readme.GENERATED`). 85줄이 덮기를 말하는 자리다. (b) README 칸에 옮기는 제목과 요약에서는 줄표와 가운뎃점을 쉼표로 바꾼다(`readme.cell`).
2. 고칠 것 없음인 편(기술문서 24편, 포트폴리오 12편)은 머리 주석의 「읽은 커밋」만 올리면 걸림이 풀린다. 그 올리기를 서기가 할지, 걸림을 그대로 둘지 정해야 한다.
3. 이 묶음 밖의 옛 말 두 군데는 이 커밋들이 만든 어긋남이 아니라서 세지 않았다. `notion/05_roles/01_roles.md` 151줄 「README의 나중에 할 일 줄」은 CLAUDE.md의 같은 말을 그대로 옮긴 것이고, 생성물 README에는 그 줄이 없다. `notion/06_sessions.md` 134줄 「FOREMAN만의 규칙(README 표, log/ 기록)」은 `bridge/handoff.py` docstring이 말한 옛 사건(런슈즈가 「README 로드맵 표」를 자기 규칙으로 읽음)을 가리킨다.

## 6. 규칙 위반

규칙 위반 없음. 파일은 Write로만 만들었고(log 한 파일), Bash는 읽기에만 썼으며 `pgrep -f`와 heredoc과 `sed -i`를 쓰지 않았다. 원고, 포트폴리오, 코드는 고치지 않았다.
