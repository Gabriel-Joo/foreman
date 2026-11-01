"""서버 없이 트랜스크립트를 한 번 적재한다 — 백필 시간 · 결과 측정, 다시 읽기(중복) 시험용.

    .venv/bin/python -m bridge.ingest             # 저장된 offset부터 끝까지
    .venv/bin/python -m bridge.ingest --reread    # offset을 0으로 돌리고 처음부터(행이 늘지 않아야 한다)

브리지(python -m bridge)가 같은 DB에 쓰고 있을 때는 돌리지 않는다 — 쓰는 쪽은 하나여야 한다.
"""

import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy import text

from bridge.assembler import Assembler
from bridge.config import get_settings
from bridge.db.engine import make_engine
from bridge.mask import Masker
from bridge.transcript.watcher import Watcher

COUNTS = """
SELECT 'character_session', COUNT(*) FROM character_session UNION ALL
SELECT 'transcript_file', COUNT(*) FROM transcript_file UNION ALL
SELECT 'turn', COUNT(*) FROM turn UNION ALL
SELECT 'turn_open', COUNT(*) FROM turn WHERE ended_at IS NULL UNION ALL
SELECT 'message', COUNT(*) FROM message UNION ALL
SELECT 'subagent_run', COUNT(*) FROM subagent_run UNION ALL
SELECT 'event', COUNT(*) FROM event
"""


async def counts(engine) -> dict[str, int]:  # noqa: ANN001
    async with engine.connect() as c:
        return {k: v for k, v in (await c.execute(text(COUNTS))).all()}


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bridge.ingest")
    ap.add_argument("--reread", action="store_true", help="offset을 0으로 돌리고 처음부터 다시 읽는다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    engine = make_engine(s)
    try:
        if args.reread:
            async with engine.begin() as c:
                await c.execute(text("UPDATE transcript_file SET read_offset = 0"))
        before = await counts(engine)
        asm = Assembler(engine, s, Masker())
        await asm.load()
        w = Watcher(s, asm)
        secs = await w.backfill()
        closed = await asm.sweep()
        after = await counts(engine)
        print(json.dumps({"seconds": round(secs, 1), "sweep_closed": closed, "before": before, "after": after,
                          "stats": await asm.stats_snapshot()}, ensure_ascii=False, indent=1, default=str))
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
