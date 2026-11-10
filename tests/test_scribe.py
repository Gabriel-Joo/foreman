from datetime import datetime

from bridge import scribe as sc


def test_parse_kst_and_clip():
    assert sc.parse_kst("2026-11-05") == datetime(2026, 11, 4, 15, 0)
    assert sc.parse_kst("2026-11-06 06:00") == datetime(2026, 11, 5, 21, 0)
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


def test_render_human_section_not_clipped(tmp_path):
    d = _data()
    d["human"].append({"id": 6360, "started_at": datetime(2026, 11, 10, 3), "prompt_text": _long_prompt(), "title": "작업", "sid": 3, "role": "coder"})
    body = sc.render("foreman", datetime(2026, 11, 4, 15), datetime(2026, 11, 10, 21), d, str(tmp_path))
    sec8 = body.split("## 8. 사람이 한 말")[1]
    assert "끝표지-지금은 말고 다음에" in sec8 and "…(뒤" not in sec8
    assert sec8.count("가") >= 3000 and sec8.count("나") >= 2500
    assert "[t:6360]" in body.split("## 2.")[0]                      # 요약 칸(1-1 후보)은 잘려도 t: 번호가 줄 앞에 남는다


def test_later_material_not_clipped():
    from bridge import scribe_room as sr
    t = datetime(2026, 11, 10, 3)
    body = sr.later_material("foreman", None, [{"id": 6383, "started_at": t, "prompt_text": _long_prompt()}],
                             [{"id": 14, "created_at": t, "body": "받은 할 일"}])
    assert "## [t:6383]" in body and "끝표지-지금은 말고 다음에" in body and "…(뒤" not in body
    assert "## 받은 할 일 #14" in body
    assert max(len(ln) for ln in body.split("\n")) < 2000


def _data():
    t = datetime(2026, 11, 5, 3, 0)
    return {
        "human": [{"id": 11, "started_at": t, "prompt_text": "역할 색이 왜 안 칠해져? 이름이 안 맞아", "title": "작업", "sid": 3, "role": "coder"},
                  {"id": 12, "started_at": t, "prompt_text": "좋아 커밋해", "title": "작업", "sid": 3, "role": "coder"}],
        "sessions": [{"id": 3, "title": "작업", "role": "coder", "cwd": "/home/u/AI_programming/foreman", "first": t, "last": t, "turns": 2, "human": 2}],
        "origins": {"human": 2}, "tokens": [("claude-opus-5-5", 10, 2_100_000, 650_000_000, 5_000_000)],
        "dispatch": [{"id": 1, "created_at": t, "request": "회고", "plan": '{"role": "coder"}', "edited": '{"role": "scribe"}', "status": "started"}],
        "approvals": [], "builds": [], "handoffs": [], "actions": {"exit": 1},
        "commits": [{"sha": "cad260d", "kst": "11-05 16:26", "subject": "11: 역할 이름 통일 — 색이 안 맞던 것 고침", "files": ["log/stage11_roles_result.md"]}],
    }


def test_render_puts_corrections_flips_mistakes_first(tmp_path):
    (tmp_path / "log").mkdir()
    (tmp_path / "log" / "stage11_roles_result.md").write_text("# 11 — 역할 결과\n", encoding="utf-8")
    base = [{"id": "구간1-3-b", "kind": "결정", "gist": "관찰만", "status": "뒤집힘", "missing": "Jenkinsfile post 알림으로"},
            {"id": "구간0-2-a", "kind": "지시", "gist": "커밋은 의미 단위로", "status": "사라짐", "where": "", "dropped_at": "summary_00"},
            {"id": "구간0-0-a", "kind": "결정", "gist": "살아 있는 것", "status": "살아 있음"}]
    mist = [{"title": "역할 색", "what": "색이 안 칠해짐", "why": "이름이 다름", "fix": "통일", "refs": ["[c:cad260d]"]}]
    body = sc.render("foreman", datetime(2026, 11, 4, 15), datetime(2026, 11, 5, 21), _data(), str(tmp_path), base, mist)
    order = [body.index(h) for h in ("## 1. 사람이 바로잡은 곳", "## 2. 뒤집힌 결정", "## 3. 실수", "## 4. 압축 손실", "## 5. 숫자", "## 8. 사람이 한 말")]
    assert order == sorted(order)                                         # 이 시스템만 가진 재료가 앞에
    assert "[t:11]" in body.split("## 2.")[0] and "[t:12]" not in body.split("## 2.")[0]   # 정정 신호가 있는 턴만 후보로
    assert "사람이 고친 것" in body and "scribe" in body                     # 포먼 계획을 사람이 고친 것
    assert "구간1-3-b" in body.split("## 3.")[0]                            # 뒤집힘은 2절에
    assert "커밋은 의미 단위로" in body and "살아 있는 것" not in body       # 4절은 사라짐 · 약해짐만
    assert "[c:cad260d]" in body.split("## 4.")[0]                          # 고침 신호 커밋은 3절에도
    assert "[log:stage11_roles_result.md] 11 — 역할 결과" in body           # 이미 쓴 기록을 가리킨다
    assert "| claude-opus-5-5 | 10 | 2.1M | 650.0M | 5.0M |" in body


def test_retro_prompt_rules():
    p = sc.retro_prompt("foreman", "11-05", "/home/u/.foreman/scribe/x/materials.md", "log/retro_20261105_foreman.md")
    assert p.startswith("[FOREMAN 서기 일감 — 회고]")
    for must in ("docs/style_guide.md", "/home/u/.foreman/scribe/x/materials.md", "사람이 바로잡은 곳 · 뒤집힌 결정 · 실수를 앞에",
                 "push하지 않는다", "retro: 11-05 foreman 회고", "근거 표시"):
        assert must in p, must
