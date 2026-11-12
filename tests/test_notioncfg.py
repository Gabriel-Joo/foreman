"""Notion 게시 설정을 프로젝트 저장소로(11-12) — <저장소>/.foreman/notion.toml(origin/main) · 짝 등록. 진짜 git(tmp) · 가짜 Notion."""
import asyncio
import subprocess
import tomllib

import pytest

from bridge import notion as nt
from bridge import notioncfg as nc
from test_notion import FakeNotion

# 런슈즈 · 펫퍼민트 칸(config/notion.toml 11-12 그대로 옮김 — 시험은 실제 config/를 읽지 않는다)
FOREMAN_TOML = """
[runshoes]
root = "4133218bb524818e8a7df47d63345270"
docs_page = "3e33218bb52480ffa796c8a04d324a06"
portfolio_page = "4133218bb52481dc803ce2938c011be0"
github = "https://github.com/Gabriel-Joo/runshoes"
ref = "origin/main"
docs = "auto"
quiet_min = 30

[petmint-rag-chatbot]
root = "4133218bb52481e9a348d79355fea5cd"
docs_page = "3ea3218bb5248091aa0bc1eb58ae9ccb"
portfolio_page = "4133218bb5248142883af1f21788f6ca"
github = "https://github.com/Gabriel-Joo/petmint-rag-chatbot"
ref = "origin/main"
docs = "auto"
quiet_min = 30
create = true
archive = false
headings = "md"
new_parent = "folder"
new_title = "numbered"
title = "keep"
order = "keep"
header = "footer"
keep_notion = ["inline_code", "image", "heading", "shape"]
skip = ["docs/README.md", "docs/next_rebuild.md", "docs/ops/"]

[ronanlab-infra]
root = "4133218bb52481079af8f3712ad8d73c"
docs_page = "4153218bb52480069acbdd52063fe2c5"
ref = "origin/main"
docs = "manual"
quiet_min = 30
create = false
title = "keep"
skip = ["docs/README.md"]
"""
BASE = tomllib.loads(FOREMAN_TOML)
ATTRS = ("docs_mode", "quiet_min", "create", "keep_title", "h1_title", "keep_order", "footer", "keep_notion", "skip", "archive_ok",
         "heading_md", "new_parent", "new_title", "root", "docs_page", "portfolio_page", "ref", "gh")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                               "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(repo)}).stdout.strip()


def _repo(tmp_path, cfg=None, push=True):
    """저장소 하나 — cfg가 있으면 .foreman/notion.toml을 커밋하고, push면 origin/main을 그 커밋으로."""
    if not (tmp_path / ".git").exists():
        _git(tmp_path, "init", "-q", "-b", "main")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "a.md").write_text("# A\n\n본문\n")
    if cfg is not None:
        (tmp_path / ".foreman").mkdir(exist_ok=True)
        (tmp_path / ".foreman" / "notion.toml").write_text(cfg)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "c")
    if push:
        _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return str(tmp_path)


def _old_publisher(name, repo):
    """고치기 전 bridge/main.py의 식 그대로 — 전후 비교용."""
    ncfg = BASE[name]
    return nt.Publisher(None, None, ncfg["root"], repo, project=name, gh=ncfg.get("github") or "https://github.com/Gabriel-Joo/foreman",
                        ref=ncfg.get("ref") or "HEAD", docs_page=ncfg.get("docs_page"), portfolio_page=ncfg.get("portfolio_page"),
                        docs_mode=ncfg.get("docs") or "off", quiet_min=float(ncfg.get("quiet_min") or 30),
                        opts={k: ncfg.get(k) for k in ("create", "title", "order", "header", "keep_notion", "skip", "archive",
                                                       "headings", "new_parent", "new_title") if k in ncfg})


def _new_publisher(cfg, name, repo):
    ncfg = BASE[name]
    return nt.Publisher(None, None, ncfg["root"], repo, project=name, gh=ncfg.get("github") or "https://github.com/Gabriel-Joo/foreman",
                        ref=ncfg.get("ref") or "HEAD", docs_page=ncfg.get("docs_page"), portfolio_page=ncfg.get("portfolio_page"),
                        **cfg.args_for(name, repo))


@pytest.mark.parametrize("name", ["runshoes", "petmint-rag-chatbot", "ronanlab-infra"])
def test_no_repo_file_means_foreman_columns_exactly_as_before(tmp_path, name):
    """설정을 안 옮긴 쪽(저장소 파일 없음)은 아무것도 달라지지 않는다 — 게시기 칸 값 전부 전후 같음."""
    repo = _repo(tmp_path)
    cfg = nc.NotionConfig(BASE)
    old, new = _old_publisher(name, repo), _new_publisher(cfg, name, repo)
    assert {a: getattr(old, a) for a in ATTRS} == {a: getattr(new, a) for a in ATTRS}
    assert cfg.state[name]["source"] == "foreman" and cfg.state[name]["error"] is None and cfg.state[name]["blob"] is None


def test_repo_file_wins_and_owns_all_repo_keys(tmp_path):
    repo = _repo(tmp_path, 'docs = "auto"\nquiet_min = 10\ntitle = "h1"\nheadings = "md"\n')
    cfg = nc.NotionConfig(BASE)
    pub = _new_publisher(cfg, "ronanlab-infra", repo)
    assert pub.docs_mode == "auto" and pub.quiet_min == 10 and pub.h1_title and not pub.keep_title and pub.heading_md
    # 저장소 파일이 있으면 FOREMAN 칸(create = false · skip)은 쓰지 않는다 — 섞지 않는다(경고로 알림)
    assert pub.create is True and pub.skip == set()
    st = cfg.state["ronanlab-infra"]
    assert st["source"] == "repo" and any("create" in w and "쓰지 않습니다" in w for w in st["warnings"])
    # 쓰기 범위는 FOREMAN 그대로
    assert pub.root == BASE["ronanlab-infra"]["root"] and pub.ref == "origin/main"


def test_root_in_repo_file_is_ignored_with_warning(tmp_path):
    sent = []
    repo = _repo(tmp_path, 'root = "4133218bb52481e9a348d79355fea5cd"\ndocs_page = "x"\nref = "HEAD"\ndocs = "manual"\nmoo = 1\n')
    cfg = nc.NotionConfig(BASE, _Notifier(sent))
    pub = _new_publisher(cfg, "ronanlab-infra", repo)
    assert pub.root == nt.norm(BASE["ronanlab-infra"]["root"]) and pub.ref == "origin/main" and pub.docs_mode == "manual"
    w = " ".join(cfg.state["ronanlab-infra"]["warnings"])
    assert "root는 FOREMAN" in w and "docs_page는 FOREMAN" in w and "ref는 FOREMAN" in w and "모르는 칸 moo" in w
    assert len(sent) == 1 and "경고" in sent[0][2]


def test_only_pushed_version_is_read(tmp_path):
    """작업 트리 · 안 올린 커밋은 보지 않는다 — origin/main에 있는 판만."""
    repo = _repo(tmp_path)
    _repo(tmp_path, 'docs = "auto"\n', push=False)          # 커밋했지만 push 안 함
    cfg = nc.NotionConfig(BASE)
    assert cfg.args_for("ronanlab-infra", repo)["docs_mode"] == "manual" and cfg.state["ronanlab-infra"]["source"] == "foreman"


class _Notifier:
    def __init__(self, sent):
        self.sent = sent
        self.rules = type("R", (), {"for_project": staticmethod(lambda p: None)})()

    def send_direct(self, project, kind, sid, msg):
        self.sent.append((project, kind, msg))


def test_broken_file_keeps_old_settings_and_alerts(tmp_path):
    sent = []
    repo = _repo(tmp_path, 'docs = "auto"\nquiet_min = 5\n')
    cfg = nc.NotionConfig(BASE, _Notifier(sent))
    pub = _new_publisher(cfg, "ronanlab-infra", repo)
    assert pub.docs_mode == "auto"
    for broken in ('docs = "auto\n', 'docs = "Auto"\n', 'quiet_min = "5"\n', 'skip = [1]\n', 'quiet_min = true\n'):
        _repo(tmp_path, broken)
        assert cfg.refresh({"ronanlab-infra": pub}) == []                    # 바뀐 것 없음 — 옛 설정 그대로
        st = cfg.state["ronanlab-infra"]
        assert pub.docs_mode == "auto" and pub.quiet_min == 5 and st["error"] and st.get("stale") and st["source"] == "repo"
    assert "FOREMAN 칸의" in sent[0][2]                                     # 처음 읽을 때 — 안 쓰는 FOREMAN 칸 경고(한 번)
    assert len(sent) == 6 and all("옛 설정을 그대로" in m for _, _, m in sent[1:])
    cfg.refresh({"ronanlab-infra": pub})
    assert len(sent) == 6                                                    # 같은 깨짐은 한 번만 알린다


def test_broken_at_startup_falls_back_to_foreman_and_alerts(tmp_path):
    sent = []
    repo = _repo(tmp_path, "docs = [\n")
    cfg = nc.NotionConfig(BASE, _Notifier(sent))
    assert cfg.args_for("ronanlab-infra", repo)["docs_mode"] == "manual"
    assert cfg.state["ronanlab-infra"]["error"] and len(sent) == 1 and "FOREMAN config/notion.toml 칸으로" in sent[0][2]


def test_missing_origin_main_is_an_error_not_silent_fallback(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "c")
    text, blob, err = nc.read_repo_file(str(tmp_path))
    assert text is None and blob is None and "origin/main" in err


def test_refresh_picks_up_new_push_and_removal(tmp_path):
    repo = _repo(tmp_path)
    cfg = nc.NotionConfig(BASE)
    pub = _new_publisher(cfg, "ronanlab-infra", repo)
    assert cfg.refresh({"ronanlab-infra": pub}) == []                        # 그대로면 configure 안 함
    _repo(tmp_path, 'docs = "auto"\ntitle = "h1"\n')
    assert cfg.refresh({"ronanlab-infra": pub}) == ["ronanlab-infra"]
    assert pub.docs_mode == "auto" and pub.h1_title and pub.create is True
    _git(tmp_path, "rm", "-q", ".foreman/notion.toml")
    _repo(tmp_path)
    assert cfg.refresh({"ronanlab-infra": pub}) == ["ronanlab-infra"]
    assert pub.docs_mode == "manual" and pub.keep_title and pub.create is False      # 파일을 지우면 FOREMAN 칸으로


def test_docsync_calls_before_tick(monkeypatch):
    from bridge import docsync as ds
    calls = []
    d = ds.DocSync({})
    d.before_tick = lambda: calls.append(1)

    async def go():
        async def fast_sleep(s):
            if calls:
                raise asyncio.CancelledError
        monkeypatch.setattr(ds.asyncio, "sleep", fast_sleep)
        with pytest.raises(asyncio.CancelledError):
            await d.run()
    asyncio.run(go())
    assert calls == [1]


# ── 짝 등록 ───────────────────────────────────────────────────
class _Eng:
    """doc_publish 행 dict — pair가 부르는 SELECT 하나만."""
    def __init__(self, rows):
        self.rows = rows

    def connect(self):
        rows = self.rows

        class C:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, sql, p):
                hit = [(k,) for k, r in rows.items() if r.get("notion_page_id") == p["id"] and k != p["f"]]

                class R:
                    def first(self):
                        return hit[0] if hit else None
                return R()
        return C()


class _PairPub(nt.Publisher):
    def __init__(self, repo, rows):
        f = FakeNotion()
        f.pages["docs"] = {"parent": "root", "title": "기술문서", "archived": False}
        f.pages["kube"] = {"parent": "docs", "title": "쿠버네티스 설치", "archived": False}
        f.pages["a" * 32] = {"parent": "kube", "title": "09. 모니터링", "archived": False}
        f.pages["b" * 32] = {"parent": "other", "title": "남의 페이지", "archived": False}
        orig = f.page

        async def page(pid):
            p = await orig(pid)
            return {**p, "properties": {"title": {"type": "title", "title": [{"plain_text": f.pages[pid]["title"]}]}}}
        f.page = page
        super().__init__(_Eng(rows), f, "root", repo, project="ronanlab-infra", ref="origin/main", docs_page="docs")
        self.rows = rows

    async def _row(self, path):
        return self.rows.get(path)

    async def _save(self, path, **kw):
        self.rows.setdefault(path, {}).update(kw)


def test_pair_registers_like_manual_sql(tmp_path):
    rows = {}
    pub = _PairPub(_repo(tmp_path), rows)
    r = asyncio.run(pub.pair("docs/a.md", "a" * 8 + "-" + "a" * 24))
    assert r["action"] == "paired" and r["title"] == "09. 모니터링" and r["parent_page_id"] == "kube"
    row = rows["docs/a.md"]
    assert row["notion_page_id"] == "a" * 32 and row["commit_sha"] is None and row["content_hash"] is None
    assert row["status"] == "published" and row["url"].endswith("a" * 32)
    assert pub.c.calls == []                                                 # Notion에는 쓰지 않는다
    with pytest.raises(nt.OutOfScope, match="이미 짝"):                     # 같은 경로 짝이 있으면 거부
        asyncio.run(pub.pair("docs/a.md", "a" * 32))


@pytest.mark.parametrize("path,pid,err", [
    ("docs/a.md", "b" * 32, nt.OutOfScope),          # 남의 프로젝트 페이지(root 밖)
    ("docs/a.md", "docs", nt.OutOfScope),            # 형식이 틀린 id
    ("docs/none.md", "a" * 32, FileNotFoundError),   # push한 판에 없는 문서
    ("log/x.md", "a" * 32, nt.OutOfScope),           # docs/ · portfolio/ 밖
])
def test_pair_refuses(tmp_path, path, pid, err):
    pub = _PairPub(_repo(tmp_path), {})
    with pytest.raises(err):
        asyncio.run(pub.pair(path, pid))


def test_pair_refuses_section_pages_and_page_already_paired(tmp_path):
    rows = {"docs/b.md": {"notion_page_id": "a" * 32, "status": "published"}}
    pub = _PairPub(_repo(tmp_path), rows)
    pub.docs_page = "a" * 31 + "f"
    with pytest.raises(nt.OutOfScope, match="이미 docs/b.md"):
        asyncio.run(pub.pair("docs/a.md", "a" * 32))
    with pytest.raises(nt.OutOfScope, match="자체는"):
        asyncio.run(pub.pair("docs/a.md", "a" * 31 + "f"))
