"""원고 쓰는 기준 한 벌(11-17 문서 도구 합치기 4단계, `docs/manuscript_rules.md`).

- 기준 문서가 읽히고, 서기 지시문 둘과 코더 규칙 절이 같은 줄을 받는다
- 기준 문서는 지시문 코드를 근거 표시로 가리켜 그 코드가 바뀌면 거꾸로 찾기에 걸린다
- em dash와 가운뎃점: 기준 커밋 뒤 새 줄(docs, 원고, 포트폴리오, README.md, CLAUDE.md, 코드 주석)에 들어오면 깨진다
  (`bridge/doctext/dashdot.py`). 기준 커밋은 `.foreman/docs.toml` `[check] dashdot_base`에서 읽는다. 문서 점검 8번도 같은 검사다
"""

import subprocess
from pathlib import Path

import pytest

from bridge import docrefs, manuscript_rules, scribe_room
from bridge.doctext import check as dcheck
from bridge.doctext import config as dcfg
from bridge.doctext import dashdot
from bridge.doctext.check import FsView, mark_problem
from bridge.doctext.marks import MARK

ROOT = Path(__file__).resolve().parent.parent
# 이 규칙이 들어오기 바로 전 main(11-17 648ac08). 값은 저장소 설정 한 곳(.foreman/docs.toml)에만 둔다
BASE = dcfg.load(ROOT).check.dashdot_base


# ── 기준 문서 읽기 ─────────────────────────────
def test_doc_has_every_section_kinds_need():
    for kind in manuscript_rules.KINDS:
        got = manuscript_rules.lines(kind)
        assert got and all(x.strip() for x in got), kind
    secs = manuscript_rules.sections(manuscript_rules.PATH.read_text(encoding="utf-8"))
    assert {"1", "2", "3", "4", "5"} <= set(secs)
    assert all("[code:" not in x and "[log:" not in x for v in secs.values() for x in v)   # 근거 표시는 떼고 넣는다


def test_user_criteria_are_in_the_doc():
    """사용자가 늘 말하는 여덟 기준(11-17 관리자 표)이 1, 2, 5절에 있다."""
    text = " ".join(manuscript_rules.lines("portfolio") + manuscript_rules.lines("techdoc"))
    for want in ("비개발자도 읽는다", "어려운 말은 처음 나오는 자리에서 한 줄로 푼다", "용어 풀이", "같은 말투",
                 "em dash", "가운뎃점", "화면 축", "결정 중심", "치른 값", "하지 않은 것을 한 것처럼 쓰지 않는다",
                 "까닭을 모르면 모른다고 적는다", "같은 범위인지",
                 # 11-17 4단계 정할 것 답: 화면 글 가운뎃점, 인프라 기준 둘
                 "화면 글에는 가운뎃점을 쓸 수 있다", "감탄과 비유를 남발하지 않는다", "결정 중심으로 쓸 때는 막혔을 때 절을 둔다",
                 # 11-17 사용자 결정(인프라 관리자 전달): 목록 허용에 「치른 값」, 저장소 예외 없음
                 "「치른 값」(그 선택으로 잃거나 떠안은 것)에만 쓴다", "저장소마다 예외로 두지 않는다"):
        assert want in text, want


def test_limit_and_todo_rules_are_in_the_doc():
    """11-17 문서 정리 A단계: 한계는 안 하기로 한 것만 까닭과 함께, 할 일은 docs/TODO.md, 묶음마다 한계 편 하나."""
    secs = manuscript_rules.sections(manuscript_rules.PATH.read_text(encoding="utf-8"))
    for want in ("안 하기로 한 것만 쓴다", "까닭을 함께 적는다", "`docs/TODO.md`로 보낸다",
                 "한계 절에 적지 않는다", "조건인 한계", "안 하는 까닭 대신 그 조건을 적는다"):
        assert want in " ".join(secs["1"]), want
    sec2 = " ".join(secs["2"])
    for want in ("「알려진 한계」 편을 하나 둔다", "한 번만 적고", "가리키는 한 줄로 바꾼다",
                 "한 편에만 해당하는 한계는 그 편에 그대로 둔다"):
        assert want in sec2, want
    sec5 = " ".join(secs["5"])     # 포트폴리오 「치른 값」: 고르면서 치른 대가, 까닭이 정의에 들어 있음
    for want in ("치른 대가", "늘 통과한다", "대개 할 일", "넣지 않고 `docs/TODO.md`로 보낸다",
                 "모든 치른 값은 한계지만 모든 한계가 치른 값은 아니다", "층을 나눠 적어",
                 "그 결정에서 잃은 것", "저장소 전체에 걸리는 것", "되풀이되는 것만 한계 편으로 올라가"):
        assert want in sec5, want
    # 지시문 셋이 모두 받는다(서기 둘은 1, 2절 전체, 코더는 1, 2절 전체)
    for kind in ("techdoc", "portfolio", "coder"):
        text = " ".join(manuscript_rules.lines(kind))
        assert "안 하기로 한 것만 쓴다" in text and "「알려진 한계」 편을 하나 둔다" in text, kind
        assert "조건인 한계" in text, kind
    assert "치른 대가" in " ".join(manuscript_rules.lines("portfolio"))   # 포트폴리오 서기는 5절 전체
    assert "치른 대가" not in " ".join(manuscript_rules.lines("coder"))   # 코더는 5절 첫 줄만


def test_arrow_quote_rule_reaches_every_prompt():
    """11-17 사용자 결정: 화살표 뒤 「」는 편 사이 참조, 화면 글과 사람 말은 " ". 서기 둘과 코더가 모두 받는다."""
    for kind in ("techdoc", "portfolio", "coder"):
        text = " ".join(manuscript_rules.lines(kind))
        assert "뒤의 「」는 편 사이 참조다" in text, kind
        assert "화면 글이나 사람 말을 그대로 옮길 때는 \" \"를 쓴다" in text, kind


def test_broken_doc_raises_and_block_says_so(monkeypatch, tmp_path):
    bad = tmp_path / "rules.md"
    bad.write_text("# 제목\n\n## 1. 모든 문서\n\n글머리 없는 문단\n", encoding="utf-8")
    with pytest.raises(manuscript_rules.ManuscriptRulesError):
        manuscript_rules.lines("techdoc", bad.read_text(encoding="utf-8"))
    monkeypatch.setattr(manuscript_rules, "PATH", tmp_path / "없음.md")
    b = manuscript_rules.block("techdoc", True)
    assert "원고 쓰는 기준을 읽지 못했습니다" in b and "docs/manuscript_rules.md" in b


def test_nested_items_and_other_sections_are_not_taken():
    text = "## 1. 가\n- 하나\n  - 아래 단계\n- 둘\n## 9. 다른\n- 셋\n## 끝\n- 넷\n"
    assert manuscript_rules.sections(text) == {"1": ["하나", "둘"], "9": ["셋"]}


# ── 지시문이 같은 한 벌을 받는다 ─────────────────
def test_scribe_prompts_and_coder_block_share_lines(tmp_path):
    common = manuscript_rules.lines("techdoc")[0]
    tech = scribe_room.task_prompt("techdoc", "foreman", str(ROOT))
    port = scribe_room.task_prompt("portfolio", "foreman", str(ROOT))
    coder = docrefs.prompt_block(ROOT, "coder")
    for p in (tech, port, coder):
        assert common in p and "`docs/manuscript_rules.md`" in p
    for x in manuscript_rules.lines("techdoc"):
        assert x in tech
    for x in manuscript_rules.lines("portfolio"):
        assert x in port
    sec5 = manuscript_rules.sections(manuscript_rules.PATH.read_text(encoding="utf-8"))["5"]
    assert "포트폴리오: " + sec5[0] in coder    # 코더는 종류 머리를 붙여 5절 첫 줄만 받는다
    assert sec5[-1] not in coder
    # 옛 지시문의 따로 적힌 기준 줄은 없다(한 벌에서만 온다)
    for old in ("표, 명령어, 설정 값처럼 목록이나 표가 더 맞는 것만 예외다", "읽는 사람과 깊이(docs/12_scribe.md"):
        assert old not in tech and old not in port
    # 다른 저장소는 FOREMAN 쪽 절대 경로를 받는다
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    other = scribe_room.task_prompt("techdoc", "x", str(tmp_path))
    assert str(manuscript_rules.PATH) in other and common in other
    assert str(manuscript_rules.PATH) in docrefs.prompt_block(tmp_path, "coder")


# ── 문서 점검과 거꾸로 찾기의 대상 ─────────────────
def test_doc_marks_resolve():
    text = manuscript_rules.PATH.read_text(encoding="utf-8")
    marks = [(m.group("k"), m.group("v")) for m in MARK.finditer(text)]
    assert ("code", "bridge/manuscript_rules.py") in marks
    view = FsView(ROOT)
    bad = [(k, v, why) for k, v in marks if (why := mark_problem(k, v, view))]
    assert not bad, bad


@pytest.mark.parametrize("code", ["bridge/manuscript_rules.py", "bridge/scribe_room.py", "bridge/docrefs.py",
                                  "tests/test_manuscript_rules.py"])
def test_prompt_code_change_hits_rules_doc(code):
    res = docrefs.scan(ROOT, files=[code])
    assert manuscript_rules.REL in [d["doc"] for d in res["docs"]], code


# ── em dash와 가운뎃점 ───────────────────────────
def test_quoted_and_code_are_not_counted():
    assert dashdot.hits_in("그림 · 표") == ["가운뎃점"]
    assert dashdot.hits_in("가 — 나") == ["em dash"]
    for ok in ("「제목 — 설명」 꼴", "`split(' — ')`", "\"한도 — 구독\"", "em dash(—)와 가운뎃점(·)",
               "`docs/11_handoff_v2.md` 「쌓인 대화 비율 · 작업 전환 권유」"):
        assert dashdot.hits_in(ok) == [], ok


def test_code_parts_are_comments_only():
    py = 'X = "가 — 나"  # 주석 — 하나\n\n\ndef f():\n    """독스트링 · 둘"""\n    return "다 · 라"\n'
    got = dashdot.py_parts(py)
    assert set(got) == {1, 5} and "주석" in got[1] and "가 — 나" not in got[1]
    js = "const a = '가 — 나'; // 주석 — 하나\nconst r = /a\\/b/; /* 덩어리 · 둘 */\nconst t = `다 · ${a} // 아님`\n"
    got = dashdot.js_parts(js)
    assert set(got) == {1, 2} and "가 — 나" not in got[1]
    assert dashdot.hash_parts('k = "a # b"  # 주석 · 셋\n') == {1: "# 주석 · 셋"}
    md = "본문 · 하나\n```\n울타리 · 둘\n```\n<!--\n주석 · 셋\n-->\n"
    assert set(dashdot.doc_parts(md)) == {1}


def test_wanted_paths():
    assert dashdot.wanted("docs/x.md") == "doc" and dashdot.wanted("notion/a/b.md") == "doc"
    assert dashdot.wanted("README.md") == "doc" and dashdot.wanted("CLAUDE.md") == "doc"    # 11-17 사용자 결정 2
    assert dashdot.wanted("bridge/x.py") == "code" and dashdot.wanted("bridge/static/js/a.js") == "code"
    for no in ("log/x.md", "bridge/README.md", "docs/a.png", "bridge/static/index.html"):
        assert dashdot.wanted(no) is None, no
    # 다른 저장소: 기록 폴더가 docs 안에 있어도 기록이 먼저다(인프라 docs/history/)
    skip = ("docs/history/", *dashdot.TOOL_DIRS)
    assert dashdot.wanted("docs/history/a.md", ("docs/",), skip) is None
    assert dashdot.wanted("docs/01_a.md", ("docs/",), skip) == "doc" and dashdot.wanted("log/a.md", ("docs/",), skip) is None


def test_screen_strings_are_not_checked():
    """화면 글(js 문자열, html)의 가운뎃점은 1절대로 쓸 수 있고, 검사는 코드 문자열을 보지 않는다(11-17 사용자 결정 1)."""
    js = "btn.title = '보내기 · 멈추기';\nconst h = `<th>입력 · 출력</th>`;\n"
    assert dashdot.js_parts(js) == {}
    assert dashdot.wanted("bridge/static/index.html") is None


def test_only_grown_hunks_count(tmp_path):
    """옛 줄을 고치기만 하면(기호 수 그대로) 걸지 않고, 기호를 더한 덩어리와 새 파일은 건다."""
    g = ["git", "-C", str(tmp_path)]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("옛 줄 · 하나\n그대로\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"], check=True)
    base = subprocess.run([*g, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    (tmp_path / "docs/a.md").write_text("옛 줄 · 하나를 고침\n그대로\n새 줄 — 더함\n", encoding="utf-8")
    (tmp_path / "x.py").write_text("# 새 파일 · 주석\n", encoding="utf-8")
    hits = {(p, r, n) for p, r, n, _ in dashdot.scan(tmp_path, base)}
    assert hits == {("docs/a.md", 3, "em dash"), ("x.py", 1, "가운뎃점")}
    assert ("docs/a.md", 1, "가운뎃점") in {(p, r, n) for p, r, n, _ in dashdot.scan(tmp_path, base, strict=True)}


def test_base_must_be_ancestor(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"], check=True)
    with pytest.raises(dashdot.DashDotError):
        dashdot.hunks(tmp_path, BASE)


def _repo_with_base(tmp_path) -> tuple[list[str], str]:
    g = ["git", "-C", str(tmp_path)]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("옛 줄 · 하나\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# 제목\n\n옛 소개 — 그대로 둔다\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"], check=True)
    base = subprocess.run([*g, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return g, base


def test_readme_new_lines_only(tmp_path):
    """README와 CLAUDE.md는 기준 뒤 새 줄만 건다. 기존 줄의 기호는 그대로 둔다(11-17 사용자 결정 2)."""
    _, base = _repo_with_base(tmp_path)
    (tmp_path / "README.md").write_text("# 제목\n\n옛 소개 — 그대로 둔다\n새 소개 · 더함\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("- 새 규칙 — 하나\n", encoding="utf-8")
    hits = {(p, r, n) for p, r, n, _ in dashdot.scan(tmp_path, base)}
    assert hits == {("README.md", 4, "가운뎃점"), ("CLAUDE.md", 1, "em dash")}


def test_moved_file_with_new_file_in_old_place(tmp_path):
    """옮긴 뒤 옛 자리에 새 파일을 만들어도(11-17 README를 docs/00_design.md로 옮기고 README를 생성물로) 옮긴 파일의 옛 줄은
    새 줄이 아니다(-C로 복사를 알아본다). 옛 자리의 새 파일과 옮긴 파일에 더한 줄은 그대로 건다."""
    g, base = _repo_with_base(tmp_path)
    subprocess.run([*g, "mv", "README.md", "docs/00_design.md"], check=True)
    (tmp_path / "docs/00_design.md").write_text("# 제목\n\n옛 소개 — 그대로 둔다\n더한 줄 · 하나\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# 새 안내\n\n생성물 · 소개\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True)
    hits = {(p, r, n) for p, r, n, _ in dashdot.scan(tmp_path, base)}
    assert hits == {("docs/00_design.md", 4, "가운뎃점"), ("README.md", 3, "가운뎃점")}


def test_moved_file_cut_by_more_than_half(tmp_path):
    """옮긴 뒤 절반 넘게 줄여도(같은 날 설계 문서 943줄을 595줄로, 유사도 42%) 남은 옛 줄은 새 줄이 아니다(복사 문턱 40%)."""
    g = ["git", "-C", str(tmp_path)]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    old = [f"옛 줄 {i:02d} 그대로 두는 설계 문장입니다" + (" — 옛 기호" if i == 1 else "") for i in range(20)]
    (tmp_path / "README.md").write_text("\n".join(old) + "\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"], check=True)
    base = subprocess.run([*g, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    (tmp_path / "docs").mkdir()
    subprocess.run([*g, "mv", "README.md", "docs/00_design.md"], check=True)
    (tmp_path / "docs/00_design.md").write_text("\n".join(old[:9]) + "\n", encoding="utf-8")   # 20줄 가운데 9줄만 남김
    (tmp_path / "README.md").write_text("# 새 안내\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True)
    assert dashdot.scan(tmp_path, base) == []


def test_check_runs_dashdot_with_repo_base(tmp_path):
    """문서 점검 8번: 칸이 있으면 새 줄을 틀림으로 세고, 커밋 판(rev, 합치기 카드)도 그 판으로 본다."""
    g, base = _repo_with_base(tmp_path)
    (tmp_path / ".foreman").mkdir()
    (tmp_path / ".foreman/docs.toml").write_text(f'[check]\nsets = []\ncover_by = []\ndashdot_base = "{base}"\n',
                                                encoding="utf-8")
    (tmp_path / "docs/a.md").write_text("옛 줄 · 하나\n새 줄 — 더함\n", encoding="utf-8")
    cfg = dcfg.load(tmp_path)
    assert cfg.check.dashdot_base == base
    res = dcheck.run(str(tmp_path), None, cfg, docrefs.resolve_sets(str(tmp_path), cfg))
    assert [(e["doc"], e["line"]) for e in res["errors"]] == [("docs/a.md", 2)] and "em dash" in res["errors"][0]["what"]
    assert res["notes"] == [] and res["dashdot"] == {"base": base, "hits": 1, "ran": True}
    assert "줄표, 가운뎃점 검사: 기준 커밋" in dcheck.render(res)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b"], check=True)
    (tmp_path / "docs/a.md").write_text("옛 줄 · 하나\n", encoding="utf-8")        # 작업 트리에서 지워도 커밋 판에는 있다
    assert [e["line"] for e in dcheck.run(str(tmp_path), "HEAD", cfg, {"docs": "docs/"})["errors"]] == [2]
    assert dcheck.run(str(tmp_path), None, cfg, {"docs": "docs/"})["errors"] == []


def test_check_without_base_says_so(tmp_path):
    """칸이 없는 저장소는 검사하지 않고 알린다. 모든 줄을 조용히 걸지도, 조용히 넘어가지도 않는다."""
    _repo_with_base(tmp_path)
    (tmp_path / "docs/a.md").write_text("새 줄 — 더함\n", encoding="utf-8")
    cfg = dcfg.DocsConfig()
    cfg.check.sets, cfg.check.cover_by = [], []
    res = dcheck.run(str(tmp_path), None, cfg, {"docs": "docs/"})
    assert res["errors"] == [] and res["notes"] == [dashdot.NO_BASE] and not res["dashdot"]["ran"]
    assert "알림  기준 커밋이 없어 줄표, 가운뎃점 검사를 하지 않았습니다" in dcheck.render(res)
    # 조상이 아닌 기준 커밋은 틀림 하나(0건으로 보이지 않게)
    cfg.check.dashdot_base = "0" * 40
    res = dcheck.run(str(tmp_path), None, cfg, {"docs": "docs/"})
    assert len(res["errors"]) == 1 and "돌리지 못했습니다" in res["errors"][0]["what"]
    assert "줄표, 가운뎃점 검사:" not in dcheck.render(res)


@pytest.mark.parametrize("bad", ['"abc"', '"648AC08"', "7", '"648ac08 "'])
def test_dashdot_base_must_be_commit_hash(bad):
    with pytest.raises(dcfg.DocsConfigError):
        dcfg.parse(f"[check]\ndashdot_base = {bad}\n")


def test_new_lines_have_no_dash_or_dot():
    assert BASE, ".foreman/docs.toml [check] dashdot_base가 없습니다"
    found = [f"{p}:{r} {n} | {s}" for p, r, n, s in dashdot.scan(ROOT, BASE)]
    assert not found, ("새 줄에 em dash나 가운뎃점이 있습니다(docs/manuscript_rules.md 「1.」 「6.」). "
                       "쉼표, 괄호, 새 문장으로 바꿉니다. 화면 글이나 절 제목 인용은 「」로 감쌉니다:\n" + "\n".join(found))
