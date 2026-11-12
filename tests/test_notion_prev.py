"""사람 수정 판정 — 지난번 올린 git 판(짝 commit_sha)과 같은 블록은 사람 수정이 아니다(11-12).

11-12 실제: 인프라 09를 force로 덮은 뒤(kept 21) 사람은 Notion을 고치지 않았는데, 다음 게시(28bc048)가 kept였던 문단 하나를
「사람이 고친 곳 1개」로 보고 멈췄다 — 맞추기는 글이 같은 블록을 손대지 않아 마지막 수정자가 처음 쓴 사람으로 남는다.
진짜 git 저장소(tmp) · 가짜 Notion · DB 없이(행은 dict).
"""
import asyncio
import subprocess

import pytest

from bridge import notion as nt
from test_notion import FakeNotion


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(repo)})
    return r.stdout.strip()


def _commit(repo, path, body, msg="c"):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "log", "-1", "--format=%h", "--", path)


V1 = "# 09. 모니터링\n\n첫 문단 그대로.\n\n대화 기록은 DB에 있다. Loki에는 서버 로그만 넣는다.\n\n셋째 문단.\n"
V2 = "# 09. 모니터링\n\n첫 문단 그대로.\n\n대화 기록은 DB에 있다. Loki에는 서버 로그만 넣는다. 확인해 보니 고쳤다.\n\n셋째 문단.\n"


class _Pub(nt.Publisher):
    def __init__(self, repo, rows, **kw):
        super().__init__(None, FakeNotion(see_all=True), "root", str(repo), project="ronanlab-infra", **kw)
        self.rows = rows
        self._me_id = "bot"
        self._limit = None
        self.c.pages["pg"] = {"parent": "root", "title": "09. 모니터링", "archived": False}

    async def _row(self, path):
        return self.rows.get(path)

    async def _save(self, path, **kw):
        self.rows.setdefault(path, {}).update(kw)

    async def parent_for(self, path):
        return "root"


def _notion_from(md, editor, path="docs/09.md"):
    """그 판의 글로 Notion 블록을 만든다 — 마지막으로 고친 쪽은 editor(사람이 옮겨 둔 페이지를 force로 덮어 kept로 남은 꼴)."""
    _, blocks = nt.md_to_blocks(md, nt.Ctx(path, "x"))
    return [{**b, "last_edited_by": {"object": "user", "id": editor}} for b in blocks]


def _setup(tmp_path, commit_sha="v1"):
    _git(tmp_path, "init", "-q", "-b", "main")
    v1 = _commit(tmp_path, "docs/09.md", V1)
    rows = {"docs/09.md": {"status": "published", "notion_page_id": "pg", "parent_page_id": "root", "title": "09. 모니터링",
                           "content_hash": "old", "url": "https://notion/pg",
                           "commit_sha": v1 if commit_sha == "v1" else commit_sha}}
    pub = _Pub(tmp_path, rows)
    for i, b in enumerate(_notion_from(V1, "human")):
        pub.c.blocks.setdefault("pg", []).append({**b, "_id": f"k{i}"})
    return pub, rows


def test_kept_block_left_by_human_is_not_flagged_when_only_git_changed(tmp_path):
    """11-12 꼴 — 사람 이름으로 남은 kept 블록, git만 그 문단을 고침 → 걸리지 않고 올라간다."""
    pub, rows = _setup(tmp_path)
    _commit(tmp_path, "docs/09.md", V2)
    prev = pub.prev_blocks("docs/09.md", rows["docs/09.md"])
    assert prev is not None
    assert asyncio.run(pub.human_edits("pg", nt.md_to_blocks(V2, nt.Ctx("docs/09.md", "y"))[1], prev)) == []
    r = asyncio.run(pub.publish("docs/09.md", "지금"))
    assert r["action"] == "updated"
    texts = [nt.plain((b.get(b["type"]) or {}).get("rich_text") or []) for b in pub.c.blocks["pg"]]
    assert any("확인해 보니 고쳤다" in t for t in texts)


def test_without_prev_the_old_rule_still_flags_it(tmp_path):
    """전과 비교 — prev 없이 보던 옛 판정은 같은 페이지에서 그 문단을 사람 수정으로 본다(고치기 전 동작)."""
    pub, _ = _setup(tmp_path)
    _commit(tmp_path, "docs/09.md", V2)
    new = nt.md_to_blocks(V2, nt.Ctx("docs/09.md", "y"))[1]
    got = asyncio.run(pub.human_edits("pg", new))
    assert len(got) == 1 and got[0].startswith("대화 기록은 DB에 있다")


def test_real_human_edit_is_still_flagged(tmp_path):
    """사람이 정말 고친 블록(지난 판과도 새 판과도 다름) → 걸린다. 지난 판 그대로인 나머지는 걸리지 않는다."""
    pub, _ = _setup(tmp_path)
    blk = next(b for b in pub.c.blocks["pg"] if "셋째 문단" in nt.plain(b.get("paragraph", {}).get("rich_text") or []))
    blk["paragraph"] = {"rich_text": [{"type": "text", "text": {"content": "셋째 문단 — 사람이 Notion에서 덧붙임"}}]}
    _commit(tmp_path, "docs/09.md", V2)
    with pytest.raises(nt.HumanEdited) as e:
        asyncio.run(pub.publish("docs/09.md", "지금"))
    assert e.value.edits == ["셋째 문단 — 사람이 Notion에서 덧붙임"]


def test_pair_without_commit_sha_keeps_old_conservative_rule(tmp_path):
    """처음 짝지은 페이지(commit_sha 비움 — 사람이 옮긴 페이지)는 지금처럼 새 판과 다른 사람 블록이 다 걸린다."""
    pub, rows = _setup(tmp_path, commit_sha=None)
    assert pub.prev_blocks("docs/09.md", rows["docs/09.md"]) is None
    _commit(tmp_path, "docs/09.md", V2)
    with pytest.raises(nt.HumanEdited) as e:
        asyncio.run(pub.publish("docs/09.md", "지금"))
    assert len(e.value.edits) == 1 and e.value.edits[0].startswith("대화 기록은 DB에 있다")


def test_unreadable_prev_commit_is_conservative(tmp_path):
    """그 커밋을 못 읽으면(없는 커밋 등) 지금처럼 보수적으로 — 걸린다."""
    pub, rows = _setup(tmp_path, commit_sha="deadbee")
    assert pub.prev_blocks("docs/09.md", rows["docs/09.md"]) is None
    _commit(tmp_path, "docs/09.md", V2)
    with pytest.raises(nt.HumanEdited):
        asyncio.run(pub.publish("docs/09.md", "지금"))


def test_prev_follows_rename(tmp_path):
    """지난번 올린 뒤 git mv 했으면 그때 경로로 읽는다(renamed_from)."""
    pub, rows = _setup(tmp_path)
    _git(tmp_path, "mv", "docs/09.md", "docs/09_monitoring.md")
    _git(tmp_path, "commit", "-q", "-m", "mv")
    _commit(tmp_path, "docs/09_monitoring.md", V2)
    rows["docs/09_monitoring.md"] = rows.pop("docs/09.md")
    assert pub.prev_blocks("docs/09_monitoring.md", rows["docs/09_monitoring.md"]) is not None
    r = asyncio.run(pub.publish("docs/09_monitoring.md", "지금"))
    assert r["action"] == "updated"


def test_force_does_not_read_prev(tmp_path, monkeypatch):
    """force면 지난 판을 읽을 까닭이 없다 — 판정을 건너뛴다(덮기 동작 그대로)."""
    pub, _ = _setup(tmp_path)
    _commit(tmp_path, "docs/09.md", V2)
    monkeypatch.setattr(pub, "prev_blocks", lambda *a: (_ for _ in ()).throw(AssertionError("읽음")))
    assert asyncio.run(pub.publish("docs/09.md", "지금", force=True))["action"] == "updated"
