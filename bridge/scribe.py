"""12a 서기 — 재료 묶음(LLM 없음, docs/12_scribe.md 「3. 무엇을 읽나」).

브리지가 DB · git · 압축 손실 점검에서 기계로 모아 서기의 첫 글이 가리키는 파일로 쓴다. 서기는 여기서 시작해 필요한 원문만 더 읽는다.
**이 시스템만 가진 재료를 앞에 둔다** — 사람이 바로잡은 곳 · 뒤집힌 결정 · 실수(「7. 포트폴리오 관점」).
- 숨긴 세션(0018 hidden_at)은 뺀다. DB 글은 이미 비밀값을 가린 것이고, 여기서 한 번 더 가린다(Masker)
- 사람 프롬프트 원문이 들어 있어 저장소 밖(~/.foreman/scribe/, 700)에 쓴다 — GitHub에 올리지 않는다
- 근거 표시: [t:<턴 id>] · [c:<커밋>] · [log:<파일>] · [docs:<파일>] — 서기는 글에 이 표시를 그대로 단다

손으로 만들기: .venv/bin/python -m bridge.scribe <프로젝트> <시작 KST> <끝 KST> [--out 경로] [--baseline all.json] [--mistakes mistakes.json]
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

KST = timedelta(hours=9)
OUT_ROOT = Path.home() / ".foreman" / "scribe"
# 사람 말은 자르지 않는다(README 「나중에 할 일」 #14, 11-10 — 1500자에서 잘려 t:6360 · t:6383 뒤쪽이 빠졌다).
# 11-10 잰 크기: FOREMAN 사람 턴 전체 330개 · 206k자, 가장 긴 턴 9.9k자 — 서기가 Read를 쪽으로 나눠 읽으면 된다.
# Read는 2000자 넘는 한 줄을 조용히 자르므로, 긴 줄은 글자를 빼지 않고 LINE_WRAP자마다 줄만 나눈다.
LINE_WRAP = 1500
# 사람이 바로잡는 말의 신호(후보만 고른다 — 판단은 서기가 원문을 보고 한다)
CORRECTION = re.compile(r"아니|아냐|잘못|틀렸|틀린|왜 |모르겠|어색|말고|다시 |안 맞|안 보|안 돼|안 되|이상해|거꾸로|오해|빠졌|잊")


def kst(dt: datetime | None) -> str:
    return (dt + KST).strftime("%m-%d %H:%M") if dt else "?"


def parse_kst(s: str) -> datetime:
    """'2026-11-05' 또는 '2026-11-05 06:00'(KST) → UTC naive."""
    fmt = "%Y-%m-%d %H:%M" if " " in s.strip() else "%Y-%m-%d"
    return datetime.strptime(s.strip(), fmt) - KST


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


def first_heading(path: Path) -> str:
    try:
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()[:5]:
            if ln.startswith("#"):
                return ln.lstrip("# ").strip()
    except OSError:
        pass
    return ""


async def collect(engine: Any, project: str, start: datetime, end: datetime, repo: str) -> dict[str, Any]:
    """DB에서 기간 · 프로젝트의 재료를 모은다(숨긴 세션 제외)."""
    p = {"p": project, "a": start, "b": end}
    sess_q = ("FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id JOIN project pr ON pr.id = ch.project_id "
              "WHERE pr.name = :p AND cs.hidden_at IS NULL AND cs.type = 'agent'")
    async with engine.connect() as c:
        human = (await c.execute(text(
            "SELECT t.id, t.started_at, t.prompt_text, COALESCE(cs.custom_title, cs.title) AS title, cs.id AS sid, cs.role "
            f"FROM turn t JOIN character_session cs ON cs.id = t.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "JOIN project pr ON pr.id = ch.project_id WHERE pr.name = :p AND cs.hidden_at IS NULL AND t.origin = 'human' "
            "AND t.started_at >= :a AND t.started_at < :b ORDER BY t.started_at"), p)).mappings().all()
        sessions = (await c.execute(text(
            "SELECT cs.id, COALESCE(cs.custom_title, cs.title) AS title, cs.role, cs.cwd, "
            "(SELECT MIN(t.started_at) FROM turn t WHERE t.session_id = cs.id AND t.started_at >= :a AND t.started_at < :b) AS first, "
            "(SELECT MAX(t.started_at) FROM turn t WHERE t.session_id = cs.id AND t.started_at >= :a AND t.started_at < :b) AS last, "
            "(SELECT COUNT(*) FROM turn t WHERE t.session_id = cs.id AND t.started_at >= :a AND t.started_at < :b) AS turns, "
            "(SELECT COUNT(*) FROM turn t WHERE t.session_id = cs.id AND t.origin = 'human' AND t.started_at >= :a AND t.started_at < :b) AS human "
            f"{sess_q} HAVING turns > 0 ORDER BY first"), p)).mappings().all()
        origins = (await c.execute(text(
            "SELECT t.origin, COUNT(*) FROM turn t JOIN character_session cs ON cs.id = t.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project pr ON pr.id = ch.project_id "
            "WHERE pr.name = :p AND cs.hidden_at IS NULL AND t.started_at >= :a AND t.started_at < :b GROUP BY t.origin"), p)).all()
        tokens = (await c.execute(text(
            "SELECT m.model, SUM(m.token_input), SUM(m.token_output), SUM(m.token_cache_read), SUM(m.token_cache_creation) "
            "FROM message m JOIN turn t ON t.id = m.turn_id JOIN character_session cs ON cs.id = t.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project pr ON pr.id = ch.project_id "
            "WHERE pr.name = :p AND cs.hidden_at IS NULL AND m.created_at >= :a AND m.created_at < :b AND m.model <> '<synthetic>' "
            "GROUP BY m.model ORDER BY SUM(m.token_output) DESC"), p)).all()
        dispatch = (await c.execute(text(
            "SELECT id, created_at, request, plan, edited, status FROM dispatch WHERE created_at >= :a AND created_at < :b ORDER BY id"),
            p)).mappings().all()
        approvals = (await c.execute(text(
            "SELECT a.id, a.created_at, a.tool, a.target, a.rule, a.reason, a.status, a.message, a.decided_by "
            "FROM approval a JOIN character_session cs ON cs.id = a.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "JOIN project pr ON pr.id = ch.project_id WHERE pr.name = :p AND a.created_at >= :a AND a.created_at < :b ORDER BY a.id"),
            p)).mappings().all()
        builds = (await c.execute(text(
            "SELECT b.stage, b.status, COUNT(*) FROM build b JOIN project pr ON pr.id = b.project_id "
            "WHERE pr.name = :p AND b.started_at >= :a AND b.started_at < :b GROUP BY b.stage, b.status"), p)).all()
        handoffs = (await c.execute(text(
            "SELECT s.id, s.kind, s.source, s.status, s.created_at, s.injected_at FROM summary s "
            "JOIN character_session cs ON cs.id = s.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "JOIN project pr ON pr.id = ch.project_id WHERE pr.name = :p AND s.created_at >= :a AND s.created_at < :b ORDER BY s.id"),
            p)).mappings().all()
        actions = (await c.execute(text(
            "SELECT sa.action, COUNT(*) FROM session_action sa JOIN character_session cs ON cs.id = sa.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id JOIN project pr ON pr.id = ch.project_id "
            "WHERE pr.name = :p AND sa.created_at >= :a AND sa.created_at < :b GROUP BY sa.action"), p)).all()
    return {"human": [dict(r) for r in human], "sessions": [dict(r) for r in sessions], "origins": dict(origins),
            "tokens": [tuple(r) for r in tokens], "dispatch": [dict(r) for r in dispatch],
            "approvals": [dict(r) for r in approvals], "builds": [tuple(r) for r in builds],
            "handoffs": [dict(r) for r in handoffs], "actions": dict(actions),
            "commits": git_commits(repo, start, end)}


def _tok(n: Any) -> str:
    n = int(n or 0)
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1e3)}k" if n >= 1e3 else str(n)


def render(project: str, start: datetime, end: datetime, d: dict[str, Any], repo: str,
           baseline: list[dict[str, Any]] | None = None, mistakes: list[dict[str, Any]] | None = None,
           mask: Any = None) -> str:
    m = mask.text if mask else (lambda s: s)
    L: list[str] = []
    w = L.append
    w(f"# 재료 묶음 — {project} 회고 {kst(start)} ~ {kst(end)} (KST)")
    w("")
    w(f"> 만든 때 {kst(datetime.now(UTC).replace(tzinfo=None))} KST · 브리지가 LLM 없이 모음(`bridge/scribe.py`). 저장소 밖 파일 — 이 글을 저장소에 붙여 넣지 마라.")
    w("> 근거 표시: [t:턴 id] · [c:커밋] · [log:파일] · [docs:파일]. 회고의 모든 주장 끝에 이 표시를 단다. 숫자는 이 묶음 · DB · git에서 온 것만 쓴다.")
    w("> 앞 세 절(바로잡은 곳 · 뒤집힌 결정 · 실수)이 이 시스템만 가진 재료다. 회고도 이 순서로 앞에 둔다(docs/style_guide.md 「3.」).")
    w("")

    # 1. 사람이 바로잡은 곳
    w("## 1. 사람이 바로잡은 곳 — 후보")
    w("")
    w("기계가 고른 후보다(말투 신호 · 계획 고침 · 거절). 원문을 읽고 실제로 바로잡은 것만 쓴다.")
    w("")
    cand = [h for h in d["human"] if CORRECTION.search(h["prompt_text"] or "")]
    w(f"### 1-1. 사람 말에 정정 신호가 있는 턴 {len(cand)}개(전체 사람 턴 {len(d['human'])}개 중)")
    for h in cand:
        w(f"- [t:{h['id']}] {kst(h['started_at'])} · {m(h['title'] or '')} — {m(_clip(h['prompt_text'], 300)).replace(chr(10), ' ')}")
    w("")
    edited = [x for x in d["dispatch"] if x.get("edited")]
    w(f"### 1-2. 포먼 계획을 사람이 고친 것 {len(edited)}건(디스패치 {len(d['dispatch'])}건 중)")
    for x in edited:
        w(f"- 디스패치 #{x['id']} {kst(x['created_at'])} — 요청: {m(_clip(x['request'], 200))}")
        w(f"  - 계획: {m(_clip(x['plan'], 400))}")
        w(f"  - 사람이 고친 것: {m(_clip(x['edited'], 400))}")
    w("")
    denied = [a for a in d["approvals"] if a["status"] not in ("approved", "allowed", "pending", "auto")]
    w(f"### 1-3. 승인 — 전체 {len(d['approvals'])}건, 상태별 " + ", ".join(
        f"{k} {v}" for k, v in sorted({a['status']: sum(1 for b in d['approvals'] if b['status'] == a['status']) for a in d['approvals']}.items())))
    for a in denied[:30]:
        w(f"- 승인 #{a['id']} {kst(a['created_at'])} {a['status']} — {a['tool']} `{m(_clip(a['target'], 120))}` · 규칙 {a['rule']} · {m(_clip(a['message'] or a['reason'], 160))}")
    w("")

    # 2. 뒤집힌 결정
    w("## 2. 뒤집힌 결정")
    w("")
    if baseline:
        flips = [x for x in baseline if x.get("status") == "뒤집힘"]
        w(f"압축 손실 점검(11-05, [log:foreman_compaction_loss_20261105.md])이 고른 뒤집힘 {len(flips)}개 — 옛 결정과 바꾼 것:")
        for x in flips:
            w(f"- {x['id']} ({x.get('kind')}) {m(x.get('gist') or '')} → {m(x.get('missing') or '')}")
    else:
        w("(점검 결과 없음)")
    w("- 그 밖에 결과 문서의 「설계와 다른 점」이 뒤집힌 결정의 원천이다 — 아래 7절의 log 파일에서 찾는다")
    w("")

    # 3. 실수 · 고친 버그
    w("## 3. 실수 · 고친 버그")
    w("")
    for x in mistakes or []:
        w(f"### {x['title']}")
        for k in ("what", "why", "fix", "late"):
            if x.get(k):
                w(f"- {dict(what='현상', why='원인', fix='고친 것', late='왜 늦게 알았나')[k]}: {x[k]}")
        if x.get("refs"):
            w(f"- 근거: {' · '.join(x['refs'])}")
        w("")
    fixes = [c for c in d["commits"] if re.search(r"고침|바로잡|버그|실패|잘못|안 맞|fix", c["subject"], re.I)]
    w(f"### 커밋 제목에 고침 · 버그 신호가 있는 것 {len(fixes)}개")
    for c in fixes:
        w(f"- [c:{c['sha']}] {c['kst']} {c['subject'][:200]}")
    w("")

    # 4. 압축 손실
    w("## 4. 압축 손실 점검 결과")
    w("")
    if baseline:
        from collections import Counter
        cnt = Counter(x.get("status") for x in baseline)
        w(f"세션 161b8e7a 손 점검 {len(baseline)}개 — " + " · ".join(f"{k} {v}" for k, v in cnt.most_common())
          + " [log:foreman_compaction_loss_20261105.md]. 런슈즈 점검은 [log:runshoes_compaction_loss_20261105.md].")
        w("같은 방식을 기계로 옮긴 「압축으로 잊은 것 찾기」의 Sonnet 판정 품질은 [log:handoff_v2_d_result.md] — 재현율 0.71 · 정밀도 0.91.")
        w("")
        w("사라짐 · 약해짐(요지 · 있는 곳 · 빠진 요약):")
        for x in baseline:
            if x.get("status") in ("사라짐", "약해짐"):
                w(f"- {x['status']} {x['id']} ({x.get('kind')}) {m(x.get('gist') or '')} — {m(x.get('where') or '문서에 없음')} · {x.get('dropped_at') or ''}")
    w("")

    # 5. 숫자
    w("## 5. 숫자")
    w("")
    w("| 무엇 | 값 |")
    w("|---|---|")
    w(f"| 세션(턴이 있던 것, 숨긴 것 빼고) | {len(d['sessions'])} |")
    w(f"| 턴 — 출처별 | {', '.join(f'{k} {v}' for k, v in sorted(d['origins'].items(), key=lambda kv: -kv[1]))} |")
    w(f"| 사람 턴 · 글자 | {len(d['human'])} · {sum(len(h['prompt_text'] or '') for h in d['human']):,}자 |")
    w(f"| 커밋(HEAD에 닿는 것) | {len(d['commits'])} |")
    w(f"| 디스패치 · 계획 고침 | {len(d['dispatch'])} · {len(edited)} |")
    w(f"| 승인 요청 | {len(d['approvals'])} |")
    w(f"| 인계 요약 | {len(d['handoffs'])} (넣음 {sum(1 for h in d['handoffs'] if h['injected_at'])}) |")
    w(f"| 세션 조작 | {', '.join(f'{k} {v}' for k, v in sorted(d['actions'].items()))} |")
    w(f"| 빌드 | {', '.join(f'{s}/{st} {n}' for s, st, n in d['builds']) or '없음'} |")
    w("")
    w("모델별 토큰(서브에이전트 포함, 출력 많은 순):")
    w("")
    w("| 모델 | 입력 | 출력 | 캐시 읽기 | 캐시 쓰기 |")
    w("|---|---|---|---|---|")
    for model, tin, tout, cr, cc in d["tokens"]:
        w(f"| {model} | {_tok(tin)} | {_tok(tout)} | {_tok(cr)} | {_tok(cc)} |")
    w("")
    w("세션별:")
    for s in d["sessions"]:
        w(f"- 세션 {s['id']} {m(s['title'] or '')} · {s['role'] or '-'} · {kst(s['first'])}~{kst(s['last'])} · 턴 {s['turns']}(사람 {s['human']}) · `{(s['cwd'] or '').replace(str(Path.home()), '~')}`")
    w("")

    # 6. 커밋
    w(f"## 6. 커밋 {len(d['commits'])}개")
    w("")
    for c in d["commits"]:
        w(f"- [c:{c['sha']}] {c['kst']} {c['subject'][:240]}")
    w("")

    # 7. 이미 쓴 기록
    w("## 7. 이미 쓴 기록 — 다시 쓰지 말고 가리킨다")
    w("")
    touched = sorted({f for c in d["commits"] for f in c["files"] if f.startswith(("log/", "docs/")) and f.endswith(".md")})
    for f in touched:
        w(f"- [{f.split('/')[0]}:{f.split('/', 1)[1]}] {first_heading(Path(repo) / f)}")
    w("")

    # 8. 사람이 한 말
    w(f"## 8. 사람이 한 말 {len(d['human'])}턴 (시간 순, 자르지 않은 원문 — 길면 쪽으로 나눠 끝까지 읽는다)")
    w("")
    for h in d["human"]:
        w(f"### [t:{h['id']}] {kst(h['started_at'])} · 세션 {h['sid']} {m(h['title'] or '')}")
        w(m(_full(h["prompt_text"])))
        w("")
    return "\n".join(L)


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_text(body, encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def retro_prompt(project: str, period: str, materials: str, out: str) -> str:
    """서기 세션의 첫 글 — 회고 일감."""
    return f"""[FOREMAN 서기 일감 — 회고] {project} {period}

너는 이 프로젝트의 서기(문서 담당)다. 위 기간의 회고를 쓴다.

먼저 읽을 것
- `docs/style_guide.md` — 문서 쓰는 기준(특히 「3.」 회고 구성 · 「4.」 문체)
- `docs/12_scribe.md` 「4. 수준을 어떻게 담보하나」 · 「7. 포트폴리오 관점」
- 재료 묶음 `{materials}` — 브리지가 DB · git · 압축 손실 점검에서 모은 것(저장소 밖. 내용을 저장소에 붙여 넣지 마라)

쓸 것: `{out}`
- 구성은 style_guide 「3.」 회고 그대로. **사람이 바로잡은 곳 · 뒤집힌 결정 · 실수를 앞에** 둔다 — 이 시스템만 가진 재료다
- 바로잡은 곳 후보(재료 1절)는 기계가 고른 것이다. 원문을 읽고 실제로 사람이 AI를 바로잡은 것만 쓴다
- 모든 주장 끝에 근거 표시([t:…] · [c:…] · [log:…] · [docs:…]). 숫자는 재료 · DB · git에서 온 것만
- 한 일은 결과 문서를 가리키고 다시 쓰지 않는다
- 사용자 프롬프트를 길게 옮기지 마라 — 판단이 드러나는 한 줄만 인용
- 쓰지 않는 것: 과장, 근거 없는 수치, 일반론("소통이 중요했다")

끝나면
- `{out}`만 `git add`하고 커밋한다(`retro: {period} {project} 회고`). push하지 않는다(따로 작업 — CLAUDE.md 「따로 작업」)
- 마지막 응답에 쓴 파일 · 절 목록 · 근거 표시 수 · 확인 못 한 것을 짧게 알린다
- 사람이 [합치기] 전에 diff를 본다. 고칠 말이 오면 그대로 고친다"""


async def _main() -> None:
    import argparse
    from bridge.config import get_settings
    from bridge.db.engine import make_engine
    from bridge.mask import Masker
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("start", help="KST, 예: '2026-11-05' 또는 '2026-11-05 00:00'")
    ap.add_argument("end", help="KST")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--out")
    ap.add_argument("--baseline")
    ap.add_argument("--mistakes", help="JSON 배열 [{title, what, why, fix, late, refs}]")
    a = ap.parse_args()
    start, end = parse_kst(a.start), parse_kst(a.end)
    e = make_engine(get_settings())
    try:
        d = await collect(e, a.project, start, end, a.repo)
    finally:
        await e.dispose()
    base = json.loads(Path(a.baseline).read_text(encoding="utf-8")) if a.baseline else None
    mist = json.loads(Path(a.mistakes).read_text(encoding="utf-8")) if a.mistakes else None
    body = render(a.project, start, end, d, a.repo, base, mist, Masker())
    out = Path(a.out) if a.out else OUT_ROOT / f"{a.project}_{(start + KST):%Y%m%d}" / "materials.md"
    write(out, body)
    print(out, f"{len(body):,}자", f"사람 턴 {len(d['human'])}", f"커밋 {len(d['commits'])}", f"세션 {len(d['sessions'])}")


if __name__ == "__main__":
    asyncio.run(_main())
