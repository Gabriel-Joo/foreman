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
