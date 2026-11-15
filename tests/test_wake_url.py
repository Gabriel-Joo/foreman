"""자동 기상 알림의 [시작] 링크(11-15) — 안 풀리는 바깥 주소가 조용히 나가지 않게."""

import asyncio
import socket

from bridge.wake import LOCAL_URL, WakeRules, check_public_url, is_local_url, link_base, load_wake


def test_link_base_falls_back_to_local():
    assert link_base(WakeRules(public_url="")) == LOCAL_URL
    assert link_base(WakeRules(public_url="https://x.dev")) == "https://x.dev"
    assert is_local_url(LOCAL_URL) and not is_local_url("https://x.dev")


def test_check_public_url_warns_when_name_does_not_resolve():
    def boom(host):
        raise socket.gaierror("Name or service not known")

    why = asyncio.run(check_public_url(WakeRules(public_url="https://foreman.nowhere.invalid"), boom))
    assert why and "foreman.nowhere.invalid" in why and "gaierror" in why and LOCAL_URL in why


def test_check_public_url_quiet_when_resolves_or_local():
    seen = []
    assert asyncio.run(check_public_url(WakeRules(public_url="https://ok.dev"), lambda h: seen.append(h))) is None
    assert seen == ["ok.dev"]
    boom = lambda h: (_ for _ in ()).throw(AssertionError("로컬 주소는 풀어 보지 않는다"))  # noqa: E731
    assert asyncio.run(check_public_url(WakeRules(public_url=""), boom)) is None
    assert asyncio.run(check_public_url(WakeRules(public_url="http://127.0.0.1:8000"), boom)) is None


def test_shipped_wake_toml_is_local():
    from pathlib import Path
    r = load_wake(Path(__file__).resolve().parent.parent / "config" / "wake.toml")
    assert is_local_url(link_base(r))      # 터널을 열지 않으므로 바깥 이름을 두지 않는다(README 3.13)
