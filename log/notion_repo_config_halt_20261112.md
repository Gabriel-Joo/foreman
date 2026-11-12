# 저장소 게시 설정을 잃으면 알리고 게시를 멈춘다 (2026-11-12, worktree foreman-2)

사용자 지시: 「저장소 파일이 있다가 사라지면 알린다 · 저장소 파일을 쓰던 프로젝트가 FOREMAN 칸으로 떨어지면 게시를 멈춘다」.
까닭: 인프라 `[ronanlab-infra]`의 저장소 몫 아홉 칸을 지우면, 브리지를 다시 띄운 뒤 깨짐 · 파일 지워짐 때 FOREMAN 칸이 비어 기본값(`create` · `archive` 켜짐, `order` 풀림)으로 **알림 없이** 한 쪽 게시가 돌 수 있었다(`log/enable_c_wave2_20261111.md` 11-12 끝 절).

## 한 일

| 파일 | 바뀐 것 |
|---|---|
| `bridge/notioncfg.py` | 기억(`.run/notion_repo_config.json`) · 프로젝트별 ref · 멈춤(`halted`, `HALT_ARGS`) · 다시 돎 알림 · `forget` · `mark` |
| `bridge/api/publish.py` | 멈춘 게시기면 `POST /api/publish`(모든 action) · `POST /api/publish/pair`를 409 `{"refused", "halted": true}`로 거절. `DELETE /api/publish/repo-config?project=`(기억 지우기, 관리 토큰만) |
| `bridge/docsync.py` | `tick`이 멈춘 게시기를 건너뜀, `sync`도 아무것도 하지 않음(마지막 문), `todo_items`가 멈춤 한 줄 |
| `bridge/main.py` | `NotionConfig(..., memory=.run/notion_repo_config.json)` · 게시기를 만든 뒤 `mark` (두 줄) |
| `config/notion.toml` | 머리 주석 4줄만(칸 값 그대로) |
| `tests/test_notioncfg_halt.py` 새로 · `tests/test_notioncfg.py` 한 시험 | 아래 확인 |

## 정한 것

- **기억하는 곳 = `.run/notion_repo_config.json`**(`{프로젝트: {blob, ref, first_at, last_at, halted?}}`). `doc_publish` 표지 줄(`@repo-config`)은 비동기 DB라 동기 함수인 `args_for` · `refresh`(맞추기 주기 · 브리지가 뜰 때)에서 바로 쓸 수 없고, `.run/`은 이미 브리지 실행 상태 자리(gitignore · 0700)다. 마이그레이션 없음. 쓰기는 tmp → `os.replace`. blob · ref가 바뀔 때만 쓴다(5분마다 쓰지 않는다)
  - 기억 파일이 깨졌으면 `….broken`으로 옮겨 두고 텔레그램 · 로그로 알린다(조용히 잊지 않게). 쓰지 못하면 그 프로젝트 이름으로 알린다
- **멈춤의 조건** — 기억에 있는 프로젝트가
  - 그 ref에 파일이 없음(지워짐) → 멈춤(도는 중이든 다시 띄운 뒤든)
  - 깨짐(TOML · 칸 형식 · ref 없음)인데 쓸 마지막 판이 없음(다시 띄운 뒤 · 이미 멈춘 채) → 멈춤
  - 도는 중 깨짐(마지막 판 있음) → **지금처럼** 마지막 판 그대로 + 알림(`stale`)
- **멈춤 = 게시기의 `config_halt`(사유 글)**. 사유 「<프로젝트>의 .foreman/notion.toml을 읽지 못해 게시를 멈췄습니다(<ref>에 파일이 없습니다 | 깨짐 — …) — 파일을 되살리거나 FOREMAN 관리자에게 알려 주십시오」. 한 쪽 게시 · force · 포트폴리오 · 묶음 옮기기 · reorder · docsync · 짝 등록 모두 409, Notion에 아무것도 쓰지 않는다. 그동안 게시기 칸은 FOREMAN 칸이 아니라 `HALT_ARGS`(docs manual · create false · archive false · order keep · title keep) — 문이 뚫려도 가장 좁게. docs를 manual로 둔 까닭: off면 서기 화면이 기술문서 줄을 숨겨 멈춤이 안 보인다
- **알림**: 텔레그램 · 로그 「🛑 …멈췄습니다」 — 멈추기 시작할 때 · 사유가 바뀔 때 한 번(같은 상태면 5분마다 되풀이하지 않는다). 브리지를 다시 띄우면 멈춘 채면 한 번 더(멈춰 있다는 것을 다시 알린다). `GET /api/publish?project=`의 `config`에 `halted: true` · `source: "repo"` · `error`(사유). 서기 할 일 한 줄 `{kind: publish, act: docsync, halted: true, why: 사유}`
- **다시 돎**: 파일이 바르게 읽히면 칸을 저장소 것으로 되돌리고 「…다시 읽었습니다 — 게시를 다시 돌립니다」 한 번. 멈춘 채 브리지를 다시 띄운 뒤 돌아와도 보낸다(멈춤을 기억 파일 `halted`에도 남김)
- **일부러 FOREMAN 칸으로 되돌리는 길**: 저장소 파일을 지운 뒤(push) 관리 토큰으로 `DELETE /api/publish/repo-config?project=<이름>` — 기억 · 멈춤을 지우고 곧바로 FOREMAN 칸으로 다시 읽어 게시기에 적용, 텔레그램 한 번. 프로젝트 토큰은 scopetoken이 막고(목록에 없는 길) 라우터가 한 번 더 403. 파일이 아직 있으면 다음 읽기에서 다시 기억한다
- **읽는 ref = 그 프로젝트 FOREMAN 칸의 `ref`**(없으면 `origin/main`) — `NotionConfig.ref_for`. FOREMAN 칸 `ref = "HEAD"`인 FOREMAN도 HEAD에서 읽는다(파일이 없으니 그대로)
- **저장소 파일을 쓴 적 없는 프로젝트**(런슈즈 · 펫퍼민트 · FOREMAN)는 기억에 없으니 전과 같다 — 처음부터 깨진 파일이면 지금처럼 FOREMAN 칸 + 알림

## 서기 화면 (손대지 않음 — 맡은 파일 밖)

- 멈춤 줄은 `act: "docsync"`로 내보냈다 — `scribe.js` docsBlock이 그 `why`를 기술문서 줄 옆에 보여 준다(새 act는 화면이 모른다, 302 `h1_missing`과 같은 사정). 그 줄의 [지금 맞추기]가 보일 수 있지만 누르면 서버가 같은 사유로 거절한다
- 눈에 띄는 빨간 줄(덮기 줄처럼)로 따로 보이려면 `scribe.js`에 `halted` 처리를 더해야 한다 — 관리자 몫으로 넘긴다

## 확인

- [x] 저장소 파일로 돌던 프로젝트에서 파일이 사라지면 → 알림 + 게시 멈춤(한 쪽 게시 · 지금 맞추기 · force · reorder · 짝 등록 409, 자동 `tick` 건너뜀, `sync` 아무것도 안 함) — `test_file_removed_while_running_halts_alerts_once_and_resumes` · `test_api_refuses_publish_pair_docsync_when_halted` · `test_auto_sync_and_sync_do_nothing_when_halted`
- [x] 브리지를 다시 띄운 뒤 파일이 깨져 있거나 없으면 → 같은 멈춤(FOREMAN 칸 알림 없음) — `test_after_restart_missing_or_broken_file_halts_not_foreman`
- [x] 파일이 돌아오면 다시 돌고 알림(도는 중 · 다시 띄운 뒤 모두, 한 번) — 위 두 시험
- [x] 도는 중 깨짐은 지금처럼(마지막 판 + 알림) — `test_broken_while_running_keeps_last_version_as_before` · 기존 `test_broken_file_keeps_old_settings_and_alerts`
- [x] 쓴 적 없는 프로젝트는 전과 같다 — `test_projects_that_never_used_repo_file_are_unchanged` · 기존 `test_no_repo_file_means_foreman_columns_exactly_as_before`(세 프로젝트 칸 값 전후 같음)
- [x] ref가 FOREMAN 칸을 따른다(HEAD · 없으면 origin/main · 옛 커밋으로 바꾸면 「사라짐」 → 멈춤) — `test_ref_follows_foreman_column`
- [x] GET config에 멈춤 표시 · 기억 지우기는 관리 토큰만 · 기억 파일 깨짐 알림 · 서기 할 일 줄 — 각 시험
- [x] **pytest 760 통과(1 skip) · node 123 통과**
- 바뀐 기존 시험 하나: `test_refresh_picks_up_new_push_and_removal` — 파일을 지우면 FOREMAN 칸으로 가던 것을 「멈춤 → forget 뒤에만 FOREMAN 칸」으로(이 일이 바꾸려던 동작 그대로)
- Notion에 올리지 않음(가짜 게시기 · 가짜 알림기 · 임시 git). `.env.notion` · 다른 저장소 읽지 않음

## 합친 뒤 알아둘 것

- **기억은 이 코드가 처음 돌 때부터 생긴다.** 합치고 브리지를 다시 띄울 때 인프라 `.foreman/notion.toml`이 바르게 읽히면 그때 기억된다. 그 순간 이미 깨져 있으면 기억되지 않고 옛 동작(FOREMAN 칸 + 알림)이다 — 다시 띄운 뒤 `GET /api/publish?project=ronanlab-infra`의 `config.source == "repo"`와 `.run/notion_repo_config.json`에 `ronanlab-infra`가 있는지 본다. **인프라 아홉 칸 지우기는 이것을 확인한 뒤가 안전하다**
- FOREMAN `config/notion.toml`은 브리지가 뜰 때만 읽으므로 `ref`를 바꾸면 브리지를 다시 띄워야 한다

## 라이브 시험(관리자)

1. 합치기 → 브리지 다시 띄우기 → 인프라 `config.source == "repo"`, 기억 파일에 `ronanlab-infra` 확인
2. `config/notion.toml [ronanlab-infra] ref`를 **인프라 저장소에서 `.foreman/notion.toml`이 처음 들어간 커밋의 부모**로 바꾼다(그 커밋은 인프라 저장소에서 `git log --diff-filter=A --format=%H -- .foreman/notion.toml`의 결과 + `^`) → 승인 대기 0 → 브리지 다시 띄우기
3. 기대: 텔레그램 「🛑 ronanlab-infra의 .foreman/notion.toml을 읽지 못해 게시를 멈췄습니다(<sha>^에 파일이 없습니다) …」 한 번, `GET /api/publish?project=ronanlab-infra`의 `config.halted == true`, `POST /api/publish`(force 없는 한 쪽 게시)가 409 `halted: true`(Notion에 아무것도 가지 않음), 서기 화면 인프라 기술문서 줄 옆에 사유
   - 주의: 그 ref에는 인프라 docs도 옛 판이다 — 멈춰 있으니 게시되지 않지만, 시험 동안 [지금 맞추기]를 누르지 않는다(눌러도 거절)
4. `ref = "origin/main"`으로 되돌리고 브리지 다시 띄우기 → 「…다시 읽었습니다 — 게시를 다시 돌립니다」 한 번, `config.halted == false`

## 되돌리는 법

- 코드: 이 브랜치의 커밋을 `git revert` → 브리지 다시 띄우기. `.run/notion_repo_config.json`은 남아도 옛 코드가 읽지 않는다(지워도 됨)
- 한 프로젝트만 FOREMAN 칸으로: `DELETE /api/publish/repo-config?project=<이름>`(관리 토큰, 저장소 파일을 먼저 지운 뒤)
- 모든 기억 지우기: `.run/notion_repo_config.json`을 지우고 브리지 다시 띄우기
