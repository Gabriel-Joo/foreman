"""조사 세션 스스로 끝내기(11-15 사용자: 「조사는 읽고 알려 주는 것이 전부라 끝나면 남을 까닭이 없다」).

조사(inspector) 세션이 결과를 보고하고 턴을 마치면 브리지가 세션을 끝낸다. 다른 역할(코더, 디자이너, 서기, 관리자)은 그대로다.

- 결과를 보고했다(finished_why가 None): 턴 끝 신호 뒤 settle_s를 기다려 본다. 그 턴이 마지막 턴이고, 일하는 중이 아니고
  (busy 아님, 열린 턴 없음, 승인 대기 없음, 뒤에서 도는 일 없음), 응답이 있고, 권한 거부로 멈추지 않았고, 묻는 말이 없다.
  묻는 말은 마지막 응답의 물음(대시보드 「답 기다림」과 같은 판정)과 사람 답 기다림(escalate 물음)이다. 답을 받아야 하니 끝내지 않는다
- 작업방(worktree) 조사: 결과 log 커밋은 그 브랜치에만 있어 작업방을 그냥 버리면 사라진다. 합치기 준비(bridge/mergeprep.py)가
  바뀐 파일이 모두 log/ 새 파일이고 충돌, 묻는 말, 늘-사람 까닭이 없으면 승인자 auto 카드를 만든다. 여기서 approve(by="auto")를
  불러 세션을 끝내고 main에 합치고 작업방을 지운다(합치기 카드 approver를 거치지 않는 근거는 docs/11_worktree.md 「6-2.」).
  log 밖 파일이나 충돌이면 카드를 지금처럼 남기고 mergeprep가 까닭을 알린다. 커밋이 없으면 작업방만 버린다(잃을 것이 없다).
  커밋 안 한 변경이 있으면 끝내지 않고 알린다(log를 잃지 않게)
- 원본 폴더 조사(포스트잇 [갱신] 등): 커밋은 이미 main에 있다. 세션만 끝낸다. push는 관리자 몫이라 하지 않는다
- 포스트잇 [갱신] 세션이면 끝내기 전에 결과 블록을 먼저 읽는다(postit.collect). 트랜스크립트는 끝난 뒤에도 남지만 순서를 지킨다
- 턴 끝 알림(bridge/notify.py, 관리자에게 보고 넘기기)이 그 턴을 판정해 기록한 뒤(notification 줄) 끝낸다. 조사는 지금 넘기기
  대상 역할(WORKER_ROLES)이 아니지만 순서는 지킨다. relay_wait_s 안에 기록이 없어도 끝낸다(넘기기는 보낸 세션이 살아 있지 않아도 된다)
- 끝냈으면 관리자 세션에 한 번: 작업방이면 mergeprep의 합친 글, 원본 폴더이거나 커밋이 없으면 「작업 보고」 글
- 조용한 고장 금지: 끝내기, 합치기, 치우기가 실패하면 텔레그램 한 번 + 관리자 세션에 + session_action 'insp-close'에 사유
- 그물: every_s마다 살아 있는 조사 세션과, 끝난 세션의 auto 카드를 다시 본다(브리지를 다시 띄운 사이 턴이 끝난 것)
- 끄기: config/handoff.toml [inspector_close] enabled = false(칸이 없으면 켜짐, 프로젝트는 foreman만)
"""

from __future__ import annotations

import asyncio
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from bridge import worktree as wt
from bridge.inject import Refused, _status
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.inspector_close")

ACT = "insp-close"          # session_action(12자까지): ok = 끝냄, 0 = 못 끝냄(detail에 까닭)
NOTIFY_KIND = "insp"        # notification.kind(8자까지)
ROLE = "inspector"
WAIT = "wait"               # 답을 받아야 해서 안 끝냄(묻는 말, 사람 답 기다림, 권한 거부)
BUSY = "busy"               # 아직 일하는 중이라 안 끝냄(다음 턴 끝에서 다시 본다)


@dataclass
class InspectorCloseCfg:
    enabled: bool = True
    projects: list[str] = field(default_factory=lambda: ["foreman"])   # 비면 모든 프로젝트
    settle_s: float = 15.0      # 턴 끝 뒤 기다림. mergeprep 턴 끝 확인(3초, 10초)과 알림 판정(settle) 뒤에 보게
    relay_wait_s: float = 90.0  # 턴 끝 알림 기록을 기다리는 최대 시간
    every_s: float = 300.0      # 그물


def load(path: str | Path) -> InspectorCloseCfg:
    """config/handoff.toml [inspector_close]. 칸이 없으면 기본값(켜짐, foreman만)."""
    p = Path(path)
    raw = tomllib.loads(p.read_text(encoding="utf-8")).get("inspector_close", {}) if p.exists() else {}
    cfg = InspectorCloseCfg()
    if "enabled" in raw:
        cfg.enabled = bool(raw["enabled"])
    if "projects" in raw:
        cfg.projects = [str(x) for x in raw["projects"]]
    for k in ("settle_s", "relay_wait_s", "every_s"):
        if k in raw:
            setattr(cfg, k, float(raw[k]))
    if cfg.every_s < 30:
        raise ValueError(f"inspector_close.every_s는 30초 이상입니다(받은 값: {cfg.every_s})")
    return cfg


def finished_why(f: dict[str, Any]) -> tuple[str | None, str | None]:
    """조사 세션이 결과를 보고하고 쉬는가. (None, None)이면 끝내도 된다. 아니면 (까닭, WAIT 또는 BUSY).
    f: state, busy, open_turn, turn_id, last_turn, approval, replied, denied, asks, esc_q, work."""
    if f.get("state") == "T":
        return "사람이 멈춰 둔 세션입니다", BUSY
    if f.get("busy"):
        return "작업 중입니다", BUSY
    if f.get("open_turn"):
        return "턴이 열려 있습니다", BUSY
    if f.get("turn_id") and f.get("last_turn") and f["last_turn"] != f["turn_id"]:
        return "그 뒤 새 턴이 시작됐습니다", BUSY
    if f.get("approval"):
        return "승인 대기가 있습니다", BUSY
    if not f.get("replied"):
        return "응답이 없습니다", BUSY
    if f.get("work"):
        return "뒤에서 도는 일이 있습니다: " + ", ".join(f["work"][:3]), BUSY
    if f.get("denied"):
        return "권한 거부로 멈췄습니다", WAIT
    if f.get("asks"):
        return "묻는 말을 남겼습니다(답을 받아야 합니다)", WAIT
    if f.get("esc_q"):
        return "사람 답을 기다립니다", WAIT
    return None, None


class InspectorClose:
    def __init__(self, handoff: Any, cfg: InspectorCloseCfg, notifier: Any = None, on_change: Any = None) -> None:
        self.h, self.cfg, self.notifier, self.on_change = handoff, cfg, notifier, on_change
        self.engine, self.sessions_dir = handoff.engine, handoff.sessions_dir
        self._locks: dict[int, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._task: asyncio.Task[Any] | None = None
        self.health: dict[str, Any] = {"closed": 0, "kept": 0, "fail": 0, "error": None}
        self._alerted: set[str] = set()     # 관리자에게 알린 실패 열쇠(텔레그램은 DB 열쇠로 한 번)
        mp = getattr(handoff, "mergeprep", None)
        if mp is not None:
            mp.auto = self          # 합치기 준비가 조사 log 카드를 승인자 auto로 만들게

    def covers(self, project: str | None) -> bool:
        return self.cfg.enabled and (not self.cfg.projects or project in self.cfg.projects)

    # ── 턴 끝 ──
    def on_turn_closed(self, session_id: int, turn_id: int | None = None, *_: Any, **__: Any) -> None:
        """조립기가 턴을 닫은 직후(트랜잭션 안일 수 있다, 여기서는 예약만)."""
        if not self.cfg.enabled:
            return

        async def go() -> None:
            await asyncio.sleep(self.cfg.settle_s)
            await self._guarded(session_id, turn_id, "turn_end")
        self._spawn(go())

    async def _guarded(self, sid: int, turn_id: int | None, via: str) -> dict[str, Any]:
        try:
            async with asyncio.timeout(300):
                return await self.close(sid, turn_id, via)
        except Exception as e:  # noqa: BLE001 , 실패가 적재를 막지 않는다. 다만 조용히 넘어가지 않는다
            why = f"{type(e).__name__}: {str(e)[:200]}"
            await self._failed(sid, None, None, f"조사 세션 끝내기 확인이 실패했습니다: {why}", f"err:{sid}:{turn_id or via}")
            return {"closed": False, "why": why}

    def _spawn(self, coro: Any) -> None:
        t = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ── 판정 ──
    async def _who(self, sid: int) -> dict[str, Any] | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT cs.role, p.name, p.repo_path, cs.cwd, cs.cc_session_id, COALESCE(cs.custom_title, cs.title) "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.id = :s"), {"s": sid})).first()
        if r is None:
            return None
        return {"role": r[0], "project": r[1], "repo": r[2], "cwd": r[3], "cc": r[4], "title": r[5]}

    async def _facts(self, sid: int, turn_id: int | None, ls: Any) -> dict[str, Any]:
        from bridge.api.dashboard import human_needs
        f: dict[str, Any] = {"state": ls.state, "busy": _status(self.sessions_dir, ls.pid) == "busy", "turn_id": turn_id}
        async with self.engine.connect() as c:
            f["open_turn"] = bool((await c.execute(text(
                "SELECT 1 FROM turn WHERE session_id = :s AND ended_at IS NULL LIMIT 1"), {"s": sid})).first())
            f["last_turn"] = (await c.execute(text("SELECT MAX(id) FROM turn WHERE session_id = :s"), {"s": sid})).scalar()
            f["approval"] = bool((await c.execute(text(
                "SELECT 1 FROM approval WHERE session_id = :s AND status = 'pending' LIMIT 1"), {"s": sid})).first())
            f["replied"] = bool((await c.execute(text(
                "SELECT 1 FROM event WHERE session_id = :s AND type = 'assistant_msg' LIMIT 1"), {"s": sid})).first())
            needs = (await human_needs(c, f"({int(sid)})")).get(sid) or {}
        f["denied"] = bool(needs.get("denied"))
        f["asks"] = needs.get("asks")
        f["esc_q"] = (needs.get("escalate") or {}).get("question")
        row = await self.h.session(sid)
        f["work"] = await self.h._running_work(row, ls.pid) if row else []
        return f

    async def _wait_relay(self, turn_id: int | None) -> bool:
        """턴 끝 알림이 그 턴을 판정해 기록했나(관리자에게 넘기기가 끝났나). 알림이 꺼져 있으면 기다리지 않는다."""
        rules = getattr(self.notifier, "rules", None)
        if not turn_id or rules is None or not getattr(rules, "enabled", False):
            return True
        loop = asyncio.get_running_loop()
        end = loop.time() + self.cfg.relay_wait_s
        while True:
            async with self.engine.connect() as c:
                if (await c.execute(text("SELECT 1 FROM notification WHERE turn_id = :t AND kind = 'turn' LIMIT 1"),
                                    {"t": turn_id})).first():
                    return True
            if loop.time() >= end:
                log.warning("턴 %s 알림 기록을 %d초 기다렸지만 없다. 조사 세션은 끝낸다", turn_id, self.cfg.relay_wait_s)
                return False
            await asyncio.sleep(2.0)

    async def _postit_first(self, sid: int) -> None:
        """포스트잇 [갱신] 세션이면 결과 블록부터 읽는다(끝낸 뒤에도 트랜스크립트는 남지만, 끝내기 전에 읽어 두는 것이 순서)."""
        from bridge import postit
        if any(r["session_id"] == sid for r in await postit._runs(self.engine, open_only=True)):
            await postit.collect(self.h, self.engine)

    # ── 끝내기 ──
    async def close(self, sid: int, turn_id: int | None = None, via: str = "turn_end") -> dict[str, Any]:
        """조사 세션 하나를 보고 끝낼 수 있으면 끝낸다. 결과 {closed, why, how}."""
        lock = self._locks.setdefault(sid, asyncio.Lock())
        if lock.locked():
            return {"closed": False, "why": "이미 보는 중입니다"}
        async with lock:
            who = await self._who(sid)
            if who is None or who["role"] != ROLE or not self.covers(who["project"]):
                return {"closed": False, "why": "스스로 끝내는 조사 세션이 아닙니다"}
            ls = (await asyncio.to_thread(live_sessions, self.sessions_dir)).get(who["cc"] or "")
            repo, name = wt.split(who["cwd"] or "")
            if ls is None and not name:
                return {"closed": False, "why": "이미 끝난 세션입니다"}
            if ls is not None:
                why, kind = finished_why(await self._facts(sid, turn_id, ls))
                if why:
                    self.health["kept"] += 1
                    if kind == WAIT:
                        await self._demote(sid, why)
                    log.info("조사 세션 %s를 끝내지 않음(%s): %s", sid, via, why)
                    return {"closed": False, "why": why}
                await self._wait_relay(turn_id)
            row = await self.h.session(sid)
            if row is None:
                return {"closed": False, "why": "세션이 없습니다"}
            try:
                await self._postit_first(sid)
            except Exception as e:  # noqa: BLE001 , 결과 읽기는 다음 훑기가 다시 한다(트랜스크립트는 남는다)
                log.warning("조사 세션 %s 포스트잇 결과 먼저 읽기 실패: %s", sid, type(e).__name__)
            if not name:
                return await self._end_base(row, who, ls, turn_id)
            return await self._end_worktree(row, who, ls, repo, name, turn_id)

    async def _demote(self, sid: int, why: str) -> None:
        mp = getattr(self.h, "mergeprep", None)
        c = mp.cards.get(sid) if mp is not None else None
        if c is not None and c.approver == "auto" and c.status == "ready":
            await mp.demote_auto(c, why)

    async def _end_base(self, row: Any, who: dict[str, Any], ls: Any, turn_id: int | None) -> dict[str, Any]:
        """원본 폴더 조사: 세션만 끝낸다. 커밋은 이미 main에 있고 push는 관리자 몫이다."""
        try:
            r = await self.h.action(row, "exit")
        except Refused as e:
            r = {"ok": False, "note": str(e)}
        if not r.get("ok"):
            return await self._failed(row.id, who, ls, f"조사 세션을 끝내지 못했습니다: {r.get('note') or '?'}", f"exit:{row.id}:{turn_id}")
        await self.h._act(row.id, ACT, ls.pid if ls else None, True, "원본 폴더 조사, 세션만 끝냄")
        await self._report(who, row.id, "조사가 일을 마쳐 브리지가 세션을 끝냈습니다. 원본 폴더라 커밋은 이미 main에 있고 push는 관리자 몫입니다.")
        return self._done({"closed": True, "how": "exit"})

    async def _end_worktree(self, row: Any, who: dict[str, Any], ls: Any, repo: str, name: str,
                            turn_id: int | None) -> dict[str, Any]:
        st = await wt.status(repo, name)
        if not st.get("exists"):
            return {"closed": False, "why": "작업방이 없습니다"}
        key = f"{row.id}:{turn_id or st.get('ahead')}"
        if st["dirty"]:
            files = ", ".join(st["dirty"][:5])
            return await self._failed(row.id, who, ls, f"커밋 안 된 변경 {len(st['dirty'])}개가 있어 조사 세션을 끝내지 않았습니다"
                                      f"(log를 잃지 않게): {files}", f"dirty:{key}")
        if st["ahead"] == 0:
            try:
                res = await self.h.worktree_act(row, "discard", end=ls is not None)
            except Refused as e:
                res = {"ok": False, "note": str(e)}
            if not res.get("ok"):
                return await self._failed(row.id, who, ls, f"커밋이 없는 조사 작업방을 치우지 못했습니다: {res.get('note') or '?'}",
                                          f"discard:{key}")
            await self.h._act(row.id, ACT, ls.pid if ls else None, True, "작업방 조사, 커밋 없음, 끝내고 작업방을 지움")
            await self._report(who, row.id, "조사가 커밋 없이 일을 마쳐 브리지가 세션을 끝내고 작업방을 지웠습니다(합칠 것이 없었습니다).")
            return self._done({"closed": True, "how": "discard"})
        mp = getattr(self.h, "mergeprep", None)
        if mp is None:
            return await self._failed(row.id, who, ls, "합치기 준비가 꺼져 있어 조사 결과 log를 스스로 합치지 않았습니다. 세션은 그대로 둡니다",
                                      f"nomp:{key}")
        card = await mp.check_one(row.id, via="turn_end", with_hidden=True)
        if card is None:
            return await self._failed(row.id, who, ls, "합치기 카드를 만들지 못해 조사 세션을 끝내지 않았습니다(나중에로 미뤘거나 일을 마친 상태가 아닙니다)",
                                      f"nocard:{key}")
        if card.status != "ready" or card.approver != "auto":
            # log 밖 파일, 충돌 등. 카드는 지금처럼 남고 까닭은 mergeprep가 알렸다(auto_why)
            return {"closed": False, "why": card.auto_why or f"카드 상태 {card.status}"}
        try:
            r = await mp.approve(row.id, by="auto")
        except Refused as e:
            return await self._failed(row.id, who, ls, f"조사 결과 log를 스스로 합치지 못했습니다: {e}", f"merge:{key}")
        if not r.get("ok"):
            # 충돌(관리자에게 넘김), 합치기 실패(텔레그램) 모두 mergeprep가 알렸다. 기록만
            await self.h._act(row.id, ACT, None, False, f"합치지 못함: {r.get('note') or r.get('status')}"[:500])
            return {"closed": False, "why": r.get("note") or r.get("status")}
        await self.h._act(row.id, ACT, None, True, f"작업방 조사, log {len(card.files)}개를 main에 합치고 끝냄")
        return self._done({"closed": True, "how": "merge"})

    def _done(self, res: dict[str, Any]) -> dict[str, Any]:
        self.health["closed"] += 1
        if self.on_change:
            self.on_change()
        return res

    # ── 알리기 ──
    async def _last_reply(self, sid: int) -> str:
        async with self.engine.connect() as c:
            t = (await c.execute(text(
                "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE session_id = :s AND type = 'assistant_msg' "
                "AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' ORDER BY id DESC LIMIT 1"),
                {"s": sid})).scalar()
        if not t or t == "null":
            return ""
        mask = getattr(self.notifier, "mask", None)
        if mask is None:
            from bridge.mask import Masker
            mask = Masker()
        return mask.text(t)[-800:]

    async def _tell(self, who: dict[str, Any] | None, msg: str) -> bool:
        mp = getattr(self.h, "mergeprep", None)
        repo = (who or {}).get("repo")
        if mp is None or not repo:
            return False
        m = await mp.manager_of(repo)
        return bool(m) and await mp._deliver(m[0], m[1], msg)

    async def _report(self, who: dict[str, Any], sid: int, what: str) -> None:
        """관리자에게 「작업 보고」 한 번(출처 relay로 잡힌다, bridge/assembler.py RELAY_HEADS). 못 넣으면 텔레그램."""
        from bridge.managers import RELAY_REPORT
        tail = await self._last_reply(sid)
        msg = (f"{RELAY_REPORT}세션 {sid} 「{who.get('title') or ''}」(조사) → {who.get('project')} 관리자]\n{what}\n"
               + (f"마지막 응답 끝:\n{tail}\n" if tail else "") + "(답하지 않아도 됩니다)")
        if not await self._tell(who, msg):
            self._notify(who.get("project"), sid, f"insp:told:{sid}", f"조사 세션 {sid}를 끝냈지만 관리자 세션에 알리지 못했습니다. {what}")

    async def _failed(self, sid: int, who: dict[str, Any] | None, ls: Any, why: str, key: str) -> dict[str, Any]:
        """못 끝냄: session_action에 사유, 텔레그램 한 번(key), 관리자 세션에 한 번."""
        self.health.update(fail=self.health["fail"] + 1, error=f"세션 {sid}: {why}"[:300])
        log.warning("조사 세션 %s: %s", sid, why)
        try:
            await self.h._act(sid, ACT, ls.pid if ls else None, False, why[:500])
        except Exception as e:  # noqa: BLE001
            log.warning("조사 세션 끝내기 기록 실패: %s", type(e).__name__)
        project = (who or {}).get("project")
        title = (who or {}).get("title") or ""
        self._notify(project, sid, f"insp:{key}", f"⚠ 조사 세션 {sid} 「{title}」: {why}")
        if key in self._alerted:            # 그물이 같은 까닭을 다시 만나도 관리자에게는 한 번
            return {"closed": False, "why": why}
        self._alerted.add(key)
        try:
            await self._tell(who, f"[FOREMAN 합치기, 조사 세션 끝내기] 세션 {sid} 「{title}」: {why}. 관리자가 보고 정한다.")
        except Exception as e:  # noqa: BLE001
            log.warning("조사 세션 끝내기 실패를 관리자에게 못 알림: %s", type(e).__name__)
        return {"closed": False, "why": why}

    def _notify(self, project: str | None, sid: int | None, key: str, msg: str) -> None:
        """텔레그램 한 번(key가 이미 있으면 보내지 않는다, 브리지를 다시 띄워도)."""
        if self.notifier is None:
            return

        async def go() -> None:
            try:
                async with self.engine.connect() as cn:
                    if (await cn.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key[:64]})).first():
                        return
                rule = self.notifier.rules.for_project(project) if project else None
                prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
                self.notifier.send_direct(project, NOTIFY_KIND, sid, f"{prefix} {msg}"[:3500], rule=key[:64], later=False)
            except Exception as e:  # noqa: BLE001
                log.warning("조사 세션 끝내기 알림 실패: %s", type(e).__name__)
        self._spawn(go())

    # ── 그물 ──
    async def sweep(self) -> int:
        """살아 있는 조사 세션(턴이 끝난 지 settle_s가 지난 것)과 끝난 세션의 auto 카드를 다시 본다. 끝낸 수."""
        live = await asyncio.to_thread(live_sessions, self.sessions_dir)
        n = 0
        sids: list[int] = []
        if live:
            async with self.engine.connect() as c:
                sids = [r[0] for r in (await c.execute(text(
                    "SELECT cs.id FROM character_session cs WHERE cs.role = :r AND cs.cc_session_id IN :cc AND NOT EXISTS ("
                    "SELECT 1 FROM turn t WHERE t.session_id = cs.id AND (t.ended_at IS NULL OR t.ended_at > :cut))")
                    .bindparams(bindparam("cc", expanding=True)),
                    {"r": ROLE, "cc": list(live), "cut": _cut(self.cfg.settle_s)})).all()]
        mp = getattr(self.h, "mergeprep", None)
        if mp is not None:
            sids += [s for s, c in list(mp.cards.items()) if c.approver == "auto" and c.status == "ready" and not c.live and s not in sids]
        for sid in sids:
            r = await self._guarded(sid, None, "sweep")
            n += bool(r.get("closed"))
        return n

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.every_s)
            try:
                async with asyncio.timeout(600):
                    await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                self.health.update(error=f"그물 실패: {type(e).__name__}: {str(e)[:160]}")
                log.exception("조사 세션 끝내기 그물 실패")
                self._notify("foreman", None, "insp:sweep", f"⚠ 조사 세션 끝내기 그물이 실패했습니다: {type(e).__name__}")

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.get_running_loop().create_task(self.run(), name="foreman-inspector-close")
        return self._task


def _cut(settle_s: float) -> Any:
    from datetime import UTC, datetime, timedelta
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=settle_s)
