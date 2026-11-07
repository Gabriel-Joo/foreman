"""사용량(11-08, docs/15_usage.md) — 1. 트랜스크립트에 남지 않는 `claude -p` 사용량 기록.

디스패처 · 압축 손실 점검은 `--no-session-persistence`라 트랜스크립트가 없다 → `message` 표에 안 들어온다.
`--output-format json`의 `modelUsage`(모델마다 토큰 + CC가 정가로 계산한 costUSD)를 `usage_extra`에 모델마다 한 행으로 남긴다.
기록 실패는 호출한 쪽(계획 · 점검)을 막지 않는다 — 로그만.
"""

import logging
from typing import Any

from sqlalchemy import text

log = logging.getLogger("foreman.usage")


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
