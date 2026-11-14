"""사용량(11-08, docs/15_usage.md) — claude -p JSON에서 모델별 사용량 뽑기 · 기록."""

import asyncio
import uuid

from sqlalchemy import text

from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.usage import cli_rows, record_cli

# 11-08 실제 claude -p(Haiku, "1") 출력 모양 — 필요한 칸만
REAL = {"result": "1", "total_cost_usd": 0.00198392,
        "usage": {"input_tokens": 2, "cache_creation_input_tokens": 9342, "cache_read_input_tokens": 11382, "output_tokens": 3},
        "modelUsage": {"claude-haiku-5-5": {"inputTokens": 2, "outputTokens": 3, "cacheReadInputTokens": 11382,
                                            "cacheCreationInputTokens": 9342, "costUSD": 0.00198392, "canonicalModel": "claude-haiku-5-5"}}}


def test_cli_rows_model_usage_and_fallback():
    assert cli_rows(REAL) == [{"model": "claude-haiku-5-5", "token_input": 2, "token_output": 3, "token_cache_read": 11382,
                               "token_cache_creation": 9342, "cost_usd": 0.00198392}]
    two = {"modelUsage": {"claude-opus-5-5": {"inputTokens": 1, "outputTokens": 2}, "claude-haiku-5-5": {"outputTokens": 5}}}
    assert [r["model"] for r in cli_rows(two)] == ["claude-opus-5-5", "claude-haiku-5-5"]     # 한 호출 안에 모델이 둘이면 둘
    old = {"usage": REAL["usage"], "total_cost_usd": 0.002}
    assert cli_rows(old)[0]["model"] == "unknown" and cli_rows(old)[0]["token_cache_read"] == 11382
    assert cli_rows(None) == [] and cli_rows({"result": "글만"}) == []


def test_record_cli_writes_rows(migrated_db):
    async def go():
        eng = make_engine(migrated_db)   # 11-14 — 전에는 Settings()(운영 DB foreman)에 썼다 지웠다. 시험 DB로
        src = "zz" + uuid.uuid4().hex[:6]
        try:
            assert await record_cli(eng, src, 7, "foreman", REAL) == 1
            async with eng.connect() as c:
                r = (await c.execute(text("SELECT model, token_cache_read, cost_usd, project FROM usage_extra WHERE source = :s"), {"s": src})).first()
            assert r[0] == "claude-haiku-5-5" and r[1] == 11382 and float(r[2]) == 0.001984 and r[3] == "foreman"
            assert await record_cli(None, src, 7, None, REAL) == 0                 # 엔진이 없으면 조용히 0(호출한 쪽을 막지 않는다)
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_extra WHERE source = :s"), {"s": src})
            await eng.dispose()
    asyncio.run(go())


# ── 2단계: 환산 · /usage 글 풀이 · 창 · 하한 · 주기 읽기 ──────────────

import tempfile  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

from bridge.usage import (Limit, UsageConfig, UsageMonitor, chain_windows, floors, limit_status, load_config,  # noqa: E402
                          next_weekly, parse_reset, parse_usage)

# 실제 config/usage.toml 대신 시험용 설정(11-14 — 값 · 한도 줄을 바꿀 때마다 시험이 깨지지 않게). 값은 11-14 실제 설정 그대로.
# 실제 설정의 모양(칸이 있는지)은 tests/test_live_config_shape.py
USAGE_TOML = """\
poll_s = 600
fail_alert = 3
tz = "Asia/Seoul"

[prices.opus]
input = 4.0
output = 20.0
cache_read = 0.20
cache_write = 8.0

[prices.sonnet]
input = 2.0
output = 10.0
cache_read = 0.20
cache_write = 4.0

[prices.haiku]
input = 0.10
output = 0.50
cache_read = 0.01
cache_write = 0.20

[prices.fable]
input = 10.0
output = 50.0
cache_read = 0.25
cache_write = 20.0

[[limits]]
key = "session_5h"
label = "5시간 세션"
match = "Current session"
window_h = 5
models = []

[[limits]]
key = "weekly_all"
label = "주간 · 전체"
match = "Current week (all models)"
window_h = 168
models = []
reset = "일요일 22:00"

[[limits]]
key = "weekly_fable"
label = "주간 · Fable"
match = "Current week (Fable)"
window_h = 168
models = ["fable"]
reset = "일요일 22:00"
"""


def _load_cfg():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "usage.toml"
        p.write_text(USAGE_TOML, encoding="utf-8")
        return load_config(p)


CFG = _load_cfg()
# 11-08 09:30 KST 실제 `claude -p "/usage"`의 result(앞부분)
CLI_BODY = """You are currently using your subscription to power your Claude Code usage

Current session: 46% used · resets Nov 8, 12:10pm (Asia/Seoul)
Current week (all models): 90% used · resets Nov 8, 10pm (Asia/Seoul)
Current week (Fable): 0% used · resets Nov 8, 10pm (Asia/Seoul)

What's contributing to your usage?
Approximate · sessions on this machine only · shares overlap

Last 24h · 363 requests · 5 sessions
  91%  Start fresh when you switch tasks · run /clear"""
# 같은 날 tmux 화면의 /usage(Usage 탭) — 머리 · 막대 · Resets가 여러 줄
SCREEN_BODY = """   Settings  Status   Config   Usage   Stats
   Session
   Total cost:            $0.0000
   Current session
   ███████████████████████                            46% used
   Resets 12:10pm (Asia/Seoul)
   Current week (all models)
   █████████████████████████████████████████████      90% used
   Resets Nov 8, 10pm (Asia/Seoul)
   Current week (Fable)
                                                      0% used
   Resets Nov 8, 10pm (Asia/Seoul)"""
NOW = datetime(2026, 11, 8, 0, 30)          # UTC = 09:30 KST


def test_usd_prices():
    t = {"input": 1_000_000, "output": 1_000_000, "cache_read": 1_000_000, "cache_write": 1_000_000}
    assert round(CFG.usd("claude-opus-5-5", t), 4) == 4 + 20 + 0.2 + 8
    assert round(CFG.usd("claude-haiku-5-5", t), 4) == 0.1 + 0.5 + 0.01 + 0.2
    assert CFG.usd("<synthetic>", t) == 0.0                                    # 표에 없는 모델은 0


def test_parse_cli_and_screen_forms():
    for body in (CLI_BODY, SCREEN_BODY):
        found, missing = parse_usage(body, CFG.limits, NOW, CFG.tz)
        assert missing == []
        assert found["session_5h"]["pct"] == 46 and found["session_5h"]["reset_at"] == datetime(2026, 11, 8, 3, 10)
        assert found["weekly_all"]["pct"] == 90 and found["weekly_all"]["reset_at"] == datetime(2026, 11, 8, 13, 0)
        assert found["weekly_fable"]["pct"] == 0
        assert "What's" not in found["weekly_fable"]["line"] and "█" not in found["weekly_all"]["line"]
    found, missing = parse_usage(CLI_BODY.replace("Current week (Fable)", "Current week (Opus)"), CFG.limits, NOW, CFG.tz)
    assert missing == ["주간 · Fable"]                                          # 글 모양이 바뀌면 못 찾은 것을 말한다
    assert parse_usage("", CFG.limits, NOW, CFG.tz)[1] == [x.label for x in CFG.limits]


# 11-14 14:23 실제 `claude -p "/usage"`(CC 2.1.325) — 5시간 줄(Current session)이 없다. 서버가 5시간 값을 안 주면 CC가 줄을 뺀다
NO_SESSION_BODY = """You are currently using your subscription to power your Claude Code usage

Current week (all models): 10% used · resets Nov 15, 10pm (Asia/Seoul)
Current week (Fable): 0% used · resets Nov 15, 10pm (Asia/Seoul)

What's contributing to your usage?
Approximate · sessions on this machine only · shares overlap

Last 24h · 363 requests · 5 sessions
  91%  Start fresh when you switch tasks · run /clear"""


def test_head_keys_tells_missing_line_from_changed_shape():
    from bridge.usage import head_keys
    found, missing = parse_usage(NO_SESSION_BODY, CFG.limits, NOW, CFG.tz)
    assert missing == ["5시간 세션"] and set(found) == {"weekly_all", "weekly_fable"}
    assert head_keys(NO_SESSION_BODY, CFG.limits) == {"weekly_all", "weekly_fable"}       # 머리가 없다 = CC가 줄을 뺐다
    shaped = CLI_BODY.replace("Current session: 46% used", "Current session: 46 percent")
    found, _ = parse_usage(shaped, CFG.limits, NOW, CFG.tz)
    assert "session_5h" not in found and "session_5h" in head_keys(shaped, CFG.limits)    # 머리는 있는데 % 없음 = 글 모양이 바뀜


def test_monitor_absent_session_line_is_not_a_failure(migrated_db):
    """5시간 줄이 없어도 읽기는 성공(주간은 기록) · 옛 5시간 값을 안 내고 · 6시간 넘게 없으면 한 번만 알린다 · 줄이 돌아오면 평소대로.
    한도 줄이 하나도 없거나 머리만 있고 %가 없으면 지금처럼 실패."""
    tag = "zz" + uuid.uuid4().hex[:6]
    lim5 = Limit(key=f"{tag}_5h", label="5시간", match="Current session", window_h=5)
    limw = Limit(key=f"{tag}_wk", label="주간", match="Current week (all models)", window_h=168)
    limf = Limit(key=f"{tag}_fb", label="주간 · Fable", match="Current week (Fable)", window_h=168, models=["fable"])
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="UTC", prices=CFG.prices, limits=[lim5, limw, limf])
    now = datetime(2001, 1, 1, 12, 0)
    full = ("Current session: 85% used · resets Jan 1, 3pm (UTC)\n"
            "Current week (all models): 25% used · resets Jan 3, 3pm (UTC)\n"
            "Current week (Fable): 5% used · resets Jan 3, 3pm (UTC)")
    gone = ("Current week (all models): 26% used · resets Jan 3, 3pm (UTC)\n"
            "\nWhat's contributing to your usage?\nLast 24h · 3 requests · 1 sessions")
    replies: list = []

    async def reader():
        return {"result": replies.pop(0)}

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        n = _Notifier()
        mon = UsageMonitor(eng, cfg, n, reader=reader)
        try:
            replies.extend([full, gone])
            assert await mon.poll(now)
            t1 = now + timedelta(minutes=10)
            assert await mon.poll(t1) and mon.error is None and mon.fails == 0 and mon.stale(t1) is False
            assert set(mon.absent) == {lim5.key, limf.key}                      # 5시간 · Fable 줄이 빠졌다(실패가 아님)
            st = {x["key"]: x for x in await limit_status(eng, cfg, t1, mon.latest, history_days=10**5, absent=mon.absent)}
            s5 = st[lim5.key]
            assert s5["absent"] and s5["measured_pct"] is None and s5["est_pct"] is None and s5["eta_100"] is None
            assert s5["last_pct"] == 85.0                                       # 옛 값은 따로 — 지금 값으로 나가지 않는다
            assert st[limw.key]["measured_pct"] == 26.0 and not st[limw.key]["absent"]
            assert await mon.check_alerts(t1) == [] and not n.sent                # 옛 85%로 80% 알림을 내지 않는다
            assert await mon.check_alerts(now + timedelta(hours=5)) == []           # 6시간 전 — 아직
            late = now + timedelta(hours=6, minutes=1)
            assert await mon.check_alerts(late) == [f"usage:{lim5.key}:absent"]     # 모델별(Fable)은 알리지 않는다
            assert len(n.sent) == 1 and "5시간 줄이 /usage에" in n.sent[0][1]
            assert await mon.check_alerts(late + timedelta(minutes=1)) == []        # 한 번만
            # 줄이 돌아오면 평소대로
            replies.append(full)
            assert await mon.poll(late) and mon.absent == {}
            assert (await limit_status(eng, cfg, late, mon.latest, history_days=10**5, absent=mon.absent))[0]["absent"] is False
            # 실패로 남는 것: 한도 줄이 하나도 없음 · 머리만 있고 %가 없음
            replies.extend(["You are currently using your subscription\n\nWhat's contributing to your usage?",
                            "Current session\nCurrent week (all models): 25% used"])
            assert not await mon.poll(late + timedelta(minutes=10)) and "하나도" in mon.error
            assert not await mon.poll(late + timedelta(minutes=20)) and "5시간" in mon.error and mon.fails == 2
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_observation WHERE limit_key LIKE :k"), {"k": tag + "%"})
                await c.execute(text("DELETE FROM notification WHERE rule LIKE :k"), {"k": f"usage:{tag}%"})
            await eng.dispose()
    asyncio.run(go())


def test_parse_reset_rollovers():
    # 날짜 없는 시각이 이미 지났으면 다음 날
    assert parse_reset("Resets 9am (Asia/Seoul)", NOW, "Asia/Seoul") == datetime(2026, 11, 9, 0, 0)
    # 12월 31일에 본 "Jan 1" → 다음 해
    assert parse_reset("resets Jan 1, 10pm (Asia/Seoul)", datetime(2026, 12, 31, 3, 0), "Asia/Seoul") == datetime(2027, 1, 1, 13, 0)
    assert parse_reset("resets 12am", NOW, "UTC") == datetime(2026, 11, 9, 0, 0)
    assert parse_reset("리셋 모름", NOW, "Asia/Seoul") is None


def test_next_weekly_sunday_22():
    # 11-08(일) 09:30 KST → 그날 22:00 KST = 13:00 UTC, 지나면 다음 주
    assert next_weekly("일요일 22:00", NOW, "Asia/Seoul") == datetime(2026, 11, 8, 13, 0)
    assert next_weekly("일요일 22:00", datetime(2026, 11, 8, 13, 1), "Asia/Seoul") == datetime(2026, 11, 15, 13, 0)
    assert next_weekly(None, NOW, "Asia/Seoul") is None


def test_chain_windows_and_anchor():
    t0 = datetime(2026, 10, 23, 11, 16)
    ts = [t0, t0 + timedelta(hours=1), t0 + timedelta(hours=5, minutes=1), t0 + timedelta(hours=6)]
    w = chain_windows(ts, 5)
    assert [(x["start"], x["end"]) for x in w] == [(t0, t0 + timedelta(hours=5)),
                                                   (ts[2], ts[2] + timedelta(hours=5))]
    # 10-23 사례: FOREMAN 첫 입력 20:16(KST)인데 화면 리셋 01:20 — 읽은 리셋이 이긴다
    r = t0 + timedelta(hours=5, minutes=4)
    w = chain_windows(ts[:2], 5, anchors=[r])
    assert len(w) == 1 and w[0]["anchored"] and w[0]["start"] == t0 and w[0]["end"] == r      # 몇 분 앞선 첫 메시지도 그 창


def test_floors_weighted_and_stable():
    assert floors([]) is None and floors([{"pct": 7, "seen_usd": 2.34}]) is None   # 20% 아래는 반올림 오차가 커서 뺀다
    f = floors([{"pct": 90, "seen_usd": 855}, {"pct": 50, "seen_usd": 470}])
    assert f["n"] == 2 and f["min"] == 940 and f["max"] == 950 and f["stable"]
    assert 945 < f["usd"] < 950                                                # 높은 %에 무게


class _Notifier:
    def __init__(self):
        self.sent = []
        self.rules = type("R", (), {"for_project": lambda self, p: None})()

    def send_direct(self, project, kind, sid, msg, rule=None):
        self.sent.append((kind, msg))
        self.rules_sent = getattr(self, "rules_sent", []) + [rule]


def test_monitor_observe_fail_alert_recover_and_status(migrated_db):
    """2001년 시각 · 이 시험만의 한도 key로 — 다른 행과 섞이지 않게(foreman_test)."""
    tag = "zz" + uuid.uuid4().hex[:6]
    lim5 = Limit(key=f"{tag}_5h", label="5시간", match="Current session", window_h=5)
    limw = Limit(key=f"{tag}_wk", label="주간", match="Current week (all models)", window_h=168)
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="UTC", prices=CFG.prices, limits=[lim5, limw])
    now = datetime(2001, 1, 1, 12, 0)
    body = ("Current session: 40% used · resets Jan 1, 3pm (UTC)\n"
            "Current week (all models): 25% used · resets Jan 3, 3pm (UTC)")
    replies: list = []

    async def reader():
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        n = _Notifier()
        mon = UsageMonitor(eng, cfg, n, reader=reader)
        try:
            async with eng.begin() as c:   # 창 안에 Opus 출력 100만 토큰 = $20
                await c.execute(text("INSERT INTO usage_extra (source, project, model, token_output, created_at) "
                                     "VALUES (:s, 'foreman', 'claude-opus-5-5', 1000000, :t)"), {"s": tag, "t": now - timedelta(hours=1)})
            replies.extend([{"result": body, "credential_expires_at": "2001-01-01T20:00:00Z"}, {"result": body}])
            assert await mon.poll(now) and await mon.poll(now + timedelta(minutes=10))
            async with eng.connect() as c:
                rows = (await c.execute(text("SELECT limit_key, pct, seen_usd FROM usage_observation WHERE limit_key LIKE :k ORDER BY limit_key"),
                                        {"k": tag + "%"})).all()
            assert [(r[0], float(r[1]), float(r[2])) for r in rows] == [(lim5.key, 40.0, 20.0), (limw.key, 25.0, 20.0)]   # 같은 값은 한 번만
            assert [k for k, m in n.sent] == ["usage"] and "로그인" in n.sent[0][1]      # 24시간 안 만료 — 한 번
            st = {x["key"]: x for x in await limit_status(eng, cfg, now + timedelta(minutes=10), mon.latest, history_days=10**5)}
            assert st[lim5.key]["floor"]["usd"] == 50.0 and st[limw.key]["floor"]["usd"] == 80.0   # $20 ÷ 40% · ÷ 25%
            assert st[lim5.key]["est_pct"] == 40.0 and st[lim5.key]["reset_at"] == datetime(2001, 1, 1, 15, 0)
            # 못 읽음 셋 — 셋째에 한 번만 알림, 화면 오류 칸. 그다음 돌아오면 한 번
            n.sent.clear()
            replies.extend([RuntimeError("시간 초과"), {"result": "Current session: 40 percent"}, RuntimeError("x"),
                            RuntimeError("y"), {"result": body}])
            for i in range(4):
                assert not await mon.poll(now + timedelta(minutes=20 + i))
            assert mon.fails == 4 and len(n.sent) == 1 and "연달아" in n.sent[0][1] and mon.snapshot()["ok"] is False
            assert await mon.poll(now + timedelta(minutes=30)) and mon.fails == 0 and mon.error is None
            assert len(n.sent) == 2 and "돌아왔다" in n.sent[1][1]
            assert mon.stale(now + timedelta(minutes=30 + 31)) is False and mon.stale(now + timedelta(hours=2)) is True
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_observation WHERE limit_key LIKE :k"), {"k": tag + "%"})
                await c.execute(text("DELETE FROM usage_extra WHERE source = :s"), {"s": tag})
            await eng.dispose()
    asyncio.run(go())


def test_alerts_thresholds_eta_once_and_after_restart(migrated_db):
    """5시간 85% + 최근 1시간 $20 → 80% · 1시간 안에 100%. 주간 96% → 95%만(80%는 따로 안 보냄). 다시 판정 · 다시 띄워도 한 번."""
    tag = "zz" + uuid.uuid4().hex[:6]
    lim5 = Limit(key=f"{tag}_5h", label="5시간", match="Current session", window_h=5)
    limw = Limit(key=f"{tag}_wk", label="주간", match="Current week (all models)", window_h=168)
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="UTC", prices=CFG.prices, limits=[lim5, limw])
    now = datetime(2001, 1, 1, 12, 0)
    body = ("Current session: 85% used · resets Jan 1, 3pm (UTC)\n"
            "Current week (all models): 96% used · resets Jan 3, 3pm (UTC)")

    async def reader():
        return {"result": body}

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        n = _Notifier()
        try:
            async with eng.begin() as c:   # 최근 1시간 안에 $20(Opus 출력 100만)
                await c.execute(text("INSERT INTO usage_extra (source, project, model, token_output, created_at) "
                                     "VALUES (:s, 'foreman', 'claude-opus-5-5', 1000000, :t)"), {"s": tag, "t": now - timedelta(minutes=30)})
            mon = UsageMonitor(eng, cfg, n, reader=reader)
            assert await mon.poll(now)
            sent = await mon.check_alerts(now)
            assert sorted(sent) == sorted([f"usage:{lim5.key}:80:01011500", f"usage:{lim5.key}:eta:01011500",
                                           f"usage:{limw.key}:95:01031500"])
            assert any("🛑 주간" in m for _, m in n.sent) and any("⏳ 5시간" in m for _, m in n.sent)
            assert all(m.startswith("[FOREMAN] ") for _, m in n.sent)
            assert await mon.check_alerts(now + timedelta(minutes=1)) == []          # 같은 창 — 다시 안 보낸다
            async with eng.begin() as c:   # 가짜 알림기는 DB에 안 쓴다 — 실제 send_direct처럼 기록해 두고 "다시 띄운" 모니터로
                for r in n.rules_sent:
                    await c.execute(text("INSERT INTO notification (kind, decision, rule, text) VALUES ('usage', 'sent', :r, 't')"), {"r": r})
            await asyncio.sleep(0.05)      # _mark(낮은 문턱) 기록이 끝나게
            mon2 = UsageMonitor(eng, cfg, _Notifier(), reader=reader)
            assert await mon2.poll(now + timedelta(minutes=2))
            assert await mon2.check_alerts(now + timedelta(minutes=2)) == []
            async with eng.connect() as c:
                low = (await c.execute(text("SELECT decision FROM notification WHERE rule = :r"), {"r": f"usage:{limw.key}:80:01031500"})).scalar()
            assert low == "skipped"                                                  # 95%를 보냈으니 80%는 보낸 것으로
            # 11-08 — /usage의 리셋 글이 1분 흔들려도(3pm → 2:59pm) 같은 창이다. 키가 달라 두 번 나갔다
            jitter = body.replace("Jan 1, 3pm", "Jan 1, 2:59pm").replace("Jan 3, 3pm", "Jan 3, 2:59pm")

            async def reader2():
                return {"result": jitter}
            mon3 = UsageMonitor(eng, cfg, _Notifier(), reader=reader2)
            assert await mon3.poll(now + timedelta(minutes=3))
            assert await mon3.check_alerts(now + timedelta(minutes=3)) == []
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_observation WHERE limit_key LIKE :k"), {"k": tag + "%"})
                await c.execute(text("DELETE FROM usage_extra WHERE source = :s"), {"s": tag})
                await c.execute(text("DELETE FROM notification WHERE rule LIKE :k"), {"k": f"usage:{tag}%"})
            await eng.dispose()
    asyncio.run(go())


def test_over_limits():
    """11-14 사용자 — 「추가 요금으로 쓰는 중」 배지는 쓴 비율이 100%를 넘은 한도가 있을 때만. 칩과 같은 수(추정, 없으면 측정)만 보고,
    줄이 빠진 한도(absent)는 값이 없으니 셈에서 뺀다. 100%는 넘은 것이 아니다."""
    from bridge.usage import over_limits

    def lim(key, est, measured, absent=False, label=None):
        return {"key": key, "label": label or key, "est_pct": est, "measured_pct": measured, "absent": absent}

    assert over_limits([]) == []
    assert over_limits([lim("a", 100.0, 100.0), lim("b", 42.0, 40.0)]) == []          # 100% 이하면 배지 없음
    assert over_limits([lim("a", 104.36, 100.0, label="5시간 세션"), lim("b", 91.0, 90.0)]) == [
        {"key": "a", "label": "5시간 세션", "pct": 104.4}]                             # 측정은 100에서 멈추고 추정이 넘는다
    assert over_limits([lim("a", None, 101.0)]) == [{"key": "a", "label": "a", "pct": 101.0}]   # 추정이 없으면 측정
    assert over_limits([lim("a", None, None)]) == []
    # 줄 없는 한도 — limit_status가 값을 비우지만, 남은 값이 있어도 세지 않는다
    assert over_limits([lim("a", 130.0, 130.0, absent=True), lim("b", 120.0, 100.0)]) == [{"key": "b", "label": "b", "pct": 120.0}]


def test_parse_contrib():
    """11-09 실제 /usage "What's contributing" 모양 — 구간마다 서브에이전트 · MCP 비중 · 제안 줄."""
    from bridge.usage import parse_contrib
    body = ("to your usage?\nApproximate · sessions on this machine only · shares overlap\n\n"
            "Last 24h · 2532 requests · 11 sessions\n  82%  Give \"general-purpose\" subagents a cheaper model\n"
            "  72%  Start fresh when you switch tasks · run /clear\n  Top subagents: general-purpose 30%\n"
            "  Top MCP servers: claude.ai Notion 5%\n\nLast 7d · 9489 requests · 52 sessions\n"
            "  80%  Start fresh when you switch tasks · run /clear\n  Top subagents: general-purpose 15%\n")
    got = parse_contrib(body)
    assert [b["span"] for b in got] == ["24h", "7d"]
    assert got[0]["subagents"] == "general-purpose 30%" and got[0]["mcp"] == "claude.ai Notion 5%"
    assert got[0]["tips"][0] == {"pct": 82, "text": "Give \"general-purpose\" subagents a cheaper model"} and len(got[0]["tips"]) == 2
    assert got[1]["mcp"] is None and got[1]["subagents"] == "general-purpose 15%"
    assert parse_contrib(None) == []


def test_alerts_no_90_threshold(migrated_db):
    """11-14 — 「추가 사용이 막혀 있으면 90%에 한 번 더」를 뺐다(막힘 판정을 지움). 92%면 80% 알림 하나, 추가 사용 글 없음."""
    tag = "zz" + uuid.uuid4().hex[:6]
    lim5 = Limit(key=f"{tag}_5h", label="5시간", match="Current session", window_h=5)
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="UTC", prices=CFG.prices, limits=[lim5])
    now = datetime(2001, 1, 1, 12, 0)

    async def reader():
        return {"result": "Current session: 92% used · resets Jan 1, 3pm (UTC)"}

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        n = _Notifier()
        try:
            mon = UsageMonitor(eng, cfg, n, reader=reader)
            assert await mon.poll(now)
            sent = await mon.check_alerts(now)
            assert sent == [f"usage:{lim5.key}:80:01011500"]
            msg = next(m for _, m in n.sent if "5시간 사용량" in m)
            assert msg.startswith("[FOREMAN] ⚠") and "추가 사용" not in msg and "한도에 닿으면 세션이 말없이 멈춘다" in msg
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_observation WHERE limit_key LIKE :k"), {"k": tag + "%"})
                await c.execute(text("DELETE FROM notification WHERE rule LIKE :k"), {"k": f"usage:{tag}%"})
            await eng.dispose()
    asyncio.run(go())
