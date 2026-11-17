"""12b 근거 확인기 · 고친 양(11-06, docs/12_scribe.md 「4. 수준을 어떻게 담보하나」) — LLM 없이.

- 근거 표시 확인: 서기 브랜치에서 바뀐 .md의 `[c:sha]`(커밋이 있나) · `[log:파일]` · `[docs:파일(:줄-줄)]`(파일 · 줄 범위가 있나) ·
  `[code:경로(:줄-줄)]`(저장소 맨 위 기준 파일 · 폴더가 있나, 11-15) · `[t:턴]`(DB에 있나). 틀린 것은 합치기 전에 패널에 띄운다 —
  포트폴리오로 나갈 글은 근거가 틀리면 안 된다(11-06 사용자)
- 원고 머리 주석(11-15, bridge/manuscript.py): 「읽은 커밋」이 저장소에 있나, 「다루는 곳」 경로가 있나. 서기가 틀리게 적으면
  「코드가 바뀐 편」 셈이 조용히 틀린다
- 근거 없는 줄(의심): 숫자나 인용이 있는데 근거 표시가 없는 본문 줄. 표 · 제목 · 인용 블록 · 코드는 빼고 센다 — 판단은 사람이
- 고친 양: 서기의 첫 초안(사람이 두 번째로 말하기 전의 커밋)과 그 뒤 고친 커밋의 줄 수. 줄어드는지가 서기 글 수준의 지표다(12d 하루 끝 자동 초안은 11-15에 회고와 함께 뺐다)
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge.doctext.check import SKIP_LINE, FsView, covers_problem, is_claim, mark_problem  # noqa: E402,F401
from bridge.doctext.config import FOREMAN_CLAIM, CheckConfig  # noqa: E402
from bridge.doctext.lines import text_lines  # noqa: E402
from bridge.doctext.marks import MARK, target  # noqa: E402,F401  (MARK는 tests/screen_words.py도 이 이름으로 읽었다)

# 근거 표시 파일과 줄, 다루는 곳 경로, 의심 줄 꼴은 문서 점검(bridge/doctext/check.py, tools/docs.py check)과 한 곳이다(11-17 3단계)
CLAIM = re.compile(FOREMAN_CLAIM)                # 숫자, 인용이 있는 줄. 근거가 있어야 할 줄
CLAIM_MIN = CheckConfig().claim_min


async def _git(repo: str, *args: str) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL)
    out, _ = await asyncio.wait_for(p.communicate(), 15)
    return p.returncode or 0, out.decode(errors="replace").strip()


def _file_problem(root: Path, kind: str, v: str) -> str | None:
    return mark_problem(kind, v, FsView(root))


async def check_text(body: str, root: str, engine: Any = None) -> dict[str, Any]:
    """한 글의 근거 표시를 확인한다 — {total, ok, bad:[{line, mark, why}], unsupported:[{line, text}]}."""
    from bridge.doctext.head import COVERS, READ, parse_head
    marks: list[tuple[int, str, str]] = []
    unsupported = []
    # 코드 울타리와 HTML 주석(원고 머리 주석) 밖 줄만. 머리 주석은 아래에서 따로 본다
    for i, ln in text_lines(body.splitlines()):
        marks += [(i, m["k"], m["v"]) for m in MARK.finditer(ln)]
        # "→ 「다른 글 제목」"은 글 안내라 주장이 아니다(11-06 포트폴리오 02, 05의 의심이 둘 다 이것). 판정은 is_claim 한 곳
        if is_claim(ln, CLAIM, CLAIM_MIN):
            unsupported.append({"line": i, "text": ln.strip()[:160]})
    bad = []
    commits: dict[str, bool] = {}
    turns: dict[str, bool] = {}
    for i, k, v in marks:
        why = None
        if k == "c":
            if v not in commits:
                rc, _ = await _git(root, "cat-file", "-e", f"{v}^{{commit}}")
                commits[v] = rc == 0 and bool(re.fullmatch(r"[0-9a-f]{6,40}", v))
            why = None if commits[v] else "그 커밋이 저장소에 없습니다"
        elif k == "t":
            if not v.isdigit():
                why = "턴 번호가 숫자가 아닙니다"
            elif engine is not None:
                if v not in turns:
                    async with engine.connect() as c:
                        turns[v] = (await c.execute(text("SELECT 1 FROM turn WHERE id = :i"), {"i": int(v)})).first() is not None
                why = None if turns[v] else "그 턴이 DB에 없습니다"
        else:
            why = _file_problem(Path(root), k, v)
        if why:
            bad.append({"line": i, "mark": f"[{k}:{v}]", "why": why})
    total = len(marks)
    head = parse_head(body)
    if head is not None:
        # 머리 주석도 근거다 — 읽은 커밋이 있어야 「코드가 바뀐 편」을 셀 수 있고, 다루는 곳이 있어야 그 셈이 뜻이 있다
        at = head["line"]
        total += 1 + max(1, len(head["covers"]))
        read = head["read"]
        if not read:
            bad.append({"line": at, "mark": f"머리 주석 {READ}", "why": "적혀 있지 않습니다"})
        else:
            rc, _ = await _git(root, "cat-file", "-e", f"{read}^{{commit}}")
            if rc != 0 or not re.fullmatch(r"[0-9a-f]{6,40}", read):
                bad.append({"line": at, "mark": f"머리 주석 {READ} {read}", "why": "그 커밋이 저장소에 없습니다"})
        if not head["covers"]:
            bad.append({"line": at, "mark": f"머리 주석 {COVERS}", "why": "적혀 있지 않습니다"})
        view = FsView(root)
        for c in head["covers"]:
            why = covers_problem(c, view)
            if why:
                bad.append({"line": at, "mark": f"머리 주석 {COVERS} {c}", "why": why})
    return {"total": total, "ok": total - len(bad), "bad": bad, "unsupported": unsupported}


async def revision(repo: str, base: str, branch: str, feedback_at: datetime | None) -> dict[str, Any]:
    """고친 양 — 사람이 두 번째로 말하기(feedback_at, UTC) 전의 커밋은 초안, 뒤는 고침. 줄 수는 더한 줄 + 뺀 줄."""
    _, log = await _git(repo, "log", "--reverse", "--format=@%h %ct", "--numstat", f"{base}..{branch}")
    draft = rev = 0
    dc = rc = 0
    cur_after = False
    for ln in log.splitlines():
        if ln.startswith("@"):
            _, ts = ln[1:].split()
            when = datetime.fromtimestamp(int(ts), UTC).replace(tzinfo=None)
            cur_after = feedback_at is not None and when >= feedback_at
            if cur_after:
                rc += 1
            else:
                dc += 1
            continue
        parts = ln.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            n = int(parts[0]) + int(parts[1])
            if cur_after:
                rev += n
            else:
                draft += n
    return {"draft_lines": draft, "revision_lines": rev, "draft_commits": dc, "revision_commits": rc,
            "ratio": round(rev / draft, 3) if draft else None}


async def feedback_time(engine: Any, session_id: int) -> datetime | None:
    """서기 세션에서 사람이 두 번째로 말한 때 — 첫 번째는 일감(첫 글)이다."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT started_at FROM turn WHERE session_id = :s AND origin = 'human' ORDER BY seq LIMIT 2"), {"s": session_id})).all()
    return rows[1][0] if len(rows) > 1 else None


async def review(engine: Any, repo: str, wt_path: str, base: str, branch: str, session_id: int) -> dict[str, Any]:
    """서기 브랜치 검토 — 바뀐 .md마다 근거 확인 + 고친 양."""
    _, names = await _git(repo, "diff", "--name-only", f"{base}...{branch}", "--", "*.md")
    files = []
    for f in [x for x in names.splitlines() if x]:
        p = Path(wt_path, f)
        if p.is_file():
            files.append({"path": f, **await check_text(p.read_text(encoding="utf-8", errors="replace"), wt_path, engine)})
    rev = await revision(repo, base, branch, await feedback_time(engine, session_id))
    return {"files": files, "marks": sum(x["total"] for x in files), "bad": sum(len(x["bad"]) for x in files),
            "unsupported": sum(len(x["unsupported"]) for x in files), "revision": rev}
