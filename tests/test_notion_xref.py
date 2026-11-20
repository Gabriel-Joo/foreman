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


def test_publish_pending_is_link_only_until_target_goes_up(patched):
    """한 편만 올리면(가리킨 편이 Notion에 없음) 지문을 비워 둔다. 글은 그대로라 link_only. 화면이 「원본이 바뀜」이 아니라
    「링크를 다시 걸어야 함」으로 보인다(11-20). 11-20부터 다른 편을 따라 다시 거는 길(relink)은 없다. 묶음 게시가 건다."""
    PAGES["portfolio/00_a.md"] = "# 한눈에\n\n자세한 것은 → 「승인 카드」.\n\n→ 「없는 편」도 있다.\n"
    PAGES["portfolio/01_b.md"] = "# 승인 카드\n\n처음으로 → 「한눈에」.\n"
    rows: dict = {}
    pub = _Pub(rows)
    r1 = asyncio.run(pub.publish("portfolio/00_a.md"))
    assert r1["action"] == "created" and r1["pending"] == ["portfolio/01_b.md"] and "relinked" not in r1
    assert any("없는 편" in w for w in r1["warnings"])
    a = rows["portfolio/00_a.md"]
    assert a["content_hash"] is None and nt.link_only(a, "c" * 7)            # 글은 그대로, 링크만
    assert not nt.link_only(a, "d" * 7)                                       # 그 뒤 커밋이 있으면 원본이 바뀐 것
    assert not nt.link_only({**a, "commit_sha": None}, "c" * 7)              # 빈 페이지만 만든 편(reserve)은 링크만이 아니다
    r2 = asyncio.run(pub.publish("portfolio/01_b.md"))
    assert r2["pending"] == [] and _page_links(pub, r2["page_id"]) == [("「한눈에」", r1["url"])]
    assert _page_links(pub, r1["page_id"]) == []                              # a는 다음 묶음 게시까지 그대로


def _one_pass(pub, monkeypatch, files, new, changed=()):
    st = {"project": "x", "files": list(files), "new": list(new), "changed": list(changed), "deleted": [], "broken": [],
          "ref_sha": "f" * 40, "titles": {}, "src": pub.src}

    async def fake_status(p, src=None):
        return st
    monkeypatch.setattr(ds, "status", fake_status)
    calls = []
    orig = pub.publish

    async def spy(path, when="", **kw):
        calls.append(path)
        return await orig(path, when, **kw)
    pub.publish = spy
    return calls


def test_docsync_one_pass_links_new_pages_and_writes_each_page_once(patched, monkeypatch):
    """기술문서 한 번 게시(11-20). 새 편의 빈 페이지를 먼저 만들어(reserve) 처음 편이 뒤 편을 가리켜도 첫 게시에서 걸린다.
    한 요청 안에서 페이지마다 글은 한 번만 쓴다(전에는 두 번째 돌기가 같은 페이지에 다시 썼다). 끝내 없는 제목은 경고로."""
    PAGES["notion/00_a.md"] = "# 00 처음\n\n→ 「둘째」와 → 「없는 편」.\n"
    PAGES["notion/01_b.md"] = "# 01 둘째\n\n→ 「00 처음」\n"
    rows: dict = {}
    pub = _Pub(rows, opts={"src": "notion/", "title": "h1", "header": "footer"})
    pub.docs_page = None                              # 차례 세우기는 이 시험 밖
    calls = _one_pass(pub, monkeypatch, PAGES, PAGES)
    r = asyncio.run(ds.sync(pub, "지금"))
    assert calls == ["notion/00_a.md", "notion/01_b.md"]
    a, b = rows["notion/00_a.md"], rows["notion/01_b.md"]
    assert a["content_hash"] == str(hash(PAGES["notion/00_a.md"])) and b["content_hash"]
    assert _page_links(pub, a["notion_page_id"]) == [("「둘째」", b["url"])]
    assert _page_links(pub, b["notion_page_id"]) == [("「00 처음」", a["url"])]
    appends = [c[1] for c in pub.c.calls if c[0] == "append"]
    assert sorted(appends) == sorted([a["notion_page_id"], b["notion_page_id"]])   # 페이지마다 한 번
    assert [c for c in pub.c.calls if c[0] == "create"] == [("create", "root", "00 처음"), ("create", "root", "01 둘째")]
    assert [w["path"] for w in r["warnings"]] == ["notion/00_a.md"] and "없는 편" in r["warnings"][0]["warning"]
    assert [(d["path"], d["action"]) for d in r["done"]] == [("notion/00_a.md", "created"), ("notion/01_b.md", "created")]


def test_portfolio_one_pass_relinks_waiting_piece(patched, monkeypatch):
    """포트폴리오 묶음 게시(11-20). 앞서 한 편만 올라가 링크를 못 건 편(바뀜, 링크만)과 새 편을 한 번에 올리면 둘 다 걸리고,
    포트폴리오 제목은 번호와 첫 H1(게시기가 정한다)."""
    PAGES["portfolio/00_a.md"] = "# 한눈에\n\n→ 「승인 카드」\n"
    PAGES["portfolio/01_b.md"] = "# 승인 카드\n\n→ 「한눈에」\n"
    rows: dict = {}
    pub = _Pub(rows)
    pub.keep_order = True                             # 차례 세우기는 이 시험 밖(DB 없는 가짜 게시기)
    asyncio.run(pub.publish("portfolio/00_a.md"))
    assert rows["portfolio/00_a.md"]["content_hash"] is None
    calls = _one_pass(pub, monkeypatch, PAGES, ["portfolio/01_b.md"], ["portfolio/00_a.md"])
    r = asyncio.run(ds.sync(pub, "지금", src=ds.PORT))
    assert sorted(calls) == ["portfolio/00_a.md", "portfolio/01_b.md"] and not r["warnings"] and not r["failed"]
    a, b = rows["portfolio/00_a.md"], rows["portfolio/01_b.md"]
    assert a["content_hash"] and _page_links(pub, a["notion_page_id"]) == [("「승인 카드」", b["url"])]
    assert pub.c.pages[b["notion_page_id"]]["title"] == "01 승인 카드"


def test_docs_projects_do_not_read_refs(patched):
    """docs/를 그대로 올리는 프로젝트(런슈즈, 펫퍼민트)는 알아보지 않는다 — 색인도 읽지 않는다."""
    pub = _Pub({})
    assert pub.xref_group("docs/a.md") is None and pub.xref_group("portfolio/00_a.md") == "portfolio/"
    pub2 = _Pub({}, opts={"src": "notion/"})
    assert pub2.xref_group("notion/02_x/01_y.md") == "notion/"
