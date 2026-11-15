"""포스트잇(11-15, bridge/postit.py) — 그물 · 점검 판정 · README 한계 줄 · 쌓임 기준. DB 시험은 tests/test_stage2_db.py.

그물 예문은 log/foreman-6_postit_proposal_20261115.md 1-2 판정 목록의 실제 말(턴 번호)이다. 그물이 깨져 늘 0이 되면 여기서 걸린다.
"""
from datetime import datetime, timedelta

import pytest

from bridge import postit as pi
from bridge.assembler import Assembler

REAL = {
    6885: "「나중에 할 일」에 올려라. 지금 맡기지 마라",
    6602: "시험 DB를 세션마다 나누는 일을 「나중에 할 일」에 넣어 주십시오",
    6549: "README 「나중에 할 일」의 「[⌂] 감독실 현황판의 「FOREMAN」이 끊긴다」 줄에 한 줄 더합니다",
    6624: "그리고 README 「나중에 할 일」의 「역할 규칙을 글이 아니라 권한으로 막기」 줄에 한 줄 더해 주십시오.",
    7088: "CLAUDE.md에 그 사실만 적어 두게 해라. 나중에 정한다",
    7328: "나중에 자꾸 탈나면 그때 다시 본다",
    6615: "「docs 커밋을 묶는 기준」은 제가 정하겠습니다. 지금은 두십시오",
    6872: "둘 다 지금은 하지 마라",
    7780: "쌓이면 그때 다시 이야기하자",
    0: "이건 포스트잇에 올려라",
}
FAKE = {
    7431: "나중에 붙은 쪽 크기에 맞춰라",
    6910: "「나중에 할 일」이 아니라 지금 고칠 일이다",
    7689: "README 나중에 할 일에서 그 줄 지워",
    7615: "단추 이름은 「그냥 끝내기(나중에 정함)」로",
    6580: "끝낸 줄은 README 「나중에 할 일」에서 뺍니다",
    1: "지금 바로 해",
}


@pytest.mark.parametrize("tid,t", REAL.items())
def test_net_catches_real_later(tid, t):
    assert pi.net_hits(t), (tid, t)


@pytest.mark.parametrize("tid,t", FAKE.items())
def test_net_skips_fake_later(tid, t):
    assert not pi.net_hits(t), (tid, t, pi.net_kind(t))


def test_net_sees_inside_pasted_and_clips_long_lines():
    t = '<pasted_content id="x">\n지시서 머리\n' + "가" * 400 + " 「포스트잇」에 넣어라 " + "나" * 400 + "\n</pasted_content>"
    hits = pi.net_hits(t)
    assert len(hits) == 1 and "포스트잇」에 넣어라" in hits[0]
    assert hits[0].startswith("…") and hits[0].endswith("…") and len(hits[0]) < 500


def test_merge_card_is_not_human():
    """합치기 카드 · 합치기 결과(브리지가 넣는 글)는 사람 말이 아니다 — 그물 · 겹침 · 마지막 사람 말에서 빠진다."""
    card = '<pasted_content id="a">\n[FOREMAN 합치기 카드] 세션 12 「x」 cc/x 커밋 2개 · 미루기: {"action":"skip"}\n</pasted_content>'
    assert Assembler._origin({}, card) == "merge_card"
    assert Assembler._origin({}, "[FOREMAN 합치기] 관리자가 승인해 세션 3 합쳤다") == "merge_card"
    assert Assembler._origin({}, "합치기 카드는 나중에 고치자") == "human"


def test_parse_check_needs_code_ref_for_done():
    known = {"p:1": "a", "p:2": "b", "L:1": "| 한계 |", "p:3": "c"}
    body = ('[{"id": "p:1", "verdict": "끝남", "evidence": "bridge/postit.py:120", "reason": "됐다"},'
            ' {"id": 2, "verdict": "끝남", "evidence": "c0ffee1 커밋 제목", "reason": "커밋이 있다"},'
            ' {"id": "L:1", "verdict": "끝남", "evidence": "tests/test_postit.py::test_x"},'
            ' {"id": "p:3", "verdict": "남음", "reason": "반만", "coder": true},'
            ' {"id": "p:9", "verdict": "끝남", "evidence": "a.py:1"}, {"id": "p:1", "verdict": "남음"}]')
    got = {g["item"]: g for g in pi.parse_check(body, known)}
    assert set(got) == {"p:1", "p:2", "L:1", "p:3"}                 # 재료에 없던 p:9 · 두 번째 p:1은 버린다
    assert got["p:1"]["verdict"] == "done" and got["L:1"]["verdict"] == "done"
    assert got["p:2"]["verdict"] == "unknown" and "코드 자리" in got["p:2"]["reason"]   # 커밋만으로는 끝남이 아니다
    assert got["p:3"]["coder"] is True and got["p:1"]["coder"] is False
    assert pi.parse_check("JSON 아님", known) == []


def test_readme_limits(tmp_path):
    (tmp_path / "README.md").write_text("# x\n## 6. 로드맵\n### 알려진 한계\n| 무엇 | 까닭 |\n|---|---|\n| CI 없음 | 손으로 |\n"
                                        "- 밖에서는 못 본다\n### 다음 절\n- 아님\n", encoding="utf-8")
    assert pi.readme_limits(str(tmp_path)) == ["| CI 없음 | 손으로 |", "- 밖에서는 못 본다"]
    (tmp_path / "README.md").write_text("# x\n## 나중에 할 일\n- a\n", encoding="utf-8")
    assert pi.readme_limits(str(tmp_path)) is None                  # 절이 없으면 없다고(빈 목록과 다르다)


def test_nudge_of(tmp_path):
    now = datetime(2026, 11, 15, 12)
    cf = {"open_max": 20, "stale_days": 7, "refresh_days": 7}
    assert pi.nudge_of(0, None, None, cf, now) is None
    assert pi.nudge_of(3, now - timedelta(days=1), None, cf, now) is None
    assert "할 일 20장" in pi.nudge_of(20, now - timedelta(days=1), None, cf, now)["why"]
    n = pi.nudge_of(2, now - timedelta(days=8), None, cf, now)
    assert "8일째" in n["why"] and "한 번도" in n["why"]
    n = pi.nudge_of(2, now - timedelta(days=3), now - timedelta(days=9), cf, now)
    assert n["since_check"] == 9 and "[갱신] 9일 없음" in n["why"]
    assert pi.conf(tmp_path / "없음.toml") == pi.CONF_DEFAULT        # 파일이 없으면 기본값
    (tmp_path / "s.toml").write_text("[postit]\nopen_max = 5\n", encoding="utf-8")
    assert pi.conf(tmp_path / "s.toml") == {**pi.CONF_DEFAULT, "open_max": 5}


def test_check_material_and_prompt():
    now = datetime(2026, 11, 15, 3)
    m = pi.check_material("foreman", [{"id": 7, "body": "질문 카드 접기", "created_at": now, "source": "chat", "confirmed": False}],
                          None, ["abc 2026-11-15 feat: x"], now)
    assert "### p:7 (대화에서 찾음" in m and "확인 전" in m and "아직 없다" in m and "끝남의 근거가 아니다" in m
    p = pi.CHECK_PROMPT.format(req="r1", project="foreman", limit=pi.README_LIMIT, materials="/m.md", tag=pi.CHECK_TAG)
    assert "<<<FOREMAN-POSTIT-CHECK r=r1>>>" in p and "파일을 고치지 마라" in p and "코드 자리" in p
