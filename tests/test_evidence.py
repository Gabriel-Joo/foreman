"""12b 근거 확인기 · 고친 양(11-06)."""

import asyncio
import subprocess
from datetime import UTC, datetime, timedelta

from bridge import evidence as ev


def _repo(tmp_path):
    r = tmp_path / "repo"
    (r / "log").mkdir(parents=True)
    (r / "docs").mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (r / "log" / "a_result.md").write_text("하나\n둘\n셋\n", encoding="utf-8")
    (r / "docs" / "12_x.md").write_text("# 12\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "처음")
    return r, g


def test_check_text_marks_and_unsupported(tmp_path):
    r, g = _repo(tmp_path)
    sha = g("rev-parse", "--short", "HEAD")
    body = f"""# 회고

- 커밋은 49개였다 [c:{sha}] [log:a_result.md:2-3]
- 없는 커밋 [c:deadbee] · 없는 파일 [log:없음.md] · 넘는 줄 [log:a_result.md:2-9] · 설계 [docs:12_x.md]
- 디스패치는 5건이고 사람이 계획을 고친 것은 1건이다
- 짧은 줄 5
| 표 | 49 |
> 인용 5건
```
코드 [c:zzz] 99
```
"""
    out = asyncio.run(ev.check_text(body, str(r)))
    assert out["total"] == 6 and out["ok"] == 3
    whys = [b["why"] for b in out["bad"]]
    assert any(w.startswith("그 커밋이") for w in whys) and any("파일이 없습니다" in w for w in whys) and any("줄 범위" in w for w in whys)
    assert [u["line"] for u in out["unsupported"]] == [5]                   # 숫자가 있는데 근거 없는 본문 줄만(표 · 인용 · 코드 · 짧은 줄 빼고)


def test_revision_splits_draft_and_after_feedback(tmp_path):
    r, g = _repo(tmp_path)
    g("checkout", "-qb", "cc/s1")
    (r / "log" / "retro.md").write_text("\n".join(f"줄 {i}" for i in range(10)) + "\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "초안")
    feedback = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=1)
    import time
    time.sleep(2)
    (r / "log" / "retro.md").write_text("\n".join(f"줄 {i}" for i in range(8)) + "\n고친 줄\n", encoding="utf-8")
    g("commit", "-qam", "고침")
    out = asyncio.run(ev.revision(str(r), "main", "cc/s1", feedback))
    assert out["draft_lines"] == 10 and out["draft_commits"] == 1
    assert out["revision_commits"] == 1 and out["revision_lines"] == 3          # 두 줄 빼고 한 줄 더함
    assert out["ratio"] == 0.3
    none = asyncio.run(ev.revision(str(r), "main", "cc/s1", None))             # 사람이 다시 말한 적 없으면 전부 초안
    assert none["revision_lines"] == 0 and none["draft_commits"] == 2
