# Notion 게시기 — 제목을 문서의 첫 H1로(`title = "h1"`) (코더, 11-12)

인프라 관리자(299)의 부탁 · 사용자 승인. 실제 Notion에는 올리지 않았다(가짜 클라이언트 · 순수 함수만, `.env.notion` 읽지 않음).

## 한 일
- `bridge/notion.py` — `first_h1(md)`(새), `Ctx.h1_title`, `Publisher.h1_title`(`title = "h1"`), `md_to_blocks`가 h1 모드에서 고른 줄만 본문에서 뺌, `publish`가 H1이 있으면 docsync가 준 README 표 제목보다 H1을 앞세움(새 페이지 · 짝지은 페이지 모두)
- `bridge/docsync.py` — `status`가 h1 모드에서 제목을 첫 H1로 잡음(H1이 바뀌면 `r["title"] != names[f]`로 `changed`) + `h1_missing` 목록
- `config/notion.toml` — 머리 주석만(프로젝트 칸 값은 그대로) · `docs/12_scribe.md` 한 줄 · `tests/test_notion_h1.py` 8개
- 적용 범위는 `docs/` 기술문서만. 포트폴리오는 `portfolio_title` 방식 그대로

## 정한 것 셋
1. **`keep`과 `h1` 동시** — 같은 `title` 칸이라 TOML에는 하나만 적힌다(코드도 `keep_title`/`h1_title`이 서로 배타). 모르는 값(오타 `H1` 등)은 설정을 거부하지 않고 기본 방식으로 돌리며 로그 경고. 다른 칸과의 충돌은 `new_title = "numbered"` 하나 — **H1이 있으면 H1이 앞선다**(단 번호 없는 파일 이름이면 `new_page_plan`이 먼저 OutOfScope로 멈춘다 — 지금 설정에 h1+numbered는 없고 그대로 둠)
2. **첫 H1이 없는 문서** — 옛 방식(「파일 이름 — README 표 설명」, 표에 없으면 파일 이름)으로 올리고 로그 경고(`foreman.docsync` · `foreman.notion`) + `status()["h1_missing"]`. **서기 할 일 줄은 넣지 않았다** — `scribe.js`가 `act`를 `docsync` · `force`만 알아서 새 act는 화면에 안 보인다(화면 파일은 내 몫이 아님). 필요하면 관리자가 화면 줄을 정한다
3. **무엇이 「첫 H1」인가** — 코드 울타리 · 맨 위 YAML 머리말 · HTML 주석 **밖**에서 처음 나오는 `# ` 줄. 앞에 빈 줄 · 글 · 인용 · 소제목이 있어도 그 줄. 그 한 줄만 본문에서 빠지고 둘째 H1부터는 본문 heading. 빈 `# `는 건너뜀. 글에서 `[t:…]` 표지 · 백틱 · `*` · 닫는 `#`을 뗌(`titles()`와 같게)
- 참고: 옛 방식은 첫 H1 앞에 다른 블록이 있으면 그 H1을 제목으로 안 보고 본문에 뒀다. h1 모드만 앞이 있어도 제목으로 본다(기본 방식은 그대로)

## 확인 체크리스트
- [x] `title = "h1"`일 때 제목이 첫 H1이다 — `test_publish_title_follows_h1_for_new_and_paired_pages`(docsync가 README 제목을 줘도 H1이 이김)
- [x] (`headings = "md"`) 본문에 H1이 한 번 더 안 들어간다 — `test_h1_title_not_repeated_in_body_even_with_headings_md`
- [x] H1을 바꾸면 Notion 제목도 바뀐다 — 같은 시험에서 짝지은 페이지로 `set_title` 확인 + `test_docsync_status_uses_h1_and_flags_changes_and_missing`에서 지문은 같고 H1만 바뀐 파일이 `changed`
- [x] 설정을 안 바꾼 프로젝트는 전과 같다 — 옛 코드(`git show HEAD:bridge/notion.py`)와 새 코드의 `md_to_blocks`를 이 저장소 `docs/` · `portfolio/` · `log/` 165파일 × (`headings` 기본 · `md`)로 견줘 차이 0. 게시 제목 방식 3가지(기본 · 제목 줌 · `headings=md`)도 시험. 런슈즈 · 펫퍼민트 실제 저장소 문서로는 견주지 않았다(그 저장소 파일은 읽지 않음)
- [x] pytest · node — pytest 706 통과 · **2 실패**(`test_mergeprep::test_load_config`(프로젝트 목록에 ronanlab-infra 있음) · `test_moveflow::test_switch_off_by_default_and_reads_file`(handoff.toml 스위치가 켜져 있음)). 둘 다 설정 값을 기대와 견주는 시험이고 이번 변경 파일과 무관(이 브랜치에서 고친 곳 없음) — 원인은 확인하지 않았고 관리자 판단 몫. node(`tests/js/*.mjs`) 실패 없음

## 되돌리는 법
- 이 커밋 `git revert` → 합친 뒤라면 원본 세션이 브리지를 다시 띄운다(`systemctl --user restart foreman-bridge`, 승인 대기 0 확인 뒤)
- 켜기 전에는 동작이 달라지지 않는다 — `config/notion.toml`에 `title = "h1"`이 없으면 어느 프로젝트도 영향 없음. 끄려면 그 줄만 지운다

## 켤 때 알아둘 것(관리자)
- 칸을 켜면 이미 짝지은 문서의 본문 지문(content_hash)은 안 바뀌어 제목만 바뀐 것으로 잡히지만, h1 모드의 본문 블록(첫 H1 앞에 다른 줄이 있던 문서)은 지문이 같으면 다시 올라가지 않는다 — 본문까지 맞추려면 그 문서를 한 번 갱신하거나 [지금 맞추기]
- 인프라 쪽은 `ronanlab-infra` 칸에 `title = "h1"`을 넣는 일(값 바꾸기)이 남았다 — 이 일에서는 칸 값을 안 바꿨다

## README에서 뺄 줄
없다.

## 덧붙임 — 시험 두 줄 고침(관리자 276 부탁, 사용자 지시)
위 pytest 실패 둘은 관리자가 `config/handoff.toml` 두 칸(`[merge_prep] projects`에 ronanlab-infra · `[move] one_flow = true`)을 켜서 실제 설정을 읽는 시험이 옛 값을 기대해 깨진 것이었다(main에서도 실패). `tests/test_mergeprep.py::test_load_config` · `tests/test_moveflow.py::test_switch_off_by_default_and_reads_file`이 실제 `config/` 대신 `tmp_path` 시험용 파일을 읽게 바꿨다(기대값 변경 아님 — 기본값 · 칸 읽기 · 꺼짐 · 깨짐은 그대로 본다). 다시 돌림: pytest 708 통과 · 1 skip · 실패 0, node(`tests/js/*.mjs`) 실패 없음.
