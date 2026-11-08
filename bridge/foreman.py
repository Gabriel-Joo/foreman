"""디스패처(11-05, docs/11_foreman_dispatch.md · 11-08 docs/14_dispatcher_note_wake.md) — 사람이 "뭘 하려는지" 말하면 계획을 낸다.

화면의 감독실 캐릭터(오피스 팀장 · 마법학교 교장 · 현장 소장 · 기본 디스패처)가 이 디스패처의 얼굴이다. 세션은 없다.
디스패처는 상주하지 않는다. 요청마다 브리지가 "상황 묶음"(프로젝트 · CLAUDE.md · 메모리 색인 · docs 색인 · 노트 · 지난 디스패치 ·
세션 · 인계 요약 · 파이프라인)을 LLM 없이 모아 `claude -p` 한 번에 넣고, 정해진 모양의 계획(JSON)을 받는다.
계획은 사람이 화면에서 보고 고친 뒤 승인해야 시작한다. 노트 고치기 제안도 같은 [시작]으로 반영한다(bridge/foreman_note.py).

- 디스패처는 읽기만: Read · Grep · Glob(docs를 찾아보게). 셸 · 쓰기 없음, 훅 끔, 세션 기록 안 남김(--no-session-persistence)
- 파일(CLAUDE.md · MEMORY.md · docs)은 mtime이 바뀐 것만 다시 읽는다
- 계획의 출처: human(사람이 말함) · wake(실패 이벤트 — bridge/wake.py, 계획만 만들고 사람에게 [시작]?을 묻는다)
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

from bridge import foreman_note as notes
from bridge.handoff import HandoffManager
from bridge.inject import Refused, _tmux_env, deliver
from bridge.liveness import live_sessions
from bridge.usage import record_cli

log = logging.getLogger("foreman.dispatch")

MODES = ("new", "handoff", "attach", "ask")
ROLES = ("coder", "inspector", "cicd", "scribe")
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


OPS_DOC = Path(__file__).resolve().parent.parent / "docs" / "operations.md"


def server_paths() -> str:
    """서버 공통 경로(클러스터 VM · 매니페스트 · 저장소 · 접속) — 어느 프로젝트 일이든 상황 묶음에 늘 넣는다.
    11-06: 포먼 CLAUDE.md 정리로 이 표가 docs/operations.md 「1.」로 갔다. 전후 비교에서 계획은 같았지만, "펫퍼민트 파드 보기"처럼
    포먼 이름이 없는 요청은 정리 전에도 이 표를 못 봐 kubectl 들어가는 법(vagrant ssh m-k8s)이 첫 글에 빠졌다."""
    body = read_cached(OPS_DOC, 8000) or ""
    m = re.search(r"^## 1\..*?$(.*?)(?=^## )", body, re.S | re.M)
    return m.group(1).strip() if m else ""


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


async def _git_checked(repo: str, *args: str) -> str:
    """실패하면 예외 — 노트의 옛 HEAD가 없어진 것(리베이스 등)을 "아무 일 없음"과 가르려고."""
    p = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), 5)
    except TimeoutError:
        p.kill()
        raise RuntimeError("git 시간 초과") from None
    if p.returncode:
        raise RuntimeError(f"git {args[0]} 실패")
    return out.decode(errors="replace").strip()


ALIASES ={"foreman": ("포먼", "FOREMAN", "Foreman")}   # 11-08 화면 이름표가 FOREMAN으로 — 사람은 여전히 "포먼"이라고 쓴다

INSTRUCTIONS = """너는 FOREMAN의 디스패처(감독)다. 사람이 하려는 일을 듣고, 어느 프로젝트에서 어떤 Claude Code 세션으로 할지 계획을 낸다.
너는 계획만 낸다 — 세션을 띄우는 것은 사람이 계획을 승인한 뒤 브리지가 한다. 파일을 고치거나 명령을 실행하지 마라.
필요하면 Read · Grep · Glob으로 아래 경로의 문서(CLAUDE.md · 메모리 · docs)를 더 읽어도 된다. 읽기는 꼭 필요한 만큼만.

판단할 것:
1. project — 아래 목록의 이름 하나. 모호하면 mode "ask"로 되묻는다(추측해서 고르지 마라)
2. mode
   - "attach": 같은 일을 이미 하고 있는 살아 있는 tmux 세션이 있으면 새로 띄우지 말고 그 세션에 보낼 글만 쓴다(attach_session)
   - "handoff": 끝났거나 오래된 세션의 일을 이어 가야 하면 그 세션의 인계 요약(summary_id)을 쓴다. 요약이 없으면 "new"로 하고 이유에 적는다
   - "new": 새 일
   - "ask": 모호하거나 위험해서 사람이 정해야 할 것이 있을 때(questions에 물을 것)
3. role — "coder"(고치기 · 만들기) · "inspector"(살펴보기 · 원인 찾기) · "cicd"(빌드 · 배포) · "scribe"(서기 — 문서 일)
   - scribe 일감(docs/12_scribe.md): 회고(retro) · 문서 맞추기(sync) · CLAUDE.md 정리(trim) · 압축 손실 반영(loss) · 포트폴리오
   - 회고 · 문서 정리 요청이면 scribe. 서기는 따로 작업(worktree)으로 띄우고, 합치기가 사람의 검토다
   - 회고의 first_prompt에는 기간(KST)을 꼭 적는다. 재료 묶음은 사람이 `python -m bridge.scribe`로 만든 경로를 준다
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
9. note_updates — 그 프로젝트 "노트"를 고칠 제안(없으면 []). 노트는 다음에 너를 부를 때 다시 들어간다. 사람이 [시작]을 누를 때만 반영된다
   - 쌓는 것은 둘뿐: "thread"(진행 중인 일 줄기 — 무엇을 · 어느 세션들에서 · 어디까지 · 남은 것) ·
     "decision"(사람이 정한 판단 · 금지 — 사람의 말이나 log에 근거가 있는 것만)
   - 쌓지 마라: 저장소 구조 · 자주 쓰는 명령 · 파일 경로 목록 — CLAUDE.md · 메모리 · docs에 있고 새 세션이 스스로 읽는다
   - {"op": "add", "kind": "thread|decision", "body": "300자 안", "source": "세션 N | log/….md | docs/….md | dispatch #N | 커밋 <sha>"}
     · {"op": "update", "id": 노트번호, "kind": ..., "body": ..., "source": ...} · {"op": "retire", "id": 노트번호, "why": "..."}
     · {"op": "touch", "id": 노트번호} (다시 확인했는데 아직 맞다 — 확인 시각만 새로)
   - 이번 요청이 노트의 진행 중인 일을 잇는다면 그 줄을 update해 지금 상태로. 끝난 일은 retire
   - ⚠ 표시(확인 뒤 바뀜)가 붙은 줄은 그대로 믿지 말고, 필요하면 Read로 확인한 뒤 update · retire · touch를 제안하라
   - 사람의 요청 글 자체가 근거면 source를 비워 둔다(브리지가 이번 dispatch 번호를 넣는다)
   - 노트 상한은 프로젝트마다 약 2000토큰이다. 짧게 쓰고, 넘치면 오래된 것을 retire하라

답은 아래 JSON 하나만, ```json 블록으로. 다른 말은 쓰지 마라.
```json
{"project": "...", "mode": "new|handoff|attach|ask", "base_session": null, "summary_id": null, "attach_session": null,
 "role": "coder", "read_only": false, "title": "...", "first_prompt": "...", "reasons": ["..."], "confidence": 0.8,
 "questions": [], "note_updates": []}
```"""

WAKE_HINT = """
# 이번 요청은 사람이 아니라 실패 이벤트가 불렀다(자동 기상 2단계)
- 계획은 사람이 텔레그램 · 화면에서 보고 [시작]을 눌러야 시작한다. 사람은 지금 자리에 없을 수 있다 — first_prompt만 읽어도 무엇을 할지 알 수 있게
- 원인을 살펴보는 일이다: role "inspector", read_only true. 고치기는 사람이 결과를 보고 정한다
- 같은 실패를 이미 살펴보는 살아 있는 세션이 있으면 "attach"
- 실패 알림 글에 프로젝트가 없으면(인프라 전체) 서버 공통 경로를 보고 가장 가까운 프로젝트를 고르고 이유에 적는다"""


class ForemanDispatcher:
    def __init__(self, engine: AsyncEngine, sessions_dir: str | Path, handoff: HandoffManager, projects: Any,
                 pipeline_snapshot: Any = None, claude_bin: str = "claude", model: str = "sonnet",
                 workdir: str | Path | None = None) -> None:
        self.engine, self.sessions_dir, self.handoff = engine, sessions_dir, handoff
        self.projects = projects                     # () -> [(repo, project_id, name, char_id)]
        self.pipeline_snapshot = pipeline_snapshot   # async () -> {"projects": [...]}
        self.claude_bin, self.model = claude_bin, model
        self.workdir = Path(workdir or Path.home() / ".foreman" / "dispatch")
        self.running: dict[int, str | None] = {}    # 지금 claude -p가 도는 디스패치 → 프로젝트(캐릭터가 일하는 모습)
        self.on_change: Any = None                  # 상태가 바뀌면(계획 시작 · 끝 · 시작 · 버림) 화면에 알린다

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

    # ── 상황 묶음 ────────────────────────────────────────
    async def context(self, request: str, project: str | None = None, wake: bool = False) -> str:
        from bridge.api.dashboard import LABEL
        projs = self.projects() or []
        # 요청에 프로젝트 이름(영문 · 한국어 이름표 · 별명)이 있으면 그 프로젝트만 자세히 — 없으면 전부(토큰을 아낀다).
        # 화면의 그 방 팀장실에서 말하면 project가 정해져 온다
        def named(p: Any) -> bool:
            if project:
                return p[2] == project
            keys = (p[2], p[2].split("-")[0], LABEL.get(p[2]) or "\0", *ALIASES.get(p[2], ()))
            return any(k in request for k in keys)
        wanted = [p for p in projs if named(p)] or projs
        live = live_sessions(self.sessions_dir)
        parts = [f"# 지금 시각 {time.strftime('%Y-%m-%d %H:%M')} (KST)",
                 f"# {'실패 이벤트(자동)' if wake else '사람의 요청'}\n{request}"]
        if project:
            parts.append(f"# 사람이 {LABEL.get(project, project)}({project}) 방에서 말했다 — 다른 프로젝트라는 근거가 없으면 이 프로젝트")
        sp = server_paths()
        if sp:
            parts.append(f"# 서버 공통 경로({OPS_DOC} 「1.」 — 클러스터 · VM · 인프라 일이면 first_prompt에 그대로 옮긴다)\n{sp}")
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
                    # 노트(11-08) — 진행 중인 일 · 사람이 정한 판단. 확인 뒤 바뀐 것은 ⚠로. 상한을 넘친 줄은 접혀 안 들어간다
                    head = await _git(repo, "rev-parse", "HEAD")
                    nt = await notes.render(c, name, head or None, _git_checked, repo)
                    fold = f", 접힌 줄 {nt['folded']}개" if nt["folded"] else ""
                    sec.append(f"- 노트(약 {nt['tokens']}/{nt['cap']}토큰{fold}):\n"
                               + (nt["text"] or "  (아직 없음 — 이번 일이 이어질 일이면 thread를, 사람이 정한 판단이 보이면 decision을 제안하라)"))
                    rd = await notes.recent_dispatches(c, name)
                    if rd:
                        sec.append("- 지난 디스패치(사람이 고친 칸 — 같은 실수를 되풀이하지 마라):\n" + "\n".join(rd))
                # 세션 — 살아 있는 것 + 최근 48시간
                rows = (await c.execute(text(
                    "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), cs.role, cs.cwd, "
                    "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id), "
                    "(SELECT LEFT(t.prompt_text, 240) FROM turn t WHERE t.session_id = cs.id AND t.origin = 'human' ORDER BY t.seq DESC LIMIT 1) "
                    "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
                    "WHERE p.name = :n AND cs.type = 'agent' AND cs.hidden_at IS NULL ORDER BY cs.id DESC LIMIT 25"), {"n": name})).all()
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
    async def plan(self, request: str, project: str | None = None, origin: str = "human",
                   wake_key: str | None = None, wake_text: str | None = None) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise Refused("무엇을 하려는지 적어 주세요")
        if project and project not in {p[2] for p in (self.projects() or [])}:
            project = None
        t0 = time.monotonic()
        wake = origin == "wake"
        ctx = await self.context(request, project, wake)
        prompt = INSTRUCTIONS + (WAKE_HINT if wake else "") + "\n\n# 상황 묶음\n" + ctx
        did = await self._record(request, len(ctx), origin, project, wake_key, wake_text)
        self.running[did] = project
        self._changed()
        try:
            return await self._plan(did, prompt, len(ctx), t0)
        finally:
            self.running.pop(did, None)
            self._changed()

    async def _plan(self, did: int, prompt: str, ctx_chars: int, t0: float) -> dict[str, Any]:
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
            # 화면 · 알림에 나가는 글 — "디스패처"라고 쓰지 않는다(11-09)
            await self._finish(did, None, "failed", f"{PLAN_TIMEOUT_S:.0f}초 안에 계획을 받지 못했습니다", t0)
            raise Refused(f"{PLAN_TIMEOUT_S:.0f}초 안에 계획을 받지 못했습니다") from None
        except OSError as e:
            why = f"claude를 띄우지 못했습니다: {e}" + (f" — PATH에 {self.claude_bin}가 없습니다(브리지 서비스의 PATH 확인)"
                                                       if isinstance(e, FileNotFoundError) else "")
            await self._finish(did, None, "failed", why, t0)
            raise Refused(why) from None
        raw = out.decode(errors="replace")
        try:
            j = json.loads(raw)
            result = j.get("result", "")
        except ValueError:
            j, result = None, raw
        # 11-08 — --no-session-persistence라 트랜스크립트가 없다. 사용량은 여기서만 남는다(docs/15_usage.md)
        await record_cli(self.engine, "dispatch", did, self.running.get(did), j)
        plan = parse_plan(result)
        if plan is None:
            await self._finish(did, None, "failed", "답에서 계획(JSON)을 찾지 못했습니다: " + (result or err.decode(errors="replace"))[:300], t0)
            raise Refused("답에서 계획을 찾지 못했습니다. 다시 물어보거나 직접 골라 주세요")
        plan = await self.check(plan)
        await self._finish(did, plan, "planned", None, t0)
        return {"dispatch_id": did, "plan": plan, "ms": round((time.monotonic() - t0) * 1000), "context_chars": ctx_chars}

    async def check(self, plan: dict[str, Any]) -> dict[str, Any]:
        """디스패처의 계획을 사실과 맞춘다 — 없는 프로젝트 · 남의 요약 · 죽은 세션을 고르면 경고를 붙이고 비운다."""
        warn = []
        names = {p[2]: p[0] for p in (self.projects() or [])}
        if plan.get("mode") not in MODES:
            warn.append(f"모르는 방식 {plan.get('mode')!r} → new"); plan["mode"] = "new"
        if plan.get("role") not in ROLES:
            plan["role"] = "coder"
        if plan["role"] == "inspector" and not plan.get("read_only") and "read_only_set" not in plan:
            plan["read_only"] = True      # 점검은 살펴보기 — 고치기 전에 승인(카드에서 끌 수 있다, 끄면 read_only_set)
            warn.append("역할이 점검이라 읽기 전용으로 시작합니다")
        plan.pop("read_only_set", None)
        # 모델(11-05) — 포먼(LLM)은 고르지 않는다. 사람이 카드에서 고른 값이 목록에 있으면 그것, 아니면 역할 기본값
        plan["model"] = self.handoff.models.pick(plan.get("model"), plan["role"])
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
            # 노트 고치기 제안(11-08) — 그 프로젝트의 지금 노트와 맞춘다. 프로젝트를 바꾸면 다른 프로젝트 줄 제안은 빠진다
            plan["note_updates"], nw = await notes.check_ops(c, plan.get("project") if plan.get("project") in names else None,
                                                             plan.get("note_updates") or [])
            warn += nw
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
        async with self.engine.connect() as c:
            st = (await c.execute(text("SELECT status FROM dispatch WHERE id = :i"), {"i": dispatch_id})).scalar()
        if st != "planned":
            raise Refused({"started": "이미 시작한 계획입니다", "discarded": "버린 계획입니다", "failed": "실패한 계획입니다"}.get(
                st or "", "없는 계획입니다"))
        plan = await self.check(dict(plan))
        if plan["mode"] == "ask":
            raise Refused("되묻는 계획입니다 — 질문에 답해 다시 물어보거나 직접 골라 주세요")
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
                                               worktree=bool(plan.get("worktree")), model=plan.get("model"))
            out["mode"] = plan["mode"]
        head = await _git(plan["repo"], "rev-parse", "HEAD") if plan.get("repo") else ""
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET edited = :e, status = 'started', started_at = NOW(3), session_id = :s, project = :p WHERE id = :i"),
                            {"e": json.dumps(plan, ensure_ascii=False), "s": out.get("session_id"), "p": plan.get("project"), "i": dispatch_id})
            # 노트 — 사람이 켠 제안만, 이 [시작]과 같은 트랜잭션으로
            touched = await notes.apply(c, plan["project"], plan.get("note_updates") or [], dispatch_id,
                                        out.get("session_id") or plan.get("attach_session"), head or None)
        out["notes"] = len(touched)
        self._changed()
        return out

    async def get(self, dispatch_id: int) -> dict[str, Any]:
        """화면이 계획 하나를 다시 연다(텔레그램 링크 · 말풍선 [제안]) — 계획은 그때 사실과 다시 맞춘다."""
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT id, origin, project, request, status, plan, wake_text, created_at, error FROM dispatch WHERE id = :i"),
                                 {"i": dispatch_id})).first()
        if not r:
            raise Refused("없는 계획입니다")
        plan = json.loads(r[5]) if r[5] else None
        if plan and r[4] == "planned":
            plan = await self.check(plan)
        return {"dispatch_id": r[0], "origin": r[1], "project": r[2], "request": r[3], "status": r[4], "plan": plan,
                "wake_text": r[6], "created_at": r[7].isoformat() + "Z" if r[7] else None, "error": r[8]}

    async def discard(self, dispatch_id: int) -> None:
        async with self.engine.begin() as c:
            r = await c.execute(text("UPDATE dispatch SET status = 'discarded' WHERE id = :i AND status = 'planned'"), {"i": dispatch_id})
        if not r.rowcount:
            raise Refused("이미 시작했거나 버린 계획입니다")
        self._changed()

    async def state(self) -> dict[str, Any]:
        """화면의 감독실 캐릭터 — 지금 계획을 세우는 중(프로젝트) · [시작]을 기다리는 자동 제안(24시간 안)."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, project, wake_text, JSON_UNQUOTE(JSON_EXTRACT(plan, '$.title')), created_at FROM dispatch "
                "WHERE origin = 'wake' AND status = 'planned' AND plan IS NOT NULL AND created_at > NOW(3) - INTERVAL 1 DAY ORDER BY id DESC"))).all()
        return {"running": [{"dispatch_id": k, "project": v} for k, v in self.running.items()],
                "pending": [{"dispatch_id": r[0], "project": r[1], "why": r[2], "title": r[3],
                             "created_at": r[4].isoformat() + "Z"} for r in rows]}

    async def notes_of(self, project: str) -> dict[str, Any]:
        """패널 — 그 프로젝트의 노트(접힘 · 확인 뒤 바뀐 것 포함)와 지난 디스패치."""
        repo = next((p[0] for p in (self.projects() or []) if p[2] == project), None)
        if not repo:
            raise Refused("모르는 프로젝트입니다")
        head = await _git(repo, "rev-parse", "HEAD")
        async with self.engine.connect() as c:
            nt = await notes.render(c, project, head or None, _git_checked, repo)
            rd = await notes.recent_dispatches(c, project, 8)
        items = [{"id": n["id"], "kind": n["kind"], "body": n["body"], "source": n["source"], "drift": n["drift"],
                  "folded": n["folded"], "checked_at": n["checked_at"].isoformat() + "Z"} for n in nt["notes"]]
        return {"project": project, "notes": items, "tokens": nt["tokens"], "cap": nt["cap"], "folded": nt["folded"],
                "dispatches": [x.strip()[2:] for x in rd]}

    async def retire_note(self, note_id: int) -> None:
        async with self.engine.begin() as c:
            if not await notes.retire_by_hand(c, note_id):
                raise Refused("이미 내린 줄입니다")

    async def _record(self, request: str, chars: int, origin: str = "human", project: str | None = None,
                      wake_key: str | None = None, wake_text: str | None = None) -> int:
        async with self.engine.begin() as c:
            r = await c.execute(text("INSERT INTO dispatch (origin, project, wake_key, wake_text, request, context_chars, model, status) "
                                     "VALUES (:o, :p, :k, :w, :r, :n, :m, 'planned')"),
                                {"o": origin, "p": project, "k": wake_key, "w": (wake_text or "")[:1000] or None,
                                 "r": request, "n": chars, "m": self.model})
            return r.lastrowid

    async def _finish(self, did: int, plan: dict[str, Any] | None, status: str, error: str | None, t0: float) -> None:
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET plan = :p, status = :s, error = :e, ms = :ms, "
                                 "project = COALESCE(:pj, project) WHERE id = :i"),
                            {"p": json.dumps(plan, ensure_ascii=False) if plan else None, "s": status, "e": (error or "")[:1000] or None,
                             "ms": round((time.monotonic() - t0) * 1000), "pj": (plan or {}).get("project") if (plan or {}).get("repo") else None,
                             "i": did})


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
