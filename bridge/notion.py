"""12c Notion 게시(11-06, docs/12_scribe.md 「5. Notion 연동」) — 원본은 git 마크다운, Notion은 게시판.

- **길 B(사용자 결정 11-06)**: 브리지가 Notion API를 직접 부른다(내부 통합 토큰 `.env.notion` NOTION_TOKEN).
  통합은 FOREMAN 페이지에만 연결돼 있어 **그 밖의 페이지는 Notion 권한이 막는다**(코드가 아니라 구조). LLM이 글을 옮겨 적지 않는다.
- 코드에서도 한 번 더 막는다(`Scope`): 고치기 · 지우기 · 옮기기는 우리가 만든 페이지(doc_publish)만, 매번 Notion에서 부모를 따라
  올라가 루트에 닿는지 본다. 루트 자체는 못 건드린다. 지우기는 휴지통(archive — 30일 되살릴 수 있다).
- 원본은 main에 커밋된 것만(`git show HEAD:<경로>`). 같은 원본은 같은 페이지에 내용을 갈아 끼운다(URL 그대로). 내용이 같으면 건너뛴다.
- 근거 표시: [c:sha] → GitHub 커밋 링크, [log:…] · [docs:…] → 게시한 커밋의 파일 링크, [t:…] → 뺀다(사용자만 볼 수 있는 DB 번호, 11-06 결정).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
TEXT_MAX = 2000             # rich_text 한 덩어리 상한(Notion)
CHUNK = 100                 # 한 번에 붙이는 블록 수 상한(Notion)
GH = "https://github.com/Gabriel-Joo/foreman"

CODE_LANG = {"py": "python", "python": "python", "js": "javascript", "mjs": "javascript", "javascript": "javascript",
             "ts": "typescript", "sh": "shell", "bash": "shell", "shell": "shell", "sql": "sql", "json": "json", "toml": "plain text",
             "yaml": "yaml", "yml": "yaml", "html": "html", "css": "css", "md": "markdown", "markdown": "markdown", "": "plain text",
             "mermaid": "mermaid"}   # 11-06 — 빠져 있어 plain text로 올라갔다. mermaid여야 Notion이 [미리보기]로 그림을 그린다


class NotionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Notion {status}: {message}")
        self.status = status


class HumanEdited(Exception):
    """Notion에서 사람이 고친 블록이 있어 덮지 않았다(11-09) — git에 옮기면 풀리고, 버리려면 force로 다시 게시한다."""

    def __init__(self, path: str, edits: list[str], url: str | None = None) -> None:
        super().__init__(f"Notion에서 사람이 고친 곳 {len(edits)}개가 있어 덮지 않았습니다 — {path}")
        self.path, self.edits, self.url = path, edits, url


class OutOfScope(Exception):
    """범위 밖 — FOREMAN 페이지 아래가 아니거나 우리가 만든 페이지가 아니다."""


# ── 변환기(마크다운 → Notion 블록) ─────────────────────────────
class Ctx:
    """링크를 풀 때 쓰는 것 — 원본 경로와 게시한 커밋. links=False(포트폴리오)면 커밋 · 파일 · 저장소 안 링크를 글자로만 둔다 —
    저장소가 비공개라 읽는 사람에게는 404다(11-06 사용자 결정)."""
    def __init__(self, path: str = "", commit: str = "HEAD", gh: str = GH, links: bool = True) -> None:
        self.path, self.commit, self.gh, self.links = path, commit, gh, links

    def blob(self, rel: str) -> str:
        return f"{self.gh}/blob/{self.commit}/{rel}"

    def resolve(self, href: str) -> str | None:
        """상대 링크(../log/a.md) → 게시한 커밋의 GitHub 파일. http(s)는 그대로. 그 밖(#앵커 등)은 None."""
        if re.match(r"https?://", href):
            return href
        if href.startswith("#") or not href:
            return None
        base = PurePosixPath(self.path).parent
        parts: list[str] = []
        for p in (base / href.split("#")[0]).parts:
            if p == "..":
                if parts:
                    parts.pop()
            elif p not in (".", ""):
                parts.append(p)
        return self.blob("/".join(parts)) if parts else None


_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<bold>\*\*(?P<btext>[^*\n]+)\*\*)"
    r"|(?P<ev>\[(?P<evk>c|log|docs|t):(?P<evv>[^\]\s]+)\])"
    r"|(?P<link>\[(?P<ltext>[^\]\n]+)\]\((?P<lhref>[^)\s]+)\))")


def _rt(content: str, *, bold: bool = False, code: bool = False, link: str | None = None, color: str | None = None) -> list[dict[str, Any]]:
    out = []
    for i in range(0, len(content), TEXT_MAX) if content else []:
        piece = content[i:i + TEXT_MAX]
        t: dict[str, Any] = {"type": "text", "text": {"content": piece}}
        if link:
            t["text"]["link"] = {"url": link}
        ann = {k: True for k, on in (("bold", bold), ("code", code)) if on}
        if color:
            ann["color"] = color
        if ann:
            t["annotations"] = ann
        out.append(t)
    return out


def inline(text: str, ctx: Ctx) -> list[dict[str, Any]]:
    """한 줄 글 → rich_text. 근거 표시 [t:…]는 빼고 이웃 공백을 하나로."""
    text = re.sub(r"\s*\[t:[^\]\s]+\]", "", text)
    out: list[dict[str, Any]] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out += _rt(text[pos:m.start()])
        if m["code"]:
            out += _rt(m["code"][1:-1], code=True)
        elif m["bold"]:
            out += _rt(m["btext"], bold=True)
        elif m["ev"]:
            k, v = m["evk"], m["evv"]
            if k == "c":
                out += _rt(v, code=True, link=f"{ctx.gh}/commit/{v}" if ctx.links else None)
            else:                                   # log · docs — 파일(줄 범위 · 절은 떼고 파일만 잇는다)
                f = re.split(r"[:#]", v)[0]
                out += _rt(f"{k}/{f}", code=True, link=ctx.blob(f"{k}/{f}") if ctx.links else None)
        elif m["link"]:
            href = ctx.resolve(m["lhref"])
            if href and not ctx.links and href.startswith(ctx.gh):
                href = None                         # 저장소 안 파일 링크 — 포트폴리오에서는 글자만
            out += _rt(m["ltext"], link=href)
        pos = m.end()
    if pos < len(text):
        out += _rt(text[pos:])
    return out


def _block(kind: str, rich: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"object": "block", "type": kind, kind: {"rich_text": rich, **extra}}


_LIST = re.compile(r"^(?P<ind>[ \t]*)(?P<mark>[-*+]|\d+[.)])\s+(?P<text>.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def md_to_blocks(md: str, ctx: Ctx | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    """(제목, 블록들). 첫 `# 제목`은 페이지 제목으로 빼고 블록에 넣지 않는다."""
    ctx = ctx or Ctx()
    lines = md.replace("\r\n", "\n").split("\n")
    title = None
    blocks: list[dict[str, Any]] = []
    i = 0
    para: list[str] = []

    def flush_para() -> None:
        if para:
            blocks.append(_block("paragraph", inline("\n".join(para), ctx)))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        fence = re.match(r"^(`{3,}|~{3,})\s*([\w+-]*)\s*$", s)
        if fence:
            flush_para()
            mark, lang = fence.group(1), fence.group(2).lower()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(mark):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(_block("code", _rt("\n".join(body)) or _rt(" "), language=CODE_LANG.get(lang, "plain text")))
            continue
        if not s:
            flush_para()
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", s)
        if h:
            flush_para()
            level, text = len(h.group(1)), h.group(2).strip()
            if level == 1 and title is None and not blocks:
                title = re.sub(r"\s*\[t:[^\]\s]+\]", "", text)
            else:
                kind = "heading_" + str(min(max(level - 1, 1), 3))    # ## → h1 · ### → h2 · #### 이상 → h3
                blocks.append(_block(kind, inline(text, ctx)))
            i += 1
            continue
        # 설명 안의 [버튼] 같은 대괄호도 받는다(11-06 — `[^\]]*`이면 「[대화] 탭」 설명의 사진이 글 문단으로 조용히 바뀌었다)
        img = re.match(r"^!\[(?P<cap>.*)\]\((?P<src>[^)\s]+)\)$", s)
        if img:                                     # 그림 — 저장소 안 PNG는 게시할 때 파일로 올린다(_upload), 바깥 주소는 그대로
            flush_para()
            src = img["src"]
            cap = inline(img["cap"], ctx) if img["cap"] else []
            if re.match(r"https?://", src):
                blocks.append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": src}, "caption": cap}})
            else:
                rel = str(PurePosixPath(ctx.path).parent / src) if ctx.path else src
                blocks.append({"object": "block", "type": "image", "_upload": os.path.normpath(rel), "image": {"caption": cap}})
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush_para()
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush_para()
            head = _cells(s)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            width = max(len(head), *(len(r) for r in rows)) if rows else len(head)
            mk = lambda cs: {"object": "block", "type": "table_row",  # noqa: E731
                             "table_row": {"cells": [inline(c, ctx) for c in (cs + [""] * width)[:width]]}}
            blocks.append({"object": "block", "type": "table",
                           "table": {"table_width": width, "has_column_header": True, "has_row_header": False,
                                     "children": [mk(head)] + [mk(r) for r in rows]}})
            continue
        if s.startswith(">"):
            flush_para()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(_block("quote", inline("\n".join(q), ctx)))
            continue
        if _LIST.match(ln):
            flush_para()
            i = _list(lines, i, blocks, ctx)
            continue
        para.append(s)
        i += 1
    flush_para()
    return title, blocks


def _list(lines: list[str], i: int, out: list[dict[str, Any]], ctx: Ctx) -> int:
    """연속된 목록 줄 → 중첩 목록 블록. 들여쓰기 깊이로 부모를 정하고, 표지 없는 들여 쓴 줄은 앞 항목에 이어 붙인다."""
    stack: list[tuple[int, dict[str, Any]]] = []          # (들여쓰기, 블록)
    while i < len(lines):
        ln = lines[i]
        m = _LIST.match(ln)
        if not m:
            if ln.strip() and stack and (len(ln) - len(ln.lstrip())) > stack[-1][0]:
                b = stack[-1][1]
                kind = b["type"]
                b[kind]["rich_text"] += _rt("\n") + inline(ln.strip(), ctx)
                i += 1
                continue
            break
        ind = len(m["ind"].expandtabs(4))
        kind = "numbered_list_item" if m["mark"][0].isdigit() else "bulleted_list_item"
        b = _block(kind, inline(m["text"], ctx))
        while stack and stack[-1][0] >= ind:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            parent[parent["type"]].setdefault("children", []).append(b)
        else:
            out.append(b)
        stack.append((ind, b))
        i += 1
    return i


def plain(rich: list[dict[str, Any]]) -> str:
    return "".join(t["text"]["content"] for t in rich)


# ── 클라이언트 ──────────────────────────────────────────────
def load_token(path: str | os.PathLike[str]) -> str | None:
    """`.env.notion`의 NOTION_TOKEN — 값을 어디에도 찍지 않는다."""
    try:
        for ln in Path(path).read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("NOTION_TOKEN="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


class NotionClient:
    """Notion REST 최소한. 초당 3번 남짓으로 천천히 부른다(429면 기다렸다 다시)."""

    def __init__(self, token: str, gap: float = 0.35) -> None:
        import httpx
        self._h = {"Authorization": f"Bearer {token}", "Notion-Version": VERSION, "Content-Type": "application/json"}
        self._c = httpx.AsyncClient(base_url=API, headers=self._h, timeout=30)
        self.gap = gap

    async def close(self) -> None:
        await self._c.aclose()

    async def _call(self, method: str, url: str, body: Any = None) -> dict[str, Any]:
        for attempt in range(4):
            await asyncio.sleep(self.gap)
            r = await self._c.request(method, url, json=body)
            if r.status_code == 429 and attempt < 3:
                await asyncio.sleep(float(r.headers.get("Retry-After", "1")))
                continue
            data = r.json() if r.content else {}
            if r.status_code >= 400:
                raise NotionError(r.status_code, str(data.get("message") or data)[:300])   # 토큰은 메시지에 없다
            return data
        raise NotionError(429, "요청이 너무 많습니다")

    async def page(self, pid: str) -> dict[str, Any]:
        return await self._call("GET", f"/pages/{pid}")

    async def create_page(self, parent: str, title: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._call("POST", "/pages", {"parent": {"page_id": parent},
                                                   "properties": {"title": {"title": _rt(title)}}, "children": children})

    async def set_title(self, pid: str, title: str) -> None:
        await self._call("PATCH", f"/pages/{pid}", {"properties": {"title": {"title": _rt(title)}}})

    async def archive_page(self, pid: str) -> None:
        await self._call("PATCH", f"/pages/{pid}", {"archived": True})

    async def move_page(self, pid: str, parent: str) -> None:
        """부모 바꾸기 — 11-06 실제로 확인(POST /pages/{id}/move)."""
        await self._call("POST", f"/pages/{pid}/move", {"parent": {"type": "page_id", "page_id": parent}})

    async def children(self, bid: str) -> list[dict[str, Any]]:
        out, cur = [], None
        while True:
            q = f"/blocks/{bid}/children?page_size=100" + (f"&start_cursor={cur}" if cur else "")
            d = await self._call("GET", q)
            out += d.get("results", [])
            if not d.get("has_more"):
                return out
            cur = d.get("next_cursor")

    async def append(self, bid: str, children: list[dict[str, Any]], after: str | None = None) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"children": children}
        if after:
            body["after"] = after                   # 그 블록 바로 뒤에 — 자리를 지키며 갈아 끼울 때
        res = (await self._call("PATCH", f"/blocks/{bid}/children", body)).get("results", [])
        if after:                                   # 응답이 부모의 자식 전체로 올 수도 있다 — 새로 만든 것만 골라 돌려준다
            ids = [r["id"] for r in res]
            k = ids.index(after) + 1 if after in ids else 0
            return res[k:k + len(children)]
        return res[-len(children):] if len(res) > len(children) else res

    async def update_block(self, bid: str, block: dict[str, Any]) -> None:
        """블록 내용만 고친다 — 블록 id가 그대로라 사람이 바꿔 둔 보기(mermaid 미리보기)가 남는다(11-06 확인)."""
        t = block["type"]
        await self._call("PATCH", f"/blocks/{bid}", {t: {k: v for k, v in block[t].items() if k != "children"}})

    async def upload_file(self, name: str, data: bytes, content_type: str = "image/png") -> str:
        """파일 올리기(11-06 확인) — 만들기 → 보내기. 그림 블록에 {"type": "file_upload", "file_upload": {"id": …}}로 붙인다."""
        import httpx
        meta = await self._call("POST", "/file_uploads", {"filename": name, "content_type": content_type})
        h = {k: v for k, v in self._h.items() if k != "Content-Type"}
        async with httpx.AsyncClient(timeout=60) as hc:
            r = await hc.post(f"{API}/file_uploads/{meta['id']}/send", headers=h, files={"file": (name, data, content_type)})
        if r.status_code >= 400:
            raise NotionError(r.status_code, str((r.json() if r.content else {}).get("message"))[:300])
        return meta["id"]

    async def delete_block(self, bid: str) -> None:
        await self._call("DELETE", f"/blocks/{bid}")


# ── 범위 ────────────────────────────────────────────────────
def norm(pid: str) -> str:
    return pid.replace("-", "").lower()


class Scope:
    """FOREMAN 루트 아래인가 — 매번 Notion에서 부모를 따라 올라간다(캐시하지 않는다: 사람이 Notion에서 옮겼을 수 있다)."""

    def __init__(self, client: Any, root: str, max_depth: int = 12) -> None:
        self.c, self.root, self.max_depth = client, norm(root), max_depth

    async def under_root(self, pid: str) -> bool:
        cur = norm(pid)
        for _ in range(self.max_depth):
            if cur == self.root:
                return True
            try:
                p = await self.c.page(cur)
            except NotionError:
                return False
            if p.get("archived") or p.get("in_trash"):
                return False
            par = p.get("parent") or {}
            if par.get("type") != "page_id":
                return False                       # 워크스페이스 · 데이터베이스 · 블록 아래 — 우리가 만들지 않는 자리
            cur = norm(par["page_id"])
        return False

    async def require(self, pid: str, *, not_root: bool = True) -> None:
        if not_root and norm(pid) == self.root:
            raise OutOfScope("FOREMAN 루트 페이지 자체는 고치거나 지울 수 없습니다")
        if not await self.under_root(pid):
            raise OutOfScope("FOREMAN 페이지 아래가 아닙니다 — 건드리지 않습니다")


# ── 게시기 ──────────────────────────────────────────────────
SECTIONS = (("log/retro_", "회고"), ("portfolio/", "포트폴리오"))   # 원본 경로 앞부분 → 루트 아래 묶음 페이지. 그 밖은 "문서"


def section_of(path: str) -> str:
    return next((name for pre, name in SECTIONS if path.startswith(pre)), "문서")


def portfolio_title(path: str, title: str) -> str:
    """포트폴리오는 루트 바로 아래에 번호 붙은 제목으로(11-06 사용자 결정) — portfolio/00_overview.md → "00 한눈에 — …".
    번호는 파일 이름 앞(config/portfolio.toml의 slug)."""
    num = PurePosixPath(path).stem.split("_", 1)[0]
    return f"{num} {title}" if num.isdigit() and not title.startswith(num + " ") else title


def git_show(repo: str, path: str, ref: str = "HEAD") -> tuple[str, str]:
    """(본문, 그 파일을 마지막으로 바꾼 커밋 짧은 해시) — ref(FOREMAN은 main HEAD, 다른 프로젝트는 push된 origin/main)에 있는 것만."""
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or p.suffix != ".md" or not str(p).startswith(("log/", "docs/", "portfolio/")):
        raise OutOfScope("log/ · docs/ · portfolio/ 아래 .md만 게시합니다")
    r = subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        where = "main" if ref == "HEAD" else ref
        raise FileNotFoundError(f"{where}에 {path}가 없습니다 — 합친(push한) 뒤에 게시해 주세요")
    sha = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h", ref, "--", path],
                         capture_output=True, text=True, timeout=15).stdout.strip()
    return r.stdout, sha


def header_block(path: str, commit: str, ctx: Ctx, when: str) -> dict[str, Any]:
    rich = (_rt("이 페이지는 사본입니다 — 원본 ") + _rt(path, code=True, link=ctx.blob(path)) + _rt(" · 커밋 ")
            + _rt(commit, code=True, link=f"{ctx.gh}/commit/{commit}") + _rt(f" · 게시 {when}. 고칠 때는 git에서 고치고 다시 게시합니다."))
    return {"object": "block", "type": "callout", "callout": {"rich_text": rich, "icon": {"type": "emoji", "emoji": "📄"}, "color": "gray_background"}}


def footer_block(path: str, commit: str, ctx: Ctx, when: str) -> dict[str, Any]:
    """맨 아래 회색 한 줄(11-09 펫퍼민트 — 사본 상자 대신 "마지막 갱신 커밋은 작게"). Notion API엔 글자 크기가 없어 회색으로."""
    rich = _rt("마지막 갱신 — ") + _rt(commit, code=True, link=f"{ctx.gh}/commit/{commit}") + _rt(f" · {when}")
    for r in rich:
        r.setdefault("annotations", {})["color"] = "gray"
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich}}


SUBPAGES = ("child_page", "child_database")     # 맞추기가 절대 지우지 않는다 — 사람이 단 하위 페이지(펫퍼민트 01 · 02 아래 단계 문서)


def adopt_notion_shape(old: list[dict[str, Any]], new: list[dict[str, Any]], keep: set[str]) -> list[dict[str, Any]]:
    """Notion 모양이 기준인 차이를 새 블록에 옮겨 담는다(11-09 펫퍼민트 사용자 결정) — 그래서 사람 수정으로 멈추지도, 덮지도 않는다.
    inline_code: 글(plain)이 같고 꾸밈만 다르면(파일명을 인라인 코드로 감쌈) 새 블록의 글을 Notion 쪽 그대로.
    image: 저장소 그림 자리(_upload)를 Notion에 있는 그림 블록과 차례대로 짝지어 그 블록을 둔다(다시 올리지 않는다)."""
    out = [dict(b) for b in new]
    if "inline_code" in keep:
        pool: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for ob in old:
            t = ob.get("type")
            rt = (ob.get(t) or {}).get("rich_text")
            if rt:
                pool.setdefault((t, plain(rt)), []).append(ob)
        for i, nb in enumerate(out):
            t = nb.get("type")
            v = nb.get(t) or {}
            rt = v.get("rich_text")
            cand = pool.get((t, plain(rt))) if rt else None
            if cand and _norm_rt(rt) != _norm_rt((cand[0].get(t) or {}).get("rich_text")):
                ob = cand.pop(0)
                out[i] = {**nb, t: {**v, "rich_text": (ob.get(t) or {}).get("rich_text")}}
    if "heading" in keep:
        # 펫퍼민트 Notion 쪽 제목은 한 단계씩 낮다(## → heading_3 등 334건, 글은 같음 — 사용자 결정: Notion 단계 그대로)
        hp: dict[str, list[str]] = {}
        for ob in old:
            if str(ob.get("type", "")).startswith("heading_"):
                hp.setdefault(plain((ob.get(ob["type"]) or {}).get("rich_text") or []), []).append(ob["type"])
        for i, nb in enumerate(out):
            t = nb.get("type", "")
            if t.startswith("heading_"):
                cand = hp.get(plain((nb.get(t) or {}).get("rich_text") or []))
                if cand and cand[0] != t:
                    ot = cand.pop(0)
                    out[i] = {**{k: v for k, v in nb.items() if k != t}, "type": ot, ot: nb[t]}
    if "image" in keep:
        imgs = [ob for ob in old if ob.get("type") == "image"]
        for i, nb in enumerate(out):
            if "_upload" in nb and imgs and not PurePosixPath(nb["_upload"]).suffix.lower() == ".webm":
                ob = imgs.pop(0)
                out[i] = {"object": "block", "type": "image", "image": {}, "_keep_as": ob["id"]}
    return out


FOOTER_HEAD = "마지막 갱신 — "
_CHECK = re.compile(r"(?m)^\s*\[[ xX]\]\s+")
_NUMHEAD = re.compile(r"^[\d\-]+\.\s*")


def compact(s: str) -> str:
    """쪽 단위 비교용 글(11-09 펫퍼민트 "shape") — 꾸밈 표시(** ~~ `) · 체크박스 표시([ ] [x]) · 모든 공백 · 줄바꿈을 뺀다.
    그래서 블록 나눔(여러 문단 인용 · 강제 줄바꿈) · 표 칸 공백 · 블록 끝 줄바꿈 · 체크박스 ↔ to_do · 제목 단계 · 코드 언어 차이는 같게 본다."""
    s = _CHECK.sub("", s or "")
    s = s.replace("**", "").replace("~~", "").replace("`", "").replace("⏎", "")
    return re.sub(r"\s+", "", s)


def flat_md(blocks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """변환 블록을 (종류, 글)로 펼친다 — 표 줄은 칸을 이어서, 자식까지."""
    out: list[tuple[str, str]] = []
    for b in blocks:
        t = b.get("type")
        v = b.get(t) or {}
        if t == "table":
            out += [("table_row", "".join(plain(c) for c in r["table_row"]["cells"])) for r in v.get("children", [])]
            continue
        out.append((t, plain(v.get("rich_text") or [])))
        out += flat_md(v.get("children", []))
    return out


async def flat_notion(client: Any, bid: str) -> list[tuple[str, str]]:
    """Notion 블록을 (종류, 글)로 펼친다(하위 페이지 빼고, 자식까지)."""
    out: list[tuple[str, str]] = []
    for b in await client.children(bid):
        t = b.get("type")
        if t in SUBPAGES:
            out.append((t, (b.get(t) or {}).get("title", "")))
            continue
        v = b.get(t) or {}
        out.append((t, "".join(plain(c) for c in v.get("cells", [])) if t == "table_row" else plain(v.get("rich_text") or [])))
        if b.get("has_children"):
            out += await flat_notion(client, b["id"])
    return out


def shape_text(flat: list[tuple[str, str]], subpage_titles: set[str]) -> str:
    """쪽 전체를 한 줄로 — 맨 아래 갱신 줄 · 하위 페이지 블록 · 하위 페이지 제목과 같은 문서 목록 줄(펫퍼민트 pipeline 7절)은 뺀다."""
    keys = {compact(x) for t in subpage_titles for x in (t, _NUMHEAD.sub("", t))}

    def doc_list(t: str, c: str) -> bool:
        # 하위 페이지 제목과 같은 줄, 또는 그 제목으로 시작하는 목록 줄("모니터링 (Prometheus·Grafana)" ↔ "15. 모니터링")
        return c in keys or (t.endswith("list_item") and any(len(k) >= 2 and c.startswith(k) for k in keys))
    return "".join(c for t, x in flat if t not in SUBPAGES and not x.startswith(FOOTER_HEAD)
                   and (c := compact(x)) and not doc_list(t, c))


def _btext(b: dict[str, Any]) -> str:
    t = b.get("type")
    return plain((b.get(t) or {}).get("rich_text") or [])


async def shape_patch(client: Any, pid: str, prev: list[dict[str, Any]], new: list[dict[str, Any]], path: str,
                      url: str | None) -> dict[str, int]:
    """지난 git(prev) → 새 git(new)에서 바뀐 맨 위 블록만 Notion에 옮긴다. Notion 블록은 같은 글(compact)로 찾고, 종류는 Notion 것.
    - 글이 바뀐 블록: 그 Notion 블록의 글만 고친다   - 빠진 블록: 그 Notion 블록을 지운다   - 새 블록: 앞 블록 뒤에 끼운다
    짝이 하나로 안 맞으면(그 글의 Notion 블록이 없거나 여럿 · 표 · 자식이 있는 블록 · 빈 블록) 아무것도 쓰기 전에 멈춘다(HumanEdited)."""
    import difflib
    st = {"kept": 0, "updated": 0, "replaced": 0, "added": 0, "deleted": 0, "reset": 0}
    old = [b for b in await client.children(pid) if b.get("type") not in SUBPAGES
           and not (b.get("type") == "paragraph" and _btext(b).startswith(FOOTER_HEAD))]
    oc = [compact(_btext(b)) for b in old]

    def find(c: str, what: str) -> int:
        hits = [k for k, x in enumerate(oc) if x == c]
        if not c or len(hits) != 1:
            raise HumanEdited(path, [f"git에서 바뀐 블록({what})이 Notion에서 {'빈 블록' if not c else f'{len(hits)}곳'}이라 "
                                     f"자동으로 맞추지 않았습니다 — 그 자리를 Notion에서 직접 고치거나 [Notion 수정 버리고 덮기]"], url)
        return hits[0]

    def simple(b: dict[str, Any]) -> bool:
        t = b.get("type")
        return t not in ("table", "image", "video") and "children" not in (b.get(t) or {})

    pc, nc = [compact(_btext(b)) for b in prev], [compact(_btext(b)) for b in new]
    plan: list[tuple[str, Any, Any]] = []                       # 먼저 다 정하고(멈출 일이 있으면 아무것도 안 쓴다) 나중에 쓴다
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=pc, b=nc, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for b in prev[i1:i2] + new[j1:j2]:
            if not simple(b):
                raise HumanEdited(path, [f"git에서 바뀐 곳에 표 · 그림 · 안쪽 목록이 있어 자동으로 맞추지 않았습니다({_btext(b)[:30] or b.get('type')})"], url)
        if tag == "replace" and i2 - i1 == j2 - j1:
            for pb, nb in zip(prev[i1:i2], new[j1:j2]):
                plan.append(("update", find(compact(_btext(pb)), _btext(pb)[:30]), nb))
            continue
        for pb in prev[i1:i2]:
            plan.append(("delete", find(compact(_btext(pb)), _btext(pb)[:30]), None))
        if j2 > j1:
            anchor = find(pc[i1 - 1], _btext(prev[i1 - 1])[:30]) if i1 > 0 else None
            if anchor is None:
                raise HumanEdited(path, ["git 맨 앞에 블록이 생겨 자동으로 맞추지 않았습니다(Notion API는 맨 앞에 끼울 수 없다)"], url)
            plan.append(("insert", anchor, new[j1:j2]))
    for op, k, nb in plan:
        ob = old[k]
        if op == "update":
            ot = ob["type"]
            await client.update_block(ob["id"], {"type": ot, ot: {"rich_text": (nb.get(nb["type"]) or {}).get("rich_text") or []}})
            st["updated"] += 1
        elif op == "delete":
            await client.delete_block(ob["id"])
            st["deleted"] += 1
        else:
            await append_tree(client, pid, nb, after=ob["id"])
            st["added"] += len(nb)
    return st


def renamed_from(repo: str, old_ref: str, new_ref: str, path: str) -> str:
    """new_ref의 path가 old_ref에서는 어느 경로였나(git 이름 바꾸기 기록). 못 찾으면 path 그대로."""
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", "diff", "-M", "--name-status", "-z", old_ref, new_ref],
                       capture_output=True, timeout=20)
    parts = r.stdout.decode("utf-8", "replace").split("\0") if r.returncode == 0 else []
    i = 0
    while i < len(parts):
        st = parts[i]
        if st.startswith(("R", "C")) and i + 2 < len(parts):
            if parts[i + 2] == path:
                return parts[i + 1]
            i += 3
        else:
            i += 2
    return path


def shape_diff(a: str, b: str, n: int = 5) -> list[str]:
    """Notion 글(a)과 git 글(b)이 갈리는 곳 몇 군데 — 알림 · 서기 할 일에 "▶ Notion '…' ↔ git '…'"."""
    import difflib
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            out.append(f"Notion '{a[max(0, i1 - 8):i2 + 8][:40]}' ↔ git '{b[max(0, j1 - 8):j2 + 8][:40]}'")
            if len(out) >= n:
                break
    return out


def adopt_by_compact(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """글(compact)이 같은 블록은 Notion 블록 모양을 그대로 쓴다(체크박스 ↔ to_do, 코드 언어, 끝 줄바꿈 등) — git만 바뀐 쪽을
    맞출 때 바뀌지 않은 블록까지 git 모양으로 다시 쓰지 않게(11-09). 자식이 있는 블록은 자식은 새 것으로."""
    pool: dict[str, list[dict[str, Any]]] = {}
    for ob in old:
        t = ob.get("type")
        if t in SUBPAGES or t == "table":
            continue
        pool.setdefault(compact(plain((ob.get(t) or {}).get("rich_text") or [])), []).append(ob)
    out = []
    for nb in new:
        t = nb.get("type")
        v = nb.get(t) or {}
        key = compact(plain(v.get("rich_text") or [])) if t not in ("table",) else None
        cand = pool.get(key) if key else None
        if cand:
            ob = cand.pop(0)
            ot = ob["type"]
            keep = {k: x for k, x in (ob.get(ot) or {}).items() if k in ("rich_text", "checked", "language", "color", "caption")}
            if "children" in v:
                keep["children"] = v["children"]
            out.append({"object": "block", "type": ot, ot: keep})
        else:
            out.append(nb)
    return out


def _strip_children(b: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """표는 줄을 같이 만들어야 해서 그대로, 그 밖의 자식은 떼어 두었다가 만든 뒤 붙인다(깊이 제한 없이)."""
    if b["type"] == "table":
        return b, []
    inner = dict(b[b["type"]])
    kids = inner.pop("children", [])
    return {**b, b["type"]: inner}, kids


async def append_tree(client: Any, parent: str, blocks: list[dict[str, Any]], after: str | None = None) -> int:
    """블록들을 붙인다(자식은 만든 뒤 붙인다). after를 주면 그 블록 바로 뒤에 차례로."""
    blocks = [b for b in blocks if "_keep_as" not in b]     # Notion에 있는 그림을 두기로 한 자리 — 새로 만들 것이 없다(11-09)
    n = 0
    for k in range(0, len(blocks), CHUNK):
        part = [_strip_children(b) for b in blocks[k:k + CHUNK]]
        made = await client.append(parent, [b for b, _ in part], after=after)
        n += len(part)
        for (_, kids), m in zip(part, made, strict=False):
            if kids:
                n += await append_tree(client, m["id"], kids)
        if after and made:
            after = made[-1]["id"]
    return n


# ── 다시 게시 — 자리를 지키며 갈아 끼우기(11-06) ──────────────
# 모두 지우고 새로 붙이면 사람이 바꿔 둔 보기(mermaid 미리보기)가 날아간다. API로는 그 보기를 정할 수 없다(code에 caption ·
# language · rich_text뿐). 블록 내용만 고치면 id가 그대로라 보기가 남는다 — 자리마다 같은 종류면 고치고, 다르면 그 하나만 바꾼다
UPDATABLE = {"paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "quote", "code",
             "callout", "to_do", "table_row"}


def _norm_rt(rt: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    out = []
    for t in rt or []:
        tx = t.get("text") or {}
        a = t.get("annotations") or {}
        out.append((tx.get("content", t.get("plain_text", "")), (tx.get("link") or {}).get("url"),
                    bool(a.get("bold")), bool(a.get("code"))))
    return out


def _same(old: dict[str, Any], new: dict[str, Any]) -> bool:
    t = new["type"]
    o, n = old.get(t) or {}, new.get(t) or {}
    if t == "table_row":
        return [_norm_rt(c) for c in o.get("cells", [])] == [_norm_rt(c) for c in n.get("cells", [])]
    return _norm_rt(o.get("rich_text")) == _norm_rt(n.get("rich_text")) and o.get("language") == n.get("language")


def _sig(b: dict[str, Any]) -> tuple[Any, ...]:
    """맞대기용 블록 지문 — 종류 + 글(+ 코드 언어 · 표 폭). 사진 · 동영상은 늘 다르게(파일이 바뀌었을 수 있다 — 매번 새로 올린다)."""
    t = b.get("type")
    v = b.get(t) or {}
    if t in ("image", "video"):
        # Notion에 있는 그림을 그대로 두기로 짝지은 새 블록(_keep_as)은 그 블록과 같은 지문 — 맞대기에서 "같음"(11-09)
        return (t, b.get("_keep_as") or (b.get("id") if b.get("id") and "_upload" not in b else None) or id(b))
    if t == "table":
        return (t, v.get("table_width"))
    return (t, tuple(x[0] for x in _norm_rt(v.get("rich_text"))), v.get("language"))


async def _keep_pair(client: Any, ob: dict[str, Any], nb: dict[str, Any], st: dict[str, int]) -> bool:
    """old 블록 자리에 new를 — 같은 종류면 내용만 고치고 id를 지킨다(mermaid 미리보기가 남는다). 못 하면 False."""
    t = nb["type"]
    if ob["type"] == t and t in UPDATABLE:
        body, kids = _strip_children(nb)
        if _same(ob, body):
            st["kept"] += 1
        else:
            await client.update_block(ob["id"], body)
            st["updated"] += 1
        if kids or ob.get("has_children"):
            await sync_children(client, ob["id"], kids, st)
        return True
    if ob["type"] == t == "table" and (ob.get("table") or {}).get("table_width") == nb["table"]["table_width"]:
        await sync_children(client, ob["id"], nb["table"]["children"], st)
        return True
    if ob["type"] == t == "divider":
        st["kept"] += 1
        return True
    return False


async def _insert_after(client: Any, parent: str, blocks: list[dict[str, Any]], anchor: str) -> str:
    """anchor 뒤에 blocks를 끼우고, 끼운 마지막 블록 id를 돌려준다(다음 끼우기의 자리)."""
    await append_tree(client, parent, blocks, after=anchor)
    ids = [b["id"] for b in await client.children(parent)]
    k = ids.index(anchor) + len(blocks) if anchor in ids else -1
    return ids[k] if 0 <= k < len(ids) else anchor


async def sync_children(client: Any, parent: str, new: list[dict[str, Any]], stats: dict[str, int] | None = None) -> dict[str, int]:
    """parent의 자식을 new에 맞춘다 — **내용으로 짝짓는다**(difflib). 같은 블록은 그대로, 바뀐 구간만 고친다.
    11-06 — 자리 순서로 맞대던 때는 글 앞에 사진 한 장을 끼우면 뒤 블록이 모두 한 칸씩 밀려 새 블록이 되고,
    사람이 미리보기로 바꿔 둔 mermaid가 모두 풀렸다. Notion API는 맨 앞에 끼울 수 없어(after만 있다), 맨 앞부터 다르면
    전부 갈아 끼운다(reset)."""
    import difflib
    st = stats if stats is not None else {"kept": 0, "updated": 0, "replaced": 0, "added": 0, "deleted": 0, "reset": 0}
    # 하위 페이지 블록은 보지도 지우지도 않는다(11-09 — 지우면 그 페이지가 휴지통으로 간다)
    old = [b for b in await client.children(parent) if b.get("type") not in SUBPAGES]
    ops = difflib.SequenceMatcher(a=[_sig(b) for b in old], b=[_sig(b) for b in new], autojunk=False).get_opcodes()
    if old and ops and ops[0][0] == "insert":         # 맨 앞에 끼워야 한다 — API로 못 하니 예전 방식
        return await _sync_positional(client, parent, old, new, st)
    anchor: str | None = None
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for ob, nb in zip(old[i1:i2], new[j1:j2]):
                await _keep_pair(client, ob, nb, st)
                anchor = ob["id"]
            continue
        olds, news = old[i1:i2], new[j1:j2]
        # 바뀐 구간 — 같은 자리 · 같은 종류는 내용만 고친다(id 유지), 나머지는 지우고 끼운다
        k = 0
        while k < len(olds) and k < len(news) and await _keep_pair(client, olds[k], news[k], st):
            anchor = olds[k]["id"]
            k += 1
        if news[k:] and anchor is None:              # 맨 앞에 다른 것을 끼워야 한다 — 지우기 전에 예전 방식으로
            return await _sync_positional(client, parent, [b for b in await client.children(parent) if b.get("type") not in SUBPAGES],
                                          new, st)
        for ob in olds[k:]:
            await client.delete_block(ob["id"])
            st["deleted"] += 1
        if news[k:]:
            anchor = await _insert_after(client, parent, news[k:], anchor)
            st["added" if not olds else "replaced"] += len(news) - k
    return st


async def _sync_positional(client: Any, parent: str, old: list[dict[str, Any]], new: list[dict[str, Any]],
                           st: dict[str, int]) -> dict[str, int]:
    """예전 방식(자리 순서) — 맨 앞부터 다를 때만."""
    anchor: str | None = None
    for i, nb in enumerate(new):
        if i >= len(old):
            st["added"] += len(new) - i
            await append_tree(client, parent, new[i:], after=anchor)
            return st
        ob, t = old[i], nb["type"]
        if ob["type"] == t and t in UPDATABLE:
            body, kids = _strip_children(nb)
            if _same(ob, body):
                st["kept"] += 1
            else:
                await client.update_block(ob["id"], body)
                st["updated"] += 1
            if kids or ob.get("has_children"):
                await sync_children(client, ob["id"], kids, st)
            anchor = ob["id"]
        elif ob["type"] == t == "table" and (ob.get("table") or {}).get("table_width") == nb["table"]["table_width"]:
            await sync_children(client, ob["id"], nb["table"]["children"], st)
            anchor = ob["id"]
        elif ob["type"] == t == "divider":
            st["kept"] += 1
            anchor = ob["id"]
        elif anchor is None:
            for b in old:                           # 맨 앞부터 달라 붙일 자리가 없다 — 전부 갈아 끼운다
                await client.delete_block(b["id"])
            st["reset"] += 1
            st["deleted"] += len(old)
            st["added"] += len(new)
            await append_tree(client, parent, new)
            return st
        else:
            await client.delete_block(ob["id"])
            await append_tree(client, parent, [nb], after=anchor)
            got = await client.children(parent)     # 새로 만든 블록 id — anchor 바로 뒤
            ids = [b["id"] for b in got]
            anchor = ids[ids.index(anchor) + 1] if anchor in ids and ids.index(anchor) + 1 < len(ids) else anchor
            st["replaced"] += 1
    for ob in old[len(new):]:
        await client.delete_block(ob["id"])
        st["deleted"] += 1
    return st


def content_digest(repo: str, path: str, body: str, ref: str = "HEAD") -> str:
    """게시 내용의 지문 — 본문 + 글이 가리키는 사진 파일 내용(11-06 — 사진만 다시 찍어 바꿨는데 본문이 같아 "바뀐 것 없음"으로
    건너뛰었다). 사진을 못 읽으면 그 경로만 넣는다(게시 때 그 사실이 따로 드러난다)."""
    h = hashlib.sha256(body.encode())
    _, blocks = md_to_blocks(body, Ctx(path, "HEAD", links=False))
    for b in blocks:
        if "_upload" in b:
            h.update(b"\0" + b["_upload"].encode())
            try:
                h.update(hashlib.sha256(git_bytes(repo, b["_upload"], ref)).digest())
            except (OutOfScope, FileNotFoundError):
                pass
    return h.hexdigest()


def git_bytes(repo: str, path: str, ref: str = "HEAD") -> bytes:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or p.suffix.lower() not in CTYPES or not str(p).startswith(("portfolio/", "docs/", "log/")):
        raise OutOfScope(f"그림은 저장소 안 portfolio/ · docs/ · log/의 PNG · JPG · GIF · WebM만 올립니다: {path}")
    r = subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True, timeout=15)
    if r.returncode != 0:
        raise FileNotFoundError(f"main에 커밋된 그림 {path}가 없습니다")
    return r.stdout


CTYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webm": "video/webm"}


async def resolve_uploads(client: Any, repo: str, blocks: list[dict[str, Any]], limit: int | None = None,
                          ref: str = "HEAD") -> list[dict[str, Any]]:
    """그림 자리(_upload)를 파일로 올려 그림 블록으로 — 게시할 때마다 올린다(그림이 바뀌었을 수 있다).
    형식은 확장자로(11-06 — GIF를 image/jpeg로 보내고 있었다), .webm은 동영상 블록. limit(워크스페이스 파일 한도)를 넘으면
    보내지 않고 거부한다 — Notion에서 처음 알면 그 글이 반쯤 올라간 채로 남는다(13, 무료 5MB)."""
    out = []
    for b in blocks:
        if "_upload" in b:
            data = git_bytes(repo, b["_upload"], ref)
            if limit and len(data) > limit:
                raise OutOfScope(f"{b['_upload']}가 {len(data) / 1e6:.1f}MB로 Notion 파일 한도 {limit / 1e6:.1f}MB를 넘습니다 — "
                                 "줄여서(tools/screen.py --colors · --every · --clip) 다시 커밋해 주세요")
            ext = PurePosixPath(b["_upload"]).suffix.lower()
            fid = await client.upload_file(PurePosixPath(b["_upload"]).name, data, CTYPES.get(ext, "image/png"))
            kind = "video" if ext == ".webm" else "image"
            b = {"object": "block", "type": kind,
                 kind: {"type": "file_upload", "file_upload": {"id": fid}, "caption": b["image"].get("caption", [])}}
        else:
            t = b["type"]
            kids = (b.get(t) or {}).get("children")
            if kids and t != "table":
                b = {**b, t: {**b[t], "children": await resolve_uploads(client, repo, kids, limit, ref)}}
        out.append(b)
    return out


class Publisher:
    """doc_publish 기록 + 범위 확인 + 게시 · 다시 게시 · 내리기. DB는 store(engine)로, Notion은 client로."""

    def __init__(self, engine: Any, client: Any, root: str, repo: str, project: str = "foreman", gh: str = GH,
                 ref: str = "HEAD", docs_page: str | None = None, portfolio_page: str | None = None,
                 docs_mode: str = "off", quiet_min: float = 30, opts: dict[str, Any] | None = None) -> None:
        """Notion 구조(11-09 사용자 결정): 「프로젝트」 > 프로젝트 페이지(root) > [기술문서](docs_page) · [포트폴리오](portfolio_page).
        ref — 어느 커밋을 원본으로 보나. FOREMAN은 HEAD(이 저장소 main), 다른 프로젝트는 origin/main(push된 것 — Notion은 GitHub에
        있는 것의 사본이다, 런슈즈 요청 3-1). docs_mode — off(docs/를 올리지 않는다) · manual · auto(push 뒤 quiet_min분 조용하면
        바뀐 파일만 자동으로, bridge/docsync.py)."""
        self.e, self.c, self.root, self.repo, self.project, self.gh = engine, client, norm(root), repo, project, gh
        self.ref, self.docs_mode, self.quiet_min = ref, docs_mode, quiet_min
        self.docs_page = norm(docs_page) if docs_page else None
        self.portfolio_page = norm(portfolio_page) if portfolio_page else None
        self.scope = Scope(client, root)
        # 11-09 펫퍼민트(사용자 결정) — 사람이 옮겨 둔 기존 페이지에 맞춘다. 기본값은 지금까지 동작 그대로
        o = opts or {}
        self.create = o.get("create", True) is not False          # False: 짝(doc_publish)이 없으면 만들지 않고 실패로 남긴다
        self.keep_title = o.get("title") == "keep"                 # 제목을 건드리지 않는다("00. 모델 준비" — 사이드바 순서)
        self.keep_order = o.get("order") == "keep"                 # 페이지를 옮기거나 차례를 바꾸지 않는다
        self.footer = o.get("header") == "footer"                  # 맨 위 사본 상자 대신 맨 아래 회색 한 줄
        self.keep_notion = set(o.get("keep_notion") or [])         # inline_code · image — Notion 모양이 기준
        self.skip = set(o.get("skip") or [])                       # 맞추기 대상이 아닌 docs 파일

    async def parent_for(self, path: str) -> str:
        """글이 놓일 페이지 — 포트폴리오는 [포트폴리오](없으면 루트 바로 아래, 11-06 방식), docs/는 [기술문서], 그 밖은 묶음 페이지."""
        if path.startswith("portfolio/"):
            return self.portfolio_page or self.root
        if path.startswith("docs/") and self.docs_page:
            return self.docs_page
        return await self._section(section_of(path))

    async def _row(self, path: str) -> dict[str, Any] | None:
        from sqlalchemy import text
        async with self.e.connect() as c:
            r = (await c.execute(text("SELECT * FROM doc_publish WHERE project = :p AND path = :f"),
                                 {"p": self.project, "f": path})).mappings().first()
        return dict(r) if r else None

    async def _save(self, path: str, **kw: Any) -> None:
        from sqlalchemy import text
        cols = ["project", "path", *kw]
        upd = ", ".join(f"{k} = VALUES({k})" for k in kw)
        async with self.e.begin() as c:
            await c.execute(text(f"INSERT INTO doc_publish ({', '.join(cols)}) VALUES ({', '.join(':' + k for k in cols)}) "
                                 f"ON DUPLICATE KEY UPDATE {upd}"), {"project": self.project, "path": path, **kw})

    async def _upload_limit(self) -> int | None:
        """워크스페이스 파일 한도(바이트) — GET /users/me의 bot.workspace_limits(11-06 확인: 5,242,880). 못 읽으면 None(검사 없이)."""
        if not hasattr(self, "_limit"):
            try:
                me = await self.c._call("GET", "/users/me")
                self._limit = ((me.get("bot") or {}).get("workspace_limits") or {}).get("max_file_upload_size_in_bytes")
            except Exception:  # noqa: BLE001 — 가짜 클라이언트 · 권한 없음 — 한도 검사만 건너뛴다
                self._limit = None
        return self._limit

    async def _section(self, name: str) -> str:
        """루트 아래 묶음 페이지(「회고」 등) — 없거나 지워졌으면 만든다. 기록 경로는 `@section/<이름>`."""
        key = f"@section/{name}"
        r = await self._row(key)
        if r and r["status"] == "published" and r["notion_page_id"] and await self.scope.under_root(r["notion_page_id"]):
            return r["notion_page_id"]
        p = await self.c.create_page(self.root, name, [])
        await self._save(key, kind="section", title=name, notion_page_id=norm(p["id"]), parent_page_id=self.root,
                         status="published", url=p.get("url"), error=None)
        return norm(p["id"])

    async def _me(self) -> str | None:
        """우리 통합(봇)의 사용자 id — 블록을 마지막으로 고친 쪽이 우리인지 본다. 못 읽으면 None(사람 수정 검사를 건너뛴다)."""
        if not hasattr(self, "_me_id"):
            try:
                self._me_id = norm((await self.c._call("GET", "/users/me"))["id"])
            except Exception:  # noqa: BLE001 — 가짜 클라이언트 · 권한 없음
                self._me_id = None
        return self._me_id

    async def human_edits(self, pid: str, new: list[dict[str, Any]]) -> list[str]:
        """Notion에서 사람이 고친(또는 더한) 블록 — 마지막으로 고친 쪽이 우리 봇이 아니고, 글이 새 원본의 어느 블록과도 다른 것.
        11-09 사용자 결정: git이 원본이지만, 사람이 고친 것을 덮지 않고 알린다("git과 Notion이 조용히 갈라진다"를 막는다).
        mermaid 코드는 뺀다 — 미리보기로만 바꿔도 마지막으로 고친 쪽이 사람이 된다. 돌려주는 값: 블록 글 앞부분들."""
        me = await self._me()
        if not me:
            return []
        sigs = {_sig(b) for b in new}
        out = []
        for b in await self.c.children(pid):
            t = b.get("type")
            le = b.get("last_edited_by") or {}
            if t in ("child_page", "child_database") or not le.get("id") or norm(le["id"]) == me:
                continue
            if t == "code" and (b.get("code") or {}).get("language") == "mermaid":
                continue
            if _sig(b) not in sigs:
                out.append(plain((b.get(t) or {}).get("rich_text") or [])[:60] or f"({t})")
        return out

    async def publish(self, path: str, when: str = "", force: bool = False, title: str | None = None) -> dict[str, Any]:
        """force — Notion에서 사람이 고친 블록이 있어도 git 원본으로 덮는다([Notion 수정 버리고 덮기]). 아니면 HumanEdited.
        title — 페이지 제목을 정해 준다(기술문서: "파일 이름 — README 표 설명", bridge/docsync.titles). 없으면 첫 H1 · 파일 이름."""
        given = title
        body, commit = git_show(self.repo, path, self.ref)
        digest = content_digest(self.repo, path, body, self.ref)
        portfolio = path.startswith("portfolio/")      # 바깥 사람이 읽는 글 — 저장소 링크 없이, 맨 위 "사본" 안내 없이(11-06)
        ctx = Ctx(path, commit or "HEAD", self.gh, links=not portfolio)
        title, blocks = md_to_blocks(body, ctx)
        title = given or title or PurePosixPath(path).stem
        if portfolio:
            title = portfolio_title(path, title)
        elif self.footer:
            blocks = blocks + [footer_block(path, commit or "HEAD", ctx, when)]     # 11-09 펫퍼민트 — 포트폴리오로 보여 줄 문서
        else:
            blocks = [header_block(path, commit or "HEAD", ctx, when)] + blocks
        row = await self._row(path)
        if row and row["status"] == "published" and row["notion_page_id"]:
            pid = row["notion_page_id"]
            if await self.scope.under_root(pid):
                if self.keep_title:
                    title = row["title"]
                # 정해진 자리([포트폴리오] · [기술문서])가 아니면 옮긴다(옮긴 순서대로 쌓인다). keep_order면 사람이 둔 자리 그대로
                want = await self.parent_for(path)
                if not self.keep_order and (portfolio or path.startswith("docs/")) and norm(row["parent_page_id"] or "") != want:
                    await self.c.move_page(pid, want)
                    await self._save(path, parent_page_id=want)
                if not self.keep_title and row["title"] != title:
                    await self.c.set_title(pid, title)
                    await self._save(path, title=title)
                if row["content_hash"] == digest:
                    return {"path": path, "action": "unchanged", "page_id": pid, "url": row["url"], "commit": commit,
                            "title": title}
                if "shape" in self.keep_notion:
                    return await self._publish_shape(path, pid, row, blocks, commit, digest, title, force)
                if self.keep_notion:
                    blocks = adopt_notion_shape(await self.c.children(pid), blocks, self.keep_notion)
                if not force and (edits := await self.human_edits(pid, blocks)):
                    raise HumanEdited(path, edits, row["url"])
                blocks = await resolve_uploads(self.c, self.repo, blocks, await self._upload_limit(), self.ref)
                st = await sync_children(self.c, pid, blocks)    # 같은 페이지 · 같은 URL, 바뀐 블록만(mermaid 미리보기가 남는다)
                if not self.keep_title:
                    await self.c.set_title(pid, title)
                await self._save(path, kind="doc", title=title, commit_sha=commit, content_hash=digest, status="published", error=None)
                return {"path": path, "action": "updated", "page_id": pid, "url": row["url"], "commit": commit, "sync": st}
            # Notion에서 지워졌거나 범위 밖으로 옮겨졌다 — 그 페이지는 두고 새로 만든다
        if not self.create:
            # 11-09 펫퍼민트 — 사람이 옮겨 둔 페이지에만 맞춘다. 짝이 없거나 범위 밖이면 새로 만들지 않고 멈춘다(사용자: 새 페이지 0)
            raise OutOfScope(f"짝 페이지가 없거나 범위 밖입니다 — 새 페이지를 만들지 않습니다(create = false): {path}")
        blocks = await resolve_uploads(self.c, self.repo, blocks, await self._upload_limit(), self.ref)
        parent = await self.parent_for(path)
        await self.scope.require(parent, not_root=parent != self.root)
        p = await self.c.create_page(parent, title, [])
        pid = norm(p["id"])
        n = await append_tree(self.c, pid, blocks)
        await self._save(path, kind="doc", title=title, notion_page_id=pid, parent_page_id=parent, commit_sha=commit,
                         content_hash=digest, status="published", url=p.get("url"), error=None)
        return {"path": path, "action": "created", "page_id": pid, "url": p.get("url"), "commit": commit, "blocks": n}

    async def _publish_shape(self, path: str, pid: str, row: dict[str, Any], blocks: list[dict[str, Any]], commit: str | None,
                             digest: str, title: str, force: bool) -> dict[str, Any]:
        """쪽 단위 비교(11-09 펫퍼민트 — 모양 예외가 끝없이 늘어서). 글(compact)로만 견준다:
        - Notion == 새 git → 글이 같다. Notion은 손대지 않고 맨 아래 갱신 줄만(모양은 Notion 그대로)
        - Notion == 지난번 맞춘 git(row.commit_sha) → Notion은 그대로고 git만 바뀌었다. 같은 글 블록은 Notion 블록을 두고 나머지만 맞춘다
        - 그 밖 → 누군가 Notion 글을 고쳤다(또는 처음이라 알 수 없다) — HumanEdited, 어디가 다른지 몇 군데
        force면 마지막 경우도 git으로 맞춘다."""
        footer = blocks[-1] if self.footer else None
        body = blocks[:-1] if footer else blocks
        nflat = await flat_notion(self.c, pid)
        subs = {x for t, x in nflat if t in SUBPAGES}
        old_t, new_t = shape_text(nflat, subs), shape_text(flat_md(body), subs)
        if old_t == new_t:
            st = await self._ensure_footer(pid, footer)
        else:
            prev_t, pbl = None, None
            if row.get("commit_sha"):
                try:
                    # 지난번 맞춘 글 — 그 뒤 옮겼으면(git mv) 그때 경로로 읽는다(11-09 펫퍼민트 docs/02_pipeline/ 이동)
                    pb, _ = git_show(self.repo, renamed_from(self.repo, row["commit_sha"], self.ref, path), row["commit_sha"])
                    _, pbl = md_to_blocks(pb, Ctx(path, row["commit_sha"], self.gh))
                    prev_t = shape_text(flat_md(pbl), subs)
                except (FileNotFoundError, OutOfScope):
                    prev_t, pbl = None, None
            if old_t != prev_t or pbl is None:
                if not force:
                    raise HumanEdited(path, shape_diff(old_t, new_t), row["url"])
                old = await self.c.children(pid)
                body = adopt_by_compact(old, adopt_notion_shape(old, body, self.keep_notion))
                body = await resolve_uploads(self.c, self.repo, body, await self._upload_limit(), self.ref)
                st = await sync_children(self.c, pid, body + ([footer] if footer else []))
            else:
                # Notion은 지난번 git 그대로 — git에서 바뀐 블록만 그 자리에서 고친다(11-09: 쪽 전체를 다시 맞추면 바뀌지 않은 곳의
                # Notion 모양 — 나뉜 인용 · 빈 줄 — 까지 git 모양으로 바뀌었다). 짝이 하나로 안 맞으면 맞추지 않고 멈춘다
                st = await shape_patch(self.c, pid, pbl, body, path, row["url"])
                st2 = await self._ensure_footer(pid, footer)
                st = {k: st.get(k, 0) + st2.get(k, 0) for k in set(st) | set(st2)}
        await self._save(path, kind="doc", title=title, commit_sha=commit, content_hash=digest, status="published", error=None)
        return {"path": path, "action": "footer" if old_t == new_t else "updated", "page_id": pid, "url": row["url"],
                "commit": commit, "sync": st}

    async def _ensure_footer(self, pid: str, footer: dict[str, Any] | None) -> dict[str, int]:
        """맨 아래 갱신 줄만 넣거나 고친다 — 다른 블록은 건드리지 않는다."""
        st = {"kept": 0, "updated": 0, "replaced": 0, "added": 0, "deleted": 0, "reset": 0}
        if not footer:
            return st
        kids = [b for b in await self.c.children(pid) if b.get("type") not in SUBPAGES]
        last = kids[-1] if kids else None
        if last and last.get("type") == "paragraph" and plain(last["paragraph"].get("rich_text") or []).startswith(FOOTER_HEAD):
            if _same(last, footer):
                st["kept"] += 1
            else:
                await self.c.update_block(last["id"], footer)
                st["updated"] += 1
        else:
            await append_tree(self.c, pid, [footer], after=last["id"] if last else None)
            st["added"] += 1
        return st

    async def archive(self, path: str) -> dict[str, Any]:
        """내리기 = 휴지통. 우리가 만든 페이지이고 지금도 루트 아래일 때만."""
        if not self.create:
            raise OutOfScope("create = false 프로젝트는 페이지를 휴지통으로 보내지 않습니다 — 사람이 옮겨 둔 페이지입니다")
        row = await self._row(path)
        if not row or row["status"] != "published" or not row["notion_page_id"]:
            raise OutOfScope("게시한 기록이 없는 글입니다 — 우리가 만든 페이지만 내립니다")
        await self.scope.require(row["notion_page_id"])
        await self.c.archive_page(row["notion_page_id"])
        await self._save(path, status="archived")
        return {"path": path, "action": "archived", "page_id": row["notion_page_id"]}

    async def move(self, path: str, section: str) -> dict[str, Any]:
        """옮기기 — 우리가 만든 글을 루트 아래 다른 묶음 페이지로. 글과 목적지 둘 다 지금 루트 아래여야 한다."""
        row = await self._row(path)
        if not row or row["status"] != "published" or not row["notion_page_id"]:
            raise OutOfScope("게시한 기록이 없는 글입니다 — 우리가 만든 페이지만 옮깁니다")
        await self.scope.require(row["notion_page_id"])
        dest = await self._section(section)
        await self.scope.require(dest)
        await self.c.move_page(row["notion_page_id"], dest)
        await self._save(path, parent_page_id=dest)
        return {"path": path, "action": "moved", "page_id": row["notion_page_id"], "section": section}

    async def reorder_portfolio(self) -> dict[str, Any]:
        """포트폴리오를 번호(파일 이름)순으로 다시 세운다(11-06 — 사이에 새 주제를 끼웠다). Notion은 만든 · 옮긴 순서로 쌓고
        API로 자리를 정할 수 없어서, 모두 임시 묶음 「정렬 중」으로 옮겼다가 번호순으로 루트에 되돌린다(페이지 · URL · 블록 그대로)."""
        from sqlalchemy import text
        async with self.e.connect() as c:
            rows = (await c.execute(text(
                "SELECT path, notion_page_id FROM doc_publish WHERE project = :p AND kind = 'doc' AND status = 'published' "
                "AND path LIKE :pre ORDER BY path"), {"p": self.project, "pre": "portfolio/%"})).all()
        return await self.reorder([(r[0], r[1]) for r in rows], self.portfolio_page or self.root, force=True)

    async def reorder(self, rows: list[tuple[str, str]], parent: str, force: bool = False) -> dict[str, Any]:
        """rows(경로, 페이지) 순서대로 parent 아래에 다시 세운다 — 임시 묶음 「정렬 중」으로 옮겼다가 순서대로 되돌린다(페이지 · URL ·
        블록 그대로). parent 아래 우리 페이지들의 지금 순서가 이미 같으면 옮기지 않는다(force면 늘). 사람이 만든 페이지는 건드리지 않는다."""
        mine = [norm(pid) for _, pid in rows]
        now = [norm(k["id"]) for k in await self.c.children(parent) if k.get("type") == "child_page" and norm(k["id"]) in set(mine)]
        if not force and now == mine:
            return {"action": "unchanged", "order": [r[0] for r in rows]}
        for pid in mine:
            await self.scope.require(pid)
        tmp = await self._section("정렬 중")
        for pid in mine:
            await self.c.move_page(pid, tmp)
        for (path, _), pid in zip(rows, mine):
            await self.c.move_page(pid, parent)
            await self._save(path, parent_page_id=parent)
        await self.archive_section("정렬 중")
        return {"action": "reordered", "order": [r[0] for r in rows]}

    async def archive_section(self, name: str) -> dict[str, Any]:
        """묶음 페이지(「회고」 · 「포트폴리오」) 내리기 — 우리가 만든 것이고, 그 아래에 살아 있는 페이지가 없을 때만(11-06)."""
        key = f"@section/{name}"
        row = await self._row(key)
        if not row or row["status"] != "published" or not row["notion_page_id"]:
            raise OutOfScope(f"「{name}」 묶음 페이지 기록이 없습니다")
        pid = row["notion_page_id"]
        await self.scope.require(pid)
        left = [k for k in await self.c.children(pid) if k.get("type") == "child_page"]
        if left:
            raise OutOfScope(f"「{name}」 아래에 페이지가 {len(left)}개 남아 있습니다 — 먼저 옮기거나 내려 주세요")
        await self.c.archive_page(pid)
        await self._save(key, status="archived")
        return {"path": key, "action": "archived", "page_id": pid}

    async def list(self) -> list[dict[str, Any]]:
        """게시할 수 있는 글(main의 portfolio/*.md) + 그 게시 기록. 원본이 게시 뒤에 바뀌었으면 changed.
        회고는 11-06부터 Notion에 두지 않는다(포트폴리오 8편이 바깥 판 — git에만 남긴다)."""
        from sqlalchemy import text
        files = subprocess.run(["git", "-C", self.repo, "ls-files", "portfolio/*.md"], capture_output=True,
                               text=True, timeout=15).stdout.split()
        async with self.e.connect() as c:
            rows = {r["path"]: dict(r) for r in (await c.execute(text(
                "SELECT path, title, status, url, commit_sha, content_hash, updated_at FROM doc_publish "
                "WHERE project = :p AND kind = 'doc' AND path LIKE :pre"), {"p": self.project, "pre": "portfolio/%"})).mappings().all()}
        out = []
        for f in sorted(set(files) | set(rows)):
            r = rows.get(f)
            changed = None
            if r and r["status"] == "published":
                try:
                    body, _ = git_show(self.repo, f, self.ref)
                    changed = content_digest(self.repo, f, body, self.ref) != r["content_hash"]
                except (FileNotFoundError, OutOfScope):
                    changed = None
            out.append({"path": f, "title": r["title"] if r else None, "status": r["status"] if r else "new",
                        "url": r["url"] if r else None, "commit": r["commit_sha"] if r else None, "changed": changed,
                        "updated_at": r["updated_at"].isoformat() + "Z" if r and r["updated_at"] else None})
        return out
