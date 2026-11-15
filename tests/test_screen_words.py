"""화면 말 시험(11-15, tests/screen_words.py) — 바꾼 이름 · 문서 [버튼] · 호버 약속. 고치는 법은 docs/11_worktree.md 「8.」."""
import shutil
from pathlib import Path

import pytest

import screen_words as sw

ROOT = Path(__file__).resolve().parent.parent


# ── 이 저장소 ───────────────────────────────────────────────

def test_repo_screen_words():
    rep = sw.check_cached(str(ROOT))
    sw.LAST = rep
    assert not rep.fails and not rep.stale, "화면 말이 어긋났습니다.\n" + sw.explain(rep)


def test_data_shape():
    d = sw.load_data(ROOT)
    for r in d["rename"]:
        assert r["old"] and r["new"] and r["commit"], r
        assert r["scope"] in sw.SCOPES, f"[[rename]] {r['old']}: scope는 {sw.SCOPES} 중 하나입니다"
    for e in d.get("button_exception", []):
        assert e["kind"] in ("버튼이 아님", "계획 표", "이력 표") and e["why"], e
    for e in d.get("code_exception", []):
        assert e["near"] and e["why"], e
    for s in d.get("scribe", []):
        assert sw.scribe_owned(s["doc"]), f"[[scribe]]는 {sw.SCRIBE_DOCS}와 원고({sw.MANUSCRIPT_DIRS})만 적습니다: {s}"
    for p in d.get("promise", []):
        assert {"file", "tip", "acts", "test"} <= p.keys(), p
        assert not p["test"] or (ROOT / p["test"]).exists(), f"[[promise]] test 파일이 없습니다: {p['test']}"


# ── 시험의 시험: 작은 가짜 저장소 ───────────────────────────────

DATA = '''
[[rename]]
old = "옛단추"
new = "새단추"
scope = "화면과 문서 인용"
commit = "x"

[[rename]]
old = "문서말"
new = "화면말"
scope = "화면"
commit = "x"
'''


def _repo(tmp_path, *, js="", py="", docs=None, data=DATA, html=""):
    (tmp_path / "bridge/static/js").mkdir(parents=True)
    (tmp_path / "tests/data").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "bridge/static/js/a.js").write_text(js, encoding="utf-8")
    (tmp_path / "bridge/a.py").write_text(py, encoding="utf-8")
    (tmp_path / "bridge/static/a.html").write_text(html, encoding="utf-8")
    for name, body in (docs or {}).items():
        (tmp_path / "docs" / name).write_text(body, encoding="utf-8")
    (tmp_path / sw.DATA).write_text(data, encoding="utf-8")
    return tmp_path


def _kinds(rep):
    return sorted((h.kind, h.where) for h in rep.fails)


def test_old_name_in_screen_string_fails(tmp_path):
    r = sw.check(_repo(tmp_path, js="const a = '옛단추 누르기';\n"))
    assert _kinds(r) == [("rename-code", "bridge/static/js/a.js:1")]
    assert "[[code_exception]]" in sw.explain(r)


def test_comments_docstrings_logs_pass(tmp_path):
    js = "// 옛단추는 지웠다\n/* 옛단추 */\nconst re = /'옛단추\"/;\nconst ok = '새단추';\n"
    py = '"""옛단추 설명."""\nimport logging\nlog = logging.getLogger(__name__)\n\ndef f():\n    """옛단추"""\n    log.info("옛단추 %s", 1)  # 옛단추\n'
    html = "<!-- 옛단추 -->\n<style>/* 옛단추 */ b{}</style>\n<b>새단추</b>\n"
    assert sw.check(_repo(tmp_path, js=js, py=py, html=html)).fails == []


def test_python_refusal_and_template_inner_string_fail(tmp_path):
    py = 'class Refused(Exception):\n    pass\n\ndef f():\n    raise Refused("옛단추에서 고릅니다")\n'
    js = "const h = `<div>${b('x', '옛단추', true)}</div>`;\n"
    assert _kinds(sw.check(_repo(tmp_path, js=js, py=py))) == [
        ("rename-code", "bridge/a.py:5"), ("rename-code", "bridge/static/js/a.js:1")]


def test_code_exception_needs_near(tmp_path):
    data = DATA + '\n[[code_exception]]\nfile = "bridge/a.py"\nold = "옛단추"\nnear = "너는 세션이다"\nwhy = "프롬프트"\n'
    py = 'P = "너는 세션이다. 옛단추"\nQ = "옛단추를 누릅니다"\n'
    r = sw.check(_repo(tmp_path, py=py, data=data))
    assert _kinds(r) == [("rename-code", "bridge/a.py:2")] and not r.stale


def test_doc_quote_and_history_line(tmp_path):
    docs = {"a.md": "- [옛단추]를 누른다\n- 「옛단추」(11-14 바뀜)\n- 옛단추라는 말은 인용이 아니다\n- 「문서말」은 문서에서 쓴다\n"}
    r = sw.check(_repo(tmp_path, js="b('새단추')\n", docs=docs))
    assert ("rename-doc", "docs/a.md:1") in _kinds(r)
    assert not any(h.where in ("docs/a.md:2", "docs/a.md:3", "docs/a.md:4") for h in r.fails)


def test_doc_button_must_exist(tmp_path):
    js = "const h = `${b('more', '더보기 ▶')} <button>＋ 세션</button> 고른 ${n}개를 옮기기`;\n"
    docs = {"a.md": "[더보기 ▶] · [+ 세션] · [고른 N개를 옮기기] · [없는 단추] · [log:x.md] · [링크](x.md)\n"}
    r = sw.check(_repo(tmp_path, js=js, docs=docs))
    assert [(h.kind, h.text) for h in r.fails] == [("button", "없는 단추")]
    assert "[[button_exception]]" in sw.explain(r)


def test_button_exception_and_stale(tmp_path):
    data = DATA + ('\n[[button_exception]]\ndoc = "docs/a.md"\nquote = "계획만"\nkind = "계획 표"\nwhy = "x"\n'
                   '\n[[button_exception]]\ndoc = "docs/a.md"\nquote = "사라진 줄"\nkind = "계획 표"\nwhy = "x"\n')
    r = sw.check(_repo(tmp_path, docs={"a.md": "[계획만] 버튼\n"}, data=data))
    assert r.fails == [] and len(r.stale) == 1 and "사라진 줄" in r.stale[0]


def test_scribe_docs_pass_only_when_listed(tmp_path):
    docs = {"operations.md": "[옛단추]를 누른다\n"}
    r = sw.check(_repo(tmp_path, js="'새단추'", docs=docs))
    assert {h.kind for h in r.fails} == {"rename-doc", "button"}
    assert "[[scribe]]" in sw.explain(r)
    data = DATA + ('\n[[scribe]]\ndoc = "docs/operations.md"\ntext = "옛단추"\n'
                   '\n[[scribe]]\ndoc = "docs/operations.md"\ntext = "이미 맞춘 것"\n')
    shutil_rm(tmp_path)
    r = sw.check(_repo(tmp_path, js="'새단추'", docs=docs, data=data))
    assert r.fails == [] and len(r.scribe) == 2                       # 옛 이름 걸림 + [버튼] 걸림 둘 다 서기 몫
    assert len(r.stale) == 1 and "이미 맞춘 것" in r.stale[0]          # 서기가 맞춘 줄은 지우라고 한다
    assert "서기 몫 2줄" in sw.summary(r)


def test_promise_needs_list(tmp_path):
    js = ("const T = '손잡이 — 더블클릭하면 원래대로 돌아갑니다.';\n"
          "const h = `<div title=\"${x} — 감독실로 갑니다. Esc로도 갑니다.\"></div><i data-tip=\"닫기 — 창을 닫습니다.\"></i>`;\n"
          "const U = '저장 — 누르면 저장합니다.';\n")
    r = sw.check(_repo(tmp_path, js=js))
    assert sorted(h.detail for h in r.fails) == ["Esc", "더블클릭"]
    data = DATA + ('\n[[promise]]\nfile = "bridge/static/js/a.js"\ntip = "손잡이 — "\nacts = "더블클릭"\ntest = ""\n'
                   '\n[[promise_skip]]\nfile = "bridge/static/js/a.js"\ntip = "감독실로 갑니다. Esc"\nwhy = "x"\n'
                   '\n[[promise]]\nfile = "bridge/static/js/a.js"\ntip = "없어진 호버 — "\nacts = "끌기"\ntest = "t.mjs"\n')
    shutil_rm(tmp_path)
    r = sw.check(_repo(tmp_path, js=js, data=data))
    assert r.fails == [] and r.promises == 2 and r.untested == 1
    assert len(r.stale) == 1 and "없어진 호버" in r.stale[0]


def test_js_scan_regex_and_nested_template():
    src = "const r = /[`'\"]/g; // '주석'\nconst t = `a${f(`b${'c'}`)}d`; const x = 1 / 2; const y = '끝';\n"
    strs, kept = sw.js_scan(src)
    assert [s for _, s in strs] == ["a", "b", "c", "", "d", "끝"]
    assert "주석" not in kept


def shutil_rm(p: Path):
    """같은 tmp_path에 가짜 저장소를 다시 만들려고 비운다."""
    for c in p.iterdir():
        shutil.rmtree(c) if c.is_dir() else c.unlink()


@pytest.mark.parametrize("line", ["(전 이름 「옛단추」)", "~~[옛단추]~~", "「옛단추」 → 「새단추」", "전에는 「옛단추」였다"])
def test_history_marks(line):
    assert sw.HIST.search(line)
