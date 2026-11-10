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


def outcome(status: str, by: str | None, terminal: str | None, ran: int | None) -> str:
    """승인 하나의 결과 — approved(사람이 허락) · denied(사람이 거부) · unknown.
    시간 초과 · 브리지 재시작 뒤에도 터미널 승인 창은 남아 있어 사람이 나중에 답한다 — 그 도구가 실행됐는지(ran:
    tool_result가 오류 없이 왔으면 1, 오류면 0, 결과 없음 None)로 거꾸로 안다. 오류는 거부와 실행 실패를 가르지 못한다."""
    if status == "allowed" or (status == "terminal" and terminal in (None, "accept", "allow")):
        return "approved"
    if status == "denied" or (status == "terminal" and terminal in ("reject", "deny")):
        return "denied"
    if ran == 1:
        return "approved"
    if ran == 0:
        return "denied"
    return "unknown"


@router.get("/history")
async def history(request: Request, days: int = 1) -> dict[str, Any]:
    """승인 이력(11-03 사용자 요청) — 무엇이 몇 번 걸렸고, 사람이 다 승인했는지. 늘 Yes만 누르는 규칙은 손볼 후보다.
    days=1이면 오늘(KST 0시부터). observe 프로젝트의 '걸렸을 것'(창을 띄우지 않은 ask)도 따로 센다."""
    days = max(1, min(days, 90))
    async with request.app.state.store.engine.connect() as c:
        since = (await c.execute(text(
            "SELECT CONVERT_TZ(DATE(CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '+09:00')) - INTERVAL :d DAY, '+09:00', '+00:00')"),
            {"d": days - 1})).scalar()
        rows = (await c.execute(text(
            "SELECT a.id, a.created_at, a.rule, a.status, a.decided_by, a.terminal_decision, a.summary, a.target, a.tool, "
            "p.name, (SELECT IF(JSON_EXTRACT(ev.payload, '$.is_error') = TRUE, 0, 1) FROM event ev "
            "WHERE ev.tool_use_id = a.tool_use_id AND ev.type = 'tool_result' LIMIT 1), a.message, a.session_id "
            "FROM approval a LEFT JOIN character_session cs ON cs.id = a.session_id "
            "LEFT JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
            "WHERE a.created_at >= :t ORDER BY a.id DESC"), {"t": since})).all()
        observe = (await c.execute(text(
            "SELECT COALESCE(p.name, '미분류'), JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.rule')), COUNT(*) FROM event e "
            "LEFT JOIN character_session cs ON cs.id = e.session_id LEFT JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id WHERE e.type = 'approval_req' AND e.ts >= :t "
            "AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.decision')) = 'ask' "
            "AND JSON_EXTRACT(e.payload, '$.enforced') = FALSE GROUP BY 1, 2 ORDER BY 3 DESC"), {"t": since})).all()
    items, by_rule = [], {}
    for r in rows:
        o = outcome(r[3], r[4], r[5], r[10])
        items.append({"id": r[0], "at": r[1].isoformat() + "Z" if r[1] else None, "rule": r[2], "status": r[3],
                      "by": r[4], "outcome": o, "summary": r[6] or (r[7] or "")[:160], "tool": r[8], "project": r[9],
                      "message": r[11], "session_id": r[12]})
        b = by_rule.setdefault(r[2], {"rule": r[2], "n": 0, "approved": 0, "denied": 0, "unknown": 0})
        b["n"] += 1
        b[o] += 1
    rules = sorted(by_rule.values(), key=lambda x: -x["n"])
    for b in rules:
        # 3번 넘게 걸렸는데 한 번도 거부하지 않았다 — 묻는 게 의미가 없을 수 있다(규칙 손볼 후보)
        b["always_yes"] = b["n"] >= 3 and b["denied"] == 0 and b["approved"] >= b["n"] - b["unknown"] and b["approved"] > 0
    total = {k: sum(b[k] for b in rules) for k in ("n", "approved", "denied", "unknown")}
    return {"days": days, "since": since.isoformat() + "Z" if since else None, "total": total, "by_rule": rules,
            "items": items[:100],
            "observe": [{"project": o[0], "rule": o[1], "n": int(o[2])} for o in observe]}


class AnswerIn(BaseModel):
    picks: dict[str, list[str]]       # 질문 글 → 고른 선택지 이름들(AskUserQuestion, 11-09)
    note: str | None = Field(default=None, max_length=4000)   # 답과 함께 보내는 글(11-10) — 글만 보내도 된다


@router.post("/{approval_id}/answer")
async def answer(approval_id: int, body: AnswerIn, request: Request) -> dict[str, Any]:
    """패널에서 세션의 질문에 답한다 — 고른 답이 그 세션에 바로 들어간다(터미널 질문 창을 건너뛴다)."""
    mgr = getattr(request.app.state, "approvals", None)
    if mgr is None:
        raise HTTPException(503, "승인 기능이 꺼져 있습니다")
    r = mgr.answer(approval_id, body.picks, body.note)
    if r == "gone":
        raise HTTPException(409, "이미 답했거나(터미널 · 시간 초과) 기다리는 질문이 없습니다")
    if r == "bad":
        raise HTTPException(422, "모든 질문에 선택지를 하나씩 고르거나 글을 적어 주세요(여러 개 고름이 아닌 질문은 하나만)")
    log.warning("화면에서 질문에 답함 #%d", approval_id)
    return {"id": approval_id, "decision": "answer"}


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
