"""코더 지시문에 「고친 코드의 문서도 함께」(11-17 사용자 지시 21). 코더 역할만. 디자이너, 조사, 서기, 관리자에게는 붙지 않는다."""

import asyncio
import subprocess
from pathlib import Path

import pytest

from bridge import docrefs, foreman, handoff, roles
from tests.test_scribe_two_paths import _hm

ROOT = Path(__file__).resolve().parent.parent
USER = ("네가 고친 코드를 가리키는 문서가 있으면 그 문서도 함께 고친다. 어느 문서가 걸리는지는 거꾸로 찾는 도구로 확인한다. "
        "문서를 고칠 수 없는 이유가 있으면 무엇이 걸리는지 보고한다.")


def test_rule_is_user_sentence_and_coder_only():
    assert roles.CODER_DOCS_RULE == USER
    assert roles.DOCS_RULE_ROLES == {"coder"}
    assert "문서도 함께 고칩니다" in roles.ROLE_DESC["coder"]
    for r in ("designer", "inspector", "scribe", "manager", None):
        assert docrefs.prompt_block(ROOT, r) == "", r


def test_prompt_block_foreman_repo():
    b = docrefs.prompt_block(ROOT, "coder")
    assert USER in b and "`.venv/bin/python tools/docs.py refs --range main...HEAD --unfixed`" in b
    assert "docrefs.py" not in b and "코드로 걸린 문서 N, 안 고침 M" in b        # 3단계: 이름 하나, 카드 줄은 나눠 센다
    assert docrefs.TONE_FOREMAN in b and "docs/style_guide.md" in b and "경어체" in b
    assert "docs/manuscript_rules.md" in b                    # 11-17 원고 쓰는 기준 한 벌
    bare = b.replace("`—`", "").replace("`·`", "")            # 기준 줄이 이름을 대는 기호(백틱 안)만 뺀다
    assert "—" not in bare and "·" not in bare                # 새 글에 em dash, 가운뎃점을 쓰지 않는다


def test_prompt_block_other_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    b = docrefs.prompt_block(tmp_path, "coder")
    assert USER in b and "tools/docs.py --repo . refs --range main...HEAD" in b
    assert docrefs.TONE_OTHER in b and docrefs.TONE_FOREMAN not in b


@pytest.mark.parametrize("role,has", [("coder", True), ("designer", False), ("inspector", False)])
def test_finish_spawn_appends_rule_to_first_prompt(monkeypatch, role, has):
    m = _hm(monkeypatch)
    m.sessions_dir = "/nonexistent"
    sent = []

    async def deliver(cc, body, **kw):
        sent.append(body)
        return {"delivered": True}

    async def nosleep(_):
        return None
    monkeypatch.setattr(handoff, "deliver", deliver)
    monkeypatch.setattr(handoff.asyncio, "sleep", nosleep)
    asyncio.run(m._finish_spawn("cc-x", "%1", str(ROOT), None, "t", None, cc="c", pid=1, role=role, first_prompt="일을 한다"))
    [body] = sent
    assert body.startswith("일을 한다")
    assert (USER in body) is has


def test_foreman_instructions_coder_line():
    ins = foreman.INSTRUCTIONS
    assert '"coder"(코더): 고친 코드를 가리키는 문서(docs, 노션 원고, 포트폴리오)도 그 코더 세션이' in ins
    assert "first_prompt에 옮기지 마라" in ins and "디자이너, 조사에는 이 규칙이 없다" in ins
