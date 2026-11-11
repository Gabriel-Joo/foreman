"""시험 DB를 세션마다 가른다(11-11, tests/testdb.py).

pytest가 뜰 때 foreman_test_<자리>_<pid>를 만들고 FOREMAN_TEST_DB에 넣는다 → 시험 파일의
Settings(mysql_database="foreman_test")는 bridge/config.py에서 이 DB로 바뀐다. 끝날 때 지운다.
마이그레이션은 각 시험이 그 DB에 이 worktree의 migrations/로 올린다(지금처럼).

만들지 못하면(MySQL이 꺼짐 · 권한 없음) 옛 공용 foreman_test로 돌고, 시작과 끝 요약에 경고를 낸다 — 조용히 넘어가지 않는다.
"""

import os

import pytest
import testdb

_state: dict = {"name": None, "warn": None, "dropped": None}


def pytest_configure(config: pytest.Config) -> None:
    if hasattr(config, "workerinput"):  # xdist 일꾼은 주인이 정한 것을 쓴다
        return
    from bridge.config import Settings
    name = testdb.make_name()
    try:
        s = Settings(mysql_database="foreman")  # 연결 정보만(DB는 고르지 않는다)
        conn = testdb.connect(s)
    except Exception as e:  # noqa: BLE001 — DB가 없어도 DB 안 쓰는 시험은 돈다
        _state["warn"] = f"시험 DB를 만들지 못했다(연결 실패: {type(e).__name__}) — 공용 foreman_test로 돈다"
        return
    try:
        with conn.cursor() as cur:
            try:
                testdb.clean_stale(cur)
            except Exception:  # noqa: BLE001 — 남은 것 치우기 실패는 시험을 막지 않는다(다음에 다시)
                pass
            try:
                testdb.create(cur, name)
            except Exception as e:  # noqa: BLE001
                _state["warn"] = (f"시험 DB {name}를 만들지 못했다({type(e).__name__}: {e}) — 공용 foreman_test로 돈다. "
                                  "둘 이상이 동시에 돌리면 깨진다")
                return
    finally:
        conn.close()
    os.environ[testdb.ENV] = name
    _state["name"] = name


def pytest_report_header(config: pytest.Config) -> str:
    return f"시험 DB: {_state['name']}" if _state["name"] else f"경고: {_state['warn']}"


def pytest_unconfigure(config: pytest.Config) -> None:
    name = _state["name"]
    if not name:
        return
    os.environ.pop(testdb.ENV, None)
    from bridge.config import Settings
    try:
        conn = testdb.connect(Settings(mysql_database="foreman"))
        try:
            with conn.cursor() as cur:
                testdb.drop(cur, name)
        finally:
            conn.close()
        _state["dropped"] = True
    except Exception as e:  # noqa: BLE001 — 다음 pytest가 뜰 때 pid가 죽은 것으로 치운다
        _state["dropped"] = False
        print(f"\n경고: 시험 DB {name}를 지우지 못했다({type(e).__name__}) — 다음 pytest 시작 때 치운다"
              " · 손으로: .venv/bin/python tests/testdb.py --clean")


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if _state["warn"]:
        terminalreporter.write_line(f"경고: {_state['warn']}", yellow=True)
