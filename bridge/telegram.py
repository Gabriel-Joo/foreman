"""브리지 밖에서 보내는 텔레그램 — 백업 실패처럼 턴과 무관한 기계적 알림용(모델이 부르는 것이 아니다).

    .venv/bin/python -m bridge.telegram "제목" "줄" …   → "[포먼] 제목\\n줄\\n…"

규칙 · 토큰은 브리지와 같다(config/notify.toml, .env.telegram). 브리지 서버가 꺼져 있어도 보낸다.
DB에 kind=direct로 남기되, DB가 죽어 있으면 기록 없이 보내기만 한다(백업 실패는 DB가 죽어서일 수 있다).
"""

import asyncio
import sys

from sqlalchemy import text

from bridge.config import get_settings
from bridge.db.engine import make_engine
from bridge.mask import Masker
from bridge.notify import SendError, default_telegram, load_rules

PROJECT = "foreman"


async def main(argv: list[str]) -> int:
    if not argv:
        print("사용법: python -m bridge.telegram 제목 [줄 …]", file=sys.stderr)
        return 2
    s = get_settings()
    rules = load_rules(s.notify_config)
    rule = rules.for_project(PROJECT)
    prefix = rule.prefix if rule else "[포먼]"
    msg = Masker().text("\n".join([f"{prefix} {argv[0]}", *argv[1:]])) or ""
    try:
        await default_telegram(rules).send(msg)
        ok, err = True, None
    except SendError as e:
        ok, err = False, str(e)
    try:
        engine = make_engine(s)
        async with asyncio.timeout(5):
            async with engine.begin() as c:
                await c.execute(text(
                    "INSERT INTO notification (kind, decision, text, error, sent_at) "
                    "VALUES ('direct', :d, :t, :e, IF(:d = 'sent', UTC_TIMESTAMP(3), NULL))"),
                    {"d": "sent" if ok else "failed", "t": msg, "e": err})
        await engine.dispose()
    except Exception:  # noqa: BLE001 — 기록은 덤
        pass
    print("알림 보냄" if ok else f"알림 실패({err})", file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
