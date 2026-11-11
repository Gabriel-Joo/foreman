"""프로젝트별 관리자 — 주소 · 서로 부탁하기(11-11 C 2물결 「둘」, README 「프로젝트별 관리자」 줄).

관리자 = 그 프로젝트 원본 폴더(.worktrees/ 밖)에서 살아 있는 역할 `manager` 세션(11-11 A 「아홉」 — 원본 폴더에 하나).
지금은 FOREMAN에만 있다. 런슈즈 · 펫퍼민트 · 인프라는 세션이 일을 마쳐도 받을 사람이 없다.

- 주소: `GET /api/managers` — 프로젝트마다 관리자 세션(없으면 없다고). 사람 · 세션 · 교장이 같은 표를 본다
- 부탁: `POST /api/managers/{project}/ask {text, from_project?, from_session?}` — 그 프로젝트 관리자 입력 칸에 넣는다
  (11-10 런슈즈 세션이 FOREMAN 코더에게 안내 문구를 고쳐 달라고 보낸 일 같은 것). 보낸 쪽 · 받는 쪽은 session_action
  `mgr-ask`에 남는다. **관리자가 없거나 못 넣으면 텔레그램 한 번 + 응답에 사유** — 조용히 사라지지 않게
- 프로젝트 토큰으로 부르면 보낸 쪽은 그 토큰의 프로젝트로 고정한다(남의 이름으로 부탁하지 못하게)
- 켜기: `config/managers.toml [managers] enabled`(처음엔 false — 꺼져 있으면 목록만 읽히고 부탁은 503)

다른 저장소에 관리자를 실제로 띄우는 것은 이 모듈이 하지 않는다 — 그 저장소 CLAUDE.md 규칙 줄과 함께 사용자가 시킬 때.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from bridge.inject import Refused, deliver

log = logging.getLogger("foreman.managers")
REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "managers.toml"
NOTIFY_KIND = "manager"   # notification.kind 칼럼 8자


@dataclass
class ManagersConfig:
    enabled: bool = False
    projects: list[str] = field(default_factory=list)   # 비면 DB의 모든 프로젝트
    error: str | None = None

    @classmethod
    def load(cls, path: Path = CONFIG) -> "ManagersConfig":
        if not path.exists():
            return cls()
        try:
            r = tomllib.loads(path.read_text()).get("managers") or {}
        except (OSError, tomllib.TOMLDecodeError) as e:
            return cls(error=f"{path.name}을 읽지 못했습니다: {e}")
        return cls(enabled=bool(r.get("enabled", False)), projects=[str(p) for p in r.get("projects") or []])


def ask_text(from_project: str | None, from_label: str | None, to_project: str, body: str) -> str:
    """관리자 입력 칸에 넣을 글 — 누가 보냈는지 · 어떻게 답하는지를 앞에."""
    who = f"{from_project or '사람'} 관리자" + (f"({from_label})" if from_label else "")
    back = (f"\n(답이나 결과는 `POST /api/managers/{from_project}/ask`로 {from_project} 관리자에게 보냅니다)"
            if from_project and from_project != to_project else "")
    return f"[관리자 부탁 — {who} → {to_project} 관리자]\n{body.strip()}{back}"


class Managers:
    def __init__(self, handoff: Any, cfg: ManagersConfig, notifier: Any = None) -> None:
        self.h = handoff                     # HandoffManager — _live_in_base · engine · sessions_dir
        self.cfg = cfg
        self.notifier = notifier

    @property
    def engine(self) -> Any:
        return self.h.engine

    async def projects(self) -> list[tuple[str, str]]:
        async with self.engine.connect() as c:
            rows = (await c.execute(text("SELECT name, repo_path FROM project WHERE repo_path IS NOT NULL ORDER BY id"))).all()
        return [(n, r) for n, r in rows if r and (not self.cfg.projects or n in self.cfg.projects)]

    async def manager_of(self, repo: str) -> dict[str, Any] | None:
        """원본 폴더에 살아 있는 역할 관리자. 여럿이면 마지막 행(아홉 뒤로는 하나뿐)."""
        ccs = self.h._live_in_base(repo)
        if not ccs:
            return None
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cc_session_id, id, role, cwd, COALESCE(custom_title, title) FROM character_session "
                "WHERE cc_session_id IN :c ORDER BY id").bindparams(bindparam("c", expanding=True)), {"c": ccs})).all()
        latest = {cc: (sid, role, cwd, title) for cc, sid, role, cwd, title in rows}
        mgr = [(cc, *v) for cc, v in latest.items() if v[1] == "manager"]
        if not mgr:
            return None
        cc, sid, _role, cwd, title = mgr[-1]
        return {"session_id": sid, "cc_session_id": cc, "cwd": cwd, "title": title}

    async def board(self) -> list[dict[str, Any]]:
        out = []
        for name, repo in await self.projects():
            try:
                m = await self.manager_of(repo)
                out.append({"project": name, "repo": repo, "manager": m,
                            "note": None if m else "관리자가 없습니다 — 부탁을 보내면 텔레그램으로 남깁니다"})
            except Exception as e:  # noqa: BLE001 — 한 프로젝트를 못 읽어도 표는 낸다
                out.append({"project": name, "repo": repo, "manager": None, "note": f"읽지 못했습니다: {type(e).__name__}"})
        return out

    async def ask(self, to_project: str, body: str, from_project: str | None = None,
                  from_session: int | None = None) -> dict[str, Any]:
        repo = dict(await self.projects()).get(to_project)
        if not repo:
            return {"delivered": False, "reason": f"프로젝트 {to_project}이(가) 없거나 관리자 대상이 아닙니다"}
        from_label = None
        if from_session:
            async with self.engine.connect() as c:
                r = (await c.execute(text("SELECT COALESCE(custom_title, title) FROM character_session WHERE id = :s"),
                                     {"s": from_session})).first()
            from_label = f"세션 {from_session}" + (f" 「{r[0]}」" if r and r[0] else "")
        msg = ask_text(from_project, from_label, to_project, body)
        m = await self.manager_of(repo)
        reason = None
        r: dict[str, Any] = {}
        if not m:
            reason = f"{to_project}에 관리자 세션이 없습니다"
        else:
            from bridge.handoff import transcript_path
            try:
                r = await deliver(m["cc_session_id"], msg, sessions_dir=self.h.sessions_dir,
                                  transcript=transcript_path(m["cwd"] or "", m["cc_session_id"]), verify_s=15.0)
                if not (r.get("delivered") or r.get("queued")):
                    reason = "입력 칸에 넣었는지 확인하지 못했습니다"
            except Refused as e:
                reason = f"넣지 못했습니다: {e}"
            except Exception as e:  # noqa: BLE001
                reason = f"넣지 못했습니다: {type(e).__name__}"
        ok = reason is None
        await self._record(m["session_id"] if m else None, ok,
                           f"{from_project or '사람'}→{to_project}" + ("" if ok else f" 실패: {reason}") + f" · {body[:300]}")
        if not ok:
            self._notify(to_project, f"⚠ {to_project} 관리자에게 부탁을 넣지 못했습니다({reason}) — {msg[:1500]}")
            log.warning("관리자 부탁 실패 %s → %s: %s", from_project, to_project, reason)
        return {"delivered": ok, "reason": reason, "to_session": m["session_id"] if m else None,
                "queued": bool(r.get("queued")), "notified": not ok and self.notifier is not None}

    async def _record(self, sid: int | None, ok: bool, detail: str) -> None:
        try:
            async with self.engine.begin() as c:
                await c.execute(text("INSERT INTO session_action (session_id, action, pid, ok, detail) "
                                     "VALUES (:s, 'mgr-ask', NULL, :o, :d)"), {"s": sid, "o": ok, "d": detail[:512]})
        except Exception as e:  # noqa: BLE001 — 기록 실패가 부탁을 막지 않는다
            log.warning("관리자 부탁 기록 실패: %s", type(e).__name__)

    def _notify(self, project: str, msg: str) -> None:
        if self.notifier is None:
            return
        try:
            rule = self.notifier.rules.for_project(project) if getattr(self.notifier, "rules", None) else None
            prefix = (rule and rule.prefix) or f"[{project}]"
            self.notifier.send_direct(project, NOTIFY_KIND, None, f"{prefix} {msg}"[:3500])
        except Exception as e:  # noqa: BLE001
            log.warning("관리자 부탁 알림 실패: %s", type(e).__name__)
