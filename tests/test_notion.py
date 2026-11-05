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
        return [{"id": b["_id"]} for b in self.blocks.get(bid, [])]

    async def append(self, bid, children):
        out = []
        for c in children:
            self.n += 1
            c = {**c, "_id": f"b{self.n}"}
            self.blocks.setdefault(bid, []).append(c)
            out.append({"id": c["_id"]})
        return out

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


def test_git_show_refuses_outside_paths(tmp_path):
    for bad in ("../x.md", "/etc/passwd.md", "README.md", "log/a.txt"):
        with pytest.raises(nt.OutOfScope):
            nt.git_show(str(tmp_path), bad)
