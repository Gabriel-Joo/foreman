"""계획 받기 실패 원인 가르기(11-10) — 「답에서 계획을 찾지 못했습니다」 하나로는 까닭을 알 수 없었다."""
from bridge.foreman import FAIL_WHY, diagnose, parse_plan

OK = '```json\n{"project": "foreman", "mode": "new", "first_prompt": "가"}\n```'


def test_ok_answer_parses():
    assert parse_plan(OK)["mode"] == "new"


def test_empty_answer():
    assert diagnose(0, "", "", {"result": ""})[0] == "empty"
    assert diagnose(0, "   \n", "", None)[0] == "empty"
    assert FAIL_WHY["empty"] == "답이 비어 있습니다"


def test_broken_json_shows_where():
    # 11-10 dispatch 237 — first_prompt 안 큰따옴표를 이스케이프하지 않은 모양(추정)
    bad = '```json\n{"project": "foreman", "mode": "new", "first_prompt": "끝에 "확인을 기다려라"를 뺀다"}\n```'
    assert parse_plan(bad) is None
    kind, detail = diagnose(0, bad, "", {"result": bad})
    assert kind == "broken" and FAIL_WHY[kind] == "답의 형식이 깨졌습니다"
    assert "delimiter (줄 1 칸 60)" in detail and "확인을 기다려라" in detail   # JSON 블록 기준 자리 · 앞뒤를 남긴다
    assert diagnose(0, '```json\n{"a": 1}\n```', "", None) == ("broken", "JSON에 mode가 없습니다")


def test_no_json_at_all():
    assert diagnose(0, "계획을 세우려면 프로젝트를 알려 주세요.", "", None)[0] == "noblock"


def test_usage_limit():
    for t in ("Claude AI usage limit reached|1762761600", "You've hit your limit · resets 3pm (Asia/Seoul)"):
        assert diagnose(0, t, "", {"result": t, "is_error": True})[0] == "limit"
    assert diagnose(1, "", "API Error: 429 rate_limit_error", None)[0] == "limit"
    assert diagnose(0, "x", "", {"api_error_status": 429})[0] == "limit"
    assert FAIL_WHY["limit"] == "사용량 한도에 막혔습니다"


def test_call_failed():
    kind, detail = diagnose(1, "", "Error: something broke", None)
    assert kind == "call" and "종료 코드 1" in detail
    assert diagnose(0, "API Error: 500", "", {"is_error": True, "subtype": "error_during_execution"})[0] == "call"
