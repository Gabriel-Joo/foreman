"""세션 인계 · 세션 조작(11단계 앞당김, 11-05 — docs/11_handoff.md).

인계 요약은 그 세션 자신이 쓴다. 브리지는 기존 입력 경로(방법 C)로 요청 프롬프트를 넣고, 트랜스크립트의 assistant 줄에서
`<<<FOREMAN-HANDOFF r=X>>> … <<<END r=X>>>`를 꺼낸다. 요청 줄의 머리 `[FOREMAN 인계 요청 r=X]`로 조립기가 그 턴을
origin=handoff로 달아 보통 응답 · 알림과 가른다.

세션 조작(끝내기 · 멈춤 · 되살리기 · 작업 중단)은 사람이 그 pane에서 치는 키와 같은 것을 보낸다(/exit · Ctrl+Z · fg · Esc).
되살리기는 FOREMAN이 멈춘 것만(session_action) — 사용자가 남겨 둔 정지 CC는 건드리지 않는다(CLAUDE.md).
"""

import asyncio
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.inject import Refused, _status, _tmux_env, deliver, resolve, tmux
from bridge.liveness import _proc_stat, live_sessions

log = logging.getLogger("foreman.handoff")

REQ_HEAD = "[FOREMAN 인계 요청 r={r}]"
IN_HEAD = "[FOREMAN 인계 r={r}]"
REQ_RE = re.compile(r"\[FOREMAN 인계 요청 r=([0-9a-f]{6})\]")
IN_RE = re.compile(r"\[FOREMAN 인계 r=([0-9a-f]{6})\]")
MAX_BODY = 4000          # 요약을 시킬 때의 분량
MAX_INJECT = 8000        # 새 세션에 넣는 글 상한
WAIT_S = 600.0           # 요약이 돌아오기를 기다리는 시간
HANDOFF_DIR = Path.home() / ".foreman" / "handoff"
KEEP_FULL = ("진행", "미완", "다음", "주의")      # 분량을 줄일 때도 통째로 넣는 절

REQUEST_PROMPT = """{head}
이 세션을 새 세션으로 넘기려고 한다. 새 세션은 이 대화를 전혀 모르고, 아래 인계 문서만 받는다.
지금까지의 대화 전체를 바탕으로 인계 문서를 써라.

- 파일을 고치거나 커밋 · 배포하지 마라. 정확히 쓰려고 git status · git log 같은 읽기는 해도 된다
- 승인을 기다리는 것 · 돌고 있는 서브에이전트 · 걸어 둔 타이머가 있으면 반드시 적어라
- 사용자가 정한 것(결정 · 하지 말라고 한 것)은 빠짐없이 "주의"에 적어라
- 직전 인계 요약을 받고 시작한 세션이면 그 내용도 지금 기준으로 고쳐 넣어라(이어 쓰기가 아니라 갱신)
- {max_body}자 안. 아래 형식 그대로, 마지막 응답에 한 번만 써라(표지 줄 두 개를 글자 그대로):

<<<FOREMAN-HANDOFF r={r}>>>
## 목표 · 맥락
(이 작업이 왜 · 무엇을 향하는지 3~5줄)
## 한 일
(결과 위주 — 커밋 해시 · 파일 경로)
## 진행 중 · 미완
(어디서 멈췄는지, 다음에 건드릴 파일 · 명령)
## 다음 할 일
(순서대로)
## 주의
(사용자가 정한 것, 하지 말 것, 막힌 것 · 확인 필요)
## 참고
(문서 · 로그 · 메모리 경로)
<<<END r={r}>>>"""

INJECT_PROMPT = """{head} 직전 세션 {src}의 인계 요약이다. 너는 이 일을 이어받는 새 세션이다.
읽고 나서 (1) 이해한 것을 5줄 안으로 말하고 (2) "다음 할 일"을 시작하기 전에 사용자의 확인을 기다려라.

{body}"""


def new_req() -> str:
    return secrets.token_hex(3)


def request_prompt(req: str) -> str:
    return REQUEST_PROMPT.format(head=REQ_HEAD.format(r=req), r=req, max_body=MAX_BODY)


def block_re(req: str) -> re.Pattern[str]:
    return re.compile(rf"<<<FOREMAN-HANDOFF r={req}>>>[ \t]*\n(.*?)\n[ \t]*<<<END r={req}>>>", re.S)


def extract_block(texts: str, req: str) -> str | None:
    """assistant 글에서 마지막 표지 짝 사이. 없으면 None."""
    found = block_re(req).findall(texts)
    body = found[-1].strip() if found else ""
    return body or None


def assistant_text(path: str | Path, offset: int) -> str:
    """offset 뒤 메인 세션 assistant 줄의 text 블록만 — user 줄(요청 프롬프트에도 표지가 있다)은 보지 않는다."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return ""
    out = []
    for raw in data.split(b"\n"):
        if b'"assistant"' not in raw:            # 빠른 거르기(정확한 판정은 아래 json)
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                out.append(b["text"])
    return "\n".join(out)


def _sections(body: str) -> list[tuple[str, str]]:
    parts, cur, buf = [], "", []
    for line in body.splitlines():
        if line.startswith("## "):
            if cur or buf:
                parts.append((cur, "\n".join(buf).strip()))
            cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if cur or buf:
        parts.append((cur, "\n".join(buf).strip()))
    return parts


def fit_body(body: str, limit: int = MAX_INJECT, full_path: str | None = None) -> tuple[str, bool]:
    """넣을 분량으로 — 넘으면 진행 중 · 미완 · 다음 할 일 · 주의는 통째로, 나머지 절은 앞부분만. (글, 줄였나)"""
    if len(body) <= limit:
        return body, False
    secs = _sections(body)
    keep = sum(len(t) + len(h) + 4 for h, t in secs if any(k in h for k in KEEP_FULL))
    others = [h for h, _ in secs if not any(k in h for k in KEEP_FULL)]
    room = max(200, (limit - keep - 300) // max(1, len(others)))
    out = []
    for h, t in secs:
        if not any(k in h for k in KEEP_FULL) and len(t) > room:
            t = t[:room].rsplit("\n", 1)[0] + "\n…(줄임)"
        out.append(f"## {h}\n{t}" if h else t)
    s = "\n".join(out)
    if full_path:
        s += f"\n\n(분량 때문에 일부 절을 줄였다 — 전체는 {full_path} 을 Read하라)"
    return s[: limit + 400], True


def inject_prompt(req: str, src: str, body: str) -> str:
    return INJECT_PROMPT.format(head=IN_HEAD.format(r=req), src=src, body=body)


def transcript_path(cwd: str, cc_session_id: str) -> str:
    """CC가 쓰는 자리 — ~/.claude/projects/<cwd의 영숫자 밖 글자를 -로>/<id>.jsonl(실측: '/' '_' → '-')."""
    return str(Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", cwd) / f"{cc_session_id}.jsonl")


def compact_body(path: str | Path) -> str | None:
    """마지막 auto-compact 요약(CC가 쓴 것) + 그 뒤 사람 프롬프트 · 마지막 응답 — 죽은 세션의 보조 수단."""
    last_compact, after_prompts, last_reply = None, [], ""
    try:
        f = open(path, "rb")
    except OSError:
        return None
    with f:
        for raw in f:
            if b'"isCompactSummary":true' in raw:
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                c = (d.get("message") or {}).get("content")
                last_compact = c if isinstance(c, str) else "".join(
                    b.get("text", "") for b in c or [] if isinstance(b, dict))
                after_prompts, last_reply = [], ""
            elif last_compact is not None and (b'"type":"user"' in raw or b'"type":"assistant"' in raw):
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                if d.get("isSidechain") or d.get("isMeta"):
                    continue
                c = (d.get("message") or {}).get("content")
                if d.get("type") == "user" and isinstance(c, str) and c.strip():
                    after_prompts.append(c.strip()[:300])
                elif d.get("type") == "assistant":
                    t = "".join(b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")
                    if t.strip():
                        last_reply = t.strip()
    if last_compact is None:
        return None
    out = ["## 마지막 자동 압축 요약(CC가 쓴 것)", last_compact.strip()[:6000]]
    if after_prompts:
        out += ["## 압축 뒤 사람 프롬프트", *[f"- {p}" for p in after_prompts[-15:]]]
    if last_reply:
        out += ["## 마지막 응답", last_reply[:2000]]
    return "\n".join(out)


@dataclass
class SessionRow:
    id: int
    cc: str | None
    character_id: int | None
    cwd: str | None
    transcript: str | None
    project: str | None
    title: str | None


class HandoffManager:
    def __init__(self, engine: AsyncEngine, sessions_dir: str | Path, notifier: Any = None, on_change: Any = None,
                 tmux_socket: str | None = None, claude_bin: str = "claude") -> None:
        self.engine, self.sessions_dir, self.notifier, self.on_change = engine, sessions_dir, notifier, on_change
        self.socket = tmux_socket or f"{os.environ.get('TMUX_TMPDIR', '/tmp')}/tmux-{os.getuid()}/default"
        self.claude_bin = claude_bin
        self.wait_s = WAIT_S
        self._tasks: set[asyncio.Task[Any]] = set()

    # ── 조회 ────────────────────────────────────────────
    async def session(self, sid: int) -> SessionRow | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, cs.character_id, cs.cwd, tf.path, p.name, cs.title "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id LEFT JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
                "WHERE cs.id = :id"), {"id": sid})).first()
        return SessionRow(*r) if r else None

    async def summaries(self, sid: int, limit: int = 20) -> list[dict[str, Any]]:
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, req, kind, source, status, turn_id, body, chars, raw, error, parent_id, injected_cc_session, "
                "injected_at, created_at FROM summary WHERE session_id = :s ORDER BY id DESC LIMIT :n"),
                {"s": sid, "n": limit})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("injected_at", "created_at"):
                d[k] = d[k].isoformat() + "Z" if d[k] else None
            if d["raw"]:
                d["raw"] = d["raw"][-4000:]
            out.append(d)
        return out

    async def summary(self, summary_id: int) -> dict[str, Any] | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT * FROM summary WHERE id = :i"), {"i": summary_id})).mappings().first()
        return dict(r) if r else None

    async def latest_ok(self, sid: int) -> dict[str, Any] | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT * FROM summary WHERE session_id = :s AND status = 'ok' ORDER BY id DESC LIMIT 1"),
                {"s": sid})).mappings().first()
        return dict(r) if r else None

    async def controls(self, row: SessionRow) -> dict[str, Any]:
        """패널이 버튼을 켜고 끄는 근거 — 실제 조작 때 다시 확인한다."""
        live = live_sessions(self.sessions_dir).get(row.cc or "")
        te = _tmux_env(live.pid) if live else None
        busy = bool(live and _status(self.sessions_dir, live.pid) == "busy")
        stopped_pid = await self._foreman_stopped(row.id)
        pending = await self._pending(row.id)
        out: dict[str, Any] = {"live": bool(live), "pid": live.pid if live else None, "state": live.state if live else None,
                               "tmux": bool(te), "busy": busy, "pending_req": pending,
                               "foreman_stopped": stopped_pid is not None}
        why = None
        if not live:
            why = "프로세스 없음(죽은 세션)"
        elif live.state == "T":
            why = "멈춘 세션" + (" — FOREMAN이 멈춤" if stopped_pid else " — 사람이 멈춤(건드리지 않는다)")
        elif not te:
            why = "tmux 밖 세션 — 입력 · 조작 불가"
        elif busy:
            why = "일하는 중"
        out["why"] = why
        ok_live = bool(live and te and live.state != "T")
        out["can"] = {
            "summary": ok_live and not busy and not pending,
            "headless": not live and bool(row.cc and row.cwd) and not pending,
            "compact": bool(row.transcript),
            "exit": ok_live and not busy,
            "stop": ok_live and not busy,
            "resume": bool(live and live.state == "T" and stopped_pid == live.pid),
            "interrupt": ok_live and busy,
            "spawn": bool(row.cwd and Path(row.cwd).is_dir()),
        }
        return out

    async def _pending(self, sid: int) -> str | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT req FROM summary WHERE session_id = :s AND status = 'requested' "
                "AND created_at > NOW(3) - INTERVAL 15 MINUTE ORDER BY id DESC LIMIT 1"), {"s": sid})).first()
        return r[0] if r else None

    async def _foreman_stopped(self, sid: int) -> int | None:
        """마지막 멈춤 · 되살리기 기록이 FOREMAN의 성공한 멈춤이면 그 pid."""
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT action, pid FROM session_action WHERE session_id = :s AND ok AND action IN ('stop', 'resume') "
                "ORDER BY id DESC LIMIT 1"), {"s": sid})).first()
        return int(r[1]) if r and r[0] == "stop" and r[1] else None

    # ── 기록 ────────────────────────────────────────────
    async def _act(self, sid: int | None, action: str, pid: int | None, ok: bool, detail: str | None) -> None:
        async with self.engine.begin() as c:
            await c.execute(text(
                "INSERT INTO session_action (session_id, action, pid, ok, detail) VALUES (:s, :a, :p, :o, :d)"),
                {"s": sid, "a": action, "p": pid, "o": ok, "d": (detail or "")[:512] or None})
        log.info("세션 조작 %s session=%s pid=%s %s %s", action, sid, pid, "ok" if ok else "실패", detail or "")

    async def _new_summary(self, row: SessionRow, kind: str, source: str, status: str, **kw: Any) -> tuple[int, str]:
        req = new_req()
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "INSERT INTO summary (character_id, session_id, req, kind, source, status, body, chars, raw, error, parent_id) "
                "VALUES (:ch, :s, :r, :k, :src, :st, :b, :n, :raw, :e, :par)"),
                {"ch": row.character_id, "s": row.id, "r": req, "k": kind, "src": source, "st": status,
                 "b": kw.get("body"), "n": len(kw["body"]) if kw.get("body") else None, "raw": kw.get("raw"),
                 "e": kw.get("error"), "par": kw.get("parent_id")})
        return res.lastrowid, req

    async def _finish(self, summary_id: int, status: str, body: str | None, raw: str | None, error: str | None,
                      turn_id: int | None = None) -> None:
        async with self.engine.begin() as c:
            await c.execute(text(
                "UPDATE summary SET status = :st, body = :b, chars = :n, raw = :raw, error = :e, "
                "turn_id = COALESCE(:t, turn_id) WHERE id = :i"),
                {"st": status, "b": body, "n": len(body) if body else None, "raw": (raw or "")[-200000:] or None,
                 "e": (error or "")[:512] or None, "t": turn_id, "i": summary_id})
        if self.on_change:
            self.on_change()

    def _notify(self, row: SessionRow, msg: str) -> None:
        if self.notifier:
            try:
                rule = self.notifier.rules.for_project(row.project) if hasattr(self.notifier, "rules") else None
                prefix = (rule.prefix if rule and rule.prefix else "[미분류]") + " "     # 승인 알림과 같은 접두어
                self.notifier.send_direct(row.project, "handoff", row.id, prefix + msg)
            except Exception as e:  # noqa: BLE001 — 알림 실패가 요약을 막지 않는다
                log.warning("인계 알림 실패: %s", type(e).__name__)

    def _spawn_task(self, coro: Any) -> None:
        t = asyncio.create_task(coro)
        self._tasks.add(t)

        def done(t: asyncio.Task[Any]) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception():
                log.error("인계 작업 실패: %r", t.exception(), exc_info=t.exception())
        t.add_done_callback(done)

    # ── 요약 받기 ────────────────────────────────────────
    async def request_live(self, row: SessionRow, kind: str = "snapshot") -> dict[str, Any]:
        """살아 있는 tmux 세션에 요약을 시킨다. 보내고 바로 돌아오고, 응답은 뒤에서 기다린다."""
        if not row.cc:
            raise Refused("CC 세션 ID가 없다")
        if await self._pending(row.id):
            raise Refused("이미 요약을 기다리는 중이다")
        _t, ls, busy = await resolve(row.cc, self.sessions_dir)
        if busy:
            raise Refused("일하는 중 — 작업이 끝난 뒤에 요약한다(일 중간에 끼면 작업과 섞인다)")
        sid, req = await self._new_summary(row, kind, "self", "requested")
        path = row.transcript or transcript_path(row.cwd or "", row.cc)
        offset = os.path.getsize(path) if os.path.exists(path) else 0
        try:
            res = await deliver(row.cc, request_prompt(req), sessions_dir=self.sessions_dir, transcript=path)
        except Refused as e:
            await self._finish(sid, "failed", None, None, f"보내지 못함: {e}")
            raise
        if not res.get("delivered"):
            await self._finish(sid, "failed", None, None, "제출이 확인되지 않았다 — 입력 칸에 남았을 수 있다")
            return {"summary_id": sid, "req": req, "status": "failed"}
        self._spawn_task(self._wait_live(row, sid, req, path, offset, (res["delivered"] or {}).get("prompt_id")))
        return {"summary_id": sid, "req": req, "status": "requested", "pid": ls.pid}

    async def _wait_live(self, row: SessionRow, sid: int, req: str, path: str, offset: int, prompt_id: str | None) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + self.wait_s
        ended_seen: float | None = None
        turn_id = None
        while loop.time() < end:
            await asyncio.sleep(2.0)
            texts = assistant_text(path, offset)
            body = extract_block(texts, req)
            if body:
                await self._finish(sid, "ok", body, texts, None, turn_id or await self._turn_of(prompt_id))
                self._notify(row, f"인계 요약 저장 ({len(body):,}자) — 세션 {row.cc[:8] if row.cc else row.id}")
                return
            if prompt_id and ended_seen is None:
                turn_id = await self._turn_of(prompt_id)
                if turn_id and await self._turn_ended(turn_id):
                    ended_seen = loop.time()
            if ended_seen and loop.time() - ended_seen > 6:     # 턴이 닫혔는데 표지가 없다(마지막 줄이 늦게 쓰일 여유 6초)
                await self._finish(sid, "failed", None, texts, "턴이 끝났는데 인계 표지가 없다", turn_id)
                self._notify(row, "인계 요약 실패 — 표지 없음(원문은 패널에)")
                return
            if row.cc and row.cc not in live_sessions(self.sessions_dir):
                await self._finish(sid, "failed", None, texts, "기다리는 중에 세션이 끝났다", turn_id)
                return
        await self._finish(sid, "timeout", None, assistant_text(path, offset), f"{self.wait_s:.0f}초 안에 돌아오지 않았다", turn_id)
        self._notify(row, "인계 요약 시간 초과")

    async def _turn_of(self, prompt_id: str | None) -> int | None:
        if not prompt_id:
            return None
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT id FROM turn WHERE prompt_id = :p"), {"p": prompt_id})).first()
        return r[0] if r else None

    async def _turn_ended(self, turn_id: int) -> bool:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT ended_at FROM turn WHERE id = :i"), {"i": turn_id})).first()
        return bool(r and r[0])

    async def request_headless(self, row: SessionRow, kind: str = "handoff") -> dict[str, Any]:
        """죽은 세션 — claude -p --resume <id>로 같은 컨텍스트를 불러 그 세션이 쓴다(fork 아님). 버튼을 누를 때만."""
        if not row.cc or not row.cwd:
            raise Refused("CC 세션 ID · cwd가 없다")
        if row.cc in live_sessions(self.sessions_dir):
            raise Refused("그 세션을 잡은 살아 있는 프로세스가 있다 — 같은 세션을 두 곳에서 이어 쓰지 않는다")
        if await self._pending(row.id):
            raise Refused("이미 요약을 기다리는 중이다")
        if not Path(row.cwd).is_dir():
            raise Refused(f"cwd가 없다: {row.cwd}")
        sid, req = await self._new_summary(row, kind, "self_headless", "requested")
        self._spawn_task(self._run_headless(row, sid, req))
        return {"summary_id": sid, "req": req, "status": "requested"}

    async def _run_headless(self, row: SessionRow, sid: int, req: str) -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        try:
            p = await asyncio.create_subprocess_exec(
                self.claude_bin, "-p", "--resume", row.cc or "", "--output-format", "text", request_prompt(req),
                cwd=row.cwd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env)
            try:
                out, err = await asyncio.wait_for(p.communicate(), self.wait_s)
            except TimeoutError:
                p.kill()
                await p.wait()
                await self._finish(sid, "timeout", None, None, f"claude -p가 {self.wait_s:.0f}초 안에 끝나지 않았다")
                return
        except OSError as e:
            await self._finish(sid, "failed", None, None, f"claude를 띄우지 못함: {e}")
            return
        texts = out.decode(errors="replace")
        body = extract_block(texts, req)
        if body:
            await self._finish(sid, "ok", body, texts, None)
            self._notify(row, f"죽은 세션 인계 요약 저장 ({len(body):,}자) — claude -p --resume")
        else:
            await self._finish(sid, "failed", None, texts or err.decode(errors="replace")[-4000:],
                               f"표지 없음 (종료 코드 {p.returncode})")

    async def from_compact(self, row: SessionRow, kind: str = "handoff") -> dict[str, Any]:
        if not row.transcript:
            raise Refused("트랜스크립트가 없다")
        body = await asyncio.to_thread(compact_body, row.transcript)
        if not body:
            raise Refused("자동 압축 요약이 없다(압축된 적 없는 세션)")
        sid, req = await self._new_summary(row, kind, "compact", "ok", body=body)
        if self.on_change:
            self.on_change()
        return {"summary_id": sid, "req": req, "status": "ok"}

    async def edit(self, summary_id: int, body: str) -> dict[str, Any]:
        src = await self.summary(summary_id)
        if not src:
            raise Refused("요약 없음")
        row = await self.session(src["session_id"])
        if not row:
            raise Refused("세션 없음")
        sid, req = await self._new_summary(row, src["kind"], "edited", "ok", body=body.strip(), parent_id=summary_id)
        if self.on_change:
            self.on_change()
        return {"summary_id": sid, "req": req, "status": "ok"}

    # ── 넣을 글 ──────────────────────────────────────────
    async def injection(self, summary_id: int) -> dict[str, Any]:
        s = await self.summary(summary_id)
        if not s or s["status"] != "ok" or not s["body"]:
            raise Refused("넣을 수 있는 요약이 아니다(ok 상태가 아님)")
        row = await self.session(s["session_id"])
        src = f"{(row.cc or '')[:8]}" + (f"({row.title})" if row and row.title else "")
        full = HANDOFF_DIR / f"{s['req']}.md"
        body, cut = fit_body(s["body"], MAX_INJECT, str(full))
        return {"summary_id": summary_id, "text": inject_prompt(s["req"], src, body), "cut": cut,
                "full_path": str(full) if cut else None, "chars": len(s["body"])}

    def _write_full(self, req: str, body: str) -> None:
        HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
        p = HANDOFF_DIR / f"{req}.md"
        p.write_text(body + "\n", encoding="utf-8")
        p.chmod(0o600)

    async def inject(self, summary_id: int, cc_session_id: str, cwd: str) -> dict[str, Any]:
        inj = await self.injection(summary_id)
        s = await self.summary(summary_id)
        if inj["cut"]:
            self._write_full(s["req"], s["body"])
        res = await deliver(cc_session_id, inj["text"], sessions_dir=self.sessions_dir,
                            transcript=transcript_path(cwd, cc_session_id), verify_s=15.0)
        if res.get("delivered"):
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE summary SET injected_cc_session = :c, injected_at = NOW(3) WHERE id = :i"),
                                {"c": cc_session_id, "i": summary_id})
        return {"delivered": bool(res.get("delivered")), "queued": res.get("queued"), "cut": inj["cut"]}

    # ── 새로 띄우기 ──────────────────────────────────────
    async def spawn(self, row: SessionRow, summary_id: int | None) -> dict[str, Any]:
        if not row.cwd or not Path(row.cwd).is_dir():
            raise Refused(f"cwd가 없다: {row.cwd}")
        if summary_id is not None:
            await self.injection(summary_id)              # 넣을 수 있는 요약인지 먼저(안 되면 띄우지도 않는다)
        base = "cc-" + re.sub(r"[^a-z0-9]+", "-", (row.project or "session").lower()).strip("-")
        existing = set((await tmux(self.socket, "list-sessions", "-F", "#{session_name}")).split())
        name, n = base, 2
        while name in existing:
            name, n = f"{base}-{n}", n + 1
        await tmux(self.socket, "new-session", "-d", "-s", name, "-c", row.cwd)
        pane = (await tmux(self.socket, "display-message", "-p", "-t", name, "#{pane_id}")).strip()
        await tmux(self.socket, "send-keys", "-t", pane, "-l", self.claude_bin)
        await tmux(self.socket, "send-keys", "-t", pane, "Enter")
        cc, pid, note = None, None, None
        loop = asyncio.get_running_loop()
        end = loop.time() + 45
        while loop.time() < end:
            await asyncio.sleep(1.0)
            screen = await tmux(self.socket, "capture-pane", "-p", "-t", pane)
            if re.search(r"trust (the files in )?this folder|Do you trust", screen, re.I):
                note = "폴더 신뢰 창 — 터미널에서 답한 뒤 [넣기]"
                break
            if cc is None:
                for ls in live_sessions(self.sessions_dir).values():
                    te = _tmux_env(ls.pid)
                    if te and te[1] == pane:
                        cc, pid = ls.session_id, ls.pid
                        break
            if cc and "❯" in screen and _status(self.sessions_dir, pid) != "busy":
                break
        await self._act(row.id, "spawn", pid, cc is not None, f"{name} {pane} cc={cc or '-'} {note or ''}")
        out: dict[str, Any] = {"tmux": name, "pane": pane, "cc_session_id": cc, "pid": pid, "note": note,
                               "injected": False}
        if cc is None and not note:
            out["note"] = "새 CC 세션을 45초 안에 찾지 못했다 — 터미널에서 확인"
            return out
        if summary_id is not None and cc and not note:
            await asyncio.sleep(1.0)
            r = await self.inject(summary_id, cc, row.cwd)
            out["injected"] = r["delivered"]
            if not r["delivered"]:
                out["note"] = "인계 글을 보냈지만 제출이 확인되지 않았다 — 입력 칸을 확인"
            else:
                self._notify(row, f"새 세션에 인계 넣음 — {name} (세션 {cc[:8]})")
        return out

    # ── 세션 조작 ────────────────────────────────────────
    async def action(self, row: SessionRow, act: str) -> dict[str, Any]:
        if not row.cc:
            raise Refused("CC 세션 ID가 없다")
        if act == "resume":
            return await self._resume(row)
        t, ls, busy = await resolve(row.cc, self.sessions_dir)
        if act == "interrupt":
            if not busy:
                raise Refused("일하는 중이 아니다 — 중단할 작업이 없다")
            await tmux(t.socket, "send-keys", "-t", t.pane, "Escape")
            await self._act(row.id, "interrupt", ls.pid, True, t.pane)
            return {"ok": True, "pane": t.pane}
        if busy:
            raise Refused("일하는 중 — 끝난 뒤에(또는 먼저 작업 중단)")
        if act == "exit":
            res = await deliver(row.cc, "/exit", sessions_dir=self.sessions_dir, transcript=None, command=True)
            gone = await self._wait(lambda: row.cc not in live_sessions(self.sessions_dir), 15)
            await self._act(row.id, "exit", ls.pid, gone, f"{t.pane} steps={','.join(res['steps'])}")
            return {"ok": gone, "pane": t.pane, "note": None if gone else "15초 안에 끝나지 않았다 — 터미널 확인"}
        if act == "stop":
            await tmux(t.socket, "send-keys", "-t", t.pane, "C-z")
            stopped = await self._wait(lambda: (_proc_stat(ls.pid) or ("?",))[0] == "T", 5)
            await self._act(row.id, "stop", ls.pid, stopped, t.pane)
            return {"ok": stopped, "pane": t.pane, "note": None if stopped else "5초 안에 멈추지 않았다"}
        raise Refused(f"모르는 조작: {act}")

    async def _resume(self, row: SessionRow) -> dict[str, Any]:
        live = live_sessions(self.sessions_dir).get(row.cc or "")
        if not live or live.state != "T":
            raise Refused("멈춘 세션이 아니다")
        if await self._foreman_stopped(row.id) != live.pid:
            raise Refused("FOREMAN이 멈춘 세션이 아니다 — 사람이 멈춘 것은 건드리지 않는다")
        te = _tmux_env(live.pid)
        if not te:
            raise Refused("tmux 밖 세션")
        socket, pane = te
        cmd = (await tmux(socket, "display-message", "-p", "-t", pane, "#{pane_current_command}")).strip()
        if cmd == "claude":
            raise Refused("pane 포그라운드가 이미 claude다")
        # fg는 가장 최근에 멈춘 작업을 되살린다 — 그 셸에 멈춘 작업이 이 claude 하나인지 본다
        await tmux(socket, "send-keys", "-t", pane, "-l", "fg")
        await tmux(socket, "send-keys", "-t", pane, "Enter")
        ok = await self._wait(lambda: (_proc_stat(live.pid) or ("?",))[0] != "T", 5)
        await self._act(row.id, "resume", live.pid, ok, pane)
        return {"ok": ok, "pane": pane, "note": None if ok else "5초 안에 돌아오지 않았다 — 터미널 확인"}

    @staticmethod
    async def _wait(cond: Any, secs: float) -> bool:
        loop = asyncio.get_running_loop()
        end = loop.time() + secs
        while loop.time() < end:
            if cond():
                return True
            await asyncio.sleep(0.3)
        return bool(cond())
