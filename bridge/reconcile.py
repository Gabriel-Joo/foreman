"""끝난 뒤 어긋난 것 훑기(reconcile, 11-11 — README 「나중에 할 일」 「끝난 뒤 어긋난 것 훑기」).

합치고 끝낸 뒤 실제와 다른 것이 남는다(11-10에 262 작업 폴더와 257 「합치기 기다림」을 사람이 손으로 정리했다).
세션이 끝날 때(프로세스가 사라짐 — bridge/session_state.py) · 합치기 · 버리기 뒤에 한 번(DEBOUNCE로 몰아서) 저장소를 훑어
다른 것을 알린다. 고치지는 않는다 — 지우기는 사람이 패널 [합치기] · [버리기]로(지울지 말지가 사람 판단이다).

찾는 것(kind):
- dirty        끝난 세션의 worktree에 커밋 안 된 변경이 있다 — 합치기도 쉬게 하기도 못 한 채 세션이 끝났다
- orphan       worktree 폴더가 남았는데 그 폴더를 쓴 세션이 없거나, 이미 합치기 · 버리기를 했거나, 끝났는데 쉬게 하기도 안 했다
- stale_rest   「합치기 기다림」(쉬게 하기 기록)인데 실제로는 끝남 — 밖에서 합침 · 이름이 다시 쓰임(받은 할 일 #17과 같은 판정,
               bridge/coder_room.py rest_stale. 화면은 이미 빼고 보인다 — 여기는 기록이 남았다는 것만)
- empty        끝난 세션의 worktree인데 앞선 커밋 0 · 변경 0 — 어긋남이 아니라 치울 것(화면 「치울 것 — 빈 worktree」, 알림 없음)
- branch       worktree 없이 cc/* 브랜치만 남음 — 원본에 들어 있으면 지워도 되고, 아니면 합치지 않은 일
- prunable     git이 아는 worktree인데 폴더가 없다(`git worktree prune` 거리)
겹치는 판정(밖에서 합침 · 이름 다시 씀)은 둘(coder_room)의 것을 쓴다.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge import coder_room as cr
from bridge import worktree as wt
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.reconcile")

DEBOUNCE_S = 60.0          # 세션이 끝난 뒤 이만큼 기다렸다 훑는다(합치기 · 버리기가 이어서 오는 동안)
REPO_DAYS = 30             # 이 기간 안에 worktree 세션이 있던 저장소만 훑는다


def _key(kind: str, where: str) -> str:
    return f"recon:{kind}:{hashlib.sha1(where.encode()).hexdigest()[:16]}"


async def repos(engine: Any) -> dict[str, str | None]:
    """훑을 저장소 → 프로젝트 이름. 최근 worktree 세션의 cwd에서 뽑는다."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT DISTINCT cs.cwd, p.name FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.cwd LIKE '%/.worktrees/%' AND cs.attached_at > :cut"),
            {"cut": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=REPO_DAYS)})).all()
    out: dict[str, str | None] = {}
    for cwd, proj in rows:
        repo, name = wt.split(cwd or "")
        if name and os.path.isdir(os.path.join(repo, ".git")):
            out.setdefault(repo, proj)
    return out


async def sweep(engine: Any, sessions_dir: Any, repo_map: dict[str, str | None] | None = None,
                live: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """한 번 훑는다 — [{kind, project, where, detail, session_id}]."""
    repo_map = repo_map if repo_map is not None else await repos(engine)
    live = live if live is not None else live_sessions(sessions_dir)
    found: list[dict[str, Any]] = []

    def add(kind: str, project: str | None, where: str, detail: str, sid: int | None = None) -> None:
        found.append({"kind": kind, "project": project, "where": where, "detail": detail, "session_id": sid})

    for repo, project in sorted(repo_map.items()):
        wt_root = Path(repo, wt.WT_DIR)
        dirs = sorted(p for p in wt_root.iterdir() if p.is_dir()) if wt_root.is_dir() else []
        async with engine.connect() as c:
            for d in dirs:
                r = (await c.execute(text(
                    "SELECT cs.id, cs.cc_session_id FROM character_session cs WHERE cs.cwd = :p OR cs.cwd LIKE :pp "
                    "ORDER BY cs.id DESC LIMIT 1"),
                    {"p": str(d), "pp": str(d).replace("%", r"\%").replace("_", r"\_") + "/%"})).first()
                if r and r[1] in live:
                    continue                                    # 도는 세션의 자리
                _, dirty = await wt.git(d, "status", "--porcelain", check=False)
                n_dirty = len([ln for ln in dirty.splitlines() if ln.strip()])
                if not r:
                    add("orphan", project, str(d), f"worktree {d.name} — 이 폴더를 쓴 세션이 없습니다"
                        + (f"(커밋 안 된 변경 {n_dirty}개)" if n_dirty else ""))
                    continue
                sid = int(r[0])
                acts = {a for (a,) in (await c.execute(text(
                    "SELECT action FROM session_action WHERE session_id = :s AND ok AND action IN ('wt-merge', 'wt-discard', 'rest')"),
                    {"s": sid})).all()}
                if n_dirty:
                    add("dirty", project, str(d), f"세션 {sid}이 끝났는데 worktree {d.name}에 커밋 안 된 변경이 {n_dirty}개 있습니다", sid)
                elif acts & {"wt-merge", "wt-discard"}:
                    add("orphan", project, str(d), f"세션 {sid}은 이미 합치기 · 버리기를 했는데 worktree {d.name}가 남았습니다", sid)
                elif "rest" not in acts:
                    st = await wt.in_base(repo, d.name) if (wt_root / d.name).is_dir() else None
                    if st:
                        # 11-13 — 앞선 커밋 0 · 변경 0 · 세션 끝남: 어긋남이 아니라 치우기만 하면 되는 빈 worktree
                        add("empty", project, str(d), f"빈 worktree {d.name} — 세션 {sid}이 끝났고 커밋이 모두 원본에 들어 있으며 변경이 없습니다", sid)
                        continue
                    add("orphan", project, str(d), f"세션 {sid}이 합치기 · 쉬게 하기 없이 끝났습니다 — worktree {d.name}"
                        + (" (합치지 않은 커밋이 있습니다)" if st is False else ""), sid)
            # 쉬게 하기 기록이 실제와 다름(받은 할 일 #17 판정 그대로)
            for sid, cwd in (await c.execute(text(
                    "SELECT cs.id, cs.cwd FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
                    "WHERE sa.action = 'rest' AND sa.ok AND cs.cwd LIKE :pp AND NOT EXISTS (SELECT 1 FROM session_action m "
                    "WHERE m.session_id = cs.id AND m.action IN ('wt-merge', 'wt-discard') AND m.ok) GROUP BY cs.id, cs.cwd"),
                    {"pp": str(wt_root).replace("%", r"\%").replace("_", r"\_") + "/%"})).all():
                why = await cr.rest_stale(engine, int(sid), cwd)
                if why:
                    add("stale_rest", project, f"rest:{sid}", f"세션 {sid}의 「합치기 기다림」 — {why}", int(sid))
        # worktree 없이 남은 cc/* 브랜치
        _, branches = await wt.git(repo, "branch", "--list", f"{wt.BRANCH_PREFIX}*", "--format=%(refname:short)", check=False)
        for b in branches.split():
            name = b[len(wt.BRANCH_PREFIX):]
            if (wt_root / name).is_dir():
                continue
            merged = await wt.in_base(repo, name)
            add("branch", project, f"{repo}:{b}", f"브랜치 {b}만 남았습니다(worktree 없음) — "
                + ("원본에 들어 있어 지워도 됩니다" if merged else "원본에 없는 커밋이 있습니다(합치지 않은 일)"))
        # git이 아는데 폴더가 없는 worktree
        _, wl = await wt.git(repo, "worktree", "list", "--porcelain", check=False)
        path = None
        for ln in wl.splitlines():
            if ln.startswith("worktree "):
                path = ln[9:]
            elif ln.startswith("prunable") and path:
                add("prunable", project, path, f"git이 아는 worktree {os.path.basename(path)}의 폴더가 없습니다(git worktree prune 거리)")
    return found


class Reconciler:
    """세션이 끝날 때 한 번 훑고 새로 찾은 것만 알린다. 마지막 결과는 /api/coder/todo `drift`로 화면에."""

    def __init__(self, engine: Any, notifier: Any, sessions_dir: Any, debounce_s: float = DEBOUNCE_S) -> None:
        self.engine, self.notifier, self.dir, self.debounce = engine, notifier, sessions_dir, debounce_s
        self.last: list[dict[str, Any]] = []
        self.at: datetime | None = None
        self._task: asyncio.Task[Any] | None = None
        self.on_change: Any = None

    def poke(self, why: str = "") -> None:
        """세션이 끝났다 · 합치기 · 버리기를 했다 — DEBOUNCE 뒤에 한 번 훑는다(그 사이 또 오면 한 번으로)."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._later(why), name="foreman-reconcile")

    async def _later(self, why: str) -> None:
        await asyncio.sleep(self.debounce)
        try:
            await self.run_once()
        except Exception as e:  # noqa: BLE001 — 훑기 실패가 브리지를 멈추지 않는다
            log.warning("훑기 실패(%s): %s: %s", why, type(e).__name__, str(e)[:200])

    async def run_once(self) -> list[str]:
        """훑고 새로 찾은 것을 알린다. 돌려주는 값: 이번에 보낸 rule 키들."""
        found = await sweep(self.engine, self.dir)
        self.last, self.at = found, datetime.now(UTC).replace(tzinfo=None)
        if self.on_change:
            self.on_change()
        found = [f for f in found if f["kind"] != "empty"]      # 빈 worktree는 고장이 아니다 — 화면 「치울 것」에만, 텔레그램은 보내지 않는다
        if found:
            log.info("훑기: 어긋난 것 %d — %s", len(found), ", ".join(f"{f['kind']} {f['where']}" for f in found)[:400])
        if self.notifier is None:
            return []
        new: list[tuple[str, dict[str, Any]]] = []
        async with self.engine.connect() as c:
            for f in found:
                key = _key(f["kind"], f["where"])
                if not (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                    new.append((key, f))
        by_project: dict[str | None, list[tuple[str, dict[str, Any]]]] = {}
        for k, f in new:
            by_project.setdefault(f["project"], []).append((k, f))
        sent = []
        for project, items in by_project.items():
            rule = self.notifier.rules.for_project(project) if project else None
            prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
            lines = [f"{prefix} 🧹 끝난 뒤 어긋난 것 {len(items)} — 실제와 화면이 다릅니다"]
            lines += [f"▶ {f['detail']}" for _, f in items[:8]]
            if len(items) > 8:
                lines.append(f"… 외 {len(items) - 8}개")
            lines.append("코더 패널 「맡길 일」에서 보고, 그 세션 패널의 [합치기] · [버리기]로 정리합니다")
            msg = "\n".join(lines)
            # 한 메시지에 여럿 — 키는 첫 것으로 보내고 나머지는 기록만(다시 알리지 않게)
            self.notifier.send_direct(project, "recon", None, msg, rule=items[0][0])
            for k, _ in items[1:]:
                await self._mark(k)
            sent += [k for k, _ in items]
        return sent

    async def _mark(self, key: str) -> None:
        async with self.engine.begin() as c:
            await c.execute(text("INSERT INTO notification (kind, decision, rule, text) VALUES ('recon', 'grouped', :r, NULL)"),
                            {"r": key})

    def for_project(self, project: str) -> list[dict[str, Any]]:
        return [f for f in self.last if f["project"] == project]
