"""사용량(11-08, docs/15_usage.md) — claude -p JSON에서 모델별 사용량 뽑기 · 기록."""

import asyncio
import uuid

from sqlalchemy import text

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.usage import cli_rows, record_cli

# 11-08 실제 claude -p(Haiku, "1") 출력 모양 — 필요한 칸만
REAL = {"result": "1", "total_cost_usd": 0.00198392,
        "usage": {"input_tokens": 2, "cache_creation_input_tokens": 9342, "cache_read_input_tokens": 11382, "output_tokens": 3},
        "modelUsage": {"claude-haiku-5-5": {"inputTokens": 2, "outputTokens": 3, "cacheReadInputTokens": 11382,
                                            "cacheCreationInputTokens": 9342, "costUSD": 0.00198392, "canonicalModel": "claude-haiku-5-5"}}}


def test_cli_rows_model_usage_and_fallback():
    assert cli_rows(REAL) == [{"model": "claude-haiku-5-5", "token_input": 2, "token_output": 3, "token_cache_read": 11382,
                               "token_cache_creation": 9342, "cost_usd": 0.00198392}]
    two = {"modelUsage": {"claude-opus-5-5": {"inputTokens": 1, "outputTokens": 2}, "claude-haiku-5-5": {"outputTokens": 5}}}
    assert [r["model"] for r in cli_rows(two)] == ["claude-opus-5-5", "claude-haiku-5-5"]     # 한 호출 안에 모델이 둘이면 둘
    old = {"usage": REAL["usage"], "total_cost_usd": 0.002}
    assert cli_rows(old)[0]["model"] == "unknown" and cli_rows(old)[0]["token_cache_read"] == 11382
    assert cli_rows(None) == [] and cli_rows({"result": "글만"}) == []


def test_record_cli_writes_rows():
    async def go():
        eng = make_engine(Settings())
        src = "zz" + uuid.uuid4().hex[:6]
        try:
            assert await record_cli(eng, src, 7, "foreman", REAL) == 1
            async with eng.connect() as c:
                r = (await c.execute(text("SELECT model, token_cache_read, cost_usd, project FROM usage_extra WHERE source = :s"), {"s": src})).first()
            assert r[0] == "claude-haiku-5-5" and r[1] == 11382 and float(r[2]) == 0.001984 and r[3] == "foreman"
            assert await record_cli(None, src, 7, None, REAL) == 0                 # 엔진이 없으면 조용히 0(호출한 쪽을 막지 않는다)
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_extra WHERE source = :s"), {"s": src})
            await eng.dispose()
    asyncio.run(go())
