"""기술 문서(docs/*.md) → Notion [기술문서] 맞추기(11-09, 런슈즈 요청 2 · 3절).

- 원본은 git, Notion은 사본이다. 기준은 push된 것(origin/main) — Notion은 GitHub에 있는 것의 사본이다
- 뒤처짐을 센다(LLM 없음): 파일마다 지문(content_digest) ↔ 게시 기록, 커밋 수는 마지막으로 다 맞춘 커밋(@docs-sync 행) ↔ ref
- docs_mode = "auto"면 docs 커밋 뒤 quiet_min분 조용해지면 바뀐 파일만 갈아 끼운다. 실패하거나 사람이 Notion에서 고친 블록이 있으면
  덮지 않고 알린다(텔레그램 · 서기 할 일) — 뒤처짐은 그대로 남아 보인다(조용히 낡지 않게)
- docs/ 바로 아래 .md만. 하위 폴더(docs/archive/ — 런슈즈 docs/README "노션 · 발표 자료에 옮기지 않는다")는 올리지 않는다
- 차례: docs/README.md 표에 나온 순서(README가 맨 앞), 표에 없는 파일은 이름순으로 뒤에
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from bridge.notion import HumanEdited, OutOfScope, content_digest, first_h1, git_show

log = logging.getLogger("foreman.docsync")

MARK = "@docs-sync"          # doc_publish 행 — commit_sha = 마지막으로 다 맞춘 ref 커밋(전체 해시)
# 11-09 하위 폴더도 읽는다(펫퍼민트 docs/02_pipeline/ — Notion 하위 페이지 구조를 따라). 빼는 것은 경로 앞부분으로:
# docs/archive/는 늘(런슈즈 docs/README "노션 · 발표 자료에 옮기지 않는다"), 프로젝트 skip의 "…/"로 끝나는 항목은 폴더 통째로
DOCS_SPEC = ":(glob)docs/**/*.md"
ALWAYS_SKIP = ("docs/archive/",)


def skipped(path: str, skip: Any = ()) -> bool:
    """대상이 아닌가 — 파일 이름 그대로 또는 "…/"로 끝나는 폴더 아래."""
    rules = (*ALWAYS_SKIP, *(skip or ()))
    return any(path == r or (r.endswith("/") and path.startswith(r)) for r in rules)


def _git(repo: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
    return r.stdout if r.returncode == 0 else ""


def docs_files(repo: str, ref: str, skip: Any = ()) -> list[str]:
    """ref에 있는 docs/ 아래 .md(하위 폴더 포함, docs/archive/ · skip 빼고), docs/README.md 표 순서로."""
    raw = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", "--name-only", ref, "docs/"],
                         capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
    files = [f for f in raw.split("\0") if f.endswith(".md") and not skipped(f, skip)]
    return order(files, _git(repo, "show", f"{ref}:docs/README.md"))


def table_rows(readme: str) -> list[tuple[str, str]]:
    """docs/README.md 표의 (docs/파일, 설명) — 첫 칸에 `x.md`가 있는 줄만, 나온 순서대로(본문에서 먼저 언급된 이름은 보지 않는다 —
    11-09 런슈즈 README 본문이 overview를 requirements보다 먼저 말해 차례가 틀렸다)."""
    out = []
    for ln in readme.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.lstrip().startswith("|") else []
        m = re.fullmatch(r"`([^`/\s]+\.md)`", cells[0]) if cells else None
        if m and not any(f == f"docs/{m.group(1)}" for f, _ in out):
            out.append((f"docs/{m.group(1)}", cells[1] if len(cells) > 1 else ""))
    return out


def order(files: list[str], readme: str) -> list[str]:
    named = [f for f, _ in table_rows(readme) if f in files]
    head = ["docs/README.md"] if "docs/README.md" in files else []
    return head + [p for p in named if p not in head] + sorted(p for p in files if p not in named and p not in head)


def _head(desc: str) -> str:
    """괄호 밖의 첫 " — " 앞 — "비교 페이지(설계안 — 결정 전)"을 "비교 페이지(설계안"으로 자르지 않게(11-09)."""
    depth = 0
    for i, ch in enumerate(desc):
        depth += ch in "(（["
        depth -= ch in ")）]" and depth > 0
        if depth == 0 and desc.startswith(" — ", i):
            return desc[:i]
    return desc


def titles(files: list[str], readme: str) -> dict[str, str]:
    """Notion 페이지 제목(11-09 정함) — "파일 이름 — README 표 설명의 앞부분"(런슈즈 docs는 H1이 없고 첫 줄이 "> 상태: …"다).
    표에 없으면 파일 이름만. 설명 앞부분 = 첫 " — " 앞, 백틱 · 굵게 표시는 뗀다."""
    desc = {f: re.sub(r"[`*]", "", _head(d)).strip() for f, d in table_rows(readme)}
    out = {}
    for f in files:
        stem = f.rsplit("/", 1)[-1][:-3]
        out[f] = f"{stem} — {desc[f]}" if desc.get(f) else stem
    return out


def ref_sha(repo: str, ref: str) -> str | None:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip() or None


def last_docs_commit(repo: str, ref: str) -> datetime | None:
    ts = _git(repo, "log", "-1", "--format=%ct", ref, "--", DOCS_SPEC).strip()
    return datetime.fromtimestamp(int(ts), UTC).replace(tzinfo=None) if ts.isdigit() else None


def commits_behind(repo: str, synced: str | None, ref: str) -> int | None:
    """마지막으로 다 맞춘 커밋 뒤로 docs를 바꾼 커밋 수. 맞춘 적이 없으면 None."""
    if not synced:
        return None
    n = _git(repo, "rev-list", "--count", f"{synced}..{ref}", "--", DOCS_SPEC).strip()
    return int(n) if n.isdigit() else None


async def status(pub: Any) -> dict[str, Any]:
    """한 프로젝트의 기술 문서 상태 — new · changed · deleted 파일, 뒤처진 커밋 수, 마지막 docs 커밋 시각."""
    files = docs_files(pub.repo, pub.ref, getattr(pub, "skip", ()))     # 대상이 아닌 파일 · 폴더(11-09 펫퍼민트)
    names = titles(files, _git(pub.repo, "show", f"{pub.ref}:docs/README.md"))
    async with pub.e.connect() as c:
        rows = {r["path"]: dict(r) for r in (await c.execute(text(
            "SELECT path, status, title, content_hash, commit_sha, notion_page_id, url FROM doc_publish "
            "WHERE project = :p AND (path LIKE 'docs/%' OR path = :m)"), {"p": pub.project, "m": MARK})).mappings().all()}
    new, changed, broken, h1_missing = [], [], [], []
    for f in files:
        r = rows.get(f)
        try:
            body, _ = git_show(pub.repo, f, pub.ref)
            dg = content_digest(pub.repo, f, body, pub.ref)
        except (FileNotFoundError, OutOfScope) as e:
            broken.append({"path": f, "error": str(e)})
            continue
        if getattr(pub, "h1_title", False):                          # title = "h1"(11-12): 제목 = 첫 H1. 없으면 README 표 제목 그대로
            h1 = first_h1(body)[1]
            if h1:
                names[f] = h1                                        # H1이 바뀌면 아래 r["title"] != names[f]로 changed가 된다
            else:
                h1_missing.append(f)
                log.warning("첫 H1이 없어 README 표 제목을 씁니다(%s): %s", pub.project, f)
        if getattr(pub, "keep_title", False) and r:
            names[f] = r["title"]                                    # 제목 유지(사람이 붙인 "00. 모델 준비" — 사이드바 순서)
        if not r or r["status"] != "published":
            new.append(f)
        elif r["content_hash"] != dg or r["title"] != names[f]:      # 제목만 바뀌어도(README 표 설명) 맞춘다
            changed.append(f)
    deleted = [p for p, r in rows.items() if p.startswith("docs/") and r["status"] == "published" and p not in files]
    mark = rows.get(MARK) or {}
    return {"project": pub.project, "mode": pub.docs_mode, "ref": pub.ref, "ref_sha": ref_sha(pub.repo, pub.ref),
            "files": files, "titles": names, "new": new, "changed": changed, "deleted": deleted, "broken": broken,
            "h1_missing": h1_missing,      # title = "h1"인데 첫 H1이 없어 README 표 제목을 쓴 파일(서기 할 일에 한 줄)
            "synced": mark.get("commit_sha"), "behind_commits": commits_behind(pub.repo, mark.get("commit_sha"), pub.ref),
            "last_commit_at": last_docs_commit(pub.repo, pub.ref)}


def behind(st: dict[str, Any]) -> int:
    return len(st["new"]) + len(st["changed"]) + len(st["deleted"])


async def sync(pub: Any, when: str, force: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    """바뀐 파일만 올리고, 지워진 원본의 페이지는 휴지통으로, 새 페이지가 생겼으면 차례를 다시 세운다.
    사람이 Notion에서 고친 페이지는 덮지 않는다(force에 든 경로만 덮는다). 하나라도 막히면 @docs-sync를 옮기지 않는다 — 뒤처짐이 남는다."""
    st = await status(pub)
    done, held, failed = [], [], []
    for f in st["new"] + st["changed"]:
        try:
            r = await pub.publish(f, when, force=f in force, title=st.get("titles", {}).get(f))
            done.append({"path": f, "action": r["action"]})
        except HumanEdited as e:
            held.append({"path": f, "edits": e.edits[:5], "count": len(e.edits), "url": e.url})
        except OutOfScope as e:                          # 게시기가 일부러 막은 것 — 사유 글 그대로(알림에 "OutOfScope:"를 붙이지 않게)
            failed.append({"path": f, "error": str(e)[:200]})
        except Exception as e:  # noqa: BLE001 — 파일 하나가 막혀도 나머지는 올린다
            failed.append({"path": f, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    for f in st["deleted"]:
        if not getattr(pub, "create", True) or not getattr(pub, "archive_ok", True):
            # 11-09 — 사람이 옮겨 둔 페이지에 맞추는 프로젝트는 원본이 사라져도 휴지통으로 보내지 않는다(create = false 또는
            # archive = false — 사용자: 새 페이지 만들기와 옛 페이지 지우기는 다른 기능, 지운 문서는 실패로만 남기고 사람이 판단).
            # 경로만 바뀐 것(git mv)이면 짝을 새 경로로 옮기면 풀린다. 그냥 옮겼으면 펫퍼민트 20쪽이 모두 휴지통으로 갈 뻔했다
            failed.append({"path": f, "error": "원본이 사라졌습니다 — 이 프로젝트는 휴지통으로 보내지 않습니다(archive = false). "
                                               "경로가 바뀌었으면 짝(doc_publish)을 새 경로로 옮겨 주세요"})
            continue
        try:
            await pub.archive(f)
            done.append({"path": f, "action": "archived"})
        except Exception as e:  # noqa: BLE001
            failed.append({"path": f, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    failed += [{"path": b["path"], "error": b["error"]} for b in st["broken"]]
    if done and pub.docs_page and not getattr(pub, "keep_order", False):   # 차례가 이미 맞으면 reorder가 옮기지 않는다. keep_order면 사람 차례 그대로
        async with pub.e.connect() as c:
            pages = {r[0]: r[1] for r in (await c.execute(text(
                "SELECT path, notion_page_id FROM doc_publish WHERE project = :p AND kind = 'doc' AND status = 'published' "
                "AND path LIKE 'docs/%'"), {"p": pub.project})).all()}
        try:
            await pub.reorder([(f, pages[f]) for f in st["files"] if f in pages], pub.docs_page)
        except Exception as e:  # noqa: BLE001 — 차례가 틀려도 내용은 맞다
            failed.append({"path": "(차례)", "error": f"{type(e).__name__}: {str(e)[:200]}"})
    if not held and not failed and st["ref_sha"]:
        await pub._save(MARK, kind="mark", title="기술문서 맞춘 커밋", commit_sha=st["ref_sha"], status="published", error=None)
    return {"project": pub.project, "ref_sha": st["ref_sha"], "done": done, "held": held, "failed": failed}


class DocSync:
    """docs_mode = auto인 프로젝트를 주기적으로 맞춘다. 결과(막힘 · 실패)는 last에 두고 서기 할 일 · 텔레그램으로 알린다."""

    def __init__(self, publishers: dict[str, Any], notifier: Any = None, every_s: float = 300) -> None:
        self.pubs, self.notifier, self.every = publishers, notifier, every_s
        self.last: dict[str, dict[str, Any]] = {}       # 프로젝트 → 마지막 맞추기 결과(+ at)
        self._sent: set[str] = set()                    # 같은 막힘을 두 번 알리지 않는다(ref 커밋 · 경로 · 종류)
        self._lock = asyncio.Lock()
        self.before_tick: Any = None                    # 11-12 — 맞추기 전에 저장소 설정 다시 읽기(bridge/notioncfg.py NotionConfig.refresh)

    async def run(self) -> None:
        await asyncio.sleep(60)                         # 브리지가 다 뜬 뒤
        while True:
            try:
                if self.before_tick:
                    async with self._lock:              # 게시 도중에 칸이 바뀌지 않게
                        self.before_tick()
                await self.tick()
            except Exception as e:  # noqa: BLE001 — 한 번 실패해도 다음에 다시
                log.warning("기술문서 맞추기 실패: %s: %s", type(e).__name__, str(e)[:200])
            await asyncio.sleep(self.every)

    async def tick(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        for name, pub in self.pubs.items():
            if pub.docs_mode != "auto":
                continue
            st = await status(pub)
            if not behind(st) and not st["broken"]:
                continue
            quiet = st["last_commit_at"] is None or now - st["last_commit_at"] >= timedelta(minutes=pub.quiet_min)
            if quiet:
                await self.run_one(name)

    async def run_one(self, name: str, force: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
        pub = self.pubs[name]
        when = (datetime.now(UTC) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
        async with self._lock:
            res = await sync(pub, when, force)
        res["at"] = time.time()
        self.last[name] = res
        n = len(res["done"])
        if n or res["held"] or res["failed"]:
            log.warning("기술문서 맞춤 %s — 올림 %d · 사람 수정으로 멈춤 %d · 실패 %d", name, n, len(res["held"]), len(res["failed"]))
        self._alert(pub, res)
        return res

    def _alert(self, pub: Any, res: dict[str, Any]) -> None:
        if not self.notifier:
            return
        rule = self.notifier.rules.for_project(pub.project)
        prefix = rule.prefix if rule else f"[{pub.project}]"
        sha = (res.get("ref_sha") or "")[:8]
        for h in res["held"]:
            key = f"held:{pub.project}:{sha}:{h['path']}"
            if key in self._sent:
                continue
            self._sent.add(key)
            self.notifier.send_direct(pub.project, "docsync", None, "\n".join([
                f"{prefix} ✋ Notion 기술문서 — 사람이 고친 곳이 있어 덮지 않았습니다 · {h['path']}",
                *[f"▶ {e}" for e in h["edits"][:3]],
                "git에 옮기면 다음 맞추기에서 풀립니다. 버리려면 서기실 할 일의 [Notion 수정 버리고 덮기]",
                *([h["url"]] if h.get("url") else [])]))
        if res["failed"]:
            key = f"fail:{pub.project}:{sha}:{','.join(sorted(f['path'] for f in res['failed']))}"
            if key not in self._sent:
                self._sent.add(key)
                self.notifier.send_direct(pub.project, "docsync", None, "\n".join([
                    f"{prefix} ⚠ Notion 기술문서 자동 게시 실패 {len(res['failed'])}개 — 뒤처진 채로 남습니다",
                    *[f"▶ {f['path']} — {f['error'][:120]}" for f in res["failed"][:4]]]))


async def summary(pub: Any, last: dict[str, Any] | None) -> dict[str, Any]:
    """기술문서 게시 상태 읽기(D2, 11-11) — 서기 화면용. 읽기만 한다. 게시됨 · 새 · 바뀜 · 지워짐 · 못 읽음 수, push 대기 커밋 수, 마지막 맞추기 결과."""
    st = await status(pub)
    files = len(st["files"])
    out: dict[str, Any] = {
        "project": pub.project, "mode": st["mode"], "total": files,
        "published": files - len(st["new"]) - len(st["broken"]),     # Notion에 올라 있는 것(바뀜 포함)
        "new": len(st["new"]), "changed": len(st["changed"]), "deleted": len(st["deleted"]), "broken": len(st["broken"]),
        "behind_commits": st["behind_commits"], "synced": st["synced"],
        "last": None,
    }
    if last:
        out["last"] = {"at": last.get("at"), "done": len(last.get("done", [])), "held": len(last.get("held", [])),
                       "failed": len(last.get("failed", [])),
                       "failed_first": (f"{last['failed'][0]['path']}: {str(last['failed'][0]['error'])[:80]}" if last.get("failed") else None)}
    return out


async def todo_items(pub: Any, last: dict[str, Any] | None) -> list[dict[str, Any]]:
    """서기 할 일 — 프로젝트 · 묶음마다 한 줄(11-09 요청 3-1: 파일마다 한 줄을 묶는다) + 사람 수정으로 멈춘 파일마다 한 줄."""
    if pub.docs_mode == "off":
        return []
    st = await status(pub)
    out = []
    n = behind(st)
    if n or st["broken"]:
        parts = [f"새 {len(st['new'])}" if st["new"] else "", f"바뀜 {len(st['changed'])}" if st["changed"] else "",
                 f"지워짐 {len(st['deleted'])}" if st["deleted"] else "", f"못 읽음 {len(st['broken'])}" if st["broken"] else ""]
        commits = f"커밋 {st['behind_commits']} · " if st["behind_commits"] else ""
        if last and last.get("failed"):
            why = f"자동 게시 실패 — {last['failed'][0]['path']}: {last['failed'][0]['error'][:80]}"
        elif pub.docs_mode == "auto":
            why = f"push 뒤 {int(pub.quiet_min)}분 조용하면 바뀐 파일만 자동으로 올립니다"
        else:
            why = "자동 게시가 꺼져 있습니다 — [지금 맞추기]로 올립니다"
        out.append({"kind": "publish", "act": "docsync", "project": pub.project,
                    "title": f"Notion 기술문서 — {commits}파일 {n + len(st['broken'])}개 뒤처짐({' · '.join(p for p in parts if p)})",
                    "why": why})
    # 첫 H1이 없는 문서(st["h1_missing"])는 서기 할 일에 넣지 않는다 — 화면이 act를 docsync · force만 알아서(scribe.js) 새 act는
    # 보이지 않고 개수만 센다. 지금은 status 필드 + 로그 경고로 남기고, 화면 줄은 관리자 몫으로 넘긴다(log 기록)
    for h in (last or {}).get("held", []):
        if h["path"] in st["changed"]:
            out.append({"kind": "publish", "act": "force", "project": pub.project, "path": h["path"],
                        "title": f"Notion에서 사람이 고친 곳 {h['count']}개 — {h['path']}",
                        "why": "덮지 않았습니다. 그 수정을 git에 옮기면 풀리고, 버리려면 [Notion 수정 버리고 덮기]"})
    return out
