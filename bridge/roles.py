"""세션 역할 — 이름 · 화면 이름 · 한 줄 설명의 한 곳(11-15, 454 제안 1 · 3, docs/roles.md).

API 검증(`bridge.api.handoff.SessionRole`) · 교장 계획(`bridge.foreman.ROLES` · 지시문) · 캐릭터 이름 · 역할 바꾸기(`bridge.handoff`) ·
알림 글(`bridge.wake`)이 모두 여기서 가져간다. 화면 쪽 같은 값은 `bridge/static/js/roles.js` 한 곳이고,
`tests/test_roles_agree.py`가 둘이 한 역할도 어긋나지 않는지 본다. 새 역할을 더하는 순서는 docs/roles.md 「3.」.

foreman(감독)은 감독실 캐릭터 몫이라 세션 역할이 아니다(고를 수 없다). helper · infra도 캐릭터 몫(`bridge.models.Role`).
"""

from __future__ import annotations

from typing import NamedTuple


class RoleInfo(NamedTuple):
    ko: str      # 화면 이름(배지 · 캐릭터 이름 · 알림 글)
    desc: str    # 한 줄 설명 — CLAUDE.md 「역할을 가르는 기준」과 같은 뜻. 화면(역할 고르기 칸) · 교장 지시문이 쓴다


# 순서는 화면 역할 고르기 칸의 순서다(첫째가 기본값)
ROLE_INFO: dict[str, RoleInfo] = {
    "coder": RoleInfo("코더", "코드를 고치거나 만듭니다"),
    "designer": RoleInfo("디자이너", "화면을 고칩니다. js, css, 테마, 캐릭터, 호버 글"),
    "manager": RoleInfo("관리자", "합치고 시험하고 push하고 기록합니다"),
    "scribe": RoleInfo("서기", "문서를 쓰고 맞춥니다"),
    "inspector": RoleInfo("조사", "읽고 알아봅니다. 고치지 않고 결과 log만 씁니다. 조사와 제안은 모두 여기입니다"),
}

SESSION_ROLES: tuple[str, ...] = tuple(ROLE_INFO)
ROLE_KO: dict[str, str] = {r: i.ko for r, i in ROLE_INFO.items()}
ROLE_DESC: dict[str, str] = {r: i.desc for r, i in ROLE_INFO.items()}
ROLE_OLD_KO: dict[str, str] = {"inspector": "점검"}   # 바꾸기 전 화면 이름(11-15 점검 → 조사) — 그 이름의 캐릭터(DB)를 새 이름으로(handoff._character_for)

# 턴 끝을 관리자에게 넘기는 작업 세션 역할(관리자 · 교장 · 조사가 아닌 것). notify · /api/dashboard가 같이 쓴다
WORKER_ROLES: frozenset[str] = frozenset({"coder", "scribe", "designer"})


def role_line() -> str:
    """교장 지시문 「3. role」 첫 줄 — `"coder"(코더 — 코드를 고치거나 만듭니다) · …`."""
    return " · ".join(f'"{r}"({i.ko} — {i.desc})' for r, i in ROLE_INFO.items())
