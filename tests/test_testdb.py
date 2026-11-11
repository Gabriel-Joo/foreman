"""세션마다 따로 쓰는 시험 DB(11-11, tests/testdb.py · bridge/config.py) — 운영 DB에는 닿지 않는다."""

import pytest
import testdb

from bridge.config import Settings, resolve_test_db
from bridge.db.migrate import LOCK, lock_name


def test_alias_only_exact_foreman_test(monkeypatch):
    monkeypatch.setenv("FOREMAN_TEST_DB", "foreman_test_wt_123")
    assert resolve_test_db("foreman_test") == "foreman_test_wt_123"
    # 운영 DB · 다른 이름은 그대로
    for other in ("foreman", "Foreman_test", "foreman_test_x", "foreman_testing", ""):
        assert resolve_test_db(other) == other
    assert Settings(mysql_database="foreman").mysql_database == "foreman"
    assert Settings(mysql_database="foreman_test").mysql_database == "foreman_test_wt_123"


def test_alias_without_env_keeps_name(monkeypatch):
    monkeypatch.delenv("FOREMAN_TEST_DB", raising=False)
    assert resolve_test_db("foreman_test") == "foreman_test"


@pytest.mark.parametrize("bad", ["foreman", "foreman_test", "other_db", "foreman_test" + "_x" * 40])
def test_alias_refuses_bad_env(monkeypatch, bad):
    monkeypatch.setenv("FOREMAN_TEST_DB", bad)
    with pytest.raises(ValueError):
        resolve_test_db("foreman_test")
    assert resolve_test_db("foreman") == "foreman"   # 운영 DB 이름은 나쁜 값이 있어도 그대로


def test_name_rule():
    n = testdb.make_name(4242)
    assert n.startswith("foreman_test_") and n.endswith("_4242") and len(n) <= 64
    assert testdb.pid_of(n) == 4242
    for not_ours in ("foreman", "foreman_test", "foreman_test_", "foreman_test_x", "foreman_test_X_1", "foreman_test_a-b_1"):
        assert testdb.pid_of(not_ours) is None


def test_stale_only_dead_pid_regardless_of_place():
    names = ["foreman_test_main_10", "foreman_test_foreman_2_10", "foreman_test_foreman_3_20", "foreman_test_main_30"]
    alive = {10, 30}
    # 자리 이름이 같거나 달라도 pid가 살아 있으면 남긴다
    assert testdb.stale(names, alive=lambda p: p in alive) == ["foreman_test_foreman_3_20"]


class _Cur:
    def __init__(self):
        self.sql = []

    def execute(self, sql, args=None):
        self.sql.append(sql)

    def fetchall(self):
        return ()


@pytest.mark.parametrize("name", ["foreman", "foreman_test", "mysql", "foreman_test_main"])
def test_drop_create_refuse_non_test_names(name):
    cur = _Cur()
    with pytest.raises(ValueError):
        testdb.drop(cur, name)
    with pytest.raises(ValueError):
        testdb.create(cur, name)
    assert cur.sql == []


def test_lock_name():
    assert lock_name("foreman") == LOCK   # 운영 DB는 돌던 브리지와 같은 잠금
    assert lock_name("foreman_test_main_1") == "foreman_migrate:foreman_test_main_1"
    assert len(lock_name("foreman_test_" + "a" * 24 + "_" + "9" * 10)) <= 64
