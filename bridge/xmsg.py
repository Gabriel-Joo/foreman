"""세션 간 메시지 읽음(11-09 사용자 — 보낸 쪽은 받는 쪽이 읽었는지 모른다).

보낸 쪽: `SendMessage {to, message}` 도구 호출(event tool_use, payload.input.message).
받는 쪽 트랜스크립트(실측 11-09, 펫퍼민트 ↔ FOREMAN):
  queue-operation enqueue  `<cross-session-message from=… from-name="보낸 세션 이름" …>\n본문`  — 도착
  그다음 dequeue(쉬던 세션이 프롬프트로 가져감) 또는 delivered · remove(작업 중에 끼어들어 읽음)    — 읽음
적재기가 이 줄들을 event type 'queued'(payload.op)로 넣는다 — 그것으로 맞춘다. 본문 앞부분으로 짝짓는다(이름 풀기 없이).
"""

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

ARRIVE_WINDOW = timedelta(minutes=10)     # 보낸 뒤 이 안에 도착 줄이 없으면 "도착 기록 없음"
_HEAD = re.compile(r"^\s*<cross-session-message\b[^>]*>\s*", re.S)
# SendMessage는 서브에이전트를 이어 부를 때도 쓴다(to = 에이전트 id, 실측 런슈즈 11-09 "a96255028a3559965") — 세션 간 메시지가 아니다
_AGENT_ID = re.compile(r"^a?[0-9a-f]{12,}$")


def is_session_target(to: str | None) -> bool:
    return bool(to) and not _AGENT_ID.match(to or "")


def body_of(content: str | None) -> str:
    """대기열 줄 글 → 메시지 본문(머리 태그 · 닫는 태그를 뗀다)."""
    s = _HEAD.sub("", content or "", count=1)
    return re.sub(r"\s*</cross-session-message>\s*$", "", s)


def key_of(s: str | None) -> str:
    """짝짓기 열쇠 — 공백을 하나로, 앞 60자."""
    return re.sub(r"\s+", " ", (s or "").strip())[:60]


def label_of(project: str | None, title: Any, role: str | None, worktree_path: str | None) -> str:
    """받는 쪽 이름 — 원본 폴더의 관리자면 「<프로젝트> 관리자」(11-11 프로젝트별 관리자 주소, bridge/managers.py)."""
    if role == "manager" and not worktree_path:
        return f"{project or '?'} 관리자 · {title}"
    return f"{project or '?'} · {title}"


def pick(send_ts: datetime, msg: str, enqueues: list[tuple], consumes: dict[int, list[tuple]]) -> dict[str, Any]:
    """보낸 것 하나의 상태. enqueues = [(event_id, session_id, ts, content)], consumes = 세션 → [(ts, op, content)] 시각순."""
    k = key_of(msg)
    if not k:
        return {}
    hit = next((e for e in enqueues if send_ts - timedelta(seconds=5) <= e[2] <= send_ts + ARRIVE_WINDOW
                and key_of(body_of(e[3])) == k), None)
    if hit is None:
        return {"arrived_at": None}
    _, sid, at, _ = hit
    out: dict[str, Any] = {"to_session": sid, "arrived_at": at, "read_at": None, "how": None}
    for ts, op, content in consumes.get(sid, []):
        if ts < at:
            continue
        if op == "dequeue" or key_of(body_of(content)) == k:
            out["read_at"], out["how"] = ts, ("prompt" if op == "dequeue" else "mid_turn")
            break
    return out


async def statuses(c: Any, sends: list[tuple[int, datetime, str]]) -> dict[int, dict[str, Any]]:
    """[(보낸 event id, 시각, 본문)] → event id → {to_session, to_label, arrived_at, read_at, how}."""
    if not sends:
        return {}
    lo = min(s[1] for s in sends) - timedelta(seconds=5)
    hi = max(s[1] for s in sends) + ARRIVE_WINDOW
    enq = [tuple(r) for r in (await c.execute(text(
        "SELECT id, session_id, ts, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.content')) FROM event "
        "WHERE type = 'queued' AND ts BETWEEN :a AND :b AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.op')) = 'enqueue' "
        "AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.content')) LIKE '%cross-session-message%' ORDER BY ts"),
        {"a": lo, "b": hi})).all()]
    consumes: dict[int, list[tuple]] = {}
    sids = sorted({e[1] for e in enq})
    if sids:
        in_ids = "(" + ",".join(str(int(i)) for i in sids) + ")"
        for sid, ts, op, content in (await c.execute(text(
                f"SELECT session_id, ts, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.op')), "
                f"COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.content')), JSON_UNQUOTE(JSON_EXTRACT(payload, '$.prompt'))) "
                f"FROM event WHERE session_id IN {in_ids} AND type = 'queued' AND ts >= :a "
                f"AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.op')) IN ('dequeue', 'delivered', 'remove') ORDER BY ts"),
                {"a": lo})).all():
            consumes.setdefault(sid, []).append((ts, op, content))
    labels: dict[int, str] = {}
    if sids:
        for sid, title, proj, role, wt in (await c.execute(text(
                f"SELECT cs.id, COALESCE(cs.custom_title, cs.title), p.name, cs.role, cs.worktree_path FROM character_session cs "
                f"JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                f"WHERE cs.id IN {in_ids}"))).all():
            labels[sid] = label_of(proj, title or sid, role, wt)
    out = {}
    for eid, ts, msg in sends:
        st = pick(ts, msg, enq, consumes)
        if st.get("to_session"):
            st["to_label"] = labels.get(st["to_session"])
        out[eid] = st
    return out
