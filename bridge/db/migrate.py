"""마이그레이션 실행기 — migrations/NNNN_*.sql을 번호 순으로 한 번씩 적용한다.

    .venv/bin/python -m bridge.db.migrate            # 밀린 것 적용
    .venv/bin/python -m bridge.db.migrate --status   # 적용 상태만

- 적용한 파일은 schema_migrations에 version · sha256과 함께 남는다. 다시 돌려도 아무것도 하지 않는다(멱등)
- 이미 적용한 파일의 내용이 바뀌었으면 멈춘다. 고치려면 새 번호 파일을 더한다
- MySQL의 DDL은 문장마다 자동 커밋이라 파일 하나가 원자적이지 않다. 중간에 실패하면 어디까지 됐는지 확인하고
  손으로 정리한 뒤 다시 돌린다(실패한 파일은 기록하지 않는다)
- 동시 실행은 GET_LOCK으로 막는다
- 비동기 엔진이 아니라 pymysql을 직접 쓴다: 파일 하나를 MULTI_STATEMENTS로 서버에 넘겨 주석 · 세미콜론 해석을 서버에 맡긴다
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

from bridge.config import REPO, get_settings

MIGRATIONS = REPO / "migrations"
NAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
LOCK = "foreman_migrate"

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     VARCHAR(64) PRIMARY KEY,
  sha256      CHAR(64) CHARACTER SET ascii NOT NULL,
  applied_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB
"""


def connect() -> pymysql.connections.Connection:
    s = get_settings()
    return pymysql.connect(
        host=s.mysql_host,
        port=s.mysql_port,
        user=s.mysql_user,
        password=s.mysql_password.get_secret_value(),
        database=s.mysql_database,
        charset="utf8mb4",
        connect_timeout=s.db_connect_timeout_s,
        read_timeout=120,
        write_timeout=120,
        client_flag=CLIENT.MULTI_STATEMENTS,
        autocommit=True,
    )


def discover() -> list[tuple[str, Path, str]]:
    out = []
    for p in sorted(MIGRATIONS.glob("*.sql")):
        if not NAME_RE.match(p.name):
            raise SystemExit(f"이름 규칙(NNNN_소문자.sql)에 맞지 않는다: {p.name}")
        out.append((p.stem, p, hashlib.sha256(p.read_bytes()).hexdigest()))
    versions = [v[:4] for v, _, _ in out]
    if len(versions) != len(set(versions)):
        raise SystemExit("같은 번호의 마이그레이션이 둘 이상 있다")
    return out


def run_file(cur: pymysql.cursors.Cursor, path: Path) -> None:
    cur.execute(path.read_text(encoding="utf-8"))
    while cur.nextset():  # 뒤 문장의 오류는 여기서 올라온다
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bridge.db.migrate")
    ap.add_argument("--status", action="store_true", help="적용 상태만 보인다")
    args = ap.parse_args(argv)

    files = discover()
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, 10)", (LOCK,))
            if cur.fetchone()[0] != 1:
                print("다른 마이그레이션이 실행 중이다", file=sys.stderr)
                return 1
            cur.execute(BOOTSTRAP)
            cur.execute("SELECT version, sha256 FROM schema_migrations")
            applied = dict(cur.fetchall())

            for version, _, digest in files:
                if version in applied and applied[version] != digest:
                    print(f"적용된 뒤 내용이 바뀌었다: {version} — 새 번호 파일로 고친다", file=sys.stderr)
                    return 1
            unknown = sorted(set(applied) - {v for v, _, _ in files})
            if unknown:
                print(f"DB에는 있는데 파일이 없다: {', '.join(unknown)}", file=sys.stderr)
                return 1

            pending = [(v, p, d) for v, p, d in files if v not in applied]
            if args.status:
                for v, _, _ in files:
                    print(f"{'적용' if v in applied else '대기'}  {v}")
                return 0
            if not pending:
                print("적용할 것 없음")
                return 0
            for version, path, digest in pending:
                print(f"적용 {version} …", end=" ", flush=True)
                run_file(cur, path)
                cur.execute("INSERT INTO schema_migrations (version, sha256) VALUES (%s, %s)", (version, digest))
                print("끝")
            return 0
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT RELEASE_LOCK(%s)", (LOCK,))
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
