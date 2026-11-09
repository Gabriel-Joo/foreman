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


def test_record_cli_writes_rows():
    async def go():
        eng = make_engine(Settings())
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

from datetime import datetime, timedelta  # noqa: E402

from bridge.usage import (Limit, UsageConfig, UsageMonitor, chain_windows, floors, limit_status, load_config,  # noqa: E402
                          next_weekly, parse_reset, parse_usage)

CFG = load_config("config/usage.toml")
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


def test_monitor_observe_fail_alert_recover_and_status():
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
            replies.extend([RuntimeError("시간 초과"), {"result": "Current session: 40% used"}, RuntimeError("x"),
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


def test_alerts_thresholds_eta_once_and_after_restart():
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


def test_credit_status():
    """11-09 사람이 넣은 크레딧 값 — 크레딧 0 · 월 한도 초과 · 자동 충전 꺼짐(지금 값)이면 막힘. 넣은 지 3일이 지나거나 달이 바뀌면
    숫자를 믿지 않는다(stale — 화면은 숫자를 감추고 '확인 필요')."""
    from datetime import date

    from bridge.usage import credit_status, credit_view
    now_c = {"balance_usd": 0, "monthly_cap_usd": 50, "monthly_used_usd": 51.3, "auto_reload": False, "as_of": "2026-11-09"}
    s = credit_status(now_c, date(2026, 11, 11))
    assert s["blocked"] and not s["stale"] and s["room_usd"] == 0
    s = credit_status(now_c, date(2026, 11, 12))                      # 3일 — 사람은 날짜를 안 본다
    assert s["stale"] and not s["blocked"]
    assert credit_status(now_c, date(2026, 12, 1))["stale"]           # 달이 바뀜
    ok = {**now_c, "balance_usd": 20, "monthly_used_usd": 10}
    s = credit_status(ok, date(2026, 11, 10))
    assert not s["blocked"] and s["available_usd"] == 20               # 잔액 20, 한도 여유 40 → 20
    assert credit_status({**ok, "auto_reload": True}, date(2026, 11, 10))["available_usd"] == 40
    assert credit_status(None, date(2026, 11, 20)) is None
    assert CFG.credits and CFG.credits["as_of"]                        # config/usage.toml에 칸이 있다
    # 판정은 CC 한도 글이 먼저 — 넣은 값은 근거가 없을 때만(그것도 3일 안)
    fresh = credit_status(now_c, date(2026, 11, 10))
    assert credit_view({"state": "flowing"}, fresh)["blocked"] is False
    assert credit_view({"state": "blocked"}, None)["blocked"] is True
    assert credit_view({"state": "unknown"}, fresh)["blocked"] is True
    assert credit_view({"state": "unknown"}, credit_status(now_c, date(2026, 11, 20)))["blocked"] is False


def test_credit_signal_from_cc_limit_messages():
    """11-09 실측 모양 — 13:10 5시간 한도 → 13:13부터 응답이 이어짐(추가 사용) → 13:32 월 지출 한도(막힘). 2001-02월 시각 · 이 시험만의 세션"""
    from bridge.usage import credit_signal
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="Asia/Seoul", prices=CFG.prices, limits=[])
    t0 = datetime(2001, 2, 5, 4, 10)                                   # UTC — KST 13:10

    async def go():
        eng = make_engine(Settings(mysql_database="foreman_test"))
        try:
            async with eng.begin() as c:
                ch = (await c.execute(text("SELECT id FROM `character` LIMIT 1"))).scalar()
                sid = (await c.execute(text(
                    "INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                    "VALUES (:c, 'agent', 'coder', :cc, '한도 시험', 'user')"), {"c": ch, "cc": str(uuid.uuid4())})).lastrowid

            async def err(at, msg):
                async with eng.begin() as c:
                    await c.execute(text("INSERT INTO event (session_id, character_id, source, ts, type, status, payload) VALUES "
                                         "(:s, :c, 'transcript', :t, 'error', 'error', :p)"),
                                    {"s": sid, "c": ch, "t": at, "p": f'{{"text": "{msg}", "error": "rate_limit"}}'})

            async def reply(at, model="claude-opus-5-5"):
                async with eng.begin() as c:
                    await c.execute(text("INSERT INTO message (id, model, token_input, token_output, created_at) VALUES "
                                         "(:i, :m, 1, 1, :t)"), {"i": "zzmsg-" + uuid.uuid4().hex, "m": model, "t": at})

            assert (await credit_signal(eng, cfg, t0 - timedelta(minutes=1)))["state"] == "unknown"     # 이번 달 근거 없음
            await err(t0, "You've hit your 5-hour limit · resets 2:10pm (Asia/Seoul)")
            await reply(t0, "<synthetic>")
            s = await credit_signal(eng, cfg, t0 + timedelta(minutes=2))
            assert s["state"] == "blocked" and s["why"] == "limit"                              # 아직 이어 쓴 응답 없음
            await reply(t0 + timedelta(minutes=3))
            s = await credit_signal(eng, cfg, t0 + timedelta(minutes=5))
            assert s["state"] == "flowing" and s["since"] == t0 + timedelta(minutes=3)          # 한도 뒤에도 응답 — 추가 사용
            await err(t0 + timedelta(minutes=22), "You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage"
                                                  "?from=cc_cli_limit_message · your 5-hour limit resets 2:10pm (Asia/Seoul)")
            async with eng.begin() as c:                                   # 같은 때 StopFailure 훅(글 없음)도 error로 — 이것을 고르면 안 된다
                await c.execute(text("INSERT INTO event (session_id, character_id, source, ts, type, status, payload) VALUES "
                                     "(:s, :c, 'hook', :t, 'error', 'error', :p)"),
                                {"s": sid, "c": ch, "t": t0 + timedelta(minutes=22, seconds=1),
                                 "p": '{"error": "rate_limit", "hook_event_name": "StopFailure"}'})
            await reply(t0 + timedelta(minutes=61))                          # 리셋(14:10 KST) 뒤 응답 — 추가 사용이 아니다
            s = await credit_signal(eng, cfg, t0 + timedelta(minutes=70))
            assert s["state"] == "blocked" and s["why"] == "spend"
            assert (await credit_signal(eng, cfg, datetime(2001, 3, 2)))["state"] == "unknown"     # 달이 바뀌면 다시 모름
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM message WHERE id LIKE 'zzmsg-%'"))
                await c.execute(text("DELETE FROM event WHERE session_id = :s"), {"s": sid})
                await c.execute(text("DELETE FROM character_session WHERE id = :s"), {"s": sid})
            await eng.dispose()
    asyncio.run(go())


def test_alerts_90_when_credits_blocked():
    """추가 사용이 막혀 있으면 90%에 한 번 더(100%가 곧 멈춤) — 글에 막힌 까닭과 '마무리'."""
    tag = "zz" + uuid.uuid4().hex[:6]
    lim5 = Limit(key=f"{tag}_5h", label="5시간", match="Current session", window_h=5)
    cr = {"balance_usd": 0, "monthly_cap_usd": 50, "monthly_used_usd": 51.3, "auto_reload": False, "as_of": "2001-01-01"}
    cfg = UsageConfig(poll_s=600, fail_alert=3, tz="UTC", prices=CFG.prices, limits=[lim5], credits=cr)
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
            assert f"usage:{lim5.key}:90:01011500" in sent
            msg = next(m for _, m in n.sent if "5시간 사용량" in m)
            assert msg.startswith("[FOREMAN] 🛑") and "추가 사용이 막혀 있습니다" in msg and "마무리할 일을 먼저 하세요" in msg
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM usage_observation WHERE limit_key LIKE :k"), {"k": tag + "%"})
                await c.execute(text("DELETE FROM notification WHERE rule LIKE :k"), {"k": f"usage:{tag}%"})
            await eng.dispose()
    asyncio.run(go())
