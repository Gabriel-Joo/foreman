"""역할 목록이 모든 곳에서 같은가(11-15, 454 제안 · docs/roles.md) — 새 역할이 한 곳만 빠져도 실패한다.

파이썬 한 곳(bridge/roles.py) ↔ JS 한 곳(bridge/static/js/roles.js) ↔ 그것을 쓰는 곳(API · 교장 · 알림 · 역할 고르기 칸) ↔
배지 색 · 테마 옷 색 · 한 줄 설명 · 역할 기본 모델 · DB 역할 값(bridge/models.Role).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bridge import foreman, handoff, roles, wake
from bridge.api import handoff as api
from bridge.model_choice import Models
from bridge.models import Role

REPO = Path(__file__).resolve().parent.parent
THEMES = ("office", "magic", "site", "plain")

_DUMP = """
const R = await import(process.argv[1]);
const P = await import(process.argv[2]);
const themes = {};
for (const n of JSON.parse(process.argv[3])) {
  const t = JSON.parse((await import('node:fs')).readFileSync(process.argv[4] + '/' + n + '/theme.json', 'utf8'));
  themes[n] = R.themeCloth(t);
}
console.log(JSON.stringify({ sessionRoles: R.SESSION_ROLES, label: R.ROLE_LABEL, desc: R.ROLE_DESC, color: R.ROLE_COLOR,
  cloth: R.ROLE_CLOTH, pick: P.ROLE_PICK, themes }));
"""


@pytest.fixture(scope="module")
def js() -> dict:
    if shutil.which("node") is None:
        pytest.skip("node 없음")
    js_dir = REPO / "bridge" / "static" / "js"
    r = subprocess.run(["node", "--input-type=module", "-e", _DUMP, (js_dir / "roles.js").as_uri(), (js_dir / "modelpick.js").as_uri(),
                        json.dumps(THEMES), str(REPO / "bridge" / "static" / "themes")],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_python_one_place():
    """파이썬 쪽은 모두 bridge/roles.py를 따른다."""
    want = list(roles.SESSION_ROLES)
    assert list(foreman.ROLES) == want
    assert list(api.SessionRole.__args__) == want
    assert list(handoff.ROLE_KO) == want and handoff.ROLE_KO is roles.ROLE_KO
    assert wake.ROLE_KO is roles.ROLE_KO
    assert set(roles.ROLE_DESC) == set(want) and all(roles.ROLE_DESC.values())
    assert roles.WORKER_ROLES <= set(want)
    assert set(want) <= {r.value for r in Role}                       # DB 역할 값(11-15 전에는 서기 · 관리자 · 디자이너가 없었다)
    for r in want:                                                    # 교장 지시문에 역할마다 이름과 한 줄 설명
        assert f'"{r}"({roles.ROLE_KO[r]} — {roles.ROLE_DESC[r]})' in foreman.INSTRUCTIONS, r
        assert Models().default_for(r), f"config/models.toml [defaults]에 {r}"   # 빠지면 코더 모델로 조용히 뜬다


def test_js_matches_python(js):
    """JS 한 곳이 파이썬과 같다 — 목록 · 순서 · 이름 · 설명."""
    want = list(roles.SESSION_ROLES)
    assert js["sessionRoles"] == want
    for r in want:
        assert js["label"][r] == roles.ROLE_KO[r], r
        assert js["desc"][r] == roles.ROLE_DESC[r], r
    assert list(js["pick"]) == want                                    # 역할 고르기 칸([+ 세션] · 계획 카드)
    assert js["pick"]["coder"] == "코더 — 코드를 고치거나 만듭니다. 그 코드를 가리키는 문서도 함께 고칩니다"


def test_every_role_has_colors(js):
    """역할마다 배지 색과 네 테마 옷 색이 있다(옷 색은 한 표 + 테마가 덮은 값). 감독도 배지 색이 있다."""
    for r in [*roles.SESSION_ROLES, "foreman"]:
        assert js["color"].get(r, "").startswith("#"), f"ROLE_COLOR에 {r}"
        assert js["cloth"].get(r, "").startswith("#"), f"ROLE_CLOTH에 {r}"
        for t in THEMES:
            assert js["themes"][t].get(r, "").startswith("#"), f"{t} 테마 옷 색에 {r}"
