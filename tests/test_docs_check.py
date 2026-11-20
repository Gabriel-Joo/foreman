"""문서 점검(11-17 문서 도구 합치기 3단계, bridge/doctext/check.py, tools/docs.py check). tmp 가짜 저장소로.

FOREMAN 꼴(설정 없음)과 인프라 꼴(.foreman/docs.toml [check])에서 인프라 scripts/docs-check.py 1~7번 규칙을 본다.
근거 확인기(bridge/evidence.py)와 같은 판정을 쓰는지는 tests/test_doctext.py가 본다.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from bridge.doctext import check as ck
from bridge.doctext import config as dcfg
from bridge.doctext.head import parse_head

ROOT = Path(__file__).resolve().parent.parent


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


def init(r: Path) -> Path:
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    return r


def head(covers: str, read: str) -> str:
    return f"<!--\n다루는 곳: {covers}\n읽은 커밋: {read}\n-->\n"


def run(r: Path, rev=None):
    from bridge import docrefs
    cfg = dcfg.load(r, rev)
    return ck.run(str(r), rev, cfg, docrefs.resolve_sets(r, cfg))


def whats(res):
    return [f"{e['doc']}:{e['line']}: {e['what']}" if e["doc"] else e["what"] for e in res["errors"]]


@pytest.fixture
def foreman(tmp_path):
    r = init(tmp_path / "proj")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, "bridge/a.py", "1\n2\n3\n")
    put(r, "bridge/b.py", "x\n")
    put(r, "docs/11_x.md", "# 11 설계\n\n본문 1\n")
    put(r, "log/r.md", "기록\n")
    c0 = commit(r)
    put(r, "notion/01_a.md", head("bridge/a.py", c0[:7]) + "# 01 가\n\n가는 세 줄이다 [code:bridge/a.py:1-3]. 설계 [docs:11_x.md#1] 기록 [log:r.md] "
        "커밋 [c:" + c0[:7] + "] 턴 [t:12]. → 「02 나」\n\n```\n울타리 [code:없음.py] → 「없는 편」\n```\n")
    put(r, "notion/02_b.md", head("bridge/b.py, .foreman/", c0[:7]) + "# 02 나\n\n나는 하나다. [code:bridge/b.py] → 「가」\n")
    put(r, "portfolio/01_p.md", head("bridge/", c0[:7]) + "# 포트폴리오\n\n![그림](img/a.png) 화면입니다.\n")
    put(r, "portfolio/img/a.png", "png")
    commit(r)
    return r


def test_foreman_default_clean(foreman):
    res = run(foreman)
    assert res["errors"] == [] and res["sets"] == {"notion": 2, "portfolio": 1}
    assert res["cover"] == {"target": 3, "covered": 3}                       # bridge/a.py, b.py, .foreman/notion.toml. docs/, log/, 원고 밖만
    assert res["reads"]["piece"] and res["marks"] == 6                         # 울타리 안은 세지 않는다(FOREMAN)


def test_cover_skips_not_code(foreman):
    """not_code의 확장자, 경로, 글롭에 드는 파일은 덮기 대상이 아니고, 덮기 밖 틀림으로도 나오지 않는다. `.md`는 빼지 않는다."""
    put(foreman, ".foreman/docs.toml", 'not_code = [".md", ".png", "static/skip.txt", "assets/*.bin"]\n')
    put(foreman, "static/skip.txt", "x\n")
    put(foreman, "static/keep.txt", "y\n")
    put(foreman, "assets/a.bin", "z\n")
    put(foreman, "assets/b.png", "p")
    put(foreman, "CLAUDE.md", "규칙\n")
    commit(foreman)
    w = whats(run(foreman))
    assert not any("assets/" in x or "skip.txt" in x for x in w)             # 글롭, 경로, 확장자로 빠짐
    assert any("static/keep.txt" in x and "덮기 밖" in x for x in w)         # 안 든 파일은 그대로 덮기 밖
    assert any("CLAUDE.md" in x and "덮기 밖" in x for x in w)               # .md는 not_code에 있어도 덮기 대상에 남는다


def test_cover_skips_generated_readme(foreman):
    """`[readme]` 표가 있으면 맨 위 README.md는 생성물이라 덮기 대상이 아니다. 표가 없으면 지금처럼 대상이다. 다른 폴더의 README.md는 그대로 대상."""
    put(foreman, "README.md", "# 가짜\n")
    put(foreman, "apps/README.md", "# 앱\n")
    commit(foreman)
    w = whats(run(foreman))
    assert any("README.md가" in x and "덮기 밖" in x and "apps/" not in x for x in w)       # 표 없음: 대상
    put(foreman, ".foreman/docs.toml", '[readme]\ntitle = "가짜"\n')
    commit(foreman)
    res = run(foreman)
    w = whats(res)
    assert not any("덮기 밖: README.md" in x for x in w)                                     # 표 있음: 대상에서 빠짐
    assert any("덮기 밖: apps/README.md" in x for x in w)


def test_cover_skips_readme_header_file(foreman):
    """`[readme] header_file`이 가리키는 파일은 저장소가 not_code에 적지 않아도 덮기 대상이 아니다(11-19). 다른 `.md`는 그대로 대상."""
    put(foreman, "top/readme_header.md", "[배지](x)\n")
    put(foreman, "top/other.md", "다른 글\n")
    put(foreman, ".foreman/docs.toml", '[readme]\ntitle = "가짜"\n')
    commit(foreman)
    w = whats(run(foreman))
    assert any("덮기 밖: top/readme_header.md" in x for x in w), w                       # header_file을 안 적으면 대상
    put(foreman, ".foreman/docs.toml", '[readme]\ntitle = "가짜"\nheader_file = "top/readme_header.md"\n')
    commit(foreman)
    w = whats(run(foreman))
    assert not any("readme_header.md" in x and "덮기 밖" in x for x in w)                     # 적으면 빠짐
    assert any("덮기 밖: top/other.md" in x for x in w)


def test_foreman_errors(foreman):
    put(foreman, "bridge/c.py", "새 파일\n")
    put(foreman, "notion/01_a.md", (foreman / "notion/01_a.md").read_text(encoding="utf-8")
        + "\n틀림 [code:bridge/a.py:2-9] [code:없음/] [docs:없음.md] [c:abcdef0] [t:x] → 「없는 편」 ![그림](img/없음.png)\n")
    put(foreman, "notion/03_c.md", "# 03 머리 없음\n")
    put(foreman, "portfolio/02_q.md", head("bridge/없음.py", "1234567") + "# 둘\n")
    commit(foreman)
    w = whats(run(foreman))
    assert "notion/03_c.md:None: 머리 주석에 다루는 곳 또는 읽은 커밋이 없습니다" in w
    assert "portfolio/02_q.md:1: 읽은 커밋 1234567이 저장소에 없습니다" in w
    assert "portfolio/02_q.md:1: 다루는 곳 「bridge/없음.py」: 그 경로가 없습니다" in w
    line = [x for x in w if x.startswith("notion/01_a.md:") and "울타리" not in x]
    assert any("[code:bridge/a.py:2-9] 줄 범위가 맞지 않습니다(파일은 3줄)" in x for x in line)
    assert any("[code:없음/] 없음/ 파일이 없습니다" in x for x in line)
    assert any("[docs:없음.md] docs/없음.md 파일이 없습니다" in x for x in line)
    assert any("[c:abcdef0] 그 커밋이 저장소에 없습니다" in x for x in line)
    assert any("[t:x] 턴 번호가 숫자가 아닙니다" in x for x in line)
    assert any("→ 「없는 편」 제목을 가진 편이 없습니다" in x for x in line)
    assert any("그림 파일이 없습니다 img/없음.png" in x for x in line)
    assert "덮기 밖: bridge/c.py가 notion 어느 편의 다루는 곳에도 들지 않습니다" in w
    assert not any("울타리" in x or "없음.py]" in x for x in w)               # 울타리 안은 보지 않는다(FOREMAN)


def test_untracked_new_piece_is_checked(foreman):
    put(foreman, "notion/04_new.md", "# 04 아직 add 안 함\n")
    assert any(e["doc"] == "notion/04_new.md" for e in run(foreman)["errors"])
    assert not any(e["doc"] == "notion/04_new.md" for e in run(foreman, "HEAD")["errors"])   # 커밋 판은 그 커밋만


def test_suspects(foreman):
    put(foreman, "notion/02_b.md", (foreman / "notion/02_b.md").read_text(encoding="utf-8")
        + "\n이 줄은 숫자 42가 있는데 근거 표시가 없는 줄이다\n짧은 7\n→ 「02 나」 다른 편 안내만 있는 줄이고 숫자는 제목에\n")
    s = run(foreman)["suspects"]
    assert [x["line"] for x in s] == [9]                                      # 짧은 줄, 참조 안 숫자는 아니다


INFRA = """records = ["docs/history/"]
read_commit = "set"
allowed_domains = ["ok.dev"]

[sets]
notion = "notion/"

[check]
sets = ["notion", "portfolio", "docs"]
numbered_only = ["docs", "portfolio"]
head_at = "top"
fenced = true
kinds = ["c", "docs", "code"]
xref = { docs = "notion" }
files_at = "read"
claim = '\\d|“|”'
claim_min = 0
banned = ["notion", "portfolio"]
cover_by = ["notion"]
"""


@pytest.fixture
def infra(tmp_path):
    r = init(tmp_path / "infra")
    put(r, ".foreman/docs.toml", INFRA)
    put(r, "apps/a.yaml", "a\nb\n")
    put(r, "docs/history/h.md", "기록\n")
    put(r, "docs/style_guide.md", "번호 없는 문서는 점검하지 않는다 [code:없음]\n")
    read = commit(r)[:7]
    put(r, "notion/01_a.md", head("apps/, .foreman/docs.toml", read) + "# 01 가\n\n가 [code:apps/a.yaml:2] [docs:history/h.md]\n")
    put(r, "docs/03_k.md", head("apps/a.yaml", read) + "# 쿠버네티스\n\n→ 「가」 참조는 원고 제목으로 찾는다\n")
    put(r, "portfolio/01_p.md", head("apps/a.yaml", read) + "# 화면\n\n주소는 www.ok.dev 입니다.\n")
    put(r, "portfolio/notes.md", "번호 없는 포트폴리오 글은 보지 않는다\n")
    commit(r)
    return r


def test_infra_config_parsed(infra):
    c = dcfg.load(infra).check
    assert c.head_at == "top" and c.fenced and c.kinds == ["c", "docs", "code", "repo"] and c.xref == {"docs": "notion"}
    assert c.files_at == "read" and c.claim == r"\d|“|”" and c.claim_min == 0 and c.domains_in == ["portfolio"]
    assert dcfg.DocsConfig().check.as_dict() == dcfg.CheckConfig().as_dict()


def test_infra_clean(infra):
    res = run(infra)
    assert res["errors"] == [] and res["sets"] == {"notion": 1, "portfolio": 1, "docs": 1}
    assert res["reads"] == {"main": [res["reads"]["main"][0]], "portfolio": [res["reads"]["main"][0]]}
    assert res["cover"] == {"target": 2, "covered": 2}


def test_infra_rules(infra):
    put(infra, "notion/01_a.md", (infra / "notion/01_a.md").read_text(encoding="utf-8")
        + "\n[t:1] 10.1.2.3 home /home/x [code:apps/b.yaml]\n\n```\n울타리 [code:없음.py] → 「없는 편」\n```\n")
    put(infra, "apps/b.yaml", "읽은 커밋 뒤에 생긴 파일\n")
    put(infra, "portfolio/01_p.md", (infra / "portfolio/01_p.md").read_text(encoding="utf-8") + "\n남의 www.other.com\n")
    read = parse_head((infra / "notion/01_a.md").read_text(encoding="utf-8"))["read"]
    put(infra, "notion/02_b.md", "\n" + head("apps/", read) + "# 02 나\n")
    commit(infra)
    w = whats(run(infra))
    assert any("[t:1] 이 저장소에서 쓰지 않는 종류입니다" in x for x in w)
    assert any("원고 금지어(IP 주소) 「10.1.2.3」" in x for x in w) and any("원고 금지어(홈 경로)" in x for x in w)
    assert any("[code:apps/b.yaml] apps/b.yaml 파일이 없습니다" in x for x in w)     # 읽은 커밋 판(files_at read)
    assert any("[code:없음.py]" in x for x in w) and any("→ 「없는 편」" in x for x in w)   # 울타리 안도 본다(fenced)
    assert any("원고 금지어(도메인) 「www.other.com」" in x for x in w) and not any("ok.dev" in x for x in w)
    assert not any(x.startswith("notion/02_b.md") and "머리 주석" in x for x in w)  # 맨 앞 빈 줄 뒤 주석은 머리(head_at top)
    put(infra, "docs/03_k.md", head("apps/a.yaml", "0000000") + "# 쿠버네티스\n")
    w = whats(run(infra))
    assert any(x.startswith("읽은 커밋이 하나가 아닙니다") for x in w)              # set: 원고와 docs가 하나
    assert not any(x.startswith("포트폴리오 읽은 커밋") for x in w)                 # 포트폴리오끼리는 따로


def test_head_at_top_and_first():
    md = "# 제목\n\n<!--\n다루는 곳: a.py\n읽은 커밋: abc1234\n-->\n"
    assert parse_head(md)["covers"] == ["a.py"] and parse_head(md, "top") is None
    assert parse_head("\n\n" + md[md.index("<!--"):], "top")["read"] == "abc1234"


@pytest.mark.parametrize("bad", ['[check]\nhead_at = "middle"\n', '[check]\nkinds = ["x"]\n', '[check]\nsets = ["nope"]\n',
                                 '[check]\nxref = { docs = "x" }\n', '[check]\nclaim = "("\n', '[check]\nclaim_min = -1\n',
                                 '[check]\nfenced = "yes"\n', '[check]\nfiles_at = "head"\n', 'check = 1\n'])
def test_bad_check_config(bad):
    with pytest.raises(dcfg.DocsConfigError):
        dcfg.parse(bad)


def test_unknown_check_field_warns():
    assert any("check.nope" in w for w in dcfg.parse("[check]\nnope = 1\n").warnings)


def test_cli_exit_codes(infra, foreman, capsys):
    spec = importlib.util.spec_from_file_location("docs_cli_check", ROOT / "tools" / "docs.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main(["--repo", str(foreman), "check"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("편 3(notion 2, portfolio 1)") and out.rstrip().endswith("틀린 것 0, 의심 0")
    put(foreman, "notion/03_c.md", "# 03 머리 없음\n")
    assert cli.main(["--repo", str(foreman), "--json", "check"]) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["doc"] == "notion/03_c.md"
    put(infra, ".foreman/docs.toml", "[check]\nhead_at = 1\n")
    assert cli.main(["--repo", str(infra), "check"]) == 2
    assert "문서 도구 실패" in capsys.readouterr().err


def test_read_only(foreman):
    before = (sh(foreman, "status", "--porcelain"), sh(foreman, "rev-parse", "HEAD"))
    run(foreman)
    run(foreman, "HEAD")
    assert (sh(foreman, "status", "--porcelain"), sh(foreman, "rev-parse", "HEAD")) == before
