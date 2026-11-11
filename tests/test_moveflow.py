"""새 세션으로 옮기기 한 흐름 스위치(11-11, config/handoff.toml [move] one_flow — bridge/handoff.py move_flow_on)."""

from pathlib import Path

from bridge.handoff import move_flow_on

CFG = Path(__file__).resolve().parent.parent / "config" / "handoff.toml"


def test_switch_off_by_default_and_reads_file(tmp_path):
    assert move_flow_on(CFG) is False                       # 처음엔 꺼 둔다 — 켜는 것은 사용자
    p = tmp_path / "h.toml"
    p.write_text("[move]\none_flow = true\n")
    assert move_flow_on(p) is True
    p.write_text("[merge_prep]\nenabled = false\n")
    assert move_flow_on(p) is False                         # 칸이 없으면 꺼짐
    p.write_text("[[[")
    assert move_flow_on(p) is False                         # 깨지면 꺼짐(옛 흐름)
    assert move_flow_on(tmp_path / "none.toml") is False
