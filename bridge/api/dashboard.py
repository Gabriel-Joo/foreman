"""대시보드 데이터(6단계) — 프로젝트별 세션 스냅샷과 세션의 최근 대화. API 토큰이 필요하다.

화면은 이 스냅샷을 한 번 받고, 그 뒤로는 WS(이벤트 · 턴 · 승인 · 세션 상태)로 고친다. 스냅샷은 몇 초마다 다시 받아
어긋난 것을 맞춘다. 그리는 쪽(static/js/render.js)은 이 모양만 안다 — 테마 렌더러로 바꿔도 여기는 그대로.

상태(README 2.1):
  SUSPENDED  프로세스가 정지(T)
  DORMANT    살아 있는 프로세스가 없다
  ACTIVE     CC가 일하는 중(sessions json status = busy) 또는 열린 턴이 있다
  IDLE       살아 있고 쉬는 중
"""

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import bindparam, text

from bridge.api.auth import require_api_token
from bridge.inject import _status, _tmux_env
from bridge.liveness import live_sessions
from bridge.compactwatch import status as compact_status
from bridge.model_choice import family as model_family
from bridge.model_choice import label as model_label

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


def _started(sessions_dir: Any, pid: int) -> datetime | None:
    """sessions/<pid>.json의 startedAt(ms) — 이 CC 프로세스가 뜬 시각(UTC, tz 없음). 그 전에 띄운 백그라운드는 이미 죽었다."""
    import json
    from pathlib import Path
    try:
        ms = json.loads(Path(sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("startedAt")
    except (OSError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, UTC).replace(tzinfo=None) if isinstance(ms, (int, float)) else None


def background_running(rows: list[tuple[Any, ...]], started: datetime | None) -> list[dict[str, Any]]:
    """bg_start(끝 알림 없는 것) 중 지금 프로세스가 뜬 뒤에 시작한 것만 — [{task, tool, description, since}]."""
    out = []
    for task, tool, desc, ts in rows:
        if started is not None and ts is not None and ts < started:
            continue
        out.append({"task": task, "tool": tool, "description": desc, "since": _iso(ts)})
    return out


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
            "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id) AS last_ts, cs.title, cs.role, cs.custom_title, cs.model "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            # 셸 세션(7단계 터미널 패널, type='shell')은 캐릭터 카드가 아니다
            # 숨긴 세션(0018, 시험 등)은 카드 · 토큰 집계에서 뺀다 — 지우지는 않았다
            "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.cc_session_id IS NOT NULL AND cs.type = 'agent' "
            "AND cs.hidden_at IS NULL"))).all()
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
        # 백그라운드 Bash · Monitor — 시작(bg_start)에 끝(bg_end)이 아직 없는 것. 살아 있는 세션만(11-06)
        live_ids = [r[0] for r in visible if r[1] in live] or [0]
        bgs: dict[int, list[tuple[Any, ...]]] = {}
        for sid_, task, tool, desc, ts in (await c.execute(text(
                "SELECT s.session_id, s.target, s.tool, JSON_UNQUOTE(JSON_EXTRACT(s.payload, '$.description')), s.ts "
                "FROM event s WHERE s.session_id IN (" + ",".join(str(int(i)) for i in live_ids) + ") "
                "AND s.type = 'bg_start' AND s.ts > :cut AND NOT EXISTS (SELECT 1 FROM event e WHERE "
                "e.session_id = s.session_id AND e.type = 'bg_end' AND e.target = s.target) ORDER BY s.ts"),
                {"cut": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)})).all():
            bgs.setdefault(sid_, []).append((task, tool, None if desc in (None, "null") else desc, ts))
        toks ={r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT t.session_id, SUM(m.token_input), SUM(m.token_output), SUM(m.token_cache_read), "
            f"SUM(m.token_cache_creation), SUM(IF(m.created_at >= :today, m.token_output, 0)), "
            f"SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0)) "
            f"FROM message m JOIN turn t ON t.id = m.turn_id WHERE t.session_id IN {in_ids} AND m.subagent_id IS NULL "
            f"GROUP BY t.session_id"), {"today": today})).all()}
        sub_toks = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT session_id, SUM(token_input + token_cache_read + token_cache_creation), SUM(token_output) "
            f"FROM subagent_run WHERE session_id IN {in_ids} GROUP BY session_id"))).all()}
        # 모델별 토큰(11-05) — 서브에이전트 메시지도 띄운 턴에 붙어 있으므로 message만 묶으면 겹치지 않는다
        by_model: dict[int, list[dict[str, Any]]] = {}
        for sid_, model, tin, tout, din, dout in (await c.execute(text(
                f"SELECT t.session_id, m.model, SUM(m.token_input + m.token_cache_read + m.token_cache_creation), "
                f"SUM(m.token_output), SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0)), "
                f"SUM(IF(m.created_at >= :today, m.token_output, 0)) "
                f"FROM message m JOIN turn t ON t.id = m.turn_id WHERE t.session_id IN {in_ids} AND m.model <> '<synthetic>' "
                f"GROUP BY t.session_id, m.model ORDER BY SUM(m.token_output) DESC"), {"today": today})).all():
            by_model.setdefault(sid_, []).append({
                "model": model, "label": model_label(model), "family": model_family(model),
                "input": int(tin or 0), "output": int(tout or 0), "today_input": int(din or 0), "today_output": int(dout or 0)})
        # 압축 알림(11-05) — 세션별 압축 횟수 · 단계(due 2번 · late 4번, notify.toml [compact])
        cmp = await compact_status(c, [r[0] for r in visible], request.app.state.compact_rules)
        # 지금 모델 — 본 대화(서브에이전트 아님)의 마지막 응답. 세션 안에서 /model로 바꾸면 따라간다
        cur_model = {r[0]: r[1] for r in (await c.execute(text(
            f"SELECT t.session_id, m.model FROM message m JOIN turn t ON t.id = m.turn_id JOIN ("
            f"  SELECT t2.session_id, MAX(m2.created_at) mx FROM message m2 JOIN turn t2 ON t2.id = m2.turn_id "
            f"  WHERE t2.session_id IN {in_ids} AND m2.subagent_id IS NULL AND m2.model <> '<synthetic>' GROUP BY t2.session_id"
            f") x ON x.session_id = t.session_id AND x.mx = m.created_at WHERE m.subagent_id IS NULL"))).all()}
        appr = (await c.execute(text(
            "SELECT id, session_id, tool, target, rule, reason, created_at, summary FROM approval WHERE status = 'pending' "
            "ORDER BY id"))).all()
        appr_rows = appr
    projects: dict[str | None, list[dict[str, Any]]] = {}
    ovl = getattr(request.app.state, "overlap", None)     # 겹침 알림(11-06, bridge/overlap.py) — 패널 띠
    for sid, cc, cwd, attached, detached, char, project, last_ts, title, role, custom, model_req in visible:
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
            "title": title, "custom_title": custom, "cc_name": _cc_name(s.sessions_dir, ls.pid) if ls else None, "role": role,
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
            # 턴이 끝나도 도는 일 — 백그라운드 Bash · Monitor. 상태 값은 늘리지 않고(README 3.11) 화면이 "기다림"으로 그린다
            "background": background_running(bgs.get(sid, []), _started(s.sessions_dir, ls.pid) if ls else None)[:10],
            "tokens": {"input": int(tk[0] or 0) + int(tk[2] or 0) + int(tk[3] or 0), "output": int(tk[1] or 0),
                       "today_output": int(tk[4] or 0), "today_input": int(tk[5] or 0),
                       "subagent_input": int(st_[0] or 0), "subagent_output": int(st_[1] or 0),
                       "by_model": by_model.get(sid, [])},
            # 모델 — model: 지금 쓰는 것(마지막 응답), model_req: 띄울 때 고른 것(입양한 세션 · CC 설정이면 null)
            "model": cur_model.get(sid), "model_label": model_label(cur_model.get(sid)),
            "model_family": model_family(cur_model.get(sid)), "model_req": model_req,
            "compact": cmp.get(sid),
            "overlap": ovl.for_session(sid) if ovl else None,
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
                       "created_at": _iso(a[6]), "summary": a[7], "status": "pending"} for a in appr_rows],
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
            "LEFT(t.prompt_text, 12000), "
            "(SELECT JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')) FROM event e WHERE e.turn_id = t.id "
            " AND e.type = 'assistant_msg' AND e.subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.block')) = 'text' "
            " ORDER BY e.id DESC LIMIT 1), "
            "(SELECT COUNT(*) FROM event e WHERE e.turn_id = t.id AND e.type = 'tool_use' AND e.subagent_id IS NULL), "
            "(SELECT COUNT(*) FROM subagent_run sr WHERE sr.spawn_turn_id = t.id) "
            "FROM turn t WHERE t.session_id = :s ORDER BY t.seq DESC LIMIT :n"), {"s": session_id, "n": limit})).all()
        # 마지막 응답 앞의 중간 글(터미널에는 도구 호출 사이사이 보인다 — 11-05 패널 개선). 턴마다 최근 12개, 각 3000자
        mid: dict[int, list[str]] = {}
        queued: dict[int, list[dict[str, Any]]] = {}
        ids = [r[0] for r in turns]
        if ids:
            rows = (await c.execute(text(
                "SELECT turn_id, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE turn_id IN :ids "
                "AND type = 'assistant_msg' AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' "
                "ORDER BY id").bindparams(bindparam("ids", expanding=True)), {"ids": ids})).all()
            for tid, t_ in rows:
                if t_:
                    mid.setdefault(tid, []).append(t_)
            # 작업 중에 보낸 입력 — 새 턴이 되지 않고 대기열로 열린 턴에 끼어든다(queued_command attachment, op=delivered).
            # 전에는 대화 패널이 턴의 첫 프롬프트만 보여서 이 글들이 아예 안 보였다(11-05 사용자 보고)
            qrows = (await c.execute(text(
                "SELECT turn_id, ts, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.prompt')) FROM event WHERE turn_id IN :ids "
                "AND type = 'queued' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.op')) = 'delivered' ORDER BY ts, id"
            ).bindparams(bindparam("ids", expanding=True)), {"ids": ids})).all()
            for tid, ts_, p in qrows:
                if p and p != "null":
                    queued.setdefault(tid, []).append({"ts": _iso(ts_), "text": p})
    return {"session_id": session_id, "turns": [
        {"id": r[0], "seq": r[1], "origin": r[2], "started_at": _iso(r[3]), "ended_at": _iso(r[4]),
         "end_reason": r[5], "duration_ms": r[6], "prompt": r[7], "reply": (r[8] or "")[:20000],
         "mid": [x[:3000] for x in mid.get(r[0], [])[:-1][-12:]],
         "queued": queued.get(r[0], [])[-20:],
         "tools": r[9], "subagents": r[10]} for r in reversed(turns)]}


# ── 11-05 활동 줄 · 도구 본문 — 터미널처럼 "무엇을 읽고 무엇이 나왔나". 본문은 DB에 없다 — 누를 때만 트랜스크립트에서 ──
@router.get("/sessions/{session_id}/activity")
async def activity(session_id: int, request: Request, limit: int = 40) -> dict[str, Any]:
    """최근 도구 호출(메인 + 서브에이전트) — 화면을 연 뒤가 아니라 DB에서. 결과 상태는 같은 tool_use_id의 tool_result."""
    limit = max(1, min(limit, 200))
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT e.id, e.ts, e.tool, e.target, e.subagent_id, e.tool_use_id, "
            "(SELECT r.status FROM event r WHERE r.session_id = e.session_id AND r.type = 'tool_result' "
            " AND r.tool_use_id = e.tool_use_id LIMIT 1) "
            "FROM event e WHERE e.session_id = :s AND e.type = 'tool_use' ORDER BY e.id DESC LIMIT :n"),
            {"s": session_id, "n": limit})).all()
    return {"session_id": session_id, "items": [
        {"id": r[0], "ts": _iso(r[1]), "tool": r[2], "target": (r[3] or "")[:200], "subagent": bool(r[4]),
         "has_body": bool(r[5]), "status": r[6]} for r in reversed(rows)]}


@router.get("/events/{event_id}/detail")
async def event_detail(event_id: int, request: Request) -> dict[str, Any]:
    """도구 호출 하나의 입력 전체 · 결과 본문. 비밀값은 가린다(Masker + URL 자격증명)."""
    from bridge.mask import Masker
    from bridge.terminal import mask_output
    from bridge.transcript.lookup import clip_input, clip_text, find_tool_call
    async with request.app.state.store.engine.connect() as c:
        r = (await c.execute(text(
            "SELECT e.type, e.tool_use_id, e.tool, e.subagent_id, "
            " (SELECT tf.path FROM character_session cs JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
            "  WHERE cs.id = e.session_id), "
            " (SELECT tf.path FROM subagent_run sr JOIN transcript_file tf ON tf.agent_id = sr.agent_id "
            "  WHERE sr.id = e.subagent_id LIMIT 1) "
            "FROM event e WHERE e.id = :i"), {"i": event_id})).first()
    if r is None:
        raise HTTPException(404, "이벤트 없음")
    etype, tuid, tool, sub_id, main_path, sub_path = r
    if etype not in ("tool_use", "tool_result") or not tuid:
        raise HTTPException(400, "도구 호출이 아니다")
    path = sub_path if sub_id else main_path
    if not path or not os.path.exists(path):
        raise HTTPException(410, "트랜스크립트 파일이 없다(지워졌거나 옮겨졌다)")
    t0 = time.monotonic()
    found = await asyncio.to_thread(find_tool_call, path, tuid)
    m = Masker()
    result, n = clip_text(found["result"])
    return {"event_id": event_id, "tool": found["name"] or tool, "tool_use_id": tuid,
            "input": m.deep(clip_input(found["input"])) if found["input"] is not None else None,
            "result": mask_output(m, result) if result is not None else None, "result_chars": n,
            "is_error": found["is_error"], "extra": m.deep(found["extra"]), "other_blocks": found["other_blocks"],
            "found": found["found"], "file": os.path.basename(path), "ms": round((time.monotonic() - t0) * 1000)}
