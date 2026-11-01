"""비동기 DB 엔진. 모든 쿼리는 호출하는 쪽에서 asyncio.timeout으로 감싼다(db_query_timeout_s)."""

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bridge.config import Settings


def make_engine(s: Settings) -> AsyncEngine:
    url = URL.create(
        "mysql+aiomysql",
        username=s.mysql_user,
        password=s.mysql_password.get_secret_value(),
        host=s.mysql_host,
        port=s.mysql_port,
        database=s.mysql_database,
        query={"charset": "utf8mb4"},
    )
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=s.db_connect_timeout_s,  # 풀에서 연결을 기다리는 상한
        pool_pre_ping=True,                   # DB 재시작 뒤 죽은 연결을 버린다
        pool_recycle=1800,
        hide_parameters=True,                 # 예외 메시지에 프롬프트 · 명령 원문이 실리지 않게
        connect_args={"connect_timeout": s.db_connect_timeout_s},
    )
