import asyncio
import subprocess

from bridge import pointers as ptr
from bridge.handoff import REQUEST_PROMPT_V2, inject_prompt, request_prompt

BODY = """## 지금 상태
main 3f2a1b0
## 다음 할 일
1. 압축 알림 b
## 읽을 곳
- `docs/a.md` — 설계 전체
- `docs/a.md:2-3` — 둘째 줄부터
- CLAUDE.md 「작업 규칙」 — 금지 항목
- docs/없음.md — 없는 파일
- docs/a.md:9-12 — 넘는 범위
- CLAUDE.md 「없는 절」 — 없는 절
- 그냥 글
"""


def test_parse_shapes():
    ps = ptr.parse(BODY)
    assert ptr.is_v2(BODY) and not ptr.is_v2("## 주의\n- x")
    assert [(p.path, p.start, p.end, p.section) for p in ps[:3]] == [
        ("docs/a.md", None, None, None), ("docs/a.md", 2, 3, None), ("CLAUDE.md", None, None, "작업 규칙")]
    assert ps[0].why == "설계 전체"
    assert ps[-1].path == "" and not ps[-1].ok        # 모양이 안 맞는 줄도 빠뜨리지 않는다


def test_check_and_reads(tmp_path):
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("하나\n둘\n셋\n", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("# 규칙\n## 작업 규칙\n- x\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"], check=True)
    ps = asyncio.run(ptr.check(ptr.parse(BODY), str(repo)))
    assert [p.ok for p in ps] == [True, True, True, False, False, False, False]
    assert ps[3].problem == "파일이 없습니다" and "줄 범위" in ps[4].problem and "찾지 못했습니다" in ps[5].problem
    assert ps[0].commits_since == 0 and not ps[0].stale
    r = ptr.reads(ps[:3], str(repo), [str(repo / "docs" / "a.md"), "/tmp/다른것"])
    # 맨 위 CLAUDE.md는 Read 없이도 세션에 들어가 있다 — 읽음으로 세고 auto로 따로 보인다
    assert r == {"total": 3, "read": 3, "missing": [], "auto": ["CLAUDE.md"]}
    assert ptr.reads(ps[:1], str(repo), [])["missing"] == ["docs/a.md"]


def test_reads_same_file_across_worktrees(tmp_path):
    """원본과 .worktrees/<이름>의 같은 상대 경로는 같은 파일로 센다(11-06 — 합치기 전 worktree에서 읽은 것)."""
    main = tmp_path / "foreman"
    wt = main / ".worktrees" / "foreman-2"
    for root in (main, wt):
        (root / "log").mkdir(parents=True)
        (root / "log" / "c.md").write_text("x\n", encoding="utf-8")
    ps = ptr.parse("## 읽을 곳\n- `log/c.md` — 결과\n")
    assert ptr.reads(ps, str(main), [str(wt / "log" / "c.md")])["missing"] == []          # 원본 세션이 worktree 경로로 읽음
    assert ptr.reads(ps, str(wt), [str(main / "log" / "c.md")])["missing"] == []          # worktree 세션이 원본 경로로 읽음
    other = main / ".worktrees" / "foreman-3" / "log" / "c.md"
    assert ptr.reads(ps, str(wt), [str(other)])["missing"] == []                           # 다른 worktree도 같은 저장소
    assert ptr.reads(ps, str(main), [str(tmp_path / "다른" / "log" / "c.md")])["missing"] == ["log/c.md"]


def test_v2_prompts():
    assert "## 읽을 곳" in request_prompt("abc123") and "<<<FOREMAN-HANDOFF r=abc123>>>" in request_prompt("abc123")
    assert "## 읽을 곳" not in request_prompt("abc123", "v1")
    assert REQUEST_PROMPT_V2.count("{max_body}") == 1
    assert "먼저 아래 「읽을 곳」을 모두 Read로" in inject_prompt("abc123", "s", BODY)
    assert "Read로" not in inject_prompt("abc123", "s", "## 주의\n- x")      # 1판 요약은 1판 문구
