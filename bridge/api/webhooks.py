"""/webhooks/{jenkins,harbor,argocd} — CI/CD 웹훅(8단계). 웹훅 토큰(FOREMAN_WEBHOOK_TOKEN)이 필요하다.

받는 곳은 두 군데다: 127.0.0.1:8000(브리지, 시험 · 로컬)과 웹훅 전용 포트 192.168.122.1:8001(클러스터가 보낸다).
전용 포트에서는 /webhooks/*만 열린다(main.py 미들웨어). 보낸 곳 IP가 VM 망이 아니면 거절한다 — 리눅스는 어느 인터페이스로
들어온 패킷이든 호스트의 주소면 받으므로(weak host), LAN에서 경로를 잡아 192.168.122.1로 보내는 것을 IP로도 막는다.
토큰은 헤더로만(Authorization: Bearer — Harbor는 "Auth Header" 칸, ArgoCD는 notifications secret). 거절은 이유를 로그에(값은 안 남긴다).
"""

import ipaddress
import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.auth import token_ok

router = APIRouter(prefix="/webhooks")
log = logging.getLogger("foreman.webhooks")


def _allowed(host: str | None, cidrs: str) -> bool:
    try:
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        return host == "testclient"    # starlette TestClient
    return any(ip in ipaddress.ip_network(c.strip(), strict=False) for c in cidrs.split(",") if c.strip())


async def _receive(request: Request, kind: str) -> JSONResponse:
    s = request.app.state.settings
    client = request.client.host if request.client else None
    if not _allowed(client, s.webhook_allow_cidrs):
        log.warning("웹훅 거절 %s %s: 허용 망 밖", client, kind)
        return JSONResponse({"error": "허용되지 않은 곳"}, status_code=403)
    expected = s.foreman_webhook_token.get_secret_value() if s.foreman_webhook_token else None
    if not expected:
        log.warning("웹훅 거절 %s %s: FOREMAN_WEBHOOK_TOKEN이 설정되지 않음", client, kind)
        return JSONResponse({"error": "웹훅 꺼짐"}, status_code=503)
    auth = request.headers.get("authorization", "")
    given = auth[7:] if auth.startswith("Bearer ") else (auth or None)   # Harbor Auth Header는 값 그대로 올 수도 있다
    if not token_ok(given, expected):
        log.warning("웹훅 거절 %s %s: %s", client, kind, "Authorization 없음" if not auth else f"토큰 불일치(길이 {len(given or '')})")
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        body: Any = json.loads(await request.body())
    except ValueError:
        log.warning("웹훅 거절 %s %s: JSON이 아님", client, kind)
        return JSONResponse({"error": "JSON이 아님"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "객체가 아님"}, status_code=400)
    mgr = getattr(request.app.state, "pipeline_mgr", None)
    if mgr is None:
        return JSONResponse({"error": "파이프라인 꺼짐"}, status_code=503)
    try:
        out = await getattr(mgr, f"on_{kind}")(body)
    except Exception as e:  # noqa: BLE001 — 보낸 쪽은 재시도한다. 이유는 로그에
        log.warning("웹훅 처리 실패 %s: %s: %s", kind, type(e).__name__, str(e)[:200])
        return JSONResponse({"error": "처리 실패"}, status_code=500)
    if "ignored" in out:
        log.info("웹훅 %s 건너뜀: %s", kind, out["ignored"])
    return JSONResponse(out, status_code=202)


@router.post("/jenkins")
async def jenkins(request: Request) -> JSONResponse:
    return await _receive(request, "jenkins")


@router.post("/harbor")
async def harbor(request: Request) -> JSONResponse:
    return await _receive(request, "harbor")


@router.post("/argocd")
async def argocd(request: Request) -> JSONResponse:
    return await _receive(request, "argocd")
