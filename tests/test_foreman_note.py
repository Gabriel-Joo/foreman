"""디스패처 노트 · 자동 기상 2단계(11-08) — 노트 제안 맞추기 · 반영 · 낡음 표시 · 상한 접기, 실패 → 계획 → 알림."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import text

from bridge import foreman_note as notes
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.inject import Refused
from bridge.wake import Waker, WakeRules, load_wake


def test_est_tokens_and_changed_fields():
    assert notes.est_tokens("가나다") == 3
    assert notes.est_tokens("abcdefg") == 2
    plan = {"mode": "new", "role": "coder", "title": "가", "first_prompt": "A", "reasons": ["x"]}
    edited = {"mode": "attach", "role": "coder", "title": "가", "first_prompt": "B", "reasons": ["y"]}
    assert notes.changed_fields(plan, edited) == ['mode "new"→"attach"', "첫 글 고침"]   # 이유는 사람이 고치는 칸이 아니다
    assert notes.changed_fields(plan, None) == []


def test_load_wake(tmp_path):
    p = tmp_path / "w.toml"
    p.write_text('enabled = true\ndaily_max = 2\npublic_url = "https://x.dev/"\nkinds = ["build_failed", "모름"]\n', encoding="utf-8")
    r = load_wake(p)
    assert (r.daily_max, r.public_url, r.kinds) == (2, "https://x.dev", ["build_failed"])
    assert load_wake(tmp_path / "없음.toml").enabled is False


def with_db(fn):
    """실제 DB — 시험 전용 프로젝트 이름으로 쓰고, 끝나면 그 이름의 행만 지운다(엔진은 한 이벤트 루프 안에서)."""
    async def run():
        eng = make_engine(Settings())
        proj = "zz-test-" + uuid.uuid4().hex[:8]
        try:
            await fn(eng, proj)
        finally:
            async with eng.begin() as c:
                await c.execute(text("DELETE FROM foreman_note WHERE project = :p"), {"p": proj})
                await c.execute(text("DELETE FROM dispatch WHERE project = :p OR wake_key LIKE :k"), {"p": proj, "k": f"%{proj}%"})
            await eng.dispose()
    asyncio.run(run())


def test_notes_check_apply_render():
    async def go(eng, proj):
        async with eng.begin() as c:
            ops, warn = await notes.check_ops(c, proj, [
                {"op": "add", "kind": "thread", "body": "발볼 검증 120켤레 — 80까지", "source": "세션 156"},
                {"op": "add", "kind": "decision", "body": "런슈즈 저장소엔 시킨 것만", "source": "아무말"},
                {"op": "add", "kind": "structure", "body": "src/ 구조"},              # 쌓지 않는 종류 — 빠진다
                {"op": "retire", "id": 999999999},                                   # 남의 · 없는 줄 — 빠진다
            ])
            assert [o["kind"] for o in ops] == ["thread", "decision"]
            assert ops[1]["source"] == "" and any("출처" in w for w in warn)
            assert any("모르는" in w or "비었음" in w for w in warn) and any("지금 노트가 아닙니다" in w for w in warn)
            ops[1]["on"] = False                                                     # 사람이 끈 제안은 반영 안 됨
            ids = await notes.apply(c, proj, ops, dispatch_id=7, session_id=201, head="abc")
            assert len(ids) == 1
            act = await notes.active(c, proj)
            assert act[0]["refs"] == {"sessions": [201], "head": "abc"} and act[0]["source"] == "세션 156"
            # 바꾸기 — 옛 줄은 내려가고(이력) 새 줄이 세션을 이어받는다
            ops2, _ = await notes.check_ops(c, proj, [{"op": "update", "id": ids[0], "body": "발볼 검증 — 100까지", "source": ""}])
            assert ops2[0]["kind"] == "thread"
            new = await notes.apply(c, proj, ops2, dispatch_id=8, session_id=205, head="def")
            act = await notes.active(c, proj)
            assert [n["id"] for n in act] == new and act[0]["refs"]["sessions"] == [201, 205]
            assert act[0]["source"] == "dispatch #8"                                 # 사람의 요청이 근거
            old = (await c.execute(text("SELECT retired_at IS NOT NULL, replaced_by FROM foreman_note WHERE id = :i"), {"i": ids[0]})).first()
            assert old == (1, new[0])
            # 낡음 — 확인 시각을 과거로 돌리면 그 뒤 세션 201의 활동이 ⚠로 붙는다(세션 201은 이 대화 — 이벤트가 있다)
            await c.execute(text("UPDATE foreman_note SET checked_at = :t, refs = :r WHERE id = :i"),
                            {"t": datetime(2026, 11, 1), "r": json.dumps({"sessions": [201]}), "i": new[0]})
            r = await notes.render(c, proj)
            assert "⚠ 확인 뒤 세션 201에 활동 있음" in r["text"] and r["folded"] == 0
            # 상한 — 넘친 줄은 지우지 않고 접는다
            for k in range(12):
                await c.execute(text("INSERT INTO foreman_note (project, kind, body, source, checked_at) VALUES (:p, 'decision', :b, 'dispatch #1', NOW(3))"),
                                {"p": proj, "b": f"판단 {k} " + "가" * 280})
            r = await notes.render(c, proj)
            assert r["tokens"] <= notes.TOKEN_CAP and r["folded"] > 0
            assert len(await notes.active(c, proj)) == 13
            assert await notes.retire_by_hand(c, new[0]) and not await notes.retire_by_hand(c, new[0])
    with_db(go)


class FakeDispatcher:
    def __init__(self, eng, proj, fail=False):
        self.eng, self.proj, self.fail, self.calls = eng, proj, fail, []

    async def plan(self, request, project, origin, wake_key, wake_text):
        self.calls.append((project, wake_key))
        if self.fail:
            raise Refused("디스패처가 180초 안에 답하지 않았습니다")
        async with self.eng.begin() as c:
            r = await c.execute(text("INSERT INTO dispatch (origin, project, wake_key, wake_text, request, status) "
                                     "VALUES ('wake', :p, :k, :w, :r, 'planned')"), {"p": self.proj, "k": wake_key, "w": wake_text, "r": request})
        return {"dispatch_id": r.lastrowid, "plan": {"project": self.proj, "repo": "/x", "mode": "new", "role": "inspector",
                                                       "read_only": True, "title": "빌드 #9 실패 원인", "reasons": ["Jenkins 로그"]}}


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda p: SimpleNamespace(prefix="[시험]"))

    def send_direct(self, project, kind, sid, msg):
        self.sent.append((project, kind, msg))


def test_waker_plans_once_and_caps():
    async def go(eng, proj):
        n, d = FakeNotifier(), FakeDispatcher(eng, proj)
        async with eng.connect() as c:          # 오늘 이미 있는 자동 계획 수(실제 DB) — 상한을 그 위로 잡는다
            # 코드와 같은 "오늘"(KST 자정부터) — 24시간 전으로 잡으면 자정 직후 base가 커져 상한이 높아졌다(11-09 00:04 실패)
            kst = datetime.now(UTC) + timedelta(hours=9)
            day0 = (kst.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=9)).replace(tzinfo=None)
            base = (await c.execute(text("SELECT COUNT(*) FROM dispatch WHERE origin = 'wake' AND created_at >= :t"), {"t": day0})).scalar()
        w = Waker(eng, d, n, WakeRules(daily_max=base + 2, public_url="https://f.dev"))
        w.failure(proj, "build_failed", f"build:{proj}:1", "❌ 파이프라인 실패 · Jenkins 빌드\n커밋 abc")
        await asyncio.gather(*w._tasks)
        assert len(d.calls) == 1 and n.sent[-1][1] == "wake"
        msg = n.sent[-1][2]
        assert msg.startswith("[시험] 🧭 파이프라인 실패 — 디스패처가 이렇게") and "빌드 #9 실패 원인 — 점검 · 읽기 전용 · 새 세션" in msg and "https://f.dev/?dispatch=" in msg
        w.failure(proj, "build_failed", f"build:{proj}:1", "같은 실패")             # 같은 실패 — 다시 계획하지 않는다
        w.failure(proj, "모르는종류", f"x:{proj}", "무시")
        await asyncio.gather(*w._tasks)
        assert len(d.calls) == 1
        w.failure(proj, "no_build", f"nobuild:{proj}:2", "빌드 알림 없음")
        w.failure(proj, "no_build", f"nobuild:{proj}:3", "빌드 알림 없음")          # 상한 — 그날 한 번 알림
        w.failure(proj, "no_build", f"nobuild:{proj}:4", "빌드 알림 없음")
        await asyncio.gather(*w._tasks)
        assert len(d.calls) == 2 and sum("다 썼습니다" in m for _, _, m in n.sent) == 1
        # 계획을 못 세우면 그것도 알린다(조용한 고장이 되지 않게)
        n2 = FakeNotifier()
        w2 = Waker(eng, FakeDispatcher(eng, proj, fail=True), n2, WakeRules(daily_max=10 ** 6))
        w2.failure(proj, "ingest_stuck", f"ingest:{proj}", "⚠ 적재 막힘")
        await asyncio.gather(*w2._tasks)
        assert "계획을 세우지 못했습니다" in n2.sent[-1][2]
    with_db(go)
