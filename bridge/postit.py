"""포스트잇(11-15 사용자, 서기 구조 다시 짜기 2번) — 열린 할 일 목록 그 자체. 받는 함(todo_inbox)이 곧 포스트잇이다.

바탕 설계: log/foreman-6_postit_proposal_20261115.md(3절 「만들 사람이 알 것」), 결과: log/foreman-5_postit_20261115.md.
들어오는 길(셋 다 포스트잇으로, source 칸):
  note    포스트잇에 바로 적음([저장])
  todo    옛 머리줄 [＋ 할 일](11-15 단추와 창을 뺐다 — 포스트잇 창이 같은 일을 한다. 옛 길 POST /api/scribe/inbox와 이미 든 줄에 남는다)
  said    대화에서 사람이 「포스트잇에 올려라」 · 「나중에 할 일에 넣어라」 — 관리자가 그 턴에서 POST /api/postit(session)를 부른다
  chat    브리지 그물(sweep) — 사람이 미루자고 했는데 포스트잇이 안 생긴 턴. 확인 전(confirmed 0, 화면에 흐리게)
  promote 옮기기 「문서에 넣을 것 고르기」의 미완(bridge/promote.py dest "postit") — 세션이 쓰지 않고 브리지가 넣는다
닫기: [x] drop(그냥 사라짐) · [→] limit(README 「알려진 한계」로 — 쓰는 것은 서기 「알려진 한계 쓰기」) · done(끝남).
[갱신]: 조사(inspector) 세션이 코드를 보고 줄마다 판정한다(끝남 · 남음 · 모름). 근거가 코드 자리일 때만 「끝남」.
판정은 제안이다 — 사람이 줄마다 닫는다(커밋만 보고 자동으로 지우지 않는다, 사용자).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

log = logging.getLogger(__name__)

MAX = 8000
SOURCES = ("note", "todo", "said", "chat", "promote")
ONE_PER_REF = ("chat", "promote")      # 근거 하나에 한 장인 출처. said · note는 글이 다르면 여러 장
DUP_REASON = "같은 근거에 같은 글이 이미 있어 새로 만들지 않았습니다"
SOURCE_KO = {"note": "포스트잇에 적음", "todo": "포스트잇에 적음", "said": "대화에서 올림", "chat": "대화에서 찾음", "promote": "옮기기 미완"}
CLOSE = ("drop", "limit", "done")
README_LIMIT = "알려진 한계"        # README 절 제목(이 글이 든 머리줄) — 아직 없을 수 있다(관리자가 「나중에 할 일」 표를 옮기기 전)
# README가 생성물인 저장소(.foreman/docs.toml [readme] 표가 켜짐)에는 한계 절을 둘 곳이 없다. 옛 길([→], 서기 「알려진 한계 쓰기」)은
# 문서 정리 E 단계의 [한계로]로 바뀔 때까지 조용히 두지 않고 이 글로 거부한다(11-17 사용자)
LIMIT_GONE = "README 한계 절이 없어졌습니다. E 단계의 [한계로]가 생기면 그것을 써야 합니다"


def readme_generated(repo: str | Path) -> bool:
    """그 저장소의 README.md가 생성물인가([readme] 표). 설정이 깨졌으면 그 까닭으로 거부한다(모르는 채 옛 길로 가지 않는다)."""
    from bridge.doctext import config as dcfg
    from bridge.inject import Refused
    try:
        return dcfg.load(repo).readme is not None
    except dcfg.DocsConfigError as e:
        raise Refused(f"문서 설정을 읽지 못해 알려진 한계로 보낼 수 없습니다: {e}") from e
CHECK_ACT = "postit-run"            # session_action(칸 12자) — [갱신] 조사 세션을 띄움(detail: "<프로젝트> <req> p<N> L<N>")
CHECK_DONE_ACT = "postit-done"      # 결과를 받음(ok) · 결과 없이 끝남(ok 0)
CHECK_TAG = "FOREMAN-POSTIT-CHECK"
NET_WAIT = timedelta(minutes=30)    # 열린 턴은 이만큼 지나야 그물이 본다 — 관리자가 그 턴에서 올릴 틈(같은 턴 두 번 막기)
NET_WINDOW = timedelta(days=2)      # 첫 훑기(브리지가 뜬 뒤 한 번)는 0033 뒤 전부, 그다음부터는 이 창만
CONF_FILE = Path(__file__).resolve().parent.parent / "config" / "scribe.toml"
CONF_DEFAULT = {"open_max": 20, "stale_days": 7, "refresh_days": 7}

# 상태 — 칸(closed_reason) + 계산(taken_by). 열린 것: new · taking · merged. limit은 README에 썼는지를 서기 세션으로 센다
_MERGED = "EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = i.taken_by AND m.action = 'wt-merge' AND m.ok)"
_DISCARDED = "EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = i.taken_by AND m.action = 'wt-discard' AND m.ok)"
STATE = ("CASE "
         f"WHEN i.closed_reason = 'limit' THEN CASE WHEN i.taken_by IS NULL THEN 'limit' WHEN {_MERGED} THEN 'limit_written' "
         f"  WHEN {_DISCARDED} THEN 'limit' ELSE 'limit_writing' END "
         "WHEN i.closed_reason IS NOT NULL THEN i.closed_reason "
         "WHEN i.dropped_at IS NOT NULL THEN 'drop' "
         "WHEN i.taken_by IS NULL THEN 'new' "
         f"WHEN {_MERGED} THEN 'merged' "
         f"WHEN {_DISCARDED} THEN 'new' "
         "WHEN EXISTS (SELECT 1 FROM character_session t WHERE t.id = i.taken_by "
         "  AND t.worktree_path IS NULL AND t.detached_at IS NOT NULL) THEN 'merged' "
         "ELSE 'taking' END")
OPEN_STATES = ("new", "taking", "merged")
STATE_KO = {"new": "열림", "taking": "코더가 하는 중", "merged": "코더 세션 끝남",
            "drop": "삭제", "done": "끝남", "limit": "알려진 한계로 보냄",
            "limit_writing": "알려진 한계로 보냄(서기가 쓰는 중)", "limit_written": "알려진 한계로 보냄(README에 씀)"}

# ── 그물(문장 꼴, LLM 없음) ──────────────────────────────────
# 438 1-3 F'': 표 이름에 올려라 · 나중에 정한다 · 미루자 · 낱말 없는 「지금은 두」 「그때 다시」. 「포스트잇」 · 「나중에 할 일」 둘 다 알아듣는다.
# 들어오는 문에서 이미 뺀 것: 띄운 세션의 첫 턴(일감 글), 합치기 카드(출처 merge_card). 붙여 넣은 글 안도 본다(사람 말이 거기 있다)
_TABLE = r"(?:나중에\s*할\s*일|포스트잇)"
NET = (
    ("표에", re.compile(_TABLE + r"[」』\"'”’)\]]*\s*(?:표\s*)?(?:에|으로|로)\s*(?:한\s*줄\s*(?:더\s*)?)?"
                         r"(?:올려|올리|올립|넣|추가|더해|더하|더합|보태|적어|적으|적습)"
                         # 「나중에 할 일」의 「…」 줄에 한 줄 더해(t:6549 · t:6624 — 낫표가 겹쳐 앞 꼴에 안 맞았다)
                         r"|" + _TABLE + r"[」』\"'”’)\]]*\s*의\s.{0,120}?줄에\s*(?:한\s*줄\s*)?(?:더|보태|넣|적)")),
    ("나중에", re.compile(r"나중에\s*(?:정한다|정하자|정하겠|정합|하자|합시다|본다|보자|봅시다|다시|한다|하겠|합니다|제가|자꾸)")),
    ("미루", re.compile(r"미루(?:자|기로|겠|어\s*두|어\s*놓)|미뤄\s*(?:두|놓|둡)")),
    ("지금은", re.compile(r"지금은\s*(?:두|하지\s*마|하지\s*말|손대지|안\s*하)")),
    ("그때", re.compile(r"(?:쌓이면|생기면|되면|세워진\s*뒤)\s*그때\s*다시|그때\s*다시\s*(?:이야기|얘기)")),
)
NOT_LATER = re.compile(r"아니라\s*지금")
_WRAP = re.compile(r"</?pasted_content[^>]*>")


def _lines(t: str) -> list[str]:
    return [ln.strip() for ln in _WRAP.sub("\n", t or "").split("\n") if ln.strip()]


def net_hits(t: str | None) -> list[str]:
    """미룬 말로 보이는 줄(잘라 낸 앞뒤) — 없으면 빈 목록. 한 줄은 맞은 자리 앞 150자 · 뒤 250자까지."""
    out = []
    for ln in _lines(t or ""):
        if NOT_LATER.search(ln):
            continue
        m = next((x for _, p in NET if (x := p.search(ln))), None)
        if m:
            a = max(0, m.start() - 150)
            out.append(("…" if a else "") + ln[a:m.end() + 250] + ("…" if m.end() + 250 < len(ln) else ""))
    return out


def net_kind(t: str | None) -> list[str]:
    """맞은 꼴 이름(시험 · 판정 목록용)."""
    return sorted({k for ln in _lines(t or "") if not NOT_LATER.search(ln) for k, p in NET if p.search(ln)})


# ── 쌓임 기준(config/scribe.toml [postit]) ───────────────────
_CONF_WARNED: set[str] = set()


def _conf_warn(msg: str) -> None:
    """설정 문제는 한 번만 경고한다(서기실을 읽을 때마다 부른다)."""
    if msg not in _CONF_WARNED:
        _CONF_WARNED.add(msg)
        log.warning("%s", msg)


def conf(path: Path | None = None) -> dict[str, int]:
    """쌓임 기준. 서기 말풍선을 정하는 설정은 이 [postit] 하나다(11-17, 옛 [nudge]는 읽는 곳이 없어 뺐다).
    파일이 없으면 기본값. 틀린 값은 기본값으로, 모르는 칸과 모르는 표는 무시하고 돌되 로그에 경고한다(조용히 무시하지 않게)."""
    import tomllib
    p = Path(path or CONF_FILE)
    try:
        whole = tomllib.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        whole = {}
    except (OSError, tomllib.TOMLDecodeError) as e:
        _conf_warn(f"{p.name}을 읽지 못해 쌓임 기준을 기본값으로 둡니다: {type(e).__name__}")
        whole = {}
    for k in whole:
        if k != "postit":
            _conf_warn(f"{p.name}의 [{k}]는 읽는 코드가 없습니다(쌓임 기준은 [postit])")
    raw = whole.get("postit") or {}
    for k in raw:
        if k not in CONF_DEFAULT:
            _conf_warn(f"{p.name} [postit]의 {k}는 모르는 칸입니다(아는 칸: {', '.join(CONF_DEFAULT)})")
    out = {}
    for k, v in CONF_DEFAULT.items():
        if k in raw and not str(raw[k]).isdigit():
            _conf_warn(f"{p.name} [postit] {k} = {raw[k]!r}는 0 이상 정수가 아니라 기본값 {v}로 둡니다")
        out[k] = int(raw[k]) if str(raw.get(k, "")).isdigit() else v
    return out


def nudge_of(n_open: int, oldest: datetime | None, last_check: datetime | None, cf: dict[str, int] | None = None,
             now: datetime | None = None) -> dict[str, Any] | None:
    """서기 말풍선(11-15 사용자 답 4 — 말풍선만, 21시 묶음에는 넣지 않는다). 열린 것이 open_max개 이상 · 가장 오래된 것이
    stale_days일 · 마지막 [갱신] 뒤 refresh_days일(한 번도 안 했으면 가장 오래된 것부터) 중 하나면."""
    if not n_open or oldest is None:
        return None
    cf = cf or conf()
    now = now or datetime.now(UTC).replace(tzinfo=None)
    days = (now - oldest).days
    since = (now - (last_check or oldest)).days
    why = []
    if n_open >= cf["open_max"]:
        why.append(f"할 일 {n_open}장")
    if days >= cf["stale_days"]:
        why.append(f"가장 오래된 것 {days}일째")
    if since >= cf["refresh_days"]:
        why.append(f"[갱신] {since}일 없음" if last_check else f"[갱신]을 한 번도 안 함({since}일)")
    return {"n": n_open, "days": days, "since_check": since, "why": ", ".join(why)} if why else None


# ── 넣기 · 닫기 ──────────────────────────────────────────────
async def _turn_of(c: Any, session_id: int) -> int | None:
    """관리자가 올릴 때 근거 턴 — 그 세션의 마지막 사람 턴(지금 그 턴 안에서 부른다)."""
    r = (await c.execute(text("SELECT id FROM turn WHERE session_id = :s AND origin = 'human' ORDER BY seq DESC LIMIT 1"),
                         {"s": session_id})).first()
    return int(r[0]) if r else None


async def add(engine: Any, project: str, body: str, source: str = "note", source_ref: str | None = None,
              confirmed: bool = True, session: int | None = None, assignee: str = "scribe") -> dict[str, Any]:
    """포스트잇 하나 — {id, created}. 11-15 고침(p:51): 같은 근거(source_ref)에 글이 다른 여러 장은 모두 넣는다.
    같은 근거에 같은 글만 새로 만들지 않고, 그때 응답은 {created: False, duplicate: True, reason}으로 겹침을 말한다.
    그물(chat)과 옮기기(promote)는 근거 하나에 한 장이다(같은 턴을 여러 번 줍지 않게).
    그물이 먼저 올린 확인 전 줄에 관리자가 같은 턴으로 올리면 그 줄을 확인된 것으로 바꾼다(두 줄이 생기지 않게)."""
    from bridge.inject import Refused
    body = (body or "").strip()
    if not body:
        raise Refused("적을 글이 비어 있습니다")
    if len(body) > MAX:
        raise Refused(f"글이 너무 깁니다({len(body)}자). {MAX}자까지 받습니다")
    if source not in SOURCES:
        raise Refused(f"모르는 출처입니다: {source}")
    async with engine.begin() as c:
        if not (await c.execute(text("SELECT 1 FROM project WHERE name = :p"), {"p": project})).first():
            raise Refused(f"모르는 프로젝트입니다: {project}")
        if session is not None and not source_ref:
            tid = await _turn_of(c, session)
            source_ref = f"t:{tid}" if tid else f"s:{session}"
        if source_ref:
            rows = (await c.execute(text("SELECT id, source, confirmed, closed_reason, body FROM todo_inbox WHERE source_ref = :r "
                                         "ORDER BY id"), {"r": source_ref})).all()
            if rows and source in ONE_PER_REF:
                # 그물 · 옮기기는 근거 하나에 한 장 — 같은 턴을 여러 번 주워도 한 장
                return {"id": int(rows[0][0]), "created": False, "duplicate": True, "reason": DUP_REASON}
            same = next((r for r in rows if (r[4] or "").strip() == body), None)
            if same:
                # 같은 근거에 같은 글 — 정말로 겹친 것만 하나로 두고, 부른 쪽이 알아보게 말한다
                return {"id": int(same[0]), "created": False, "duplicate": True, "reason": DUP_REASON}
            pending = next((r for r in rows if r[1] == "chat" and not r[2] and r[3] is None), None)
            if pending and source != "chat":
                # 그물이 먼저 올린 확인 전 줄은 같은 근거의 첫 글이 확인된 줄로 바꾼다. 글이 다른 다음 것은 새 장이다
                await c.execute(text("UPDATE todo_inbox SET body = :b, source = :s, confirmed = TRUE WHERE id = :i"),
                                {"b": body, "s": source, "i": pending[0]})
                return {"id": int(pending[0]), "created": True, "upgraded": True}
        r = await c.execute(text("INSERT INTO todo_inbox (project, body, assignee, source, source_ref, confirmed) "
                                 "VALUES (:p, :b, :a, :s, :r, :c)"),
                            {"p": project, "b": body, "a": assignee, "s": source, "r": source_ref, "c": bool(confirmed)})
        return {"id": int(r.lastrowid), "created": True}


async def close(engine: Any, iid: int, reason: str, note: str | None = None) -> bool:
    """[x] drop · [→] limit · done. 열린 것만. limit은 가져간 세션을 풀어 둔다 — README에 쓰는 서기가 새로 가져간다."""
    from bridge.inject import Refused
    if reason not in CLOSE:
        raise Refused(f"닫는 까닭은 {', '.join(CLOSE)} 중 하나입니다: {reason}")
    if reason == "limit":
        async with engine.connect() as c:
            row = (await c.execute(text("SELECT p.repo_path FROM todo_inbox i JOIN project p ON p.name = i.project "
                                        "WHERE i.id = :i"), {"i": iid})).first()
        if row and row[0] and readme_generated(row[0]):
            raise Refused(LIMIT_GONE)
    async with engine.begin() as c:
        r = await c.execute(text(
            "UPDATE todo_inbox SET closed_reason = :r, closed_at = UTC_TIMESTAMP(3), closed_note = :n, "
            "taken_by = CASE WHEN :r = 'limit' THEN NULL ELSE taken_by END, "
            "taken_at = CASE WHEN :r = 'limit' THEN NULL ELSE taken_at END "
            "WHERE id = :i AND closed_reason IS NULL AND dropped_at IS NULL"),
            {"r": reason, "n": (note or "")[:2000] or None, "i": iid})
        if r.rowcount:
            await c.execute(text("UPDATE postit_check SET resolved = 'closed', resolved_at = UTC_TIMESTAMP(3) "
                                 "WHERE item = :it AND resolved IS NULL"), {"it": f"p:{iid}"})
        return r.rowcount > 0


async def confirm(engine: Any, ids: list[int]) -> int:
    """확인 전(그물) 줄을 사람이 [저장]으로 받아들임."""
    if not ids:
        return 0
    async with engine.begin() as c:
        r = await c.execute(text("UPDATE todo_inbox SET confirmed = TRUE WHERE id IN :ids AND closed_reason IS NULL AND NOT confirmed")
                            .bindparams(bindparam("ids", expanding=True)), {"ids": [int(i) for i in ids]})
        return r.rowcount


_COLS = ("i.id, i.project, i.body, i.assignee, i.source, i.source_ref, i.confirmed, i.created_at, i.edited_at, i.taken_by, "
         "i.closed_reason, i.closed_at, i.closed_note")


async def items(engine: Any, project: str | None = None, open_only: bool = True, limit: int = 300) -> list[dict[str, Any]]:
    """열린 것은 오래된 것부터, 닫힌 것(open_only=False)은 최근 닫힌 것부터."""
    where = f"{STATE} IN ('new', 'taking', 'merged')" if open_only else f"{STATE} NOT IN ('new', 'taking', 'merged')"
    order = "i.id" if open_only else "COALESCE(i.closed_at, i.dropped_at) DESC, i.id DESC"
    q = (f"SELECT {_COLS}, {STATE} AS state FROM todo_inbox i WHERE {where}"
         + (" AND i.project = :p" if project else "") + f" ORDER BY {order} LIMIT :n")
    async with engine.connect() as c:
        rows = (await c.execute(text(q), {"p": project, "n": limit})).mappings().all()
    return [dict(r) for r in rows]


async def limit_pending(engine: Any, project: str) -> list[dict[str, Any]]:
    """[→]로 보냈는데 README에 아직 안 쓴 것 — 서기 「알려진 한계 쓰기」가 가져간다(오래된 것부터)."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            f"SELECT i.id, i.body, i.created_at, i.closed_at FROM todo_inbox i WHERE i.project = :p AND {STATE} = 'limit' ORDER BY i.id"),
            {"p": project})).mappings().all()
    return [dict(r) for r in rows]


async def readme_drop_pending(engine: Any, project: str, since: datetime | None) -> list[dict[str, Any]]:
    """[갱신]에서 사람이 「끝남」으로 닫은 README 「알려진 한계」 줄 — README에서 지우는 것은 서기 몫이라 그때까지 센다.
    since = 지난 「알려진 한계 쓰기」가 합쳐진 시각(scribe_room.later_since) — 그 뒤에 닫은 것만 남았다."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT id, item, item_text, evidence, reason, resolved_at FROM postit_check WHERE project = :p AND item LIKE 'L:%' "
            "AND resolved = 'closed' AND resolved_at >= :s ORDER BY id"), {"p": project, "s": since or datetime(2000, 1, 1)})).mappings().all()
    return [dict(r) for r in rows]


# ── [갱신] — 조사 세션 ───────────────────────────────────────
def readme_limits(repo: str) -> list[str] | None:
    """README 「알려진 한계」 절의 줄(목록 줄 · 표 줄). 절이 없으면 None."""
    try:
        lines = Path(repo, "README.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    start = next((i for i, ln in enumerate(lines) if ln.startswith("#") and README_LIMIT in ln), None)
    if start is None:
        return None
    lvl = len(lines[start]) - len(lines[start].lstrip("#"))
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("#") and len(ln) - len(ln.lstrip("#")) <= lvl:
            break
        s = ln.strip()
        if s.startswith(("- ", "* ")) or (s.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", s)):
            out.append(s)
    if out and out[0].startswith("|"):
        out = out[1:]          # 표 머리 줄
    return out


CHECK_PROMPT = """[FOREMAN 조사 일감 — 포스트잇 갱신 r={req}] {project}

너는 조사(읽기 전용) 세션이다. 포스트잇(열린 할 일)과 README 「{limit}」 줄 가운데 **이미 끝난 것**을 코드를 보고 찾는다. 가볍게 보지 말고 제대로 본다.
- 재료(저장소 밖): `{materials}` — 끝까지 읽는다. 항목마다 id가 있다(포스트잇 p:번호, README 줄 L:번호)
- 항목마다 그 일이 지금 저장소에 되어 있는지 본다. 관련 코드 · 시험 · 설정 · docs를 직접 열어 확인한다. 커밋 제목은 찾을 실마리로만 쓴다
- 판정
  - 끝남: 근거가 **코드 자리**일 때만. `파일:줄`(예: `bridge/postit.py:120`) 또는 시험 이름(`tests/test_x.py::test_y`). 커밋 해시 · 커밋 제목 · log 글뿐이면 끝남이 아니라 모름이다
  - 남음: 아직 안 됐다. 일부만 됐으면 남음이고 까닭에 된 것과 남은 것을 나눠 적는다. 할 일이 정해져 있고 코드를 고치는 일이면 coder를 true로(코더에게 맡길 만함)
  - 모름: 확인할 수 없다. 까닭을 적는다
- 파일을 고치지 마라. 커밋하지 마라. 시험은 돌리지 않아도 된다(돌린다면 그 시험 하나만)
- 사람에게 묻지 않는다. 판단이 서지 않으면 모름이다
- `pgrep -f` · `pkill -f`를 쓰지 않는다(브리지가 거부한다)
- 끝나면 마지막 응답에 한 번만 아래 모양으로 써라(JSON 배열, 표지 줄 두 개를 글자 그대로). 재료의 모든 항목을 하나씩:

<<<{tag} r={req}>>>
[{{"id": "p:12", "verdict": "끝남", "evidence": "bridge/x.py:40, tests/test_x.py::test_y", "reason": "한 줄", "coder": false}}]
<<<END r={req}>>>
"""

VERDICTS = {"끝남": "done", "done": "done", "남음": "left", "left": "left", "모름": "unknown", "unknown": "unknown"}
VERDICT_KO = {"done": "끝난 것 같음", "left": "남음", "unknown": "모름"}
# 코드 자리 — 파일:줄 또는 시험 이름. 커밋 해시 · 제목만으로는 「끝남」을 받지 않는다(사용자 — 커밋만 보고 지우지 마라)
CODE_REF = re.compile(r"[\w./-]+\.(?:py|js|mjs|ts|sql|toml|html|css|sh|md|json|yaml|yml):\d+|[\w./-]*::test_\w+|\btest_\w+")


def check_material(project: str, posts: list[dict[str, Any]], limits: list[str] | None, commits: list[str], now: datetime,
                   mk: Any = None) -> str:
    from bridge import scribe as sc
    m = mk.text if mk else (lambda s: s)
    out = [f"# 포스트잇 갱신 재료 — {project} ({sc.kst(now)}, 포스트잇 {len(posts)} · README 줄 {len(limits or [])})",
           "사람 말은 자르지 않은 원문이다. 길면 쪽으로 나눠 끝까지 읽는다.", "", f"## 포스트잇(열린 것 {len(posts)})", ""]
    for x in posts:
        out += [f"### p:{x['id']} ({SOURCE_KO.get(x.get('source') or '', x.get('source') or '')}, {sc.kst(x['created_at'])}"
                + (", 확인 전" if not x.get("confirmed", True) else "") + ")", m(sc._full(x["body"])) or "", ""]
    out += [f"## README 「{README_LIMIT}」", ""]
    if limits is None:
        out += [f"README에 「{README_LIMIT}」 절이 아직 없다. 볼 줄이 없다.", ""]
    for n, ln in enumerate(limits or [], 1):
        out += [f"### L:{n}", m(ln), ""]
    out += ["## 최근 커밋(참고 — 끝남의 근거가 아니다)", ""] + [f"- {c}" for c in commits] + [""]
    return "\n".join(out)


def parse_check(body: str, known: dict[str, str]) -> list[dict[str, Any]]:
    """조사 세션이 낸 배열 → 재료에 있던 항목만. 「끝남」인데 근거가 코드 자리가 아니면 「모름」으로 내린다."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out, seen = [], set()
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict):
            continue
        iid = str(d.get("id") or "").strip()
        if iid.isdigit():
            iid = f"p:{iid}"
        if iid not in known or iid in seen:
            continue
        seen.add(iid)
        v = VERDICTS.get(str(d.get("verdict") or "").strip(), "unknown")
        ev = str(d.get("evidence") or "").strip()[:1000]
        why = str(d.get("reason") or "").strip()[:1000]
        if v == "done" and not CODE_REF.search(ev):
            v, why = "unknown", ("근거가 코드 자리(파일:줄, 시험 이름)가 아니라 모름으로 둡니다. " + why)[:1000]
        out.append({"item": iid, "item_text": known[iid][:500], "verdict": v, "evidence": ev or None, "reason": why or None,
                    "coder": bool(d.get("coder")) and v == "left"})
    return out


def _recent_commits(repo: str, n: int = 40) -> list[str]:
    try:
        return subprocess.run(["git", "-C", repo, "log", f"-{n}", "--format=%h %cs %s"], capture_output=True, text=True,
                              timeout=15).stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return []


async def _runs(engine: Any, project: str | None = None, open_only: bool = False) -> list[dict[str, Any]]:
    """[갱신] 세션 기록 — 최근 것부터. done: 결과 기록(ok · detail · 시각) 또는 None(아직)."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT a.session_id, a.detail, a.created_at, d.ok, d.detail, d.created_at FROM session_action a "
            "LEFT JOIN session_action d ON d.session_id = a.session_id AND d.action = :done "
            "WHERE a.action = :act AND a.ok" + (" AND a.detail LIKE :p" if project else "")
            + (" AND d.id IS NULL" if open_only else "") + " ORDER BY a.id DESC LIMIT 20"),
            {"act": CHECK_ACT, "done": CHECK_DONE_ACT, "p": f"{project} %"})).all()
    out = []
    for sid, det, at, ok, ddet, dat in rows:
        w = (det or "").split()
        out.append({"session_id": sid, "project": w[0] if w else None, "req": w[1] if len(w) > 1 else "", "at": at,
                    "done": None if dat is None else {"ok": bool(ok), "detail": ddet, "at": dat}})
    return out


async def start_check(m: Any, engine: Any, project: str) -> dict[str, Any]:
    """[갱신] — 조사 세션을 원본 폴더에 띄운다(고치지 않으니 worktree가 필요 없다 — 합치기 카드도 생기지 않는다)."""
    from bridge import handoff as ho
    from bridge import scribe as sc
    from bridge.inject import Refused
    from bridge.liveness import live_sessions
    from bridge.mask import Masker
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :p"), {"p": project})).first()
    repo = r[0] if r else None
    if not repo or not Path(repo, ".git").exists():
        raise Refused("이 프로젝트의 저장소를 찾지 못했습니다")
    live = set(live_sessions(m.sessions_dir))
    for run in await _runs(engine, project, open_only=True):
        row = await m.session(run["session_id"])
        if row and row.cc in live:
            raise Refused(f"이미 [갱신] 중입니다(조사 세션 {run['session_id']}). 끝나면 결과가 포스트잇에 뜹니다")
    posts = await items(engine, project)
    limits = readme_limits(repo)
    if not posts and not limits:
        raise Refused("볼 포스트잇도 README 「알려진 한계」 줄도 없습니다. 띄우지 않았습니다")
    now = datetime.now(UTC).replace(tzinfo=None)
    req = ho.new_req()
    day = (now + timedelta(hours=9)).strftime("%Y%m%d")
    mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / f"postit_check_{req}.md",
                   check_material(project, posts, limits, _recent_commits(repo), now, Masker()))
    prompt = CHECK_PROMPT.format(req=req, project=project, limit=README_LIMIT, materials=mat, tag=CHECK_TAG)
    res = await m.spawn_new(repo, None, "조사 — 포스트잇 갱신", role="inspector", worktree=False, first_prompt=prompt)
    if res.get("session_id"):
        await m._act(res["session_id"], CHECK_ACT, res.get("pid"), True, f"{project} {req} p{len(posts)} L{len(limits or [])}")
        known = {f"p:{x['id']}": x["body"] for x in posts} | {f"L:{n}": ln for n, ln in enumerate(limits or [], 1)}
        _KNOWN[(int(res["session_id"]), req)] = known
    return {"project": project, "session_id": res.get("session_id"), "items": len(posts), "limits": len(limits or []),
            **{k: res.get(k) for k in ("tmux", "note", "injected")}}


# 띄울 때 넘긴 항목(브리지를 다시 띄우면 사라진다 — 그때는 재료 파일에서 다시 읽는다)
_KNOWN: dict[tuple[int, str], dict[str, str]] = {}


def _known_from_material(project: str, req: str) -> dict[str, str]:
    from bridge import scribe as sc
    out: dict[str, str] = {}
    for f in sorted(sc.OUT_ROOT.glob(f"{project}_*/postit_check_{req}.md")):
        cur, buf = None, []
        for ln in f.read_text(encoding="utf-8").splitlines() + ["### end"]:
            if ln.startswith("### ") or ln.startswith("## "):
                if cur:
                    out[cur] = "\n".join(buf).strip()
                mm = re.match(r"### ((?:p|L):\d+)", ln)
                cur, buf = (mm.group(1) if mm else None), []
            elif cur:
                buf.append(ln)
    return out


async def collect(m: Any, engine: Any) -> int:
    """열린 [갱신] 세션의 마지막 응답에서 결과 블록을 읽어 postit_check에 넣는다. 결과 없이 세션이 끝났으면 실패로 남긴다
    (조용히 사라지지 않게 — 화면에 「결과 없이 끝났습니다」). 넣은 판정 수."""
    from bridge import handoff as ho
    from bridge.liveness import live_sessions
    from bridge.promote import extract
    n = 0
    live = None
    for run in await _runs(engine, open_only=True):
        sid, req, project = int(run["session_id"]), run["req"], run["project"]
        row = await m.session(sid)
        if row is None or not row.cc or not req or not project:
            continue
        path = row.transcript or ho.transcript_path(row.cwd or "", row.cc)
        body = extract(ho.assistant_text(path, 0), CHECK_TAG, req) if Path(path).exists() else None
        if body is None:
            live = live if live is not None else set(live_sessions(m.sessions_dir))
            if row.cc not in live:
                await m._act(sid, CHECK_DONE_ACT, None, False, f"{req} 결과 없이 끝났습니다")
            continue
        known = _KNOWN.get((sid, req)) or _known_from_material(project, req)
        got = parse_check(body, known)
        async with engine.begin() as c:
            if got:
                await c.execute(text("UPDATE postit_check SET resolved = 'stale', resolved_at = UTC_TIMESTAMP(3) "
                                     "WHERE project = :p AND resolved IS NULL AND item IN :it")
                                .bindparams(bindparam("it", expanding=True)), {"p": project, "it": [g["item"] for g in got]})
            for g in got:
                await c.execute(text("INSERT INTO postit_check (project, session_id, item, item_text, verdict, evidence, reason, coder) "
                                     "VALUES (:p, :s, :item, :item_text, :verdict, :evidence, :reason, :coder)"),
                                {"p": project, "s": sid, **g})
        nd = sum(g["verdict"] == "done" for g in got)
        await m._act(sid, CHECK_DONE_ACT, None, True, f"{req} 판정 {len(got)} 끝남 {nd}")
        n += len(got)
    return n


async def checks(engine: Any, project: str) -> list[dict[str, Any]]:
    """사람이 아직 닫지도 남기지도 않은 판정 — 항목마다 마지막 하나."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT id, session_id, item, item_text, verdict, evidence, reason, coder, created_at FROM postit_check "
            "WHERE project = :p AND resolved IS NULL ORDER BY id"), {"p": project})).mappings().all()
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        by[r["item"]] = dict(r)
    return list(by.values())


async def resolve_check(engine: Any, cid: int, action: str) -> dict[str, Any]:
    """판정 한 줄 — close(닫음: 포스트잇은 done으로, README 줄은 서기가 지울 줄로 센다) · keep(남김)."""
    from bridge.inject import Refused
    if action not in ("close", "keep"):
        raise Refused("close · keep 중 하나입니다")
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT item, session_id, evidence, reason, resolved FROM postit_check WHERE id = :i"),
                             {"i": cid})).first()
    if not r:
        raise Refused("그 판정이 없습니다")
    if r[4] is not None:
        return {"ok": False, "why": "이미 정한 판정입니다"}
    if action == "close" and r[0].startswith("p:"):
        await close(engine, int(r[0][2:]), "done", f"[갱신] 조사 세션 {r[1]}: {r[2] or ''} {('— ' + r[3]) if r[3] else ''}".strip())
    async with engine.begin() as c:
        await c.execute(text("UPDATE postit_check SET resolved = :a, resolved_at = UTC_TIMESTAMP(3) WHERE id = :i AND resolved IS NULL"),
                        {"a": "closed" if action == "close" else "kept", "i": cid})
    return {"ok": True}


# ── 한 프로젝트 요약(머리 탭 · 서기실 · 서기 할 일) ─────────────
async def summary(engine: Any, project: str, since: datetime | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    posts = await items(engine, project)
    runs = await _runs(engine, project)
    last = runs[0] if runs else None
    last_ok = next((r for r in runs if r["done"] and r["done"]["ok"]), None)
    cks = await checks(engine, project)
    oldest = posts[0]["created_at"] if posts else None
    run_state = None
    if last:
        run_state = {"session_id": last["session_id"], "at": last["at"],
                     "state": "running" if last["done"] is None else "done" if last["done"]["ok"] else "failed",
                     "detail": (last["done"] or {}).get("detail")}
    return {"open": len(posts), "unconfirmed": sum(not x["confirmed"] for x in posts),
            "oldest_at": oldest, "oldest_days": (now - oldest).days if oldest else 0,
            "likely_done": sum(k["verdict"] == "done" for k in cks),
            "recommend": sum(bool(k["coder"]) for k in cks if k["item"].startswith("p:")),
            "limit_pending": len(await limit_pending(engine, project)),
            "readme_drop": len(await readme_drop_pending(engine, project, since)),
            "check": run_state, "last_check_at": last_ok["at"] if last_ok else None,
            "nudge": nudge_of(len(posts), oldest, last_ok["at"] if last_ok else None, now=now)}


# ── 그물 훑기 ────────────────────────────────────────────────
_NET_SQL = ("SELECT t.id, t.prompt_text, p.name AS project FROM turn t JOIN character_session cs ON cs.id = t.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE t.origin = 'human' AND cs.hidden_at IS NULL AND t.started_at >= :cut "
            "AND (t.ended_at IS NOT NULL OR t.started_at < :wait) "
            "AND NOT EXISTS (SELECT 1 FROM todo_inbox i WHERE i.source_ref = CONCAT('t:', t.id)) "
            # 띄운 세션의 첫 턴 = 띄울 때 넣은 일감 글(438 1-2, 40턴 모두 이것). 역할로 빼지 않는다
            "AND NOT (t.seq = (SELECT MIN(t2.seq) FROM turn t2 WHERE t2.session_id = t.session_id) "
            "  AND EXISTS (SELECT 1 FROM session_action a WHERE a.action = 'spawn' AND a.ok "
            "              AND a.detail LIKE CONCAT('%새 세션 행 ', t.session_id))) "
            "ORDER BY t.id")


async def net_cutoff(engine: Any) -> datetime | None:
    """그물이 보기 시작하는 때 — 0033이 적용된 시각. 그 전 말은 서기가 README 표로 이미 옮겼다(다시 올리면 겹친다)."""
    async with engine.connect() as c:
        return (await c.execute(text("SELECT applied_at FROM schema_migrations WHERE version LIKE '0033%' LIMIT 1"))).scalar()


async def candidates(engine: Any, since: datetime | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """그물에 걸리는 턴(아직 포스트잇이 없는 것) — {id, project, hits}."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    cut = since or await net_cutoff(engine)
    if cut is None:
        return []
    async with engine.connect() as c:
        rows = (await c.execute(text(_NET_SQL), {"cut": cut, "wait": now - NET_WAIT})).mappings().all()
    return [{"id": r["id"], "project": r["project"], "hits": h} for r in rows if (h := net_hits(r["prompt_text"]))]


async def sweep(engine: Any, since: datetime | None = None, now: datetime | None = None) -> int:
    """그물 — 사람이 미루자고 했는데 포스트잇이 없는 턴을 「확인 전」으로 올린다. 올린 수."""
    n = 0
    for x in await candidates(engine, since, now):
        r = await add(engine, x["project"], "\n".join(x["hits"][:3]), "chat", f"t:{x['id']}", confirmed=False)
        n += r["created"]
    return n


async def run(engine: Any, m: Any, every: float = 120.0, on_change: Any = None) -> None:
    """브리지 안 주기 일 — 그물 훑기 · [갱신] 결과 받기. 실패는 로그로 남기고 다음 차례에 다시 한다."""
    first = True
    while True:
        try:
            cut = await net_cutoff(engine)
            since = None if first or cut is None else max(cut, datetime.now(UTC).replace(tzinfo=None) - NET_WINDOW)
            got = await sweep(engine, since)
            got += await collect(m, engine) if m is not None else 0
            first = False
            if got and on_change:
                on_change()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("포스트잇 훑기 실패")
        await asyncio.sleep(every)
