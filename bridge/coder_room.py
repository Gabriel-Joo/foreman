"""코더 상주(11-09, log/coder_resident_20261109.md) — 방마다 늘 있는 코더의 "맡길 일 N" 중 DB에서 세는 것. LLM 없음.

- 받은 할 일 — 머리줄 [＋ 할 일]에서 "코더에게"로 받은 것 중 새로(bridge/scribe_room.py 받는 함, 0028 assignee)
- 쉬게 한 일 — [쉬게 하기]로 세션만 끝내고 worktree를 남긴 것(session_action 'rest'). 합치거나 버리기 전까지, 다시 살아나지 않은 것
나머지 신호(파이프라인 실패 · 빌드 알림 없음 · 승인 대기 · 권한 거부)는 화면이 이미 받는 값(대시보드 · 파이프라인 스냅숏)으로 센다 —
새로 판정하지 않는다(bridge/static/js/coder.js coderJobs).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge import scribe_room as sr
from bridge import worktree as wt
from bridge.handoff import REST_ACT
from bridge.liveness import live_sessions


async def rested(engine: Any, sessions_dir: str | Path, project: str | None = None) -> list[dict[str, Any]]:
    """쉬게 한 일 — 오래된 것부터. worktree 폴더가 남아 있고 세션이 살아 있지 않은 것만."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT cs.id, cs.cc_session_id, cs.cwd, COALESCE(cs.custom_title, cs.title), p.name, MAX(sa.created_at) "
            "FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE sa.action = :a AND sa.ok AND cs.hidden_at IS NULL " + ("AND p.name = :p " if project else "")
            + "AND NOT EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = cs.id AND m.action IN ('wt-merge', 'wt-discard') AND m.ok) "
            "GROUP BY cs.id, cs.cc_session_id, cs.cwd, cs.custom_title, cs.title, p.name ORDER BY MAX(sa.created_at)"),
            {"a": REST_ACT, "p": project})).all()
    live = live_sessions(sessions_dir)
    now = datetime.now(UTC).replace(tzinfo=None)
    out = []
    for sid, cc, cwd, title, proj, at in rows:
        repo, name = wt.split(cwd or "")
        if not name or not Path(repo, wt.WT_DIR, name).is_dir() or (cc and cc in live):
            continue
        out.append({"session_id": sid, "title": title or f"세션 {sid}", "project": proj, "branch": wt.BRANCH_PREFIX + name,
                    "rested_at": at.isoformat() + "Z", "days": (now - at).days})
    return out


async def todo(engine: Any, sessions_dir: str | Path) -> dict[str, dict[str, Any]]:
    """프로젝트마다 {inbox: [코더 몫 새로], rested: [쉬게 한 일]} — 화면이 1분마다 부른다."""
    async with engine.connect() as c:
        names = [r[0] for r in (await c.execute(text("SELECT name FROM project"))).all()]
    rs = await rested(engine, sessions_dir)
    out: dict[str, dict[str, Any]] = {}
    for name in names:
        inbox = await sr.inbox_new(engine, name, "coder")
        out[name] = {"inbox": [{"id": x["id"], "body": x["body"], "created_at": x["created_at"].isoformat() + "Z"} for x in inbox],
                     "rested": [r for r in rs if r["project"] == name]}
    return out
