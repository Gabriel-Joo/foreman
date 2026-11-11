"""브리지 자체 인증. HTTP는 Authorization: Bearer, WS는 연결 직후 첫 메시지(쿼리스트링은 로그에 남아서 쓰지 않는다).

토큰 두 종류(11-11):
- 관리 토큰(`FOREMAN_API_TOKEN`) — 모든 API. `request.state.token_scope = None`
- 프로젝트 토큰(`bridge/scopetoken.py`, `config/tokens.toml` 켜야 받음) — 그 프로젝트 세션 · 방 API만.
  `request.state.token_scope = "<프로젝트>"`. 범위 밖이면 403 + 무엇이 왜 막혔는지(로그에도 — 값은 남기지 않는다)
"""

import hmac
import json
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bridge.config import Settings

_bearer = HTTPBearer(auto_error=False)
log = logging.getLogger("foreman.auth")


def token_ok(given: str | None, expected: str) -> bool:
    if not given:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def _book(request: Request):  # noqa: ANN202
    from bridge.scopetoken import TokenBook, TokenConfig
    b = getattr(request.app.state, "token_book", None)
    if b is None:
        cfg = TokenConfig.load()
        if cfg.error:
            log.error("프로젝트 토큰 설정을 못 읽어 받지 않습니다: %s", cfg.error)
        b = TokenBook(cfg)
        request.app.state.token_book = b
    return b


async def _project_scope(request: Request, given: str) -> str | None:
    """프로젝트 토큰이면 그 프로젝트 이름. 꺼져 있거나 모르는 토큰이면 None."""
    book = _book(request)
    if not book.cfg.enabled:
        return None
    store = getattr(request.app.state, "store", None)
    if store is None:
        return None
    from sqlalchemy import text
    async with store.engine.connect() as c:
        names = [r[0] for r in (await c.execute(text("SELECT name FROM project"))).all()]
    return book.project_of(given, names)


async def _check_scope(request: Request, scope: str) -> str | None:
    from sqlalchemy import text

    from bridge.scopetoken import why_out_of_scope
    engine = request.app.state.store.engine

    async def session_project(sid: int) -> str | None:
        async with engine.connect() as c:
            r = (await c.execute(text(
                "SELECT p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :s"), {"s": sid})).first()
        return r[0] if r else None

    async def repo_of(project: str) -> str | None:
        async with engine.connect() as c:
            r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :n"), {"n": project})).first()
        return r[0] if r else None

    body = None
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            raw = await request.body()          # FastAPI가 이미 읽어 둔 것을 돌려준다
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
    return await why_out_of_scope(scope, request.method, request.url.path, dict(request.query_params), body,
                                  session_project, repo_of)


async def require_api_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    s: Settings = Depends(settings_of),
) -> None:
    given = creds.credentials if creds else None
    if given and token_ok(given, s.foreman_api_token.get_secret_value()):
        request.state.token_scope = None
        return
    scope = None
    if given:
        try:
            scope = await _project_scope(request, given)
        except Exception as e:  # noqa: BLE001 — DB를 못 읽으면 프로젝트 토큰은 받지 않는다(관리 토큰은 그대로)
            log.warning("프로젝트 토큰 확인 실패 %s: %s: %s", request.url.path, type(e).__name__, str(e)[:200])
    if scope is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증 필요", headers={"WWW-Authenticate": "Bearer"})
    try:
        why = await _check_scope(request, scope)
    except Exception as e:  # noqa: BLE001 — 범위를 못 보면 막는다(이유와 함께)
        why = f"프로젝트 토큰({scope})의 범위를 확인하지 못했습니다: {type(e).__name__}"
    if why:
        log.warning("프로젝트 토큰 거절 %s %s: %s", request.method, request.url.path, why)
        raise HTTPException(status.HTTP_403_FORBIDDEN, why)
    request.state.token_scope = scope
