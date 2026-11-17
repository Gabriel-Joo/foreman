"""비밀값 파일이 가리기(bridge/mask.py) 대상에서 빠지면 깨지는 시험(11-17).

11-17 전에는 가리기 목록을 손으로 적어 .env.notion, .env.project_tokens가 빠져 있었다.
이 시험은 실제 비밀값을 출력하지 않는다. 진짜 파일은 이름과 키 이름(= 왼쪽)만 보고, 가짜 값은 tmp에 만든다.
"""

import re

import pytest

from bridge.config import REPO
from bridge.mask import EXAMPLE_SUFFIX, SECRET_KEY, Masker, configured_secret_files, secret_env_files

# 코드와 설정이 이름으로 여는 비밀값 파일을 찾는 꼴(.env.example 같은 예시는 뺀다)
ENV_NAME = re.compile(r"\.env(?:\.[A-Za-z0-9_]+)+")
SCAN = ("bridge/**/*.py", "tools/**/*.py", "config/*.toml")
# 비밀값 파일에 있어도 비밀이 아닌 키(가리지 않는 것이 맞다). 새 키가 이 목록에도 SECRET_KEY에도 없으면 시험이 깨진다
NON_SECRET_KEYS = {"MYSQL_DATABASE", "MYSQL_USER", "DEBUG_ENDPOINTS", "TELEGRAM_CHAT_ID"}


def _code_env_names() -> set[str]:
    names: set[str] = set()
    for pat in SCAN:
        for f in REPO.glob(pat):
            if ".venv" in f.parts or "node_modules" in f.parts:
                continue
            for m in ENV_NAME.finditer(f.read_text(encoding="utf-8", errors="replace")):
                n = m.group(0)
                if not EXAMPLE_SUFFIX.search(n):
                    names.add(n)
    return names


def test_selection_picks_every_env_but_examples(tmp_path):
    for n in (".env", ".env.db", ".env.notion", ".env.project_tokens", ".env.new_one", ".env.db.example",
              ".env.bridge.sample"):
        (tmp_path / n).write_text("X=1\n", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "notify.toml").write_text('[telegram]\nenv_file = "sub/tg.env"\n', encoding="utf-8")
    (tmp_path / "config" / "tokens.toml").write_text('[project_tokens]\nfile = ".env.project_tokens"\n', encoding="utf-8")
    got = {p.relative_to(tmp_path).as_posix() for p in secret_env_files(tmp_path)}
    assert got == {".env", ".env.db", ".env.notion", ".env.project_tokens", ".env.new_one", "sub/tg.env"}


def test_new_files_values_are_masked(tmp_path):
    # 형식 패턴에 걸리지 않는 가짜 값(접두어 없음). 정확한 값 가리기로만 잡혀야 한다
    (tmp_path / ".env.notion").write_text("NOTION_TOKEN=FakeNotionValue9x7q2w\n", encoding="utf-8")
    (tmp_path / ".env.project_tokens").write_text(
        "FOREMAN_TOKEN_RUNSHOES=fakeProj-Tok_0a9b8c7d6e\nFOREMAN_TOKEN_PETMINT_RAG_CHATBOT='fakeQuoted_11223344'\n",
        encoding="utf-8")
    m = Masker(secret_env_files(tmp_path))
    out = m.text("a FakeNotionValue9x7q2w b fakeProj-Tok_0a9b8c7d6e c fakeQuoted_11223344")
    assert out == ("a «masked:NOTION_TOKEN» b «masked:FOREMAN_TOKEN_RUNSHOES» "
                   "c «masked:FOREMAN_TOKEN_PETMINT_RAG_CHATBOT»")


def test_code_named_env_files_would_be_selected(tmp_path):
    """bridge, tools, config가 이름으로 여는 .env 파일이 맨 위에 있으면 모두 가리기 대상이 되는가."""
    names = _code_env_names()
    assert {".env.db", ".env.bridge", ".env.telegram", ".env.notion", ".env.project_tokens"} <= names
    for n in names:
        (tmp_path / n).write_text("X=1\n", encoding="utf-8")
    got = {p.name for p in secret_env_files(tmp_path)}
    assert names <= got, f"가리기 대상에서 빠진 비밀값 파일: {sorted(names - got)}"


def test_real_repo_secret_files_are_covered():
    """저장소에 실제로 있는 비밀값 파일(이름만 본다)과 config가 가리키는 파일이 모두 가리기 대상인가."""
    covered = set(secret_env_files())
    present = {p for p in REPO.glob(".env*") if p.is_file() and not EXAMPLE_SUFFIX.search(p.name)}
    missing = sorted(p.name for p in present - covered)
    assert not missing, f"가리기 대상에서 빠진 비밀값 파일: {missing}"
    for p in configured_secret_files():
        assert p in covered, f"config가 가리키는 비밀값 파일이 빠짐: {p.name}"


def test_real_secret_keys_are_secret_named():
    """실제 비밀값 파일의 키 이름이 SECRET_KEY에 걸리는가. 값은 = 왼쪽만 잘라 버리고 남기지 않는다."""
    files = [p for p in secret_env_files() if p.exists()]
    if not files:
        pytest.skip("비밀값 파일이 없는 작업 폴더")
    unmatched: list[str] = []
    for p in files:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.partition("=")[0].strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if not SECRET_KEY.search(key) and key not in NON_SECRET_KEYS:
                unmatched.append(f"{p.name}:{key}")
    assert not unmatched, f"비밀 키 판정(SECRET_KEY)에 안 걸리는 키(값이 안 가려진다): {unmatched}"
