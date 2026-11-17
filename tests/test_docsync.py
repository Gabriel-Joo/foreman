"""기술문서 → Notion 맞추기(11-09) — 차례 · 범위 · 사람 수정 멈춤 · 다 맞춘 커밋 표시 · 다시 세우기 생략."""
import asyncio
import subprocess

from bridge import docsync as ds
from bridge import notion as nt
from test_notion import FakeNotion


def test_order_and_titles_from_readme_table():
    """차례는 표의 줄 순서만(본문에서 먼저 말한 이름은 보지 않는다 — 11-09 런슈즈), 제목은 "파일 이름 — 표 설명 앞부분"."""
    files = ["docs/zz.md", "docs/02_screens.md", "docs/README.md", "docs/overview.md", "docs/requirements.md"]
    readme = ("본문: `overview.md`(전체 구조) · `requirements.md`\n\n| 파일 | 다루는 것 |\n|---|---|\n"
              "| `requirements.md` | 무엇을 만드는가 — 문제 · 사용자 |\n| `overview.md` | **전체 구조** — 지도 |\n"
              "| `02_screens.md` | 화면 |\n| `없는파일.md` | … |\n| `08_compare.md` | 비교 페이지(설계안 — 결정 전) |\n")
    assert ds.titles(["docs/08_compare.md"], readme) == {"docs/08_compare.md": "08_compare — 비교 페이지(설계안 — 결정 전)"}
    assert ds.order(files, readme) == ["docs/README.md", "docs/requirements.md", "docs/overview.md", "docs/02_screens.md",
                                       "docs/zz.md"]
    assert ds.titles(files, readme) == {"docs/zz.md": "zz", "docs/02_screens.md": "02_screens — 화면", "docs/README.md": "README",
                                        "docs/overview.md": "overview — 전체 구조",
                                        "docs/requirements.md": "requirements — 무엇을 만드는가"}


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(repo)})


def test_docs_files_subfolders_and_skip_folders(tmp_path):
    """11-09 — 하위 폴더도 읽는다(펫퍼민트 docs/02_pipeline/). docs/archive/는 늘, skip의 "…/"는 폴더 통째로, 파일 이름은 그대로 뺀다."""
    for d in ("archive", "02_pipeline", "ops"):
        (tmp_path / "docs" / d).mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("목차\n")
    (tmp_path / "docs" / "02_pipeline.md").write_text("# 파이프라인\n")
    (tmp_path / "docs" / "02_pipeline" / "00_model.md").write_text("# 모델\n")
    (tmp_path / "docs" / "archive" / "old.md").write_text("# 옛\n")
    (tmp_path / "docs" / "ops" / "저녁실행.md").write_text("# 운영\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "docs")
    got = ds.docs_files(str(tmp_path), "HEAD", ["docs/README.md", "docs/ops/"])
    assert got == ["docs/02_pipeline.md", "docs/02_pipeline/00_model.md"]
    assert ds.last_docs_commit(str(tmp_path), "HEAD") is not None          # 하위 폴더 커밋도 docs 커밋으로 센다


def test_sync_never_archives_when_create_false(monkeypatch):
    """11-09 — create = false(사람이 옮겨 둔 페이지)는 원본이 사라져도 휴지통으로 보내지 않고 실패로 남긴다.
    경로만 바뀐 것(git mv)을 그냥 맞췄으면 펫퍼민트 20쪽이 모두 휴지통으로 갈 뻔했다."""
    _status(monkeypatch, deleted=["docs/00_model_setup.md"])
    pub = _Pub()
    pub.create = False
    r = asyncio.run(ds.sync(pub, "지금"))
    assert pub.calls == [] and r["failed"][0]["path"] == "docs/00_model_setup.md" and "휴지통" in r["failed"][0]["error"]
    p = nt.Publisher(None, FakeNotion(see_all=True), "root", "/repo", opts={"create": False})
    try:
        asyncio.run(p.archive("docs/x.md"))
        raise AssertionError("archive가 막히지 않았다")
    except nt.OutOfScope:
        pass


def test_docs_files_only_top_level_md_at_ref(tmp_path):
    """docs/archive/는 올리지 않는다(런슈즈 docs/README). ref에 커밋된 것만(작업 트리 아님)."""
    (tmp_path / "docs" / "archive").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("| `b.md` |\n| `a.md` |\n")
    (tmp_path / "docs" / "a.md").write_text("# A\n")
    (tmp_path / "docs" / "b.md").write_text("# B\n")
    (tmp_path / "docs" / "img.png").write_bytes(b"x")
    (tmp_path / "docs" / "archive" / "old.md").write_text("# 옛\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "docs")
    (tmp_path / "docs" / "c.md").write_text("# 커밋 안 함\n")
    assert ds.docs_files(str(tmp_path), "HEAD") == ["docs/README.md", "docs/b.md", "docs/a.md"]
    assert ds.commits_behind(str(tmp_path), None, "HEAD") is None


def _para(text, editor=None, t="paragraph"):
    b = {"object": "block", "type": t, t: {"rich_text": [{"type": "text", "text": {"content": text}}]}}
    if t == "code":
        b[t]["language"] = "mermaid"
    if editor:
        b["last_edited_by"] = {"object": "user", "id": editor}
    return b


def test_human_edits_only_people_and_differing_text():
    """사람이 고친(더한) 블록만 — 봇이 고친 것 · 원본과 글이 같은 것(이미 git에 옮김) · mermaid(미리보기만 바꿔도 사람)는 빼고."""
    f = FakeNotion(see_all=True)
    f.blocks["pg"] = [{**_para("원본 그대로", "bot"), "_id": "a"}, {**_para("사람이 고침", "human"), "_id": "b"},
                      {**_para("git에 옮긴 수정", "human"), "_id": "c"}, {**_para("graph TD", "human", "code"), "_id": "d"},
                      {**_para("사람이 더한 메모", "human"), "_id": "e"}]
    pub = nt.Publisher(None, f, "root", "/repo")
    pub._me_id = "bot"
    new = [_para("원본 그대로"), _para("원본 문장"), _para("git에 옮긴 수정"), _para("graph TD; 바뀜", t="code")]
    assert asyncio.run(pub.human_edits("pg", new)) == ["사람이 고침", "사람이 더한 메모"]
    pub._me_id = None                                      # 봇 id를 못 읽으면 검사하지 않는다(가짜 · 권한 없음)
    assert asyncio.run(pub.human_edits("pg", new)) == []


def _human_pub(blocks):
    f = FakeNotion(see_all=True)
    f.blocks["pg"] = [{**b, "_id": str(i)} for i, b in enumerate(blocks)]
    pub = nt.Publisher(None, f, "root", "/repo")
    pub._me_id = "bot"
    return pub, f


def test_human_edits_ignores_empty_blocks_only():
    """11-17 — 사람이 만든 빈 문단 · 공백만 있는 문단은 고침으로 세지 않는다. 글이 있는 블록이 바뀌었으면 섞여 있어도 멈춘다.
    그림 · 구분선처럼 글이 없는 게 본디인 블록은 지금처럼 센다."""
    new = [_para("원본")]
    pub, _ = _human_pub([_para("원본", "bot"), _para("", "human"), _para("   ", "human"), _para("", "human", "bulleted_list_item")])
    assert asyncio.run(pub.human_edits("pg", new)) == []                       # 빈 블록만
    pub, _ = _human_pub([_para("원본", "bot"), _para("사람이 고침", "human")])
    assert asyncio.run(pub.human_edits("pg", new)) == ["사람이 고침"]            # 글 블록 바뀜
    pub, _ = _human_pub([_para("원본", "bot"), _para("", "human"), _para("사람이 고침", "human"), _para(" \n", "human")])
    assert asyncio.run(pub.human_edits("pg", new)) == ["사람이 고침"]            # 섞임
    div = {"object": "block", "type": "divider", "divider": {}, "last_edited_by": {"id": "human"}}
    pub, _ = _human_pub([_para("원본", "bot"), div])
    assert asyncio.run(pub.human_edits("pg", new)) == ["(divider)"]            # 글 없는 블록 종류는 그대로


def test_trailing_empty_block_does_not_hold_and_is_removed_on_overwrite():
    """04_approval 꼴(11-17) — 페이지 맨 끝에 사람이 만든 빈 문단 하나: 멈추지 않고, 올릴 때 git 판에 맞춰 지워진다."""
    pub, f = _human_pub([_para("원본", "bot"), _para("", "human")])
    assert asyncio.run(pub.human_edits("pg", [_para("원본")])) == []
    asyncio.run(nt.sync_children(f, "pg", [_para("원본")]))
    assert [nt.plain(b["paragraph"]["rich_text"]) for b in f.blocks["pg"]] == ["원본"]


class _Pub:
    """sync가 부르는 것만 — publish · archive · _save. status는 시험마다 바꿔 끼운다."""

    def __init__(self, held=(), fail=()):
        self.project, self.docs_page, self.saved, self.calls = "runshoes", None, [], []
        self.held, self.fail = set(held), set(fail)

    async def publish(self, path, when, force=False, title=None, relink=True):
        self.calls.append((path, force))
        if path in self.held and not force:
            raise nt.HumanEdited(path, ["사람이 고침"], "https://notion/x")
        if path in self.fail:
            raise nt.NotionError(400, "거부")
        return {"action": "updated"}

    async def archive(self, path):
        self.calls.append((path, "archive"))
        return {"action": "archived"}

    async def _save(self, path, **kw):
        self.saved.append((path, kw))


def _status(monkeypatch, **kw):
    st = {"project": "runshoes", "files": [], "new": [], "changed": [], "deleted": [], "broken": [], "ref_sha": "f" * 40,
          "synced": None, "behind_commits": None, "last_commit_at": None, "mode": "auto", "ref": "origin/main", **kw}

    async def fake(pub):
        return st
    monkeypatch.setattr(ds, "status", fake)


def test_sync_holds_human_edits_and_does_not_move_mark(monkeypatch):
    """사람이 고친 페이지는 덮지 않고 멈춘다 — 다른 파일은 올리고, 다 맞춘 커밋 표시(@docs-sync)는 옮기지 않는다(뒤처짐이 남는다)."""
    _status(monkeypatch, new=["docs/a.md"], changed=["docs/b.md", "docs/c.md"], deleted=["docs/gone.md"])
    pub = _Pub(held={"docs/b.md"}, fail={"docs/c.md"})
    r = asyncio.run(ds.sync(pub, "지금"))
    assert [d["path"] for d in r["done"]] == ["docs/a.md", "docs/gone.md"]
    assert r["held"][0]["path"] == "docs/b.md" and r["held"][0]["count"] == 1
    assert r["failed"][0]["path"] == "docs/c.md"
    assert pub.saved == []
    # 덮기 — 그 파일만 force, 다 되면 표시를 ref 커밋으로 옮긴다
    _status(monkeypatch, changed=["docs/b.md"])
    pub = _Pub(held={"docs/b.md"})
    r = asyncio.run(ds.sync(pub, "지금", {"docs/b.md"}))
    assert pub.calls == [("docs/b.md", True)] and not r["held"]
    assert pub.saved == [(ds.MARK, {"kind": "mark", "title": "기술문서 맞춘 커밋", "commit_sha": "f" * 40,
                                    "status": "published", "error": None})]


def test_reorder_skips_when_order_already_right():
    """차례가 이미 맞으면 옮기지 않는다 — 자동 맞추기마다 페이지를 옮기지 않게."""
    f = FakeNotion(see_all=True)
    for pid in ("d1", "d2"):
        f.pages[pid] = {"parent": "root", "title": pid, "archived": False}
    pub = nt.Publisher(None, f, "root", "/repo")
    r = asyncio.run(pub.reorder([("docs/a.md", "d1"), ("docs/b.md", "d2")], "root"))
    assert r["action"] == "unchanged" and not [c for c in f.calls if c[0] == "move"]


def test_summary_counts_and_last_result(monkeypatch):
    """서기 화면 읽기(D2) — 게시됨 · 새 · 바뀜 · 지워짐 · 못 읽음 수와 push 대기 커밋, 마지막 맞추기 결과. 처음이면 behind_commits는 None."""
    _status(monkeypatch, files=["docs/a.md", "docs/b.md", "docs/c.md", "docs/d.md"], new=["docs/c.md"], changed=["docs/a.md"],
            deleted=["docs/x.md"], broken=[{"path": "docs/d.md", "error": "x"}], behind_commits=3, synced="abc")
    last = {"at": 123.0, "done": [{"path": "docs/a.md"}], "held": [], "failed": [{"path": "docs/b.md", "error": "거부됨"}]}
    r = asyncio.run(ds.summary(_Pub(), last))
    assert (r["total"], r["published"], r["new"], r["changed"], r["deleted"], r["broken"]) == (4, 2, 1, 1, 1, 1)
    assert r["behind_commits"] == 3 and r["last"]["failed"] == 1 and r["last"]["failed_first"] == "docs/b.md: 거부됨"
    _status(monkeypatch)
    assert asyncio.run(ds.summary(_Pub(), None))["last"] is None
