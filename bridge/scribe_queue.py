"""서기실 전체 줄(11-19 사용자 결정). 「포트폴리오 쓰기」와 「기술문서 쓰기」의 [전체]. 표는 migrations/0035.

편을 한꺼번에 띄우지 않고 줄을 세워 한 편씩 돈다. 까닭 둘(사용자): 쓰기는 글을 고치는 일이라 두 편이 같은 줄을 각자 고칠 수 있다
(펫퍼민트 B에서 09편과 12편이 같은 줄을 각자 골랐다). 편마다 사람이 정할 거리가 올라오는데 한꺼번에 쏟아지면 볼 수 없다.

- 한 편이 끝남 = 그 편 세션의 브랜치가 main에 합쳐졌을 때. 다음 편 서기는 앞 편의 고침이 든 main 위에서 시작한다
  (worktree는 띄울 때 main의 지금 커밋에서 갈라진다, bridge/worktree.py create)
- 실패 셋: 세션이 커밋 없이 끝남, 합치기 카드에 문서 점검 틀림이 있음, 카드를 미룸(skip). 실패 목록에 넣고 다음 편으로 넘어간다.
  띄우지 못한 편(같은 편이 이미 열려 있음 등, scribe_room.blocked 그대로)도 실패로 넣고 넘어간다
- 사람 승인 파일을 건드린 편(카드가 사람 승인): 기다리지 않고 「미룬 것」으로 넣고 넘어간다. 사람이 나중에 모아서 누른다
- 합치기 가름(줄이 띄운 세션만, bridge/mergeprep.py prep): 바뀐 파일이 그 편 원고 하나와 기록 폴더뿐이고 문서 점검 새 틀림 0이면
  카드 없이 합친다(승인자 auto, 조사 세션 log 길과 한 벌). 코드 파일이 섞이면 지금처럼 카드(관리자가 시험 뒤 합친다)
- 멈추기: 지금 편이 끝나면 다음 편을 띄우지 않는다. 판단거리(편마다 마지막 응답의 「사람이 정할 것」)는 모았다가 줄이 끝나면 보인다
- 줄은 한 프로젝트에 하나(포트폴리오와 기술문서가 이 한 벌을 나눠 쓴다). 브리지가 다시 떠도 DB에서 이어진다
- 조용한 고장 금지: 지금 편이 STALL_MIN분 넘게 안 끝나면 화면에 「오래 안 끝남」과 텔레그램 한 번. 띄우기가 거부가 아닌 까닭으로
  실패하면 줄을 멈추고 알린다(38편이 같은 까닭으로 줄줄이 실패하지 않게)
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from bridge import worktree as wt
from bridge.inject import Refused
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.scribe_queue")

NOTIFY_KIND = "squeue"       # notification.kind(8자까지)
STALL_MIN = 60               # 지금 편이 이만큼(분) 넘게 안 끝나면 「오래 안 끝남」. 한 편 고쳐 쓰기는 보통 이보다 짧다(log 참고)
NOCOMMIT_GRACE_S = 120.0     # 살아 있는 세션이 커밋 없이 일을 마친 채 이만큼(초) 그대로면 「커밋 없이 끝남」으로 본다
START_GRACE_S = 180.0       # 띄운 뒤 이만큼(초)은 그물이 그 편을 보지 않는다
EVERY_S = 60.0              # 그물(놓친 합침, 커밋 없이 끝남, 오래 안 끝남, 브리지를 다시 띄운 뒤 이어가기)
DECISIONS_MAX = 3000
ACTIVE = ("running", "paused")
STATE_KO = {"running": "도는 중", "paused": "멈춤", "done": "끝남", "closed": "닫음"}

# 줄 세션 일감에 덧붙는 약속(scribe_room.task_prompt가 extra["queue"]로 붙인다)
QUEUE_RULES = """줄로 띄운 세션(서기실 [전체])
- 이 세션은 서기실 전체 줄이 띄운 편 하나다. 이 편이 main에 합쳐져야 다음 편이 뜬다. 오래 붙잡지 말고 이 편만 고친다
- 사람에게 묻고 기다리지 않는다. 정해야 할 것은 마지막 응답 끝에 `## 사람이 정할 것` 절로 적고 끝낸다(줄이 끝나면 사람이 한 번에 본다)
- 이 편 원고(와 `log/` 기록)만 바꾸고 문서 점검 틀림이 없으면 카드 없이 합쳐진다. 다른 파일을 바꾸면 합치기 카드로 가서 사람이나 관리자를 기다린다
- 고칠 것이 없으면 커밋하지 않고 끝내도 된다(줄은 그 편을 실패 목록에 넣고 넘어간다). 그때도 까닭을 마지막 응답에 적는다"""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(v: Any) -> Any:
    return v.isoformat() + "Z" if isinstance(v, datetime) else v


# ── 순수 판정 ────────────────────────────────────────────
def piece_file(task: str, topic: str) -> str:
    """그 편 원고 파일 하나(합치기 가름의 「원고 하나」). 포트폴리오 그림(portfolio/img/)은 넣지 않는다. 화면 사진은 사람이 본다."""
    from bridge.scribe_room import PIECE_TASKS
    return f"{PIECE_TASKS[task]['dir']}{topic}.md"


def piece_only_why(changes: list[dict[str, str]], task: str, topic: str, records: list[str]) -> str | None:
    """줄 세션 카드를 승인 없이 합쳐도 되나(파일만 본다). 바뀐 파일이 그 편 원고(더함, 고침)와 기록 폴더(records, 지우기는
    늘-사람 판정이 따로 잡는다)뿐이면 None, 아니면 까닭. 「짝 표」로 따로 받는 파일은 없다: 노션 짝(doc_publish)은 DB 표이고
    번호 짝(pair_numbers)은 `.foreman/docs.toml` 칸이라 저장소 파일로 바뀌지 않는다(log/foreman-4_scribe_queue_20261119.md)."""
    if not changes:
        return "바뀐 파일이 없습니다"
    mine = piece_file(task, topic)
    pfx = tuple(r if r.endswith("/") else r + "/" for r in records or ["log/"])
    others, gone = [], []
    for ch in changes:
        p = ch["path"]
        if p == mine:
            if ch["status"] not in ("A", "M"):
                gone.append(p)
        elif not p.startswith(pfx):
            others.append(p)
    if gone:
        return "원고를 지웠습니다: " + ", ".join(gone)
    if others:
        return ("그 편 원고와 기록 밖 파일이 바뀌었습니다: " + ", ".join(others[:5])
                + (f" 외 {len(others) - 5}개" if len(others) > 5 else ""))
    if not any(ch["path"] == mine for ch in changes):
        return f"그 편 원고({mine})가 바뀌지 않았습니다"
    return None


_DEC_HEAD = re.compile(r"^\s*(?:#{1,6}\s*|\*\*|\d+\.\s*)?「?사람이 정할 것」?\**\s*:?\s*$", re.M)


def decisions_of(reply: str) -> str:
    """마지막 응답에서 「사람이 정할 것」 절. 머리 줄 뒤 끝까지(다음 같은 깊이 머리가 오면 거기까지). 없으면 빈 글."""
    if not reply:
        return ""
    ms = list(_DEC_HEAD.finditer(reply))
    if not ms:
        return ""
    body = reply[ms[-1].end():]
    nxt = re.search(r"^\s*#{1,6}\s", body, re.M)
    if nxt:
        body = body[:nxt.start()]
    body = body.strip()
    if re.fullmatch(r"[\s\-*]*(없음|없다|없습니다)\.?", body):
        return ""
    return body[:DECISIONS_MAX]


def counts(items: list[dict[str, Any]]) -> dict[str, int]:
    c = {k: 0 for k in ("waiting", "running", "merged", "auto", "card", "failed", "held", "decisions")}
    for it in items:
        c[it["state"]] = c.get(it["state"], 0) + 1
        if it["state"] == "merged":
            c["auto" if it.get("how") == "auto" else "card"] += 1
        if it.get("decisions"):
            c["decisions"] += 1
    return c


# ── 보기 ────────────────────────────────────────────────
async def _queue_rows(c: Any, qid: int) -> list[dict[str, Any]]:
    rows = (await c.execute(text(
        "SELECT id, pos, topic, title, state, session_id, how, reason, decisions, started_at, ended_at "
        "FROM scribe_queue_item WHERE queue_id = :q ORDER BY pos"), {"q": qid})).mappings().all()
    return [dict(r) for r in rows]


async def view(engine: Any, project: str) -> dict[str, Any] | None:
    """화면에 내릴 줄. 그 프로젝트의 닫히지 않은 마지막 줄. 없으면 None. 판단거리와 미룬 것은 줄이 끝났을 때만 글까지 내린다
    (도는 동안은 수만, 사용자: 줄이 끝나면 한 번에)."""
    try:
        async with engine.connect() as c:
            q = (await c.execute(text(
                "SELECT id, task, state, note, created_at, ended_at FROM scribe_queue WHERE project = :p AND state <> 'closed' "
                "ORDER BY id DESC LIMIT 1"), {"p": project})).mappings().first()
            if q is None:
                return None
            items = await _queue_rows(c, q["id"])
    except Exception as e:  # noqa: BLE001, 0035 전 DB 등. 0으로 보이지 않게 까닭을 내린다
        return {"error": f"줄을 읽지 못했습니다({type(e).__name__})"}
    now = _now()
    cur = next((i for i in items if i["state"] == "running"), None)
    done = q["state"] == "done"
    out_items = []
    for i in items:
        d = {k: _iso(i[k]) for k in ("id", "pos", "topic", "title", "state", "session_id", "how", "reason", "started_at", "ended_at")}
        d["has_decisions"] = bool(i["decisions"])
        if done:
            d["decisions"] = i["decisions"] or ""
        out_items.append(d)
    run_min = int((now - cur["started_at"]).total_seconds() // 60) if cur and cur["started_at"] else None
    return {"id": int(q["id"]), "task": q["task"], "state": q["state"], "state_ko": STATE_KO.get(q["state"], q["state"]),
            "note": q["note"], "created_at": _iso(q["created_at"]), "ended_at": _iso(q["ended_at"]),
            "items": out_items, "counts": counts(items),
            "current": ({"topic": cur["topic"], "title": cur["title"], "session_id": cur["session_id"], "reason": cur["reason"],
                         "minutes": run_min, "stalled": run_min is not None and run_min >= STALL_MIN} if cur else None),
            "stall_min": STALL_MIN}


# ── 줄 ─────────────────────────────────────────────────
class ScribeQueue:
    """줄을 돌리는 것. handoff(HandoffManager, spawn_new와 worktree_act), mergeprep(카드 가름과 approve)를 쓴다.
    main.py가 handoff.scribe_queue와 mergeprep.queue에 잇는다."""

    def __init__(self, handoff: Any, publishers: Any = None, notifier: Any = None, on_change: Any = None) -> None:
        self.h, self.engine, self.sessions_dir = handoff, handoff.engine, handoff.sessions_dir
        self.publishers = publishers or (lambda: None)
        self.notifier, self.on_change = notifier, on_change
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._task: asyncio.Task[Any] | None = None
        self._idle_seen: dict[int, float] = {}       # 세션 → 커밋 없이 일을 마친 것을 처음 본 때(loop 시각)
        self.health: dict[str, Any] = {"ok": True, "last": None, "error": None}
        mp = getattr(handoff, "mergeprep", None)
        if mp is not None:
            mp.queue = self
        handoff.scribe_queue = self

    @property
    def mp(self) -> Any:
        return getattr(self.h, "mergeprep", None)

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

    def _spawn(self, coro: Any) -> None:
        t = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ── 사람 단추 ──
    async def begin(self, project: str, task: str, topics: list[str] | None = None) -> dict[str, Any]:
        """줄을 세운다. topics를 안 주면 코드가 바뀐 편(머리 주석을 읽지 못한 편 포함)을 파일 차례로. 바로 첫 편을 띄운다."""
        from bridge import scribe_room as sr
        if task not in sr.PIECE_TASKS:
            raise Refused("전체 줄은 포트폴리오 쓰기와 기술문서 쓰기만 됩니다")
        if self.mp is None:
            raise Refused("합치기 준비가 꺼져 있어 줄을 돌릴 수 없습니다. 한 편이 끝났는지(합쳐졌는지) 알 길이 없습니다")
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :p"), {"p": project})).first()
            act = (await c.execute(text("SELECT id, task FROM scribe_queue WHERE project = :p AND state IN ('running', 'paused') LIMIT 1"),
                                   {"p": project})).first()
        if act is not None:
            raise Refused(f"이 프로젝트에는 이미 도는 줄이 있습니다({sr.TASKS[act[1]]['title']}, 줄 {act[0]}). 끝나거나 닫은 뒤에 세웁니다")
        repo = r[0] if r else None
        if not repo:
            raise Refused("이 프로젝트의 저장소를 찾지 못했습니다")
        sr.piece_task_ok(task, project, repo, self.publishers())
        whole = [o for o in await sr.open_tasks(self.engine, project) if o["task"] == task and not o.get("topic")]
        if whole:
            raise Refused(f"「{sr.TASKS[task]['title']}」 통째 쓰기가 열려 있습니다(세션 {whole[0]['session_id']}). 모든 편이 막히니 합치거나 버린 뒤에 세웁니다")
        tps = sr.topics(repo, task)
        if topics:
            byslug = {t["slug"]: t for t in tps}
            miss = [t for t in topics if t not in byslug]
            if miss:
                raise Refused(f"{sr.PIECE_TASKS[task]['label']}을 찾지 못했습니다: {', '.join(miss[:5])}")
            pick = [byslug[t] for t in dict.fromkeys(topics)]
        else:
            pick = [t for t in tps if t["commits"] != 0]
        if not pick:
            raise Refused("고쳐 쓸 편이 없습니다(코드가 바뀐 편이 없습니다)")
        async with self.engine.begin() as c:
            qid = (await c.execute(text("INSERT INTO scribe_queue (project, task, state) VALUES (:p, :t, 'running')"),
                                   {"p": project, "t": task})).lastrowid
            for i, t in enumerate(pick):
                await c.execute(text("INSERT INTO scribe_queue_item (queue_id, pos, topic, title, state) VALUES (:q, :i, :s, :ti, 'waiting')"),
                                {"q": qid, "i": i, "s": t["slug"], "ti": (t["title"] or t["slug"])[:300]})
        await self.advance(project)
        return {"queue_id": int(qid), "items": len(pick)}

    async def _set_state(self, qid: int, want: str, allow: tuple[str, ...], note: str | None = None) -> dict[str, Any]:
        async with self.engine.begin() as c:
            row = (await c.execute(text("SELECT project, state FROM scribe_queue WHERE id = :q"), {"q": qid})).first()
            if row is None:
                raise Refused("그 줄이 없습니다")
            if row[1] not in allow:
                raise Refused(f"지금 줄 상태({STATE_KO.get(row[1], row[1])})에서는 할 수 없습니다")
            await c.execute(text("UPDATE scribe_queue SET state = :s, note = :n WHERE id = :q"), {"s": want, "n": note, "q": qid})
        self._changed()
        return {"project": row[0], "state": want}

    async def pause(self, qid: int) -> dict[str, Any]:
        r = await self._set_state(qid, "paused", ("running",), "멈추기: 지금 편이 끝나면 다음 편을 띄우지 않습니다")
        return {**r, "note": "멈췄습니다. 지금 도는 편은 끝까지 돌고, 다음 편은 띄우지 않습니다."}

    async def resume(self, qid: int) -> dict[str, Any]:
        r = await self._set_state(qid, "running", ("paused",))
        await self.advance(r["project"])
        return {**r, "note": "이어 갑니다."}

    async def close(self, qid: int) -> dict[str, Any]:
        """끝난 줄(또는 멈춘 줄)을 화면에서 치운다. 멈춘 줄을 닫으면 남은 편은 띄우지 않는다. 지금 도는 편 세션은 건드리지 않는다."""
        r = await self._set_state(qid, "closed", ("done", "paused"))
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE scribe_queue SET ended_at = COALESCE(ended_at, UTC_TIMESTAMP(3)) WHERE id = :q"), {"q": qid})
        return {**r, "note": "줄을 닫았습니다."}

    # ── 줄 돌리기 ──
    async def running_item(self, sid: int) -> dict[str, Any] | None:
        """이 세션이 줄이 띄워 지금 도는 편이면 {item_id, queue_id, project, task, topic, title}. 합치기 준비가 부른다."""
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT i.id, q.id, q.project, q.task, i.topic, i.title FROM scribe_queue_item i JOIN scribe_queue q ON q.id = i.queue_id "
                "WHERE i.session_id = :s AND i.state = 'running' ORDER BY i.id DESC LIMIT 1"), {"s": sid})).first()
        if r is None:
            return None
        return {"item_id": int(r[0]), "queue_id": int(r[1]), "project": r[2], "task": r[3], "topic": r[4], "title": r[5]}

    async def advance(self, project: str) -> None:
        """도는 줄에 지금 편이 없으면 다음 편을 띄운다. 띄우지 못한 편(거부)은 실패로 넣고 다음 편. 남은 편이 없으면 줄을 끝낸다."""
        from bridge import scribe_room as sr
        async with self._lock:
            while True:
                async with self.engine.connect() as c:
                    q = (await c.execute(text(
                        "SELECT id, task, state FROM scribe_queue WHERE project = :p AND state IN ('running', 'paused') ORDER BY id DESC LIMIT 1"),
                        {"p": project})).first()
                    if q is None:
                        return
                    items = await _queue_rows(c, q[0])
                if any(i["state"] == "running" for i in items):
                    return
                nxt = next((i for i in items if i["state"] == "waiting"), None)
                if nxt is None:
                    await self._finish_queue(project, int(q[0]), q[1], items)
                    return
                if q[2] != "running":
                    return                                     # 멈춤. 지금 편이 끝났으니 여기서 선다
                try:
                    res = await sr.start(self.h, self.engine, project, q[1], nxt["topic"], publishers=self.publishers(), queue=int(q[0]))
                except Refused as e:
                    await self._end_item(nxt["id"], "failed", f"띄우지 못했습니다: {e}")
                    continue
                except Exception as e:  # noqa: BLE001, 같은 까닭으로 줄줄이 실패하지 않게 줄을 멈추고 알린다
                    why = f"편 「{nxt['title']}」을 띄우다 실패해 줄을 멈췄습니다: {type(e).__name__}: {str(e)[:160]}"
                    log.warning(why)
                    await self._set_state(int(q[0]), "paused", ("running",), why)
                    self._notify(project, f"squeue:spawn:{nxt['id']}", f"⚠ 서기실 전체 줄: {why}", later=False)
                    return
                sid = res.get("session_id")
                if not sid:
                    why = f"편 「{nxt['title']}」 세션이 떴는지 알 수 없어 줄을 멈췄습니다({res.get('note') or '세션 번호 없음'})"
                    await self._set_state(int(q[0]), "paused", ("running",), why)
                    self._notify(project, f"squeue:nosid:{nxt['id']}", f"⚠ 서기실 전체 줄: {why}", later=False)
                    return
                async with self.engine.begin() as c:
                    await c.execute(text("UPDATE scribe_queue_item SET state = 'running', session_id = :s, started_at = UTC_TIMESTAMP(3), "
                                         "reason = '서기가 고쳐 쓰는 중' WHERE id = :i"), {"s": sid, "i": nxt["id"]})
                self._changed()
                return

    async def _finish_queue(self, project: str, qid: int, task: str, items: list[dict[str, Any]]) -> None:
        async with self.engine.begin() as c:
            n = (await c.execute(text("UPDATE scribe_queue SET state = 'done', ended_at = UTC_TIMESTAMP(3) WHERE id = :q AND state IN ('running', 'paused')"),
                                 {"q": qid})).rowcount
        if not n:
            return
        k = counts(items)
        from bridge import scribe_room as sr
        msg = (f"서기실 전체 줄({sr.TASKS[task]['title']})이 끝났습니다: 합침 {k['merged']}(카드 없이 {k['auto']}, 카드로 {k['card']}), "
               f"실패 {k['failed']}, 미룸 {k['held']}, 판단거리 {k['decisions']}편. 서기실에서 한 번에 봅니다")
        self._notify(project, f"squeue:done:{qid}", msg)
        self._changed()

    async def _end_item(self, item_id: int, state: str, reason: str | None, how: str | None = None) -> bool:
        async with self.engine.begin() as c:
            n = (await c.execute(text(
                "UPDATE scribe_queue_item SET state = :st, reason = :r, how = :h, ended_at = UTC_TIMESTAMP(3) WHERE id = :i AND state IN ('waiting', 'running')"),
                {"st": state, "r": (reason or None) and reason[:1000], "h": how, "i": item_id})).rowcount
        if n:
            self._changed()
        return bool(n)

    async def _finish(self, sid: int, state: str, reason: str | None, how: str | None = None) -> bool:
        """도는 편을 끝낸다(merged, failed, held). 판단거리를 아직 안 읽었으면 읽는다. 그리고 다음 편으로."""
        it = await self.running_item(sid)
        if it is None:
            return False
        await self._grab_decisions(it["item_id"], sid)
        ok = await self._end_item(it["item_id"], state, reason, how)
        self._idle_seen.pop(sid, None)
        if ok:
            await self.advance(it["project"])
        return ok

    async def _grab_decisions(self, item_id: int, sid: int) -> None:
        try:
            async with self.engine.connect() as c:
                have = (await c.execute(text("SELECT decisions FROM scribe_queue_item WHERE id = :i"), {"i": item_id})).scalar()
            if have:
                return
            d = decisions_of(await self._last_reply(sid))
            if d:
                async with self.engine.begin() as c:
                    await c.execute(text("UPDATE scribe_queue_item SET decisions = :d WHERE id = :i"), {"d": d, "i": item_id})
        except Exception as e:  # noqa: BLE001, 판단거리를 못 읽어도 줄은 간다. 다만 그렇다고 남긴다
            log.warning("줄 편 %s 판단거리 읽기 실패: %s", item_id, type(e).__name__)
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE scribe_queue_item SET decisions = :d WHERE id = :i AND decisions IS NULL"),
                                {"d": f"(마지막 응답을 읽지 못했습니다: {type(e).__name__}. 세션 {sid} 패널에서 봅니다)", "i": item_id})

    async def _last_reply(self, sid: int) -> str:
        async with self.engine.connect() as c:
            t = (await c.execute(text(
                "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE session_id = :s AND type = 'assistant_msg' "
                "AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' ORDER BY id DESC LIMIT 1"),
                {"s": sid})).scalar()
        if not t or t == "null":
            return ""
        from bridge.mask import Masker
        return Masker().text(t)

    # ── 합치기 준비와 handoff가 알린다 ──
    async def on_card(self, sid: int, kind: str, why: str | None) -> None:
        """합치기 준비가 줄 세션 카드를 갈랐다. auto(카드 없이 합칠 것, 합친 뒤 merged), card(카드로 기다림), fail, held."""
        it = await self.running_item(sid)
        if it is None:
            return
        await self._grab_decisions(it["item_id"], sid)
        if kind == "fail":
            await self._finish(sid, "failed", why)
        elif kind == "held":
            await self._finish(sid, "held", why)
        else:
            reason = "카드 없이 합치는 중" if kind == "auto" else why or "합치기 카드를 기다립니다"
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE scribe_queue_item SET reason = :r WHERE id = :i AND state = 'running'"),
                                {"r": reason[:1000], "i": it["item_id"]})
            self._changed()

    async def auto_merge(self, sid: int) -> None:
        """승인자 auto 줄 카드를 합친다(조사 세션 log 길과 같은 approve(by=auto)). 결과는 handoff → on_worktree가 받는다.
        못 합치면(충돌 넘김, 실패) mergeprep가 알리고 카드로 남는다. 줄은 그 편 카드를 기다린다(그물이 오래 안 끝남을 본다)."""
        mp = self.mp
        if mp is None:
            return
        try:
            r = await mp.approve(sid, by="auto")
        except Refused as e:
            r = {"ok": False, "note": str(e)}
        if not r.get("ok"):
            it = await self.running_item(sid)
            if it is not None:
                async with self.engine.begin() as c:
                    await c.execute(text("UPDATE scribe_queue_item SET reason = :r WHERE id = :i AND state = 'running'"),
                                    {"r": f"카드 없이 합치지 못해 카드로 남았습니다: {r.get('note') or r.get('status')}"[:1000], "i": it["item_id"]})
                self._changed()

    def on_worktree(self, sid: int, act: str, res: dict[str, Any]) -> None:
        """handoff.worktree_act 끝(합침, 버림). 카드 승인자가 auto였으면 카드 없이 합친 것이다(그 판정은 지금 메모리 카드에 있다)."""
        if not res.get("ok"):
            return
        c = (self.mp.cards.get(sid) if self.mp is not None else None)
        how = "auto" if c is not None and c.approved_by == "auto" else "card"

        async def go() -> None:
            try:
                if act == "merge":
                    await self._finish(sid, "merged", None, how)
                else:
                    await self._finish(sid, "failed", "작업방을 버렸습니다")
            except Exception as e:  # noqa: BLE001, 그물이 다시 본다
                log.warning("줄 편 끝 받기 실패(세션 %s): %s", sid, type(e).__name__)
        self._spawn(go())

    async def on_skip(self, sid: int) -> None:
        await self._finish(sid, "failed", "합치기 카드를 미뤘습니다([나중에])")

    # ── 그물 ──
    async def tick(self, only: str | None = None) -> None:
        """도는 줄마다 지금 편을 다시 본다(놓친 합침, 버림, 커밋 없이 끝남, 카드 없이 못 합친 것, 오래 안 끝남). 지금 편이 없으면 다음 편.
        only: 그 프로젝트 줄만(시험이 같은 시험 DB의 다른 줄을 건드리지 않게)."""
        async with self.engine.connect() as c:
            qs = (await c.execute(text(
                "SELECT id, project, task, stall_told FROM scribe_queue WHERE state IN ('running', 'paused')"
                + (" AND project = :p" if only else "")), {"p": only})).all()
        for qid, project, task, told in qs:
            async with self.engine.connect() as c:
                items = await _queue_rows(c, qid)
            cur = next((i for i in items if i["state"] == "running"), None)
            if cur is None:
                await self.advance(project)
                continue
            try:
                await self._check_item(project, cur)
            except Exception as e:  # noqa: BLE001
                log.warning("줄 편 %s 보기 실패: %s", cur["id"], type(e).__name__)
                self.health["error"] = f"줄 편 {cur['id']}: {type(e).__name__}: {str(e)[:160]}"
            if cur["started_at"] and _now() - cur["started_at"] >= timedelta(minutes=STALL_MIN) and told != cur["id"]:
                async with self.engine.begin() as c:
                    await c.execute(text("UPDATE scribe_queue SET stall_told = :i WHERE id = :q"), {"i": cur["id"], "q": qid})
                self._notify(project, f"squeue:stall:{cur['id']}",
                             f"⚠ 서기실 전체 줄: 편 「{cur['title']}」(세션 {cur['session_id']})이 {STALL_MIN}분 넘게 끝나지 않습니다. "
                             f"지금: {cur['reason'] or '?'}. 서기실에서 봅니다", later=False)
                self._changed()

    async def _check_item(self, project: str, cur: dict[str, Any]) -> None:
        sid = cur["session_id"]
        if not sid or (cur["started_at"] and _now() - cur["started_at"] < timedelta(seconds=START_GRACE_S)):
            return                      # 막 띄운 세션은 CC가 살아 있다고 잡히기 전이다. 「커밋 없이 끝남」으로 잘못 보지 않게
        row = await self.h.session(sid)
        if row is None:
            await self._finish(sid, "failed", "세션을 찾지 못했습니다")
            return
        repo, name = wt.split(row.cwd or "")
        if not name:
            await self._finish(sid, "failed", "작업방(worktree) 세션이 아닙니다")
            return
        st = await wt.status(repo, name)
        if not st.get("exists"):
            merged = await self._merged_act(sid)
            if merged is not None:
                await self._finish(sid, "merged", None, merged)
            else:
                await self._finish(sid, "failed", "작업방이 없어졌습니다(버렸거나 밖에서 치웠습니다)")
            return
        mp = self.mp
        card = mp.cards.get(sid) if mp is not None else None
        if st["ahead"] > 0:
            if card is not None and card.status == "ready" and card.approver == "auto" and not self._busy_merge(sid):
                await self.auto_merge(sid)
            elif card is not None and card.status == "failed" and card.error:
                await self._finish(sid, "failed", f"합치기 준비 실패: {card.error}")
            return
        live = await asyncio.to_thread(live_sessions, self.sessions_dir)
        ls = live.get(row.cc or "")
        if ls is None:
            if st["dirty"]:
                await self._finish(sid, "failed", f"커밋 안 한 변경 {len(st['dirty'])}개를 남긴 채 끝났습니다(작업방은 그대로 둡니다)")
                return
            await self._finish(sid, "failed", "커밋 없이 끝났습니다")      # 먼저 끝낸다(버림 알림이 까닭을 덮지 않게)
            await self._discard(row, False)
            return
        if ls.state == "T" or mp is None:
            return
        done = await mp._done_live(sid, row.cc, ls.pid)
        loop = asyncio.get_running_loop()
        if not done:
            self._idle_seen.pop(sid, None)
            return
        first = self._idle_seen.setdefault(sid, loop.time())
        if loop.time() - first < NOCOMMIT_GRACE_S:
            return
        if st["dirty"]:
            await self._finish(sid, "failed", f"커밋하지 않고 일을 마쳤습니다(커밋 안 한 변경 {len(st['dirty'])}개, 세션과 작업방은 그대로 둡니다)")
            return
        await self._finish(sid, "failed", "커밋 없이 일을 마쳤습니다(세션을 끝내고 작업방을 지웠습니다)")
        await self._discard(row, True)

    def _busy_merge(self, sid: int) -> bool:
        c = self.mp.cards.get(sid) if self.mp is not None else None
        return c is not None and c.status == "merging"

    async def _discard(self, row: Any, end: bool) -> None:
        """커밋이 없는 줄 세션의 작업방을 치운다(잃을 것이 없다. 열린 일로 남아 그 편을 막지 않게). 못 치우면 까닭을 남긴다."""
        try:
            await self.h.worktree_act(row, "discard", end=end)
        except Exception as e:  # noqa: BLE001
            log.warning("줄 세션 %s 작업방 치우기 실패: %s", row.id, e)

    async def _merged_act(self, sid: int) -> str | None:
        """브리지가 다시 뜬 사이 합쳐졌나(session_action wt-merge). 합쳤으면 auto(카드 없이) 또는 card, 아니면 None."""
        async with self.engine.connect() as c:
            ok = (await c.execute(text("SELECT 1 FROM session_action WHERE session_id = :s AND action = 'wt-merge' AND ok LIMIT 1"),
                                  {"s": sid})).first()
            if not ok:
                return None
            d = (await c.execute(text("SELECT detail FROM session_action WHERE session_id = :s AND action = 'mprep-merge' AND ok "
                                      "ORDER BY id DESC LIMIT 1"), {"s": sid})).scalar()
        return "auto" if d and "승인 없이" in d else "card"

    # ── 알리기 ──
    def _notify(self, project: str | None, key: str, msg: str, later: bool | None = None) -> None:
        if self.notifier is None:
            return

        async def go() -> None:
            try:
                async with self.engine.connect() as cn:
                    if (await cn.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key[:64]})).first():
                        return
                rule = self.notifier.rules.for_project(project) if project else None
                prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
                self.notifier.send_direct(project, NOTIFY_KIND, None, f"{prefix} {msg}"[:3500], rule=key[:64],
                                          **({"later": later} if later is not None else {}))
            except Exception as e:  # noqa: BLE001
                log.warning("서기실 줄 알림 실패: %s", type(e).__name__)
        self._spawn(go())

    # ── 돌기 ──
    async def run(self) -> None:
        while True:
            try:
                async with asyncio.timeout(300):
                    await self.tick()
                self.health.update(ok=True, last=_iso(_now()))
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                why = f"서기실 줄 그물 실패: {type(e).__name__}: {str(e)[:160]}"
                log.warning(why)
                self.health.update(ok=False, error=why)
                self._notify("foreman", f"squeue:err:{_now():%Y%m%d%H}", f"⚠ {why}")
            await asyncio.sleep(EVERY_S)

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.get_running_loop().create_task(self.run(), name="foreman-scribe-queue")
        return self._task
