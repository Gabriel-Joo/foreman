"""`.venv/bin/python -m bridge` — 1단계 동안은 tmux 세션 foreman-bridge에서 손으로 띄운다(systemd는 6단계 즈음)."""

import logging

import uvicorn

from bridge.config import get_settings
from bridge.main import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx는 INFO에서 요청 URL을 통째로 찍는다 — 텔레그램 URL에는 봇 토큰이 들어 있다(4단계부터 로그에 찍혔다, 7단계에 발견)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    s = get_settings()
    uvicorn.run(create_app(s), host=s.bind_host, port=s.bind_port, proxy_headers=False, log_level="info")


if __name__ == "__main__":
    main()
