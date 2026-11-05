import json

import pytest

from bridge import losscheck as lc


def _line(**d):
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n"     # CC 트랜스크립트 모양(공백 없음)


def test_extract_rules(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("".join([
        _line(type="user", timestamp="2026-11-01T00:00:01Z", message={"content": "첫 지시"}),
        _line(type="assistant", timestamp="2026-11-01T00:00:02Z", message={"content": [{"type": "text", "text": "답"}]}),
        _line(type="user", timestamp="2026-11-01T00:00:03Z", message={"content": [{"type": "tool_result", "content": "x"}]}),
        _line(type="user", timestamp="2026-11-01T00:00:04Z", isSidechain=True, message={"content": "서브에이전트"}),
        _line(type="user", timestamp="2026-11-01T00:00:05Z", isMeta=True, message={"content": "메타"}),
        _line(type="user", timestamp="2026-11-01T00:00:06Z", message={"content": "[FOREMAN 인계 요청 r=abc] 브리지 글"}),
        _line(type="user", timestamp="2026-11-01T00:00:07Z",
              message={"content": [{"type": "text", "text": '<pasted_content id="ab12">\n붙여넣은 결정\n</pasted_content id="ab12">'}]}),
        _line(type="user", timestamp="2026-11-01T00:00:08Z", isCompactSummary=True, message={"content": "요약 0"}),
        _line(type="user", timestamp="2026-11-01T00:00:09Z", message={"content": "압축 뒤 지시"}),
        _line(type="user", timestamp="2026-11-01T00:00:10Z", message={"content": "자른 뒤"}),
    ]), encoding="utf-8")
    segs = lc.extract(p, until="2026-11-01T00:00:09Z")
    assert [[x["text"] for x in s.prompts] for s in segs] == [["첫 지시", "붙여넣은 결정"], ["압축 뒤 지시"]]
    assert segs[0].summary == "요약 0" and segs[0].summary_ts == "2026-11-01T00:00:08Z" and segs[1].summary is None
    assert len(lc.extract(p)[1].prompts) == 2


def _segs(*ns):
    return [lc.Seg(prompts=[{"ts": "", "text": f"{i}-{k}"} for k in range(n)]) for i, n in enumerate(ns)]


def test_groups_keep_segments_and_split_only_big_ones():
    assert lc.groups(_segs(17, 5, 17, 6, 3, 15, 5, 5), limit=80) == [[(0, 0, 17), (1, 0, 5), (2, 0, 17), (3, 0, 6), (4, 0, 3),
                                                                    (5, 0, 15), (6, 0, 5)]]   # 마지막 구간은 맥락이라 빼고 68개
    assert lc.groups(_segs(17, 5, 17, 6, 3, 15, 5, 5)) == [[(0, 0, 17)], [(1, 0, 5)], [(2, 0, 17)], [(3, 0, 6), (4, 0, 3)],
                                                          [(5, 0, 15), (6, 0, 5)]]          # 기본 20개씩
    assert lc.groups(_segs(50, 40, 9), limit=80) == [[(0, 0, 50)], [(1, 0, 40)]]       # 50+40 > 80 → 구간 단위로 새 묶음
    assert lc.groups(_segs(170, 1), limit=80) == [[(0, 0, 80)], [(0, 80, 160)], [(0, 160, 170)]]


def test_context_and_memory_dir(tmp_path):
    segs = _segs(2, 1)
    segs[0].summary, segs[0].summary_ts = "요약 본문", "T0"
    ctx = lc.context_text(segs, "# 규칙", {"b.md": "B", "a.md": "A"})
    assert "요약 본문" in ctx and "[구간1-0]" in ctx and "# 규칙" in ctx and ctx.index("## a.md") < ctx.index("## b.md")
    assert str(lc.memory_dir("/home/u/AI_programming/foreman")).endswith(".claude/projects/-home-u-AI-programming-foreman/memory")


def test_parse_items():
    body = [{"id": "구간0-1-a", "kind": "결정", "gist": "요지", "status": "사라짐", "where": "repo:README.md", "dropped_at": "summary_00"},
            {"id": "x", "kind": "엉뚱", "gist": "g", "status": "모름"}, {"gist": ""}]
    t = f"앞말\n<<<FOREMAN-LOSS r=q1>>>\n{json.dumps(body, ensure_ascii=False)}\n<<<END r=q1>>>"
    out = lc.parse_items(t, "q1")
    assert [(x["id"], x["kind"], x["status"]) for x in out] == [("구간0-1-a", "결정", "사라짐"), ("x", "결정", "사라짐")]
    with pytest.raises(ValueError):
        lc.parse_items(t, "다른r")
    obj = {"items": body[:1], "empty": ["구간0-2"]}
    items, empty = lc.parse_result(f"<<<FOREMAN-LOSS r=q2>>>\n{json.dumps(obj, ensure_ascii=False)}\n<<<END r=q2>>>", "q2")
    assert len(items) == 1 and empty == ["구간0-2"]
    # 빠짐없이 봤나 — items에도 empty에도 없는 프롬프트가 건너뛴 것
    assert lc.coverage(["구간0-1", "구간0-2", "구간0-3"], items, empty) == ["구간0-3"]


def test_compare_by_prompt():
    base = [{"id": "구간0-1-a", "status": "사라짐", "where": "repo:README.md"}, {"id": "구간0-1-b", "status": "살아 있음", "where": ""},
            {"id": "구간0-2", "status": "약해짐", "where": ""}, {"id": "구간1-0", "status": "뒤집힘", "where": ""}]
    mine = [{"id": "구간0-1", "status": "약해짐", "where": "repo:docs/x.md"}, {"id": "구간1-0-a", "status": "사라짐", "where": ""},
            {"id": "구간1-3", "status": "사라짐", "where": ""}]
    c = lc.compare(mine, base)
    assert c["lost_prompts"]["recall"] == 0.5 and c["lost_prompts"]["missed"] == ["구간0-2"]
    assert c["lost_prompts"]["extra"] == ["구간1-0", "구간1-3"] and c["flipped"]["mine_said_lost"] == ["구간1-0"]
    assert c["repo_where_lost"] == {"mine": 1, "base": 1}
