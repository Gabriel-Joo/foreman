"""Notion 게시기 `title = "h1"`(11-12) — 제목 = 문서의 첫 H1. 가짜 Notion · 순수 함수만(네트워크 · 토큰 없음)."""
import asyncio

import pytest

from bridge import docsync as ds
from bridge import notion as nt
from test_notion import FakeNotion


def test_first_h1_rules():
    """첫 H1 = 코드 울타리 · 맨 위 YAML 머리말 · HTML 주석 밖에서 처음 나오는 `# ` 줄. 앞에 다른 줄이 있어도 된다."""
    f = nt.first_h1
    assert f("# 제목\n\n본문") == (0, "제목")
    assert f("\n\n<!-- 주석 -->\n# 제목 [t:1234] `코드` **굵게**\n") == (3, "제목 코드 굵게")
    assert f("---\ntitle: x\n# yaml 안 주석\n---\n\n# 진짜\n") == (5, "진짜")
    assert f("<!--\n# 주석 안\n-->\n# 진짜") == (3, "진짜")
    assert f("```bash\n# 셸 주석\n```\n~~~\n# 또\n~~~\n# 진짜") == (6, "진짜")
    assert f("> 상태: 초안\n\n## 소제목\n\n# 뒤늦은 H1") == (4, "뒤늦은 H1")      # 앞에 인용 · 소제목이 있어도 첫 H1
    assert f("# 닫는 표시 ##") == (0, "닫는 표시")
    assert f("# \n# 둘째") == (1, "둘째")                                          # 빈 제목은 건너뜀
    assert f("본문만\n## 소제목") == (None, None)
    assert f("#해시태그 아님\n") == (None, None)


def test_h1_title_not_repeated_in_body_even_with_headings_md():
    md = "# 제목\n\n## 가\n\n본문\n\n### 나\n"
    for hm in (False, True):
        t, blocks = nt.md_to_blocks(md, nt.Ctx(heading_md=hm, h1_title=True))
        assert t == "제목"
        kinds = [b["type"] for b in blocks]
        assert kinds == (["heading_2", "paragraph", "heading_3"] if hm else ["heading_1", "paragraph", "heading_2"])


def test_h1_after_other_blocks_still_removed_from_body_and_second_h1_kept():
    md = "> 상태\n\n# 제목\n\n# 둘째 H1\n"
    t, blocks = nt.md_to_blocks(md, nt.Ctx(h1_title=True))
    assert t == "제목"
    assert [b["type"] for b in blocks] == ["quote", "heading_1"]      # 둘째 H1은 본문 heading으로 남는다
    # 옛 방식(h1_title 꺼짐)은 앞에 블록이 있으면 이 H1을 제목으로 보지 않고 본문에 둔다 — 그대로
    t2, b2 = nt.md_to_blocks(md, nt.Ctx())
    assert t2 is None and [b["type"] for b in b2] == ["quote", "heading_1", "heading_1"]


def test_default_output_unchanged_when_h1_off():
    """설정을 안 바꾼 쪽(런슈즈 · 펫퍼민트 · FOREMAN)은 제목 · 블록이 같다."""
    md = "# 제목 [t:12]\n\n## 가\n\n본문 `x`\n\n- a\n- b\n"
    for hm in (False, True):
        a = nt.md_to_blocks(md, nt.Ctx(heading_md=hm))
        b = nt.md_to_blocks(md, nt.Ctx(heading_md=hm, h1_title=False))
        assert a == b
    assert nt.md_to_blocks(md, nt.Ctx())[0] == "제목"
    p = nt.Publisher(None, None, "a" * 32, ".", project="x", opts={"title": "keep", "headings": "md"})
    assert p.keep_title and not p.h1_title and not p._ctx("docs/a.md", "HEAD").h1_title
    q = nt.Publisher(None, None, "a" * 32, ".", project="x")
    assert not q.keep_title and not q.h1_title


def test_h1_option_is_docs_only_and_exclusive_with_keep(caplog):
    p = nt.Publisher(None, None, "a" * 32, ".", project="x", opts={"title": "h1"})
    assert p.h1_title and not p.keep_title                       # 한 칸이라 keep과 h1은 함께 켜지지 않는다
    assert p._ctx("docs/a.md", "HEAD").h1_title
    assert not p._ctx("portfolio/00_a.md", "HEAD").h1_title      # 포트폴리오는 그대로
    with caplog.at_level("WARNING"):
        r = nt.Publisher(None, None, "a" * 32, ".", project="x", opts={"title": "H1"})   # 모르는 값
    assert not r.h1_title and not r.keep_title and "title" in caplog.text


class _Pub(nt.Publisher):
    """DB 없이 — 행은 dict로, git은 파일 맵으로."""
    def __init__(self, files, rows, **kw):
        super().__init__(None, FakeNotion(), "root", ".", project="x", **kw)
        self.files, self.rows = files, rows

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


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(nt, "git_show", lambda repo, path, ref="HEAD": (PAGES[path], "c" * 40))
    monkeypatch.setattr(nt, "content_digest", lambda repo, path, body, ref="HEAD": str(hash(body)))
    PAGES.clear()


PAGES: dict[str, str] = {}


def _run(coro):
    return asyncio.run(coro)


def test_publish_title_follows_h1_for_new_and_paired_pages(patched):
    PAGES["docs/a.md"] = "# 첫 제목\n\n## 가\n\n본문\n"
    PAGES["docs/b.md"] = "본문만 있고 H1 없음\n"
    rows: dict = {}
    pub = _Pub(PAGES, rows, opts={"title": "h1", "headings": "md"})
    r = _run(pub.publish("docs/a.md", title="a — README 표 설명"))      # docsync가 README 제목을 줘도 H1이 앞선다
    assert r["action"] == "created"
    pid = r["page_id"]
    assert pub.c.pages[pid]["title"] == "첫 제목" and rows["docs/a.md"]["title"] == "첫 제목"
    body_kinds = [b["type"] for b in pub.c.blocks[pid]]
    assert "heading_2" in body_kinds and "heading_1" not in body_kinds    # H1이 본문에 한 번 더 들어가지 않는다
    # H1을 바꾼다 → 이미 짝지은 페이지의 Notion 제목도 바뀐다
    rows["docs/a.md"].update(status="published", notion_page_id=pid, parent_page_id="root", content_hash="old")
    PAGES["docs/a.md"] = "# 바뀐 제목\n\n## 가\n\n본문\n"
    r2 = _run(pub.publish("docs/a.md", title="a — README 표 설명"))
    assert r2["action"] == "updated"
    assert pub.c.pages[pid]["title"] == "바뀐 제목" and rows["docs/a.md"]["title"] == "바뀐 제목"
    # 제목만 바뀐 경우(본문 지문 같음)도 set_title이 불린다
    PAGES["docs/a.md"] = PAGES["docs/a.md"]
    rows["docs/a.md"]["content_hash"] = str(hash(PAGES["docs/a.md"]))
    rows["docs/a.md"]["title"] = "옛 제목"
    r3 = _run(pub.publish("docs/a.md"))
    assert r3["action"] == "unchanged" and pub.c.pages[pid]["title"] == "바뀐 제목"
    # H1이 없는 문서 → README 표 제목 방식으로 돌아간다
    r4 = _run(pub.publish("docs/b.md", title="b — 표 설명"))
    assert pub.c.pages[r4["page_id"]]["title"] == "b — 표 설명"


def test_publish_without_h1_option_keeps_old_title_logic(patched):
    PAGES["docs/a.md"] = "# 첫 제목\n\n## 가\n\n본문\n"
    for opts, given, want in ((None, "a — 표", "a — 표"), (None, None, "첫 제목"), ({"headings": "md"}, "a — 표", "a — 표")):
        pub = _Pub(PAGES, {}, opts=opts)
        r = _run(pub.publish("docs/a.md", title=given))
        assert pub.c.pages[r["page_id"]]["title"] == want
        kinds = [b["type"] for b in pub.c.blocks[r["page_id"]]]
        assert kinds[1:3] == (["heading_1", "paragraph"] if not opts else ["heading_2", "paragraph"])   # [0]은 사본 안내 상자


def test_docsync_status_uses_h1_and_flags_changes_and_missing(monkeypatch):
    files = {"docs/a.md": "# 새 H1\n본문", "docs/b.md": "H1 없음", "docs/README.md": "| 파일 | 설명 |\n|---|---|\n| `a.md` | 에이 — 길게 |\n"}
    monkeypatch.setattr(ds, "docs_files", lambda repo, ref, skip=(), src="docs/": ["docs/a.md", "docs/b.md"])
    monkeypatch.setattr(ds, "_git", lambda repo, *a: files["docs/README.md"] if a[:1] == ("show",) else "")
    monkeypatch.setattr(ds, "git_show", lambda repo, f, ref: (files[f], "c"))
    monkeypatch.setattr(ds, "content_digest", lambda repo, f, body, ref: "d")

    class Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            class R:
                def mappings(s):
                    class M:
                        def all(m):
                            return [{"path": "docs/a.md", "status": "published", "title": "옛 H1", "content_hash": "d",
                                     "commit_sha": "c", "notion_page_id": "p", "url": "u"},
                                    {"path": "docs/b.md", "status": "published", "title": "b", "content_hash": "d",
                                     "commit_sha": "c", "notion_page_id": "p2", "url": "u"}]
                    return M()
            return R()

    class E:
        def connect(self):
            return Conn()

    pub = nt.Publisher(E(), None, "a" * 32, ".", project="x", docs_mode="auto", opts={"title": "h1"})
    st = _run(ds.status(pub))
    assert st["titles"]["docs/a.md"] == "새 H1" and st["changed"] == ["docs/a.md"]     # H1이 바뀌어 changed(지문은 같아도)
    assert st["h1_missing"] == ["docs/b.md"] and st["titles"]["docs/b.md"] == "b"      # README 표에 없으니 파일 이름
    off = nt.Publisher(E(), None, "a" * 32, ".", project="x", docs_mode="auto")
    st2 = _run(ds.status(off))
    assert st2["titles"]["docs/a.md"] == "a — 에이" and st2["h1_missing"] == []
