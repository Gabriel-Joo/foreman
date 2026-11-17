# 노션 원고 근거 범위 검사 (11-17, foreman-5)

관리자 410의 조사 일감(사용자 지시 19의 2번). `notion/` 원고 50편의 근거 표시를 원문과 맞대어, 줄 번호가 아니라 **범위**가 어긋난 곳을 찾았다. 기준 커밋 `910bbad`. 원고, docs, 코드는 고치지 않았다.

## 어떻게 봤나

- 원고 50편, 근거 표시 3,793개(`[code:]` 2,454, `[log:]` 949, `[docs:]` 220, `[c:]` 169, `[t:]` 1). code 표시는 줄 없이 파일 단위다
- 원고 머리 주석의 읽은 커밋은 둘이다. `e5d584b`(11-15 19:15) 34편, `9a7c22d`(11-16 05:55) 16편
- 다섯 묶음(00~03, 04~07, 08~09, 10~13, 14~16)을 Explore 서브에이전트 다섯이 병렬로 봤다. 숫자, 「모든」 「만」 「늘」 같은 범위 말, 프로젝트 이름이 든 문장을 먼저 봤고, 범위까지 맞대 본 인용은 모두 합쳐 약 590개다(묶음별 약 200, 90, 120, 150, 110). 나머지 단순 서술 인용은 범위를 보지 않았다
- 아래 항목은 서브에이전트 보고를 받은 뒤 관리자 일감 세션(이 세션)이 원고 줄과 근거 원문을 직접 다시 연 것만 적었다. 다시 열어 보니 줄 번호가 다른 것은 바로잡았고, 범위 문제가 아니라 낱말 문제였던 것은 「글만 다듬으면 되는 것」으로 내렸다
- 읽은 커밋 `e5d584b` 뒤 코드를 바꾼 커밋은 다섯이다: `883c4c9`(hook 견본 한도), `cd14ed6`(브리지 밖 포기 알림과 hook 통과 기록), `58f9f03`(hook 스크립트 입력 바이트), `7ccb55f`(통째로 지우기 막음), `a312dfc`(노션 변환기). `9a7c22d` 뒤에는 docs 커밋만 있다. 그래서 어긋남의 대부분은 「코드가 바뀌어서」가 아니라 **원고를 쓸 때 이미 옛 log 시점의 수를 지금처럼 썼거나 처음부터 잘못 센 것**이다

## 확실히 틀린 것 (11건)

| # | 원고 파일:줄 | 문장 요지 | 근거 | 그때 범위 / 지금 범위 |
|---|---|---|---|---|
| 1 | `notion/04_approval.md:74` | PreToolUse가 승인 정책보다 먼저 거부하는 넷(스키마 잠금, 다른 저장소, pgrep, 역할 규칙)은 「프로젝트가 observe여도 막는다」 | `bridge/approvals.py:168-182`, `config/roles.toml:11-18` | 원고: 넷 모두 늘 막음. 지금: 스키마 잠금, 다른 저장소, pgrep은 승인 모드와 상관없이 막지만, 역할 규칙은 `roles.cfg.mode == "enforce"`이거나 규칙에 `enforce`가 붙을 때만 막는다. 지금 `mode = "observe"`, `projects = ["foreman"]`, `enforce = ["inspector-write"]`라서 FOREMAN 세션의 조사 쓰기 하나만 막고 나머지 넷은 기록만 한다. 같은 묶음 `05_roles/02_guards.md`는 이 범위를 맞게 썼다 |
| 2 | `notion/11_notify.md:224-242`, `:252`, `:314` 표 | 브리지 밖 알림은 `python -m bridge.telegram`, 그 쓰임은 백업 실패 하나. 토큰 파일 하나인 까닭 첫째 「보내는 길이 하나(브리지)」. 「어디서 오나」 표의 브리지를 거치지 않는 줄은 DB 백업 실패 하나 | `deploy/mysql/backup.sh`, `bridge/telegram.py`. 원고 읽은 커밋 `e5d584b` | 그때: 브리지 밖 알림 길 하나. 지금: `cd14ed6`(11-15 20:08)이 `deploy/systemd/foreman-bridge.service`의 `OnFailure`로 `scripts/foreman-bridge-alert.sh`를 더했다. 이 스크립트는 `bridge.telegram`도 `notification` 표도 거치지 않고 curl과 `.env.telegram`을 직접 읽는다(스크립트 4, 19행). 「`bridge.telegram` 쓰임은 백업 하나」는 글자 그대로는 맞지만, 절이 다루는 범위가 하나에서 둘이 됐고, 「보내는 길이 하나」와 표는 어긋난다. 머리 주석 「다루는 곳」에도 두 파일이 없다 |
| 3 | `notion/10_scribe.md:74` | `config/scribe.toml`의 `[nudge]` 값은 「지금」 알려진 한계 쓰기 몫에만 쓰인다 | `bridge/scribe_room.py:50-72` | 지금: `scribe_room.nudge_of`, `nudge_conf`를 부르는 곳은 시험(`tests/test_stage2_db.py:1563-1567`)뿐이고, 서기 말풍선은 `bridge/postit.py:509`의 `nudge_of`가 정한다. `[nudge]` 값은 어디에서도 쓰이지 않는다. 같은 묶음 `10_scribe/01_room.md:230`은 「옛 기준」으로 맞게 써서 두 편이 서로 어긋난다. 원고는 함수 docstring(`scribe_room.py:61`)을 따른 것으로 보인다 |
| 4 | `notion/10_scribe/04_notion.md:285` | 원고 나무(하위 페이지 만들기, 「정렬 중」을 거친 차례)는 가짜 Notion으로만 시험했고 「이 원고가 처음 올라갈 때가 그 첫 실제 시험이다」 | `log/foreman-4_techdoc_portfolio_path_20261115.md`(올리기 전 log) | 그때: 아직 안 올림. 지금: `log/foreman-4_notion_first_publish_20261115.md`(커밋 `1a854cf`, 11-15 20:13)가 50편을 실제 Notion에 올려 자리, 차례, 섞임이 모두 「맞음」이라고 적었고(15, 16, 21행), 11-16에 다시 게시했다. 원고의 읽은 커밋 `9a7c22d`는 그 뒤다. 아직 실제로 못 본 것은 「사람이 둔 글이 섞였을 때」와 「사람이 고친 블록에서 멈추는지」뿐이다 |
| 5 | `notion/02_ingest/02_hooks.md:124` | 이 PC의 모든 CC 세션이 하루에도 「수백 번」 hook 스크립트를 부른다 | `log/stage1_bridge_db_result.md` | 걸린 log에는 이 수가 없다. 실측은 `log/manager410_overhead_20261115.md:246`: 하루 `/hooks/pre` 호출 11-08 1,336, 09 5,213, 10 3,591, 11 3,213, 12 2,716, 13 5,474, 14 4,222, 15 9,373. 수천 번 단위이고, PreToolUse만 센 것이라 다른 hook까지 더하면 더 크다 |
| 6 | `notion/01_structure/01_placement.md:63`, 표 `:65-70` | 「이 서버에는 이미 MySQL이 셋 있었다」, 후보 표 세 줄 | `log/01_kickoff_result.md` MySQL 줄 | log: 클러스터 파드 둘(펫퍼민트, 런슈즈)과 호스트 도커 둘(3306 `mysql`, 3307 `runshoes-mysql-dev`)로 넷. 표에 3307이 빠졌다. 같은 원고 `:75`는 3306과 3307을 둘 다 말해 원고 안에서도 어긋난다 |
| 7 | `notion/15_db/01_tables.md:7`, `:23` | 표가 스물아홉 개이고, 그 말고 `schema_migrations`가 하나 더 있다 | `migrations/*.sql`, `bridge/db/migrate.py:30` | 마이그레이션이 만드는 표는 28개(이름 28개, 지우거나 이름을 바꾼 마이그레이션 없음)이고 `schema_migrations`를 더해 29개다. `migrations/`는 `e5d584b` 뒤 바뀌지 않아 처음부터 하나 많게 셌다. `notion/15_db.md:19`의 「표 29개(`schema_migrations` 포함)」가 맞고 두 편이 어긋난다 |
| 8 | `notion/14_screen/05_check.md:240` | 화면 말 목록에 「서기 몫 7줄이 있다」 | `tests/data/screen_words.toml` | 그때(`e5d584b`): `[[scribe]]` 7줄. 지금: 0줄. `6fcf7ad`(11-15 19:52, 읽은 커밋 뒤)가 7줄을 모두 지웠다. 나머지 수(바꾼 이름 34 등)는 같다. 같은 절 `:259`의 요약 예시 「서기 몫 13줄 남음」도 지금 값과 다를 가능성이 크다(pytest를 돌리지 않아 지금 값은 못 봄) |
| 9 | `notion/09_dispatcher/03_overlap.md:76` | 떼는 한글 조사가 「스물세 개」 | `bridge/overlap.py:38-39` `_JOSA` | 코드는 24개(첫 줄 11, 둘째 줄 13). `overlap.py`는 `e5d584b` 뒤 바뀌지 않아 처음부터 잘못 셌다 |
| 10 | `notion/09_dispatcher/01_plan.md:70` | 「세 저장소의 docs만 해도 수백 KB」 | `docs/11_foreman_dispatch.md`(이 문구 없음, 원고가 쓴 수) | 지금 등록 프로젝트는 넷(`migrations/0029_seed_ronanlab_infra.sql`, 11-10 인프라). 같은 원고 `:80`은 「프로젝트가 넷이면」이라고 써서 원고 안에서 어긋난다 |
| 11 | `notion/09_dispatcher/02_note_wake.md:86` | 노트 상한 2000토큰은 「프로젝트 셋이 2000씩 써도 넘치지 않는 크기」 | `docs/14_dispatcher_note_wake.md:75`(11-08 처음 커밋 `8907665`) | 그때(11-08): 프로젝트 셋. 지금: 넷(인프라 11-10). 넷 × 2000 = 8000도 묶음 1만~2만 안이라 결론은 그대로지만, 근거가 쓰인 때의 수를 지금 수로 썼다 |

## 판단이 필요한 것 (13건)

| # | 원고 파일:줄 | 문장 요지 | 근거 | 그때 / 지금 | 왜 판단이 필요한가 |
|---|---|---|---|---|---|
| 1 | `notion/00_foreman.md:147` | 「인프라처럼 새로 붙인 프로젝트는 처음엔 묻지 않고 지켜보기만 하는 모드로 둔다」 | `config/approval.toml:149-163` | 인프라가 observe인 까닭은 주석상 「인프라 묶음 1(노드 증설, 가용성) 동안 사용자가 승인 카드를 풀었다, 끝나면 enforce로」인 임시값이다. 런슈즈, 펫퍼민트는 「관찰로 시작한다」는 주석이 따로 있다 | 「새 프로젝트는 관찰로 시작」이라는 규칙은 런슈즈, 펫퍼민트로는 있다고 볼 수 있지만, 예로 든 인프라의 까닭은 다르다. 한 경우의 까닭을 일반 규칙의 예로 넓혔는지 정해야 한다 |
| 2 | `notion/04_approval.md:27`, `:53`, `:55`, `notion/04_approval/02_flow.md:94`, `:110` | 「세 프로젝트 모두 자동 모드」(:27, :55는 「세어 보니」로 과거 조사, :53 앞뒤, 02_flow :94, :110은 현재형) | `log/stage5_approval_result.md`(11-02, FOREMAN, 런슈즈, 펫퍼민트) | 그때: 프로젝트 셋. 지금: 승인 정책에 넷(인프라 11-10) | 02_flow `:94`, `:110`은 현재형이라 인프라까지 덮어야 하는데, 인프라 세션이 자동 모드인지는 확인하지 못했다. 틀렸다고 단정할 수 없다 |
| 3 | `notion/01_structure/01_placement.md:260` | 브리지는 화면과 API용, hook용, 웹훅용 토큰을 따로 두고, 인증 없이 열린 경로는 `/healthz` 하나뿐 | `bridge/config.py`, `config/tokens.toml:11` | 설정 칸의 토큰은 셋이 맞다. 그런데 프로젝트 토큰(`config/tokens.toml` `enabled = true`, 11-11)이 원고를 쓰기 전부터 켜져 있다 | 「셋」을 설정 칸 수로 읽으면 맞고 토큰 종류로 읽으면 넷이다. `/healthz` 「하나뿐」도 `02_startup.md`는 「데이터를 내는 경로 가운데」로 좁혀 썼다(화면 파일은 인증 없이 나간다) |
| 4 | `notion/01_structure/02_startup.md:179` | 연결이 끊기면 hook 스크립트는 아무것도 내지 않고 「조용히」 끝난다 | `bridge/approvals.py`, 원고 읽은 커밋 `e5d584b` | 그때: 흔적 없음. 지금(`cd14ed6` 뒤): 출력은 여전히 없지만 `.run/hook_miss.log`에 한 줄을 남긴다 | 「아무것도 내지 않는다」는 맞고 「조용히」는 이제 반만 맞다. 9a7c22d 판 `02_ingest/02_hooks.md`는 기록을 적었다 |
| 5 | `notion/03_session.md:332` | 「CC 안에서 Esc가 취소로 쓰이는 곳만 48곳」 | `log/prompt_vs_dialog_20261113.md` | 48은 11-13 그때 CC 실행 파일의 문자열 수다 | 현재형으로 썼다. CC 판이 바뀌면 수가 달라질 수 있어 「그때 판」을 붙일지 정해야 한다 |
| 6 | `notion/14_screen/02_office.md:88` | `plain` 테마의 구역은 「감독실, 책상, 서버랙, 창가, 전화 다섯뿐」 | `bridge/static/themes/plain/theme.json` `layout.zones` | 키가 9개: 위 다섯과 `manager`, `designer`, `infra`, `lounge_seats`. 11-09, 11-10에 더해졌고 원고를 쓸 때도 같았다 | 더해진 넷은 좌석 묶음과 출하 줄이다. 「구역」을 방 칸으로만 읽으면 다섯이 맞다 |
| 7 | `notion/09_dispatcher/04_managers.md:28` | 「지금은 네 프로젝트에 관리자를 세운 기록이 있다」 | `log/coder_c_wave2_20261111.md`, `log/runshoes_manager_20261112.md` | 두 log는 인프라와 런슈즈까지만 덮는다. 펫퍼민트 관리자는 `config/notify.toml` 11-13 주석에 나온다 | 문장은 사실일 수 있지만 걸린 근거가 네 프로젝트를 덮지 못한다. 실제 관리자 세션은 DB라 확인하지 않았다 |
| 8 | `notion/08_handoff.md:37`, `notion/08_handoff/01_loss.md:60` | 「압축은 문서가 있든 없든 세션의 기억을 같은 비율로 깎는다」 | `log/foreman_compaction_loss_20261105.md`, `log/runshoes_compaction_loss_20261105.md` | 표본은 세션 둘(런슈즈 180/282, FOREMAN 90/142, 63~64%) | log에도 같은 말이 있지만, 표본 둘을 일반 규칙처럼 썼다 |
| 9 | `notion/06_sessions.md:44` | 「FOREMAN 저장소에서만 서기실이 모르는 계획 길 서기가 15개」 | `log/foreman-4_scribe_two_paths_20261115.md:21-28` | log 표 마지막 칸: foreman 15, petmint-rag-chatbot 1, runshoes 0, ronanlab-infra 0 | 「FOREMAN에서만」은 펫퍼민트 1을 덮지 못한다. 그 1이 같은 표의 「260 doccheck」와 같은 세션이면 원고가 맞는데, log만으로는 가를 수 없다 |
| 10 | `notion/05_roles/02_guards.md:314` | 런슈즈에서 다시 돌려 보니 해석기 안 쓰기 「이 꼴이 200건이 넘었다」 | `log/inspect_roleguard_20261114.md` | log: 「해석기 찾아바꾸기 꼴」 런슈즈 206, 「해석기 쓰기」 448 | 「이 꼴」이 앞 문장 전체(파일 열어 쓰기, 448)인지 소스 찾아바꾸기(206)인지 문장으로는 가를 수 없다. 뒤 문장으로 보면 206 쪽이다 |
| 11 | `notion/08_handoff/02_summary.md:177` | 바뀐 상태를 「보는 것은 네 가지다」 | `bridge/handoff_state.py:72-130` | 코드는 ①~④ 넷이고, 바로 아래 표는 다섯 줄(작업방이 있나와 브랜치 새 커밋을 나눔) | 코드와는 맞고 표와 수가 어긋나 보인다. 글 다듬기로 끝날 수도 있다 |
| 12 | `notion/10_scribe.md:22` | 서기 잉크 갈색은 포먼 금색과 다른 역할의 「파랑, 초록, 보라」와 겹치지 않게 고른 색 | 근거 표시 없음(출처는 `docs/12_scribe.md` 11-06로 보임). 지금 `bridge/static/js/roles.js` | 지금 다른 역할 색: 코더 파랑, 조사 초록, 관리자 빨강, 디자이너 분홍. 보라가 없다 | 역할이 다섯이 되기 전의 색 목록으로 보인다. 근거 표시가 없어 그때가 언제인지도 원고로는 알 수 없다 |
| 13 | `notion/15_db.md:19-20` 등 | 「이 편을 쓸 때」 `event` 약 24만 행, 약 280MB, DB 약 320MB, 덤프 약 36MB 하루 약 3MB | 원고가 시점을 밝힘 | 백업 폴더는 11-15 37.4MB, 11-17 45.0MB(서브에이전트가 잼, 하루 약 3.5MB로 빨라짐) | 시점을 적은 글이라 틀린 것은 아니다. 고칠지는 사람이 정한다 |

## 글만 다듬으면 되는 것

- `notion/04_approval.md:123`, `notion/04_approval/02_flow.md:298`: 「3번 넘게 걸렸는데」. 코드(`bridge/api/approvals.py:88`)는 `n >= 3`, 즉 3번 이상이다. 코드 주석도 「3번 넘게」라 범위가 아니라 낱말 문제다
- `notion/04_approval.md:27`, `notion/04_approval/01_rules.md:16`은 「승인 18건」, `01_rules.md:236`은 「19번」. 근거 `log/stage5_approval_result.md`가 표(18)와 본문(19)으로 갈려 있다. 하나로 맞춘다
- `notion/04_approval/01_rules.md:236`: 「런슈즈와 펫퍼민트에서 git push 79건, kubectl 132건, rm -r 60건」. log는 push 79를 런슈즈 것으로만 적었고 kubectl, rm -r은 두 프로젝트 합계다. 「합계」를 붙이거나 push만 런슈즈로 쓴다
- `notion/04_approval/02_flow.md:63`, `:68`: hook 통과 기록의 브리지 쪽 갈래에 `bridge/approvals.py`의 「역할판정예외」가 빠졌다
- `notion/05_roles.md`, `notion/05_roles/01_roles.md`(읽은 커밋 `e5d584b`): 판정이 실패할 때 `cd14ed6` 뒤 생긴 hook 통과 기록 한 줄을 적지 않았다. `05_roles/02_guards.md`는 적었다
- `notion/01_structure.md:177-228` 모듈 지도: `cd14ed6`이 만든 `bridge/hookmiss.py`가 없다
- `notion/01_structure/01_placement.md:65-70` 표: 위 확실 6번을 고칠 때 3307 줄을 더한다
- `notion/15_db/01_tables.md:7`: 「다섯 덩어리로 묶고」. 본문 절은 1~5 덩어리와 6절 「되돌리기용 표」(표 하나)다. 6절을 덩어리로 칠지 맞춘다
- `notion/08_handoff/04_move.md:95`(「여섯 갈래」 중 다섯을 보임)와 `notion/08_handoff/01_loss.md:172`(「다섯 갈래」): `bridge/losscheck.py` `OUTCOMES`는 running 포함 여섯, 화면은 다섯이라 둘 다 맞다. 같은 말로 맞춘다
- `notion/09_dispatcher/04_managers.md:198`: 30초로 줄인 근거(17.4초 세 번)가 `log/overhead_marks_20261113.md`로 걸렸는데 그 log에는 17.4초가 없다. 실제 근거는 `log/manager318_overhead_20261113.md`, `log/overhead_fix_20261113.md`
- `notion/10_scribe/04_notion.md:145`: 인프라 칸에 「쓰기 범위만」이라 했는데 `config/notion.toml` `[ronanlab-infra]`에는 `github`, `ref`도 있다
- `notion/10_scribe.md:88`: 「542였다」는 log에서 「542~546개」(`log/foreman-4_scribe_retro_removal_20261115.md:32`)

## 그 밖에

- 본 원고: 50편 전부. 범위까지 맞대 본 인용: 약 590개(전체 3,793개 가운데). 맞대 본 수와 상수(역할 다섯, 상태 넷, 테마 넷, ask 규칙 열둘, 승인 대기 3600/3630/3660초, 마이그레이션 33개, js 파일 31개, 시험 파일 89개, 알림 접두어, 사용량 설정 등) 대부분은 원문과 같았다
- 「한 프로젝트 얘기를 모든 프로젝트로 쓴 것」은 확실한 것이 없었다. 가까운 것은 판단 1(인프라 까닭을 일반 규칙의 예로)과 판단 9(FOREMAN에서만)
- 못 본 것
  - 단순 서술 인용 약 3,200개는 범위를 보지 않았다
  - 운영 DB 값(관리자 세션이 어느 프로젝트에 떠 있는지, `event` 행 수, 서기 세션 수), 실제 Notion 페이지 상태
  - 시험 수 1,176과 210, 화면 말 요약 줄의 지금 값(pytest를 돌리지 않았다)
  - 인프라 세션이 CC 자동 모드인지
  - `[c:]` 인용은 커밋이 있는지만 봤고 커밋 내용 범위는 다 보지 않았다
  - log 안의 작은 수치 일부(성능 ms, CC 판 시험 줄)
- 코드가 이상해 보이는 곳
  - `bridge/mask.py:19` `ENV_FILES = (".env.db", ".env.bridge", ".env.telegram")`: 저장소에 있는 `.env.notion`, `.env.project_tokens`가 정확한 값 가리기에 들어가지 않는다(파일 이름만 확인, 값은 보지 않음). 원고 `02_ingest/04_bus.md`는 「비밀 파일 셋」으로 코드와 맞게 썼다
  - `bridge/scribe_room.py:50-72` `nudge_conf`, `nudge_of`, `NUDGE_DEFAULT`: 부르는 곳이 시험뿐인 죽은 코드로 보이고, docstring(61행)이 쓰이는 것처럼 적어 원고 확실 3번을 낳은 것으로 보인다
  - `bridge/hookmiss.py:4` 머리 주석 「스크립트 쪽 7갈래」. `scripts/foreman-decide.sh`의 통과 기록은 8갈래다(원고 `04_approval/02_flow.md`는 8로 맞게 씀)

## 규칙 위반

- **서브에이전트 하나(08~09 묶음)가 Bash 리디렉션으로 파일 하나를 썼다.** 일감은 「파일은 Write로 log 하나만, Bash 리디렉션 금지, 서브에이전트도 같다」였다. 인용 줄을 모으려고 이 세션의 임시 폴더(저장소 밖 scratchpad)에 `s02.txt` 하나를 만들었고, 서브에이전트가 스스로 보고했다. 저장소 안 파일은 건드리지 않았고 그 뒤로 리디렉션은 없었다. 그 파일은 저장소 밖 임시 파일이라 지우지 않고 두었다
- 이 세션(부모)은 규칙 위반 없음. 파일은 Write로 이 log 하나만 만들었고, `pgrep -f`를 쓰지 않았다. 서브에이전트 다섯은 모두 끝났다(돌고 있는 것 없음)
