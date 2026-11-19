"""서기실(12a, 11-06) — 서기에게 시킬 일 · 할 일 세기(LLM 없음) · 일 시키기(worktree 서기 세션).

시킬 일은 아래 TASKS 한 곳이다(11-17 기준 문서 점검, 문서 고치기, CLAUDE.md 정리, 알려진 한계 쓰기, 포트폴리오 쓰기, 기술문서 쓰기,
Notion 게시). 회고 쓰기와 README 갱신은 11-15에 뺐다(docs/12_scribe.md 「0.」).
Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py)이고, 나머지는 서기 세션을 worktree로 띄운다. 합치기가 사람의 검토 관문이다.
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
    # 11-17 문서 정리 E — 포스트잇 [한계로]로 보낸 줄을 고른 편의 「알려진 한계」 절에 까닭과 함께 쓴다(키는 later 그대로).
    # TODO 항목에서 보낸 것은 같은 커밋에서 docs/TODO.md 항목을 지운다. 11-19 README 한계 줄 빼기는 없앴다(README가 생성물)
    "later": {"title": "알려진 한계 쓰기", "desc": "포스트잇에서 [한계로] 보낸 것을 고른 편의 「알려진 한계」에 까닭과 함께 씁니다."},
    # 메뉴에는 없다(화면 ORDER 밖) — 물어보기 답 · 문서 점검 결과의 [바로 고치기]에서만 뜬다(D2, 11-11)
    "docfix": {"title": "문서 고치기", "desc": "물어보기 답이나 문서 점검 결과에 적힌 어긋남을 고칩니다."},
    # 11-15 화면 축 — 정해진 주제 목록(config/portfolio.toml)을 없앴다. 편 목록은 portfolio/ 폴더 파일과 머리 주석이 정한다
    "portfolio": {"title": "포트폴리오 쓰기", "desc": "보여줄 화면이 있으면 화면마다, 없으면 결정마다 편 목록을 정해 비개발자도 읽을 글을 portfolio/에 씁니다. 게시는 [게시] 버튼으로 합니다."},
    # 11-15 노션 기술문서 — 서기 세션 하나가 목차를 정하고 편마다 서브에이전트가 notion/ 원고를 쓴다. 메뉴에는 원고 폴더가 notion/인
    # 프로젝트만 보인다(todo의 techdoc). 게시는 사람이 [Notion에 올리기]
    "techdoc": {"title": "기술문서 쓰기", "desc": "코드를 읽고 notion/ 원고를 통으로 씁니다. 목차는 서기가 정하고 편마다 서브에이전트가 씁니다. 게시는 [Notion에 올리기]로 합니다."},
    "publish": {"title": "Notion 게시", "desc": "포트폴리오와 기술문서를 Notion에 올립니다. 세션 없이 [게시] 버튼으로 합니다."},
}
PORTFOLIO_DIR = "portfolio/"   # 이 폴더가 있는 저장소만 「포트폴리오 쓰기」를 보인다(11-15 전에는 config/portfolio.toml)
TECHDOC_DIR = "notion/"        # 기술문서 원고 폴더(게시기 src가 이것인 프로젝트만 「기술문서 쓰기」)
TECHDOC_DAYS = 2               # 마지막으로 기술문서 서기 세션을 합친 뒤 이만큼 지나고, 다루는 코드가 바뀐 편이 있으면 할 일에 올린다(11-15 사용자)


# 서기 말풍선 기준은 bridge/postit.py conf, nudge_of(config/scribe.toml [postit]) 한 곳이다. 11-09 받는 함 때의 [nudge] 기준
# (nudge_conf, nudge_of)은 11-15 포스트잇 뒤로 부르는 곳이 시험뿐이라 11-17에 뺐다(설정을 바꿔도 아무 일이 없었다)


SLUG = re.compile(r"[0-9a-z_]{1,40}")
TOPIC_MAX = 120     # 편 이름(원고 폴더 아래 경로에서 .md를 뗀 것) 최대 길이. API topic 칸 한도도 이 값(bridge/api/scribe.py)

# 편이 있는 일(11-19 foreman-125). 포트폴리오 쓰기와 기술문서 쓰기가 같은 길을 지난다: 편 목록(topics), 맡을 파일(touches),
# 일 제목(_what), 막기(blocked), 띄우기의 편 찾기(start), 기록(_record). 일마다 다른 것은 이 표에만 둔다(판정을 두 벌로 두지 않는다).
# - dir: 원고 폴더. 편 이름(topic, slug)은 그 아래 경로에서 .md를 뗀 것
# - nested: 하위 폴더 편을 받나. 기술문서는 받는다(notion/10_scribe/03_evidence.md → 10_scribe/03_evidence). 포트폴리오는
#   portfolio/img/ 아래가 편이 아니라 받지 않는다
# - own: 편 하나가 맡을 파일. 포트폴리오는 portfolio/<slug>로 시작하는 것(11-15부터 그대로), 기술문서는 그 편 파일 하나
#   (notion/<slug>*로 두면 같은 이름 폴더 아래 하위 편까지 맡아 다른 편과 막힌다)
PIECE_TASKS: dict[str, dict[str, Any]] = {
    "portfolio": {"dir": PORTFOLIO_DIR, "nested": False, "own": "{dir}{slug}*", "label": "포트폴리오 편"},
    "techdoc": {"dir": TECHDOC_DIR, "nested": True, "own": "{dir}{slug}.md", "label": "기술문서 편"},
}


def topic_ok(task: str, topic: str) -> bool:
    """편 이름 꼴: 칸마다 소문자, 숫자, 밑줄(1~40자). 하위 폴더는 nested인 일만. 「..」, 앞뒤 /, 빈 칸은 꼴에서 걸러진다."""
    spec = PIECE_TASKS[task]
    parts = topic.split("/")
    return (len(topic) <= TOPIC_MAX and (spec["nested"] or len(parts) == 1)
            and all(SLUG.fullmatch(p) for p in parts))


def _topics_of(task: str, pcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    d = PIECE_TASKS[task]["dir"]
    out = []
    for p in pcs:
        slug = p["path"][len(d):-3]
        if not p["path"].startswith(d) or not topic_ok(task, slug):
            continue                                   # portfolio/img/ 아래, 이름이 틀린 파일은 편이 아니다
        out.append({"slug": slug, "title": p["title"], "read": p["read"], "covers": p["covers"],
                    "commits": p["commits"], "why": p["why"], "written": True})
    return out


def topics(repo: str, task: str = "portfolio") -> list[dict[str, Any]]:
    """편이 있는 일의 편: main(HEAD)의 원고 폴더 아래 .md, 파일 번호 차례(11-15: 정해진 주제 목록 없음).
    편마다 머리 주석(bridge/manuscript.py)의 읽은 커밋 뒤 다루는 코드를 바꾼 feat, fix 커밋 수(commits, 셀 수 없으면 None과 why)."""
    from bridge import manuscript as ms
    return _topics_of(task, ms.pieces(repo, PIECE_TASKS[task]["dir"], "HEAD"))


def topic_rows(task: str, tps: list[dict[str, Any]], opened: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """화면에 내릴 편 목록. 편마다 막힌 까닭(blocked)을 붙인다. 포트폴리오와 기술문서가 같은 꼴(scribe.js pieceButtons)."""
    return [{**{k: t[k] for k in ("slug", "title", "written", "commits", "why", "read")}, "blocked": blocked(task, opened, t["slug"])}
            for t in tps]


def has_portfolio(repo: str) -> bool:
    return Path(repo, PORTFOLIO_DIR).is_dir()


async def last_techdoc_merge(engine: Any, project: str, repo: str) -> tuple[datetime | None, str]:
    """마지막으로 기술문서 서기 세션(scribe-task techdoc)을 합친 시각(UTC)과 출처. 그런 기록이 없으면 notion/을 마지막으로 바꾼
    커밋 시각(계획 · 직접 띄우기로 일 종류 없이 쓴 원고도 있을 수 있다) — 둘 다 없으면 (None, "")."""
    async with engine.connect() as c:
        r = (await c.execute(text(
            "SELECT MAX(m.created_at) FROM session_action m JOIN character_session cs ON cs.id = m.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
            "WHERE p.name = :p AND m.action = 'wt-merge' AND m.ok AND EXISTS (SELECT 1 FROM session_action sa "
            "  WHERE sa.session_id = m.session_id AND sa.action = :a AND sa.ok AND sa.detail LIKE 'techdoc%')"),
            {"p": project, "a": TASK_ACT})).scalar()
    if r:
        return r, "merge"
    ts = _git(repo, "log", "-1", "--format=%ct", "HEAD", "--", TECHDOC_DIR)
    if ts.isdigit():
        return datetime.fromtimestamp(int(ts), UTC).replace(tzinfo=None), "commit"
    return None, ""


def techdoc_state(pieces: list[dict[str, Any]], last_at: datetime | None, now: datetime) -> dict[str, Any]:
    """기술문서 쓰기를 할 일에 올릴까(11-15 사용자) — 마지막으로 합친 뒤 TECHDOC_DAYS일이 지났고, 다루는 코드가 바뀐 편이 있을 때.
    이틀이 지났어도 코드가 그대로면 올리지 않는다. 머리 주석을 읽지 못한 편(셀 수 없음)은 바뀐 것으로 센다 — 조용히 「그대로」가 되지 않게.
    원고가 하나도 없으면 올리지 않는다(첫 목차는 사람이 정한다)."""
    from bridge.manuscript import tally
    t = tally(pieces)
    need = t["changed"] + t["unknown"]
    days = (now - last_at).days if last_at else None
    due = bool(pieces) and need > 0 and (days is None or days >= TECHDOC_DAYS)
    if not pieces:
        why = "아직 쓴 원고가 없습니다"
    else:
        why = f"글 {t['total']}편 가운데 코드가 바뀐 편 {t['changed']}" + (f", 머리 주석을 읽지 못한 편 {t['unknown']}" if t["unknown"] else "")
        if days is not None:
            why += f". 마지막으로 합친 지 {days}일" + ("" if days >= TECHDOC_DAYS else "(이틀이 지나야 할 일에 올립니다)")
    return {**t, "need": need, "days": days, "due": due, "why": why}


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
        # 11-15 포스트잇 — 열린 것은 할 일 목록 그 자체(서기 몫이 아니다). 서기 몫은 [한계로] 보내 아직 안 쓴 줄 ·
        # 11-19 전에는 [갱신]에서 끝났다고 닫은 README 한계 줄도 셌다(README가 생성물이라 뺐다). 쌓이면 서기 말풍선(bridge/postit.py nudge_of — 21시 묶음에는 넣지 않는다)
        from bridge import postit as pi
        pst = await pi.summary(engine, name)
        nudge = pst["nudge"]
        lim = pst["limit_pending"]
        behind["later"] = {"n": lim, "stale": bool(lim), "unit": "줄", "why": f"쓸 줄 {lim}"}
        if lim:
            items.append({"kind": "later", "title": f"알려진 한계 쓰기: 쓸 줄 {lim}",
                          "why": "포스트잇 [한계로] 보낸 것입니다. 쓰는 것은 서기 세션입니다"})
        if pst["check"] and pst["check"]["state"] == "failed":
            items.append({"kind": "postit", "title": f"포스트잇 [갱신] 실패: 조사 세션 {pst['check']['session_id']}",
                          "why": pst["check"]["detail"] or "결과 없이 끝났습니다"})
        port_pub: dict[str, Any] | None = None
        docs_pub: dict[str, Any] | None = None
        pub_error: str | None = None
        if (pub := publishers.get(name)) is not None:
            # 11-09 런슈즈 요청 3-1 — 파일마다 한 줄이던 것을 묶음마다 한 줄로. 포트폴리오는 사람이 [게시](바깥 독자에게 내는 글)
            # D2: Notion이 꺼져 있어도 다른 할 일은 센다 — 다만 삼키지 않고 pub_error로 내려 화면이 「읽지 못했습니다」를 보인다
            # 11-17 포트폴리오도 프로젝트마다(전에는 FOREMAN만). 따로 잡아 포트폴리오를 못 읽어도 기술문서 줄은 남는다
            try:
                docs = await pub.list()
                port_pub = {"total": len(docs), "published": sum(d["status"] == "published" for d in docs),
                            "new": sum(d["status"] == "new" for d in docs), "changed": sum(bool(d["changed"]) for d in docs)}
                pend = [d for d in docs if d["status"] == "new" or d["changed"]]
                if pend:
                    nn = sum(d["status"] == "new" for d in pend)
                    place = "" if getattr(pub, "portfolio_page", None) else " Notion 자리가 정해지지 않아 아직 올릴 수 없습니다."
                    items.append({"kind": "publish", "title": f"Notion 포트폴리오: 파일 {len(pend)}개 뒤처짐"
                                  f"({' · '.join(x for x in (f'새 {nn}' if nn else '', f'바뀜 {len(pend) - nn}' if len(pend) - nn else '') if x)})",
                                  "why": ", ".join(Path(d["path"]).name for d in pend[:4]) + (" …" if len(pend) > 4 else "")
                                  + ". 아래 「포트폴리오 게시」에서 올립니다." + place})
            except Exception as e:  # noqa: BLE001
                port_pub = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            try:
                # 11-19 메모리가 비었으면(브리지를 다시 띄운 뒤) DB의 멈춘 편 행에서 덮기 줄을 되살린다
                last_res, held_error = await docsync.last_for(name) if docsync else (None, None)
                if pub.docs_mode != "off":
                    docs_pub = await ds.summary(pub, last_res)
                got = await ds.todo_items(pub, last_res)
                items += got
                if docs_pub is not None:
                    # 화면이 「멈춤 N」인데 덮기 단추가 없으면 그 까닭을 쓰게(조용히 비지 않게): 지금 덮을 수 있는 편 수, 못 읽은 까닭
                    docs_pub["held_buttons"] = sum(1 for x in got if x.get("act") == "force")
                    docs_pub["held_error"] = held_error
                    docs_pub["held_list_missing"] = ds.held_list_missing(docs_pub, last_res, held_error)
            except Exception as e:  # noqa: BLE001
                pub_error = f"{type(e).__name__}: {str(e)[:120]}"
        opened = await open_tasks(engine, name)
        # 포트폴리오(11-15 화면 축) — 편 목록은 portfolio/ 파일. 「그 뒤 커밋」은 편마다 읽은 커밋 뒤 다루는 코드를 바꾼 feat · fix 커밋.
        # 머리줄은 「글 N편 가운데 코드가 바뀐 편 M」(저장소 전체 커밋을 세던 것을 고쳤다)
        tps, portfolio = [], None
        if has_portfolio(repo):
            tps = topic_rows("portfolio", topics(repo, "portfolio"), opened)
            from bridge.manuscript import tally
            portfolio = {**tally(tps), "written": len(tps), "blocked": blocked("portfolio", opened),
                         "unread": f"커밋 기록을 {UNREAD}" if tps and not git_ok else None}
        techdoc = None
        if pub is not None and getattr(pub, "src", "docs/") == TECHDOC_DIR:
            # 11-15 기술문서 쓰기 — 원고 폴더가 notion/인 프로젝트만. 이틀 + 코드가 바뀐 편이 있으면 할 일에 올린다
            from bridge import manuscript as ms
            pcs = ms.pieces(repo, TECHDOC_DIR, "HEAD")
            last_at, last_src = await last_techdoc_merge(engine, name, repo)
            techdoc = {**techdoc_state(pcs, last_at, datetime.now(UTC).replace(tzinfo=None)),
                       "last_at": _iso(last_at), "last_from": last_src,
                       "pieces": [{k: p[k] for k in ("path", "title", "commits", "why")} for p in pcs],
                       # 11-19 foreman-125 편 하나 고쳐 쓰기([갱신], 편 목록 단추). 포트폴리오의 topics와 같은 꼴
                       "topics": topic_rows("techdoc", _topics_of("techdoc", pcs), opened)}
            behind["techdoc"] = {"n": techdoc["need"], "stale": techdoc["due"], "unit": "편", "why": techdoc["why"]}
            if techdoc["due"]:
                items.append({"kind": "techdoc", "title": f"기술문서 쓰기: 코드가 바뀐 편 {techdoc['need']}", "why": techdoc["why"]})
        report = doccheck_report(repo)
        out[name] = {"items": items, "open": opened, "topics": tps, "nudge": nudge,
                     "blocked": {k: b for k in TASKS if k not in ("publish", "portfolio") and (b := blocked(k, opened))},
                     "behind": behind, "inbox": None, "postit": _json_postit(pst), "techdoc": techdoc,
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
# later(알려진 한계 쓰기)는 여기에 docs/TODO.md만 두고(11-19 전에는 README.md도), 띄울 때 [한계로]에서 고른 편 파일을 더한다(start, blocked의 extra).
# 원고 폴더 통째로 적으면 열린 포트폴리오, 기술문서 일과 늘 겹쳐 막힌다.
# 편이 있는 일(포트폴리오, 기술문서)의 맡을 파일은 여기가 아니라 PIECE_TASKS(편 없이 시키면 원고 폴더 통째로)
TOUCHES = {"doccheck": ["log/doccheck_*"], "later": ["docs/TODO.md"],
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
    """그 일이 고치는 파일(files_overlap 꼴). 편이 있는 일(PIECE_TASKS)은 편 하나면 그 편 파일만(own), 편 없이 시키면 원고 폴더 통째로."""
    if (spec := PIECE_TASKS.get(task)) is not None:
        return [spec["own"].format(dir=spec["dir"], slug=topic)] if topic else [spec["dir"]]
    return list(TOUCHES.get(task, []))


def _what(o: dict[str, Any]) -> str:
    if o["task"] in TASKS:
        return TASKS[o["task"]]["title"] + (f": {o['topic']}" if o["task"] in PIECE_TASKS and o.get("topic") else "")
    return o.get("title") or "서기 세션"


def blocked(task: str, opened: list[dict[str, Any]], topic: str | None = None, extra: list[str] | None = None) -> str | None:
    """이 일을 지금 시킬 수 없는 까닭(없으면 None) — 화면 버튼과 서버가 같은 판단을 쓴다.
    편이 있는 일(포트폴리오, 기술문서)은 편이 다르면 다른 일이다(서로 다른 파일). 같은 편만 막는다. 편 없이 시킨 것(폴더 통째로)은
    파일 겹침으로 모든 편과 막힌다. 일 종류 없는 서기 세션(plan)은 맡을 파일로만 본다. extra는 띄울 때 정해지는 파일(later의 고른 편)."""
    from bridge.foreman import files_overlap
    for o in opened:
        if o["task"] == task and task != PLAN_TASK and (task not in PIECE_TASKS or o.get("topic") == topic):
            return f"「{_what(o)}」이 이미 열려 있습니다(세션 {o['session_id']}). 합치거나 버린 뒤에 시켜 주세요"
    mine = touches(task, topic) + list(extra or [])
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
    - scribe: 서기 「알려진 한계 쓰기」(start의 later)가 가져갈 것 = [한계로] 보내 아직 안 쓴 줄
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


def later_material(project: str, when: datetime | None, inbox: list[dict[str, Any]], mk: Any = None) -> str:
    """「알려진 한계 쓰기」 재료(later.md). 쓸 줄(포스트잇 [한계로]: 편, 까닭, TODO 번호)만 든다(11-19 전에는 [갱신]에서 닫은
    README 줄을 뺄 줄로 더했다). 사람 말은 자르지 않는다(#14, 11-10)."""
    from bridge import scribe as sc
    m = mk.text if mk else (lambda s: s)
    lines = [f"# 「{_pi.LIMIT_TITLE}」 — {project} ({(sc.kst(when) + ' 뒤') if when else '처음부터'}, 쓸 줄 {len(inbox)}개)",
             "사람 말은 자르지 않은 원문이다 — 길면 쪽으로 나눠 끝까지 읽는다.", ""]
    if inbox:
        lines += ["# 쓸 줄 — 사람이 포스트잇에서 [한계로] 보낸 것(안 하기로 한 것과 그 까닭)", ""]
        for x in inbox:
            src = f"TODO 항목 {x['todo']}" if x.get("todo") else f"포스트잇 #{x['id']}"
            lines += [f"## {src} {sc.kst(x['created_at'])}",
                      f"- 편: `{x['piece']}`" if x.get("piece") else "- 편: (없음. 11-17 전 [→]로 보낸 옛 줄이다. 쓰지 말고 마지막 응답에 적는다)",
                      f"- 안 하는 까닭(사람이 적음): {m(x['reason'])}" if x.get("reason") else "- 안 하는 까닭: (없음)",
                      "- 글:", m(x["body"]) or "", ""]
    return "\n".join(lines)


def _head_rule() -> str:
    """노션 원고, 포트폴리오 일감이 같이 쓰는 머리 주석 설명(꼴은 bridge/doctext/head.py 한 곳)."""
    from bridge.doctext.head import COVERS, READ, head_text
    return ("```\n" + head_text(["bridge/docsync.py", "bridge/static/js/scribe.js", "config/notion.toml"], "1a2b3c4") + "\n```\n"
            f"- {COVERS}: 그 편이 설명하는 코드 경로(파일, 끝이 /인 폴더). 쉼표로 나눈다. 실제 있는 경로만. 이 경로를 바꾼 feat, fix 커밋이 생기면\n"
            "  서기실이 그 편을 「코드가 바뀐 편」으로 센다. 너무 넓게(bridge/ 통째로) 적으면 늘 바뀐 편이 되고, 빠뜨리면 낡아도 모른다\n"
            f"- {READ}: 쓰기 전에 읽은 main 커밋(`git rev-parse --short HEAD`). 고쳐 쓸 때마다 새 값으로 바꾼다\n"
            "- 머리 주석이 없거나 틀리면 서기실이 그 편을 셀 수 없다(「머리 주석을 읽지 못한 편」). 합치기 전에 근거 확인기가 경로와 커밋을 본다")


MANUSCRIPT_HEAD = _head_rule()


def _rules_block(kind: str, repo: str) -> str:
    """원고 쓰는 기준 한 벌(`docs/manuscript_rules.md`, bridge/manuscript_rules.py). 기술문서와 포트폴리오 지시문이 같이 쓴다."""
    from bridge import manuscript_rules
    from bridge.docrefs import FOREMAN_ROOT, _same_repo
    return manuscript_rules.block(kind, _same_repo(repo, FOREMAN_ROOT))


COMMON = """
지켜야 할 것
- 먼저 이 저장소의 CLAUDE.md와 `docs/style_guide.md`(있으면)를 읽는다. 원고 쓰는 기준(모든 저장소 한 벌)은 FOREMAN `docs/manuscript_rules.md`이고 기술문서, 포트폴리오 일감에는 그 줄이 들어 있다
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
        body = f"""할 일: 사람이 포스트잇에서 [한계로] 보낸 줄을 고른 편의 「{_pi.LIMIT_TITLE}」 절에 쓴다.
- 재료(저장소 밖, 사람 말 원문): `{e.get('materials') or '(없음)'}` — 쓸 줄(편, 안 하는 까닭, 글)
- 무엇이 한계이고 무엇을 한계 절에 쓰는지는 아래 「원고 쓰는 기준」이 정한다(한계, 조건, 설계, 할 일 넷으로 가르는 줄과 한계 편의 꼴).
  사람이 [한계로]로 보냈어도 읽어 보고 한계가 아닌 줄(고르지 않은 조건, 하기로 정한 설계, 까닭 없는 할 일)이면 쓰지 말고
  마지막 응답에 어느 갈래로 보이는지와 까닭을 적는다. 까닭을 지어내지 않는다
- 쓸 줄: 재료가 고른 편(`편:`)의 「{_pi.LIMIT_TITLE}」 절에 쓰고, 그 줄에 사람이 적은 안 하는 까닭을 함께 적는다. 까닭을 바꾸지 않는다.
  할 일 말투(「할 것: …」)가 아니라 그 편을 읽는 사람에게 알리는 말투로 다시 쓴다.
  절이 없으면 그 편 끝에 `## {_pi.LIMIT_TITLE}`을 만든다. 같은 한계가 이미 있으면 그 줄에 보탠다
- TODO 항목에서 온 줄(재료 제목이 「TODO 항목 번호」): 같은 커밋에서 `docs/TODO.md`의 그 항목(머리 줄과 들여 쓴 내용 줄)을 지우고,
  커밋 메시지 본문에 `(todo:번호)`를 적는다(포스트잇 창이 그 커밋을 끝낸 커밋으로 읽는다)
- 편이 없는 옛 줄, 고른 편이 저장소에 없는 줄은 쓰지 말고 마지막 응답에 적는다
- 고칠 곳: 재료가 고른 편 파일, `docs/TODO.md`(TODO에서 온 줄만)

{_rules_block("limit", repo)}"""
    elif task == "portfolio":
        slug = e.get("slug") or ""
        if slug:
            what = f"""할 일: 포트폴리오 글 「{e.get('title') or slug}」(`portfolio/{slug}.md`)을 지금 화면과 코드에 맞게 고쳐 쓴다.
- 이 편의 머리 주석이 말하는 다루는 곳: {e.get('covers') or '(없음 — 이번에 정해 적는다)'}. 읽은 커밋 뒤 그 코드를 바꾼 커밋: {e.get('commits') or '(셀 수 없음)'}
- 다른 편: {e.get('siblings') or '(없음)'}. 같은 내용을 다시 쓰지 말고 "→ 「제목」"으로 가리킨다
- 고칠 곳은 `portfolio/{slug}.md`와 `portfolio/img/{slug}_*`뿐이다"""
        else:
            what = f"""할 일: 포트폴리오를 `portfolio/`에 쓴다. 정해진 주제 목록은 없다. 먼저 아래 「축 고르기」로 축을 정하고, 그 축으로 편 목록을 정해 새로 쓰거나 고쳐 쓴다.
- 지금 있는 편: {e.get('siblings') or '(없음)'}
- 편 목록은 `portfolio/` 폴더 파일이 정한다. 파일 이름 `NN_이름.md`(앞 번호가 차례). 필요한 만큼 늘린다
- 고른 축이 아닌 옛 편은 새 편으로 바꿔 쓰고, 쓸 데가 없어진 편 파일은 지운다. Notion에 남은 옛 페이지는 사람이 서기실 「포트폴리오 게시」의 [원본 없는 페이지 내리기]로 치운다
- 서브에이전트(Agent 도구)에게 편마다 맡겨도 된다. 맡길 때 아래 「원고 쓰는 기준」 「쓰는 법」 「머리 주석」을 그대로 준다
- 고칠 곳은 `portfolio/`뿐이다"""
        body = f"""{what}

{_rules_block("portfolio", repo)}

축 고르기(위 기준의 화면 축과 결정 중심 가운데 하나)
- 이 프로젝트에 보여줄 화면이 있는지는 저장소를 보고 정한다. 화면 파일(html, css, 화면 js), UI 폴더, `tools/screen.py`로 찍을 수 있는 화면이 있으면 있다. 서버 설정, 배포 파일, 스크립트뿐이면 없다. 프로젝트마다 다시 묻지 않고 이 기준 하나로 정한다
- 고른 축과 본 근거(어느 파일을 봤나)를 `log/`에 적는다. `log/`가 없는 저장소면 마지막 응답에만 적는다
- 화면 축이면 편 끝 링크는 `[기술문서: 서기와 문서](../notion/11_scribe.md)`처럼 원고 경로로 건다. 게시하면 그 Notion 페이지로 걸린다(노션 원고를 먼저 올린 뒤 포트폴리오를 올린다)
- 결정 중심이면 코드 속까지 파고드는 설명은 노션 원고 몫이니 필요하면 편 끝에 그 원고로 링크 한 줄을 건다. 사진과 영상은 그 결정을 보여 주는 것이 있을 때만 넣는다(없어도 된다). 넣으면 아래 찍는 법과 비밀값 확인을 그대로 따른다

화면 사진과 영상(화면 축일 때 필수, 결정 중심일 때는 넣는다면. docs/13_demo_capture.md 그대로)
- 화면 축으로 쓰는 글이라 화면이 보이지 않으면 뜻이 없다. 편마다 그 화면 사진을 한 장 이상 넣는다. 움직임이 중요한 것(캐릭터가 움직임, 띠가 뜸, 카드가 왔다 감 등)은 영상으로 넣는다
- 먼저 `portfolio/img/`에 남은 사진과 영상을 연다. 그 화면이 지금과 같으면 다시 쓴다. 화면이 바뀌었거나 없으면 새로 찍는다. 남은 파일 이름은 옛 글 번호(00 ~ 09) 기준이니 그 편의 화면이 맞는지 열어 보고 쓴다
- 사진: `tools/screen.py`로 직접 찍는다(사람에게 부탁하지 않는다). 찍는 크기, 한 장 크기 한도, 명령 예시는 `docs/style_guide.md` 「FOREMAN 찍는 법」을 따른다(숫자를 여기에 따로 적지 않는다). 패널을 열거나 버튼을 눌러야 하면 `--eval`, 부분 확대는 `--clip`
- 영상: 시연 모드(`/?demo=<대본 이름>`, 대본은 `bridge/static/demo/*.json`)로 `tools/screen.py --record <대본 이름>`을 쓴다. 8초 이하 한 가지 동작은 GIF, 그보다 길거나 패널까지 같이 보이면 WebM(13 문서 5절). 크기 한도는 `docs/style_guide.md` 「FOREMAN 찍는 법」을 따른다. 쓸 만한 대본이 없으면 새로 만든다
- 파일 이름은 `{slug or '<편 이름>'}_<무엇>.png`, `.gif`, `.webm`(`portfolio/img/` 아래). 글에는 `![설명](img/…)`로 넣고 캡션 끝에 〔실제 화면〕 〔시연 재생〕 〔실제 기록 재생〕 중 하나를 밝힌다. 사진은 쓸 것만 복사해 커밋한다(크기 한도는 위 「FOREMAN 찍는 법」)
- 찍기 전에 화면에 비밀값, 토큰, 다른 프로젝트의 민감한 글, 이 세션의 백그라운드 이름이 없는지 사진을 열어 본다. 실제 데이터가 너무 드러나는 화면은 시연 모드로 찍는다

머리 주석(편마다 맨 위. 노션에는 나가지 않는다)
{MANUSCRIPT_HEAD}

쓰는 법(기준은 위 「원고 쓰는 기준」)
- 코드에서 지금 상태를, docs/와 log/에서 까닭을 본다. 코드와 다르게 쓰지 않는다
- 근거는 근거 표시로만 단다: `[code:경로]` `[c:해시]` `[log:파일]` `[docs:파일]`. 노션 판에서는 떼어지고 git 원고에만 남는다. `[t:턴]`은 쓰지 않는다
- 독자에게 뜻 없는 것(서버 IP, `/home/…`, 포트, tmux 이름)은 쓰지 않는다
- 구조는 ```mermaid 블록으로 그려도 된다(Notion에 코드로 올라가고 사람이 한 번 미리보기로 바꾼다)
- 커밋 메시지: CLAUDE.md 「커밋 메시지」 꼴(예: `docs: 서기실 화면 포트폴리오를 씀`)""" + (
            f"\n\n덧붙인 요청(사람이 관리자를 거쳐 넘긴 것)\n{e['note']}" if e.get("note") else "")
    elif task == "techdoc":
        slug = e.get("slug") or ""
        if slug:
            # 11-19 foreman-125 편 하나 고쳐 쓰기([갱신], 편 목록 단추). 포트폴리오 편 하나와 같은 꼴이고, 나머지 약속은 통째 쓰기와 같다
            piece = f"{TECHDOC_DIR}{slug}.md"
            what = f"""할 일: 노션 기술문서 원고 한 편 「{e.get('title') or slug}」(`{piece}`)을 지금 코드에 맞게 고쳐 쓴다. 이 편 하나만 고친다.
원고 쓰기만 한다. Notion에 올리는 것은 사람이 서기실 「기술문서 게시」의 [Notion에 올리기]로 한다.
- 이 편의 머리 주석이 말하는 다루는 곳: {e.get('covers') or '(없음 — 이번에 정해 적는다)'}. 읽은 커밋 뒤 그 코드를 바꾼 커밋: {e.get('commits') or '(셀 수 없음)'}
- 다른 편: {e.get('siblings') or '(없음)'}. 다른 편은 고치지 않는다. 같은 내용을 다시 쓰지 말고 "→ 「제목」"으로 가리킨다.
  다른 편이 지금 코드와 어긋나 보이면 고치지 말고 마지막 응답에 적는다
- 파일 이름과 나무 자리는 바꾸지 않는다. 편을 옮기거나 쪼개야 할 것 같으면 고치지 말고 마지막 응답에 적는다"""
            order = f"""일하는 순서
1. `git rev-parse --short HEAD`를 적어 둔다
2. 이 편 전체를 처음부터 끝까지 읽고, 다루는 곳의 코드를 지금 판으로 읽어 문단마다 맞댄다. 다루는 곳이 빠졌거나 너무 넓으면 머리 주석의 다루는 곳도 고친다
3. 지금 코드와 다른 곳을 고친다. 서브에이전트(Agent 도구)에게 맡기면 위 「원고 쓰는 기준」과 아래 「머리 주석」 「쓰는 법」을 그대로 준다
4. 머리 「읽은 커밋」은 이 편 전체를 지금 코드와 맞대 읽었을 때만 1의 값으로 올린다. 고친 자리만 보고 끝냈으면 올리지 않고 그대로 두고,
   마지막 응답에 「읽은 커밋을 올리지 않았다」와 그 까닭을 적는다. 올리면 서기실이 이 편을 「그대로」로 센다
5. 바꾼 원고(`{piece}`)를 커밋한다"""
            tree, where, state = "", f"`{piece}`", ""
        else:
            what = f"""할 일: 이 프로젝트의 노션 기술문서 원고를 `{TECHDOC_DIR}`에 통으로 쓴다. 없으면 처음부터, 있으면 지금 코드에 맞게 고친다.
원고 쓰기만 한다. Notion에 올리는 것은 사람이 서기실 「기술문서 게시」의 [Notion에 올리기]로 한다."""
            order = """일하는 순서
1. `git rev-parse --short HEAD`를 적어 둔다. 모든 편의 「읽은 커밋」은 이 값 하나다(한 벌이 한 커밋의 사진)
2. 코드 지도를 읽고 목차(폴더 나무)를 정한다: 모듈 docstring, API 라우터, 화면 js, 마이그레이션, 설정 파일. 지난 원고가 있으면 그 나무를 고친다.
   편 수를 미리 정하지 않는다. 코드가 필요로 하는 만큼. 다른 프로젝트의 원고 구조를 베끼지 않는다
3. 편마다 서브에이전트(Agent 도구)에게 한 편씩 맡긴다. 동시에 몇 개든 된다. 맡길 때 그 편의 다루는 곳, 읽은 커밋, 위 「원고 쓰는 기준」과 아래 「나무 규칙」 「머리 주석」 「쓰는 법」을 그대로 준다
4. 돌아온 원고를 맞댄다: 편 사이 겹침, 어느 편에도 없는 코드, 다루는 곳이 실제 경로인지, 근거 표시가 맞는지
5. 바꾼 원고를 커밋한다"""
            tree = f"""나무 규칙
- `{TECHDOC_DIR}NN_이름.md` 한 편이 Notion [기술문서] 아래 페이지 하나다. `{TECHDOC_DIR}NN_이름/` 폴더 아래 글은 `NN_이름.md` 페이지의 하위 페이지다(폴더를 만들면 같은 이름 .md도 둔다)
- 파일 이름 앞 번호가 차례다(00, 01, …, 사이에 끼울 때는 03a). 편 수와 깊이 제한은 없다
- 제목은 각 글의 첫 `# ` 줄이다(Notion 페이지 제목이 된다)

"""
            where = f"`{TECHDOC_DIR}`"
            state = f"""

지금 원고(서기실이 센 것)
- 읽은 커밋 뒤 다루는 코드가 바뀐 편: {e.get('changed') or '(없음)'}
- 머리 주석을 읽지 못한 편: {e.get('unknown') or '(없음)'}
- 있는 편: {e.get('tree') or '(없음 — 처음 쓴다)'}"""
        body = f"""{what}

{_rules_block("techdoc", repo)}

{order}

{tree}머리 주석(편마다 맨 위. 노션에는 나가지 않는다)
{MANUSCRIPT_HEAD}

쓰는 법(기준은 위 「원고 쓰는 기준」)
- 노션 화면에서 보기 좋게 소제목과 표를 쓰되 설명은 문단으로 쓴다. 실제 명령어, 설정 값, 수치를 넣는다
- 코드에서 지금 상태를, docs/와 log/에서 까닭을 본다. 둘 다 본다. 코드 전체를 읽어도 된다. 코드와 다르게 쓰지 않는다
- 근거는 근거 표시로만 단다: `[code:경로]` `[c:해시]` `[log:파일]` `[docs:파일]`. 노션 판에서는 떼어지고 git 원고에만 남는다. 합치기 전에 근거 확인기가 그 경로, 커밋이 있는지 본다
- 비밀값, 토큰, 내부 주소는 쓰지 않는다
- 고칠 곳은 {where}뿐이다
- 커밋 메시지: CLAUDE.md 「커밋 메시지」 꼴(예: `docs: 기술문서 원고를 지금 코드에 맞춤`){state}""" + (
            f"\n\n덧붙인 요청(사람이 관리자를 거쳐 넘긴 것)\n{e['note']}" if e.get("note") else "")
    else:
        raise ValueError(task)
    return head + body + "\n" + COMMON


NOTE_MAX = 4000
REPORT_RE = re.compile(r"doccheck_[0-9A-Za-z_]{1,40}\.md")


async def _record(engine: Any, project: str, name: str, task: str, topic: str | None, res: dict[str, Any],
                  extra: list[str] | None = None) -> None:
    """서기실 [시키기]도 계획 · 직접 띄우기와 같은 dispatch 기록(origin scribe, 맡을 파일 = 그 일의 TOUCHES)을 남긴다(11-15).
    그래야 계획 겹침(file_conflicts)이 서기실 세션을 안다. 실패해도 띄우기는 되돌리지 않는다(open_tasks는 scribe-task로도 센다).
    extra는 띄울 때 정해지는 파일(later의 고른 편, 11-17)."""
    from bridge.foreman import record_spawn
    try:
        files = touches(task, topic) + list(extra or [])
        await record_spawn(engine, "scribe", project, {"role": "scribe", "title": name, "files": files, "worktree": True},
                           res, None, f"(서기실) {name}")
    except Exception as e:  # noqa: BLE001 — 0030 전 DB 등
        log.warning("서기실 띄우기 기록(dispatch) 실패: %s", type(e).__name__)


async def start(m: Any, engine: Any, project: str, task: str, topic: str | None = None, note: str | None = None,
                publishers: dict[str, Any] | None = None) -> dict[str, Any]:
    """서기 일을 worktree 세션으로 띄운다(handoff.spawn_new). 편이 있는 일(PIECE_TASKS: 포트폴리오, 11-19부터 기술문서)은
    편(topic)이 있으면 그 편만, 없으면 원고 폴더 통째로(11-15). 편은 main의 원고 폴더에 있는 것만 받는다.
    기술문서 쓰기(techdoc, 11-15)는 게시기 원고 폴더(src)가 notion/인 프로젝트만 — publishers로 본다. note는 덧붙인 요청.
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
    tps: list[dict[str, Any]] = []
    if task == "portfolio" and not has_portfolio(repo):
        raise Refused(f"이 저장소에는 {PORTFOLIO_DIR} 폴더가 없습니다. 포트폴리오를 쓰는 프로젝트가 아닙니다")
    if task == "techdoc":
        pub = (publishers or {}).get(project)
        if pub is None or getattr(pub, "src", "docs/") != TECHDOC_DIR:
            raise Refused(f"이 프로젝트는 기술문서 원고 폴더가 {TECHDOC_DIR}이 아닙니다(config/notion.toml src). 기술문서 쓰기를 시킬 수 없습니다")
    spec = PIECE_TASKS.get(task)
    if spec is not None:
        # 편이 있는 일: 편은 main의 원고 폴더에 있는 것만. 없는 편, 원고 폴더 밖 경로(「..」, 다른 폴더)는 목록에 없어 거절된다
        tps = topics(repo, task)
        if topic:
            tp = next((t for t in tps if t["slug"] == topic), None)
            if tp is None:
                form = "" if topic_ok(task, topic) else f". 편 이름은 {spec['dir']} 아래 경로에서 .md를 뗀 것입니다(소문자, 숫자, 밑줄)"
                raise Refused(f"{spec['label']}을 찾지 못했습니다({topic}). main의 {spec['dir']}에 있는 편만 고쳐 쓸 수 있습니다{form}")
        note = (note or "").strip()[:NOTE_MAX]          # 덧붙인 요청(목차 결정 등 — 사람이 관리자를 거쳐 넘긴 것)
    extra_files: list[str] = []
    if task == "later":
        # [한계로]에서 고른 편 파일도 맡는다(겹침 판단과 dispatch 기록)
        extra_files = sorted({x["piece"] for x in await inbox_new(engine, project) if x.get("piece")})
    why = blocked(task, await open_tasks(engine, project), topic if spec is not None else None, extra_files)
    if why:
        raise Refused(why)
    if task == "docfix" and topic and not Path(repo, "log", topic).is_file():
        raise Refused(f"log/{topic}가 main에 없습니다. 문서 점검 결과를 합친 뒤에 고칠 수 있습니다")
    now = datetime.now(UTC).replace(tzinfo=None)
    day = (now + KST).strftime("%Y%m%d")
    extra: dict[str, str] = {}
    if task == "later":
        when = await later_since(engine, project)
        inbox = await inbox_new(engine, project)
        if not inbox:                      # 빈손으로 Opus 세션을 띄우지 않는다(11-06 — 범위가 비어 사람 턴 0개로 떴다)
            raise Refused(f"{'지난 정리 뒤로' if when else '지금까지'} 포스트잇에서 [한계로] 보낸 것이 없습니다. 띄우지 않았습니다")
        from bridge.mask import Masker
        mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / "later.md", later_material(project, when, inbox, Masker()))
        extra["materials"] = str(mat)
        prompt = task_prompt(task, project, repo, extra)
    else:
        if spec is not None:
            extra["siblings"] = ", ".join(f"「{t['title']}」(`{spec['dir']}{t['slug']}.md`)" for t in tps if t is not tp)
            extra["note"] = note or ""
            if tp is not None:
                extra.update(slug=tp["slug"], title=tp["title"], covers=", ".join(f"`{c}`" for c in tp["covers"]),
                             commits="" if tp["commits"] is None else f"{tp['commits']}개")
        if task == "techdoc" and tp is None:
            from bridge import manuscript as ms
            pcs = ms.pieces(repo, TECHDOC_DIR, "HEAD")
            extra.update(changed=", ".join(f"`{p['path']}`({p['commits']}개)" for p in pcs if p["commits"]),
                         unknown=", ".join(f"`{p['path']}`({p['why']})" for p in pcs if p["commits"] is None),
                         tree=", ".join(f"`{p['path']}`" for p in pcs), note=note or "")
        if task == "docfix":
            extra.update(report=f"log/{topic}" if topic else "", note=note or "")
        if task == "doccheck":
            extra["stages"] = ", ".join(stages_without_result(repo)) or "(없음)"
        prompt = task_prompt(task, project, repo, extra)
    name = f"서기 — {TASKS[task]['title']}" + (f": {tp['title'].split(' — ')[0]}" if tp else "")
    # 일 종류(scribe-task)는 spawn_new가 남긴다(11-15 — 세 길이 같은 기록). 맡을 파일은 계획 길과 같은 dispatch_session으로.
    # techdoc의 합친 시각이 「이틀」 할 일의 기준이다(last_techdoc_merge)
    detail = f"{task} {tp['slug']}" if tp else f"docfix {fix_src}" if fix_src else task
    res = await m.spawn_new(repo, None, name, role="scribe", worktree=True, first_prompt=prompt, scribe_task=detail)
    await _record(engine, project, name, task, tp["slug"] if tp else None, res, extra_files)
    if task == "later" and res.get("session_id"):
        # 어디까지 봤나 — 이 세션이 합쳐지면 다음 정리의 기준점이 된다(later_since)
        await m._act(res["session_id"], LATER_ACT, res.get("pid"), True, f"{now.isoformat()} 쓸 줄 {len(inbox)}개")
        # 받은 할 일은 이 세션이 가져간다 — 합쳐지면 "옮김", 버려지면 다시 "새로"(상태는 계산, _INBOX_STATE)
        await _inbox_take(engine, [x["id"] for x in inbox], res["session_id"])
    return {"task": task, "project": project, "topic": tp["slug"] if tp else None, **{k: res.get(k) for k in ("tmux", "cc_session_id", "worktree", "note", "injected")}}
