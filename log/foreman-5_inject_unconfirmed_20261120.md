# 보낸 것과 도는 것은 맞는데 화면이 모름 (foreman-5, 2026-11-20)

시작한 main 커밋: 80a6dbc. 규칙 위반 있음(아래 「규칙 위반」).

TODO foreman-161, foreman-41. 관리자 410의 코더 일감.

## 조사 결과: 504가 난 까닭은 둘이다

브리지 로그(`journalctl --user -u foreman-bridge`, 11-20)와 운영 DB, 트랜스크립트를 읽기만 해서 맞대 보았다. 다른 세션에는 아무것도 보내지 않았다.

1. **세션 692(18:21:04 504)는 제출 확인을 아예 하지 않았다.** 이 504 앞뒤에 「주입 제출 확인 안 됨」 줄이 없다. 692의 트랜스크립트 파일은 18:21:04.21에 처음 생겼다(`stat` birth, 첫 줄 timestamp 09:21:04.1Z). 즉 보낸 그 글로 CC가 파일을 만들었고, 그 순간 DB `transcript_file`에는 경로가 없었다. `inject_input`은 `tf.path`가 없으면 `transcript=None`으로 `deliver`를 불러 기록 확인도 입력 칸 확인도 건너뛰고 바로 504(`left_in_box` 없음)를 돌렸다. 화면(`store.js`)은 이것을 「제출됐는지 확인하지 못했습니다」로 그렸다. 지금 DB에는 692의 경로(tf 2342)가 있다.
2. **나머지 20번(「입력 칸에 없다(제출된 것으로 보임)」)은 CC가 기록을 늦게 썼다.** 세션 509(런슈즈) 13:57:50, 13:58:04 두 건을 보았다. 기록된 user 줄은 붙여넣은 지 0.1~0.3초 뒤 timestamp인데, 10초 확인 창 안에 `find_delivery`가 찾지 못했다. 지금 파일에 같은 함수를 돌리면 찾는다(`find_delivery(path, offset, DB의 보낸 글)`이 prompt로 맞음). 글 모양도 맞는다(282자, 감싼 안쪽 282자, 특이 글자 없음). 그래서 모양이 아니라 쓰인 때가 늦었다고 본다. CC가 왜 늦게 썼는지(버퍼링 등)는 알아내지 못했다. 20번 모두 입력 칸은 비어 있었다.
3. **대화가 「불러오는 중」에 머문 것은 화면이 빈 결과와 불러오는 중을 같게 그렸기 때문이다.** `render.js` `convoHtml`은 턴이 0개면 `''`를 돌리고, `opanel.js`는 `''`를 「불러오는 중…」으로 바꿔 그렸다. 692는 첫 글 전(18:19:45)에 대화와 활동 요청이 200(턴 0개)으로 왔다. 활동 탭은 원래 「활동이 아직 없습니다.」를 그려 문제가 없었다.
4. **foreman-41**: `handoff.spawn_new`의 첫 글 길이 보내기 전에 `summary.injected_cc_session`, `injected_at`을 적고 `drift`는 적지 않았다. 패널 「바뀐 것」이 drift에서 오므로 빈 목록이었다.

## 한 일

- `bridge/inject.py`: `deliver` 결과에 `outcome`(delivered, queued, unconfirmed, left, unknown). 기록에서 못 찾으면(슬래시 명령 빼고) 뒤에서 `LATE_S`(120초) 동안 1초마다 기록을 다시 보는 일을 띄우고 `check` 번호를 준다(`check_state`, `on_late` 콜백). `submitted(res)`는 delivered, queued, unconfirmed를 넣은 것으로 본다.
- `bridge/api/sessions.py`: DB에 경로가 없으면 `handoff.transcript_path(cwd, cc)`로 본다. HTTP는 `input_http_status`로 unconfirmed도 202(`verified: false`, `check`), left와 unknown만 504. 늦은 결과는 입력 이벤트 「(늦게 확인) 들어갔습니다: …」 또는 「(늦게 확인) 기록에서 찾지 못했습니다: …」(payload `late`, `check`)로 남아 활동 탭에 보인다. `GET /api/sessions/{id}/input/{check}`로 상태를 물을 수 있다.
- `bridge/managers.py`: 관리자 부탁(`ask`)과 중계(`relay`)가 unconfirmed를 넣은 것으로 돌린다(`verified`, `check` 함께). 늦게 봐도 없으면 그때 `session_action`에 실패로 남기고 텔레그램. left면 사유 「입력 칸에 글이 남아 제출되지 않았습니다」.
- `bridge/handoff.py`: 첫 글 넣기를 `_send_first`로 떼고, 넣음 기록을 `_mark_injected`(drift 포함) 하나로. 기록으로 확인했을 때 바로, unconfirmed면 늦게 찾았을 때 적는다. 끝내 못 찾거나 left면 적지 않는다. `inject()`도 같은 함수를 쓰고 `delivered`는 `submitted`, `verified`를 따로 돌린다. `bridge/foreman.py` attach 길도 `submitted`.
- `bridge/static/js/render.js` `convoHtml`: c 없음과 받는 중은 「불러오는 중…」, 받았는데 비었으면 「아직 대화가 없습니다.」, 실패면 「대화를 불러오지 못했습니다(까닭).」. `opanel.js`는 바꿔 그리지 않는다.
- 문서: `docs/00_design.md` 제출 확인 줄, `notion/03_session.md` 5절 그림과 10절(10-3 새 절), `notion/06_sessions.md` 표 한 줄, `notion/08_handoff/02_summary.md` 넣은 뒤, `notion/09_dispatcher/04_managers.md` 부탁 실패와 넘기기 실패, `notion/14_screen/03_panel.md` 대화 세 상태, `portfolio/04_session_panel.md` 대화 탭 빈 상태와 입력 칸 늦은 확인. 머리 주석 「다루는 곳」에 새 시험 파일을 더했다. 「읽은 커밋」은 바꾸지 않았다(이 편 전체를 다시 읽은 것이 아니다).
- 시험: `tests/test_inject_late.py`(확인 못 함 뒤 실제 들어감, 끝내 없음, 입력 칸에 남음, 새 세션 파일이 그 글로 생김, 슬래시 명령, HTTP 갈래, 입력 API의 경로 대신 찾기와 늦은 활동 줄과 확인 번호, foreman-41 넣음 기록 네 갈래, 관리자 부탁과 중계), `tests/js/convo_state.test.mjs`(빈 대화, 불러오는 중, 실패, 턴 있음).

## 갈래를 정한 까닭

- **unconfirmed를 202로**: 실측 20번 모두 입력 칸이 비었고 실제로 들어갔다. 504로 두면 사람과 관리자 길이 다시 보내 두 번 들어간다. 「기록으로 확인 못 함」은 `verified: false`로 남겨 정보를 잃지 않는다. 화면(`store.js`)은 전에도 504 + 입력 칸 비었음을 「보냈습니다.」로 그렸으므로 사람에게 보이는 결과 글은 같다.
- **left, unknown은 504로 남김**: left는 실제로 제출되지 않은 것이고, unknown은 화면도 못 읽어 「보냈습니다」라 할 근거가 없다. 둘 다 늦게 다시 보기는 돌아(left는 사람이 대화창에서 Enter를 누를 수 있다) 활동 줄로 결과가 남는다.
- **늦게 다시 보기 120초**: 509 건은 10초를 넘겼지만 몇 초였는지는 기록에 없다(맞대 본 파일 크기 변화 시각이 남지 않음). 관리자 중계 기다림(`RELAY_GRACE` 30초)이나 사람 반응보다 길게 잡았다. 잰 값이 아니다.
- **슬래시 명령은 다시 보지 않음**: `/model` 등은 기록 모양이 달라 끝내 못 맞춘다. 다시 보면 매번 「찾지 못했습니다」 줄이 남아 헛알림이 된다. 모델 바꾸기는 지금처럼 화면으로 본다.
- **확인 번호는 메모리에만**: 브리지를 다시 띄우면 사라지고 GET은 404다. 결과는 이벤트(활동 줄)와 `session_action`에 남으므로 DB 칸을 새로 만들지 않았다(스키마는 다른 세션과 잠금을 다툰다).

## 하지 않은 것, 다른 파일 몫

- `bridge/static/js/store.js`는 691 파일이라 고치지 않았다. 바꾸면 좋을 것: `sendInput`이 202 + `verified: false` + `check`면 「보냈습니다. 기록을 확인하는 중입니다.」로 띄우고 `GET …/input/{check}`를 몇 번 물어 결과로 바꾸기, 입력 이벤트에 `payload.late`가 있으면 「주입:」 대신 「늦게 확인:」으로 그리기. 지금은 「주입: (늦게 확인) 들어갔습니다: …」로 보인다. `switchModel`의 504 + `left_in_box === false` 갈래는 이제 202로 와서 쓰이지 않지만 그대로 두어도 해가 없다.
- `bridge/mergeprep.py` `_deliver`, `bridge/terminal.py`, `bridge/promote.py`, `handoff.resend_reads`, `handoff` 요청 길은 그대로 `delivered or queued`만 성공으로 본다. unconfirmed가 이 길에서는 실패로 남아 사람에게 텔레그램이 갈 수 있다(조용하지는 않다). 같은 판정(`submitted`)으로 바꿀지는 정할 것으로 남긴다.
- 화면 말 바뀜(`tests/data/screen_words.toml`은 691 파일이라 고치지 않음): 새 말 「아직 대화가 없습니다.」, 「대화를 불러오지 못했습니다(까닭).」, 「(늦게 확인) 들어갔습니다」, 「(늦게 확인) 기록에서 찾지 못했습니다」, 관리자 사유 「입력 칸에 글이 남아 제출되지 않았습니다」, 첫 글 「첫 글이 입력 칸에 남아 제출되지 않았습니다. 그 세션 대화창에서 Enter를 눌러 주세요.」. 없앤 말은 없다.
- 실제 화면은 보지 못했다(브리지를 다시 띄우지 않는 worktree 세션). 시험만 통과했다.

## 확인

- `tools/docs.py check` 틀린 것 0(아래 커밋 직전 다시 돌림), `.venv/bin/python -m pytest -q` 전부 통과, `node --test tests/js/` 전부 통과. 숫자는 보고에 적는다.
- `tools/docs.py refs --range main...HEAD --unfixed`: 걸리는 문서 66, 안 고침 61(포트폴리오를 고치기 전 셈). 대부분 큰 파일(`bridge/foreman.py`, `bridge/handoff.py`, `render.js`)을 다른 기능 때문에 가리키는 문단이다. 504, 제출, 불러오는 중, 입력 칸, 넣었는지 확인 같은 낱말로 걸린 편을 찾아 맞지 않는 문단만 고쳤고(위 「한 일」 문서 줄), 나머지는 지금 코드와 맞아 그대로 두었다. `docs/operations.md`, `docs/style_guide.md`도 걸렸지만 이번 동작을 말하는 줄이 없었다.

## 규칙 위반

- 11-20, 원인 조사 중 트랜스크립트 줄 모양을 보려고 파이썬 조각을 Bash heredoc(`python - <<'X'`)으로 한 번 넘겼다. 일감 지시 「heredoc 금지(스크래치 파일도 같다)」를 어겼다. 바로 알아채고 그 뒤 조사 스크립트는 모두 Write로 스크래치 폴더에 써서 돌렸다. 저장소 파일은 바꾸지 않았다.
- 처음 쓴 주석과 시험 설명에 em dash와 가운뎃점을 넣어 `tools/docs.py check`가 24줄을 틀림으로 잡았다. 커밋 전에 모두 고쳤다.

## 사람이 정할 것

1. `store.js` 쪽 「확인 중」 표시와 늦은 결과 줄 다듬기를 691 합친 뒤 따로 맡길지(위 「하지 않은 것」 첫 줄).
2. 합치기 준비, 셸 패널, 문서로 옮기기, 인계 요청 길도 unconfirmed를 넣은 것으로 볼지. 지금은 실패로 남아 텔레그램이 갈 수 있다.
3. 늦게 다시 보기 120초가 맞는지. 잰 값이 아니다. CC가 기록을 늦게 쓰는 까닭과 시간은 모른다.
