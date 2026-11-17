"""원고 쓰는 기준 한 벌(11-17 문서 도구 합치기 4단계, `docs/manuscript_rules.md`).

- 기준 문서가 읽히고, 서기 지시문 둘과 코더 규칙 절이 같은 줄을 받는다
- 기준 문서는 지시문 코드를 근거 표시로 가리켜 그 코드가 바뀌면 거꾸로 찾기에 걸린다
- em dash와 가운뎃점: 기준 커밋 뒤 새 줄(docs, 원고, 포트폴리오, 코드 주석)에 들어오면 깨진다(`bridge/doctext/dashdot.py`)
"""

import subprocess
from pathlib import Path

import pytest

from bridge import docrefs, manuscript_rules, scribe_room
from bridge.doctext import dashdot
from bridge.doctext.check import FsView, mark_problem
from bridge.doctext.marks import MARK

ROOT = Path(__file__).resolve().parent.parent
# 이 규칙이 들어오기 바로 전 main(11-17 648ac08). 이 커밋 뒤에 더한 줄만 본다. 바꾸지 않는다
BASE = "648ac08a0285c88626a2d5c16ae98732f47cb8a8"


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
                 "까닭을 모르면 모른다고 적는다", "같은 범위인지"):
        assert want in text, want


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
    assert "포트폴리오: " + manuscript_rules.lines("portfolio")[-4] in coder    # 코더는 종류 머리를 붙여 받는다
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
    assert dashdot.wanted("bridge/x.py") == "code" and dashdot.wanted("bridge/static/js/a.js") == "code"
    for no in ("log/x.md", "README.md", "CLAUDE.md", "docs/a.png", "bridge/static/index.html"):
        assert dashdot.wanted(no) is None, no


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


def test_new_lines_have_no_dash_or_dot():
    found = [f"{p}:{r} {n} | {s}" for p, r, n, s in dashdot.scan(ROOT, BASE)]
    assert not found, ("새 줄에 em dash나 가운뎃점이 있습니다(docs/manuscript_rules.md 「1.」 「6.」). "
                       "쉼표, 괄호, 새 문장으로 바꿉니다. 화면 글이나 절 제목 인용은 「」로 감쌉니다:\n" + "\n".join(found))
