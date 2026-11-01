"""event 테이블에 쓰는 곳은 여기 하나다(event에 FK가 없으므로 참조 무결성은 이 모듈이 맡는다 — 0001_init.sql)."""

import asyncio
import json
from datetime import UTC
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.config import Settings
from bridge.models import EventIn, clip_target

_INSERT_EVENT = text(
    """
    INSERT INTO event (uuid, parent_uuid, session_id, character_id, turn_id, message_id, subagent_id,
                       tool_use_id, source, ts, type, tool, target, target_truncated, status, commit_sha, payload)
    VALUES (:uuid, :parent_uuid, :session_id, :character_id, :turn_id, :message_id, :subagent_id,
            :tool_use_id, :source, :ts, :type, :tool, :target, :target_truncated, :status, :commit_sha, :payload)
    """
)


class Store:
    def __init__(self, engine: AsyncEngine, settings: Settings) -> None:
        self.engine = engine
        self.timeout = settings.db_query_timeout_s

    async def ping(self) -> None:
        async with asyncio.timeout(self.timeout):
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

    async def character_exists(self, character_id: int) -> bool:
        async with asyncio.timeout(self.timeout):
            async with self.engine.connect() as conn:
                res = await conn.execute(text("SELECT 1 FROM `character` WHERE id = :id"), {"id": character_id})
                return res.first() is not None

    async def delete_debug_events(self) -> int:
        async with asyncio.timeout(self.timeout):
            async with self.engine.begin() as conn:
                res = await conn.execute(text("DELETE FROM event WHERE source = 'debug'"))
                return res.rowcount

    async def insert_event(self, ev: EventIn) -> dict[str, Any]:
        """적재하고 WS로 내보낼 형태(id 포함)를 돌려준다. 중복 uuid면 IntegrityError(1062)가 올라간다."""
        target, full = clip_target(ev.target)
        payload = dict(ev.payload or {})
        if full is not None:
            payload["target_full"] = full
        ts = ev.ts.astimezone(UTC).replace(tzinfo=None)  # DB는 UTC naive
        params = {
            "uuid": ev.uuid,
            "parent_uuid": ev.parent_uuid,
            "session_id": ev.session_id,
            "character_id": ev.character_id,
            "turn_id": ev.turn_id,
            "message_id": ev.message_id,
            "subagent_id": ev.subagent_id,
            "tool_use_id": ev.tool_use_id,
            "source": ev.source.value,
            "ts": ts,
            "type": ev.type.value,
            "tool": ev.tool,
            "target": target,
            "target_truncated": full is not None,
            "status": ev.status.value if ev.status else None,
            "commit_sha": ev.commit_sha,
            "payload": json.dumps(payload, ensure_ascii=False) if payload else None,
        }
        async with asyncio.timeout(self.timeout):
            async with self.engine.begin() as conn:
                res = await conn.execute(_INSERT_EVENT, params)
                event_id = res.lastrowid
        out = {k: v for k, v in params.items() if k not in ("payload", "ts")}
        out.update(id=event_id, ts=ts.isoformat(timespec="milliseconds") + "Z", payload=payload or None)
        return out
