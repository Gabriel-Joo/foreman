"""세션 간 메시지 읽음(11-09) — 보낸 SendMessage ↔ 받는 쪽 대기열 줄(실측 모양: 펫퍼민트 ↔ FOREMAN)."""

from datetime import datetime, timedelta

from bridge.xmsg import body_of, is_session_target, key_of, pick

T = datetime(2026, 11, 9, 6, 0, 0)
MSG = "펫퍼민트 — 2e287cb push는 이 세션 사용자에게 직접 확인받은 뒤 하겠습니다."
ENQ = f'<cross-session-message from="uds:/tmp/cc-socks/1.sock" from-name="petmint-rag-chatbot-c6" from-mode="prompting">\n{MSG}\n</cross-session-message>'


def test_body_and_key():
    assert body_of(ENQ) == MSG
    assert key_of("  a \n b  ") == "a b"
    assert is_session_target("foreman-e7") and is_session_target("uds:/tmp/cc-socks/3531271.sock")
    assert not is_session_target("a96255028a3559965") and not is_session_target(None)   # 서브에이전트 이어 부르기


def test_pick_read_as_prompt_or_mid_turn():
    enq = [(1, 224, T + timedelta(seconds=1), ENQ)]
    # 쉬던 세션 — dequeue(프롬프트로 가져감)
    got = pick(T, MSG, enq, {224: [(T + timedelta(seconds=2), "dequeue", None)]})
    assert got["to_session"] == 224 and got["read_at"] == T + timedelta(seconds=2) and got["how"] == "prompt"
    # 작업 중 — delivered · remove(같은 본문)
    got = pick(T, MSG, enq, {224: [(T + timedelta(seconds=2), "remove", ENQ)]})
    assert got["how"] == "mid_turn"
    # 다른 글이 끼어들어 읽힌 것은 이 메시지가 아니다
    got = pick(T, MSG, enq, {224: [(T + timedelta(seconds=2), "delivered", "다른 사람 글")]})
    assert got["arrived_at"] and got["read_at"] is None
    # 도착 전의 소비는 세지 않는다
    got = pick(T, MSG, enq, {224: [(T, "dequeue", None)]})
    assert got["read_at"] is None


def test_pick_no_arrival():
    assert pick(T, MSG, [], {}) == {"arrived_at": None}
    late = [(1, 224, T + timedelta(minutes=30), ENQ)]          # 10분 넘어 온 같은 글은 다른 보내기다
    assert pick(T, MSG, late, {}) == {"arrived_at": None}
    assert pick(T, "", [], {}) == {}
