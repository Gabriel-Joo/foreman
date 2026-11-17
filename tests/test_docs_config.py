"""저장소마다 다른 문서 규칙 `.foreman/docs.toml`(11-17 문서 도구 합치기 1단계, bridge/doctext/config.py). 없으면 FOREMAN 지금 동작."""

import subprocess

import pytest

from bridge.doctext import config as dcfg


def test_config_defaults_are_foreman_behavior(tmp_path):
    from bridge import docrefs
    c = dcfg.load(tmp_path)
    assert c.source == "default" and c.warnings == []
    assert c.sets == {"docs": docrefs.DOCS_DIR, "notion": None, "portfolio": docrefs.PORTFOLIO_DIR}
    assert c.records == ["log/"]                     # 1단계 전 docrefs SKIP_CODE_DIRS. 2단계부터 docrefs가 이 값을 쓴다
    sets = docrefs.doc_sets(None)
    assert docrefs.trigger_kind("log/x.py", sets, c) is None and docrefs.trigger_kind("bridge/x.py", sets, c) == "code"
    assert (c.pair_numbers, c.read_commit, c.allowed_domains, c.not_code) == (False, "piece", [], [".md"])


INFRA_TOML = """
records = ["docs/history/"]
pair_numbers = true
read_commit = "set"
allowed_domains = ["Example.dev"]
not_code = [".md", ".png"]
later = 1

[sets]
notion = "notion/"
"""


def test_config_infra_like(tmp_path):
    (tmp_path / ".foreman").mkdir()
    (tmp_path / ".foreman" / "docs.toml").write_text(INFRA_TOML, encoding="utf-8")
    c = dcfg.load(tmp_path)
    assert c.source == ".foreman/docs.toml"
    assert c.sets == {"docs": "docs/", "notion": "notion/", "portfolio": "portfolio/"}
    assert (c.records, c.pair_numbers, c.read_commit) == (["docs/history/"], True, "set")
    assert c.allowed_domains == ["example.dev"] and c.not_code == [".md", ".png"]
    assert c.warnings == [".foreman/docs.toml: 모르는 칸 later는 쓰지 않습니다"]


def test_config_top_keys_after_table_are_warned():
    """[sets] 뒤에 쓴 맨 위 칸은 TOML에서 sets 안으로 들어간다. 조용히 기본값이 되지 않고 경고로 보인다."""
    c = dcfg.parse("[sets]\nnotion = 'notion/'\nrecords = ['docs/history/']\n")
    assert c.records == ["log/"] and "sets.records" in c.warnings[0]


def test_not_code_takes_extension_path_and_glob():
    """11-17 `not_code`는 확장자뿐 아니라 파일 경로, 글롭도 받는다(근거를 달 문장이 없는 `__init__.py`, `.gitignore`)."""
    c = dcfg.parse("not_code = ['.md', '.gitignore', 'bridge/__init__.py', 'pkg/*/__init__.py']")
    assert c.not_code == [".md", ".gitignore", "bridge/__init__.py", "pkg/*/__init__.py"]
    m = lambda p: dcfg.not_code_match(p, c.not_code)  # noqa: E731
    assert m("README.md") and m(".gitignore") and m("sub/.gitignore")            # 확장자 꼴(끝 글자)
    assert m("bridge/__init__.py") and not m("xbridge/__init__.py") and not m("bridge/api/__init__.py")   # 경로는 통째로
    assert m("pkg/a/__init__.py") and m("pkg/a/b/__init__.py") and not m("pkg/__init__.py")
    assert not m("bridge/a.py")


def test_not_code_decides_trigger():
    from bridge import docrefs
    c = dcfg.parse("not_code = ['.md', 'bridge/__init__.py', '.gitignore']")
    sets = docrefs.doc_sets(None)
    assert docrefs.trigger_kind("bridge/__init__.py", sets, c) is None and docrefs.trigger_kind(".gitignore", sets, c) is None
    assert docrefs.trigger_kind("bridge/api/__init__.py", sets, c) == "code"      # 이름을 안 넣은 같은 이름 파일은 그대로 코드
    assert docrefs.trigger_kind("README.md", sets, c) == "doc"


@pytest.mark.parametrize("body,why", [
    ("not_code = ['Makefile']", "확장자나 저장소 안 파일 경로"),
    ("not_code = ['/abs/x.py']", "확장자나 저장소 안 파일 경로"),
    ("not_code = ['../x.py']", "확장자나 저장소 안 파일 경로"),
    ("records = 'log/'", "글자 목록"),
    ("records = ['/abs/']", "저장소 안 폴더"),
    ("[sets]\ndocs = 'docs'", "저장소 안 폴더"),
    ("[sets]\nnotion = '../x/'", "저장소 안 폴더"),
    ("pair_numbers = 'yes'", "true 또는 false"),
    ("read_commit = 'each'", "piece 또는 set"),
    ("not_code = ['md']", "확장자"),
    ("sets = 1", "표"),
    ("records = [", "읽지 못했습니다"),
])
def test_config_bad_values_stop(body, why):
    with pytest.raises(dcfg.DocsConfigError, match=why):
        dcfg.parse(body)


def test_config_unknown_set_is_warned():
    c = dcfg.parse("[sets]\nwiki = 'wiki/'\n")
    assert c.sets["docs"] == "docs/" and "sets.wiki" in c.warnings[0]


def test_config_from_rev(tmp_path):
    def sh(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    sh("init", "-q")
    sh("config", "user.email", "t@t")
    sh("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    sh("add", ".")
    sh("commit", "-qm", "a")
    assert dcfg.load(tmp_path, "HEAD").source == "default"
    (tmp_path / ".foreman").mkdir()
    (tmp_path / ".foreman" / "docs.toml").write_text("read_commit = 'set'\n", encoding="utf-8")
    sh("add", ".")
    sh("commit", "-qm", "b")
    assert dcfg.load(tmp_path, "HEAD").read_commit == "set"
    assert dcfg.load(tmp_path, "HEAD~1").read_commit == "piece"
    with pytest.raises(dcfg.DocsConfigError, match="찾지 못했습니다"):
        dcfg.load(tmp_path, "nosuch")
