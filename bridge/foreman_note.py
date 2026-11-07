"""디스패처 노트(11-08, docs/14_dispatcher_note_wake.md) — 프로젝트마다 크기를 정한 기록. 디스패처를 부를 때마다 상황 묶음에 넣는다.

상주 세션은 대화가 쌓여 압축되고, 압축 요약에 무엇이 남을지 고를 수 없다. 노트는 "무엇이 남을지 사람이 고르는 압축 요약"이다.
- 쌓는 것: thread(진행 중인 일 줄기) · decision(사람이 정한 판단). 지난 디스패치와 사람이 고친 칸은 dispatch 표에서 바로 읽는다
- 쌓지 않는 것: 구조 · 명령 — CC 메모리 · CLAUDE.md · docs에 있고 새 세션이 스스로 읽는다. 사본은 원본이 바뀌면 조용히 낡는다
- 줄마다 출처와 확인 시각. 확인 뒤 바뀐 것(그 세션의 활동 · 커밋)을 기계로 붙여 낡은 줄이 사실처럼 보이지 않게 한다
- 상한 TOKEN_CAP(2k). 넘친 줄은 지우지 않고 접는다 — 묶음에 안 들어가고, 화면에 "접힘 N줄"로 보인다
- 고치기는 디스패처가 계획(note_updates)에 제안하고, 사람이 [시작]을 누를 때 같이 반영한다
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

TOKEN_CAP = 2000
BODY_MAX = 300
KINDS = {"thread": "진행 중인 일", "decision": "사람이 정한 판단"}
OPS = ("add", "update", "retire", "touch")
REPO_ROOT = Path(__file__).resolve().parent.parent
# 사람이 고친 칸으로 볼 것(디스패처가 고르는 칸) — 이유 · 경고 · 확신도는 사람이 고치는 칸이 아니다
EDIT_FIELDS = ("project", "mode", "role", "read_only", "summary_id", "attach_session", "title", "worktree", "model", "first_prompt")
SOURCE_RE = re.compile(r"^(세션 \d+|dispatch #\d+|(log|docs)/[\w.\-/]+\.md|커밋 [0-9a-f]{7,40})$")


def est_tokens(s: str) -> int:
    """대략의 토큰 수 — 한글 한 자 ≈ 1토큰, 나머지 ≈ 3.5자에 1토큰(실측 없이 넉넉히)."""
    hangul = sum(1 for ch in s if "가" <= ch <= "힣")
    return hangul + round((len(s) - hangul) / 3.5)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def changed_fields(plan: dict[str, Any] | None, edited: dict[str, Any] | None) -> list[str]:
    """디스패처의 계획 → 사람이 시작한 계획에서 바뀐 칸(첫 글은 '첫 글 고침'으로만)."""
    if not plan or not edited:
        return []
    out = []
    for k in EDIT_FIELDS:
        a, b = plan.get(k), edited.get(k)
        if (a or None) == (b or None):
            continue
        if k == "first_prompt":
            out.append("첫 글 고침")
        else:
            out.append(f"{k} {json.dumps(a, ensure_ascii=False)}→{json.dumps(b, ensure_ascii=False)}")
    return out


async def active(c: Any, project: str) -> list[dict[str, Any]]:
    rows = (await c.execute(text(
        "SELECT id, kind, body, source, refs, checked_at, created_at FROM foreman_note "
        "WHERE project = :p AND retired_at IS NULL ORDER BY checked_at DESC, id DESC"), {"p": project})).all()
    return [{"id": r[0], "kind": r[1], "body": r[2], "source": r[3], "refs": json.loads(r[4]) if r[4] else {},
             "checked_at": r[5], "created_at": r[6]} for r in rows]


async def drift(c: Any, note: dict[str, Any], head: str | None, git: Any = None, repo: str | None = None) -> list[str]:
    """확인 뒤 바뀐 것 — 그 줄이 가리키는 세션에 뒤 활동이 있거나 HEAD가 움직였거나 출처 파일이 없어졌으면 한 마디씩."""
    out = []
    refs = note.get("refs") or {}
    at = note["checked_at"]
    sids = [int(s) for s in (refs.get("sessions") or []) if str(s).isdigit()]
    if sids:
        rows = (await c.execute(text(
            "SELECT e.session_id, MAX(e.ts) FROM event e WHERE e.session_id IN :s GROUP BY e.session_id").bindparams(
                bindparam("s", expanding=True)), {"s": sids})).all()
        newer = [str(sid) for sid, ts in rows if ts and ts > at]
        if newer:
            out.append(f"확인 뒤 세션 {', '.join(newer)}에 활동 있음")
    if head and refs.get("head") and refs["head"] != head and git and repo:
        try:
            n = (await git(repo, "rev-list", "--count", f"{refs['head']}..{head}")).strip()
            if n and n != "0":
                out.append(f"확인 뒤 커밋 {n}개")
        except Exception:  # noqa: BLE001 — 옛 HEAD가 없어졌으면(리베이스) 그냥 "움직임"
            out.append("확인 뒤 HEAD가 바뀜")
    src = note.get("source") or ""
    if re.match(r"^(log|docs)/", src) and not (REPO_ROOT / src).exists():
        out.append("출처 파일이 없음")
    return out


async def render(c: Any, project: str, head: str | None = None, git: Any = None, repo: str | None = None,
                 cap: int = TOKEN_CAP) -> dict[str, Any]:
    """노트 → 상황 묶음 글. 진행 중인 일 먼저, 최근 확인한 것부터 상한까지. 넘친 줄은 접는다(지우지 않는다)."""
    notes = await active(c, project)
    notes.sort(key=lambda n: (n["kind"] != "thread", -n["checked_at"].timestamp()))
    lines, used, folded = [], 0, []
    for n in notes:
        d = await drift(c, n, head, git, repo)
        n["drift"] = d
        ln = (f"  - [노트 {n['id']} · {KINDS.get(n['kind'], n['kind'])}] {n['body']} "
              f"(출처 {n['source']}, 확인 {n['checked_at']:%m-%d %H:%M} UTC{' — ⚠ ' + ' · '.join(d) if d else ''})")
        t = est_tokens(ln)
        if used + t > cap:
            folded.append(n)
            n["folded"] = True
            continue
        n["folded"] = False
        used += t
        lines.append(ln)
    return {"notes": notes, "text": "\n".join(lines), "tokens": used, "folded": len(folded), "cap": cap}


async def recent_dispatches(c: Any, project: str, limit: int = 5) -> list[str]:
    """지난 디스패치와 사람이 고친 칸 — 디스패처가 같은 실수를 되풀이하지 않게(새로 저장하지 않고 dispatch 표에서)."""
    rows = (await c.execute(text(
        "SELECT id, origin, created_at, LEFT(request, 160), status, plan, edited FROM dispatch "
        "WHERE project = :p AND status IN ('started', 'discarded') ORDER BY id DESC LIMIT :n"), {"p": project, "n": limit})).all()
    out = []
    for did, origin, at, req, status, plan, edited in rows:
        p = json.loads(plan) if plan else {}
        e = json.loads(edited) if edited else None
        ch = changed_fields(p, e)
        what = f"{p.get('mode')} · {p.get('role')} · \"{(p.get('title') or '')[:40]}\""
        res = ("시작함" + (f", 사람이 고침: {'; '.join(ch)[:240]}" if ch else ", 고친 것 없음")) if status == "started" else "사람이 버림"
        out.append(f"  - dispatch #{did} {at:%m-%d} {'[자동] ' if origin == 'wake' else ''}요청 \"{re.sub(r'\s+', ' ', req or '')}\" → {what} → {res}")
    return out


async def check_ops(c: Any, project: str | None, ops: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """디스패처가 제안한 노트 고치기를 사실과 맞춘다. 모양이 틀리거나 남의 프로젝트 줄이면 빼고 경고."""
    warn: list[str] = []
    if not isinstance(ops, list) or not project:
        return [], ([] if not ops else ["노트 고치기 제안을 읽지 못했습니다(프로젝트가 정해지지 않음)"])
    mine = {n["id"]: n for n in await active(c, project)}
    out = []
    for o in ops[:8]:
        if not isinstance(o, dict) or o.get("op") not in OPS:
            warn.append(f"노트 제안 하나를 뺐습니다(모르는 모양: {str(o)[:60]})")
            continue
        op = {"op": o["op"], "on": o.get("on", True) is not False}
        if op["op"] in ("update", "retire", "touch"):
            try:
                nid = int(o.get("id"))
            except (TypeError, ValueError):
                nid = None
            if nid not in mine:
                warn.append(f"노트 {o.get('id')}은(는) 이 프로젝트의 지금 노트가 아닙니다 — 제안을 뺐습니다")
                continue
            op["id"] = nid
            op["was"] = mine[nid]["body"]
            op["kind"] = mine[nid]["kind"]
        if op["op"] in ("add", "update"):
            kind = o.get("kind") or op.get("kind")
            body = re.sub(r"\s+", " ", str(o.get("body") or "")).strip()
            if kind not in KINDS or not body:
                warn.append("노트 제안 하나를 뺐습니다(종류 · 내용이 비었음)")
                continue
            if len(body) > BODY_MAX:
                body = body[:BODY_MAX - 1] + "…"
                warn.append(f"노트 제안이 {BODY_MAX}자를 넘어 잘랐습니다")
            src = str(o.get("source") or "").strip()
            if not SOURCE_RE.match(src):
                warn.append(f"노트 제안의 출처 {src!r}를 알아볼 수 없어 '이번 요청'으로 바꿨습니다")
                src = ""                        # 시작할 때 "dispatch #<이번>"으로 채운다
            elif re.match(r"^(log|docs)/", src) and not (REPO_ROOT / src).exists():
                warn.append(f"노트 출처 파일 {src}이(가) 없습니다")
            op.update(kind=kind, body=body, source=src)
        if op["op"] == "retire":
            op["why"] = str(o.get("why") or "")[:200]
        out.append(op)
    return out, warn


async def apply(c: Any, project: str, ops: list[dict[str, Any]], dispatch_id: int, session_id: int | None,
                head: str | None) -> list[int]:
    """사람이 [시작]을 누를 때 — 켠 제안만 반영한다(같은 트랜잭션). 진행 중인 일 줄에는 이번에 띄운 세션을 붙인다."""
    now, touched = _now(), []
    mine = {n["id"]: n for n in await active(c, project)}
    for o in ops:
        if not o.get("on", True):
            continue
        src = o.get("source") or f"dispatch #{dispatch_id}"
        if o["op"] == "touch" and o["id"] in mine:
            refs = dict(mine[o["id"]]["refs"])
            if head:
                refs["head"] = head
            await c.execute(text("UPDATE foreman_note SET checked_at = :t, refs = :r, dispatch_id = :d WHERE id = :i"),
                            {"t": now, "r": json.dumps(refs), "d": dispatch_id, "i": o["id"]})
            touched.append(o["id"])
        elif o["op"] == "retire" and o["id"] in mine:
            await c.execute(text("UPDATE foreman_note SET retired_at = :t, dispatch_id = :d WHERE id = :i"),
                            {"t": now, "d": dispatch_id, "i": o["id"]})
            touched.append(o["id"])
        elif o["op"] in ("add", "update"):
            refs = dict(mine[o["id"]]["refs"]) if o["op"] == "update" and o.get("id") in mine else {}
            if o["kind"] == "thread" and session_id:
                refs["sessions"] = sorted({*(int(s) for s in refs.get("sessions") or []), int(session_id)})[-6:]
            if head:
                refs["head"] = head
            r = await c.execute(text(
                "INSERT INTO foreman_note (project, kind, body, source, refs, checked_at, dispatch_id) VALUES (:p, :k, :b, :s, :r, :t, :d)"),
                {"p": project, "k": o["kind"], "b": o["body"], "s": src, "r": json.dumps(refs), "t": now, "d": dispatch_id})
            touched.append(r.lastrowid)
            if o["op"] == "update" and o.get("id") in mine:
                await c.execute(text("UPDATE foreman_note SET retired_at = :t, replaced_by = :n, dispatch_id = :d WHERE id = :i"),
                                {"t": now, "n": r.lastrowid, "d": dispatch_id, "i": o["id"]})
    return touched


async def retire_by_hand(c: Any, note_id: int) -> bool:
    """화면에서 사람이 내린다(디스패처 제안 없이) — 사람이 고치는 것은 바로 반영."""
    r = await c.execute(text("UPDATE foreman_note SET retired_at = :t WHERE id = :i AND retired_at IS NULL"),
                        {"t": _now(), "i": note_id})
    return bool(r.rowcount)
