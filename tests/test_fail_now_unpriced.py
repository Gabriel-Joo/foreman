"""실패 알림은 묶음을 켠 프로젝트에서도 바로, 가격 칸이 빠진 토큰은 0원이 아니라 「모름」(11-17 사용자, 관리자 410 일감).

1. 「실패는 묶어서 늦게 알 이유가 없다」. 인계 요약 실패, 시간 초과(종류 handoff, [digest] kinds에 있음)가 21:00 묶음으로 가던 것을
   바로 보낸다. 성공(인계 요약 저장)은 그대로 묶인다. Notion ✋(덮지 않음), 어긋남 🧹은 사람이 볼 목록이라 묶음 그대로
2. config/usage.toml에서 출처 없는 가격 칸을 비우면, 그 토큰은 환산에서 0원으로 더해지지 않고 unpriced로 따로 나온다
실제 config/*.toml은 읽지 않는다(묶음 규칙과 가격은 시험 안에서 만든다).
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import text

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.handoff import HandoffManager
from bridge.notify import Notifier, ProjectRule, Rules
from bridge.usage import Limit, UsageConfig, breakdown, limit_status, window_unpriced

PRICES = {"opus": {"input": 4.0, "output": 20.0, "cache_read": 0.2, "cache_write": 8.0},
          "half": {"input": 1.0, "output": 2.0}}          # 캐시 두 칸이 빠진 모델(출처 없는 칸을 비운 꼴)
T = {"input": 1_000_000, "output": 1_000_000, "cache_read": 1_000_000, "cache_write": 1_000_000}


def _notifier() -> Notifier:
    pr = ProjectRule("[FM]", {"stop"}, {"human"}, set(), False, 0.0, digest=True)
    n = Notifier(None, Rules(projects={"foreman": pr}), None, None)    # type: ignore[arg-type]
    n.sent = []                                                          # type: ignore[attr-defined]

    def send_direct(project, kind, sid, msg, rule=None, later=None):
        n.sent.append({"kind": kind, "msg": msg, "later": later,       # type: ignore[attr-defined]
                       "decision": n.direct_decision(project, kind, msg, later)})
    n.send_direct = send_direct                                          # type: ignore[method-assign]
    return n


def test_digest_kinds_failure_goes_now_success_stays():
    n = _notifier()
    d = n.direct_decision
    assert d("foreman", "handoff", "[FM] 인계 요약 저장 (1,234자)") == "digest"            # 성공은 묶음
    assert d("foreman", "handoff", "[FM] ⚠ 인계 요약 시간 초과") == "pending"               # ⚠는 [digest] urgent_marks
    assert d("foreman", "handoff", "[FM] 인계 요약 실패", later=False) == "pending"         # 글이 바뀌어도 later=False면 바로
    assert d("foreman", "docsync", "[FM] ✋ Notion 기술문서, 사람이 고친 곳이 있어 덮지 않았습니다") == "digest"
    assert d("foreman", "docsync", "[FM] ⚠ Notion 기술문서 자동 게시 실패 1개") == "pending"
    assert d("foreman", "recon", "[FM] 🧹 끝난 뒤 어긋난 것 1") == "digest"
    assert d("foreman", "merge", "[FM] ⚠ 합치기 실패") == "pending"
    assert d("nodigest", "handoff", "[X] 인계 요약 저장") == "pending"                      # 묶음을 안 켠 프로젝트는 원래대로


def test_handoff_notify_failure_now_success_digest():
    n = _notifier()
    h = HandoffManager.__new__(HandoffManager)
    h.notifier = n
    row = SimpleNamespace(project="foreman", id=7)
    h._notify(row, "인계 요약 저장 (10자)")
    h._notify(row, "인계 요약 시간 초과, 900초 안에 돌아오지 않았습니다", fail=True)
    h._notify(row, "인계 요약 실패, 표지가 없습니다", fail=True)
    ok, slow, bad = n.sent                                                                   # type: ignore[attr-defined]
    assert ok["decision"] == "digest" and ok["later"] is None and "⚠" not in ok["msg"]
    for x in (slow, bad):
        assert x["decision"] == "pending" and x["later"] is False and x["msg"].startswith("[FM] ⚠ 인계 요약")


def test_wait_live_session_gone_and_timeout_notify(monkeypatch):
    """전에는 조용했던 것(기다리는 중에 세션이 끝남)과 시간 초과가 바로 나간다."""
    import bridge.handoff as ho
    n = _notifier()
    h = HandoffManager.__new__(HandoffManager)
    h.notifier, h.sessions_dir, h.wait_s = n, "/nonexistent", 0.0
    done = []

    async def finish(sid, status, body, raw, error, turn_id=None):
        done.append(status)
    h._finish = finish                                                                       # type: ignore[method-assign]
    monkeypatch.setattr(ho, "assistant_text", lambda path, off: "")
    monkeypatch.setattr(ho, "live_sessions", lambda d: set())

    async def nosleep(_s):
        return None
    monkeypatch.setattr(ho.asyncio, "sleep", nosleep)
    row = SimpleNamespace(project="foreman", id=7, cc="aaaa-bbbb")
    asyncio.run(h._wait_live(row, 1, "REQ", "/nonexistent", 0, None))                     # wait_s 0: 바로 시간 초과
    h.wait_s = 60.0
    asyncio.run(h._wait_live(row, 2, "REQ", "/nonexistent", 0, None))                      # 세션이 없다
    assert done == ["timeout", "failed"]
    assert [x["decision"] for x in n.sent] == ["pending", "pending"]                        # type: ignore[attr-defined]
    assert "시간 초과" in n.sent[0]["msg"] and "세션이 끝났습니다" in n.sent[1]["msg"]       # type: ignore[attr-defined]


def test_unpriced_is_not_zero():
    cfg = UsageConfig(prices=PRICES)
    assert cfg.unpriced("claude-opus-5-5", T) == {}
    assert round(cfg.usd("claude-half-1", T), 4) == 3.0                                     # 아는 칸만
    assert cfg.unpriced("claude-half-1", T) == {"cache_read": 1_000_000, "cache_write": 1_000_000}
    assert cfg.unpriced("claude-fable-5-2", T) == T                                         # 표에 없는 모델은 전부 모름
    assert cfg.unpriced("claude-fable-5-2", {"input": 0, "output": 5, "cache_read": 0, "cache_write": 0}) == {"output": 5}
    lim = Limit(key="f", label="주간 · Fable", match="x", window_h=168, models=["fable"])
    assert window_unpriced(cfg, lim, {"claude-fable-5-2": {**T, "input": 0}, "claude-opus-5-5": T}) == [
        {"model": "claude-fable-5-2", "kind": k, "tokens": 1_000_000} for k in ("output", "cache_read", "cache_write")]


def test_breakdown_and_limits_show_unpriced(migrated_db):
    """2003년 시각, 이 시험만의 source로(다른 행과 섞이지 않게)."""
    tag = "zz" + uuid.uuid4().hex[:6]
    now = datetime(2003, 3, 3, 12, 0)
    lim = Limit(key=f"{tag}_fb", label="주간 · Fable", match="x", window_h=168, models=["fable"], reset="일요일 22:00")
    cfg = UsageConfig(tz="UTC", prices=PRICES, limits=[lim])

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        try:
            async with eng.begin() as c:
                for model, out, cr in (("claude-opus-5-5", 1_000_000, 0), ("claude-fable-5-2", 1_000_000, 2_000_000)):
                    await c.execute(text("INSERT INTO usage_extra (source, project, model, token_output, token_cache_read, created_at) "
                                         "VALUES (:s, 'foreman', :m, :o, :cr, :t)"),
                                    {"s": tag, "m": model, "o": out, "cr": cr, "t": now - timedelta(hours=1)})
            b = await breakdown(eng, cfg, now - timedelta(hours=2), now)
            assert b["total_usd"] == 20.0                                                   # Fable은 0원으로 더하지 않았다
            assert b["unpriced"] == [{"model": "claude-fable-5-2", "kind": "cache_read", "tokens": 2_000_000},
                                     {"model": "claude-fable-5-2", "kind": "output", "tokens": 1_000_000}]
            m = {x["key"]: x for x in b["by_model"]}
            assert m["claude-fable-5-2"]["unpriced"] == {"output": 1_000_000, "cache_read": 2_000_000}
            assert m["claude-opus-5-5"]["unpriced"] == {}
            assert b["by_project"][0]["unpriced"] == {"output": 1_000_000, "cache_read": 2_000_000}   # 섞인 줄에도 남는다
            st = (await limit_status(eng, cfg, now, history_days=1))[0]
            assert st["window_usd"] == 0.0 and [x["kind"] for x in st["unpriced"]] == ["output", "cache_read"]
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_extra WHERE source = :s"), {"s": tag})
            await eng.dispose()
    asyncio.run(go())
