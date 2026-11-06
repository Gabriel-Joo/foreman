import asyncio

import pytest

from bridge import notion as nt

MD = """# 11-05 회고 [t:5871]

> 상태: 기간 11-05 — 재료 `materials.md`

## 1. 사람이 바로잡은 곳

- **역할 색**이 안 칠해졌다 [t:12] [c:cad260d]
  - 테마 이름이 달랐다 [log:stage11_roles_result.md]
    - 시험으로 고정 [docs:12_scribe.md:40-60]
- 두 번째 [링크](../docs/style_guide.md) · [밖](https://example.com/a)
1. 번호 하나

| 무엇 | 값 |
|---|---|
| 커밋 | 48 |
| 파이프 \\| 안 | `코드` |

```python
print("안녕")
```

---
끝 문단
둘째 줄
"""


def test_md_to_blocks_shapes_and_markers():
    ctx = nt.Ctx("log/retro_20261105_foreman.md", "abc1234")
    title, bs = nt.md_to_blocks(MD, ctx)
    assert title == "11-05 회고"                                         # 첫 # 은 제목, 턴 표시는 뺀다
    kinds = [b["type"] for b in bs]
    assert kinds == ["quote", "heading_1", "bulleted_list_item", "bulleted_list_item", "numbered_list_item",
                     "table", "code", "divider", "paragraph"]
    li = bs[2]["bulleted_list_item"]
    assert nt.plain(li["rich_text"]) == "역할 색이 안 칠해졌다 cad260d"     # [t:12] 사라짐
    assert li["rich_text"][0]["annotations"] == {"bold": True}
    commit = li["rich_text"][-1]
    assert commit["text"]["link"]["url"].endswith("/commit/cad260d") and commit["annotations"]["code"]
    child = li["children"][0]["bulleted_list_item"]
    ev = child["rich_text"][-1]
    assert ev["text"]["content"] == "log/stage11_roles_result.md"
    assert ev["text"]["link"]["url"].endswith("/blob/abc1234/log/stage11_roles_result.md")
    grand = child["children"][0]["bulleted_list_item"]["rich_text"][-1]     # 3단 중첩, 줄 범위는 떼고 파일만
    assert grand["text"]["link"]["url"].endswith("/blob/abc1234/docs/12_scribe.md")
    rel = bs[3]["bulleted_list_item"]["rich_text"]
    assert rel[1]["text"]["link"]["url"].endswith("/blob/abc1234/docs/style_guide.md")   # 상대 링크 → 같은 커밋의 파일
    assert rel[3]["text"]["link"]["url"] == "https://example.com/a"
    tbl = bs[5]["table"]
    assert tbl["table_width"] == 2 and tbl["has_column_header"] and len(tbl["children"]) == 3
    assert nt.plain(tbl["children"][2]["table_row"]["cells"][0]) == "파이프 | 안"
    assert tbl["children"][2]["table_row"]["cells"][1][0]["annotations"]["code"]
    code = bs[6]["code"]
    assert code["language"] == "python" and nt.plain(code["rich_text"]) == 'print("안녕")'
    assert nt.plain(bs[8]["paragraph"]["rich_text"]) == "끝 문단\n둘째 줄"


def test_long_text_split_and_empty_code():
    _, bs = nt.md_to_blocks("가" * 4500 + "\n\n```\n```\n")
    rt = bs[0]["paragraph"]["rich_text"]
    assert [len(t["text"]["content"]) for t in rt] == [2000, 2000, 500]
    assert bs[1]["code"]["language"] == "plain text" and bs[1]["code"]["rich_text"]


def test_strip_children_keeps_table_rows():
    _, bs = nt.md_to_blocks("- a\n  - b\n\n| x |\n|---|\n| 1 |\n")
    li, kids = nt._strip_children(bs[0])
    assert "children" not in li["bulleted_list_item"] and len(kids) == 1
    tb, kids2 = nt._strip_children(bs[1])
    assert kids2 == [] and len(tb["table"]["children"]) == 2


def test_load_token(tmp_path):
    f = tmp_path / ".env.notion"
    f.write_text("# 주석\nNOTION_TOKEN='ntn_x'\n", encoding="utf-8")
    assert nt.load_token(f) == "ntn_x"
    assert nt.load_token(tmp_path / "없음") is None


class FakeNotion:
    """페이지 트리 — 프로젝트(밖) > FOREMAN 루트. 통합 권한처럼, 루트 아래가 아닌 페이지는 404로 숨긴다(see_all이면 보인다)."""

    def __init__(self, see_all: bool = False) -> None:
        self.pages = {"proj": {"parent": None, "title": "프로젝트", "archived": False},
                      "root": {"parent": "proj", "title": "FOREMAN", "archived": False},
                      "other": {"parent": "proj", "title": "펫퍼민트", "archived": False}}
        self.blocks: dict[str, list[dict]] = {}
        self.n = 0
        self.see_all = see_all
        self.calls: list[tuple] = []

    def _visible(self, pid):
        if self.see_all:
            return True
        cur = pid
        while cur:
            if cur == "root":
                return True
            cur = self.pages[cur]["parent"]
        return False

    async def page(self, pid):
        p = self.pages.get(pid)
        if not p or not self._visible(pid):
            raise nt.NotionError(404, "없음")
        par = {"type": "page_id", "page_id": p["parent"]} if p["parent"] else {"type": "workspace", "workspace": True}
        return {"id": pid, "parent": par, "archived": p["archived"], "url": f"https://notion/{pid}"}

    async def create_page(self, parent, title, children):
        await self.page(parent)
        self.n += 1
        pid = f"p{self.n}"
        self.pages[pid] = {"parent": parent, "title": title, "archived": False}
        self.blocks[pid] = list(children)
        self.calls.append(("create", parent, title))
        return {"id": pid, "url": f"https://notion/{pid}"}

    async def set_title(self, pid, title):
        await self.page(pid)
        self.pages[pid]["title"] = title

    async def archive_page(self, pid):
        await self.page(pid)
        self.pages[pid]["archived"] = True
        self.calls.append(("archive", pid))

    async def children(self, bid):
        # 실제 Notion처럼 하위 페이지도 child_page 블록으로 돌려준다(휴지통 간 것은 빼고) — 묶음 페이지 내리기가 본다
        subs = [{"type": "child_page", "id": pid, "child_page": {"title": p["title"]}, "has_children": False}
                for pid, p in self.pages.items() if p["parent"] == bid and not p["archived"]]
        return [{**b, "id": b["_id"], "has_children": bool(self.blocks.get(b["_id"]))} for b in self.blocks.get(bid, [])] + subs

    async def append(self, bid, children, after=None):
        out = []
        lst = self.blocks.setdefault(bid, [])
        at = next((i + 1 for i, b in enumerate(lst) if b["_id"] == after), len(lst)) if after else len(lst)
        for c in children:
            self.n += 1
            c = {**c, "_id": f"b{self.n}"}
            lst.insert(at, c)
            at += 1
            out.append({"id": c["_id"]})
        self.calls.append(("append", bid, len(children), after))
        return out

    async def update_block(self, bid, block):
        for lst in self.blocks.values():
            for i, b in enumerate(lst):
                if b["_id"] == bid:
                    t = block["type"]
                    lst[i] = {**b, t: {**b[t], **block[t]}}
                    self.calls.append(("update", bid))
                    return
        raise nt.NotionError(404, "없음")

    async def upload_file(self, name, data, content_type="image/png"):
        self.n += 1
        self.calls.append(("upload", name, len(data)))
        return f"f{self.n}"

    async def move_page(self, pid, parent):
        await self.page(pid)
        await self.page(parent)
        self.pages[pid]["parent"] = parent
        self.calls.append(("move", pid, parent))

    async def delete_block(self, bid):
        for k, v in self.blocks.items():
            self.blocks[k] = [b for b in v if b["_id"] != bid]


def test_scope_walks_up_to_root():
    f = FakeNotion(see_all=True)
    f.pages["sec"] = {"parent": "root", "title": "회고", "archived": False}
    f.pages["doc"] = {"parent": "sec", "title": "글", "archived": False}
    s = nt.Scope(f, "root")
    assert asyncio.run(s.under_root("doc")) and asyncio.run(s.under_root("root"))
    assert not asyncio.run(s.under_root("other")) and not asyncio.run(s.under_root("proj"))
    with pytest.raises(nt.OutOfScope):
        asyncio.run(s.require("root"))                                   # 루트 자체는 못 건드린다
    with pytest.raises(nt.OutOfScope):
        asyncio.run(s.require("other"))                                  # 코드가 막는다(권한이 다 보여도)
    f.pages["doc"]["archived"] = True
    assert not asyncio.run(s.under_root("doc"))


def test_portfolio_mode_no_repo_links_and_image_placeholder():
    ctx = nt.Ctx("portfolio/01_context.md", "abc1234", links=False)
    _, bs = nt.md_to_blocks("- 근거 [c:abc1234] [log:x_result.md] [상대](../docs/a.md) [밖](https://example.com/)\n\n"
                            "![화면 — 마법학교](img/office.png)\n", ctx)
    rt = bs[0]["bulleted_list_item"]["rich_text"]
    links = [t["text"].get("link") for t in rt]
    assert links.count(None) == len(links) - 1 and {"url": "https://example.com/"} in links   # 저장소 링크는 글자만, 바깥은 그대로
    assert bs[1]["type"] == "image" and bs[1]["_upload"] == "portfolio/img/office.png"
    assert nt.plain(bs[1]["image"]["caption"]) == "화면 — 마법학교"


def test_portfolio_title_number():
    assert nt.portfolio_title("portfolio/00_overview.md", "한눈에 — FOREMAN이 무엇인가") == "00 한눈에 — FOREMAN이 무엇인가"
    assert nt.portfolio_title("portfolio/07_models_cost.md", "07 모델 고르기와 비용") == "07 모델 고르기와 비용"   # 두 번 붙이지 않는다
    assert nt.portfolio_title("portfolio/extra.md", "번외") == "번외"


def test_mermaid_keeps_language():
    _, bs = nt.md_to_blocks("```mermaid\nflowchart LR\n  A --> B\n```\n")
    assert bs[0]["code"]["language"] == "mermaid" and "A --> B" in nt.plain(bs[0]["code"]["rich_text"])


def test_sync_keeps_block_ids_and_replaces_only_changed():
    """다시 게시 — 같은 자리 · 같은 종류면 내용만 고쳐 id가 남는다(mermaid 미리보기 보존), 바뀐 종류는 그 하나만."""
    f = FakeNotion(see_all=True)
    _, b1 = nt.md_to_blocks("> 이 글은 A를 다룬다\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n문단 하나\n\n- 목록\n")
    asyncio.run(nt.append_tree(f, "root", b1))
    ids1 = [b["_id"] for b in f.blocks["root"]]
    mer = ids1[1]
    _, b2 = nt.md_to_blocks("> 이 글은 A를 다룬다(고침)\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n## 제목으로 바뀜\n\n- 목록\n- 하나 더\n")
    st = asyncio.run(nt.sync_children(f, "root", b2))
    ids2 = [b["_id"] for b in f.blocks["root"]]
    assert ids2[0] == ids1[0] and ids2[1] == mer                              # 첫 줄은 고쳤고 mermaid는 그대로(같은 블록)
    assert st["updated"] == 1 and st["kept"] >= 2 and st["replaced"] == 1 and st["added"] == 1
    assert [b["type"] for b in f.blocks["root"]] == ["quote", "code", "heading_1", "bulleted_list_item", "bulleted_list_item"]
    _, b3 = nt.md_to_blocks("## 맨 앞부터 다름\n")
    st3 = asyncio.run(nt.sync_children(f, "root", b3))
    assert st3["reset"] == 1 and [b["type"] for b in f.blocks["root"]] == ["heading_1"]


def test_git_show_refuses_outside_paths(tmp_path):
    for bad in ("../x.md", "/etc/passwd.md", "README.md", "log/a.txt"):
        with pytest.raises(nt.OutOfScope):
            nt.git_show(str(tmp_path), bad)
