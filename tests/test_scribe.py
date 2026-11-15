from datetime import datetime

from bridge import scribe as sc


def test_kst_and_clip():
    assert sc.kst(datetime(2026, 11, 5, 17, 16)) == "11-06 02:16"
    assert sc._clip('<pasted_content id="ab">\n가나다\n</pasted_content id="ab">', 10) == "가나다"
    assert sc._clip("가" * 20, 5).startswith("가가가가가 …(뒤 15자")


def _long_prompt() -> str:
    # 1500자를 크게 넘고, 끝에 표지가 있고, Read가 자르는 2000자 넘는 한 줄이 섞인 사람 말(#14, 11-10)
    return '<pasted_content id="x">\n' + "앞부분 " + "가" * 3000 + "\n" + "나" * 2500 + "\n끝표지-지금은 말고 다음에\n</pasted_content id=\"x\">"


def test_full_keeps_every_char_and_wraps_long_lines():
    raw = _long_prompt()
    out = sc._full(raw)
    assert "pasted_content" not in out and "줄임" not in out
    assert out.replace("\n", "") == sc._unwrap(raw).replace("\n", "")    # 글자는 하나도 빠지지 않는다
    assert max(len(ln) for ln in out.split("\n")) <= sc.LINE_WRAP < 2000  # Read가 자르는 길이의 줄이 없다
    assert out.endswith("끝표지-지금은 말고 다음에")


def test_later_material_not_clipped():
    from bridge import scribe_room as sr
    t = datetime(2026, 11, 10, 3)
    body = sr.later_material("foreman", None, [{"id": 6383, "started_at": t, "prompt_text": _long_prompt()}],
                             [{"id": 14, "created_at": t, "body": "받은 할 일"}])
    assert "## [t:6383]" in body and "끝표지-지금은 말고 다음에" in body and "…(뒤" not in body
    assert "## 받은 할 일 #14" in body
    assert max(len(ln) for ln in body.split("\n")) < 2000


def test_retro_material_removed():
    """회고 쓰기는 11-15에 뺐다(docs/12_scribe.md 「0.」). 재료 묶음과 지시문이 남지 않는다."""
    for name in ("collect", "render", "retro_prompt", "parse_kst"):
        assert not hasattr(sc, name), name
