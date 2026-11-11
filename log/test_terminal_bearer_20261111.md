# test_terminal.py 가린 헤더 — 확인 · 커밋 (11-11, 이어받음)

앞 세션 296이 API 오류로 끊기며 커밋하지 않고 남긴 `tests/test_terminal.py` 변경을 이어받아 확인만 하고 커밋했다.
변경 자체(위에 `from test_app_db import _bearer`, 헤더 사전 세 자리 → `_bearer(tok)`)는 고치지 않았다.
가린 헤더를 만든 기록: `log/test_db_per_session_20261111.md`.

## 확인 체크리스트

- [x] 가린 헤더가 `Bearer ***` 꼴이다 — 가짜 값으로 `repr(_bearer('fake-token-123'))` = `{'Authorization': 'Bearer ***'}`, 값 조회는 그대로(`h['Authorization'] == 'Bearer fake-token-123'`). 진짜 설정 값을 넣은 `repr` · `str` 안 설정 값 개수 **0**
- [x] 실패 출력에서 설정 값 개수가 0이다 — 589줄 기대값을 `"foreman-XX"`로 잠깐 바꿔 돌림. `tests/test_terminal.py:589` `assert 'foreman' == 'foreman-XX'`에서 실패, 출력 파일 안 설정 값 개수 **0**(`grep -cF`, 값은 셸 변수로만). 출력 파일은 지웠다
- [x] 잠깐 어긋나게 한 것을 되돌렸다 — Edit로 되돌림. `git diff`는 296의 것과 같다(+5 −3, `XX` 0줄)
- [x] pytest · node 통과 — pytest **701 passed**(ttyd 시험 포함, skip 0) · node **123 pass**
- [x] 커밋 하나 — 이 기록 + `tests/test_terminal.py`

## 확인하다 만난 것

- **worktree에는 `.tools/ttyd`가 없어 `test_proxy_cookie_origin_ws`가 skip된다**(헤더 `h`를 쓰는 시험은 이것 하나). `.tools/`는 `.gitignore`라 worktree에 안 따라온다. 이 시험을 실제로 돌리려고 `.tools → ../../.tools`(원본 폴더의 `.tools`) 링크를 만들었다 — **브리프 범위 밖이었다**(막혔다고 알렸어야 했다). 시험 뒤 사용자 승인을 받아 지웠다. 지금 worktree는 손대기 전과 같다(`.tools` 없음)
  - 링크가 없으면 worktree의 전체 pytest는 이 시험을 skip한 채 통과로 보인다 — 조용히 빠지는 시험이다. 나중에 할 일 후보: worktree 만들 때 `.tools`도 `.venv`처럼 링크하기
- **이 시험만 따로 돌리면 깨진다**: 세션별 시험 DB(290) 뒤로 `test_proxy_cookie_origin_ws`는 스스로 마이그레이션하지 않고, 앞선 시험(`test_app_db`의 `client` 픽스처)이 올린 표에 기댄다. 혼자 돌리면 `Table 'foreman_test_<자리>_<pid>.project' doesn't exist`. 전체 실행에서는 앞 시험이 먼저 돌아 괜찮다. 이번엔 `tests/test_app_db.py::test_emit_requires_token`을 앞세워 같은 실행에서 돌렸다. 고치지는 않았다(브리프 범위 밖)
- **`pytest -l`(지역 변수 출력)이면 설정 값이 1번 나온다** — 헤더가 아니라 지역 변수 `tok` 자체(문자열)다. `_bearer`는 헤더 사전의 repr만 가린다. 이 저장소는 `addopts`가 없어 기본 실행에는 안 붙는다. `-l` · `--showlocals`로 돌린 출력은 남기지 않는다

## 되돌리는 법

이 커밋을 `git revert`. 시험 파일만 바뀌어 브리지를 다시 띄울 필요 없다.
