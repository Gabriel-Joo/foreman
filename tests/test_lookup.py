"""도구 본문 찾기(11-05) — 끝에서 거꾸로 조각 단위로 읽어도 조각 경계에 걸친 줄을 놓치지 않는다."""

import json

from bridge.transcript import lookup


def _lines(n_pad: int) -> list[dict]:
    pad = [{"type": "user", "message": {"content": "x" * 50}} for _ in range(n_pad)]
    use = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_A", "name": "Bash", "input": {"command": "ls -la", "description": "목록"}}]}}
    res = {"type": "user", "toolUseResult": {"stdout": "a", "stderr": "경고", "interrupted": False},
           "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_A", "content": "합계 0\nfile",
                                    "is_error": False}]}}
    return pad + [use] + pad + [res] + pad


def test_find_across_chunk_boundaries(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in _lines(40)) + "\n", encoding="utf-8")
    for chunk in (37, 64, 101, 4096, 1 << 20):           # 줄보다 작은 조각까지
        monkeypatch.setattr(lookup, "CHUNK", chunk)
        r = lookup.find_tool_call(p, "toolu_A")
        assert r["found"] == {"use": True, "result": True}, chunk
        assert r["name"] == "Bash" and r["input"]["command"] == "ls -la"
        assert r["result"] == "합계 0\nfile" and r["is_error"] is False and r["extra"] == {"stderr": "경고"}
    assert lookup.find_tool_call(p, "toolu_없음")["found"] == {"use": False, "result": False}


def test_clip():
    s, n = lookup.clip_text("가" * (lookup.MAX_TEXT + 500))
    assert n == lookup.MAX_TEXT + 500 and "줄임" in s and len(s) < lookup.MAX_TEXT + 100
    assert lookup.clip_input({"c": "y" * (lookup.MAX_INPUT + 5)})["c"].endswith("5자 줄임)")
