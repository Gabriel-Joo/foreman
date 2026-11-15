"""교장 계획을 그 프로젝트 관리자에게 바로 넘기기(11-11 C 2물결 「셋」, log/coder_c_wave2_20261111.md).

지금까지는 교장 계획 카드를 사람이 복사해 관리자에게 옮겼다. 이제 카드의 [관리자에게 보내기]가:
1. 사람이 고친 계획을 확인(`ForemanDispatcher.check`)하고 dispatch.edited에 저장, handed_to · handed_at을 적는다(status는 planned 그대로)
2. 그 프로젝트 관리자(bridge/managers.py — 원본 폴더의 역할 manager) 입력 칸에 계획 요약 + 시작 명령을 넣는다
3. 관리자가 `POST /api/foreman/start {"dispatch_id": N, "use_saved": true}`로 띄운다 — 교장 [시작]과 같은 길이라
   dispatch · dispatch_session 기록이 그대로 이어 붙는다(교장 ④)
조용히 사라지지 않게:
- 관리자가 없거나 못 넣으면 넘기지 않은 것으로 되돌리고(handed_to 비움) 카드에 사유 + 텔레그램 한 번(Managers.ask)
- 넘긴 뒤 `wait_min`분 안에 시작하지 않으면 텔레그램 한 번(handed_alert_at — 브리지를 다시 띄워도 한 번)
켜기: `config/managers.toml [handover] enabled`(처음엔 false — 꺼져 있으면 카드에 단추가 안 뜨고 API는 503)
"""

from __future__ import annotations

import asyncio
import json
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge.inject import Refused

log = logging.getLogger("foreman.handover")
CONFIG = Path(__file__).resolve().parent.parent / "config" / "managers.toml"


@dataclass
class HandoverConfig:
    enabled: bool = False
    wait_min: int = 15
    every_s: int = 60
    error: str | None = None

    @classmethod
    def load(cls, path: Path = CONFIG) -> "HandoverConfig":
        if not path.exists():
            return cls()
        try:
            r = tomllib.loads(path.read_text()).get("handover") or {}
        except (OSError, tomllib.TOMLDecodeError) as e:
            return cls(error=f"{path.name}을 읽지 못했습니다: {e}")
        return cls(enabled=bool(r.get("enabled", False)), wait_min=int(r.get("wait_min", 15)), every_s=int(r.get("every_s", 60)))


def plan_text(did: int, plan: dict[str, Any], request: str | None, base_url: str) -> str:
    """관리자 입력 칸에 넣을 글 — 무엇을 띄울지 한눈에 + 그대로 칠 시작 명령."""
    ss = plan.get("sessions") or []
    on = [s for s in ss if s.get("on", True)]
    lines = [f"[교장 계획 #{did} — 사람이 승인해 {plan.get('project')} 관리자에게 넘깁니다]"]
    if request:
        lines.append(f"요청: {request.strip()[:600]}")
    lines.append(f"방식: {plan.get('mode')} · 세션 {len(on)}개")
    for i, s in enumerate(on, 1):
        files = s.get("files") or []
        lines.append(f"  {i}「{s.get('title') or s.get('role')}」 {s.get('role')} · {s.get('model') or '기본 모델'}"
                     + (" · 작업방" if s.get("worktree") else " · 원본 폴더")
                     + (f" · 맡을 파일 {', '.join(files[:8])}" + (f" 외 {len(files) - 8}" if len(files) > 8 else "") if files else ""))
    lines += [
        "",
        "고칠 것이 없으면 아래로 띄웁니다(교장 [시작]과 같은 길 — 계획 기록이 이어 붙습니다).",
        "$T = 이 프로젝트 토큰(FOREMAN은 .env.bridge FOREMAN_API_TOKEN, 다른 프로젝트는 .env.project_tokens FOREMAN_TOKEN_<프로젝트>) — 셸 변수로만:",
        f"curl -s -X POST -H \"Authorization: Bearer $T\" -H 'Content-Type: application/json' "
        f"-d '{{\"dispatch_id\": {did}, \"use_saved\": true}}' {base_url}/api/foreman/start",
        "계획이 틀렸으면 띄우지 말고 사람에게 묻습니다(첫 글 · 맡을 파일은 GET /api/foreman/dispatch/" f"{did} 로 봅니다).",
    ]
    return "\n".join(lines)


class Handover:
    def __init__(self, foreman: Any, managers: Any, cfg: HandoverConfig, notifier: Any = None,
                 base_url: str = "http://127.0.0.1:8000") -> None:
        self.f = foreman
        self.m = managers
        self.cfg = cfg
        self.notifier = notifier
        self.base_url = base_url
        self.health: dict[str, Any] = {"ok": True, "error": None}
        self._task: asyncio.Task[Any] | None = None

    @property
    def engine(self) -> Any:
        return self.f.engine

    async def send(self, did: int, plan: dict[str, Any], inbox_ids: list[int] | None = None) -> dict[str, Any]:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT status, request FROM dispatch WHERE id = :i"), {"i": did})).first()
        if not r or r[0] != "planned":
            raise Refused("시작 전 계획만 넘길 수 있습니다" + (f"(지금 {r[0]})" if r else "(없는 계획)"))
        plan = await self.f.check(dict(plan), did)
        if plan.get("mode") == "ask":
            raise Refused("되묻는 계획입니다. 답을 받아 다시 물어본 뒤 넘겨 주세요")
        if not any(s.get("on", True) and (s.get("first_prompt") or "").strip() for s in plan.get("sessions") or []):
            raise Refused("켠 세션이 없거나 첫 글이 비었습니다")
        project, repo = plan.get("project"), plan.get("repo")
        mgr = await self.m.manager_of(repo) if repo else None
        if inbox_ids:
            plan["inbox_ids"] = [int(i) for i in inbox_ids]
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET edited = :e, project = :p, handed_to = :m, handed_at = NOW(3), "
                                 "handed_alert_at = NULL WHERE id = :i AND status = 'planned'"),
                            {"e": json.dumps(plan, ensure_ascii=False), "p": project, "m": mgr and mgr["session_id"], "i": did})
        out = await self.m.ask(project, plan_text(did, plan, r[1], self.base_url), None)
        if not out.get("delivered"):
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE dispatch SET handed_to = NULL, handed_at = NULL WHERE id = :i"), {"i": did})
            return {"handed": False, "reason": out.get("reason"), "notified": out.get("notified"),
                    "note": f"{project} 관리자에게 넘기지 못했습니다({out.get('reason')}). [이대로 시작]으로 직접 띄울 수 있습니다."}
        return {"handed": True, "to_session": out.get("to_session"), "queued": out.get("queued"),
                "note": f"{project} 관리자(세션 {out.get('to_session')})에게 넘겼습니다. {self.cfg.wait_min}분 안에 시작하지 않으면 알립니다."}

    async def check_stale(self) -> list[int]:
        """넘긴 지 wait_min분이 지나도 시작하지 않은 계획 — 한 번씩 알린다."""
        async with self.engine.begin() as c:
            rows = (await c.execute(text(
                "SELECT id, project, handed_to, TIMESTAMPDIFF(MINUTE, handed_at, NOW(3)) FROM dispatch "
                "WHERE status = 'planned' AND handed_at IS NOT NULL AND handed_alert_at IS NULL "
                "AND handed_at < NOW(3) - INTERVAL :w MINUTE"), {"w": self.cfg.wait_min})).all()
            for did, *_ in rows:
                await c.execute(text("UPDATE dispatch SET handed_alert_at = NOW(3) WHERE id = :i"), {"i": did})
        for did, project, sid, mins in rows:
            self._notify(project, f"⚠ 교장 계획 #{did}을 {project} 관리자(세션 {sid})에게 넘긴 지 {mins}분이 지났는데 아직 시작하지 않았습니다 — "
                                  "관리자 세션을 보거나, 계획 카드에서 [이대로 시작]으로 직접 띄워 주세요")
        return [r[0] for r in rows]

    def _notify(self, project: str | None, msg: str) -> None:
        log.warning("%s", msg)
        if self.notifier is None:
            return
        try:
            rule = self.notifier.rules.for_project(project or "foreman") if getattr(self.notifier, "rules", None) else None
            prefix = (rule and rule.prefix) or f"[{project or 'FOREMAN'}]"
            self.notifier.send_direct(project or "foreman", "manager", None, f"{prefix} {msg}"[:3500])
        except Exception as e:  # noqa: BLE001
            log.warning("넘김 알림 실패: %s", type(e).__name__)

    async def run(self) -> None:
        bad_hour = None
        while True:
            await asyncio.sleep(self.cfg.every_s)
            try:
                await asyncio.wait_for(self.check_stale(), 60)
                self.health = {"ok": True, "error": None}
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 한 번 실패가 감시를 멈추지 않는다. 시간마다 한 번 알림
                why = f"관리자에게 넘긴 계획 감시 실패: {type(e).__name__}: {str(e)[:200]}"
                self.health = {"ok": False, "error": why}
                import time
                h = int(time.time() // 3600)
                if h != bad_hour:
                    bad_hour = h
                    self._notify("foreman", f"⚠ {why}")

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="foreman-handover")
        return self._task
