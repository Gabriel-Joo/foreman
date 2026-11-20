# foreman-5 작은 고침 여럿 결과 (2026-11-20)

- 시작한 main 커밋: b89b3b6 (끝낼 때 main은 b7f8f53까지 나아가 있었다)
- 일감: 관리자 410, 서기실 전체 대조 줄에서 서기들이 짚은 것과 사용자 결정 11-20
- 규칙 위반 없음

## 한 일

1. `bridge/api/hooks.py`: 받은 JSON이 객체가 아닐 때 400과 함께 로그 한 줄(`hook 거절 <주소> <경로>: 객체가 아님(list)`)을 남긴다. 값은 남기지 않고 자료형 이름만 쓴다. 시험은 `tests/test_app_db.py` `test_hooks_reject_non_object_logs_reason`(TODO foreman-151, 줄은 지우지 않았다)
2. 낡은 주석(동작은 그대로)
   - `bridge/store.py` 머리 주석: event에 쓰는 곳은 여기 하나가 아니다. `store.py`(/emit 한 건, debug 줄 지우기), `assembler.py`(덩어리 INSERT, 부 에이전트 turn_id UPDATE), `pipeline.py`(commit_sha UPDATE)
   - `bridge/static/js/slash.js` 머리 주석: 「'!'는 언제나 막는다」가 11-09 이후 동작과 달랐다. 지금은 입력 API의 `bang_check`가 ask 규칙, sudo, 여러 줄, 빈 명령만 막고 나머지는 그대로 보낸다
   - `bridge/static/js/office.js` 서기실 주석: 「무엇을 시킬지 고르는 창 · 할 일 · 포스트잇 · Notion 게시」를 지금 `scribe.js`의 칸(물어보기, 할 일, 포스트잇, 전체 줄, 포트폴리오와 기술문서의 쓰기와 게시)으로 고침
   - `migrations/`는 고치지 않았다. 낡은 것: `0001_init.sql` 151줄 「쓰는 곳은 bridge/store.py 하나」(위 store.py와 같은 사정). 「마이그레이션 주석의 폴더 경로」는 어느 줄인지 찾지 못했다(`0029_seed_ronanlab_infra.sql`에 폴더 경로 시드가 있으나 주석이 낡았는지는 가리지 못했다)
3. 옛 화면 이름
   - 「CC 화면」 → 「세션 화면」: `bridge/terminal.py`, `bridge/api/terminal.py`, `bridge/static/js/ccscreen.js`, `deploy/shell/foreman-cc-view`, 그리고 같은 이름이 남은 주석(`bridge/config.py`, `bridge/inject.py`, `bridge/static/js/opanel.js`, `store.js`, `bridge/static/office.html`). 이 이름은 `screen_words.toml`에 이미 한 줄이 있어(`fcd4b68`) 새 줄은 더하지 않았다. `tests/test_ccscreen.py`의 이력 주석(「CC 화면」 → 「세션 화면」)은 이력이라 두었다. `notion/01_structure.md`, `03_session.md`, `17_limits.md`의 「CC 화면」은 탭 이름이 아니라 Claude Code 자체 화면을 가리키는 말이라 두었다
   - 「넘기기 전 정리」 → 「옮기기 전 정리」, 「대화 결정 문서에 적기」 → 「대화에서만 정한 것 문서에 적기」(기준은 `notion/08_handoff/01_loss.md`와 화면의 `handoff.js` `promote.js`). 코드(`promote.py`, `handoff.py`, `losscheck.py`, `api/handoff.py`, `opanel.js`), 시험 둘, `docs/operations.md`, `portfolio/15_telegram.md`, `notion/11_notify.md`, `notion/08_handoff/03_promote.md`. 이 둘은 `tests/data/screen_words.toml`에 한 줄씩 더했다. 더한 뒤 화면 말 시험이 남은 곳을 더 잡지는 않았다. 이 이름의 `promote.py` 요청문 머리도 바뀌어 새 세션이 받는 글이 달라진다
   - `docs/TODO.md` 317줄에 옛 이름이 적혀 있으나 그 줄은 이 고침을 가리키는 할 일이라 건드리지 않았다
4. `STALL_MIN` 60분 → 15분(`bridge/scribe_queue.py`)
   - 잰 값: 전체 대조 줄 1(38편)에서 편마다 서기 시간이 최소 74초, 가운데 162초, 최대 268초. 15분(900초)은 최대의 3배쯤이다. 이 수는 일감에서 받은 값이고 이 세션에서 다시 재지 않았다
   - 고친 곳: 코드 주석, `docs/12_scribe.md` 91줄, `notion/10_scribe/01_room.md` 270줄, `notion/11_notify.md` 316줄, 시험(20분 지난 편이 걸리는지, 상수가 15인지)
5. `manager_allow`를 CLAUDE.md대로: `config/roles.toml`과 `bridge/roleguard.py` 기본값에서 `README.md`를 빼고 `docs/TODO.md`를 넣었다. `docs/roles.md` 34줄, `notion/05_roles/01_roles.md`, `notion/05_roles/02_guards.md` 여러 줄, `roleguard.py` 머리 주석, `tests/test_roleguard.py`(README와 다른 docs는 막히고 TODO.md는 통과). 거부 문구는 설정 값을 그대로 읽어 따로 고칠 곳이 없었다. 도는 브리지는 다시 띄우지 않았다. 합친 뒤 원본 세션이 띄워야 새 값이 적용된다
6. 덧붙임(관리자 410, 사용자 11-20): `/usage`를 no-cache 목록(`bridge/main.py` 미들웨어)에 넣었다. 시험은 `tests/test_app_db.py`가 화면 주소 여섯 개의 `Cache-Control`을 본다. 원고 `notion/01_structure/02_startup.md` 195줄과 `notion/14_screen.md` 25줄을 맞췄다(TODO foreman-153, 줄은 지우지 않았다)
7. 사용자가 hooks.py 400 로그와 `manager_allow`를 다시 확인했다(그대로 한다)

## 문서

- `tools/docs.py check`: 틀린 것 0(의심 326은 이 고침 전부터 있던 「」 없는 참조)
- 고친 원고의 「읽은 커밋」은 올리지 않았다. 이름과 숫자 몇 곳만 맞췄고 편 전체를 지금 코드에 맞대어 읽지는 않았다
- 합치기 카드에 사람에게 갈 문서: `docs/operations.md`, `docs/roles.md`
- 동시에 도는 세션과 겹침: `notion/05_roles/01_roles.md`는 「」 없는 참조 서기와 겹칠 수 있다. 내가 고친 줄은 156줄 하나다

## 시험

- `.venv/bin/python -m pytest -q`: 1522건 통과(238초)
- `node --test tests/js/`: 250건 통과
- `tools/docs.py check`: 틀린 것 0
- 실제 화면과 도는 브리지는 확인하지 않았다(브리지를 다시 띄우지 않았다). 시험만 통과했다

## 사람이 정할 것

- 고친 원고의 「읽은 커밋」을 올릴지(편 전체를 맞대어 읽지 않아 올리지 않았다)
- `migrations/0001_init.sql` 151줄 주석을 다음 마이그레이션 때 같이 고칠지
- 합친 뒤 브리지를 다시 띄워야 `manager_allow`, `STALL_MIN`, `/usage` no-cache가 적용된다
