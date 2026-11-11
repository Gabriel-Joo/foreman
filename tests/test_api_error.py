"""API 오류 종류 가르기(11-11, bridge/api_error.py) — 11-10 · 11-09 실제 오류 글 꼴로."""

from bridge.api_error import classify, one_line

SAFEGUARD = ("API Error: Sonnet 5.5's safeguards flagged this message (https://www.anthropic.com/legal/aup). This sometimes "
             "happens with safe, normal content. Try rephrasing, or try a different model with /model. "
             "Learn more: https://support.claude.com/en/articles/8106465\n\nDetails: `[reasoning_extraction]`\n\n"
             "Request ID: req_011CgtKkMaLMkhEyDRTbEGka\n\nMessage ID: msg_01abc")
LIMIT = ("You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage?from=cc_cli_limit_message · "
         "your 5-hour limit resets 2:10pm (Asia/Seoul)")


def test_safeguard_with_request_id():
    c = classify(SAFEGUARD, "invalid_request")
    assert (c["kind"], c["detail"], c["request_id"]) == ("safeguard", "reasoning_extraction", "req_011CgtKkMaLMkhEyDRTbEGka")
    line = one_line(c)
    assert line.startswith("안전 분류기 거부 [reasoning_extraction] · req_011CgtKkMaLMkhEyDRTbEGka — /model")
    assert "http" not in line                              # URL은 싣지 않는다


def test_rate_limit_and_others():
    c = classify(LIMIT, "rate_limit")
    assert c["kind"] == "rate_limit" and c["reset"] == "2:10pm (Asia/Seoul)" and "2:10pm (Asia/Seoul)에 풀림" in one_line(c)
    assert classify(None, "rate_limit")["kind"] == "rate_limit"            # hook — error 값만
    assert classify("API Error: 529 {\"type\":\"overloaded_error\"}")["kind"] == "overloaded"
    assert classify("API Error: 500 Internal server error")["kind"] == "server"
    assert classify("Prompt is too long")["kind"] == "context"
    c = classify("API Error: something new", "invalid_request")
    assert c["kind"] == "unknown" and c["label"] == "API 오류" and c["request_id"] is None
