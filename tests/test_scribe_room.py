"""서기실(12a, 11-06) — 할 일 세기(LLM 없음) · 시킬 일 프롬프트."""

import subprocess

import pytest

from bridge import scribe_room as sr


def _repo(tmp_path, result_convention=True):
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "log").mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (r / "README.md").write_text("# x\n", encoding="utf-8")
    (r / "docs" / "11_handoff.md").write_text("# 11\n", encoding="utf-8")
    (r / "docs" / "12_scribe.md").write_text("# 12\n", encoding="utf-8")
    (r / "docs" / "style_guide.md").write_text("# 기준\n", encoding="utf-8")
    if result_convention:
        (r / "log" / "stage11_handoff_result.md").write_text("# 결과\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "처음")
    for i in range(3):
        (r / f"f{i}.txt").write_text(str(i))
        g("add", "."), g("commit", "-qm", f"c{i}")
    return r


def test_commits_since_readme(tmp_path):
    r = _repo(tmp_path)
    n, last = sr.commits_since_path(str(r), "README.md")
    assert n == 3 and last
    assert sr.commits_since_path(str(r), "없는.md") == (0, None)


def test_stages_without_result_only_with_convention(tmp_path):
    r = _repo(tmp_path)
    assert sr.stages_without_result(str(r)) == ["docs/12_scribe.md"]       # 11은 stage11_*가 있다, style_guide는 번호 없음
    r2 = _repo(tmp_path / "b", result_convention=False)
    assert sr.stages_without_result(str(r2)) == []                          # 결과 문서 관례가 없는 저장소는 세지 않는다(펫퍼민트)


@pytest.mark.parametrize("task", ["doccheck", "readme", "trim", "later"])
def test_task_prompts(task):
    p = sr.task_prompt(task, "foreman", "/repo", {"stages": "docs/12_x.md", "since": "abc", "materials": "/m/later.md"})
    assert p.startswith(f"[FOREMAN 서기 일감 — {sr.TASKS[task]['title']}] foreman")
    assert "push하지 않는다" in p and "CLAUDE.md" in p
    if task == "doccheck":
        assert "고치지 마라" in p and "docs/12_x.md" in p
    if task == "later":
        assert "/m/later.md" in p and "README.md만 고친다" in p
    with pytest.raises(ValueError):
        sr.task_prompt("publish", "foreman", "/repo")


def test_blocked_same_task_same_file_and_cap():
    """동시에 시키기(11-06) — 같은 일 · 같은 파일 · 둘 넘게는 막고, 파일이 다른 일은 같이 둔다."""
    trim = {"session_id": 194, "task": "trim", "title": "서기 — CLAUDE.md 정리"}
    later = {"session_id": 193, "task": "later", "title": "서기 — 나중에 할 일 정리"}
    assert sr.blocked("later", [trim]) is None                                # CLAUDE.md · docs/ ↔ README.md — 겹치지 않는다
    assert "이미 열려" in sr.blocked("trim", [trim])
    assert "README.md" in sr.blocked("readme", [later])                       # README 갱신 ↔ 나중에 할 일 — 같은 파일
    assert "동시에 2개까지" in sr.blocked("retro", [trim, later])
    assert sr.blocked("retro", []) is None


def test_portfolio_topics_and_blocked_per_topic(tmp_path):
    """포트폴리오 쓰기(12c) — 주제는 config/portfolio.toml 순서, 같은 주제만 막고 다른 주제는 같이 연다."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config/portfolio.toml").write_text(
        '[[topic]]\nslug = "00_overview"\ntitle = "한눈에 — 무엇"\nabout = "A"\nsources = ["README.md"]\nscreenshots = true\n\n'
        '[[topic]]\nslug = "01_loss"\ntitle = "압축 손실"\nabout = "B"\n\n[[topic]]\nslug = "../bad"\ntitle = "x"\n', encoding="utf-8")
    (tmp_path / "portfolio").mkdir()
    (tmp_path / "portfolio/01_loss.md").write_text("# x\n", encoding="utf-8")
    tps = sr.topics(str(tmp_path))
    assert [t["slug"] for t in tps] == ["00_overview", "01_loss"]                 # 이상한 slug는 버린다
    assert [t["written"] for t in tps] == [False, True] and tps[0]["screenshots"]
    assert sr.topics(str(tmp_path / "없음")) == []
    a = {"session_id": 1, "task": "portfolio", "topic": "00_overview", "title": "서기"}
    assert "이미 열려" in sr.blocked("portfolio", [a], "00_overview")
    assert sr.blocked("portfolio", [a], "01_loss") is None                       # 다른 주제 — 다른 파일
    assert sr.blocked("readme", [a]) is None
    p = sr.task_prompt("portfolio", "foreman", "/repo", {"slug": "00_overview", "title": "한눈에", "about": "A",
                                                         "sources": "`README.md`", "screenshots": "1", "siblings": ""})
    assert "portfolio/00_overview.md" in p and "> 이 글은" in p and "tools/screen.py" in p and "[t:턴]" in p
    assert "tools/screen.py" not in sr.task_prompt("portfolio", "foreman", "/repo", {"slug": "01_loss", "title": "t", "about": "B", "sources": ""})


def test_later_pattern():
    assert sr.LATER.search("이건 나중에 하자") and sr.LATER.search("일단 미루고") and not sr.LATER.search("지금 바로 해")


def test_last_change_commits_since_and_unreadable(tmp_path):
    """포트폴리오 마지막 쓴 시각 + 그 뒤 커밋 수(D2). 바꾼 적 없으면 0이고, git을 못 읽으면 0이 아니라 None(「읽지 못했습니다」)."""
    r = _repo(tmp_path)
    when, n = sr.last_change(str(r), "README.md")
    assert when and n == 3
    assert sr.last_change(str(r), "portfolio/없음.md") == (None, 0)
    assert sr.last_change(str(tmp_path / "git아님"), "README.md") == (None, None)


def test_doccheck_report_latest_and_docfix_prompt(tmp_path):
    r = _repo(tmp_path)
    assert sr.doccheck_report(str(r)) is None
    (r / "log" / "doccheck_20261110.md").write_text("a", encoding="utf-8")
    (r / "log" / "doccheck_20261111.md").write_text("b", encoding="utf-8")
    assert sr.doccheck_report(str(r)) == "doccheck_20261111.md"
    p = sr.task_prompt("docfix", "foreman", "/repo", {"report": "log/doccheck_20261111.md"})
    assert "log/doccheck_20261111.md" in p and "고치는 일이다" in p and "push하지 않는다" in p
    q = sr.task_prompt("docfix", "foreman", "/repo", {"note": "docs에 안 들어간 것 둘"})
    assert "docs에 안 들어간 것 둘" in q and "그대로 믿지 말고" in q


def test_docfix_blocked_with_readme_and_start_refuses_without_source():
    import asyncio
    from bridge.inject import Refused
    later = {"session_id": 5, "task": "later", "title": "서기"}
    assert "README.md" in sr.blocked("docfix", [later])                        # README를 고치는 일과 같이 못 연다
    for topic, note in ((None, None), ("../etc/passwd", None), ("doccheck_x/../y.md", "a")):
        with pytest.raises(Refused):
            asyncio.run(sr.start(None, None, "foreman", "docfix", topic, note))
