from bridge.foreman import ROLES
from bridge.model_choice import DEFAULT_PATH, Models, family, label


def test_label_and_family():
    assert label("claude-opus-5-5") == "Opus 5.5"
    assert label("claude-haiku-4-5-20251001") == "Haiku 4.5"
    assert label("claude-opus-4-8") == "Opus 4.8"
    assert label("claude-fable-5-1") == "Fable 5.1"
    assert label("gpt-x") == "gpt-x" and label(None) == ""
    assert family("claude-sonnet-5-5") == "sonnet" and family("weird") == "other" and family(None) == ""


def test_pick_valid_or_role_default(tmp_path):
    p = tmp_path / "m.toml"
    p.write_text('choices = [{id="opus", label="Opus"}, {id="sonnet", label="Sonnet"}, {id="bad id; rm", label="x"}]\n'
                 '[defaults]\ncoder = "opus"\ninspector = "sonnet"\nscribe = "nope"\n', encoding="utf-8")
    m = Models(p)
    assert [c["id"] for c in m.choices] == ["opus", "sonnet"]     # 셸에 들어갈 수 없는 id는 버린다
    assert m.defaults == {"coder": "opus", "inspector": "sonnet"}  # 목록에 없는 기본값은 버린다
    assert m.pick("sonnet", "coder") == "sonnet"
    assert m.pick("haiku", "inspector") == "sonnet"                # 목록에 없으면 역할 기본값
    assert m.pick(None, None) == "opus"                            # 역할이 없으면 coder
    assert m.pick(None, "scribe") is None                           # 기본값도 없으면 CC 설정(--model 없이)


def test_missing_file_means_cc_default(tmp_path):
    m = Models(tmp_path / "없음.toml")
    assert m.choices == [] and m.pick("opus", "coder") is None


def test_switch_screen_counts():
    from bridge.api.sessions import _counts
    old = "❯ /model sonnet\n  ⎿  Set model to Sonnet 5.5 and saved as your default for new sessions\n"
    ask = "   Switch model?\n   ❯ 1. Yes, switch to Haiku 5.5\n     2. No, go back\n"
    assert _counts(None) == (0, 0)
    assert _counts(old) == (1, 0)                                   # 옛 결과 줄 — 보내기 전 수로 센다
    assert _counts(old + "❯ /model haiku\n" + ask) == (1, 1)        # 새 확인 창
    assert _counts(old + ask.replace("❯ 1.", "  1.")) == (1, 0)     # 커서가 Yes에 없으면 고르지 않는다
    assert _counts(old + "❯ /model haiku\n  ⎿  Set model to Haiku 5.5\n") == (2, 0)


def test_repo_config_covers_dispatcher_roles():
    m = Models(DEFAULT_PATH)
    ids = {c["id"] for c in m.choices}
    # 11-14 사용자 — 버전까지 보이게, Fable도. CC 2.1.325가 이 id들을 받는 것을 실제로 확인했다(log/foreman-3_model_menu_20261114.md)
    assert {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"} <= ids
    assert all("·" not in (c["label"] + c.get("note", "")) for c in m.choices)   # 창 글에 가운뎃점을 쓰지 않는다
    for r in ROLES:
        assert m.default_for(r) in ids, r
    assert m.task("losscheck") in ids


def test_aliases_map_to_versioned_ids(tmp_path):
    """11-14 전 DB 값 · 계획 카드 값(opus 등 별칭)은 목록의 id로 바꿔 받는다 — [이어서] · 옮기기가 깨지지 않게."""
    p = tmp_path / "m.toml"
    p.write_text('choices = [{id="claude-opus-5-5", label="Opus 5.5"}, {id="claude-sonnet-5-5", label="Sonnet 5.5"}]\n'
                 '[aliases]\nopus = "claude-opus-5-5"\nsonnet = "claude-sonnet-5-5"\nhaiku = "claude-haiku-5-5"\n'
                 '[defaults]\ncoder = "opus"\ninspector = "claude-sonnet-5-5"\n[tasks]\nlosscheck = "sonnet"\n', encoding="utf-8")
    m = Models(p)
    assert m.aliases == {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}   # 목록에 없는 id를 가리키는 별칭은 버린다
    assert m.resolve("opus") == "claude-opus-5-5" and m.resolve("claude-sonnet-5-5") == "claude-sonnet-5-5"
    assert m.resolve("haiku") is None and m.resolve(None) is None and not m.valid("haiku")
    assert m.defaults == {"coder": "claude-opus-5-5", "inspector": "claude-sonnet-5-5"}   # 기본값의 별칭도 id로
    assert m.task("losscheck") == "claude-sonnet-5-5"
    assert m.pick("sonnet", "coder") == "claude-sonnet-5-5" and m.pick("haiku", "coder") == "claude-opus-5-5"
    assert m.view()["aliases"]["opus"] == "claude-opus-5-5"


def test_windows_by_id_before_family():
    from bridge.model_choice import load_windows, window_of
    w = {"claude-opus-5-5": 1_000_000, "opus": 300_000}
    assert window_of(w, "claude-opus-5-5") == 1_000_000      # id로 적은 값이 먼저
    assert window_of(w, "claude-opus-5") == 300_000          # 없으면 family
    assert window_of({"claude-haiku-4-5": 200_000}, "claude-haiku-4-5-20251001") == 200_000   # 날짜 꼬리를 떼고도
    real = load_windows(DEFAULT_PATH)
    assert window_of(real, "claude-opus-5-5") == 1_000_000
    assert window_of(real, "claude-fable-5-2") is None and window_of(real, "claude-opus-5") is None   # 모르면 모름(토큰만)
