"""사람이 해야 풀리는 대기(11-09) — 글로 묻고 끝난 응답 판정 · CC auto mode 거부 문구."""

from bridge.api.dashboard import DENIED_PREFIX, _DENY_REASON, asks_text


def test_asks_text():
    assert asks_text("셋 중 하나를 골라 주세요.\n- (가) 직접 반영\n- (나) 허용 규칙")
    assert asks_text("둘 다 받으실지, 하나라도 빼실지 알려 주세요.\n2. 다음")
    assert asks_text("이대로 진행할까요?")
    assert not asks_text("커밋했고 push했습니다. 시험 487 통과입니다.")
    assert not asks_text(None)
    # 앞쪽(600자 밖)에 있던 물음은 보지 않는다 — 끝에 남은 말만
    assert not asks_text("어떻게 할까요?\n" + "결과를 정리했습니다. " * 60)


def test_denied_text():
    t = ("Permission for this action was denied by the Claude Code auto mode classifier. "
         "Reason: [External System Writes]. If you have other tasks ...")
    assert t.startswith(DENIED_PREFIX)
    assert _DENY_REASON.search(t).group(1) == "External System Writes"
