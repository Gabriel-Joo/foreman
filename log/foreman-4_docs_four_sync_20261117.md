# docs 네 편을 코드에 맞춤 (2026-11-17, 서기, 관리자 410 일감, 사용자 지시 19의 1번)

> 대상: `docs/10_office_design.md`, `docs/12_scribe.md`, `docs/14_dispatcher_note_wake.md`, `docs/15_usage.md`. 읽은 기준 커밋 `910bbad`.
> 나눠 쓴 방법: 서브에이전트 셋(10, 12, 14와 15)이 병렬로 고쳤고, 관리 세션이 근거를 다시 확인하고 문서끼리 어긋남, 공개 서술 기준, 시험, 커밋을 맡았다. 서브에이전트는 모두 끝났다.
> 점검 기준 `9a7c22d` 뒤로 네 문서가 다루는 코드와 설정에는 커밋이 없다. 그래서 점검 결과는 지금 코드에도 그대로 걸린다.

## 1. 고친 곳

| 파일 | 절 | 코드에서 무엇이 어떻게 달랐나 | 근거 파일 | 근거 커밋 |
|---|---|---|---|---|
| 12_scribe | 1. 일감 표 | 문서는 `sync`, `loss`, `polish`를 포함한 일곱이었다. 코드 `TASKS`는 `doccheck`, `trim`, `later`, `docfix`, `portfolio`, `techdoc`, `publish`. 표를 지금 일곱으로 바꾸고 세션인지(publish만 세션 없음), 화면 이름, 나오는 것을 적었다. 옛 셋은 표 아래에 「코드에 들어간 적이 없다」로 남겼다(`git log -S`로 bridge에서 0건, 11-05 설계 `3305027`에만). 교장 지시문 목록이 `TASKS`와 다르다는 줄을 더했다 | `bridge/scribe_room.py` `TASKS`, `task_prompt`, `start`, `bridge/static/js/scribe.js` | `549be68`, `5de720b`, `f2fee1d`, `16dcb3a` |
| 12_scribe | 2. 할 일 세기 | polish, loss 후보는 세지 않는다. 실제로 세는 later 줄, [갱신] 실패, Notion 뒤처짐, docfix를 더했다. 80줄 기준이 `CLAUDE_MD_MAX`임을 밝혔다. 옛 줄은 「바뀜」으로 남겼다 | `scribe_room.todo` | 위와 같음 |
| 12_scribe | 2. 어떻게 도나 | worktree 이름 `scribe-<날짜>` 규칙이 코드에 없다. 실제는 `<프로젝트>[-N]`, 브랜치 `cc/<프로젝트>[-N]`. polish의 `claude -p` 예외도 없다. 세션 없이 도는 것은 publish와 물어보기 | `bridge/handoff.py` `spawn_new`, `bridge/worktree.py` `create` | `f964a79` |
| 12_scribe | 3. 재료 | 경로는 `~/.foreman/scribe/<프로젝트>_<날짜>/`. 코드가 700으로 맞추는 것은 날짜 폴더이고 파일은 600, 맨 위 폴더 권한은 코드가 정하지 않는다. 문서 고치기 재료(`NOTE_MAX` 4000)를 더했다 | `bridge/scribe.py` `write`, `OUT_ROOT` | 확인 못 함 |
| 12_scribe | 6. 토큰, 9. 상태 줄, 10. 3 | 옛 일감 이름을 쓴 줄에 「11-05 어림, 옛 이름」 머리말과 지금 일감(1절)을 가리키는 말을 붙였다 | `TASKS` | 위와 같음 |
| 12_scribe | 11-6. 조용히 쌓이지 않게 | `config/scribe.toml`에 `[postit]`이 없어 기본값으로 돈다. 파일에 있는 `[nudge]`(`new_min` 3, `oldest_days` 3)를 적고, 이 값은 브리지가 쓰지 않는다고 적었다 | `config/scribe.toml`, `bridge/postit.py` `CONF_DEFAULT`, `bridge/scribe_room.py` `nudge_conf` | 확인 못 함 |
| 12_scribe | 11-7. API | `source?` 칸이 빠져 있었다. 다섯 POST 모두 거절이면 409 `{"refused": …}`. `/api/postit`은 201 또는 200, 나머지 성공은 200, `/refresh`만 202(꺼져 있으면 503) | `bridge/api/postit.py` | `ee966ec` |
| 14 | 1. 이름 | 기본(도형) 테마 감독실 캐릭터 이름이 「디스패처」였다. 코드는 「감독」 | `bridge/static/themes/plain/theme.json` | `bdcd0cd`(11-09, 본문 「기본 테마 이름은 "감독"으로」). 점검이 짐작한 `a0982c7`은 아니다 |
| 14 | 4. 자동 기상 | 실패 알림 글이 「디스패처가 살펴볼 계획을 세우지 못했습니다」였다. 코드는 「⚠ {종류} — 살펴볼 계획을 세우지 못했습니다(…). 실패 알림을 직접 봐 주세요」(두 곳) | `bridge/wake.py` `_wake`, `_wake_inner` | 처음 `8907665`, 바뀜 `bdcd0cd` |
| 15 | 2. 환산 표 | Fable 줄이 없었다. `$10`, `$50`, `$0.25`, `$20`과 주간 한도 `weekly_fable`(「주간 · Fable」)을 더했다. 값의 출처는 커밋, 주석, 기록에 없어 「확인 못 함」으로 적었다 | `config/usage.toml` `[prices.fable]`, `[[limits]]` | `5958940` |
| 10 | 코더 호버, 자리 말풍선 호버, 기다림 호버, 멈춘 턴 호버 | 화면 글이 em dash를 빼며 바뀌었다(「일 N: …」, 「코더 자리: 맡길 일」, 「서기 자리: 문서 할 일」 또는 「포스트잇 쌓임」, 「…돎(둘레의 작은 캐릭터)」, 마침표로 나눔). 기다림 위치 글은 WAITING일 때만 붙는다 | `bridge/static/js/office.js` `seatHits`, `actorTip` | `945b3a7` |
| 10 | 맡길 일 「셈」 | 셈에 `drift`(끝난 뒤 어긋난 것: 고아 worktree, 커밋 안 된 변경, 실제와 다른 합치기 기다림, 남은 브랜치. 빈 worktree는 뺌)가 빠져 있었다. API 응답도 `{inbox, rested, drift}` | `bridge/static/js/coder.js` `coderJobs`, `bridge/api/coder.py` | `4f2abba`, `80b1aa2` |
| 10 | 합치기 막대 대기 수 | 「`ready` 카드 수」만 적혀 있었다. 코드는 관리자가 승인하는 카드와(11-12) 브리지가 스스로 합치는 조사 카드(11-15)를 뺀다 | `bridge/dashboard.py` `merge_waits`, `manager_card` | `edfac07`, `e4c7b9b` |
| 10 | 쌓기 절 자리 말풍선, 「자리」 줄, 잘림 고침 줄 | 「정리할까요?」는 「포스트잇 쌓임」으로 바뀌었다. `placeStack`은 `overhead.js`가 아니라 `office.js`에 있다. `placeBubble`은 이제 없다 | `office.js` `scribeText`, `placeStack`, `overhead.js` | `9f8d647`(쌓기). 「포스트잇 쌓임」 커밋은 확인 못 함 |
| 10 | 근거 해시 넷 | squash 전 해시 `e4a901c`, `1a61703`, `2819d41`, `edf5ef1`은 main 이력에 없다(관리 세션이 `merge-base --is-ancestor`로 확인). 제목과 `git log -S`로 짝을 찾아 바꿨다 | 각 커밋 | `80b1aa2`, `a7541cd`, `9f8d647`, `2fe1c93` |

## 2. 점검 결과 번호별 처리(`log/foreman-8_doc_drift_20261116.md`)

| 번호 | 처리 | 짧게 |
|---|---|---|
| 1 | 고침 | 점검에 없던 worktree 이름, polish `claude -p` 예외도 같이 고쳤다 |
| 15 | 고침 | 근거 커밋은 점검이 짐작한 `a0982c7`이 아니라 `bdcd0cd` |
| 16 | 고침 | 코드 글 그대로 인용 |
| 17 | 고침 | 값의 출처는 확인 못 함 |
| 18 | 고침 | `/refresh` 202, 503과 `source` 칸도 더함 |
| 19 | 고침 | 그런데 `[nudge]`는 시험만 읽는다(아래 「3.」) |
| 「맞았던 것」 14, 15 설정 값 | 이미 맞음 | `9a7c22d` 뒤 바뀐 커밋 없음 |
| 「맞았던 것」 12 숫자, 노션과 포트폴리오 길 | 이미 맞음 | `TECHDOC_DAYS` 2, `LINE_WRAP` 1500, `MAX` 8000, `open_max` 20, `stale_days` 7, `refresh_days` 7, 그물 2분, `NET_WAIT` 30분, `NET_WINDOW` 2일, 물어보기 숫자 |
| 「못 본 것」 10 방 배치, 말풍선, 머리 위 표시 세부 숫자 | 이미 맞음(호버 글과 셈은 고침, 위 표) | 방 열한 개, 복도 세 줄, `coder_home`, 역할 색, `DEPART_GAP` 등 코더 숫자, `needMark` 순서, `RELAY_GRACE`, 발밑 원 숫자, 포스트잇 창 크기와 z-index, 세션 화면 숫자를 코드와 맞대었다 |
| 「못 본 것」 12 재료 폴더 경로와 권한 | 고침 | 700은 날짜 폴더. 실제 권한은 `stat`으로만 읽었다(맨 위와 날짜 폴더 9개 모두 700) |
| 「못 본 것」 12 DB 수치(11-4) | 이미 맞음 | 그물 `NET`은 `ee966ec` 뒤로 바뀌지 않았고 수치는 같은 커밋의 log와 같다. 고칠 근거가 코드에 없다. DB는 열지 않았다 |

## 3. 코드가 이상해 보이는 곳 (고치지 않음, 사람이 정함)

- **`config/scribe.toml` `[nudge]`는 바꿔도 아무 일도 없다.** 읽는 `scribe_room.nudge_conf`, `nudge_of`를 시험(`tests/test_stage2_db.py`)만 부르고 브리지 안에서 부르는 곳이 없다. 말풍선은 `bridge/postit.py` `nudge_of`(`[postit]` 기본값)가 정한다. 조용한 고장 쪽이라 지울지 다시 이을지 정해야 한다
- `bridge/static/js/office.js` 경고등 호버가 「100%가 되면 리셋까지 모든 세션이 멈춥니다」라고 한다. `43ef9f0`(11-14)에서 알림 글은 「추가 요금으로 넘어가거나, 추가 사용이 꺼져 있으면 멈춥니다」로 바꿨고, `docs/15_usage.md` 6절도 「늘 멈춘다고 쓰지 않는다」고 한다. 화면 글 하나가 남았다
- `bridge/scribe_room.py` `start`의 later 거절 글이 옛 재료(「"나중에, 미루"라고 한 사람 말도, 받은 할 일도 없습니다」)를 말한다. 화면에 나올 수 있다
- `bridge/foreman.py` 교장 지시문: 서기 일감을 「sync, trim, loss, 포트폴리오」라고 하는 줄이 있고, task 목록에 techdoc이 없다(뒤의 것은 `log/foreman-4_docs_five_sync_20261116.md` 「3.」과 같다)
- `bridge/coder_room.py` `todo`가 코더 몫 `inbox_new(..., "coder")`를 부르지만 11-15부터 늘 `[]`이다(죽은 길)
- `config/usage.toml` `[prices.fable]` 캐시 읽기가 입력의 2.5%다. 다른 모델은 5%, 10%라 비율이 다르다. 출처를 못 찾아 맞는지 모른다
- 낡은 주석, docstring(동작 무관): `config/scribe.toml` 머리 주석(옛 [＋ 할 일]), `bridge/scribe_room.py` 머리 「시킬 일」 목록(docfix, portfolio, techdoc 빠짐), `bridge/scribe.py` 머리(700 자리), `bridge/api/coder.py` `coder_todo`(`drift` 빠짐), `bridge/coder_room.py` `todo`, `office.js` 181줄 근처 머리 칩 옛 글, `render.js` `sessionSub`(「따로 작업」), `themes/{office,magic,site}/theme.json` `aura._`(「render.js ROLE_COLOR」, 지금은 `roles.js`)

## 4. 문서끼리 어긋남

- 12_scribe 11-6(말풍선은 `[postit]` 기준)과 10_office_design 쌓기 절(「포스트잇 쌓임」)은 같은 코드를 말한다. 어긋남 없음
- 14 「4.」 실패 알림 글과 `docs/11_foreman_dispatch.md` 「7.」(5편 맞추기 때 고친 알림 둘째 줄)은 서로 다른 글이라 겹치지 않는다

## 5. 못 본 것, 불확실

- 화면을 띄워 보지 않았다. 10의 호버 글은 코드 문자열로만 맞췄다
- sync, loss, polish를 왜 코드에 두지 않았는지는 기록에 없다(문서에도 그렇게 적었다)
- 12 10절 「일감마다 모델을 바꿀 수 있다」는 확인하지 않았다. 서기실 `start`는 모델을 넘기지 않는다
- 15 6-3절 /usage 띠 글은 문서가 「5시간 확인할 수 없음.」인데 화면은 설정 라벨을 써서 「5시간 세션 …」으로 보일 수 있다. 문서와 코드가 같은 커밋(`f0cd39f`)이라 그 뒤 코드가 바뀐 것이 아니어서 두었다
- 14 「4.」 알림 링크 줄의 옛 도메인은 원래 있던 줄이라 두었다(새로 넣지 않음)
- 10의 에셋 조사 절, 이름표 자리 기준의 지난 측정 숫자는 그때 잰 값이라 다시 재지 않았다

## 6. 확인 체크리스트

- [x] docs 넷을 모두 봤는가: 봤다(서브에이전트 셋이 나눠 보고, 관리 세션이 근거 커밋과 응답 코드, `[nudge]` 호출처, squash 전 해시, 설정 라벨을 다시 확인했다)
- [x] 지시 16의 문서 점검 결과를 반영했는가: 「2.」 표, 번호마다 처리
- [x] 어긋난 곳마다 무엇이 어떻게 달랐는지 적었는가: 「1.」 표
- [x] 코드가 이상해 보이는 곳을 따로 모았는가: 「3.」, 고치지 않았다
- [x] 시험이 통과하는가: 통과(아래 「7.」)
- [x] README와 CLAUDE.md를 건드리지 않았는가: 건드리지 않았다(`git diff --name-only`는 docs 넷과 이 log뿐)

새로 넣은 낱말의 em dash와 가운뎃점은 코드 글 인용 둘(`wake.py` 알림 글, `usage.toml` 라벨 「주간 · Fable」)뿐이다(낱말 단위 diff). IP, 도메인, 토큰, 홈 경로를 새로 넣지 않았다.

## 7. 시험

- `.venv/bin/python -m pytest -q`: 1176 통과, 실패 0. 알려진 시각 시험 `test_digest_send_failure_and_late_are_reported`도 이번 시각대에는 통과했다(고치지 않았다)
- 화면 말 시험: 서기 몫 0줄
- `node --test tests/js/`: 210 통과, 실패 0

## 8. 규칙 위반

규칙 위반 없음(관리 세션, 서브에이전트 셋 모두).
