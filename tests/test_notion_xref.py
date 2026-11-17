"""편 사이 참조 「→ 「제목」」을 노션 페이지 링크로(11-17 사용자 지시 22의 10번) — 변환 함수와 가짜 Notion으로."""
import asyncio

import pytest

from bridge import docsync as ds
from bridge import notion as nt
from test_notion import FakeNotion

TITLES = {"portfolio/00_a.md": "한눈에", "portfolio/01_b.md": "승인 카드", "portfolio/02_c.md": "세션 패널: 대화와 활동",
          "portfolio/03_d.md": "겹침", "portfolio/04_e.md": "겹침",
          "notion/03_session.md": "03 세션 지켜보기와 글 넣기", "notion/02_x/01_y.md": "02-01 손으로 세운 클러스터"}


def _ctx(path="portfolio/00_a.md", pages=None, titles=None):
    ctx = nt.Ctx(path, "HEAD", links=False, manuscript=True)
    ctx.pages = pages if pages is not None else {p: f"https://notion/{p}" for p in TITLES}
    ctx.xref = nt.xref_index(titles or TITLES)
    return ctx


def _links(rich):
    return [(r["text"]["content"], (r["text"].get("link") or {}).get("url")) for r in rich if (r["text"].get("link") or {}).get("url")]


def test_one_ref_becomes_link_and_arrow_stays_text():
    ctx = _ctx()
    rich = nt.inline("자세한 것은 → 「승인 카드」에서 다룬다.", ctx)
    assert nt.plain(rich) == "자세한 것은 → 「승인 카드」에서 다룬다."
    assert _links(rich) == [("「승인 카드」", "https://notion/portfolio/01_b.md")]
    assert not ctx.warnings and not ctx.pending and ctx.refs == {"portfolio/01_b.md"}


def test_several_refs_in_one_line_and_in_bold():
    ctx = _ctx()
    rich = nt.inline("→ 「승인 카드」와 →「세션 패널: 대화와 활동」, **굵게 → 「한눈에」**", ctx)
    got = _links(rich)
    assert [g[0] for g in got] == ["「승인 카드」", "「세션 패널: 대화와 활동」"]   # 「한눈에」는 자기 편 — 링크 없이
    ctx2 = _ctx("portfolio/01_b.md")
    rich2 = nt.inline("**굵게 → 「한눈에」**", ctx2)
    assert _links(rich2) == [("「한눈에」", "https://notion/portfolio/00_a.md")]
    assert all(r.get("annotations", {}).get("bold") for r in rich2)


def test_table_cell_and_list_item():
    md = ("# 한눈에\n\n| 물음 | 자세히 |\n|---|---|\n| 카드는? | → 「승인 카드」 |\n\n- 목록 안 → 「세션 패널: 대화와 활동」\n"
          "  - 안쪽 → 「승인 카드」\n")
    ctx = _ctx()
    _, blocks = nt.md_to_blocks(md, ctx)
    table = next(b for b in blocks if b["type"] == "table")
    cell = table["table"]["children"][1]["table_row"]["cells"][1]
    assert _links(cell) == [("「승인 카드」", "https://notion/portfolio/01_b.md")]
    item = next(b for b in blocks if b["type"] == "bulleted_list_item")
    assert _links(item["bulleted_list_item"]["rich_text"])[0][0] == "「세션 패널: 대화와 활동」"
    inner = item["bulleted_list_item"]["children"][0]["bulleted_list_item"]["rich_text"]
    assert _links(inner)[0][0] == "「승인 카드」"


def test_missing_and_duplicate_titles_stay_text_with_warning():
    ctx = _ctx()
    rich = nt.inline("→ 「없는 편」, → 「겹침」 끝", ctx)
    assert _links(rich) == [] and len(rich) == 1 and nt.plain(rich) == "→ 「없는 편」, → 「겹침」 끝"   # 한 덩어리 그대로
    assert any("없는 편" in w and "없어" in w for w in ctx.warnings)
    assert any("겹침" in w and "2개" in w and "portfolio/03_d.md" in w for w in ctx.warnings)
    nt.inline("→ 「없는 편」", ctx)
    assert len(ctx.warnings) == 2                       # 같은 경고는 한 번


def test_numbered_titles_both_ways():
    """FOREMAN은 번호째(→ 「03 세션 …」), 인프라는 번호 없이(→ 「손으로 세운 클러스터」). 둘 다 그 편으로."""
    ctx = _ctx("notion/00_a.md")
    a = _links(nt.inline("→ 「03 세션 지켜보기와 글 넣기」", ctx))
    b = _links(nt.inline("→ 「세션 지켜보기와 글 넣기」", ctx))
    c = _links(nt.inline("→ 「손으로 세운 클러스터」", ctx))
    assert a[0][1] == b[0][1] == "https://notion/notion/03_session.md"
    assert c[0][1] == "https://notion/notion/02_x/01_y.md"


def test_exact_title_wins_over_bare():
    titles = {"notion/04_approval.md": "04 승인", "notion/09_x.md": "승인"}
    ctx = _ctx("notion/00_a.md", titles=titles, pages={p: f"u:{p}" for p in titles})
    assert _links(nt.inline("→ 「승인」", ctx))[0][1] == "u:notion/09_x.md"
    assert _links(nt.inline("→ 「04 승인」", ctx))[0][1] == "u:notion/04_approval.md"


def test_not_yet_published_is_pending_not_warning():
    ctx = _ctx(pages={})
    rich = nt.inline("→ 「승인 카드」", ctx)
    assert _links(rich) == [] and ctx.pending == ["portfolio/01_b.md"] and not ctx.warnings


def test_markdown_link_still_works_and_code_is_not_ref():
    ctx = _ctx()
    rich = nt.inline("[승인 카드](01_b.md)와 `→ 「승인 카드」`", ctx)
    assert _links(rich) == [("승인 카드", "https://notion/portfolio/01_b.md")]
    assert any(r.get("annotations", {}).get("code") and r["text"]["content"] == "→ 「승인 카드」" for r in rich)


def test_evidence_and_head_comment_removed_first():
    md = "<!-- 다루는 곳: x / 읽은 커밋: abc → 「없는 편」 -->\n# 한눈에\n\n본문 → 「승인 카드」 [code:bridge/x.py:1-2] 끝.\n"
    ctx = _ctx()
    _, blocks = nt.md_to_blocks(md, ctx)
    rich = blocks[0]["paragraph"]["rich_text"]
    assert nt.plain(rich) == "본문 → 「승인 카드」 끝." and _links(rich)[0][0] == "「승인 카드」"
    assert not ctx.warnings                            # 머리 주석 안의 참조는 보지 않는다


def test_non_manuscript_unchanged():
    """원고가 아닌 글(xref 없음)은 전과 똑같이 한 덩어리 글자 — 사람이 옮긴 페이지와 맞대는 블록 지문이 바뀌지 않는다."""
    ctx = nt.Ctx("docs/a.md")
    rich = nt.inline("앞 → 「승인 카드」 뒤", ctx)
    assert rich == nt._rt("앞 → 「승인 카드」 뒤")


# ── 가짜 Notion으로 게시 ───────────────────────────────────────
PAGES: dict[str, str] = {}


class _Pub(nt.Publisher):
    """DB 없이 — 행은 dict로, git은 PAGES로."""
    def __init__(self, rows, **kw):
        super().__init__(None, FakeNotion(), "root", ".", project="x", portfolio_page="root", **kw)
        self.rows = rows

    async def _row(self, path):
        return self.rows.get(path)

    async def _save(self, path, **kw):
        self.rows.setdefault(path, {}).update(kw)

    async def parent_for(self, path):
        return "root"

    async def _upload_limit(self):
        return None

    async def human_edits(self, pid, blocks, prev=None):
        return []

    async def _page_urls(self):
        return {p: r["url"] for p, r in self.rows.items() if r.get("status") == "published" and r.get("url")}

    async def _pending_paths(self, group):
        return sorted(p for p, r in self.rows.items() if p.startswith(group) and r.get("status") == "published"
                      and r.get("content_hash") is None and r.get("commit_sha"))


@pytest.fixture
def patched(monkeypatch):
    PAGES.clear()
    monkeypatch.setattr(nt, "git_show", lambda repo, path, ref="HEAD": (PAGES[path], "c" * 7))
    monkeypatch.setattr(nt, "content_digest", lambda repo, path, body, ref="HEAD": str(hash(body)))
    monkeypatch.setattr(nt, "ref_titles", lambda repo, ref, prefix, cache=None: {
        p: nt.first_h1(b)[1] for p, b in PAGES.items() if p.startswith(prefix)})


def _page_links(pub, pid):
    out = []
    for b in pub.c.blocks[pid]:
        out += _links((b.get(b["type"]) or {}).get("rich_text") or [])
    return out


def test_publish_pending_then_relinked_when_target_goes_up(patched):
    PAGES["portfolio/00_a.md"] = "# 한눈에\n\n자세한 것은 → 「승인 카드」.\n\n→ 「없는 편」도 있다.\n"
    PAGES["portfolio/01_b.md"] = "# 승인 카드\n\n처음으로 → 「한눈에」.\n"
    rows: dict = {}
    pub = _Pub(rows)
    r1 = asyncio.run(pub.publish("portfolio/00_a.md"))
    assert r1["action"] == "created" and r1["pending"] == ["portfolio/01_b.md"]
    assert any("없는 편" in w for w in r1["warnings"])
    assert rows["portfolio/00_a.md"]["content_hash"] is None          # 기억 — 「바뀜」으로 남는다
    a_pid = r1["page_id"]
    assert _page_links(pub, a_pid) == []
    r2 = asyncio.run(pub.publish("portfolio/01_b.md"))
    assert r2["pending"] == [] and _page_links(pub, r2["page_id"]) == [("「한눈에」", r1["url"])]
    assert [d["path"] for d in r2["relinked"]] == ["portfolio/00_a.md"] and not r2["relink_failed"]
    assert _page_links(pub, a_pid) == [("「승인 카드」", r2["url"])]          # 같은 페이지에 링크가 걸렸다
    assert rows["portfolio/00_a.md"]["content_hash"] == str(hash(PAGES["portfolio/00_a.md"]))
    # 다시 올리면 바뀐 것 없음
    assert asyncio.run(pub.publish("portfolio/00_a.md"))["action"] == "unchanged"


def test_relink_skips_pages_waiting_for_other_targets(patched):
    PAGES["portfolio/00_a.md"] = "# 한눈에\n\n→ 「셋째」\n"
    PAGES["portfolio/01_b.md"] = "# 승인 카드\n\n본문\n"
    PAGES["portfolio/02_c.md"] = "# 셋째\n\n본문\n"
    rows: dict = {}
    pub = _Pub(rows)
    asyncio.run(pub.publish("portfolio/00_a.md"))
    r = asyncio.run(pub.publish("portfolio/01_b.md"))
    assert r["relinked"] == []                       # a는 c를 기다린다 — b가 올라가도 다시 올리지 않는다
    r = asyncio.run(pub.publish("portfolio/02_c.md"))
    assert [d["path"] for d in r["relinked"]] == ["portfolio/00_a.md"]


def test_docsync_two_passes_link_new_pages(patched, monkeypatch):
    """기술문서 한 번 게시 — 처음 편이 뒤 편을 가리켜도 다 올린 뒤 두 번째 돌기에서 걸린다. 끝내 없는 제목은 경고로."""
    PAGES["notion/00_a.md"] = "# 00 처음\n\n→ 「둘째」와 → 「없는 편」.\n"
    PAGES["notion/01_b.md"] = "# 01 둘째\n\n→ 「00 처음」\n"
    rows: dict = {}
    pub = _Pub(rows, opts={"src": "notion/", "title": "h1", "header": "footer"})
    pub.docs_page = None                              # 차례 세우기는 이 시험 밖
    st = {"project": "x", "files": list(PAGES), "new": list(PAGES), "changed": [], "deleted": [], "broken": [],
          "ref_sha": "f" * 40, "titles": {}, "src": "notion/"}

    async def fake_status(p):
        return st
    monkeypatch.setattr(ds, "status", fake_status)
    calls = []
    orig = pub.publish

    async def spy(path, when="", **kw):
        calls.append((path, kw.get("relink")))
        return await orig(path, when, **kw)
    pub.publish = spy
    r = asyncio.run(ds.sync(pub, "지금"))
    assert calls == [("notion/00_a.md", False), ("notion/01_b.md", False), ("notion/00_a.md", False)]
    a = rows["notion/00_a.md"]
    assert a["content_hash"] == str(hash(PAGES["notion/00_a.md"]))
    links = _page_links(pub, a["notion_page_id"])
    assert links == [("「둘째」", rows["notion/01_b.md"]["url"])]
    assert [w["path"] for w in r["warnings"]] == ["notion/00_a.md"] and "없는 편" in r["warnings"][0]["warning"]
    assert [d["path"] for d in r["done"]] == ["notion/00_a.md", "notion/01_b.md"]


def test_docs_projects_do_not_read_refs(patched):
    """docs/를 그대로 올리는 프로젝트(런슈즈, 펫퍼민트)는 알아보지 않는다 — 색인도 읽지 않는다."""
    pub = _Pub({})
    assert pub.xref_group("docs/a.md") is None and pub.xref_group("portfolio/00_a.md") == "portfolio/"
    pub2 = _Pub({}, opts={"src": "notion/"})
    assert pub2.xref_group("notion/02_x/01_y.md") == "notion/"
