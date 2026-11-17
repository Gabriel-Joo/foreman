# README 생성기와 점검 9번 (11-17, 코더 foreman-5, 관리자 410 일감, 문서 정리 B)

처음 일감은 README 안 주석 울타리 둘(편 목록)을 채우는 것이었다. 일하는 중에 관리자가 일감을 바꿨다(사용자 지시 11-17): README에 손으로 쓰는 부분을 두지 않고 전부 자동으로 만든다. 다만 지금 README.md는 덮지 않는다. 그래서 이 브랜치는 생성기, 점검 규칙, 시험, 문서만 넣고 README.md는 한 글자도 바꾸지 않았다. FOREMAN에서는 생성기가 꺼진 채다(아래 「켜는 법」).

## 1. 한 일

- `bridge/doctext/readme.py` 새로: README 글 전체를 만들고(`build`), 맞댄다(`diff`, `links_in`)
- `bridge/doctext/check.py`: 점검 9번 README(`readme_check`), 만들기(`readme_build`), 프로젝트 이름(`readme_project`). `run`에 `links` 인자(기본 None)
- `bridge/doctext/config.py`: `.foreman/docs.toml` 맨 위 표 `[readme]`(칸 `title`, `project`). 표가 있어야 켜진다
- `tools/docs.py`: 명령 `readme [--dry]`, 맨 위 인자 `--links <JSON>`, 게시 기록 읽기(`notion_links`)
- 시험 `tests/test_docs_readme.py` 20개(tmp 저장소, DB 안 씀)
- 문서: `docs/12_scribe.md` 「5.」 세 줄, `docs/operations.md` 한 줄, `docs/11_worktree.md` 「9.」 한 문장, `bridge/doctext/__init__.py` 독스트링, 원고 `notion/10_scribe/03_evidence.md` 한 문단과 머리 「다루는 곳」에 새 시험 파일

울타리 꼴(처음 판)은 버렸다. 「울타리를 소개와 링크까지 넓히기」와 「파일 전체 다시 쓰기」 가운데 전체 다시 쓰기가 단순하다. 울타리 짝 맞추기(끝 없음, 겹침, 이름 다름)를 다룰 일이 사라지고, 점검은 파일 통째 비교 하나다.

## 2. README 꼴

```
<!-- 이 파일은 `tools/docs.py readme`가 만든다. 손으로 고치면 다음에 만들 때 날아간다. 소개는 ... 노션 주소는 게시 기록에서 온다 -->
# <제목>

<포트폴리오 00편 첫 본문 문단>

## 포트폴리오

[노션에서 보기](<포트폴리오 00편 노션 주소>)     (없으면 「아직 노션에 올라가지 않았습니다.」)

| 번호 | 제목 |
|---|---|
| 00 | [한눈에 보는 FOREMAN](portfolio/00_overview.md) |
...

## 기술문서

(같은 꼴, 하위 편은 01-01 번호로 부모 편 바로 뒤)
```

- 제목: `[readme] title`, 없으면 프로젝트 이름(`[readme] project`, 없으면 origin 주소의 저장소 이름, 그것도 없으면 폴더 이름). FOREMAN은 origin 이름이 `foreman`이라 켤 때 `title = "FOREMAN"`을 적어야 지금 제목과 같다
- 소개 문단: 포트폴리오 폴더 맨 위 `00_*.md`의 첫 # 줄 뒤 첫 본문 문단. 인용(`>`), 절 제목, 그림, 표, 목록, HTML 주석, 코드 울타리는 건너뛴다. 두 저장소 모두 「> 이 글은 …」 인용 다음의 굵은 요약 문단이 걸린다. 글은 그대로 두고 근거 표시만 뗀다(노션 판과 같은 `STRIP`). 근거 표시를 남기면 README에서 링크도 아닌 대괄호가 보인다
- 편 목록: 번호는 첫 # 줄 앞 번호(`03 `, `02-01 `), 없으면 파일 이름 번호(`01_a/02_b.md`는 01-02). 제목은 번호를 뗀 첫 # 줄. 제목 안 `|`는 `\|`로
- **하위 편을 넣었다**: 노션에서도 하위 편이 따로 페이지이고, 하위 편 제목이 바뀌어도 점검이 걸어야 해서다. FOREMAN 기술문서 50줄, 인프라 29줄이다. 번호가 없는 파일(예: 묶음 안 `TODO.md`)은 표에 넣지 않고 알린다
- 노션 링크: 묶음 맨 위 편(하위 편이 아닌 것 가운데 번호가 가장 앞, 곧 00편)의 게시 주소. 게시 기록 `doc_publish`의 게시된 doc 행(`status = 'published'`, `kind = 'doc'`). 11-17 두 프로젝트 모두 `notion/00_*`, `portfolio/00_overview.md` 주소가 있다

## 3. 명령

- `tools/docs.py [--repo R] readme`: README.md 전체를 다시 쓴다. 문서 도구 가운데 파일을 쓰는 것은 이것 하나다
  - `[readme]` 표가 없으면 거부(종료 2, 쓰지 않음). 지금 FOREMAN README를 실수로 덮지 않게 하는 막음이기도 하다
  - `--dry`: 쓰지 않고 만들 글을 찍는다. 표가 없어도, `--rev`와 함께도 된다. `--rev`만 주고 쓰려 하면 거부
  - 만들 수 없으면(포트폴리오 00편이 없음, 첫 문단이 없음, 묶음 폴더가 없음, 번호 붙은 편이 없음) 쓰지 않고 까닭과 함께 종료 2
  - 게시 기록을 못 읽으면(설정 없음, 연결 실패) 쓰지 않고 종료 2. 주소를 빈 채로 쓰지 않는다
  - 같으면 「README.md가 이미 같습니다」, 다르면 「README.md를 새로 썼습니다」. 두 번 돌려도 같은 바이트다(시험)
- `--links <JSON>`: `{편 경로: 주소}`를 게시 기록 대신 쓴다(시험, 미리 보기)

## 4. 점검 9번

- `[readme]` 표가 있으면 README.md가 만들 글과 한 글자라도 다를 때 틀림 하나. 까닭에 처음 다른 줄(README 쪽과 만들 글 쪽 앞 60자)과 「tools/docs.py readme로 다시 만듭니다」를 보인다. 편이 늘거나 줄거나, 하위 편 제목이나 소개 문단이 바뀌거나, 사람이 손으로 줄을 더하면 걸린다(시험 다섯 갈래)
- README.md가 없으면 틀림, 만들 수 없으면 그 까닭이 틀림
- 표가 없으면 검사하지 않고 결과 notes에 「[readme] 표가 없어 README 생성 검사를 하지 않았습니다」. 런슈즈, 펫퍼민트, 지금 FOREMAN이 이 길이다
- 노션 주소: `tools/docs.py check`는 게시 기록을 읽어 넘긴다. 읽지 못하면 README에 걸린 주소를 그대로 두고 나머지만 맞대며 notes에 「게시 기록을 읽지 못해 …」를 알린다. pytest(`tests/test_docs_selfcheck.py`)와 합치기 카드(`bridge/mergeprep.py`)는 `run`에 주소를 넘기지 않으므로 늘 이 길이다. 그래서 노션 주소가 바뀐 것은 명령으로 돌린 점검만 잡는다. 시험 DB에는 게시 기록이 없어 pytest에서 주소까지 맞대려면 DB를 따로 열어야 하는데, 그러면 시험이 실제 DB에 기대게 되어 하지 않았다
- 노션에 아직 없는 묶음은 틀림이 아니라 알림이다. README에는 그 사실이 글로 들어가므로, 나중에 게시되면 README가 달라져 점검이 걸고 다시 만들면 링크가 걸린다

## 5. 시험

- `.venv/bin/python -m pytest -q` 전체, `node --test tests/js/`, `tools/docs.py check` 결과는 아래 「8.」
- `tests/test_docs_readme.py` 20개: 번호와 소개 문단, 전체 꼴(인용, 근거 표시, 다음 문단이 빠지는가, 하위 편 차례, `|` 가르기), 두 번 돌려 같은 바이트와 점검 통과, 바뀜 다섯 갈래를 점검이 거는가, 링크가 바뀜과 게시 기록을 못 읽을 때, 노션에 없는 묶음, `[readme]` 없으면 거부하고 README 그대로, `--rev` 거부, 소개 편이 없으면 아무것도 쓰지 않음, 첫 문단 없음, `check` 명령 출력에 README 틀림, 프로젝트 이름(폴더, origin), 설정 오류와 모르는 칸
- 지금 FOREMAN과 인프라에 `readme --dry`를 돌려 꼴을 눈으로 봤다(쓰지 않음)
- 인프라 tmp 사본(`git clone --no-hardlinks`)에 `[readme]` 표만 넣고: 점검 틀림 1(README가 다름) → `readme`로 씀 → 다시 돌려 「이미 같습니다」 → 점검 틀림 0. 노션 주소는 실제 게시 기록에서 읽었다(읽기만)

## 6. README를 가리키는 곳 (FOREMAN, `log/` 빼고, 11-17 이 브랜치 기준)

찾은 명령: `git grep -n README -- ':!log' ':!README.md'`에서 다른 README(`docs/README` 같은 것)를 뺀 491줄. 갈래:

### 6-1. 코드가 README 내용을 직접 읽거나 쓰는 곳 (README가 생성물이 되면 바로 깨지는 것)

- `bridge/postit.py` 36(`README_LIMIT = "알려진 한계"`), 276~(README.md를 열어 「알려진 한계」 절 줄을 읽는다), 299~333(포스트잇 [갱신] 재료와 지시문에 그 줄), 411(볼 줄이 없으면 거부 글). 절이 없으면 None으로 다루므로 깨지지는 않지만, [→]로 보낸 한계를 쓸 곳이 사라진다
- `bridge/scribe_room.py` 31~32(서기 일감 `later` 「알려진 한계 쓰기」가 README에 쓴다), 283(`docfix` 고칠 파일에 README.md), 464~546(지시문에 README 한계 절), 524, 533(문서 점검, 고치기 대상에 README)
- `bridge/roleguard.py` 12, 64: 관리자가 고칠 수 있는 파일에 README.md
- `bridge/promote.py` 136~137: 옮기기 목적지가 README.md인 미완은 포스트잇으로 돌린다(README 쓰기는 이미 없음)
- `bridge/doctext/dashdot.py` 29: 줄표 검사 대상에 맨 위 README.md(생성물이 되면 소개 문단에 기호가 있을 때 걸린다)
- `migrations/0033_postit.sql` 10, 16(한계로 보냄 상태 설명)

### 6-2. 기준 문서

- `CLAUDE.md` 13(「새 세션이 먼저 읽을 것 1. README.md 전체 설계」), 25(README 반영), 31, 43(「나중에 할 일」, 3.12), 84(「README 로드맵 표」)
- `docs/operations.md` 28(설계 표 `README.md`), 96(3.12), 110(3.2), 129, 137(3.1), 138~139(3.6)
- `docs/style_guide.md` 11, 17, 26(파일 번호는 README 로드맵 번호를 따른다, 「나중에 할 일」)
- `docs/manuscript_rules.md` 63, 70(줄표 검사 대상, 이 브랜치는 건드리지 않음)

### 6-3. 절 번호나 절 이름으로 가리키는 곳 (docs, 코드 주석, 설정, 마이그레이션, 원고)

- 2.1: `bridge/api/dashboard.py` 6, `bridge/liveness.py` 5
- 2.2: `bridge/pipeline.py` 14, `config/pipeline.toml` 36
- 2.3: `bridge/handoff.py` 1021, `migrations/0017_character_reassign.sql` 1
- 2.4: `bridge/terminal.py` 714, `migrations/0002_seed.sql` 1, `migrations/0011_session_title.sql` 5
- 3(절 3 전체): `tests/test_scribe_ask.py` 72, 74
- 3.1: `bridge/inject.py` 1, `docs/operations.md` 137
- 3.2: `bridge/api/hooks.py` 4, `bridge/assembler.py` 9, `bridge/notify.py` 1, `docs/operations.md` 110, `migrations/0003_turn_prompt_id.sql` 9, `notion/02_ingest.md` 30
- 3.3: `bridge/approval.py` 74, `bridge/hookmiss.py` 3, `tests/fixtures/approval_strict.toml` 58
- 3.4: `bridge/worktree.py` 1, `docs/11_worktree.md` 3
- 3.5: `bridge/wake.py` 3, `docs/11_foreman_dispatch.md` 80, `docs/14_dispatcher_note_wake.md` 52
- 3.6: `docs/operations.md` 138, 139
- 3.8: `bridge/static/js/theme.js` 1, 81, `bridge/static/themes/plain/theme.json` 5
- 3.10: `bridge/api/ws.py` 7, `bridge/static/debug.html` 18, 143, `bridge/static/js/store.js` 226
- 3.11: `bridge/api/dashboard.py` 320, 741, `bridge/assembler.py` 17, `bridge/static/js/office.js` 2740, `bridge/static/js/theme.js` 36
- 3.12: `CLAUDE.md` 43, `bridge/config.py` 45, `deploy/mysql/compose.yml` 1, `docs/operations.md` 96
- 3.13: `docs/02_cloudflare_tunnel.md` 6, 8, `docs/14_dispatcher_note_wake.md` 65, `tests/test_wake_url.py` 35
- 5(데이터 모델): `migrations/0001_init.sql` 1, `0006` 5, `0007` 2, `0012_pipeline.sql` 7
- 「알려진 한계」 30줄: `bridge/postit.py` 10, 265, 276, 411, `bridge/scribe_room.py` 31, 32, 464, `bridge/static/js/postit.js` 82, 105, 119, 152, `docs/10_office_design.md` 154, `docs/12_scribe.md` 37, 84, 297, 298, `migrations/0033_postit.sql` 10, 16, `notion/10_scribe/01_room.md` 34, 157, `notion/10_scribe/02_postit.md` 183, 191, 205, `notion/15_db/01_tables.md` 368, 374, `portfolio/10_scribe_room.md` 31, `portfolio/11_postit.md` 38, 44, `tests/test_scribe_room.py` 212
- 「나중에 할 일」(11-15에 뺀 절) 20줄: `CLAUDE.md` 31, 43, `bridge/mergeprep.py` 273, 1342, `bridge/pgrep_guard.py` 1, `bridge/promote.py` 137, `bridge/reconcile.py` 1, `bridge/stallwatch.py` 1, `bridge/static/js/handoff.js` 183, `docs/11_foreman_dispatch.md` 125, `docs/11_worktree.md` 200, 250, `docs/style_guide.md` 17, `migrations/0033_postit.sql` 3, 61, `notion/08_handoff/03_promote.md` 100, `tests/test_mergeprep.py` 126, `tests/test_postit.py` 15, 16, 29
- 그 밖 절 이름: 「자는 사이에 커밋이 쌓이면 안 된다」 `bridge/foreman.py` 568, `docs/11_foreman_dispatch.md` 160, 「자동 기상」 `bridge/foreman.py` 594, 「6. 로드맵」 `bridge/scribe_room.py` 546

절 번호 꼴(`README 3.12`처럼)만 세면 log와 원고 밖 52줄이다.

### 6-4. 원고의 근거 표시

- `[code:README.md]`(모두 줄 번호 없는 파일 단위) 95개가 원고 21편에 있다: `notion/00_foreman.md`(18), `notion/01_structure/01_placement.md`(19), `notion/15_db.md`(8), `notion/04_approval/01_rules.md`(7), `notion/04_approval/02_flow.md`(6), `notion/16_tests.md`(6), `notion/01_structure.md`, `notion/03_session.md`, `notion/04_approval.md`(각 4), `notion/09_dispatcher/02_note_wake.md`, `notion/12_pipeline.md`, `notion/14_screen.md`(각 3), `notion/11_notify.md`(2), 1개씩 `notion/01_structure/02_startup.md`, `notion/02_ingest/02_hooks.md`, `notion/02_ingest/03_turns.md`, `notion/08_handoff/04_move.md`, `notion/10_scribe/02_postit.md`, `notion/14_screen/01_store.md`, `notion/14_screen/04_shell.md`, `notion/15_db/01_tables.md`
- 머리 「다루는 곳」에 README.md: `notion/00_foreman.md`
- README를 글로만 말하는 원고는 위를 포함해 41편(근거 표시 없이 「README의 알려진 한계」 같은 말)
- 파일 단위 표시라 README가 생성물로 바뀌어도 점검은 깨지지 않는다(파일은 있다). 그러나 가리키던 내용이 사라지므로 조용히 틀린 근거가 된다

### 6-5. 그 밖

- 서기 일감 이름과 설명, 화면 글(`bridge/scribe_room.py` 29, `bridge/scribe_ask.py` 25, `bridge/static/js/postit.js`), 시험(`tests/test_scribe_room.py`, `tests/test_scribe_two_paths.py`, `tests/test_postit.py` 등), `LICENSES.md` 4줄, `bridge/static/demo/stills.json` 583(시연 근거 글에 `repo:README.md`). 전체는 위 명령으로 다시 뽑는다

## 7. 지금 README 내용을 옮길 곳 (안, 뒤에 사용자 결정이 났다)

사용자 결정(관리자 410이 전함, 11-17): 셋으로 나눈다. `CLAUDE.md`는 세션이 지킬 규칙(짧게), `docs/00_design.md`는 설계 전체(세션과 개발자), `README.md`는 처음 온 사람에게 길만(생성물). 차례는 `git mv`(내용 그대로) → 가리킴 고치기 → CLAUDE.md 13줄 가리킴 → README 생성. 옮기기는 아래 13, 14절 보고를 사용자가 본 뒤 관리자가 알린다. 아래는 결정 전에 쓴 안이고 1번이 결정과 같다.

1. `git mv README.md docs/00_design.md`로 옮기고 같은 커밋에서 새 README를 만든다. 이력(`git log --follow`)이 이어지고, 절 번호(1~7, 3.1~3.13)를 그대로 두면 가리키는 곳은 「README 3.12」를 「`docs/00_design.md` 3.12」로 바꾸는 글자 바꾸기로 끝난다. `docs/` 번호 00은 비어 있고 style_guide의 「NN은 로드맵 번호」와도 부딪히지 않는다(로드맵 0단계는 이미 끝났다)
   - 줄표 검사: `bridge/doctext/dashdot.py`가 `git diff -M`으로 이름 바꿈을 알아보므로 내용이 같은 옮김은 새 줄로 세지 않을 것으로 본다. 다만 돌려 보지 못했다(scratchpad 사본에서 `git mv`를 하려 했으나 다른 저장소 쓰기 막음에 걸렸다. 우회하지 않았다)
   - 새 파일이 docs 묶음에 들어가면 거꾸로 찾기가 그 안 경로로 걸기 시작한다(지금 README.md는 묶음 밖이라 근거 표시로 가리킬 때만 걸린다, `docs/11_worktree.md` 「9.」 한계). 처음 합칠 때 카드에 걸리는 문서가 늘 수 있다
2. 가리키는 곳 바꾸기(코더 몫, 한 브랜치에): 6-2 기준 문서, 6-3 절 번호(코드 주석, 설정, 마이그레이션 주석, 시험 글), 6-4 원고 근거 표시 95개를 `[docs:00_design.md]`로, 머리 「다루는 곳」. 원고는 근거만 바꾸고 「읽은 커밋」은 그대로(내용을 다시 읽은 것이 아니다)
3. 6-1 코드: 포스트잇 「알려진 한계」의 자리가 README에서 사라진다. 문서 정리 C, D(한계와 TODO 다시 가르기, 한계 편 셋) 결정과 묶어 정해야 한다. 그 전에 README를 바꾸면 [→] 한계 보내기와 서기 `later` 일감이 쓸 곳을 잃는다(지금 README에 한계 줄 1개). 가장 작은 길은 `README_LIMIT` 읽는 파일을 `docs/00_design.md`로 바꾸는 것이다
4. `CLAUDE.md` 13줄은 「1. `docs/00_design.md` 전체 설계」로. CLAUDE.md는 관리자가 사용자에게 먼저 묻는다
5. 차례: (a) 사용자 결정 → (b) 코더가 2, 3을 고치고 `git mv`와 `[readme]` 켜기와 `tools/docs.py readme`를 한 브랜치에서 → (c) 관리자가 합치고 pytest(점검 9번이 그때부터 FOREMAN을 지킨다)

다른 길: README 내용을 docs 여러 편에 나눠 옮기기. 가리키는 곳이 절마다 다른 파일로 갈려 바꾸기가 훨씬 커지고, 대부분 노션 원고에 이미 더 자세히 있어 결국 줄일 글이다. 그래서 1번(통째 옮기기)을 먼저 하고 나누기는 따로 정하는 쪽을 권한다.

## 8. 503 「README에서 볼 것」 처리

README가 문지기가 되면 아래 줄들은 README에서 사라진다. 옮긴 설계 문서(7.의 `docs/00_design.md`)에 남느냐가 갈림이라 이번에는 README도 그 문서도 고치지 않았다(관리자 지시: README를 덮지 않는다).

| 항목 | 판단 |
|---|---|
| 449줄 `config/portfolio.toml` | 런슈즈 저장소 Jenkinsfile(origin/main)에 지금도 있다. 런슈즈 규칙을 옮긴 줄이라 사실은 맞다. 펫퍼민트 조건은 다르다(`docs/`, `data/review/`, 루트 `*.md`). 옮긴 문서에 남기면 「런슈즈 기준」이라고만 밝히면 된다 |
| 133~134줄 hook 목록 | 실제 견본은 UserPromptSubmit, Stop, StopFailure, SessionEnd, SubagentStart, SubagentStop, PreToolUse, PermissionRequest(`deploy/hooks/foreman-hooks.json`). PostToolUse는 없다. 옮긴 문서에서 고칠 것 |
| 607줄 화면 JS 줄 수 | 지금 화면 html, js, css 합 12,510줄. 숫자는 또 낡으니 빼는 쪽 |
| 863줄 줄 번호 인용 | 「6. 알려진 한계」 안이라 이번 일감에서 건드리지 말라고 했다. 한계 자리를 정할 때(C, D) 함수 이름으로 |
| 문서 표에 roles, manuscript_rules | 문지기 README에는 docs 표가 없다. 옮긴 문서의 「문서」 표나 `docs/operations.md`가 맡을 일 |
| 사용량, kickoff 상태 칸 | 사용량은 `docs/15_usage.md` 머리대로 1, 2, 4 끝, 사람 입력과 가중치 맞추기 남음. kickoff 「4 남음」은 맞다(기존 구현 조사를 한 기록이 `log/01_kickoff_result.md` 말고 없다) |
| 브리지 밖 알림과 훅 통과 기록 | `docs/operations.md` 「3.」에 이미 있다. 옮긴 문서 3.12, 3.3에 한 줄씩이면 된다(381줄 「허용 쪽으로 새지 않는다」 뒤에 통과는 `.run/hook_miss.log`에 남는다) |
| 노션 기술문서와 portfolio 길 | 문지기 README의 두 절과 노션 링크가 그것이다. 해결됨(켜면) |
| 포스트잇 사용법 한 줄 | 문지기에는 넣지 않는다. CLAUDE.md와 `docs/12_scribe.md` 「11.」에 있다 |
| 「기록」 표가 일부 목록인지 | 일부다(표 28줄, `log/` 파일 325개). 문지기에는 없다. 옮긴 문서에 남기면 「초기 기록만」이라고 밝힐 것 |

## 9. 인프라에 넘길 것 (인프라 세션 몫, 이 세션은 읽기만 했다)

- `.foreman/docs.toml`에 `[readme]` 표 한 줄을 더하고(제목과 프로젝트는 origin 이름 `ronanlab-infra`로 맞아 칸이 없어도 된다), FOREMAN 명령 `tools/docs.py --repo <인프라> readme`로 README를 만든다. tmp 사본에서 「틀림 1 → 씀 → 같음 → 틀림 0」을 확인했다
- 걸리는 것: 지금 인프라 README 14줄의 내용(클러스터 설명, 폴더 그림, 비밀값 안내)이 사라진다. 그 줄을 근거로 쓰는 곳이 10곳이다: `docs/00_overview.md` 2(다루는 곳), 94(`README.md:3`), `docs/14_operations.md` 38(`README.md:14`), `docs/style_guide.md` 13, `notion/00_overview.md` 2(다루는 곳), 27, 39, `notion/14_operations.md` 33, `portfolio/00_overview.md` 13, 49, `portfolio/11_limits.md` 17, 31. 인프라는 `files_at = "read"`라 읽은 커밋을 올릴 때까지는 점검이 깨지지 않지만, 올리면 `README.md:3`과 `:14`는 새 README의 엉뚱한 줄(제목 아래 빈 줄 근처, 표 줄)을 가리키게 된다. 그 근거를 `bootstrap/`, `cluster/`, `apps/*/scripts/create-secrets.sh` 같은 실제 파일로 옮긴 뒤 README를 바꾸는 차례가 맞다
- `portfolio/10_docs.md` 42, 46의 `[docs:README.md:3]`, `[docs:README.md:32]`는 docs 폴더의 README(문서 차례)라 이번 일과 상관없다

## 10. 사람이 정할 것

1. ~~지금 README 내용이 갈 곳~~: 정해졌다(7. 머리). 남은 것은 13절 밀림 빼기 방법과 14절 고쳐 쓰기를 언제 할지
2. 포스트잇 「알려진 한계」의 자리(6-1). README가 생성물이 되면 그 절을 둘 수 없다. C, D 단계와 함께
3. FOREMAN 제목: 켤 때 `[readme] title = "FOREMAN"`(안 적으면 `foreman`)
4. 하위 편을 표에 넣었다(FOREMAN 기술문서 50줄). 맨 위 편만 원하면 `rows`에서 하위 편을 빼면 된다
5. pytest가 노션 주소까지 맞대게 할지(4.). 지금은 명령으로 돌린 점검만 주소를 본다

## 11. 시험 결과

- `.venv/bin/python -m pytest -q`: 1389 passed
  - 첫 판은 1개 실패였다. 점검 9번이 꺼진 저장소에도 결과 `notes`에 「[readme] 표가 없어…」를 넣어, `notes == []`를 보는 `tests/test_manuscript_rules.py`가 깨졌다. 그 파일은 다른 코더가 고치는 중이라 건드리지 않고, 꺼짐은 결과 `readme.ran`(false) 칸과 출력 한 줄로 옮겼다(점검 8번 `dashdot.ran`과 같은 꼴)
- `node --test tests/js/`: 227 pass, 0 fail
- `.venv/bin/python tools/docs.py check`: 틀린 것 0, 의심 235, 알림 「[readme] 표가 없어 README 생성 검사를 하지 않았습니다」
- README.md는 이 브랜치에서 바뀌지 않았다
- 거꾸로 찾기로 걸린 문서 가운데 고치지 않은 것: `notion/07_merge/01_card.md`(합치기 카드 점검 줄. 카드는 노션 주소를 넘기지 않아 README 규칙도 주소 빼고 맞댄다. 문단은 지금도 맞다), `docs/manuscript_rules.md` 63, 65(점검 8번 설명, 맞다. 이 일감에서 건드리지 말라고 한 파일), `notion/06_sessions.md`, `notion/07_merge.md`, `notion/10_scribe.md`, `notion/16_tests.md`(`tools/docs.py`의 refs와 check를 말하는 줄, 맞다)

## 13. 옮기기 전 확인 (2) 덮기와 밀림

- **덮기**: `docs/00_design.md`는 덮기 대상이 아니다. 덮기는 문서 묶음 폴더(docs, notion, portfolio)와 기록 폴더 밖의 추적 파일만 센다(`bridge/doctext/check.py` 4번). 그래서 옮겨도 덮기 틀림이 생기지 않는다
  - 생성물 README.md는 계속 덮기 대상이다. 지금은 `notion/00_foreman.md` 「다루는 곳」이 덮는다. 옮긴 뒤 그 편의 README 근거 18개는 설계 문서로 바뀌므로, README.md 덮기는 생성기를 설명하는 `notion/10_scribe/03_evidence.md` 「다루는 곳」으로 옮기는 안을 권한다(그 편이 이 브랜치에서 README 생성을 설명한다). `00_foreman.md`에 그대로 두어도 틀림은 아니다
- **밀림(거꾸로 찾기)**: 지금 README.md는 「묶음 밖 *.md」라 문서 트리거다(`bridge/docrefs.py` `trigger_kind`가 "doc"). `tools/docs.py refs README.md`로 원고 21편이 「문서로만 걸림」으로 걸린다(6-4의 21편과 같다)
  - 옮긴 뒤 `docs/00_design.md`도 문서 트리거다(docs 묶음 문서). 원고 근거를 `[docs:00_design.md]`로 바꾸면 설계 문서를 고칠 때 그 21편이 걸린다. 사람이 고치는 문서라 맞다
  - 생성물 README.md를 트리거에서 빼는 안 둘:
    1. **권함**: `[readme]` 표가 켜진 저장소에서는 `trigger_kind`가 맨 위 `README.md`를 None으로 본다(생성물이라는 것을 이미 그 표가 말한다). 새 칸이 없고, 켜는 순간 함께 빠진다. 코드 몇 줄과 시험 하나
    2. `.foreman/docs.toml`에 새 칸(예: `not_trigger = ["README.md"]`). 다른 생성물도 받을 수 있지만 지금 생성물은 README 하나뿐이고, `[readme]`를 켜고 이 칸을 빠뜨리면 다시 걸린다
  - 어느 쪽이든 근거를 고친 뒤에는 README.md를 가리키는 원고가 0이 되어야 걸릴 것도 없다. 빼기는 그 뒤 누가 실수로 `[code:README.md]`를 달았을 때 헛걸림을 막는 것이다. 그 근거 자체를 막으려면 점검이 생성물을 가리키는 근거 표시를 틀림으로 세는 규칙이 따로 필요하다(지금은 없음)
- 줄표 검사: `git mv`는 `git diff -M`으로 이름 바꿈이 되어 새 줄로 세지 않을 것으로 본다(7. 1번, 돌려 보지 못함)

## 14. 옮기기 전 확인 (3) 기준 문서 0절에 맞는가

docs 기준(`docs/manuscript_rules.md` 「0.」 「1.」 「3.」): 세션이 읽는 글, 얕게, 짧게, 평서체, 결론 먼저 근거 바로, 지금 상태와 까닭, em dash와 가운뎃점 없음. 지금 README(941줄)를 대 보면:

- **말투는 대체로 맞다**: 평서체다. 메모체 줄끝(함, 음, 임)은 3줄
- **기호**: 가운뎃점 든 줄 168, em dash 든 줄 150(겹치는 줄 있음). 옮긴 그대로는 새 줄이 아니라 점검에 안 걸리지만, 그 줄을 고칠 때마다 덩어리 맞대기로 걸린다. 고치려면 약 250줄
- **얕고 짧게에 어긋남(가장 큼)**:
  - 3.3 승인 정책 152줄: 오탐 고친 내력(「실행과 글자」 표 38줄, 오탐 패턴 표, 다른 구현 비교, 다시 돌려 본 수치 세 번). 노션 원고 `04_approval` 세 편이 같은 것을 더 자세히 다룬다. 줄이면 40줄 안팎
  - 5. 데이터 모델 195줄: `migrations/`와 원고 `15_db`가 기준이고 README 표는 「개념 설명」이라 스스로 밝힌다. 마이그레이션을 가리키는 몇 줄로 줄일 수 있다(약 170줄 덜어냄)
  - 3.11 서브에이전트 50줄, 3.1 49줄, 3.2 45줄: 실측 숫자와 경위가 섞여 있다. 각각 절반쯤
- **계획으로 보이는 절**: 2.2(인프라 캐릭터 등장), 2.4, 3.5 자동 기상 상한 표, 3.7 LLM 지표, 3.8 테마 매핑 표, 7. 데모 시나리오(7절은 프로메테우스가 아직 없다고 스스로 적는다). 약 100줄이 「만들 것」을 지금처럼 쓴다. 7절 말고는 코드와 대 보지 않았다. 옮긴 뒤 고칠 때 코드와 대어 「아직 없음」을 밝히거나 계획 절로 모아야 한다
- **진행 기록 꼴**: 날짜(11-NN) 든 줄 61, 취소선 2, 해소된 경고 상자 1(2.4 「11-05 해소」). docs 기준은 날짜를 허용하지만(평서, 결정의 까닭) 「(11-09 바뀜) ~~옛 동작~~」처럼 쌓인 줄은 지금 상태 한 줄로 바꿔야 한다
- 「문서」 절 55줄(브리프 표, 기록 표 28줄)은 `docs/operations.md`나 docs 목록 쪽 일이고, 기록 표는 일부 목록이라 지우는 쪽
- **대략**: 941줄 가운데 400~450줄을 덜어내거나 고쳐 써야 docs 기준에 맞는다. 이번에는 고치지 않았다(지시)

## 12. 규칙

- 진행 글 두 줄을 영어로 썼다(「Now the DocsConfig class and parse.」, 「Now the manuscript 03_evidence: …」). 둘 다 Edit 도구 호출 사이였고, 훅 알림을 보고 다음 글부터 한국어로 바로잡았다
- 관리자 지시(README를 덮지 마라)를 받은 뒤, 「표가 없으면 거부하는가」를 실제 FOREMAN 저장소에서 `readme`로 확인하려다 auto mode 분류기에 막혔다. 거부될 것이었지만 실제 README를 쓰는 명령이라 막힌 것이 맞다. 그 확인은 tmp 저장소 시험(`test_refuses_without_readme_table`)으로 옮겼다
- scratchpad 사본에서 `git mv`를 하려다 다른 저장소 쓰기 막음에 걸렸다. 우회하지 않았다(7. 1번에 「돌려 보지 못했다」로 적음)
