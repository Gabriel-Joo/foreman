"""서기에게 물어보기(11-10) — 서기 세션 없이 문서·기록에 대해 묻는다. docs/12_scribe.md 「12. 물어보기」.

`claude -p` 한 번(읽기 전용 · 세션을 남기지 않음)이다. 답만 하고 파일은 고치지 않는다 —
고치는 일은 [시키기]로 worktree 서기 세션을 띄우고 [합치기]로 검토한다. 막는 것은 말이 아니라 도구다(foreman.py `_plan`과 같은 허용 목록).
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge.inject import Refused
from bridge.usage import record_cli

ASK_MAX = 2000              # 질문 글자 상한
ASK_TIMEOUT_S = 120.0
COMMIT_DAYS = 3             # 재료에 넣는 최근 커밋 기간

INSTRUCTIONS = """너는 이 프로젝트의 문서 담당(서기)이다. 사람이 문서 · 기록에 대해 묻는다. 아래 재료와 저장소 파일(README · docs · log · CLAUDE.md)을 읽고 한국어로 답하라.
- 읽기만 한다. 파일을 고치거나 명령을 실행할 수 없다. 문서를 고쳐 달라는 말이면 고치지 말고 "서기실의 [시키기]에서 시키십시오"라고 답하라.
- 근거가 있는 것만 답한다. 파일에서 읽은 것은 파일 이름을, 재료에서 읽은 것은 커밋 해시나 포스트잇 번호를 적어라. 모르면 모른다고 하라.
- 짧게 답한다. 비밀값(.env*, 토큰, 키)은 읽지도 적지도 마라.
"""

_ALLOWED = "Read,Grep,Glob"
_DENIED = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent"


async def material(engine: Any, project: str, repo: str) -> str:
    """재료 묶음(LLM 없음) — 받은 할 일 · 최근 커밋. 비밀값은 가린다."""
    from bridge import scribe as sc
    from bridge import scribe_room as sr
    from bridge.mask import Masker
    now = datetime.now(UTC).replace(tzinfo=None)
    lines = [f"# 재료 — {project} ({sc.kst(now)} KST, 저장소 {repo})", ""]
    inbox = await sr.inbox_list(engine, project, 30)
    lines.append(f"## 포스트잇 {len(inbox)}개(최근 것부터, 닫힌 것 포함)")
    for x in inbox:
        lines.append(f"- #{x['id']} [{sr.inbox_label(x['state'], x.get('assignee'))}] {sc._clip(x['body'], 300)}")
    lines += ["", f"## 최근 {COMMIT_DAYS}일 커밋"]
    try:
        for c in sc.git_commits(repo, now - timedelta(days=COMMIT_DAYS), now)[-40:]:
            lines.append(f"- {c['sha']} {c['kst']} {c['subject']}")
    except Exception:  # noqa: BLE001 — git이 안 되면 커밋 절만 비운다
        lines.append("- (git 기록을 읽지 못했습니다)")
    return Masker().text("\n".join(lines))


async def ask(engine: Any, project: str, question: str, claude_bin: str = "claude", model: str = "sonnet") -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise Refused("묻는 글이 비었습니다")
    if len(question) > ASK_MAX:
        raise Refused(f"묻는 글이 너무 깁니다({ASK_MAX}자까지)")
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :p"), {"p": project})).first()
    repo = r[0] if r else None
    if not repo or not Path(repo, ".git").exists():
        raise Refused("이 프로젝트의 저장소를 찾지 못했습니다")
    prompt = INSTRUCTIONS + "\n" + await material(engine, project, repo) + "\n\n# 질문\n" + question
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    t0 = time.monotonic()
    try:
        p = await asyncio.create_subprocess_exec(
            claude_bin, "-p", "--model", model, "--output-format", "json", "--no-session-persistence",
            "--settings", '{"disableAllHooks": true}',
            "--allowedTools", _ALLOWED, "--disallowedTools", _DENIED,
            cwd=repo, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        out, err = await asyncio.wait_for(p.communicate(prompt.encode()), ASK_TIMEOUT_S)
    except TimeoutError:
        p.kill()
        raise Refused(f"{ASK_TIMEOUT_S:.0f}초 안에 답을 받지 못했습니다") from None
    except OSError as e:
        raise Refused(f"claude를 띄우지 못했습니다: {e}") from None
    import json
    raw = out.decode(errors="replace")
    try:
        j = json.loads(raw)
        answer = str(j.get("result") or "").strip()
    except ValueError:
        j, answer = None, ""
    await record_cli(engine, "scribe_ask", None, project, j)
    if not answer:
        raise Refused("답을 받지 못했습니다: " + (err.decode(errors="replace") or raw)[:200])
    from bridge.mask import Masker
    return {"answer": Masker().text(answer), "ms": round((time.monotonic() - t0) * 1000)}
