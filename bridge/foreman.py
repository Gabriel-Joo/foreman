"""포먼 디스패처(11-05, docs/11_foreman_dispatch.md) — 사람이 "뭘 하려는지" 말하면 포먼이 계획을 낸다.

포먼은 상주하지 않는다. 요청마다 브리지가 "상황 묶음"(프로젝트 · CLAUDE.md · 메모리 색인 · docs 색인 · 세션 · 인계 요약 · 파이프라인)을
LLM 없이 모아 `claude -p` 한 번에 넣고, 정해진 모양의 계획(JSON)을 받는다. 계획은 사람이 화면에서 보고 고친 뒤 승인해야 시작한다.

- 포먼은 읽기만: Read · Grep · Glob(docs를 찾아보게). 셸 · 쓰기 없음, 훅 끔, 세션 기록 안 남김(--no-session-persistence)
- 파일(CLAUDE.md · MEMORY.md · docs)은 mtime이 바뀐 것만 다시 읽는다
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.handoff import HandoffManager
from bridge.inject import Refused, _tmux_env, deliver
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.dispatch")

MODES = ("new", "handoff", "attach", "ask")
ROLES = ("coder", "inspector", "cicd")
PLAN_TIMEOUT_S = 180.0
_cache: dict[str, tuple[float, str]] = {}


def read_cached(path: Path, limit: int) -> str | None:
    """mtime이 같으면 전에 읽은 것. 없으면 None."""
    try:
        m = path.stat().st_mtime
    except OSError:
        return None
    k = str(path)
    if k in _cache and _cache[k][0] == m:
        return _cache[k][1]
    try:
        s = path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return None
    _cache[k] = (m, s)
    return s


def memory_dir(repo: str) -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", repo) / "memory"


def docs_index(repo: str, cap: int = 60) -> list[str]:
    out = []
    for p in sorted(Path(repo, "docs").glob("*.md"))[:cap]:
        head = read_cached(p, 4000) or ""
        title = next((ln.lstrip("# ").strip() for ln in head.splitlines() if ln.startswith("#")), "")
        out.append(f"docs/{p.name} — {title[:100]}")
    return out


async def _git(repo: str, *args: str) -> str:
    p = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), 5)
    except TimeoutError:
        p.kill()
        return ""
    return out.decode(errors="replace").strip()


INSTRUCTIONS = """너는 FOREMAN의 포먼(감독)이다. 사람이 하려는 일을 듣고, 어느 프로젝트에서 어떤 Claude Code 세션으로 할지 계획을 낸다.
너는 계획만 낸다 — 세션을 띄우는 것은 사람이 계획을 승인한 뒤 브리지가 한다. 파일을 고치거나 명령을 실행하지 마라.
필요하면 Read · Grep · Glob으로 아래 경로의 문서(CLAUDE.md · 메모리 · docs)를 더 읽어도 된다. 읽기는 꼭 필요한 만큼만.

판단할 것:
1. project — 아래 목록의 이름 하나. 모호하면 mode "ask"로 되묻는다(추측해서 고르지 마라)
2. mode
   - "attach": 같은 일을 이미 하고 있는 살아 있는 tmux 세션이 있으면 새로 띄우지 말고 그 세션에 보낼 글만 쓴다(attach_session)
   - "handoff": 끝났거나 오래된 세션의 일을 이어 가야 하면 그 세션의 인계 요약(summary_id)을 쓴다. 요약이 없으면 "new"로 하고 이유에 적는다
   - "new": 새 일
   - "ask": 모호하거나 위험해서 사람이 정해야 할 것이 있을 때(questions에 물을 것)
3. role — "coder"(고치기 · 만들기) · "inspector"(살펴보기 · 원인 찾기) · "cicd"(빌드 · 배포)
4. read_only — 원인 분석 · 조사만이면 true(CC 읽기 전용 모드로 띄운다). 고치는 일이면 false
5. title — 세션 이름(한국어, 짧게)
6. first_prompt — 새 세션(또는 attach 세션)에 넣을 첫 글. 한국어로:
   - 무엇을 하려는지(사람의 요청을 구체적으로)
   - 먼저 읽을 문서 경로(docs/… — 새 세션은 CLAUDE.md와 메모리 색인은 스스로 읽으니 다시 옮기지 마라)
   - 지켜야 할 것: 상황 묶음에 보이는 사용자 결정 · 금지(특히 압축 손실 점검 목록에서 이 일과 겹치는 것)
   - 끝에 "이해한 것을 5줄 안으로 말하고, 시작하기 전에 사용자의 확인을 기다려라."
   - 인계 요약 본문은 넣지 마라 — summary_id를 고르면 브리지가 뒤에 붙인다
7. reasons — 왜 이렇게 판단했는지(짧게, 근거가 된 세션 · 요약 · 문서를 짚어서)
8. confidence — 0~1. 0.6 아래면 mode "ask"를 생각하라

답은 아래 JSON 하나만, ```json 블록으로. 다른 말은 쓰지 마라.
```json
{"project": "...", "mode": "new|handoff|attach|ask", "base_session": null, "summary_id": null, "attach_session": null,
 "role": "coder", "read_only": false, "title": "...", "first_prompt": "...", "reasons": ["..."], "confidence": 0.8,
 "questions": []}
```"""


class ForemanDispatcher:
    def __init__(self, engine: AsyncEngine, sessions_dir: str | Path, handoff: HandoffManager, projects: Any,
                 pipeline_snapshot: Any = None, claude_bin: str = "claude", model: str = "sonnet",
                 workdir: str | Path | None = None) -> None:
        self.engine, self.sessions_dir, self.handoff = engine, sessions_dir, handoff
        self.projects = projects                     # () -> [(repo, project_id, name, char_id)]
        self.pipeline_snapshot = pipeline_snapshot   # async () -> {"projects": [...]}
        self.claude_bin, self.model = claude_bin, model
        self.workdir = Path(workdir or Path.home() / ".foreman" / "dispatch")

    # ── 상황 묶음 ────────────────────────────────────────
    async def context(self, request: str) -> str:
        from bridge.api.dashboard import LABEL
        projs = self.projects() or []
        # 요청에 프로젝트 이름(영문 · 한국어 이름표)이 있으면 그 프로젝트만 자세히 — 없으면 전부(토큰을 아낀다)
        named = lambda p: p[2] in request or p[2].split("-")[0] in request or (LABEL.get(p[2]) or "\0") in request   # noqa: E731
        wanted = [p for p in projs if named(p)] or projs
        live = live_sessions(self.sessions_dir)
        parts = [f"# 지금 시각 {time.strftime('%Y-%m-%d %H:%M')} (KST)", f"# 사람의 요청\n{request}"]
        async with self.engine.connect() as c:
            for repo, _pid, name, _ch in projs:
                full = any(p[2] == name for p in wanted)
                branch = await _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
                commits = await _git(repo, "log", "--oneline", "-5", "--no-decorate")
                dirty = len([x for x in (await _git(repo, "status", "--porcelain")).splitlines() if x.strip()])
                sec = [f"\n## 프로젝트 {name} (화면 이름 {LABEL.get(name, name)}){'' if full else ' — 요약만'}\n- 저장소: {repo} (브랜치 {branch}, 고친 채 커밋 안 한 파일 {dirty}개)",
                       "- 최근 커밋:\n" + "\n".join("  " + x[:140] for x in commits.splitlines())]
                if full:
                    cm = read_cached(Path(repo, "CLAUDE.md"), 6000)
                    sec.append(f"- CLAUDE.md({repo}/CLAUDE.md):\n" + ("\n".join("  " + x for x in cm.splitlines()) if cm else "  (없음)"))
                    mi = read_cached(memory_dir(repo) / "MEMORY.md", 4000)
                    sec.append(f"- 메모리 색인({memory_dir(repo)}/MEMORY.md — 새 세션이 스스로 읽는다):\n" +
                               ("\n".join("  " + x for x in mi.splitlines()) if mi else "  (없음)"))
                    di = docs_index(repo)
                    if di:
                        sec.append("- docs 목록(본문은 Read로):\n" + "\n".join("  " + x for x in di))
                    loss = sorted(Path(__file__).resolve().parent.parent.joinpath("log").glob(f"{name}_compaction_loss_*.md"))
                    if loss:
                        sec.append(f"- 압축 손실 점검(이 프로젝트 세션이 잊은 사용자 지시 · 결정 목록): {loss[-1]} — 이 일과 겹치는 항목은 first_prompt의 '지켜야 할 것'에")
                # 세션 — 살아 있는 것 + 최근 48시간
                rows = (await c.execute(text(
                    "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), cs.role, cs.cwd, "
                    "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id), "
                    "(SELECT LEFT(t.prompt_text, 240) FROM turn t WHERE t.session_id = cs.id AND t.origin = 'human' ORDER BY t.seq DESC LIMIT 1) "
                    "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
                    "WHERE p.name = :n AND cs.type = 'agent' ORDER BY cs.id DESC LIMIT 25"), {"n": name})).all()
                ss = []
                for sid, cc, title, role, cwd, last, prompt in rows:
                    ls = live.get(cc or "")
                    if not ls and not (last and (datetime.now(UTC).replace(tzinfo=None) - last).total_seconds() < 48 * 3600):   # DB 시각은 UTC
                        continue
                    state = ("멈춤" if ls.state == "T" else "살아 있음") if ls else "끝남"
                    tm = "tmux 안(입력 가능)" if ls and _tmux_env(ls.pid) else ("tmux 밖(입력 불가)" if ls else "")
                    ss.append(f"  - 세션 {sid} \"{title or cc[:8]}\" [{state}{', ' + tm if tm else ''}] 역할 {role}, 마지막 활동 {last}(UTC)")
                    # 이 세션이 지금 무슨 일을 하는지 — 최근 사람 요청 3개 · 마지막 답 앞부분(같은 일을 하는 세션이면 attach)
                    hum = (await c.execute(text(
                        "SELECT t.started_at, LEFT(t.prompt_text, 400), "
                        "(SELECT LEFT(JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')), 300) FROM event e WHERE e.turn_id = t.id "
                        " AND e.type = 'assistant_msg' AND e.subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.block')) = 'text' "
                        " ORDER BY e.id DESC LIMIT 1) "
                        "FROM turn t WHERE t.session_id = :s AND t.origin = 'human' ORDER BY t.seq DESC LIMIT 3"), {"s": sid})).all()
                    for at, pr, rep in hum:
                        p_ = re.sub(r"\s+", " ", re.sub(r"</?pasted_content[^>]*>", "", pr or ""))[:220]
                        ss.append(f"    · {at:%m-%d %H:%M} 사람 요청: {p_}" + (f"\n      → 답: {re.sub(chr(10), ' ', rep or '')[:220]}" if rep else ""))
                    srow = (await c.execute(text(
                        "SELECT id, created_at, LEFT(body, 700) FROM summary WHERE session_id = :s AND status = 'ok' ORDER BY id DESC LIMIT 1"),
                        {"s": sid})).first()
                    if srow:
                        ss.append(f"    · 인계 요약 summary_id={srow[0]} ({srow[1]}) 앞부분: " + re.sub(r"\s+", " ", srow[2] or "")[:600])
                sec.append("- 세션:\n" + ("\n".join(ss) if ss else "  (최근 세션 없음)"))
                parts.append("\n".join(sec))
        if self.pipeline_snapshot:
            try:
                snap = await self.pipeline_snapshot()
                pl = []
                for p in snap.get("projects", []):
                    ch = (p.get("chains") or [None])[0]
                    if ch:
                        st = ", ".join(f"{k} {v.get('status')}" for k, v in (ch.get("stages") or {}).items())
                        pl.append(f"- {p['project']}: 마지막 빌드 {ch.get('short')} — {st}" + (f" (깨짐: {ch['broke']})" if ch.get("broke") else ""))
                if pl:
                    parts.append("\n## 파이프라인\n" + "\n".join(pl))
            except Exception as e:  # noqa: BLE001
                log.warning("파이프라인 상태를 못 읽음: %s", type(e).__name__)
        return "\n".join(parts)

    # ── 계획 ─────────────────────────────────────────────
    async def plan(self, request: str) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise Refused("무엇을 하려는지 적어 주세요")
        t0 = time.monotonic()
        ctx = await self.context(request)
        prompt = INSTRUCTIONS + "\n\n# 상황 묶음\n" + ctx
        did = await self._record(request, len(ctx))
        self.workdir.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        dirs = [x for p in (self.projects() or []) for x in ("--add-dir", p[0])]
        try:
            p = await asyncio.create_subprocess_exec(
                self.claude_bin, "-p", "--model", self.model, "--output-format", "json", "--no-session-persistence",
                "--settings", json.dumps({"disableAllHooks": True}),
                "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent",
                *dirs,                                   # --add-dir는 값을 여러 개 받아 뒤의 인자를 삼킨다 — 프롬프트는 stdin으로
                cwd=str(self.workdir), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env)
            out, err = await asyncio.wait_for(p.communicate(prompt.encode()), PLAN_TIMEOUT_S)
        except TimeoutError:
            p.kill()
            await self._finish(did, None, "failed", f"포먼이 {PLAN_TIMEOUT_S:.0f}초 안에 답하지 않았습니다", t0)
            raise Refused(f"포먼이 {PLAN_TIMEOUT_S:.0f}초 안에 답하지 않았습니다") from None
        except OSError as e:
            await self._finish(did, None, "failed", f"claude를 띄우지 못했습니다: {e}", t0)
            raise Refused(f"claude를 띄우지 못했습니다: {e}") from None
        raw = out.decode(errors="replace")
        try:
            result = json.loads(raw).get("result", "")
        except ValueError:
            result = raw
        plan = parse_plan(result)
        if plan is None:
            await self._finish(did, None, "failed", "포먼의 답에서 계획(JSON)을 찾지 못했습니다: " + (result or err.decode(errors="replace"))[:300], t0)
            raise Refused("포먼의 답에서 계획을 찾지 못했습니다. 다시 물어보거나 직접 골라 주세요")
        plan = await self.check(plan)
        await self._finish(did, plan, "planned", None, t0)
        return {"dispatch_id": did, "plan": plan, "ms": round((time.monotonic() - t0) * 1000), "context_chars": len(ctx)}

    async def check(self, plan: dict[str, Any]) -> dict[str, Any]:
        """포먼의 계획을 사실과 맞춘다 — 없는 프로젝트 · 남의 요약 · 죽은 세션을 고르면 경고를 붙이고 비운다."""
        warn = []
        names = {p[2]: p[0] for p in (self.projects() or [])}
        if plan.get("mode") not in MODES:
            warn.append(f"모르는 방식 {plan.get('mode')!r} → new"); plan["mode"] = "new"
        if plan.get("role") not in ROLES:
            plan["role"] = "coder"
        if plan.get("project") not in names and plan["mode"] != "ask":
            warn.append(f"모르는 프로젝트 {plan.get('project')!r} — 사람이 골라 주세요"); plan["mode"] = "ask"
        plan["repo"] = names.get(plan.get("project"))
        async with self.engine.connect() as c:
            if plan.get("summary_id"):
                r = (await c.execute(text("SELECT s.status, p.name FROM summary s JOIN character_session cs ON cs.id = s.session_id "
                                          "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                                          "WHERE s.id = :i"), {"i": plan["summary_id"]})).first()
                if not r or r[0] != "ok" or r[1] != plan.get("project"):
                    warn.append(f"인계 요약 {plan['summary_id']}을(를) 쓸 수 없습니다(없거나 다른 프로젝트) — 비웠습니다"); plan["summary_id"] = None
            if plan.get("attach_session"):
                r = (await c.execute(text("SELECT cc_session_id FROM character_session WHERE id = :i"), {"i": plan["attach_session"]})).first()
                ls = live_sessions(self.sessions_dir).get(r[0]) if r else None
                if not ls or ls.state == "T" or not _tmux_env(ls.pid):
                    warn.append(f"세션 {plan['attach_session']}에 보낼 수 없습니다(끝났거나 tmux 밖) — 새로 띄우기로 바꿨습니다")
                    plan["attach_session"] = None
                    plan["mode"] = "handoff" if plan.get("summary_id") else "new"
        if plan["mode"] == "attach" and not plan.get("attach_session"):
            plan["mode"] = "new"
        if plan["mode"] == "handoff" and not plan.get("summary_id"):
            plan["mode"] = "new"
        # 따로 작업(worktree, 11-05) — 그 프로젝트에 살아 있는 세션이 있으면 기본으로 켠다. 사람이 카드에서 끌 수 있다
        repo = plan.get("repo")
        others = [ls for ls in live_sessions(self.sessions_dir).values()
                  if repo and (ls.cwd == repo or ls.cwd.startswith(repo.rstrip("/") + "/"))]
        plan["live_here"] = len(others)
        if plan.get("worktree") is None:
            plan["worktree"] = bool(others)
        plan["warnings"] = warn + list(plan.get("warnings") or [])
        plan["first_prompt"] = str(plan.get("first_prompt") or "")[:12000]
        plan["title"] = str(plan.get("title") or "")[:120]
        return plan

    # ── 시작 ─────────────────────────────────────────────
    async def start(self, dispatch_id: int, plan: dict[str, Any]) -> dict[str, Any]:
        plan = await self.check(dict(plan))
        if plan["mode"] == "ask":
            raise Refused("포먼이 되묻는 계획입니다 — 질문에 답해 다시 물어보거나 직접 골라 주세요")
        if not plan["first_prompt"].strip():
            raise Refused("넣을 첫 글이 비었습니다")
        if plan["mode"] == "attach":
            async with self.engine.connect() as c:
                r = (await c.execute(text("SELECT cc_session_id, cwd FROM character_session WHERE id = :i"), {"i": plan["attach_session"]})).first()
            from bridge.handoff import transcript_path
            res = await deliver(r[0], plan["first_prompt"], sessions_dir=self.sessions_dir, transcript=transcript_path(r[1] or "", r[0]))
            out = {"mode": "attach", "session_id": plan["attach_session"], "injected": bool(res.get("delivered")), "queued": res.get("queued")}
        else:
            out = await self.handoff.spawn_new(plan["repo"], plan.get("summary_id") if plan["mode"] == "handoff" else None,
                                               plan.get("title") or None, first_prompt=plan["first_prompt"],
                                               read_only=bool(plan.get("read_only")), role=plan.get("role"),
                                               worktree=bool(plan.get("worktree")))
            out["mode"] = plan["mode"]
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET edited = :e, status = 'started', started_at = NOW(3), session_id = :s WHERE id = :i"),
                            {"e": json.dumps(plan, ensure_ascii=False), "s": out.get("session_id"), "i": dispatch_id})
        return out

    async def _record(self, request: str, chars: int) -> int:
        async with self.engine.begin() as c:
            r = await c.execute(text("INSERT INTO dispatch (request, context_chars, model, status) VALUES (:r, :n, :m, 'planned')"),
                                {"r": request, "n": chars, "m": self.model})
            return r.lastrowid

    async def _finish(self, did: int, plan: dict[str, Any] | None, status: str, error: str | None, t0: float) -> None:
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET plan = :p, status = :s, error = :e, ms = :ms WHERE id = :i"),
                            {"p": json.dumps(plan, ensure_ascii=False) if plan else None, "s": status, "e": (error or "")[:1000] or None,
                             "ms": round((time.monotonic() - t0) * 1000), "i": did})


def parse_plan(s: str) -> dict[str, Any] | None:
    """포먼의 답에서 계획 JSON — ```json 블록이 있으면 그것, 없으면 첫 { … 마지막 }."""
    m = re.findall(r"```json\s*(\{.*?\})\s*```", s or "", re.S)
    cands = m[::-1] or ([s[s.find("{"): s.rfind("}") + 1]] if s and "{" in s else [])
    for c in cands:
        try:
            d = json.loads(c)
        except ValueError:
            continue
        if isinstance(d, dict) and "mode" in d:
            return d
    return None
