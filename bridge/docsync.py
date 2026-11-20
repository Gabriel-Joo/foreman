"""기술 문서(docs/*.md)와 포트폴리오(portfolio/*.md) → Notion 맞추기(11-09, 런슈즈 요청 2 · 3절. 포트폴리오는 11-20부터 같은 함수).

- 원본은 git, Notion은 사본이다. 기준은 push된 것(origin/main) — Notion은 GitHub에 있는 것의 사본이다
- 뒤처짐을 센다(LLM 없음): 파일마다 지문(content_digest) ↔ 게시 기록, 커밋 수는 마지막으로 다 맞춘 커밋(@docs-sync 행) ↔ ref
- docs_mode = "auto"면 docs 커밋 뒤 quiet_min분 조용해지면 바뀐 파일만 갈아 끼운다. 실패하거나 사람이 Notion에서 고친 블록이 있으면
  덮지 않고 알린다(텔레그램 · 서기 할 일) — 뒤처짐은 그대로 남아 보인다(조용히 낡지 않게)
- docs/ 아래 .md(하위 폴더까지). docs/archive/(런슈즈 docs/README "노션 · 발표 자료에 옮기지 않는다")는 올리지 않는다
- 차례: docs/README.md 표에 나온 순서(README가 맨 앞), 표에 없는 파일은 이름순으로 뒤에
- 11-15 원고 폴더를 프로젝트 칸으로(`src`, 기본 docs/). FOREMAN은 notion/ — docs를 그대로 옮기지 않고 사람이 읽을 원고를 따로 쓴다.
  notion/은 폴더 나무가 곧 페이지 나무(`NN_이름/` 아래 글은 `NN_이름.md` 페이지 아래, bridge/notion.py parent_for), 차례는 파일 번호,
  차례는 부모 페이지마다 세운다. 편마다 머리 주석(bridge/manuscript.py)으로 「읽은 커밋 뒤 다루는 코드가 바뀐 편」을 센다(막지는 않는다)
- 11-20 묶음(group)은 둘이다. 기술문서(게시기의 원고 폴더 src)와 포트폴리오(PORT). 함수마다 src를 받고, 없으면 기술문서다.
  포트폴리오는 자동 맞추기가 없고 사람이 [Notion에 올리기]를 눌러야만 올라간다. 한 번에 새 편 만들기, 바뀐 편 고치기, 원본이 사라진 편
  휴지통으로, 번호순 다시 세우기까지 한다. 한 편만 올리는 길(only)도 같은 함수다
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from bridge.doctext.titles import first_h1
from bridge.notion import HumanEdited, NotionError, OutOfScope, content_digest, git_show, link_only

log = logging.getLogger("foreman.docsync")

MARK = "@docs-sync"          # doc_publish 행 — commit_sha = 마지막으로 다 맞춘 ref 커밋(전체 해시)
# 11-09 하위 폴더도 읽는다(펫퍼민트 docs/02_pipeline/ — Notion 하위 페이지 구조를 따라). 빼는 것은 경로 앞부분으로:
# docs/archive/는 늘(런슈즈 docs/README "노션 · 발표 자료에 옮기지 않는다"), 프로젝트 skip의 "…/"로 끝나는 항목은 폴더 통째로
LAST_MARK = "@docs-last"    # doc_publish 행. title = 마지막 맞추기의 멈춤, 실패 수(JSON), error = 첫 실패. 때는 행의 updated_at
LAST_WINDOW = timedelta(minutes=10)     # 「올림 N」으로 세는 한 묶음의 길이(마지막으로 올린 때에서 거슬러)
# 11-19 사람 수정으로 멈춘 편마다 한 행(덮기 단추 자료). @docs-last에는 수만 남아, 브리지를 다시 띄우면 단추가 사라졌다.
# path = 앞붙이 + 원고 경로, kind mark, status held(풀리면 released), title = {"count": n}, error = 고친 곳 앞부분(JSON 목록),
# url = Notion 페이지, commit_sha = 비운다(옛 한 쪽 게시가 남긴 행만 ref가 있다)
HELD_PRE = "@docs-held/"
DOCS_SPEC =":(glob)docs/**/*.md"
ALWAYS_SKIP = ("docs/archive/",)
# 11-20 포트폴리오 묶음. 기술문서와 같은 함수를 쓰고 표시 행만 따로(맞춘 커밋, 마지막 결과). 멈춘 편 행은 경로가 portfolio/로 갈린다
PORT = "portfolio/"
PORT_MARK = "@portfolio-sync"
PORT_LAST = "@portfolio-last"


def src_of(pub: Any) -> str:
    """게시기의 원고 폴더(11-15 src) — 없으면 docs/(가짜 게시기 · 옛 칸)."""
    return getattr(pub, "src", None) or "docs/"


def marks(src: str) -> tuple[str, str]:
    """묶음의 (맞춘 커밋 행, 마지막 결과 행)."""
    return (PORT_MARK, PORT_LAST) if src == PORT else (MARK, LAST_MARK)


def label(src: str) -> str:
    """알림과 서기 할 일에 쓰는 묶음 이름."""
    return "포트폴리오" if src == PORT else "기술문서"


def group_of(pub: Any, path: str) -> str | None:
    """한 편이 든 묶음(11-20). portfolio/ 아래면 포트폴리오, 원고 폴더 아래 .md면 기술문서(기술문서 게시가 켜졌을 때만). 그 밖은 None."""
    if path.startswith(PORT):
        return PORT
    src = src_of(pub)
    if getattr(pub, "docs_mode", "off") != "off" and path.startswith(src):
        return src
    return None


def spec(src: str = "docs/") -> str:
    return f":(glob){src}**/*.md"


def skipped(path: str, skip: Any = (), src: str = "docs/") -> bool:
    """대상이 아닌가 — 파일 이름 그대로 또는 "…/"로 끝나는 폴더 아래. 원고 폴더의 archive/는 늘 뺀다."""
    rules = (*ALWAYS_SKIP, f"{src}archive/", *(skip or ()))
    return any(path == r or (r.endswith("/") and path.startswith(r)) for r in rules)


def _git(repo: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
    return r.stdout if r.returncode == 0 else ""


def docs_files(repo: str, ref: str, skip: Any = (), src: str = "docs/") -> list[str]:
    """ref에 있는 원고 폴더 아래 .md(하위 폴더 포함, archive/ · skip 빼고). docs/는 docs/README.md 표 순서로,
    notion/은 나무 차례로(파일 번호, 부모 글이 그 폴더 글보다 앞 — bridge/manuscript.tree_order), portfolio/는 경로 차례(파일 번호)."""
    if src == "notion/":
        from bridge.manuscript import files as tree_files
        return [f for f in tree_files(repo, src, ref) if not skipped(f, skip, src)]
    raw = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", "--name-only", ref, src],
                         capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
    files = [f for f in raw.split("\0") if f.endswith(".md") and not skipped(f, skip, src)]
    if src == PORT:
        return sorted(files)
    return order(files, _git(repo, "show", f"{ref}:{src}README.md"))


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


def last_docs_commit(repo: str, ref: str, src: str = "docs/") -> datetime | None:
    ts = _git(repo, "log", "-1", "--format=%ct", ref, "--", spec(src)).strip()
    return datetime.fromtimestamp(int(ts), UTC).replace(tzinfo=None) if ts.isdigit() else None


def commits_behind(repo: str, synced: str | None, ref: str, src: str = "docs/") -> int | None:
    """마지막으로 다 맞춘 커밋 뒤로 원고 폴더를 바꾼 커밋 수. 맞춘 적이 없으면 None."""
    if not synced:
        return None
    n = _git(repo, "rev-list", "--count", f"{synced}..{ref}", "--", spec(src)).strip()
    return int(n) if n.isdigit() else None


async def status(pub: Any, src: str | None = None) -> dict[str, Any]:
    """한 묶음의 상태. new, changed, deleted 파일, 뒤처진 커밋 수, 마지막 원고 커밋 시각.
    원고(notion/, portfolio/, 11-15)는 편마다 머리 주석으로 「읽은 커밋 뒤 다루는 코드가 바뀐 편」(code_changed)과 셀 수 없는 편(code_unknown)도.
    relink(11-20): changed 가운데 글은 그대로이고 링크만 다시 걸면 되는 편(notion.link_only).
    포트폴리오는 제목을 따로 정하지 않는다(첫 H1에 번호를 붙인다, notion.portfolio_title). 그래서 제목 비교 없이 지문으로만 바뀜을 가린다."""
    from bridge.doctext.head import parse_head
    from bridge.manuscript import code_commits
    from bridge.notion import MANUSCRIPTS
    src = src or src_of(pub)
    port = src == PORT
    mark_key = marks(src)[0]
    # 대상이 아닌 파일 · 폴더(11-09 펫퍼민트)는 기술문서 칸이다. 포트폴리오에는 쓰지 않는다
    files = docs_files(pub.repo, pub.ref, () if port else getattr(pub, "skip", ()), src=src)
    names = {} if port else titles(files, _git(pub.repo, "show", f"{pub.ref}:{src}README.md"))
    async with pub.e.connect() as c:
        rows = {r["path"]: dict(r) for r in (await c.execute(text(
            "SELECT path, status, title, content_hash, commit_sha, notion_page_id, url FROM doc_publish "
            "WHERE project = :p AND (path LIKE :pre OR path = :m)"), {"p": pub.project, "pre": f"{src}%", "m": mark_key})).mappings().all()}
    new, changed, relink, broken, h1_missing = [], [], [], [], []
    code_changed: list[dict[str, Any]] = []
    code_unknown: list[str] = []
    ref_sha_now = ref_sha(pub.repo, pub.ref)
    for f in files:
        r = rows.get(f)
        try:
            body, sha = git_show(pub.repo, f, pub.ref)
            dg = content_digest(pub.repo, f, body, pub.ref)
        except (FileNotFoundError, OutOfScope) as e:
            broken.append({"path": f, "error": str(e)})
            continue
        if src in MANUSCRIPTS:
            h = parse_head(body) or {}
            n = code_commits(pub.repo, h.get("read"), h.get("covers") or [], pub.ref, ref_sha_now)
            if n is None:
                code_unknown.append(f)
            elif n:
                code_changed.append({"path": f, "commits": n})
        if not port and getattr(pub, "h1_title", False):             # title = "h1"(11-12): 제목 = 첫 H1. 없으면 README 표 제목 그대로
            h1 = first_h1(body)[1]
            if h1:
                names[f] = h1                                        # H1이 바뀌면 아래 r["title"] != names[f]로 changed가 된다
            else:
                h1_missing.append(f)
                log.warning("첫 H1이 없어 README 표 제목을 씁니다(%s): %s", pub.project, f)
        if not port and getattr(pub, "keep_title", False) and r:
            names[f] = r["title"]                                    # 제목 유지(사람이 붙인 "00. 모델 준비" — 사이드바 순서)
        if not r or r["status"] != "published":
            new.append(f)
        elif r["content_hash"] != dg or (not port and r["title"] != names[f]):   # 제목만 바뀌어도(README 표 설명) 맞춘다
            changed.append(f)
            if link_only(r, sha):
                relink.append(f)
    deleted = [p for p, r in rows.items() if p.startswith(src) and r["status"] == "published" and p not in files]
    mark = rows.get(mark_key) or {}
    return {"project": pub.project, "mode": pub.docs_mode, "ref": pub.ref, "ref_sha": ref_sha_now, "src": src,
            "files": files, "titles": names, "new": new, "changed": changed, "relink": relink, "deleted": deleted, "broken": broken,
            "h1_missing": h1_missing,      # title = "h1"인데 첫 H1이 없어 README 표 제목을 쓴 파일(서기 할 일에 한 줄)
            "code_changed": code_changed, "code_unknown": code_unknown,
            "synced": mark.get("commit_sha"), "behind_commits": commits_behind(pub.repo, mark.get("commit_sha"), pub.ref, src),
            "last_commit_at": last_docs_commit(pub.repo, pub.ref, src)}


def behind(st: dict[str, Any]) -> int:
    return len(st["new"]) + len(st["changed"]) + len(st["deleted"])


def _fail(f: str, e: BaseException) -> dict[str, Any]:
    """실패 한 줄. kind는 한 편 게시 API가 응답 코드를 고르는 데 쓴다(scope 409, notion 502)."""
    if isinstance(e, OutOfScope | FileNotFoundError):    # 게시기가 일부러 막은 것. 사유 글 그대로(알림에 "OutOfScope:"를 붙이지 않게)
        return {"path": f, "error": str(e)[:200], "kind": "scope"}
    return {"path": f, "error": f"{type(e).__name__}: {str(e)[:200]}", "kind": "notion" if isinstance(e, NotionError) else "error"}


async def sync(pub: Any, when: str, force: set[str] | frozenset[str] = frozenset(), src: str | None = None,
               only: set[str] | frozenset[str] | None = None) -> dict[str, Any]:
    """한 묶음(src, 없으면 기술문서)의 바뀐 편만 올리고, 지워진 원본의 페이지는 휴지통으로, 새 페이지가 생겼으면 차례를 다시 세운다.
    사람이 Notion에서 고친 페이지는 덮지 않는다(force에 든 경로만 덮는다). 하나라도 막히면 맞춘 커밋 행을 옮기지 않는다(뒤처짐이 남는다).
    한 요청 안에서 한 페이지에는 한 번만 쓴다(11-20): 새 편의 빈 페이지를 먼저 만들어(Publisher.reserve) 편 사이 링크가 첫 게시에서 걸린다.
    only(11-20): 그 편만 올린다(한 편 게시 API). 휴지통 보내기, 차례 세우기, 맞춘 커밋 행은 하지 않는다(그 편 하나만 다룬다).
    저장소 게시 설정을 잃어 멈춘 게시기(config_halt, bridge/notioncfg.py)는 아무것도 하지 않는다 — API · tick이 먼저 막지만 마지막 문."""
    src = src or src_of(pub)
    port = src == PORT
    if getattr(pub, "config_halt", None):
        return {"project": pub.project, "src": src, "ref_sha": None, "done": [], "held": [], "failed": [], "halted": pub.config_halt}
    if port and not getattr(pub, "portfolio_page", None):
        why = f"{pub.project}의 포트폴리오 Notion 자리가 정해지지 않았습니다(config/notion.toml portfolio_page)"
        return {"project": pub.project, "src": src, "ref_sha": None, "done": [], "held": [], "failed": [{"path": PORT, "error": why, "kind": "scope"}]}
    st = await status(pub, src)
    done, held, failed = [], [], []
    warnings: list[dict[str, Any]] = []
    names = st.get("titles", {})
    targets = st["new"] + st["changed"]
    if only is not None:
        targets = [f for f in targets if f in only]
        for f in sorted(set(only) - set(targets)):
            if f in st["files"]:
                done.append({"path": f, "action": "unchanged"})
            elif not any(b["path"] == f for b in st["broken"]):
                failed.append({"path": f, "error": f"{pub.ref}에 {f}가 없습니다. 합친(push한) 뒤에 게시해 주세요", "kind": "scope"})
    # 새 편의 빈 페이지 먼저(나무 차례라 부모 글이 먼저). 실패한 편은 아래에서 올리지 않는다
    skip: set[str] = set()
    made: set[str] = set()                               # 빈 페이지를 먼저 만든 편. 게시 결과가 updated여도 사람에게는 새 편(created)이다
    reserve = getattr(pub, "reserve", None)
    for f in (x for x in targets if x in st["new"]) if reserve else ():
        try:
            if await reserve(f, None if port else names.get(f)):
                made.add(f)
        except Exception as e:  # noqa: BLE001 (한 편이 막혀도 나머지는 올린다)
            failed.append(_fail(f, e))
            skip.add(f)
    for f in targets:
        if f in skip:
            continue
        try:
            # 포트폴리오는 제목을 주지 않는다(게시기가 첫 H1에 번호를 붙인다). 기술문서는 README 표 제목이나 첫 H1
            r = await pub.publish(f, when, force=f in force, title=None if port else names.get(f))
        except HumanEdited as e:
            held.append({"path": f, "edits": e.edits[:5], "count": len(e.edits), "url": e.url})
            continue
        except Exception as e:  # noqa: BLE001 — 파일 하나가 막혀도 나머지는 올린다
            failed.append(_fail(f, e))
            continue
        done.append({"path": f, "action": "created" if f in made else r["action"], "url": r.get("url"), "page_id": r.get("page_id")})
        warnings += [{"path": f, "warning": w} for w in r.get("warnings") or []]
        if r.get("pending"):
            # 빈 페이지를 먼저 만들었어도 Notion에 없는 편(그 편이 막혔다, 다른 묶음 밖). 지문이 비어 「링크를 다시 걸어야 함」으로 남는다
            warnings.append({"path": f, "warning": "가리킨 편이 아직 Notion에 없어 링크를 못 걸었습니다: " + ", ".join(r["pending"])})
    tree = src == "notion/"
    for f in st["deleted"] if only is None else ():
        if tree and any(x.startswith(f"{f[:-3]}/") for x in st["files"]):
            # 11-15 나무 — 부모 페이지를 휴지통으로 보내면 Notion이 그 아래 페이지까지 함께 보낸다. 아래 글이 남아 있으면 내리지 않는다
            failed.append({"path": f, "error": f"원고가 사라졌지만 그 아래 글({f[:-3]}/)이 남아 있어 내리지 않습니다. "
                                               "아래 글을 옮기거나 지운 뒤 맞춥니다"})
            continue
        if not getattr(pub, "create", True) or not getattr(pub, "archive_ok", True):
            # 11-09 — 사람이 옮겨 둔 페이지에 맞추는 프로젝트는 원본이 사라져도 휴지통으로 보내지 않는다(create = false 또는
            # archive = false — 사용자: 새 페이지 만들기와 옛 페이지 지우기는 다른 기능, 지운 문서는 실패로만 남기고 사람이 판단).
            # 경로만 바뀐 것(git mv)이면 짝을 새 경로로 옮기면 풀린다. 그냥 옮겼으면 펫퍼민트 20쪽이 모두 휴지통으로 갈 뻔했다
            failed.append({"path": f, "error": "원본이 사라졌습니다. 이 프로젝트는 휴지통으로 보내지 않습니다(archive = false). "
                                               "경로가 바뀌었으면 짝(doc_publish)을 새 경로로 옮겨 주세요"})
            continue
        try:
            await pub.archive(f)
            done.append({"path": f, "action": "archived"})
        except Exception as e:  # noqa: BLE001
            failed.append(_fail(f, e))
    failed += [{"path": b["path"], "error": b["error"], "kind": "scope"} for b in st["broken"] if only is None or b["path"] in only]
    place = getattr(pub, "portfolio_page" if port else "docs_page", None)
    # 차례가 이미 맞으면 reorder가 옮기지 않는다. keep_order면 사람 차례 그대로. 한 편만 올릴 때는 다른 편을 옮기지 않는다
    if done and place and only is None and not getattr(pub, "keep_order", False):
        async with pub.e.connect() as c:
            got = (await c.execute(text(
                "SELECT path, notion_page_id, parent_page_id FROM doc_publish WHERE project = :p AND kind = 'doc' AND status = 'published' "
                "AND path LIKE :pre"), {"p": pub.project, "pre": f"{src}%"})).all()
        pages = {r[0]: r[1] for r in got}
        if tree:
            # 11-15 나무 — 부모 페이지마다 그 아래 글을 파일 번호 차례로(reorder는 부모 하나씩 세운다)
            groups: dict[str, list[tuple[str, str]]] = {}
            parent_of = {r[0]: (r[2] or place) for r in got}
            for f in st["files"]:
                if f in pages:
                    groups.setdefault(parent_of[f], []).append((f, pages[f]))
            plan = list(groups.items())
        else:
            plan = [(place, [(f, pages[f]) for f in st["files"] if f in pages])]
        for parent, rows_ in plan:
            try:
                await pub.reorder(rows_, parent)
            except Exception as e:  # noqa: BLE001 — 차례가 틀려도 내용은 맞다
                failed.append({"path": "(차례)", "error": f"{type(e).__name__}: {str(e)[:200]}", "kind": "error"})
    if only is None and not held and not failed and st["ref_sha"]:
        await pub._save(marks(src)[0], kind="mark", title=f"{label(src)} 맞춘 커밋", commit_sha=st["ref_sha"], status="published", error=None)
    return {"project": pub.project, "src": src, "ref_sha": st["ref_sha"], "done": done, "held": held, "failed": failed, "warnings": warnings}


class DocSync:
    """docs_mode = auto인 프로젝트의 기술문서를 주기적으로 맞추고, 사람이 누른 게시(기술문서, 포트폴리오)도 이 길로 돈다.
    결과(막힘, 실패)는 last에 두고 서기 할 일과 텔레그램으로 알린다. 게시는 모두 한 잠금 안에서 돈다. 잇달아 눌러도 같은 페이지에
    두 요청이 함께 쓰지 않는다(11-20, TODO 「Can't edit block that is archived」)."""

    def __init__(self, publishers: dict[str, Any], notifier: Any = None, every_s: float = 300) -> None:
        self.pubs, self.notifier, self.every = publishers, notifier, every_s
        self.last: dict[str, dict[str, Any]] = {}       # 프로젝트(포트폴리오는 "프로젝트#portfolio/") → 마지막 맞추기 결과(+ at)
        self._sent: set[str] = set()                    # 같은 막힘을 두 번 알리지 않는다(ref 커밋 · 경로 · 종류)
        self._lock = asyncio.Lock()
        self.before_tick: Any = None                    # 11-12 — 맞추기 전에 저장소 설정 다시 읽기(bridge/notioncfg.py NotionConfig.refresh)

    def _key(self, name: str, src: str | None) -> str:
        """last의 열쇠. 기술문서는 프로젝트 이름 그대로(전과 같음), 포트폴리오는 뒤에 #portfolio/."""
        return f"{name}#{PORT}" if src == PORT else name

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
        """자동 맞추기는 기술문서만. 포트폴리오는 바깥 독자에게 내는 글이라 사람이 눌러야만 올라간다."""
        now = datetime.now(UTC).replace(tzinfo=None)
        for name, pub in self.pubs.items():
            if pub.docs_mode != "auto" or getattr(pub, "config_halt", None):     # 멈춘 게시기는 건너뛴다(알림은 notioncfg가 했다)
                continue
            st = await status(pub)
            if not behind(st) and not st["broken"]:
                continue
            quiet = st["last_commit_at"] is None or now - st["last_commit_at"] >= timedelta(minutes=pub.quiet_min)
            if quiet:
                await self.run_one(name)

    async def run_one(self, name: str, force: set[str] | frozenset[str] = frozenset(), src: str | None = None,
                      only: set[str] | frozenset[str] | None = None) -> dict[str, Any]:
        """한 묶음 맞추기(sync)와 그 뒤 기록, 알림. only면 그 편만 올리고, 다른 편의 멈춤 줄(덮기 단추)은 그대로 둔다."""
        pub = self.pubs[name]
        src = src or src_of(pub)
        key = self._key(name, src)
        when = (datetime.now(UTC) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
        if only is not None:
            await self.last_for(name, src)              # 다시 띄운 뒤면 DB의 멈춘 편을 먼저 되살린다(다른 편 행을 잘못 풀지 않게)
        async with self._lock:
            res = await sync(pub, when, force, src, only)
        res["at"] = time.time()
        if only is not None:
            keep = [h for h in (self.last.get(key) or {}).get("held", []) if h["path"] not in only]
            res["held"] = keep + res["held"]
        self.last[key] = res
        await self._persist(pub, res, src)
        await self.save_held(name, src)
        n = len(res["done"])
        if n or res["held"] or res["failed"]:
            log.warning("%s 맞춤 %s — 올림 %d · 사람 수정으로 멈춤 %d · 실패 %d", label(src), name, n, len(res["held"]), len(res["failed"]))
        self._alert(pub, res, src)
        return res

    async def _persist(self, pub: Any, res: dict[str, Any], src: str | None = None) -> None:
        """한 번의 맞추기 결과(멈춤, 실패 수와 첫 실패)를 마지막 결과 행(@docs-last, @portfolio-last)에 남긴다. 브리지를 다시 띄운 뒤에도
        화면이 같은 말을 하게. 올린 편과 때는 편마다 행(updated_at)에 이미 있다. 못 남겨도 맞추기는 이어 가고 로그에 남긴다."""
        first = f"{res['failed'][0]['path']}: {str(res['failed'][0]['error'])[:200]}" if res["failed"] else None
        try:
            await pub._save(marks(src or src_of(pub))[1], kind="mark",
                            title=json.dumps({"held": len(res["held"]), "failed": len(res["failed"]), "at": int(res["at"])}),   # at: 같은 결과가 이어져도 행이 바뀌어 updated_at이 오른다
                            status="published", error=first)
        except Exception as e:  # noqa: BLE001
            log.warning("%s 맞추기 결과를 남기지 못했습니다(%s): %s: %s", label(src or ""), pub.project, type(e).__name__, str(e)[:120])

    async def save_held(self, name: str, src: str | None = None) -> None:
        """멈춘 편 목록(last의 held)을 편마다 DB 행(HELD_PRE)으로 맞춘다(11-19). 그 묶음의 목록에 없는 옛 행은 released로.
        못 남겨도 맞추기와 게시는 이어 가고 로그에 남긴다(화면은 메모리로 지금 단추를 그대로 보인다)."""
        pub = self.pubs.get(name)
        if pub is None:
            return
        src = src or src_of(pub)
        res = self.last.get(self._key(name, src))
        if res is None:
            return
        try:
            async with pub.e.connect() as c:
                old = {r[0] for r in (await c.execute(text(
                    "SELECT path, status FROM doc_publish WHERE project = :p AND path LIKE :pre"),
                    {"p": pub.project, "pre": f"{HELD_PRE}{src}%"})).all() if r[1] == "held"}
            want = {}
            for h in res.get("held", []):
                want[HELD_PRE + h["path"]] = h
            for key, h in want.items():
                await pub._save(key, kind="mark", title=json.dumps({"count": int(h.get("count", len(h.get("edits", []))))}),
                                status="held", url=h.get("url"), commit_sha=h.get("ref_sha"), error=_edits_json(h.get("edits", [])))
            for key in old - set(want):
                await pub._save(key, status="released")
        except Exception as e:  # noqa: BLE001
            log.warning("멈춘 편 목록을 남기지 못했습니다(%s): %s: %s", name, type(e).__name__, str(e)[:120])

    async def last_for(self, name: str, src: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
        """서기 화면이 읽는 마지막 결과(11-19). 메모리에 없으면(브리지를 다시 띄운 뒤) DB의 멈춘 편 행에서 held를 되살린다.
        되살린 것은 at이 없어 「마지막으로 올림」 수는 그대로 마지막 결과 행에서 읽힌다(last_published). 못 읽으면 (None, 까닭)."""
        pub = self.pubs.get(name)
        src = src or (src_of(pub) if pub is not None else None)
        key = self._key(name, src)
        if key in self.last:
            return self.last[key], None
        if pub is None:
            return None, None
        try:
            held = await load_held(pub, src)
        except Exception as e:  # noqa: BLE001 (못 읽었는데 멈춘 편이 없다고 하지 않는다)
            return None, f"{type(e).__name__}: {str(e)[:80]}"
        if not held:
            return None, None
        self.last[key] = {"project": name, "src": src, "ref_sha": None, "done": [], "held": held, "failed": [], "restored": True}
        return self.last[key], None

    def _alert(self, pub: Any, res: dict[str, Any], src: str | None = None) -> None:
        if not self.notifier:
            return
        what = label(src or src_of(pub))
        rule = self.notifier.rules.for_project(pub.project)
        prefix = rule.prefix if rule else f"[{pub.project}]"
        sha = (res.get("ref_sha") or "")[:8]
        for h in res["held"]:
            key = f"held:{pub.project}:{sha}:{h['path']}"
            if key in self._sent:
                continue
            self._sent.add(key)
            self.notifier.send_direct(pub.project, "docsync", None, "\n".join([
                f"{prefix} ✋ Notion {what} — 사람이 고친 곳이 있어 덮지 않았습니다 · {h['path']}",
                *[f"▶ {e}" for e in h["edits"][:3]],
                f"git에 옮기면 다음 맞추기에서 풀립니다. 버리려면 서기실 「{what} 게시」의 [Notion 수정 버리고 덮기]",
                *([h["url"]] if h.get("url") else [])]))
        if res["failed"]:
            key = f"fail:{pub.project}:{sha}:{','.join(sorted(f['path'] for f in res['failed']))}"
            if key not in self._sent:
                self._sent.add(key)
                self.notifier.send_direct(pub.project, "docsync", None, "\n".join([
                    f"{prefix} ⚠ Notion {what} 게시 실패 {len(res['failed'])}개 — 뒤처진 채로 남습니다",
                    *[f"▶ {f['path']} — {f['error'][:120]}" for f in res["failed"][:4]]]))


def _edits_json(edits: list[str]) -> str:
    """고친 곳 앞부분을 error 칸(512자)에 들어가게 JSON 목록으로. 넘치면 뒤 항목부터 버린다."""
    out = [str(e)[:120] for e in edits[:5]]
    while out and len(json.dumps(out, ensure_ascii=False)) > 500:
        out.pop()
    return json.dumps(out, ensure_ascii=False)


async def load_held(pub: Any, src: str | None = None) -> list[dict[str, Any]]:
    """DB에 남은 한 묶음의 멈춘 편(HELD_PRE 행, status held)을 메모리 held 꼴로 읽는다(11-19). 읽지 못하면 예외를 그대로 올린다."""
    src = src or src_of(pub)
    async with pub.e.connect() as c:
        rows = (await c.execute(text(
            "SELECT path, status, title, error, url, commit_sha FROM doc_publish WHERE project = :p AND path LIKE :pre"),
            {"p": pub.project, "pre": f"{HELD_PRE}{src}%"})).mappings().all()
    out = []
    for r in rows:
        if r["status"] != "held":
            continue
        try:
            n = int(json.loads(r["title"] or "{}").get("count", 0))
        except (ValueError, AttributeError):
            n = 0
        try:
            edits = [str(x) for x in json.loads(r["error"] or "[]")]
        except ValueError:
            edits = []
        h = {"path": r["path"][len(HELD_PRE):], "edits": edits, "count": n or len(edits), "url": r["url"]}
        if r["commit_sha"]:
            h["ref_sha"] = r["commit_sha"]
        out.append(h)
    return out


def held_list_missing(summ: dict[str, Any], last: dict[str, Any] | None, held_error: str | None) -> int | None:
    """「멈춤 N」인데 멈춘 편 목록 자체가 없으면 N, 아니면 None(11-19).
    옛 브리지가 멈춘 편 행(HELD_PRE)을 남기지 않아 목록을 모르는 경우다. 목록은 있는데 지금 덮을 편이 0인 경우
    (그 뒤 git이 다시 바뀜, 이미 맞춰짐)와 가른다. 목록을 못 읽은 경우(held_error)도 따로 말하므로 여기서는 None"""
    n = int(((summ or {}).get("last") or {}).get("held") or 0)
    if not n or held_error or (last or {}).get("held"):
        return None
    return n


async def last_published(pub: Any, mem: dict[str, Any] | None = None, src: str | None = None) -> dict[str, Any] | None:
    """「마지막으로 올린 때」와 그 결과를 DB에서 읽는다(11-17). 메모리(mem)는 보태기만 하고 없어도 같은 글이 나온다.

    - 때: 묶음 폴더(src, 없으면 원고 폴더) 아래 게시된 편의 updated_at 가운데 가장 늦은 것. 자동 맞추기, [Notion에 올리기],
      한 편 게시가 모두 Publisher.publish로 그 행을 쓰므로 어떤 길로 올렸든 들어간다
    - 올림: 그 때에서 LAST_WINDOW 안에 올라간 편 수(한 번의 맞추기든 한 편씩이든 같은 셈)
    - 멈춤, 실패: 맞추기가 남긴 마지막 결과 행(marks)이 그 묶음 안이면 그것, 아니면 메모리(mem)가 그 묶음 안일 때 그것
    - DB에 올린 편도 맞추기 기록도 없으면 None(정말 없을 때만). 읽지 못하면 예외를 그대로 올린다(없다고 하지 않는다)"""
    src = src or src_of(pub)
    last_key = marks(src)[1]
    async with pub.e.connect() as c:
        rows = (await c.execute(text(
            "SELECT path, kind, status, title, error, updated_at FROM doc_publish "
            "WHERE project = :p AND (path LIKE :pre OR path = :m)"), {"p": pub.project, "pre": f"{src}%", "m": last_key})).mappings().all()
    docs = [r["updated_at"] for r in rows if r["path"].startswith(src) and r["status"] == "published" and r["updated_at"]]
    mark = next((r for r in rows if r["path"] == last_key), None)
    mark_at = mark["updated_at"] if mark and mark["updated_at"] else None
    at = max([*docs, *([mark_at] if mark_at else [])], default=None)
    mem_at = datetime.fromtimestamp(mem["at"], UTC).replace(tzinfo=None) if mem and mem.get("at") else None
    if at is None and mem_at is None:
        return None
    at = max(x for x in (at, mem_at) if x)
    start = at - LAST_WINDOW
    out: dict[str, Any] = {"at": at.replace(tzinfo=UTC).timestamp(), "done": sum(1 for d in docs if d >= start),
                           "held": 0, "failed": 0, "failed_first": None}
    if mem and mem_at and mem_at >= start:
        out.update(held=len(mem.get("held", [])), failed=len(mem.get("failed", [])),
                   failed_first=(f"{mem['failed'][0]['path']}: {str(mem['failed'][0]['error'])[:80]}" if mem.get("failed") else None))
        out["done"] = max(out["done"], len(mem.get("done", [])))
    elif mark and mark_at and mark_at >= start:
        try:
            n = json.loads(mark["title"] or "{}")
        except ValueError:
            n = {}
        out.update(held=int(n.get("held", 0)), failed=int(n.get("failed", 0)), failed_first=mark["error"])
    return out


async def summary(pub: Any, last: dict[str, Any] | None, src: str | None = None) -> dict[str, Any]:
    """한 묶음의 게시 상태 읽기(D2, 11-11) — 서기 화면용. 읽기만 한다. 게시됨 · 새 · 바뀜 · 지워짐 · 못 읽음 수, push 대기 커밋 수,
    마지막 맞추기 결과. 마지막으로 올린 때는 DB에서(last_published). 브리지를 다시 띄워도 남는다. 못 읽으면 last_error(화면이 「읽지 못했습니다」)."""
    st = await status(pub, src)
    files = len(st["files"])
    out: dict[str, Any] = {
        "project": pub.project, "mode": st["mode"], "total": files, "src": st.get("src", "docs/"),
        "published": files - len(st["new"]) - len(st["broken"]),     # Notion에 올라 있는 것(바뀜 포함)
        "new": len(st["new"]), "changed": len(st["changed"]), "deleted": len(st["deleted"]), "broken": len(st["broken"]),
        "relink": len(st.get("relink", [])),                          # 바뀜 가운데 링크만 다시 걸면 되는 편(11-20)
        # 원고(notion/, portfolio/, 11-15). 읽은 커밋 뒤 다루는 코드가 바뀐 편, 셀 수 없는 편(머리 주석 없음 등). 게시 확인 창이 보인다(막지 않는다)
        "code_changed": len(st.get("code_changed", [])), "code_unknown": len(st.get("code_unknown", [])),
        "code_changed_paths": [x["path"] for x in st.get("code_changed", [])][:10],
        "behind_commits": st["behind_commits"], "synced": st["synced"],
        "last": None, "last_error": None,
    }
    try:
        out["last"] = await last_published(pub, last, src)
    except Exception as e:  # noqa: BLE001 - 못 읽었는데 「기록 없음」이라고 하지 않는다
        out["last_error"] = f"{type(e).__name__}: {str(e)[:80]}"
    return out


async def todo_items(pub: Any, last: dict[str, Any] | None, src: str | None = None) -> list[dict[str, Any]]:
    """서기 할 일. 묶음마다 한 줄(11-09 요청 3-1: 파일마다 한 줄을 묶는다) + 사람 수정으로 멈춘 파일마다 한 줄.
    줄마다 src를 달아 화면이 기술문서 칸과 포트폴리오 칸에 덮기 단추를 나눠 단다(11-20)."""
    src = src or src_of(pub)
    port = src == PORT
    what = label(src)
    if halt := getattr(pub, "config_halt", None):
        # 저장소 게시 설정을 잃어 멈춤(11-12) — 이 한 줄만(기술문서 쪽에서 한 번). act docsync — 서기 화면이 기술문서 줄 옆에 why를 보인다
        # (scribe.js docsPubBlock). 그 줄의 [지금 맞추기]를 눌러도 서버가 같은 사유로 거절한다
        return [] if port else [{"kind": "publish", "act": "docsync", "project": pub.project, "halted": True, "src": src,
                                 "title": "Notion 게시 멈춤(저장소 게시 설정을 읽지 못했습니다)", "why": halt}]
    if not port and pub.docs_mode == "off":
        return []
    st = await status(pub, src)
    out = []
    n = behind(st)
    if n or st["broken"]:
        relink = len(st.get("relink", []))
        parts = [f"새 {len(st['new'])}" if st["new"] else "",
                 f"바뀜 {len(st['changed']) - relink}" if len(st["changed"]) - relink else "",
                 f"링크만 {relink}" if relink else "",
                 f"지워짐 {len(st['deleted'])}" if st["deleted"] else "", f"못 읽음 {len(st['broken'])}" if st["broken"] else ""]
        commits = f"커밋 {st['behind_commits']} · " if st["behind_commits"] else ""
        if last and last.get("failed"):
            why = f"게시 실패, {last['failed'][0]['path']}: {last['failed'][0]['error'][:80]}"
        elif port:
            why = ("Notion 자리가 정해지지 않아 아직 올릴 수 없습니다(config/notion.toml portfolio_page)"
                   if not getattr(pub, "portfolio_page", None)
                   else "자동 게시가 없습니다. 서기실 「포트폴리오 게시」의 [Notion에 올리기]를 눌러야만 올라갑니다")
        elif pub.docs_mode == "auto":
            why = f"push 뒤 {int(pub.quiet_min)}분 조용하면 바뀐 파일만 자동으로 올립니다"
        elif st.get("src") == "notion/":
            why = "자동 게시가 없습니다. 서기실 [Notion에 올리기]를 눌러야만 올라갑니다"
        else:
            why = "자동 게시가 꺼져 있습니다. [지금 맞추기]로 올립니다"
        out.append({"kind": "publish", "act": "docsync", "project": pub.project, "src": src,
                    "title": f"Notion {what}: {commits}파일 {n + len(st['broken'])}개 뒤처짐({' · '.join(p for p in parts if p)})",
                    "why": why})
    # 첫 H1이 없는 문서(st["h1_missing"])는 서기 할 일에 넣지 않는다 — 화면이 act를 docsync · force만 알아서(scribe.js) 새 act는
    # 보이지 않고 개수만 센다. 지금은 status 필드 + 로그 경고로 남기고, 화면 줄은 관리자 몫으로 넘긴다(log 기록)
    for h in (last or {}).get("held", []):
        # 옛 한 쪽 게시가 남긴 줄(ref_sha가 있는 것)은 git이 그 뒤로 또 바뀌었으면 사라진다
        if h["path"] in st["changed"] and h.get("ref_sha", st["ref_sha"]) == st["ref_sha"]:
            out.append({"kind": "publish", "act": "force", "project": pub.project, "path": h["path"], "src": src,
                        "title": f"Notion에서 사람이 고친 곳 {h['count']}개: {h['path']}",
                        "why": "덮지 않았습니다. 그 수정을 git에 옮기면 풀리고, 버리려면 [Notion 수정 버리고 덮기]"})
    return out
