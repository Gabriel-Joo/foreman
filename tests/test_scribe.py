from datetime import datetime

from bridge import scribe as sc


def test_parse_kst_and_clip():
    assert sc.parse_kst("2026-11-05") == datetime(2026, 11, 4, 15, 0)
    assert sc.parse_kst("2026-11-06 06:00") == datetime(2026, 11, 5, 21, 0)
    assert sc.kst(datetime(2026, 11, 5, 17, 16)) == "11-06 02:16"
    assert sc._clip('<pasted_content id="ab">\n가나다\n</pasted_content id="ab">', 10) == "가나다"
    assert sc._clip("가" * 20, 5).startswith("가가가가가 …(뒤 15자")


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
