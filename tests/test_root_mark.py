"""맨 위 문서 근거 표시 `[repo:경로]`와 문서를 가리키는 `[code:]` 잡기(11-20 관리자 410 일감, `bridge/doctext/marks.py`).

원고가 `[code:CLAUDE.md]`로 규칙 문서를 가리켰고, `[docs:CLAUDE.md]`로 바꾸자 점검이 `docs/CLAUDE.md`로 풀어 틀림이 났다.
맨 위 문서는 `[repo:]` 한 꼴로 쓰고, 표시를 경로로 푸는 곳(점검, 근거 확인기, 거꾸로 찾기, 노션 판)은 모두 `mark_target` 하나를 쓴다.
"""

import subprocess
from pathlib import Path

from bridge import docrefs
from bridge import notion as nt
from bridge.doctext import check as ck
from bridge.doctext import config as dcfg
from bridge.doctext.check import FsView
from bridge.doctext.marks import STRIP, code_doc, mark_path, mark_target


# ── 판정 함수 하나 ──
def test_mark_target_resolves_each_kind():
    assert mark_target("repo", "CLAUDE.md:7") == ("CLAUDE.md", 7, None)
    assert mark_target("repo", ".claude/agents/Explore.md") == (".claude/agents/Explore.md", None, None)
    assert mark_target("docs", "12_scribe.md:10-20#절") == ("docs/12_scribe.md", 10, 20)     # docs:X는 언제나 docs/X
    assert mark_target("docs", "x.md", docs_dir="manual/") == ("manual/x.md", None, None)
    assert mark_target("log", "a.md", log_dir="docs/history/") == ("docs/history/a.md", None, None)
    assert mark_target("code", "bridge/x.py:3") == ("bridge/x.py", 3, None)
    assert mark_target("c", "abc1234") is None and mark_target("t", "12") is None
    assert mark_path("docs", "CLAUDE.md") == "docs/CLAUDE.md"                                # 맨 위로 풀지 않는다


def test_code_doc():
    assert code_doc("code", "CLAUDE.md") and code_doc("code", "contract/README.md:72")
    assert not code_doc("code", "bridge/x.py") and not code_doc("code", "bridge/static/js/")
    assert not code_doc("repo", "CLAUDE.md") and not code_doc("docs", "x.md")


def test_strip_removes_repo_mark():
    assert STRIP.sub("", "규칙이다 [repo:CLAUDE.md:7] [code:a.py].") == "규칙이다."


# ── 점검 ──
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
    """원고 한 편. 옛 줄에 [code:CLAUDE.md] 하나. 둘째 값은 기준 커밋."""
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, "bridge/a.py", "1\n")
    put(r, "CLAUDE.md", "# 규칙\n\n둘째 줄\n")
    put(r, "docs/12_x.md", "# 12\n")
    c0 = commit(r)
    put(r, "notion/01_a.md", head(c0[:7]) + "# 01 가\n\n옛 줄은 규칙을 따른다 [code:CLAUDE.md].\n\n코드는 이것이다 [code:bridge/a.py].\n")
    c1 = commit(r, "원고")
    put(r, ".foreman/docs.toml", '[check]\ncover_by = []\n' + (f'code_doc_base = "{c1}"\n' if base else ""))
    commit(r, "설정")
    return r, c1


def run(r: Path, rev=None):
    cfg = dcfg.load(r, rev)
    return ck.run(str(r), rev, cfg, docrefs.resolve_sets(r, cfg))


def errs(res) -> list[str]:
    return [e["what"] for e in res["errors"]]


def test_repo_mark_resolves_top_level(tmp_path):
    r, _ = make(tmp_path)
    f = r / "notion/01_a.md"
    f.write_text(f.read_text(encoding="utf-8") + "\n새 줄은 [repo:CLAUDE.md:3]과 [docs:12_x.md]를 가리킨다.\n", encoding="utf-8")
    assert errs(run(r)) == []
    f.write_text(f.read_text(encoding="utf-8") + "\n없는 줄 [repo:CLAUDE.md:9], 맨 위로 풀지 않음 [docs:CLAUDE.md].\n", encoding="utf-8")
    got = errs(run(r))
    assert any(w.startswith("[repo:CLAUDE.md:9] 줄 범위가 맞지 않습니다") for w in got)
    assert any(w == "[docs:CLAUDE.md] docs/CLAUDE.md 파일이 없습니다" for w in got)          # docs:X는 언제나 docs/X


def test_repo_mark_one_form_only():
    v = FsView(Path("."))
    assert ck.mark_problem("repo", "bridge/doctext/marks.py", v) == "문서(.md)가 아닙니다. 코드는 [code:bridge/doctext/marks.py]로 씁니다"
    assert ck.mark_problem("repo", "docs/style_guide.md", v) == "docs/ 아래 파일은 [docs:style_guide.md]로 씁니다"
    assert ck.mark_problem("repo", "CLAUDE.md", v) is None


def test_old_code_doc_is_suspect_new_is_error(tmp_path):
    r, c1 = make(tmp_path)
    res = run(r)
    assert res["errors"] == []
    sus = [s for s in res["suspects"] if s.get("code_doc")]
    assert [s["line"] for s in sus] == [7] and "[repo:CLAUDE.md]로 씁니다" in sus[0]["what"]
    assert res["code_doc"] == {"base": c1, "new": 0, "old": 1, "ran": True}
    put(r, "notion/01_a.md", (r / "notion/01_a.md").read_text(encoding="utf-8") + "\n새 줄 [code:CLAUDE.md:3], 문서 [code:docs/12_x.md].\n")
    res = run(r)
    assert sorted(errs(res)) == ["[code:CLAUDE.md:3] 코드가 아닌 문서를 가리킵니다([repo:CLAUDE.md:3]로 씁니다)",
                                 "[code:docs/12_x.md] 코드가 아닌 문서를 가리킵니다([docs:12_x.md]로 씁니다)"]
    assert res["code_doc"]["new"] == 2 and "새 줄 2곳(틀림), 옛 줄 1곳(의심)" in ck.render(res)


def test_converted_line_is_not_new(tmp_path):
    """옛 줄의 [code:CLAUDE.md]를 [repo:]로 바꾸기만 한 줄은 줄표 검사에서도 새 줄이 아니다(표시를 떼고 맞댄다)."""
    r, _ = make(tmp_path)
    put(r, "notion/01_a.md", head("0000000") + "# 01 가\n\n옛 줄은 규칙을 따른다 · 가운뎃점 [code:CLAUDE.md].\n")
    c = commit(r, "가운뎃점 옛 줄")
    put(r, ".foreman/docs.toml", f'[check]\ncover_by = []\ncode_doc_base = "{c}"\ndashdot_base = "{c}"\n')
    commit(r, "설정")
    f = r / "notion/01_a.md"
    f.write_text(f.read_text(encoding="utf-8").replace("[code:CLAUDE.md]", "[repo:CLAUDE.md]"), encoding="utf-8")
    res = run(r)
    assert res["dashdot"]["hits"] == 0 and res["code_doc"]["old"] == 0


def test_no_base_counts_all_as_suspects(tmp_path):
    r, _ = make(tmp_path, base=False)
    res = run(r)
    assert res["errors"] == [] and res["code_doc"]["ran"] is False and res["code_doc"]["old"] == 1
    assert any("code_doc_base" in n and "1곳" in n for n in res["notes"])


def test_repo_kind_allowed_where_code_is(tmp_path):
    """다른 저장소는 kinds = ["c", "docs", "code"]로 적었다. 설정을 고치지 않아도 repo를 쓴다."""
    r, _ = make(tmp_path)
    put(r, ".foreman/docs.toml", '[check]\ncover_by = []\nkinds = ["c", "docs", "code"]\n')
    assert "repo" in dcfg.load(r).check.kinds
    put(r, ".foreman/docs.toml", '[check]\ncover_by = []\nkinds = ["c", "docs"]\n')
    assert "repo" not in dcfg.load(r).check.kinds


# ── 거꾸로 찾기와 노션 판 ──
def test_refs_find_piece_by_top_level_change(tmp_path):
    r, _ = make(tmp_path)
    put(r, "notion/02_b.md", head("0000000") + "# 02 나\n\n규칙을 따른다 [repo:CLAUDE.md:3].\n")
    c0 = commit(r, "02")
    put(r, "CLAUDE.md", "# 규칙\n\n둘째 줄 바꿈\n")
    c1 = commit(r, "규칙")
    res = docrefs.scan(r, rng=f"{c0}..{c1}")
    hit = {d["doc"]: d for d in res["docs"]}
    assert "notion/02_b.md" in hit and "notion/01_a.md" in hit       # 01은 옛 [code:CLAUDE.md]로도 아직 걸린다
    h = [x for x in hit["notion/02_b.md"]["hits"] if x["how"] == "mark"][0]
    assert h["code"] == "CLAUDE.md" and tuple(h["range"]) == (3, 3) and h["overlap"] is True
    assert [x["target"] for x in docrefs.refs_in("[repo:CLAUDE.md] [docs:a.md]")] == ["CLAUDE.md", "docs/a.md"]


def test_notion_strips_and_renders_repo_mark():
    _, blocks = nt.md_to_blocks("규칙이다 [repo:CLAUDE.md:7].\n", nt.Ctx(manuscript=True))
    assert nt.plain(blocks[0]["paragraph"]["rich_text"]) == "규칙이다."
    runs = nt.inline("규칙 [repo:CLAUDE.md:7] [docs:12_x.md] [code:bridge/a.py:3]", nt.Ctx(commit="abc"))
    got = [(t["text"]["content"], (t["text"].get("link") or {}).get("url", "")) for t in runs if (t.get("annotations") or {}).get("code")]
    assert [g[0] for g in got] == ["CLAUDE.md", "docs/12_x.md", "bridge/a.py"]
    assert got[0][1].endswith("/blob/abc/CLAUDE.md") and got[1][1].endswith("/blob/abc/docs/12_x.md")
