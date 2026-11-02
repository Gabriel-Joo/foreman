"""대시보드 데이터(6단계) — 프로젝트별 세션 스냅샷과 세션의 최근 대화. API 토큰이 필요하다.

화면은 이 스냅샷을 한 번 받고, 그 뒤로는 WS(이벤트 · 턴 · 승인 · 세션 상태)로 고친다. 스냅샷은 몇 초마다 다시 받아
어긋난 것을 맞춘다. 그리는 쪽(static/js/render.js)은 이 모양만 안다 — 테마 렌더러로 바꿔도 여기는 그대로.

상태(README 2.1):
  SUSPENDED  프로세스가 정지(T)
  DORMANT    살아 있는 프로세스가 없다
  ACTIVE     CC가 일하는 중(sessions json status = busy) 또는 열린 턴이 있다
  IDLE       살아 있고 쉬는 중
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from bridge.api.auth import require_api_token
from bridge.inject import _status, _tmux_env
from bridge.liveness import live_sessions

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])

PROJECT_ORDER = ["runshoes", "petmint-rag-chatbot", "foreman"]
LABEL = {"runshoes": "런슈즈", "petmint-rag-chatbot": "펫퍼민트", "foreman": "포먼", None: "미분류"}
DORMANT_SHOW_H = 48          # 프로세스가 없는 세션은 이 시간 안에 활동이 있던 것만
KST = timedelta(hours=9)
_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _cc_name(sessions_dir: Any, pid: int) -> str | None:
    """sessions/<pid>.json의 name(CC가 붙이는 짧은 이름, 예: petmint-rag-chatbot-33). .key는 열지 않는다."""
    import json
    from pathlib import Path
    try:
        return json.loads(Path(sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError):
        return None


def invalidate() -> None:
    """세션 상태가 바뀌었다 — 다음 스냅샷은 새로 만든다."""
    _cache["data"] = None


def char_state(proc: str | None, cc_status: str | None, open_turn: bool) -> str:
    """프로세스가 살아 있으면 CC가 직접 적는 status가 기준이다(busy → ACTIVE, 그 밖 → IDLE).
    열린 턴은 status를 모를 때만 본다 — 끝 신호 없이 멈춘 턴 하나가 세션을 몇 시간씩 ACTIVE로 보이게 했다
    (6단계 실측: 펫퍼민트가 프롬프트 · API 요청 뒤 응답도 끝 신호도 없이 10시간, CC status는 idle)."""
    if proc is None:
        return "DORMANT"
    if proc == "T":
        return "SUSPENDED"
    if cc_status is not None:
        return "ACTIVE" if cc_status == "busy" else "IDLE"
    return "ACTIVE" if open_turn else "IDLE"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def _today_utc() -> datetime:
    """한국 시간 오늘 0시를 UTC로(토큰 '오늘' 합계)."""
    now_kst = datetime.now(UTC).replace(tzinfo=None) + KST
    return datetime(now_kst.year, now_kst.month, now_kst.day) - KST


@router.get("/dashboard")
async def dashboard(request: Request) -> dict[str, Any]:
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < 2.0:   # 탭 여러 개 · 잦은 새로고침
        return _cache["data"]
    s = request.app.state.settings
    live = live_sessions(s.sessions_dir)
    cut = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=DORMANT_SHOW_H)
    today = _today_utc()
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT cs.id, cs.cc_session_id, cs.cwd, cs.attached_at, cs.detached_at, ch.name, p.name, "
            "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id) AS last_ts, cs.title, cs.role "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            # 셸 세션(7단계 터미널 패널, type='shell')은 캐릭터 카드가 아니다
            "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.cc_session_id IS NOT NULL AND cs.type = 'agent'"))).all()
        visible = [r for r in rows if (r[1] in live) or (r[7] and r[7] >= cut)]
        ids = [r[0] for r in visible] or [0]
        in_ids = "(" + ",".join(str(int(i)) for i in ids) + ")"
        open_turns = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT session_id, id, origin, started_at, LEFT(prompt_text, 300) FROM turn "
            f"WHERE session_id IN {in_ids} AND ended_at IS NULL"))).all()}
        acts = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT e.session_id, e.tool, e.target, e.ts, e.subagent_id FROM event e JOIN ("
            f"  SELECT session_id, MAX(id) mid FROM event WHERE session_id IN {in_ids} AND type = 'tool_use' "
            f"  AND source = 'transcript' GROUP BY session_id) x ON x.mid = e.id"))).all()}
        subs = {}
        for sid, status, desc in (await c.execute(text(
                f"SELECT session_id, status, description FROM subagent_run WHERE session_id IN {in_ids} "
                f"AND status = 'running'"))).all():
            subs.setdefault(sid, []).append(desc)
        toks = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT t.session_id, SUM(m.token_input), SUM(m.token_output), SUM(m.token_cache_read), "
            f"SUM(m.token_cache_creation), SUM(IF(m.created_at >= :today, m.token_output, 0)), "
            f"SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0)) "
            f"FROM message m JOIN turn t ON t.id = m.turn_id WHERE t.session_id IN {in_ids} AND m.subagent_id IS NULL "
            f"GROUP BY t.session_id"), {"today": today})).all()}
        sub_toks = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT session_id, SUM(token_input + token_cache_read + token_cache_creation), SUM(token_output) "
            f"FROM subagent_run WHERE session_id IN {in_ids} GROUP BY session_id"))).all()}
        appr = (await c.execute(text(
            "SELECT id, session_id, tool, target, rule, reason, created_at FROM approval WHERE status = 'pending' "
            "ORDER BY id"))).all()
        appr_rows = appr
    projects: dict[str | None, list[dict[str, Any]]] = {}
    for sid, cc, cwd, attached, detached, char, project, last_ts, title, role in visible:
        ls = live.get(cc)
        cc_status = _status(s.sessions_dir, ls.pid) if ls else None
        te = _tmux_env(ls.pid) if ls else None
        ot = open_turns.get(sid)
        act = acts.get(sid)
        tk = toks.get(sid) or (0, 0, 0, 0, 0, 0)
        st_ = sub_toks.get(sid) or (0, 0)
        projects.setdefault(project, []).append({
            "id": sid, "cc_session_id": cc, "short": (cc or "")[:8], "character": char, "project": project,
            # 세션을 알아보는 이름: CC가 붙인 제목(ai-title) → 살아 있으면 CC 세션 이름(예: runshoes-50) → 짧은 id.
            # 캐릭터(포먼 등) · 역할(coder 등)은 따로 — 한 캐릭터에 세션 여럿이 붙어 있다(2단계 입양)
            "title": title, "cc_name": _cc_name(s.sessions_dir, ls.pid) if ls else None, "role": role,
            "cwd": cwd, "pid": ls.pid if ls else None, "proc": ls.state if ls else None, "cc_status": cc_status,
            "state": char_state(ls.state if ls else None, cc_status, ot is not None),
            # 열린 턴이 있는데 CC는 일하지 않는다 — 끝 신호 없이 멈춘 턴(숨기지 않고 따로 보인다)
            "stuck_turn": bool(ot is not None and ls and ls.state != "T" and cc_status not in (None, "busy")),
            "injectable": bool(ls and te and ls.state != "T"), "tmux_pane": te[1] if te else None,
            "open_turn": {"id": ot[0], "origin": ot[1], "started_at": _iso(ot[2]), "prompt": ot[3]} if ot else None,
            "activity": {"tool": act[0], "target": (act[1] or "")[:200], "ts": _iso(act[2]),
                         "subagent": act[3] is not None} if act else None,
            "subagents_running": len(subs.get(sid, [])),
            "subagent_descs": [d for d in subs.get(sid, []) if d][:10],
            "tokens": {"input": int(tk[0] or 0) + int(tk[2] or 0) + int(tk[3] or 0), "output": int(tk[1] or 0),
                       "today_output": int(tk[4] or 0), "today_input": int(tk[5] or 0),
                       "subagent_input": int(st_[0] or 0), "subagent_output": int(st_[1] or 0)},
            "last_ts": _iso(last_ts), "attached_at": _iso(attached), "detached_at": _iso(detached),
        })
    order = {"ACTIVE": 0, "SUSPENDED": 1, "IDLE": 2, "DORMANT": 3}
    out_projects = []
    for name in [*PROJECT_ORDER, *sorted(k for k in projects if k and k not in PROJECT_ORDER), None]:
        if name not in projects:
            continue
        ss = sorted(projects[name], key=lambda x: (order[x["state"]], -(datetime.fromisoformat(x["last_ts"][:-1]).timestamp() if x["last_ts"] else 0)))
        out_projects.append({"name": name, "label": LABEL.get(name, name), "sessions": ss})
    data = {
        "generated_at": _iso(datetime.now(UTC).replace(tzinfo=None)),
        "projects": out_projects,
        "approvals": [{"id": a[0], "session_id": a[1], "tool": a[2], "target": a[3], "rule": a[4], "reason": a[5],
                       "created_at": _iso(a[6]), "status": "pending"} for a in appr_rows],
        "hidden_dormant": len(rows) - len(visible),
        "terminal": term.snapshot() if (term := getattr(request.app.state, "terminal", None)) else {"enabled": False},
        # 적재(수집기) 상태 — 막히면 머리 띠(11-03, bridge/ingest_health.py)
        "ingest": mon.snapshot() if (mon := getattr(request.app.state, "ingest_monitor", None)) else None,
    }
    _cache.update(at=time.monotonic(), data=data)
    return data


@router.get("/sessions/{session_id}/conversation")
async def conversation(session_id: int, request: Request, limit: int = 15) -> dict[str, Any]:
    """최근 턴 — 입력(내 프롬프트 · 완료 알림 등)과 그 턴의 마지막 응답. 도구 결과 본문은 DB에 없다(2단계 원칙)."""
    limit = max(1, min(limit, 50))
    async with request.app.state.store.engine.connect() as c:
        if (await c.execute(text("SELECT 1 FROM character_session WHERE id = :s"), {"s": session_id})).first() is None:
            raise HTTPException(404, "세션 없음")
        turns = (await c.execute(text(
            "SELECT t.id, t.seq, t.origin, t.started_at, t.ended_at, t.end_reason, t.duration_ms, "
            "LEFT(t.prompt_text, 4000), "
            "(SELECT JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')) FROM event e WHERE e.turn_id = t.id "
            " AND e.type = 'assistant_msg' AND e.subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.block')) = 'text' "
            " ORDER BY e.id DESC LIMIT 1), "
            "(SELECT COUNT(*) FROM event e WHERE e.turn_id = t.id AND e.type = 'tool_use' AND e.subagent_id IS NULL), "
            "(SELECT COUNT(*) FROM subagent_run sr WHERE sr.spawn_turn_id = t.id) "
            "FROM turn t WHERE t.session_id = :s ORDER BY t.seq DESC LIMIT :n"), {"s": session_id, "n": limit})).all()
    return {"session_id": session_id, "turns": [
        {"id": r[0], "seq": r[1], "origin": r[2], "started_at": _iso(r[3]), "ended_at": _iso(r[4]),
         "end_reason": r[5], "duration_ms": r[6], "prompt": r[7], "reply": (r[8] or "")[:6000],
         "tools": r[9], "subagents": r[10]} for r in reversed(turns)]}
