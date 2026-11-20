"""노션 기술문서 원고(notion/)와 포트폴리오 원고(11-15) — 머리 주석 · 나무 부모 · 부모마다 차례 · 노션 판에서 떼기 · 코드가 바뀐 편 ·
원본 없는 포트폴리오 내리기 · 근거 확인기 [code:]. 진짜 git 저장소(tmp) · 가짜 Notion · 메모리 게시 기록(doc_publish)."""
import asyncio
import re
import subprocess

import pytest

from bridge import docsync as ds
from bridge import evidence as ev
from bridge import manuscript as ms
from bridge import notion as nt
from bridge import notioncfg as nc
from test_notion import FakeNotion


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(repo)})
    return r.stdout.strip()


def _write(repo, files):
    for path, body in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if body is None:
            p.unlink()
        else:
            p.write_text(body, encoding="utf-8")


def _commit(repo, files, msg):
    _write(repo, files)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "--short", "HEAD")


class FakeDB:
    """doc_publish 한 표만 — 게시기 · 맞추기가 부르는 SELECT · INSERT 꼴만 알아듣는다(MySQL 없이)."""

    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def connect(self):
        return _Conn(self)

    def begin(self):
        return _Conn(self)


class _Res:
    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols

    def mappings(self):
        return self

    def all(self):
        return [r if self.cols is None else tuple(r.get(c) for c in self.cols) for r in self._shaped()]

    def first(self):
        a = self.all()
        return a[0] if a else None

    def _shaped(self):
        return [dict(r) if self.cols is None else r for r in self.rows]


class _Conn:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, q, params=None):
        sql, p = str(q), dict(params or {})
        if sql.startswith("INSERT INTO doc_publish"):
            row = self.db.rows.setdefault((p["project"], p["path"]), {"kind": None, "status": None, "updated_at": None})
            row.update(p)
            return _Res([], None)
        assert "FROM doc_publish" in sql, sql
        cols_txt = sql.split("SELECT", 1)[1].split("FROM", 1)[0].strip()
        cols = None if cols_txt == "*" else [c.strip() for c in cols_txt.split(",")]
        out = []
        for (proj, path), r in sorted(self.db.rows.items()):
            if proj != p.get("p"):
                continue
            ok = True
            if "path = :f" in sql:
                ok &= path == p["f"]
            if "LIKE :pre" in sql:
                like = path.startswith(p["pre"].rstrip("%"))
                ok &= like or ("path = :m" in sql and path == p.get("m"))
            if "kind = 'doc'" in sql:
                ok &= r.get("kind") == "doc"
            if "status = 'published'" in sql:
                ok &= r.get("status") == "published"
            if "notion_page_id = :id" in sql:
                ok &= r.get("notion_page_id") == p["id"]
            if ok:
                out.append(r)
        return _Res(out, None) if cols is None else _MapOrTuple(out, cols)


class _MapOrTuple(_Res):
    """같은 결과를 .mappings()로도(딕트) .all()로도(튜플) 읽는다."""

    def mappings(self):
        return _Res([{c: r.get(c) for c in self.cols} for r in self.rows], None)


def _fake_notion():
    f = FakeNotion(see_all=True)
    f.pages["docs"] = {"parent": "root", "title": "[기술문서]", "archived": False}
    f.pages["port"] = {"parent": "root", "title": "[포트폴리오]", "archived": False}
    return f


def _pub(repo, db, f, **opts):
    return nt.Publisher(db, f, "root", str(repo), project="foreman", ref="HEAD", docs_page="docs", portfolio_page="port",
                        docs_mode="manual", opts={"src": "notion/", "title": "h1", "header": "footer", **opts})


def _texts(f, pid):
    return [nt.plain((b.get(b["type"]) or {}).get("rich_text") or []) for b in f.blocks.get(pid, [])]


# ── 머리 주석 ───────────────────────────────────────────────

def test_head_parse_strip_and_roundtrip():
    md = ms.head_text(["bridge/a.py", "bridge/static/js/"], "abc1234") + "\n# 제목\n\n본문 [code:bridge/a.py]\n\n```\n<!-- 코드 안 -->\n```\n"
    h = ms.parse_head(md)
    assert h == {"covers": ["bridge/a.py", "bridge/static/js/"], "read": "abc1234", "line": 1}
    assert "다루는 곳" not in ms.strip_comments(md) and "<!-- 코드 안 -->" in ms.strip_comments(md)   # 울타리 안 주석은 글이다
    assert ms.parse_head("# 머리 주석 없음\n<!-- 그냥 주석 -->\n") is None
    two = "<!--\n다루는 곳: a.py\n다루는 곳: `b/`, c.toml\n읽은 커밋:\n-->\n"
    assert ms.parse_head(two) == {"covers": ["a.py", "b/", "c.toml"], "read": None, "line": 1}
    assert ms.bad_covers(["../x", "/etc", "ok/", ":(glob)x"]) == ["../x", "/etc", ":(glob)x"]


def test_tree_order_and_parent():
    paths = ["notion/10_z.md", "notion/02_b/01_c.md", "notion/02_b.md", "notion/00_a.md", "notion/02_b/00_d.md",
             "notion/03a_e.md", "notion/03_f.md", "notion/README.md"]
    assert ms.tree_order(paths) == ["notion/00_a.md", "notion/02_b.md", "notion/02_b/00_d.md", "notion/02_b/01_c.md",
                                    "notion/03_f.md", "notion/03a_e.md", "notion/10_z.md", "notion/README.md"]
    assert ms.tree_parent("notion/02_b/01_c.md", "notion/") == "notion/02_b.md"
    assert ms.tree_parent("notion/02_b.md", "notion/") is None


def test_notion_cut_strips_head_and_marks_but_docs_keep_them():
    md = ms.head_text(["bridge/a.py"], "abc1234") + "\n# 브리지\n\n훅을 받는다 [code:bridge/a.py:10-20] [c:abc1234] [log:x.md].\n"
    title, bs = nt.md_to_blocks(md, nt.Ctx("notion/02_bridge.md", "abc", links=False, h1_title=True, manuscript=True))
    assert title == "브리지" and [nt.plain(b["paragraph"]["rich_text"]) for b in bs] == ["훅을 받는다."]
    _, docs = nt.md_to_blocks("본문 [code:bridge/a.py:3]\n", nt.Ctx("docs/a.md", "abc"))
    rt = docs[0]["paragraph"]["rich_text"]
    assert rt[-1]["text"]["content"] == "bridge/a.py" and rt[-1]["text"]["link"]["url"].endswith("/blob/abc/bridge/a.py")
    _, port = nt.md_to_blocks("<!--\n읽은 커밋: abc\n-->\n# 글\n\n근거 [c:abc1234]\n", nt.Ctx("portfolio/01.md", links=False, manuscript=True))
    assert [nt.plain(b["paragraph"]["rich_text"]) for b in port] == ["근거"]


def test_code_commits_counts_feat_fix_on_covered_paths_only(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    read = _commit(tmp_path, {"bridge/a.py": "1", "bridge/b.py": "1", "bridge/static/x.js": "1"}, "feat: 처음")
    _commit(tmp_path, {"bridge/a.py": "2"}, "fix: a 고침")
    _commit(tmp_path, {"bridge/a.py": "3"}, "docs: a 주석")              # 문서 맞추기 커밋은 세지 않는다
    _commit(tmp_path, {"bridge/b.py": "2"}, "feat: b")                   # 다루지 않는 곳
    _commit(tmp_path, {"bridge/static/x.js": "2"}, "feat!: 폴더 안")
    assert ms.code_commits(str(tmp_path), read, ["bridge/a.py"]) == 1
    assert ms.code_commits(str(tmp_path), read, ["bridge/a.py", "bridge/static/"]) == 2
    assert ms.code_commits(str(tmp_path), read, ["bridge/static/*.js"]) == 1
    assert ms.code_commits(str(tmp_path), "0000000", ["bridge/a.py"]) is None       # 저장소에 없는 커밋 — 0이 아니라 셀 수 없음
    assert ms.code_commits(str(tmp_path), None, ["bridge/a.py"]) is None
    assert ms.code_commits(str(tmp_path), read, ["../밖"]) is None


# ── 노션 원고 → [기술문서] ──────────────────────────────────────

def _tree_repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    read = _commit(tmp_path, {"bridge/a.py": "1", "bridge/b.py": "1"}, "feat: 코드")
    h = lambda covers: ms.head_text(covers, read) + "\n"  # noqa: E731
    _commit(tmp_path, {
        "notion/00_intro.md": h(["bridge/b.py"]) + "# 들어가며\n\n이 글 [c:" + read + "]\n",
        "notion/02_bridge.md": h(["bridge/a.py"]) + "# 브리지\n\n훅 [code:bridge/a.py]\n",
        "notion/02_bridge/01_hooks.md": h(["bridge/a.py"]) + "# 훅\n\n자세히\n",
        "notion/02_bridge/00_db.md": "# DB\n\n머리 주석 없음\n",
        "notion/01_shape.md": h(["bridge/b.py"]) + "# 생김새\n\n본문\n",
        "docs/12.md": "# docs는 올리지 않는다\n",
    }, "docs: 원고")
    return read


def test_tree_sync_parents_order_titles_and_clean_cut(tmp_path):
    _tree_repo(tmp_path)
    db, f = FakeDB(), _fake_notion()
    pub = _pub(tmp_path, db, f)
    st = asyncio.run(ds.status(pub))
    assert st["files"] == ["notion/00_intro.md", "notion/01_shape.md", "notion/02_bridge.md", "notion/02_bridge/00_db.md",
                           "notion/02_bridge/01_hooks.md"]                                      # docs/는 대상이 아니다
    assert st["code_unknown"] == ["notion/02_bridge/00_db.md"] and st["code_changed"] == []
    r = asyncio.run(ds.sync(pub, "지금"))
    assert not r["failed"] and not r["held"] and len(r["done"]) == 5
    page = {p: db.rows[("foreman", p)]["notion_page_id"] for p in st["files"]}
    titles = {p: f.pages[page[p]]["title"] for p in st["files"]}
    assert titles["notion/02_bridge.md"] == "브리지" and titles["notion/02_bridge/01_hooks.md"] == "훅"   # 제목은 첫 H1
    assert f.pages[page["notion/02_bridge/01_hooks.md"]]["parent"] == page["notion/02_bridge.md"]          # 폴더 아래는 그 글 아래
    assert f.pages[page["notion/01_shape.md"]]["parent"] == "docs"
    kids = lambda pid: [k["id"] for k in asyncio.run(f.children(pid)) if k["type"] == "child_page"]  # noqa: E731
    assert kids("docs") == [page[p] for p in ("notion/00_intro.md", "notion/01_shape.md", "notion/02_bridge.md")]
    assert kids(page["notion/02_bridge.md"]) == [page["notion/02_bridge/00_db.md"], page["notion/02_bridge/01_hooks.md"]]
    body = " ".join(t for p in st["files"] for t in _texts(f, page[p]))
    assert "다루는 곳" not in body and "[code:" not in body and "[c:" not in body and "bridge/a.py" not in body
    links = [t["text"].get("link") for p in st["files"] for b in f.blocks[page[p]] for t in (b.get(b["type"]) or {}).get("rich_text", [])]
    assert not any(links)                                                                   # 비공개 저장소 — 링크 없음(꼬리 줄도)
    assert any(nt.is_footer_text(t) and "읽은 커밋" in t and "—" not in t for t in _texts(f, page["notion/02_bridge.md"]))
    assert asyncio.run(ds.status(pub))["new"] == []


def test_tree_counts_code_changes_after_read_and_summary(tmp_path):
    _tree_repo(tmp_path)
    _commit(tmp_path, {"bridge/a.py": "2"}, "fix: 브리지 고침")
    _commit(tmp_path, {"bridge/a.py": "3"}, "test: 시험만")
    db, f = FakeDB(), _fake_notion()
    pub = _pub(tmp_path, db, f)
    st = asyncio.run(ds.status(pub))
    assert st["code_changed"] == [{"path": "notion/02_bridge.md", "commits": 1}, {"path": "notion/02_bridge/01_hooks.md", "commits": 1}]
    s = asyncio.run(ds.summary(pub, None))
    assert (s["src"], s["code_changed"], s["code_unknown"], s["total"]) == ("notion/", 2, 1, 5)
    items = asyncio.run(ds.todo_items(pub, None))
    assert items and "[Notion에 올리기]" in items[0]["why"]


def test_child_without_parent_and_parent_deleted_with_children(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, {"notion/02_x/01_y.md": "# 와이\n"}, "docs: 부모 없는 글")
    db, f = FakeDB(), _fake_notion()
    pub = _pub(tmp_path, db, f)
    r = asyncio.run(ds.sync(pub, "지금"))
    assert r["failed"][0]["path"] == "notion/02_x/01_y.md" and "부모 글 notion/02_x.md" in r["failed"][0]["error"]
    _commit(tmp_path, {"notion/02_x.md": "# 엑스\n"}, "docs: 부모")
    r = asyncio.run(ds.sync(pub, "지금"))
    assert not r["failed"] and {d["path"] for d in r["done"]} == {"notion/02_x.md", "notion/02_x/01_y.md"}
    _commit(tmp_path, {"notion/02_x.md": None}, "docs: 부모만 지움")
    r = asyncio.run(ds.sync(pub, "지금"))
    assert r["failed"][0]["path"] == "notion/02_x.md" and "아래 글" in r["failed"][0]["error"]   # 휴지통에 보내면 아래 페이지도 간다
    assert not [c for c in f.calls if c[0] == "archive"]


def test_docs_projects_unchanged(tmp_path):
    """런슈즈 · 펫퍼민트 · 인프라(src 없음 = docs/)는 그대로 — notion/은 보지 않고 docs/README 표 차례, 원고 셈 없음."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, {"docs/README.md": "| `b.md` | 비 |\n", "docs/b.md": "# B\n", "notion/00_a.md": "# 원고\n"}, "docs")
    pub = nt.Publisher(FakeDB(), _fake_notion(), "root", str(tmp_path), project="runshoes", docs_page="docs", docs_mode="auto")
    assert pub.src == "docs/" and not pub.tree
    st = asyncio.run(ds.status(pub))
    assert st["files"] == ["docs/README.md", "docs/b.md"] and st["code_changed"] == [] and st["code_unknown"] == []
    odd = nt.Publisher(FakeDB(), _fake_notion(), "root", str(tmp_path), opts={"src": "../x/"})
    assert odd.src == "docs/"                                                        # 모르는 값은 docs/로(로그 경고)


def test_repo_config_src_validated():
    assert nc.parse_repo_file('src = "notion/"\n')[0] == {"src": "notion/"}
    with pytest.raises(ValueError, match="src"):
        nc.parse_repo_file('src = "log/"\n')
    assert "src" in nc.OPT_KEYS


def test_portfolio_links_to_published_notion_piece(tmp_path):
    """사용자 목차 결정 4(11-15) — 포트폴리오 편 끝 노션 링크 한 줄. 원고 상대 경로가 게시된 노션 원고면 그 Notion 페이지로 걸고,
    아직 안 올린 원고 · 저장소 파일은 글자만(비공개 저장소)."""
    _tree_repo(tmp_path)
    _commit(tmp_path, {"portfolio/01_room.md": "# 서기실\n\n본문\n\n[기술문서: 브리지](../notion/02_bridge.md) · "
                                                "[없는 편](../notion/09_none.md) · [저장소 파일](../bridge/a.py)\n"}, "docs: 포트폴리오")
    db, f = FakeDB(), _fake_notion()
    pub = _pub(tmp_path, db, f)
    asyncio.run(ds.sync(pub, "지금"))
    asyncio.run(pub.publish("portfolio/01_room.md", "지금"))
    pid = db.rows[("foreman", "portfolio/01_room.md")]["notion_page_id"]
    rt = [t for b in f.blocks[pid] for t in (b.get(b["type"]) or {}).get("rich_text", [])]
    links = {t["text"]["content"]: (t["text"].get("link") or {}).get("url") for t in rt}
    assert links["기술문서: 브리지"] == db.rows[("foreman", "notion/02_bridge.md")]["url"]
    assert links["없는 편"] is None and links["저장소 파일"] is None


# ── 포트폴리오 옛 편 내리기 ─────────────────────────────────────

def test_portfolio_sync_archives_only_gone_sources(tmp_path):
    """포트폴리오 [Notion에 올리기] 한 번(11-20)이 git에서 지운 편만 휴지통으로 보낸다(전에는 따로 누르던 [원본 없는 페이지 내리기])."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, {"portfolio/00_old.md": "# 옛\n", "portfolio/01_keep.md": "# 남김\n"}, "docs: 옛 판")
    db, f = FakeDB(), _fake_notion()
    pub = _pub(tmp_path, db, f)
    assert [d["action"] for d in asyncio.run(ds.sync(pub, "지금", src=ds.PORT))["done"]] == ["created", "created"]
    _commit(tmp_path, {"portfolio/00_old.md": None, "portfolio/02_new.md": "# 새\n"}, "docs: 새 판")
    lst = {d["path"]: d for d in asyncio.run(pub.list())}
    assert lst["portfolio/00_old.md"]["gone"] and not lst["portfolio/01_keep.md"]["gone"] and not lst["portfolio/02_new.md"]["gone"]
    r = asyncio.run(ds.sync(pub, "지금", src=ds.PORT))
    assert sorted((d["path"], d["action"]) for d in r["done"]) == [("portfolio/00_old.md", "archived"), ("portfolio/02_new.md", "created")]
    old = db.rows[("foreman", "portfolio/00_old.md")]
    assert old["status"] == "archived" and f.pages[old["notion_page_id"]]["archived"]
    assert not f.pages[db.rows[("foreman", "portfolio/01_keep.md")]["notion_page_id"]]["archived"]
    assert asyncio.run(ds.sync(pub, "지금", src=ds.PORT))["done"] == []                # 두 번 눌러도 더 하지 않는다


# ── 근거 확인기 ─────────────────────────────────────────────

def test_evidence_code_marks_and_head(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    read = _commit(tmp_path, {"bridge/a.py": "1\n2\n3\n"}, "feat: a")
    body = (ms.head_text(["bridge/a.py", "bridge/없음.py"], read) + "\n# 글\n\n"
            "있음 [code:bridge/a.py:2-3] 폴더 [code:bridge/] 없음 [code:bridge/b.py] 밖 [code:../x] 넘침 [code:bridge/a.py:9]\n")
    r = asyncio.run(ev.check_text(body, str(tmp_path)))
    whys = {b["mark"]: b["why"] for b in r["bad"]}
    assert set(whys) == {"[code:bridge/b.py]", "[code:../x]", "[code:bridge/a.py:9]", "머리 주석 다루는 곳 bridge/없음.py"}
    assert "파일이 없습니다" in whys["[code:bridge/b.py]"] and "밖" in whys["[code:../x]"]
    assert not any(u["text"].startswith("읽은 커밋") for u in r["unsupported"])          # 머리 주석 줄은 「근거 없는 줄」이 아니다
    gone = asyncio.run(ev.check_text(ms.head_text(["bridge/a.py"], "deadbee") + "\n", str(tmp_path)))
    assert [b["why"] for b in gone["bad"]] == ["그 커밋이 저장소에 없습니다"]
    assert re.search(r"code", ev.MARK.pattern)
