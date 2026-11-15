"""서기 재료 도우미(LLM 없음, docs/12_scribe.md 「3. 무엇을 읽나」).

서기 일감의 재료를 만들 때 함께 쓰는 작은 함수만 둔다. 쓰는 곳: 「나중에 할 일 정리」 재료(scribe_room.later_material), 물어보기 재료(scribe_ask).
- 사람 말 원문은 자르지 않는다(_full). 요약 줄만 자른다(_clip)
- 사람 프롬프트 원문이 든 재료는 저장소 밖(~/.foreman/scribe/, 700)에 쓴다(write). GitHub에 올리지 않는다
회고 재료 묶음(collect, render, retro_prompt)은 11-15에 회고 쓰기와 함께 뺐다(docs/12_scribe.md 「0.」).
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

KST = timedelta(hours=9)
OUT_ROOT = Path.home() / ".foreman" / "scribe"
# 사람 말은 자르지 않는다(받은 할 일 #14, log/scribe_material_noclip_20261110.md, 11-10 — 1500자에서 잘려 t:6360 · t:6383 뒤쪽이 빠졌다).
# 11-10 잰 크기: FOREMAN 사람 턴 전체 330개 · 206k자, 가장 긴 턴 9.9k자 — 서기가 Read를 쪽으로 나눠 읽으면 된다.
# Read는 2000자 넘는 한 줄을 조용히 자르므로, 긴 줄은 글자를 빼지 않고 LINE_WRAP자마다 줄만 나눈다.
LINE_WRAP = 1500


def kst(dt: datetime | None) -> str:
    return (dt + KST).strftime("%m-%d %H:%M") if dt else "?"


def _unwrap(t: str | None) -> str:
    t = (t or "").strip()
    return re.sub(r"^<pasted_content[^>]*>\s*|\s*</pasted_content[^>]*>$", "", t)


def _clip(t: str | None, n: int) -> str:
    """요약 칸(목록 한 줄 · 계획 · 승인 사유)용 — 사람 말 원문에는 쓰지 않는다(_full)."""
    t = _unwrap(t)
    return t if len(t) <= n else t[:n] + f" …(뒤 {len(t) - n}자 줄임)"


def _full(t: str | None) -> str:
    """사람 말 원문 — 자르지 않는다. pasted_content 껍데기만 벗기고, Read가 자르지 않게 긴 줄만 나눈다."""
    out = []
    for ln in _unwrap(t).split("\n"):
        out += [ln[i:i + LINE_WRAP] for i in range(0, len(ln), LINE_WRAP)] or [""]
    return "\n".join(out)


def git_commits(repo: str, start: datetime, end: datetime) -> list[dict[str, str]]:
    """기간의 커밋(모든 가지가 아니라 지금 HEAD에 닿는 것) — 해시 · KST 시각 · 제목 · 바뀐 파일."""
    fmt = "%x1e%h%x1f%cI%x1f%s"
    out = subprocess.run(["git", "-C", repo, "log", "--reverse", f"--since={start.isoformat()}Z",
                          f"--until={end.isoformat()}Z", f"--format={fmt}", "--name-only"],
                         capture_output=True, text=True, timeout=30).stdout
    rows = []
    for chunk in out.split("\x1e"):
        if not chunk.strip():
            continue
        head, *files = chunk.strip().split("\n")
        h, iso, subj = head.split("\x1f", 2)
        when = datetime.fromisoformat(iso).astimezone(UTC).replace(tzinfo=None)
        rows.append({"sha": h, "kst": kst(when), "subject": subj, "files": [f for f in files if f.strip()]})
    return rows


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_text(body, encoding="utf-8")
    os.chmod(path, 0o600)
    return path
