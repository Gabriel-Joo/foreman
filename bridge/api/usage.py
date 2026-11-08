"""/api/usage — 사용량 · 한도(11-08, docs/15_usage.md).

GET  /api/usage        한도별 측정 % · 리셋 · 창 안 환산액 · 하한 · 읽기 사이 추정 % · 이 속도면 언제 100%,
                       읽기 상태(마지막으로 읽은 시각 · 오류 · 낡음 · 로그인 만료), 모델 · 프로젝트 · 세션 · 시간대별 표
POST /api/usage/poll   지금 /usage를 한 번 읽는다(모델 호출 없음)
시각은 UTC ISO(…Z) — 화면이 tz로 바꾼다. 금액은 API 정가 비율 환산(config/usage.toml)이고 한도는 '하한'이다.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from bridge.api.auth import require_api_token
from bridge.usage import UsageConfig, breakdown, limit_status, load_config

router = APIRouter(prefix="/api/usage", dependencies=[Depends(require_api_token)])
_cache: dict[str, Any] = {"at": 0.0, "key": None, "data": None}
CACHE_S = 20.0


def invalidate() -> None:
    _cache["data"] = None


def _j(v: Any) -> Any:
    """datetime → UTC ISO(…Z), 안쪽까지."""
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds") + "Z"
    if isinstance(v, dict):
        return {k: _j(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_j(x) for x in v]
    return v


def _cfg(request: Request) -> UsageConfig:
    mon = getattr(request.app.state, "usage", None)
    if mon is not None:
        return mon.cfg
    try:
        return load_config(request.app.state.settings.usage_config)
    except OSError as e:
        raise HTTPException(503, f"사용량 설정(config/usage.toml)을 읽지 못했습니다: {type(e).__name__}") from None


@router.get("")
async def usage(request: Request, hours: float | None = None) -> dict[str, Any]:
    """hours를 주면 표의 기간이 지금부터 그 시간 전까지, 없으면 지금 주간 창(리셋 - 7일)부터."""
    key = hours
    if _cache["data"] is not None and _cache["key"] == key and time.monotonic() - _cache["at"] < CACHE_S:
        return _cache["data"]
    cfg = _cfg(request)
    engine = request.app.state.store.engine
    mon = getattr(request.app.state, "usage", None)
    now = datetime.now(UTC).replace(tzinfo=None)
    limits = await limit_status(engine, cfg, now, mon.latest if mon else None)
    if hours:
        start = now - timedelta(hours=max(1.0, min(hours, 24 * 31)))
    else:
        wk = next((x for x in limits if x["window_h"] >= 24 and x["window_start"]), None)
        start = wk["window_start"] if wk else now - timedelta(days=7)
    tables = await breakdown(engine, cfg, start, now)
    reading = mon.snapshot() if mon else {"ok": False, "error": "사용량 읽기가 꺼져 있습니다(usage_enabled)", "stale": True}
    data = _j({"generated_at": now, "tz": cfg.tz, "basis": "API 정가 비율 환산(config/usage.toml) — 한도는 하한입니다",
               "reading": reading, "limits": limits, "period": {"start": start, "end": now}, **tables})
    _cache.update(at=time.monotonic(), key=key, data=data)
    return data


@router.post("/poll")
async def poll(request: Request) -> dict[str, Any]:
    mon = getattr(request.app.state, "usage", None)
    if mon is None:
        raise HTTPException(503, "사용량 읽기가 꺼져 있습니다")
    ok = await mon.poll()
    invalidate()
    return _j({"ok": ok, **mon.snapshot()})
