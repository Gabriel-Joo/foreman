"""인계 검증(11-06) — 인계를 만들 때의 git · 잠금 상태를 적어 두고, 넣을 때 지금과 비교해 "인계 뒤 바뀐 것"을 붙인다.

근거: 인계 r=690cec(세션 65d05e2c)를 받은 세션이 "c는 cc/foreman-2에만 있고 아직 합치지 않았다 · 잠금은 65d05e2c"를 읽었는데,
그 사이 c는 main에 합쳐졌고 worktree는 없어졌고 잠금은 다른 세션에 있었다. 받은 세션이 알아챈 것은 우연이었다
(log/overlap_alert_20261106.md) — 조용한 고장과 같은 모양이라 기계가 본다.

- snapshot(cwd, project, schema): 인계 요약을 만들 때. 실패해도 요약은 만든다(상태 없이)
- drift(state, project, schema, paths): 넣을 때(미리보기 포함). 줄 목록 — 비면 바뀐 것 없음
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bridge import worktree as wt

MAX_SUBJECTS = 5


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _git(cwd: str, *args: str) -> str | None:
    try:
        rc, out = await wt.git(cwd, *args, check=False)
    except OSError:
        return None
    return out if rc == 0 else None


def _lock_of(schema: Any, project: str | None) -> dict[str, Any] | None:
    if schema is None or not project:
        return None
    h = schema.view().get(project)
    if not h or not h.get("held"):
        return None
    return {"cc": (h.get("cc") or "")[:8], "wt": h.get("wt")}


async def snapshot(cwd: str | None, project: str | None, schema: Any = None) -> dict[str, Any] | None:
    """그 세션 폴더 기준의 지금 상태. git 저장소가 아니면 None."""
    if not cwd or not Path(cwd).is_dir():
        return None
    top = await _git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return None
    repo, wt_name = wt.split(top)
    head = await _git(top, "rev-parse", "HEAD")
    branch = await _git(top, "branch", "--show-current")
    base = await _git(repo, "branch", "--show-current")
    base_head = await _git(repo, "rev-parse", "HEAD") if base else None
    return {"at": _now().isoformat(timespec="seconds") + "Z", "repo": repo, "worktree": wt_name,
            "branch": branch or None, "head": head, "base": base or None, "base_head": base_head,
            "lock": _lock_of(schema, project)}


def _ago(at: str | None) -> str:
    if not at:
        return ""
    try:
        secs = (_now() - datetime.fromisoformat(at.rstrip("Z"))).total_seconds()
    except ValueError:
        return ""
    m = int(secs // 60)
    return f"{m // 60}시간 {m % 60}분" if m >= 60 else f"{m}분"


async def drift(state: dict[str, Any] | None, project: str | None, schema: Any = None,
                paths: list[str] | None = None) -> list[str]:
    """인계 뒤 바뀐 것 — 사람이 읽는 줄 목록. 상태가 없거나 저장소가 사라졌으면 그 사실 한 줄."""
    if not state or not state.get("repo"):
        return []
    repo = state["repo"]
    if not Path(repo).is_dir():
        return [f"인계 때 저장소 `{repo}`가 지금은 없습니다."]
    out: list[str] = []
    head, base, base_head = state.get("head"), state.get("base"), state.get("base_head")
    short = (head or "")[:7]
    # ① worktree · 브랜치
    if state.get("worktree"):
        name, branch = state["worktree"], state.get("branch") or f"{wt.BRANCH_PREFIX}{state['worktree']}"
        path = os.path.join(repo, wt.WT_DIR, name)
        merged = bool(head and base and await _git(repo, "merge-base", "--is-ancestor", head, base) is not None)
        if not Path(path).is_dir():
            out.append(f"worktree `{name}`(브랜치 `{branch}`)는 지금 없습니다 — "
                       + (f"인계 때 커밋 {short}은 `{base}`에 합쳐졌습니다." if merged
                          else f"인계 때 커밋 {short}은 `{base}`에 없습니다(합치지 않고 버렸을 수 있습니다)."))
        else:
            n = await _git(repo, "rev-list", "--count", f"{head}..{branch}") if head else None
            if n and n != "0":
                out.append(f"브랜치 `{branch}`에 인계 뒤 커밋이 {n}개 더 있습니다.")
            if merged:
                out.append(f"인계 때 커밋 {short}은 이미 `{base}`에 합쳐졌습니다.")
    elif state.get("branch"):
        now_branch = await _git(repo, "branch", "--show-current")
        if now_branch and now_branch != state["branch"]:
            out.append(f"원본 폴더의 브랜치가 `{state['branch']}`에서 `{now_branch}`로 바뀌었습니다.")
        n = await _git(repo, "rev-list", "--count", f"{head}..{state['branch']}") if head else None
        if n and n != "0" and state["branch"] != base:
            out.append(f"브랜치 `{state['branch']}`에 인계 뒤 커밋이 {n}개 더 있습니다.")
    # ② 기준 브랜치(main)에 생긴 커밋
    if base and base_head:
        log = await _git(repo, "log", "--format=%h %s", f"{base_head}..{base}")
        subs = [x for x in (log or "").splitlines() if x.strip()]
        if subs:
            more = f" 외 {len(subs) - MAX_SUBJECTS}개" if len(subs) > MAX_SUBJECTS else ""
            out.append(f"`{base}`에 인계 뒤 커밋이 {len(subs)}개 생겼습니다: "
                       + " / ".join(s[:80] for s in subs[:MAX_SUBJECTS]) + more)
        # ③ 「읽을 곳」 파일 중 그 사이 바뀐 것
        if paths:
            ch = await _git(repo, "log", "--name-only", "--format=", f"{base_head}..{base}", "--", *paths)
            files = sorted({x for x in (ch or "").splitlines() if x.strip()})
            if files:
                out.append("읽을 곳 중 인계 뒤 바뀐 파일: " + ", ".join(f"`{f}`" for f in files[:8]))
    # ④ 스키마 잠금
    then, now = state.get("lock"), _lock_of(schema, project)
    if (then or {}).get("cc") != (now or {}).get("cc"):
        who = lambda x: f"세션 {x['cc']}" + (f"(worktree {x['wt']})" if x.get("wt") else "") if x else "아무도 없음"  # noqa: E731
        out.append(f"스키마 잠금이 {who(then)}에서 {who(now)}로 바뀌었습니다.")
    if out:
        ago = _ago(state.get("at"))
        out.insert(0, f"인계를 쓴 지 {ago} 지났습니다." if ago else "인계를 쓴 뒤 상태가 바뀌었습니다.")
    return out


def block(lines: list[str]) -> str:
    """넣는 글 맨 앞에 붙일 절. 비면 빈 글."""
    if not lines:
        return ""
    return ("## 인계 뒤 바뀐 것 (브리지가 git · 잠금으로 확인)\n"
            + "\n".join(f"- {x}" for x in lines)
            + "\n- **아래 「지금 상태」 · 「다음 할 일」은 인계를 쓴 때 기준이다. 위와 어긋나는 것은 지금 상태를 직접 보고 다시 판단하라.**\n")
