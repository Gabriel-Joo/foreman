"""디스패처 노트(11-08, docs/14_dispatcher_note_wake.md) — 프로젝트마다 크기를 정한 기록. 디스패처를 부를 때마다 상황 묶음에 넣는다.

상주 세션은 대화가 쌓여 압축되고, 압축 요약에 무엇이 남을지 고를 수 없다. 노트는 "무엇이 남을지 사람이 고르는 압축 요약"이다.
- 쌓는 것: 진행 중인 일(thread) 하나뿐(11-13 사용자 — 화면 · 묶음 이름도 「진행 중인 일」). 지난 디스패치와 사람이 고친 칸은 dispatch 표에서 바로 읽는다
- 쌓지 않는 것: 구조 · 명령 · 규칙 · 금지 · 설계 결정 — CLAUDE.md · docs · CC 메모리에 있고 새 세션이 스스로 읽는다. 사본은 원본이 바뀌면
  조용히 낡는다. 옛 「사람이 정한 판단(decision)」 칸은 11-13에 없앴다 — 남은 decision 줄은 읽지 않고(active), 새로 쌓는 제안은 뺀다(check_ops)
- 줄마다 출처와 확인 시각. 확인 뒤 바뀐 것(그 세션의 활동)을 기계로 붙여 낡은 줄이 사실처럼 보이지 않게 한다
- 상한 TOKEN_CAP(2k). 넘친 줄은 지우지 않고 접는다 — 묶음에 안 들어가고, 화면에 "접힘 N줄"로 보인다
- 고치기는 디스패처가 계획(note_updates)에 제안하고, 사람이 [시작]을 누를 때 같이 반영한다
"""

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from bridge import worktree as wt

TOKEN_CAP = 2000
BODY_MAX = 300
KINDS = {"thread": "진행 중인 일"}
# 11-13 없앤 칸 — 교장이 그래도 제안하면 빼고 계획 카드에 이 말로 시작하는 경고(「노트 」로 시작하는 글은 카드가 숨긴다)
DROPPED_WARN = "규칙 · 판단 제안을 뺐습니다"
OPS = ("add", "update", "retire", "touch")
REPO_ROOT = Path(__file__).resolve().parent.parent
# 사람이 고친 칸으로 볼 것(디스패처가 고르는 칸) — 이유 · 경고 · 확신도는 사람이 고치는 칸이 아니다
EDIT_FIELDS = ("project", "mode", "role", "read_only", "summary_id", "attach_session", "title", "worktree", "model", "first_prompt")
SOURCE_RE = re.compile(r"^(세션 \d+|dispatch #\d+|(log|docs)/[\w.\-/]+\.md|커밋 [0-9a-f]{7,40})$")


@dataclass
class NoteRules:
    """끝난 「진행 중인 일」 줄 다루기(11-13, log/note_auto_retire_20261113.md).
    - stale_days · stale_commits: 기계로 끝남을 못 가르는 thread 줄을 「낡음 — 확인 필요」로 보이는 문턱(마지막 확인 뒤).
      FOREMAN은 하루 커밋이 100개 남짓(11-10~13 실측)이라 커밋 수는 프로젝트마다 속도가 달라 날수를 주로 · 커밋은 넉넉히
    - manager_spawn_done: 「관리자 띄우기」 줄 — 붙은 세션이 살아 있는 관리자이고 그 줄의 dispatch가 그 관리자를 띄웠고 첫 턴이
      끝났으면 끝으로 본다. 띄운 계획의 첫 글에 다른 일이 들었는지는 기계로 못 가른다 — 켤지는 사람이 정한다(기본 끔)"""
    stale_days: float = 3.0
    stale_commits: int = 150
    manager_spawn_done: bool = False


def load_rules(path: str | Path) -> NoteRules:
    """config/wake.toml의 [note] 칸(없으면 코드 기본값). 읽지 못해도 기본값으로 돈다."""
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("note") or {}
    except (OSError, tomllib.TOMLDecodeError):
        raw = {}
    d = NoteRules()
    return NoteRules(stale_days=float(raw.get("stale_days", d.stale_days)),
                     stale_commits=int(raw.get("stale_commits", d.stale_commits)),
                     manager_spawn_done=bool(raw.get("manager_spawn_done", d.manager_spawn_done)))


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
    """지금 진행 중인 일 줄. 11-13 전 decision 줄은 DB에 남아 있어도 읽지 않는다 — 묶음 · 패널 · 제안 맞추기에 안 들어간다."""
    rows = (await c.execute(text(
        "SELECT id, kind, body, source, refs, checked_at, created_at, dispatch_id FROM foreman_note "
        "WHERE project = :p AND retired_at IS NULL AND kind = 'thread' ORDER BY checked_at DESC, id DESC"), {"p": project})).all()
    return [{"id": r[0], "kind": r[1], "body": r[2], "source": r[3], "refs": json.loads(r[4]) if r[4] else {},
             "checked_at": r[5], "created_at": r[6], "dispatch_id": r[7]} for r in rows]


async def drift(c: Any, note: dict[str, Any], head: str | None, git: Any = None, repo: str | None = None) -> list[str]:
    """확인 뒤 바뀐 것 — 그 줄이 가리키는 세션에 뒤 활동이 있거나 출처 파일이 없어졌으면 한 마디씩.
    확인 뒤 커밋 수는 글로 붙이지 않고 note["commits"]에만 남긴다(낡음 문턱 stale_commits). 11-13 — 「⚠ 확인 뒤 커밋 N개」는 저장소 전체의
    커밋이라 그 줄의 일과 상관없이 FOREMAN에서 거의 모든 줄에 늘 붙었다(하루 100개 남짓). log/note_threads_only_20261113.md"""
    out = []
    note["commits"] = None
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
            note["commits"] = int(n) if n.isdigit() else None
        except Exception:  # noqa: BLE001 — 옛 HEAD가 없어졌으면(리베이스) 셀 수 없다 — 날수 문턱만
            pass
    src = note.get("source") or ""
    if re.match(r"^(log|docs)/", src) and not (REPO_ROOT / src).exists():
        out.append("출처 파일이 없음")
    return out


def stale_why(note: dict[str, Any], rules: NoteRules, now: datetime | None = None) -> list[str]:
    """「낡음 — 확인 필요」 까닭(thread만). 마지막 확인 뒤 stale_days가 지났거나 커밋이 stale_commits개를 넘었으면."""
    if note.get("kind") != "thread":
        return []
    out = []
    days = ((now or _now()) - note["checked_at"]).total_seconds() / 86400
    if days >= rules.stale_days:
        out.append(f"확인 뒤 {days:.0f}일")
    if (note.get("commits") or 0) >= rules.stale_commits:
        out.append(f"확인 뒤 커밋 {note['commits']}개")
    return out


async def render(c: Any, project: str, head: str | None = None, git: Any = None, repo: str | None = None,
                 cap: int = TOKEN_CAP, rules: NoteRules | None = None, now: datetime | None = None) -> dict[str, Any]:
    """진행 중인 일 → 상황 묶음 글. 최근 확인한 것부터 상한까지. 넘친 줄은 접는다(지우지 않는다).
    낡은 줄(stale_why)은 「낡음(확인 필요)」으로 갈라 맨 뒤에 — 디스패처가 진행 중인 일로 믿지 않게(11-13)."""
    rules = rules or NoteRules()
    notes = await active(c, project)
    for n in notes:
        n["drift"] = await drift(c, n, head, git, repo)
        n["stale"] = stale_why(n, rules, now)
    notes.sort(key=lambda n: (bool(n["stale"]), -n["checked_at"].timestamp()))
    lines, used, folded = [], 0, []
    for n in notes:
        d = n["drift"]
        what = " · 낡음(확인 필요 — 끝났을 수 있다. 진행 중이라고 믿지 말고 확인하라)" if n["stale"] else ""
        ln = (f"  - [줄 {n['id']}{what}] {n['body']} "
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
    """디스패처가 제안한 진행 중인 일 고치기를 사실과 맞춘다. 모양이 틀리거나 남의 프로젝트 줄이면 빼고 경고.
    없앤 칸(decision — 규칙 · 판단)을 쌓자는 제안은 빼고 DROPPED_WARN으로 시작하는 경고(계획 카드에 뜬다, 11-13)."""
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
                warn.append(f"노트 {o.get('id')}은(는) 이 프로젝트의 지금 진행 중인 일이 아닙니다. 제안을 뺐습니다")
                continue
            op["id"] = nid
            op["was"] = mine[nid]["body"]
            op["kind"] = mine[nid]["kind"]
        if op["op"] in ("add", "update"):
            kind = o.get("kind") or op.get("kind") or "thread"
            body = re.sub(r"\s+", " ", str(o.get("body") or "")).strip()
            if kind == "decision":
                warn.append(f"{DROPPED_WARN}. 진행 중인 일만 쌓습니다(규칙 · 금지 · 설계 결정은 CLAUDE.md · docs 몫): {body[:60]}")
                continue
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


async def touch_by_hand(c: Any, note_id: int) -> bool:
    """화면에서 사람이 「아직 진행 중」 — 확인 시각을 지금으로(낡음이 풀린다). 진행 중인 일 줄만."""
    r = await c.execute(text("UPDATE foreman_note SET checked_at = :t WHERE id = :i AND retired_at IS NULL AND kind = 'thread'"),
                        {"t": _now(), "i": note_id})
    return bool(r.rowcount)


# ── 끝난 「진행 중인 일」 줄을 기계로 내리기(11-13 사용자 결정, log/note_auto_retire_20261113.md) ─────────────
# 줄에 붙은 세션(refs.sessions)이 모두 끝났고 그 세션들이 남긴 일이 없으면 내린다. 지우지 않는다 — retired_at과
# refs.auto_retired {why, at}(스키마 그대로). 사람이 되살리면 refs.keep — 다시 기계로 내리지 않는다. 남은 decision 줄은 보지 않는다(active).
# 원본 폴더 세션은 끝남을 못 가른다(같은 줄기가 다음 세션으로 이어진다) — 붙은 세션이 원본 폴더 세션뿐이면 내리지 않는다.

async def session_facts(c: Any, sids: list[int], live: set[str] | None) -> dict[int, dict[str, Any]]:
    """세션마다 끝남을 가를 사실 — 살아 있나 · worktree(저장소, 이름) · 합침/버림 기록 · 합치기 카드 · 같은 자리를 뒤에 쓴 세션.
    live: 살아 있는 CC 세션 id들(liveness.live_sessions). None이면 detached_at으로."""
    if not sids:
        return {}
    rows = (await c.execute(text(
        "SELECT cs.id, cs.cc_session_id, cs.cwd, cs.worktree_path, cs.detached_at, cs.role, "
        " (SELECT GROUP_CONCAT(DISTINCT m.action) FROM session_action m WHERE m.session_id = cs.id AND m.ok "
        "   AND m.action IN ('wt-merge', 'wt-discard')), "
        " (SELECT mc.status FROM merge_card mc WHERE mc.session_id = cs.id), "
        " (SELECT MIN(cs2.id) FROM character_session cs2 WHERE cs2.id > cs.id AND cs2.cwd = cs.cwd) "
        "FROM character_session cs WHERE cs.id IN :s").bindparams(bindparam("s", expanding=True)), {"s": sids})).all()
    out: dict[int, dict[str, Any]] = {}
    for sid, cc, cwd, wtp, det, role, acts, card, later in rows:
        repo, name = wt.split(wtp or cwd or "")
        alive = (cc in live) if live is not None and cc else det is None
        out[int(sid)] = {"alive": bool(alive), "repo": repo if name else None, "wt": name, "acts": set((acts or "").split(",")) - {""},
                         "card": card, "later": later, "role": role, "in_base": None, "dir": None}
    return out


async def _git_facts(f: dict[str, Any], in_base: Any) -> None:
    """worktree 세션에 합침 · 버림 · 카드 · 뒤 세션이 없을 때만 git을 본다(폴더 · 브랜치가 아직 이 세션의 것)."""
    if not f["wt"] or f["alive"] or f["acts"] or f["card"] == "merged" or f["later"]:
        return
    f["dir"] = (Path(f["repo"]) / wt.WT_DIR / f["wt"]).is_dir()
    try:
        f["in_base"] = await in_base(f["repo"], f["wt"])
    except Exception:  # noqa: BLE001 — 저장소를 못 읽으면 「끝났다」고 하지 않는다
        f["in_base"] = "error"


def verdict(sids: list[int], facts: dict[int, dict[str, Any]], spawned: set[int] | None = None) -> tuple[str, str]:
    """("done" | "open" | "unknown", 까닭). done만 내린다.
    spawned: 이 줄의 dispatch가 띄웠고 첫 턴이 끝난 관리자 세션들(rules.manager_spawn_done일 때만 넘어온다)."""
    if not sids:
        return "unknown", "붙은 세션이 없음"
    missing = [s for s in sids if s not in facts]
    if missing:
        return "unknown", f"세션 {', '.join(map(str, missing))}을 찾지 못함"
    spawned = spawned or set()
    parts, decided = [], False             # decided: 기계로 끝남을 가른 세션이 하나라도 있나(원본 폴더 세션은 못 가른다)
    for s in sids:
        f = facts[s]
        if f["alive"]:
            if s in spawned:
                parts.append(f"{s} 관리자 띄움 끝(첫 턴 끝, 세션은 계속 돈다)")
                decided = True             # 띄운 일은 기계로 갈린다 — 원본 폴더 세션이어도
                continue
            return "unknown", f"세션 {s}이 살아 있음"
        if not f["wt"]:
            parts.append(f"{s} 끝남(원본 폴더)")
            continue
        decided = True
        if "wt-merge" in f["acts"]:
            parts.append(f"{s} 합침")
        elif "wt-discard" in f["acts"]:
            parts.append(f"{s} 버림")
        elif f["card"] == "merged":
            parts.append(f"{s} 합침(카드)")
        elif f["later"]:
            # worktree.create는 쓰던 이름(폴더 · 브랜치)을 피한다 — 같은 자리를 뒤 세션이 썼으면 이 세션의 브랜치는 그 전에 없어졌다
            parts.append(f"{s} 브랜치 없어짐(자리를 세션 {f['later']}이 다시 씀)")
        elif f["in_base"] is True:
            parts.append(f"{s} 커밋이 원본에 들어 있음")
        elif f["in_base"] is None and f["dir"] is False:
            parts.append(f"{s} 폴더 · 브랜치 없어짐")
        else:
            return "open", f"세션 {s}의 일이 남음(합치지 않은 커밋 · 폴더)"
    if not decided:
        return "unknown", "원본 폴더 세션뿐이라 끝남을 기계로 못 가름"
    return "done", "자동: 세션 " + " · ".join(parts)


async def _spawned_managers(c: Any, note: dict[str, Any], sids: list[int]) -> set[int]:
    """이 줄의 dispatch가 띄운 관리자 세션 중 첫 턴이 끝난 것(「관리자 띄우기」 줄 — rules.manager_spawn_done)."""
    did = note.get("dispatch_id")
    m = re.match(r"^dispatch #(\d+)$", note.get("source") or "")
    ids = {int(x) for x in (did, m and m.group(1)) if x}
    if not ids or not sids:
        return set()
    rows = (await c.execute(text(
        "SELECT ds.session_id FROM dispatch_session ds JOIN character_session cs ON cs.id = ds.session_id "
        "WHERE ds.dispatch_id IN :d AND ds.session_id IN :s AND ds.status = 'started' AND ds.role = 'manager' AND cs.role = 'manager' "
        "AND EXISTS (SELECT 1 FROM turn t WHERE t.session_id = cs.id AND t.seq = 1 AND t.ended_at IS NOT NULL)").bindparams(
            bindparam("d", expanding=True), bindparam("s", expanding=True)), {"d": sorted(ids), "s": sids})).all()
    return {int(r[0]) for r in rows}


async def sweep(c: Any, project: str, live: set[str] | None, rules: NoteRules | None = None,
                in_base: Any = None, dry_run: bool = False) -> list[dict[str, Any]]:
    """그 프로젝트의 진행 중인 일 줄을 훑어 끝난 줄을 내린다. 돌려주는 값: 줄마다 {id, verdict, why}(내린 줄은 retired=True)."""
    rules = rules or NoteRules()
    in_base = in_base or wt.in_base
    out = []
    for n in await active(c, project):
        if n["refs"].get("keep"):
            continue
        sids = [int(s) for s in (n["refs"].get("sessions") or []) if str(s).isdigit()]
        facts = await session_facts(c, sids, live)
        for f in facts.values():
            await _git_facts(f, in_base)
        spawned = await _spawned_managers(c, n, sids) if rules.manager_spawn_done else set()
        v, why = verdict(sids, facts, spawned)
        row = {"id": n["id"], "verdict": v, "why": why, "retired": False}
        if v == "done" and not dry_run:
            refs = dict(n["refs"], auto_retired={"why": why, "at": _now().isoformat(timespec="seconds") + "Z"})
            r = await c.execute(text("UPDATE foreman_note SET retired_at = :t, refs = :r WHERE id = :i AND retired_at IS NULL"),
                                {"t": _now(), "r": json.dumps(refs, ensure_ascii=False), "i": n["id"]})
            row["retired"] = bool(r.rowcount)
        out.append(row)
    return out


async def auto_retired(c: Any, project: str, days: int = 14, limit: int = 30) -> list[dict[str, Any]]:
    """화면 「자동으로 내린 줄」 — 기계가 내린 줄(최근 days일). 조용히 사라지지 않게 보인다."""
    rows = (await c.execute(text(
        "SELECT id, body, refs, retired_at FROM foreman_note WHERE project = :p AND retired_at IS NOT NULL "
        "AND replaced_by IS NULL AND JSON_EXTRACT(refs, '$.auto_retired') IS NOT NULL AND retired_at > :t "
        "ORDER BY retired_at DESC, id DESC LIMIT :n"),
        {"p": project, "t": _now() - timedelta(days=days), "n": limit})).all()
    out = []
    for nid, body, refs, at in rows:
        a = (json.loads(refs) if refs else {}).get("auto_retired") or {}
        out.append({"id": nid, "body": body, "why": a.get("why") or "", "retired_at": at.isoformat() + "Z"})
    return out


async def restore(c: Any, note_id: int) -> bool:
    """기계가 내린 줄을 사람이 되살린다 — 다시 진행 중으로, refs.keep(다시 자동으로 내리지 않음), 확인 시각은 지금."""
    r = (await c.execute(text("SELECT refs FROM foreman_note WHERE id = :i AND retired_at IS NOT NULL AND replaced_by IS NULL"),
                         {"i": note_id})).first()
    if not r:
        return False
    refs = json.loads(r[0]) if r[0] else {}
    if not refs.get("auto_retired"):
        return False                     # 사람 · 디스패처가 내린 줄은 여기서 되살리지 않는다
    refs.pop("auto_retired")
    refs["keep"] = True
    u = await c.execute(text("UPDATE foreman_note SET retired_at = NULL, checked_at = :t, refs = :r WHERE id = :i AND retired_at IS NOT NULL"),
                        {"t": _now(), "r": json.dumps(refs, ensure_ascii=False), "i": note_id})
    return bool(u.rowcount)
