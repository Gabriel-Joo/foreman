"""원고 머리 주석(11-15): 노션 기술문서 원고와 포트폴리오 편 맨 위의 노션에 나가지 않는 HTML 주석.

    <!--
    다루는 곳: bridge/docsync.py, bridge/notion.py, config/notion.toml
    읽은 커밋: 1a2b3c4
    -->

- 다루는 곳: 그 편이 설명하는 코드 경로(파일, 끝이 /인 폴더, *가 든 글롭). 쉼표로 나누고, 같은 이름 줄을 여러 줄 써도 모인다.
  값 둘레 백틱은 뗀다
- 읽은 커밋: 서기가 그 글을 쓸 때 읽은 커밋
- 두 칸 가운데 하나라도 든 첫 주석(코드 울타리 밖)이 머리 주석이다. 맨 앞이 아니어도 된다
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from bridge.doctext.lines import comments, split

COVERS = "다루는 곳"
READ = "읽은 커밋"
FIELD = re.compile(rf"^\s*(?P<k>{COVERS}|{READ})\s*:\s*(?P<v>.*?)\s*$")
SHA = re.compile(r"[0-9a-f]{6,40}")


def head_text(covers: list[str], read: str) -> str:
    """머리 주석 한 덩어리. 서기 일감 지시문의 견본과 시험이 쓴다."""
    return f"<!--\n{COVERS}: {', '.join(covers)}\n{READ}: {read}\n-->"


def parse_head(md: str, at: str = "first") -> dict[str, Any] | None:
    """머리 주석 → {covers: [...], read: 해시 또는 None, line: 시작 줄(1부터)}. 없으면 None.
    at "first"(FOREMAN): 두 칸 가운데 하나라도 든 울타리 밖 첫 주석. "top"(인프라 docs-check.py): 빈 줄 뒤 파일 맨 앞 주석만."""
    lines = split(md)
    found_any = comments(lines)
    if at == "top":
        first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
        found_any = [c for c in found_any if c[0] == first][:1]
    for a, _, body in found_any:
        covers: list[str] = []
        read = None
        found = False
        for ln in body.split("\n"):
            m = FIELD.match(ln)
            if not m:
                continue
            found = True
            if m["k"] == COVERS:
                covers += [c.strip().strip("`") for c in m["v"].split(",") if c.strip().strip("`")]
            else:
                read = m["v"].strip().strip("`") or None
        if found:
            return {"covers": covers, "read": read, "line": a + 1}
    return None


def strip_comments(md: str) -> str:
    """HTML 주석 줄을 뗀 글(노션 판). 주석만 있는 줄은 통째로 빠지고, 코드 울타리 안은 그대로."""
    lines = split(md)
    cut = {k for a, b, _ in comments(lines) for k in range(a, b + 1)}
    if not cut:
        return md
    return "\n".join(ln for k, ln in enumerate(lines) if k not in cut)


def bad_covers(covers: list[str]) -> list[str]:
    """저장소 밖을 가리키거나 모양이 틀린 다루는 곳."""
    return [c for c in covers if PurePosixPath(c).is_absolute() or ".." in PurePosixPath(c).parts or c.startswith(":")]
