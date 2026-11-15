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


async def reused_by(c: Any, sid: int, wt_path: str) -> int | None:
    """그 worktree 자리(이름)를 이 세션 뒤에 다른 세션이 쓰는가 — 이름은 다시 쓰인다(foreman · foreman-3 …).
    다시 쓰였으면 이 세션의 worktree는 이미 한 번 지워졌다(합쳤거나 버렸다) — 지금 폴더는 뒤 세션 것."""
    r = (await c.execute(text(
        "SELECT MIN(id) FROM character_session WHERE id > :s AND (cwd = :p OR cwd LIKE :pp)"),
        {"s": sid, "p": wt_path, "pp": wt_path.replace("%", r"\%").replace("_", r"\_") + "/%"})).scalar()
    return int(r) if r else None


async def rest_stale(engine: Any, sid: int, cwd: str | None) -> str | None:
    """쉬게 한 일이 실제로는 끝난 것인가(11-11, 받은 할 일 #17) — 까닭 한 줄, 아니면 None.
    밖에서(git merge --ff-only 등) 합쳤거나, 같은 이름을 뒤 세션이 다시 썼거나, 브랜치가 지워졌으면."""
    repo, name = wt.split(cwd or "")
    if not name:
        return None
    path = str(Path(repo, wt.WT_DIR, name))
    async with engine.connect() as c:
        later = await reused_by(c, sid, path)
    if later:
        return f"같은 작업방 이름({name})을 뒤에 세션 {later}이 다시 썼습니다. 이 세션의 작업방은 이미 지워졌습니다"
    if not Path(path).is_dir():
        return f"작업방 {name}가 없습니다. 이미 합쳤거나 버렸습니다"
    try:
        merged = await wt.in_base(repo, name)
    except Exception:  # noqa: BLE001 — git을 못 읽으면 실제와 다르다고 말하지 않는다
        return None
    if merged is None:
        return f"브랜치 {wt.BRANCH_PREFIX}{name}가 없습니다. 이미 합쳤거나 버렸습니다"
    if merged:
        _, dirty = await wt.git(path, "status", "--porcelain", check=False)
        if not dirty.strip():
            return (f"브랜치 {wt.BRANCH_PREFIX}{name}의 커밋이 모두 원본에 들어 있습니다(밖에서 합쳤거나 합칠 커밋이 없음)"
                    ". 작업방만 남았습니다")
    return None


async def rested(engine: Any, sessions_dir: str | Path, project: str | None = None) -> list[dict[str, Any]]:
    """쉬게 한 일 — 오래된 것부터. worktree 폴더가 남아 있고 세션이 살아 있지 않은 것만.
    밖에서 합쳤거나 이름이 다시 쓰인 것(rest_stale)은 「합치기 기다림」으로 세지 않는다(11-11, 받은 할 일 #17)."""
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
        if await rest_stale(engine, sid, cwd):
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
