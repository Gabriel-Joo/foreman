# 밀린 기술문서 원고 밀어내기 (foreman-4, 11-17)

읽은 커밋: fb7121b (main). 서기실 「코드가 바뀐 편」 20편과, 실패 알림 변경에 닿아 미뤄 둔 3편(08_handoff/01_loss, 08_handoff/03_promote, 09_dispatcher/02_note_wake)을 맞췄다. 편 전체를 새로 쓰지 않고 읽은 커밋 뒤 바뀐 코드에 걸린 문단만 고쳤다. 다섯 묶음을 서브에이전트에게 나눠 맡기고 돌아온 원고를 맞댔다.

## 1. 한 일

| 편 | 고친 것 |
|---|---|
| 00_foreman, 05_roles, 09_dispatcher, 14_screen/03_panel, 09_dispatcher/02_note_wake | 머리 「읽은 커밋」만. 걸린 문단은 지금 코드와 맞았다. 02_note_wake의 「계획을 세우지 못함」(`wake`)은 원래 묶음 종류가 아니라 실패 알림 변경과 관계없다 |
| 05_roles/01_roles | 교장 지시문의 코더 줄 요지, 본문 날짜 걷음, 다루는 곳에 `bridge/docrefs.py` |
| 06_sessions | 코더 첫 글에 붙는 「고친 코드의 문서도 함께」 절, 멈춘 세션을 작업방 규칙에서 살아 있는 세션으로 셈. 다루는 곳에 `bridge/docrefs.py` |
| 07_merge, 07_merge/01_card | 합친 뒤 글의 「걸리는 문서」, 관리자 몫, 찾지 못함을 「조용한 고장」 표에. 다루는 곳에 `tools/docrefs.py`, `bridge/static/js/handoff.js` |
| 08_handoff, 08_handoff/02_summary, 04_move, 01_loss, 03_promote | 인계 요약 실패 여섯은 ⚠와 「바로」로 곧장 가고 성공은 묶임. 점검과 문서 옮기기 실패는 아직 묶인다는 것. 코더 규칙 절이 인계 글 뒤에 붙음 |
| 09_dispatcher/01_plan | 본문 날짜 걷음, 다루는 곳에 `bridge/docrefs.py` |
| 10_scribe, 10_scribe/01_room | 코더가 문서를 함께 고쳐 서기 일감이 좁아진 것, 포트폴리오 게시 묶음을 프로젝트별로(5adb03a) |
| 10_scribe/04_notion | `GET /api/publish?project=`의 포트폴리오 상태, `portfolio_page`가 비면 게시 거절, `[c:dc4944e]`를 main의 `[c:16dcb3a]`로, 머리 견본의 자리표시를 fb7121b로 |
| 11_notify | 묶음 표와 「어디서 오나」 표의 옮기기 요약 줄, 실패 알림 문단 둘, 점검과 문서 옮기기 실패는 묶인다는 문장 |
| 13_usage | Fable 가격 네 칸 「출처 없음」, 환산 「모름」(`unpriced`), `/usage` 화면의 「+ 모름」 |
| 14_screen | 화면 js 수 32, js 지도에 `shipstate.js` |
| 14_screen/05_check | 목록 수 다시 셈(바뀌지 않음), 본문 날짜 걷음 |
| 16_tests | 시험 수: 파이썬 파일 95, pytest 1,221, js 파일 39, js 시험 222(돌려서 통과). 새 시험 묶음 문단 |

맞대기에서 관리자가 직접 고친 것: 고친 문단에 남아 있던 본문 날짜 「11-17」 9곳을 걷었다(07_merge, 07_merge/01_card 4곳, 10_scribe, 10_scribe/01_room 2곳, 11_notify, 14_screen/05_check). 11_notify 묶음 표의 「실패는 빼고」를 「인계 요약 실패는 빼고」로 좁혔다. 08 묶음이 코드로 확인한 대로 점검과 문서 옮기기의 실패는 같은 `handoff` 종류로 아직 묶이기 때문이다.

## 2. 코드가 이상해 보인 것 (고치지 않음)

- **실패는 바로 안다는 규칙의 구멍**: `bridge/losscheck.py`(압축으로 잊은 것 찾기 실패 두 곳)와 `bridge/promote.py`(목록 실패 두 곳, 확인 실패 한 곳)가 `HandoffManager._notify`를 `fail=True` 없이 부른다. 그래서 묶음을 켠 프로젝트에서는 이 실패들이 21:00에야 간다. `log/foreman-5_fail_now_unpriced_20261117.md` 1-3 표에는 이 다섯이 빠져 있다. 고치면 08_handoff/01_loss, 03_promote, 11_notify의 「묶음에 실린다」 문장도 같이 고쳐야 한다
- **Fable 주간 한도 추정이 잠깐 낮게 나올 수 있음**: `bridge/usage.py` `limit_status`가 14일치 관찰을 보는데, 가격을 지우기 전 관찰에는 옛 Fable 가격으로 센 `seen_usd`가 남아 있다. 같은 창에서 그 관찰이 마지막이면 추정이 측정 %보다 낮게 나올 수 있다. 새 관찰이 쌓이면 풀린다
- **빈 코더 세션에는 코더 문서 규칙이 붙지 않음**: 첫 글도 요약도 없이 띄운 코더 세션에는 `bridge/handoff.py`가 규칙 절을 넣지 않는다. `log/foreman-8_docrefs_20261117.md` 3절에 「붙지 않는 곳」으로 적혀 있어 의도된 것이다. 다른 저장소의 빈 코더 세션은 그 저장소 CLAUDE.md에도 이 규칙이 없을 수 있다. 원고(06_sessions)에는 한계로 적었다
- `config/models.toml`의 Fable 설명 「가장 비싸고」가 가격 출처를 지운 지금과 결이 다르다. 13_usage가 그 설명을 옮기고 있어 원고는 두었다

## 3. 그대로 둔 것

- 「판단이 필요한 것」(`log/foreman-5_notion_evidence_scope_20261117.md`)에 걸린 줄: 00_foreman 147, 06_sessions 44, 08_handoff 37, 08_handoff/01_loss 60, 08_handoff/02_summary 177, 10_scribe 22
- docrefs `--unfixed`가 14_screen과 14_screen/03_panel의 몇 줄을 「안 고침」으로 낸다. `bridge/static/`, `tests/`처럼 넓은 경로를 가리키는 줄이라 걸린다. 읽어 보니 지금 코드와 맞았다
- 14_screen/05_check의 「지금(fb7121b)」 「처음 쓸 때(e5d584b)」처럼 본문에 해시를 둔 문장은 예전부터 있던 것이라(목록 수를 어느 판에서 셌는지 밝히는 문장) 해시를 새 값으로만 바꿨다
- 03_promote 172줄의 em dash는 실제 알림 글을 인용한 것이다

## 4. 확인

- 23편 머리 「읽은 커밋」 모두 fb7121b. 새로 단 커밋 근거(16dcb3a, 408e4ed, 6fcf7ad, 9ac4527)는 모두 main에 있다
- `tests/test_evidence.py`, `tests/test_screen_words.py`, `tests/test_techdoc.py` 통과(31개). 화면 말 서기 몫 0줄
- 실제 화면은 보지 않았다. 화면 글은 코드와 log에서 옮겼다

## 5. 규칙

규칙 위반 하나: 맞대기 중 본문 날짜를 걷기 직전에 도구 호출 사이 진행 글 한 줄을 영어로 썼다(「항상 한국어로」 위반). 브리지 훅이 알려 주어 알았고, 그 뒤 글은 한국어로 썼다. 원고와 log 내용에는 영향이 없다.

그 밖에는 새로 쓴 줄에 em dash와 가운뎃점 없음(인용한 알림 글 하나만 예외), 고친 곳은 `notion/`과 이 log뿐, 파일은 Edit와 Write로만 고쳤다.
