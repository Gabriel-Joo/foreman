"""브리지 자체 인증. HTTP는 Authorization: Bearer, WS는 연결 직후 첫 메시지(쿼리스트링은 로그에 남아서 쓰지 않는다)."""

import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bridge.config import Settings

_bearer = HTTPBearer(auto_error=False)


def token_ok(given: str | None, expected: str) -> bool:
    if not given:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def require_api_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    s: Settings = Depends(settings_of),
) -> None:
    if creds is None or not token_ok(creds.credentials, s.foreman_api_token.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증 필요", headers={"WWW-Authenticate": "Bearer"})
