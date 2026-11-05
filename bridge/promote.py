"""인계 2판 ① 문서로 옮기기(11-05, docs/11_handoff_v2.md 2장 ①).

넘기기 전에, 이 대화에서 정했지만 아직 문서에 없는 결정 · 금지 · 기준 · 선호 · 미완을 문서로 옮긴다.
1/2 목록 — 브리지가 세션에 요청을 넣으면 세션이 JSON 목록을 낸다(무엇 · 원문 · 어디로 · 왜). 그 세션이 받은(또는 쓴) 2판
         인계가 있으면 그 「문서와 다른 지금」 절을 같이 넣는다 — 인계에 적힌 "문서로 옮길 것"이 여기로 들어온다.
사람    — 패널에서 목적지 · 문장을 고치고, 항목마다 승인 · 빼기를 고른다.
2/2 쓰기 — 승인한 것만 세션에 보내 쓰고 커밋하게 한다(`인계 전 결정 기록: …`). 세션이 그 일을 했는지는 브리지가 git으로
         확인한다 — 커밋이 있나, 메시지 머리, 승인한 파일만 바뀌었나. 어긋나면 write_failed + 알림(조용히 빠지지 않게).

요청 머리는 인계 요청과 같은 `[FOREMAN 인계 요청 r=X]` — 조립기가 이 턴을 origin=handoff로 달아 보통 응답 · 알림과 가른다.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import text

from bridge import handoff as ho
from bridge import pointers as ptr
from bridge.inject import Refused, deliver, resolve
from bridge.liveness import live_sessions

KINDS = ("결정", "금지", "기준", "선호", "미완")
STATES = ("pending", "approved", "dropped")
SPECIAL_DEST = ("memory", "drop")
COMMIT_HEAD = "인계 전 결정 기록"
MAX_ITEMS = 60
DIFF_SECTION = "문서와 다른 지금"

LIST_PROMPT = """{head} 문서로 옮기기 1/2 — 목록만
이 세션을 넘기기 전에, 이 대화에서 정했지만 아직 저장소 문서 · 메모리에 없는 것을 문서로 옮기려 한다. 이번에는 **목록만** 만든다.

- 파일을 고치거나 커밋하지 마라. 이미 문서에 있는지 확인하려고 읽기 · grep은 해도 된다(이미 있으면 목록에서 뺀다)
- 대상: 사용자가 정한 결정 · 금지 · 기준 · 선호, 끝나지 않은 일. 이미 끝난 일 · 그때뿐인 지시는 뺀다
- 항목마다
  - kind: 결정 | 금지 | 기준 | 선호 | 미완
  - what: 문서에 들어갈 한두 문장(그 문서 문체로)
  - quote: 사용자 말 그대로(없으면 빈 글)
  - dest: 저장소 맨 위 기준 .md 경로(예: CLAUDE.md, docs/11_handoff.md) · "memory"(사람의 작업 선호 — CC 메모리) · "drop"(그때뿐이라 버림)
  - section: 그 파일의 절 제목(있는 절이면 글자 그대로, 없으면 새 이름). memory · drop이면 빈 글
  - why: 왜 거기인지 한 줄. CLAUDE.md는 꼭 지킬 것만 짧게, 상세는 docs
{extra}- 아래 모양 그대로, 마지막 응답에 한 번만 써라(JSON 배열, 표지 줄 두 개를 글자 그대로). 없으면 빈 배열 []:

<<<FOREMAN-PROMOTE r={r}>>>
[{{"kind": "결정", "what": "…", "quote": "…", "dest": "CLAUDE.md", "section": "작업 규칙", "why": "…"}}]
<<<END r={r}>>>"""

EXTRA_DIFF = """- 아래는 이 일의 인계(#{sid})에 적힌 「{sec}」 절이다. 여기 있는 것도 하나씩 판단해 목록에 넣어라(이미 문서에 있으면 뺀다):
{body}
"""

WRITE_PROMPT = """{head} 문서로 옮기기 2/2 — 승인한 것만 쓰기
사람이 패널에서 고치고 승인한 항목이 아래에 있다. **이것만** 써라.

- 항목마다 dest 파일의 section 절에 넣는다. 그 문서의 문체 · 짧기를 따르고, 비슷한 줄이 이미 있으면 고쳐 합친다. 절이 없으면 맞는 자리에 만든다
- dest가 memory인 항목은 CC 지속 메모리 규칙대로 쓴다(파일 하나 + MEMORY.md 한 줄)
- 목록에 없는 파일은 고치지 마라. 저장소 파일은 아래 dest만 `git add`해서 커밋 하나로 묶는다. 메시지 첫 줄은 `{commit_head}: <요지>`
- push는 이 저장소 CLAUDE.md 규칙을 따른다(worktree 세션이면 push하지 않는다)
- 못 쓴 항목이 있으면 skipped에 id와 이유를 적는다
- 끝나면 마지막 응답에 한 번만 써라(표지 줄 두 개를 글자 그대로):

<<<FOREMAN-PROMOTED r={r}>>>
{{"commit": "<커밋 해시, 저장소 파일이 없으면 빈 글>", "files": ["CLAUDE.md"], "memory": ["<메모리 파일 절대 경로>"], "skipped": [{{"id": 3, "why": "…"}}]}}
<<<END r={r}>>>

항목:
{items}"""


def block_re(tag: str, req: str) -> re.Pattern[str]:
    return re.compile(rf"<<<{tag} r={req}>>>[ \t]*\n(.*?)\n[ \t]*<<<END r={req}>>>", re.S)


def extract(texts: str, tag: str, req: str) -> str | None:
    found = block_re(tag, req).findall(texts or "")
    return found[-1].strip() if found else None


def diff_section(body: str | None) -> str | None:
    """2판 인계 본문의 「문서와 다른 지금」 절(다음 ## 전까지). 비었거나 "없음"이면 None."""
    for h, t in ho._sections(body or ""):
        if h == DIFF_SECTION:
            t = t.strip()
            return t if t and t not in ("없음", "- 없음") else None
    return None


def list_prompt(req: str, diff: str | None = None, summary_id: int | None = None) -> str:
    extra = EXTRA_DIFF.format(sid=summary_id, sec=DIFF_SECTION,
                              body="\n".join("  > " + ln for ln in diff.splitlines())) if diff else ""
    return LIST_PROMPT.format(head=ho.REQ_HEAD.format(r=req), r=req, extra=extra)


def write_prompt(req: str, items: list[dict[str, Any]]) -> str:
    keep = [{k: it.get(k) for k in ("id", "kind", "what", "quote", "dest", "section")} for it in items]
    return WRITE_PROMPT.format(head=ho.REQ_HEAD.format(r=req), r=req, commit_head=COMMIT_HEAD,
                               items=json.dumps(keep, ensure_ascii=False, indent=1))


def _s(v: Any, n: int) -> str:
    return (v if isinstance(v, str) else "" if v is None else str(v)).strip()[:n]


def parse_items(body: str) -> list[dict[str, Any]]:
    """세션이 낸 JSON 배열 → 고른 칸만, id를 1부터. 모양이 틀리면 Refused(원문은 raw에 남는다)."""
    try:
        data = json.loads(body)
    except ValueError as e:
        raise Refused(f"목록이 JSON이 아닙니다: {e}") from None
    if not isinstance(data, list):
        raise Refused("목록이 배열이 아닙니다")
    out = []
    for d in data[:MAX_ITEMS]:
        if not isinstance(d, dict) or not _s(d.get("what"), 10):
            continue
        dest = _s(d.get("dest"), 255) or "drop"
        out.append({"id": len(out) + 1, "kind": _s(d.get("kind"), 8) if _s(d.get("kind"), 8) in KINDS else "결정",
                    "what": _s(d.get("what"), 2000), "quote": _s(d.get("quote"), 2000), "dest": dest,
                    "section": "" if dest in SPECIAL_DEST else _s(d.get("section"), 200),
                    "why": _s(d.get("why"), 500), "state": "dropped" if dest == "drop" else "pending"})
    return out


def check_dest(item: dict[str, Any], repo: str | None) -> dict[str, Any]:
    """목적지 확인 — {ok, problem, note}. 막는 것: 저장소 밖 · .md 아님 · 저장소 모름. 알리기만: 새 파일 · 새 절."""
    dest = (item.get("dest") or "").strip()
    if dest in SPECIAL_DEST:
        return {"ok": True, "problem": None, "note": None}
    if not dest:
        return {"ok": False, "problem": "목적지가 비었습니다", "note": None}
    if not repo:
        return {"ok": False, "problem": "저장소를 찾지 못했습니다", "note": None}
    p = PurePosixPath(dest)
    if p.is_absolute() or ".." in p.parts or dest.startswith("~"):
        return {"ok": False, "problem": "저장소 맨 위 기준 경로만 됩니다", "note": None}
    if p.suffix.lower() != ".md":
        return {"ok": False, "problem": "문서(.md)만 됩니다", "note": None}
    f = Path(repo) / dest
    if not f.is_file():
        return {"ok": True, "problem": None, "note": "새 파일입니다"}
    sec = (item.get("section") or "").strip()
    if sec:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return {"ok": False, "problem": "읽을 수 없습니다", "note": None}
        if not any(ln.startswith("#") and sec in ln for ln in lines):
            return {"ok": True, "problem": None, "note": "새 절입니다"}
    return {"ok": True, "problem": None, "note": None}


def merge_edits(items: list[dict[str, Any]], edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """사람이 고친 칸(what · dest · section · state)만 받는다. 원문 · 종류 · 이유는 세션이 낸 그대로."""
    by = {e.get("id"): e for e in edits if isinstance(e, dict)}
    out = []
    for it in items:
        e = by.get(it["id"])
        it = dict(it)
        if e:
            if isinstance(e.get("what"), str) and e["what"].strip():
                it["what"] = e["what"].strip()[:2000]
            if isinstance(e.get("dest"), str):
                it["dest"] = e["dest"].strip()[:255] or "drop"
                if it["dest"] in SPECIAL_DEST:
                    it["section"] = ""
            if isinstance(e.get("section"), str) and it["dest"] not in SPECIAL_DEST:
                it["section"] = e["section"].strip()[:200]
            if e.get("state") in STATES:
                it["state"] = e["state"]
        if it["dest"] == "drop" and it["state"] == "approved":
            it["state"] = "dropped"
        out.append(it)
    return out


async def verify(repo: str, base: str, out: dict[str, Any] | None, approved: list[dict[str, Any]],
                 since_ts: float) -> dict[str, Any]:
    """세션이 승인한 것만 썼나 — git으로 본다. 세션이 낸 결과 블록이 없어도 base 뒤 커밋 중 머리가 맞는 것을 찾는다."""
    problems: list[str] = []
    want = sorted({it["dest"] for it in approved if it["dest"] not in SPECIAL_DEST})
    mem_want = any(it["dest"] == "memory" for it in approved)
    out = out or {}
    commit = _s(out.get("commit"), 40)
    if want:
        if commit:
            full = await ptr._git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
            if not full:
                problems.append(f"세션이 알린 커밋 {commit[:10]}이 저장소에 없습니다")
                commit = ""
            else:
                commit = full
        if not commit:
            log = await ptr._git(repo, "log", "--format=%H %s", f"{base}..HEAD")
            hits = [ln.split(" ", 1)[0] for ln in log.splitlines() if ln.split(" ", 1)[-1].startswith(COMMIT_HEAD)]
            commit = hits[0] if hits else ""
        if not commit:
            problems.append(f"「{COMMIT_HEAD}」 커밋이 없습니다")
    files: list[str] = []
    if commit:
        if not await _is_ancestor(repo, base, commit) or commit == base:
            problems.append("쓰기 요청 전의 커밋입니다")
        subj = await ptr._git(repo, "log", "-1", "--format=%s", commit)
        if not subj.startswith(COMMIT_HEAD):
            problems.append(f"커밋 메시지 머리가 「{COMMIT_HEAD}」가 아닙니다")
        files = [f for f in (await ptr._git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit)).splitlines() if f]
        extra = [f for f in files if f not in want]
        if extra:
            problems.append("승인하지 않은 파일도 바뀌었습니다: " + ", ".join(extra))
        miss = [f for f in want if f not in files]
        skipped_ids = {s.get("id") for s in out.get("skipped") or [] if isinstance(s, dict)}
        miss_unexplained = [f for f in miss if not all(it["id"] in skipped_ids for it in approved if it["dest"] == f)]
        if miss_unexplained:
            problems.append("승인했는데 커밋에 없는 파일: " + ", ".join(miss_unexplained))
    memory = [m for m in out.get("memory") or [] if isinstance(m, str)]
    if mem_want:
        fresh = [m for m in memory if os.path.isfile(m) and os.path.getmtime(m) >= since_ts - 1]
        if not fresh:
            problems.append("메모리 항목을 승인했는데 새로 쓴 메모리 파일이 없습니다")
    return {"ok": not problems, "problems": problems, "commit": commit or None, "files": files,
            "memory": memory, "skipped": [s for s in out.get("skipped") or [] if isinstance(s, dict)]}


async def _is_ancestor(repo: str, a: str, b: str) -> bool:
    proc = await asyncio.create_subprocess_exec("git", "-C", repo, "merge-base", "--is-ancestor", a, b,
                                                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    return await proc.wait() == 0


class Promoter:
    """HandoffManager에 붙어 DB · 입력 경로 · 알림을 같이 쓴다(main.py가 handoff.promote로 넣는다)."""

    def __init__(self, m: Any) -> None:
        self.m = m
        self.wait_s = ho.WAIT_S

    # ── 조회 ────────────────────────────────────────────
    async def list(self, sid: int, limit: int = 5) -> list[dict[str, Any]]:
        async with self.m.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, summary_id, req, status, items, commit_sha, result, error, raw, created_at, updated_at "
                "FROM promotion WHERE session_id = :s ORDER BY id DESC LIMIT :n"), {"s": sid, "n": limit})).mappings().all()
        row = await self.m.session(sid)
        repo = await ho.repo_root(row.cwd if row else None)
        out = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"]) if d["items"] else []
            d["result"] = json.loads(d["result"]) if d["result"] else None
            for it in d["items"]:
                it["check"] = check_dest(it, repo)
            for k in ("created_at", "updated_at"):
                d[k] = d[k].isoformat() + "Z" if d[k] else None
            d["raw"] = (d["raw"] or "")[-4000:] if d["status"] in ("failed", "timeout") else None
            out.append(d)
        return out

    async def get(self, pid: int) -> dict[str, Any] | None:
        async with self.m.engine.connect() as c:
            r = (await c.execute(text("SELECT * FROM promotion WHERE id = :i"), {"i": pid})).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["items"] = json.loads(d["items"]) if d["items"] else []
        return d

    async def inputs(self, row: ho.SessionRow, limit: int = 5) -> list[dict[str, Any]]:
        """같이 넣을 수 있는 인계 — 「문서와 다른 지금」이 있는 2판만. 이 세션이 받은 것 → 이 세션이 쓴 것 → 같은 프로젝트 순.
        같은 프로젝트까지 보는 이유: 인계를 받은 세션이 끝난 뒤(worktree를 합치려면 끝내야 한다) 다른 세션에서 옮길 수 있게."""
        async with self.m.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT s.id, s.body, s.created_at, COALESCE(cs.custom_title, cs.title) AS title, cs.cc_session_id, "
                "(s.injected_cc_session = :c) AS got, (s.session_id = :s) AS own "
                "FROM summary s JOIN character_session cs ON cs.id = s.session_id "
                "LEFT JOIN `character` ch ON ch.id = cs.character_id "
                "WHERE s.status = 'ok' AND s.body IS NOT NULL AND (s.injected_cc_session = :c OR s.session_id = :s OR "
                " (ch.project_id IS NOT NULL AND ch.project_id = (SELECT project_id FROM `character` WHERE id = :ch))) "
                "ORDER BY got DESC, own DESC, s.id DESC LIMIT 30"),
                {"c": row.cc or "", "s": row.id, "ch": row.character_id or 0})).mappings().all()
        out = []
        for r in rows:
            if not ptr.is_v2(r["body"]) or not (d := diff_section(r["body"])):
                continue
            out.append({"id": r["id"], "title": r["title"], "cc": (r["cc_session_id"] or "")[:8],
                        "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
                        "why": "이 세션이 받은 인계" if r["got"] else "이 세션이 쓴 인계" if r["own"] else "같은 프로젝트의 인계",
                        "diff": d[:600]})
            if len(out) >= limit:
                break
        return out

    async def _input_body(self, summary_id: int) -> str:
        async with self.m.engine.connect() as c:
            r = (await c.execute(text("SELECT body FROM summary WHERE id = :i AND status = 'ok'"), {"i": summary_id})).first()
        d = diff_section(r[0]) if r and ptr.is_v2(r[0]) else None
        if not d:
            raise Refused(f"인계 #{summary_id}에 「{DIFF_SECTION}」 절이 없습니다")
        return d

    async def _busy(self, sid: int) -> bool:
        async with self.m.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT 1 FROM promotion WHERE session_id = :s AND status IN ('requested', 'writing') "
                "AND updated_at > NOW(3) - INTERVAL 15 MINUTE LIMIT 1"), {"s": sid})).first()
        return bool(r)

    async def _save(self, pid: int, **kw: Any) -> None:
        cols = ", ".join(f"{k} = :{k}" for k in kw)
        for k in ("items", "result"):
            if k in kw and not isinstance(kw[k], str) and kw[k] is not None:
                kw[k] = json.dumps(kw[k], ensure_ascii=False)
        if "raw" in kw and kw["raw"]:
            kw["raw"] = kw["raw"][-200000:]
        if "error" in kw and kw["error"]:
            kw["error"] = kw["error"][:512]
        async with self.m.engine.begin() as c:
            await c.execute(text(f"UPDATE promotion SET {cols} WHERE id = :pid"), {**kw, "pid": pid})
        if self.m.on_change:
            self.m.on_change()

    async def _send(self, row: ho.SessionRow, prompt: str) -> tuple[str, int, str | None]:
        """보내고 (트랜스크립트 경로, 보내기 전 크기, prompt_id). 받지 못하면 Refused."""
        if not row.cc:
            raise Refused("CC 세션 ID가 없습니다")
        _t, _ls, busy = await resolve(row.cc, self.m.sessions_dir)
        if busy:
            raise Refused("작업 중입니다. 작업이 끝난 뒤에 해 주세요(중간에 끼면 작업과 섞입니다)")
        path = row.transcript or ho.transcript_path(row.cwd or "", row.cc)
        offset = os.path.getsize(path) if os.path.exists(path) else 0
        res = await deliver(row.cc, prompt, sessions_dir=self.m.sessions_dir, transcript=path)
        if not res.get("delivered"):
            raise Refused("제출이 확인되지 않았습니다 — 입력 칸에 남았을 수 있습니다")
        return path, offset, (res["delivered"] or {}).get("prompt_id")

    async def _wait(self, row: ho.SessionRow, tag: str, req: str, path: str, offset: int,
                    prompt_id: str | None) -> tuple[str | None, str, str | None]:
        """(블록, 원문, 실패 이유). 턴이 닫혔는데 블록이 없거나 · 세션이 끝났거나 · 시간이 지나면 이유를 낸다."""
        loop = asyncio.get_running_loop()
        end, ended_seen, texts = loop.time() + self.wait_s, None, ""
        while loop.time() < end:
            await asyncio.sleep(2.0)
            texts = ho.assistant_text(path, offset)
            if (body := extract(texts, tag, req)) is not None:
                return body, texts, None
            if prompt_id and ended_seen is None:
                t = await self.m._turn_of(prompt_id)
                if t and await self.m._turn_ended(t):
                    ended_seen = loop.time()
            if ended_seen and loop.time() - ended_seen > 6:
                return None, texts, "턴이 끝났는데 표지가 없습니다"
            if row.cc and row.cc not in live_sessions(self.m.sessions_dir):
                return None, texts, "기다리는 중에 세션이 끝났습니다"
        return None, ho.assistant_text(path, offset), f"{self.wait_s:.0f}초 안에 돌아오지 않았습니다"

    # ── 1/2 목록 ────────────────────────────────────────
    async def request(self, row: ho.SessionRow, summary_id: int | None = None, no_input: bool = False) -> dict[str, Any]:
        """summary_id를 주면 그 인계를, 안 주면 inputs()의 첫째를 같이 넣는다. no_input이면 넣지 않는다."""
        if await self._busy(row.id) or await self.m._pending(row.id):
            raise Refused("이미 이 세션에 인계 · 옮기기 요청을 기다리는 중입니다")
        diff = None
        if no_input:
            summary_id = None
        elif summary_id is not None:
            diff = await self._input_body(summary_id)
        elif cand := await self.inputs(row, 1):
            summary_id = cand[0]["id"]
            diff = await self._input_body(summary_id)
        req = ho.new_req()
        async with self.m.engine.begin() as c:
            res = await c.execute(text(
                "INSERT INTO promotion (session_id, summary_id, req, status) VALUES (:s, :sm, :r, 'requested')"),
                {"s": row.id, "sm": summary_id, "r": req})
        pid = res.lastrowid
        try:
            path, offset, prompt_id = await self._send(row, list_prompt(req, diff, summary_id))
        except Refused as e:
            await self._save(pid, status="failed", error=f"보내지 못함: {e}")
            raise
        self.m._spawn_task(self._wait_list(row, pid, req, path, offset, prompt_id))
        return {"promotion_id": pid, "req": req, "status": "requested", "summary_id": summary_id}

    async def _wait_list(self, row: ho.SessionRow, pid: int, req: str, path: str, offset: int, prompt_id: str | None) -> None:
        body, texts, why = await self._wait(row, "FOREMAN-PROMOTE", req, path, offset, prompt_id)
        if body is None:
            await self._save(pid, status="timeout" if "초 안에" in (why or "") else "failed", raw=texts, error=why)
            self.m._notify(row, f"문서로 옮기기 목록 실패 — {why}")
            return
        try:
            items = parse_items(body)
        except Refused as e:
            await self._save(pid, status="failed", raw=texts, error=str(e))
            self.m._notify(row, f"문서로 옮기기 목록 실패 — {e}")
            return
        await self._save(pid, status="listed", items=items, raw=texts)
        self.m._notify(row, f"문서로 옮길 것 {len(items)}개 — 패널에서 고치고 승인해 주세요")

    # ── 사람 ────────────────────────────────────────────
    async def edit(self, pid: int, edits: list[dict[str, Any]]) -> dict[str, Any]:
        p = await self.get(pid)
        if not p:
            raise Refused("옮기기 목록이 없습니다")
        if p["status"] not in ("listed", "write_failed"):
            raise Refused("지금은 고칠 수 없습니다(목록을 받은 뒤 · 쓰기 전에만 고칩니다)")
        items = merge_edits(p["items"], edits)
        await self._save(pid, items=items)
        return {"promotion_id": pid, "items": len(items), "approved": sum(it["state"] == "approved" for it in items)}

    # ── 2/2 쓰기 ────────────────────────────────────────
    async def write(self, pid: int) -> dict[str, Any]:
        p = await self.get(pid)
        if not p:
            raise Refused("옮기기 목록이 없습니다")
        if p["status"] not in ("listed", "write_failed"):
            raise Refused("쓸 수 있는 상태가 아닙니다")
        row = await self.m.session(p["session_id"])
        if not row:
            raise Refused("세션이 없습니다")
        approved = [it for it in p["items"] if it["state"] == "approved"]
        if not approved:
            raise Refused("승인한 항목이 없습니다")
        repo = await ho.repo_root(row.cwd)
        bad = [(it, ck) for it in approved if not (ck := check_dest(it, repo))["ok"]]
        if bad:
            raise Refused("목적지가 틀렸습니다 — " + "; ".join(f"#{it['id']} {it['dest']}: {ck['problem']}" for it, ck in bad))
        if await self._busy(row.id) or await self.m._pending(row.id):
            raise Refused("이미 이 세션에 인계 · 옮기기 요청을 기다리는 중입니다")
        base = await ptr._git(repo or "", "rev-parse", "HEAD")
        if not base:
            raise Refused("저장소 HEAD를 읽지 못했습니다")
        req = ho.new_req()
        await self._save(pid, status="writing", write_req=req, base_head=base, error=None, result=None, commit_sha=None)
        wall = time.time()          # 메모리 파일이 이 뒤에 쓰였나를 본다
        try:
            path, offset, prompt_id = await self._send(row, write_prompt(req, approved))
        except Refused as e:
            await self._save(pid, status="write_failed", error=f"보내지 못함: {e}")
            raise
        self.m._spawn_task(self._wait_write(row, pid, req, path, offset, prompt_id, repo or "", base, approved, wall))
        return {"promotion_id": pid, "req": req, "status": "writing", "approved": len(approved)}

    async def _wait_write(self, row: ho.SessionRow, pid: int, req: str, path: str, offset: int, prompt_id: str | None,
                          repo: str, base: str, approved: list[dict[str, Any]], wall: float) -> None:
        body, texts, why = await self._wait(row, "FOREMAN-PROMOTED", req, path, offset, prompt_id)
        out = None
        if body is not None:
            try:
                out = json.loads(body)
            except ValueError:
                out = None
            if not isinstance(out, dict):
                out, why = None, "결과 블록이 JSON 객체가 아닙니다"
        res = await verify(repo, base, out, approved, wall)
        if why and body is None:
            res["problems"].insert(0, f"결과 블록 없음 — {why}")
            res["ok"] = False
        await self._save(pid, status="written" if res["ok"] else "write_failed", result=res, commit_sha=res["commit"],
                         raw=texts, error=None if res["ok"] else "; ".join(res["problems"])[:512])
        if res["ok"]:
            self.m._notify(row, f"문서로 옮기기 끝 — {len(approved)}개, 커밋 {(res['commit'] or '없음')[:8]}")
        else:
            self.m._notify(row, "문서로 옮기기 확인 실패 — " + "; ".join(res["problems"])[:300])
