"""실패 알림이 묶음으로 미뤄지지 않는지 코드를 훑어 본다(11-17 사용자 「실패는 바로」, 관리자 410 일감).

514(log/foreman-5_fail_now_unpriced_20261117.md)는 묶음 종류(kind)마다 notify.py와 handoff.py를 읽어 표를 만들었다.
그래서 다른 모듈이 HandoffManager._notify를 빌려 부르는 곳(bridge/losscheck.py, bridge/promote.py의 self.m._notify)이
빠졌다. 이 시험은 종류가 아니라 「알림을 부르는 곳」에서 출발한다.

- bridge/ 아래 모든 .py에서 `_notify(...)`, `send_direct(...)` 호출을 찾는다
- 호출 안 글자(문자열 상수, f-string의 글자 부분)에 「실패」, 「시간 초과」, 「못」이 들면 실패 알림으로 본다
- 실패 알림은 다음 가운데 하나여야 한다. fail= 인자(HandoffManager._notify), later=False, 글에 [digest] urgent_marks
  (⚠ ❌ 🛑 ⏰ ❓), 또는 종류가 [digest] kinds 밖(묶음으로 갈 수 없다)
- 종류를 모르는 _notify(아래 NOTIFY_KIND_BY_MODULE에 없는 모듈)는 묶음 종류로 본다. 새 모듈이 _notify를 만들면 여기에 적어야 시험이 지난다
"""

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.notify import Rules

ROOT = Path(__file__).resolve().parents[1]
FAIL_WORDS = ("실패", "시간 초과", "못")
DIGEST_KINDS = Rules().digest_kinds
URGENT = Rules().urgent_marks

# 모듈 안 self._notify가 보내는 종류. handoff.py의 _notify는 kind= 인자, 없으면 handoff
NOTIFY_KIND_BY_MODULE = {
    "bridge/handoff.py": "handoff",
    "bridge/losscheck.py": "handoff",      # self.m._notify, m은 HandoffManager
    "bridge/promote.py": "handoff",
    "bridge/mergeprep.py": "merge",
    "bridge/inspector_close.py": "insp",
    "bridge/managers.py": "manager",
    "bridge/handover.py": "manager",
}


def _texts(call: ast.Call) -> str:
    """호출 인자 안의 글자(문자열 상수와 f-string 글자). rule=, kind=, 그리고 mergeprep의 키 인자는 뺀다."""
    out = []
    nodes = list(call.args) + [k.value for k in call.keywords if k.arg not in ("rule", "kind")]
    for n in nodes:
        for x in ast.walk(n):
            if isinstance(x, ast.Constant) and isinstance(x.value, str) and not x.value.startswith("mergeprep:"):
                out.append(x.value)
    return "".join(out)


def _module_consts(tree: ast.Module) -> dict[str, str]:
    return {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}


def _kind(call: ast.Call, rel: str, consts: dict[str, str]) -> str | None:
    """보내는 종류. 알 수 없으면 None(묶음 종류로 본다)."""
    kw = {k.arg: k.value for k in call.keywords}
    if call.func.attr == "send_direct":     # type: ignore[union-attr]
        node = call.args[1] if len(call.args) > 1 else kw.get("kind")
    else:
        node = kw.get("kind")
        if node is None:
            return NOTIFY_KIND_BY_MODULE.get(rel)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _wrapper_bodies(tree: ast.Module) -> set[int]:
    """_notify 정의 안의 호출(감싸는 함수가 넘겨받은 글을 보내는 곳)은 부른 쪽에서 본다."""
    skip: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_notify":
            skip |= {id(x) for x in ast.walk(n)}
    return skip


def scan() -> tuple[list[dict], list[dict]]:
    """(실패 알림 모두, 그 가운데 묶음으로 갈 수 있는 것)."""
    fails, bad = [], []
    for p in sorted((ROOT / "bridge").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8"))
        consts, skip = _module_consts(tree), _wrapper_bodies(tree)
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr in ("_notify", "send_direct")) or id(call) in skip:
                continue
            txt = _texts(call)
            if not any(w in txt for w in FAIL_WORDS):
                continue
            kw = {k.arg: k.value for k in call.keywords}
            later = kw.get("later")
            fail = kw.get("fail")
            ok = ((fail is not None and not (isinstance(fail, ast.Constant) and not fail.value))
                  or (isinstance(later, ast.Constant) and later.value is False)
                  or any(m in txt for m in URGENT))
            kind = _kind(call, rel, consts)
            item = {"where": f"{rel}:{call.lineno}", "kind": kind, "text": txt[:80]}
            fails.append(item)
            if not ok and (kind is None or kind in DIGEST_KINDS):
                bad.append(item)
    return fails, bad


def test_failure_notifies_never_wait_for_digest():
    fails, bad = scan()
    assert len(fails) >= 20, f"실패 알림을 거의 못 찾았습니다(훑기가 고장 났을 수 있습니다): {len(fails)}"
    assert not bad, "묶음 종류인데 fail=True, later=False, ⚠ 어느 것도 없는 실패 알림:\n" + "\n".join(
        f"{b['where']} [{b['kind']}] {b['text']}" for b in bad)


def test_scan_catches_the_five_514_missed():
    """514가 놓친 다섯이 훑기에 잡히는 꼴인지(fail= 인자를 떼면 bad로 나오는지) 본다."""
    src = "class X:\n    def f(self, row, e):\n        self.m._notify(row, f'목록 실패: {e}')\n"
    tree = ast.parse(src)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_notify")
    assert any(w in _texts(call) for w in FAIL_WORDS)
    assert _kind(call, "bridge/promote.py", {}) in DIGEST_KINDS
    assert "fail" not in {k.arg for k in call.keywords}


class _M:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def _notify(self, row, msg, kind="handoff", fail=False):
        self.calls.append((msg, fail))


def test_losscheck_exception_notifies_now(monkeypatch):
    from bridge.losscheck import LossChecker
    m = _M()
    lc = LossChecker(m, mask=SimpleNamespace(deep=lambda x: x))

    async def boom(*a, **k):
        raise RuntimeError("x")

    async def save(*a, **k):
        return None
    monkeypatch.setattr(lc, "_run_inner", boom)
    monkeypatch.setattr(lc, "_save", save)
    asyncio.run(lc._run(1, SimpleNamespace(project="foreman"), "p", "r"))
    assert m.calls and m.calls[0][1] is True and "실패" in m.calls[0][0]


@pytest.mark.parametrize("why", ["120초 안에 돌아오지 않았습니다", "세션이 끝났습니다"])
def test_promote_list_failure_notifies_now(monkeypatch, why):
    from bridge.promote import Promoter
    m = _M()
    pr = Promoter(m)

    async def wait(*a, **k):
        return None, "", why

    async def save(*a, **k):
        return None
    monkeypatch.setattr(pr, "_wait", wait)
    monkeypatch.setattr(pr, "_save", save)
    asyncio.run(pr._wait_list(SimpleNamespace(project="foreman"), 1, "r", "p", 0, None))
    assert m.calls == [(f"대화에서만 정한 것 문서에 적기 — 목록 실패: {why}", True)]
