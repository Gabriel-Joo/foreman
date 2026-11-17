"""README 생성(11-17 문서 정리 B, bridge/doctext/readme.py, tools/docs.py readme, 문서 점검 9번). tmp 가짜 저장소로.

노션 주소는 게시 기록(DB) 대신 --links 파일이나 links 인자로 넘긴다. 실제 README.md와 DB는 건드리지 않는다.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from bridge import docrefs
from bridge.doctext import check as ck
from bridge.doctext import config as dcfg
from bridge.doctext import readme as rd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("docs_tool_readme", ROOT / "tools" / "docs.py")
docs_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_tool)

URL_P = "https://example.invalid/p/portfolio-top"
URL_N = "https://example.invalid/p/notion-top"
LINKS = {"portfolio/00_overview.md": URL_P, "notion/00_intro.md": URL_N}


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


FILES = {
    ".foreman/notion.toml": 'src = "notion/"\n',
    ".foreman/docs.toml": '[readme]\ntitle = "가짜"\nproject = "fake"\n',
    "portfolio/00_overview.md": ("<!--\n다루는 곳: a.py\n읽은 커밋: 1a2b3c4\n-->\n# 한눈에 보는 가짜\n\n> 이 글은 안내입니다.\n\n"
                                 "![그림](img/a.png)\n\n**가짜는 시험용 저장소입니다** [code:a.py:1].\n둘째 줄도 같은 문단입니다.\n\n"
                                 "다음 문단은 들어가지 않습니다.\n"),
    "portfolio/01_screen.md": "# 화면 | 하나\n\n본문\n",
    "notion/00_intro.md": "# 00 들어가며\n\n본문\n",
    "notion/01_parts.md": "# 01 구조\n\n본문\n",
    "notion/01_parts/01_place.md": "# 어디에 두었나\n\n본문\n",
    "notion/01_parts/02_start.md": "# 01-02 뜨는 차례\n\n본문\n",
    "notion/TODO.md": "# 번호 없는 글\n",
    "a.py": "x = 1\n",
}


def make(tmp_path: Path, files=None, name="fake") -> Path:
    r = tmp_path / name
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    for k, v in (FILES if files is None else files).items():
        put(r, k, v)
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", "init")
    return r


def links_file(tmp_path: Path, links=None) -> str:
    f = tmp_path / "links.json"
    f.write_text(json.dumps(LINKS if links is None else links), encoding="utf-8")
    return str(f)


def cli(capsys, *argv):
    rc = docs_tool.main(list(argv))
    out = capsys.readouterr()
    return rc, out.out, out.err


def check9(r: Path, links=LINKS, rev=None):
    cfg = dcfg.load(r, rev)
    return ck.readme_check(str(r), rev, cfg, docrefs.resolve_sets(r, cfg), links)


def test_number_and_intro():
    assert rd.number("03_x.md") == "03" and rd.number("01_a/02_b.md") == "01-02"
    assert rd.number("TODO.md") is None and rd.number("01_a/b.md") is None
    assert rd.intro(FILES["portfolio/00_overview.md"]) == "**가짜는 시험용 저장소입니다**. 둘째 줄도 같은 문단입니다."
    assert rd.intro("본문만\n") is None


def test_build_whole_file(tmp_path, capsys):
    r = make(tmp_path)
    rc, out, err = cli(capsys, "--repo", str(r), "--links", links_file(tmp_path), "readme")
    assert rc == 0 and "새로 썼습니다" in out
    text = (r / "README.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines[0] == rd.TOP and lines[1] == "# 가짜"
    assert "**가짜는 시험용 저장소입니다**. 둘째 줄도 같은 문단입니다." in text and "[code:" not in text
    assert "다음 문단" not in text and "안내입니다" not in text
    assert text.index("## 포트폴리오") < text.index("## 기술문서")
    assert f"[노션에서 보기]({URL_P})" in text and f"[노션에서 보기]({URL_N})" in text
    assert "| 01 | [화면 \\| 하나](portfolio/01_screen.md) |" in text
    assert "| 00 | [들어가며](notion/00_intro.md) |" in text
    # 하위 편: 제목에 번호가 없으면 파일 번호, 있으면 제목 번호. 부모 편이 하위 편보다 앞
    assert text.index("| 01 | [구조]") < text.index("| 01-01 | [어디에 두었나](notion/01_parts/01_place.md) |")
    assert "| 01-02 | [뜨는 차례](notion/01_parts/02_start.md) |" in text
    assert "TODO" not in text and "번호가 없어 표에 넣지 않은 파일 1개(notion/TODO.md)" in out
    assert text.endswith("|\n")


def test_twice_same_and_check_passes(tmp_path, capsys):
    r = make(tmp_path)
    lf = links_file(tmp_path)
    cli(capsys, "--repo", str(r), "--links", lf, "readme")
    first = (r / "README.md").read_bytes()
    rc, out, _ = cli(capsys, "--repo", str(r), "--links", lf, "readme")
    assert rc == 0 and "이미 같습니다" in out and (r / "README.md").read_bytes() == first
    assert check9(r) == ([], ["기술문서: 번호가 없어 표에 넣지 않은 파일 1개(notion/TODO.md)"])


@pytest.mark.parametrize("change,where", [
    (lambda r: put(r, "portfolio/02_new.md", "# 새 편\n"), "새 편"),                        # 편이 늘었다
    (lambda r: put(r, "notion/01_parts/01_place.md", "# 어디에 놓았나\n"), "어디에"),         # 하위 편 제목이 바뀌었다
    (lambda r: (r / "notion/01_parts.md").unlink(), "구조"),                                  # 편이 줄었다
    (lambda r: put(r, "portfolio/00_overview.md", "# 한눈에 보는 가짜\n\n바뀐 소개입니다.\n"), "소개"),
    (lambda r: put(r, "README.md", (r / "README.md").read_text(encoding="utf-8") + "\n손으로 더한 줄\n"), "손으로"),
])
def test_check_catches_drift(tmp_path, capsys, change, where):
    r = make(tmp_path)
    cli(capsys, "--repo", str(r), "--links", links_file(tmp_path), "readme")
    change(r)
    errs, _ = check9(r)
    assert len(errs) == 1 and "README.md가 지금 원고로 만든 글과 다릅니다" in errs[0] and "tools/docs.py readme" in errs[0]


def test_check_link_changed_and_fallback(tmp_path, capsys):
    r = make(tmp_path)
    cli(capsys, "--repo", str(r), "--links", links_file(tmp_path), "readme")
    errs, _ = check9(r, {**LINKS, "notion/00_intro.md": "https://example.invalid/p/moved"})
    assert errs and "노션에서 보기" in errs[0]
    # 게시 기록을 못 읽으면 README에 걸린 주소로 나머지만 맞대고 알린다(틀림으로 세지 않는다)
    errs, notes = check9(r, None)
    assert errs == [] and any("게시 기록을 읽지 못해" in n for n in notes)


def test_unpublished_set_says_so(tmp_path, capsys):
    r = make(tmp_path)
    rc, out, _ = cli(capsys, "--repo", str(r), "--links", links_file(tmp_path, {"portfolio/00_overview.md": URL_P}), "readme")
    text = (r / "README.md").read_text(encoding="utf-8")
    assert rc == 0 and rd.NO_LINK in text and "[노션에서 보기]()" not in text
    assert "기술문서: 맨 위 편 notion/00_intro.md의 노션 주소가 게시 기록에 없어" in out


def test_refuses_without_readme_table(tmp_path, capsys):
    files = {k: v for k, v in FILES.items() if k != ".foreman/docs.toml"}
    files["README.md"] = "# 사람이 쓴 설계 문서\n"
    r = make(tmp_path, files)
    lf = links_file(tmp_path)
    rc, out, err = cli(capsys, "--repo", str(r), "--links", lf, "readme")
    assert rc == 2 and "[readme] 표가 없음" in err
    assert (r / "README.md").read_text(encoding="utf-8") == "# 사람이 쓴 설계 문서\n"
    rc, out, _ = cli(capsys, "--repo", str(r), "--links", lf, "readme", "--dry")      # 미리 보기는 된다, 쓰지 않는다
    assert rc == 0 and out.startswith(rd.TOP) and "# fake" in out
    assert sh(r, "status", "--porcelain") == ""
    assert check9(r) == ([], ["[readme] 표가 없어 README 생성 검사를 하지 않았습니다(.foreman/docs.toml)"])


def test_rev_needs_dry(tmp_path, capsys):
    r = make(tmp_path)
    rc, _, err = cli(capsys, "--repo", str(r), "--rev", "HEAD", "--links", links_file(tmp_path), "readme")
    assert rc == 2 and "--rev" in err and not (r / "README.md").exists()


@pytest.mark.parametrize("drop,why", [
    ("portfolio/00_overview.md", "포트폴리오 00편이 없어"),
])
def test_cannot_build_writes_nothing(tmp_path, capsys, drop, why):
    files = {k: v for k, v in FILES.items() if k != drop}
    r = make(tmp_path, files)
    rc, _, err = cli(capsys, "--repo", str(r), "--links", links_file(tmp_path), "readme")
    assert rc == 2 and why in err and not (r / "README.md").exists()
    errs, _ = check9(r)
    assert errs == ["README.md가 없습니다(tools/docs.py readme로 만듭니다)"]


def test_intro_missing_paragraph(tmp_path, capsys):
    r = make(tmp_path, {**FILES, "portfolio/00_overview.md": "# 한눈에\n\n> 인용뿐\n\n## 절\n"})
    rc, _, err = cli(capsys, "--repo", str(r), "--links", links_file(tmp_path), "readme")
    assert rc == 2 and "본문 문단이 없어" in err


def test_check_command_shows_readme_error(tmp_path, capsys):
    r = make(tmp_path)
    lf = links_file(tmp_path)
    cli(capsys, "--repo", str(r), "--links", lf, "readme")
    put(r, "portfolio/02_new.md", "# 새 편\n")
    rc, out, _ = cli(capsys, "--repo", str(r), "--links", lf, "check")
    assert rc == 1 and "틀림  README.md: README.md가 지금 원고로 만든 글과 다릅니다" in out


def test_project_from_origin(tmp_path):
    files = dict(FILES)
    files[".foreman/docs.toml"] = "[readme]\n"
    r = make(tmp_path, files, name="checkout")
    cfg = dcfg.load(r)
    assert ck.readme_project(str(r), cfg) == "checkout"          # origin이 없으면 폴더 이름
    sh(r, "remote", "add", "origin", "https://example.invalid/someone/real-name.git")
    assert ck.readme_project(str(r), cfg) == "real-name"
    assert ck.readme_build(str(r), None, cfg, docrefs.resolve_sets(r, cfg), {}).text.split("\n")[1] == "# real-name"


@pytest.mark.parametrize("body,why", [
    ("readme = 1\n", "표"),
    ('[readme]\ntitle = ""\n', "한 줄 글"),
    ('[readme]\nproject = "a\\nb"\n', "한 줄 글"),
])
def test_config_errors(body, why):
    with pytest.raises(dcfg.DocsConfigError, match=why):
        dcfg.parse(body)


def test_config_unknown_key_warns():
    c = dcfg.parse('[readme]\ntitel = "x"\n')
    assert c.readme == {} and any("readme.titel" in w for w in c.warnings)
