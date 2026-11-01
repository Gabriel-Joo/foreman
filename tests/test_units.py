from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from bridge.api.auth import token_ok
from bridge.config import Settings
from bridge.models import TARGET_MAX, EventIn, EventSource, EventType, clip_target


def test_clip_target_short_unchanged():
    assert clip_target("git status") == ("git status", None)
    assert clip_target(None) == (None, None)
    s = "x" * TARGET_MAX
    assert clip_target(s) == (s, None)


def test_clip_target_long_marks_and_keeps_full():
    s = "y" * (TARGET_MAX + 500)
    clipped, full = clip_target(s)
    assert len(clipped) == TARGET_MAX
    assert clipped.endswith("…")
    assert full == s


def test_token_ok():
    assert token_ok("a" * 40, "a" * 40)
    assert not token_ok("a" * 40, "b" * 40)
    assert not token_ok(None, "a" * 40)
    assert not token_ok("", "a" * 40)


def test_short_token_rejected():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            mysql_password=SecretStr("x"),
            foreman_api_token=SecretStr("short"),
            foreman_hook_token=SecretStr("h" * 40),
        )


def test_naive_ts_is_utc():
    ev = EventIn(source=EventSource.DEBUG, type=EventType.DEBUG, ts=datetime(2026, 11, 2, 0, 0))
    assert ev.ts.tzinfo is UTC


def test_mask_exact_only_secret_keys(tmp_path):
    from bridge.mask import Masker
    env = tmp_path / ".env.x"
    env.write_text("MYSQL_USER=foreman_app\nMY_PASSWORD=Zq8vLm2pXy\nCHAT_ID=123456789\n", encoding="utf-8")
    m = Masker([env])
    assert m.text("user foreman_app pw Zq8vLm2pXy") == "user foreman_app pw «masked:MY_PASSWORD»"


def test_mask_patterns():
    from bridge.mask import Masker
    m = Masker([])
    assert "«masked:telegram-bot-token»" in m.text("bot 1234567890:" + "A" * 35)
    assert m.text("curl -H 'Authorization: Bearer abcdefghijklmnop1234'").endswith("Bearer «masked»'")
    assert m.text("export API_KEY=abcdef123456") == "export API_KEY=«masked»"
    assert m.text("max_tokens: 4096") == "max_tokens: 4096"          # 6자 미만은 그대로
    assert m.text("regex sk-ant-[A-Za-z0-9_-]{20,}") == "regex sk-ant-[A-Za-z0-9_-]{20,}"  # 키 모양이 아니다
    assert m.deep({"a": ["x" * 10]}, clip=4) == {"a": ["xxxx…(10자)"]}
