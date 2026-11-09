"""'!' 명령이 글로 들어간 것 알림(11-09, bridge/bang_watch.py)."""

from datetime import datetime
from types import SimpleNamespace

from bridge.bang_watch import BangWatch, bang_text


def test_bang_text():
    # 11-07 ~ 11-09에 실제로 글로 간 모양(앞 공백 — 0x20 0x21)
    assert bang_text(" !bash /tmp/reviews-20261109/dump.sh") == "!bash /tmp/reviews-20261109/dump.sh"
    assert bang_text("\n  !scripts/load-prod.sh --apply\n둘째 줄") == "!scripts/load-prod.sh --apply"
    assert bang_text("!echo HELLO") == "!echo HELLO"        # 훅에 이 모양으로 오면 실행이 안 된 것
    assert bang_text("<bash-input>echo HELLO</bash-input>") is None   # 실행된 것
    assert bang_text("! 뒤가 공백") is None
    assert bang_text("이거 해 줘! 지금") is None
    assert bang_text(None) is None


class _Conn:
    def __init__(self, seen):
        self.seen = seen

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, q, params):
        sql = str(q)
        if "FROM notification" in sql:
            return SimpleNamespace(first=lambda: (1,) if params["r"] in self.seen else None)
        return SimpleNamespace(first=lambda: ("배포 점검", "runshoes"))


async def test_alert_once_per_prompt():
    seen: set[str] = set()
    sent = []
    notifier = SimpleNamespace(rules=SimpleNamespace(for_project=lambda n: SimpleNamespace(prefix="[런슈즈]")),
                               send_direct=lambda p, k, s, m, rule=None: sent.append((p, k, s, m, rule)))
    w = BangWatch(SimpleNamespace(connect=lambda: _Conn(seen)), notifier)
    ts = datetime(2026, 11, 9, 13, 17)
    key = await w.alert(217, "!bash dump.sh", ts)
    assert key == "bang:217:20261109131700" and sent[-1][1] == "bang"
    assert sent[-1][3].startswith("[런슈즈] ⚠ '!' 명령이 실행되지 않고 글로 들어갔습니다 — 「배포 점검」") and "▶ !bash dump.sh" in sent[-1][3]
    seen.add(key)
    assert await w.alert(217, "!bash dump.sh", ts) is None and len(sent) == 1
