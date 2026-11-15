"""서기실(12a, 11-06) — 서기에게 시킬 일 · 할 일 세기(LLM 없음) · 일 시키기(worktree 서기 세션).

시킬 일(사용자 11-06): 문서 점검 · CLAUDE.md 정리 · 알려진 한계 쓰기(11-15 전 「나중에 할 일 정리」) · Notion 게시. 회고 쓰기와 README 갱신은 11-15에 뺐다(docs/12_scribe.md 「0.」).
Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py)이고, 나머지는 서기 세션을 worktree로 띄운다 — 합치기가 사람의 검토 관문이다.
할 일(docs/12_scribe.md 「2. 언제 일하나」 2): 기계로 센다 — 서기 머리 위 "할 일 N", 누르면 목록. 자동으로 돌리지는 않는다.
다른 저장소(런슈즈 · 펫퍼민트)는 읽기만 하고, 일은 사람이 그 방 서기를 눌렀을 때만 띄운다(그 저장소의 CLAUDE.md를 따르게 한다).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

log = logging.getLogger("foreman.scribe_room")

KST = timedelta(hours=9)
CLAUDE_MD_MAX = 80           # CLAUDE.md 줄 수 상한(설계 「2.」 예시)
# 11-15 포스트잇 — 미룬 말은 브리지 그물(bridge/postit.py NET)이 포스트잇에 바로 올린다. 서기가 README 표로 옮기는 단계는 없다

TASKS = {
    "doccheck": {"title": "문서 점검", "desc": "코드와 문서(README · docs · CLAUDE.md)가 안 맞는 곳을 찾아 보고합니다. 고치지는 않습니다."},
    "trim": {"title": "CLAUDE.md 정리", "desc": "꼭 지킬 것만 짧게 남기고 상세는 docs로 옮겨 가리킵니다."},
    # 11-15 포스트잇 — 할 일은 포스트잇에 남고, 서기는 [→]로 보낸 것만 README 「알려진 한계」에 쓴다(키는 later 그대로)
    "later": {"title": "알려진 한계 쓰기", "desc": "포스트잇에서 [→]로 보낸 것을 README 「알려진 한계」에 쓰고, [갱신]에서 끝났다고 닫은 줄을 뺍니다."},
    # 메뉴에는 없다(화면 ORDER 밖) — 물어보기 답 · 문서 점검 결과의 [바로 고치기]에서만 뜬다(D2, 11-11)
    "docfix": {"title": "문서 고치기", "desc": "물어보기 답이나 문서 점검 결과에 적힌 어긋남을 고칩니다."},
    "portfolio": {"title": "포트폴리오 쓰기", "desc": "주제를 하나 골라 바깥 독자가 읽을 글을 portfolio/에 씁니다. 게시는 [게시] 버튼으로 합니다."},
    "publish": {"title": "Notion 게시", "desc": "포트폴리오와 기술문서를 Notion에 올립니다. 세션 없이 [게시] 버튼으로 합니다."},
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
    """[nudge] 기준 판단(11-09). 11-15 포스트잇 뒤로 서기 말풍선은 bridge/postit.py nudge_of(열린 포스트잇)가 정하고,
    이것은 README에 아직 안 쓴 [→] 줄(「알려진 한계 쓰기」 몫)에만 쓴다."""
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


UNREAD = "읽지 못했습니다"


def last_change(repo: str, path: str) -> tuple[str | None, int | None]:
    """그 경로를 마지막으로 바꾼 커밋의 시각(ISO)과 그 뒤 쌓인 커밋 수. 바꾼 적 없으면 (None, 0), git을 못 읽으면 (None, None)."""
    out = _git(repo, "log", "-1", "--format=%h %cI", "HEAD", "--", path)
    if not out:
        return None, (0 if _git(repo, "rev-parse", "HEAD") else None)
    sha, _, when = out.partition(" ")
    n = _git(repo, "rev-list", "--count", f"{sha}..HEAD")
    return when, (int(n) if n.isdigit() else None)


def doccheck_report(repo: str) -> str | None:
    """가장 최근 문서 점검 결과 파일(log/doccheck_*.md) 이름 — 합쳐진 것만 보인다."""
    d = Path(repo, "log")
    names = sorted(p.name for p in d.glob("doccheck_*.md")) if d.is_dir() else []
    return names[-1] if names else None


async def fixed_reports(engine: Any, project: str) -> set[str]:
    """[바로 고치기]로 시켜 합쳐진 문서 점검 결과 이름 — 같은 결과를 또 고치라고 하지 않게."""
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT sa.detail FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE p.name = :p AND sa.action = :a AND sa.ok AND sa.detail LIKE 'docfix %' AND EXISTS ("
            "  SELECT 1 FROM session_action m WHERE m.session_id = sa.session_id AND m.action = 'wt-merge' AND m.ok)"),
            {"p": project, "a": TASK_ACT})).all()
    return {r[0].split()[1] for r in rows if r[0] and len(r[0].split()) > 1}


async def todo(engine: Any, publishers: dict[str, Any] | None = None, docsync: Any = None) -> dict[str, dict[str, Any]]:
    """프로젝트마다 할 일 — [{kind(시킬 일), title, why}]. 기계로만 센다. publishers — 프로젝트 → Notion 게시기(11-09 프로젝트마다).
    D2(11-11): 한 목록으로 합치려고 일마다 밀린 수(behind) · 받은 할 일 수(inbox) · 포트폴리오 상태 · 게시 상태(port_pub · docs_pub)를 더한다.
    못 읽은 것은 0이 아니라 unread / error로 내려 화면이 「읽지 못했습니다」로 보인다."""
    from bridge import docsync as ds
    publishers = publishers or {}
    async with engine.connect() as c:
        projects = (await c.execute(text("SELECT name, repo_path FROM project"))).all()
    out: dict[str, dict[str, Any]] = {}
    for name, repo in projects:
        if not repo or not Path(repo, ".git").exists():
            continue
        items: list[dict[str, str]] = []
        git_ok = bool(_git(repo, "rev-parse", "HEAD"))
        behind: dict[str, dict[str, Any]] = {}
        stages = stages_without_result(repo)
        behind["doccheck"] = {"n": len(stages), "stale": bool(stages), "unit": "단계", "why": "결과 문서 없는 단계: " + ", ".join(stages[:5])}
        for d in stages[:5]:
            items.append({"kind": "doccheck", "title": f"결과 문서 없는 단계: {d}", "why": "설계 문서는 있는데 log/에 결과가 없습니다"})
        cm = Path(repo, "CLAUDE.md")
        if cm.is_file():
            lines = len(cm.read_text(encoding="utf-8", errors="replace").splitlines())
            behind["trim"] = {"n": max(0, lines - CLAUDE_MD_MAX), "stale": lines > CLAUDE_MD_MAX, "unit": "줄",
                              "why": f"CLAUDE.md {lines}줄(상한 {CLAUDE_MD_MAX}줄)"}
            if lines > CLAUDE_MD_MAX:
                items.append({"kind": "trim", "title": f"CLAUDE.md 정리: {lines}줄", "why": f"{CLAUDE_MD_MAX}줄을 넘었습니다"})
        # 11-15 포스트잇 — 열린 것은 할 일 목록 그 자체(서기 몫이 아니다). 서기 몫은 [→]로 보내 README에 아직 안 쓴 줄 ·
        # [갱신]에서 끝났다고 닫은 README 한계 줄뿐. 쌓이면 서기 말풍선(bridge/postit.py nudge_of — 21시 묶음에는 넣지 않는다)
        from bridge import postit as pi
        pst = await pi.summary(engine, name, await later_since(engine, name))
        nudge = pst["nudge"]
        lim, drop = pst["limit_pending"], pst["readme_drop"]
        behind["later"] = {"n": lim + drop, "stale": bool(lim or drop), "unit": "줄", "why": f"쓸 줄 {lim}, 뺄 줄 {drop}"}
        if lim or drop:
            items.append({"kind": "later", "title": f"알려진 한계 쓰기: 쓸 줄 {lim}, 뺄 줄 {drop}",
                          "why": "포스트잇 [→]로 보낸 것과 [갱신]에서 끝났다고 닫은 줄입니다. README에 쓰는 것은 서기 세션입니다"})
        if pst["check"] and pst["check"]["state"] == "failed":
            items.append({"kind": "postit", "title": f"포스트잇 [갱신] 실패: 조사 세션{pst['check']['session_id']}",
                          "why": pst["check"]["detail"] or "결과 없이 끝났습니다"})
        port_pub: dict[str, Any] | None = None
        docs_pub: dict[str, Any] | None = None
        pub_error: str | None = None
        if (pub := publishers.get(name)) is not None:
            # 11-09 런슈즈 요청 3-1 — 파일마다 한 줄이던 것을 묶음마다 한 줄로. 포트폴리오는 사람이 [게시](바깥 독자에게 내는 글)
            # D2: Notion이 꺼져 있어도 다른 할 일은 센다 — 다만 삼키지 않고 pub_error로 내려 화면이 「읽지 못했습니다」를 보인다
            try:
                if name == "foreman":
                    docs = await pub.list()
                    port_pub = {"total": len(docs), "published": sum(d["status"] == "published" for d in docs),
                                "new": sum(d["status"] == "new" for d in docs), "changed": sum(bool(d["changed"]) for d in docs)}
                    pend = [d for d in docs if d["status"] == "new" or d["changed"]]
                    if pend:
                        nn = sum(d["status"] == "new" for d in pend)
                        items.append({"kind": "publish", "title": f"Notion 포트폴리오: 파일 {len(pend)}개 뒤처짐"
                                      f"({' · '.join(x for x in (f'새 {nn}' if nn else '', f'바뀜 {len(pend) - nn}' if len(pend) - nn else '') if x)})",
                                      "why": ", ".join(Path(d["path"]).name for d in pend[:4]) + (" …" if len(pend) > 4 else "")
                                      + ". 아래 「포트폴리오 게시」에서 올립니다"})
                last_res = docsync.last.get(name) if docsync else None
                if pub.docs_mode != "off":
                    docs_pub = await ds.summary(pub, last_res)
                items += await ds.todo_items(pub, last_res)
            except Exception as e:  # noqa: BLE001
                pub_error = f"{type(e).__name__}: {str(e)[:120]}"
        opened = await open_tasks(engine, name)
        tps = []
        for t in topics(repo):
            when, since = last_change(repo, f"portfolio/{t['slug']}.md") if t["written"] else (None, None)
            tps.append({**{k: t[k] for k in ("slug", "title", "about", "written")}, "blocked": blocked("portfolio", opened, t["slug"]),
                        "last_at": when, "since": since})
        portfolio = None
        if tps:
            written = [t for t in tps if t["written"]]
            newest = max((t for t in written if t["last_at"]), key=lambda t: t["last_at"], default=None)
            portfolio = {"written": len(written), "total": len(tps),
                         "last_at": newest["last_at"] if newest else None, "since": newest["since"] if newest else None,
                         "unread": f"커밋 기록을 {UNREAD}" if written and (not git_ok or newest is None or newest["since"] is None) else None}
        report = doccheck_report(repo)
        out[name] = {"items": items, "open": opened, "topics": tps, "nudge": nudge,
                     "blocked": {k: b for k in TASKS if k not in ("publish", "portfolio") and (b := blocked(k, opened))},
                     "behind": behind, "inbox": None, "postit": _json_postit(pst),
                     "portfolio": portfolio, "port_pub": port_pub, "docs_pub": docs_pub, "pub_error": pub_error,
                     "report": {"name": report, "fixed": report in await fixed_reports(engine, name)} if report else None}
    return out


def _iso(v: Any) -> Any:
    return v.isoformat() + "Z" if isinstance(v, datetime) else v


def _json_postit(p: dict[str, Any]) -> dict[str, Any]:
    """포스트잇 요약을 화면으로 — 시각은 UTC ISO(Z)."""
    out = {k: _iso(v) for k, v in p.items() if k != "check"}
    out["check"] = {k: _iso(v) for k, v in p["check"].items()} if p.get("check") else None
    return out


LATER_ACT = "scribe-later"     # session_action — 나중에 할 일 정리를 띄울 때 "어디까지 봤나"(detail: until ISO)
TASK_ACT = "scribe-task"       # session_action — 서기 세션이 무슨 일인지(detail: 일 [토픽]). 합치거나 버리기 전까지 "열려 있다"
PLAN_TASK = "plan"             # 계획 [시작] · 직접 띄우기로 일 종류 없이 띄운 서기 세션(handoff.spawn_new가 남긴다)

# 동시에 시키기(11-06 판단, 11-15 상한을 뺐다) — 막는 것은 둘: 같은 일 · 같은 파일. 개수 상한은 두지 않는다(11-15 사용자).
# worktree는 서로를 못 봐서 충돌은 합칠 때 난다 — 같은 파일을 고치는 두 일이 열려 있으면 뒤의 합치기가 rebase 충돌.
# 파일 겹침은 계획 겹침과 같은 판단(foreman.files_overlap — 폴더는 끝에 /, 글롭 *)을 쓴다
TOUCHES = {"doccheck": ["log/doccheck_*"], "later": ["README.md"],
           "trim": ["CLAUDE.md", "docs/"], "docfix": ["README.md", "CLAUDE.md", "docs/"]}


async def open_tasks(engine: Any, project: str) -> list[dict[str, Any]]:
    """열려 있는 서기 일 — 역할 scribe로 띄웠고 아직 합치지도 버리지도 않은 것(세션이 끝났어도 합치기를 기다리면 열려 있다).
    띄운 길은 묻지 않는다(11-15 두 길 합치기): 서기실 [시키기] · 계획 [시작] · 직접 띄우기 모두 scribe-task(11-15 뒤) 또는
    dispatch_session(계획 · 직접, 11-15 전)이 있다. 맡을 파일은 dispatch_session의 files, 없으면 일 종류의 TOUCHES.
    「열려 있다」는 계획 겹침과 같은 판단(foreman.still_open — worktree 폴더가 없어지면 닫힘)."""
    from bridge.foreman import UNMERGED_SQL, norm_files, still_open
    async with engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT cs.id, COALESCE(cs.custom_title, cs.title), cs.worktree_path, cs.detached_at IS NOT NULL, "
            "  (SELECT sa.detail FROM session_action sa WHERE sa.session_id = cs.id AND sa.action = :a AND sa.ok ORDER BY sa.id DESC LIMIT 1), "
            "  (SELECT ds.files FROM dispatch_session ds WHERE ds.session_id = cs.id AND ds.status = 'started' ORDER BY ds.id DESC LIMIT 1) "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            f"WHERE p.name = :p AND cs.role = 'scribe' AND {UNMERGED_SQL} AND ("
            "  EXISTS (SELECT 1 FROM session_action sa WHERE sa.session_id = cs.id AND sa.action = :a AND sa.ok) "
            "  OR EXISTS (SELECT 1 FROM dispatch_session ds WHERE ds.session_id = cs.id AND ds.status = 'started')) "
            "ORDER BY cs.id"), {"p": project, "a": TASK_ACT})).all()
    out = []
    for sid, t, wpath, detached, d, files in rows:
        if not still_open(wpath, bool(detached)):
            continue
        w = (d or "").split() or [PLAN_TASK]
        task, topic = w[0], (w[1] if len(w) > 1 else None)
        fs = norm_files(json.loads(files) if isinstance(files, str) else files) if files else []
        out.append({"session_id": int(sid), "task": task, "topic": topic, "title": t, "files": fs or sorted(touches(task, topic))})
    return out


def touches(task: str, topic: str | None = None) -> list[str]:
    """그 일이 고치는 파일(files_overlap 꼴) — 포트폴리오는 주제마다 다르다(글 · 사진 모두 portfolio/<slug>로 시작)."""
    if task == "portfolio":
        return [f"portfolio/{topic}*"] if topic else ["portfolio/"]
    return list(TOUCHES.get(task, []))


def _what(o: dict[str, Any]) -> str:
    if o["task"] in TASKS:
        return TASKS[o["task"]]["title"] + (f": {o['topic']}" if o["task"] == "portfolio" and o.get("topic") else "")
    return o.get("title") or "서기 세션"


def blocked(task: str, opened: list[dict[str, Any]], topic: str | None = None) -> str | None:
    """이 일을 지금 시킬 수 없는 까닭(없으면 None) — 화면 버튼과 서버가 같은 판단을 쓴다.
    포트폴리오는 주제가 다르면 다른 일이다(서로 다른 파일) — 같은 주제만 막는다. 일 종류 없는 서기 세션(plan)은 맡을 파일로만 본다."""
    from bridge.foreman import files_overlap
    for o in opened:
        if o["task"] == task and task != PLAN_TASK and (task != "portfolio" or o.get("topic") == topic):
            return f"「{_what(o)}」이 이미 열려 있습니다(세션 {o['session_id']}). 합치거나 버린 뒤에 시켜 주세요"
    mine = touches(task, topic)
    for o in opened:
        common = files_overlap(mine, o.get("files") or touches(o["task"], o.get("topic")))
        if common:
            return (f"「{_what(o)}」(세션 {o['session_id']})와 같은 파일({', '.join(common)})을 "
                    "고칩니다. 합칠 때 충돌합니다. 그 일을 합치거나 버린 뒤에 시켜 주세요")
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


# ── 받는 함 = 포스트잇(11-09 migrations/0027 → 11-15 0033, bridge/postit.py) ───────────
# 사람이 적은 할 일은 포스트잇에 남는다(「받은 할 일」과 포스트잇은 같은 것 — 11-15 사용자). 서기가 README 표로 옮기지 않는다.
# 상태는 bridge/postit.py STATE(닫힌 까닭 칸 + 가져간 세션 계산). 아래 inbox_* 이름은 부르는 곳(start · foreman · coder_room)에 맞춰 남긴다
from bridge import postit as _pi  # noqa: E402

INBOX_MAX = _pi.MAX
INBOX_STALE_DAYS = 3
# 받는 사람(0028) — 11-15 [＋ 할 일]의 「코더에게」를 없앴다(사용자는 관리자에게만 말한다). 칸은 남긴다: 포스트잇 [띄우기]로
# 코더 세션이 가져가면 coder가 된다(inbox_take_pick). 옛 코더 몫 줄도 그대로 읽힌다
ASSIGNEES = ("scribe", "coder")
_INBOX_STATE = _pi.STATE
ASSIGNEE_KO = {"scribe": "포스트잇", "coder": "코더가 가져감"}


def inbox_label(state: str, assignee: str | None = None) -> str:
    """상태 이름(화면 글) — bridge/postit.py STATE_KO."""
    return _pi.STATE_KO.get(state, state)


async def inbox_add(engine: Any, project: str, body: str, assignee: str = "scribe", source: str = "todo") -> int:
    """[＋ 할 일](source todo)로 포스트잇 하나. 옛 API(/api/scribe/inbox)도 이 길이다."""
    from bridge.inject import Refused
    if assignee not in ASSIGNEES:
        raise Refused(f"받는 사람은 {', '.join(ASSIGNEES)} 중 하나입니다: {assignee}")
    return (await _pi.add(engine, project, body, source, assignee=assignee))["id"]


async def inbox_list(engine: Any, project: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """최근 것부터 — 닫힌 것도 보인다(물어보기 재료 · 옛 API)."""
    q = (f"SELECT i.id, i.project, i.body, i.assignee, i.source, i.confirmed, i.created_at, i.taken_by, i.dropped_at, i.closed_reason, "
         f"{_INBOX_STATE} AS state FROM todo_inbox i " + ("WHERE i.project = :p " if project else "") + "ORDER BY i.id DESC LIMIT :n")
    async with engine.connect() as c:
        rows = (await c.execute(text(q), {"p": project, "n": limit})).mappings().all()
    return [dict(r) for r in rows]


async def inbox_new(engine: Any, project: str, assignee: str = "scribe") -> list[dict[str, Any]]:
    """가져갈 것 — 오래된 것부터. 11-15 포스트잇 뒤로:
    - scribe: 서기 「알려진 한계 쓰기」(start의 later)가 가져갈 것 = [→]로 보내 README에 아직 안 쓴 줄
    - coder: 없다 — 코더 「맡길 일」은 포스트잇의 코더 추천 [띄우기]로 옮겼다"""
    if assignee != "scribe":
        return []
    return await _pi.limit_pending(engine, project)


async def inbox_take_coder(engine: Any, iid: int, session_id: int) -> bool:
    """코더에게 받은 할 일을 계획으로 띄운 세션이 가져간다(11-09) — 새로인 코더 몫만. 아니면 False(시작은 막지 않는다)."""
    async with engine.begin() as c:
        r = await c.execute(text(
            f"UPDATE todo_inbox i SET i.taken_by = :s, i.taken_at = UTC_TIMESTAMP(3) WHERE i.id = :i AND i.assignee = 'coder' "
            f"AND {_INBOX_STATE} = 'new'"), {"s": session_id, "i": iid})
        return r.rowcount > 0


async def inbox_take_pick(engine: Any, iid: int, session_id: int) -> bool:
    """목록에서 사람이 골라 「이거 해라」 한 할 일(11-11 받은 할 일 #8) — 받는 사람이 서기 정리였어도 코더 몫으로 바꿔 가져간다.
    새로인 것만. 아니면 False(시작은 막지 않는다)."""
    async with engine.begin() as c:
        r = await c.execute(text(
            f"UPDATE todo_inbox i SET i.assignee = 'coder', i.taken_by = :s, i.taken_at = UTC_TIMESTAMP(3) "
            f"WHERE i.id = :i AND {_INBOX_STATE} = 'new'"), {"s": session_id, "i": iid})
        return r.rowcount > 0


async def inbox_edit(engine: Any, iid: int, body: str) -> bool:
    """목록에서 바로 고치기(11-11 받은 할 일 #8) — 새로인 것만(가져간 것은 그 세션이 이미 읽었다). 고친 시각은 edited_at(0031)."""
    from bridge.inject import Refused
    body = (body or "").strip()
    if not body:
        raise Refused("고친 글이 비어 있습니다. 지우려면 [버리기]를 누릅니다")
    if len(body) > INBOX_MAX:
        raise Refused(f"글이 너무 깁니다({len(body)}자). {INBOX_MAX}자까지 받습니다")
    async with engine.begin() as c:
        try:
            r = await c.execute(text(f"UPDATE todo_inbox i SET i.body = :b, i.edited_at = UTC_TIMESTAMP(3) "
                                     f"WHERE i.id = :i AND {_INBOX_STATE} = 'new'"), {"b": body, "i": iid})
        except Exception:  # noqa: BLE001 — 0031 전 DB(edited_at 없음). 글만 고친다
            r = await c.execute(text(f"UPDATE todo_inbox i SET i.body = :b WHERE i.id = :i AND {_INBOX_STATE} = 'new'"),
                                {"b": body, "i": iid})
        return r.rowcount > 0


async def inbox_drop(engine: Any, iid: int) -> bool:
    """[x] — 안 하기로 함(11-15 포스트잇: closed_reason drop. 옛 칸 dropped_at도 함께 — 0032 코드가 읽어도 버림)."""
    ok = await _pi.close(engine, iid, "drop")
    if ok:
        async with engine.begin() as c:
            await c.execute(text("UPDATE todo_inbox SET dropped_at = closed_at WHERE id = :i AND dropped_at IS NULL"), {"i": iid})
    return ok


async def _inbox_take(engine: Any, ids: list[int], session_id: int) -> None:
    if not ids:
        return
    from sqlalchemy import bindparam
    async with engine.begin() as c:
        await c.execute(text("UPDATE todo_inbox SET taken_by = :s, taken_at = UTC_TIMESTAMP(3) WHERE id IN :ids")
                        .bindparams(bindparam("ids", expanding=True)), {"s": session_id, "ids": ids})


async def later_prompts(engine: Any, project: str, since: datetime | None, limit: int = 300) -> list[dict[str, Any]]:
    """「알려진 한계 쓰기」(start의 later)가 README에서 뺄 줄 — [갱신]에서 사람이 「끝남」으로 닫은 README 「알려진 한계」 줄.
    11-15 포스트잇 전에는 「나중에 · 미루」 사람 턴이었다. 미룬 말은 이제 브리지 그물이 포스트잇에 바로 올리고(bridge/postit.py sweep)
    서기 재료로 주지 않는다. 이름은 부르는 곳(start)에 맞춰 남긴다. 모양: {id, started_at, prompt_text, item, evidence}"""
    rows = await _pi.readme_drop_pending(engine, project, since)
    return [{"id": r["id"], "started_at": r["resolved_at"], "prompt_text": r["item_text"] or "", "item": r["item"],
             "evidence": r["evidence"], "reason": r["reason"]} for r in rows][:limit]


def later_material(project: str, when: datetime | None, rows: list[dict[str, Any]], inbox: list[dict[str, Any]], mk: Any = None) -> str:
    """「알려진 한계 쓰기」 재료(later.md) — 쓸 줄(포스트잇 [→]) · 뺄 줄([갱신]에서 닫음). 사람 말은 자르지 않는다(#14, 11-10)."""
    from bridge import scribe as sc
    m = mk.text if mk else (lambda s: s)
    lines = [f"# README 「{_pi.README_LIMIT}」 — {project} ({(sc.kst(when) + ' 뒤') if when else '처음부터'}, 쓸 줄 {len(inbox)}개 · 뺄 줄 {len(rows)}개)",
             "사람 말은 자르지 않은 원문이다 — 길면 쪽으로 나눠 끝까지 읽는다.", ""]
    if inbox:
        lines += [f"# 쓸 줄 — 사람이 포스트잇에서 [→]로 보낸 것(못 풀 것, README를 읽는 남에게 「지금은 ~이다」로 알릴 것)", ""]
        for x in inbox:
            lines += [f"## 포스트잇 #{x['id']} {sc.kst(x['created_at'])}", m(x["body"]) or "", ""]
    if rows:
        lines += [f"# 뺄 줄 — [갱신] 조사 세션이 「끝남」으로 보고 사람이 닫은 README 「{_pi.README_LIMIT}」 줄", ""]
        for x in rows:
            lines += [f"## {x.get('item') or ''} (판정 #{x['id']} {sc.kst(x['started_at'])})", m(x["prompt_text"]) or "",
                      f"근거: {x.get('evidence') or '(없음)'}" + (f" — {x['reason']}" if x.get("reason") else ""), ""]
    return "\n".join(lines)


COMMON = """
지켜야 할 것
- 먼저 이 저장소의 CLAUDE.md와 `docs/style_guide.md`(있으면)를 읽는다
- 너는 따로 작업(worktree) 세션이다: 이 브랜치에 커밋하고 push하지 않는다. 브리지를 다시 띄우지 않는다
- 끝나면 바꾼 파일만 `git add`해 커밋하고, 마지막 응답에 바꾼 파일 · 무엇을 · 확인 못 한 것을 짧게 알린다. 사람이 [합치기] 전에 diff를 본다
- `pgrep -f` · `pkill -f`를 쓰지 않는다 — CC는 Bash 명령 전체를 `bash -c`로 돌려 패턴이 자기 셸에 걸린다(브리지가 거부한다). 기다릴 때는 그 작업의 PID나 결과 파일을 본다"""


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
    elif task == "docfix":
        src = (f"- 고칠 목록: `{e['report']}`(문서 점검 결과 — 먼저 끝까지 읽는다). 항목마다 지금 저장소와 다시 맞는지 확인한 뒤 고친다"
               if e.get("report") else f"- 고칠 것(사람이 서기에게 물어 얻은 답 — 그대로 믿지 말고 지금 저장소와 맞는지 확인한 뒤 고친다):\n{e.get('note') or '(없음)'}")
        body = f"""할 일: 코드와 안 맞는 문서를 고친다. 찾기는 이미 끝났다 — 고치는 일이다.
{src}
- 고칠 곳: README.md · docs/ · CLAUDE.md 중 목록이 가리키는 문서만. 코드는 건드리지 않는다(코드가 틀렸다고 보이면 고치지 말고 마지막 응답에 알린다)
- 문서에 적힌 것이 맞고 저장소가 틀린 것으로 보이는 항목, 확인할 수 없는 항목은 고치지 않고 마지막 응답에 따로 적는다
- 항목마다 무엇을 어떻게 고쳤는지 근거(파일:줄 · 커밋)와 함께 마지막 응답에 알린다"""
    elif task == "trim":
        body = f"""할 일: CLAUDE.md를 정리한다(docs/12_scribe.md 「trim」).
- 꼭 지킬 금지 · 결정만 짧게 남기고, 상세는 docs/로 옮겨 가리킨다. 규칙을 없애지 않는다 — 옮길 뿐이다
- 옮긴 규칙마다 목적지를 표로: `log/trim_{today}.md`
- 사용자 원문 인용 · 날짜 표시는 그대로 둔다"""
    elif task == "later":
        body = f"""할 일: README 「{_pi.README_LIMIT}」 절을 맞춘다. 할 일은 README가 아니라 포스트잇에 있다(11-15) — 여기에는 못 풀 것만 쓴다.
- 재료(저장소 밖, 사람 말 원문): `{e.get('materials') or '(없음)'}` — 쓸 줄(포스트잇에서 사람이 [→]로 보낸 것) · 뺄 줄([갱신]에서 끝났다고 닫은 것)
- 쓸 줄: 할 일 말투(「할 것: …」)를 README를 읽는 남에게 알리는 말투(「지금은 ~이다. ~하면 다시 연다」)로 다시 쓴다. 근거 칸에 `포스트잇 #번호`. 같은 한계가 이미 있으면 그 줄에 보탠다
- 뺄 줄: 그 줄을 지운다. 재료의 근거(코드 자리)가 지금 저장소와 맞는지 한 번 본 뒤 지운다. 안 맞으면 지우지 말고 마지막 응답에 적는다
- 절이 없으면 README 「6. 로드맵」 아래에 `### {_pi.README_LIMIT}`을 만든다
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


NOTE_MAX = 4000
REPORT_RE = re.compile(r"doccheck_[0-9A-Za-z_]{1,40}\.md")


async def _record(engine: Any, project: str, name: str, task: str, topic: str | None, res: dict[str, Any]) -> None:
    """서기실 [시키기]도 계획 · 직접 띄우기와 같은 dispatch 기록(origin scribe, 맡을 파일 = 그 일의 TOUCHES)을 남긴다(11-15).
    그래야 계획 겹침(file_conflicts)이 서기실 세션을 안다. 실패해도 띄우기는 되돌리지 않는다(open_tasks는 scribe-task로도 센다)."""
    from bridge.foreman import record_spawn
    try:
        await record_spawn(engine, "scribe", project, {"role": "scribe", "title": name, "files": touches(task, topic), "worktree": True},
                           res, None, f"(서기실) {name}")
    except Exception as e:  # noqa: BLE001 — 0030 전 DB 등
        log.warning("서기실 띄우기 기록(dispatch) 실패: %s", type(e).__name__)


async def start(m: Any, engine: Any, project: str, task: str, topic: str | None = None, note: str | None = None) -> dict[str, Any]:
    """서기 일을 worktree 세션으로 띄운다(handoff.spawn_new). 포트폴리오는 주제(topic)가 있어야 한다.
    문서 고치기(docfix, D2)는 고칠 목록이 있어야 한다 — topic에 문서 점검 결과 이름(log/doccheck_*.md) 또는 note에 물어보기 답."""
    from bridge import scribe as sc
    from bridge.inject import Refused
    if task not in TASKS or task == "publish":
        raise Refused("세션으로 시키는 일이 아닙니다")
    fix_src: str | None = None
    if task == "docfix":
        note = (note or "").strip()[:NOTE_MAX]
        if topic:
            if not REPORT_RE.fullmatch(topic):
                raise Refused(f"문서 점검 결과 이름이 아닙니다: {topic}")
            fix_src = topic
        elif note:
            fix_src = "ask"
        else:
            raise Refused("고칠 목록이 없습니다. 문서 점검 결과나 물어보기 답이 있어야 합니다")
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
            raise Refused(f"포트폴리오 주제를 찾지 못했습니다({topic or '없음'}). {TOPICS_FILE}에 있는 주제만 시킬 수 있습니다")
    why = blocked(task, await open_tasks(engine, project), topic if task == "portfolio" else None)
    if why:
        raise Refused(why)
    if task == "docfix" and topic and not Path(repo, "log", topic).is_file():
        raise Refused(f"log/{topic}가 main에 없습니다. 문서 점검 결과를 합친 뒤에 고칠 수 있습니다")
    now = datetime.now(UTC).replace(tzinfo=None)
    day = (now + KST).strftime("%Y%m%d")
    extra: dict[str, str] = {}
    if task == "later":
        when = await later_since(engine, project)
        rows = await later_prompts(engine, project, when)
        inbox = await inbox_new(engine, project)
        if not rows and not inbox:         # 빈손으로 Opus 세션을 띄우지 않는다(11-06 — 범위가 비어 사람 턴 0개로 떴다)
            raise Refused(f"{'지난 정리 뒤로' if when else '지금까지'} \"나중에 · 미루\"라고 한 사람 말도, 받은 할 일도 없습니다. 띄우지 않았습니다")
        from bridge.mask import Masker
        mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / "later.md", later_material(project, when, rows, inbox, Masker()))
        extra["materials"] = str(mat)
        prompt = task_prompt(task, project, repo, extra)
    else:
        if tp is not None:
            extra.update(slug=tp["slug"], title=tp["title"], about=tp["about"], screenshots="1" if tp["screenshots"] else "",
                         sources=", ".join(f"`{s}`" for s in tp["sources"]) or "(없음)",
                         siblings=", ".join(f"「{t['title']}」(`portfolio/{t['slug']}.md`)" for t in tps if t["written"] and t is not tp))
        if task == "docfix":
            extra.update(report=f"log/{topic}" if topic else "", note=note or "")
        if task == "doccheck":
            extra["stages"] = ", ".join(stages_without_result(repo)) or "(없음)"
        prompt = task_prompt(task, project, repo, extra)
    name = f"서기 — {TASKS[task]['title']}" + (f": {tp['title'].split(' — ')[0]}" if tp else "")
    # 일 종류(scribe-task)는 spawn_new가 남긴다(11-15 — 세 길이 같은 기록). 맡을 파일은 계획 길과 같은 dispatch_session으로
    detail = f"{task} {tp['slug']}" if tp else f"docfix {fix_src}" if fix_src else task
    res = await m.spawn_new(repo, None, name, role="scribe", worktree=True, first_prompt=prompt, scribe_task=detail)
    await _record(engine, project, name, task, tp["slug"] if tp else None, res)
    if task == "later" and res.get("session_id"):
        # 어디까지 봤나 — 이 세션이 합쳐지면 다음 정리의 기준점이 된다(later_since)
        await m._act(res["session_id"], LATER_ACT, res.get("pid"), True, f"{now.isoformat()} 미룬 말 {len(rows)}개 받은 할 일 {len(inbox)}개")
        # 받은 할 일은 이 세션이 가져간다 — 합쳐지면 "옮김", 버려지면 다시 "새로"(상태는 계산, _INBOX_STATE)
        await _inbox_take(engine, [x["id"] for x in inbox], res["session_id"])
    return {"task": task, "project": project, "topic": tp["slug"] if tp else None, **{k: res.get(k) for k in ("tmux", "cc_session_id", "worktree", "note", "injected")}}
