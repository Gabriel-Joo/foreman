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
import os
import re
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.approval import Decision, Policy, _short
from bridge.approval_summary import summarize
from bridge.models import EventIn, EventSource, EventStatus, EventType

log = logging.getLogger("foreman.approval")


def _questions_text(inp: dict[str, Any]) -> str:
    """AskUserQuestion — 질문과 선택지를 읽는 글로(11-09 사용자: JSON 300자에서 잘려 선택지를 못 봤다)."""
    out: list[str] = []
    qs = inp.get("questions") if isinstance(inp.get("questions"), list) else []
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict):
            continue
        head = f"[{q['header']}] " if q.get("header") else ""
        out.append(f"{i}. {head}{q.get('question') or ''}" + (" (여러 개 고름)" if q.get("multiSelect") else ""))
        for j, o in enumerate(q.get("options") or [], 1):
            if isinstance(o, dict):
                out.append(f"   {j}) {o.get('label') or ''}" + (f" — {o['description']}" if o.get("description") else ""))
    return "\n".join(out)


def _target(tool: str, inp: dict[str, Any]) -> str:
    if tool == "AskUserQuestion" and (t := _questions_text(inp)):
        return t[:1024]                    # approval.target 칸 크기
    v = inp.get("command") or inp.get("file_path") or inp.get("notebook_path") or inp.get("path") \
        or inp.get("url") or inp.get("pattern") or inp.get("description")
    return v if isinstance(v, str) else json.dumps(inp, ensure_ascii=False)[:300]


def _scratchpad(p: dict[str, Any]) -> str | None:
    """세션 스크래치패드 — hook 입력에는 없다. 트랜스크립트 경로에서 만든다(11-03):
    ~/.claude/projects/<디렉토리>/<세션>.jsonl → /tmp/claude-<uid>/<디렉토리>/<세션>/scratchpad. 모양이 다르면 None(예외를 안 쓴다)."""
    tp = p.get("transcript_path") or ""
    sid = p.get("session_id") or ""
    if not tp or not sid:
        return None
    path = Path(tp)
    if path.name != f"{sid}.jsonl" or path.parent.parent != Path.home() / ".claude" / "projects":
        return None
    return f"/tmp/claude-{os.getuid()}/{path.parent.name}/{sid}/scratchpad"


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
        self.recent: "OrderedDict[str, tuple[str | None, Decision, str | None, str | None]]" = OrderedDict()  # 키 → (tool_use_id, 판정, prompt_id, 요약)
        self.waiting: dict[int, asyncio.Future[tuple[str, str | None]]] = {}
        self.by_tool_use: dict[str, int] = {}
        # 질문(AskUserQuestion) 대기 — aid → 원래 입력. 패널에서 답하면 answers를 붙여 updatedInput으로 돌려준다(11-09)
        self.questions: dict[int, dict[str, Any]] = {}
        self.answers: dict[int, dict[str, str]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._rule_notice: dict[str, float] = {}   # 안전 규칙 파일 도구 편집 알림 — 파일 → 마지막 알린 시각
        self.schema: Any = None                    # 스키마 잠금(bridge/schemalock.py) — main.py가 넣는다
        self.scope: Any = None                     # 다른 저장소는 읽기만(bridge/reposcope.py, 11-09) — main.py가 넣는다

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
        # 스키마 잠금 — 다른 세션이 이 프로젝트의 스키마를 바꾸는 중이면 거부. 승인 모드(observe)와 상관없이(11-05 사용자 지시)
        why_lock = self.schema.check(project, p.get("session_id"), p.get("cwd"), tool, inp) if self.schema else None
        rule = "스키마-잠금"
        if not why_lock and self.scope:
            # 다른 저장소는 읽기만 — 역시 승인 모드와 상관없이(11-09 사용자)
            why_lock = self.scope.check(project, p.get("cwd"), tool, inp, p.get("scratchpad_dir") or _scratchpad(p))
            rule = "다른저장소-쓰기"
        if why_lock:
            dec = Decision("deny", rule, why_lock)
            log.warning("deny %s %s — %s", project, tool, why_lock)
            self._bg(self._record_pre(p, tool, inp, dec, pp.mode, True, None))
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": f"FOREMAN {why_lock}"}}
        dec = self.policy.decide(tool, inp, p.get("cwd"), p.get("scratchpad_dir") or _scratchpad(p), project)
        enforced = pp.mode == "enforce" and dec.verdict in ("allow", "ask")
        sid = p.get("session_id") or ""
        summary = self._summary(tool, inp, dec.rule, dec.reason, p.get("cwd")) if dec.verdict == "ask" else None
        self.recent[_key(sid, tool, inp)] = (p.get("tool_use_id"), dec, p.get("prompt_id"), summary)
        self.recent.move_to_end(_key(sid, tool, inp))
        while len(self.recent) > 4096:
            self.recent.popitem(last=False)
        if dec.verdict == "ask":
            # 거절 · 보류는 언제나 이유를 남긴다(1단계 교훈)
            log.warning("ask %s[%s] %s %s — %s: %s", project or "미분류", pp.mode, tool,
                        _short(self.mask.text(_target(tool, inp)) or "", 80), dec.rule, dec.reason)
        self._bg(self._record_pre(p, tool, inp, dec, pp.mode, enforced, summary))
        if dec.rule == "규칙파일-편집":
            self._rule_file_notice(project, tool, inp, dec.reason)
        if not enforced:
            return None
        # CC 승인 창에 보이는 문구 — 무엇을 대상으로가 맨 앞(11-03). 규칙 이름 · 이유는 뒤에
        why = f"FOREMAN {summary}  [{dec.rule}: {dec.reason}]" if summary else f"FOREMAN {dec.rule}: {dec.reason}"
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": dec.verdict,
                                       "permissionDecisionReason": why}}

    def _rule_file_notice(self, project: str | None, tool: str, inp: dict[str, Any], reason: str = "") -> None:
        """안전 규칙 · 설정 파일을 고쳤다(묻지 않고 통과) — 대신 알린다. 같은 파일은 10분에 한 번(11-03).
        11-05부터 Bash로 고치는 것도(경로는 판정 이유 괄호 안)."""
        path = str(inp.get("file_path") or (re.findall(r"\(([^()]*)\)\s*$", reason) or [reason])[0])
        now = time.monotonic()
        if now - self._rule_notice.get(path, -1e9) < 600:
            return
        self._rule_notice[path] = now
        log.warning("안전 규칙 파일 수정(%s) %s — 묻지 않고 통과, 알림", tool, path)
        if self.notifier:
            rule_ = self.notifier.rules.for_project(project)
            prefix = rule_.prefix if rule_ else "[미분류]"
            self.notifier.send_direct(project, "rulefile", None,
                                      f"{prefix} 🛡 안전 규칙 파일 수정 · {tool}\n▶ {path}\n"
                                      f"묻지 않고 통과 — 브리지를 다시 띄워야 반영된다. "
                                      f"10분 안의 다음 수정은 따로 알리지 않는다")

    def _summary(self, tool: str, inp: dict[str, Any], rule: str, reason: str, cwd: str | None) -> str | None:
        try:
            return self.mask.text(summarize(tool, inp, rule, reason, cwd)) or None
        except Exception as e:  # noqa: BLE001 — 요약 실패가 판정을 막으면 안 된다
            log.warning("승인 요약 실패: %s: %s", type(e).__name__, str(e)[:200])
            return None

    async def _record_pre(self, p: dict[str, Any], tool: str, inp: dict[str, Any], dec: Decision, mode: str,
                          enforced: bool, summary: str | None = None) -> None:
        try:
            sess_id, char_id, turn_id = await self.asm.ids_for(p)
            self.pipeline.submit(EventIn(
                source=EventSource.HOOK, type=EventType.APPROVAL_REQ, session_id=sess_id, character_id=char_id,
                turn_id=turn_id, tool_use_id=p.get("tool_use_id"), tool=tool[:64],
                target=self.mask.text(_target(tool, inp)),
                status=EventStatus.WAITING if dec.verdict == "ask" and enforced else EventStatus.WORKING,
                payload={"decision": dec.verdict, "rule": dec.rule, "reason": dec.reason, "mode": mode,
                         "enforced": enforced, "permission_mode": p.get("permission_mode"), "summary": summary}))
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
        tuid, dec, _pid, summary = self.recent.get(_key(sid, tool, inp), (None, None, None, None))
        rule, reason = (dec.rule, dec.reason) if dec and dec.verdict == "ask" else ("cc", "CC가 묻는다(auto mode 분류기 · 설정)")
        if tool == "AskUserQuestion":
            rule, reason = "질문", "세션이 사용자에게 묻는 질문입니다 — 패널의 선택지나 그 세션의 터미널에서 답합니다"
        if not summary:   # CC 자체가 묻는 것에도 — 규칙이 아니라 명령을 본다
            summary = self._summary(tool, inp, rule, reason, p.get("cwd"))
        target = self.mask.text(_target(tool, inp)) or ""
        sess_id, _char, turn_id = await self.asm.ids_for(p)
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "INSERT INTO approval (session_id, turn_id, tool_use_id, tool, target, rule, reason, summary, status) "
                "VALUES (:s, :t, :tu, :tool, :tg, :r, :why, :sum, 'pending')"),
                {"s": sess_id, "t": turn_id, "tu": tuid, "tool": tool[:64], "tg": target[:1024], "r": rule[:64],
                 "why": reason[:255], "sum": (summary or "")[:512] or None})
            aid = res.lastrowid
        fut: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
        self.waiting[aid] = fut
        if tuid:
            self.by_tool_use[tuid] = aid
        if tool == "AskUserQuestion" and isinstance(inp.get("questions"), list):
            self.questions[aid] = inp
        # 칸 크기(1024)까지 — 전에는 300자로 잘라 보내 화면이 다시 불러올 때(1024)와 달랐다
        item = {"id": aid, "project": project, "session_id": sess_id, "tool": tool, "target": target[:1024],
                "rule": rule, "reason": reason, "summary": summary, "wait_s": pp.wait_s,
                "questions": self.questions_of(aid)}
        log.warning("승인 대기 #%d %s %s — %s", aid, project or "미분류", summary or _short(target, 80), rule)
        self.pipeline.publish({"type": "approval", "op": "pending", "approval": item})
        if self.notifier:
            self.notifier.send_direct(project, "approval", sess_id,
                                      _approval_text(project, tool, target, rule, reason, pp.wait_s, self.notifier,
                                                     summary))
        try:
            async with asyncio.timeout(pp.wait_s):
                outcome, message = await fut
        except TimeoutError:
            outcome, message = "timeout", None
            # 시간 초과도 알린다(11-06 사용자: 화면을 계속 보고 있지 않다) — 이제 터미널 승인 창만 남는다
            if self.notifier:
                rule_ = self.notifier.rules.for_project(project)
                self.notifier.send_direct(project, "appr_to", sess_id, "\n".join([
                    f"{rule_.prefix if rule_ else '[미분류]'} ⏰ 승인 대기 시간이 지났습니다 · {tool}",
                    *([f"▶ {summary}"] if summary else [_short(target, 120)]),
                    f"{int(pp.wait_s // 60)}분 동안 답이 없어 화면 승인을 닫았습니다. 이제 그 세션의 터미널에서만 답할 수 있습니다"]))
        finally:
            self.waiting.pop(aid, None)
            q_inp = self.questions.pop(aid, None)
            answers = self.answers.pop(aid, None)
            if tuid:
                self.by_tool_use.pop(tuid, None)
        if outcome == "answer":                    # 패널에서 질문에 답했다 — 기록은 "허용 · 화면에서", 메시지 칸에 고른 답
            outcome, message = "allow", _short("; ".join(f"{k} → {v}" for k, v in (answers or {}).items()), 250)
        status = {"allow": "allowed", "deny": "denied"}.get(outcome, outcome)
        terminal = message if outcome == "terminal" else None   # 터미널이면 두 번째 값은 CC가 기록한 결정
        message = None if outcome == "terminal" else message
        await self._finish(aid, status, {"allow": "browser", "deny": "browser"}.get(outcome, outcome), message, terminal)
        self.pipeline.publish({"type": "approval", "op": "resolved", "approval": item | {"status": status}})
        self._bg(self._record_res(p, tool, target, aid, status, rule, message))
        if outcome == "allow" and q_inp is not None and answers:
            # 문서(hooks — AskUserQuestion): 원래 입력 전체 + answers(질문 글 → 고른 선택지 이름)를 updatedInput으로
            return {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                           "decision": {"behavior": "allow", "updatedInput": {**q_inp, "answers": answers}}}}
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

    def questions_of(self, aid: int) -> list[dict[str, Any]] | None:
        """패널 카드용 — 질문 · 선택지(이름 · 설명 · 여러 개 고름). 질문 대기가 아니면 None."""
        inp = self.questions.get(aid)
        if not inp:
            return None
        return [{"question": str(q.get("question") or ""), "header": q.get("header"), "multi": bool(q.get("multiSelect")),
                 "options": [{"label": str(o.get("label") or ""), "description": o.get("description")}
                             for o in q.get("options") or [] if isinstance(o, dict)]}
                for q in inp.get("questions") or [] if isinstance(q, dict)]

    def answer(self, aid: int, picks: dict[str, list[str]]) -> str:
        """패널에서 질문에 답한다. picks — 질문 글 → 고른 선택지 이름들. 돌려주는 값: ok · gone · bad(질문 · 선택지가 맞지 않음).
        여러 개 고름은 ", "로 잇는다(문서: "Multi-select answers join labels with commas" — 띄어쓰기는 문서에 없고,
        ", "로 이은 답이 세션에 그대로 들어가는 것은 11-09 실측 #70)."""
        fut, qs = self.waiting.get(aid), self.questions_of(aid)
        if fut is None or fut.done() or qs is None:
            return "gone"
        out: dict[str, str] = {}
        for q in qs:
            got = picks.get(q["question"]) or []
            labels = [o["label"] for o in q["options"]]
            if not got or any(g not in labels for g in got) or (len(got) > 1 and not q["multi"]):
                return "bad"
            out[q["question"]] = ", ".join(got)
        self.answers[aid] = out
        fut.set_result(("answer", None))
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
                   notifier: Any, summary: str | None = None) -> str:
    rule_ = notifier.rules.for_project(project) if notifier else None
    prefix = rule_.prefix if rule_ else "[미분류]"
    if tool == "AskUserQuestion":          # 질문은 승인이 아니다 — 질문과 선택지를 그대로(11-09)
        return "\n".join([f"{prefix} ❓ 세션이 묻습니다 — 답을 기다립니다", _short(target, 700),
                          "확인 페이지의 선택지를 누르거나 그 세션의 터미널에서 답합니다"])
    # 무엇을 대상으로가 둘째 줄(11-03) — 명령 원문은 그 아래 짧게
    return "\n".join([
        f"{prefix} 🔐 승인 대기 · {tool}",
        *([f"▶ {summary}"] if summary else []),
        f"명령: {_short(target, 120)}" if summary else _short(target, 160),
        f"규칙: {rule} — {reason}",
        f"확인 페이지에서 승인 · 거부, 또는 터미널에서. {int(wait_s // 60)}분이 지나면 터미널로만",
    ])


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
