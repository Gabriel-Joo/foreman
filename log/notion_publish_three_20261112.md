# Notion 게시기 셋 — 사람 수정 판정 · 프로젝트 토큰으로 게시 · 설정을 프로젝트 저장소로 (코더, 11-12)

사용자 지시. 실제 Notion에는 올리지 않았다(가짜 클라이언트 · 진짜 git tmp 저장소만, `.env.notion` 읽지 않음). worktree `cc/foreman-2`에 커밋만 — push · 브리지 재시작 안 함. 다른 저장소는 `git rev-parse`로 읽기만(런슈즈 · 펫퍼민트 origin/main에 `.foreman/notion.toml` 없음 확인).

| 커밋 | 무엇 |
|---|---|
| `dbf7e7c` | 둘 — 사람 수정 판정 |
| `42392cf` | 넷 — 프로젝트 토큰으로 자기 프로젝트 게시 |
| `49321d6` | 다섯 — 설정을 프로젝트 저장소로 · 짝 등록 API · 다시 읽기 |

## 둘 — 사람 수정 판정 (`dbf7e7c`)

- `Publisher.prev_blocks(path, row)`(새): 짝의 `commit_sha` 판을 `renamed_from`으로 경로를 따라가 읽어 블록으로. `commit_sha` 없음 · 못 읽음(없는 커밋 · 경로 밖)이면 None
- `human_edits(pid, new, prev=None)`: 견주는 지문 = 새 판 ∪ 지난 판. 지난 판과 글이 같은 블록은 사람 수정이 아니다. prev가 None이면 옛 판정 그대로
- `publish`(기본 길)만 바꿈. `keep_notion`이 있으면 prev에도 같은 `adopt_notion_shape`를 씌운다. force면 prev를 읽지 않는다. **`keep_notion = shape`(펫퍼민트) 길은 손대지 않음**
- 시험 `tests/test_notion_prev.py` 7개: 11-12 꼴(사람 이름 kept 블록 + git만 고침 → 올라감) · 같은 페이지를 옛 판정으로 보면 걸림(전후 비교) · 사람이 정말 고친 블록만 걸림 · commit_sha 없는 짝은 지금처럼 · 못 읽는 커밋은 보수적 · git mv 뒤에도 지난 판을 찾음 · force는 prev를 안 읽음. `test_notion_h1.py` 가짜 `human_edits` 인자 하나 더함
- 남는 한계: 사람이 블록을 「지난 git 판 글」로 되돌려 고친 경우는 잡지 않는다(그 글은 git이 이미 가졌던 것이라 덮어도 잃는 것이 없다)

## 넷 — 프로젝트 토큰으로 게시 (`42392cf`)

- `bridge/scopetoken.py` `_publish_why`: `POST /api/publish`는 본문 `project`(없으면 foreman)가 토큰 프로젝트일 때만. `force`(거짓이 분명한 값 — 없음 · false · 0 · "false" — 밖은 모두 force로 본다. pydantic이 "true" · 1을 True로 받아서) · `action = "docsync"`는 403 「프로젝트 토큰(x)으로는 할 수 없습니다 — force · 한꺼번에 맞추기는 FOREMAN 관리자에게 부탁합니다」. `GET /api/publish`는 `?project=`(없으면 foreman)가 자기 프로젝트일 때만
- `bridge/api/publish.py`: 라우터가 검증된 본문으로 한 번 더 본다(범위 판정은 날 JSON을 본다 — 칸막이가 새지 않게). `GET /api/publish?project=` 받음 — 없으면 지금처럼 `app.state.publisher`(서기 화면 그대로)
- archive · move · reorder는 자기 프로젝트면 프로젝트 토큰으로 된다(지시가 막으라 한 것은 force · docsync 둘). 막아야 하면 `_publish_why`에 action 하나 더하면 된다
- 시험 `tests/test_publish_scope.py`(진짜 라우터 + 가짜 게시기): 자기 것 허용 · 남의 것 · 기본값 foreman 403 · force(True · "true" · 1) · docsync 403 · 관리 토큰은 다 됨 · 상태 읽기 ?project

## 다섯 — 설정을 프로젝트 저장소로 (`49321d6`)

- `bridge/notioncfg.py`(새): `git rev-parse origin/main:.foreman/notion.toml` → blob → `cat-file`. 칸 목록 `REPO_KEYS`(형식도 본다) · `FOREMAN_ONLY`(root · docs_page · portfolio_page · **github · ref**) 한 곳에. `NotionConfig.args_for` · `refresh`
- `Publisher.configure(docs_mode, quiet_min, opts)`: 칸 읽기를 `__init__`에서 떼어 냄(쓰기 범위는 `__init__`만 — 다시 읽기로 root가 바뀌는 길이 없다)
- `bridge/main.py`: 게시기를 만들 때 `NotionConfig.args_for`로. `DocSync.before_tick` = 다시 읽기
- `POST /api/publish/pair {project, path, page_id}` → `Publisher.pair`: docs/ · portfolio/ 문서가 push한 판에 있어야, 32자리 id, root · [기술문서] · [포트폴리오] 자체 거부, `Scope.under_root`, 같은 경로에 짝(page id 있음) · 같은 페이지가 다른 경로와 짝이면 거부. Notion에는 읽기만(`page`), 제목 · 부모 · url 그대로, `content_hash` · `commit_sha` NULL — 관리자 11-12 SQL과 같은 꼴
- `GET /api/publish?project=`에 `config`(출처 repo/foreman · blob · 경고 · 오류 · stale · docs_mode)

### 정한 것

1. **다시 읽기는 맞추기 주기(5분)마다** — API를 만들지 않았다. 까닭: 프로젝트 관리자가 push한 뒤 부르는 것을 잊으면 옛 설정으로 조용히 도는데, 주기 읽기는 push만으로 따라온다. API 면을 늘리지 않는다. blob이 같으면 다시 풀지 않아 싸다. 결과는 GET `config`로 본다. 그래서 **auto 프로젝트가 없어도 맞추기 고리를 늘 띄운다**(옛: auto가 하나라도 있을 때만). auto가 아닌 프로젝트는 tick이 건너뛰니 하는 일은 설정 읽기뿐. 다시 읽기는 맞추기 잠금 안에서(게시 도중 칸이 바뀌지 않게). 늦음: push 뒤 최대 5분 + 로컬 `origin/main`이 fetch된 뒤(게시와 같은 전제)
2. **저장소 파일이 있으면 REPO_KEYS를 통째로 그 파일이 가진다**(칸마다 섞지 않음). 까닭: 섞으면 저장소에서 칸을 지워도 FOREMAN 값이 살아 조용히 다르게 돈다. FOREMAN 칸에 남은 값은 경고(「저장소 파일이 앞서 FOREMAN 칸의 …는 쓰지 않습니다」 — 텔레그램 한 번). 인프라가 옮기면 FOREMAN `[ronanlab-infra]`의 그 칸들을 지우면 경고가 없어진다
3. **github · ref도 FOREMAN에만** — 지시 목록에 없던 둘. ref는 「push한 판만」 약속(저장소가 `HEAD`로 바꾸면 안 올린 커밋이 게시된다), github은 사본 링크
4. **깨진 파일**(TOML 오류 · 칸 형식 · docs 값 · origin/main 없음): 옛 설정 그대로(`stale`) + 로그 + 텔레그램(같은 blob·사유는 한 번). 브리지가 뜰 때부터 깨졌으면 옛 설정이 없으니 FOREMAN 칸 + 알림. **파일이 없는 것과 origin/main이 없는 것을 가른다**(뒤는 오류)
5. 파일 꼴은 표 없이 맨 위 칸만(`docs = "manual"` …). 모르는 칸은 쓰지 않고 경고
6. 알림 kind는 `docsync`(기술문서 알림과 같은 줄)

### 전후 비교(바꾸지 않은 쪽)
- 시험 `test_no_repo_file_means_foreman_columns_exactly_as_before`: 런슈즈 · 펫퍼민트 · 인프라 칸으로 옛 `main.py` 식 게시기와 새 게시기의 칸 18개(docs_mode · quiet_min · create · keep_title · h1_title · keep_order · footer · keep_notion · skip · archive_ok · heading_md · new_parent · new_title · root · docs_page · portfolio_page · ref · gh) 같음
- 실제 `config/notion.toml`(읽기만)로 스크래치 스크립트: foreman · runshoes · petmint · ronanlab-infra 차이 0, 출처 모두 foreman
- 제목 · 판정: 기존 `test_notion_h1` · `test_docsync` · `test_notion` 그대로 통과

## 시험
- 끝에 한 번: **pytest 742 통과 · 1 skip · 실패 0**, node `tests/js/*.mjs` 26 파일 실패 없음
- 새 시험: `test_notion_prev.py` 7 · `test_publish_scope.py` 10 · `test_notioncfg.py` 17

## 되돌리는 법
- 커밋마다 따로 `git revert`(다섯 → 넷 → 둘 차례가 안전 — 다섯이 넷의 `scopetoken.py` · `publish.py` 위에 줄을 더함). 합친 뒤라면 원본 세션이 승인 대기 0 확인 뒤 `systemctl --user restart foreman-bridge`
- 다섯만 끄고 싶으면: 저장소 파일이 없으면 동작은 전과 같다(맞추기 고리가 늘 도는 것만 다름). 인프라가 파일을 올린 뒤 되돌리려면 그 파일을 지우고 push(5분 안에 FOREMAN 칸으로)
- 넷: 프로젝트 토큰이 꺼져 있으면(`config/tokens.toml enabled = false`) 영향 없음

## 관리자에게(합친 뒤)
- 브리지 다시 띄우기 필요(파이썬 변경). 띄운 뒤 `GET /api/publish?project=ronanlab-infra`의 `config.source`가 foreman인지, 로그에 `foreman.notioncfg` 경고가 없는지
- 인프라 관리자에게 알릴 것: `.foreman/notion.toml` 꼴(맨 위 칸만, root류 빼고), 옮긴 뒤 FOREMAN `[ronanlab-infra]`의 REPO_KEYS 줄 정리, 짝 등록은 `POST /api/publish/pair`, force · [지금 맞추기]는 여전히 FOREMAN 관리자에게
- 인프라 09: 이 고침 뒤 force 없는 게시는 kept 문단으로 멈추지 않아야 한다(짝 `commit_sha 64d1d56`이 있어 지난 판을 읽는다)

## README에서 뺄 줄
없다(「나중에 할 일」에 이 일의 줄이 없었다). 넣을 만한 것: 서기 화면이 `config` 출처 · 경고를 보이게(지금은 API로만)
