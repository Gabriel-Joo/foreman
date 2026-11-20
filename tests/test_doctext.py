"""문서 문법 묶음(11-17 문서 도구 합치기 1단계, bridge/doctext). 문법 하나를 한 곳에서만 정하는지와, FOREMAN 꼴과
인프라 꼴(머리 주석이 맨 앞, 번호 없는 참조, [docs:history/…:줄-줄])을 둘 다 읽는지 본다."""

from pathlib import Path

import pytest

from bridge import doctext as dt
from bridge.doctext.lines import COMMENT, FENCED, TEXT, comments, walk

ROOT = Path(__file__).resolve().parent.parent


# ── 울타리와 주석 ───────────────────────────────────────────
def kinds(md):
    lines = md.splitlines()
    return [k for _, k in walk(lines)]


def test_walk_fence_and_comment():
    md = "a\n```py\n<!-- 안 -->\n# 셸\n```\nb\n<!--\n```\n-->\nc\n~~~\nx\n~~~\n"
    assert kinds(md) == [TEXT, FENCED, FENCED, FENCED, FENCED, TEXT, COMMENT, COMMENT, COMMENT, TEXT, FENCED, FENCED, FENCED]


def test_walk_closing_fence_needs_same_char_and_length():
    md = "````\n```\n~~~~\n````\nt\n"
    assert kinds(md) == [FENCED, FENCED, FENCED, FENCED, TEXT]


def test_comments_blocks_and_unclosed():
    lines = "<!-- 한 줄 -->\nt\n<!--\n둘\n-->\n<!-- 안 닫힘\n끝".split("\n")
    assert comments(lines) == [(0, 0, " 한 줄 "), (2, 4, "\n둘\n"), (5, 6, " 안 닫힘\n끝")]


def test_text_lines_numbers_from_one():
    assert list(dt.text_lines(["a", "```", "b", "```", "c"])) == [(1, "a"), (5, "c")]


# ── 근거 표시 ──────────────────────────────────────────────
def test_marks_all_kinds():
    ln = "글 [c:1a2b3c4] [t:12] [log:a_20261117.md] [docs:11_worktree.md:5-9] [code:bridge/x.py:3] [x:y] [code:a b]"
    got = [(k, v) for k, v, _ in dt.marks(ln)]
    assert got == [("c", "1a2b3c4"), ("t", "12"), ("log", "a_20261117.md"), ("docs", "11_worktree.md:5-9"), ("code", "bridge/x.py:3")]
    assert [m["v"] for m in dt.CODE_MARK.finditer(ln)] == ["bridge/x.py:3"]
    assert dt.KINDS == ("c", "t", "log", "docs", "code", "repo")


@pytest.mark.parametrize("v,want", [
    ("bridge/x.py", ("bridge/x.py", None, None)),
    ("bridge/x.py:10", ("bridge/x.py", 10, None)),
    ("bridge/x.py:10-20", ("bridge/x.py", 10, 20)),
    ("bridge/static/js/", ("bridge/static/js/", None, None)),
    ("history/cluster_state_20261116.md:193-197", ("history/cluster_state_20261116.md", 193, 197)),   # 인프라 꼴
    ("12_scribe.md:3#절", ("12_scribe.md", 3, None)),
    ("x.py:abc", None),
])
def test_target(v, want):
    assert dt.target(v) == want


def test_split_range_and_mark_file():
    assert dt.split_range("bridge/x.py:10-40") == ("bridge/x.py", (10, 40))
    assert dt.split_range("bridge/x.py:7") == ("bridge/x.py", (7, 7))
    assert dt.split_range("bridge/x.py") == ("bridge/x.py", None)
    assert dt.mark_file("history/a.md:193-197") == "history/a.md"
    assert dt.mark_file("12_scribe.md#절") == "12_scribe.md"


def test_strip():
    assert dt.STRIP.sub("", "문장이다 [c:abc1234] [code:a/b.py:1-2].") == "문장이다."
    assert dt.STRIP_TURN.sub("", "문장 [t:3] [c:abc1234]") == "문장 [c:abc1234]"


# ── 머리 주석 ──────────────────────────────────────────────
FOREMAN_PIECE = """# 03 세션 지켜보기

글 앞에 무엇이 있어도 된다.

<!--
다루는 곳: `bridge/a.py`, bridge/static/js/
다루는 곳: tests/test_*.py
읽은 커밋: `1a2b3c4`
-->

본문 [code:bridge/a.py:1-3]. → 「04 다음 편」
"""

INFRA_PIECE = """<!--
다루는 곳: platform/metallb/, cluster/Vagrantfile
읽은 커밋: 736d833
-->
# 02 노드

본문 [docs:history/cluster_state_20261116.md:193-197]. → 「역할 라벨」
"""


def test_parse_head_foreman_and_infra():
    assert dt.parse_head(FOREMAN_PIECE) == {"covers": ["bridge/a.py", "bridge/static/js/", "tests/test_*.py"], "read": "1a2b3c4", "line": 5}
    assert dt.parse_head(INFRA_PIECE) == {"covers": ["platform/metallb/", "cluster/Vagrantfile"], "read": "736d833", "line": 1}
    assert dt.parse_head("# 없음\n\n<!-- 다른 주석 -->\n") is None
    assert dt.parse_head("```\n<!--\n읽은 커밋: abc1234\n-->\n```\n") is None      # 울타리 안 주석은 머리 주석이 아니다


def test_head_text_round_trip_and_strip():
    h = dt.head_text(["bridge/x.py", "config/"], "abc1234")
    assert dt.parse_head(h + "\n# 제목\n") == {"covers": ["bridge/x.py", "config/"], "read": "abc1234", "line": 1}
    assert dt.strip_comments(INFRA_PIECE).startswith("# 02 노드")
    assert dt.bad_covers(["../x", "/etc/", ":(glob)x", "ok/"]) == ["../x", "/etc/", ":(glob)x"]


# ── 제목과 참조 ────────────────────────────────────────────
def test_first_h1():
    assert dt.first_h1(FOREMAN_PIECE) == (0, "03 세션 지켜보기")
    assert dt.first_h1(INFRA_PIECE) == (4, "02 노드")
    assert dt.first_h1("---\ntitle: x\n---\n```\n# 셸\n```\n# `코드` 제목 [t:3] ##\n") == (6, "코드 제목")


def test_xref_foreman_numbered_and_infra_bare():
    idx = dt.xref_index({"notion/03_a.md": "03 세션 지켜보기", "notion/04_b.md": "04 다음 편", "notion/05_c.md": "역할 라벨",
                         "notion/06_d.md": "06 겹침", "notion/07_e.md": "07 겹침"})
    assert dt.xref_lookup(idx, "04 다음 편") == ["notion/04_b.md"]          # FOREMAN: 번호째
    assert dt.xref_lookup(idx, "다음 편") == ["notion/04_b.md"]             # 인프라: 번호 없이
    assert dt.xref_lookup(idx, "`역할` 라벨") == ["notion/05_c.md"]
    assert dt.xref_lookup(idx, "겹침") == ["notion/06_d.md", "notion/07_e.md"]
    assert dt.xref_lookup(idx, "없는 편") == []
    assert [m["t"] for m in dt.XREF.finditer("→ 「가」, → 「`나`」, →「다」")] == ["가", "다"]


# ── 쓰는 곳이 모두 이 묶음을 쓴다 ─────────────────────────────
def test_users_share_one_definition():
    from bridge import docrefs, evidence, manuscript, notion
    from tests import screen_words
    assert evidence.MARK is dt.MARK and screen_words.MARK is dt.MARK
    assert docrefs.MARK is dt.REF_MARK and not hasattr(docrefs, "parse_head")   # 3단계: 거꾸로 찾기는 머리 주석을 읽지 않는다
    assert docrefs._tree is dt.tree and docrefs._read_many is dt.read_many and docrefs.DocrefsError is dt.RepoError   # 2단계
    from bridge.doctext import check
    assert evidence.SKIP_LINE is check.SKIP_LINE and evidence.mark_problem is check.mark_problem   # 3단계: 점검과 한 곳
    assert evidence.covers_problem is check.covers_problem and evidence.is_claim is check.is_claim
    assert manuscript.parse_head is dt.parse_head and manuscript.head_text is dt.head_text
    assert notion.first_h1 is dt.first_h1 and notion.xref_index is dt.xref_index


def test_no_grammar_copies_left():
    """근거 표시, 머리 주석 칸, 번호 뗀 제목, 참조 정규식을 다른 파일에 다시 쓰지 않는다(묶음 밖에서 찾으면 걸린다).
    울타리 꼴은 보지 않는다. bridge/notion.py md_to_blocks의 코드 블록 규칙은 Notion 블록 변환(언어 이름까지 읽는다)이라 따로다."""
    pats = [r"(?:c|t|log|docs|code):", r"c|log|docs|code|t", "다루는 곳|", r"\d{2}(?:-\d{2})?\s+", "→[ \\t]*)「", "→\\s*「"]
    hits = []
    for f in sorted((ROOT / "bridge").rglob("*.py")):
        if "doctext" in f.parts:
            continue
        txt = f.read_text(encoding="utf-8")
        hits += [f"{f.relative_to(ROOT)}: {p}" for p in pats if p in txt]
    assert hits == []
