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
    assert r == {"total": 3, "read": 2, "missing": ["CLAUDE.md"]}


def test_v2_prompts():
    assert "## 읽을 곳" in request_prompt("abc123") and "<<<FOREMAN-HANDOFF r=abc123>>>" in request_prompt("abc123")
    assert "## 읽을 곳" not in request_prompt("abc123", "v1")
    assert REQUEST_PROMPT_V2.count("{max_body}") == 1
    assert "먼저 아래 「읽을 곳」을 모두 Read로" in inject_prompt("abc123", "s", BODY)
    assert "Read로" not in inject_prompt("abc123", "s", "## 주의\n- x")      # 1판 요약은 1판 문구
