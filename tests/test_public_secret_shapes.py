"""공개되는 글(log, notion, portfolio, docs)에 비밀값 꼴이 들어 있으면 깨지는 시험(11-17).

이 저장소는 Public이다. 실제 비밀값과 비교하지 않고 꼴로만 본다.
걸린 줄은 값을 내지 않고 파일 이름, 줄 번호, 꼴 이름만 낸다.
"""

import re

from bridge.config import REPO
from bridge import mask

PUBLIC_DIRS = ("log", "notion", "portfolio", "docs")

# 공개 글용 키=값 꼴. mask.py의 키=값 패턴(DB에 넣기 전, 넓게 가린다)을 그대로 쓰면 11-17 기준 5줄이 오탐이었다:
# 소문자 코드 이름(password=식, token=경로, token_output = 식)과 한글 예시값, 이미 가린 «masked».
# 실제 비밀값 파일의 키는 모두 대문자 환경변수 이름이고 값은 ASCII 토큰 글자라서 그 꼴로 좁힌다.
# 값 길이 8은 mask.MIN_EXACT와 같다. /로 시작하는 값(경로)은 뺀다
PUBLIC_KV = re.compile(
    r"\b[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|_PWD)[A-Z0-9_]*\s*[=:]\s*['\"]?(?!/)[A-Za-z0-9._~+/=-]{8,}"
)

# mask.py의 형식 패턴 전부(여기에 Notion ntn_, secret_ 꼴이 들어 있다)에 이름을 붙이고, 키=값만 위 꼴로 바꾼다
SHAPES: list[tuple[str, re.Pattern[str]]] = []
for _pat, _rep in mask._PATTERNS:
    if _rep.startswith("«"):
        SHAPES.append((_rep, _pat))
    elif "Bearer" in _pat.pattern:
        SHAPES.append(("bearer", _pat))
    else:
        SHAPES.append(("key=value", PUBLIC_KV))
assert [n for n, _ in SHAPES].count("key=value") == 1, "mask.py 패턴이 바뀌었다. 이 표를 맞춘다"
# 프로젝트 토큰(.env.project_tokens)은 접두어 없는 token_urlsafe(32) 값이라 키와 붙은 대입 꼴로만 잡힌다:
# 위 key=value 꼴이 FOREMAN_TOKEN_<프로젝트>=<값>을 잡는다


def _public_files():
    for d in PUBLIC_DIRS:
        root = REPO / d
        if root.is_dir():
            yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def scan(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        for name, pat in SHAPES:
            if pat.search(line):
                hits.append((i, name))
    # 여러 줄에 걸치는 개인키 블록
    for name, pat in SHAPES:
        if "PRIVATE KEY" in pat.pattern:
            for m in pat.finditer(text):
                hits.append((text.count("\n", 0, m.start()) + 1, name))
    return hits


def test_scan_catches_fake_shapes():
    fake = "\n".join([
        "bot 1234567890:" + "A" * 35,
        "notion ntn_" + "a1" * 23,
        "old notion secret_" + "B2" * 22,
        "export FOREMAN_TOKEN_RUNSHOES=fakeProjTok_123456",
        "curl -H 'Authorization: Bearer abcdefghijklmnop1234'",
        "key sk-ant-" + "x" * 24,
    ])
    names = {n for _, n in scan(fake)}
    assert {"«masked:telegram-bot-token»", "«masked:notion-token»", "key=value", "bearer",
            "«masked:anthropic-key»"} <= names
    assert len({i for i, _ in scan(fake)}) == 6


def test_scan_ignores_plain_words():
    ok = "\n".join([
        "secret_key 같은 낱말, ntn_ 접두어 설명, NOTION_TOKEN을 넣는다",
        "T=$(sed -n 's/^FOREMAN_TOKEN_RUNSHOES=//p' .env.project_tokens)",
        "Authorization: Bearer $T",
        "max_tokens: 4096",
        # 11-17 실제 오탐 꼴(값은 바꿈)
        "password=s.mysql_password",
        "token=/dev/null",
        "token_output = GREATEST(a, b)",
        "DB_PASSWORD=예시값입니다만",
        "MY_API_KEY=«masked»",
    ])
    assert scan(ok) == []


def test_public_text_has_no_secret_shapes():
    found: list[str] = []
    for p in _public_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue   # 그림 같은 이진 파일
        for line_no, name in scan(text):
            found.append(f"{p.relative_to(REPO).as_posix()}:{line_no} {name}")
    assert not found, "공개되는 글에 비밀값 꼴이 있습니다(값은 출력하지 않음):\n" + "\n".join(found)
