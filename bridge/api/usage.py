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
from sqlalchemy import text

from bridge.api.auth import require_api_token
from bridge.usage import (UsageConfig, breakdown, credit_signal, credit_status, credit_view, limit_status, load_config,
                          parse_contrib)

router = APIRouter(prefix="/api/usage", dependencies=[Depends(require_api_token)])
_cache: dict[str, Any] = {"at": 0.0, "key": None, "data": None}
CACHE_S = 20.0


def invalidate() -> None:
    _cache["data"] = None
    _brief["data"] = None


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
    recent = await breakdown(engine, cfg, now - timedelta(hours=1), now)     # 지금 어디서 나가나(최근 1시간)
    reading = mon.snapshot() if mon else {"ok": False, "error": "사용량 읽기가 꺼져 있습니다(usage_enabled)", "stale": True}
    async with engine.connect() as c:
        obs = [dict(r) for r in (await c.execute(text(
            "SELECT limit_key, pct, observed_at, reset_at, source, seen_usd FROM usage_observation "
            "ORDER BY observed_at DESC LIMIT 40"))).mappings().all()]
    for o in obs:
        o["pct"] = float(o["pct"])
        o["seen_usd"] = float(o["seen_usd"]) if o["seen_usd"] is not None else None
    data = _j({"generated_at": now, "tz": cfg.tz, "basis": "API 정가 비율 환산(config/usage.toml) — 한도는 하한입니다",
               "reading": reading, "limits": limits, "period": {"start": start, "end": now}, **tables,
               "recent": {"total_usd": recent["total_usd"], "by_kind": recent["by_kind"], "by_session": recent["by_session"][:8]},
               "observations": obs})
    _cache.update(at=time.monotonic(), key=key, data=data)
    return data


_brief: dict[str, Any] = {"at": 0.0, "data": None}


@router.get("/brief")
async def brief(request: Request) -> dict[str, Any]:
    """머리 칩 · 캐릭터 열기용(가볍게, 15초 캐시) — 한도별 % · 읽기 상태 · 지난 30분 환산액 상위 세션 셋(달러/시간)."""
    if _brief["data"] is not None and time.monotonic() - _brief["at"] < 15.0:
        return _brief["data"]
    cfg = _cfg(request)
    engine = request.app.state.store.engine
    mon = getattr(request.app.state, "usage", None)
    now = datetime.now(UTC).replace(tzinfo=None)
    limits = await limit_status(engine, cfg, now, mon.latest if mon else None)
    hot = await breakdown(engine, cfg, now - timedelta(minutes=30), now)
    reading = mon.snapshot() if mon else {"ok": False, "error": "사용량 읽기가 꺼져 있습니다(usage_enabled)", "stale": True}
    data = _j({"reading": {k: reading.get(k) for k in ("ok", "error", "last_ok_at", "stale", "credential_expires_at")},
               "limits": [{k: x[k] for k in ("key", "label", "window_h", "measured_pct", "est_pct", "reset_at", "eta_100",
                                             "eta_before_reset")} for x in limits],
               "hot": [{"session_id": s["key"], "usd_h": round(s["usd"] * 2, 2)} for s in hot["by_session"]
                       if isinstance(s["key"], int) and s["usd"] > 0][:3],
               # 11-09 /usage "What's contributing"(CC 추정 — 대략 · 이 기기 세션만 · 겹침 있음) — 사용량 호버에
               "contributing": parse_contrib(reading.get("contributing")),
               # 11-09 추가 사용(크레딧) — CC가 한도에 닿을 때 남긴 글이 먼저(credit_signal), 사람이 넣은 값은 3일 안일 때만 참고
               "credits": credit_view(await credit_signal(engine, cfg, now),
                                      credit_status(cfg.credits, now.replace(tzinfo=UTC).astimezone(cfg.zone).date()))})
    _brief.update(at=time.monotonic(), data=data)
    return data


@router.post("/poll")
async def poll(request: Request) -> dict[str, Any]:
    mon = getattr(request.app.state, "usage", None)
    if mon is None:
        raise HTTPException(503, "사용량 읽기가 꺼져 있습니다")
    ok = await mon.poll()
    invalidate()
    return _j({"ok": ok, **mon.snapshot()})
