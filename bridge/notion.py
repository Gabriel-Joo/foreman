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
        img = re.match(r"^!\[(?P<cap>[^\]]*)\]\((?P<src>[^)\s]+)\)$", s)
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


def git_show(repo: str, path: str) -> tuple[str, str]:
    """(본문, 그 파일을 마지막으로 바꾼 커밋 짧은 해시) — main HEAD에 커밋된 것만."""
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or p.suffix != ".md" or not str(p).startswith(("log/", "docs/", "portfolio/")):
        raise OutOfScope("log/ · docs/ · portfolio/ 아래 .md만 게시합니다")
    r = subprocess.run(["git", "-C", repo, "show", f"HEAD:{path}"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise FileNotFoundError(f"main에 커밋된 {path}가 없습니다 — 합친 뒤에 게시해 주세요")
    sha = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h", "HEAD", "--", path],
                         capture_output=True, text=True, timeout=15).stdout.strip()
    return r.stdout, sha


def header_block(path: str, commit: str, ctx: Ctx, when: str) -> dict[str, Any]:
    rich = (_rt("이 페이지는 사본입니다 — 원본 ") + _rt(path, code=True, link=ctx.blob(path)) + _rt(" · 커밋 ")
            + _rt(commit, code=True, link=f"{ctx.gh}/commit/{commit}") + _rt(f" · 게시 {when}. 고칠 때는 git에서 고치고 다시 게시합니다."))
    return {"object": "block", "type": "callout", "callout": {"rich_text": rich, "icon": {"type": "emoji", "emoji": "📄"}, "color": "gray_background"}}


def _strip_children(b: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """표는 줄을 같이 만들어야 해서 그대로, 그 밖의 자식은 떼어 두었다가 만든 뒤 붙인다(깊이 제한 없이)."""
    if b["type"] == "table":
        return b, []
    inner = dict(b[b["type"]])
    kids = inner.pop("children", [])
    return {**b, b["type"]: inner}, kids


async def append_tree(client: Any, parent: str, blocks: list[dict[str, Any]], after: str | None = None) -> int:
    """블록들을 붙인다(자식은 만든 뒤 붙인다). after를 주면 그 블록 바로 뒤에 차례로."""
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


async def sync_children(client: Any, parent: str, new: list[dict[str, Any]], stats: dict[str, int] | None = None) -> dict[str, int]:
    """parent의 자식을 new에 맞춘다 — 같은 자리 · 같은 종류면 내용만(같으면 그대로), 다르면 그 블록만 바꾼다.
    맨 앞 블록부터 다르면 붙일 자리가 없어 전부 갈아 끼운다(reset)."""
    st = stats if stats is not None else {"kept": 0, "updated": 0, "replaced": 0, "added": 0, "deleted": 0, "reset": 0}
    old = await client.children(parent)
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


def git_bytes(repo: str, path: str) -> bytes:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif") or not str(p).startswith(("portfolio/", "docs/", "log/")):
        raise OutOfScope(f"그림은 저장소 안 portfolio/ · docs/ · log/의 PNG · JPG만 올립니다: {path}")
    r = subprocess.run(["git", "-C", repo, "show", f"HEAD:{path}"], capture_output=True, timeout=15)
    if r.returncode != 0:
        raise FileNotFoundError(f"main에 커밋된 그림 {path}가 없습니다")
    return r.stdout


async def resolve_uploads(client: Any, repo: str, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """그림 자리(_upload)를 파일로 올려 그림 블록으로 — 게시할 때마다 올린다(그림이 바뀌었을 수 있다)."""
    out = []
    for b in blocks:
        if "_upload" in b:
            data = git_bytes(repo, b["_upload"])
            ctype = "image/png" if b["_upload"].lower().endswith(".png") else "image/jpeg"
            fid = await client.upload_file(PurePosixPath(b["_upload"]).name, data, ctype)
            b = {"object": "block", "type": "image",
                 "image": {"type": "file_upload", "file_upload": {"id": fid}, "caption": b["image"].get("caption", [])}}
        else:
            t = b["type"]
            kids = (b.get(t) or {}).get("children")
            if kids and t != "table":
                b = {**b, t: {**b[t], "children": await resolve_uploads(client, repo, kids)}}
        out.append(b)
    return out


class Publisher:
    """doc_publish 기록 + 범위 확인 + 게시 · 다시 게시 · 내리기. DB는 store(engine)로, Notion은 client로."""

    def __init__(self, engine: Any, client: Any, root: str, repo: str, project: str = "foreman", gh: str = GH) -> None:
        self.e, self.c, self.root, self.repo, self.project, self.gh = engine, client, norm(root), repo, project, gh
        self.scope = Scope(client, root)

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

    async def publish(self, path: str, when: str = "") -> dict[str, Any]:
        body, commit = git_show(self.repo, path)
        digest = hashlib.sha256(body.encode()).hexdigest()
        portfolio = path.startswith("portfolio/")      # 바깥 사람이 읽는 글 — 저장소 링크 없이, 맨 위 "사본" 안내 없이(11-06)
        ctx = Ctx(path, commit or "HEAD", self.gh, links=not portfolio)
        title, blocks = md_to_blocks(body, ctx)
        title = title or PurePosixPath(path).stem
        if portfolio:
            title = portfolio_title(path, title)
        else:
            blocks = [header_block(path, commit or "HEAD", ctx, when)] + blocks
        row = await self._row(path)
        if row and row["status"] == "published" and row["notion_page_id"]:
            pid = row["notion_page_id"]
            if await self.scope.under_root(pid):
                # 포트폴리오는 루트 바로 아래(11-06 — 「포트폴리오」 묶음을 없앴다). 예전 자리에 있으면 옮긴다(옮긴 순서대로 쌓인다)
                if portfolio and norm(row["parent_page_id"] or "") != self.root:
                    await self.c.move_page(pid, self.root)
                    await self._save(path, parent_page_id=self.root)
                if row["title"] != title:
                    await self.c.set_title(pid, title)
                    await self._save(path, title=title)
                if row["content_hash"] == digest:
                    return {"path": path, "action": "unchanged", "page_id": pid, "url": row["url"], "commit": commit,
                            "title": title}
                blocks = await resolve_uploads(self.c, self.repo, blocks)
                st = await sync_children(self.c, pid, blocks)    # 같은 페이지 · 같은 URL, 바뀐 블록만(mermaid 미리보기가 남는다)
                await self.c.set_title(pid, title)
                await self._save(path, kind="doc", title=title, commit_sha=commit, content_hash=digest, status="published", error=None)
                return {"path": path, "action": "updated", "page_id": pid, "url": row["url"], "commit": commit, "sync": st}
            # Notion에서 지워졌거나 범위 밖으로 옮겨졌다 — 그 페이지는 두고 새로 만든다
        blocks = await resolve_uploads(self.c, self.repo, blocks)
        parent = self.root if portfolio else await self._section(section_of(path))
        await self.scope.require(parent, not_root=not portfolio)
        p = await self.c.create_page(parent, title, [])
        pid = norm(p["id"])
        n = await append_tree(self.c, pid, blocks)
        await self._save(path, kind="doc", title=title, notion_page_id=pid, parent_page_id=parent, commit_sha=commit,
                         content_hash=digest, status="published", url=p.get("url"), error=None)
        return {"path": path, "action": "created", "page_id": pid, "url": p.get("url"), "commit": commit, "blocks": n}

    async def archive(self, path: str) -> dict[str, Any]:
        """내리기 = 휴지통. 우리가 만든 페이지이고 지금도 루트 아래일 때만."""
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
                    body, _ = git_show(self.repo, f)
                    changed = hashlib.sha256(body.encode()).hexdigest() != r["content_hash"]
                except (FileNotFoundError, OutOfScope):
                    changed = None
            out.append({"path": f, "title": r["title"] if r else None, "status": r["status"] if r else "new",
                        "url": r["url"] if r else None, "commit": r["commit_sha"] if r else None, "changed": changed,
                        "updated_at": r["updated_at"].isoformat() + "Z" if r and r["updated_at"] else None})
        return out
