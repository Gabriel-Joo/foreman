"""거꾸로 찾기(11-17 사용자 지시 21, bridge/docrefs.py, tools/docrefs.py). tmp 가짜 저장소로. 읽기만 하는지도 본다."""

import json
import subprocess
from pathlib import Path

import pytest

from bridge import docrefs as dr

ROOT = Path(__file__).resolve().parent.parent


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


DOC = """# 11 설계

## 1. 합치기

- 카드는 `bridge/mergeprep.py`가 만든다
  이어지는 줄
- 화면은 `handoff.js` 하나다
- 이름만 같은 `x.py`는 두 곳이라 걸지 않는다
- 맨글 경로 bridge/transcript/reader.py 도 본다
- 맨 위 폴더 `bridge/`와 글롭 `tests/*`는 너무 넓어 걸지 않는다

```
`bridge/mergeprep.py` 울타리 안은 보지 않는다
```

## 2. 다른 것

문단 첫 줄
`bridge/transcript` 폴더를 말한다
문단 끝 줄
"""

NOTION = """<!--
다루는 곳: bridge/mergeprep.py, bridge/static/js/
읽은 커밋: abc1234
-->
# 07 합치기

## 카드

카드는 브리지가 만든다 [code:bridge/transcript/]. 자세한 판정은 [code:bridge/mergeprep.py:3-4].
"""

PORTFOLIO = """<!--
다루는 곳: bridge/*.py
읽은 커밋: abc1234
-->
# 합치기 화면

화면을 보입니다.
"""


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t"); sh(r, "config", "user.name", "t")
    put(r, "bridge/mergeprep.py", "".join(f"line{i}\n" for i in range(1, 21)))
    put(r, "bridge/static/js/handoff.js", "x\n")
    put(r, "bridge/x.py", "x\n"); put(r, "tools/x.py", "x\n")
    put(r, "bridge/transcript/reader.py", "x\n")
    put(r, "docs/11_x.md", DOC)
    put(r, "notion/07_merge.md", NOTION)
    put(r, "portfolio/07_merge.md", PORTFOLIO)
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    sh(r, "add", "."); sh(r, "commit", "-qm", "init")
    return r


def by_doc(res):
    return {d["doc"]: d for d in res["docs"]}


def test_refs_in_kinds():
    refs = dr.refs_in(DOC)
    got = {(r["target"], r["how"]) for r in refs}
    assert ("bridge/mergeprep.py", "path") in got and ("handoff.js", "name") in got and ("x.py", "name") in got
    assert ("bridge/transcript/reader.py", "path") in got and ("bridge/transcript", "path") in got
    assert not any(t in ("bridge/", "tests/*") for t, _ in got)           # 맨 위 폴더, 넓은 글롭은 백틱이어도 걸지 않는다
    assert all(r["line"] != 13 for r in refs)                             # 울타리 안
    n = dr.refs_in(NOTION)
    assert {(r["target"], r["how"], r["line"]) for r in n if r["how"] == "covers"} == {
        ("bridge/mergeprep.py", "covers", 1), ("bridge/static/js/", "covers", 1)}
    assert {(r["target"], tuple(r["range"]) if r["range"] else None) for r in n if r["how"] == "mark"} == {
        ("bridge/transcript/", None), ("bridge/mergeprep.py", (3, 4))}


def test_files_mode_finds_docs_notion_portfolio(repo):
    res = dr.scan(repo, files=["bridge/mergeprep.py"])
    assert res["sets"] == {"docs": "docs/", "notion": "notion/", "portfolio": "portfolio/"}   # .foreman/notion.toml src
    d = by_doc(res)
    assert set(d) == {"docs/11_x.md", "notion/07_merge.md", "portfolio/07_merge.md"}
    assert all(x["fixed"] is None for x in res["docs"]) and res["unfixed"] == 0        # 범위가 없으면 고쳤는지 모름
    [h] = d["docs/11_x.md"]["hits"]
    assert h["line"] == 5 and h["heading"] == "1. 합치기" and h["how"] == "path"
    assert (h["para_from"], h["para_to"]) == (5, 6) and "이어지는 줄" in h["para"]        # 목록 항목 + 들여 쓴 이어지는 줄
    nh = {(x["how"], x["line"]) for x in d["notion/07_merge.md"]["hits"]}
    assert nh == {("covers", 1), ("mark", 9)}
    assert d["notion/07_merge.md"]["kind"] == "notion" and d["portfolio/07_merge.md"]["kind"] == "portfolio"
    assert d["portfolio/07_merge.md"]["hits"][0]["how"] == "covers"                    # 글롭 bridge/*.py


def test_folder_name_and_ambiguous(repo):
    d = by_doc(dr.scan(repo, files=["bridge/transcript/reader.py"]))
    ln = {h["line"] for h in d["docs/11_x.md"]["hits"]}
    assert ln == {9, 19}                                     # 맨글 경로 + 백틱 폴더(/ 없이)
    para = [h for h in d["docs/11_x.md"]["hits"] if h["line"] == 19][0]
    assert (para["para_from"], para["para_to"]) == (18, 20) and para["heading"] == "2. 다른 것"
    assert any(h["how"] == "mark" for h in d["notion/07_merge.md"]["hits"])            # [code:bridge/transcript/]는 아래 파일 모두
    assert "docs/11_x.md" in by_doc(dr.scan(repo, files=["bridge/static/js/handoff.js"]))   # 파일 이름이 하나뿐이면 건다
    x = dr.scan(repo, files=["bridge/x.py"])
    assert "docs/11_x.md" not in by_doc(x)                   # x.py는 bridge/, tools/ 두 곳이라 이름만으로 걸지 않는다


def test_range_fixed_unfixed_and_line_overlap(repo):
    a = sh(repo, "rev-parse", "HEAD")
    put(repo, "bridge/mergeprep.py", "".join(f"line{i}\n" for i in range(1, 21)).replace("line10\n", "LINE10\n"))
    put(repo, "notion/07_merge.md", NOTION + "\n덧붙임\n")
    put(repo, "log/x.md", "`bridge/x.py`\n")
    sh(repo, "add", "."); sh(repo, "commit", "-qm", "fix: 고침")
    res = dr.scan(repo, rng=f"{a}..HEAD")
    assert res["code"] == ["bridge/mergeprep.py"]            # 문서, log, *.md는 코드가 아니다
    d = by_doc(res)
    assert d["notion/07_merge.md"]["fixed"] is True and d["docs/11_x.md"]["fixed"] is False
    assert res["total"] == 3 and res["unfixed"] == 2
    assert res["docs"][-1]["doc"] == "notion/07_merge.md"     # 안 고친 것 먼저
    mark = [h for h in d["notion/07_merge.md"]["hits"] if h["range"]][0]
    assert mark["range"] == [3, 4] and mark["overlap"] is False          # 바뀐 줄은 10
    assert all(h["overlap"] is None for h in d["docs/11_x.md"]["hits"])  # 줄 번호 없는 가리킴
    put(repo, "bridge/mergeprep.py", "".join(f"line{i}\n" for i in range(1, 21)).replace("line3\n", "L3\n"))
    sh(repo, "commit", "-qam", "fix: 3")
    m2 = [h for h in by_doc(dr.scan(repo, rng="HEAD~1..HEAD"))["notion/07_merge.md"]["hits"] if h["range"]][0]
    assert m2["overlap"] is True
    # 갈라진 곳부터(A...B), 파일로 좁히기
    assert dr.scan(repo, rng=f"{a}...HEAD", files=["bridge/static/js/"])["code"] == []


def test_doc_folder_media_is_not_code(repo):
    """문서 묶음 아래 사진(png, gif, webm)이나 다른 파일은 코드가 아니다(11-17 합치기 카드 헛걸림 「걸리는 문서 4, 안 고침 3」)."""
    a = sh(repo, "rev-parse", "HEAD")
    for rel in ("portfolio/img/a.png", "portfolio/img/b.gif", "portfolio/img/c.webm", "notion/img/d.png", "docs/img/e.svg"):
        put(repo, rel, "x\n")
    put(repo, "bridge/transcript/reader.py", "y\n")
    sh(repo, "add", "."); sh(repo, "commit", "-qm", "feat: 사진")
    res = dr.scan(repo, rng=f"{a}..HEAD")
    assert res["code"] == ["bridge/transcript/reader.py"]
    sets = dr.doc_sets("notion/")
    assert not dr.is_code("portfolio/img/a.png", sets) and not dr.is_code("notion/x.json", sets)
    assert dr.is_code("bridge/static/img/a.png", sets) and dr.is_code("portfolio.py", sets)


def test_files_mode_line_ranges(repo):
    hit = [h for h in by_doc(dr.scan(repo, files=["bridge/mergeprep.py:4-6"]))["notion/07_merge.md"]["hits"] if h["range"]][0]
    assert hit["overlap"] is True
    hit = [h for h in by_doc(dr.scan(repo, files=["bridge/mergeprep.py:9"]))["notion/07_merge.md"]["hits"] if h["range"]][0]
    assert hit["overlap"] is False


def test_src_from_foreman_config_and_default(repo, tmp_path):
    (repo / ".foreman" / "notion.toml").unlink()
    cfg = tmp_path / "notion.toml"
    cfg.write_text('[proj]\nsrc = "notion/"\n[other]\nsrc = "docs/"\n')
    assert dr.manuscript_src(repo, cfg) == "notion/"
    cfg.write_text('[proj]\nsrc = "docs/"\n')
    assert dr.doc_sets(dr.manuscript_src(repo, cfg)) == {"docs": "docs/", "portfolio": "portfolio/"}   # docs/면 한 묶음
    cfg.write_text("[other]\n")
    assert dr.manuscript_src(repo, cfg) is None
    res = dr.scan(repo, files=["bridge/mergeprep.py"], config=cfg)
    assert "notion/07_merge.md" not in by_doc(res)           # 원고 폴더를 모르면 보지 않는다


def test_worktree_project_name(repo):
    sh(repo, "worktree", "add", "-q", "-b", "cc/w", str(repo / ".worktrees" / "w"))
    assert dr.project_name(repo / ".worktrees" / "w") == "proj"


def test_read_only(repo):
    a = sh(repo, "rev-parse", "HEAD")
    put(repo, "bridge/x.py", "y\n")                          # 안 올린 변경이 있어도 그대로 둔다
    before = (sh(repo, "status", "--porcelain"), sh(repo, "rev-parse", "HEAD"), sh(repo, "stash", "list"))
    dr.scan(repo, files=["bridge/mergeprep.py"]); dr.scan(repo, rng=f"{a}..HEAD")
    assert (sh(repo, "status", "--porcelain"), sh(repo, "rev-parse", "HEAD"), sh(repo, "stash", "list")) == before


def test_errors(repo):
    with pytest.raises(dr.DocrefsError):
        dr.scan(repo)
    with pytest.raises(dr.DocrefsError):
        dr.scan(repo, rng="nope..HEAD")


def test_card_docs_and_count_line(repo):
    a = sh(repo, "rev-parse", "HEAD")
    put(repo, "bridge/mergeprep.py", "z\n"); sh(repo, "commit", "-qam", "fix: z")
    c = dr.card_docs(dr.scan(repo, rng=f"{a}..HEAD"), limit=2)
    assert c["total"] == 3 and c["unfixed"] == 3 and len(c["docs"]) == 2 and c["readme"] == []
    assert set(c["docs"][0]) >= {"where", "kind", "lines", "count", "files", "stale", "hits"}
    assert dr.count_line(c) == "걸리는 문서 3, 안 고침 3"
    assert dr.count_line({"readme": [], "docs": [{"stale": True}, {"stale": False}]}) == "걸리는 문서 2, 안 고침 1"   # 옛 카드
    assert dr.count_line({"docs": []}) == "" and dr.count_line(None) == ""


def test_cli(repo, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("docrefs_cli", ROOT / "tools" / "docrefs.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    a = sh(repo, "rev-parse", "HEAD")
    put(repo, "bridge/mergeprep.py", "z\n"); sh(repo, "commit", "-qam", "fix: z")
    assert cli.main(["--repo", str(repo), "--range", f"{a}..HEAD"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("걸리는 문서 3, 안 고침 3") and "[안 고침] docs/11_x.md (docs) 줄 5" in out
    assert "「1. 합치기」 경로" in out and "(5-6) - 카드는" in out
    assert cli.main(["--repo", str(repo), "bridge/mergeprep.py", "--json", "--brief"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["total"] == 3 and j["range"] is None
    assert cli.main(["--repo", str(repo), "--range", "nope..HEAD"]) == 2
    assert "거꾸로 찾기 실패" in capsys.readouterr().err
