# 시험 DB를 세션마다 가르기 — 결과 (11-11, 코더 foreman-2 · cc/foreman-2)

## 한 일

- **새 `tests/testdb.py`**: 이름 짓기 · 만들기 · 지우기 · 남은 것 치우기를 한 곳에 모았다. 손으로 쓰는 명령도 이 파일이다
- **새 `tests/conftest.py`**: pytest가 뜰 때 남은 것을 치우고, 이 세션의 DB를 만들어 `FOREMAN_TEST_DB`에 넣는다. 끝날 때(`pytest_unconfigure`) 지운다. 시작 머리글에 `시험 DB: <이름>`이 찍힌다
- **`bridge/config.py`**: `resolve_test_db()`와 `mysql_database` 검사기를 더했다. 값이 **정확히 `"foreman_test"`** 이고 `FOREMAN_TEST_DB`가 있을 때만 그 DB로 바꾼다. `FOREMAN_TEST_DB`가 `foreman_test_`로 시작하지 않거나 64자를 넘으면 거부한다. 그 밖의 값(운영 `foreman` 등)은 그대로 둔다
  - 시험 파일 10곳의 `Settings(mysql_database="foreman_test")`는 **고치지 않았다**. 앞으로 다른 세션이 같은 식으로 쓰는 새 시험도 저절로 갈린다
- **`bridge/db/migrate.py`**: `GET_LOCK` 이름을 DB마다 따로 잡는다(`lock_name()`). 운영 `foreman`은 옛 이름 `foreman_migrate` 그대로(돌던 브리지와 같은 잠금), 그 밖은 `foreman_migrate:<db>`. 잠금은 서버 전체 이름이라, 그대로 두면 동시에 도는 두 시험이 서로 10초를 기다리다 실패할 수 있었다
- **`tests/test_terminal.py` 한 줄**: `model_copy(update=…)`는 검사기를 거치지 않아 `resolve_test_db("foreman_test")`로 바꿨다
- **`tests/test_app_db.py`** (관리자 승인 뒤): 운영 DB `foreman`에 앱을 띄우던 시험을 세션 시험 DB로 옮겼다(픽스처에서 migrate를 먼저 올린다). 같이 토큰 헤더를 `_bearer()`(repr이 `Bearer ***`)로 만들고, 거부 사유 검사를 `leaked` 변수로 뺐다. 시험의 뜻(201/409/401/503 등)은 그대로다
- **새 `tests/test_testdb.py`** (13건): 운영 DB 이름이 바뀌지 않는다 / 접두사가 아니면 거부 / `drop` · `create`가 `foreman` · `foreman_test`를 거부 / 남은 것 치우기는 pid만 본다 / 잠금 이름

## 이름 짓는 규칙

`foreman_test_<자리>_<pid>` (예: `foreman_test_foreman_2_822428`, 원본 폴더는 `foreman_test_main_<pid>`)
- `<자리>`: `.worktrees/<이름>` 아래면 그 이름(소문자, `[a-z0-9_]` 밖의 글자는 `_`, 24자까지), 원본 폴더면 `main`. 목록만 보고 어느 세션 것인지 알 수 있다
- `<pid>`: pytest 프로세스 pid. 같은 worktree에서 둘을 동시에 돌려도 이름이 다르다. 남은 것인지 가리는 기준도 이것이다
- 운영 DB 보호: 만들기 · 지우기는 `^foreman_test_[a-z0-9_]{1,24}_\d+$`에 맞는 이름만 받는다. `foreman` · `foreman_test`는 여기서 막힌다. DB 권한도 `foreman\_test\_%`만 열렸다(아래)

## 남을 때 처리

| 경우 | 어떻게 되나 | 확인 |
|---|---|---|
| 정상 끝 · 실패로 끝 | `pytest_unconfigure`에서 지운다. 이 DB에 붙어 있는 내 연결은 먼저 끊고(`KILL`), `lock_wait_timeout=15`로 끝없이 걸리지 않게 한다 | 끝난 뒤 `foreman\_test\_%` 0개 |
| Ctrl+C (SIGINT) | 위와 같다 — 끊기면서 지운다 | 직접 확인: 끊은 쪽은 바로 사라짐 |
| 죽음 (kill -9 · 세션이 끝남) | 남는다 → **다음 pytest가 뜰 때** 이름 끝의 pid가 이 서버에 살아 있지 않은 것을 지운다 | 직접 확인: `남음 foreman_test_foreman_2_843292` → 다음 pytest 뒤 0개 |
| 손으로 | `.venv/bin/python tests/testdb.py`(목록 · 살아 있음/남음), `--clean`(남은 것만 지움) | |

- 치우기는 **pid만 본다 — 자리 이름은 보지 않는다**. 다른 worktree의 살아 있는 시험은 지우지 않는다. 같은 worktree라도 pid가 살아 있으면 지우지 않는다(`test_stale_only_dead_pid_regardless_of_place`, 실제로는 동시 실행 중 두 DB가 끝까지 같이 있었다)
- pid가 다른 프로세스에 다시 쓰이면 그 DB는 한동안 남는다(지우지 않는 쪽으로 틀린다). 손 명령으로 볼 수 있다
- DB를 만들지 못하면(MySQL이 꺼짐 · 권한 없음) 옛 공용 `foreman_test`로 돌고, **시작 머리글과 끝 요약에 경고**를 낸다(조용히 넘어가지 않는다). 권한이 열리기 전에 실제로 이렇게 돌았다

## 조사 결과

- 시험 계정 `foreman_app`에는 처음에 `CREATE DATABASE` 권한이 없었다(`foreman`.* · `foreman_test`.*만). 관리자에게 알렸고, 사용자가 `GRANT … ON \`foreman\_test\_%\`.* TO 'foreman_app'@'%'`를 쳤다(SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER). 이 세션은 권한을 건드리지 않았다
- `foreman_test`를 이름으로 쓰는 시험은 10개 파일이고 모두 `Settings(mysql_database="foreman_test")` 꼴이다(`test_terminal`만 `model_copy`). conftest는 없었고 CI(GitHub Actions)도 아직 없다
- 마이그레이션은 시험마다 `migrate_main([], settings=s)`로 그 DB에 이 저장소의 `migrations/`를 올린다(`REPO`가 `bridge/config.py` 위치 기준이라 worktree마다 자기 것). 그래서 DB만 가르면 마이그레이션도 갈린다
- **운영 DB에 쓰는 시험이 따로 있었다**: `test_app_db`(앱 전체를 운영 `foreman`에 띄우고 `/api/debug/events`를 지움). 첫 동시 실행에서 이 시험 1건이 깨졌다(`test_emit_duplicate_uuid_409` — 두 실행이 같은 uuid를 넣고 서로의 DELETE가 지움). 위처럼 고쳤다
- 아직 운영 DB에 쓰는 시험 둘: `test_foreman_note.py`(`with_db`)와 `test_usage.py::test_record_cli_writes_rows`. 둘 다 무작위 이름(`zz-test-<hex>` · `zz<hex>`)으로 쓰고 자기 행만 지워서 동시 실행에서는 겹치지 않는다. 이번에는 두었다(나중에 할 일 후보 — 아래)
- **토큰이 출력에 풀려 나오던 문제**: `assert client.post(..., headers=_auth()).status_code == 409`가 실패하면 pytest가 호출 인자를 풀어 쓰면서 `FOREMAN_API_TOKEN` 값을 그대로 출력했다. 첫 동시 실행에서 이 세션의 도구 출력에 한 번 찍혔다(출력 파일은 바로 지움 · 로그 · 커밋에는 없음 · 교체는 사용자 판단으로 관리자가 알림). hook 토큰이 든 `{"Authorization": f"Bearer {hook}"}`도 같았다. `_bearer()`로 막았다

## 확인 (11-11)

| 항목 | 결과 |
|---|---|
| 혼자 전체 | pytest **698 통과 · 1 건너뜀**(전과 같음 + 새 13건 포함), node **123 통과**. 머리글 `시험 DB: foreman_test_foreman_2_805678`, 경고 없음 |
| 동시 둘 | 이 worktree(A) + scratchpad 복사본(B, git 밖)을 같이: **A 698 · B 698 통과**(1 건너뜀씩). 도는 동안 `foreman_test_foreman_2_822428` · `foreman_test_main_822430` 둘이 따로 있었다 |
| 한쪽만 마이그레이션 | B에만 시험용 `0099_only_in_copy.sql`(표 `only_in_copy`, 커밋 안 함 · 복사본째 지움). 도는 중: B DB는 `0099` + `only_in_copy`, A DB는 `0031`에 표 없음. A에 「DB에는 있는데 파일이 없다」 없음 |
| 치워짐 | 매번 끝난 뒤 `SHOW DATABASES LIKE 'foreman\_test\_%'` → 0개 |
| 운영 DB | `foreman` 표 27 · `schema_migrations` 마지막 `0031_handover_todo_edit`(31개) — 모든 실행 전후 같음. 공용 `foreman_test`도 표 27 그대로 |

## 설계와 달랐던 점

- 브리프는 "시험 파일 여기저기 대신 한 곳으로"였다. 그렇게 했지만 두 곳은 시험 파일을 고쳤다: `test_terminal`(`model_copy`가 검사기를 안 거침, 한 줄)과 `test_app_db`(원래 운영 DB를 쓰던 시험 — `foreman_test` 문제와는 별개였지만 동시 실행을 깨서 관리자 승인 뒤 옮김)
- 시험 DB 이름을 바꾸는 자리를 운영 코드(`bridge/config.py`)에 두었다. 시험 파일 10곳 · 앞으로 쓸 시험을 고치지 않으려는 선택이다. 바뀌는 조건은 값이 정확히 `"foreman_test"`이고 환경변수가 접두사에 맞을 때뿐이며, 운영 `foreman`에는 닿지 않는 것을 `test_testdb.py`가 지킨다
- 마이그레이션 잠금 이름을 바꿔야 했다(브리프에 없음). 운영 DB 잠금 이름은 그대로다

## 되돌리는 법

- 이 브랜치의 커밋을 `git revert`하면 예전처럼 모두 공용 `foreman_test`를 쓴다. 코드만 되돌릴 때 `tests/conftest.py`를 지우면, 환경변수가 없어 `resolve_test_db`가 그대로 `foreman_test`를 돌려준다(config는 둬도 됨)
- 남은 시험 DB 정리: `.venv/bin/python tests/testdb.py --clean`
- DB 권한 되돌리기(사용자가): `docker exec -it foreman-mysql mysql -uroot -p -e "REVOKE ALL PRIVILEGES ON \`foreman\_test\_%\`.* FROM 'foreman_app'@'%';"`

## README에서 뺄 줄

- 「나중에 할 일」 **「시험 DB를 세션마다 나누기」** 줄 — 이번에 했다

## 관리자가 지시문에서 뺄 문구

- 「시험 DB(`foreman_test`)를 지금은 셋이 같이 쓴다 … 전체 pytest 전에 `ps -eo pid,args | grep '[p]ytest'`로 따로 확인하고, 돌고 있으면 그 PID가 끝날 때까지 기다린다」
- 그 밖의 「혼자 돌리고 기다려라」 류. 다만 **합친 뒤부터** 맞는 말이다 — 아직 이 브랜치를 안 가진 worktree는 예전처럼 공용 `foreman_test`를 쓴다

## 문서에 옮길 것 (docs는 서기 292가 맞추는 중이라 고치지 않았다)

- `docs/operations.md` 「3. 돌리기 · 확인」: pytest는 세션마다 `foreman_test_<자리>_<pid>`를 만들어 쓰고 끝나면 지운다. 시작 머리글의 `시험 DB:` 줄로 어느 DB인지 본다. 「공용 foreman_test로 돈다」 경고가 나오면 따로 돌지 않는 것이다(MySQL · 권한 확인). 남은 것은 `.venv/bin/python tests/testdb.py [--clean]`
- 새 시험이 DB를 쓰면 `Settings(mysql_database="foreman_test")`라고 쓰면 된다(자동으로 세션 DB). `model_copy(update=…)`로 바꿀 때는 `resolve_test_db("foreman_test")`. 운영 `Settings()` · `get_settings()`로 DB에 쓰지 않는다
- 토큰이 든 헤더를 assert 줄 안에서 만들지 않는다(실패하면 pytest가 값을 풀어 쓴다) — `test_app_db.py`의 `_bearer()` 참고

## 나중에 할 일 후보

- `test_foreman_note.py` · `test_usage.py::test_record_cli_writes_rows`도 운영 DB 대신 세션 시험 DB로(지금은 무작위 이름이라 겹치지는 않는다 — 시험이 죽으면 운영 DB에 `zz…` 행이 남을 수 있다)
