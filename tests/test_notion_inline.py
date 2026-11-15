"""Notion 변환기 줄 안 꾸밈(11-15) — 굵게 안 코드 · `*`, 근거 표시만 있는 줄, 표 칸 안 `|`, 이중 백틱. 순수 함수만."""
import re
import subprocess
from pathlib import Path

import pytest

from bridge import notion as nt

ROOT = Path(__file__).resolve().parent.parent
MANUSCRIPT_DOUBLE_TICK = {"notion/15_db/01_tables.md"}      # 이중 백틱 줄(11-15 첫 게시 확인 E) — 서기가 원고에서 고친다


def _runs(text, **kw):
    return [(t["text"]["content"], bool((t.get("annotations") or {}).get("bold")), bool((t.get("annotations") or {}).get("code")))
            for t in nt.inline(text, nt.Ctx(**kw))]


def test_bold_with_code_inside():
    assert _runs("**`/model`이 바꿨다.**") == [("/model", True, True), ("이 바꿨다.", True, False)]
    assert _runs("앞 **굵게 `x` 끝** 뒤") == [("앞 ", False, False), ("굵게 ", True, False), ("x", True, True), (" 끝", True, False), (" 뒤", False, False)]


def test_bold_with_single_star():
    assert _runs("**`config/*.toml` 값**") == [("config/*.toml", True, True), (" 값", True, False)]
    assert _runs("**config/*.toml 값**") == [("config/*.toml 값", True, False)]
    # 굵게 둘이 한 줄에 — 첫 `**`에서 닫는다
    assert _runs("**가** 와 **나**") == [("가", True, False), (" 와 ", False, False), ("나", True, False)]


def test_bold_link_and_evidence_inside():
    runs = nt.inline("**[글](https://x.test/a)**", nt.Ctx())
    assert runs[0]["annotations"]["bold"] and runs[0]["text"]["link"]["url"] == "https://x.test/a"


def test_no_raw_markers_left():
    for md in ("**`a` b**", "**x `*` y**", "**`a`**와 **`b`**"):
        txt = nt.plain(nt.inline(md, nt.Ctx()))
        assert "**" not in txt and "`" not in txt


def test_evidence_only_line_makes_no_paragraph():
    md = "# 제목\n\n본문\n\n[code:bridge/a.py] [docs:12_x.md]\n\n끝\n"
    _, blocks = nt.md_to_blocks(md, nt.Ctx(manuscript=True))
    assert [nt.plain(b["paragraph"]["rich_text"]) for b in blocks] == ["본문", "끝"]
    # 표 바로 뒤
    md = "| a | b |\n| --- | --- |\n| 1 | 2 |\n[code:x.py]\n"
    _, blocks = nt.md_to_blocks(md, nt.Ctx(manuscript=True))
    assert [b["type"] for b in blocks] == ["table"]


def test_evidence_with_text_is_kept():
    _, blocks = nt.md_to_blocks("뜻 [code:x.py]\n", nt.Ctx(manuscript=True))
    assert nt.plain(blocks[0]["paragraph"]["rich_text"]) == "뜻"


def test_table_cell_pipe_in_code():
    assert nt._cells("| `a || true` | b |") == ["`a || true`", "b"]
    assert nt._cells("| 가 | 나 \\| 다 |") == ["가", "나 | 다"]
    assert nt._cells("| `짝 없는 | x | y |") == ["`짝 없는", "x", "y"]       # 짝 없는 백틱은 뒤 칸을 삼키지 않는다
    md = "| 줄 | 뜻 |\n| --- | --- |\n| `a || true` | 계속 |\n"
    _, blocks = nt.md_to_blocks(md)
    assert blocks[0]["table"]["table_width"] == 2


def test_double_backtick():
    assert _runs("글 `` ` `` 끝") == [("글 ", False, False), ("`", False, True), (" 끝", False, False)]
    assert _runs("`` a`b ``") == [("a`b", False, True)]
    assert _runs("`평범` 하나") == [("평범", False, True), (" 하나", False, False)]


def _has_git(path):
    return subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", path], capture_output=True).returncode == 0


@pytest.mark.parametrize("folder,manuscript", [("notion", True), ("portfolio", True)])
def test_real_manuscripts_have_no_leftovers(folder, manuscript):
    """실제 원고 전체(노션 50편 · 포트폴리오 16편)를 바꿔서 빈 문단 · 날것 `**` · 굵게 안 날것 백틱이 없는지 본다."""
    files = sorted((ROOT / folder).rglob("*.md"))
    if not files:
        pytest.skip(f"{folder}/ 원고가 없습니다")
    bad = []
    for f in files:
        rel = str(f.relative_to(ROOT))
        ctx = nt.Ctx(path=rel, manuscript=manuscript, h1_title=True, links=False)
        _, blocks = nt.md_to_blocks(f.read_text(encoding="utf-8"), ctx)

        def walk(bs):
            for b in bs:
                t = b["type"]
                v = b.get(t) or {}
                if t == "table":
                    for r in v["children"]:
                        yield from ((rel, "cell", nt.plain(c)) for c in r["table_row"]["cells"])
                    continue
                if t == "code":
                    continue
                if "rich_text" in v:
                    yield rel, t, v["rich_text"]
                yield from walk(v.get("children", []))

        for rel_, t, rt in walk(blocks):
            if isinstance(rt, str):
                continue
            txt = nt.plain(rt)
            if t == "paragraph" and not txt.strip():
                bad.append((rel_, "빈 문단"))
            # 코드 구간 안의 `**`는 글자 그대로가 맞다(굵게 설명하는 글) — 코드 아닌 조각만 본다
            if any("**" in x["text"]["content"] for x in rt if not (x.get("annotations") or {}).get("code")):
                bad.append((rel_, f"날것 ** {txt[:40]}"))
            if any((x.get("annotations") or {}).get("bold") and "`" in x["text"]["content"] for x in rt):
                bad.append((rel_, f"굵게 안 백틱 {txt[:40]}"))
    # 굵은 글 안에 짝 없는 백틱 글자가 든 원고(백틱 하나를 글자로 쓴 줄, 이중 백틱 몫)는 원고가 고친다 — 그 편만 뺀다
    bad = [b for b in bad if not (b[0] in MANUSCRIPT_DOUBLE_TICK and b[1].startswith("굵게 안 백틱"))]
    assert not bad, bad
