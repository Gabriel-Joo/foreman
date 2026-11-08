"""사용량(11-08, docs/15_usage.md).

1. 트랜스크립트에 남지 않는 `claude -p` 사용량 기록 — 디스패처 · 압축 손실 점검은 `--no-session-persistence`라
   트랜스크립트가 없다 → `message` 표에 안 들어온다. `--output-format json`의 `modelUsage`(모델마다 토큰 + CC가 정가로
   계산한 costUSD)를 `usage_extra`에 모델마다 한 행으로 남긴다. 기록 실패는 호출한 쪽(계획 · 점검)을 막지 않는다 — 로그만.
2. 집계 · 환산 · 창 — `message` + `usage_extra`를 API 정가 비율(config/usage.toml)로 달러 한 줄로 더한다.
   한도 %는 `claude -p "/usage"`로 읽는다(모델 호출 없음 · 비용 0 · 어떤 세션도 막지 않음). 값이 바뀔 때만
   `usage_observation`(source cli)에 남기고, 그때 창에서 본 환산액(seen_usd)도 같이 → 하한 = seen_usd ÷ % × 100.
   못 읽으면 조용히 넘어가지 않는다: 연달아 fail_alert번이면 텔레그램, 돌아오면 한 번, 화면에는 마지막 읽은 시각.

시각: DB는 UTC(naive). 화면 · 리셋 글은 config의 tz(Asia/Seoul).
"""

import asyncio
import json
import logging
import os
import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

log = logging.getLogger("foreman.usage")

TOKEN_KINDS = ("input", "output", "cache_read", "cache_write")


def cli_rows(out: dict[str, Any] | None) -> list[dict[str, Any]]:
    """`claude -p --output-format json` 결과 → 모델별 행. modelUsage가 없으면(옛 CC) usage 한 줄을 모델 모름으로."""
    if not isinstance(out, dict):
        return []
    mu = out.get("modelUsage")
    rows = []
    if isinstance(mu, dict) and mu:
        for model, u in mu.items():
            if not isinstance(u, dict):
                continue
            rows.append({"model": str(u.get("canonicalModel") or model)[:64],
                         "token_input": int(u.get("inputTokens") or 0), "token_output": int(u.get("outputTokens") or 0),
                         "token_cache_read": int(u.get("cacheReadInputTokens") or 0),
                         "token_cache_creation": int(u.get("cacheCreationInputTokens") or 0),
                         "cost_usd": u.get("costUSD")})
        return rows
    u = out.get("usage")
    if isinstance(u, dict):
        rows.append({"model": "unknown", "token_input": int(u.get("input_tokens") or 0), "token_output": int(u.get("output_tokens") or 0),
                     "token_cache_read": int(u.get("cache_read_input_tokens") or 0),
                     "token_cache_creation": int(u.get("cache_creation_input_tokens") or 0),
                     "cost_usd": out.get("total_cost_usd")})
    return rows


async def record_cli(engine: Any, source: str, ref_id: int | None, project: str | None, out: dict[str, Any] | None) -> int:
    """기록한 행 수. 실패하면 0(로그만)."""
    rows = cli_rows(out)
    if not rows or engine is None:
        return 0
    try:
        async with engine.begin() as c:
            for r in rows:
                await c.execute(text(
                    "INSERT INTO usage_extra (source, ref_id, project, model, token_input, token_output, token_cache_read, "
                    "token_cache_creation, cost_usd) VALUES (:s, :ref, :p, :model, :token_input, :token_output, :token_cache_read, "
                    ":token_cache_creation, :cost_usd)"), {"s": source, "ref": ref_id, "p": project, **r})
        return len(rows)
    except Exception as e:  # noqa: BLE001
        log.warning("claude -p 사용량을 남기지 못함(%s #%s): %s", source, ref_id, type(e).__name__)
        return 0


# ── 2. 설정 ───────────────────────────────────────────

@dataclass
class Limit:
    key: str
    label: str
    match: str                      # /usage 줄 머리
    window_h: float
    models: list[str] = field(default_factory=list)   # 이 글자가 든 모델만(빈 목록이면 전부)
    reset: str | None = None        # 처음 값("일요일 22:00") — 읽은 리셋 시각이 있으면 그것이 이긴다

    def counts(self, model: str) -> bool:
        m = (model or "").lower()
        return not self.models or any(x in m for x in self.models)


@dataclass
class UsageConfig:
    poll_s: float = 600
    fail_alert: int = 3
    tz: str = "Asia/Seoul"
    prices: dict[str, dict[str, float]] = field(default_factory=dict)
    limits: list[Limit] = field(default_factory=list)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    def price(self, model: str) -> dict[str, float] | None:
        m = (model or "").lower()
        for name, p in self.prices.items():
            if name in m:
                return p
        return None

    def usd(self, model: str, t: dict[str, int]) -> float:
        """100만 토큰당 정가로 환산. 표에 없는 모델(<synthetic> 등)은 0."""
        p = self.price(model)
        if p is None:
            return 0.0
        return sum(t.get(k, 0) * p.get(k, 0.0) for k in TOKEN_KINDS) / 1e6


def load_config(path: str | Path) -> UsageConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    prices = {str(k).lower(): {kk: float(vv) for kk, vv in v.items()} for k, v in (raw.get("prices") or {}).items()}
    limits = [Limit(key=x["key"], label=x.get("label", x["key"]), match=x["match"], window_h=float(x["window_h"]),
                    models=[str(m).lower() for m in x.get("models") or []], reset=x.get("reset"))
              for x in raw.get("limits") or []]
    return UsageConfig(poll_s=float(raw.get("poll_s", 600)), fail_alert=int(raw.get("fail_alert", 3)),
                       tz=str(raw.get("tz", "Asia/Seoul")), prices=prices, limits=limits)


# ── 2. /usage 글 풀이 ─────────────────────────────────

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*used", re.I)
_RESET = re.compile(r"resets?\s+(?:(?P<mon>[A-Za-z]{3})[a-z]*\.?\s+(?P<day>\d{1,2}),?\s*(?:at\s+)?)?"
                    r"(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>am|pm)(?:\s*\((?P<tz>[^)]+)\))?", re.I)
_KO_DAYS = "월화수목금토일"


def _utc(dt: datetime) -> datetime:
    """aware → UTC naive(DB 모양)."""
    return dt.astimezone(UTC).replace(tzinfo=None)


def parse_reset(s: str, now: datetime, tz: str) -> datetime | None:
    """"resets Nov 8, 12:10pm (Asia/Seoul)" · "Resets 12:10pm" → UTC naive. 날짜가 없으면 다가오는 그 시각.
    now는 UTC naive."""
    m = _RESET.search(s or "")
    if not m:
        return None
    try:
        z = ZoneInfo(m["tz"].strip()) if m["tz"] else ZoneInfo(tz)
    except Exception:  # noqa: BLE001 — 모르는 시간대 이름이면 설정 값
        z = ZoneInfo(tz)
    now_l = now.replace(tzinfo=UTC).astimezone(z)
    h = int(m["h"]) % 12 + (12 if m["ap"].lower() == "pm" else 0)
    mi = int(m["mi"] or 0)
    if h > 23 or mi > 59:
        return None
    try:
        if m["mon"]:
            mon = m["mon"][:3].lower()
            if mon not in _MONTHS:
                return None
            cands = [datetime(y, _MONTHS.index(mon) + 1, int(m["day"]), h, mi, tzinfo=z) for y in (now_l.year - 1, now_l.year, now_l.year + 1)]
            dt = min(cands, key=lambda d: abs((d - now_l).total_seconds()))   # 연말 · 연초를 넘는 글
        else:
            dt = now_l.replace(hour=h, minute=mi, second=0, microsecond=0)
            if dt < now_l - timedelta(minutes=5):
                dt += timedelta(days=1)
    except ValueError:
        return None
    return _utc(dt)


def next_weekly(spec: str | None, now: datetime, tz: str) -> datetime | None:
    """"일요일 22:00" → now(UTC naive) 뒤 첫 그 시각(UTC naive). 설정의 처음 값 — 읽은 값이 없을 때만 쓴다."""
    m = re.match(r"\s*([월화수목금토일])요일\s+(\d{1,2}):(\d{2})", spec or "")
    if not m:
        return None
    z = ZoneInfo(tz)
    now_l = now.replace(tzinfo=UTC).astimezone(z)
    dt = now_l.replace(hour=int(m[2]), minute=int(m[3]), second=0, microsecond=0)
    dt += timedelta(days=(_KO_DAYS.index(m[1]) - now_l.weekday()) % 7)
    if dt <= now_l:
        dt += timedelta(days=7)
    return _utc(dt)


def parse_usage(body: str, limits: list[Limit], now: datetime, tz: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """/usage 글 → ({한도 key: {pct, reset_at, line}}, 못 찾은 한도 label 목록).
    `claude -p` 모양(한 줄: "Current session: 46% used · resets …")과 tmux 화면 모양(머리 · 막대 · Resets가 여러 줄) 둘 다.
    머리 줄부터 다음 머리 전까지(최대 4줄)에서 "N% used"와 "resets …"를 찾는다 — 아래 "What's contributing"의 %는 used가 없다."""
    lines = [ln.strip() for ln in (body or "").splitlines()]
    heads: list[tuple[int, Limit]] = []
    for i, ln in enumerate(lines):
        for lim in limits:
            if ln.lower().startswith(lim.match.lower()):
                heads.append((i, lim))
                break
    found: dict[str, dict[str, Any]] = {}
    for n, (i, lim) in enumerate(heads):
        end = min(heads[n + 1][0] if n + 1 < len(heads) else len(lines), i + 4)
        got: list[str] = []
        for x in lines[i:end]:
            if not x and any(_PCT.search(g) for g in got):
                break                                   # % 뒤 빈 줄 — 그 아래는 다른 글("What's contributing" 등)
            if x:
                got.append(x)
        block = " ".join(got)
        pm = _PCT.search(block)
        if not pm or lim.key in found:
            continue
        found[lim.key] = {"pct": float(pm[1]), "reset_at": parse_reset(block, now, tz),
                          "line": re.sub(r"\s+", " ", re.sub(r"[▀-▟]+", " ", block))[:200].strip()}   # 막대 글자는 뺀다
    missing = [lim.label for lim in limits if lim.key not in found]
    return found, missing


# ── 2. 집계 · 환산 · 창 ───────────────────────────────

_SUMS = ("SUM(token_input) ti, SUM(token_output) tout, SUM(token_cache_read) tcr, SUM(token_cache_creation) tcw, COUNT(*) n")


def _tok(r: Any) -> dict[str, int]:
    return {"input": int(r.ti or 0), "output": int(r.tout or 0), "cache_read": int(r.tcr or 0), "cache_write": int(r.tcw or 0)}


async def spend_by_model(engine: Any, start: datetime, end: datetime) -> dict[str, dict[str, int]]:
    """[start, end) 안의 모델별 토큰(message + usage_extra). 시각은 UTC naive."""
    out: dict[str, dict[str, int]] = {}
    async with engine.connect() as c:
        for tbl in ("message", "usage_extra"):
            rows = (await c.execute(text(f"SELECT model, {_SUMS} FROM {tbl} WHERE created_at >= :a AND created_at < :b GROUP BY model"),
                                    {"a": start, "b": end})).all()
            for r in rows:
                t = out.setdefault(r.model, {k: 0 for k in TOKEN_KINDS} | {"n": 0})
                for k, v in _tok(r).items():
                    t[k] += v
                t["n"] += int(r.n or 0)
    return out


def window_usd(cfg: UsageConfig, lim: Limit, by_model: dict[str, dict[str, int]]) -> float:
    return sum(cfg.usd(m, t) for m, t in by_model.items() if lim.counts(m))


def chain_windows(times: list[datetime], hours: float, anchors: list[datetime] | None = None) -> list[dict[str, Any]]:
    """5시간 창 다시 짓기 — 창은 그 창의 첫 메시지부터 hours. 메시지 시각을 차례로 이어 붙인다.
    anchors(읽은 리셋 시각)가 있으면 [리셋 - hours, 리셋)을 그대로 쓴다 — FOREMAN 밖 사용이 창을 먼저 열 수 있다(10-23)."""
    h = timedelta(hours=hours)
    known = sorted({(r - h, r) for r in anchors or []})
    wins: list[dict[str, Any]] = []
    for t in sorted(times):
        if wins and t < wins[-1]["end"]:
            continue
        # 새로 열 창 [t, t+h)가 읽은 창과 겹치면 읽은 창 — 10-23처럼 첫 메시지가 거꾸로 셈한 시작보다 몇 분 앞설 수 있다
        k = next((w for w in known if t < w[1] and t + h > w[0]), None)
        wins.append({"start": min(t, k[0]), "end": k[1], "anchored": True} if k else {"start": t, "end": t + h, "anchored": False})
    return wins


async def _times(engine: Any, start: datetime, end: datetime) -> list[datetime]:
    async with engine.connect() as c:
        rows = (await c.execute(text("SELECT created_at FROM message WHERE created_at >= :a AND created_at < :b "
                                     "UNION ALL SELECT created_at FROM usage_extra WHERE created_at >= :a AND created_at < :b"),
                                {"a": start, "b": end})).all()
    return [r[0] for r in rows]


async def current_window(engine: Any, lim: Limit, reset_at: datetime | None, now: datetime) -> dict[str, Any] | None:
    """지금 창 [start, end). 읽은 리셋이 앞이면 그대로. 지났으면 — 주간은 7일씩 넘기고, 5시간은 리셋 뒤 첫 메시지부터
    다시 짓는다(쓰지 않았으면 None — 창이 아직 안 열렸다)."""
    h = timedelta(hours=lim.window_h)
    if reset_at is None:
        return None
    if reset_at > now:
        return {"start": reset_at - h, "end": reset_at, "anchored": True}
    if lim.window_h >= 24:
        k = int((now - reset_at) / h) + 1
        r = reset_at + k * h
        return {"start": r - h, "end": r, "anchored": False}
    wins = chain_windows(await _times(engine, reset_at, now), lim.window_h)
    return wins[-1] if wins and wins[-1]["end"] > now else None


# ── 2. 관찰 · 하한 · 지금 % ───────────────────────────

async def observe(engine: Any, cfg: UsageConfig, lim: Limit, pct: float, reset_at: datetime | None, at: datetime,
                  source: str, line: str) -> tuple[bool, float | None]:
    """관찰 하나 — 그 시각 창에서 FOREMAN이 본 환산액(seen_usd)과 같이. 같은 (한도, %, 리셋)은 한 번만(값이 바뀔 때만).
    (새로 남겼나, 지금 계산한 seen_usd) — 같은 %라 안 남겨도 seen_usd는 지금 값(읽기 사이 추정의 기준)."""
    seen = None
    w = await current_window(engine, lim, reset_at, at)
    if w:
        seen = round(window_usd(cfg, lim, await spend_by_model(engine, w["start"], at)), 4)
    raw = f"{pct:g}% resets {reset_at:%Y-%m-%d %H:%M}" if reset_at else f"{pct:g}%"
    async with engine.begin() as c:
        res = await c.execute(text(
            "INSERT IGNORE INTO usage_observation (limit_key, pct, observed_at, reset_at, source, raw, seen_usd) "
            "VALUES (:k, :p, :at, :r, :s, :raw, :seen)"),
            {"k": lim.key, "p": pct, "at": at, "r": reset_at, "s": source, "raw": raw, "seen": seen})
    if res.rowcount:
        log.info("사용량 관찰 %s %s%% (%s) 창 환산 $%s — %s", lim.key, pct, source, seen, line[:80])
    return bool(res.rowcount), seen


def floors(obs: list[dict[str, Any]], min_pct: float = 20.0) -> dict[str, Any] | None:
    """관찰들 → 하한(달러). 높은 %에 무게(정수 % 반올림 오차가 작다). 범위 · 근거 수 · 10% 안에 모이면 안정.
    20% 아래는 뺀다 — 11-08 5시간 7%($2.34 → $33)가 52%($45 → $87)와 크게 어긋났다(±0.5%p가 ±7%)."""
    xs = [(float(o["seen_usd"]) / float(o["pct"]) * 100, float(o["pct"])) for o in obs
          if o.get("seen_usd") is not None and float(o["pct"]) >= min_pct and float(o["seen_usd"]) > 0]
    if not xs:
        return None
    w = sum(p for _, p in xs)
    est = sum(v * p for v, p in xs) / w
    lo, hi = min(v for v, _ in xs), max(v for v, _ in xs)
    return {"usd": round(est, 2), "min": round(lo, 2), "max": round(hi, 2), "n": len(xs), "stable": (hi - lo) <= 0.1 * est}


async def limit_status(engine: Any, cfg: UsageConfig, now: datetime, latest: dict[str, dict[str, Any]] | None = None,
                       history_days: int = 14) -> list[dict[str, Any]]:
    """한도마다: 측정 %(마지막 읽기) · 리셋 · 지금 창 환산 · 하한 · 읽기 사이 추정 % · 최근 1시간 속도 · 이 속도면 언제 100%."""
    out = []
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT limit_key, pct, observed_at, reset_at, source, seen_usd FROM usage_observation "
            "WHERE observed_at >= :a ORDER BY observed_at"), {"a": now - timedelta(days=history_days)})).mappings().all()
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_key.setdefault(r["limit_key"], []).append(dict(r))
    hour = await spend_by_model(engine, now - timedelta(hours=1), now)
    for lim in cfg.limits:
        obs = by_key.get(lim.key, [])
        last = (latest or {}).get(lim.key)
        if last is None and obs:
            o = obs[-1]
            last = {"pct": float(o["pct"]), "reset_at": o["reset_at"], "observed_at": o["observed_at"], "seen_usd": o["seen_usd"]}
        reset_at = (last or {}).get("reset_at") or next_weekly(lim.reset, now, cfg.tz)
        w = await current_window(engine, lim, reset_at, now)
        u_now = window_usd(cfg, lim, await spend_by_model(engine, w["start"], now)) if w else 0.0
        fl = floors(obs)
        measured = last["pct"] if last else None
        same_window = bool(last and w and last.get("observed_at") and last["observed_at"] >= w["start"])
        est = None
        if fl and fl["usd"] > 0:
            if same_window and last.get("seen_usd") is not None:
                est = measured + (u_now - float(last["seen_usd"])) / fl["usd"] * 100
            else:
                est = u_now / fl["usd"] * 100
        elif same_window:
            est = measured
        elif last and not w:
            est = 0.0                                       # 창이 지나고 아직 안 열렸다
        rate = window_usd(cfg, lim, hour)                  # 달러/시간
        eta = None
        if est is not None and fl and rate > 0 and est < 100:
            eta = now + timedelta(hours=fl["usd"] * (100 - est) / 100 / rate)
        out.append({"key": lim.key, "label": lim.label, "window_h": lim.window_h,
                    "measured_pct": measured, "measured_at": last.get("observed_at") if last else None,
                    "reset_at": w["end"] if w else reset_at, "window_start": w["start"] if w else None,
                    "window_anchored": bool(w and w["anchored"]),
                    "window_usd": round(u_now, 2), "floor": fl,
                    "est_pct": round(est, 1) if est is not None else None, "rate_usd_h": round(rate, 2),
                    "eta_100": eta, "eta_before_reset": bool(eta and w and eta < w["end"]), "observations": len(obs)})
    return out


# ── 2. 표(모델 · 프로젝트 · 세션 · 시간대) ────────────

async def breakdown(engine: Any, cfg: UsageConfig, start: datetime, end: datetime) -> dict[str, Any]:
    """[start, end)의 사용량 — 모델 · 프로젝트 · 세션 · 시간(UTC 정시, 화면이 tz로)별 토큰과 환산액 · 비중."""
    async with engine.connect() as c:
        msg = (await c.execute(text(
            "SELECT m.model, COALESCE(t.session_id, sr.session_id) sid, DATE_FORMAT(m.created_at, '%Y-%m-%d %H:00:00') h, "
            f"{_SUMS.replace('token_', 'm.token_')} FROM message m LEFT JOIN turn t ON t.id = m.turn_id "
            "LEFT JOIN subagent_run sr ON sr.id = m.subagent_id WHERE m.created_at >= :a AND m.created_at < :b GROUP BY 1, 2, 3"),
            {"a": start, "b": end})).all()
        ext = (await c.execute(text(
            f"SELECT model, source, project, DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00') h, {_SUMS} FROM usage_extra "
            "WHERE created_at >= :a AND created_at < :b GROUP BY 1, 2, 3, 4"), {"a": start, "b": end})).all()
        sids = sorted({r.sid for r in msg if r.sid is not None})
        meta: dict[int, tuple[str | None, str | None]] = {}
        if sids:
            q = text("SELECT cs.id, COALESCE(cs.custom_title, cs.title) title, p.name FROM character_session cs "
                     "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                     "WHERE cs.id IN (" + ",".join(str(int(s)) for s in sids) + ")")
            meta = {r.id: (r.title, r.name) for r in (await c.execute(q)).all()}

    tables: dict[str, dict[Any, dict[str, Any]]] = {"model": {}, "project": {}, "session": {}, "hour": {}}

    def add(kind: str, key: Any, model: str, t: dict[str, int], n: int, **extra: Any) -> None:
        row = tables[kind].setdefault(key, {"key": key, **extra, **{k: 0 for k in TOKEN_KINDS},
                                            **{f"usd_{k}": 0.0 for k in TOKEN_KINDS}, "usd": 0.0, "n": 0})
        p = cfg.price(model) or {}
        for k in TOKEN_KINDS:
            row[k] += t[k]
            row[f"usd_{k}"] += t[k] * p.get(k, 0.0) / 1e6     # 어디서 나가나 — 종류별(긴 맥락을 응답마다 다시 읽는 캐시 읽기 등)
        row["usd"] += cfg.usd(model, t)
        row["n"] += n

    for r in msg:
        t = _tok(r)
        title, proj = meta.get(r.sid, (None, None)) if r.sid is not None else (None, None)
        add("model", r.model, r.model, t, int(r.n))
        add("project", proj or "(모름)", r.model, t, int(r.n))
        add("session", r.sid, r.model, t, int(r.n), title=title, project=proj)
        add("hour", r.h, r.model, t, int(r.n))
    for r in ext:
        t = _tok(r)
        add("model", r.model, r.model, t, int(r.n))
        add("project", r.project or "(모름)", r.model, t, int(r.n))
        add("session", f"claude -p · {r.source}", r.model, t, int(r.n), title=f"claude -p({r.source})", project=r.project)
        add("hour", r.h, r.model, t, int(r.n))
    total = sum(x["usd"] for x in tables["model"].values()) or 0.0
    out: dict[str, Any] = {"total_usd": round(total, 2),
                           "by_kind": {k: round(sum(x[f"usd_{k}"] for x in tables["model"].values()), 4) for k in TOKEN_KINDS}}
    for kind, rows in tables.items():
        lst = list(rows.values())
        for x in lst:
            x["share"] = round(x["usd"] / total, 4) if total else 0.0
            x["usd"] = round(x["usd"], 4)
            for k in TOKEN_KINDS:
                x[f"usd_{k}"] = round(x[f"usd_{k}"], 4)
        lst.sort(key=(lambda x: str(x["key"])) if kind == "hour" else (lambda x: -x["usd"]))
        out[f"by_{kind}"] = lst
    return out


# ── 2. 주기 읽기 ─────────────────────────────────────

async def run_usage_cli(claude_bin: str, workdir: Path, timeout_s: float = 60.0) -> dict[str, Any]:
    """`claude -p "/usage"` — 모델을 부르지 않는 로컬 명령. 세션 기록을 남기지 않고 훅도 끈다."""
    workdir.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    p = await asyncio.create_subprocess_exec(
        claude_bin, "-p", "/usage", "--output-format", "json", "--no-session-persistence",
        "--settings", json.dumps({"disableAllHooks": True}), cwd=str(workdir),
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    try:
        out, err = await asyncio.wait_for(p.communicate(), timeout_s)
    except TimeoutError:
        p.kill()
        raise RuntimeError(f"{timeout_s:.0f}초 안에 답하지 않았습니다") from None
    try:
        j = json.loads(out.decode(errors="replace"))
    except ValueError:
        raise RuntimeError("JSON이 아닌 답입니다: " + (out or err).decode(errors="replace")[:200]) from None
    if not isinstance(j, dict) or j.get("is_error"):
        raise RuntimeError("오류 답입니다: " + str((j or {}).get("result", ""))[:200])
    return j


class UsageMonitor:
    """poll_s마다 /usage를 읽어 한도 %를 안다. 조용히 망가지지 않게:
    - 못 읽음(실행 실패 · 시간 초과 · 오류 답 · 줄 머리를 못 찾음)이 연달아 fail_alert번 → 텔레그램 한 번, 돌아오면 한 번
    - 화면(snapshot)에 마지막으로 읽은 시각 · 오류 · 낡음(stale)
    - CC 로그인 만료(credential_expires_at)가 24시간 안이면 텔레그램 한 번 — 만료되면 모든 세션 · 디스패처가 멈춘다"""

    def __init__(self, engine: Any, cfg: UsageConfig, notifier: Any = None, claude_bin: str = "claude",
                 workdir: Path | None = None, reader: Any = None, on_change: Any = None) -> None:
        self.engine, self.cfg, self.notifier = engine, cfg, notifier
        self.claude_bin = claude_bin
        self.workdir = workdir or Path.home() / ".foreman" / "usage"
        self.reader = reader or (lambda: run_usage_cli(self.claude_bin, self.workdir))
        self.on_change = on_change or (lambda: None)
        self.fails = 0
        self.alerted = False
        self.latest: dict[str, dict[str, Any]] = {}
        self.last_ok_at: datetime | None = None
        self.last_try_at: datetime | None = None
        self.error: str | None = None
        self.credential_expires_at: datetime | None = None
        self.contrib: str | None = None
        self._sent_rules: set[str] = set()
        self._lock = asyncio.Lock()

    async def run(self, tick_s: float = 60.0) -> None:
        """1분마다: /usage는 poll_s마다만 읽고, 알림 판정(80 · 95% · 1시간 안에 5시간 한도)은 매번 — 읽기 사이에도 추정 %가 오른다."""
        while True:
            now = datetime.now(UTC).replace(tzinfo=None)
            try:
                if self.last_try_at is None or (now - self.last_try_at).total_seconds() >= self.cfg.poll_s:
                    await self.poll()
                await self.check_alerts()
            except Exception as e:  # noqa: BLE001 — 루프는 죽지 않는다
                log.warning("사용량 루프 오류: %s: %s", type(e).__name__, str(e)[:200])
            await asyncio.sleep(tick_s)

    async def check_alerts(self, now: datetime | None = None) -> list[str]:
        """한도마다 추정(없으면 측정) %가 80 · 95%를 넘으면, 5시간 한도는 이 속도면 1시간 안에 100%(리셋 전)면 — 창마다 한 번.
        같은 창 · 같은 문턱은 rule 키(notification.rule)로 한 번만 — 브리지를 다시 띄워도. 보낸 rule 목록."""
        now = now or datetime.now(UTC).replace(tzinfo=None)
        sent: list[str] = []
        for x in await limit_status(self.engine, self.cfg, now, self.latest):
            pct = x["est_pct"] if x["est_pct"] is not None else x["measured_pct"]
            if pct is None:
                continue
            tag = f"{x['reset_at']:%m%d%H%M}" if x["reset_at"] else "na"
            # 같은 창의 다른 키 — /usage의 리셋 글이 읽을 때마다 1분씩 흔들린다(11-08 21:59 ↔ 22:00, 17:19 ↔ 17:20 —
            # 95% · ⏳ 알림이 같은 창에 두 번 나갔다). 앞뒤 5분 안의 키는 같은 창으로 본다
            near = [f"{x['reset_at'] + timedelta(minutes=m):%m%d%H%M}" for m in range(-5, 6) if m] if x["reset_at"] else []
            src = (f"측정 {x['measured_pct']:g}% · {self._local(x['measured_at'])} 읽음" if x["measured_pct"] is not None else "측정 없음")
            reset = f"리셋 {self._local(x['reset_at'])}" if x["reset_at"] else "리셋 모름"
            eta = f" 이 속도면 {self._local(x['eta_100'])}에 100%." if x["eta_100"] and x["eta_before_reset"] else ""
            stale = "" if self.error is None else " (지금 /usage를 못 읽고 있어 FOREMAN이 본 사용량으로만 추정)"
            for thr in (95, 80):
                if pct >= thr:
                    rules = [f"usage:{x['key']}:{t}:{tag}" for t in (95, 80) if t <= thr]   # 95%를 보냈으면 80%는 따로 안 보낸다
                    if await self._once(rules[0], f"{'🛑' if thr >= 95 else '⚠'} {x['label']} 사용량 약 {pct:.0f}% — {src}, {reset}.{eta}"
                                                  f"{stale} 한도에 닿으면 세션이 말없이 멈춘다. 화면 머리의 사용량 칩 → /usage", also=rules[1:],
                                        same=[f"usage:{x['key']}:{thr}:{t}" for t in near]):
                        sent.append(rules[0])
                    break
            if (x["window_h"] < 24 and x["eta_100"] and x["eta_before_reset"]
                    and (x["eta_100"] - now) <= timedelta(hours=1) and pct < 100):
                r = f"usage:{x['key']}:eta:{tag}"
                if await self._once(r, f"⏳ {x['label']}이 이 속도(최근 1시간 ${x['rate_usd_h']:.1f}/시간)면 {self._local(x['eta_100'])}에 100% — "
                                       f"리셋({self._local(x['reset_at'])})보다 먼저. 지금 약 {pct:.0f}%{stale}",
                                    same=[f"usage:{x['key']}:eta:{t}" for t in near]):
                    sent.append(r)
        return sent

    async def _once(self, rule: str, msg: str, also: list[str] | None = None, like: str | None = None,
                    same: list[str] | None = None) -> bool:
        """rule로 이미 보냈으면 False. 보내면 also도 보낸 것으로(같은 창의 낮은 문턱). like: rule 없이 남은 옛 기록을 글로 찾는다.
        same: 같은 알림으로 보는 다른 키(리셋 시각이 1분씩 흔들린 같은 창)."""
        keys = [rule, *(also or [])]
        alike = [rule, *(same or [])]
        if any(k in self._sent_rules for k in alike):
            return False
        try:
            async with self.engine.connect() as c:
                hit = (await c.execute(text("SELECT 1 FROM notification WHERE kind = 'usage' AND (rule IN :rs OR "
                                            "(:like IS NOT NULL AND rule IS NULL AND text LIKE :like)) LIMIT 1"
                                            ).bindparams(bindparam("rs", expanding=True)),
                                       {"rs": alike, "like": like})).first()
        except Exception:  # noqa: BLE001 — 확인을 못 하면 메모리만으로(한 번은 보낸다)
            hit = None
        self._sent_rules.update(keys)
        if hit:
            return False
        self._send(msg, rule=rule)
        for k in also or []:                                      # 낮은 문턱도 기록 — 다시 띄운 뒤 80%가 따로 나가지 않게
            self._mark(k)
        return True

    def _mark(self, rule: str) -> None:
        async def go() -> None:
            try:
                async with self.engine.begin() as c:
                    await c.execute(text("INSERT INTO notification (kind, decision, rule, text) VALUES ('usage', 'skipped', :r, :t)"),
                                    {"r": rule, "t": "더 높은 문턱을 보냈다"})
            except Exception:  # noqa: BLE001
                pass
        asyncio.get_running_loop().create_task(go())

    async def poll(self, now: datetime | None = None) -> bool:
        async with self._lock:
            now = now or datetime.now(UTC).replace(tzinfo=None)
            self.last_try_at = now
            try:
                j = await self.reader()
                body = str(j.get("result") or "")
                found, missing = parse_usage(body, self.cfg.limits, now, self.cfg.tz)
                if missing:
                    raise RuntimeError("/usage 글에서 " + " · ".join(missing) + " 줄을 찾지 못했습니다(글 모양이 바뀌었을 수 있습니다)")
            except Exception as e:  # noqa: BLE001
                self._failed(str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {str(e)[:200]}")
                return False
            for lim in self.cfg.limits:
                f = found[lim.key]
                seen = None
                try:
                    seen = (await observe(self.engine, self.cfg, lim, f["pct"], f["reset_at"], now, "cli", f["line"]))[1]
                except Exception as e:  # noqa: BLE001 — 기록이 안 돼도 화면 값은 갱신한다(로그)
                    log.warning("사용량 관찰을 남기지 못함(%s): %s", lim.key, type(e).__name__)
                self.latest[lim.key] = {"pct": f["pct"], "reset_at": f["reset_at"], "observed_at": now, "line": f["line"],
                                        "seen_usd": seen}
            self.contrib = body.split("What's contributing", 1)[1].strip()[:1500] if "What's contributing" in body else None
            await self._credential(j.get("credential_expires_at"), now)
            if self.alerted:
                self._send("✅ 사용량 읽기 돌아왔다 — " + " · ".join(f"{lim.label} {found[lim.key]['pct']:g}%" for lim in self.cfg.limits))
            self.fails, self.alerted, self.error, self.last_ok_at = 0, False, None, now
            self.on_change()
            return True

    def _failed(self, why: str) -> None:
        self.fails += 1
        self.error = why
        log.warning("사용량을 읽지 못함(%d번째): %s", self.fails, why)
        if self.fails >= self.cfg.fail_alert and not self.alerted:
            self.alerted = True
            last = self._local(self.last_ok_at)
            self._send(f"⚠ 사용량(/usage)을 {self.fails}번 연달아 읽지 못했다 — 한도 % · 80/95% 알림이 멈춘다\n{why[:300]}\n"
                       f"마지막으로 읽은 때: {last or '없음'}")
        self.on_change()

    async def _credential(self, v: Any, now: datetime) -> None:
        """로그인 만료 24시간 안 — 만료 시각마다 한 번(rule로, 브리지를 다시 띄워도. 11-08 처음엔 메모리로만 막아 재기동마다 또 나갔다)."""
        if not v:
            return
        try:
            exp = _utc(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
        except ValueError:
            return
        self.credential_expires_at = exp
        if exp - now < timedelta(hours=24):
            await self._once(f"usage:login:{exp:%Y%m%d%H%M}",
                             f"⚠ CC 로그인이 {self._local(exp)}에 만료된다 — 그 뒤로 모든 세션 · 디스패처 · 사용량 읽기가 멈춘다. "
                             "아무 CC 터미널에서 /login 해 주세요", like=f"%로그인이 {self._local(exp)}에 만료%")

    def _local(self, dt: datetime | None) -> str | None:
        return dt.replace(tzinfo=UTC).astimezone(self.cfg.zone).strftime("%m-%d %H:%M") if dt else None

    def stale(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC).replace(tzinfo=None)
        if self.last_ok_at is None:
            return self.last_try_at is not None
        return (now - self.last_ok_at).total_seconds() > self.cfg.poll_s * self.cfg.fail_alert + 60

    def snapshot(self) -> dict[str, Any]:
        return {"ok": self.error is None and not self.stale(), "error": self.error, "fails": self.fails,
                "last_ok_at": self.last_ok_at, "last_try_at": self.last_try_at, "stale": self.stale(),
                "poll_s": self.cfg.poll_s, "credential_expires_at": self.credential_expires_at, "contributing": self.contrib}

    def _send(self, msg: str, rule: str | None = None) -> None:
        log.warning("사용량 알림: %s", msg.splitlines()[0])
        if self.notifier is None:
            return
        pr = self.notifier.rules.for_project("foreman")
        self.notifier.send_direct("foreman", "usage", None, f"{(pr and pr.prefix) or '[FOREMAN]'} {msg}", rule=rule)
