# 포트폴리오 「판단이 필요한 것」 처리 (서기, foreman-6, 2026-11-17)

관리자 410의 서기 일감(사용자 지시 22의 4번). 대상은 `log/foreman-6_portfolio_scope_check_20261117.md` 「판단이 필요한 것」 19건. 기준 커밋 main `4386b3a`. 항목마다 지금 코드와 설정을 다시 열어 넷(수 바뀜, 기능 생김, 기준에 따라 맞음, 애매함) 가운데 하나로 나눴다. 「이미 풀림」은 오늘 다른 커밋이 이미 고친 것이다. 편 전체를 새로 쓰지 않고 그 문장만 고쳤고, 편 머리 「읽은 커밋」은 그대로 뒀다. 서브에이전트는 쓰지 않았다.

관리자 덧붙임(작업 중 받음): 코더 521이 `portfolio/10_scribe_room.md`를 고치는 중이라, 10편은 건드리지 않고 아래 「521 뒤 볼 것」에만 적었다.

## 항목별

줄 번호는 범위 검사 때(`910bbad`) 것이다. 오늘 커밋으로 줄이 밀린 곳은 지금 줄을 괄호에 적었다.

| 항목 | 종류 | 한 것 | 근거 파일과 커밋 |
|---|---|---|---|
| `05_approval.md:40` 브리지가 꺼지면 원래대로 묻고 허용으로 새지 않는다 | 기준에 따라 맞음 | 「원래대로 스스로 정합니다」로 바꾸고, 허용을 대신 내지 않지만 FOREMAN이 묻기로 한 명령도 auto mode 판단에 맡겨져 꼭 묻는다고 할 수는 없다고 한 줄 풀어 씀 | `scripts/foreman-decide.sh:2-5`(판정이 없으면 아무것도 안 냄, CC가 스스로 정함), `config/approval.toml:12-13`(`pass`는 CC가 정함). `cd14ed6`는 통과 기록만 더했고 동작은 그대로 |
| `05_approval.md:20` 확정할 수 없으면 묻는다 | 기준에 따라 맞음 | 변수가 든 평범한 경로는 고정된 앞부분과 변수가 비었을 때 남는 경로만 보아 통째가 아니면 묻지 않는다고 한 줄 더함 | `bridge/approval.py:372-404` `_protected_delete`(명령 치환으로 시작하면 묻기, 변수 경로는 앞부분과 빈 값만 봄), `config/approval.toml:9, 57-60` |
| `05_approval.md:44` 기간별 표는 클래식 「승인 이력」 | 기준에 따라 맞음 | 패널 「승인 기록」을 펼치면 같은 표가 나오고 클래식에서는 이름이 「승인 이력」이라고 풀어 씀 | `bridge/static/js/opanel.js:79, 113`, `bridge/static/js/render.js:619, 749, 799`(같은 `mountApprovalHistory`). 패널에는 `e508c6d`(11-05)부터 있었다 |
| `06_handoff.md:14, 60` 새 세션은 같은 폴더 | 기준에 따라 맞음 | 60줄에 다른 살아 있는 세션이 있으면 작업방에서 뜨고 「⑂ 새 세션은 작업방에서 뜹니다. …」가 미리 보이며 관리자는 늘 원본 폴더라고 더함. 14줄 「같은 자리」는 캐릭터 자리로 읽혀 그대로 | `bridge/handoff.py:891-903` `will_worktree`(옮기는 세션은 빼고 셈, 관리자 `False`), `bridge/static/js/handoff.js:372` 화면 글 |
| `07_merge.md:30` 늘 사람 승인 나열 | 기준에 따라 맞음 | 커밋 글의 이력 다시 쓰기 말과 서브모듈 바뀜도 사람 승인으로 올라간다고 한 줄 더함. 프로젝트별 `human_paths`는 지금 넷 모두 비어 있어 넣지 않음 | `config/handoff.toml` `[merge_prep.human_always]` `history_words`, `submodules`, `[merge_prep.per_project.foreman]`(빈 칸), `bridge/mergeprep.py:91-101, 221-226` |
| `07_merge.md:36` 사람 승인 카드는 작업 세션 보라색 | 기준에 따라 맞음 | 평소는 관리자 머리 위 「사용자 답 기다림」, 관리자가 없거나 올리지 못했을 때만 작업 세션 보라색이 먼저 오게 문장 차례를 바꿈 | `bridge/api/dashboard.py:496-514` `merge_waits`(`to_manager`), `bridge/static/js/render.js:117`, `bridge/mergeprep.py:643-707`, `bridge/static/js/office.js:3561`(「🔀 합치기 대기 N」) |
| `08_foreman_plan.md:36` 교장에게 모아 넘기는 것 | 기준에 따라 맞음 | 규칙 파일, 문서 목록, 진행 중인 일, 지난 요청은 이름이 나온 프로젝트(또는 그 방)만, 나머지는 최근 커밋과 세션만, 이름이 없으면 전부라고 풀어 씀 | `bridge/foreman.py:379-457` `context()`(`wanted`, `full`) |
| `09_new_session.md:12`(캡션), `:14` 「감독에게 말하기」 | 기준에 따라 맞음 | 캡션은 사진에 찍힌 글(「감독에게 말하기」)과 같아 그대로. 14줄에 테마를 고르면 「팀장에게 말하기」, 「교장에게 말하기」, 「소장에게 말하기」가 붙는다고 괄호로 더함 | `bridge/static/js/foremanchat.js:14, 74, 93` `fmName()`, `bridge/static/themes/{office,magic,site,plain}/theme.json` `foreman.name`(팀장, 교장, 소장, 감독), 사진 `portfolio/img/09_new_session_window.png` 직접 봄 |
| `10_scribe_room.md:10, 34, 50` 포트폴리오를 공통 기능처럼 | 이미 풀림(일부), 521 뒤 볼 것 | 고치지 않음(관리자 지시). 아래 「521 뒤 볼 것」 | `5adb03a`(513) |
| `11_postit.md:28` 관리자가 그 자리에서 올린다 | 기준에 따라 맞음 | 「FOREMAN 프로젝트에서는」으로 한정하고, 규칙이 FOREMAN 규칙 문서에만 있어 다른 프로젝트는 그물이 줍는다고 한 줄 더함 | 이 저장소 `CLAUDE.md` 「작업 규칙」 포스트잇 줄, `bridge/postit.py:7`. 다른 세 저장소 `CLAUDE.md`의 「포스트잇」, `postit` 개수 0(오늘 다시 셈), 브리지 지시문에 `/api/postit` 안내 없음(grep) |
| `11_postit.md:50` 합치거나 끝내면 「코더 세션 끝남」 | 기준에 따라 맞음 | 작업방 세션은 합쳤을 때, 원본 폴더 세션은 끝났을 때 「코더 세션 끝남」, 작업방을 합치지 않고 끝내면 「코더가 하는 중」, 버리면 「열림」이라고 풀어 씀 | `bridge/postit.py:46-61` `STATE`, `STATE_KO`, `bridge/api/postit.py:67`(화면 이름표) |
| `15_telegram.md:9, 13, 21` 알림은 모두 브리지가 보내고 DB에 남는다 | 기능 생김 | 바로 가는 알림 표에 「브리지 자신이 멈춰 다시 뜨지 못한다」 줄과, 이 알림만 따로 둔 스크립트가 보내고 앞머리는 늘 「[FOREMAN]」, DB 기록에 남지 않는다는 문단을 더함 | `cd14ed6`(브리지 밖 알림): `scripts/foreman-bridge-alert.sh:1-5, 18, 26`, `deploy/systemd/foreman-bridge.service:9` `OnFailure=`. 설치는 사용자 홈 유닛 파일에 `OnFailure=foreman-bridge-alert.service` 있음(읽기만), `log/manager410_overhead_20261115.md:231, 245` |
| `15_telegram.md:21` 앞머리가 정해진 프로젝트의 세션만 보낸다 | 기준에 따라 맞음 | 「턴 끝 알림은」으로 좁히고, 바로 가는 알림은 프로젝트 밖 세션이어도 「[미분류]」를 달고 간다고 한 줄 더함 | `bridge/notify.py:488`(턴 끝은 건너뜀 기록), `bridge/approvals.py:228, 250, 328, 449`, `bridge/handoff.py:546` |
| `15_telegram.md:27-37`(지금 27-40) 바로 가는 알림 표 | 기능 생김(인계 실패 줄은 이미 풀림) | 표에 세 줄 더함: 압축으로 잊은 것 찾기와 문서에 적기 실패(`4386b3a`), 세션이 안전 규칙 파일을 고침, 합치기로 안전 규칙 파일이 바뀜(`7ccb55f`). 48줄 「바로 보냄」 문장도 압축 점검, 문서에 적기 실패와 판정 묶음 일부 실패까지 넓힘. 인계 요약 실패 줄은 `afcad6b`(514)로 이미 있었다 | `bridge/losscheck.py:428, 467-472`, `bridge/promote.py:446, 452, 544`, `bridge/handoff.py:540-550`(`fail=True`면 글 앞 ⚠, `later=False`), `bridge/approvals.py:226-232`, `bridge/handoff.py:1302-1305`(종류 `rulefile`), `config/notify.toml` `[digest] kinds`(`rulefile` 없음) |
| `15_telegram.md:47`(지금 50) 묶음을 켠 프로젝트는 보고가 관리자에게 | 기준에 따라 맞음 | 그대로. 조건은 `relay_reports`와 관리자 세션이지만 지금 네 프로젝트 모두 `relay_reports`, `digest`가 켜져 있어 결과가 같고 독자가 헷갈릴 일이 없다 | `config/notify.toml:39, 41, 48, 50, 55, 57, 61, 63` |
| `15_telegram.md:51`(지금 54) 망가졌다는 알림이 나가면 계획 | 기준에 따라 맞음 | 적재 막힘 가운데 DB 연결 끊김, 시간 초과는 계획하지 않고 알림만 보낸다고 한 줄 더함 | `bridge/ingest_health.py:47-53`(`transient`면 `on_failure`를 부르지 않음) |
| `03_pipeline.md:9, 19, 23` 「배포 파이프 없음」과 FOREMAN 방 | 이미 풀림 | 고치지 않음. 23줄이 인프라 방과 FOREMAN 방을 모두 들고, 인용한 까닭 글이 지금 코드와 글자까지 같음을 확인 | `bridge/static/js/office.js:37-39` `NO_SHIP`, `:1409`. 고친 커밋은 512, 516(`9ac4527`, `35171b8`) |
| `03_pipeline.md:37`(`01_pixel_office.md:41`도) 실패면 현황판 빨강, 🔥, ✕ | 기준에 따라 맞음 | 03편 37줄에 빌드 알림 없음, 웹훅 끊김 의심일 때도 같은 표시가 켜진다고 한 줄 더함. 01편 41줄은 「실패가 있으면」 넓게 쓴 예시라 그대로 | `bridge/static/js/office.js:3014-3017` `siteState` |
| `01_pixel_office.md:15-17` 테마 셋 | 기준에 따라 맞음 | 그대로. 머리줄에서 고르는 테마는 셋이고, 넷째(도형)는 주소로만 연다. 이 편은 머리줄 단추를 말해 헷갈릴 일이 없다 | `bridge/static/office.html:202` `THEMES`, `bridge/static/themes/plain/` |

수가 바뀐 항목은 없었다. 19건 가운데 기능 생김 2건(고침), 기준에 따라 맞음 14건(풀어 씀 11, 그대로 3), 이미 풀림 2건(03편 하나, 10편 일부), 10편 1건은 521 뒤로 넘겼다(15편 27-37줄의 인계 실패 줄도 이미 풀림이지만, 나머지가 기능 생김이라 그쪽으로 셌다).

## 521 뒤 볼 것

10편은 이 세션이 고치지 않았다. `main 4386b3a` 기준으로 본 것만 적는다.

- `10_scribe_room.md:10`(굵은 요지) 「포트폴리오와 기술문서를 Notion에 올리는 게시도 같은 창에 있습니다」: 지금과 맞다. 게시 칸은 `5adb03a`로 서기실을 연 프로젝트의 게시 목록을 읽는다(`bridge/static/js/scribe.js:54, 73-83`)
- `10_scribe_room.md:50` 게시 칸 문단: 지금과 맞다. 이미 「서기실을 연 프로젝트의 게시 목록」, portfolio 폴더 없으면 「아직 없음」, Notion 자리 없으면 막힘으로 고쳐져 있다(`5adb03a` 커밋 글과 같다)
- `10_scribe_room.md:34` 일감 표 「포트폴리오 쓰기」 줄: 아직 한정이 없다. 「기술문서 쓰기」 줄에는 「원고 폴더를 따로 둔 프로젝트만」이 있는데, 「포트폴리오 쓰기」는 `portfolio/` 폴더가 있는 저장소에만 보인다(`bridge/scribe_room.py:42` `PORTFOLIO_DIR`, `:69` `has_portfolio`, `:236`). 지금 그 폴더가 있는 것은 FOREMAN뿐이다. 521이 끝난 뒤 「(portfolio 폴더를 둔 프로젝트만)」 같은 한정을 더할지 보면 된다

## 사람에게 물을 것

- `15_telegram.md` 머리 「다루는 곳」: 이번에 브리지 밖 알림을 본문에 넣었는데, 그 코드(`scripts/foreman-bridge-alert.sh`, `deploy/systemd/`)가 「다루는 곳」에 없어 서기실 「코드가 바뀐 편」 셈에 계속 잡히지 않는다. 일감이 머리 주석은 「읽은 커밋」을 바꾸지 말라고만 했고 「다루는 곳」은 말하지 않아 손대지 않았다. 더한다면 「다루는 곳」 줄 끝에 `, scripts/foreman-bridge-alert.sh, deploy/systemd/foreman-bridge.service`를 붙이는 안이다

애매해서 고치지 않은 항목은 이것 말고 없다. 19건 모두 지금 코드와 설정, 저장소 파일만으로 판정할 수 있었다(DB, 다른 세션 상태, 그때 CC 판이 필요한 것 없음).

## 시험

- `.venv/bin/python -m pytest -q`: 1227 passed, 1 warning(fastapi testclient 사용 중단 경고), 206초. 화면 말 시험 「서기 몫 0줄 남음」
- 새로 쓴 줄의 em dash, 가운뎃점: 0개(diff에서 셈. 걸린 하나는 15편 54줄에 원래 있던 🧭 알림 첫 줄 인용)
- 본문에 새 근거 표시를 달지 않았다. 06편, 07편, 08편 고친 문단에 원래 있던 근거 표시는 자리만 그대로 두었다

## 규칙 위반

규칙 위반 없음. 파일은 Edit와 Write로만 고쳤다(포트폴리오 8편과 이 log). `portfolio/10_scribe_room.md`, `notion/`, `bridge/`, `tests/`, `config/`, `docs/`, README.md, CLAUDE.md는 건드리지 않았다. 다른 저장소 세 곳은 `CLAUDE.md` 안 낱말 개수만 셌다(`grep -c`). systemd는 읽으려다 샌드박스에서 막혀, 사용자 홈의 유닛 파일을 grep으로 읽기만 했다. `pgrep -f`, sudo, push, 브리지 다시 띄우기, 노션 게시, 리디렉션이나 heredoc 파일 만들기는 쓰지 않았다. 진행 글은 모두 한국어로 썼다.
