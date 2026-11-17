"""문서 도구 명령 tools/docs.py(11-17 문서 도구 합치기 1단계). tmp 가짜 저장소 둘(FOREMAN 꼴, 인프라 꼴)을 --repo로 읽기만 한다."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("docs_tool", ROOT / "tools" / "docs.py")
docs_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_tool)


def sh(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(r: Path, rel: str, body: str) -> None:
    f = r / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")


def make_repo(r: Path, files: dict[str, str]) -> Path:
    r.mkdir()
    sh(r, "init", "-q")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    for k, v in files.items():
        put(r, k, v)
    sh(r, "add", ".")
    sh(r, "commit", "-qm", "init")
    return r


FOREMAN_FILES = {
    ".foreman/notion.toml": 'src = "notion/"\n',
    "bridge/a.py": "x = 1\n" * 30,
    "notion/03_a.md": "# 03 첫 편\n\n<!--\n다루는 곳: bridge/a.py\n읽은 커밋: 1a2b3c4\n-->\n\n본문 [code:bridge/a.py:2-4]. → 「04 둘째 편」\n",
    "notion/04_b.md": "<!--\n다루는 곳: bridge/\n읽은 커밋: 5d6e7f8\n-->\n# 04 둘째 편\n\n```\n[code:울타리/안.py]\n```\n",
    "portfolio/01_x.md": "# 한눈에\n\n머리 주석 없는 편 [log:a_20261117.md]\n",
    "docs/11_x.md": "# 11 설계\n\n[docs:12_y.md:3]\n",
    "log/r_20261117.md": "# 기록\n\n[code:bridge/a.py]\n",
}

INFRA_FILES = {
    ".foreman/notion.toml": 'src = "notion/"\n',
    ".foreman/docs.toml": 'records = ["docs/history/"]\npair_numbers = true\nread_commit = "set"\n\n[sets]\nnotion = "notion/"\n',
    "platform/metallb/pool.yaml": "a: 1\n",
    "notion/02_nodes.md": "<!--\n다루는 곳: platform/metallb/\n읽은 커밋: 736d833\n-->\n# 02 노드\n\n"
                          "본문 [docs:history/cluster_state_20261116.md:193-197]. → 「역할 라벨」\n",
    "notion/03_roles.md": "<!--\n다루는 곳: platform/\n읽은 커밋: 736d833\n-->\n# 03 역할 라벨\n",
    "docs/02_nodes.md": "<!--\n다루는 곳: platform/\n읽은 커밋: 736d833\n-->\n# 노드 개발자 문서\n\n→ 「역할 라벨」\n",
    "docs/history/cluster_state_20261116.md": "# 기록\n" + "줄\n" * 200,
}


def run(capsys, *argv):
    rc = docs_tool.main(list(argv))
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_head_foreman_like(tmp_path, capsys):
    r = make_repo(tmp_path / "fm", FOREMAN_FILES)
    rc, out, _ = run(capsys, "--repo", str(r), "--json", "head")
    assert rc == 0
    res = json.loads(out)["sets"]
    assert set(res) == {"docs", "notion", "portfolio"}                    # log/는 문서 묶음이 아니다
    n = {p["path"]: p for p in res["notion"]["pieces"]}
    assert n["notion/03_a.md"] == {"path": "notion/03_a.md", "title": "03 첫 편", "head": True, "covers": ["bridge/a.py"], "read": "1a2b3c4"}
    assert n["notion/04_b.md"]["covers"] == ["bridge/"] and res["notion"]["reads"] == ["1a2b3c4", "5d6e7f8"]   # FOREMAN은 편마다
    assert res["portfolio"]["no_head"] == ["portfolio/01_x.md"]
    rc, out, _ = run(capsys, "--repo", str(r), "head", "--set", "notion")
    assert rc == 0 and out.startswith("[노션 원고] notion/ 편 2") and "읽은 커밋 2가지" in out


def test_marks_foreman_like(tmp_path, capsys):
    r = make_repo(tmp_path / "fm", FOREMAN_FILES)
    rc, out, _ = run(capsys, "--repo", str(r), "--json", "marks")
    assert rc == 0
    ms = json.loads(out)["marks"]
    got = {(m["doc"], m["kind"], m["value"]) for m in ms}
    assert ("notion/03_a.md", "code", "bridge/a.py:2-4") in got
    assert ("portfolio/01_x.md", "log", "a_20261117.md") in got and ("docs/11_x.md", "docs", "12_y.md:3") in got
    assert not any(m["doc"].startswith("log/") or "울타리" in m["value"] for m in ms)      # 기록 폴더, 울타리 안은 읽지 않는다
    code = next(m for m in ms if m["kind"] == "code")
    assert (code["file"], code["from"], code["to"], code["line"]) == ("bridge/a.py", 2, 4, 8)
    x = next(m for m in ms if m["kind"] == "xref")
    assert x["refers"] == ["notion/04_b.md"]
    rc, out, _ = run(capsys, "--repo", str(r), "marks", "notion/03_a.md", "log/r_20261117.md")
    assert "notion/03_a.md:8 [code] bridge/a.py 줄 2-4" in out and "참조 「04 둘째 편」 → notion/04_b.md" in out
    assert "문서 묶음 밖이라 읽지 않았습니다: log/r_20261117.md" in out


def test_infra_like_reads_config_and_bare_xref(tmp_path, capsys):
    r = make_repo(tmp_path / "infra", INFRA_FILES)
    rc, out, _ = run(capsys, "--repo", str(r), "--json", "config")
    c = json.loads(out)
    assert rc == 0 and c["source"] == ".foreman/docs.toml"
    assert (c["records"], c["pair_numbers"], c["read_commit"]) == (["docs/history/"], True, "set")
    rc, out, _ = run(capsys, "--repo", str(r), "--json", "head")
    res = json.loads(out)["sets"]
    assert [p["path"] for p in res["docs"]["pieces"]] == ["docs/02_nodes.md"]          # docs/history/는 기록이라 뺀다
    assert res["notion"]["reads"] == ["736d833"]
    rc, out, _ = run(capsys, "--repo", str(r), "--json", "marks", "--set", "notion")
    ms = json.loads(out)["marks"]
    d = next(m for m in ms if m["kind"] == "docs")
    assert (d["file"], d["from"], d["to"]) == ("history/cluster_state_20261116.md", 193, 197)
    assert next(m for m in ms if m["kind"] == "xref")["refers"] == ["notion/03_roles.md"]   # 번호 없이 쓴 참조


def test_rev_reads_commit_not_worktree(tmp_path, capsys):
    r = make_repo(tmp_path / "fm", FOREMAN_FILES)
    put(r, "notion/03_a.md", "# 바뀐 제목\n")
    rc, out, _ = run(capsys, "--repo", str(r), "--rev", "HEAD", "--json", "head", "--set", "notion")
    assert rc == 0 and json.loads(out)["sets"]["notion"]["pieces"][0]["title"] == "03 첫 편"


def test_reads_only(tmp_path, capsys):
    r = make_repo(tmp_path / "fm", FOREMAN_FILES)
    before = sh(r, "status", "--porcelain")
    for cmd in (["head"], ["marks"], ["config"]):
        assert run(capsys, "--repo", str(r), *cmd)[0] == 0
    assert sh(r, "status", "--porcelain") == before == ""


@pytest.mark.parametrize("setup,argv,why", [
    (None, ["--repo", "{tmp}/없음", "head"], "저장소 폴더가 없습니다"),
    ("plain", ["--repo", "{tmp}/plain", "head"], "git 저장소가 아닙니다"),
    ("repo", ["--repo", "{tmp}/fm", "--rev", "nosuch", "head"], "nosuch"),
    ("broken", ["--repo", "{tmp}/fm", "config"], "docs.toml"),
])
def test_fails_loudly(tmp_path, capsys, setup, argv, why):
    if setup == "plain":
        (tmp_path / "plain").mkdir()
    elif setup in ("repo", "broken"):
        files = dict(FOREMAN_FILES)
        if setup == "broken":
            files[".foreman/docs.toml"] = "records = [\n"
        make_repo(tmp_path / "fm", files)
    rc, out, err = run(capsys, *[a.replace("{tmp}", str(tmp_path)) for a in argv])
    assert rc == 2 and out == "" and why in err


def test_outside_foreman_fails(tmp_path):
    """명령 파일만 FOREMAN 밖으로 옮겨 부르면 조용히 넘지 않고 2로 끝난다."""
    lone = tmp_path / "tools" / "docs.py"
    lone.parent.mkdir()
    lone.write_text((ROOT / "tools" / "docs.py").read_text(encoding="utf-8"), encoding="utf-8")
    p = subprocess.run([sys.executable, "-I", str(lone), "config"], capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 2 and "불러오지 못했습니다" in p.stderr
