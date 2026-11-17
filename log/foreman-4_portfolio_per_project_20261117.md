# 서기실 포트폴리오 패널을 프로젝트별로 (foreman-4, 2026-11-17)

관리자 410의 코더 일감(사용자 지시 11-17). 브랜치 `cc/foreman-4`.

## 고친 것

- `bridge/static/js/scribe.js`
  - 게시 목록을 프로젝트마다 따로 든다(`pubs[room]`, 못 읽음과 읽은 시각도 프로젝트마다). 목록은 `GET /api/publish?project=<고른 프로젝트>`로 부른다. 전에는 `fetch('/api/publish')`로 FOREMAN만 물었다
  - 「이 프로젝트는 포트폴리오를 게시하지 않습니다(지금은 FOREMAN만 연결돼 있습니다)」 줄을 지웠다. 대신 고른 프로젝트의 상태를 보인다
    - 그 판에 `portfolio/`가 없고 게시 기록도 없으면 「포트폴리오 게시: 아직 없음. 이 프로젝트에는 portfolio/ 폴더가 없습니다.」
    - 원본 커밋을 읽지 못하면 「원본 커밋 origin/main을 읽지 못했습니다.」(없음으로 삼키지 않는다)
    - Notion 자리가 없으면 머리줄에 「Notion 자리 없음」, 펼치면 「게시할 수 없습니다: …」, [게시]와 [다시 게시]는 꺼지고 호버에 까닭
  - [게시], [다시 게시], [내리기]에 `data-proj`를 붙였다. 전에는 [원본 없는 페이지 내리기]만 붙어 있고 나머지는 빠지면 `'foreman'`으로 갔다. 이제 빠져도 고른 프로젝트로 간다. 누른 뒤 다시 읽기도 그 프로젝트다
- `bridge/notion.py`
  - `Publisher.portfolio_place()`: `portfolio_page`가 비어 있으면 `OutOfScope("…포트폴리오 Notion 자리가 정해지지 않았습니다…")`. `parent_for`(게시)와 `reorder_portfolio`(차례 다시 세우기)가 이것을 쓴다. 전에는 `self.portfolio_page or self.root`로 프로젝트 페이지 바로 아래에 조용히 떨어졌다
  - `Publisher.portfolio_files()`: 목록을 게시가 읽는 판(`ref`)에서 센다(`git ls-tree -r -z`). 전에는 작업 폴더 색인(`git ls-files`)이라 다른 프로젝트(`ref = origin/main`)에서는 push 안 된 글도 목록에 섞일 수 있었다. 판을 읽지 못하면 None, `list()`는 OSError로 올린다
  - `Publisher.portfolio_state()`: `has_dir`(None은 읽지 못함), `place`, `ref`, `place_why`
- `bridge/api/publish.py`: `GET /api/publish`가 `portfolio`(위 상태)를 함께 내린다. `has_dir`가 None이면 목록을 읽지 않고 빈 목록
- `bridge/scribe_room.py` `todo`: 「Notion 포트폴리오: 파일 N개 뒤처짐」 줄과 `port_pub`을 FOREMAN만이 아니라 게시기가 있는 모든 프로젝트에서 센다. 따로 잡아 포트폴리오를 못 읽어도 기술문서 줄은 남는다. 자리가 없는 프로젝트는 줄 끝에 「Notion 자리가 정해지지 않아 아직 올릴 수 없습니다.」
- `docs/12_scribe.md` 7절에 「게시는 프로젝트마다(11-17 사용자)」 항목

## 기술문서 길과 같게 한 점

- 게시기는 이미 프로젝트마다 하나다(`bridge/main.py`가 `config/notion.toml` 칸마다 `Publisher`). POST `/api/publish`도 이미 `project`를 받았다. 막혀 있던 것은 화면(FOREMAN만 부름)과 자리 없음 처리였다
- Notion 자리는 기술문서의 `docs_page`와 같은 꼴인 `portfolio_page`, FOREMAN `config/notion.toml` 그 프로젝트 칸에서만 정한다(`notioncfg.REPO_KEYS`에 없다. 저장소 `.foreman/notion.toml`에 두면 쓰지 않고 경고, 기술문서 자리와 같다). 새 칸은 만들지 않았다
- 범위 확인(`Scope`)은 그대로. 원본 판은 기술문서와 같은 `ref`

## 사람이 넣을 값

- 없다. `config/notion.toml`의 네 프로젝트(foreman, runshoes, petmint-rag-chatbot, ronanlab-infra) 칸에 `portfolio_page`가 이미 들어 있다(인프라는 11-12 299 요청 때 넣었고 그 아래는 비어 있다). 설정 파일은 고치지 않았다
- 앞으로 새 프로젝트가 포트폴리오를 쓰면 그 칸에 `portfolio_page`를 넣는다. 넣기 전까지는 상태만 보이고 게시는 막힌다

## 확인 체크리스트

- [x] 인프라를 골랐을 때 포트폴리오 상태가 보이는가: 보인다. 실제 인프라 저장소를 읽기만 해서(`git ls-tree`, 저장소는 고치지 않음) `portfolio_state`를 돌렸다. `origin/main`은 `has_dir False, place True`라 화면은 「아직 없음」이다. 인프라 포트폴리오 열두 편은 아직 인프라의 작업 브랜치(`docs/portfolio-20`)에만 있고 main에 합쳐지지 않았다. 그 브랜치 판으로 읽으면 `has_dir True`, 12편이 잡힌다. 인프라가 main에 합치고 push하면 목록이 뜬다. 브리지를 다시 띄우지 않아 실제 미리보기 화면은 보지 않았다(파이썬 변경은 합친 뒤 관리자가 다시 띄운다). 화면은 `tests/js/scribe.test.mjs`로 확인
- [x] portfolio/가 없는 프로젝트에서 「아직 없음」으로 뜨는가: 뜬다(js 시험, pytest `test_portfolio_state_has_dir`, `test_api_get_and_post_by_project`의 `plain` 프로젝트)
- [x] 게시 버튼이 고른 프로젝트로 동작하는가: 실제 Notion에 올리지 않고 가짜로 확인. js 시험이 [게시], [원본 없는 페이지 내리기], `data-proj` 없는 [게시] 모두 `project: ronanlab-infra`로 보내는지 본다. pytest는 가짜 Notion 나무(FOREMAN 루트, 인프라 루트, 자리 없는 새 프로젝트)와 같은 DB 표로 게시, 다시 게시, 원본 없는 페이지 내리기, 차례 다시 세우기가 자기 [포트폴리오] 아래에서만 일어나고 FOREMAN 페이지(블록, 제목, 휴지통 여부, 자리)를 건드리지 않는지, 잘못 짝지은 기록이 FOREMAN 페이지를 가리켜도 덮지 않는지(Scope), 자리 없는 프로젝트는 아무것도 만들지 않고 거절하는지 본다
- [x] FOREMAN 쪽 동작이 그대로인가: 그대로다. FOREMAN 칸에 `portfolio_page`가 있어 자리 거절에 걸리지 않고, `ref = HEAD`라 목록도 같다(지금 이 브랜치 HEAD로 16편). js 시험 「FOREMAN은 그대로」. 옛 DB 시험 하나(`test_notion_publish_update_unchanged_archive_and_scope`)가 11-06의 「자리 없으면 루트 아래」 동작을 기대해 깨졌다. 이번에 막은 동작이라 그 시험에서 자리를 루트로 정해 두게 고쳤다(시험이 보던 옮기기, 제목, 차례는 그대로 본다)
- [x] 화면 말 시험이 통과하는가: 통과(전체 pytest 안). 이름을 바꾼 것이 아니라 옛 안내 줄을 지운 것이라 `tests/data/screen_words.toml`에는 줄을 더하지 않았다

## 시험

- `.venv/bin/python -m pytest -q`: 1197 통과(새 `tests/test_portfolio_projects.py` 7개 포함)
- `node --test tests/js/`: 221 통과

## 남은 것, 다른 몫

- 화면에 [차례 다시 세우기] 버튼은 원래 없다(API `action: reorder`만). 이번에도 더하지 않았다. 서버 쪽은 프로젝트별로 돌고 자리가 없으면 거절한다
- 서기 몫, 원고가 다시 볼 곳: 없음(`docs/operations.md`, `docs/style_guide.md`, `notion/`, `portfolio/`는 건드리지 않았다)
- 511(`cc/foreman-5`)과 겹침: `bridge/notion.py` 머리 주석과 `bridge/scribe_room.py`의 nudge, later 줄은 건드리지 않았다. `scribe_room.todo`의 게시 묶음(포트폴리오 뒤처짐 줄)만 고쳤다

## 규칙 위반

- 진행 글 한 줄을 영어로 썼다(작업 초반, 게시기를 고치기 직전 「Now edit the publisher…」). 훅이 알려 준 뒤 바로 한국어로 돌아왔고, 그 뒤 진행 글은 모두 한국어다
- 새 주석과 docs, 시험 이름에 em dash와 가운뎃점을 몇 곳 썼다가(`notion.py` docstring 두 곳, `publish.py` 주석, `docs/12_scribe.md` 두 줄, 시험 이름 셋과 주석 하나) 커밋 전에 찾아 쉼표로 바꿨다. 남은 것은 화면 툴팁 첫 줄의 「제목 — 설명」 나눔(허용)과 원래 있던 줄뿐이다
