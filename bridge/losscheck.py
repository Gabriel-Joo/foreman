"""인계 2판 d — [잃은 것 보기]: 압축 손실 점검을 기계로(11-06, docs/11_handoff_v2.md 3장 「압축 손실 점검을 버튼으로」).

11-05에 손으로 한 점검(런슈즈 · 포먼, log/*_compaction_loss_20261105.md)을 그대로 옮긴다.
1. 추출(LLM 없음) — 트랜스크립트에서 압축 구간별 사람 프롬프트와 그 구간을 대신한 압축 요약을 뽑는다.
   순서는 파일 순서(timestamp로 다시 정렬하지 않는다), 압축 요약 줄 · 사이드체인 · 도구 결과 · 브리지가 넣은 글은 프롬프트가 아니다.
2. 지금 맥락 — 마지막 요약 + 그 뒤 프롬프트 + 저장소 CLAUDE.md + 지속 메모리.
3. 판정(`claude -p`, 기본 Sonnet) — 프롬프트 약 80개씩 묶어 여러 번. 작업 폴더(저장소 밖)의 파일을 Read · Grep으로 읽고,
   저장소는 읽기만(있는 곳을 찾으려고). 결과 모양은 손 점검의 all.json과 같다.
작업 폴더에는 사용자 프롬프트 원문 · 요약 전문이 있다 — 저장소에 두지 않는다(GitHub에 올리지 않는다).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATUSES = ("살아 있음", "약해짐", "사라짐", "뒤집힘", "끝남")
LOST = ("사라짐", "약해짐")
KINDS = ("결정", "금지", "기준", "선호", "지시", "미완")
GROUP_MAX = 20                 # 판정 한 번에 넣는 프롬프트 수. 설계는 약 80(Opus 에이전트 기준)이었으나 Sonnet에 68개를 한 번에
                               # 주니 훑어 읽어 정답 프롬프트 53개 중 18개만 봤다(11-06) — 작게 나누고 빠짐없이 봤는지 센다
JUDGE_TIMEOUT_S = 1800.0

_WRAP = re.compile(r'^\s*<pasted_content id="[0-9a-f]+">\s*|\s*</pasted_content id="[0-9a-f]+">\s*$')
_NOT_PROMPT = ("<agent-message", "<task-notification", "[Request interrupted", "Another Claude session", "<command-",
               "<local-command", "[FOREMAN 인계", "Caveat:", "<system-reminder")


@dataclass
class Seg:
    """압축 하나가 대신한 구간. summary는 이 구간 끝의 압축 요약(마지막 구간은 None — 아직 압축되지 않음)."""
    prompts: list[dict[str, str]] = field(default_factory=list)
    summary: str | None = None
    summary_ts: str | None = None
    start: str | None = None


def _text(c: Any) -> str:
    if isinstance(c, str):
        return c
    return "".join(b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")


def extract(path: str | os.PathLike[str], until: str | None = None) -> list[Seg]:
    """트랜스크립트 → 구간 목록. until(ISO 시각)을 주면 그 시각 뒤 줄은 보지 않는다(정답과 같은 자리에서 자르기)."""
    segs = [Seg()]
    with open(path, "rb") as f:
        for raw in f:
            if b'"type":"user"' not in raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("type") != "user" or d.get("isSidechain"):
                continue
            ts = d.get("timestamp")
            if until and ts and ts > until:
                break
            c = (d.get("message") or {}).get("content")
            if d.get("isCompactSummary"):
                segs[-1].summary, segs[-1].summary_ts = _text(c), ts
                segs.append(Seg(start=ts))
                continue
            if d.get("isMeta"):
                continue
            if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                continue
            t = _WRAP.sub("", _text(c)).strip()
            if not t or t.startswith(_NOT_PROMPT):
                continue
            if (d.get("origin") or {}).get("kind") not in (None, "human") and d.get("turnOrigin") not in (None, "human"):
                continue
            if segs[-1].start is None:
                segs[-1].start = ts
            segs[-1].prompts.append({"ts": ts or "", "text": t})
    return segs


def groups(segs: list[Seg], limit: int = GROUP_MAX) -> list[list[tuple[int, int, int]]]:
    """판정할 프롬프트(마지막 구간 빼고)를 약 limit개씩 — [(구간, 시작, 끝)] 묶음. 구간은 되도록 쪼개지 않는다."""
    out: list[list[tuple[int, int, int]]] = []
    cur: list[tuple[int, int, int]] = []
    n = 0
    for i, s in enumerate(segs[:-1]):
        k = 0
        while k < len(s.prompts):
            rest = len(s.prompts) - k
            if cur and n + rest > limit:             # 구간을 쪼개지 않으려고 새 묶음부터
                out.append(cur)
                cur, n = [], 0
            take = min(rest, limit - n)              # 한 구간이 limit보다 크면 그때만 쪼갠다
            cur.append((i, k, k + take))
            n, k = n + take, k + take
            if n >= limit:
                out.append(cur)
                cur, n = [], 0
    if cur:
        out.append(cur)
    return out


def memory_dir(cwd: str) -> Path:
    """CC 지속 메모리 폴더 — ~/.claude/projects/<cwd의 / · _ · . 을 -로>/memory."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd) / "memory"


def context_text(segs: list[Seg], claude_md: str, memory: dict[str, str]) -> str:
    """지금 세션이 들고 있는 것 — 마지막 요약 · 그 뒤 프롬프트 · CLAUDE.md · 메모리."""
    last = len(segs) - 1
    prev = segs[last - 1] if last >= 1 else None
    out = [f"# 지금 세션이 들고 있는 것 ①: 마지막 압축 요약(구간 {last - 1} → {prev.summary_ts if prev else '없음'})\n\n"
           + ((prev.summary or "") if prev else "(압축된 적 없음)")]
    out.append(f"\n\n# ②: 마지막 압축 뒤 사람 프롬프트(구간 {last}, 원문 그대로 컨텍스트에 있음)\n")
    for k, p in enumerate(segs[last].prompts):
        out.append(f"\n--- [구간{last}-{k}] {p['ts']}\n{p['text']}\n")
    out.append("\n\n# ③: 저장소 CLAUDE.md(매 세션 자동으로 읽힌다)\n\n" + claude_md)
    out.append("\n\n# ④: 지속 메모리(MEMORY.md 색인은 자동으로 읽히고, 각 파일은 필요할 때 읽는다)\n")
    for name in sorted(memory):
        out.append(f"\n## {name}\n{memory[name]}\n")
    return "".join(out)


def write_workdir(wd: Path, segs: list[Seg], ctx: str) -> list[tuple[str, list[str]]]:
    """판정 재료를 작업 폴더에 — prompts_<g>.md(묶음마다) · summary_NN.md · current_context.md.
    [(묶음 파일 이름, 그 묶음의 프롬프트 id들)]을 돌려준다(빠짐없이 봤는지 셀 때 쓴다)."""
    wd.mkdir(parents=True, exist_ok=True)
    os.chmod(wd, 0o700)
    names = []
    for gi, g in enumerate(groups(segs)):
        name = f"prompts_{chr(ord('A') + gi)}.md"
        with open(wd / name, "w", encoding="utf-8") as f:
            for i, a, b in g:
                s = segs[i]
                f.write(f"\n\n######## 구간 {i} (시작 {s.start}, 이 구간은 {s.summary_ts}에 압축됨 → summary_{i:02d}.md)\n")
                for k in range(a, b):
                    p = s.prompts[k]
                    f.write(f"\n--- [구간{i}-{k}] {p['ts']}\n{p['text']}\n")
        names.append((name, [f"구간{i}-{k}" for i, a, b in g for k in range(a, b)]))
    for i, s in enumerate(segs[:-1]):
        (wd / f"summary_{i:02d}.md").write_text(s.summary or "", encoding="utf-8")
    (wd / "current_context.md").write_text(ctx, encoding="utf-8")
    return names


JUDGE_PROMPT = """너는 Claude Code 세션의 **압축 손실 점검**을 한다. 파일은 고치지 마라(읽기 · 찾기만).

작업 폴더(지금 폴더)
- `{prompts}` — 판정할 사람 프롬프트. 구간마다 "######## 구간 N" 머리, 프롬프트마다 "--- [구간N-k] 시각"
- `summary_NN.md` — 구간 NN이 끝날 때 CC가 만든 압축 요약(그 구간 대화를 이 요약이 대신했다). 총 {n_sum}개(00~{last_sum})
- `current_context.md` — 이 세션이 **지금** 들고 있는 것: ① 마지막 압축 요약 ② 그 뒤 프롬프트 ③ CLAUDE.md ④ 지속 메모리
저장소 `{repo}` — 읽기만. 잃은 것이 저장소 문서(README · docs · log)에 적혀 있는지 찾을 때 쓴다(Grep 권장).

할 일
1. `{prompts}`의 프롬프트 {n}개({first} ~ {last})를 **하나도 빼지 말고 차례로** 읽고, 각각에서 **오래 지켜야 하는 것**을 골라낸다: 사용자가 정한 결정 · 금지 · 기준 · 선호, 사용자가 시킨 지시(그 뒤로도 지켜야 하는 것), 끝나지 않은 일(미완). 끝난 일(끝남)도 항목으로 낸다.
   - 그때뿐인 요청 · 질문 · 잡담은 뺀다. 한 프롬프트에 여럿이면 하나하나 나눈다(id 끝에 -a, -b …). 긴 프롬프트에는 보통 여러 개가 있다
   - 고를 것이 없는 프롬프트는 empty에 id를 적는다. **모든 프롬프트 id가 items나 empty에 나와야 한다**(브리지가 센다)
2. 항목마다 **지금 맥락**(current_context.md)에 남았는지 판정한다.
   - 살아 있음: 내용과 이유가 지금 맥락에 그대로 있다
   - 약해짐: 일부만 남았다(이유 · 조건 · 범위가 빠짐, 다른 맥락으로만 언급됨)
   - 사라짐: 지금 맥락에 없다
   - 뒤집힘: 나중 프롬프트가 바꿨다 — 되살리면 안 된다(missing에 무엇으로 바뀌었는지)
   - 끝남: **미완 · 지시**가 실행돼 더 할 것이 없을 때만
   - **결정 · 금지 · 기준 · 선호는 끝남이 될 수 없다.** 이미 구현됐거나 저장소 문서에 적혀 있어도, 앞으로 코드 · 문서를 고칠 때 지켜야 하는 규칙이다 — 지금 맥락에 있는지로 살아 있음 · 약해짐 · 사라짐을 가른다(문서에만 있으면 사라짐 + `repo:<경로>`). 나중 결정이 바꿨으면 뒤집힘
3. 사라짐 · 약해짐은 언제 빠졌는지 본다: 그 구간부터 차례로 summary_NN.md를 보고, 처음 빠진 요약 이름(dropped_at, 예 "summary_03")
4. where: 지금 남은 곳 또는 되살릴 곳. 모양은 `CLAUDE.md(…)` · `current_summary(…)` · `memory:<파일>` · `prompt_after(구간N-k)` · `repo:<경로>`를 " · "로 잇는다.
   사라짐이어도 저장소 문서에 있으면 `repo:<경로>`를 꼭 적는다(그것이 "읽기만 하면 되살릴 수 있는가"의 근거다)

마지막 응답에 아래 모양 그대로 **한 번만** 써라(JSON 객체, 표지 줄 두 개를 글자 그대로). 글은 한국어로:

<<<FOREMAN-LOSS r={r}>>>
{{"items": [{{"id": "구간0-3-a", "ts": "<프롬프트 시각>", "kind": "결정|금지|기준|선호|지시|미완", "quote": "<사용자 말 그대로, 200자 이내>", "gist": "<요지 한 줄>", "status": "살아 있음|약해짐|사라짐|뒤집힘|끝남", "where": "…", "dropped_at": "summary_NN 또는 null", "missing": "<약해짐 · 뒤집힘이면 무엇이 빠졌나/바뀌었나>", "why_matters": "<사라짐 · 약해짐이면 앞으로 어디서 문제가 되나>"}}],
 "empty": ["<고를 것이 없던 프롬프트 id, 예 구간0-4>"]}}
<<<END r={r}>>>"""


def judge_prompt(prompts_file: str, ids: list[str], n_sum: int, repo: str, req: str) -> str:
    return JUDGE_PROMPT.format(prompts=prompts_file, n=len(ids), first=ids[0] if ids else "", last=ids[-1] if ids else "",
                               n_sum=n_sum, last_sum=f"{max(n_sum - 1, 0):02d}", repo=repo, r=req)


def _prompt_of(item_id: str) -> str:
    """구간0-3-a → 구간0-3 (프롬프트 단위로 맞대려고)."""
    m = re.match(r"(구간\d+-\d+)", item_id or "")
    return m.group(1) if m else item_id


def coverage(ids: list[str], items: list[dict[str, Any]], empty: list[str]) -> list[str]:
    """판정이 건너뛴 프롬프트 — items에도 empty에도 없는 id."""
    seen = {_prompt_of(x["id"]) for x in items} | {_prompt_of(e) for e in empty}
    return [i for i in ids if i not in seen]


def parse_result(text: str, req: str) -> tuple[list[dict[str, Any]], list[str]]:
    """(items, empty). 배열만 낸 옛 모양도 받는다."""
    m = list(re.finditer(rf"<<<FOREMAN-LOSS r={req}>>>[ \t]*\n(.*?)\n[ \t]*<<<END r={req}>>>", text or "", re.S))
    if not m:
        raise ValueError("판정 결과 표지가 없습니다")
    data = json.loads(m[-1].group(1))
    empty: list[str] = []
    if isinstance(data, dict):
        empty = [str(e) for e in data.get("empty") or [] if isinstance(e, str)]
        data = data.get("items")
    if not isinstance(data, list):
        raise ValueError("판정 결과에 items 배열이 없습니다")
    return _items(data), empty


def parse_items(text: str, req: str) -> list[dict[str, Any]]:
    return parse_result(text, req)[0]


def _items(data: list[Any]) -> list[dict[str, Any]]:
    out = []
    for d in data:
        if not isinstance(d, dict) or not d.get("gist"):
            continue
        st = d.get("status") if d.get("status") in STATUSES else "사라짐"
        out.append({"id": str(d.get("id") or ""), "ts": str(d.get("ts") or ""),
                    "kind": d.get("kind") if d.get("kind") in KINDS else "결정",
                    "quote": str(d.get("quote") or "")[:400], "gist": str(d["gist"])[:300], "status": st,
                    "where": str(d.get("where") or ""), "dropped_at": d.get("dropped_at") or None,
                    "missing": str(d.get("missing") or ""), "why_matters": str(d.get("why_matters") or "")})
    return out


async def run_judge(prompt: str, wd: Path, repo: str, claude_bin: str = "claude", model: str = "sonnet",
                    timeout: float = JUDGE_TIMEOUT_S) -> dict[str, Any]:
    """`claude -p` 한 번 — {text, usage, cost_usd, ms, error}. 디스패처와 같은 방식(stdin, 훅 끔, 읽기 도구만)."""
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    t0 = time.monotonic()
    try:
        p = await asyncio.create_subprocess_exec(
            claude_bin, "-p", "--model", model, "--output-format", "json", "--no-session-persistence",
            "--settings", json.dumps({"disableAllHooks": True}),
            "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent",
            "--add-dir", repo,                                   # 값을 여러 개 받아 뒤 인자를 삼킨다 — 프롬프트는 stdin
            cwd=str(wd), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env)
        out, err = await asyncio.wait_for(p.communicate(prompt.encode()), timeout)
    except TimeoutError:
        p.kill()
        return {"text": "", "usage": None, "cost_usd": None, "ms": round((time.monotonic() - t0) * 1000),
                "error": f"{timeout:.0f}초 안에 끝나지 않았습니다"}
    except OSError as e:
        return {"text": "", "usage": None, "cost_usd": None, "ms": 0, "error": f"claude를 띄우지 못했습니다: {e}"}
    raw = out.decode(errors="replace")
    try:
        j = json.loads(raw)
    except ValueError:
        j = {"result": raw}
    return {"text": j.get("result") or "", "usage": j.get("usage"), "cost_usd": j.get("total_cost_usd"),
            "ms": round((time.monotonic() - t0) * 1000),
            "error": None if p.returncode == 0 else (err.decode(errors="replace")[-300:] or f"종료 코드 {p.returncode}")}


def compare(mine: list[dict[str, Any]], base: list[dict[str, Any]]) -> dict[str, Any]:
    """정답과 맞대기 — 항목은 고르는 결이 달라 1:1로 못 맞춘다. 상태별 개수와 **프롬프트 단위**로 본다.
    lost_recall: 정답이 잃었다(사라짐 · 약해짐)고 한 프롬프트 중 이쪽도 잃었다고 한 비율. lost_precision은 반대 방향."""
    cnt = lambda xs: dict(Counter(x["status"] for x in xs))  # noqa: E731
    lost = lambda xs: {_prompt_of(x["id"]) for x in xs if x["status"] in LOST}  # noqa: E731
    flip = lambda xs: {_prompt_of(x["id"]) for x in xs if x["status"] == "뒤집힘"}  # noqa: E731
    bl, ml = lost(base), lost(mine)
    hit = bl & ml
    return {"items": {"mine": len(mine), "base": len(base)}, "status": {"mine": cnt(mine), "base": cnt(base)},
            "lost_prompts": {"base": len(bl), "mine": len(ml), "both": len(hit),
                             "recall": round(len(hit) / len(bl), 2) if bl else None,
                             "precision": round(len(hit) / len(ml), 2) if ml else None,
                             "missed": sorted(bl - ml), "extra": sorted(ml - bl)},
            "flipped": {"base": sorted(flip(base)), "mine": sorted(flip(mine)),
                        "mine_said_lost": sorted(flip(base) & ml)},       # 뒤집힌 것을 "되살릴 것"으로 잘못 낸 자리
            "repo_where_lost": {"mine": sum(1 for x in mine if x["status"] in LOST and "repo:" in x["where"]),
                                "base": sum(1 for x in base if x["status"] in LOST and "repo:" in x["where"])}}


async def judge_all(wd: Path, names: list[tuple[str, list[str]]], n_sum: int, repo: str, req: str,
                    on_group: Any = None, **kw: Any) -> dict[str, Any]:
    """묶음마다 판정 — 차례로 돈다(동시에 돌리면 토큰 한도에 같이 걸린다). 하나가 실패해도 나머지는 남긴다.
    묶음마다 건너뛴 프롬프트(skipped)를 센다 — 판정이 조용히 얇아지지 않게."""
    items: list[dict[str, Any]] = []
    runs = []
    for name, ids in names:
        r = await run_judge(judge_prompt(name, ids, n_sum, repo, req), wd, repo, **kw)
        got: list[dict[str, Any]] = []
        empty: list[str] = []
        if r["error"] is None:
            try:
                got, empty = parse_result(r["text"], req)
                items += got
            except ValueError as e:
                r["error"] = str(e)
        tag = name[8:-3]
        (wd / f"result_{tag}.json").write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
        (wd / f"raw_{tag}.txt").write_text(r["text"], encoding="utf-8")
        runs.append({"group": name, "prompts": len(ids), "items": len(got), "empty": len(empty),
                     "skipped": coverage(ids, got, empty) if r["error"] is None else ids,
                     "ms": r["ms"], "cost_usd": r["cost_usd"], "usage": r["usage"], "error": r["error"]})
        if on_group:
            await on_group(items, runs)
    return {"items": items, "runs": runs}


# ── 브리지에서 돌리기(2부) ─────────────────────────────────────
WORK_ROOT = Path.home() / ".foreman" / "losscheck"
SHOW = 40                      # 화면 · 옮기기 입력에 내는 잃은 것 최대 수


def summarize(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(x["status"] for x in items))


def lost(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """화면 · c 입력용 — 사라짐 먼저, 그다음 약해짐. 뒤집힘 · 끝남 · 살아 있음은 내지 않는다(되살리면 안 되거나 남아 있다)."""
    order = {"사라짐": 0, "약해짐": 1}
    return sorted((x for x in items if x["status"] in LOST), key=lambda x: (order[x["status"]], x["id"]))


def lost_text(items: list[dict[str, Any]], limit: int = SHOW) -> str:
    """문서로 옮기기(c) 목록 요청에 같이 넣을 글 — 항목마다 상태 · 종류 · 요지 · 원문 · 있는 곳."""
    out = []
    for x in lost(items)[:limit]:
        line = f"- [{x['status']} · {x['kind']}] {x['gist']}"
        if x.get("quote"):
            line += f"\n  원문: “{x['quote'][:200]}”"
        if x.get("where"):
            line += f"\n  있는 곳: {x['where'][:200]}"
        if x["status"] == "약해짐" and x.get("missing"):
            line += f"\n  빠진 것: {x['missing'][:200]}"
        out.append(line)
    return "\n".join(out)


class LossChecker:
    """HandoffManager에 붙어 DB · 알림을 같이 쓴다(main.py가 handoff.losscheck로 넣는다). 버튼을 누를 때만 돈다."""

    def __init__(self, m: Any, model: str = "sonnet", claude_bin: str = "claude", mask: Any = None,
                 root: Path = WORK_ROOT) -> None:
        self.m, self.model, self.claude_bin, self.root = m, model, claude_bin, root
        if mask is None:
            from bridge.mask import Masker
            mask = Masker()
        self.mask = mask
        self.judge = judge_all            # 시험에서 바꿔 끼운다

    async def recover(self) -> int:
        """브리지가 뜰 때 — 돌던 점검은 작업이 같이 죽었다. running으로 남기지 않고 failed로(조용히 멈춘 채 두지 않게)."""
        from sqlalchemy import text
        async with self.m.engine.begin() as c:
            r = await c.execute(text("UPDATE loss_check SET status = 'failed', error = :e WHERE status = 'running'"),
                                {"e": "브리지가 다시 떠서 멈췄습니다 — 다시 눌러 주세요"})
        return r.rowcount or 0

    async def _save(self, lid: int, **kw: Any) -> None:
        from sqlalchemy import text
        for k in ("items", "runs"):
            if k in kw and kw[k] is not None and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k], ensure_ascii=False)
        if kw.get("error"):
            kw["error"] = kw["error"][:512]
        cols = ", ".join(f"{k} = :{k}" for k in kw)
        async with self.m.engine.begin() as c:
            await c.execute(text(f"UPDATE loss_check SET {cols} WHERE id = :lid"), {**kw, "lid": lid})
        if self.m.on_change:
            self.m.on_change()

    async def running(self, sid: int) -> bool:
        from sqlalchemy import text
        async with self.m.engine.connect() as c:
            return (await c.execute(text("SELECT 1 FROM loss_check WHERE session_id = :s AND status = 'running' LIMIT 1"),
                                    {"s": sid})).first() is not None

    async def start(self, row: Any) -> dict[str, Any]:
        from sqlalchemy import text
        from bridge import handoff as ho
        from bridge.inject import Refused
        if await self.running(row.id):
            raise Refused("이미 이 세션의 점검이 돌고 있습니다")
        path = row.transcript or ho.transcript_path(row.cwd or "", row.cc or "")
        if not path or not os.path.isfile(path):
            raise Refused("트랜스크립트를 찾지 못했습니다")
        repo = await ho.repo_root(row.cwd)
        if not repo:
            raise Refused("저장소를 찾지 못했습니다")
        async with self.m.engine.begin() as c:
            res = await c.execute(text("INSERT INTO loss_check (session_id, status, model) VALUES (:s, 'running', :m)"),
                                  {"s": row.id, "m": self.model})
        lid = res.lastrowid
        if self.m.on_change:
            self.m.on_change()
        self.m._spawn_task(self._run(lid, row, path, repo))
        return {"loss_check_id": lid, "status": "running", "model": self.model}

    async def _run(self, lid: int, row: Any, path: str, repo: str) -> None:
        try:
            await self._run_inner(lid, row, path, repo)
        except Exception as e:  # noqa: BLE001 — 어떤 실패든 running으로 남기지 않는다
            await self._save(lid, status="failed", error=f"{type(e).__name__}: {e}")
            self.m._notify(row, f"잃은 것 보기 실패 — {type(e).__name__}")

    async def _run_inner(self, lid: int, row: Any, path: str, repo: str) -> None:
        segs = await asyncio.to_thread(extract, path)
        if len(segs) < 2 or not any(s.prompts for s in segs[:-1]):
            await self._save(lid, status="failed", segments=len(segs), error="압축된 적이 없습니다 — 볼 것이 없습니다")
            return
        md = memory_dir(row.cwd or repo)
        claude_md = Path(repo, "CLAUDE.md")
        ctx = context_text(segs, claude_md.read_text(encoding="utf-8") if claude_md.is_file() else "",
                           {p.name: p.read_text(encoding="utf-8") for p in sorted(md.glob("*.md"))} if md.is_dir() else {})
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        wd = self.root / str(lid)
        names = await asyncio.to_thread(write_workdir, wd, segs, ctx)
        await self._save(lid, workdir=str(wd), segments=len(segs), prompts=sum(len(i) for _, i in names),
                         groups_total=len(names))

        async def progress(items: list[dict[str, Any]], runs: list[dict[str, Any]]) -> None:
            await self._save(lid, groups_done=len(runs), items=self.mask.deep(items), runs=_runs_view(runs),
                             cost_usd=round(sum(r["cost_usd"] or 0 for r in runs), 4))

        res = await self.judge(wd, names, len(segs) - 1, repo, f"lc{lid:04d}"[-6:], on_group=progress,
                               model=self.model, claude_bin=self.claude_bin)
        runs = res["runs"]
        bad = [r for r in runs if r["error"]]
        skipped = sum(len(r["skipped"]) for r in runs if not r["error"])
        cnt = summarize(res["items"])
        err = "; ".join(x for x in [f"묶음 {len(bad)}개 실패" if bad else "", f"건너뛴 프롬프트 {skipped}개" if skipped else ""] if x)
        status = "failed" if bad and len(bad) == len(runs) else "done"
        await self._save(lid, status=status, items=self.mask.deep(res["items"]), runs=_runs_view(runs),
                         groups_done=len(runs), cost_usd=round(sum(r["cost_usd"] or 0 for r in runs), 4), error=err or None)
        if status == "failed":
            self.m._notify(row, f"잃은 것 보기 실패 — {err}")
        else:
            self.m._notify(row, f"잃은 것 보기 끝 — 사라짐 {cnt.get('사라짐', 0)} · 약해짐 {cnt.get('약해짐', 0)}"
                                f"{' (' + err + ')' if err else ''} — 패널에서 보고 [옮길 것 뽑기]에 넣을 수 있습니다")

    async def list(self, sid: int, limit: int = 3) -> list[dict[str, Any]]:
        from sqlalchemy import text
        async with self.m.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, status, model, segments, prompts, groups_total, groups_done, items, runs, cost_usd, error, "
                "created_at, updated_at FROM loss_check WHERE session_id = :s ORDER BY id DESC LIMIT :n"),
                {"s": sid, "n": limit})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            items = json.loads(d.pop("items") or "[]")
            d["runs"] = json.loads(d["runs"] or "[]")
            d["counts"] = summarize(items)
            d["lost"] = [{k: x.get(k) for k in ("id", "kind", "status", "gist", "quote", "where", "dropped_at", "missing",
                                                "why_matters")} for x in lost(items)[:SHOW]]
            d["lost_total"] = len(lost(items))
            d["cost_usd"] = float(d["cost_usd"]) if d["cost_usd"] is not None else None
            for k in ("created_at", "updated_at"):
                d[k] = d[k].isoformat() + "Z" if d[k] else None
            out.append(d)
        return out

    async def items_of(self, lid: int) -> tuple[int, list[dict[str, Any]]] | None:
        """(session_id, items) — 끝난 점검만."""
        from sqlalchemy import text
        async with self.m.engine.connect() as c:
            r = (await c.execute(text("SELECT session_id, items FROM loss_check WHERE id = :i AND status = 'done'"),
                                 {"i": lid})).first()
        return (r[0], json.loads(r[1] or "[]")) if r else None


def _runs_view(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DB에 남길 묶음 기록 — usage 원본은 빼고 토큰 합만."""
    out = []
    for r in runs:
        u = r.get("usage") or {}
        out.append({k: r.get(k) for k in ("group", "prompts", "items", "empty", "skipped", "ms", "cost_usd", "error")}
                   | {"tokens": sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                                 "cache_creation_input_tokens"))})
    return out


def _main() -> None:
    """손으로 맞대 보기: python -m bridge.losscheck <트랜스크립트> <작업 폴더> <저장소> [--until ISO] [--base all.json]
    [--context current_context.md(정답과 같은 맥락으로)] [--model sonnet] [--extract-only]"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("workdir")
    ap.add_argument("repo")
    ap.add_argument("--until")
    ap.add_argument("--base")
    ap.add_argument("--context")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--extract-only", action="store_true")
    a = ap.parse_args()
    segs = extract(a.transcript, a.until)
    wd = Path(a.workdir)
    if a.context:
        ctx = Path(a.context).read_text(encoding="utf-8")
    else:
        md = memory_dir(a.repo)
        ctx = context_text(segs, (Path(a.repo) / "CLAUDE.md").read_text(encoding="utf-8"),
                           {p.name: p.read_text(encoding="utf-8") for p in sorted(md.glob("*.md"))} if md.is_dir() else {})
    names = write_workdir(wd, segs, ctx)
    print("구간", len(segs), "프롬프트", [len(s.prompts) for s in segs], "묶음", [(n, len(i)) for n, i in names])
    (wd / "segs.json").write_text(json.dumps([s.__dict__ for s in segs], ensure_ascii=False, indent=1), encoding="utf-8")
    if a.extract_only:
        return
    res = asyncio.run(judge_all(wd, names, len(segs) - 1, a.repo, "d0" + str(int(time.time()))[-4:], model=a.model))
    (wd / "all.json").write_text(json.dumps(res["items"], ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps([{k: v for k, v in r.items() if k != "usage"} for r in res["runs"]], ensure_ascii=False, indent=1))
    print("합계", round(sum(r["cost_usd"] or 0 for r in res["runs"]), 2), "달러",
          round(sum(r["ms"] for r in res["runs"]) / 60000, 1), "분")
    if a.base:
        base = json.loads(Path(a.base).read_text(encoding="utf-8"))
        cmp = compare(res["items"], base)
        (wd / "compare.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in cmp.items() if k != "flipped"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    _main()
