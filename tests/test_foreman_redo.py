"""계획 「다시 받기」가 앞 계획을 끊는다(11-14, 받은 할 일 #18) — 가짜 claude 스크립트로 시험한다."""

import asyncio
import itertools
import os
import stat

import pytest

from bridge import foreman as fm

FAKE = """#!/bin/bash
# 인자로 받은 이름(첫 줄 stdin)에 따라 PID를 남기고 오래 자다가 계획 JSON을 낸다
read -r first
echo $$ >> "$FAKE_PIDS"
if [ "$FAKE_SLEEP" != 0 ]; then sleep "$FAKE_SLEEP" >/dev/null 2>&1 </dev/null & wait $!; fi
echo '{"result": "```json\\n{\\"project\\": \\"zz\\", \\"mode\\": \\"new\\", \\"first_prompt\\": \\"가\\"}\\n```"}'
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return "Z" not in open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False


def _make(tmp_path, monkeypatch, sleep="30"):
    exe = tmp_path / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    pids = tmp_path / "pids"
    monkeypatch.setenv("FAKE_PIDS", str(pids))
    monkeypatch.setenv("FAKE_SLEEP", sleep)
    d = fm.ForemanDispatcher(None, tmp_path, None, lambda: [(str(tmp_path), 1, "zz", 1)], claude_bin=str(exe), workdir=tmp_path / "wd")
    ids, status = itertools.count(1), {}

    async def noop(*a, **k):
        return ""

    async def record(*a, **k):
        return next(ids)

    async def finish(did, plan, st, err, t0):
        status[did] = (st, err)

    async def check(plan, did=None):
        return plan

    async def rec_cli(*a, **k):
        return None

    d.sweep_notes, d.context, d._record, d._finish, d.check = noop, noop, record, finish, check
    monkeypatch.setattr(fm, "record_cli", rec_cli)
    return d, pids, status


def test_redo_kills_first_and_ignores_its_result(tmp_path, monkeypatch):
    async def run():
        d, pids, status = _make(tmp_path, monkeypatch)
        t1 = asyncio.create_task(d.plan("가", "zz"))
        for _ in range(100):                     # 앞 프로세스가 뜰 때까지
            await asyncio.sleep(0.05)
            if pids.exists() and pids.read_text().split():
                break
        first = int(pids.read_text().split()[0])
        assert _alive(first) and list(d.running) == [1]
        monkeypatch.setenv("FAKE_SLEEP", "0")    # 새 계획은 바로 끝난다
        r2 = await d.plan("나", "zz")
        with pytest.raises(fm.Refused):
            await t1
        return first, r2, status, d

    first, r2, status, d = asyncio.run(run())
    assert not _alive(first)                                  # 앞 프로세스가 끝났다
    assert status[1] == ("replaced", "다시 받기로 끊었습니다")   # 조용히 사라지지 않고 기록
    assert status[2][0] == "planned" and r2["dispatch_id"] == 2   # 새 결과만 남는다
    assert d.running == {} and d._procs == {} and d._cut == set()   # 남은 시간 표시도 하나도 안 남는다


def test_redo_during_spawn_still_cuts(tmp_path, monkeypatch):
    """앞 계획이 아직 프로세스를 띄우는 중(_procs에 없음)에 끊겨도 결과를 버린다."""
    async def run():
        d, pids, status = _make(tmp_path, monkeypatch, sleep="0")
        d.running[1], d._origin[1] = "zz", "human"
        assert d._cut_earlier(2, "zz") == [1]
        assert 1 in d._cut
        # 같은 방이 아닌 계획 · 자동(wake) 계획은 끊지 않는다
        d.running.update({3: "other", 4: "zz"})
        d._origin.update({3: "human", 4: "wake"})
        assert d._cut_earlier(9, "zz") == [1]
    asyncio.run(run())
