"""시험 DB를 세션마다 가른다(11-11, tests/testdb.py).

pytest가 뜰 때 foreman_test_<자리>_<pid>를 만들고 FOREMAN_TEST_DB에 넣는다 → 시험 파일의
Settings(mysql_database="foreman_test")는 bridge/config.py에서 이 DB로 바뀐다. 끝날 때 지운다.
마이그레이션은 각 시험이 그 DB에 이 worktree의 migrations/로 올린다 — 스스로 올리지 않는 시험은 아래 migrated_db 고정물을 받는다(11-14).

만들지 못하면(MySQL이 꺼짐 · 권한 없음) 옛 공용 foreman_test로 돌고, 시작과 끝 요약에 경고를 낸다 — 조용히 넘어가지 않는다.
"""

import os
import sys

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


@pytest.fixture(autouse=True)
def _hook_miss_log_isolated(tmp_path_factory, monkeypatch):
    """판정 없이 통과한 기록(`.run/hook_miss.log`)을 모든 시험에서 임시 폴더로 돌린다(11-15).

    브리지 쪽 갈래(역할 판정 예외 등)를 가짜 예외로 부르는 시험이 실제 기록에 줄을 넣어, 나중에 갈래별 수로 알림 문턱을
    정할 때 거짓 값이 되는 일이 있었다(log/foreman-5_hook_miss_test_isolation_20261115.md). 기록을 확인하는 시험은
    자기 고정물(miss_log)로 다시 덮어쓴다."""
    monkeypatch.setenv("FOREMAN_HOOK_MISS_LOG", str(tmp_path_factory.mktemp("hookmiss") / "hook_miss.log"))


@pytest.fixture(scope="session")
def migrated_db():
    """시험 DB에 이 worktree의 migrations/를 올리고 그 Settings를 준다(pytest 한 번에 한 번, 11-14).

    표를 쓰는 시험은 이것을 받는다 — 전에는 몇 시험이 스스로 올리지 않고 앞서 돈 시험(test_app_db의 client 등)이 올린 표에
    기대어, 그 파일만 혼자 돌리면 `Table '…' doesn't exist`로 깨졌다(log/test_isolation_20261114.md)."""
    from bridge.config import Settings
    from bridge.db.migrate import main as migrate_main
    s = Settings(mysql_database="foreman_test")   # bridge/config.py가 이 pytest의 시험 DB로 바꾼다
    assert migrate_main([], settings=s) == 0
    return s


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
    # 화면 말 시험(11-15) — 서기 몫 · 시험 없는 호버 약속이 남은 수를 매번 찍어 잊히지 않게
    sw = sys.modules.get("screen_words")
    if sw is not None and sw.LAST is not None:
        terminalreporter.write_line(sw.summary(sw.LAST), yellow=bool(sw.LAST.scribe))
