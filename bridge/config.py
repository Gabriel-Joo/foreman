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

    # 2단계 — 트랜스크립트 와처 · 조립
    projects_root: Path = Path.home() / ".claude" / "projects"
    sessions_dir: Path = Path.home() / ".claude" / "sessions"   # <pid>.json만 읽는다(.key는 열지 않는다)
    watch_enabled: bool = True          # 테스트 · 일회성 적재(python -m bridge.ingest)에서는 끈다
    # 뜰 때 "돌던 잃은 것 점검"을 failed로 — 운영 DB에 앱을 띄우는 시험(test_app_db)은 끈다. 11-09 시험이 운영 브리지에서
    # 돌던 점검 #2를 "브리지가 다시 떠서 멈췄습니다"로 바꿨다(브리지는 그대로 돌고 있었다)
    losscheck_recover: bool = True
    ingest_chunk_bytes: int = 8 << 20   # 한 번에 읽는 양(= DB 트랜잭션 하나)
    ingest_timeout_s: float = 120.0     # 덩어리 하나 적재 상한
    ingest_alert_s: float = 300.0       # 한 파일이 이만큼 같은 자리에서 실패 중이면 "적재 막힘"(텔레그램 · 대시보드, 11-03)
    ingest_tick_alert_s: float = 120.0  # 실시간 감시 루프가 이만큼 돌지 않으면 "와처 멈춤"
    rescan_s: float = 60.0              # inotify를 놓쳤을 때를 위한 전체 크기 비교 주기
    sweep_s: float = 30.0               # 프로세스가 사라진 세션의 열린 턴을 닫는 주기
    link_s: float = 30.0                # 서브에이전트 턴 연결 · 토큰 합계 주기
    idle_close_s: float = 60.0          # 프로세스가 없고 이만큼 조용하면 열린 턴을 닫는다
    # 끝 신호 없이 버려진 턴(abandoned) — 응답 없는 열린 턴이 이만큼 조용하면(CC가 일하지 않을 때) 또는
    # 다음 입력이 이만큼 뒤에 오면. 실측: 진짜로 다음 입력에 합쳐진 것(merged)은 최대 56분
    turn_abandon_s: float = 3600.0
    subagent_stale_s: float = 1800.0    # running인데 이만큼 기록 · 끝 신호가 없으면 stale(옛 CC는 meta에 finished가 없다)

    # 4단계 — 텔레그램 알림(규칙은 config/notify.toml)
    notify_enabled: bool = True         # 테스트에서는 끈다
    notify_config: Path = REPO / "config" / "notify.toml"

    # 5단계 — 승인 정책(규칙은 config/approval.toml)
    approval_enabled: bool = True
    approval_config: Path = REPO / "config" / "approval.toml"

    # 7단계 — 터미널 패널(ttyd + tmux). ttyd는 TCP 포트를 열지 않고 UNIX 소켓에만 묶는다(.run/은 0700).
    # 브라우저는 브리지(127.0.0.1)의 /terminal/을 거쳐서만 닿는다 — 쿠키 인증(API 토큰으로 받는다)
    terminal_enabled: bool = True       # 테스트에서는 끈다
    ttyd_bin: Path = REPO / ".tools" / "ttyd"
    terminal_socket: Path = REPO / ".run" / "ttyd.sock"
    terminal_tmux_session: str = "foreman-shell"
    terminal_rcfile: Path = REPO / "deploy" / "shell" / "foreman-bashrc"
    terminal_request_ttl_s: float = 1800.0   # CC가 부탁한 명령을 이만큼 기다린다(그 뒤 친 명령은 결과를 전달하지 않는다)
    terminal_output_lines: int = 60          # 세션에 전달하는 출력 — 마지막 N줄(마스킹 후)
    terminal_cookie_ttl_s: float = 12 * 3600

    # 8단계 — CI/CD 웹훅(Jenkins · Harbor · ArgoCD)과 인과 체인(규칙은 config/pipeline.toml).
    # 웹훅은 클러스터(libvirt VM)에서 온다 — 127.0.0.1에는 닿지 못하므로 virbr0(호스트 쪽 192.168.122.1)에 웹훅 전용 포트를 연다.
    # 그 포트는 /webhooks/*만 받고, 보낸 곳이 VM 망(아래 CIDR)이어야 하며, 토큰(FOREMAN_WEBHOOK_TOKEN — hook · API와 별개)이 필요하다
    foreman_webhook_token: SecretStr | None = None
    # 11-03 재개: Jenkins는 Jenkinsfile 알림(웹훅 포트 8001) + 토큰 없는 보정(로컬 git 폴링 → 빠진 알림 찾기).
    # 끄면(False) 8001이 닫혀 Jenkinsfile curl은 바로 실패하고 || true — 빌드 영향 없음(log/stage8_cicd_result.md 되돌리기)
    pipeline_enabled: bool = True
    pipeline_config: Path = REPO / "config" / "pipeline.toml"
    webhook_bind_host: str = "192.168.122.1"
    webhook_bind_port: int = 8001
    webhook_allow_cidrs: str = "127.0.0.0/8,192.168.121.0/24,192.168.122.0/24"
    # 11-08 사용량(docs/15_usage.md) — /usage 주기 읽기 · 환산 · 한도. 끄면 읽기만 멈추고 /api/usage 집계는 남는다
    usage_enabled: bool = True
    usage_config: Path = REPO / "config" / "usage.toml"

    @field_validator("foreman_webhook_token")
    @classmethod
    def _webhook_long_enough(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and len(v.get_secret_value()) < MIN_TOKEN_LEN:
            raise ValueError(f"토큰은 {MIN_TOKEN_LEN}자 이상이어야 한다")
        return v

    @field_validator("foreman_api_token", "foreman_hook_token")
    @classmethod
    def _long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < MIN_TOKEN_LEN:
            raise ValueError(f"토큰은 {MIN_TOKEN_LEN}자 이상이어야 한다")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
