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
    "publish": {"title": "Notion 게시", "desc": "회고 · 문서를 Notion에 올립니다. 세션 없이 [게시] 버튼으로 합니다."},
}


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


async def todo(engine: Any, publisher: Any = None) -> dict[str, dict[str, Any]]:
    """프로젝트마다 할 일 — [{kind(시킬 일), title, why}]. 기계로만 센다."""
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
        if publisher is not None and name == getattr(publisher, "project", None):
            try:
                for d in await publisher.list():
                    if d["status"] == "new" or d["changed"]:
                        items.append({"kind": "publish", "title": f"Notion 게시 — {Path(d['path']).name}",
                                      "why": "아직 안 올렸습니다" if d["status"] == "new" else "게시 뒤 원본이 바뀌었습니다"})
            except Exception:  # noqa: BLE001 — Notion이 꺼져 있어도 다른 할 일은 센다
                pass
        opened = await open_tasks(engine, name)
        out[name] = {"items": items, "open": opened,
                     "blocked": {k: b for k in TASKS if k != "publish" and (b := blocked(k, opened))}}
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
    return [{"session_id": sid, "task": (d or "").split()[0], "title": t} for sid, d, t in rows if (d or "").split()]


def blocked(task: str, opened: list[dict[str, Any]]) -> str | None:
    """이 일을 지금 시킬 수 없는 까닭(없으면 None) — 화면 버튼과 서버가 같은 판단을 쓴다."""
    for o in opened:
        if o["task"] == task:
            return f"「{TASKS[task]['title']}」이 이미 열려 있습니다(세션 {o['session_id']}) — 합치거나 버린 뒤에 시켜 주세요"
    for o in opened:
        common = sorted(TOUCHES.get(task, set()) & TOUCHES.get(o["task"], set()))
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
        body = f"""할 일: 대화에서 "나중에 하자"고 한 것을 README 「나중에 할 일 (정해 두고 미룬 것)」 표에 넣는다.
- 재료(저장소 밖, 사람 말 원문): `{e.get('materials') or '(없음)'}` — 지난 정리가 합쳐진 뒤(없으면 처음부터) "나중에 · 미루"가 나온 사람 말
- 항목마다 무엇 · 언제 · 조건 · 근거(결과 문서 · log). 이미 한 것은 표에서 뺀다. 그때뿐인 "나중에"(잠깐 뒤에)는 넣지 않는다
- README.md만 고친다"""
    else:
        raise ValueError(task)
    return head + body + "\n" + COMMON


async def start(m: Any, engine: Any, project: str, task: str) -> dict[str, Any]:
    """서기 일을 worktree 세션으로 띄운다(handoff.spawn_new). 회고는 재료 묶음을 먼저 만든다."""
    from bridge import scribe as sc
    from bridge.inject import Refused
    if task not in TASKS or task == "publish":
        raise Refused("세션으로 시키는 일이 아닙니다")
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT repo_path FROM project WHERE name = :p"), {"p": project})).first()
    repo = r[0] if r else None
    if not repo or not Path(repo, ".git").exists():
        raise Refused("이 프로젝트의 저장소를 찾지 못했습니다")
    why = blocked(task, await open_tasks(engine, project))
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
        if not rows:                       # 빈손으로 Opus 세션을 띄우지 않는다(11-06 — 범위가 비어 사람 턴 0개로 떴다)
            raise Refused(f"{'지난 정리 뒤로' if when else '지금까지'} \"나중에 · 미루\"라고 한 사람 말이 없습니다 — 띄우지 않았습니다")
        from bridge.mask import Masker
        mk = Masker()
        lines = [f"# 미룬 말 — {project} ({(sc.kst(when) + ' 뒤') if when else '처음부터'}, 사람 턴 {len(rows)}개)",
                 "README 「나중에 할 일」 표에 이미 있는 것은 빼고, 이미 한 일도 뺀다(지난 정리를 버렸으면 같은 범위를 다시 본다).", ""]
        for x in rows:
            lines += [f"## [t:{x['id']}] {sc.kst(x['started_at'])}", mk.text(sc._clip(x["prompt_text"], 1500)) or "", ""]
        mat = sc.write(sc.OUT_ROOT / f"{project}_{day}" / "later.md", "\n".join(lines))
        extra["materials"] = str(mat)
        prompt = task_prompt(task, project, repo, extra)
    else:
        if task == "readme":
            extra["since"] = commits_since_path(repo, "README.md")[1] or "?"
        if task == "doccheck":
            extra["stages"] = ", ".join(stages_without_result(repo)) or "(없음)"
        prompt = task_prompt(task, project, repo, extra)
    res = await m.spawn_new(repo, None, f"서기 — {TASKS[task]['title']}", role="scribe", worktree=True, first_prompt=prompt)
    if res.get("session_id"):
        await m._act(res["session_id"], TASK_ACT, res.get("pid"), True, task)
    if task == "later" and res.get("session_id"):
        # 어디까지 봤나 — 이 세션이 합쳐지면 다음 정리의 기준점이 된다(later_since)
        await m._act(res["session_id"], LATER_ACT, res.get("pid"), True, f"{now.isoformat()} 미룬 말 {len(rows)}개")
    return {"task": task, "project": project, **{k: res.get(k) for k in ("tmux", "cc_session_id", "worktree", "note", "injected")}}
