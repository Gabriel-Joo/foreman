"""새 세션으로 옮기기 한 흐름 스위치(11-11, config/handoff.toml [move] one_flow — bridge/handoff.py move_flow_on)."""

from bridge.handoff import move_flow_on


def test_switch_off_by_default_and_reads_file(tmp_path):
    # 실제 config/handoff.toml 대신 시험용 파일만 읽는다(11-12 사용자 — 스위치를 켜고 끌 때마다 시험이 깨지지 않게)
    p = tmp_path / "h.toml"
    p.write_text("[move]\none_flow = false\n")
    assert move_flow_on(p) is False                         # 꺼 둔 값 그대로
    p.write_text("[move]\none_flow = true\n")
    assert move_flow_on(p) is True
    p.write_text("[merge_prep]\nenabled = false\n")
    assert move_flow_on(p) is False                         # 칸이 없으면 꺼짐
    p.write_text("[[[")
    assert move_flow_on(p) is False                         # 깨지면 꺼짐(옛 흐름)
    assert move_flow_on(tmp_path / "none.toml") is False
