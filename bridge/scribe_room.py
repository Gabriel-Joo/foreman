"""서기실(12a, 11-06) — 서기에게 시킬 일 · 할 일 세기(LLM 없음) · 일 시키기(worktree 서기 세션).

시킬 일(사용자 11-06): 회고 쓰기 · 문서 점검 · README 갱신 · CLAUDE.md 정리 · 나중에 할 일 정리 · Notion 게시.
Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py)이고, 나머지는 서기 세션을 worktree로 띄운다 — 합치기가 사람의 검토 관문이다.
할 일(docs/12_scribe.md 「2. 언제 일하나」 2): 기계로 센다 — 서기 머리 위 "할 일 N", 누르면 목록. 자동으로 돌리지는 않는다.
다른 저장소(런슈즈 · 펫퍼민트)는 읽기만 하고, 일은 사람이 그 방 서기를 눌렀을 때만 띄운다(그 저장소의 CLAUDE.md를 따르게 한다).
"""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

KST = timedelta(hours=9)
README_STALE = 10            # README가 바뀐 뒤 커밋이 이만큼 쌓이면 "README 갱신"
RETRO_STALE = 10             # 마지막 회고 뒤 커밋이 이만큼이면 "회고 쓰기"
CLAUDE_MD_MAX = 80           # CLAUDE.md 줄 수 상한(설계 「2.」 예시)
LATER = re.compile(r"나중에|미루|나중 일|later", re.I)

TASKS = {
    "retro": {"title": "회고 쓰기", "desc": "DB 기록(사람이 바로잡은 곳 · 뒤집힌 결정 · 실수 먼저)을 읽고 새 회고를 씁니다."},
    "doccheck": {"title": "문서 점검", "desc": "코드와 문서(README · docs · CLAUDE.md)가 안 맞는 곳을 찾아 보고합니다. 고치지는 않습니다."},
    "readme": {"title": "README 갱신", "desc": "마지막 README 변경 뒤의 커밋 · 결과 문서로 로드맵 표를 맞춥니다."},
    "trim": {"title": "CLAUDE.md 정리", "desc": "꼭 지킬 것만 짧게 남기고 상세는 docs로 옮겨 가리킵니다."},
    "later": {"title": "나중에 할 일 정리", "desc": "대화에서 \"나중에 하자\"고 한 것을 모아 README 「나중에 할 일」 표에 넣습니다."},
    "portfolio": {"title": "포트폴리오 쓰기", "desc": "주제를 하나 골라 바깥 독자가 읽을 글을 portfolio/에 씁니다. 게시는 [게시] 버튼으로 합니다."},
    "publish": {"title": "Notion 게시", "desc": "회고 · 문서를 Notion에 올립니다. 세션 없이 [게시] 버튼으로 합니다."},
}
TOPICS_FILE = "config/portfolio.toml"   # 포트폴리오 주제 — 이 파일이 있는 저장소만 「포트폴리오 쓰기」를 보인다(12c, 11-06)


NUDGE_FILE = Path(__file__).resolve().parent.parent / "config" / "scribe.toml"
NUDGE_DEFAULT = {"new_min": 3, "oldest_days": 3}


def nudge_conf(path: Path | None = None) -> dict[str, int]:
    """서기 제안 기준(config/scribe.toml [nudge]) — 없거나 틀리면 기본값."""
    import tomllib
    try:
        raw = tomllib.loads(Path(path or NUDGE_FILE).read_text(encoding="utf-8")).get("nudge") or {}
    except (OSError, tomllib.TOMLDecodeError):
        raw = {}
    return {k: int(raw.get(k, v)) if str(raw.get(k, v)).isdigit() else v for k, v in NUDGE_DEFAULT.items()}


def nudge_of(inbox: list[dict[str, Any]], conf: dict[str, int] | None = None, now: datetime | None = None) -> dict[str, Any] | None:
    """서기 머리 위 "정리할까요?"(11-09) — 서기 몫 새로가 new_min개 이상이거나 가장 오래된 것이 oldest_days일 지났으면.
    자동은 제안까지만: 누르면 서기 창이 「나중에 할 일 정리」를 고른 채 열리고, 세션은 사람이 [시키기]를 눌러야 뜬다."""
    if not inbox:
        return None
    cf = conf or nudge_conf()
    days = ((now or datetime.now(UTC).replace(tzinfo=None)) - inbox[0]["created_at"]).days
    if len(inbox) >= cf["new_min"] or days >= cf["oldest_days"]:
        return {"n": len(inbox), "days": days, "why": f"새로 {len(inbox)}개" + (f" · 가장 오래된 것 {days}일째" if days >= 1 else "")}
    return None


def topics(repo: str) -> list[dict[str, Any]]:
    """포트폴리오 주제 — 순서대로. written: main에 portfolio/<slug>.md가 있나."""
    import tomllib
    f = Path(repo, TOPICS_FILE)
    if not f.is_file():
        return []
    try:
        raw = tomllib.loads(f.read_text(encoding="utf-8")).get("topic", [])
    except (tomllib.TOMLDecodeError, OSError):
        return []
    out = []
    for t in raw:
        slug = str(t.get("slug", ""))
        if not re.fullmatch(r"[0-9a-z_]{1,40}", slug):
            continue
        out.append({"slug": slug, "title": str(t.get("title", slug)), "about": str(t.get("about", "")),
                    "sources": [str(s) for s in t.get("sources", [])], "screenshots": bool(t.get("screenshots")),
                    "written": Path(repo, "portfolio", f"{slug}.md").is_file()})
    return out


def _git(repo: str, *a: str) -> str:
    try:
        return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def commits_since_path(repo: str, *paths: str) -> tuple[int, str | None]:
    """그 경로를 마지막으로 바꾼 커밋 뒤로 쌓인 커밋 수와 그 커밋."""
    last = _git(repo, "log", "-1", "--format=%h", "HEAD", "--", *paths)
    if not last:
        return 0, None
    n = _git(repo, "rev-list", "--count", f"{last}..HEAD")
    return (int(n) if n.isdigit() else 0), last


def stages_without_result(repo: str) -> list[str]:
    """docs/NN_*.md 중 결과 문서(log/NN_* · log/stage<N>_*)가 하나도 없는 것 — 단계를 했는데 기록이 없는지."""
    root = Path(repo)
    out = []
    logs = [p.name for p in (root / "log").glob("*.md")] if (root / "log").is_dir() else []
    if not any(x.endswith("_result.md") for x in logs):
        return []           # 결과 문서 관례(log/…_result.md)가 없는 저장소 — 펫퍼민트처럼 설계 문서 자체가 기록이면 거짓 경보다(11-06)
    for d in sorted((root / "docs").glob("[0-9][0-9]*_*.md")) if (root / "docs").is_dir() else []:
        m = re.match(r"(\d+)", d.name)
        if not m:
            continue
        nn, n = m.group(1), str(int(m.group(1)))
        if not any(x.startswith((f"{nn}_", f"{nn}a_", f"stage{n}_", f"stage{n}a_")) for x in logs):
            out.append(f"docs/{d.name}")
    return out


async def todo(engine: Any, publishers: dict[str, Any] | None = None, docsync: Any = None) -> dict[str, dict[str, Any]]:
    """프로젝트마다 할 일 — [{kind(시킬 일), title, why}]. 기계로만 센다. publishers — 프로젝트 → Notion 게시기(11-09 프로젝트마다)."""
    from bridge import docsync as ds
    publishers = publishers or {}
    async with engine.connect() as c:
        projects = (await c.execute(text("SELECT name, repo_path FROM project"))).all()
    out: dict[str, dict[str, Any]] = {}
    for name, repo in projects:
        if not repo or not Path(repo, ".git").exists():
            continue
        items: list[dict[str, str]] = []
        n, last = commits_since_path(repo, "README.md")
        if n >= README_STALE:
            items.append({"kind": "readme", "title": f"README 갱신 — 그 뒤 커밋 {n}개", "why": f"README가 {last} 뒤로 그대로입니다"})
        for d in stages_without_result(repo)[:5]:
            items.append({"kind": "doccheck", "title": f"결과 문서 없는 단계 — {d}", "why": "설계 문서는 있는데 log/에 결과가 없습니다"})
        cm = Path(repo, "CLAUDE.md")
        if cm.is_file():
            lines = len(cm.read_text(encoding="utf-8", errors="replace").splitlines())
            if lines > CLAUDE_MD_MAX:
                items.append({"kind": "trim", "title": f"CLAUDE.md 정리 — {lines}줄", "why": f"{CLAUDE_MD_MAX}줄을 넘었습니다"})
        retros = sorted(Path(repo, "log").glob("retro_*.md")) if Path(repo, "log").is_dir() else []
        rn, _ = commits_since_path(repo, *[str(p.relative_to(repo)) for p in retros]) if retros else (0, None)
        if retros and rn >= RETRO_STALE:
            items.append({"kind": "retro", "title": f"회고 쓰기 — 마지막 회고 뒤 커밋 {rn}개", "why": retros[-1].name})
        later = await _later_count(engine, name, repo)
        if later:
            items.append({"kind": "later", "title": f"나중에 할 일 정리 — \"나중에\" {later}번", "why": "지난 정리가 합쳐진 뒤(없으면 처음부터) 사람이 미룬 말"})
        inbox = await inbox_new(engine, name)
        nudge = nudge_of(inbox)
        if inbox:
            age = (datetime.now(UTC).replace(tzinfo=None) - inbox[0]["created_at"]).days
            items.append({"kind": "later", "title": f"받은 할 일 {len(inbox)}개" + (f" — 가장 오래된 것 {age}일째" if age >= INBOX_STALE_DAYS else ""),
                          "why": "머리줄 [＋ 할 일]로 받은 글 — 「나중에 할 일 정리」가 README 표로 옮깁니다"})
        if (pub := publishers.get(name)) is not None:
            # 11-09 런슈즈 요청 3-1 — 파일마다 한 줄이던 것을 묶음마다 한 줄로. 포트폴리오는 사람이 [게시](바깥 독자에게 내는 글)
            try:
                if name == "foreman":
                    pend = [d for d in await pub.list() if d["status"] == "new" or d["changed"]]
                    if pend:
                        nn = sum(d["status"] == "new" for d in pend)
                        items.append({"kind": "publish", "title": f"Notion 포트폴리오 — 파일 {len(pend)}개 뒤처짐"
                                      f"({' · '.join(x for x in (f'새 {nn}' if nn else '', f'바뀜 {len(pend) - nn}' if len(pend) - nn else '') if x)})",
                                      "why": ", ".join(Path(d["path"]).name for d in pend[:4]) + (" …" if len(pend) > 4 else "")
                                      + " — 아래 「Notion 게시」에서 올립니다"})
                items += await ds.todo_items(pub, (docsync.last.get(name) if docsync else None))
            except Exception:  # noqa: BLE001 — Notion이 꺼져 있어도 다른 할 일은 센다
                pass
        opened = await open_tasks(engine, name)
        tps = [{**{k: t[k] for k in ("slug", "title", "about", "written")}, "blocked": blocked("portfolio", opened, t["slug"])}
               for t in topics(repo)]
        out[name] = {"items": items, "open": opened, "topics": tps, "nudge": nudge,
                     "blocked": {k: b for k in TASKS if k not in ("publish", "portfolio") and (b := blocked(k, opened))}}
    return out


LATER_ACT = "scribe-later"     # session_action — 나중에 할 일 정리를 띄울 때 "어디까지 봤나"(detail: until ISO)
TASK_ACT = "scribe-task"       # session_action — 서기 일을 띄울 때 무슨 일인지(detail: task). 합치거나 버리기 전까지 "열려 있다"

# 동시에 시키기(11-06 판단) — 허용하되 셋을 막는다: 같은 일 · 같은 파일 · 프로젝트당 둘 넘게.
# worktree는 서로를 못 봐서 충돌은 합칠 때 난다 — 같은 파일을 고치는 두 일이 열려 있으면 뒤의 합치기가 rebase 충돌.
# 둘까지인 이유: 문서 초안은 사람이 diff를 하나씩 보고 합친다(검토 빚, docs/12_scribe.md 「2.」), 각각 Opus 세션이다
TOUCHES = {"retro": {"log/retro_"}, "doccheck": {"log/doccheck_"}, "readme": {"README.md"}, "later": {"README.md"},
           "trim": {"CLAUDE.md", "docs/"}}
MAX_OPEN = 2


async def open_tasks(engine: Any, project: str) -> list[dict[str, Any]]:
    """열려 있는 서기 일 — 띄웠고 아직 합치지도 버리지도 않은 것(세션이 끝났어도 합치기를 기다리면 열려 있다)."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT sa.session_id, sa.detail, COALESCE(cs.custom_title, cs.title) FROM session_action sa "
            "JOIN character_session cs ON cs.id = sa.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "JOIN project p ON p.id = ch.project_id WHERE p.name = :p AND sa.action = :a AND sa.ok AND NOT EXISTS ("
            "  SELECT 1 FROM session_action m WHERE m.session_id = sa.session_id AND m.action IN ('wt-merge', 'wt-discard') AND m.ok) "
            "ORDER BY sa.id"), {"p": project, "a": TASK_ACT})).all()
    out = []
    for sid, d, t in rows:
        w = (d or "").split()
        if w:
            out.append({"session_id": sid, "task": w[0], "topic": w[1] if len(w) > 1 else None, "title": t})
    return out


def touches(task: str, topic: str | None = None) -> set[str]:
    """그 일이 고치는 파일(앞부분) — 포트폴리오는 주제마다 다르다(글 · 사진 모두 portfolio/<slug>로 시작)."""
    if task == "portfolio":
        return {f"portfolio/{topic}"} if topic else {"portfolio/"}
    return TOUCHES.get(task, set())


def blocked(task: str, opened: list[dict[str, Any]], topic: str | None = None) -> str | None:
    """이 일을 지금 시킬 수 없는 까닭(없으면 None) — 화면 버튼과 서버가 같은 판단을 쓴다.
    포트폴리오는 주제가 다르면 다른 일이다(서로 다른 파일) — 같은 주제만 막는다."""
    for o in opened:
        if o["task"] == task and (task != "portfolio" or o.get("topic") == topic):
            what = TASKS[task]["title"] + (f" — {topic}" if task == "portfolio" else "")
            return f"「{what}」이 이미 열려 있습니다(세션 {o['session_id']}) — 합치거나 버린 뒤에 시켜 주세요"
    for o in opened:
        common = sorted(touches(task, topic) & touches(o["task"], o.get("topic")))
        if common:
            return (f"「{TASKS.get(o['task'], {}).get('title', o['task'])}」(세션 {o['session_id']})와 같은 파일({', '.join(common)})을 "
                    "고칩니다 — 합칠 때 충돌합니다. 그 일을 합치거나 버린 뒤에 시켜 주세요")
    if len(opened) >= MAX_OPEN:
        return f"서기 일이 이미 {len(opened)}개 열려 있습니다(동시에 {MAX_OPEN}개까지) — 하나를 합치거나 버린 뒤에 시켜 주세요"
    return None


async def later_since(engine: Any, project: str) -> datetime | None:
    """나중에 할 일 정리의 기준점 — 지난번 정리 세션이 **합쳐진** 것의 until. 없으면 None(처음부터 전부).
    11-06: README 마지막 변경을 기준으로 했더니 README가 막 바뀐 뒤라 사람 턴이 0개였다. README는 다른 일로도 자주 바뀐다.
    버린 정리(합치지 않음)는 세지 않는다 — 다음에 같은 범위를 다시 본다(이미 표에 있는 것은 서기가 뺀다).
    커밋 0개로 합쳐진 정리는 센다 — 다 봤고 더할 것이 없었다는 뜻이다."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT sa.detail FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE p.name = :p AND sa.action = :a AND sa.ok AND EXISTS (SELECT 1 FROM session_action m "
            "  WHERE m.session_id = sa.session_id AND m.action = 'wt-merge' AND m.ok) ORDER BY sa.id DESC LIMIT 1"),
            {"p": project, "a": LATER_ACT})).first()
    if not rows or not rows[0]:
        return None
    try:
        return datetime.fromisoformat(rows[0].split()[0])
    except ValueError:
        return None


async def _later_count(engine: Any, project: str, repo: str) -> int:
    return len(await later_prompts(engine, project, await later_since(engine, project)))


# ── 할 일 받는 함(11-09, migrations/0027) ─────────────────────────
# 사람이 머리줄 [＋ 할 일]에 적은 글 — 세션을 거치지 않고 그대로 둔다. 「나중에 할 일 정리」 서기가 재료로 받아 README 표로 옮긴다.
# 상태는 계산한다: 버림(dropped_at) / 새로(아무도 안 가져감 · 가져간 정리를 버림) / 정리 중(가져간 세션이 아직 열림) / 옮김(합쳐짐)
INBOX_MAX = 8000
INBOX_STALE_DAYS = 3        # 새로인 채 이만큼 지나면 서기 할 일 글에 "N일째"를 붙여 눈에 띄게(조용히 쌓이지 않게)
# 받는 사람(11-09, 0028) — 서기 정리(「나중에 할 일 정리」가 README 표로) · 코더에게(그 방 코더의 "맡길 일", 계획으로 세션이 가져감)
ASSIGNEES = ("scribe", "coder")
# 코더 몫이 끝나는 때: 가져간 세션이 합쳐짐, 또는 원본 폴더(worktree 아님) 세션이 끝남 — 원본 폴더 세션은 합치기가 없다
_INBOX_STATE = ("CASE WHEN i.dropped_at IS NOT NULL THEN 'dropped' WHEN i.taken_by IS NULL THEN 'new' "
                "WHEN EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = i.taken_by AND m.action = 'wt-merge' AND m.ok) THEN 'moved' "
                "WHEN EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = i.taken_by AND m.action = 'wt-discard' AND m.ok) THEN 'new' "
                "WHEN i.assignee = 'coder' AND EXISTS (SELECT 1 FROM character_session t WHERE t.id = i.taken_by "
                "  AND t.worktree_path IS NULL AND t.detached_at IS NOT NULL) THEN 'moved' "
                "ELSE 'taking' END")
INBOX_LABEL = {"new": "새로", "taking": "서기가 정리 중", "moved": "옮김", "dropped": "버림"}
INBOX_LABEL_CODER = {"new": "새로", "taking": "코더가 하는 중", "moved": "끝남", "dropped": "버림"}
ASSIGNEE_KO = {"scribe": "서기 정리", "coder": "코더에게"}


def inbox_label(state: str, assignee: str | None) -> str:
    """받는 사람에 맞는 상태 이름 — 코더 몫은 합쳐지면 "옮김" 대신 "끝남"."""
    return (INBOX_LABEL_CODER if assignee == "coder" else INBOX_LABEL).get(state, state)


async def inbox_add(engine: Any, project: str, body: str, assignee: str = "scribe") -> int:
    from bridge.inject import Refused
    body = (body or "").strip()
    if not body:
        raise Refused("적을 글이 비어 있습니다")
    if len(body) > INBOX_MAX:
        raise Refused(f"글이 너무 깁니다({len(body)}자) — {INBOX_MAX}자까지 받습니다")
    if assignee not in ASSIGNEES:
        raise Refused(f"받는 사람은 서기 정리 · 코더에게 중 하나입니다: {assignee}")
    async with engine.begin() as c:
        if not (await c.execute(text("SELECT 1 FROM project WHERE name = :p"), {"p": project})).first():
            raise Refused(f"모르는 프로젝트입니다: {project}")
        r = await c.execute(text("INSERT INTO todo_inbox (project, body, assignee) VALUES (:p, :b, :a)"),
                            {"p": project, "b": body, "a": assignee})
        return int(r.lastrowid)


async def inbox_list(engine: Any, project: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """최근 것부터 — 버린 것도 보인다(나중에 다시 볼 수 있게)."""
    q = (f"SELECT i.id, i.project, i.body, i.assignee, i.created_at, i.taken_by, i.dropped_at, {_INBOX_STATE} AS state FROM todo_inbox i "
         + ("WHERE i.project = :p " if project else "") + "ORDER BY i.id DESC LIMIT :n")
    async with engine.connect() as c:
        rows = (await c.execute(text(q), {"p": project, "n": limit})).mappings().all()
    return [dict(r) for r in rows]


async def inbox_new(engine: Any, project: str, assignee: str = "scribe") -> list[dict[str, Any]]:
    """받는 사람이 가져갈 것 — 새로인 것만, 오래된 것부터. 서기 「나중에 할 일 정리」는 서기 몫만 가져간다."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            f"SELECT i.id, i.body, i.created_at FROM todo_inbox i WHERE i.project = :p AND i.assignee = :a "
            f"AND {_INBOX_STATE} = 'new' ORDER BY i.id"), {"p": project, "a": assignee})).mappings().all()
    return [dict(r) for r in rows]


async def inbox_take_coder(engine: Any, iid: int, session_id: int) -> bool:
    """코더에게 받은 할 일을 계획으로 띄운 세션이 가져간다(11-09) — 새로인 코더 몫만. 아니면 False(시작은 막지 않는다)."""
    async with engine.begin() as c:
        r = await c.execute(text(
            f"UPDATE todo_inbox i SET i.taken_by = :s, i.taken_at = UTC_TIMESTAMP(3) WHERE i.id = :i AND i.assignee = 'coder' "
            f"AND {_INBOX_STATE} = 'new'"), {"s": session_id, "i": iid})
        return r.rowcount > 0


async def inbox_drop(engine: Any, iid: int) -> bool:
    async with engine.begin() as c:
        r = await c.execute(text("UPDATE todo_inbox SET dropped_at = UTC_TIMESTAMP(3) WHERE id = :i AND dropped_at IS NULL"), {"i": iid})
        return r.rowcount > 0


async def _inbox_take(engine: Any, ids: list[int], session_id: int) -> None:
    if not ids:
        return
    from sqlalchemy import bindparam
    async with engine.begin() as c:
        await c.execute(text("UPDATE todo_inbox SET taken_by = :s, taken_at = UTC_TIMESTAMP(3) WHERE id IN :ids")
                        .bindparams(bindparam("ids", expanding=True)), {"s": session_id, "ids": ids})


async def later_prompts(engine: Any, project: str, since: datetime | None, limit: int = 300) -> list[dict[str, Any]]:
    """사람이 "나중에 · 미루"라고 한 턴 — since(UTC) 뒤, None이면 처음부터. 오래된 것부터, limit개까지."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT t.id, t.started_at, t.prompt_text FROM turn t JOIN character_session cs ON cs.id = t.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE p.name = :p AND t.origin = 'human' AND cs.hidden_at IS NULL AND t.started_at >= :s ORDER BY t.started_at"),
            {"p": project, "s": since or datetime(2000, 1, 1)})).mappings().all()
    return [dict(r) for r in rows if LATER.search(r["prompt_text"] or "")][:limit]


COMMON = """
지켜야 할 것
- 먼저 이 저장소의 CLAUDE.md와 `docs/style_guide.md`(있으면)를 읽는다
- 너는 따로 작업(worktree) 세션이다: 이 브랜치에 커밋하고 push하지 않는다. 브리지를 다시 띄우지 않는다
- 끝나면 바꾼 파일만 `git add`해 커밋하고, 마지막 응답에 바꾼 파일 · 무엇을 · 확인 못 한 것을 짧게 알린다. 사람이 [합치기] 전에 diff를 본다"""


def task_prompt(task: str, project: str, repo: str, extra: dict[str, str] | None = None) -> str:
    today = (datetime.now(UTC) + KST).strftime("%Y%m%d")
    e = extra or {}
    head = f"[FOREMAN 서기 일감 — {TASKS[task]['title']}] {project}\n\n너는 이 프로젝트의 서기(문서 담당)다.\n"
    if task == "doccheck":
        body = f"""할 일: 코드와 문서가 안 맞는 곳을 찾는다. **고치지 마라 — 보고만.**
- 대상: README · docs/ · CLAUDE.md에 적힌 경로 · 파일 · 함수 · 설정 키 · 명령 · 숫자가 지금 저장소와 맞는지
- 결과 문서가 없는 단계: {e.get('stages') or '(없음)'}
- 항목마다: 문서 위치(`경로 「절」`) · 문서에 적힌 것 · 실제 · 근거(파일:줄 · 커밋)
- 쓸 곳: `log/doccheck_{today}.md` — 어긋남만, 맞는 것은 쓰지 않는다"""
    elif task == "readme":
        body = f"""할 일: README를 지금에 맞춘다.
- 마지막 README 변경({e.get('since') or '?'}) 뒤의 커밋 · `log/` 결과 문서를 읽고 로드맵 표의 상태 · 링크를 고친다
- 결과 문서를 가리키고 내용을 다시 쓰지 않는다. README.md만 고친다"""
    elif task == "trim":
        body = f"""할 일: CLAUDE.md를 정리한다(docs/12_scribe.md 「trim」).
- 꼭 지킬 금지 · 결정만 짧게 남기고, 상세는 docs/로 옮겨 가리킨다. 규칙을 없애지 않는다 — 옮길 뿐이다
- 옮긴 규칙마다 목적지를 표로: `log/trim_{today}.md`
- 사용자 원문 인용 · 날짜 표시는 그대로 둔다"""
    elif task == "later":
        body = f"""할 일: 대화에서 "나중에 하자"고 한 것과 사람이 [＋ 할 일]로 적은 것을 README 「나중에 할 일 (정해 두고 미룬 것)」 표에 넣는다.
- 재료(저장소 밖, 사람 말 원문): `{e.get('materials') or '(없음)'}` — 받은 할 일(모두 넣는다) + 지난 정리가 합쳐진 뒤(없으면 처음부터) "나중에 · 미루"가 나온 사람 말
- 받은 할 일은 근거 칸에 `받은 할 일 #번호`를 적는다. 같은 일이 표에 이미 있으면 새 줄을 만들지 않고 그 줄에 보탠다
- 항목마다 무엇 · 언제 · 조건 · 근거(결과 문서 · log). 이미 한 것은 표에서 뺀다. 그때뿐인 "나중에"(잠깐 뒤에)는 넣지 않는다
- README.md만 고친다"""
    elif task == "portfolio":
        slug = e["slug"]
        shots = (f"""
- 화면 사진: `tools/screen.py`로 직접 찍는다(사람에게 부탁하지 않는다). 예: `.venv/bin/python tools/screen.py --themes magic --sizes 1920x1080 --views foreman --out /tmp/<폴더>`
  쓸 것만 `portfolio/img/{slug}_<무엇>.png`로 복사해 커밋한다(한 장에 1MB 안쪽, 많아야 셋). 글에는 `![설명](img/{slug}_<무엇>.png)`
  찍기 전에 화면에 비밀값 · 토큰 · 다른 프로젝트의 민감한 글이 없는지 사진을 열어 본다""" if e.get("screenshots") == "1" else "")
        body = f"""할 일: 포트폴리오 글 「{e['title']}」을 `portfolio/{slug}.md`에 쓴다(12c). 읽는 사람은 이 저장소 밖의 사람이다(채용 담당 · AI 인프라 · AI 엔지니어).
- 이 글이 다룰 것: {e['about']}
- 먼저 읽을 재료: {e['sources']} — 필요하면 더 읽는다(코드 · git log · 다른 log/)
- 이미 쓴 다른 글: {e.get('siblings') or '(없음)'} — 같은 내용을 다시 쓰지 말고 "→ 「제목」"으로 가리킨다

틀(`docs/style_guide.md` 「포트폴리오 문서」)
1. `# 제목` 다음 줄에 `> 이 글은 …을 다룬다.` 한 줄(사용자 결정 11-06 — 주제 글마다 머리에 "이 글은 뭘 다루는지")
2. 한 줄 요약(굵게) → 문제(왜 필요했나) → 판단(무엇을 고르고 무엇을 버렸나, 이유) → 구조 · 흐름 → 겪은 문제와 풀이 → 결과 · 숫자 → 한계 · 다음
- 구조는 ```mermaid 블록으로 그려도 된다(Notion에 코드로 올라가고 사람이 한 번 미리보기로 바꾼다){shots}

지켜야 할 것(바깥 독자)
- 근거 표시는 그대로 단다: `[c:해시]` · `[log:파일]` · `[docs:파일]` — 게시할 때 글자만 남는다(저장소는 비공개라 링크가 없다). `[t:턴]`은 쓰지 않는다
- 내부 주소 · 포트 · 경로 중 독자에게 뜻 없는 것(서버 IP, `/home/…`, tmux 이름)은 쓰지 않는다. 프롬프트 · 대화 원문을 길게 옮기지 않는다(한 줄 인용은 된다)
- 숫자는 log · DB · git에서 온 것만. 꾸밈말(혁신적 · 완벽하게) 없이, 한 것과 안 한 것을 정직하게
- 고칠 곳은 `portfolio/{slug}.md`와 `portfolio/img/{slug}_*`뿐이다 — 다른 파일은 건드리지 않는다
- 커밋 메시지: `portfolio: {slug} — <한 줄>`"""
    else:
        raise ValueError(task)
    return head + body + "\n" + COMMON


async def start(m: Any, engine: Any, project: str, task: str, topic: str | None = None) -> dict[str, Any]:
    """서기 일을 worktree 세션으로 띄운다(handoff.spawn_new). 회고는 재료 묶음을 먼저 만든다. 포트폴리오는 주제(topic)가 있어야 한다."""
    from bridge import scribe as sc
    from bridge.inject import Refused
    if task not in TASKS or task == "publish":
        raise Refused("세션으로 시키는 일이 아닙니다")
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :p"), {"p": project})).first()
    repo = r[0] if r else None
    if not repo or not Path(repo, ".git").exists():
        raise Refused("이 프로젝트의 저장소를 찾지 못했습니다")
    tp = None
    if task == "portfolio":
        tps = topics(repo)
        tp = next((t for t in tps if t["slug"] == topic), None)
        if tp is None:
            raise Refused(f"포트폴리오 주제를 찾지 못했습니다({topic or '없음'}) — {TOPICS_FILE}에 있는 주제만 시킬 수 있습니다")
    why = blocked(task, await open_tasks(engine, project), topic if task == "portfolio" else None)
    if why:
        raise Refused(why)
    now = datetime.now(UTC).replace(tzinfo=None)
    day = (now + KST).strftime("%Y%m%d")
    extra: dict[str, str] = {}
    if task == "retro":
        retros = sorted(Path(repo, "log").glob("retro_*.md"))
        last = _git(repo, "log", "-1", "--format=%cI", "HEAD", "--", *[str(p.relative_to(repo)) for p in retros]) if retros else ""
        start_utc = datetime.fromisoformat(last).astimezone(UTC).replace(tzinfo=None) if last else now - timedelta(days=1)
        d = await sc.collect(engine, project, start_utc, now, repo)
        from bridge.mask import Masker
        body = sc.render(project, start_utc, now, d, repo, None, None, Masker())
        mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / "materials.md", body)
        period = f"{sc.kst(start_utc)} ~ {sc.kst(now)} KST"
        prompt = sc.retro_prompt(project, period, str(mat), f"log/retro_{day}_{project}.md")
    elif task == "later":
        when = await later_since(engine, project)
        rows = await later_prompts(engine, project, when)
        inbox = await inbox_new(engine, project)
        if not rows and not inbox:         # 빈손으로 Opus 세션을 띄우지 않는다(11-06 — 범위가 비어 사람 턴 0개로 떴다)
            raise Refused(f"{'지난 정리 뒤로' if when else '지금까지'} \"나중에 · 미루\"라고 한 사람 말도, 받은 할 일도 없습니다 — 띄우지 않았습니다")
        from bridge.mask import Masker
        mk = Masker()
        lines = [f"# 미룬 말 · 받은 할 일 — {project} ({(sc.kst(when) + ' 뒤') if when else '처음부터'}, 사람 턴 {len(rows)}개 · 받은 할 일 {len(inbox)}개)",
                 "README 「나중에 할 일」 표에 이미 있는 것은 빼고, 이미 한 일도 뺀다(지난 정리를 버렸으면 같은 범위를 다시 본다).", ""]
        if inbox:
            lines += ["# 받은 할 일 — 사람이 머리줄 [＋ 할 일]로 직접 적은 것. 모두 할 일이다(\"그때뿐\"으로 거르지 않는다)", ""]
            for x in inbox:
                lines += [f"## 받은 할 일 #{x['id']} {sc.kst(x['created_at'])}", mk.text(x["body"]) or "", ""]
            lines += ["# 대화에서 미룬 말", ""]
        for x in rows:
            lines += [f"## [t:{x['id']}] {sc.kst(x['started_at'])}", mk.text(sc._clip(x["prompt_text"], 1500)) or "", ""]
        mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / "later.md", "\n".join(lines))
        extra["materials"] = str(mat)
        prompt = task_prompt(task, project, repo, extra)
    else:
        if tp is not None:
            extra.update(slug=tp["slug"], title=tp["title"], about=tp["about"], screenshots="1" if tp["screenshots"] else "",
                         sources=", ".join(f"`{s}`" for s in tp["sources"]) or "(없음)",
                         siblings=", ".join(f"「{t['title']}」(`portfolio/{t['slug']}.md`)" for t in tps if t["written"] and t is not tp))
        if task == "readme":
            extra["since"] = commits_since_path(repo, "README.md")[1] or "?"
        if task == "doccheck":
            extra["stages"] = ", ".join(stages_without_result(repo)) or "(없음)"
        prompt = task_prompt(task, project, repo, extra)
    name = f"서기 — {TASKS[task]['title']}" + (f": {tp['title'].split(' — ')[0]}" if tp else "")
    res = await m.spawn_new(repo, None, name, role="scribe", worktree=True, first_prompt=prompt)
    if res.get("session_id"):
        await m._act(res["session_id"], TASK_ACT, res.get("pid"), True, f"{task} {tp['slug']}" if tp else task)
    if task == "later" and res.get("session_id"):
        # 어디까지 봤나 — 이 세션이 합쳐지면 다음 정리의 기준점이 된다(later_since)
        await m._act(res["session_id"], LATER_ACT, res.get("pid"), True, f"{now.isoformat()} 미룬 말 {len(rows)}개 받은 할 일 {len(inbox)}개")
        # 받은 할 일은 이 세션이 가져간다 — 합쳐지면 "옮김", 버려지면 다시 "새로"(상태는 계산, _INBOX_STATE)
        await _inbox_take(engine, [x["id"] for x in inbox], res["session_id"])
    return {"task": task, "project": project, "topic": tp["slug"] if tp else None, **{k: res.get(k) for k in ("tmux", "cc_session_id", "worktree", "note", "injected")}}
