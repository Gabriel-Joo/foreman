"""합치기 카드의 「문서 점검」 한 줄(11-17 사용자 결정, bridge/mergeprep.py `doc_check`, `check_line`). tmp 가짜 저장소로.

그 브랜치 판으로 돌린 문서 점검의 틀린 것을 세고, 이 브랜치로 새로 생긴 것과 갈라진 곳에 원래 있던 것을 가른다.
못 돌렸으면 0으로 보이지 않고 그 말이 남는다.
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from bridge import mergeprep as mp


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


def head(covers: str, read: str) -> str:
    return f"<!--\n다루는 곳: {covers}\n읽은 커밋: {read}\n-->\n"


def make(tmp_path: Path) -> tuple[Path, str]:
    """깨끗한 저장소: 원고 한 편이 코드와 .foreman/을 덮고 근거도 맞다. 둘째 값은 읽은 커밋."""
    r = tmp_path / "proj"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@t")
    sh(r, "config", "user.name", "t")
    put(r, ".foreman/notion.toml", 'src = "notion/"\n')
    put(r, "bridge/a.py", "1\n2\n")
    c0 = commit(r)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0[:7]) + "# 01 가\n\n두 줄이다 [code:bridge/a.py:1-2].\n")
    commit(r, "원고")
    return r, c0[:7]


def branch(r: Path, name: str = "cc/w") -> None:
    sh(r, "checkout", "-q", "-b", name)


def back(r: Path) -> None:
    sh(r, "checkout", "-q", "main")


def test_clean_branch_counts_zero(tmp_path):
    r, _ = make(tmp_path)
    branch(r)
    put(r, "bridge/a.py", "1\n2\n3\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert c == {"total": 0, "new": 0, "old": 0, "lines": []}
    assert mp.check_line(c) == "문서 점검, 이 브랜치로 새로 생긴 틀린 것 0" and not mp._check_bad(c)


def test_new_error_is_counted_and_shown(tmp_path):
    """새 파일이 어느 편의 다루는 곳에도 안 들면(535가 test_docsync_last.py에서 본 일) 그 브랜치에서 바로 보인다."""
    r, _ = make(tmp_path)
    branch(r)
    put(r, "tests/test_new.py", "x\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert (c["total"], c["new"], c["old"]) == (1, 1, 0)
    assert "덮기 밖: tests/test_new.py" in c["lines"][0]
    assert mp.check_line(c) == "문서 점검, 이 브랜치로 새로 생긴 틀린 것 1" and mp._check_bad(c)


def test_old_errors_are_split_from_new(tmp_path):
    """main에 원래 있던 틀림(근거 파일이 없음)은 `old`, 브랜치가 더한 것만 `new`. 줄이 밀려도 같은 틀림은 같은 것이다."""
    r, c0 = make(tmp_path)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0) + "# 01 가\n\n두 줄이다 [code:bridge/a.py:1-2]. 없다 [code:bridge/none.py].\n")
    commit(r, "원래 틀림")
    branch(r)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0) + "# 01 가\n\n앞에 한 줄 더.\n\n두 줄이다 [code:bridge/a.py:1-2]. 없다 [code:bridge/none.py].\n")
    put(r, "tests/test_new.py", "x\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert (c["total"], c["new"], c["old"]) == (2, 1, 1)
    assert "tests/test_new.py" in c["lines"][0]
    assert mp.check_line(c) == "문서 점검, 이 브랜치로 새로 생긴 틀린 것 1, 원래 있던 것 1"


def test_only_old_errors_is_not_bad(tmp_path):
    r, c0 = make(tmp_path)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0) + "# 01 가\n\n없다 [code:bridge/none.py].\n")
    commit(r, "원래 틀림")
    branch(r)
    put(r, "bridge/a.py", "1\n2\n3\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert (c["new"], c["old"]) == (0, 1) and not mp._check_bad(c)
    assert mp.check_line(c).endswith("0, 원래 있던 것 1")


def test_branch_fixing_an_old_error_is_not_negative(tmp_path):
    r, c0 = make(tmp_path)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0) + "# 01 가\n\n없다 [code:bridge/none.py].\n")
    commit(r, "원래 틀림")
    branch(r)
    put(r, "notion/01_a.md", head("bridge/a.py, .foreman/", c0) + "# 01 가\n\n고쳤다.\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert (c["total"], c["new"], c["old"]) == (0, 0, 0)


def test_lines_are_capped_but_count_is_full(tmp_path):
    r, _ = make(tmp_path)
    branch(r)
    for i in range(mp.CHECK_SHOW + 3):
        put(r, f"tests/test_n{i}.py", "x\n")
    commit(r)
    back(r)
    c = mp.doc_check(str(r), "main", "cc/w")
    assert c["new"] == mp.CHECK_SHOW + 3 and len(c["lines"]) == mp.CHECK_SHOW


def test_check_that_cannot_run_is_not_zero(tmp_path):
    """브랜치가 없거나 설정이 깨지면 0이 아니라 못 돌렸다는 말(조용한 고장)."""
    r, _ = make(tmp_path)
    c = mp.doc_check(str(r), "main", "cc/none")
    assert "new" not in c and c["error"].startswith("점검을 돌리지 못했습니다(")
    assert mp.check_line(c) == c["error"] and mp._check_bad(c)
    branch(r)
    put(r, ".foreman/docs.toml", "read_commit = 'each'\n")
    commit(r)
    back(r)
    c2 = mp.doc_check(str(r), "main", "cc/w")
    assert "error" in c2 and "read_commit" in c2["error"]


def test_old_card_without_check_shows_nothing():
    assert mp.check_line(None) == "" and mp.check_line({}) == "" and not mp._check_bad(None)


def test_card_msg_carries_check_line():
    """관리자 카드 글에 한 줄과 처음 몇 줄. 새 것이 없으면 줄만, 못 돌렸으면 경고."""
    m = mp.MergePrep.__new__(mp.MergePrep)
    m.cfg = SimpleNamespace(rule=lambda p: SimpleNamespace(squash=False), approver_of=lambda p: "manager", keep_docs_h=48)
    c = SimpleNamespace(sid=7, title="t", project="p", branch="cc/w", ahead=1, files=["a"], conflict=[], ff=True, base="main", behind=0,
                        live=False, asks=None, auto_why=None, rule_files=[], rule_files_error=None, human_why=[],
                        docs={"docs": [], "check": {"total": 1, "new": 1, "old": 0, "lines": ["덮기 밖: x"]}})
    s = m._card_msg(c)
    assert "⚠ 문서 점검, 이 브랜치로 새로 생긴 틀린 것 1." in s and "새 틀림: 덮기 밖: x." in s
    c.docs = {"docs": [], "check": {"error": "점검을 돌리지 못했습니다(x)"}}
    assert "⚠ 점검을 돌리지 못했습니다(x)." in m._card_msg(c)
    c.docs = {"docs": [], "check": {"total": 0, "new": 0, "old": 0, "lines": []}}
    s = m._card_msg(c)
    assert "문서 점검, 이 브랜치로 새로 생긴 틀린 것 0." in s and "⚠ 문서 점검" not in s
