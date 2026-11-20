"""거꾸로 찾기가 `.foreman/docs.toml`을 쓰는지(11-17 문서 도구 합치기 2단계). tmp 가짜 저장소로.

인프라 꼴은 인프라 `scripts/docs_for_code.py --self-test`의 장면을 그대로 옮겼다(기록 폴더 docs/history/, 번호 짝, [docs:] 사슬, 줄 범위).
FOREMAN 꼴(설정 없음)은 문서 트리거([docs:], 묶음 밖 *.md)와 폴더 인자를 본다.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from bridge import docrefs as dr
from bridge.doctext import config as dcfg

ROOT = Path(__file__).resolve().parent.parent


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


def commit(r: Path, msg: str) -> str:
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", msg)
    return sh(r, "rev-parse", "HEAD")


def ten(tag: str, change: int | None = None) -> str:
    return "".join(f"{tag} {i}{' 바꿈' if i == change else ''}\n" for i in range(1, 11))


def by_doc(res):
    return {d["doc"]: d for d in res["docs"]}


def init(r: Path) -> Path:
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    return r


INFRA_TOML = 'records = ["docs/history/"]\npair_numbers = true\n\n[sets]\nnotion = "notion/"\n'


@pytest.fixture
def infra(tmp_path):
    r = init(tmp_path / "infra")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, ".foreman/docs.toml", INFRA_TOML)
    put(r, "cluster/Vagrantfile", ten("vm"))
    put(r, "apps/a/deploy.yaml", ten("deploy"))
    put(r, "scripts/tool.sh", ten("echo"))
    put(r, "docs/history/data.txt", "기록\n")
    put(r, "docs/history/old.md", "# 옛 기록\n\n`apps/a/deploy.yaml`를 바꿨다. [code:apps/a/deploy.yaml]\n")
    put(r, "docs/style_guide.md", "# 쓰는 법\n규칙 둘\n규칙 셋\n규칙 넷\n규칙 다섯\n")
    put(r, "docs/03_kube.md", "<!--\n다루는 곳: apps/a/\n읽은 커밋: 0000000\n-->\n# 쿠버네티스\n\n"
        "VM 앞 줄. [code:cluster/Vagrantfile:2-3]\n\nVM 뒤 줄. [code:cluster/Vagrantfile:8-9]\n")
    put(r, "notion/03_kube.md", "# 03 쿠버네티스\n\n쓰는 법을 따른다. [docs:style_guide.md:2-3]\n")
    put(r, "notion/03_kube/01_sub.md", "# 03-01 아래 편\n\n본문.\n")
    put(r, "notion/04_other.md", "# 04 다른 편\n\n규칙 다섯. [docs:style_guide.md:5]\n\n옛 기록. [docs:history/old.md]\n")
    put(r, "portfolio/00_x.md", "# 한눈에\n\n도구를 씁니다. [code:scripts/tool.sh]\n")
    commit(r, "base")
    return r


def test_infra_files_mode(infra):
    d = by_doc(dr.scan(infra, files=["scripts/tool.sh"]))
    assert "portfolio/00_x.md" in d and d["portfolio/00_x.md"]["fixed"] is None
    d = by_doc(dr.scan(infra, files=["apps/a/deploy.yaml"]))
    assert "docs/03_kube.md" not in d                                         # 다루는 곳(apps/a/)은 덮기 검사 몫(3단계)
    assert not any(k.startswith("docs/history/") for k in d)                  # 기록 폴더는 문서가 아니다
    r = dr.scan(infra, files=["docs/history/data.txt"])
    assert not r["triggers"] and not r["docs"] and "기록 폴더" in r["warnings"][0]
    r = dr.scan(infra, files=["cluster/Vagrantfile:2-2"])
    assert [h["line"] for h in by_doc(r)["docs/03_kube.md"]["hits"]] == [7]     # 겹치는 줄 번호만
    assert r["config"] == ".foreman/docs.toml"


def test_infra_range_pair_chain_and_lines(infra):
    c0 = sh(infra, "rev-parse", "HEAD")
    put(infra, "apps/a/deploy.yaml", ten("deploy", 4))
    put(infra, "docs/history/data.txt", "기록 바꿈\n")
    c1 = commit(infra, "code only")
    r = dr.scan(infra, rng=f"{c0}..{c1}")
    assert r["docs"] == [] and r["unfixed"] == 0                               # 다루는 곳으로만 가리킨 파일은 걸지 않는다(3단계)
    assert r["code"] == ["apps/a/deploy.yaml"]                                 # 기록 폴더 파일은 코드가 아니다

    put(infra, "apps/a/deploy.yaml", ten("deploy", 5))
    put(infra, "docs/03_kube.md", (infra / "docs/03_kube.md").read_text(encoding="utf-8") + "\n덧붙임.\n")
    c2 = commit(infra, "code and doc")
    d = by_doc(dr.scan(infra, rng=f"{c1}..{c2}"))
    assert "docs/03_kube.md" not in d                                          # 자기 자신은 걸지 않는다
    assert d["notion/03_kube.md"]["fixed"] is False and d["notion/03_kube.md"]["hits"][0]["how"] == "pair"   # 번호 짝
    assert d["notion/03_kube.md"]["by"] == "doc"
    assert "notion/03_kube/01_sub.md" in d and "notion/04_other.md" not in d

    put(infra, "cluster/Vagrantfile", ten("vm", 9))
    c3 = commit(infra, "vm line 9")
    assert [h["line"] for h in by_doc(dr.scan(infra, rng=f"{c2}..{c3}"))["docs/03_kube.md"]["hits"]] == [9]
    put(infra, "cluster/Vagrantfile", (infra / "cluster/Vagrantfile").read_text(encoding="utf-8").replace("vm 5\n", "vm 5 바꿈\n"))
    c4 = commit(infra, "vm line 5")
    r = dr.scan(infra, rng=f"{c3}..{c4}")
    assert r["code"] == ["cluster/Vagrantfile"] and not r["docs"]             # 어느 줄 번호와도 안 겹친다

    put(infra, "docs/style_guide.md", "# 쓰는 법\n규칙 둘 바꿈\n규칙 셋\n규칙 넷\n규칙 다섯\n")
    put(infra, "docs/history/old.md", "# 옛 기록\n\n바꿈.\n")
    c5 = commit(infra, "style guide line 2")
    r = dr.scan(infra, rng=f"{c4}..{c5}")
    d = by_doc(r)
    assert d["notion/03_kube.md"]["fixed"] is False and d["notion/03_kube.md"]["hits"][0]["code"] == "docs/style_guide.md"
    assert "notion/04_other.md" not in d                                       # 안 겹치는 줄, 기록 폴더
    assert r["triggers"] == ["docs/style_guide.md"] and r["code"] == []
    assert by_doc(dr.scan(infra, rng=f"{c4}...{c5}")).keys() == d.keys()


def test_insert_only_hunk_does_not_hit_line_before(infra):
    """줄을 넣기만 한 덩어리는 그 앞 줄을 바꾸지 않는다(인프라 11-17 고장을 옮김)."""
    c0 = sh(infra, "rev-parse", "HEAD")
    put(infra, "cluster/Vagrantfile", ten("vm").replace("vm 3\n", "vm 3\n넣은 줄\n"))
    c1 = commit(infra, "insert after 3")
    assert dr.changed_lines(str(infra), c0, c1, ["cluster/Vagrantfile"]) == {"cluster/Vagrantfile": [(4, 3)]}
    assert "docs/03_kube.md" not in by_doc(dr.scan(infra, rng=f"{c0}..{c1}"))   # 2-3 줄 근거 뒤에 넣었다
    put(infra, "cluster/Vagrantfile", ten("vm").replace("vm 2\n", "vm 2\n넣은 줄\n"))
    c2 = commit(infra, "insert inside 2-3")
    hit = by_doc(dr.scan(infra, rng=f"{c0}..{c2}"))["docs/03_kube.md"]["hits"]
    assert [h["line"] for h in hit] == [7] and hit[0]["overlap"] is True        # 근거 범위 안쪽에 끼면 건다


@pytest.fixture
def foreman(tmp_path):
    r = init(tmp_path / "proj")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, "bridge/a.py", "x\n")
    put(r, "bridge/sub/b.py", "x\n")
    put(r, "bridge/sub/c.py", "x\n")
    put(r, "CLAUDE.md", "# 규칙\n")
    put(r, "docs/11_x.md", "# 11 설계\n\n`bridge/a.py`를 본다. `docs/12_y.md`도 본다.\n")
    put(r, "docs/12_y.md", "# 12 다른 설계\n\n[docs:11_x.md] 자기와 다른 문서를 가리킨다.\n")
    put(r, "notion/11_x.md", "<!--\n다루는 곳: docs/11_x.md, bridge/a.py\n읽은 커밋: abc1234\n-->\n# 11 설계\n\n"
        "규칙을 따른다 [repo:CLAUDE.md]. 설계는 [docs:11_x.md]. 맨글 docs/12_y.md는 걸지 않는다.\n")
    put(r, "log/r.md", "[docs:11_x.md]\n")
    commit(r, "init")
    return r


def test_foreman_doc_triggers(foreman):
    c0 = sh(foreman, "rev-parse", "HEAD")
    put(foreman, "docs/11_x.md", "# 11 설계\n\n바꿈.\n")
    put(foreman, "CLAUDE.md", "# 규칙\n\n바꿈\n")
    c1 = commit(foreman, "docs only")
    r = dr.scan(foreman, rng=f"{c0}..{c1}")
    assert r["config"] == "default" and r["code"] == [] and r["triggers"] == ["CLAUDE.md", "docs/11_x.md"]
    d = by_doc(r)
    got = {(h["how"], h["code"]) for h in d["notion/11_x.md"]["hits"]}
    assert got == {("mark", "CLAUDE.md"), ("mark", "docs/11_x.md")}          # 다루는 곳 docs/11_x.md로는 걸지 않는다(3단계)
    assert all(x["by"] == "doc" for x in r["docs"]) and r["by"]["doc"]["total"] == len(r["docs"])
    assert {(h["how"], h["code"]) for h in d["docs/12_y.md"]["hits"]} == {("mark", "docs/11_x.md")}
    assert "docs/11_x.md" not in d and "log/r.md" not in d                   # 자기 자신, 기록 폴더는 걸지 않는다
    assert not any(h["how"] == "pair" for x in r["docs"] for h in x["hits"])  # FOREMAN은 번호 짝을 켜지 않는다
    put(foreman, "docs/12_y.md", "# 12 다른 설계\n\n[docs:11_x.md] 바꿈.\n")
    c2 = commit(foreman, "docs 12")
    assert dr.scan(foreman, rng=f"{c1}..{c2}")["docs"] == []                 # 경로를 적기만 한 것으로는 문서가 걸지 않는다


def test_foreman_folder_argument_expands(foreman):
    r = dr.scan(foreman, files=["bridge/sub/"])
    assert r["triggers"] == ["bridge/sub/b.py", "bridge/sub/c.py"] and r["docs"] == []
    r = dr.scan(foreman, files=["bridge/*.py"])
    assert "docs/11_x.md" in by_doc(r) and "notion/11_x.md" not in by_doc(r) and "bridge/a.py" in r["code"]
    r = dr.scan(foreman, files=["notion/"])
    assert r["triggers"] == [] and "아래에 걸게 하는 파일이 없습니다" in r["warnings"][0]


def test_config_wins_over_card_docs_dir(foreman):
    """그 저장소 docs.toml이 있으면 합치기 카드가 넘기는 docs_dir보다 앞선다. 없으면 docs_dir를 쓴다."""
    assert dr.scan(foreman, files=["bridge/a.py"], docs_dir="docs")["sets"]["docs"] == "docs/"
    assert dr.scan(foreman, files=["bridge/a.py"], docs_dir="manual")["sets"]["docs"] == "manual/"
    put(foreman, ".foreman/docs.toml", '[sets]\ndocs = "docs/"\nnotion = "notion/"\n')
    assert dr.scan(foreman, files=["bridge/a.py"], docs_dir="manual")["sets"]["docs"] == "docs/"


def test_config_records_and_not_code(foreman):
    put(foreman, ".foreman/docs.toml", 'records = ["log/", "bridge/sub/"]\nnot_code = [".md", ".py"]\n')
    cfg = dcfg.load(foreman)
    sets = dr.resolve_sets(foreman, cfg)
    assert dr.trigger_kind("bridge/sub/b.py", sets, cfg) is None and dr.trigger_kind("bridge/a.py", sets, cfg) is None
    assert dr.trigger_kind("bridge/a.js", sets, cfg) == "code" and dr.trigger_kind("README.md", sets, cfg) == "doc"


def test_generated_readme_is_not_trigger(foreman):
    """[readme] 표가 켜지면 맨 위 README.md는 생성물이라 걸지 않는다. 다른 폴더의 README.md는 그대로 문서 트리거다."""
    put(foreman, "README.md", "# 손으로 쓴 README\n")
    put(foreman, "notion/20_r.md", "# 20 읽기\n\n안내를 따른다 [repo:README.md].\n")
    commit(foreman, "readme")
    assert dr.trigger_kind("README.md", dr.resolve_sets(foreman, dcfg.load(foreman)), dcfg.load(foreman)) == "doc"
    assert "notion/20_r.md" in by_doc(dr.scan(foreman, files=["README.md"]))
    put(foreman, ".foreman/docs.toml", '[readme]\ntitle = "가짜"\n')
    cfg = dcfg.load(foreman)
    sets = dr.resolve_sets(foreman, cfg)
    assert dr.trigger_kind("README.md", sets, cfg) is None
    assert dr.trigger_kind("bridge/README.md", sets, cfg) == "doc"
    assert by_doc(dr.scan(foreman, files=["README.md"])) == {}


def test_broken_config_fails(foreman):
    put(foreman, ".foreman/docs.toml", "records = [\n")
    with pytest.raises(dr.DocrefsError, match="docs.toml"):
        dr.scan(foreman, files=["bridge/a.py"])


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"t_{name}", ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_docs_refs_args(infra, capsys):
    """tools/docs.py refs 하나로 모았다(3단계에서 tools/docrefs.py 껍데기를 지웠다). 다른 저장소 껍데기가 넘기는 옛 인자 차례도 받는다."""
    docs = load_tool("docs")
    assert not (ROOT / "tools" / "docrefs.py").exists()
    c0 = sh(infra, "rev-parse", "HEAD")
    put(infra, "docs/style_guide.md", "# 쓰는 법\n규칙 둘 바꿈\n규칙 셋\n규칙 넷\n규칙 다섯\n")
    put(infra, "apps/a/deploy.yaml", ten("deploy", 2))
    commit(infra, "both")
    outs = []
    for argv in (["--repo", str(infra), "refs", "--range", f"{c0}..HEAD"],
                 ["--repo", str(infra), "--json", "refs", "--range", f"{c0}..HEAD", "--unfixed"],
                 ["--repo", str(infra), "refs", "cluster/Vagrantfile:2", "--brief"]):
        assert docs.main(argv) == 0
        outs.append(capsys.readouterr().out)
    # deploy.yaml은 docs/03_kube.md 다루는 곳으로만 가리켜 걸지 않는다. style_guide.md 줄 2는 원고 근거 표시가 건다
    assert outs[0].startswith("걸리는 문서 1, 안 고침 1 (범위") and "코드 파일 1개, 문서 1개" in outs[0]
    assert "\n문서로만 걸린 문서 1, 안 고침 1\n" in outs[0]
    assert "번호 짝" not in outs[0] and "notion/03_kube.md (노션 원고, 문서로만 걸림)" in outs[0]
    assert all(d["fixed"] is False for d in json.loads(outs[1])["docs"])
    assert "docs/03_kube.md" in outs[2]
    # 인프라 껍데기는 옛 인자를 refs 뒤에 그대로 넘긴다(--json, --rev가 뒤에 와도 같다)
    assert docs.main(["--repo", str(infra), "refs", "--range", f"{c0}..HEAD", "--unfixed", "--json"]) == 0
    assert capsys.readouterr().out == outs[1]
    assert docs.main(["--repo", str(infra), "refs", "scripts/tool.sh", "--rev", c0, "--brief"]) == 0
    assert "portfolio/00_x.md" in capsys.readouterr().out
    put(infra, ".foreman/docs.toml", "records = [\n")
    assert docs.main(["--repo", str(infra), "refs", "scripts/tool.sh"]) == 2
    assert "거꾸로 찾기 실패" in capsys.readouterr().err
