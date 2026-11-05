"""인계 2판 ① 문서로 옮기기(11-05) — 요청문 · 목록 풀기 · 목적지 확인 · 사람 고침 · git 확인. DB · tmux 없이."""

import subprocess
import time

import pytest

from bridge import promote as pm
from bridge.assembler import Assembler
from bridge.inject import Refused

V2 = """## 지금 상태
- main
## 문서와 다른 지금
- 시험 세션은 끝낸 뒤 hidden_reason='test'로 숨겨 왔음
## 읽을 곳
- `CLAUDE.md` 「작업 규칙」 — 금지"""


def test_prompts_are_handoff_turns_and_carry_diff():
    p = pm.list_prompt("abc123", pm.diff_section(V2), 42)
    assert p.startswith("[FOREMAN 인계 요청 r=abc123] 대화 결정 문서에 적기 1/2")
    assert "<<<FOREMAN-PROMOTE r=abc123>>>" in p and "<<<END r=abc123>>>" in p
    assert "인계(#42)" in p and "  > - 시험 세션은 끝낸 뒤" in p
    assert Assembler._origin({}, p) == "handoff"          # 보통 응답 · 알림과 가른다
    assert "인계(#" not in pm.list_prompt("abc123")
    w = pm.write_prompt("def456", [{"id": 2, "kind": "기준", "what": "x", "quote": "", "dest": "CLAUDE.md",
                                    "section": "작업 규칙", "why": "안 보냄", "state": "approved"}])
    assert Assembler._origin({}, w) == "handoff" and "<<<FOREMAN-PROMOTED r=def456>>>" in w
    assert '"id": 2' in w and "안 보냄" not in w and "인계 전 결정 기록" in w


def test_diff_section_empty_is_none():
    assert pm.diff_section("## 문서와 다른 지금\n없음\n## 읽을 곳\n- `a.md` — x") is None
    assert pm.diff_section("## 지금 상태\nx") is None


def test_extract_takes_last_block_for_req():
    t = "<<<FOREMAN-PROMOTE r=aaaaaa>>>\n[]\n<<<END r=aaaaaa>>>\n다시:\n<<<FOREMAN-PROMOTE r=aaaaaa>>>\n[1]\n<<<END r=aaaaaa>>>"
    assert pm.extract(t, "FOREMAN-PROMOTE", "aaaaaa") == "[1]"
    assert pm.extract(t, "FOREMAN-PROMOTE", "bbbbbb") is None
    assert pm.extract(t, "FOREMAN-PROMOTED", "aaaaaa") is None


def test_parse_items_normalizes():
    items = pm.parse_items('[{"kind":"금지","what":"시험 세션은 끝낸 뒤 숨긴다","quote":"q","dest":"CLAUDE.md",'
                           '"section":"작업 규칙","why":"매번"}, {"what":"그때뿐","dest":"drop","section":"x"},'
                           '{"kind":"이상함","what":"메모리로","dest":"memory","section":"무시"}, "줄", {"what":""}]')
    assert [i["id"] for i in items] == [1, 2, 3]
    assert items[0]["state"] == "pending" and items[0]["section"] == "작업 규칙"
    assert items[1]["state"] == "dropped" and items[1]["section"] == ""
    assert items[2]["kind"] == "결정" and items[2]["section"] == ""
    with pytest.raises(Refused):
        pm.parse_items("목록 아님")
    with pytest.raises(Refused):
        pm.parse_items('{"what": "배열 아님"}')
    assert pm.parse_items("[]") == []


def test_check_dest(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# x\n## 작업 규칙\n- a\n", encoding="utf-8")
    ck = lambda d, s="": pm.check_dest({"dest": d, "section": s}, str(tmp_path))  # noqa: E731
    assert ck("CLAUDE.md", "작업 규칙") == {"ok": True, "problem": None, "note": None}
    assert ck("CLAUDE.md", "없는 절")["note"] == "새 절입니다"
    assert ck("docs/new.md")["note"] == "새 파일입니다"
    assert ck("memory")["ok"] and ck("drop")["ok"]
    for bad in ("/etc/passwd.md", "../x.md", "~/x.md", "config/notify.toml", ""):
        assert not ck(bad)["ok"], bad
    assert not pm.check_dest({"dest": "CLAUDE.md"}, None)["ok"]


def test_merge_edits_only_human_fields():
    items = pm.parse_items('[{"what":"원래","quote":"원문","dest":"CLAUDE.md","section":"작업 규칙","why":"w"},'
                           '{"what":"둘","dest":"docs/a.md","section":"s"}]')
    out = pm.merge_edits(items, [{"id": 1, "what": "고침", "quote": "바꾸려 함", "state": "approved", "dest": "docs/b.md"},
                                 {"id": 2, "dest": "drop", "state": "approved"}, {"id": 9, "state": "approved"}])
    assert out[0]["what"] == "고침" and out[0]["quote"] == "원문" and out[0]["dest"] == "docs/b.md"
    assert out[0]["state"] == "approved" and out[0]["section"] == "작업 규칙"
    assert out[1]["state"] == "dropped" and out[1]["section"] == ""        # 버림은 승인될 수 없다
    assert items[0]["what"] == "원래"                                       # 원본은 그대로


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "CLAUDE.md").write_text("## 작업 규칙\n", encoding="utf-8")
    (r / "README.md").write_text("x\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "처음")
    return r


def _commit(r, msg, **files):
    for k, v in files.items():
        (r / k).write_text(v, encoding="utf-8")
        _git(r, "add", k)
    _git(r, "commit", "-qm", msg)
    return _git(r, "rev-parse", "HEAD")


A = [{"id": 1, "dest": "CLAUDE.md", "state": "approved"}]


async def test_verify_ok_and_fallback_without_block(repo):
    base = _git(repo, "rev-parse", "HEAD")
    c = _commit(repo, "인계 전 결정 기록: 시험 세션 숨김", **{"CLAUDE.md": "## 작업 규칙\n- 숨긴다\n"})
    r = await pm.verify(str(repo), base, {"commit": c[:10], "files": ["CLAUDE.md"]}, A, time.time())
    assert r["ok"] and r["commit"] == c and r["files"] == ["CLAUDE.md"]
    r = await pm.verify(str(repo), base, None, A, time.time())            # 결과 블록이 없어도 커밋을 찾는다
    assert r["ok"] and r["commit"] == c


async def test_verify_catches_wrong_files_head_and_missing(repo):
    base = _git(repo, "rev-parse", "HEAD")
    r = await pm.verify(str(repo), base, {"commit": ""}, A, time.time())
    assert not r["ok"] and any("커밋이 없습니다" in p for p in r["problems"])
    c = _commit(repo, "인계 전 결정 기록: x", **{"CLAUDE.md": "a\n", "README.md": "몰래\n"})
    r = await pm.verify(str(repo), base, {"commit": c}, A, time.time())
    assert not r["ok"] and any("README.md" in p for p in r["problems"])
    c2 = _commit(repo, "다른 일", **{"CLAUDE.md": "b\n"})
    r = await pm.verify(str(repo), c, {"commit": c2}, A, time.time())
    assert not r["ok"] and any("머리" in p for p in r["problems"])
    r = await pm.verify(str(repo), c2, {"commit": base}, A, time.time())   # 요청 전 커밋
    assert not r["ok"] and any("요청 전" in p for p in r["problems"])
    two = A + [{"id": 2, "dest": "docs/a.md", "state": "approved"}]
    c3 = _commit(repo, "인계 전 결정 기록: y", **{"CLAUDE.md": "c\n"})
    r = await pm.verify(str(repo), c2, {"commit": c3}, two, time.time())
    assert not r["ok"] and any("docs/a.md" in p for p in r["problems"])
    r = await pm.verify(str(repo), c2, {"commit": c3, "skipped": [{"id": 2, "why": "이미 있음"}]}, two, time.time())
    assert r["ok"]                                                         # 이유를 단 건너뜀은 괜찮다


async def test_verify_memory(repo, tmp_path):
    base = _git(repo, "rev-parse", "HEAD")
    mem = [{"id": 1, "dest": "memory", "state": "approved"}]
    t0 = time.time()
    r = await pm.verify(str(repo), base, {"memory": []}, mem, t0)
    assert not r["ok"] and "메모리" in r["problems"][0]
    f = tmp_path / "m.md"
    f.write_text("x", encoding="utf-8")
    r = await pm.verify(str(repo), base, {"memory": [str(f)]}, mem, t0)
    assert r["ok"] and r["commit"] is None
