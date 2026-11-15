# 문서 점검: 코드(main 9a7c22d)와 안 맞는 곳 (11-16, 조사, 관리자 410 일감)

보고만 한다. 아무것도 고치지 않았다. 서기들이 맡은 다섯 docs(`style_guide`, `11_foreman_dispatch`, `operations`, `11_worktree`, `11_handoff_v2`)와 `notion/`, `portfolio/`는 보지 않았다.
본 것: `README.md`, `CLAUDE.md`, `docs/01`, `02`, `10`, `11_handoff`, `12`, `13`, `14`, `15`, `roles`. 문서별로 Explore를 나눠 돌렸고, 아래는 코드에서 직접 다시 확인한 것만 적었다(확인 방법은 맨 끝).

## 어긋난 곳

고칠 쪽은 문서, 코드, 사람 판단 중 하나다.

| # | 문서(파일, 절) | 문서가 말하는 것 | 코드가 하는 것(파일) | 근거 커밋 | 고칠 쪽 |
|---|---|---|---|---|---|
| 1 | `docs/12_scribe.md` 1절 일감 표(38~46줄), 65, 78, 189~193, 218줄 | 일감 종류가 `sync`, `loss`, `polish`이고 「시킬 일 셋」이다. `polish`는 `claude -p` 한 번으로 돈다 | `TASKS`는 `doccheck`, `trim`, `later`, `docfix`, `portfolio`, `techdoc`, `publish` 일곱이다(`bridge/scribe_room.py` 27~44줄). 세션으로 뜨는 것은 `publish`를 뺀 여섯. 문서에 `doccheck`, `docfix`, `publish` 설명이 없다(`docs/12_scribe.md`에서 두 이름 0건) | 일감 이름은 11-06 `ccf0c0e` 무렵, 지금 모양은 `16dcb3a`, `b97ff43` 쪽. 사라진 시점은 확인 못 함 | 문서 |
| 2 | `docs/13_demo_capture.md` 57줄 | 녹화 명령에 `--as webm,gif` | `tools/screen.py`에 `--as`가 없다. `--webm`(플래그)이 있어야 WebM도 만들고 GIF는 늘 만든다(468줄) | 설계 `5583ced`, 구현 `4876338`(11-06) | 문서 |
| 3 | `docs/13_demo_capture.md` 36줄, 서기 지시문 영상 줄 | 시연 주소가 `/?theme=office&demo=<대본>` | 도구는 `/office?probe=1&theme=…&demo=…&hold=1`을 연다(`tools/screen.py` 218줄). `bridge/static/js/demo.js` 머리 주석은 `/?demo=`. `/`가 `/office`로 이어지는지는 안 봄 | 확인 못 함 | 문서(+주석), 사람 판단 |
| 4 | `docs/13_demo_capture.md` 62, 98줄 | GIF 3MB, WebM 4MB 안, 5MB 넘으면 실패 | 도구가 막는 것은 `--max-mb`(기본 5.0) 하나. 3MB와 4MB는 서기 지시문에만 있고 검사는 없다 | 확인 못 함 | 문서(검사한다는 말이면 코드) |
| 5 | `docs/13_demo_capture.md` 머리, 6~7절 | 「13a~13e 만듦」, 영상 V1~V7과 글별 사진 표가 옛 10편 기준 | 지금 `portfolio/`는 00~09의 새 편 목록이다. 5줄이 옛 10편 기준이라고 밝히긴 한다. 9절 「정할 것」은 열린 채 | `16dcb3a` 화면 축 | 문서 |
| 6 | `README.md` 449줄 | 문서만 바뀐 빌드 건너뜀 조건에 `config/portfolio.toml` | 그 파일은 없다. 읽던 코드도 없다. 단 이 줄은 런슈즈 쪽 Jenkinsfile 규칙을 옮긴 것일 수 있어 사실이 바뀐 것인지 모른다 | 삭제 `16dcb3a`(`c9f7739`) | 사람 판단(런슈즈 Jenkinsfile을 보고 줄에서 뺄지) |
| 7 | `README.md` 133~134줄(3.2 그림) | 상태 hook 목록에 `PostToolUse`, `PermissionRequest`는 없다 | 실제 hook 설정은 UserPromptSubmit, Stop, StopFailure, SessionEnd, SubagentStart, SubagentStop, PreToolUse, PermissionRequest(`deploy/hooks/foreman-hooks.json`). `PostToolUse`는 없다. 승인 요청 경로는 3.3 본문(381줄)에만 나온다 | 확인 못 함(옛 서술) | 문서 |
| 8 | `README.md` 607줄 | 파드로 옮길 수 있는 정적 HTML과 JS가 약 1,260줄 | `bridge/static/js/*.js` 합계 10,920줄 | 줄이 들어간 것은 `25357f1`(11-03) | 문서(숫자를 빼거나 고침) |
| 9 | `README.md` 863줄(알려진 한계) | `bridge/handoff.py` `spawn` 797~807, `will_worktree` 876~885 | `spawn` 799, `spawn_new` 811, `will_worktree` 878. 뜻은 아직 맞다. 줄 번호만 밀렸다 | `7ccb55f`, `a0982c7`, `8d12fd0` | 문서(줄 번호를 함수 이름으로) |
| 10 | `CLAUDE.md` 「역할을 가르는 기준」 조사 줄 | 「읽고 알아본다. 고치지 않는다」 | 조사는 `log/`에 새 파일을 쓴다(`config/roles.toml` `inspector_allow`, `bridge/roles.py` 한 줄 설명 「…결과 log만 씁니다」, `docs/roles.md`). 같은 줄 안에서 `docs/roles.md`와 다르다 | `8d12fd0`가 CLAUDE.md에 6줄을 더하며 반영 안 함 | 문서(CLAUDE.md는 관리자가 사용자에게 먼저 물은 뒤) |
| 11 | `docs/11_handoff.md` 1~5, 60, 62~65줄 | 1판이 기본인 설계. `GET /api/sessions/{id}/summaries` 경로. 요청 본문 `{kind, mode}`, spawn은 `{summary_id\|null}` | `fmt` 기본값이 `"v2"`(`bridge/api/handoff.py` 21줄), 1판은 `fmt=v1`로만. `/summaries` GET 경로는 없고 `GET /sessions/{sid}/handoff`가 `summaries`로 같이 준다(72~76줄). 본문에 `fmt`, spawn에 `replace`, `note`가 더 있다(28~31줄). 머리에 「2판이 기본」 안내 없음 | `ee966ec`가 이 문서에 마지막으로 닿음. 칸 추가 시점은 확인 못 함 | 문서 |
| 12 | `docs/11_handoff.md` 3~4줄 | 「캐릭터 재배치, 포먼 채용은 11단계에 남는다」 | `migrations/0016_foreman_dispatch.sql`, `0017_character_reassign.sql`이 있고 `docs/11_foreman_dispatch.md`가 끝남으로 올라 있다. 설계 시점 글이라 낡은 정도는 약하다 | `0016`, `0017`(11-05) | 문서(머리 한 줄) |
| 13 | `docs/roles.md` 2절 표 조사 줄(35줄), 3절 3번과 9번 | 조사가 쓰는 곳은 「`log/` 아래 새 파일, 이 세션이 만든 파일」 두 갈래. 조사의 스스로 끝남 언급 없음 | 판정에 「git이 아직 모르는 파일」 한 갈래가 더 있다(`bridge/roleguard.py` 298줄 `ls-files --error-unmatch`). 조사는 보고하고 턴을 마치면 브리지가 스스로 끝낸다(`bridge/inspector_close.py`, 끄는 값 `config/handoff.toml [inspector_close]`). `WORKER_ROLES`에서 조사가 빠진다(`bridge/roles.py`) | `8d12fd0`, `e4c7b9b` | 문서 |
| 14 | `docs/roles.md` 3절 3번 | 「다른 역할 색과 겹치지 않게(`tests/js/theme.test.mjs`)」 | 시험은 옷 색(`ROLE_CLOTH`)만 본다. 배지 색(`ROLE_COLOR`)끼리의 겹침은 어느 시험도 안 본다 | `a0982c7` | 사람 판단(문서를 옷 색이라고 좁힐지, 배지 색 시험을 더할지) |
| 15 | `docs/14_dispatcher_note_wake.md` 12줄 | 기본 테마 감독실 캐릭터 이름이 「디스패처」 | 기본(도형) 테마는 `"foreman": {"name": "감독"}`(`bridge/static/themes/plain/theme.json` 4줄). 「디스패처」는 화면 말 약속과도 부딪힌다 | `a0982c7`(theme.json 4개를 건드림) | 문서 |
| 16 | `docs/14_dispatcher_note_wake.md` 4절 | 계획을 못 세우면 「디스패처가 살펴볼 계획을 세우지 못했습니다」를 보낸다 | 실제 글은 「⚠ {종류} 살펴볼 계획을 세우지 못했습니다(…). 실패 알림을 직접 봐 주세요」(`bridge/wake.py` 113, 138줄) | 확인 못 함 | 문서 |
| 17 | `docs/15_usage.md` 2절 환산 표 | 모델 세 줄(Opus, Sonnet, Haiku 5.5) | `config/usage.toml`에 `[prices.fable]`이 있고 한도 줄 `weekly_fable`도 있다. 표만 빠졌다 | 확인 못 함 | 문서 |
| 18 | `docs/12_scribe.md` 294줄 | `POST /api/postit` 응답은 201과 200 | 거절(`Refused`)이면 409 `{"refused": …}`(`bridge/api/postit.py` 116, 130, 143줄). `/save`, `/refresh`, `/check`, `/close`도 같다 | `db4f3e7` 무렵 | 문서 |
| 19 | `docs/12_scribe.md` 286줄 근처(postit 설정 설명) | `config/scribe.toml`의 `[postit]`만 설명 | 파일에는 `[nudge]`(`new_min=3`, `oldest_days=3`)만 있고 문서에 없다. `[postit]`은 없고 코드 기본값(문서도 그렇게 적어 맞다) | 확인 못 함 | 문서 |
| 20 | `README.md` 문서 표(892~908줄), 기준 문서 | `docs/roles.md`가 없다 | `docs/roles.md`가 있고 CLAUDE.md가 역할 기준으로 가리킨다 | `a0982c7` | 문서 |
| 21 | `README.md` 문서 표 상태 칸 | 사용량 「1만 끝(11-08)」, kickoff 「4 남음」 | `docs/15_usage.md` 머리는 1, 2, 4가 끝남. 나머지 칸은 문서 머리를 끝까지 대조하지 못함 | 확인 못 함 | 문서(불확실) |

## 코드가 이상해 보이는 곳

문서가 맞고 코드가 틀려 보이는 곳이다. 이번 점검에서는 확실한 것이 없다. 아래는 코드를 고칠지 사람이 볼 만한 것들이다.

- `bridge/static/js/demo.js` 머리 주석이 `/?demo=`로 적혀 있다(3번). 도구와 서기 지시문이 쓰는 주소와 어긋난다. 코드가 틀린 게 아니라 주석이 낡았을 가능성이 크다.
- `config/scribe.toml` 머리 주석과 `bridge/api/scribe.py` `/inbox` docstring이 11-15에 빠진 머리줄 [＋ 할 일] 「서기 정리」를 아직 말한다(`docs/12_scribe.md` 235, 261줄은 맞게 옛 길이라고 적음). 주석 한두 줄이라 관리자 규칙 3번(주석 오타)에 든다.
- `config/notion.toml` 32줄 근처 저장소 칸 키 목록 주석에 `src`가 없다. `bridge/notioncfg.py` `REPO_KEYS`에는 있다. 주석만 낡았다.
- `docs/13_demo_capture.md` 4번처럼 3MB, 4MB 상한을 서기 지시문만 말하고 도구는 검사하지 않는다. 문서가 「도구가 막는다」는 뜻이었다면 코드가 모자란 것이다. 사람이 정한다.

## README에서 볼 것

README를 손볼 때 쓸 목록이다. 지금 고치지 않는다.

- 449줄 `config/portfolio.toml`(6번)
- 133~134줄 hook 목록(7번)
- 607줄 화면 JS 줄 수(8번)
- 863줄 줄 번호 인용(9번)
- 문서 표에 `docs/roles.md` 추가, 사용량과 kickoff 상태 칸(20, 21번)
- **브리지 밖 알림과 훅 통과 기록이 README에 없다.** 3.12 systemd 줄(616줄)은 「유닛 + 사람이 부르는 스크립트」까지다. 코드에는 `deploy/systemd/foreman-bridge.service`의 `OnFailure=foreman-bridge-alert.service`, `scripts/foreman-bridge-alert.sh`, `bridge/hookmiss.py`, `scripts/foreman-decide.sh`가 있다(`cd14ed6`, `58f9f03`). 이 일은 `docs/operations.md`에는 반영돼 있다. 381줄의 「브리지가 꺼져 있으면 hook은 아무것도 돌려주지 않는다. 허용 쪽으로 새지 않는다」도 통과 기록 이전 서술이라, 통과는 이제 기록으로 남는다는 말을 더해야 한다. 맨 앞 원칙(조용한 고장은 스스로 알린다)과 바로 닿는 줄이다
- **노션 기술문서(`notion/`)와 `portfolio/` 길이 README에 한 줄도 없다.** 107줄은 「프로젝트마다 두는 서기로 바꿨다」까지다. README가 기능 설명을 docs로 미루는 방침이면 그대로 둬도 된다. 정할 것은 사람 몫
- 포스트잇은 859줄 알려진 한계 도입문에만 나온다. 로드맵과 나중에 할 일 표를 11-15(`74e722d`)에 뺐으므로 구멍은 아니다. 사용법 한 줄(`POST /api/postit`)을 둘지는 정하기 나름
- 「기록(`log/`)」 표(910~941줄)는 31줄이고 실제 log는 280개 넘는다. 일부 목록인지 전체 목록인지 표에 적혀 있지 않다. 끊어진 링크는 0개였다

## 맞았던 것

- CLAUDE.md의 절 번호(`11_worktree` 6, 8절, `12_scribe` 11절, `operations` 4, 5절, `style_guide` 4-1절), 가리키는 파일, 세 API 요청 꼴(`escalate`, `postit`, `worktree`), 마이그레이션 0018, `.github` 없음은 모두 맞았다
- `docs/roles.md`의 역할 값, 화면 이름, 색, 권한표, 새 역할 체크리스트가 가리키는 파일 열두 개는 모두 코드와 같다. `ROLE_INFO`와 `roles.js`도 같다
- `docs/14`, `docs/15`의 설정 값과 숫자(`wake.toml`, `usage.toml`)는 맞았다
- `docs/10_office_design.md`는 확인한 상수, 함수, 포스트잇 칸이 모두 맞았다(방 배치와 말풍선 세부 숫자는 일부만 봄)
- `docs/12_scribe.md`의 노션 기술문서와 포트폴리오 길, 숫자(`TECHDOC_DAYS=2`, `LINE_WRAP=1500`, 포스트잇 `MAX=8000` 등)는 맞았다
- `docs/01_kickoff.md`, `docs/02_cloudflare_tunnel.md`는 어긋남을 못 찾았다(터널 이름 등 서버 실제 상태는 코드로 못 봄)
- 서브에이전트가 어긋남이라고 했으나 직접 보니 아니었던 것: 「인계 요약 저장」 알림 글(`bridge/handoff.py` 593, 656줄에 있다)

## 못 본 것, 불확실

- `docs/10_office_design.md` 484줄 중 방 배치, 말풍선, 머리 위 표시 세부 숫자는 이름이 나오는 상수와 함수만 봤다
- `docs/12_scribe.md`의 DB 수치 절(273줄 근처, 438 기간), 재료 폴더 경로와 권한(83줄)은 DB와 파일 시스템을 보지 않았다
- README 3.3 승인 규칙을 `config/approval.toml`과 한 줄씩 대지는 않았다
- 근거 커밋을 못 찾은 항목은 표에 「확인 못 함」으로 적었다
- 이 점검의 화면 말 시험(`tests/data/screen_words.toml`)이 잡는 옛 이름은 세지 않았다

## 확인 방법

서브에이전트 4개(Explore, 읽기 전용)의 보고 가운데 표의 항목은 직접 코드를 열어 다시 확인했다. 직접 확인한 것: 일감 표, `--as`와 `--webm`, hook 목록 json, JS 줄 수, `spawn`과 `will_worktree` 줄, 기본 테마 이름, `usage.toml` fable, `roleguard` 판정, 409 응답, `/summaries` 경로 없음. 서브에이전트는 모두 끝났고 남은 것은 없다.

## 규칙 위반 없음
