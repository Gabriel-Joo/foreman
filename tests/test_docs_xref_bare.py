"""「」 없는 편 사이 참조(11-19 관리자 410 일감, `bridge/doctext/titles.py` bare_xrefs, 문서 점검 5번). tmp 가짜 저장소로.

원고 기준(`docs/manuscript_rules.md`)은 편 사이 참조를 → 「제목」으로 쓰게 하는데, → 07 합치기, 「→ 포스트잇」처럼 쓴 줄은
점검도 노션 링크도 빠졌다. 기준 커밋(`[check] xref_base`) 뒤 더하거나 고친 줄만 틀림, 옛 줄은 의심으로 센다(main의 틀린 것 0을 지키며).
"""

import subprocess
from pathlib import Path

from bridge import docrefs
from bridge import mergeprep as mp
from bridge import scribe_room as sr
from bridge.doctext import check as ck
from bridge.doctext import config as dcfg
from bridge.doctext.titles import bare_xrefs, xref_index

IDX = xref_index({"notion/07.md": "07 합치기", "notion/07/01.md": "합치기 카드", "notion/04.md": "04 승인",
                  "notion/10/02.md": "포스트잇", "notion/14.md": "14 화면", "notion/14/02.md": "옆 패널"})


def found(line: str) -> list[tuple[str, bool]]:
    return [(t, inner) for _c, t, inner in bare_xrefs(line, IDX)]


def test_proper_xref_is_not_bare():
    assert found("자세한 것은 → 「07 합치기」에서 다룬다. →「합치기 카드」") == []


def test_bare_xref_is_caught():
    assert found("자세한 것은 → 07 합치기에서 다룬다.") == [("07 합치기", False)]
    assert found("카드는 → 합치기 카드, 붙이는 일은 → 포스트잇에서") == [("합치기 카드", False), ("포스트잇", False)]
    assert found("(→ 14 화면 아래 편들)") == [("14 화면", False)]                  # 번호 붙은 제목은 뒤를 보지 않는다
    assert found("| 끌기 손잡이 | → 옆 패널 |") == [("옆 패널", False)]            # 표 칸
    assert found("글로 남기는 칸이다 → 합치기 카드 [code:a.py].") == [("합치기 카드", False)]


def test_arrow_inside_brackets_is_caught():
    assert found("받는지는 「→ 포스트잇」이 다룬다.") == [("포스트잇", True)]


def test_screen_text_code_and_flow_are_not_caught():
    assert found('누르면 → "포스트잇에 올렸습니다"가 뜬다') == []                # 화면 글은 " "
    assert found("`a → 포스트잇` 명령") == []                                      # 백틱 안
    assert found("조립기 → 알림기 → 승인 → 와처") == []                           # 흐름: 「승인」 뒤가 조사가 아니다
    assert found("값 → 화면 이름 | 캐릭터") == []                                  # 「화면」으로 시작하는 다른 말
    assert found("→ 브리지가 뜬다") == []                                          # 제목이 아닌 말
    assert bare_xrefs("→ 07 합치기", ({}, {})) == []                               # 색인이 비면 판정하지 않는다


# ── 점검(run): 기준 커밋 뒤 새 줄은 틀림, 옛 줄은 의심 ──
def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


def commit(r: Path, msg: str = "c") -> str:
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", msg)
    return sh(r, "rev-parse", "HEAD")


def head(read: str) -> str:
    return f"<!--\n다루는 곳: bridge/a.py, .foreman/\n읽은 커밋: {read}\n-->\n"


def make(tmp_path: Path, base: bool = True) -> tuple[Path, str]:
    """원고 두 편. 01편에 옛 「」 없는 참조 두 곳(본문 하나, 화살표가 「」 안 하나)과 울타리 안 흐름 하나. 둘째 값은 기준 커밋."""
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, "bridge/a.py", "1\n")
    c0 = commit(r)
    put(r, "notion/01_a.md", head(c0[:7]) + "# 01 가\n\n옛 줄은 → 02 나에서 다룬다.\n\n받는 길은 「→ 02 나」가 다룬다.\n\n"
        "바른 꼴은 → 「02 나」다.\n\n```\n가 → 02 나\n```\n")
    put(r, "notion/02_b.md", head(c0[:7]) + "# 02 나\n\n나는 하나다.\n")
    c1 = commit(r, "원고")
    if base:
        put(r, ".foreman/docs.toml", f'[check]\ncover_by = []\nxref_base = "{c1}"\n')
        commit(r, "설정")
    return r, c1


def run(r: Path, rev=None):
    cfg = dcfg.load(r, rev)
    return ck.run(str(r), rev, cfg, docrefs.resolve_sets(r, cfg))


def test_old_lines_are_suspects_not_errors(tmp_path):
    r, c1 = make(tmp_path)
    res = run(r)
    assert res["errors"] == []
    xs = [s for s in res["suspects"] if s.get("xref")]
    assert [(s["line"], s["what"].split(":")[0]) for s in xs] == [(7, "→ 02 나"), (9, "「→ 02 나」")]   # 울타리 안은 안 본다
    assert res["xref_bare"] == {"base": c1, "new": 0, "old": 2, "ran": True}
    out = ck.render(res)
    assert "새 줄 0곳(틀림), 옛 줄 2곳(의심)" in out and "의심  notion/01_a.md" not in out    # 아무 편도 안 고쳤으면 -v 없이 줄은 안 보인다


def test_new_and_changed_lines_are_errors(tmp_path):
    r, _ = make(tmp_path)
    f = r / "notion/01_a.md"
    f.write_text(f.read_text(encoding="utf-8").replace("바른 꼴은", "새 줄은 → 02 나와 같다. 바른 꼴은"), encoding="utf-8")
    put(r, "notion/02_b.md", (r / "notion/02_b.md").read_text(encoding="utf-8") + "\n가는 → 01 가 편에 있다.\n")
    res = run(r)                                      # 작업 트리(커밋 전)
    assert sorted((e["doc"], e["line"]) for e in res["errors"]) == [("notion/01_a.md", 11), ("notion/02_b.md", 9)]
    assert all("편 사이 참조에 「」가 없습니다(→ 「" in e["what"] for e in res["errors"])
    assert res["xref_bare"]["new"] == 2 and res["xref_bare"]["old"] == 2
    # 고친 편(01)의 옛 줄은 -v 없이도 보여 그 편을 고쳐 쓰는 사람이 함께 맞춘다
    old = [s for s in res["suspects"] if s.get("xref")]
    assert all(s["touched"] for s in old)
    assert "의심  notion/01_a.md:7:" in ck.render(res)
    commit(r)
    assert len(run(r, "HEAD")["errors"]) == 2         # 커밋 판(--rev, 합치기 카드)도 같다


def test_moved_old_line_is_not_new(tmp_path):
    """옛 줄을 다른 편으로 옮기기만 하면(근거 표시만 덧붙여도) 새 줄이 아니다. 줄표 검사와 같은 옮긴 줄 풀이."""
    r, _ = make(tmp_path)
    f = r / "notion/01_a.md"
    f.write_text(f.read_text(encoding="utf-8").replace("옛 줄은 → 02 나에서 다룬다.\n\n", ""), encoding="utf-8")
    put(r, "notion/02_b.md", (r / "notion/02_b.md").read_text(encoding="utf-8") + "\n옛 줄은 → 02 나에서 다룬다. [code:bridge/a.py]\n")
    res = run(r)
    assert res["errors"] == [] and res["xref_bare"]["old"] == 2


def test_no_base_counts_all_as_suspects(tmp_path):
    r, _ = make(tmp_path, base=False)
    put(r, "notion/02_b.md", (r / "notion/02_b.md").read_text(encoding="utf-8") + "\n가는 → 01 가 편에 있다.\n")
    res = run(r)
    assert res["errors"] == [] and res["xref_bare"]["ran"] is False and res["xref_bare"]["old"] == 3
    assert any("xref_base" in n and "3곳" in n for n in res["notes"])


def test_bad_base_is_an_error_not_silence(tmp_path):
    r, _ = make(tmp_path)
    put(r, ".foreman/docs.toml", '[check]\ncover_by = []\nxref_base = "' + "0" * 40 + '"\n')
    res = run(r)
    assert any("「」 없는 편 사이 참조 검사를 돌리지 못했습니다" in e["what"] for e in res["errors"])


def test_config_xref_base_must_be_hash():
    assert dcfg.parse('[check]\nxref_base = "abc1234"\n').check.xref_base == "abc1234"
    try:
        dcfg.parse('[check]\nxref_base = "main"\n')
    except dcfg.DocsConfigError as e:
        assert "커밋 해시" in str(e)
    else:
        raise AssertionError("main을 받았습니다")


def test_merge_card_shows_new_bare_xref(tmp_path):
    """합치기 카드의 「이 브랜치로 새로 생긴 틀린 것」에 고친 줄의 「」 없는 참조가 나온다. 옛 줄은 나오지 않는다."""
    r, _ = make(tmp_path)
    sh(r, "checkout", "-q", "-b", "cc/w")
    put(r, "notion/02_b.md", (r / "notion/02_b.md").read_text(encoding="utf-8") + "\n가는 → 01 가 편에 있다.\n")
    commit(r)
    sh(r, "checkout", "-q", "main")
    c = mp.doc_check(str(r), "main", "cc/w")
    assert (c["new"], c["old"]) == (1, 0)
    assert "notion/02_b.md:9: → 01 가: 편 사이 참조에 「」가 없습니다" in c["lines"][0]


def test_scribe_prompt_lists_piece_bare_xrefs(tmp_path):
    """서기실이 편 하나를 띄울 때 지시문에 그 편의 「」 없는 참조(옛 줄 포함)가 줄 번호와 함께 들어간다."""
    r, _ = make(tmp_path)
    got = sr.piece_xrefs(str(r), "notion/01_a.md")
    assert got == "2곳: 7줄 → 02 나, 9줄 「→ 02 나」"
    assert sr.piece_xrefs(str(r), "notion/02_b.md") == ""
    p = sr.task_prompt("techdoc", "proj", str(r), {"slug": "01_a", "title": "01 가", "xrefs": got})
    assert "이 편에서 「」 없이 쓴 편 사이 참조 2곳: 7줄 → 02 나" in p
    assert "「」 없이 쓴" not in sr.task_prompt("techdoc", "proj", str(r), {"slug": "02_b", "title": "02 나", "xrefs": ""})
