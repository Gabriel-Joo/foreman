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
                 '[defaults]\ncoder = "opus"\ninspector = "sonnet"\ncicd = "nope"\n', encoding="utf-8")
    m = Models(p)
    assert [c["id"] for c in m.choices] == ["opus", "sonnet"]     # 셸에 들어갈 수 없는 id는 버린다
    assert m.defaults == {"coder": "opus", "inspector": "sonnet"}  # 목록에 없는 기본값은 버린다
    assert m.pick("sonnet", "coder") == "sonnet"
    assert m.pick("haiku", "inspector") == "sonnet"                # 목록에 없으면 역할 기본값
    assert m.pick(None, None) == "opus"                            # 역할이 없으면 coder
    assert m.pick(None, "cicd") is None                            # 기본값도 없으면 CC 설정(--model 없이)


def test_missing_file_means_cc_default(tmp_path):
    m = Models(tmp_path / "없음.toml")
    assert m.choices == [] and m.pick("opus", "coder") is None


def test_repo_config_covers_dispatcher_roles():
    m = Models(DEFAULT_PATH)
    ids = {c["id"] for c in m.choices}
    assert {"opus", "sonnet", "haiku"} <= ids
    for r in ROLES:
        assert m.default_for(r) in ids, r
