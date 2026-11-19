"""foreman-136(11-19). 맨 아래 갱신 줄에서 줄표와 가운뎃점을 뺐다. 이미 노션에 올라간 옛 꼴 줄도 갱신 줄로 알아봐야
쪽이 「사람이 고침」으로 멈추지 않는다. 가짜 노션으로만 본다(실제 노션에 쓰지 않는다)."""
import asyncio
import hashlib

import pytest

from bridge import notion as nt
from tests.test_notion import FakeNotion

OLD = "마지막 갱신 — c10a0ab · 2026-11-19 13:34 KST · 읽은 커밋 f8cea0d"
NEW = "마지막 갱신 c10a0ab(2026-11-19 13:34 KST), 읽은 커밋 f8cea0d"
WHEN = "2026-11-20 09:00 KST"


def _para(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": nt._rt(text)}}


def test_footer_block_new_form_has_no_dash_or_middle_dot():
    b = nt.footer_block("docs/a.md", "c10a0ab", nt.Ctx("docs/a.md", links=False), "2026-11-19 13:34 KST", "f8cea0d")
    text = nt.plain(b["paragraph"]["rich_text"])
    assert text == NEW
    assert "—" not in text and "·" not in text
    b2 = nt.footer_block("docs/a.md", "c10a0ab", nt.Ctx("docs/a.md", links=False), "")      # 시각, 읽은 커밋 없음
    assert nt.plain(b2["paragraph"]["rich_text"]) == "마지막 갱신 c10a0ab"


@pytest.mark.parametrize("text", [
    NEW,                                                         # (2) 새 꼴
    "마지막 갱신 c10a0ab(2026-11-19 13:34 KST)",
    "마지막 갱신 c10a0ab",
    "마지막 갱신 HEAD(2026-11-19 13:34 KST)",
    OLD,                                                         # 옛 꼴
    "마지막 갱신 — c10a0ab · 2026-11-19 13:34 KST",
    "마지막 갱신 — c10a0ab · ",                                  # 옛 꼴, 시각이 비었을 때
    "마지막 갱신 — c10a0ab ·  · 읽은 커밋 f8cea0d",
])
def test_both_forms_are_footer(text):
    assert nt.is_footer_text(text)


@pytest.mark.parametrize("text", [
    "마지막 갱신은 매주 월요일에 한다",                          # (3) 본문 문단이 우연히 「마지막 갱신」으로 시작
    "마지막 갱신 날짜는 표에 적는다",
    "마지막 갱신 c10a0ab 뒤로 바뀐 것은 없다",
    "마지막 갱신 — 11월에 했다",                                  # 옛 첫머리로 시작하는 본문(전에는 첫머리만 보아 빠졌다)
    "마지막 갱신 — c10a0ab · 시각 · 읽은 커밋 f8cea0d 뒤에 덧붙인 말",
    "",
])
def test_body_paragraph_is_not_footer(text):
    assert not nt.is_footer_text(text)


def test_shape_text_keeps_body_paragraph_and_drops_both_footers():
    flat = [("paragraph", "마지막 갱신은 매주 월요일에 한다"), ("paragraph", OLD)]
    assert nt.shape_text(flat, set()) == nt.compact("마지막 갱신은 매주 월요일에 한다")
    assert nt.shape_text([("paragraph", "본문"), ("paragraph", NEW)], set()) == "본문"


class _Pub(nt.Publisher):
    """DB 없이. 행은 dict로, git은 판(sha)마다 파일 맵으로."""
    def __init__(self, rows, **kw):
        super().__init__(None, FakeNotion(), "root", ".", project="x", **kw)
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


GIT: dict[str, str] = {}          # sha → 본문(경로 하나만 쓴다)


@pytest.fixture
def shape_pub(monkeypatch):
    GIT.clear()
    monkeypatch.setattr(nt, "git_show", lambda repo, path, ref="HEAD": (GIT[ref], ref if ref != "HEAD" else "bbbbbbb"))
    monkeypatch.setattr(nt, "renamed_from", lambda repo, old, new, path: path)
    monkeypatch.setattr(nt, "content_digest", lambda repo, path, body, ref="HEAD": hashlib.sha256(body.encode()).hexdigest())
    rows: dict = {}
    pub = _Pub(rows, opts={"header": "footer", "keep_notion": ["inline_code", "image", "heading", "shape"], "title": "h1"})
    return pub, rows


def _seed(pub, rows, body: str, footer_text: str, content_hash: str = "옛 지문"):
    """노션에 지난 판(aaaaaaa) 글과 갱신 줄 하나가 올라가 있는 쪽을 만든다."""
    GIT["aaaaaaa"] = body
    p = asyncio.run(pub.c.create_page("root", "글", []))
    _, blocks = nt.md_to_blocks(body, pub._ctx("docs/a.md", "aaaaaaa"))
    asyncio.run(nt.append_tree(pub.c, p["id"], [*blocks, _para(footer_text)]))
    rows["docs/a.md"] = {"status": "published", "notion_page_id": p["id"], "parent_page_id": "root", "title": "글",
                           "commit_sha": "aaaaaaa", "content_hash": content_hash, "url": p["url"]}
    return p["id"]


def _texts(pub, pid):
    return [nt.plain((b.get(b["type"]) or {}).get("rich_text") or []) for b in pub.c.blocks[pid]]


def test_old_footer_page_updates_without_human_edit_when_git_changed(shape_pub):
    """(1) 옛 꼴 갱신 줄이 있는 쪽, git 글이 바뀜. 그래도 「사람이 고침」으로 멈추지 않고 바뀐 블록만 고치고 갱신 줄은 새 꼴로."""
    pub, rows = shape_pub
    pid = _seed(pub, rows, "# 글\n\n첫 문단\n\n둘째 문단\n", OLD)
    GIT["HEAD"] = "# 글\n\n첫 문단 고침\n\n둘째 문단\n"
    r = asyncio.run(pub.publish("docs/a.md", when=WHEN))
    assert r["action"] == "updated"
    texts = _texts(pub, pid)
    assert texts[-1] == f"마지막 갱신 bbbbbbb({WHEN})"
    assert sum(nt.is_footer_text(t) for t in texts) == 1 and OLD not in texts      # 옛 줄은 바뀌었고 두 줄이 되지 않았다
    assert "첫 문단 고침" in texts and r["sync"]["updated"] >= 2


def test_old_footer_page_same_text_only_footer_changes(shape_pub):
    """(1) 글은 같고 지문만 다름(예: 사진). 이때는 갱신 줄만 새 꼴로 고친다."""
    pub, rows = shape_pub
    body = "# 글\n\n첫 문단\n"
    pid = _seed(pub, rows, body, OLD)
    GIT["HEAD"] = body
    ids = [b["_id"] for b in pub.c.blocks[pid]]
    r = asyncio.run(pub.publish("docs/a.md", when=WHEN))
    assert r["action"] == "footer"
    assert [b["_id"] for b in pub.c.blocks[pid]] == ids                              # 같은 블록을 고쳤다(새로 붙이지 않음)
    assert _texts(pub, pid)[-1] == f"마지막 갱신 bbbbbbb({WHEN})"


def test_new_footer_is_recognised_on_next_publish(shape_pub):
    """(2) 새 꼴로 바뀐 뒤 다시 맞춰도 갱신 줄을 알아본다. 멈추지 않고 한 줄로 남는다."""
    pub, rows = shape_pub
    body = "# 글\n\n첫 문단\n"
    pid = _seed(pub, rows, body, NEW)
    GIT["HEAD"] = "# 글\n\n첫 문단\n\n새 문단\n"
    r = asyncio.run(pub.publish("docs/a.md", when=WHEN))
    assert r["action"] == "updated"
    assert sum(nt.is_footer_text(t) for t in _texts(pub, pid)) == 1


def test_body_paragraph_like_footer_is_compared_as_body(shape_pub):
    """(3) 본문 맨 끝 문단이 「마지막 갱신」으로 시작해도 갱신 줄로 보지 않는다. 고치지 않고 그 뒤에 갱신 줄을 붙인다."""
    pub, rows = shape_pub
    body = "# 글\n\n마지막 갱신은 매주 월요일에 한다\n"
    pid = _seed(pub, rows, body, OLD)
    asyncio.run(pub.c.delete_block(pub.c.blocks[pid][-1]["_id"]))                   # 갱신 줄 없이 본문만 있는 쪽
    GIT["HEAD"] = body
    r = asyncio.run(pub.publish("docs/a.md", when=WHEN))
    assert r["action"] == "footer"
    assert _texts(pub, pid)[-2:] == ["마지막 갱신은 매주 월요일에 한다", f"마지막 갱신 bbbbbbb({WHEN})"]


def test_digest_does_not_depend_on_footer_form(shape_pub, tmp_path):
    """(4) 지문은 git 본문(과 사진)만 본다. 갱신 줄 꼴을 바꿔도 지문이 같은 쪽은 「바뀌지 않음」이라 다시 올라가지 않는다.
    그래서 옛 꼴 줄은 그 편 글이 다음에 바뀔 때 새 꼴로 바뀐다(그때까지 노션에 옛 꼴이 남는다)."""
    pub, rows = shape_pub
    body = "# 글\n\n첫 문단\n"
    pid = _seed(pub, rows, body, OLD, content_hash=hashlib.sha256(body.encode()).hexdigest())
    GIT["HEAD"] = body
    n = len(pub.c.calls)
    r = asyncio.run(pub.publish("docs/a.md", when=WHEN))
    assert r["action"] == "unchanged" and len(pub.c.calls) == n and _texts(pub, pid)[-1] == OLD


def test_real_content_digest_is_body_only(tmp_path):
    body = "# 글\n\n첫 문단\n"
    assert nt.content_digest(str(tmp_path), "docs/a.md", body) == hashlib.sha256(body.encode()).hexdigest()
