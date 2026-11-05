"""포먼 디스패처(11-05) — 계획 꺼내기 · 사실과 맞추기(DB 없이 되는 부분)."""

from bridge.foreman import parse_plan, docs_index, read_cached, memory_dir


def test_parse_plan_json_block_and_bare():
    s = "생각 정리…\n```json\n{\"project\": \"runshoes\", \"mode\": \"handoff\", \"summary_id\": 3}\n```\n끝"
    assert parse_plan(s)["summary_id"] == 3
    assert parse_plan('앞말 {"project": "petmint-rag-chatbot", "mode": "new"} 뒷말')["mode"] == "new"
    assert parse_plan("계획 없음") is None
    assert parse_plan('```json\n{"a": 1}\n```') is None                      # mode 없는 JSON은 계획이 아니다


def test_docs_index_and_cache(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "01_a.md").write_text("# 첫 문서 제목\n본문", encoding="utf-8")
    (tmp_path / "docs" / "02_b.md").write_text("서두\n## 둘째\n", encoding="utf-8")
    assert docs_index(str(tmp_path)) == ["docs/01_a.md — 첫 문서 제목", "docs/02_b.md — 둘째"]
    p = tmp_path / "x.md"
    p.write_text("하나", encoding="utf-8")
    assert read_cached(p, 100) == "하나"
    assert read_cached(tmp_path / "없음.md", 100) is None
    assert str(memory_dir("/home/u/AI_programming/run_shoes")).endswith("-home-u-AI-programming-run-shoes/memory")
