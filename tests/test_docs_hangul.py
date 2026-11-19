"""한글 이름 파일(11-19 코더 일감, 관리자 410). git은 기본값으로 비아스키 파일 이름을 따옴표와 8진수로 내보낸다.
문서 도구가 그것을 줄 단위로 읽어 덮기 밖으로 세던 조용한 고장을 막았는지, 막은 뒤에도 따옴표 경로가 나오면 알리는지 본다.
"""

import subprocess
from pathlib import Path

import pytest

from bridge import docrefs
from bridge.doctext import check as ck
from bridge.doctext import config as dcfg
from bridge.doctext import dashdot
from bridge.doctext import repo as rp

KO = "data/review/답안_평가.md"          # records 폴더 안
KO_CSV = "data/표본_자료.csv"            # not_code 글롭에 드는 파일
KO_CODE = "bridge/한글모듈.py"           # 덮어야 하는 코드
KO_DOC = "docs/11_설계.md"


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


def commit(r: Path) -> str:
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", "c")
    return sh(r, "rev-parse", "HEAD")


def head(covers: str, read: str) -> str:
    return f"<!--\n다루는 곳: {covers}\n읽은 커밋: {read}\n-->\n"


@pytest.fixture
def ko(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    sh(r, "config", "core.quotepath", "true")              # 기본값 그대로. 이 값이어도 도구가 이름을 바르게 읽어야 한다
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, ".foreman/docs.toml", 'records = ["log/", "data/review/"]\nnot_code = [".md", "data/*.csv"]\n')
    put(r, KO_CODE, "x = 1\n")
    put(r, KO, "기록\n")
    put(r, KO_CSV, "a,b\n")
    put(r, KO_DOC, "# 11 설계\n\n본문\n")
    c0 = commit(r)
    put(r, "notion/01_a.md", head("bridge/, .foreman/", c0[:7]) + "# 01 가\n\n한글 이름 모듈을 다룬다 [code:" + KO_CODE + "].\n")
    commit(r)
    return r


def run(r: Path, rev=None):
    cfg = dcfg.load(r, rev)
    return ck.run(str(r), rev, cfg, docrefs.resolve_sets(r, cfg))


def test_git_prints_quoted_by_default(ko):
    """전제: 이 git은 한글 이름을 따옴표와 8진수로 내보낸다(그래서 고친 것이 의미가 있다)."""
    out = sh(ko, "ls-files")
    assert any(x.startswith('"') and "\\352" in x or "\\353" in x for x in out.splitlines())


def test_tree_gives_plain_hangul_names(ko):
    assert KO_CODE in rp.tree(ko, None) and KO in rp.tree(ko, None)
    assert KO_CODE in rp.tree(ko, "HEAD") and KO_CSV in rp.tree(ko, "HEAD", ["data/"])
    assert not any(rp.is_quoted(x) for x in rp.tree(ko, "HEAD"))


def test_cover_counts_hangul_names_right(ko):
    """records 폴더, not_code 글롭에 한글 이름 파일이 걸러지고, 한글 이름 코드는 덮기 대상에 바른 이름으로 든다."""
    for rev in (None, "HEAD"):
        res = run(ko, rev)
        assert res["errors"] == [], res["errors"]
        assert res["cover"]["target"] == 3 and res["cover"]["covered"] == 3     # KO_CODE, .foreman/notion.toml, .foreman/docs.toml
        assert res["marks"] == 1


def test_uncovered_hangul_is_reported_with_plain_name(ko):
    put(ko, "tools/덮이지_않음.py", "y\n")
    commit(ko)
    w = [e["what"] for e in run(ko)["errors"]]
    assert w == ["덮기 밖: tools/덮이지_않음.py가 notion 어느 편의 다루는 곳에도 들지 않습니다"]


def test_pieces_see_new_hangul_note(ko):
    """작업 트리의 아직 add하지 않은 새 편도 한글 이름으로 본다."""
    put(ko, "notion/02_한글편.md", head("bridge/", "HEAD") + "# 02 한글편\n\n본문\n")
    assert "notion/02_한글편.md" in ck.pieces_of(str(ko), None, "notion/", True, ["log/"])


def test_quoted_path_in_file_list_is_reported_not_counted(ko, monkeypatch):
    """git이 따옴표 경로를 내보내는 길이 생겨도, 덮기 밖으로 세지 않고 틀림 하나로 알린다."""
    real = rp.tree

    def fake(repo, rev, dirs=None):
        return [*real(repo, rev, dirs), '"data/review/answer_\\352\\261\\264.md"', '"x/\\353\\213\\265.py"']
    monkeypatch.setattr(ck, "tree", fake)
    monkeypatch.setattr(ck.GitView, "__init__", ck.GitView.__init__)
    res = run(ko, "HEAD")
    msgs = [e["what"] for e in res["errors"]]
    quoted = [m for m in msgs if "따옴표로 내보내" in m]
    assert len(quoted) == 1 and "answer_" in quoted[0] and "2개" in quoted[0]
    assert not any("덮기 밖" in m for m in msgs)


def test_refs_range_catches_hangul_code_change(ko):
    a = sh(ko, "rev-parse", "HEAD")
    put(ko, KO_CODE, "x = 2\n")
    put(ko, "bridge/새_한글.py", "z\n")
    put(ko, KO_DOC, "# 11 설계\n\n`" + KO_CODE + "`를 쓴다\n")
    commit(ko)
    res = docrefs.scan(ko, rng=f"{a}..HEAD")
    assert KO_CODE in res["code"] and "bridge/새_한글.py" in res["code"]
    d = {x["doc"]: x for x in res["docs"]}
    assert KO_DOC in d and d[KO_DOC]["fixed"] is True


def test_refs_changed_lines_hangul_header(ko):
    a = sh(ko, "rev-parse", "HEAD")
    put(ko, KO_CODE, "x = 2\n")
    commit(ko)
    assert docrefs.changed_lines(str(ko), a, "HEAD", [KO_CODE]) == {KO_CODE: [(1, 1)]}


def test_changed_lines_quoted_header_raises(monkeypatch):
    out = '--- "a/x/\\353\\213.py"\n+++ "b/x/\\353\\213.py"\n@@ -1 +1 @@\n'
    monkeypatch.setattr(docrefs, "_gits", lambda *a, **k: out)
    with pytest.raises(docrefs.DocrefsError, match="따옴표로 내보내 파일 이름을 읽지 못했습니다"):
        docrefs.changed_lines("/x", "a", "b", ["x"])


def test_dashdot_sees_hangul_new_file_and_diff(ko):
    base = sh(ko, "rev-parse", "HEAD")
    put(ko, "docs/12_한글.md", "# 12 한글\n\n가 — 나\n")
    put(ko, KO_DOC, "# 11 설계\n\n본문\n새 줄 · 가운뎃점\n")
    hs = dashdot.hunks(ko, base)                         # 작업 트리: 추적하지 않는 한글 이름 새 파일과 고친 한글 이름 파일
    assert ("docs/12_한글.md", None, range(0), range(1, 4)) in hs
    assert any(h[0] == KO_DOC for h in hs)
    hits = dashdot.scan(ko, base)
    assert {(p, name) for p, _, name, _ in hits} == {("docs/12_한글.md", "em dash"), (KO_DOC, "가운뎃점")}
    commit(ko)
    assert {p for p, *_ in dashdot.scan(ko, base, rev="HEAD")} == {"docs/12_한글.md", KO_DOC}


def test_dashdot_quoted_header_is_reported(ko, monkeypatch):
    monkeypatch.setattr(dashdot, "_git", lambda *a, **k: '--- /dev/null\n+++ "b/docs/\\355\\225\\234.md"\n@@ -0,0 +1 @@\n')
    with pytest.raises(dashdot.DashDotError, match="따옴표로 내보내 파일 이름을 읽지 못했습니다"):
        dashdot.hunks(ko, "HEAD", rev="HEAD")
    r = dashdot.for_repo(ko, "HEAD", {"docs": "docs/"}, ["log/"], "HEAD")
    assert "따옴표로 내보내" in r["error"]


def test_is_quoted():
    assert rp.is_quoted('"a/\\352\\261.md"') and rp.is_quoted('"a\\"b"')
    assert not rp.is_quoted("data/답.md") and not rp.is_quoted('"그냥 따옴표"')
