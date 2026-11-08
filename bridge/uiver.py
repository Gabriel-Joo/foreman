"""화면 코드 지문(11-09) — 열린 페이지가 옛 화면 코드로 도는 것을 알아채게.

브리지를 다시 띄워도 열린 브라우저 탭은 처음 받은 js · css를 그대로 쓴다. 11-09에 질문 카드 선택지 버튼을 만들고
브리지를 다시 띄웠는데, 사용자 탭은 옛 코드라 버튼이 안 나왔고 아무도 몰랐다(조용한 고장).
static 아래 js · css · html의 이름 · 크기 · 수정 시각으로 짧은 지문을 만들어 WS hello · /api/dashboard에 싣는다.
페이지는 처음 받은 지문과 달라지면 [새로 고침] 띠를 띄운다(store.js).
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"
_cache: dict[str, float | str] = {"at": 0.0, "ver": ""}


def ui_version(max_age_s: float = 5.0) -> str:
    now = time.monotonic()
    if _cache["ver"] and now - float(_cache["at"]) < max_age_s:
        return str(_cache["ver"])
    h = hashlib.sha1()
    for p in sorted(STATIC.rglob("*")):
        if p.suffix in (".js", ".css", ".html") and p.is_file():
            st = p.stat()
            h.update(f"{p.relative_to(STATIC)}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    _cache.update(at=now, ver=h.hexdigest()[:12])
    return str(_cache["ver"])
