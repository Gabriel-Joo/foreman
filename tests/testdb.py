"""세션마다 따로 쓰는 시험 DB(11-11) — 이름 짓기 · 만들기 · 치우기.

pytest가 뜰 때(conftest) foreman_test_<자리>_<pid> 를 만들어 FOREMAN_TEST_DB 환경변수에 넣고, 끝날 때 지운다.
시험 파일은 그대로 Settings(mysql_database="foreman_test")라고 쓴다 — bridge/config.py가 그 값만 이 DB로 바꿔 읽는다.

이름 규칙: foreman_test_<자리>_<pid>
  <자리>  .worktrees/<이름> 아래면 그 이름(소문자, [a-z0-9_] 밖은 _), 원본 폴더면 main
  <pid>   pytest 프로세스 pid — 같은 worktree에서 둘을 동시에 돌려도 이름이 다르다
남은 것 치우기: pytest가 뜰 때마다 이름 끝의 pid가 이 서버에 살아 있지 않은 것을 지운다(자리 이름은 보지 않는다 —
  다른 worktree의 살아 있는 시험은 지우지 않는다). 손으로:
    .venv/bin/python tests/testdb.py            # 목록(살아 있음/남음)
    .venv/bin/python tests/testdb.py --clean    # 남은 것(pid 죽음)만 지운다
운영 DB(foreman)와 옛 공용 시험 DB(foreman_test)는 이름 검사(OURS)에 걸리지 않아 지울 수 없다.
"""

import os
import re
import sys
from pathlib import Path

import pymysql

REPO = Path(__file__).resolve().parent.parent
PREFIX = "foreman_test_"
ENV = "FOREMAN_TEST_DB"
OURS = re.compile(r"^foreman_test_[a-z0-9_]{1,24}_(\d{1,10})$")


def place() -> str:
    """이 저장소 자리 — worktree 이름 또는 main."""
    if REPO.parent.name == ".worktrees":
        tag = re.sub(r"[^a-z0-9_]", "_", REPO.name.lower())[:24].strip("_")
        return tag or "wt"
    return "main"


def make_name(pid: int | None = None) -> str:
    name = f"{PREFIX}{place()}_{pid or os.getpid()}"
    assert OURS.match(name), name
    return name


def pid_of(name: str) -> int | None:
    m = OURS.match(name)
    return int(m.group(1)) if m else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def connect(s) -> pymysql.connections.Connection:
    """DB를 고르지 않은 연결(만들기 · 지우기용)."""
    return pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), charset="utf8mb4",
                           connect_timeout=s.db_connect_timeout_s, autocommit=True)


def listing(cur) -> list[str]:
    cur.execute(r"SHOW DATABASES LIKE 'foreman\_test\_%'")
    return [n for (n,) in cur.fetchall() if OURS.match(n)]


def stale(names: list[str], alive=pid_alive) -> list[str]:
    """pid가 죽은 것만 — 자리 이름은 보지 않는다."""
    return [n for n in names if not alive(pid_of(n))]


def create(cur, name: str) -> None:
    if not OURS.match(name):
        raise ValueError(f"시험 DB 이름이 아니다: {name}")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")


def drop(cur, name: str) -> None:
    """이 DB에 붙은 내 연결을 끊고 지운다. 메타데이터 잠금에 끝없이 걸리지 않게 lock_wait_timeout을 짧게."""
    if not OURS.match(name):  # foreman · foreman_test는 여기서 막힌다
        raise ValueError(f"시험 DB 이름이 아니다: {name}")
    cur.execute("SELECT id FROM information_schema.processlist WHERE db = %s AND id <> CONNECTION_ID()", (name,))
    for (tid,) in cur.fetchall():
        try:
            cur.execute(f"KILL {int(tid)}")
        except pymysql.MySQLError:
            pass  # 그 사이 끝났다
    cur.execute("SET SESSION lock_wait_timeout = 15")
    cur.execute(f"DROP DATABASE IF EXISTS `{name}`")


def clean_stale(cur) -> tuple[list[str], list[str]]:
    """남은 것 치우기 — (지운 것, 못 지운 것)."""
    done, failed = [], []
    for n in stale(listing(cur)):
        try:
            drop(cur, n)
            done.append(n)
        except pymysql.MySQLError:
            failed.append(n)
    return done, failed


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(REPO))
    from bridge.config import Settings
    s = Settings(mysql_database="foreman")  # 연결 정보만 쓴다(DB는 고르지 않는다)
    conn = connect(s)
    try:
        with conn.cursor() as cur:
            if "--clean" in argv:
                done, failed = clean_stale(cur)
                print(f"지움 {len(done)}: {' '.join(done) or '-'}")
                if failed:
                    print(f"못 지움 {len(failed)}: {' '.join(failed)}", file=sys.stderr)
                    return 1
                return 0
            for n in listing(cur):
                print(f"{'살아 있음' if pid_alive(pid_of(n)) else '남음'}  {n}")
            return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
