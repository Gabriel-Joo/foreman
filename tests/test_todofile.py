"""docs/TODO.md 읽고 쓰기(11-17 문서 정리 E, bridge/todofile.py). 두 꼴 읽기, 다음 번호, 30일 셈, (todo:번호) 커밋, 커밋 안전 장치.

임시 git 저장소에서만 돈다(실제 저장소에 커밋하지 않는다).
"""
import asyncio
import subprocess
from datetime import date, datetime

import pytest

from bridge import todofile as tf

FOREMAN = """# TODO, 남은 일

꼴과 번호: 항목은 `- **foreman-N** 제목 (올린 날)`, 다음 줄에 내용.

## 1. 바탕

- **foreman-1** 재시작 추세 감시 (2026-11-15)
  이벤트 이름만 정의돼 있다.
  나온 곳: `notion/00_foreman.md` 61
- **foreman-3** 재부팅 확인 (2026-09-01)
  재부팅은 사람이 시킬 때만.

## 2. 세션

- **foreman-2** 끼어든 입력 (2026-11-16)
  나온 곳: p:3
"""

INFRA = """# TODO: 남은 일

꼴은 `- infra-번호 (올린 날) 할 일 → 어디서 나왔나`이다.

## 가용성

- infra-1 (2026-11-16) 옛 Harbor PVC 다섯 지우기. 사람이 판단한다 → 08 1-2절
- infra-7 (2026-10-01) runshoes MySQL 정기 백업 → 08 1-4절
"""


def test_parse_two_styles():
    xs = tf.parse(FOREMAN)
    assert [x.id for x in xs] == ["foreman-1", "foreman-3", "foreman-2"]
    assert xs[0].title == "재시작 추세 감시" and xs[0].date == date(2026, 11, 15) and xs[0].bold
    assert FOREMAN.split("\n")[xs[0].end].startswith("- **foreman-3**")       # 들여 쓴 내용 줄까지 한 항목
    ys = tf.parse(INFRA)
    assert [y.id for y in ys] == ["infra-1", "infra-7"]
    assert ys[0].title == "옛 Harbor PVC 다섯 지우기. 사람이 판단한다" and not ys[0].bold     # 「→ 나온 곳」은 제목이 아니다
    assert tf.parse("# 제목\n\n- [ ] 번호 없는 체크 목록\n| 표 | 줄 |\n") == []
    assert tf.prefix_of(FOREMAN, xs) == "foreman" and tf.prefix_of(INFRA, ys) == "infra"
    assert tf.prefix_of("꼴은 `- infra-번호 (올린 날)`\n", []) == "infra"                    # 항목이 없으면 머리 글에서
    assert tf.prefix_of("- [ ] 체크\n", []) is None


def test_entry_and_number():
    assert tf.max_number("foreman", FOREMAN) == 3
    assert tf.max_number("foreman", FOREMAN, "-- **foreman-12** 지운 것") == 12              # 지운 번호도 다시 쓰지 않는다
    assert tf.max_number("infra", FOREMAN) == 0
    d = date(2026, 11, 17)
    bold = tf.entry_lines("foreman", 4, "질문 카드 접기\n\n답한 뒤 한 줄로", d, "포스트잇 p:9", True)
    assert bold == ["- **foreman-4** 질문 카드 접기 (2026-11-17)", "  답한 뒤 한 줄로", "  나온 곳: 포스트잇 p:9"]
    plain = tf.entry_lines("infra", 8, "백업 한 벌 더\n다른 디스크에", d, "포스트잇 p:9", False)
    assert plain == ["- infra-8 (2026-11-17) 백업 한 벌 더 다른 디스크에 → 포스트잇 p:9"]
    with pytest.raises(tf.TodoError):
        tf.entry_lines("infra", 8, "  \n ", d, "x", False)
    # 「포스트잇에서 보낸 것」 절이 없으면 끝에 만들고, 있으면 그 절 끝에 더한다
    once = tf.add_entry(INFRA, plain)
    assert once.endswith(f"\n\n{tf.SECTION}\n\n{plain[0]}\n")
    twice = tf.add_entry(once, ["- infra-9 (2026-11-17) 둘째 → 포스트잇 p:10"])
    assert twice.count(tf.SECTION) == 1 and twice.endswith(f"{plain[0]}\n- infra-9 (2026-11-17) 둘째 → 포스트잇 p:10\n")
    mid = tf.add_entry(f"# T\n\n{tf.SECTION}\n\n- infra-1 (2026-11-16) a → b\n\n## 다음 절\n\n- infra-2 (2026-11-16) c → d\n", plain)
    assert "- infra-1 (2026-11-16) a → b\n" + plain[0] + "\n\n## 다음 절" in mid
    assert [x.id for x in tf.parse(mid)] == ["infra-1", "infra-8", "infra-2"]


def test_remove_and_entry_text():
    out = tf.remove_entry(FOREMAN, "foreman-1")
    assert "foreman-1" not in out and "이벤트 이름만" not in out and "- **foreman-3** 재부팅 확인" in out
    assert tf.entry_text(FOREMAN, "foreman-3") == "- **foreman-3** 재부팅 확인 (2026-09-01)\n재부팅은 사람이 시킬 때만."
    assert tf.entry_text(FOREMAN, "foreman-9") is None
    with pytest.raises(tf.TodoError, match="없습니다"):
        tf.remove_entry(FOREMAN, "foreman-9")


def test_refs_in():
    assert tf.refs_in("fix: 백업을 넣음 (todo:infra-7)") == ["infra-7"]
    assert tf.refs_in("본문\n(todo: infra-7, infra-12)\n") == ["infra-7", "infra-12"]
    assert tf.refs_in("todo:infra-7 괄호 없음") == [] and tf.refs_in("") == []


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout


def _repo(tmp_path, text=INFRA):
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main", str(r))
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    if text is not None:
        (r / "docs" / "TODO.md").write_text(text, encoding="utf-8")
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


def test_view_counts_old_and_commit_done(tmp_path):
    r = _repo(tmp_path)
    v = tf.view(str(r), now=datetime(2026, 11, 17))
    assert v["exists"] and v["prefix"] == "infra" and v["n"] == 2 and v["old"] == 1 and v["done"] == 0
    old = {i["id"]: i for i in v["items"]}
    assert old["infra-7"]["old"] and old["infra-7"]["days"] == 47 and not old["infra-1"]["old"]
    assert tf.view(str(r), now=datetime(2026, 10, 31))["old"] == 0                              # 30일은 넘어야 한다(30일째는 아님)
    (r / "a.txt").write_text("b\n", encoding="utf-8")
    _git(r, "commit", "-q", "-am", "ops: 백업을 넣음", "-m", "(todo:infra-7)")
    v = tf.view(str(r), now=datetime(2026, 11, 17))
    assert v["done"] == 1 and {i["id"]: i for i in v["items"]}["infra-7"]["done_by"]["subject"] == "ops: 백업을 넣음"
    # 항목을 저절로 지우지 않는다. 여전히 파일에 있다
    assert "infra-7" in (r / "docs" / "TODO.md").read_text(encoding="utf-8")


def test_view_missing_and_unnumbered(tmp_path):
    assert tf.view(None)["error"] == "이 프로젝트의 저장소를 찾지 못했습니다"
    r = _repo(tmp_path, None)
    v = tf.view(str(r))
    assert not v["exists"] and v["error"] == "이 저장소에는 docs/TODO.md가 없습니다"
    r2 = _repo(tmp_path / "b", "# TODO\n\n- [ ] 체크 목록 꼴\n")
    v2 = tf.view(str(r2))
    assert v2["exists"] and v2["n"] == 0 and "번호 붙은 항목이 없습니다" in v2["error"]
    with pytest.raises(tf.TodoError, match="번호 꼴"):
        asyncio.run(tf.add(str(r2), "새 일", "포스트잇 p:1", "왜"))
    with pytest.raises(tf.TodoError, match="없습니다"):
        asyncio.run(tf.add(str(r), "새 일", "포스트잇 p:1", "왜"))


def test_add_commits_only_todo_and_skips_used_numbers(tmp_path):
    r = _repo(tmp_path)
    # 지운 번호(infra-9)는 기록에 남아 다시 쓰지 않는다
    (r / "docs" / "TODO.md").write_text(INFRA + "- infra-9 (2026-11-16) 끝난 것 → x\n", encoding="utf-8")
    _git(r, "commit", "-q", "-am", "docs: 더함")
    (r / "docs" / "TODO.md").write_text(INFRA, encoding="utf-8")
    _git(r, "commit", "-q", "-am", "docs: 지움 (todo:infra-9)")
    # 다른 세션이 올려 둔 스테이지와 고치는 중인 파일은 그대로 남는다
    (r / "a.txt").write_text("남의 변경\n", encoding="utf-8")
    _git(r, "add", "a.txt")
    (r / "b.txt").write_text("추적 안 함\n", encoding="utf-8")
    res = asyncio.run(tf.add(str(r), "다른 디스크에 백업\n둘째 줄", "포스트잇 p:12", "포스트잇 #12에서 보냄", date(2026, 11, 17)))
    assert res["value"] == "infra-10"
    assert _git(r, "log", "-1", "--format=%s") == "docs: TODO에 infra-10 항목을 더함\n"
    assert _git(r, "show", "--name-only", "--format=", "HEAD").split() == ["docs/TODO.md"]
    assert _git(r, "diff", "--cached", "--name-only").split() == ["a.txt"]                     # 남의 스테이지는 그대로
    assert "- infra-10 (2026-11-17) 다른 디스크에 백업 둘째 줄 → 포스트잇 p:12" in _git(r, "show", "HEAD:docs/TODO.md")
    assert _git(r, "status", "--porcelain", "--", "docs/TODO.md") == ""
    # 지우기도 그 파일만
    res2 = asyncio.run(tf.remove(str(r), "infra-1", "커밋이 끝냈다고 함"))
    assert res2["value"] == "infra-1" and "infra-1 " not in _git(r, "show", "HEAD:docs/TODO.md")
    assert _git(r, "log", "-1", "--format=%s") == "docs: TODO에서 infra-1 항목을 지움\n"


def test_commit_refuses_when_todo_dirty_or_detached(tmp_path):
    r = _repo(tmp_path)
    (r / "docs" / "TODO.md").write_text(INFRA + "- infra-20 (2026-11-17) 고치는 중 → x\n", encoding="utf-8")
    with pytest.raises(tf.TodoError, match="커밋 안 된 변경이 있어 건드리지 않았습니다"):
        asyncio.run(tf.add(str(r), "새 일", "p", "왜"))
    assert "infra-20" in (r / "docs" / "TODO.md").read_text(encoding="utf-8")                  # 고치던 글은 그대로
    _git(r, "checkout", "-q", "--", "docs/TODO.md")
    _git(r, "checkout", "-q", "--detach")
    with pytest.raises(tf.TodoError, match="브랜치 위에 있지 않아"):
        asyncio.run(tf.add(str(r), "새 일", "p", "왜"))
    _git(r, "checkout", "-q", "main")
    # 커밋이 실패하면(여기서는 훅이 거부) 그 파일을 되돌리고 까닭을 올린다
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 훅이 막음 >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    with pytest.raises(tf.TodoError, match="커밋하지 못했습니다: 훅이 막음"):
        asyncio.run(tf.add(str(r), "새 일", "p", "왜"))
    assert _git(r, "status", "--porcelain", "--", "docs/TODO.md") == ""
