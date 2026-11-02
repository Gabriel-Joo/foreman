"""승인 흐름 — PreToolUse 판정 · 기록, PermissionRequest 대기, 터미널 · 브라우저 · 시간 초과 중 먼저 온 결정(5단계).

실측(CC 2.1.316, auto mode):
- PreToolUse의 ask는 승인 창을 띄운다(auto mode의 자동 통과보다 앞선다). allow도 적용된다(source=hook)
- 승인 창이 뜨면 PermissionRequest hook이 불리고, 그 hook의 allow · deny가 결정이 된다
- hook이 기다리는 동안에도 터미널에는 승인 창이 이미 떠 있고, 터미널에서 먼저 답하면 hook과 무관하게 진행된다
- PermissionRequest 입력에는 tool_use_id가 없다 → 바로 앞 PreToolUse(같은 세션 · 도구 · 입력)에서 찾는다

PreToolUse는 모든 도구 호출 앞에서 불리므로 판정은 메모리에서 끝내고, 기록(DB)은 뒤에서 한다.
"""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.approval import Decision, Policy, _short
from bridge.models import EventIn, EventSource, EventStatus, EventType

log = logging.getLogger("foreman.approval")


def _target(tool: str, inp: dict[str, Any]) -> str:
    v = inp.get("command") or inp.get("file_path") or inp.get("notebook_path") or inp.get("path") \
        or inp.get("url") or inp.get("pattern") or inp.get("description")
    return v if isinstance(v, str) else json.dumps(inp, ensure_ascii=False)[:300]


def _key(sid: str, tool: str, inp: dict[str, Any]) -> str:
    return sid + "|" + tool + "|" + hashlib.sha1(json.dumps(inp, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ApprovalManager:
    def __init__(self, engine: AsyncEngine, policy: Policy, assembler: Any, pipeline: Any, masker: Any,
                 notifier: Any = None) -> None:
        self.engine = engine
        self.policy = policy
        self.asm = assembler
        self.pipeline = pipeline
        self.mask = masker
        self.notifier = notifier
        self.recent: "OrderedDict[str, tuple[str | None, Decision, str | None]]" = OrderedDict()  # 키 → (tool_use_id, 판정, prompt_id)
        self.waiting: dict[int, asyncio.Future[tuple[str, str | None]]] = {}
        self.by_tool_use: dict[str, int] = {}
        self._tasks: set[asyncio.Task[Any]] = set()

    def _bg(self, coro: Any) -> None:
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def start(self) -> int:
        """다시 떴다 — 기다리던 연결은 끊겼다(터미널 승인 창은 남아 있다)."""
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "UPDATE approval SET status = 'abandoned', decided_by = 'bridge', decided_at = UTC_TIMESTAMP(3) "
                "WHERE status = 'pending'"))
            return res.rowcount

    def _project(self, p: dict[str, Any]) -> str | None:
        tp = p.get("transcript_path") or ""
        project, _char = self.asm._project_for(p.get("cwd"), Path(tp).parent.name if tp else "")
        return project

    # ── PreToolUse ─────────────────────────────────────────
    def pre_tool_use(self, p: dict[str, Any]) -> dict[str, Any] | None:
        tool, inp = p.get("tool_name") or "?", p.get("tool_input") or {}
        project = self._project(p)
        pp = self.policy.for_project(project)
        dec = self.policy.decide(tool, inp, p.get("cwd"), p.get("scratchpad_dir"), project)
        enforced = pp.mode == "enforce" and dec.verdict in ("allow", "ask")
        sid = p.get("session_id") or ""
        self.recent[_key(sid, tool, inp)] = (p.get("tool_use_id"), dec, p.get("prompt_id"))
        self.recent.move_to_end(_key(sid, tool, inp))
        while len(self.recent) > 4096:
            self.recent.popitem(last=False)
        if dec.verdict == "ask":
            # 거절 · 보류는 언제나 이유를 남긴다(1단계 교훈)
            log.warning("ask %s[%s] %s %s — %s: %s", project or "미분류", pp.mode, tool,
                        _short(self.mask.text(_target(tool, inp)) or "", 80), dec.rule, dec.reason)
        self._bg(self._record_pre(p, tool, inp, dec, pp.mode, enforced))
        if not enforced:
            return None
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": dec.verdict,
                                       "permissionDecisionReason": f"FOREMAN {dec.rule}: {dec.reason}"}}

    async def _record_pre(self, p: dict[str, Any], tool: str, inp: dict[str, Any], dec: Decision, mode: str,
                          enforced: bool) -> None:
        try:
            sess_id, char_id, turn_id = await self.asm.ids_for(p)
            self.pipeline.submit(EventIn(
                source=EventSource.HOOK, type=EventType.APPROVAL_REQ, session_id=sess_id, character_id=char_id,
                turn_id=turn_id, tool_use_id=p.get("tool_use_id"), tool=tool[:64],
                target=self.mask.text(_target(tool, inp)),
                status=EventStatus.WAITING if dec.verdict == "ask" and enforced else EventStatus.WORKING,
                payload={"decision": dec.verdict, "rule": dec.rule, "reason": dec.reason, "mode": mode,
                         "enforced": enforced, "permission_mode": p.get("permission_mode")}))
        except Exception as e:  # noqa: BLE001 — 기록 실패가 판정을 바꾸지 않는다
            log.warning("판정 기록 실패: %s: %s", type(e).__name__, str(e)[:200])

    # ── PermissionRequest ──────────────────────────────────
    async def permission_request(self, p: dict[str, Any]) -> dict[str, Any] | None:
        tool, inp = p.get("tool_name") or "?", p.get("tool_input") or {}
        project = self._project(p)
        pp = self.policy.for_project(project)
        if not pp.remote_approval:
            return None
        sid = p.get("session_id") or ""
        tuid, dec, _pid = self.recent.get(_key(sid, tool, inp), (None, None, None))
        rule, reason = (dec.rule, dec.reason) if dec and dec.verdict == "ask" else ("cc", "CC가 묻는다(auto mode 분류기 · 설정)")
        target = self.mask.text(_target(tool, inp)) or ""
        sess_id, _char, turn_id = await self.asm.ids_for(p)
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "INSERT INTO approval (session_id, turn_id, tool_use_id, tool, target, rule, reason, status) "
                "VALUES (:s, :t, :tu, :tool, :tg, :r, :why, 'pending')"),
                {"s": sess_id, "t": turn_id, "tu": tuid, "tool": tool[:64], "tg": target[:1024], "r": rule[:64],
                 "why": reason[:255]})
            aid = res.lastrowid
        fut: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
        self.waiting[aid] = fut
        if tuid:
            self.by_tool_use[tuid] = aid
        item = {"id": aid, "project": project, "session_id": sess_id, "tool": tool, "target": target[:300],
                "rule": rule, "reason": reason, "wait_s": pp.wait_s}
        log.warning("승인 대기 #%d %s %s %s — %s", aid, project or "미분류", tool, _short(target, 80), rule)
        self.pipeline.publish({"type": "approval", "op": "pending", "approval": item})
        if self.notifier:
            self.notifier.send_direct(project, "approval", sess_id,
                                      _approval_text(project, tool, target, rule, reason, pp.wait_s, self.notifier))
        try:
            async with asyncio.timeout(pp.wait_s):
                outcome, message = await fut
        except TimeoutError:
            outcome, message = "timeout", None
        finally:
            self.waiting.pop(aid, None)
            if tuid:
                self.by_tool_use.pop(tuid, None)
        status = {"allow": "allowed", "deny": "denied"}.get(outcome, outcome)
        terminal = message if outcome == "terminal" else None   # 터미널이면 두 번째 값은 CC가 기록한 결정
        message = None if outcome == "terminal" else message
        await self._finish(aid, status, {"allow": "browser", "deny": "browser"}.get(outcome, outcome), message, terminal)
        self.pipeline.publish({"type": "approval", "op": "resolved", "approval": item | {"status": status}})
        self._bg(self._record_res(p, tool, target, aid, status, rule, message))
        if outcome == "allow":
            return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
        if outcome == "deny":
            return {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                           "decision": {"behavior": "deny", "message": message or "브라우저에서 거부"}}}
        return None  # 터미널에서 답했거나 시간 초과 — 아무 결정도 돌려주지 않는다(터미널 승인 창이 정한다)

    async def _finish(self, aid: int, status: str, by: str, message: str | None, terminal: str | None = None) -> None:
        try:
            async with self.engine.begin() as c:
                await c.execute(text(
                    "UPDATE approval SET status = :st, decided_by = :by, message = :m, "
                    "terminal_decision = COALESCE(:td, terminal_decision), decided_at = UTC_TIMESTAMP(3) "
                    "WHERE id = :id AND status = 'pending'"),
                    {"st": status, "by": by, "m": (message or "")[:255] or None, "td": terminal, "id": aid})
        except Exception as e:  # noqa: BLE001
            log.warning("승인 기록 실패 #%d: %s", aid, type(e).__name__)
        log.warning("승인 #%d → %s (%s)%s", aid, status, by, f": {message}" if message else "")

    async def _record_res(self, p: dict[str, Any], tool: str, target: str, aid: int, status: str, rule: str,
                          message: str | None) -> None:
        try:
            sess_id, char_id, turn_id = await self.asm.ids_for(p)
            self.pipeline.submit(EventIn(
                source=EventSource.BRIDGE, type=EventType.APPROVAL_RES, session_id=sess_id, character_id=char_id,
                turn_id=turn_id, tool=tool[:64], target=target,
                status=EventStatus.DONE if status == "allowed" else EventStatus.ERROR if status == "denied" else EventStatus.IDLE,
                payload={"approval_id": aid, "status": status, "rule": rule, "message": message}))
        except Exception as e:  # noqa: BLE001
            log.warning("승인 결과 기록 실패: %s", type(e).__name__)

    # ── 결정 ───────────────────────────────────────────────
    def decide(self, aid: int, decision: str, message: str | None) -> str:
        """브라우저에서. 돌려주는 값: ok · gone(이미 결정됐거나 없다)."""
        fut = self.waiting.get(aid)
        if fut is None or fut.done():
            return "gone"
        fut.set_result((decision, message))
        return "ok"

    def on_tool_result(self, tool_use_id: str | None, perm: dict[str, Any] | None) -> None:
        """트랜스크립트에 그 도구의 결과가 왔다 — 터미널에서 이미 답했다. 기다리던 hook을 풀어 준다."""
        if not tool_use_id or tool_use_id not in self.by_tool_use:
            return
        aid = self.by_tool_use[tool_use_id]
        fut = self.waiting.get(aid)
        if fut is None or fut.done():
            return
        fut.set_result(("terminal", (perm or {}).get("decision")))   # 기록은 기다리던 쪽이 한 번만


def _approval_text(project: str | None, tool: str, target: str, rule: str, reason: str, wait_s: float,
                   notifier: Any) -> str:
    rule_ = notifier.rules.for_project(project) if notifier else None
    prefix = rule_.prefix if rule_ else "[미분류]"
    return "\n".join([
        f"{prefix} 🔐 승인 대기 · {tool}",
        _short(target, 160),
        f"이유: {rule} — {reason}",
        f"확인 페이지에서 승인 · 거부, 또는 터미널에서. {int(wait_s // 60)}분이 지나면 터미널로만",
    ])


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
