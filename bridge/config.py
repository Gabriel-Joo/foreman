"""브리지 설정.

비밀값은 저장소 맨 위 파일에서 읽는다(권한 600, .gitignore `.env*`):
  .env.db      MYSQL_USER · MYSQL_PASSWORD · MYSQL_DATABASE (compose와 같은 파일. MYSQL_ROOT_PASSWORD는 읽지 않는다)
  .env.bridge  FOREMAN_API_TOKEN · FOREMAN_HOOK_TOKEN
비밀이 아닌 값은 여기 기본값이고 같은 이름의 환경변수로 덮어쓴다.
비밀값은 SecretStr이라 repr·로그에 값이 나오지 않는다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = Path(__file__).resolve().parent.parent

MIN_TOKEN_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO / ".env.db", REPO / ".env.bridge"),
        env_file_encoding="utf-8",
        extra="ignore",  # MYSQL_ROOT_PASSWORD 등 브리지가 쓰지 않는 키는 버린다
    )

    # DB — 호스트 도커 FOREMAN 전용 MySQL (README 3.12)
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3308
    mysql_database: str = "foreman"
    mysql_user: str = "foreman_app"
    mysql_password: SecretStr

    # 브리지 자체 인증 — 브라우저·API용과 hook용을 나눈다(hook 토큰이 새도 주입·API는 못 쓴다)
    foreman_api_token: SecretStr
    foreman_hook_token: SecretStr

    # 바인드 — 개발 중에는 ssh -L로만 붙는다. 외부 노출은 브리프 02(터널 + Access)
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000

    # 모든 외부 호출에 타임아웃(01 결과 "부수적으로 확인한 것" — timeout 없는 클라이언트는 끝없이 멈춘다)
    db_connect_timeout_s: int = 5
    db_query_timeout_s: float = 5.0
    db_retry_max_s: float = 10.0

    ws_auth_timeout_s: float = 5.0
    ws_heartbeat_s: float = 15.0

    # 적재 대기열 상한. 넘치면 생산자가 받는다(2단계 와처는 offset을 멈추는 것으로 대응)
    ingest_queue_max: int = 10_000

    # 디버그 엔드포인트(/api/debug/*). 터널로 내보내기 전에 끈다
    debug_endpoints: bool = Field(default=False)

    @field_validator("foreman_api_token", "foreman_hook_token")
    @classmethod
    def _long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < MIN_TOKEN_LEN:
            raise ValueError(f"토큰은 {MIN_TOKEN_LEN}자 이상이어야 한다")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
