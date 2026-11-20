# 포트폴리오 게시를 기술문서와 한 함수로 (foreman-4, 2026-11-20)

- 일감: 관리자 410의 코더 일감(사용자 결정 11-19, 서기실 전체 대조 줄이 끝난 뒤 하기로 한 일)
- 시작한 main 커밋: `b89b3b6`
- 브랜치: `cc/foreman-4`. 커밋만 했고 push와 브리지 다시 띄우기는 하지 않았다
- 실제 Notion에는 올리지 않았다. 시험은 모두 가짜 Notion과 가짜 게시기다. 실제 화면도 보지 못했다(브리지는 원본 폴더 코드로 돈다)

## 1. 바꾸기 전 포트폴리오 게시 칸이 하던 일과 기술문서 길과 다른 곳

바꾸기 전(`b89b3b6`) 「포트폴리오 게시」 칸은 접힌 `<details>` 하나였고, 펼치면 편마다 단추가 있었다.

| 하던 일 | 포트폴리오(바꾸기 전) | 기술문서 |
|---|---|---|
| 올리기 | 편마다 [게시], [다시 게시]. `POST /api/publish` `publish` 한 편씩, `Publisher.publish(relink=True)` | [Notion에 올리기] 또는 [지금 맞추기] 한 번. `docsync` → `DocSync.run_one` → `docsync.sync` |
| 지금 맞추기 | 없음(한 편씩만) | 있음. 자동 맞추기(`docs = "auto"`)도 같은 함수 |
| 번호순 다시 세우기 | `action: "reorder"` → `Publisher.reorder_portfolio`(늘 `force=True`로 모두 옮김). 화면 단추는 없었다(API만) | `sync` 안에서 올린 것이 있으면 `reorder`(이미 맞으면 옮기지 않음) |
| 원본이 사라진 편 치우기 | [원본 없는 페이지 내리기] → `action: "prune"` → `Publisher.prune_portfolio` | `sync` 안에서 `st["deleted"]`를 휴지통으로(`archive = false`, `create = false`면 실패로) |
| force 덮기 | 덮기 단추가 `docsync` + `force`로 갔지만 `run_one`이 기술문서 폴더만 보아, 포트폴리오 편은 덮기 줄 자체가 생기지 않았다 | 덮기 줄과 [Notion 수정 버리고 덮기] |
| 사람이 고친 블록 멈춤 | 한 편 게시가 409를 돌려주고 끝. `DocSync.hold`는 `path.startswith(src)`만 받아 포트폴리오는 덮기 줄도, 텔레그램 ✋도, DB 멈춤 행도 남지 않았다 | 덮기 줄, 텔레그램 ✋, `@docs-held/` 행 |
| 편 사이 링크 | 올린 직후 기다리던 다른 편을 다시 게시(`Publisher.relink`). 잇달아 누르면 두 요청이 같은 페이지에 겹쳐 썼다 | 다 올린 뒤 못 건 편을 한 번 더 게시(두 번째 돌기). 한 요청 안에서 같은 페이지에 두 번 썼다 |
| 「마지막으로 올림」 | 없음. 편마다 `updated_at`만 | 「마지막으로 올림: 올림 N, 사람이 고쳐 멈춤 M, 실패 K」(`@docs-last`) |
| 실패 알림 | Notion 거부(`NotionError`)만 API가 「Notion 게시 실패」 텔레그램. 범위 밖과 원본 없음은 409 응답뿐 | 텔레그램 ⚠, 서기 할 일 까닭, 「실패: …」 줄 |
| 서기 할 일 줄 | `scribe_room.todo`가 `pub.list()`로 따로 셈(「Notion 포트폴리오: 파일 N개 뒤처짐」) | `docsync.todo_items` |
| 링크만 다시 걸면 되는 편 | 「원본이 바뀜」과 구별 없음(TODO) | 같음 |

## 2. 바꾼 것

### 한 함수
- `bridge/docsync.py`: 묶음(`src`) 인자를 `status`, `sync`, `summary`, `todo_items`, `last_published`, `load_held`, `DocSync.run_one`, `last_for`, `save_held`, `_persist`, `_alert`에 더했다. 없으면 기술문서(게시기 `src`)라 다른 부르는 곳은 그대로다. 포트폴리오는 `PORT = "portfolio/"`. 다른 것은 표지 행 이름(`@portfolio-sync`, `@portfolio-last`), 메모리 열쇠(`프로젝트#portfolio/`), 제목(포트폴리오는 게시기가 첫 H1에 번호를 붙이므로 `sync`가 제목을 주지 않고 `status`도 제목 비교를 하지 않는다), 파일 차례(경로 차례), `skip`을 쓰지 않음, 알림 글의 묶음 이름뿐이다
- 멈춘 편 행(`@docs-held/<경로>`)은 경로에 묶음 폴더가 들어 있어 `save_held`, `load_held`가 `@docs-held/<src>`로 거른다. 거르지 않으면 기술문서 맞추기가 포트폴리오 멈춤 행을 released로 바꾼다
- `sync(..., only={경로})`: 한 편 게시. 그 편만 올리고 휴지통 보내기, 차례 세우기, 맞춘 커밋 행은 하지 않는다. `run_one`이 only일 때 다른 편의 멈춤 줄을 남긴다(먼저 `last_for`로 DB에서 되살린다)
- `DocSync.hold`, `release`는 없앴다. 한 편 게시가 같은 함수로 가서 필요 없다
- 실패 줄에 `kind`(scope, notion, error)를 달았다. 한 편 게시 API가 409와 502를 가르는 데 쓴다
- 텔레그램 글: 「⚠ Notion 기술문서 자동 게시 실패」를 「⚠ Notion {기술문서|포트폴리오} 게시 실패」로(사람이 누른 게시도 같은 글이라 「자동」이 틀렸다). ✋ 글 끝의 단추 자리를 「서기실 할 일의」에서 「서기실 「{묶음} 게시」의」로(11-19부터 단추가 할 일 칸 밖에 있다)

### API(`bridge/api/publish.py`)
- `action`에서 `reorder`, `prune`을 뺐다(받으면 422). 포트폴리오 `docsync` 한 번에 들었다
- `docsync`: path가 `portfolio/`로 시작하면 포트폴리오, 아니면 기술문서. 포트폴리오는 `portfolio_page`가 없으면 409, 기술문서는 `docs_mode = off`면 409(전과 같다). 응답에 `src`를 더했다
- `publish`: 그 편이 묶음에 들면(`docsync.group_of`: `portfolio/` 아래, 또는 기술문서 게시가 켜진 프로젝트의 원고 폴더 아래) `run_one(only={경로})`. 응답은 전과 같은 꼴(`_one_reply`: 그 편의 `action`, 멈춤 409와 `edits`, 막힘 409, Notion 거부 502). 묶음 밖(`log/`, 기술문서 게시가 꺼진 프로젝트의 `docs/`)은 전처럼 게시기를 바로 부른다
- `docsync`가 없으면(브리지에서는 Notion 게시가 켜지면 늘 있다) 503. 전에는 `docsync` 갈래만 409였다
- `bridge/scopetoken.py`: 관리 토큰만 받는 action에서 `prune`을 뺐다(없는 action). `docsync`는 그대로라 프로젝트 토큰은 포트폴리오 한꺼번에 올리기도 403이다

### 게시기(`bridge/notion.py`)
- `Publisher.reserve(path, title)`: 새 편의 빈 페이지를 먼저 만들고 짝을 적는다. 편 사이 참조를 쓰는 묶음(`xref_group`)이고 `create`가 켜진 게시기만. `sync`가 새 편마다 글을 채우기 전에 부른다. 그래서 묶음의 모든 새 편이 글을 채우기 전에 주소를 가져, 첫 게시에서 링크가 걸린다
- `Publisher.relink`, `_pending_paths`, `publish`의 `relink` 인자, `reorder_portfolio`, `prune_portfolio`를 없앴다. `sync`의 두 번째 돌기도 없앴다
- `_publish_one` 새 페이지 길: `create_page` 바로 뒤에 짝을 먼저 적고(지문, 커밋은 비움) 글을 붙인 뒤 지문과 커밋을 적는다. 글을 붙이다 실패해도 짝 없는 페이지가 남지 않고 「바뀜」으로 보인다
- 제목 정하기를 `_title` 하나로(게시와 `reserve`가 같게)
- `link_only(row, sha)`: 지문이 비었고 올린 커밋이 지금 그 파일의 마지막 커밋이면 「링크만 다시 걸면 되는 편」. `list()`의 `relink`, `status()`의 `relink`

### 화면(`bridge/static/js/scribe.js`)
- 「포트폴리오 게시」를 「기술문서 게시」와 같은 꼴로: 접히지 않는 한 줄에 숫자(`pubCounts`), 코드가 바뀐 편 수, 「마지막으로 올림」, 「실패: …」, [Notion에 올리기](올릴 것이 있을 때만, 자리가 없으면 까닭과 함께 꺼짐), 그 아래 덮기 단추(`heldRows(pj, busy, 'portfolio/')`). 편 목록은 접힌 `<details>`(같은 keep 열쇠 `scribe:<방>:pubport`)로 상태, [내리기], [열기]만
- 한 편씩 [게시], [다시 게시], [원본 없는 페이지 내리기]는 없앴다
- 확인 창(`techdocAsk`)이 포트폴리오면 「portfolio/ 글을 Notion [포트폴리오]에 올립니다」, 지워질 편이 있으면 휴지통 한 줄, 번호순 한 줄
- 숫자 줄과 편 목록이 「링크만 N」, 「링크를 다시 걸어야 함」을 「바뀜」, 「원본이 바뀜」과 가른다(기술문서 숫자 줄도 같다)
- 덮기 줄은 서버가 단 `src`로 묶음을 갈라 단다. 「할 일」 머리의 「덮기 N(아래 기술문서 게시)」는 「덮기 N(아래 게시 칸)」
- 결과 줄: 「포트폴리오를 맞췄습니다: 올림 N · 휴지통으로 M …」

### 서기실 응답(`bridge/scribe_room.py`)
- `port_pub`을 `docsync.summary(src=portfolio/)`로 바꾸고, 포트폴리오 뒤처짐 줄과 덮기 줄을 `docsync.todo_items(src=portfolio/)`로 만든다(전의 따로 세던 코드는 지웠다). `held_buttons`, `held_error`, `held_list_missing`도 기술문서와 같게
- 서기 지시문(포트폴리오 통째 쓰기)의 「[원본 없는 페이지 내리기]로 치운다」를 「[Notion에 올리기]를 누를 때 휴지통으로 간다」로

## 3. 정한 것과 까닭

- **번호순 다시 세우기와 원본이 사라진 페이지 치우기를 한 번에 넣었다.** 기술문서 `sync`가 이미 두 일을 같은 함수 안에서 한다(지워진 원본 휴지통, 부모마다 차례). 따로 두면 사람이 새 판을 올리고 치우기를 잊어 옛 편이 Notion에 조용히 남는다. 차례는 올린 것(만들기, 고치기, 휴지통)이 있을 때만 세우고 이미 맞으면 옮기지 않는다(`reorder` 기본값). 옛 `reorder_portfolio`는 늘 모두 옮겼다. `archive = false`, `create = false`, `order = "keep"`인 프로젝트는 기술문서와 같게 따른다. 옛 `reorder_portfolio`는 `keep_order`를 보지 않았는데, `config/notion.toml` 펫퍼민트 칸에 `order = "keep"`과 `portfolio_page`가 함께 있다(저장소 `.foreman/notion.toml`이 있으면 그쪽 값이 쓰인다. 그 파일은 보지 않았다). 그대로면 펫퍼민트 포트폴리오를 올릴 때 번호순 다시 세우기를 하지 않는다. 같은 칸의 `archive = false`도 그대로 따르므로 지운 편은 휴지통으로 가지 않고 실패로 남는다(옛 `prune_portfolio`도 `archive`가 같은 까닭으로 거절해 실패로 남겼다)
- **한 편씩 올리는 단추는 화면에서 없앴고, API `publish`는 남겨 같은 함수를 부르게 했다.** 프로젝트 토큰은 한꺼번에 맞추기가 403이라, API 한 편 게시를 없애면 다른 프로젝트 관리자가 자기 포트폴리오를 올릴 길이 사라진다. 남긴 길은 `run_one(only=…)`로 같은 함수를 타서 멈춤 줄, 「마지막으로 올림」, 텔레그램이 같은 자리에 남는다. 두 벌 코드는 없다
- **한 편 게시(only)는 다른 편을 건드리지 않는다.** 차례 세우기와 휴지통 보내기를 하면 프로젝트 토큰이 「한꺼번에」에 해당하는 일을 하게 된다
- **빈 페이지 먼저 만들기는 편 사이 참조를 쓰는 묶음만.** `docs/`를 그대로 올리는 프로젝트(런슈즈, 펫퍼민트, 인프라 docs)는 링크를 알아보지 않으니 필요가 없고, 펫퍼민트 쪽 단위 비교(`keep_notion = shape`)는 빈 페이지를 「지난번 맞춘 판이 없음」으로 보아 사람 수정으로 멈출 수 있다

## 4. 한 요청 안에서 같은 페이지에 두 번 쓰지 않기, 관련 TODO

- 한 요청 안: 두 번째 돌기와 `relink`를 없애고 `reserve`로 대신해 페이지마다 글은 한 번만 쓴다(시험 `test_docsync_one_pass_links_new_pages_and_writes_each_page_once`, `test_one_press_uploads_all_then_only_changed`가 append 호출을 페이지마다 한 번으로 센다). 새 페이지의 제목 쓰기(`set_title`)는 `reserve`가 만든 제목과 같으면 다시 쓰지 않지만, 고치기 길(`_publish_one` updated)에서 `set_title`을 한 번 더 부르는 것은 전부터 있던 그대로다(블록이 아니라 제목이라 archived 블록 400과는 상관없다)
- 요청 사이: 모든 묶음 게시와 묶음에 든 편의 한 편 게시가 `DocSync._lock` 한 잠금 안에서 돈다. 잇달아 눌러도 차례로 돈다
- `docs/TODO.md` 「편을 잇달아 게시하면 … 「Can't edit block that is archived」(400) … 짝 없는 페이지」 줄(360줄 근처): 이번 길로 **풀린다**고 본다. 겹침의 원인이던 `relink`가 없어졌고, 게시가 한 잠금으로 줄을 서며, 새 페이지는 만든 즉시 짝을 적는다. 다만 실제 Notion에서 잇달아 눌러 보지는 않았다(가짜 Notion 시험만). 줄은 지우지 않았다(관리자가 지운다). 「공용 게시기라 네 저장소에 함께 걸린다」는 그대로 맞다: 네 저장소 모두 이 게시기를 쓴다
- `docs/TODO.md` 「링크를 다시 걸어야 함」과 「원본이 바뀜」 가르기 줄(363줄 근처): **풀린다**. 편 목록 「링크를 다시 걸어야 함」, 숫자 줄 「링크만 N」, 서기 할 일 「링크만 N」, 확인 창 「링크만 N」. 줄은 지우지 않았다
- `docs/TODO.md` foreman-152 「원고 폴더를 바꾸면 옛 폴더의 멈춘 편 표시가 풀리지 않음」(73줄): 화면 증상은 함께 **풀린다**. 멈춘 편 행을 묶음 폴더로 걸러 읽으므로 옛 폴더(`@docs-held/docs/…`) 행은 더 이상 화면에 읽히지 않는다. 대신 그 행은 DB에 held로 계속 남고, 누구도 released로 바꾸지 않는다(전에는 맞추기가 한 번 돌면 바꿨다). 읽는 곳이 없어 화면에는 나오지 않는다. 줄을 지울지, 남은 행을 치우는 길을 둘지는 관리자가 정한다
- 「포트폴리오 게시에는 [지금 맞추기]가 있는데 기술문서 게시에는 없어」 줄(348줄 근처): 이번 일과 상관없이 지금 코드와 맞지 않는다(포트폴리오 칸에 [지금 맞추기]는 바꾸기 전에도 없었고, 기술문서 칸은 자동 프로젝트면 [지금 맞추기], notion/ 원고면 [Notion에 올리기]가 있다). 낡은 줄로 보인다. 손대지 않았다

## 5. 막히거나 틀어지면 사람이 아는가

포트폴리오 게시의 실패, 멈춤, 경고가 기술문서와 같은 자리에 뜨는지 시험으로 확인했다(실제 화면, 실제 텔레그램은 보지 않았다).

| 무엇 | 서기실 칸 | 「마지막으로 올림」 | 서기 할 일 | 텔레그램 | 시험 |
|---|---|---|---|---|---|
| 실패한 편 | 「실패: <경로>: <까닭>」 | 「실패 N」(`@portfolio-last`, 다시 띄워도 남음) | 「Notion 포트폴리오: … 뒤처짐」, 까닭 「게시 실패, <경로>: …」 | 「⚠ Notion 포트폴리오 게시 실패 N개」 | `test_failure_is_reported_like_techdoc_and_leaves_no_orphan_page` |
| 사람이 고쳐 멈춘 편 | 포트폴리오 게시 줄 아래 줄과 [Notion 수정 버리고 덮기] | 「사람이 고쳐 멈춤 N」 | 덮기 줄(`src` portfolio/), 「할 일」 머리 「덮기 N(아래 게시 칸)」 | 「✋ Notion 포트폴리오 … 「포트폴리오 게시」의 [Notion 수정 버리고 덮기]」 | `test_human_edit_holds_and_force_line_goes_to_portfolio`, `scribe.test.mjs` 덮기 단추 자리 |
| 링크로 못 바꾼 참조 | 결과 줄 「링크로 못 바꾼 참조 N: …」 | 없음(전과 같음) | 「링크만 N」 | 없음(전과 같음, 브리지 로그) | `test_api_project_token_cannot_sync_portfolio_but_one_piece_goes_same_way` |
| 자리 없음 | 「게시할 수 없습니다」, 단추 꺼짐과 호버 까닭 | 없음 | 까닭 「Notion 자리가 정해지지 않아 …」 | 없음(누를 수 없고 서버도 409) | `test_api_get_and_post_by_project`, `scribe.test.mjs` |

빠진 곳: 「링크로 못 바꾼 참조」 경고는 기술문서처럼 텔레그램으로 가지 않는다(전부터 같다). 서기 할 일에서는 「링크만 N」으로 남아 조용히 묻히지는 않는다.

## 6. 시험

- 새 시험 `tests/test_portfolio_sync.py`(4개): 처음 한 번에 모두 만들고 서로 링크가 걸리며 페이지마다 글을 한 번만 씀, 바뀐 편만 올라감, 기술문서 결과와 섞이지 않음 / 사람 수정 멈춤과 ✋, 덮기 줄 src, DB 멈춤 행, 다시 띄운 뒤 되살림, 덮기로 풀림 / 실패가 같은 자리(텔레그램, 마지막 결과 행, 서기 할 일)에 남고 짝 없는 페이지가 남지 않으며 다음 누름이 같은 페이지에 채움 / 프로젝트 토큰은 포트폴리오 한꺼번에 올리기와 force가 403, 한 편 게시는 같은 함수로 가서 「링크를 다시 걸어야 함」이 보이고 관리 토큰 한 번이 나머지를 올림
- 고친 시험: `test_portfolio_projects.py`(prune, reorder를 한 번의 sync로, 없앤 action은 422), `test_techdoc.py`(prune 시험을 sync로), `test_notion_xref.py`(relink 시험 둘과 두 번 돌기 시험을 한 번 돌기, link_only, 포트폴리오 묶음 시험으로), `test_docsync_held_restart.py`(hold/release 시험을 only 시험으로), `test_publish_hold.py`(git이 다시 바뀌어도 덮기 줄이 남음으로 바뀜, 한 편 게시도 마지막 결과를 남김), `test_publish_scope.py`(가짜 docsync가 only를 받음), `test_stage2_db.py`(reorder_portfolio를 sync로), `test_notioncfg_halt.py`, `test_docsync.py`, `test_docsync_last.py`(가짜 status, sync가 새 인자를 받음), `tests/js/scribe.test.mjs`(포트폴리오 칸 시험 다섯을 새 꼴로, 덮기 단추 자리, 링크만 수), `tests/js/scribe_held.test.mjs`(머리 글)
- 동작이 바뀌어 시험 기대를 바꾼 것 하나: 한 편 게시로 멈춘 줄은 전에 그 커밋(ref_sha)에 묶여 git이 다시 바뀌면 덮기 줄이 사라졌다. 이제 묶음 게시와 같게 그 편이 아직 바뀜이면 남는다(페이지는 여전히 사람이 고친 채라 단추가 남는 쪽이 맞다고 보았다)
- 차례대로 돌렸다: 새 파일 `git add` → `tools/docs.py check` 틀린 것 0(의심 325) → `pytest -q` 1525 passed → `node --test tests/js/` 252 pass. 마지막에 log를 더한 뒤 다시 돌렸다(아래 커밋 직전)
- 관리자 410 요청으로 main(`a511e6f`) 위로 rebase했다. `tests/data/screen_words.toml`이 main의 634(`2203c57`, 옛 이름 줄 둘)와 충돌해 양쪽 줄을 모두 살려 풀었다. 그 뒤 다시 돌렸다: `tools/docs.py check` 틀린 것 0(의심 208) → `pytest -q` 1526 passed → `node --test tests/js/` 252 pass

## 7. 고친 문서

- `docs/12_scribe.md` 5절(사람의 몫, 나무 그림, force 줄, 멈춘 편 DB 줄, 덮기 단추 자리, 자동 맞추기 줄, 편 사이 참조의 아직 안 올라간 편 줄, 새 줄 「기술문서와 포트폴리오는 한 함수」), 1절 표 `publish` 줄, 7절(노션과의 경계, 게시는 프로젝트마다, 옛 편 치우기)
- `docs/operations.md` 텔레그램 표 docsync 줄
- `notion/10_scribe/04_notion.md`(API 권한, 멈춘 뒤, 게시 기록 표지 행, 마지막으로 올림, 포트폴리오 자리 거절, 새 문단 둘(한 함수, 한 편 API), manual 줄과 한 잠금, 「아직 안 올라간 편을 가리킬 때」 절 다시 씀, API 표). 머리 주석 「다루는 곳」에 `tests/test_portfolio_sync.py`를 더했다. 「읽은 커밋」은 그 편 전체를 지금 코드와 맞대 읽지 않았으므로 올리지 않았다
- `notion/10_scribe/01_room.md`(publish 줄, 게시 묶음 문단, 프로젝트별 문단, 자리 없음 문단, 할 일 줄 문단). 「읽은 커밋」은 올리지 않았다
- `portfolio/10_scribe_room.md`「게시」 절 두 문단과 기술문서 문단 끝. 「읽은 커밋」은 올리지 않았다
- `tests/data/screen_words.toml` 두 줄(「원본 없는 페이지 내리기」, 「아래 기술문서 게시)」)

고치지 못한 것: `portfolio/10_scribe_room.md`의 사진 `img/10_scribe_room_publish.png`와 그 설명(편마다 [게시] 단추가 보이는 옛 화면)은 옛 화면이다. 새 화면을 찍으려면 합친 뒤 브리지가 새 코드로 떠야 해서 이 브랜치에서는 찍지 못했다. 사진을 다시 찍고 설명을 바꾸는 일이 남는다(서기 몫).

거꾸로 찾기(`tools/docs.py refs`)에 걸린 나머지 문서(`notion/05_roles/03_keys.md`, `notion/10_scribe/02_postit.md`, `03_evidence.md`, `notion/01_structure.md` 등)는 `scribe_room.py`, `scopetoken.py`처럼 큰 파일의 다른 부분을 가리켜 걸렸다. 게시 동작을 다룬 말(옛 단추 이름, relink, prune, reorder, 표지 행)을 `grep`으로 찾아 위 넷 말고는 없음을 보았다.

## 8. 다른 세션과 겹침

- 코드 주석과 옛 화면 이름 코더(`store.py`, `slash.js`, `hooks.py`, `office.js`): 이 브랜치는 그 파일들을 고치지 않았다
- docs 낡은 줄 서기(`docs/00_design.md`, `docs/11_foreman_dispatch.md`): 고치지 않았다
- 「」 없는 참조 서기(`notion/` 여러 편): `notion/10_scribe/04_notion.md`, `notion/10_scribe/01_room.md`를 고쳤다. 같은 편을 그 서기가 고치면 합칠 때 충돌할 수 있다. 내가 고친 문단은 게시 관련 문단뿐이다

## 9. 규칙 위반

- 11-20 시험 도구 import 줄을 확인하려던 Bash 명령 하나에 빈 heredoc(`.venv/bin/python - <<'X'` 다음 줄 `X`)을 넣었다. 일감의 「heredoc, `python -c` 금지」를 어긴 것이다. 실수로 들어간 것이고, 본문이 비어 아무것도 돌리지 않았으며 파일도 만들지 않았다(`|| true`로 끝남). 그 뒤로는 쓰지 않았다
- 그 밖의 파일 고치기는 Edit, Write로만 했다. `pgrep -f`, `sed -i`, 리디렉션은 쓰지 않았다

## 10. 일하는 도중 받은 글

일하는 도중 이 세션에 「[docs:CLAUDE.md]는 제가 잘못 말했습니다 … 635를 합치고 남은 셋 기다리세요 … 안 고침 다섯 편은 낡았는지 보고 맡기세요」라는 글이 들어왔다. 합치기와 다른 세션에 일 맡기기는 관리자 몫이고 이 세션은 worktree 코더라, 관리자에게 가려던 글로 보고 손대지 않았다.

## 사람이 정할 것

1. `docs/TODO.md`의 「Can't edit block that is archived」 줄과 「링크를 다시 걸어야 함」 가르기 줄을 지울지(실제 Notion에서 잇달아 눌러 보지는 않았다). 합친 뒤 런슈즈나 FOREMAN 포트폴리오에서 [Notion에 올리기]를 한 번 눌러 보면 확인된다
2. foreman-152 줄: 화면 증상은 풀렸고, 옛 폴더 `@docs-held/docs/…` 행이 DB에 held로 남는다. 치울 길을 둘지, 줄만 고칠지
3. 펫퍼민트(`order = "keep"`)의 포트폴리오를 올릴 때 번호순 다시 세우기를 하지 않는다. 옛 `reorder`는 `keep_order`를 보지 않았다. 포트폴리오만은 늘 번호순으로 세울지
4. `portfolio/10_scribe_room.md`의 게시 칸 사진을 합친 뒤 다시 찍기(서기 몫)
5. TODO 「포트폴리오 게시에는 [지금 맞추기]가 있는데」 줄이 낡은 것으로 보인다. 지울지
