"""/api/approvals — 승인 대기 목록과 브라우저 결정(5단계). API 토큰이 필요하다."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from bridge.api.auth import require_api_token

router = APIRouter(prefix="/api/approvals", dependencies=[Depends(require_api_token)])
log = logging.getLogger("foreman.approval")


class DecideIn(BaseModel):
    decision: str = Field(pattern="^(allow|deny)$")
    message: str | None = Field(default=None, max_length=255)   # 거부 이유 — 모델에게 간다


@router.get("")
async def list_approvals(request: Request, status: str = "pending", limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 500))
    where = "" if status == "all" else "WHERE a.status = :st"
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT a.id, a.status, a.tool, a.target, a.rule, a.reason, a.decided_by, a.message, a.terminal_decision, "
            "a.created_at, a.decided_at, a.session_id, p.name FROM approval a "
            "LEFT JOIN character_session cs ON cs.id = a.session_id LEFT JOIN `character` ch ON ch.id = cs.character_id "
            f"LEFT JOIN project p ON p.id = ch.project_id {where} ORDER BY a.id DESC LIMIT :n"),
            {"st": status, "n": limit})).all()
    return [{"id": r[0], "status": r[1], "tool": r[2], "target": r[3], "rule": r[4], "reason": r[5],
             "decided_by": r[6], "message": r[7], "terminal_decision": r[8],
             "created_at": r[9].isoformat() + "Z" if r[9] else None,
             "decided_at": r[10].isoformat() + "Z" if r[10] else None, "session_id": r[11], "project": r[12]}
            for r in rows]


@router.post("/{approval_id}")
async def decide(approval_id: int, body: DecideIn, request: Request) -> dict[str, Any]:
    mgr = getattr(request.app.state, "approvals", None)
    if mgr is None:
        raise HTTPException(503, "승인 기능이 꺼져 있다")
    r = mgr.decide(approval_id, body.decision, body.message)
    if r == "gone":
        # 이미 터미널에서 답했거나, 시간이 지났거나, 브리지가 다시 떴다 — 이유를 남긴다
        log.warning("브라우저 결정 거절 #%d(%s): 이미 결정됐거나 기다리는 연결이 없다", approval_id, body.decision)
        raise HTTPException(409, "이미 결정됐거나(터미널 · 시간 초과) 기다리는 요청이 없다")
    log.warning("브라우저 결정 #%d: %s%s", approval_id, body.decision, f" — {body.message}" if body.message else "")
    return {"id": approval_id, "decision": body.decision}
