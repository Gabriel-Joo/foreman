from bridge.switchwatch import SwitchSignal, should_suggest, switch_message, switch_phrase


def test_switch_phrase_head_only():
    assert switch_phrase("좋아. 다음 일로 넘어가자 — 알림 문구 고치기") is not None
    assert switch_phrase("이번엔 런슈즈 쪽 로그를 보자") is not None
    assert switch_phrase("이제 다른 건데, 펫퍼민트 docs 반영") is not None
    assert switch_phrase("테스트 돌려줘") is None                              # 같은 일의 다음 단계는 전환이 아니다
    assert switch_phrase("") is None and switch_phrase(None) is None
    assert switch_phrase("x" * 200 + " 다음 일") is None                       # 긴 글 뒤쪽의 우연한 낱말은 안 본다


def test_should_suggest_needs_all_three():
    assert should_suggest(45, 40, "다음 일", True, False)                      # 말 + 커밋 + 45%
    assert should_suggest(45, 40, "다음 일", False, True)                      # 말 + 쉼
    assert not should_suggest(45, 40, "다음 일", False, False)                 # 말만 — 약하다
    assert not should_suggest(45, 40, None, True, True)                        # 커밋 · 쉼만 — 같은 주제일 수 있다
    assert not should_suggest(39, 40, "다음 일", True, True)                   # 아직 가볍다
    assert not should_suggest(None, 40, "다음 일", True, True)                 # 창을 모르는 모델


def test_switch_message_wording():
    m = switch_message("[포먼]", "세션", 52, SwitchSignal(1, "p", True, False, "다음 일"))
    assert "방금 커밋했고" in m and "52%" in m and "[새 세션으로 옮기기]" in m and "clear" not in m
    m = switch_message("[포먼]", "세션", 52, SwitchSignal(1, "p", True, True, "다음 일"))
    assert "방금 커밋했고 한참 쉬었다 왔고" in m
