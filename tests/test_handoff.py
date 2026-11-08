"""세션 인계(11-05) — 표지 꺼내기 · 분량 줄이기 · 트랜스크립트 자리 · 압축 요약. DB · tmux 없이."""

import json

from bridge import handoff as h
from bridge.assembler import Assembler


def _w(p, *objs):
    with open(p, "a", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n")


def _asst(t, side=False):
    return {"type": "assistant", "isSidechain": side, "message": {"content": [{"type": "text", "text": t}]}}


def test_prompt_has_markers_and_origin():
    p = h.request_prompt("7f3a9c")
    assert p.startswith("[FOREMAN 인계 요청 r=7f3a9c]")
    assert "<<<FOREMAN-HANDOFF r=7f3a9c>>>" in p and "<<<END r=7f3a9c>>>" in p
    wrapped = '\n\n<pasted_content id="ab12">\n' + p + '\n</pasted_content id="ab12">\n'
    assert Assembler._origin({}, wrapped) == "handoff"           # 여러 줄이라 감싸여 온다
    assert Assembler._origin({}, h.inject_prompt("7f3a9c", "c5320140", "본문")) == "handoff_in"
    assert Assembler._origin({}, "보통 입력") == "human"


def test_wt_block_only_for_worktree(tmp_path):
    """받는 세션이 worktree에서 떴으면 그 사실(브랜치 · push 안 함)을 붙인다 — 원본 폴더 · 없음이면 빈 글(11-09)."""
    repo = tmp_path / "foreman"
    (repo / ".worktrees" / "foreman-2").mkdir(parents=True)
    b = h.wt_block(str(repo / ".worktrees" / "foreman-2"))
    assert b.startswith("## 이 세션이 뜬 자리") and "`cc/foreman-2`" in b and "push하지 않는다" in b
    assert h.wt_block(str(repo)) == "" and h.wt_block(None) == ""
    # 인계 글로 감싸도 맨 앞 표지는 그대로(받은 세션 판정 handoff_in)
    assert Assembler._origin({}, h.inject_prompt("7f3a9c", "c5320140", b + "본문")) == "handoff_in"


def test_will_worktree_replace_excludes_old_session(tmp_path):
    """새 세션으로 옮기기(replace)는 옛 세션을 세지 않는다 — 옛 세션 하나뿐이면 원본 폴더, 다른 세션이 더 있으면 worktree(11-09)."""
    import os
    from types import SimpleNamespace
    repo, sd = tmp_path / "foreman", tmp_path / "sessions"
    repo.mkdir()
    sd.mkdir()
    old, other = "a" * 8 + "-0000-0000-0000-000000000001", "b" * 8 + "-0000-0000-0000-000000000002"
    (sd / f"{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "sessionId": old, "cwd": str(repo)}))
    me = SimpleNamespace(sessions_dir=str(sd), project_of=lambda c: ("foreman" if str(c).startswith(str(repo)) else None,))
    ww = lambda ex=None: h.HandoffManager.will_worktree(me, str(repo), ex)   # noqa: E731
    assert ww() is True and ww(old) is False                          # 옛 세션 하나뿐 — 옮기기면 원본 폴더
    (sd / f"{os.getppid()}.json").write_text(json.dumps({"pid": os.getppid(), "sessionId": other,
                                                         "cwd": str(repo / ".worktrees" / "foreman-2")}))
    assert ww(old) is True                                            # 다른 세션(worktree 안이라도 같은 프로젝트)이 더 있다


def test_extract_only_from_assistant_and_matching_req(tmp_path):
    p = tmp_path / "t.jsonl"
    _w(p, {"type": "user", "message": {"content": h.request_prompt("aaaaaa")}})   # 요청에도 표지가 있다 — 보지 않는다
    off = 0
    _w(p, _asst("<<<FOREMAN-HANDOFF r=bbbbbb>>>\n다른 요청\n<<<END r=bbbbbb>>>"),
       _asst("<<<FOREMAN-HANDOFF r=aaaaaa>>>\n서브에이전트 글\n<<<END r=aaaaaa>>>", side=True),
       _asst("정리했습니다.\n<<<FOREMAN-HANDOFF r=aaaaaa>>>\n## 한 일\n- x\n<<<END r=aaaaaa>>>\n끝."))
    texts = h.assistant_text(p, off)
    assert h.extract_block(texts, "aaaaaa") == "## 한 일\n- x"
    assert h.extract_block(texts, "cccccc") is None
    assert "서브에이전트 글" not in texts


def test_extract_takes_last_pair():
    t = "<<<FOREMAN-HANDOFF r=aaaaaa>>>\n초안\n<<<END r=aaaaaa>>>\n고쳐서 다시:\n<<<FOREMAN-HANDOFF r=aaaaaa>>>\n최종\n<<<END r=aaaaaa>>>"
    assert h.extract_block(t, "aaaaaa") == "최종"


def test_fit_body_keeps_open_items_whole():
    body = "\n".join([
        "## 목표 · 맥락", "맥락 " * 2000,
        "## 한 일", "한일 " * 2000,
        "## 진행 중 · 미완", "미완-끝까지",
        "## 다음 할 일", "다음 " * 300 + "다음-끝",
        "## 주의", "주의-끝",
    ])
    out, cut = h.fit_body(body, 8000, "/x/full.md")
    assert cut and len(out) <= 8400
    for keep in ("미완-끝까지", "다음-끝", "주의-끝", "/x/full.md"):
        assert keep in out
    assert "…(줄임)" in out
    assert h.fit_body("짧다", 8000) == ("짧다", False)


def test_transcript_path():
    p = h.transcript_path("/home/u/AI_programming/run.shoes", "abc")
    assert p.endswith("/.claude/projects/-home-u-AI-programming-run-shoes/abc.jsonl")


def test_compact_body(tmp_path):
    p = tmp_path / "t.jsonl"
    _w(p, {"type": "user", "isCompactSummary": True, "message": {"content": "옛 압축"}},
       {"type": "user", "isCompactSummary": True, "message": {"content": "새 압축 요약"}},
       {"type": "user", "message": {"content": "압축 뒤 지시"}},
       {"type": "user", "isMeta": True, "message": {"content": "메타"}},
       _asst("마지막 답"))
    b = h.compact_body(p)
    assert "새 압축 요약" in b and "옛 압축" not in b and "압축 뒤 지시" in b and "메타" not in b and "마지막 답" in b
    q = tmp_path / "n.jsonl"
    _w(q, {"type": "user", "message": {"content": "압축 없음"}})
    assert h.compact_body(q) is None
